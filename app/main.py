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
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .party import MODES, PartyStore, insert_position
from .sonos import Sonos
from .spotify import Spotify

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
ADMIN_PIN = os.environ.get("ADMIN_PIN", "")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
STATIC = Path(__file__).parent / "static"

store = PartyStore(DATA_DIR / "session.json")
sonos = Sonos(os.environ.get("SONOS_IP") or None)
spotify = (
    Spotify(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"], os.environ.get("SPOTIFY_MARKET", "CH"))
    if os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")
    else None
)

app = FastAPI(title="Vendredi Party")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Un seul ajout/suppression à la fois : la position d'insertion dépend de l'état de la file.
queue_lock = threading.Lock()


# --- Cache de l'état Sonos (beaucoup de téléphones interrogent en même temps) ---

_snap = {"at": 0.0, "data": None}


def snapshot(force: bool = False) -> dict:
    s = store.session
    if not force and _snap["data"] and time.time() - _snap["at"] < 2:
        return _snap["data"]
    data = sonos.snapshot(s.room_uid)
    store.reconcile({t["track_id"] for t in data["upcoming"] if t["track_id"]})
    _snap.update(at=time.time(), data=data)
    return data


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


def _admin_token() -> str:
    return hmac.new(_secret(), ADMIN_PIN.encode(), hashlib.sha256).hexdigest()


def require_admin(request: Request):
    token = request.cookies.get("vp_admin", "")
    if not ADMIN_PIN or not hmac.compare_digest(token, _admin_token()):
        raise HTTPException(401, "Code admin requis")


_failures: dict[str, tuple[int, float]] = {}


class Login(BaseModel):
    pin: str


@app.post("/api/admin/login")
def admin_login(body: Login, request: Request, response: Response):
    if not ADMIN_PIN:
        raise HTTPException(503, "ADMIN_PIN n'est pas configuré sur le serveur")
    ip = request.client.host if request.client else "?"
    count, until = _failures.get(ip, (0, 0))
    if time.time() < until:
        raise HTTPException(429, "Trop d'essais, réessaie dans quelques minutes")
    if not hmac.compare_digest(body.pin, ADMIN_PIN):
        count += 1
        _failures[ip] = (count, time.time() + 300 if count >= 5 else 0)
        raise HTTPException(401, "Code incorrect")
    _failures.pop(ip, None)
    response.set_cookie("vp_admin", _admin_token(), httponly=True, samesite="strict", max_age=86400 * 30)
    return {"ok": True}


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
    return admin_state()


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


@app.post("/api/admin/purge", dependencies=[Depends(require_admin)])
def admin_purge(body: GuestRef):
    """Retire de la file tous les titres en attente d'un invité."""
    require_active()
    remove_requests([r for r in store.pending() if r.guest_id == body.guest_id])
    return admin_state()


@app.post("/api/admin/skip", dependencies=[Depends(require_admin)])
def admin_skip():
    require_active()
    sonos.skip(store.session.room_uid)
    _snap["data"] = None
    return {"ok": True}


@app.get("/api/admin/state", dependencies=[Depends(require_admin)])
def admin_state():
    s = store.session
    result = {
        "active": s.active,
        "room_uid": s.room_uid,
        "room_name": s.room_name,
        "mode": s.mode,
        "started_at": s.started_at,
        "spotify_configured": spotify is not None,
        "requests": [r.__dict__ for r in reversed(s.requests)],
        "guests": store.guests(),
        "bans": [{"guest_id": g, **b} for g, b in store.active_bans().items()],
    }
    if s.active:
        try:
            result["sonos"] = public_sonos(snapshot())
        except Exception as e:
            result["sonos_error"] = str(e)
    return result


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


@app.get("/art")
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


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def ban_message(guest_id: str, ip: str) -> str | None:
    ban = store.ban_status(guest_id, ip)
    if ban is None:
        return None
    if ban["until"] == 0:
        return "L'hôte t'a retiré l'accès à la file d'attente 🚫"
    minutes = max(1, round((ban["until"] - time.time()) / 60))
    return f"Pause forcée : tu pourras de nouveau ajouter des titres dans {minutes} min ⏳"


@app.get("/api/state")
def state(request: Request, guest_id: str = ""):
    s = store.session
    if not s.active:
        return {"active": False}
    blocked = ban_message(guest_id, client_ip(request))
    try:
        return {"active": True, "room": s.room_name, "blocked": blocked, **public_sonos(snapshot(), guest_id)}
    except Exception:
        return {"active": True, "room": s.room_name, "blocked": blocked, "error": "Sonos injoignable pour le moment"}


@app.get("/api/search")
def search(q: str):
    require_active()
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    q = q.strip()[:100]
    if len(q) < 2:
        return []
    return spotify.search(q)


GUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class Enqueue(BaseModel):
    track_id: str
    guest_id: str
    guest_name: str


@app.post("/api/queue")
def enqueue(body: Enqueue, request: Request):
    require_active()
    ip = client_ip(request)
    if msg := ban_message(body.guest_id, ip):
        raise HTTPException(403, msg)
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    name = " ".join(body.guest_name.split())[:30]
    if not name:
        raise HTTPException(400, "Indique ton prénom")
    if not GUEST_ID_RE.match(body.guest_id) or not re.match(r"^[A-Za-z0-9]{22}$", body.track_id):
        raise HTTPException(400, "Requête invalide")

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


@app.post("/api/queue/remove")
def guest_remove(body: GuestRemove):
    """Un invité retire un de ses propres titres encore en attente."""
    require_active()
    req = next((r for r in store.pending() if r.id == body.request_id and r.guest_id == body.guest_id), None)
    if req is None:
        raise HTTPException(404, "Titre introuvable ou déjà joué")
    remove_requests([req])
    return {"ok": True}


@app.get("/qr.svg")
def qr(request: Request):
    url = PUBLIC_URL or str(request.base_url).rstrip("/")
    buf = io.BytesIO()
    # Fichier SVG autonome (avec xmlns) : svg_inline ne s'affiche pas dans une balise <img>.
    segno.make(url + "/", error="m").save(buf, kind="svg", scale=8, border=2, dark="#111", light="#fff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html")
