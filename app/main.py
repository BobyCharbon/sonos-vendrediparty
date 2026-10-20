import asyncio
import contextlib
import hashlib
import io
import hmac
import os
import random
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import segno
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from . import calendar_ics, games, heist, island, links, neon, president, quiz
from .party import HOST_ID, MODES, PartyStore, end_of_requests, fair_moves, insert_position
from .push import Push, valid_subscription
from .security import Limiter
from .sonos import Sonos, seconds
from .spotify import Spotify, SpotifyError, SpotifyUser
from .spotify_player import QUEUE_MANAGED_IN_SPOTIFY, SpotifyPlayer

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
ADMIN_PIN = os.environ.get("ADMIN_PIN", "")
def configured_public_url() -> str:
    # Une adresse propre à chaque déploiement pour les QR et le retour OAuth Spotify.
    # Ne pas reprendre l'ancienne variable PUBLIC_URL, encore locale sur certaines stacks.
    return (os.environ.get("PARTY_PUBLIC_URL") or "https://party.bobycharbon.ch").rstrip("/")


PUBLIC_URL = configured_public_url()
STATIC = Path(__file__).parent / "static"
EVENTS_WEB = Path(os.environ.get("EVENTS_WEB_DIR") or str(Path(__file__).parent / "events-web"))
# Section Événements : en développement (active sur le site de test, « Bientôt » en production).
# L'image Docker de la branche develop est construite avec EVENTS_ENABLED=1, celle de main avec 0.
EVENTS_ENABLED = os.environ.get("EVENTS_ENABLED", "0") == "1"


def build_id() -> str:
    """Empreinte du code déployé (pages, scripts, serveur) : change à chaque mise à jour du site."""
    h = hashlib.sha1()
    for f in sorted(list(STATIC.rglob("*")) + list(Path(__file__).parent.glob("*.py"))):
        if f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


BUILD_ID = build_id()

# Proxies de confiance (même variable qu'uvicorn) : leur IP n'identifie personne.
PROXY_IPS = {ip.strip() for ip in os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1").split(",") if ip.strip()}
store = PartyStore(DATA_DIR / "session.json", ignored_ips=PROXY_IPS)
quiz.STATS_PATH = DATA_DIR / "quiz_stats.json"  # classement général du Quiz, toutes parties confondues
sonos = Sonos(os.environ.get("SONOS_IP") or None)
spotify = (
    Spotify(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"], os.environ.get("SPOTIFY_MARKET", "CH"))
    if os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")
    else None
)
push = Push(DATA_DIR, PUBLIC_URL)
# Compte Spotify de l’hôte : Sonos via Spotify Connect ou téléphone à l’extérieur.
spotify_user = (SpotifyUser(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"], DATA_DIR / "spotify_user.json",
                            PUBLIC_URL + "/api/spotify/callback") if spotify else None)
spotify_player = SpotifyPlayer(spotify_user, spotify, store, sonos) if spotify else None


def spotify_queue() -> bool:
    return store.session.source in ("spotify", "spotify_sonos")


def player():
    """File Spotify des nouvelles soirées, ou file Sonos native des anciennes sessions."""
    if spotify_queue():
        if spotify_player is None:
            raise HTTPException(503, "Spotify n'est pas configuré sur le serveur")
        return spotify_player
    return sonos

@contextlib.asynccontextmanager
async def lifespan(app):
    threading.Thread(target=watch_sonos, daemon=True).start()
    yield


app = FastAPI(title="Vendredi Party", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
# Compression : les pages et scripts pèsent environ 4 fois moins sur le réseau (le flux temps réel n'est pas compressé).
app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=6)


@app.exception_handler(SpotifyError)
async def spotify_error_response(request: Request, error: SpotifyError):
    return JSONResponse(status_code=502, content={"detail": str(error)})

# Un seul ajout/suppression à la fois : la position d'insertion dépend de l'état de la file.
queue_lock = threading.Lock()


# --- Cache de l'état Sonos (beaucoup de téléphones interrogent en même temps) ---

_snap = {"at": 0.0, "data": None, "fingerprint": None, "version": 0, "current": None}
_snap_lock = threading.Lock()


def notify_guest(guest_id: str, payload: dict):
    subs = store.session.push.get(guest_id)
    if subs:
        push.send(list(subs), payload, on_gone=lambda sub: store.remove_push(sub["endpoint"]))


def notify_admin(payload: dict, kind: str = "messages"):
    """kind : « messages » ou « games », selon ce que l'hôte a choisi de recevoir."""
    if store.session.admin_notify.get(kind, kind == "messages") and store.session.admin_push:
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
    if spotify_queue():
        # La file renvoyée par Spotify peut être partielle ou momentanément en retard.
        # Seul un démarrage observé prouve qu'une demande a été jouée (une occurrence).
        req = next((r for r in store.pending() if r.track_id == cur["track_id"]), None)
        if req:
            req.status = "played"
            store.save()
            done = [req]
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
        data = player().snapshot(s.room_uid)
        done = [] if spotify_queue() else store.reconcile({t["track_id"] for t in data["upcoming"] if t["track_id"]})
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
        time.sleep(5 if spotify_queue() else 1.5)


# Version de chaque partie (en mémoire) : un téléphone ne recharge sa partie que si elle a changé.
game_versions: dict[str, int] = {}


def save_games(*codes: str):
    """Enregistre un changement de partie sans faire recharger la musique de tous les invités."""
    for c in codes:
        if c:
            game_versions[c] = game_versions.get(c, 0) + 1
    store.save(notify=False)


def games_stamp() -> str:
    return ",".join(f"{c}:{game_versions.get(c, 0)}" for c in sorted(store.session.games))


def events_version() -> str:
    # « musique|parties » : chaque page ne recharge que ce qui la concerne.
    return f"{store.version}.{_snap['version']}|{games_stamp()}"


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


class PinChoice(BaseModel):
    pin: str | None = None  # None : code tiré au hasard


@app.post("/api/admin/pin", dependencies=[Depends(require_admin)])
def admin_new_pin(body: PinChoice | None = None):
    """Nouveau code de la musique : au hasard, ou celui que l'hôte choisit (déconnecte tous les invités)."""
    pin = (body.pin or "").strip() if body else ""
    if pin:
        if not re.fullmatch(r"[0-9]{4}", pin):
            raise HTTPException(400, "Le code doit faire exactement 4 chiffres")
        if pin == store.session.guest_pin:
            raise HTTPException(409, "C'est déjà le code actuel")
        if pin in store.session.games:
            raise HTTPException(409, "Ce code est utilisé par une partie de jeu en cours : choisis-en un autre")
    store.regenerate_pin(pin or None)
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
    room_uid: str = ""
    mode: str = "next"
    source: str = "spotify_sonos"  # spotify_sonos (maison) | spotify (extérieur)
    playlist: str | None = None  # lancer aussi une playlist (sinon : ce qui joue déjà)


@app.post("/api/admin/start", dependencies=[Depends(require_admin)])
def admin_start(body: Start):
    if body.mode not in MODES:
        raise HTTPException(400, "Mode inconnu")
    if body.source == "spotify":
        if not (spotify_user and spotify_user.connected):
            raise HTTPException(409, "Connecte d'abord ton compte Spotify (Réglages)")
        store.start("spotify", "Spotify · ton téléphone", body.mode, source="spotify")
        _snap["data"] = None
        return admin_state()
    if body.source not in ("sonos", "spotify_sonos"):
        raise HTTPException(400, "Source inconnue")
    if not (spotify_user and spotify_user.connected):
        raise HTTPException(409, "Connecte d'abord ton compte Spotify (Réglages)")
    room = next((r for r in sonos.rooms() if r["uid"] == body.room_uid), None)
    if room is None:
        raise HTTPException(404, "Pièce introuvable")
    device = ((spotify_user.playback() or {}).get("device") or {})
    expected = room.get("spotify_name", room["name"])
    if not device.get("id") or device.get("name", "").strip().casefold() != expected.strip().casefold():
        raise HTTPException(409, f"Dans Spotify, sélectionne « {expected} » comme appareil et lance un titre, puis démarre la soirée")
    if device.get("is_restricted"):
        raise HTTPException(409, "Spotify indique que cette enceinte ne peut pas être pilotée par son API. L'ajout direct n'est pas disponible sur cet appareil.")
    store.start(room["uid"], room["name"], "next", source="spotify_sonos",
                spotify_device_id=device["id"], spotify_device_name=device["name"])
    _snap.update(data=None, current=None)
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
                player().launch_playlist(store.session.room_uid, playlist_id, keep)
            except LookupError as e:
                raise HTTPException(404, str(e))
            except Exception as e:
                raise HTTPException(502, f"Sonos a refusé la playlist : {e}")
            finally:
                _snap["data"] = None
        # Les demandes qui n'étaient plus dans la file (ou sans titre Spotify) ne reviendront pas.
        kept = {tid for tid, _ in keep}
        for r in store.pending():
            if not spotify_queue() and r.track_id not in kept:
                r.status = "removed"
        store.save()


_spotify_states: dict[str, float] = {}


@app.get("/api/admin/spotify/login", dependencies=[Depends(require_admin)])
def spotify_login():
    """Party extérieur : connexion (une fois) du compte Spotify de l'hôte."""
    if not spotify_user:
        raise HTTPException(503, "Spotify n'est pas configuré sur le serveur")
    state = secrets.token_urlsafe(16)
    _spotify_states[state] = time.time()
    return RedirectResponse(spotify_user.auth_url(state))


@app.get("/api/spotify/callback")
def spotify_callback(code: str = "", state: str = "", error: str = ""):
    if not spotify_user:
        raise HTTPException(503)
    if error or time.time() - _spotify_states.pop(state, 0) > 600:
        return RedirectResponse("/admin?spotify=refus#settings")
    try:
        spotify_user.exchange(code)
    except SpotifyError:
        return RedirectResponse("/admin?spotify=erreur#settings")
    store.save()
    return RedirectResponse("/admin?spotify=ok#settings")


@app.post("/api/admin/spotify/logout", dependencies=[Depends(require_admin)])
def spotify_logout():
    if spotify_user:
        spotify_user.disconnect()
    return admin_state()


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
    require_editable_queue()
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
                player().move(store.session.room_uid, src, dst)
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
    require_editable_queue()
    removed = []
    with queue_lock:
        snap = snapshot(force=True)
        positions = {t["track_id"]: t["pos"] for t in reversed(snap["upcoming"]) if t["track_id"]}
        for req in sorted(reqs, key=lambda r: positions.get(r.track_id, 0), reverse=True):
            if req.track_id in positions:
                player().remove_at(store.session.room_uid, positions[req.track_id])
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
    try:
        getattr(player(), body.action)(store.session.room_uid)
    except SpotifyError as e:
        raise HTTPException(409, str(e))
    _snap["data"] = None
    return admin_state()


class Volume(BaseModel):
    volume: int


@app.post("/api/admin/volume", dependencies=[Depends(require_admin)])
def admin_volume(body: Volume):
    require_active()
    try:
        player().set_volume(store.session.room_uid, max(0, min(100, body.volume)))
    except SpotifyError as e:
        raise HTTPException(409, str(e))
    _snap["data"] = None
    return {"ok": True}


@app.get("/api/admin/speakers", dependencies=[Depends(require_admin)])
def admin_speakers():
    require_active()
    try:
        return player().speakers(store.session.room_uid)
    except Exception as e:
        raise HTTPException(502, f"Impossible de joindre les Sonos : {e}")


class SpeakerGroup(BaseModel):
    uid: str
    join: bool


@app.post("/api/admin/speakers/group", dependencies=[Depends(require_admin)])
def admin_speaker_group(body: SpeakerGroup):
    """Ajoute une enceinte au groupe de la soirée (elle joue la même musique) ou l'en retire."""
    require_active()
    if store.session.source == "spotify":
        raise HTTPException(409, "Les groupes Sonos se règlent en mode maison")
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
    if store.session.source == "spotify":
        raise HTTPException(409, "Les enceintes Sonos se règlent en mode maison")
    try:
        sonos.set_speaker_volume(body.uid, max(0, min(100, body.volume)))
    except KeyError:
        raise HTTPException(404, "Enceinte introuvable")
    _snap["data"] = None
    return {"ok": True}


@app.post("/api/admin/skip", dependencies=[Depends(require_admin)])
def admin_skip():
    require_active()
    try:
        player().skip(store.session.room_uid)
    except SpotifyError as e:
        raise HTTPException(409, str(e))
    _snap["data"] = None
    return {"ok": True}


def guest_url() -> str:
    return PUBLIC_URL + "/"


_link_http = httpx.Client(timeout=8)


def search_or_link(q: str) -> list[dict]:
    """Recherche Spotify, ou lien collé (Spotify, Deezer, YouTube, Apple Music) → le titre sur Spotify."""
    if spotify is None:
        raise HTTPException(503, "Recherche Spotify non configurée")
    try:
        found = links.resolve(q.strip()[:500], spotify, _link_http)
    except links.LinkError as e:
        raise HTTPException(400, str(e))
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(502, "Impossible de lire ce lien pour le moment")
    if found is not None:
        if not found["tracks"]:
            raise HTTPException(404, f"Titre introuvable sur Spotify ({found['via']})")
        return [{**t, "via": found["via"]} for t in found["tracks"]]
    q = q.strip()[:100]
    return spotify.search(q) if len(q) >= 2 else []


@app.get("/api/admin/search", dependencies=[Depends(require_admin)])
def admin_search(q: str):
    return search_or_link(q)


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
        if (dup is not None or recently_sent(track["id"])) and not body.force:
            where = "envoyé à Spotify à l'instant" if dup is None else "en cours de lecture" if dup == 0 else f"en {dup}ᵉ position"
            raise HTTPException(409, {"duplicate": True, "message": f"« {track['title']} » est déjà dans la file ({where}). L'ajouter quand même ?"})
        if body.where == "next":
            pos = snap["current_pos"] + 1 if snap["current_pos"] else 0
        else:
            upcoming = [(t["pos"], t["track_id"]) for t in snap["upcoming"]]
            pos = end_of_requests(snap["current_pos"], upcoming, store.pending())
        submit_track(track, pos, HOST_ID, "Hôte")
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
        "guests": (store.prune_inactive(), store.guests())[1],
        "bans": [{"guest_id": g, **b} for g, b in store.active_bans().items()],
        "messages": list(reversed(s.messages)),
        "top_playlists": s.top_playlists,
        "source": s.source,
        "spotify_transfer_issues": s.spotify_transfer_issues,
        "spotify_legacy_pending": len(s.vqueue),
        "spotify_account": {"connected": spotify_user.connected, "name": spotify_user.name,
                            "premium": spotify_user.data.get("premium", True)} if spotify_user else None,
        "admin_notify": s.admin_notify,
        "games": [games.summary(g) for g in (prune_games() or s.games).values()],
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
         "art": art_url(t["art"]), "by": names.get(t["track_id"]), "eta": eta,
         # Titre ajouté depuis l'app Sonos (YouTube Music…) : on l'indique.
         "service": t.get("service") if t.get("service") and t.get("service") != "Spotify" else None}
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
    require_editable_queue()
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
            player().move(uid, body.pos, targets[body.action])
        elif body.action == "play":
            player().play_at(uid, body.pos)
        elif body.action == "remove":
            player().remove_at(uid, body.pos)
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
    require_editable_queue()
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
                player().add_spotify_track(store.session.room_uid, it["track_id"], it["title"], pos)
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

GAME_CODE_RE = re.compile(r"^[0-9]{4}$")
_game_creations: dict[str, list[float]] = {}
# Parties fermées récemment : les joueurs encore dessus apprennent qui l'a terminée (pendant 15 min).
_ended_games: dict[str, dict] = {}


def end_game(code: str, by: str):
    g = store.session.games.pop(code, None)
    if g:
        room = store.session.games.get(g.get("room") or "")
        if room and room.get("current") == code:
            games.room_merge(room, g)  # retour à la salle, avec le tableau de la soirée mis à jour
            room["updated_at"] = time.time()
        if g["type"] == "room" and g.get("current"):
            store.session.games.pop(g["current"], None)
        _ended_games[code] = {"by": by, "host": g.get("host_name", ""), "game": games.GAMES.get(g["type"], ""), "at": time.time(),
                              "room": g.get("room") if room else None}
        save_games(code, (room or {}).get("code", ""), g.get("current") or "")


def prune_games():
    """Oublie les parties inactives depuis 4 h, et celles d'un jeu qui n'existe plus."""
    changed = False
    for g in store.session.games.values():
        # Ancien « Blackjack à boire » : devenu le Blackjack avec l'option alcool.
        if g["type"] == "blackjack_drinks":
            g["type"] = "blackjack"
            g["options"]["sips"] = g["options"].get("sips") or 2
            changed = True
    old = [c for c, g in store.session.games.items()
           if time.time() - g["updated_at"] > 4 * 3600 or g["type"] not in games.GAMES]
    for code in old:
        del store.session.games[code]
    if old or changed:
        save_games(*old)


def get_game(code: str) -> dict:
    prune_games()
    g = store.session.games.get(code) if GAME_CODE_RE.match(code) else None
    if g is None:
        ended = _ended_games.get(code)
        if ended and time.time() - ended["at"] < 900:
            raise HTTPException(404, {"message": "Partie terminée", "ended": ended})
        raise HTTPException(404, "Partie introuvable ou terminée")
    return g


class GameCreate(BaseModel):
    guest_id: str
    name: str
    type: str
    white: bool = True
    plays: bool = True  # l'animateur joue aussi (sinon : maître du jeu, il voit les rôles)
    mode: str = "soft"  # Qui de nous ? : soft | awkward | hot | mix
    sips: int = 0  # Qui de nous ? : gorgées pour la personne désignée
    cats: list[str] = []  # Le Divan : catégories de cartes
    floors: int = 5  # Pyramide : nombre d'étages (5 à 8)
    pmode: str = "hard"  # Pyramide : soft (1 gorgée par carte) | hard (1, 2, 3, 4)
    boat: bool = True  # Pyramide : phase du bateau à la fin
    poteau: str = "soft"  # Pyramide : soft (tout le monde boit 1) | hard (celui qui tire boit cul sec)
    double: bool = False  # Pyramide : gorgées par étage 2, 4, 6… au lieu de 1, 2, 3…


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
    g = build_game(body)
    _game_creations[ip] = recent + [time.time()]
    game_presence(request, body.guest_id, body.name)
    notify_admin({"title": f"🎮 {games.GAMES[g['type']]}", "body": f"{g['host_name']} lance une partie · code {g['code']}",
                  "url": "/admin#games", "tag": f"game-{g['code']}"}, kind="games")
    store.session.games[g["code"]] = g
    save_games(g["code"])
    return full_view(g, body.guest_id)


def build_game(body: GameCreate) -> dict:
    """Nouvelle partie avec ses options (création directe, ou lancement depuis une salle de jeux)."""
    try:
        g = games.new_game(body.type, body.guest_id, clean_name(body.name), body.white,
                           code=games.new_code(set(store.session.games) | {store.session.guest_pin}), plays=body.plays,
                           mode=body.mode, sips=body.sips)
    except games.GameError as e:
        raise HTTPException(400, str(e))
    if body.type == "pyramid":
        g["options"].update(floors=max(5, min(8, body.floors)), pmode="soft" if body.pmode == "soft" else "hard", boat=body.boat,
                            poteau="hard" if body.poteau == "hard" else "soft", double=body.double)
    if body.type == "divan" and body.cats:
        try:
            games.divan_set_cats(g, body.cats)
        except games.GameError as e:
            raise HTTPException(400, str(e))
    return g


# ── Salle de jeux : un code pour toute la soirée, l'animateur y lance les jeux ──
def room_child(room: dict) -> dict | None:
    child = store.session.games.get(room.get("current") or "")
    if room.get("current") and not child:
        room["current"] = None  # jeu fermé ou expiré
    return child


def room_of(g: dict) -> dict | None:
    return store.session.games.get(g.get("room") or "")


def room_launch(room: dict, me: str, settings: dict):
    """L'animateur lance un jeu : tous les joueurs de la salle y sont inscrits d'office."""
    if room_child(room):
        raise HTTPException(409, "Un jeu est déjà en cours : termine-le d'abord")
    kind = settings.get("type")
    if kind not in games.GAMES or kind == "room":
        raise HTTPException(400, "Jeu inconnu")
    if kind == "heist" and (len(room["players"]) > 8 or any(p.get("manual") for p in room["players"])):
        raise HTTPException(409, "Le braquage accueille 8 joueurs maximum, chacun avec son téléphone.")
    if kind == "island" and (len(room["players"]) > 8 or any(p.get("manual") for p in room["players"])):
        raise HTTPException(409, "L’île accueille au maximum 8 joueurs, chacun avec son téléphone.")
    if kind == "neon" and (len(room["players"]) > 8 or any(p.get("manual") for p in room["players"])):
        raise HTTPException(409, "Néon Knockout accueille au maximum 8 joueurs, chacun avec son téléphone.")
    if kind == "president" and (len(room["players"]) > 6 or any(p.get("manual") for p in room["players"])):
        raise HTTPException(409, "Président accueille au maximum 6 joueurs, chacun avec son téléphone. Ajuste les participants de la salle avant de le lancer.")
    host = room["host"] or me
    hp = games.player(room, host)
    fields = {k: v for k, v in settings.items() if k in GameCreate.model_fields and k not in ("guest_id", "name", "type")}
    fields["plays"] = bool(hp) and fields.get("plays", True)
    body = GameCreate(guest_id=host, name=room.get("host_name") or "Animateur", type=kind, **fields)
    if len(store.session.games) >= 30:
        prune_games()
    child = build_game(body)
    for p in room["players"]:
        if p["id"] == host:
            continue
        try:
            if p.get("manual"):
                if kind in games.MANUAL_GAMES:
                    games.add_guest(child, p["name"], p["id"])
            else:
                games.join(child, p["id"], p["name"])
        except games.GameError:
            pass
    child["leads"] = list(room.get("leads", []))
    child["room"] = room["code"]
    room["current"] = child["code"]
    store.session.games[child["code"]] = child


def full_view(g: dict, gid: str) -> dict:
    v = games.view(g, gid)
    if g["type"] == "room":
        v["room_info"] = games.room_view(g, gid, room_child(g))
    return v


def game_presence(request: Request, guest_id: str, name: str):
    """Un joueur (même sans le code de la musique) apparaît dans la liste des invités de l'admin."""
    if not GUEST_ID_RE.match(guest_id or ""):
        return
    clean = " ".join((name or "").split())[:30]
    if clean:
        store.register_guest(guest_id, clean, client_ip(request), via="games")
    else:
        store.seen(guest_id)


class Presence(BaseModel):
    guest_id: str
    name: str


@app.post("/api/presence")
def presence(body: Presence, request: Request):
    """Prénom saisi dans l'onglet Jeux : l'hôte voit la personne dans ses Réglages."""
    check_guest_id(body.guest_id)
    game_presence(request, body.guest_id, body.name)
    return {"ok": True}


def admin_lead(g: dict, request: Request, guest_id: str):
    """L'admin de la soirée a toujours au moins les droits de l'animateur, dans tous les jeux."""
    if guest_id and is_admin(request) and guest_id not in g.setdefault("leads", []):
        g["leads"].append(guest_id)
        store.save(notify=False)


def sync_player_name(g: dict, guest_id: str, name: str):
    """Le joueur a changé de prénom (en haut à droite) : la partie en cours le reprend."""
    p = games.player(g, guest_id) if guest_id else None
    clean = " ".join((name or "").split())[:30]
    if p and clean and p["name"] != clean and not p.get("manual"):
        p["name"] = clean
        if g.get("host") == guest_id:
            g["host_name"] = clean
        save_games(g["code"], g.get("room") or "")


@app.get("/api/games/{code}")
def game_state(code: str, request: Request, guest_id: str = "", name: str = ""):
    g = get_game(code)
    game_presence(request, guest_id, name)
    sync_player_name(g, guest_id, name)
    admin_lead(g, request, guest_id)
    if quiz.tick(g):  # Quiz : le temps a avancé (fin d'une question, question suivante…)
        g["updated_at"] = time.time()
        save_games(g["code"], g.get("room") or "")
    with neon.LOCK, island.LOCK, heist.LOCK:
        if heist.tick(g):
            save_games(g["code"])
        if island.tick(g):
            save_games(g["code"])
        if neon.tick(g):
            save_games(g["code"])
        return full_view(g, guest_id)


class GameAction(BaseModel):
    guest_id: str
    name: str = ""
    action: str
    target: str = ""  # identifiant public (pid) d'un joueur
    guess: str = ""
    names: list[str] = []  # roulette : participants notés par l'animateur
    amount: int = 0  # blackjack : mise
    who: str = ""  # Pyramide : l'animateur agit pour ce joueur (pid)
    slots: list[int] = []  # Pyramide : cartes à revoir
    values: list[str] = []  # Pyramide : valeurs du test de mémoire
    settings: dict = {}  # Quiz : réglages de la partie (mode, thèmes, difficulté…)


# Actions de l'animateur (créateur de la partie) ; les autres sont ouvertes à tous les joueurs.
HOST_ACTIONS = {"ban", "start", "vote_start", "close_vote", "eliminate", "skip_guess", "next", "restart", "remove", "end", "up", "down", "names", "spin", "deal", "skip", "cspin", "tq", "finish", "treveal", "tjudge", "addguest", "mvote",
                "pflip", "pbu", "pliar", "ppeek_ok", "ppeek_no", "pmemory", "presults", "pboat", "pboatgo", "paccept", "prefuse", "bclose", "qset", "handover", "nset", "hset"}


@app.post("/api/games/{code}")
def game_action(code: str, body: GameAction, request: Request):
    g = get_game(code)
    child = room_child(g) if g["type"] == "room" else None
    # Les actions de cartes et les retraits de la salle sont atomiques entre téléphones.
    lock = president.LOCK if g["type"] == "president" or (child and child["type"] == "president") else contextlib.nullcontext()
    neon_lock = neon.LOCK if g["type"] == "neon" or (child and child["type"] == "neon") else contextlib.nullcontext()
    island_lock = island.LOCK if g["type"] == "island" or (child and child["type"] == "island") else contextlib.nullcontext()
    heist_lock = heist.LOCK if g["type"] == "heist" or (child and child["type"] == "heist") else contextlib.nullcontext()
    with lock, neon_lock, island_lock, heist_lock:
        return perform_game_action(code, body, request)


def perform_game_action(code: str, body: GameAction, request: Request):
    check_guest_id(body.guest_id)
    g = get_game(code)
    game_presence(request, body.guest_id, body.name)
    sync_player_name(g, body.guest_id, body.name)
    admin_lead(g, request, body.guest_id)
    a, me = body.action, body.guest_id
    if g["type"] == "president" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "up", "down", "handover", "end", "prplay", "prpass", "prexchange"}:
        raise HTTPException(400, "Action indisponible au Président")
    if g["type"] == "heist" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "hset"}:
        raise HTTPException(400, "Action indisponible au Braquage")
    if g["type"] == "island" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end"}:
        raise HTTPException(400, "Action indisponible sur l’île")
    if g["type"] == "neon" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "nset", "nteam"}:
        raise HTTPException(400, "Action indisponible dans Néon Knockout")
    # Cible d'un vote : un joueur (pid) ; pour « Je n'ai jamais », une réponse (yes / no).
    target = games.gid_of(g, body.target) or (body.target if g["type"] in ("never", "casino", "pyramid", "biskit") else "")
    # Pyramide : l'animateur peut agir pour un joueur (participant sans téléphone, ou qui traîne).
    actor = games.gid_of(g, body.who) if body.who and games.is_lead(g, me) and games.gid_of(g, body.who) else me
    if a in HOST_ACTIONS and not games.is_lead(g, me):
        raise HTTPException(403, "Seul l'animateur de la partie peut faire ça")
    if a == "join" and (msg := ban_message(me, client_ip(request))):
        raise HTTPException(403, msg)
    if a == "end":
        end_game(g["code"], "host")
        return None
    if g["type"] == "room" and a == "launch":
        if not games.is_lead(g, me):
            raise HTTPException(403, "Seul l'animateur lance les jeux")
        room_launch(g, me, body.settings)
        g["updated_at"] = time.time()
        save_games(g["code"], g.get("current") or "")
        return full_view(g, me)
    actions = {
        "join": (games.join, me, clean_name(body.name) if a == "join" else ""),
        "leave": (games.leave, me), "vote": (games.vote, me, target), "guess": (games.white_guess, me, body.guess),
        "start": (games.start,), "vote_start": (games.start_vote,), "close_vote": (games.close_vote,),
        "eliminate": (games.eliminate, target), "skip_guess": (games.skip_white_guess,),
        "next": (games.next_step,), "restart": (games.restart,), "remove": (games.kick, target), "ban": (games.ban, target),
        "up": (games.move, target, -1), "down": (games.move, target, 1),
        "names": (games.set_names, body.names), "spin": (games.spin,),
        "bet": (games.bj_bet, me, body.amount), "hit": (games.bj_hit, me), "stand": (games.bj_stand, me),
        "double": (games.bj_double, me), "rebuy": (games.bj_rebuy, me),
        "deal": (games.bj_deal,), "skip": (games.bj_force_stand,),
        "cbet": (games.casino_bet, me, body.target, body.amount), "cclear": (games.casino_clear, me),
        "crebuy": (games.casino_rebuy, me), "cspin": (games.casino_spin,),
        "cundo": (games.casino_undo, me), "cready": (games.casino_ready, me, random),
        "dnext": (games.divan_next, me), "djoker": (games.divan_joker, me), "dback": (games.divan_back, me), "dheart": (games.divan_heart, me),
        "tanswer": (games.tmc_answer, me, body.guess), "tjudge": (games.tmc_judge, me, body.amount),
        "addguest": (games.add_guest, body.guess), "mvote": (games.vote_for, target, body.guess),
        "tq": (games.tmc_change_question,), "treveal": (games.tmc_reveal,), "finish": (games.tmc_finish,),
        "pans": (games.pyr_answer, actor, body.target), "pflip": (games.pyr_flip,), "pclaim": (games.pyr_claim, actor),
        "pbu": (games.pyr_judge, body.target, False), "pliar": (games.pyr_judge, body.target, True),
        "preveal": (games.pyr_reveal, actor, body.amount), "ppeek": (games.pyr_peek, actor, body.slots),
        "ppeek_ok": (games.pyr_peek_decide, body.target, True), "ppeek_no": (games.pyr_peek_decide, body.target, False),
        "ptop": (games.pyr_top, actor), "pmemory": (games.pyr_to_memory,), "pmem": (games.pyr_memory, actor, body.values),
        "presults": (games.pyr_results,), "pboat": (games.pyr_pick_boat, random), "pboatgo": (games.pyr_boat_start,),
        "pbans": (games.pyr_boat_answer, actor, body.target),
        "paccept": (games.pyr_accept, target), "prefuse": (games.pyr_refuse, target),
        "bdraw": (games.bk_draw, actor, random), "bpick": (games.bk_complete, actor, target, body.guess, random),
        "btap": (games.bk_tap, actor), "bclose": (games.bk_close_reflex,),
        "qset": (quiz.configure, body.settings), "qans": (quiz.answer, actor, body.amount, random, body.guess),
        "handover": (games.handover, me, target),
        "hset": (heist.configure, body.settings),
        "nset": (neon.configure, body.settings),
        "nteam": (neon.team, me, body.amount),
        "prplay": (president.play, me, body.values, body.guess),
        "prpass": (president.pass_turn, me, body.guess),
        "prexchange": (president.exchange_cards, me, body.values, body.guess),
        "qjoker": (quiz.joker, actor, body.guess, random), "qstop": (quiz.stop, actor),
        "qpause": (quiz.pause, actor, games.is_lead(g, me) or len(g["players"]) <= 1, random),
    }
    if g["type"] == "quiz" and a == "next":
        actions["next"] = (quiz.next_step, random, body.guess)
    if a not in actions:
        raise HTTPException(400, "Action inconnue")
    fn, *args = actions[a]
    try:
        action_result = fn(g, *args)
    except (games.GameError, quiz.QuizError, president.PresidentError, neon.NeonError, island.IslandError, heist.HeistError) as e:
        raise HTTPException(409, str(e))
    g["updated_at"] = time.time()
    # Salle de jeux : rejoindre, quitter, exclure ou passer la main vaut aussi pour le jeu en cours (et inversement).
    other = room_child(g) if g["type"] == "room" else room_of(g)
    if other:
        other["updated_at"] = time.time()
        try:
            if a == "join" and me not in other.get("kicked", []):
                games.join(other, me, clean_name(body.name))
            elif a == "leave" and games.player(other, me):
                games.leave(other, me)
            elif a == "remove" and target and games.player(other, target):
                games.kick(other, target)
            elif a == "ban" and target:
                games.ban(other, target)
            elif a == "handover" and target:
                # Le nouvel animateur l'est aussi de l'autre (salle ou jeu) ; l'ancien quitte les deux.
                other["host"], other["host_name"] = target, g["host_name"]
                if me in other.get("leads", []):
                    other["leads"].remove(me)
                if games.player(other, me):
                    games.leave(other, me)
            elif a == "addguest" and g["type"] == "room" and other["type"] in games.MANUAL_GAMES:
                games.add_guest(other, body.guess, action_result["id"])
        except games.GameError:
            pass
    if not g["players"] and not g["host"]:
        del store.session.games[g["code"]]
    save_games(g["code"], g.get("room") or "", g.get("current") or "")
    return full_view(g, me)


@app.get("/qr/game/{code}.svg")
def game_qr(code: str):
    g = get_game(code)
    buf = io.BytesIO()
    segno.make(f"{guest_url()}?game={g['code']}", error="m").save(buf, kind="svg", scale=8, border=2, dark="#111", light="#fff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})


@app.post("/api/admin/games/close", dependencies=[Depends(require_admin)])
def admin_close_game(body: GameAction):
    """L'hôte de la soirée peut fermer n'importe quelle partie (body.target = code)."""
    end_game(body.target, "admin")
    return admin_state()


# --- Invités ---

def public_sonos(snap: dict, guest_id: str = "") -> dict:
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    mine = {r.track_id: r.id for r in store.pending() if guest_id and r.guest_id == guest_id}

    def view(t, eta):
        return {"title": t["title"], "artist": t["artist"], "art": art_url(t["art"]), "track_id": t["track_id"],
                "by": names.get(t["track_id"]), "rid": mine.get(t["track_id"]), "eta": eta,
                "service": t.get("service") if t.get("service") and t.get("service") != "Spotify" else None}

    now = snap["now"]
    current_id = (snap["current"] or {}).get("track_id")
    return {
        "queue_editable": not spotify_queue(),
        "device": snap.get("device", ""),
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
    store.prune_inactive()
    store.seen(guest_id)
    store.link_token(guest_id, guest_token(request))
    base = {
        "active": True, "room": s.room_name, "source": s.source, "blocked": ban_message(guest_id, client_ip(request)),
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
        return {**base, "error": "La musique est injoignable pour le moment"}


@app.get("/api/search", dependencies=[Depends(require_guest)])
def search(q: str):
    require_active()
    return search_or_link(q)


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


def require_editable_queue():
    if spotify_queue():
        raise HTTPException(409, QUEUE_MANAGED_IN_SPOTIFY)


def recently_sent(track_id: str) -> bool:
    # L'API de lecture peut mettre quelques secondes à refléter un ajout accepté.
    return spotify_queue() and any(
        r.track_id == track_id and time.time() - r.added_at < 10 for r in store.pending()
    )


def submit_track(track: dict, position: int, guest_id: str, name: str, ip: str = ""):
    # Empêche le watcher d'observer la lecture entre l'envoi et l'enregistrement de l'auteur.
    with _snap_lock:
        try:
            player().add_spotify_track(store.session.room_uid, track["id"], track["title"], position)
        except SpotifyError as e:
            raise HTTPException(502, str(e))
        except Exception as e:
            if spotify_queue():
                raise HTTPException(502, "Envoi non confirmé : vérifie la file Spotify avant de réessayer") from e
            raise HTTPException(502, f"Sonos a refusé l'ajout : {e}")
        store.add(track, guest_id, name, ip)
        _snap["data"] = None


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
        if any(t and t["track_id"] == track["id"] for t in in_queue) or recently_sent(track["id"]):
            raise HTTPException(409, "Ce titre est déjà dans la file 🙂")

        upcoming = [(t["pos"], t["track_id"]) for t in snap["upcoming"]]
        pos = insert_position(s.mode, snap["current_pos"], upcoming, store.pending(), body.guest_id)
        submit_track(track, pos, body.guest_id, name, ip)
    return {"ok": True, "track": track, "source": s.source}


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


class AdminNotify(BaseModel):
    kind: str  # messages | games
    on: bool


@app.post("/api/admin/notify", dependencies=[Depends(require_admin)])
def admin_notify(body: AdminNotify):
    if body.kind not in ("messages", "games"):
        raise HTTPException(400, "Type inconnu")
    store.session.admin_notify[body.kind] = body.on
    store.save(notify=False)
    return {"admin_notify": store.session.admin_notify}


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
                # « version du site|version de l'état » : une page dont la version du site change se recharge.
                yield f"data: {BUILD_ID}|{version}\n\n"
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
        # Adresse versionnée (?v=…, change à chaque déploiement) : le téléphone la garde, pas d'aller-retour.
        versioned = request.query_params.get("v") == BUILD_ID
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if versioned else "no-cache"
    return response


_pages: dict[str, str] = {}


def page(name: str) -> Response:
    """Page HTML avec des adresses de scripts et de styles versionnées (mises en cache jusqu'au prochain déploiement)."""
    if name not in _pages:
        html = (STATIC / name).read_text(encoding="utf-8")
        if not EVENTS_ENABLED:
            html = html.replace("<html", '<html data-events="soon"', 1)  # onglet affiché « Bientôt », module non chargé
        _pages[name] = re.sub(r'(/static/[\w./-]+\.(?:js|css))(?=")', rf"\1?v={BUILD_ID}", html)
    return Response(_pages[name], media_type="text/html; charset=utf-8", headers=NO_CACHE)


@app.get("/")
def index():
    return page("index.html")


@app.get("/admin")
def admin_page():
    return page("admin.html")


@app.get("/api/calendar.ics")
def calendar_file(
    uid: str = Query(max_length=36),
    title: str = Query(max_length=200),
    start: str = Query(max_length=40),
    end: str | None = Query(default=None, max_length=40),
    location: str = Query(default="", max_length=300),
    description: str = Query(default="", max_length=2000),
    url: str = Query(default="", max_length=500),
):
    """Sortie au format iCalendar. Le client transmet ce qu'il affiche déjà : iOS ouvre
    alors directement « Ajouter au calendrier » et Android l'importe dans l'agenda choisi."""
    try:
        body = calendar_ics.build(uid=uid, title=title, start=start, end=end, location=location, description=description, url=url)
    except calendar_ics.CalendarError as exc:
        raise HTTPException(400, str(exc)) from None
    return Response(body, media_type="text/calendar; charset=utf-8", headers={
        **NO_CACHE,
        "Content-Disposition": f'attachment; filename="{calendar_ics.filename(title)}"',
        "X-Content-Type-Options": "nosniff",
    })


@app.get("/events")
def events_redirect():
    return RedirectResponse("/events/", status_code=307)


@app.get("/events/{resource:path}")
def events_web(resource: str):
    """Module web local ; l'accès aux données reste protégé par Supabase Auth/RLS."""
    if not EVENTS_ENABLED:
        return Response("Les événements arrivent bientôt.", status_code=404, headers=NO_CACHE)
    root = EVENTS_WEB.resolve()
    if any(part.startswith(".") for part in Path(resource).parts):
        raise HTTPException(404, "Page introuvable")
    requested = (root / resource).resolve()
    if not requested.is_relative_to(root):
        raise HTTPException(404, "Page introuvable")
    if requested.is_file():
        headers = {"Cache-Control": "public, max-age=31536000, immutable"} if resource.startswith(("_expo/", "assets/")) else NO_CACHE
        response = FileResponse(requested, headers=headers)
    elif resource.startswith(("_expo/", "assets/")) or Path(resource).suffix:
        raise HTTPException(404, "Ressource introuvable")
    elif (root / "index.html").is_file():
        response = FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})
    else:
        return Response("Les événements sont momentanément indisponibles. Réessaie dans un instant.", status_code=503, headers=NO_CACHE)
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/sw.js")
def service_worker():
    # À la racine du site : le service worker couvre la page invités et l'admin.
    return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers=NO_CACHE)


class NeonInput(BaseModel):
    guest_id: str
    x: float = 0
    y: float = 0
    charging: bool = False
    cancel: bool = False


@app.post("/api/games/{code}/neon")
def neon_frame(code: str, body: NeonInput):
    """Small snapshots, no presence/disk write/event broadcast on each input frame."""
    check_guest_id(body.guest_id)
    with neon.LOCK:
        g = get_game(code)
        if g["type"] != "neon":
            raise HTTPException(400, "Ce jeu n'est pas Néon Knockout")
        if body.guest_id in g.get("kicked", []):
            raise HTTPException(403, "Tu as été banni de cette partie")
        changed = neon.tick(g)
        try:
            neon.input_state(g, body.guest_id, body.x, body.y, body.charging, cancel=body.cancel)
        except neon.NeonError as e:
            raise HTTPException(400, str(e))
        if changed:
            g["updated_at"] = time.time()
            save_games(g["code"])
        return neon.view(g, body.guest_id)


class IslandInput(BaseModel):
    guest_id: str
    x: float = 0
    y: float = 0
    jump: bool = False
    cancel: bool = False


@app.post("/api/games/{code}/island")
def island_frame(code: str, body: IslandInput):
    """Authoritative small snapshots; disk writes only on phase transitions."""
    check_guest_id(body.guest_id)
    with island.LOCK:
        g = get_game(code)
        if g["type"] != "island":
            raise HTTPException(400, "Ce jeu n’est pas L’île qui s’effondre")
        if body.guest_id in g.get("kicked", []) or (body.guest_id in g.get("removed", []) and not games.player(g, body.guest_id)):
            raise HTTPException(403, "Tu ne participes plus à cette partie")
        changed = island.tick(g)
        try:
            island.input_state(g, body.guest_id, body.x, body.y, body.jump, cancel=body.cancel)
        except island.IslandError as e:
            raise HTTPException(400, str(e))
        if changed:
            g["updated_at"] = time.time()
            save_games(g["code"])
        return island.view(g, body.guest_id)


class HeistInput(BaseModel):
    guest_id: str
    x: float = 0
    y: float = 0
    action: bool = False
    cancel: bool = False


@app.post("/api/games/{code}/heist")
def heist_frame(code: str, body: HeistInput):
    check_guest_id(body.guest_id)
    with heist.LOCK:
        g = get_game(code)
        if g["type"] != "heist":
            raise HTTPException(400, "Ce jeu n’est pas un braquage")
        if body.guest_id in g.get("kicked", []) or (body.guest_id in g.get("removed", []) and not games.player(g, body.guest_id)):
            raise HTTPException(403, "Tu ne participes plus à cette partie")
        phase = g["phase"]
        changed = heist.tick(g)
        try:
            heist.input_state(g, body.guest_id, body.x, body.y, body.action, cancel=body.cancel)
        except heist.HeistError as e:
            raise HTTPException(400, str(e))
        if changed or phase != g["phase"]:
            g["updated_at"] = time.time()
            save_games(g["code"])
        return heist.view(g, body.guest_id)
