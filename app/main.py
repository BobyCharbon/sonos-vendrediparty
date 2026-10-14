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

from . import games
from .party import HOST_ID, MODES, PartyStore, end_of_requests, fair_moves, insert_position
from .push import Push, valid_subscription
from .security import Limiter
from .sonos import Sonos, seconds
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
push = Push(DATA_DIR, PUBLIC_URL)

@contextlib.asynccontextmanager
async def lifespan(app):
    threading.Thread(target=watch_sonos, daemon=True).start()
    yield


app = FastAPI(title="Vendredi Party", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Un seul ajout/suppression à la fois : la position d'insertion dépend de l'état de la file.
queue_lock = threading.Lock()


# --- Cache de l'état Sonos (beaucoup de téléphones interrogent en même temps) ---

_snap = {"at": 0.0, "data": None, "fingerprint": None, "version": 0, "current": None}
_snap_lock = threading.Lock()


def notify_guest(guest_id: str, payload: dict):
    subs = store.session.push.get(guest_id)
    if subs:
        push.send(list(subs), payload, on_gone=lambda sub: store.remove_push(sub["endpoint"]))


def notify_admin(payload: dict):
    if store.session.admin_push:
        push.send(list(store.session.admin_push), payload, on_gone=lambda sub: store.remove_push(sub["endpoint"]))


def track_changed(data: dict, done: list):
    """Le titre en cours a changé : historique de la soirée, et notification à l'invité qui l'a demandé."""
    cur = data["current"]
    key = (cur["pos"], cur["track_id"] or cur["title"]) if cur else None
    if key == _snap["current"]:
        return
    _snap["current"] = key
    if cur is None:
        return
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    last = store.session.played[-1] if store.session.played else {}
    # Après un redémarrage du serveur, le titre en cours est peut-être déjà dans l'historique.
    if (last.get("track_id"), last.get("title")) != (cur["track_id"], cur["title"]):
        store.track_started({"track_id": cur["track_id"], "title": cur["title"], "artist": cur["artist"],
                             "art": cur["art"], "by": names.get(cur["track_id"])})
    for r in done:
        if r.track_id == cur["track_id"]:
            notify_guest(r.guest_id, {"title": "🎶 Ton titre passe !", "body": f"{r.title} · {r.artist}",
                                      "url": "/", "tag": "now-playing"})


def snapshot(force: bool = False) -> dict:
    s = store.session
    with _snap_lock:
        if not force and _snap["data"] and time.time() - _snap["at"] < 3:
            return _snap["data"]
        data = sonos.snapshot(s.room_uid)
        done = store.reconcile({t["track_id"] for t in data["upcoming"] if t["track_id"]})
        track_changed(data, done)
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


# Admin : 3 essais, puis 15 s d'attente entre chaque essai (le verrou global reste contre les attaques réparties).
admin_limiter = Limiter(per_ip=3, ip_lock=15, global_max=30, global_window=900, global_lock=900, cooldown=True)
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
    playlist: str | None = None  # lancer aussi une playlist (sinon : ce qui joue déjà)


@app.post("/api/admin/start", dependencies=[Depends(require_admin)])
def admin_start(body: Start):
    if body.mode not in MODES:
        raise HTTPException(400, "Mode inconnu")
    room = next((r for r in sonos.rooms() if r["uid"] == body.room_uid), None)
    if room is None:
        raise HTTPException(404, "Pièce introuvable")
    store.start(room["uid"], room["name"], body.mode)
    _snap["data"] = None
    if body.playlist:
        launch_playlist(body.playlist)
    return admin_state()


@app.get("/api/admin/playlists", dependencies=[Depends(require_admin)])
def admin_playlists():
    try:
        return sonos.playlists()
    except Exception as e:
        raise HTTPException(502, f"Impossible de lire les playlists Sonos : {e}")


def launch_playlist(playlist_id: str):
    with queue_lock:
        snap = snapshot(force=True)
        pending = {r.track_id: r for r in store.pending()}
        # Demandes des invités encore à venir, dans l'ordre de la file : elles passeront en premier.
        keep = [(t["track_id"], t["title"]) for t in snap["upcoming"] if t["track_id"] in pending]
        # Pas de lecture de l'état Sonos pendant le remplacement : la file vide ferait croire les demandes jouées.
        with _snap_lock:
            try:
                sonos.launch_playlist(store.session.room_uid, playlist_id, keep)
            except LookupError as e:
                raise HTTPException(404, str(e))
            except Exception as e:
                raise HTTPException(502, f"Sonos a refusé la playlist : {e}")
            finally:
                _snap["data"] = None
        # Les demandes qui n'étaient plus dans la file (ou sans titre Spotify) ne reviendront pas.
        kept = {tid for tid, _ in keep}
        for r in store.pending():
            if r.track_id not in kept:
                r.status = "removed"
        store.save()


class PlaylistRef(BaseModel):
    id: str


SPOTIFY_PLAYLIST_RE = re.compile(r"(?:open\.spotify\.com/(?:intl-[a-z-]+/)?playlist/|spotify:playlist:)([A-Za-z0-9]{22})")


def spotify_playlist_title(playlist_id: str) -> str:
    # oEmbed : public, sans compte, et marche aussi pour les playlists éditoriales de Spotify.
    try:
        r = httpx.get("https://open.spotify.com/oembed", params={"url": f"https://open.spotify.com/playlist/{playlist_id}"}, timeout=8)
        r.raise_for_status()
        return r.json().get("title") or "Playlist Spotify"
    except Exception:
        return "Playlist Spotify"


class TopPlaylist(BaseModel):
    action: str  # add | remove | up
    id: str = ""
    url: str = ""


@app.post("/api/admin/playlists/top", dependencies=[Depends(require_admin)])
def admin_top_playlists(body: TopPlaylist):
    """Liste des playlists favorites (Réglages) : ajout par lien Spotify ou depuis Sonos, retrait, ordre."""
    top = store.session.top_playlists
    if body.action == "add":
        if body.url:
            m = SPOTIFY_PLAYLIST_RE.search(body.url)
            if not m:
                raise HTTPException(400, "Colle le lien d'une playlist Spotify (Partager → Copier le lien)")
            entry = {"id": f"spotify:playlist:{m.group(1)}", "title": spotify_playlist_title(m.group(1))}
        else:
            item = next((p for p in sonos.playlists() if p["id"] == body.id), None)
            if item is None:
                raise HTTPException(404, "Playlist introuvable")
            entry = {"id": item["id"], "title": item["title"].strip()}
        if any(p["id"] == entry["id"] for p in top):
            raise HTTPException(409, "Cette playlist est déjà dans la liste")
        top.append(entry)
    elif body.action == "remove":
        store.session.top_playlists = [p for p in top if p["id"] != body.id]
    elif body.action == "up":
        i = next((i for i, p in enumerate(top) if p["id"] == body.id), 0)
        if i > 0:
            top[i - 1], top[i] = top[i], top[i - 1]
    else:
        raise HTTPException(400, "Action inconnue")
    store.save()
    return admin_state()


@app.post("/api/admin/playlist", dependencies=[Depends(require_admin)])
def admin_playlist(body: PlaylistRef):
    """Remplace la file par une playlist Sonos, en aléatoire avec fondu enchaîné."""
    require_active()
    if not (body.id.startswith(("sq:", "fav:")) or re.fullmatch(r"spotify:playlist:[A-Za-z0-9]{22}", body.id)):
        raise HTTPException(400, "Playlist invalide")
    launch_playlist(body.id)
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


# Suppressions faites par l'hôte, annulables pendant une minute : jeton -> titres à remettre.
_undo: dict[str, dict] = {}


def undo_token(items: list[dict], request_ids: list[str]) -> str | None:
    items = [it for it in items if it["track_id"]]  # seuls les titres Spotify peuvent être remis
    if not items:
        return None
    for token in [t for t, u in _undo.items() if time.time() - u["at"] > 60]:
        del _undo[token]
    token = secrets.token_hex(8)
    _undo[token] = {"items": items, "request_ids": request_ids, "at": time.time()}
    return token


def remove_requests(reqs) -> str | None:
    """Retire des demandes de la file Sonos (de la fin vers le début pour garder les positions valides).
    Renvoie un jeton pour annuler."""
    removed = []
    with queue_lock:
        snap = snapshot(force=True)
        positions = {t["track_id"]: t["pos"] for t in reversed(snap["upcoming"]) if t["track_id"]}
        for req in sorted(reqs, key=lambda r: positions.get(r.track_id, 0), reverse=True):
            if req.track_id in positions:
                sonos.remove_at(store.session.room_uid, positions[req.track_id])
                removed.append({"pos": positions[req.track_id], "track_id": req.track_id, "title": req.title})
            req.status = "removed"
        store.save()
        _snap["data"] = None
    return undo_token(removed, [r.id for r in reqs])


@app.post("/api/admin/remove", dependencies=[Depends(require_admin)])
def admin_remove(body: Remove):
    require_active()
    req = next((r for r in store.pending() if r.id == body.request_id), None)
    if req is None:
        raise HTTPException(404, "Demande introuvable ou déjà jouée")
    return {**admin_state(), "undo": remove_requests([req])}


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


class Rename(BaseModel):
    guest_id: str
    name: str


@app.post("/api/admin/rename", dependencies=[Depends(require_admin)])
def admin_rename(body: Rename):
    """L'hôte renomme un invité (la page de l'invité reprend ce nom)."""
    store.rename_guest(body.guest_id, clean_name(body.name))
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
    return {**admin_state(), "undo": remove_requests([r for r in store.pending() if r.guest_id == body.guest_id])}


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
        "top_playlists": s.top_playlists,
        "games": [games.summary(g) for g in s.games.values()],
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


def etas(snap: dict) -> list[int | None]:
    """Secondes avant le début de chaque titre à venir (None si inconnu ou si la lecture est en pause)."""
    upcoming = snap["upcoming"]
    left = None
    if snap["state"] in ("PLAYING", "TRANSITIONING"):
        duration, position = seconds(snap["now"]["duration"]), seconds(snap["now"]["position"])
        if duration and position is not None:
            left = max(0, duration - position)
    # Titres ajoutés par lien Spotify : Sonos ne connaît pas toujours leur durée, Spotify si.
    known = {r.track_id: r.duration_ms // 1000 for r in store.session.requests if r.duration_ms}
    result = []
    for t in upcoming:
        result.append(left)
        duration = t.get("duration") or known.get(t["track_id"])
        left = left + duration if left is not None and duration else None
    return result


def admin_queue(snap: dict, limit: int = 150) -> list[dict]:
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    return [
        {"pos": t["pos"], "key": track_key(t), "title": t["title"], "artist": t["artist"],
         "art": art_url(t["art"]), "by": names.get(t["track_id"]), "eta": eta}
        for t, eta in zip(snap["upcoming"][:limit], etas(snap))
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
            reqs = [r for r in store.pending() if item["track_id"] and r.track_id == item["track_id"]]
            for r in reqs:
                r.status = "removed"
            store.save()
            undo = undo_token([{"pos": body.pos, "track_id": item["track_id"], "title": item["title"]}], [r.id for r in reqs])
        else:
            raise HTTPException(400, "Action inconnue")
        _snap["data"] = None
    return {**admin_state(), "undo": undo if body.action == "remove" else None}


class UndoRef(BaseModel):
    token: str


@app.post("/api/admin/undo", dependencies=[Depends(require_admin)])
def admin_undo(body: UndoRef):
    """Remet dans la file les titres que l'hôte vient de retirer, à leur place."""
    require_active()
    entry = _undo.pop(body.token, None)
    if entry is None or time.time() - entry["at"] > 60:
        raise HTTPException(404, "Trop tard pour annuler")
    with queue_lock:
        snap = snapshot(force=True)
        cur = snap["current_pos"]
        last = snap["upcoming"][-1]["pos"] if snap["upcoming"] else cur
        # Dans l'ordre croissant : chaque titre retrouve sa position d'origine.
        for it in sorted(entry["items"], key=lambda it: it["pos"]):
            pos = 0 if not cur or it["pos"] > last + 1 else max(cur + 1, it["pos"])
            try:
                sonos.add_spotify_track(store.session.room_uid, it["track_id"], it["title"], pos)
            except Exception as e:
                raise HTTPException(502, f"Sonos a refusé l'ajout : {e}")
            last += 1
        for r in store.session.requests:
            if r.id in entry["request_ids"] and r.status == "removed":
                r.status = "queued"
        store.save()
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


# --- Jeux ---
# Ouverts à tous (sans le code de la musique) : n'importe qui crée une partie et la partage par son code / QR.

GAME_CODE_RE = re.compile(r"^[A-Z]{4}$")
_game_creations: dict[str, list[float]] = {}


def prune_games():
    """Oublie les parties inactives depuis 4 h."""
    old = [c for c, g in store.session.games.items() if time.time() - g["updated_at"] > 4 * 3600]
    for code in old:
        del store.session.games[code]
    if old:
        store.save()


def get_game(code: str) -> dict:
    prune_games()
    g = store.session.games.get(code.upper()) if GAME_CODE_RE.match(code.upper()) else None
    if g is None:
        raise HTTPException(404, "Partie introuvable ou terminée")
    return g


class GameCreate(BaseModel):
    guest_id: str
    name: str
    type: str
    white: bool = True
    plays: bool = True  # l'animateur joue aussi (sinon : maître du jeu, il voit les rôles)


@app.post("/api/games")
def create_game(body: GameCreate, request: Request):
    check_guest_id(body.guest_id)
    ip = client_ip(request)
    if msg := ban_message(body.guest_id, ip):
        raise HTTPException(403, msg)
    # Page publique : 5 créations par adresse toutes les 10 minutes, 30 parties au plus.
    recent = [t for t in _game_creations.get(ip, []) if time.time() - t < 600]
    if len(recent) >= 5 and ip not in PROXY_IPS:
        raise HTTPException(429, "Trop de parties créées, réessaie dans quelques minutes")
    prune_games()
    if len(store.session.games) >= 30:
        raise HTTPException(429, "Trop de parties en cours, réessaie plus tard")
    try:
        g = games.new_game(body.type, body.guest_id, clean_name(body.name), body.white,
                           code=games.new_code(store.session.games), plays=body.plays)
    except games.GameError as e:
        raise HTTPException(400, str(e))
    _game_creations[ip] = recent + [time.time()]
    store.session.games[g["code"]] = g
    store.save()
    return games.view(g, body.guest_id)


@app.get("/api/games/{code}")
def game_state(code: str, guest_id: str = ""):
    return games.view(get_game(code), guest_id)


class GameAction(BaseModel):
    guest_id: str
    name: str = ""
    action: str
    target: str = ""  # identifiant public (pid) d'un joueur
    guess: str = ""


# Actions de l'animateur (créateur de la partie) ; les autres sont ouvertes à tous les joueurs.
HOST_ACTIONS = {"start", "vote_start", "close_vote", "eliminate", "skip_guess", "next", "restart", "remove", "end", "up", "down"}


@app.post("/api/games/{code}")
def game_action(code: str, body: GameAction, request: Request):
    check_guest_id(body.guest_id)
    g = get_game(code)
    a, me = body.action, body.guest_id
    target = games.gid_of(g, body.target)
    if a in HOST_ACTIONS and g["host"] != me:
        raise HTTPException(403, "Seul l'animateur de la partie peut faire ça")
    if a == "join" and (msg := ban_message(me, client_ip(request))):
        raise HTTPException(403, msg)
    if a == "end":
        del store.session.games[g["code"]]
        store.save()
        return None
    actions = {
        "join": (games.join, me, clean_name(body.name) if a == "join" else ""),
        "leave": (games.leave, me), "vote": (games.vote, me, target), "guess": (games.white_guess, me, body.guess),
        "start": (games.start,), "vote_start": (games.start_vote,), "close_vote": (games.close_vote,),
        "eliminate": (games.eliminate, target), "skip_guess": (games.skip_white_guess,),
        "next": (games.next_step,), "restart": (games.restart,), "remove": (games.leave, target),
        "up": (games.move, target, -1), "down": (games.move, target, 1),
    }
    if a not in actions:
        raise HTTPException(400, "Action inconnue")
    fn, *args = actions[a]
    try:
        fn(g, *args)
    except games.GameError as e:
        raise HTTPException(409, str(e))
    g["updated_at"] = time.time()
    if not g["players"] and not g["host"]:
        del store.session.games[g["code"]]
    store.save()
    return games.view(g, me)


@app.get("/qr/game/{code}.svg")
def game_qr(code: str):
    g = get_game(code)
    buf = io.BytesIO()
    segno.make(f"{guest_url()}?game={g['code']}", error="m").save(buf, kind="svg", scale=8, border=2, dark="#111", light="#fff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})


@app.post("/api/admin/games/close", dependencies=[Depends(require_admin)])
def admin_close_game(body: GameAction):
    """L'hôte de la soirée peut fermer n'importe quelle partie (body.target = code)."""
    store.session.games.pop(body.target.upper(), None)
    store.save()
    return admin_state()


# --- Invités ---

def public_sonos(snap: dict, guest_id: str = "") -> dict:
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    mine = {r.track_id: r.id for r in store.pending() if guest_id and r.guest_id == guest_id}

    def view(t, eta):
        return {"title": t["title"], "artist": t["artist"], "art": art_url(t["art"]), "track_id": t["track_id"],
                "by": names.get(t["track_id"]), "rid": mine.get(t["track_id"]), "eta": eta}

    now = snap["now"]
    current_id = (snap["current"] or {}).get("track_id")
    return {
        "state": snap["state"],
        "from_queue": snap["from_queue"],
        "now": {**now, "art": art_url(now["art"]), "by": names.get(current_id), "track_id": current_id},
        "upcoming": [view(t, eta) for t, eta in zip(snap["upcoming"][:25], etas(snap))],
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
        # Prénom connu du serveur (l'hôte a pu le modifier) : la page invité le reprend.
        "name": s.guests.get(guest_id, {}).get("name"),
        # Ses propres messages et les réponses de l'hôte.
        "messages": [{k: m.get(k) for k in ("id", "text", "at", "reply", "reply_at")} for m in store.messages_of(guest_id)] if guest_id else [],
        # Déjà passés (le plus récent d'abord, sans le titre en cours) : pour les retrouver sur Spotify.
        "played": [{**p, "art": art_url(p["art"])} for p in reversed(s.played[-16:-1])],
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
    notify_admin({"title": f"💬 {name}", "body": text, "url": "/admin#settings", "tag": "message"})
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


@app.get("/api/push/key", dependencies=[Depends(require_viewer)])
def push_key():
    return {"key": push.public_key}


class PushSubscribe(BaseModel):
    guest_id: str = ""
    subscription: dict


def checked_subscription(sub: dict) -> dict:
    if not valid_subscription(sub):
        raise HTTPException(400, "Abonnement invalide")
    return sub


@app.post("/api/push/subscribe", dependencies=[Depends(require_guest)])
def push_subscribe(body: PushSubscribe):
    """L'invité veut être prévenu quand son titre passe."""
    check_guest_id(body.guest_id)
    store.add_push(body.guest_id, checked_subscription(body.subscription))
    return {"ok": True}


@app.post("/api/admin/push/subscribe", dependencies=[Depends(require_admin)])
def admin_push_subscribe(body: PushSubscribe):
    """L'hôte veut être prévenu des nouveaux messages."""
    store.add_push(None, checked_subscription(body.subscription))
    return {"ok": True}


class PushUnsubscribe(BaseModel):
    endpoint: str


@app.post("/api/push/unsubscribe", dependencies=[Depends(require_viewer)])
def push_unsubscribe(body: PushUnsubscribe):
    store.remove_push(body.endpoint)
    return {"ok": True}


@app.get("/api/events")
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


@app.get("/sw.js")
def service_worker():
    # À la racine du site : le service worker couvre la page invités et l'admin.
    return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers=NO_CACHE)
