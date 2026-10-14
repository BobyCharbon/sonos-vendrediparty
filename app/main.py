import asyncio
import contextlib
import hashlib
import io
import hmac
import os
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import segno
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .party import HOST_ID, MODES, PartyStore, end_of_requests, fair_moves, insert_position
from .security import Limiter
from .sonos import Sonos
from .spotify import Spotify

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
ADMIN_PIN = os.environ.get("ADMIN_PIN", "")
# Adresse de la page invités encodée dans le QR code (avec ?pin=<code>).
PUBLIC_URL = "https://party.bobycharbon.ch"
STATIC = Path(__file__).parent / "static"

# Proxies de confiance (même variable qu'uvicorn) : leur IP n'identifie personne.
PROXY_IPS = {ip.strip() for ip in os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1").split(",") if ip.strip()}
store = PartyStore(DATA_DIR / "session.json", ignored_ips=PROXY_IPS)
sonos = Sonos(os.environ.get("SONOS_IP") or None)
spotify = (
    Spotify(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"], os.environ.get("SPOTIFY_MARKET", "CH"))
    if os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")
    else None
)

@contextlib.asynccontextmanager
async def lifespan(app):
    threading.Thread(target=watch_sonos, daemon=True).start()
    yield


app = FastAPI(title="Vendredi Party", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Un seul ajout/suppression à la fois : la position d'insertion dépend de l'état de la file.
queue_lock = threading.Lock()


# --- Cache de l'état Sonos (beaucoup de téléphones interrogent en même temps) ---

_snap = {"at": 0.0, "data": None, "fingerprint": None, "version": 0}
_snap_lock = threading.Lock()


def snapshot(force: bool = False) -> dict:
    s = store.session
    with _snap_lock:
        if not force and _snap["data"] and time.time() - _snap["at"] < 3:
            return _snap["data"]
        data = sonos.snapshot(s.room_uid)
        store.reconcile({t["track_id"] for t in data["upcoming"] if t["track_id"]})
        # Le Sonos a changé (titre, file, lecture, volume) : on prévient les pages ouvertes.
        fingerprint = (data["state"], data["current_pos"], data["from_queue"], data.get("volume"),
                       data["now"]["title"], tuple((t["pos"], t["track_id"], t["title"]) for t in data["upcoming"]))
        if fingerprint != _snap["fingerprint"]:
            _snap["fingerprint"] = fingerprint
            _snap["version"] += 1
        _snap.update(at=time.time(), data=data)
        return data


def watch_sonos():
    """Interroge le Sonos en continu pendant la soirée pour détecter les changements faits ailleurs."""
    while True:
        if store.session.active:
            try:
                snapshot(force=True)
            except Exception:
                pass  # Sonos momentanément injoignable : on réessaie au tour suivant
        time.sleep(1.5)


def events_version() -> str:
    return f"{store.version}.{_snap['version']}"


def require_active():
    if not store.session.active:
        raise HTTPException(409, "Aucune soirée en cours")


# --- Admin ---

def _secret() -> bytes:
    path = DATA_DIR / "secret"
    if not path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
    return path.read_text().encode()


def _token(kind: str, pin: str) -> str:
    # Le cookie dépend du code : changer le code déconnecte tout le monde.
    return hmac.new(_secret(), f"{kind}:{pin}".encode(), hashlib.sha256).hexdigest()


def is_admin(request: Request) -> bool:
    token = request.cookies.get("vp_admin", "")
    return bool(ADMIN_PIN) and hmac.compare_digest(token, _token("admin", ADMIN_PIN))


def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(401, "Code admin requis")


def _guest_cookie(nonce: str) -> str:
    # Un jeton par saisie du code : l'hôte peut déconnecter une personne sans changer le code.
    return f"{nonce}.{_token('guest', store.session.guest_pin + ':' + nonce)}"


def guest_token(request: Request) -> str | None:
    """Jeton de l'invité s'il est valide pour le code en cours et non révoqué."""
    nonce, _, _sig = request.cookies.get("vp_guest", "").partition(".")
    if not nonce or not hmac.compare_digest(request.cookies.get("vp_guest", ""), _guest_cookie(nonce)):
        return None
    return None if nonce in store.session.revoked else nonce


def is_guest(request: Request) -> bool:
    return guest_token(request) is not None


def require_guest(request: Request):
    """Invité ayant saisi le code d'accès en cours. L'admin aussi : un nouveau code déconnecte tout le monde."""
    if not is_guest(request):
        raise HTTPException(401, "Code d'accès requis")


def require_viewer(request: Request):
    """Pochettes et flux en direct : utilisés à la fois par la page invités et par l'admin."""
    if not (is_guest(request) or is_admin(request)):
        raise HTTPException(401, "Code d'accès requis")


def client_ip(request: Request) -> str:
    # Derrière HAProxy, uvicorn remplace l'IP par X-Forwarded-For (FORWARDED_ALLOW_IPS).
    return request.client.host if request.client else ""


def set_auth_cookie(request: Request, response: Response, name: str, value: str, samesite: str):
    response.set_cookie(name, value, httponly=True, samesite=samesite, max_age=86400 * 30,
                        secure=request.url.scheme == "https")


admin_limiter = Limiter(per_ip=5, ip_lock=900, global_max=20, global_window=900, global_lock=900)
guest_limiter = Limiter(per_ip=5, ip_lock=900, global_max=30, global_window=600, global_lock=600)


class Login(BaseModel):
    pin: str


@app.post("/api/admin/login")
def admin_login(body: Login, request: Request, response: Response):
    if not ADMIN_PIN:
        raise HTTPException(503, "ADMIN_PIN n'est pas configuré sur le serveur")
    ip = client_ip(request)
    if msg := admin_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not hmac.compare_digest(body.pin, ADMIN_PIN):
        admin_limiter.fail(ip)
        raise HTTPException(401, "Code incorrect")
    admin_limiter.success(ip)
    set_auth_cookie(request, response, "vp_admin", _token("admin", ADMIN_PIN), "strict")
    return {"ok": True}


@app.post("/api/join")
def guest_join(body: Login, request: Request, response: Response):
    ip = client_ip(request)
    if msg := guest_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not hmac.compare_digest(body.pin.strip(), store.session.guest_pin):
        guest_limiter.fail(ip)
        raise HTTPException(401, "Code incorrect")
    guest_limiter.success(ip)
    set_auth_cookie(request, response, "vp_guest", _guest_cookie(secrets.token_hex(8)), "lax")
    return {"ok": True}


@app.post("/api/admin/pin", dependencies=[Depends(require_admin)])
def admin_new_pin():
    store.regenerate_pin()
    return admin_state()


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie("vp_admin")
    return {"ok": True}


@app.get("/api/admin/rooms", dependencies=[Depends(require_admin)])
def admin_rooms():
    try:
        return sonos.rooms()
    except Exception as e:
        raise HTTPException(502, f"Impossible de joindre les Sonos : {e}")


class Start(BaseModel):
    room_uid: str
    mode: str = "next"


@app.post("/api/admin/start", dependencies=[Depends(require_admin)])
def admin_start(body: Start):
    if body.mode not in MODES:
        raise HTTPException(400, "Mode inconnu")
    room = next((r for r in sonos.rooms() if r["uid"] == body.room_uid), None)
    if room is None:
        raise HTTPException(404, "Pièce introuvable")
    store.start(room["uid"], room["name"], body.mode)
    _snap["data"] = None
    return admin_state()


@app.post("/api/admin/stop", dependencies=[Depends(require_admin)])
def admin_stop():
    store.stop()
    return admin_state()


class Mode(BaseModel):
    mode: str


@app.post("/api/admin/mode", dependencies=[Depends(require_admin)])
def admin_mode(body: Mode):
    if body.mode not in MODES:
        raise HTTPException(400, "Mode inconnu")
    store.session.mode = body.mode
    store.save()
    moved = 0
    if body.mode == "fair" and store.session.active:
        # Remet tout de suite la file actuelle au tour par tour (utile en cas d'abus).
        with queue_lock:
            snap = snapshot(force=True)
            upcoming = [(t["pos"], t["track_id"]) for t in snap["upcoming"]]
            for src, dst in fair_moves(snap["current_pos"], upcoming, store.pending()):
                sonos.move(store.session.room_uid, src, dst)
                moved += 1
            _snap["data"] = None
    return {**admin_state(), "reordered": moved}


class Remove(BaseModel):
    request_id: str


def remove_requests(reqs):
    """Retire des demandes de la file Sonos (de la fin vers le début pour garder les positions valides)."""
    with queue_lock:
        snap = snapshot(force=True)
        positions = {t["track_id"]: t["pos"] for t in reversed(snap["upcoming"]) if t["track_id"]}
        for req in sorted(reqs, key=lambda r: positions.get(r.track_id, 0), reverse=True):
            if req.track_id in positions:
                sonos.remove_at(store.session.room_uid, positions[req.track_id])
            req.status = "removed"
        store.save()
        _snap["data"] = None


@app.post("/api/admin/remove", dependencies=[Depends(require_admin)])
def admin_remove(body: Remove):
    require_active()
    req = next((r for r in store.pending() if r.id == body.request_id), None)
    if req is None:
        raise HTTPException(404, "Demande introuvable ou déjà jouée")
    remove_requests([req])
    return admin_state()


class Ban(BaseModel):
    guest_id: str
    minutes: int | None = None  # None : bannissement sans limite


@app.post("/api/admin/ban", dependencies=[Depends(require_admin)])
def admin_ban(body: Ban):
    if body.minutes is not None and not 1 <= body.minutes <= 24 * 60:
        raise HTTPException(400, "Durée invalide")
    store.ban(body.guest_id, body.minutes)
    return admin_state()


class GuestRef(BaseModel):
    guest_id: str


@app.post("/api/admin/unban", dependencies=[Depends(require_admin)])
def admin_unban(body: GuestRef):
    store.unban(body.guest_id)
    return admin_state()


@app.post("/api/admin/kick", dependencies=[Depends(require_admin)])
def admin_kick(body: GuestRef):
    """Déconnecte un invité : il devra ressaisir le code (ce n'est pas un ban)."""
    store.kick(body.guest_id)
    return admin_state()


@app.post("/api/admin/purge", dependencies=[Depends(require_admin)])
def admin_purge(body: GuestRef):
    """Retire de la file tous les titres en attente d'un invité."""
    require_active()
    remove_requests([r for r in store.pending() if r.guest_id == body.guest_id])
    return admin_state()


class Playback(BaseModel):
    action: str  # play | pause


@app.post("/api/admin/playback", dependencies=[Depends(require_admin)])
def admin_playback(body: Playback):
    require_active()
    if body.action not in ("play", "pause"):
        raise HTTPException(400, "Action inconnue")
    getattr(sonos, body.action)(store.session.room_uid)
    _snap["data"] = None
    return admin_state()


class Volume(BaseModel):
    volume: int


@app.post("/api/admin/volume", dependencies=[Depends(require_admin)])
def admin_volume(body: Volume):
    require_active()
    sonos.set_volume(store.session.room_uid, max(0, min(100, body.volume)))
    _snap["data"] = None
    return {"ok": True}


@app.get("/api/admin/speakers", dependencies=[Depends(require_admin)])
def admin_speakers():
    require_active()
    try:
        return sonos.speakers(store.session.room_uid)
    except Exception as e:
        raise HTTPException(502, f"Impossible de joindre les Sonos : {e}")


class SpeakerGroup(BaseModel):
    uid: str
    join: bool


@app.post("/api/admin/speakers/group", dependencies=[Depends(require_admin)])
def admin_speaker_group(body: SpeakerGroup):
    """Ajoute une enceinte au groupe de la soirée (elle joue la même musique) ou l'en retire."""
    require_active()
    try:
        sonos.group_speaker(store.session.room_uid, body.uid, body.join)
    except KeyError:
        raise HTTPException(404, "Enceinte introuvable")
    _snap["data"] = None
    return sonos.speakers(store.session.room_uid)


class SpeakerVolume(BaseModel):
    uid: str
    volume: int


@app.post("/api/admin/speakers/volume", dependencies=[Depends(require_admin)])
def admin_speaker_volume(body: SpeakerVolume):
    require_active()
    try:
        sonos.set_speaker_volume(body.uid, max(0, min(100, body.volume)))
    except KeyError:
        raise HTTPException(404, "Enceinte introuvable")
    _snap["data"] = None
    return {"ok": True}


@app.post("/api/admin/skip", dependencies=[Depends(require_admin)])
def admin_skip():
    require_active()
    sonos.skip(store.session.room_uid)
    _snap["data"] = None
    return {"ok": True}


def guest_url() -> str:
    return PUBLIC_URL + "/"


@app.get("/api/admin/search", dependencies=[Depends(require_admin)])
def admin_search(q: str):
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    q = q.strip()[:100]
    return spotify.search(q) if len(q) >= 2 else []


class AdminAdd(BaseModel):
    track_id: str
    where: str = "next"  # next : juste après le titre en cours | end : après la dernière demande
    force: bool = False  # ajouter même si le titre est déjà dans la file


@app.post("/api/admin/add", dependencies=[Depends(require_admin)])
def admin_add(body: AdminAdd):
    """L'hôte ajoute un titre : ensuite, ou à la suite des demandes (avant la suite de la playlist)."""
    require_active()
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    if body.where not in ("next", "end") or not re.match(r"^[A-Za-z0-9]{22}$", body.track_id):
        raise HTTPException(400, "Requête invalide")
    track = spotify.track(body.track_id)
    with queue_lock:
        snap = snapshot(force=True)
        if not snap["from_queue"]:
            raise HTTPException(409, "La musique ne joue pas depuis la file Sonos : lance une playlist depuis l'app Sonos.")
        dup = next((i for i, t in enumerate([snap["current"]] + snap["upcoming"]) if t and t["track_id"] == track["id"]), None)
        if dup is not None and not body.force:
            where = "en cours de lecture" if dup == 0 else f"en {dup}ᵉ position"
            raise HTTPException(409, {"duplicate": True, "message": f"« {track['title']} » est déjà dans la file ({where}). L'ajouter quand même ?"})
        if body.where == "next":
            pos = snap["current_pos"] + 1 if snap["current_pos"] else 0
        else:
            upcoming = [(t["pos"], t["track_id"]) for t in snap["upcoming"]]
            pos = end_of_requests(snap["current_pos"], upcoming, store.pending())
        try:
            sonos.add_spotify_track(store.session.room_uid, track["id"], track["title"], pos)
        except Exception as e:
            raise HTTPException(502, f"Sonos a refusé l'ajout : {e}")
        store.add(track, HOST_ID, "Hôte")
        _snap["data"] = None
    return {**admin_state(), "added": track}


@app.get("/api/admin/state", dependencies=[Depends(require_admin)])
def admin_state():
    s = store.session
    result = {
        "guest_pin": s.guest_pin,
        "guest_url": guest_url(),
        "active": s.active,
        "room_uid": s.room_uid,
        "room_name": s.room_name,
        "mode": s.mode,
        "started_at": s.started_at,
        "spotify_configured": spotify is not None,
        "requests": [r.__dict__ for r in reversed(s.requests)],
        "guests": store.guests(),
        "bans": [{"guest_id": g, **b} for g, b in store.active_bans().items()],
        "messages": list(reversed(s.messages)),
    }
    if s.active:
        try:
            snap = snapshot()
            result["sonos"] = {**public_sonos(snap), "volume": snap.get("volume")}
            result["queue"] = admin_queue(snap)
        except Exception as e:
            result["sonos_error"] = str(e)
    return result


def track_key(t: dict) -> str:
    """Identifie un titre de la file, pour vérifier qu'il n'a pas bougé entre l'affichage et l'action."""
    return t["track_id"] or f"{t['title']}|{t['artist']}"


def admin_queue(snap: dict, limit: int = 150) -> list[dict]:
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    return [
        {"pos": t["pos"], "key": track_key(t), "title": t["title"], "artist": t["artist"],
         "art": art_url(t["art"]), "by": names.get(t["track_id"])}
        for t in snap["upcoming"][:limit]
    ]


class QueueAction(BaseModel):
    pos: int
    key: str
    action: str  # next | up | down | play | remove


@app.post("/api/admin/queue", dependencies=[Depends(require_admin)])
def admin_queue_action(body: QueueAction):
    """Modifie n'importe quel titre à venir (invités ou playlist de l'hôte)."""
    require_active()
    uid = store.session.room_uid
    with queue_lock:
        snap = snapshot(force=True)
        upcoming = snap["upcoming"]
        item = next((t for t in upcoming if t["pos"] == body.pos), None)
        if item is None or track_key(item) != body.key:
            raise HTTPException(409, "La file a changé entre-temps, réessaie")
        first, last = snap["current_pos"] + 1, upcoming[-1]["pos"]
        targets = {"next": first, "up": max(first, body.pos - 1), "down": min(last, body.pos + 1)}
        if body.action in targets:
            sonos.move(uid, body.pos, targets[body.action])
        elif body.action == "play":
            sonos.play_at(uid, body.pos)
        elif body.action == "remove":
            sonos.remove_at(uid, body.pos)
            for r in store.pending():
                if item["track_id"] and r.track_id == item["track_id"]:
                    r.status = "removed"
            store.save()
        else:
            raise HTTPException(400, "Action inconnue")
        _snap["data"] = None
    return admin_state()


class Reply(BaseModel):
    id: str
    text: str


@app.post("/api/admin/messages/reply", dependencies=[Depends(require_admin)])
def admin_reply(body: Reply):
    text = body.text.strip()[:300]
    if not text:
        raise HTTPException(400, "Réponse vide")
    if store.reply(body.id, text) is None:
        raise HTTPException(404, "Message introuvable")
    return admin_state()


class MessageAction(BaseModel):
    ids: list[str] | None = None  # None : tous les messages
    action: str  # read | unread | delete


@app.post("/api/admin/messages", dependencies=[Depends(require_admin)])
def admin_messages(body: MessageAction):
    if body.action not in ("read", "unread", "delete"):
        raise HTTPException(400, "Action inconnue")
    ids = set(body.ids) if body.ids is not None else None
    store.update_messages(ids, read=body.action == "read", delete=body.action == "delete")
    return admin_state()


# --- Invités ---

def public_sonos(snap: dict, guest_id: str = "") -> dict:
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    mine = {r.track_id: r.id for r in store.pending() if guest_id and r.guest_id == guest_id}

    def view(t):
        return {"title": t["title"], "artist": t["artist"], "art": art_url(t["art"]),
                "by": names.get(t["track_id"]), "rid": mine.get(t["track_id"])}

    now = snap["now"]
    return {
        "state": snap["state"],
        "from_queue": snap["from_queue"],
        "now": {**now, "art": art_url(now["art"]), "by": names.get((snap["current"] or {}).get("track_id"))},
        "upcoming": [view(t) for t in snap["upcoming"][:25]],
        "upcoming_total": len(snap["upcoming"]),
    }


def art_url(url: str) -> str:
    # Les pochettes Sonos sont servies par l'enceinte : on les relaie pour les téléphones.
    if not url:
        return ""
    m = re.match(r"^(?:https?://[\d.]+:1400)?(/getaa\?.*)$", url)
    return f"/art?p={quote(m.group(1), safe='')}" if m else url


@app.get("/art", dependencies=[Depends(require_viewer)])
def art(p: str):
    if not p.startswith("/getaa?") or not store.session.room_uid:
        raise HTTPException(404)
    try:
        ip = (_snap["data"] or snapshot())["coordinator_ip"]
        r = httpx.get(f"http://{ip}:1400{p}", timeout=8)
        r.raise_for_status()
    except Exception:
        # Le Sonos va parfois chercher la pochette chez Spotify et met trop de temps.
        raise HTTPException(404)
    return Response(r.content, media_type=r.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": "public, max-age=86400"})


def ban_message(guest_id: str, ip: str) -> str | None:
    ban = store.ban_status(guest_id, ip)
    if ban is None:
        return None
    if ban["until"] == 0:
        return "L'hôte t'a retiré l'accès à la file d'attente 🚫"
    minutes = max(1, round((ban["until"] - time.time()) / 60))
    return f"Pause forcée : tu pourras de nouveau ajouter des titres dans {minutes} min ⏳"


@app.get("/api/state", dependencies=[Depends(require_guest)])
def state(request: Request, guest_id: str = ""):
    s = store.session
    if not s.active:
        return {"active": False}
    store.seen(guest_id)
    store.link_token(guest_id, guest_token(request))
    base = {
        "active": True, "room": s.room_name, "blocked": ban_message(guest_id, client_ip(request)),
        # Ses propres messages et les réponses de l'hôte.
        "messages": [{k: m.get(k) for k in ("id", "text", "at", "reply", "reply_at")} for m in store.messages_of(guest_id)] if guest_id else [],
    }
    try:
        return {**base, **public_sonos(snapshot(), guest_id)}
    except Exception:
        return {**base, "error": "Sonos injoignable pour le moment"}


@app.get("/api/search", dependencies=[Depends(require_guest)])
def search(q: str):
    require_active()
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    q = q.strip()[:100]
    if len(q) < 2:
        return []
    return spotify.search(q)


GUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def clean_name(raw: str) -> str:
    name = " ".join(raw.split())[:30]
    if not name:
        raise HTTPException(400, "Indique ton prénom")
    return name


def check_guest_id(guest_id: str):
    if not GUEST_ID_RE.match(guest_id):
        raise HTTPException(400, "Requête invalide")


class Hello(BaseModel):
    guest_id: str
    guest_name: str


@app.post("/api/hello", dependencies=[Depends(require_guest)])
def hello(body: Hello, request: Request):
    """L'invité a saisi son prénom : il apparaît dans l'admin."""
    check_guest_id(body.guest_id)
    store.register_guest(body.guest_id, clean_name(body.guest_name), client_ip(request))
    store.link_token(body.guest_id, guest_token(request))
    store.seen(body.guest_id)
    return {"ok": True}


class Message(BaseModel):
    guest_id: str
    guest_name: str
    text: str


_last_message: dict[str, float] = {}


@app.post("/api/message", dependencies=[Depends(require_guest)])
def send_message(body: Message, request: Request):
    require_active()
    check_guest_id(body.guest_id)
    ip = client_ip(request)
    if msg := ban_message(body.guest_id, ip):
        raise HTTPException(403, msg)
    text = body.text.strip()[:300]
    if not text:
        raise HTTPException(400, "Message vide")
    if time.time() - _last_message.get(body.guest_id, 0) < 15:
        raise HTTPException(429, "Attends quelques secondes avant d'envoyer un autre message")
    unread = sum(1 for m in store.session.messages if m["guest_id"] == body.guest_id and not m["read"])
    if unread >= 3:
        raise HTTPException(429, "L'hôte n'a pas encore lu tes messages, patience 🙂")
    name = clean_name(body.guest_name)
    store.register_guest(body.guest_id, name, ip)
    store.add_message(body.guest_id, name, text)
    _last_message[body.guest_id] = time.time()
    return {"ok": True}


class Enqueue(BaseModel):
    track_id: str
    guest_id: str
    guest_name: str


@app.post("/api/queue", dependencies=[Depends(require_guest)])
def enqueue(body: Enqueue, request: Request):
    require_active()
    ip = client_ip(request)
    if msg := ban_message(body.guest_id, ip):
        raise HTTPException(403, msg)
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    name = clean_name(body.guest_name)
    check_guest_id(body.guest_id)
    if not re.match(r"^[A-Za-z0-9]{22}$", body.track_id):
        raise HTTPException(400, "Requête invalide")
    store.register_guest(body.guest_id, name, ip)

    track = spotify.track(body.track_id)
    s = store.session
    with queue_lock:
        snap = snapshot(force=True)
        if not snap["from_queue"]:
            raise HTTPException(409, "La musique ne joue pas depuis la file Sonos. Demande à l'hôte de la lancer depuis l'app Sonos.")
        in_queue = [snap["current"]] + snap["upcoming"]
        if any(t and t["track_id"] == track["id"] for t in in_queue):
            raise HTTPException(409, "Ce titre est déjà dans la file 🙂")

        upcoming = [(t["pos"], t["track_id"]) for t in snap["upcoming"]]
        pos = insert_position(s.mode, snap["current_pos"], upcoming, store.pending(), body.guest_id)
        try:
            sonos.add_spotify_track(s.room_uid, track["id"], track["title"], pos)
        except Exception as e:
            raise HTTPException(502, f"Sonos a refusé l'ajout : {e}")
        store.add(track, body.guest_id, name, ip)
        _snap["data"] = None
    return {"ok": True, "track": track}


class GuestRemove(BaseModel):
    request_id: str
    guest_id: str


@app.post("/api/queue/remove", dependencies=[Depends(require_guest)])
def guest_remove(body: GuestRemove):
    """Un invité retire un de ses propres titres encore en attente."""
    require_active()
    req = next((r for r in store.pending() if r.id == body.request_id and r.guest_id == body.guest_id), None)
    if req is None:
        raise HTTPException(404, "Titre introuvable ou déjà joué")
    remove_requests([req])
    return {"ok": True}


@app.get("/api/events", dependencies=[Depends(require_viewer)])
async def events(request: Request):
    """Flux SSE : envoie un signal dès que l'état change, la page se rafraîchit aussitôt."""
    async def stream():
        last, last_ping = None, time.time()
        while not await request.is_disconnected():
            version = events_version()
            if version != last:
                last = version
                yield f"data: {version}\n\n"
            elif time.time() - last_ping > 15:
                # Garde la connexion ouverte à travers HAProxy.
                yield ": ping\n\n"
                last_ping = time.time()
            await asyncio.sleep(0.3)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/qr.svg", dependencies=[Depends(require_admin)])
def qr(request: Request):
    # Le code est inclus : scanner le QR suffit pour entrer.
    url = f"{guest_url()}?pin={store.session.guest_pin}"
    buf = io.BytesIO()
    # Fichier SVG autonome (avec xmlns) : svg_inline ne s'affiche pas dans une balise <img>.
    segno.make(url, error="m").save(buf, kind="svg", scale=8, border=2, dark="#111", light="#fff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})


# Les pages et le CSS sont revérifiés à chaque visite : une mise à jour est visible tout de suite.
NO_CACHE = {"Cache-Control": "no-cache"}


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers=NO_CACHE)


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html", headers=NO_CACHE)
