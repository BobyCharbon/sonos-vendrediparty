import asyncio
import base64
import contextlib
import hashlib
import io
import logging
import hmac
import os
import random
import re
import secrets
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote, unquote, urlparse

import httpx
import segno
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import beerpong, brain, brain_game, calendar_ics, debate, games, heist, island, likely, links, masque, neon, president, psy, purity, quiz, reflet
from . import pet, pet_coll_store, pet_reactions, pet_store
from . import tv_zicou
from . import pet_pot, tv_star
# Adresse du déploiement et fonctions en bêta (Compagnon : allumé sur le site de test seulement).
from .features import COMPAGNON_SOON, TEST_SITE_HOST, compagnon_enabled, configured_public_url, discussions_enabled, invites_v2_enabled
from .game_lock import LOCK as GAMES_LOCK
from .accounts import AccountError, Accounts, ServiceUnavailable, TermsRequired
from .account_auth import AccountAuth
from .group_admin import ROLE_KEY, GroupAdmin
from .app_invites import JOIN_PAGE as APP_JOIN_PAGE, AppInvites, join_meta
from . import event_invites, event_preview
from .contact_names import MAX_FRIENDS as CONTACT_MAX_FRIENDS, MAX_HASHES as CONTACT_MAX_HASHES, ContactNames
from .group_chats import LEVELS as CHAT_LEVELS, PHOTO_MAX as CHAT_PHOTO_MAX, GroupChats
from .moderation import ContentRefused, require_clean
from .moderation_api import Moderation, router as moderation_router
from .wallet import MEDIA_TYPE as PKPASS_TYPE, PASS_TYPE_ID, WalletError
from .wallet_tickets import WalletTickets
from .tricount import CURRENCIES as TC_CURRENCIES, Tricount
from .assistant import MAX_PHOTO as AI_PHOTO_MAX, Assistant, ConsentRequired, UsageLog, assistant_consent_key
from .account_data import LocalStores, activity_forgetter, forget_local
from .ai_event_edit import EventEditor
from . import ai_feedback
from .covers import Covers
from .ai_events import MAX_IMAGE_B64 as AI_EVENT_MAX_IMAGE, MAX_TEXT as AI_EVENT_MAX_TEXT, MAX_TURNS as AI_EVENT_MAX_TURNS, EventAssistant
from .places import MAX_QUERY as PLACE_MAX_QUERY, Places
from .audit import AuditLog
from .feedback import (ADMIN_STATUSES as FEEDBACK_STATUSES, AUTHORS as FEEDBACK_AUTHORS, KINDS as FEEDBACK_KINDS,
                       FeedbackBox, build_prompt, meta as feedback_meta, with_defaults as feedback_with_defaults)
from .feedback_remote import (OPS as FEEDBACK_SYNC_OPS, SYNC_HEADER as FEEDBACK_SYNC_HEADER, WRITES as FEEDBACK_SYNC_WRITES,
                              FeedbackRemote, FeedbackUnavailable)
from .github_issues import GitHubError, Issues
from .guest_gate import GuestGate
from . import live_activity
from .apns import TOPICS
from .party import ADMIN_NOTIFY_DEFAULTS, GUEST_NOTIFY_DEFAULTS, HOST_ID, MODES, PartyStore, end_of_requests, fair_moves, insert_position
from .apns import Apns
from .push import Push, valid_subscription
from .security import Limiter
from .sonos import Sonos, seconds
from .spotify import Spotify, SpotifyError, SpotifyUser
from .spotify_player import QUEUE_MANAGED_IN_SPOTIFY, SpotifyPlayer

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
journal = AuditLog(DATA_DIR / "audit.jsonl")  # actions admin et connexions : ajout seul
# Compte progressivement obligatoire : parties et titres en invité, réglés par l'admin (app/guest_gate.py).
guest_gate = GuestGate(DATA_DIR / "guest_gate.json")
ADMIN_PIN = os.environ.get("ADMIN_PIN", "")


PUBLIC_URL = configured_public_url()
STATIC = Path(__file__).parent / "static"
EVENTS_WEB = Path(os.environ.get("EVENTS_WEB_DIR") or str(Path(__file__).parent / "events-web"))
# Section Événements : ouverte à tous les comptes, en production comme sur le site de test (décision du 04.11, fin
# du « Bientôt »). Les Discussions, elles, restent absentes hors site de test (app/features.py, discussions_enabled).


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
# Idées et bugs des invités, gardés d'une soirée à l'autre. Site de test : la liste de la production (une seule liste
# pour les deux sites), lue et écrite par /api/feedback-sync ; FEEDBACK_SYNC_SECRET identique des deux côtés.
FEEDBACK_REMOTE_URL = os.environ.get("FEEDBACK_REMOTE_URL", "").strip()
FEEDBACK_SYNC_SECRET = os.environ.get("FEEDBACK_SYNC_SECRET", "").strip()
FEEDBACK_SYNC_MIN_SECRET = 32
local_feedback = FeedbackBox(DATA_DIR / "feedback.json")
feedback = (FeedbackRemote(FEEDBACK_REMOTE_URL, FEEDBACK_SYNC_SECRET)
            if FEEDBACK_REMOTE_URL and len(FEEDBACK_SYNC_SECRET) >= FEEDBACK_SYNC_MIN_SECRET else local_feedback)
# Retours → Claude : issues « claude-fix » corrigées par .github/workflows/claude-fix.yml (commit sur develop).
log = logging.getLogger("vendrediparty")
github = Issues(os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPO", "BobyCharbon/sonos-vendrediparty"))
quiz.STATS_PATH = DATA_DIR / "quiz_stats.json"  # classement général du Quiz, toutes parties confondues
purity.STATS_PATH = DATA_DIR / "purity_stats.json"  # classement général du Purify Test (comptes Party)
purity.scrub()  # anciens profils par catégorie (données sensibles) : jamais gardés, effacés au démarrage
sonos = Sonos(os.environ.get("SONOS_IP") or None)
spotify = (
    Spotify(os.environ["SPOTIFY_CLIENT_ID"], os.environ["SPOTIFY_CLIENT_SECRET"], os.environ.get("SPOTIFY_MARKET", "CH"))
    if os.environ.get("SPOTIFY_CLIENT_ID") and os.environ.get("SPOTIFY_CLIENT_SECRET")
    else None
)
push = Push(DATA_DIR, PUBLIC_URL, apns=Apns.from_env(os.environ))
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

def absorb_local_feedback():
    """Site de test qui passe à la liste commune : ses avis gardés jusqu'ici partent une fois vers la production,
    puis le fichier local est mis de côté (rien ne se perd, rien n'est envoyé deux fois)."""
    path = DATA_DIR / "feedback.json"
    for _ in range(30):
        if not local_feedback.items:
            return
        try:
            site = feedback_site()[0]
            added = feedback.absorb([{**i, "context": {**(i.get("context") or {}), "site": (i.get("context") or {}).get("site") or site}}
                                     for i in local_feedback.items])
        except FeedbackUnavailable:
            time.sleep(60)
            continue
        path.replace(path.with_suffix(".json.synced"))
        local_feedback.items = []
        log.info("Avis du site versés dans la liste commune : %s ajoutés", added)
        return


@contextlib.asynccontextmanager
async def lifespan(app):
    threading.Thread(target=watch_sonos, daemon=True).start()
    if feedback is not local_feedback:
        threading.Thread(target=absorb_local_feedback, daemon=True).start()
    yield


app = FastAPI(title="Vendredi Party", lifespan=lifespan)


@app.exception_handler(TermsRequired)
async def terms_required_response(request: Request, exc: TermsRequired):
    """CGU exigées par la base (terms_enforced) et pas encore acceptées : 403 avec un code reconnaissable, l'app ouvre
    la feuille des CGU (accept_terms) puis relance l'action."""
    return JSONResponse({"detail": str(exc), "code": exc.code}, status_code=403)


@app.exception_handler(FeedbackUnavailable)
async def feedback_unavailable(request: Request, exc: FeedbackUnavailable):
    return JSONResponse({"detail": str(exc)}, status_code=503)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
# Compression : les pages et scripts pèsent environ 4 fois moins sur le réseau (le flux temps réel n'est pas compressé).
app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=6)


@app.exception_handler(SpotifyError)
async def spotify_error_response(request: Request, error: SpotifyError):
    return JSONResponse(status_code=502, content={"detail": str(error)})


@app.exception_handler(httpx.HTTPError)
async def upstream_error_response(request: Request, error: httpx.HTTPError):
    # Un service distant (Spotify, Sonos, Supabase) qui répond mal ou pas du tout
    # donne un 502 clair plutôt qu'un 500 opaque. Le détail reste côté serveur.
    return JSONResponse(status_code=502, content={"detail": "Un service distant est momentanément indisponible. Réessaie dans un instant."})

# Un seul ajout/suppression à la fois : la position d'insertion dépend de l'état de la file.
queue_lock = threading.Lock()


# --- Cache de l'état Sonos (beaucoup de téléphones interrogent en même temps) ---

_snap = {"at": 0.0, "data": None, "fingerprint": None, "version": 0, "current": None}
_snap_lock = threading.Lock()


def guest_prefs(guest_id: str) -> dict:
    """Types connus seulement : un ancien choix (ex. « games », retiré le 05.11.2026) n'est plus renvoyé."""
    saved = store.session.guest_notify.get(guest_id, {})
    return {kind: saved.get(kind, on) for kind, on in GUEST_NOTIFY_DEFAULTS.items()}


def notify_guest(guest_id: str, payload: dict, kind: str):
    """kind : un type de GUEST_NOTIFY_DEFAULTS ; l'invité ne reçoit que ce qu'il a choisi (Réglages › Notifications).
    Pendant la lune de son compte (Réglages), elle arrive sans son ni vibration."""
    subs = store.session.push.get(guest_id)
    if subs and guest_prefs(guest_id)[kind]:
        push.send(list(subs), quiet_if(payload, accounts.paused(guest_id)), on_gone=lambda sub: store.remove_push(sub["endpoint"]))


def notify_admin(payload: dict, kind: str = "messages"):
    """kind : un type de ADMIN_NOTIFY_DEFAULTS, selon ce que l'hôte a choisi de recevoir. Lune d'un compte admin :
    en silence aussi (« le mode nuit coupe tout », admin compris)."""
    if {**ADMIN_NOTIFY_DEFAULTS, **store.session.admin_notify}[kind] and store.session.admin_push:
        push.send(list(store.session.admin_push), quiet_if(payload, accounts.admin_paused()),
                  on_gone=lambda sub: store.remove_push(sub["endpoint"]))


def quiet_if(payload: dict, silent: bool) -> dict:
    """Pause des notifications : même notification, marquée « silent » (Web Push : silent ; APNs : sans son)."""
    return {**payload, "silent": True} if silent else payload


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
                                      "url": "/", "tag": "now-playing"}, kind="track")


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


# Live Activities (app/live_activity.py) : dernière vue envoyée à chaque activité, en mémoire (un redémarrage
# du serveur renvoie simplement une mise à jour).
_live: dict[str, dict] = {}


def live_slots(data: dict) -> list[live_activity.Slot]:
    by_pos = requests_by_position(data["upcoming"], store.pending())
    slots = []
    for ahead, (t, eta) in enumerate(zip(data["upcoming"], etas(data))):
        if req := by_pos.get(t["pos"]):
            slots.append(live_activity.Slot(req.id, req.guest_id, req.track_id, req.title, req.artist,
                                            req.added_at, ahead, eta))
    return slots


def refresh_live_activities(data: dict, now: float | None = None):
    """À chaque tour de suivi de la file : pousse aux Live Activities ce qui a changé (app fermée comprise)."""
    s = store.session
    if push.apns is None or not (s.activities or s.activity_start_tokens):
        return
    now = now or time.time()
    slots = live_slots(data)
    paused = data["state"] not in ("PLAYING", "TRANSITIONING")
    current = (data.get("current") or {}).get("track_id")
    tracked = {rid: {**info, **_live.get(rid, {})} for rid, info in s.activities.items()}
    owners_of = {slot.rid: slot.owner for slot in slots}
    busy = frozenset(info.get("owner", "") for info in tracked.values()
                     if current and info.get("track_id") == current and info.get("key") == ("playing",))
    steps = (live_activity.plan(slots, current, tracked, paused, now)
             + live_activity.starts(slots, set(s.activity_start_tokens), tracked, set(s.activities_started), paused, now,
                                    busy))
    for step in steps:
        if step.event == "start":
            target = s.activity_start_tokens.get(owners_of[step.rid])
            s.activities_started = s.activities_started[-199:] + [step.rid]
        else:
            target = s.activities.get(step.rid)
        if not target:
            continue
        _live[step.rid] = {"key": step.key, "remaining": step.payload["content-state"]["remaining"]}
        if step.event == "end":
            s.activities.pop(step.rid, None)  # dernier envoi : l'activité ne sera plus suivie
            _live.pop(step.rid, None)
        gone = (lambda rid=step.rid: s.activities.pop(rid, None)) if step.event == "update" else (lambda: None)
        push.send_live_activity(target, step.event, step.payload, step.priority, on_gone=gone)
    if any(step.event in ("start", "end") for step in steps):
        store.save(notify=False)


def watch_sonos():
    """Interroge le Sonos en continu pendant la soirée pour détecter les changements faits ailleurs."""
    while True:
        if store.session.active:
            try:
                refresh_live_activities(snapshot(force=True))
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


def _eq(a: str, b: str) -> bool:
    # Comparaison à temps constant sur les octets : un cookie ou un code non-ASCII
    # (ex. « é ») ne fait plus planter hmac.compare_digest (TypeError → 500).
    return hmac.compare_digest(a.encode("utf-8", "replace"), b.encode("utf-8", "replace"))


def is_admin(request: Request) -> bool:
    token = request.cookies.get("vp_admin", "")
    return bool(ADMIN_PIN) and _eq(token, _token("admin", ADMIN_PIN))


def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(401, "Code admin requis")


PIN_ACTOR = "Code PIN"


def _actor_cookie(name: str) -> str:
    # Signé avec le code admin : un cookie inventé (ou d'avant un changement de code) retombe sur « Code PIN ».
    tag = quote(name, safe="")
    return f"{tag}.{_token('admin-by', ADMIN_PIN + ':' + tag)}"


def admin_actor(request: Request) -> str:
    """Qui agit dans l'admin : le surnom du compte root/admin, ou « Code PIN »."""
    tag, _, _sig = request.cookies.get("vp_admin_by", "").rpartition(".")
    if tag and _eq(request.cookies.get("vp_admin_by", ""), _actor_cookie(unquote(tag))):
        return unquote(tag)
    return PIN_ACTOR


def guest_ref(guest_id: str) -> dict:
    g = store.session.guests.get(guest_id) or store.session.bans.get(guest_id) or {}
    return {"id": guest_id, "name": g.get("name") or ""}


def log_admin(request: Request, action: str, target: dict | None = None, details: dict | None = None):
    journal.record(action, admin_actor(request), target, details)


def _guest_cookie(nonce: str) -> str:
    # Un jeton par saisie du code : l'hôte peut déconnecter une personne sans changer le code.
    return f"{nonce}.{_token('guest', store.session.guest_pin + ':' + nonce)}"


def guest_token(request: Request) -> str | None:
    """Jeton de l'invité s'il est valide pour le code en cours et non révoqué."""
    nonce, _, _sig = request.cookies.get("vp_guest", "").partition(".")
    if not nonce or not _eq(request.cookies.get("vp_guest", ""), _guest_cookie(nonce)):
        return None
    return None if nonce in store.session.revoked else nonce


def is_guest(request: Request) -> bool:
    return guest_token(request) is not None


# Appels de l'app iOS native (ios/Party/Music/PartyAPI.swift) : onglet Musique et extension « Partager ».
NATIVE_APP_HEADER = "x-party-native"


def native_host(request: Request) -> bool:
    """L'hôte connecté, depuis l'app native."""
    return bool(request.headers.get(NATIVE_APP_HEADER)) and is_admin(request)


def owners(request: Request, guest_id: str) -> set[str]:
    """Demandes « à moi » : celles de l'invité ; dans l'app, l'hôte y ajoute ses titres ajoutés en tant qu'hôte
    (HOST_ID) : suivi « Ton titre arrive » et retrait depuis l'écran natif."""
    return ({guest_id} if guest_id else set()) | ({HOST_ID} if native_host(request) else set())


def require_guest(request: Request):
    """Invité ayant saisi le code d'accès en cours (un nouveau code déconnecte tout le monde). La page web l'exige
    même dans le navigateur de l'hôte (il voit ce que voient ses invités) ; l'app native, elle, ne redemande pas
    le code à l'hôte connecté (aucun droit de plus : l'hôte a déjà tous les droits)."""
    if not (is_guest(request) or native_host(request)):
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
    pin: str = Field(max_length=64)


@app.post("/api/admin/login")
def admin_login(body: Login, request: Request, response: Response):
    if not ADMIN_PIN:
        raise HTTPException(503, "ADMIN_PIN n'est pas configuré sur le serveur")
    ip = client_ip(request)
    if msg := admin_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not _eq(body.pin, ADMIN_PIN):
        admin_limiter.fail(ip)
        journal.record("admin.login_failed", "Inconnu", ip=ip)
        raise HTTPException(401, "Code incorrect")
    admin_limiter.success(ip)
    set_auth_cookie(request, response, "vp_admin", _token("admin", ADMIN_PIN), "strict")
    response.delete_cookie("vp_admin_by")
    journal.record("admin.login", PIN_ACTOR, details={"method": "code PIN"}, ip=ip)
    return {"ok": True}


@app.post("/api/join")
def guest_join(body: Login, request: Request, response: Response):
    ip = client_ip(request)
    if msg := guest_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not _eq(body.pin.strip(), store.session.guest_pin):
        guest_limiter.fail(ip)
        raise HTTPException(401, "Code incorrect")
    guest_limiter.success(ip)
    set_auth_cookie(request, response, "vp_guest", _guest_cookie(secrets.token_hex(8)), "lax")
    return {"ok": True}


class PinChoice(BaseModel):
    pin: str | None = None  # None : code tiré au hasard


@app.post("/api/admin/pin", dependencies=[Depends(require_admin)])
def admin_new_pin(request: Request, body: PinChoice | None = None):
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
    log_admin(request, "admin.pin", details={"choice": "choisi" if pin else "au hasard"})
    return admin_state()


@app.post("/api/admin/logout")
def admin_logout(request: Request, response: Response):
    if is_admin(request):
        log_admin(request, "admin.logout")
    response.delete_cookie("vp_admin")
    response.delete_cookie("vp_admin_by")
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
    source: str = "sonos"  # sonos (maison : file Sonos native) | spotify (extérieur) | spotify_sonos (Sonos via Spotify Connect)
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
    if body.source == "sonos":
        # Party maison : file Sonos native, pilotée par l'API locale Sonos (Spotify lié au système Sonos).
        # Aucun compte Spotify à connecter dans Party ; réordonner, retirer et le mode équitable restent possibles.
        try:
            room = next((r for r in sonos.rooms() if r["uid"] == body.room_uid), None)
        except Exception as e:
            raise HTTPException(502, f"Impossible de joindre les Sonos : {e}")
        if room is None:
            raise HTTPException(404, "Pièce introuvable")
        store.start(room["uid"], room["name"], body.mode)
        _snap.update(data=None, current=None)
        if body.playlist:
            launch_playlist(body.playlist)
        return admin_state()
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
def admin_stop(request: Request):
    store.stop()
    log_admin(request, "admin.stop")
    return admin_state()


class GuestGateSettings(BaseModel):
    games: int | None = Field(default=None, ge=0, le=50)   # parties en invité avant compte (0 : compte pour jouer)
    tracks: int | None = Field(default=None, ge=0, le=50)  # titres en invité par soirée (0 : compte pour proposer)


@app.post("/api/admin/guest-gate", dependencies=[Depends(require_admin)])
def admin_guest_gate(body: GuestGateSettings, request: Request):
    """Réglages « Parties en invité avant compte » et « Titres en invité par soirée » (journalisés)."""
    before, after = guest_gate.set_settings(body.games, body.tracks)
    if before != after:
        log_admin(request, "admin.guest_gate", None, {k: f"{before[k]} → {after[k]}" for k in after if before[k] != after[k]})
    store.version += 1  # les pages ouvertes relisent l'état (limite de titres affichée aux invités)
    return {"guest_gate": after}


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


def requests_by_position(upcoming: list[dict], reqs) -> dict:
    """Chaque exemplaire d'un titre dans la file ↔ sa demande : le k-ième exemplaire (par position) est la k-ième
    demande encore en attente de ce titre (ordre d'ajout). Un doublon se retire donc seul, sans emporter l'autre."""
    pending: dict[str, list] = {}
    for r in reqs:
        pending.setdefault(r.track_id, []).append(r)
    seen: dict[str, int] = {}
    mapping = {}
    for t in sorted(upcoming, key=lambda t: t["pos"]):
        tid = t["track_id"]
        if not tid:
            continue
        k = seen.get(tid, 0)
        seen[tid] = k + 1
        if k < len(pending.get(tid, [])):
            mapping[t["pos"]] = pending[tid][k]
    return mapping


def remove_requests(reqs) -> str | None:
    """Retire des demandes de la file Sonos (de la fin vers le début pour garder les positions valides).
    Renvoie un jeton pour annuler."""
    require_editable_queue()
    removed = []
    with queue_lock:
        snap = snapshot(force=True)
        # Position de CET exemplaire (un doublon n'emporte pas l'autre).
        pos_of = {r.id: pos for pos, r in requests_by_position(snap["upcoming"], store.pending()).items()}
        for req in sorted(reqs, key=lambda r: pos_of.get(r.id, 0), reverse=True):
            if req.id in pos_of:
                player().remove_at(store.session.room_uid, pos_of[req.id])
                removed.append({"pos": pos_of[req.id], "track_id": req.track_id, "title": req.title})
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
def admin_ban(body: Ban, request: Request):
    if body.minutes is not None and not 1 <= body.minutes <= 24 * 60:
        raise HTTPException(400, "Durée invalide")
    store.ban(body.guest_id, body.minutes)
    log_admin(request, "admin.ban", guest_ref(body.guest_id), {"minutes": body.minutes} if body.minutes else {"minutes": "sans limite"})
    return admin_state()


class GuestRef(BaseModel):
    guest_id: str


@app.post("/api/admin/unban", dependencies=[Depends(require_admin)])
def admin_unban(body: GuestRef, request: Request):
    target = guest_ref(body.guest_id)
    store.unban(body.guest_id)
    log_admin(request, "admin.unban", target)
    return admin_state()


class Rename(BaseModel):
    guest_id: str
    name: str


@app.post("/api/admin/rename", dependencies=[Depends(require_admin)])
def admin_rename(body: Rename, request: Request):
    """L'hôte renomme un invité (la page de l'invité reprend ce nom)."""
    target, name = guest_ref(body.guest_id), clean_name(body.name)
    store.rename_guest(body.guest_id, name)
    log_admin(request, "admin.rename", target, {"to": name})
    return admin_state()


@app.post("/api/admin/kick", dependencies=[Depends(require_admin)])
def admin_kick(body: GuestRef, request: Request):
    """Déconnecte un invité : il devra ressaisir le code (ce n'est pas un ban)."""
    target = guest_ref(body.guest_id)
    store.kick(body.guest_id)
    log_admin(request, "admin.kick", target)
    return admin_state()


@app.post("/api/admin/purge", dependencies=[Depends(require_admin)])
def admin_purge(body: GuestRef, request: Request):
    """Retire de la file tous les titres en attente d'un invité."""
    require_active()
    log_admin(request, "admin.purge", guest_ref(body.guest_id))
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
    except Exception as e:  # enceinte qui ne répond pas dans le délai court (app/sonos.py, VOLUME_TIMEOUT)
        log.warning("Volume non réglé : %s", e)
        raise HTTPException(502, "Les enceintes ne répondent pas, réessaie")
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
    except Exception as e:  # enceinte qui a décroché du Wi-Fi : réponse en moins de 3 s au lieu de 20
        log.warning("Volume d'enceinte non réglé : %s", e)
        raise HTTPException(502, "Cette enceinte ne répond pas, réessaie")
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
        "feedback_new": feedback.count_new(),
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
        "admin_notify": {**ADMIN_NOTIFY_DEFAULTS, **s.admin_notify},
        "games": [games.summary(g) for g in (prune_games() or s.games).values()],
        "event": {"id": s.event_id, "title": s.event_title} if s.event_id else None,
        "guest_gate": guest_gate.settings(),
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
    action: str  # next | up | down | play | remove | move (vers « to », poignée de l'admin natif)
    to: int | None = None


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
        if body.action == "move":
            if body.to is None:
                raise HTTPException(400, "Position visée manquante")
            targets["move"] = min(last, max(first, body.to))
        if body.action in targets:
            player().move(uid, body.pos, targets[body.action])
        elif body.action == "play":
            player().play_at(uid, body.pos)
        elif body.action == "remove":
            player().remove_at(uid, body.pos)
            # Seulement la demande de cet exemplaire : l'autre exemplaire d'un doublon reste demandé.
            req = requests_by_position(upcoming, store.pending()).get(body.pos)
            reqs = [req] if req else []
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
    for g in list(store.session.games.values()):
        # Ancien « Blackjack à boire » : devenu le Blackjack avec l'option alcool.
        if g["type"] == "blackjack_drinks":
            g["type"] = "blackjack"
            g["options"]["sips"] = g["options"].get("sips") or 2
            changed = True
    old = [c for c, g in list(store.session.games.items())
           if time.time() - g["updated_at"] > 4 * 3600 or g["type"] not in games.GAMES]
    for code in old:
        store.session.games.pop(code, None)
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
    cats: list[str] = []  # Le Divan : catégories de cartes ; Pour ou contre : thèmes
    public: bool = False  # Pour ou contre : prénoms affichés sur l'échelle à la révélation
    floors: int = 5  # Pyramide : nombre d'étages (5 à 8)
    pmode: str = "hard"  # Pyramide : soft (1 gorgée par carte) | hard (1, 2, 3, 4)
    boat: bool = True  # Pyramide : phase du bateau à la fin
    poteau: str = "soft"  # Pyramide : soft (tout le monde boit 1) | hard (celui qui tire boit un shot ou un verre d'eau)
    double: bool = False  # Pyramide : gorgées par étage 2, 4, 6… au lieu de 1, 2, 3…
    impostors: int = 0  # Undercover : nombre d'imposteurs (0 = selon le nombre de joueurs)
    reveal: bool = False  # Undercover : les imposteurs savent qu'ils le sont
    hint: bool = False  # Undercover : indice (catégorie du mot) pour les imposteurs qui se savent imposteurs
    white_hint: bool = False  # Undercover : indice pour Mr. White
    token: str = Field(default="", max_length=4096)  # Purify Test : jeton du compte Party (création réservée aux comptes)


ACCOUNT_GAMES = ("purity",)  # jeux réservés aux comptes Party connectés


def require_account(token: str, guest_id: str, ip: str):
    """Jeu réservé aux comptes : le jeton Supabase présenté doit être celui du compte qui occupe cette place."""
    if not token:
        raise HTTPException(401, "Connecte-toi avec ton numéro pour jouer au Purify Test")
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not 20 < len(token) < 4096:
        raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
    try:
        account = accounts.link(token)
    except AccountError as e:
        raise HTTPException(401, str(e))
    account_limiter.success(ip)
    if account["guest_id"] != guest_id:
        raise HTTPException(403, "Ce compte ne correspond pas à ta place : recharge la page une fois connecté")


# App VendrediParty de l'App Store (Release, ios/Party/AppConfig.swift) : Apple refuse les jeux d'argent simulés
# à un compte développeur individuel. Casino et Blackjack y sont masqués (games.js) et refusés ici ; le site,
# l'app BETA et Android les gardent.
STORE_APP_MARK = "PartyStore"
STORE_HIDDEN_GAMES = ("casino", "blackjack")


def check_store_game(request: Request, kind: str):
    if kind in STORE_HIDDEN_GAMES and STORE_APP_MARK in request.headers.get("user-agent", ""):
        raise HTTPException(403, "Ce jeu n'est pas proposé dans l'app de l'App Store : ouvre-le sur le site Party.")


@app.post("/api/games")
def create_game(body: GameCreate, request: Request):
    check_guest_id(body.guest_id)
    check_store_game(request, body.type)
    ip = client_ip(request)
    if msg := ban_message(body.guest_id, ip):
        raise HTTPException(403, msg)
    if body.type in ACCOUNT_GAMES:
        require_account(body.token, body.guest_id, ip)
    if body.type != "room" and not gate_free(body.guest_id, request) and guest_gate.blocked(body.guest_id):
        raise gate_games_refused(body.guest_id, "")
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
    title, text = f"🎮 {games.GAMES[g['type']]}", f"{g['host_name']} lance une partie · code {g['code']}"
    # Seul l'hôte est prévenu (son réglage) ; les invités, jamais : chacun invite qui il veut (choix de l'admin du 05.11.2026).
    notify_admin({"title": title, "body": text, "url": "/admin#games", "tag": f"game-{g['code']}"}, kind="games")
    store.session.games[g["code"]] = g
    if g["type"] != "room" and not gate_free(body.guest_id, request):
        guest_gate.record(body.guest_id, g["code"])  # sa nouvelle partie compte (une salle, non)
    save_games(g["code"])
    return with_gate(full_view(g, body.guest_id), body.guest_id, request, g["code"])


def build_game(body: GameCreate) -> dict:
    """Nouvelle partie avec ses options (création directe, ou lancement depuis une salle de jeux)."""
    try:
        g = games.new_game(body.type, body.guest_id, clean_name(body.name), body.white,
                           code=games.new_code(set(store.session.games) | {store.session.guest_pin}), plays=body.plays,
                           mode=body.mode, sips=body.sips)
    except games.GameError as e:
        raise HTTPException(400, str(e))
    if body.type == "undercover":
        g["options"].update(impostors=max(0, min(3, body.impostors)), reveal=body.reveal, hint=body.hint, white_hint=body.white_hint)
    if body.type == "pyramid":
        g["options"].update(floors=max(5, min(8, body.floors)), pmode="soft" if body.pmode == "soft" else "hard", boat=body.boat,
                            poteau="hard" if body.poteau == "hard" else "soft", double=body.double)
    if body.type == "purity":
        # Gorgées choisies à la création → option alcool ; sinon 2 gorgées proposées si on l'active plus tard.
        sips = g["options"]["sips"]
        g["options"].update(alcohol=sips > 0, sips=sips or 2)
    if body.type == "likely":
        # Paquets de questions choisis sur la carte du jeu (« cats »), gorgées bornées pour ce jeu.
        try:
            likely.configure(g, {"packs": body.cats or ["family"], "sips": min(g["options"]["sips"], likely.MAX_SIPS)})
        except likely.LikelyError as e:
            raise HTTPException(400, str(e))
    if body.type == "debate":
        try:
            debate.configure(g, {"themes": body.cats or list(debate.DEFAULT_THEMES), "public": body.public})
        except debate.DebateError as e:
            raise HTTPException(400, str(e))
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
    accounts_only = kind in ACCOUNT_GAMES
    if accounts_only and not seat_linked(room, me):
        raise HTTPException(403, "Connecte-toi avec ton numéro pour lancer le Purify Test")
    host = room["host"] or me
    hp = games.player(room, host)
    fields = {k: v for k, v in settings.items() if k in GameCreate.model_fields and k not in ("guest_id", "name", "type", "token")}
    fields["plays"] = bool(hp) and fields.get("plays", True) and (not accounts_only or seat_linked(room, host)) \
        and (gate_free(host) or not guest_gate.blocked(host))  # invité au bout de ses parties : il anime sans jouer
    body = GameCreate(guest_id=host, name=room.get("host_name") or "Animateur", type=kind, **fields)
    if len(store.session.games) >= 30:
        prune_games()
    child = build_game(body)
    if fields["plays"] and not gate_free(host):
        guest_gate.record(host, child["code"])
    for p in room["players"]:
        if p["id"] == host or (accounts_only and not seat_linked(room, p["id"])):
            continue  # Purify Test : seuls les comptes connectés sont inscrits d'office
        if not p.get("manual") and not seat_linked(room, p["id"]) and not gate_enter(child, p["id"], None):
            continue  # invité au bout de ses parties en invité : il voit l'écran « Crée ton compte »
        try:
            if p.get("manual"):
                if kind in games.MANUAL_GAMES:
                    games.add_guest(child, p["name"], p["id"])
            else:
                games.join(child, p["id"], p["name"])
        except games.GameError:
            pass
    child["leads"] = list(room.get("leads", []))
    # Les autres identités des joueurs (onglet resté sur l'identité d'invité, place reprise) les suivent dans le jeu :
    # sinon ce téléphone y prendrait une deuxième place.
    child["aliases"] = {a: o for a, o in (room.get("aliases") or {}).items() if games.player(child, o)}
    child["room"] = room["code"]
    room["rvotes"] = {}  # le vote du jeu suivant repart à zéro
    room["current"] = child["code"]
    store.session.games[child["code"]] = child


def seat_ids(g: dict, gid: str) -> list[str]:
    """Toutes les identités d'une place : la sienne et celles qui y mènent (alias)."""
    return [gid] + [a for a, o in (g.get("aliases") or {}).items() if o == gid]


def seat_linked(g: dict, gid: str) -> bool:
    """La place appartient à un compte Party connecté (sous son identifiant ou l'un de ses alias)."""
    return any(map(accounts.is_linked, seat_ids(g, gid)))


# ── Compte progressivement obligatoire (app/guest_gate.py) ──
GATE_GAMES_MSG = "Crée ton compte pour jouer une nouvelle partie : 30 secondes, juste ton numéro."


def gate_free(gid: str, request: Request | None = None) -> bool:
    """Comptes Party, hôte et admin : jamais limités (seuls les invités sans compte le sont)."""
    return (not gid or gid.startswith("acct-") or gid == HOST_ID or accounts.is_linked(gid)
            or (request is not None and is_admin(request)))


def gate_games_refused(gid: str, code: str) -> HTTPException:
    st = guest_gate.status(gid, code)
    return HTTPException(403, {"message": GATE_GAMES_MSG, "account_required": "games", "played": st["played"],
                               "limit": st["limit"], "code": code})


def gate_enter(g: dict, gid: str, request: Request | None) -> bool:
    """L'invité entre dans une partie (jamais une salle) : refusé s'il a joué ses parties en invité, sinon compté.
    Déjà assis dans cette partie : rien ne change (une partie commencée n'est jamais interrompue)."""
    if g["type"] == "room" or gate_free(gid, request) or games.player(g, gid):
        return True
    if guest_gate.blocked(gid, g["code"]):
        return False
    guest_gate.record(gid, g["code"])
    return True


def with_gate(v: dict, gid: str, request: Request | None, code: str = "") -> dict:
    """Vue d'une partie + où en est l'invité (message doux après sa 1re partie, compte requis ensuite)."""
    if v is None or gate_free(gid, request):
        return v
    st = guest_gate.status(gid, code)
    if v.get("me") or v.get("is_owner") or v.get("type") == "room":
        st = {**st, "blocked": False}  # déjà dans cette partie (ou dans la salle) : rien ne l'en sort
    return {**v, "gate": st}


def full_view(g: dict, gid: str) -> dict:
    v = games.view(g, gid)
    if g["type"] == "room":
        v["room_info"] = games.room_view(g, gid, room_child(g))
    # Présence et homonymes : l'animateur repère d'un coup d'œil un joueur parti ou en double.
    now = time.time()
    for p in v.get("players", []):
        real = games.player(g, games.gid_of(g, p["pid"]))
        if not real or real.get("manual"):
            continue
        last = last_seen_of(g, real["id"])
        p["online"] = now - last < ONLINE_WINDOW
        p["seen_ago"] = int(now - last) if last else None
        ids = seat_ids(g, real["id"])
        if photo := next(filter(None, map(accounts.photo, ids)), None):
            p["photo"] = photo  # compte Party : la photo de profil remplace l'initiale
        if any(map(accounts.is_linked, ids)):
            p["account"] = True  # compte Party : son nom ouvre sa fiche profil
        twins = [x for x in g["players"] if not x.get("manual") and same_name(x["name"], real["name"])]
        if len(twins) > 1:
            p["twin"] = twins.index(real) + 1
    return v


def game_presence(request: Request, guest_id: str, name: str):
    """Un joueur (même sans le code de la musique) apparaît dans la liste des invités de l'admin."""
    if not GUEST_ID_RE.match(guest_id or ""):
        return
    clean = " ".join((name or "").split())[:30]
    if clean:
        store.register_guest(guest_id, clean, client_ip(request), via="games")
    store.seen(guest_id)  # signe de vie : sert à savoir qui est encore là (présence dans les parties)


class Presence(BaseModel):
    guest_id: str
    name: str


@app.post("/api/presence")
def presence(body: Presence, request: Request):
    """Prénom saisi dans l'onglet Jeux : l'hôte voit la personne dans ses Réglages."""
    check_guest_id(body.guest_id)
    game_presence(request, body.guest_id, body.name)
    return {"ok": True}


accounts = Accounts(_secret())
group_admin = GroupAdmin(accounts)
group_chats = GroupChats(group_admin)
# Modération commune (Signaler, blocage, CGU, écran Signalements) : relais pour l'app iOS native.
app.include_router(moderation_router(Moderation(group_admin, group_chats)))
contact_names = ContactNames(accounts)
app_invites = AppInvites(accounts, configured_public_url)
# Billets dans Apple Wallet : certificats dans WALLET_DIR (par défaut DATA_DIR/wallet) ; sans eux, bouton masqué.
wallet = WalletTickets(accounts, Path(os.environ.get("WALLET_DIR") or DATA_DIR / "wallet"))
tricount =Tricount(group_admin, lambda: guest_url())
# Accords « envoyer à Anthropic » (avis, assistant) : un seul fichier, une clé par usage (app/ai_feedback.ConsentBox).
ai_consents = ai_feedback.ConsentBox(DATA_DIR / "ai_feedback_consent.json")
# Assistant IA (Claude) : sans ANTHROPIC_API_KEY dans l'environnement, il reste éteint et le dit. Deux plafonds par mois :
# par personne (AI_MONTHLY_BUDGET_USD) et pour toute l'app, tous usages compris (AI_GLOBAL_MONTHLY_BUDGET_USD, 30 $).
assistant = Assistant(accounts, UsageLog(DATA_DIR / "ai_usage.json"),
                      (lambda: __import__("anthropic").Anthropic(timeout=60.0)) if os.environ.get("ANTHROPIC_API_KEY") else None,
                      float(os.environ.get("AI_MONTHLY_BUDGET_USD", "3")), TC_CURRENCIES, consents=ai_consents,
                      global_budget_usd=float(os.environ.get("AI_GLOBAL_MONTHLY_BUDGET_USD", "30")))
covers = Covers(DATA_DIR, PUBLIC_URL)
event_assistant = EventAssistant(assistant, accounts, covers)
event_editor = EventEditor(event_assistant)
# « Ton avis » écrit avec l'IA : ouvert à tous ceux qui écrivent un avis (sans droit ai.use), après leur accord.
feedback_writer = ai_feedback.FeedbackWriter(assistant, ai_consents, games.GAMES)
places = Places(os.environ.get("GOOGLE_MAPS_API_KEY", ""))  # sans clé : l'app cherche dans les Plans d'Apple
account_auth = AccountAuth(accounts)
# Ne compte que les vrais refus (compte sans droit admin). Un jeton expiré ou invalide n'est jamais compté :
# un jeton Supabase ne se devine pas, et l'app rouverte après 1 h en présente un périmé. Compté, il bloquait
# l'adresse de toute la maison (box partagée) et le compte root ne devenait plus admin (bug du 26.10).
account_limiter = Limiter(per_ip=10, ip_lock=300, global_max=200, global_window=600, global_lock=120)


class AccountLink(BaseModel):
    token: str
    guest_id: str = ""


@app.post("/api/account/link")
def account_link(body: AccountLink, request: Request, background: BackgroundTasks):
    """Compte Party connecté → identifiant de joueur du compte (même sur tous ses appareils), surnom et photo.
    Les places que ce téléphone occupait déjà dans des parties suivent le compte."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    try:
        account = accounts.link(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))
    account_limiter.success(ip)
    log_account_link(account, ip)
    new, old = account["guest_id"], body.guest_id
    # Une place de compte ne passe jamais à un autre compte (téléphone qui change de compte).
    if GUEST_ID_RE.match(old or "") and old != new and not old.startswith("acct-"):
        merge_identity(old, new)
    if account["name"]:
        game_presence(request, new, account["name"])
    uid = accounts.uid_of(new)
    if uid and compagnon_enabled() and store.session.active and soiree_zicous.due(uid):
        # 🪩 son Zicou peut danser sur l'Apple TV s'il joue à la partie regardée, même sans événement lié
        background.add_task(refresh_soiree_zicou, body.token, uid)
    return account


LINK_LOG_EVERY = 30 * 60  # s : une connexion de compte par demi-heure au plus dans le journal
_last_link_log: dict[str, float] = {}


def log_account_link(account: dict, ip: str):
    gid, now = account["guest_id"], time.time()
    if now - _last_link_log.get(gid, 0) < LINK_LOG_EVERY:
        return
    _last_link_log[gid] = now
    name = account["name"] or "Compte sans surnom"
    journal.record("account.link", name, {"id": gid, "name": name}, ip=ip)


def merge_identity(old: str, new: str):
    """Avis 6bad207324a3 : un invité qui joue et se connecte en même temps n'a plus deux profils. Places de jeu,
    fiche d'invité, bannissement, titres demandés, notifications : tout passe au compte, puis une seule sauvegarde
    (verrou des parties puis celui de la soirée, dans cet ordre comme partout)."""
    with GAMES_LOCK, store.lock:
        changed = link_seats(old, new)
        guest_changed = store.merge_guest(old, new)
        if guest_changed:
            store.version += 1  # liste des invités de l'hôte et file d'attente rechargées
        if changed or guest_changed:
            save_games(*changed)
    # Compte créé après des parties en invité : ses stats du Quiz le suivent, son compteur d'invité disparaît.
    quiz.merge_player(old, new)
    guest_gate.forget(old)


def link_seats(old: str, new: str) -> list[str]:
    """Les places que ce téléphone occupait dans des parties deviennent celles du compte (vrai renommage, voir
    app/seat_rename.py). À la déconnexion, la place reste au compte. Renvoie les codes des parties modifiées."""
    changed = []
    for g in list(store.session.games.values()):
        seat = canonical_gid(g, old)  # place reprise plus tôt par ce téléphone (alias) : c'est elle qui suit
        if games.rename_player(g, seat, new):
            if seat != old:
                g["aliases"][old] = new
            changed.append(g["code"])
        elif not games.player(g, new) and games.player(g, seat):
            # Identifiant ancien ou atypique (pas renommable sans risque) : l'ancien alias, comme avant.
            g.setdefault("aliases", {})[new] = seat
            changed.append(g["code"])
        if old in (g.get("kicked") or []) and new not in g["kicked"]:
            g["kicked"].append(new)  # banni de cette partie : se connecter ne lève pas le bannissement
            changed.append(g["code"])
    return list(dict.fromkeys(changed))


class AccountToken(BaseModel):
    token: str


class SessionRefresh(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


@app.post("/api/account/refresh")
def account_refresh(body: SessionRefresh, request: Request):
    """Session de compte expirée (app rouverte après 1 h, module Événements pas chargé) : Party la renouvelle
    lui-même, sinon le compte ne serait plus reconnu (ni admin) avant d'ouvrir l'onglet Événements."""
    if msg := account_limiter.blocked(client_ip(request)):
        raise HTTPException(429, msg)
    try:
        return accounts.refresh(body.refresh_token)
    except AccountError as e:
        raise HTTPException(401, str(e))


class MemberToken(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class PhoneCode(BaseModel):
    phone: str = Field(min_length=8, max_length=16)


class PhoneVerify(PhoneCode):
    code: str = Field(min_length=6, max_length=6)


class AccountDelete(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    confirm: str = Field(max_length=20)


# Connexion native (Réglages de l'app iOS) : mêmes comptes et même session que le module Événements.
otp_limiter = Limiter(per_ip=20, ip_lock=900, global_max=120, global_window=600, global_lock=300)


@app.post("/api/account/otp")
def account_otp(body: PhoneCode, request: Request):
    ip = client_ip(request)
    if msg := otp_limiter.blocked(ip):
        raise HTTPException(429, msg)
    otp_limiter.fail(ip)  # chaque envoi compte : pas de rafale de SMS depuis une même adresse
    return account_call(lambda: account_auth.send_code(body.phone.strip()) or {"ok": True})


@app.post("/api/account/verify")
def account_verify(body: PhoneVerify, request: Request):
    ip = client_ip(request)
    if msg := otp_limiter.blocked(ip):
        raise HTTPException(429, msg)
    try:
        result = account_auth.verify(body.phone.strip(), body.code.strip())
    except AccountError as e:
        otp_limiter.fail(ip)
        raise HTTPException(400, str(e))
    otp_limiter.success(ip)
    return result


@app.post("/api/account/logout")
def account_logout(body: MemberToken):
    account_auth.sign_out(body.token)
    return {"ok": True}


@app.post("/api/account/delete")
def account_delete(body: AccountDelete):
    uid = ""
    with contextlib.suppress(AccountError):
        uid = accounts._uid(body.token)
    result = account_call(lambda: account_auth.delete_account(body.token, body.confirm) or {"ok": True})
    if uid:  # « Tout part avec la suppression du compte » : fichiers locaux du serveur compris (app/account_data.py)
        forget_local(local_stores(), uid, (assistant_consent_key(uid),))
    return result


def local_stores() -> LocalStores:
    return LocalStores(purity_forget=purity.forget, quiz_forget=quiz.forget_player, usage_forget=assistant.usage.forget,
                       consent_forget=ai_consents.forget, gate_forget=guest_gate.forget,
                       feedback_forget=local_feedback.forget, activity_forget=activity_forgetter(pet_party_log))


QUIET_TIME = r"^([01]\d|2[0-3]):[0-5]\d(:00)?$"


class NotificationPatch(BaseModel):
    """Préférences de notification du compte (table Supabase notification_prefs), champs connus seulement."""
    model_config = ConfigDict(extra="forbid")
    push_enabled: bool | None = None
    quiet_start: str | None = Field(None, pattern=QUIET_TIME)
    quiet_end: str | None = Field(None, pattern=QUIET_TIME)
    new_event: Literal["all", "subscribed", "none"] | None = None
    event_changed: bool | None = None
    poll_new: bool | None = None
    date_fixed: bool | None = None
    poll_nudge: bool | None = None
    waitlist: bool | None = None
    reminders: list[Literal["7d", "1d", "2h", "0h"]] | None = Field(None, max_length=4)
    chat: Literal["all", "mentions", "none"] | None = None
    group_broadcasts: bool | None = None  # annonces et @tout des groupes de Discussions
    rsvp_mine: bool | None = None
    proposals: bool | None = None
    # Un réglage par type de notification (migration 20261103120000) : tout ce qu'on peut recevoir se coupe.
    announcements: bool | None = None
    rsvp_set: bool | None = None
    invites: bool | None = None
    proposal_result: bool | None = None
    link_join: bool | None = None
    group_messages: bool | None = None
    group_invites: bool | None = None
    group_joins: bool | None = None
    # Billets payants (migration 20261103130000) : quelqu'un dit avoir payé ; mon paiement est confirmé.
    ticket_pay_declared: bool | None = None
    ticket_pay_confirmed: bool | None = None
    # Billets QR remis par l'organisateur (migration 20261104233000) : « Ton billet est prêt ».
    ticket_issued: bool | None = None
    # Mes amis dans Party (migration 20261104090000) : quelqu'un rejoint grâce à mon lien (envoyée par la base) ;
    # un contact de l'iPhone arrive sur Party (notification locale de l'app, calculée sur l'iPhone).
    referral_joins: bool | None = None
    contact_joins: bool | None = None
    # Messages directs (migration 20261104100000) : « Nouveau message de X ».
    direct_messages: bool | None = None
    # Compagnon (migration 20261104130000) : rappel doux du jour ; alertes avant qu'il ne s'envole.
    pet_daily: bool | None = None
    pet_alerts: bool | None = None
    # Compagnon, lot 1 (migration 20261104150000) : cadeau d'un ami ; paliers de série.
    pet_gifts: bool | None = None
    pet_streaks: bool | None = None
    # Barre « petit cadeau » pleine (migration 20261105160000) : au plus 2 par jour, jamais la nuit.
    pet_bar: bool | None = None
    # Modération (migration 20261104200000) : nouveau signalement (modérateurs) ; message de la modération.
    moderation_reports: bool | None = None
    moderation_notices: bool | None = None
    # Annonces aux groupes (migration 20261106220000) : annonce à valider, événement à valider pour mon groupe,
    # réponse du groupe à mes demandes.
    announce_requests: bool | None = None
    group_event_requests: bool | None = None
    announce_results: bool | None = None


class NotificationUpdate(MemberToken):
    patch: NotificationPatch


@app.post("/api/account/notifications")
def account_notifications(body: MemberToken):
    """Réglages natifs › Notifications › Événements : lues avec la session du membre (ses droits Supabase)."""
    try:
        return accounts.notification_prefs(body.token)
    except ServiceUnavailable as e:  # base lente ou injoignable : « Réessaie », pas « reconnecte-toi »
        raise HTTPException(503, str(e))
    except AccountError as e:
        raise HTTPException(401, str(e))


@app.post("/api/account/notifications/update")
def account_notifications_update(body: NotificationUpdate):
    # Seuls les champs envoyés changent ; les heures de silence se coupent ensemble (toutes deux à null).
    patch = body.patch.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(400, "Rien à changer")
    if any(v is None for k, v in patch.items() if k not in ("quiet_start", "quiet_end")):
        raise HTTPException(400, "Valeur manquante")
    try:
        return accounts.update_notification_prefs(body.token, patch)
    except ServiceUnavailable as e:  # base lente ou injoignable : « Réessaie », pas « reconnecte-toi »
        raise HTTPException(503, str(e))
    except AccountError as e:
        raise HTTPException(401, str(e))


class NotificationPause(MemberToken):
    # all : la lune (tout, en silence) ; chats : Discussions des groupes ; event_chats : discussions des événements
    what: Literal["all", "chats", "event_chats"]
    span: Literal["30m", "1h", "2h", "morning", "off"]


@app.post("/api/account/notifications/pause")
def account_notifications_pause(body: NotificationPause):
    """Réglages natifs : lune en haut de la racine, pauses des Discussions (groupes, événements). Fin calculée par la
    base (Zurich) ; pendant la pause, les notifications arrivent sans son."""
    try:
        return accounts.set_notification_pause(body.token, body.what, body.span)
    except AccountError as e:
        raise HTTPException(401, str(e))


class MemberPush(MemberToken):
    device: str = Field(pattern=r"^[0-9a-f]{64,200}$")  # jeton APNs de l'iPhone
    on: bool


@app.post("/api/account/push")
def account_push(body: MemberPush):
    """Réglages natifs : cet iPhone reçoit les notifications des événements du compte (envoi APNs par Supabase)."""
    try:
        accounts.register_push(body.token, body.device, body.on)
    except AccountError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class GroupName(MemberToken):
    name: str = Field(max_length=60)
    join: bool = False  # créé depuis Discussions : le créateur en fait partie d'office


class GroupMember(MemberToken):
    group_id: str = Field(pattern=UUID)
    user_id: str = Field(pattern=UUID)
    on: bool


class GroupRef(MemberToken):
    group_id: str = Field(pattern=UUID)


def account_call(work, status: int = 400):
    try:
        return work()
    except ConsentRequired as e:  # IA : accord exprès pas encore donné (l'app montre sa feuille d'accord)
        raise HTTPException(403, str(e))
    except TermsRequired:  # 403 {"code": "terms_required"} (terms_required_response) : feuille des CGU puis nouvel essai
        raise
    except ServiceUnavailable as e:  # panne passagère de la base : « Réessaie dans un instant », jamais un refus
        raise HTTPException(503, str(e))
    except AccountError as e:
        raise HTTPException(status, str(e))


# Discussions de groupe (et messages directs) : absentes hors site de test (app/features.py) ; leurs routes
# répondent alors 404 (middleware discussions_off), sauf le blocage d'une personne, commun à toute l'app.
def chats_call(token: str, work, status: int = 400):
    return account_call(work, status)


class WalletTicket(MemberToken):
    event_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")


# Origine du QR : celle de la page qui demande le billet (en-tête Origin posé par le navigateur), pour que le QR
# du Wallet soit exactement celui de l'app ; sinon l'adresse publique de Party.
WALLET_ORIGIN = re.compile(r"^https?://[a-z0-9.-]+(:\d{1,5})?$", re.IGNORECASE)


@app.get("/api/wallet/status")
def wallet_status():
    """Le bouton « Ajouter à Apple Wallet » ne s'affiche que si les certificats sont en place sur le serveur."""
    return {"enabled": wallet.enabled}


@app.post("/api/wallet/ticket")
def wallet_ticket(body: WalletTicket, request: Request):
    """Prépare le billet Wallet de la personne connectée ; rend le lien de téléchargement (quelques minutes)."""
    if not wallet.enabled:
        raise HTTPException(503, "Wallet pas encore configuré")
    origin = request.headers.get("origin") or ""
    origin = origin.rstrip("/") if WALLET_ORIGIN.match(origin) else PUBLIC_URL
    try:
        link = wallet.prepare(body.token, body.event_id.lower(), origin)
    except AccountError as e:
        raise HTTPException(401, str(e))
    except WalletError as e:
        raise HTTPException(404, str(e))
    return {"url": f"/api/wallet/pass/{link}.pkpass"}


@app.get("/api/wallet/pass/{link}.pkpass")
def wallet_pass(link: str):
    data = wallet.download(link)
    if data is None:
        raise HTTPException(404, "Lien expiré : touche à nouveau « Ajouter à Apple Wallet ».")
    return Response(data, media_type=PKPASS_TYPE, headers={
        # « inline » : Safari montre directement la feuille d'ajout à Cartes (pas un téléchargement).
        "Content-Disposition": 'inline; filename="billet.pkpass"', "Cache-Control": "no-store"})


class WalletNotify(MemberToken):
    event_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    member: str | None = Field(default=None, pattern=r"^[0-9a-fA-F-]{36}$")  # absent : tous les billets de l'événement


def wallet_push(token: str, event_id: str, member: str | None, background: BackgroundTasks) -> dict:
    """Prévient les iPhone dont le pass a changé (la base dit lesquels, selon les droits) ; envoi en arrière-plan."""
    if not wallet.enabled:
        return {"devices": 0}
    targets = wallet.push_targets(token, event_id.lower(), member.lower() if member else None)
    if targets:
        background.add_task(wallet.notify, targets)
    return {"devices": len(targets)}


@app.post("/api/wallet/notify")
def wallet_notify(body: WalletNotify, background: BackgroundTasks):
    """Après un scan, un paiement confirmé, un nouveau QR ou un événement modifié (module Événements)."""
    try:
        return wallet_push(body.token, body.event_id, body.member, background)
    except AccountError as e:
        raise HTTPException(401, str(e))
    except WalletError as e:
        raise HTTPException(403, str(e))


# --- PassKit Web Service (webServiceURL du pass) : appelé par l'iPhone, sans session ---------------------------
PASSKIT = "/api/wallet/passkit/v1"
PASSKIT_ID = r"^[A-Za-z0-9._-]{1,128}$"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def passkit_origin(request: Request) -> str:
    """Le pass est servi sur l'adresse que l'iPhone a appelée (webServiceURL = https://<hôte>/…)."""
    host = request.headers.get("host") or ""
    return f"https://{host}" if WALLET_ORIGIN.match(f"https://{host}") else PUBLIC_URL


def passkit_token(request: Request) -> str:
    scheme, _, value = (request.headers.get("authorization") or "").partition(" ")
    if scheme != "ApplePass" or not re.fullmatch(r"[0-9a-f]{64}", value.strip()):
        raise HTTPException(401)
    return value.strip()


def passkit_ids(*values: str) -> None:
    if not wallet.enabled:
        raise HTTPException(503, "Wallet pas encore configuré")
    if not all(re.fullmatch(PASSKIT_ID, v) for v in values):
        raise HTTPException(404)


class PassKitRegistration(BaseModel):
    pushToken: str = Field(pattern=r"^[0-9A-Fa-f]{16,200}$")


@app.post(PASSKIT + "/devices/{device}/registrations/{pass_type}/{serial}")
def passkit_register(device: str, pass_type: str, serial: str, body: PassKitRegistration, request: Request):
    passkit_ids(device, pass_type, serial)
    token = passkit_token(request)
    if pass_type != PASS_TYPE_ID:
        raise HTTPException(404)
    try:
        result = wallet.register(token, serial, device, body.pushToken)
    except WalletError:
        raise HTTPException(400)
    if result == "unauthorized":
        raise HTTPException(401)
    return Response(status_code=201 if result == "created" else 200)


@app.delete(PASSKIT + "/devices/{device}/registrations/{pass_type}/{serial}")
def passkit_unregister(device: str, pass_type: str, serial: str, request: Request):
    passkit_ids(device, pass_type, serial)
    token = passkit_token(request)
    try:
        ok = pass_type == PASS_TYPE_ID and wallet.unregister(token, serial, device)
    except WalletError:
        ok = False
    if not ok:
        raise HTTPException(401)
    return Response(status_code=200)


@app.get(PASSKIT + "/devices/{device}/registrations/{pass_type}")
def passkit_updated(device: str, pass_type: str, passesUpdatedSince: str | None = Query(default=None, max_length=64)):
    passkit_ids(device, pass_type)
    if pass_type != PASS_TYPE_ID:
        raise HTTPException(404)
    # Repère opaque pour l'iPhone : microsecondes depuis 1970 (aucun « + » ni « : » à encoder dans l'adresse).
    tag = passesUpdatedSince or ""
    since = (EPOCH + timedelta(microseconds=int(tag))).isoformat() if tag.isdigit() and len(tag) <= 18 else None
    try:
        found = wallet.updated(device, since)
    except WalletError:
        raise HTTPException(503)
    if not found.get("serials"):
        return Response(status_code=204)
    last = datetime.fromisoformat(str(found["last_updated"]).replace("Z", "+00:00"))
    return {"serialNumbers": found["serials"], "lastUpdated": str((last - EPOCH) // timedelta(microseconds=1))}


@app.get(PASSKIT + "/passes/{pass_type}/{serial}")
def passkit_pass(pass_type: str, serial: str, request: Request):
    passkit_ids(pass_type, serial)
    token = passkit_token(request)
    if pass_type != PASS_TYPE_ID:
        raise HTTPException(401)
    # Toujours le pass entier (jamais 304) : If-Modified-Since n'a que la seconde, deux changements dans la même
    # seconde (arrivée puis paiement) feraient manquer le second.
    try:
        found = wallet.latest(token, serial, passkit_origin(request))
    except WalletError:
        raise HTTPException(503)
    if found is None:
        raise HTTPException(401)
    data, modified = found
    return Response(data, media_type=PKPASS_TYPE, headers={"Last-Modified": format_datetime(modified, usegmt=True),
                                                           "Cache-Control": "no-store"})


@app.post(PASSKIT + "/log")
async def passkit_log(request: Request):
    """Erreurs remontées par Wallet (pass refusé, serveur injoignable…) : dans le journal du serveur."""
    try:
        logs = (await request.json()).get("logs") or []
    except (ValueError, AttributeError):
        logs = []
    for line in logs[:20]:
        logging.getLogger("wallet").warning("Wallet (iPhone) : %s", str(line)[:300])
    return Response(status_code=200)


@app.post("/api/account/groups")
def account_groups(body: MemberToken):
    """Réglages natifs › Groupes."""
    return account_call(lambda: accounts.groups(body.token), 401)


@app.post("/api/account/groups/create")
def account_group_create(body: GroupName):
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(400, "Donne un nom au groupe")
    return account_call(lambda: accounts.create_group(body.token, name, body.join))


@app.post("/api/account/groups/member")
def account_group_member(body: GroupMember):
    return account_call(lambda: accounts.set_group_member(body.token, body.group_id, body.user_id, body.on))


@app.post("/api/account/groups/delete")
def account_group_delete(body: GroupRef):
    return account_call(lambda: accounts.delete_group(body.token, body.group_id))


class AdminDecision(MemberToken):
    id: str = Field(pattern=UUID)
    yes: bool
    reason: str | None = Field(default=None, max_length=500)


class AdminSwitch(MemberToken):
    on: bool


class AdminMemberUpdate(MemberToken):
    id: str = Field(pattern=UUID)
    role: str | None = Field(default=None, pattern=ROLE_KEY)
    status: Literal["active", "banned"] | None = None
    beta: bool | None = None


class AdminMemberDelete(MemberToken):
    id: str = Field(pattern=UUID)
    confirm_name: str = Field(max_length=60)


class AdminPermission(MemberToken):
    role: str = Field(pattern=ROLE_KEY)
    perm: str = Field(min_length=1, max_length=60, pattern=r"^[a-z_.]+$")
    on: bool


ROLE_COLOR = r"^#[0-9A-Fa-f]{6}$"


class AdminRoleFields(MemberToken):
    label: str = Field(min_length=1, max_length=30)
    color: str | None = Field(default=None, pattern=ROLE_COLOR)
    icon: str | None = Field(default=None, max_length=8)


class AdminRoleCreate(AdminRoleFields):
    copy_from: str | None = Field(default=None, pattern=ROLE_KEY)


class AdminRoleUpdate(AdminRoleFields):
    key: str = Field(pattern=ROLE_KEY)


class AdminRoleDelete(MemberToken):
    key: str = Field(pattern=ROLE_KEY)
    move_to: str | None = Field(default=None, pattern=ROLE_KEY)


class AdminRoleOrder(MemberToken):
    keys: list[str] = Field(min_length=2, max_length=40)

    @field_validator("keys")
    @classmethod
    def valid_keys(cls, keys: list[str]) -> list[str]:
        if any(not re.fullmatch(ROLE_KEY, k) for k in keys):
            raise ValueError("rôle inconnu")
        return keys


class AdminJournal(MemberToken):
    member: str | None = Field(default=None, pattern=UUID)
    before: int | None = Field(default=None, ge=1)


# Discussions de groupe (avis n°10) pour l'app native : la base revérifie tout avec la session du membre.
# direct : conversation privée à deux (messages directs, 4.11) ; group_id est alors l'id de la conversation.
class ChatRef(MemberToken):
    group_id: str = Field(pattern=UUID)
    direct: bool = False


class ChatDirectStart(MemberToken):
    user_id: str = Field(pattern=UUID)
    # Empreinte du numéro de la personne (contacts de l'iPhone, même clé que contacts_match) : preuve qu'on la connaît.
    contact_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ChatBlock(MemberToken):
    user_id: str = Field(pattern=UUID)
    on: bool


class ChatSend(ChatRef):
    body: str = Field(default="", max_length=2000)
    reply_to: str | None = Field(default=None, pattern=UUID)
    photo_path: str | None = Field(default=None, max_length=200, pattern=r"^[0-9a-f-]{36}/[0-9]+-[0-9a-f]{10}\.(jpg|png)$")
    # Fournis par l'app (envoi en un seul appel) : personnes citées, identifiant du message affiché tout de suite.
    mentions: list[Annotated[str, Field(pattern=UUID)]] | None = Field(default=None, max_length=100)
    id: str | None = Field(default=None, pattern=UUID)
    audio_path: str | None = Field(default=None, max_length=200, pattern=r"^[0-9a-f-]{36}/[0-9]+-[0-9a-f]{10}\.(m4a|webm|ogg)$")
    audio_seconds: float | None = Field(default=None, ge=0, le=600)


class ChatPhoto(ChatRef):
    photo: str = Field(min_length=1, max_length=CHAT_PHOTO_MAX * 4 // 3 + 8)  # base64


class ChatMessage(MemberToken):
    id: str = Field(pattern=UUID)
    direct: bool = False


class ChatReact(ChatMessage):
    emoji: str = Field(min_length=1, max_length=16)
    on: bool


class ChatPin(ChatMessage):
    pin: bool


class ChatNotify(ChatRef):
    level: Literal[CHAT_LEVELS]


class ChatAdmin(ChatRef):
    user_id: str = Field(pattern=UUID)
    on: bool


class ChatEveryone(ChatRef):
    who: Literal["all", "staff"]  # qui peut écrire @tout : tous les membres, ou admins et organisateurs


@app.post("/api/account/chats")
def account_chats(body: MemberToken):
    return chats_call(body.token, lambda: group_chats.chats(body.token), 401)


@app.post("/api/account/chats/open")
def account_chat_open(body: ChatRef):
    return chats_call(body.token, lambda: group_chats.conversation(body.token, body.group_id, body.direct))


@app.post("/api/account/chats/direct")
def account_chat_direct(body: ChatDirectStart):
    """« Écrire » (Mes amis, fiche d'un membre) : LA conversation privée avec cette personne (créée si besoin)."""
    return chats_call(body.token, lambda: group_chats.start_direct(body.token, body.user_id, body.contact_hash))


@app.post("/api/account/chats/block")
def account_chat_block(body: ChatBlock):
    """Bloquer / débloquer une personne en messages directs (elle n'en est pas prévenue)."""
    return chats_call(body.token, lambda: group_chats.block(body.token, body.user_id, body.on))


@app.post("/api/account/chats/send")
def account_chat_send(body: ChatSend):
    return chats_call(body.token, lambda: group_chats.send(body.token, body.group_id, body.body.strip(), body.reply_to, body.photo_path,
                                                 body.mentions, body.id, body.audio_path, body.audio_seconds, body.direct))


@app.post("/api/account/chats/audio")
def account_chat_audio(body: ChatPhoto):
    """Message vocal (base64) : déposé dans le dossier du groupe, puis envoyé avec /chats/send (audio_path)."""
    try:
        data = base64.b64decode(body.photo, validate=True)
    except ValueError:
        raise HTTPException(400, "Enregistrement illisible") from None
    return chats_call(body.token, lambda: group_chats.upload_audio(body.token, body.group_id, data))


@app.post("/api/account/chats/photo")
def account_chat_photo(body: ChatPhoto):
    try:
        data = base64.b64decode(body.photo, validate=True)
    except ValueError:
        raise HTTPException(400, "Photo illisible") from None
    return chats_call(body.token, lambda: group_chats.upload_photo(body.token, body.group_id, data))


# ── Tricount (Réglages › Pot commun de l'app iOS) : dépenses partagées, lien pour rejoindre, profil de paiement ──
class TcRef(MemberToken):
    group_id: str = Field(pattern=UUID)


class TcCreate(MemberToken):
    name: str = Field(min_length=1, max_length=60)
    emoji: str = Field(default="💸", max_length=8)
    currency: str = Field(default="CHF", pattern=r"^[A-Z]{3}$")
    my_name: str = Field(min_length=1, max_length=40)


class TcUpdate(TcRef):
    name: str | None = Field(default=None, max_length=60)
    emoji: str | None = Field(default=None, max_length=8)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    archived: bool | None = None


class TcJoin(MemberToken):
    link: str = Field(pattern=UUID)
    my_name: str = Field(default="", max_length=40)
    claim: str | None = Field(default=None, pattern=UUID)


class TcMember(TcRef):
    member_id: str | None = Field(default=None, pattern=UUID)
    name: str = Field(default="", max_length=40)


class TcExpense(TcRef):
    expense: dict


class TcExpenseRef(TcRef):
    expense_id: str = Field(pattern=UUID)


class TcSettle(TcRef):
    from_id: str = Field(pattern=UUID)
    to_id: str = Field(pattern=UUID)
    amount_cents: int = Field(gt=0, le=100_000_000)


class TcReceipt(TcRef):
    photo: str = Field(min_length=1, max_length=CHAT_PHOTO_MAX * 4 // 3 + 8)  # base64


class TcPayment(MemberToken):
    iban: str = Field(default="", max_length=42)
    holder: str = Field(default="", max_length=80)
    links: dict[str, str] = Field(default_factory=dict, max_length=8)
    note: str = Field(default="", max_length=200)


@app.post("/api/account/tricount")
def account_tricount_list(body: MemberToken):
    return account_call(lambda: tricount.overview(body.token), 401)


@app.post("/api/account/tricount/open")
def account_tricount_open(body: TcRef):
    return account_call(lambda: tricount.state(body.token, body.group_id))


@app.post("/api/account/tricount/create")
def account_tricount_create(body: TcCreate):
    return account_call(lambda: tricount.create(body.token, body.name, body.emoji, body.currency, body.my_name))


@app.post("/api/account/tricount/update")
def account_tricount_update(body: TcUpdate):
    return account_call(lambda: tricount.update(body.token, body.group_id, body.name, body.emoji, body.currency, body.archived))


@app.post("/api/account/tricount/link")
def account_tricount_link(body: TcRef):
    """Nouveau lien pour rejoindre : l'ancien ne marche plus."""
    return account_call(lambda: tricount.renew_link(body.token, body.group_id))


@app.post("/api/account/tricount/join/info")
def account_tricount_join_info(body: TcJoin):
    return account_call(lambda: tricount.join_info(body.token, body.link))


@app.post("/api/account/tricount/join")
def account_tricount_join(body: TcJoin):
    return account_call(lambda: tricount.join(body.token, body.link, body.my_name, body.claim))


@app.post("/api/account/tricount/member")
def account_tricount_member(body: TcMember):
    """Ajouter un prénom (sans member_id) ou renommer (avec)."""
    if body.member_id:
        return account_call(lambda: tricount.rename_member(body.token, body.group_id, body.member_id, body.name))
    return account_call(lambda: tricount.add_member(body.token, body.group_id, body.name))


@app.post("/api/account/tricount/member/remove")
def account_tricount_member_remove(body: TcMember):
    if not body.member_id:
        raise HTTPException(400, "Personne à retirer ?")
    return account_call(lambda: tricount.remove_member(body.token, body.group_id, body.member_id))


@app.post("/api/account/tricount/leave")
def account_tricount_leave(body: TcRef):
    return account_call(lambda: tricount.leave(body.token, body.group_id))


@app.post("/api/account/tricount/expense")
def account_tricount_expense(body: TcExpense):
    return account_call(lambda: tricount.save_expense(body.token, body.group_id, body.expense))


@app.post("/api/account/tricount/expense/delete")
def account_tricount_expense_delete(body: TcExpenseRef):
    return account_call(lambda: tricount.delete_expense(body.token, body.group_id, body.expense_id))


@app.post("/api/account/tricount/settle")
def account_tricount_settle(body: TcSettle):
    return account_call(lambda: tricount.settle_up(body.token, body.group_id, body.from_id, body.to_id, body.amount_cents))


@app.post("/api/account/tricount/receipt")
def account_tricount_receipt(body: TcReceipt):
    try:
        data = base64.b64decode(body.photo, validate=True)
    except ValueError:
        raise HTTPException(400, "Photo illisible") from None
    return account_call(lambda: tricount.upload_receipt(body.token, body.group_id, data))


@app.post("/api/account/ai/status")
def account_ai_status(body: MemberToken):
    """Droit, configuration, accord (« accepted », « declined », « ») et plafonds de l'assistant IA."""
    return account_call(lambda: assistant.status(body.token), 401)


class AiConsent(MemberToken):
    accept: bool


@app.post("/api/account/ai/consent")
def account_ai_consent(body: AiConsent):
    """Même accord « IA » que les avis (/api/feedback/ai/consent, clé acct:<uid>) : un seul pour toute l'IA de Party.
    Refus ou retrait : plus aucun appel de l'assistant ni du scan de ticket (403 « Accord requis »)."""
    return account_call(lambda: assistant.set_consent(body.token, body.accept), 401)


class AiPhoto(MemberToken):
    photo: str = Field(min_length=1, max_length=AI_PHOTO_MAX * 4 // 3 + 8)  # base64


@app.post("/api/account/ai/receipt")
def account_ai_receipt(body: AiPhoto):
    try:
        data = base64.b64decode(body.photo, validate=True)
    except ValueError:
        raise HTTPException(400, "Photo illisible") from None
    return account_call(lambda: assistant.read_receipt(body.token, data))


class AiEventDraft(MemberToken):
    turns: list[str] = Field(min_length=1, max_length=AI_EVENT_MAX_TURNS * 2)
    draft: dict | None = None
    # Captures d'écran (affiche, page d'un site) en base64 : l'IA y lit l'événement. 3 au plus, réduites par l'app.
    images: list[Annotated[str, Field(max_length=AI_EVENT_MAX_IMAGE)]] = Field(default=[], max_length=3)


@app.get("/covers/{name}")
def event_cover(name: str):
    """Couverture d'un événement (image de la page, capture ou affiche générée), réencodée en JPEG par app.covers."""
    path = covers.path(name)
    if path is None:
        raise HTTPException(404, "Image introuvable")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.post("/api/account/ai/event/draft")
def account_ai_event_draft(body: AiEventDraft):
    """Ce que la personne a dit (description, puis ses réponses) → brouillon d'événement et questions de l'IA."""
    if sum(len(t) for t in body.turns) > AI_EVENT_MAX_TEXT * AI_EVENT_MAX_TURNS:
        raise HTTPException(400, "Description trop longue")
    return account_call(lambda: event_assistant.draft(body.token, body.turns, body.draft, images=body.images))


class AiEventCreate(MemberToken):
    draft: dict
    place: dict | None = None


@app.post("/api/account/ai/event/create")
def account_ai_event_create(body: AiEventCreate):
    """Brouillon confirmé dans l'app (compte à rebours de 5 s) → événement publié ou proposé."""
    return account_call(lambda: event_assistant.create(body.token, body.draft, body.place))


@app.post("/api/account/ai/event/draft/save")
def account_ai_event_draft_save(body: AiEventCreate):
    """Étape 1 « La soirée » confirmée (« Oui, continuer ») → événement en brouillon, sans invité ; l'app ouvre ensuite
    l'étape 2 « Les invités » (/events/event/<id>/invite), où la personne invite elle-même puis publie."""
    return account_call(lambda: event_assistant.save_draft(body.token, body.draft, body.place))


EVENT_ID = r"^[0-9a-f-]{36}$"


class AiEventEditLoad(MemberToken):
    event_id: str = Field(pattern=EVENT_ID)


@app.post("/api/account/ai/event/edit/load")
def account_ai_event_edit_load(body: AiEventEditLoad):
    """« ✨ Modifier avec l'IA » : l'événement tel qu'il est, en brouillon (seul qui peut le modifier l'obtient)."""
    return account_call(lambda: event_editor.load(body.token, body.event_id))


class AiEventEditDraft(AiEventEditLoad):
    turns: list[str] = Field(min_length=1, max_length=AI_EVENT_MAX_TURNS * 2)


@app.post("/api/account/ai/event/edit/draft")
def account_ai_event_edit_draft(body: AiEventEditDraft):
    """Ce que la personne veut changer → l'événement modifié et la liste des changements (rien n'est encore écrit)."""
    if sum(len(t) for t in body.turns) > AI_EVENT_MAX_TEXT * AI_EVENT_MAX_TURNS:
        raise HTTPException(400, "Demande trop longue")
    return account_call(lambda: event_editor.draft(body.token, body.event_id, body.turns))


class AiEventEditSave(AiEventEditLoad):
    draft: dict
    place: dict | None = None  # absent : le lieu ne change pas
    announce: bool = True  # message récapitulatif dans la discussion de l'événement


@app.post("/api/account/ai/event/edit/save")
def account_ai_event_edit_save(body: AiEventEditSave, background: BackgroundTasks):
    saved = account_call(lambda: event_editor.save(body.token, body.event_id, body.draft, body.place, body.announce))
    with contextlib.suppress(AccountError, WalletError):  # titre, date, lieu : les billets dans Cartes se mettent à jour
        wallet_push(body.token, body.event_id, None, background)
    return saved


class AiPlaces(MemberToken):
    query: str = Field(min_length=1, max_length=PLACE_MAX_QUERY)
    broad: str = Field(default="", max_length=PLACE_MAX_QUERY)  # même lieu, cherché plus largement (type et ville)
    kind: Literal["home", "venue"] = "venue"  # adresse de particulier (Geocoding) ou établissement (Places)


@app.post("/api/account/ai/places")
def account_ai_places(body: AiPlaces):
    """Lieux possibles dans Google Maps pour le lieu dit (la personne choisit le bon) ; vide sans clé Google."""
    def run():
        assistant.allowed(body.token)
        return {"source": "google" if places.configured else "none",
                "places": places.find(body.query, body.broad, body.kind)}
    return account_call(run)


@app.post("/api/account/ai/usage")
def account_ai_usage(body: MemberToken):
    return account_call(lambda: assistant.report(body.token), 403)


@app.post("/api/account/tricount/payment")
def account_tricount_payment(body: MemberToken):
    return account_call(lambda: tricount.payment(body.token), 401)


@app.post("/api/account/tricount/payment/save")
def account_tricount_payment_save(body: TcPayment):
    return account_call(lambda: tricount.set_payment(body.token, body.iban, body.holder, body.links, body.note))


@app.get("/pot/{link}", response_class=HTMLResponse)
@app.get("/tricount/{link}", response_class=HTMLResponse)  # premiers liens partagés, avant le nom « Pot commun »
def tricount_link_page(link: str):
    """Lien partagé : sur un iPhone avec l'app Party, le lien universel ouvre directement « Rejoindre » ; sinon cette page."""
    if not re.match(UUID, link):
        raise HTTPException(404, "Lien invalide")
    return HTMLResponse(TRICOUNT_LINK_PAGE, headers=NO_CACHE)


TRICOUNT_LINK_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Rejoindre un pot commun · Party</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,sans-serif;background:#140f24;color:#fff}
main{max-width:420px;padding:32px 24px;text-align:center}h1{font-size:1.8rem;margin:.4em 0}p{color:#d8d0f2;line-height:1.5}
.i{font-size:4rem}</style></head><body><main><div class="i">💸</div><h1>On t'invite dans un pot commun</h1>
<p>Ouvre ce lien sur ton iPhone avec l'app <b>Party</b> : il t'emmène directement sur « Rejoindre », dans Réglages › Pot commun.</p>
<p>Pas encore l'app ? Demande le lien TestFlight à la personne qui t'a invité.</p></main></body></html>"""


@app.post("/api/account/chats/react")
def account_chat_react(body: ChatReact):
    return chats_call(body.token, lambda: group_chats.react(body.token, body.id, body.emoji, body.on, body.direct))


@app.post("/api/account/chats/pin")
def account_chat_pin(body: ChatPin):
    return chats_call(body.token, lambda: group_chats.pin(body.token, body.id, body.pin, body.direct))


@app.post("/api/account/chats/delete")
def account_chat_delete(body: ChatMessage):
    return chats_call(body.token, lambda: group_chats.delete(body.token, body.id, body.direct))


@app.post("/api/account/chats/notify")
def account_chat_notify(body: ChatNotify):
    return chats_call(body.token, lambda: group_chats.notify(body.token, body.group_id, body.level, body.direct))


@app.post("/api/account/chats/admin")
def account_chat_admin(body: ChatAdmin):
    return chats_call(body.token, lambda: group_chats.set_admin(body.token, body.group_id, body.user_id, body.on))


@app.post("/api/account/chats/organizer")
def account_chat_organizer(body: ChatAdmin):
    """Rôle de groupe « Organisateur » (annonces) : nommé ou retiré par les admins du groupe."""
    return chats_call(body.token, lambda: group_chats.set_organizer(body.token, body.group_id, body.user_id, body.on))


@app.post("/api/account/chats/everyone")
def account_chat_everyone(body: ChatEveryone):
    """Qui peut écrire @tout dans ce groupe (choix des admins du groupe)."""
    return chats_call(body.token, lambda: group_chats.set_everyone(body.token, body.group_id, body.who))


@app.post("/api/account/chats/read")
def account_chat_read(body: ChatRef):
    return chats_call(body.token, lambda: group_chats.read(body.token, body.group_id, body.direct))


# Réglages natifs › Administration du groupe : la base revérifie chaque droit avec la session du membre.
@app.post("/api/account/group-admin")
def account_group_admin(body: MemberToken):
    return account_call(lambda: group_admin.overview(body.token), 401)


@app.post("/api/account/group-admin/event")
def account_group_admin_event(body: AdminDecision):
    return account_call(lambda: group_admin.decide_event(body.token, body.id, body.yes, (body.reason or "").strip()))


@app.post("/api/account/group-admin/request")
def account_group_admin_request(body: AdminDecision):
    return account_call(lambda: group_admin.decide_request(body.token, body.id, body.yes))


@app.post("/api/account/group-admin/approval")
def account_group_admin_approval(body: AdminSwitch):
    return account_call(lambda: group_admin.set_require_approval(body.token, body.on))


@app.post("/api/account/group-admin/members")
def account_group_admin_members(body: MemberToken):
    return account_call(lambda: group_admin.members(body.token), 401)


@app.post("/api/account/group-admin/member")
def account_group_admin_member(body: AdminMemberUpdate):
    return account_call(lambda: group_admin.update_member(body.token, body.id, body.role, body.status, body.beta))


@app.post("/api/account/group-admin/member/delete")
def account_group_admin_member_delete(body: AdminMemberDelete):
    return account_call(lambda: group_admin.delete_member(body.token, body.id, body.confirm_name.strip()))


@app.post("/api/account/group-admin/roles")
def account_group_admin_roles(body: MemberToken):
    return account_call(lambda: group_admin.roles(body.token), 401)


@app.post("/api/account/group-admin/permission")
def account_group_admin_permission(body: AdminPermission):
    return account_call(lambda: group_admin.set_permission(body.token, body.role, body.perm, body.on))


@app.post("/api/account/group-admin/role/create")
def account_group_admin_role_create(body: AdminRoleCreate):
    return account_call(lambda: group_admin.create_role(body.token, body.label.strip(), body.color, (body.icon or "").strip() or None,
                                                        body.copy_from))


@app.post("/api/account/group-admin/role/update")
def account_group_admin_role_update(body: AdminRoleUpdate):
    return account_call(lambda: group_admin.update_role(body.token, body.key, body.label.strip(), body.color,
                                                        (body.icon or "").strip() or None))


@app.post("/api/account/group-admin/role/delete")
def account_group_admin_role_delete(body: AdminRoleDelete):
    return account_call(lambda: group_admin.delete_role(body.token, body.key, body.move_to))


@app.post("/api/account/group-admin/roles/order")
def account_group_admin_roles_order(body: AdminRoleOrder):
    return account_call(lambda: group_admin.reorder_roles(body.token, body.keys))


@app.post("/api/account/group-admin/journal")
def account_group_admin_journal(body: AdminJournal):
    return account_call(lambda: group_admin.journal(body.token, body.member, body.before))


class AnnouncementPage(MemberToken):
    before_at: str | None = Field(default=None, max_length=40, pattern=r"^[0-9T:.+\-Z ]+$")
    before_id: str | None = Field(default=None, pattern=UUID)


class AnnouncementNew(MemberToken):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class TopicSave(MemberToken):
    kind: Literal["categories", "tags"]
    id: str | None = Field(default=None, pattern=UUID)
    name: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    archived: bool | None = None


@app.post("/api/account/announcements")
def account_announcements(body: AnnouncementPage):
    """Réglages natifs › Annonces admin (lecture pour tous les membres)."""
    return account_call(lambda: group_admin.announcements(body.token, body.before_at, body.before_id), 401)


@app.post("/api/account/group-admin/announce")
def account_group_admin_announce(body: AnnouncementNew):
    title, text = body.title.strip(), body.body.strip()
    if not title or not text:
        raise HTTPException(400, "Un titre et un message, s'il te plaît.")
    return account_call(lambda: group_admin.publish(body.token, title, text))


@app.post("/api/account/group-admin/taxonomy")
def account_group_admin_taxonomy(body: MemberToken):
    return account_call(lambda: group_admin.taxonomy(body.token), 401)


@app.post("/api/account/group-admin/taxonomy/save")
def account_group_admin_taxonomy_save(body: TopicSave):
    fields = {k: v for k, v in (("name", body.name), ("color", body.color), ("archived", body.archived)) if v is not None}
    if not fields or (body.id is None and not body.name):
        raise HTTPException(400, "Donne un nom.")
    return account_call(lambda: group_admin.save_topic(body.token, body.kind, body.id, fields))


class MemberCardIn(MemberToken):
    id: str | None = Field(default=None, pattern=UUID)
    # Jeux : la partie et le numéro du joueur (jamais son identifiant, qui ne quitte pas le serveur).
    game: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    pid: str | None = Field(default=None, max_length=40)


class PrivacyName(MemberToken):
    on: bool


class PrivacyPhone(MemberToken):
    group_id: str = Field(pattern=UUID)
    on: bool


@app.post("/api/account/card")
def account_card(body: MemberCardIn):
    """Fiche profil d'un compte (Réglages, groupes, jeux…) : ce que les choix de la personne laissent voir."""
    guest = None
    if body.game and body.pid:
        g = get_game(body.game)
        real = games.gid_of(g, body.pid)
        ids = [real] + [a for a, o in (g.get("aliases") or {}).items() if o == real]
        guest = next((i for i in ids if accounts.is_linked(i)), None)
        if not guest:
            raise HTTPException(404, "Ce joueur n'a pas de compte Party.")
    elif not body.id:
        raise HTTPException(400, "Profil inconnu")
    return account_call(lambda: accounts.member_card(body.token, body.id, guest), 404)


@app.post("/api/account/privacy")
def account_privacy(body: MemberToken):
    return account_call(lambda: accounts.privacy(body.token), 401)


@app.post("/api/account/privacy/name")
def account_privacy_name(body: PrivacyName):
    return account_call(lambda: accounts.set_name_public(body.token, body.on))


@app.post("/api/account/privacy/phone")
def account_privacy_phone(body: PrivacyPhone):
    return account_call(lambda: accounts.set_group_phone_share(body.token, body.group_id, body.on))


class ContactHashes(MemberToken):
    hashes: list[str] = Field(max_length=CONTACT_MAX_HASHES)


@app.post("/api/account/contacts/key")
def account_contacts_key(body: MemberToken):
    """App iPhone, noms des contacts : clé des empreintes (HMAC-SHA256 du numéro E.164), comptes actifs seulement."""
    return {"key": account_call(lambda: contact_names.key(body.token), 401)}


@app.post("/api/account/contacts/match")
def account_contacts_match(body: ContactHashes):
    """Empreintes du répertoire → comptes Party correspondants ({user_id, hash}). Rien n'est gardé ; limite dans la base."""
    try:
        return {"matches": contact_names.match(body.token, body.hashes)}
    except AccountError as e:
        raise HTTPException(429 if str(e).startswith("Trop de demandes") else 400, str(e))


class FriendIds(MemberToken):
    ids: list[str] = Field(max_length=CONTACT_MAX_FRIENDS)


class AppInviteRenew(MemberToken):
    renew: bool = False


class AppInviteToken(BaseModel):
    invite: str = Field(pattern=UUID)


class AppInviteClaim(MemberToken):
    invite: str = Field(pattern=UUID)


@app.post("/api/account/contacts/friends")
def account_contacts_friends(body: FriendIds):
    """Réglages › Mes amis dans Party : surnom, photo, arrivée et groupes en commun des comptes reconnus sur l'iPhone."""
    return {"friends": account_call(lambda: contact_names.friends(body.token, body.ids))}


@app.post("/api/account/invite")
def account_app_invite(body: AppInviteRenew):
    """Mon lien personnel d'invitation dans Party (renew : nouveau lien, l'ancien ne marche plus)."""
    try:
        return app_invites.mine(body.token, body.renew)
    except AccountError as e:
        raise HTTPException(429 if "5 fois" in str(e) else 400, str(e))


@app.post("/api/account/invite/preview")
def account_app_invite_preview(body: AppInviteToken):
    """Avant connexion : qui invite (surnom, photo). Lien inconnu ou retiré : invite = null."""
    return {"invite": account_call(lambda: app_invites.preview(body.invite), 503)}


@app.post("/api/account/invite/claim")
def account_app_invite_claim(body: AppInviteClaim):
    """Nouveau compte arrivé par un lien : la base note qui l'a invité (une fois) et prévient cette personne."""
    return account_call(lambda: app_invites.claim(body.token, body.invite))


class InvitedByIn(MemberToken):
    id: str = Field(pattern=UUID)


@app.post("/api/account/card/invited-by")
def account_card_invited_by(body: InvitedByIn):
    """Fiche d'un membre › « Invité par » (lien Party, groupe, événement) : null sans le droit « Voir qui a invité qui »."""
    return {"invited_by": account_call(lambda: app_invites.invited_by(body.token, body.id))}


class GroupInvitationAnswer(MemberToken):
    id: str = Field(pattern=UUID)
    accept: bool


class GroupLink(MemberToken):
    group_id: str = Field(pattern=UUID)
    renew: bool = False


class GroupInvite(MemberToken):
    group_id: str = Field(pattern=UUID)
    member: str | None = Field(default=None, pattern=UUID)
    phone: str | None = Field(default=None, min_length=8, max_length=20, pattern=r"^[+0-9 .()-]+$")


@app.post("/api/account/groups/invitations")
def account_group_invitations(body: MemberToken):
    """Réglages › Groupes : les invitations reçues (par mon compte ou mon numéro)."""
    return {"invitations": account_call(lambda: accounts.group_invitations(body.token), 401)}


@app.post("/api/account/groups/invitations/answer")
def account_group_invitation_answer(body: GroupInvitationAnswer):
    return {"invitations": account_call(lambda: accounts.answer_group_invitation(body.token, body.id, body.accept))}


@app.post("/api/account/groups/link")
def account_group_link(body: GroupLink):
    """Lien d'invitation d'un groupe (créateur) : adresse publique du module Événements."""
    token = account_call(lambda: accounts.group_invite_link(body.token, body.group_id, body.renew))
    return {"url": group_link_url(token)}


class GroupLinkRef(MemberToken):
    id: str = Field(pattern=UUID)


def group_link_url(link: str) -> str:
    return f"{guest_url().rstrip('/')}/events/group-invite/{link}"


@app.post("/api/account/groups/link/single")
def account_group_single_link(body: GroupRef):
    """Nouveau lien unique (une personne, une fois, 7 jours) : le créateur en crée un par personne invitée."""
    link = account_call(lambda: accounts.group_single_link(body.token, body.group_id))
    return {"url": group_link_url(link), "links": account_call(lambda: accounts.group_links(body.token, body.group_id))}


@app.post("/api/account/groups/links")
def account_group_links(body: GroupRef):
    return {"links": account_call(lambda: accounts.group_links(body.token, body.group_id))}


@app.post("/api/account/groups/links/revoke")
def account_group_link_revoke(body: GroupLinkRef):
    account_call(lambda: accounts.revoke_link(body.token, body.id))
    return {"ok": True}


@app.post("/api/account/groups/invite")
def account_group_invite(body: GroupInvite):
    if not body.member and not body.phone:
        raise HTTPException(400, "Choisis une personne ou un numéro")
    return account_call(lambda: accounts.invite_to_group(body.token, body.group_id, body.member, body.phone))


class SubscriptionSet(MemberToken):
    kind: Literal["category", "tag"]
    id: str = Field(pattern=UUID)
    on: bool


@app.post("/api/account/subscriptions")
def account_subscriptions(body: MemberToken):
    """Réglages natifs › Abonnements."""
    try:
        return accounts.subscriptions(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))


@app.post("/api/account/subscriptions/set")
def account_subscription_set(body: SubscriptionSet):
    try:
        return accounts.set_subscription(body.token, body.kind, body.id, body.on)
    except AccountError as e:
        raise HTTPException(400, str(e))


MAX_PROFILE_PHOTO = 5 * 1024 * 1024  # JPEG recadré par l'app (~200 Ko) ; même plafond que le module Événements


class ProfileUpdate(MemberToken):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    display_name: str = Field(max_length=40)
    photo: str = Field("", max_length=7 * 1024 * 1024)  # JPEG en base64


@app.post("/api/account/profile")
def account_profile(body: MemberToken):
    """Réglages natifs › Mon profil."""
    try:
        return accounts.profile(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))


@app.post("/api/account/profile/update")
def account_profile_update(body: ProfileUpdate):
    fields = {k: " ".join(getattr(body, k).split()) for k in ("first_name", "last_name", "display_name")}
    if not all(fields.values()):
        raise HTTPException(400, "Prénom, nom et surnom sont obligatoires")
    photo = None
    if body.photo:
        try:
            photo = base64.b64decode(body.photo, validate=True)
        except ValueError:
            raise HTTPException(400, "Photo illisible : choisis-la à nouveau")
        if not photo.startswith(b"\xff\xd8\xff") or len(photo) > MAX_PROFILE_PHOTO:
            raise HTTPException(400, "Photo illisible ou trop lourde : choisis-en une autre")
    try:
        return accounts.update_profile(body.token, fields, photo)
    except AccountError as e:
        raise HTTPException(400, str(e))


class EventLink(BaseModel):
    event_id: str = Field("", pattern=r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?$")
    title: str = Field("", max_length=120)


@app.post("/api/admin/event/options", dependencies=[Depends(require_admin)])
def admin_event_options(body: AccountToken):
    """Événements du jour et à venir que le compte de l'hôte voit : on peut en lier un à la soirée."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    try:
        return accounts.upcoming_events(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))


@app.post("/api/admin/event", dependencies=[Depends(require_admin)])
def admin_event(body: EventLink, request: Request):
    """Lie la soirée à un événement (ses comptes notés « Présent » entrent sans le code), ou la délie (vide)."""
    title = " ".join(body.title.split()) if body.event_id else ""
    with GAMES_LOCK, store.lock:
        store.session.event_id, store.session.event_title = body.event_id, title
        if not body.event_id:  # délier : les accès sans code donnés pour l'ancien événement tombent
            store.session.revoked = (store.session.revoked + list(store.session.event_passes.values()))[-500:]
            store.session.event_passes = {}
        store.save()
    log_admin(request, "admin.event", details={"title": title or "aucun"})
    return admin_state()


@app.post("/api/join/account")
def guest_join_account(body: AccountToken, request: Request, response: Response, background: BackgroundTasks):
    """Soirée liée à un événement : un compte noté « Présent » (pas en liste d'attente) entre sans le code.
    L'app revérifie régulièrement : noté absent entre-temps, son accès sans code est révoqué."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    s = store.session
    if not (s.active and s.event_id):
        raise HTTPException(409, "Aucune soirée liée à un événement : entre le code de la soirée.")
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    try:
        uid, present = accounts.attending(body.token, s.event_id)
    except AccountError as e:
        raise HTTPException(401, str(e))
    account_limiter.success(ip)
    nonce = store.event_pass(uid, present)
    if nonce is None:
        raise HTTPException(403, f"Tu n'es pas noté présent à « {s.event_title} » : entre le code de la soirée.")
    set_auth_cookie(request, response, "vp_guest", _guest_cookie(nonce), "lax")
    if compagnon_enabled() and soiree_zicous.due(uid):   # 🪩 son Zicou danse sur l'Apple TV (relu après la réponse)
        background.add_task(refresh_soiree_zicou, body.token, uid)
    return {"ok": True, "event_title": s.event_title}


@app.post("/api/account/admin")
def account_admin(body: AccountToken, request: Request, response: Response):
    """Compte Party root ou admin (droits « Ouvrir la page admin » + « Réglages du site ») : session admin sans code PIN."""
    if not ADMIN_PIN:
        raise HTTPException(503, "ADMIN_PIN n'est pas configuré sur le serveur")
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    try:
        allowed = accounts.is_party_admin(body.token)
        who = accounts.link(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))
    name = who["name"] or "Compte sans surnom"
    if not allowed:
        account_limiter.fail(ip)
        journal.record("admin.denied", name, {"id": who["guest_id"], "name": name}, ip=ip)
        raise HTTPException(403, "Ton compte n'a pas l'accès admin de Party")
    account_limiter.success(ip)
    set_auth_cookie(request, response, "vp_admin", _token("admin", ADMIN_PIN), "strict")
    set_auth_cookie(request, response, "vp_admin_by", _actor_cookie(name), "strict")
    journal.record("admin.login", name, {"id": who["guest_id"], "name": name}, {"method": "compte"}, ip=ip)
    return {"ok": True}


@app.get("/api/admin/audit", dependencies=[Depends(require_admin)])
def admin_audit(limit: int = Query(100, ge=1, le=500), before: str | None = Query(None, max_length=64)):
    """Journal (lecture seule) : actions admin, connexions, refus. Aucune route ne le modifie."""
    return {"entries": journal.read(limit, before)}


ONLINE_WINDOW = 45  # s : un téléphone ouvert sur la partie se manifeste au moins toutes les 15 s


def canonical_gid(g: dict, guest_id: str) -> str:
    """Identifiant du joueur dans cette partie : un téléphone qui a repris sa place parle au nom de l'ancien."""
    return (g.get("aliases") or {}).get(guest_id, guest_id)


def last_seen_of(g: dict, gid: str) -> float:
    """Dernier signe de vie du joueur, sur n'importe lequel de ses appareils (identifiant d'origine ou alias)."""
    ids = [gid] + [a for a, o in (g.get("aliases") or {}).items() if o == gid]
    return max(store.last_seen.get(i, 0) for i in ids)


def is_online(g: dict, gid: str) -> bool:
    return time.time() - last_seen_of(g, gid) < ONLINE_WINDOW


def same_name(a: str, b: str) -> bool:
    key = lambda n: "".join(c for c in unicodedata.normalize("NFKD", " ".join((n or "").split())) if not unicodedata.combining(c)).casefold()
    return bool(key(a)) and key(a) == key(b)


SECRET_SEAT_GAMES = ("masque", "reflet")


def reclaim_seat(g: dict, guest_id: str, name: str, ip: str) -> str:
    """Joueur qui revient avec un autre identifiant (app installée ↔ Safari, navigation privée, stockage effacé…) :
    même prénom, et même appareil (même adresse) ou ancienne place inoccupée → il reprend sa place (points, rôle,
    cartes) au lieu d'apparaître en double. Un joueur en ligne sur un autre appareil n'est jamais remplacé.

    Sécurité : le siège de l'animateur (host) et des leads n'est jamais repris par simple prénom. Derrière le NAT
    d'une soirée tout le monde partage une IP, donc « même appareil » ne prouve rien ; un invité pourrait sinon
    s'emparer du rôle d'animateur (end/ban/launch) en se nommant comme lui. L'animateur qui revient garde sa place
    via son identifiant stable (compte Party connecté, ou cookie/stockage conservé), pas via le prénom."""
    if games.player(g, guest_id) or guest_id in (g.get("aliases") or {}):
        return canonical_gid(g, guest_id)
    if guest_id in g.get("kicked", []):
        return guest_id
    # Jeux à réponses secrètes en cours : une place ne se reprend jamais par prénom (même réseau de la soirée), sinon un
    # homonyme lirait la réponse secrète d'un joueur parti fermer son téléphone, ou lèverait le masque à sa place.
    if g["type"] in SECRET_SEAT_GAMES and g["phase"] not in ("lobby", "end"):
        return guest_id

    def mine(p):
        known = (store.session.guests.get(p["id"]) or {}).get("ips", [])
        return bool(ip) and ip not in PROXY_IPS and ip in known

    # Idem pour une place liée à un compte Party : son titulaire la retrouve en se connectant, jamais par prénom
    # (sinon un homonyme lirait ses réponses privées au Purify Test).
    protected = {g.get("host")} | set(g.get("leads") or [])
    seats = [p for p in g["players"]
             if not p.get("manual") and p["id"] != guest_id and p["id"] not in protected and not p["id"].startswith("acct-")
             and same_name(p["name"], name)]
    seats = [p for p in seats if mine(p) or not is_online(g, p["id"])]
    if len(seats) != 1:
        return guest_id  # personne, ou ambigu (deux places possibles) : nouvelle place
    old = seats[0]["id"]
    for game in filter(None, (g, room_child(g) if g["type"] == "room" else room_of(g))):
        if games.player(game, old):
            game.setdefault("aliases", {})[guest_id] = old
    return old


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
    # Tous les téléphones interrogent en même temps : une seule avancée automatique (fin d'une question…) à la fois.
    with GAMES_LOCK:
        return read_game(code, request, guest_id, name)


def read_game(code: str, request: Request, guest_id: str, name: str):
    g = get_game(code)
    check_store_game(request, g["type"])
    game_presence(request, guest_id, name)
    guest_id = canonical_gid(g, guest_id)
    sync_player_name(g, guest_id, name)
    admin_lead(g, request, guest_id)
    if g.get("phase") == "end" and guest_id.startswith("acct-") and pet_reactions.rewardable_game(g) \
            and any(p.get("id") == guest_id for p in g.get("players", [])):
        # 🥚 Petit bonus pour son Zicou (une fois par partie, sous GAMES_LOCK) ; jamais pour un jeu à boire.
        zicou_react(guest_id, "party", str(g.get("id") or g["code"]))
    if g.get("paused"):
        pass  # en pause : le temps ne fait rien avancer
    elif quiz.tick(g):  # Quiz : le temps a avancé (fin d'une question, question suivante…)
        g["updated_at"] = time.time()
        save_games(g["code"], g.get("room") or "")
    if not g.get("paused") and heist.tick(g):
        save_games(g["code"])
    if not g.get("paused") and island.tick(g):
        save_games(g["code"])
    if not g.get("paused") and neon.tick(g):
        save_games(g["code"])
    return with_gate(full_view(g, guest_id), guest_id, request, g["code"])


class GameAction(BaseModel):
    # Bornes généreuses : elles ne gênent aucun usage réel mais coupent les corps démesurés
    # (ex. flood O(n²) de set_names) avant qu'ils n'atteignent la logique de jeu.
    guest_id: str = Field(max_length=200)
    name: str = Field(default="", max_length=100)
    action: str = Field(max_length=40)
    target: str = Field(default="", max_length=200)  # identifiant public (pid) d'un joueur
    guess: str = Field(default="", max_length=500)
    names: list[str] = Field(default=[], max_length=100)  # roulette : participants notés par l'animateur
    amount: int = 0  # blackjack : mise
    who: str = Field(default="", max_length=200)  # Pyramide : l'animateur agit pour ce joueur (pid)
    slots: list[int] = Field(default=[], max_length=500)  # Pyramide : cartes à revoir
    values: list[str] = Field(default=[], max_length=500)  # Pyramide : valeurs du test de mémoire
    settings: dict = {}  # Quiz : réglages de la partie (mode, thèmes, difficulté…)
    done: bool = False  # Purify Test : affirmation cochée (« déjà fait ») ou décochée
    token: str = Field(default="", max_length=4096)  # Purify Test : jeton du compte Party pour rejoindre


PURITY_ONLY = {"puset", "puans", "pusub", "puunsub", "pureveal"}
# « Qui est le plus… ? » : chacun vote sur son téléphone ; celui de l'animateur fait voter les participants sans
# téléphone (lkvote, avec who = votant) et passe un absent (lkskip, avec target).
LIKELY_ONLY = {"lkset", "lkvote", "lkskip", "lkswap"}
LIKELY_ACTIONS = {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "addguest", "up", "down", "pause", "resume"} | LIKELY_ONLY
# « Pour ou contre » : vote sur 5 crans (dbvote, amount = cran, who = votant sans téléphone), revote décidé par
# l'animateur, dilemmes proposés par les joueurs (dbpropose, guess = texte) et validés par l'animateur (amount = numéro).
DEBATE_ONLY = {"dbset", "dbvote", "dbskip", "dbswap", "dbrevote", "dbpropose", "dbaccept", "dbrefuse", "dbreport"}
DEBATE_ACTIONS = {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "addguest", "up", "down", "pause", "resume"} | DEBATE_ONLY
PSY_ONLY = {"psyans", "psysub", "psyreveal"}
PSY_ACTIONS = {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "pause", "resume"} | PSY_ONLY
PURITY_ACTIONS = {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "pause", "resume"} | PURITY_ONLY
# « Le Masque » : chacun écrit (mswrite, guess = texte), puis relie les réponses aux prénoms et choisit de lever son
# masque (msguess, settings = {picks: {réponse: pid}, unmask}) ; l'animateur règle, change, montre, retire, révèle.
MASQUE_ONLY = {"msset", "mswrite", "msswap", "msshow", "msguess", "mshide", "msreveal", "msreport"}
MASQUE_ACTIONS = {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "pause", "resume"} | MASQUE_ONLY
# « Le Reflet » : qui est devant le miroir choisit et parie (rfpick, settings = {i, bet}) ; les autres votent (rfvote,
# done = oui) ; l'animateur règle et n'attend plus un absent (rfskip).
REFLET_ONLY = {"rfset", "rfpick", "rfswap", "rfvote", "rfskip"}
REFLET_ACTIONS = {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "pause", "resume"} | REFLET_ONLY

# Actions propres à un jeu : refusées ailleurs (sinon elles lisent l'état d'un autre jeu et le serveur plante).
GAME_ONLY_ACTIONS = {
    "pyramid": {"pans", "pflip", "pclaim", "pbu", "pliar", "preveal", "ppeek", "ppeek_ok", "ppeek_no", "ptop", "pmemory",
                "pmem", "presults", "pboat", "pboatgo", "pbans", "paccept", "prefuse"},
    "biskit": {"bdraw", "bpick", "btap", "bclose", "broll"},
    "blackjack": {"bet", "hit", "stand", "double", "rebuy", "deal", "skip"},
    "casino": {"cbet", "cclear", "crebuy", "cspin", "cundo", "cready"},
    "divan": {"dnext", "djoker", "dback", "dheart"},
    "tmc": {"tanswer", "tjudge", "tq", "treveal", "finish"},
    "quiz": {"qset", "qans", "qjoker", "qstop", "qpause"},
    "room": {"rvote"},
    "beerpong": {"bpset", "bphit", "bpsent", "bpreroll", "bpundo"},
}

# Actions de l'animateur (créateur de la partie) ; les autres sont ouvertes à tous les joueurs.
# Seuls coups possibles pendant une pause : reprendre, terminer, gérer les joueurs.
PAUSE_ALLOWED = {"pause", "resume", "end", "remove", "ban", "handover", "addguest", "leave", "join", "up", "down"}
HOST_ACTIONS = {"msset", "msswap", "msshow", "mshide", "msreveal", "rfset", "rfskip", "psyreveal", "pause", "resume", "bpset", "puset", "pureveal","ban", "start", "vote_start", "close_vote", "eliminate", "skip_guess", "next", "restart", "remove", "end", "up", "down", "names", "spin", "deal", "skip", "cspin", "tq", "finish", "tjudge", "addguest", "mvote",
                "pflip", "pbu", "pliar", "ppeek_ok", "ppeek_no", "pmemory", "presults", "pboat", "pboatgo", "paccept", "prefuse", "bclose", "qset", "handover", "nset", "hset",
                "lkset", "lkskip", "lkswap", "dbset", "dbskip", "dbswap", "dbrevote", "dbaccept", "dbrefuse"}


# « Signaler » une réponse du Masque ou un dilemme proposé (Apple 1.2) : retiré aussitôt pour la table, et noté dans le
# journal de l'admin (Réglages › Journal) avec le texte, son auteur et qui l'a signalé, pour bannir au besoin.
REPORT_ACTIONS = {"msreport", "dbreport"}


def log_game_report(g: dict, reporter: str, reported: dict, request: Request):
    def name(gid: str) -> str:
        return (games.player(g, gid) or {}).get("name", "")
    author = reported.get("author") or ""
    journal.record("game.report", name(reporter) or "Joueur", {"name": f'{games.GAMES.get(g["type"], g["type"])} ({g["code"]})', "id": g["code"]},
                   {"text": reported.get("text", ""), "author": name(author) if author else reported.get("by", ""),
                    "author_id": author}, client_ip(request))


@app.post("/api/games/{code}")
def game_action(code: str, body: GameAction, request: Request):
    # Chaque action est atomique entre téléphones, dans tous les jeux (dernière mise, dernier vote…).
    with GAMES_LOCK:
        return perform_game_action(code, body, request)


def perform_game_action(code: str, body: GameAction, request: Request):
    check_guest_id(body.guest_id)
    g = get_game(code)
    check_store_game(request, g["type"])
    game_presence(request, body.guest_id, body.name)
    if body.action == "join":
        if g["type"] in ACCOUNT_GAMES:
            require_account(body.token, body.guest_id, client_ip(request))
        reclaim_seat(g, body.guest_id, clean_name(body.name), client_ip(request))
    body.guest_id = canonical_gid(g, body.guest_id)
    sync_player_name(g, body.guest_id, body.name)
    admin_lead(g, request, body.guest_id)
    a, me = body.action, body.guest_id
    if g["type"] == "president" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "up", "down", "handover", "end", "prplay", "prpass", "prexchange", "pause", "resume"}:
        raise HTTPException(400, "Action indisponible au Président")
    if g["type"] == "heist" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "hset", "pause", "resume"}:
        raise HTTPException(400, "Action indisponible au Braquage")
    if g["type"] == "island" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "pause", "resume"}:
        raise HTTPException(400, "Action indisponible sur l’île")
    if g["type"] == "neon" and a not in {"join", "leave", "start", "next", "restart", "remove", "ban", "handover", "end", "nset", "nteam", "pause", "resume"}:
        raise HTTPException(400, "Action indisponible dans Néon Knockout")
    if g["type"] == "purity" and a not in PURITY_ACTIONS:
        raise HTTPException(400, "Action indisponible au Purify Test")
    if g["type"] != "purity" and a in PURITY_ONLY:
        raise HTTPException(400, "Action inconnue")
    if g["type"] == "likely" and a not in LIKELY_ACTIONS:
        raise HTTPException(400, "Action indisponible dans ce jeu")
    if g["type"] != "likely" and a in LIKELY_ONLY:
        raise HTTPException(400, "Action inconnue")
    if g["type"] == "debate" and a not in DEBATE_ACTIONS:
        raise HTTPException(400, "Action indisponible dans ce jeu")
    if g["type"] != "debate" and a in DEBATE_ONLY:
        raise HTTPException(400, "Action inconnue")
    if g["type"] == "psy" and a not in PSY_ACTIONS:
        raise HTTPException(400, "Action indisponible dans ce jeu")
    if g["type"] != "psy" and a in PSY_ONLY:
        raise HTTPException(400, "Action inconnue")
    if g["type"] == "masque" and a not in MASQUE_ACTIONS:
        raise HTTPException(400, "Action indisponible dans ce jeu")
    if g["type"] != "masque" and a in MASQUE_ONLY:
        raise HTTPException(400, "Action inconnue")
    if g["type"] == "reflet" and a not in REFLET_ACTIONS:
        raise HTTPException(400, "Action indisponible dans ce jeu")
    if g["type"] != "reflet" and a in REFLET_ONLY:
        raise HTTPException(400, "Action inconnue")
    # Cible d'un vote : un joueur (pid) ; pour « Je n'ai jamais », une réponse (yes / no).
    target = games.gid_of(g, body.target) or (body.target if g["type"] in ("never", "casino", "pyramid", "biskit") else "")
    # Pyramide : l'animateur peut agir pour un joueur (participant sans téléphone, ou qui traîne).
    actor = games.gid_of(g, body.who) if body.who and games.is_lead(g, me) and games.gid_of(g, body.who) else me
    # Blackjack, Casino : l'animateur mise et joue pour un participant sans téléphone (jamais pour un autre joueur).
    seat = actor if actor != me and games.is_manual(g, actor) else me
    if any(a in only and g["type"] != kind for kind, only in GAME_ONLY_ACTIONS.items()):
        raise HTTPException(400, "Action indisponible dans ce jeu")
    # Pyramide, Biskit : leurs coups n'existent qu'une fois la partie lancée.
    if (a in GAME_ONLY_ACTIONS["pyramid"] and not g.get("pyr")) or (a in GAME_ONLY_ACTIONS["biskit"] and not g.get("bk")):
        raise HTTPException(409, "La partie n'a pas encore commencé")
    if a in HOST_ACTIONS and not games.is_lead(g, me):
        raise HTTPException(403, "Seul l'animateur de la partie peut faire ça")
    if g.get("paused") and a not in PAUSE_ALLOWED:
        raise HTTPException(409, "⏸ La partie est en pause : l'animateur la relance")
    if a == "join" and (msg := ban_message(me, client_ip(request))):
        raise HTTPException(403, msg)
    # Invité au bout de ses parties en invité : une NOUVELLE partie demande un compte (sa place, elle, reste).
    if a == "join" and g["type"] != "room" and not games.player(g, me) and not gate_free(me, request) \
            and guest_gate.blocked(me, g["code"]):
        raise gate_games_refused(me, g["code"])
    if a == "end":
        end_game(g["code"], "host")
        return None
    if g["type"] == "room" and a == "launch":
        if not games.is_lead(g, me):
            raise HTTPException(403, "Seul l'animateur lance les jeux")
        check_store_game(request, body.settings.get("type", ""))
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
        "bet": (games.bj_bet, seat, body.amount), "hit": (games.bj_hit, seat), "stand": (games.bj_stand, seat),
        "double": (games.bj_double, seat), "rebuy": (games.bj_rebuy, seat),
        "deal": (games.bj_deal,), "skip": (games.bj_force_stand,),
        "cbet": (games.casino_bet, seat, body.target, body.amount), "cclear": (games.casino_clear, seat),
        "crebuy": (games.casino_rebuy, seat), "cspin": (games.casino_spin,),
        "cundo": (games.casino_undo, seat), "cready": (games.casino_ready, seat, random),
        "dnext": (games.divan_next, me), "djoker": (games.divan_joker, me), "dback": (games.divan_back, me), "dheart": (games.divan_heart, me),
        "tanswer": (games.tmc_answer, me, body.guess), "tjudge": (games.tmc_judge, me, body.amount),
        "addguest": (games.add_guest, body.guess), "mvote": (games.vote_for, target, body.guess),
        "rvote": (games.room_vote, me, body.target),
        "pause": (games.pause_game, me), "resume": (games.resume_game,),
        "bpset": (games.bp_call, beerpong.configure if g["phase"] == "lobby" else beerpong.configure_live, body.settings),
        "bphit": (games.bp_mark, me, beerpong.hit, body.settings.get("team"), body.settings.get("cup"), body.settings.get("pid"), random),
        "bpsent": (games.bp_mark, me, beerpong.sentence, body.amount, random),
        "bpreroll": (games.bp_mark, me, beerpong.reroll, random), "bpundo": (games.bp_mark, me, beerpong.undo),
        "tq": (games.tmc_change_question,), "treveal": (games.tmc_reveal, me), "finish": (games.tmc_finish,),
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
        "broll": (games.bk_roll, actor, games.is_lead(g, me) and actor != me, random),
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
        "puset": (purity.configure, body.settings), "puans": (purity.answer, me, body.amount, body.done),
        "pusub": (purity.submit, me), "puunsub": (purity.unsubmit, me), "pureveal": (games.purity_reveal,),
        "lkset": (likely.configure, body.settings), "lkvote": (games.lk_vote, actor, target, me),
        "lkskip": (games.lk_skip, target), "lkswap": (games.lk_swap, random),
        "psyans": (games.psy_answer, me, body.settings.get("q"), body.settings.get("a")),
        "psysub": (games.psy_submit, me), "psyreveal": (games.psy_reveal,),
        "dbset": (debate.configure, body.settings), "dbvote": (games.db_vote, actor, body.amount if "amount" in body.model_fields_set else None, me),
        "dbskip": (games.db_skip, target), "dbswap": (games.db_swap, random), "dbrevote": (games.db_revote,),
        "dbpropose": (games.db_propose, me, body.guess), "dbaccept": (games.db_accept, body.amount),
        "dbrefuse": (games.db_refuse, body.amount), "dbreport": (games.db_report, me),
        "msset": (masque.configure, body.settings), "mswrite": (masque.write, me, body.guess, random),
        "msswap": (masque.swap, random), "msshow": (masque.show, random),
        "msguess": (masque.guess, me, body.settings.get("picks"), body.settings.get("unmask")),
        "mshide": (masque.hide, body.amount), "msreveal": (masque.reveal,),
        "msreport": (masque.report, me, body.amount),
        "rfset": (reflet.configure, body.settings), "rfpick": (reflet.pick, me, body.settings.get("i"), body.settings.get("bet")),
        "rfswap": (reflet.swap, me, games.is_lead(g, me), random), "rfvote": (reflet.vote, me, body.done),
        "rfskip": (reflet.skip, target),
    }
    if g["type"] == "quiz" and a == "next":
        actions["next"] = (quiz.next_step, random, body.guess)
    if a not in actions:
        raise HTTPException(400, "Action inconnue")
    fn, *args = actions[a]
    try:
        action_result = fn(g, *args)
    except (games.GameError, quiz.QuizError, purity.PurityError, president.PresidentError, neon.NeonError, island.IslandError,
            heist.HeistError, likely.LikelyError, debate.DebateError, masque.MasqueError, reflet.RefletError) as e:
        raise HTTPException(409, str(e))
    g["updated_at"] = time.time()
    if a in REPORT_ACTIONS and action_result:
        log_game_report(g, me, action_result, request)
    if a == "join" and g["type"] != "room" and not gate_free(me, request):
        guest_gate.record(me, g["code"])
    # Salle de jeux : rejoindre, quitter, exclure ou passer la main vaut aussi pour le jeu en cours (et inversement).
    other = room_child(g) if g["type"] == "room" else room_of(g)
    if other:
        other["updated_at"] = time.time()
        try:
            if a == "join" and me not in other.get("kicked", []):
                # Purify Test en cours dans la salle : seuls les comptes connectés y entrent. Jeu en cours de la
                # salle : un invité au bout de ses parties en invité reste dans la salle, sans y être inscrit.
                if (other["type"] not in ACCOUNT_GAMES or seat_linked(g, me)) \
                        and (g["type"] != "room" or seat_linked(g, me) or gate_enter(other, me, request)):
                    games.join(other, me, clean_name(body.name))
            elif a == "leave" and games.player(other, me):
                games.leave(other, me)
            elif a == "remove" and target and games.player(other, target):
                games.kick(other, target)
            elif a == "ban" and target:
                games.ban(other, target)
            elif a == "handover" and target:
                # Le nouvel animateur l'est aussi de l'autre (salle ou jeu) ; l'ancien y reste joueur.
                other["host"], other["host_name"] = target, g["host_name"]
                if me in other.get("leads", []):
                    other["leads"].remove(me)
            elif a == "addguest" and g["type"] == "room" and other["type"] in games.MANUAL_GAMES:
                games.add_guest(other, body.guess, action_result["id"])
        except games.GameError:
            pass
    if not g["players"] and not g["host"]:
        store.session.games.pop(g["code"], None)
    save_games(g["code"], g.get("room") or "", g.get("current") or "")
    return with_gate(full_view(g, me), me, request, g["code"])


@app.get("/api/purity/leaderboard")
def purity_leaderboard():
    """Classement général du Purify Test (record d'impureté de chaque compte) ; sans identifiant de compte."""
    return purity.leaderboard()


class PurityPublic(AccountToken):
    on: bool


@app.post("/api/purity/me/public")
def purity_me_public(body: PurityPublic, request: Request):
    """Son choix « apparaître dans le classement général du Purify Test » (désactivé par défaut)."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    try:
        gid = accounts.verified_gid(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))
    return purity.set_public(gid, body.on)


@app.post("/api/purity/me")
def purity_me(body: AccountToken, request: Request):
    """Réglages : stats Purify Test du compte connecté (dernier test par catégorie, record), pour lui seul."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    try:
        gid = accounts.verified_gid(body.token)
    except AccountError as e:
        raise HTTPException(401, str(e))
    account_limiter.success(ip)
    return purity.profile(gid)


# 🧠 Méninges : entraînement cérébral solo (mini-jeux dans le navigateur, résultats et stats ici).
BRAIN_GAME_ID = r"^[a-z_]{2,20}$"
# Méninges sans fin : limites de forme seulement (valeurs absurdes refusées) ; le plausible est borné par brain.validate.
BRAIN_SCORE_LIMIT = 1_000_000_000
BRAIN_LEVEL_LIMIT = 9999
BRAIN_DURATION_LIMIT_MS = 24 * 3600 * 1000


class BrainResult(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    game: str = Field(pattern=BRAIN_GAME_ID)
    score: int = Field(ge=0, le=BRAIN_SCORE_LIMIT)  # bien au-delà du plafond : brain.validate borne, ne refuse pas
    accuracy: float = Field(ge=0, le=1)
    avg_rt_ms: int = Field(default=0, ge=0, le=60_000)
    level: int = Field(default=1, ge=1, le=BRAIN_LEVEL_LIMIT)
    duration_ms: int = Field(ge=0, le=BRAIN_DURATION_LIMIT_MS)


class BrainCompare(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    target: str | None = Field(default=None, pattern=UUID)


class BrainLocalSession(BaseModel):
    game: str = Field(pattern=BRAIN_GAME_ID)
    score: int = Field(ge=0, le=BRAIN_SCORE_LIMIT)
    accuracy: float | None = Field(default=None, ge=0, le=1)
    avg_rt_ms: int = Field(default=0, ge=0, le=60_000)
    level: int = Field(default=1, ge=1, le=BRAIN_LEVEL_LIMIT)
    duration_ms: int = Field(default=0, ge=0, le=BRAIN_DURATION_LIMIT_MS)
    played_at: str = Field(max_length=40)


class BrainLocal(BaseModel):
    sessions: list[BrainLocalSession] = Field(default_factory=list, max_length=brain.LOCAL_MAX)


class BrainGame(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    game: str = Field(pattern=BRAIN_GAME_ID)


class BrainGameLocal(BrainLocal):
    game: str = Field(pattern=BRAIN_GAME_ID)


def brain_account(request: Request, work):
    """Appel Méninges au nom du compte : mêmes garde-fous que le Purify Test (limite par adresse, jeton vérifié)."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    try:
        result = account_call(work, 401)
    except brain.BrainUnavailable as e:   # panne passagère : 503, le téléphone garde la partie et la renverra
        raise HTTPException(503, str(e))
    except brain.BrainError as e:
        raise HTTPException(400, str(e))
    account_limiter.success(ip)
    return result


@app.get("/api/brain/catalog")
def brain_catalog():
    """Domaines et jeux de Méninges (libellés pour les écrans de stats)."""
    return brain.catalog()


@app.post("/api/brain/result")
def brain_result(body: BrainResult, request: Request, response: Response):
    """Fin d'une partie de Méninges : le résultat (borné) est enregistré pour le compte connecté."""
    try:
        result = brain.validate(body.game, body.score, body.accuracy, body.avg_rt_ms, body.level, body.duration_ms)
    except brain.BrainError as e:
        raise HTTPException(400, str(e))
    out = brain_account(request, lambda: brain.BrainStore(accounts).record(body.token, result))
    with contextlib.suppress(AccountError):   # 🧠 bandeau « Zicou est fier de toi » (le bonus vient de la base)
        gid = accounts.gid(accounts._uid(body.token))
        zicou_react(gid, "brain", f"{result['game']}:{time.time_ns()}")
        if items := zicou_now(response, gid):   # seulement s'il y a un bandeau (réponse de Méninges inchangée sinon)
            out = {**out, "zicou": items}
    return out


@app.post("/api/brain/me")
def brain_me(body: AccountToken, request: Request):
    """Profil Méninges du compte connecté : Température, domaines, jeux, série, évolution, forces et faiblesses."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    return brain_account(request, lambda: brain.BrainStore(accounts).me(body.token))


@app.post("/api/brain/compare")
def brain_compare(body: BrainCompare, request: Request):
    """Classement Méninges entre amis (Température), percentile, et le profil d'un membre à comparer."""
    return brain_account(request, lambda: brain.BrainStore(accounts).compare(body.token, body.target))


@app.post("/api/brain/local")
def brain_local(body: BrainLocal):
    """Joueur non connecté : même profil, calculé à partir des parties gardées sur son téléphone (rien n'est enregistré)."""
    return brain.profile([s.model_dump() for s in body.sessions])


@app.post("/api/brain/game")
def brain_game_stats(body: BrainGame, request: Request):
    """Statistiques d'un jeu de Méninges pour le compte connecté (écran de fin enrichi, fiche du jeu)."""
    return brain_account(request, lambda: brain.BrainStore(accounts).game(body.token, body.game))


@app.post("/api/brain/game/local")
def brain_game_local(body: BrainGameLocal):
    """Joueur non connecté : statistiques d'un jeu, calculées à partir des parties gardées sur son téléphone."""
    try:
        return brain_game.game_detail([s.model_dump() for s in body.sessions], body.game)
    except brain.BrainError as e:
        raise HTTPException(400, str(e))


# 🥚 Compagnon : personnage à entretenir (app/pet.py pour la vie, app/pet_store.py pour la base). Compte requis.
pet_party_log = pet_store.PartyLog(DATA_DIR / "pet_party.json")
PET_ACTIONS = Literal["feed", "play", "cuddle", "sleep", "wake", "heal", "rename", "outfit", "new_egg",
                      "chest", "bonus_chest", "tuck", "treat",   # ces 4 : boucle du jour (app/pet_loop.py)
                      "adopt",   # adoption explicite : seule action qui pond le premier œuf
                      "bar"]     # barre « petit cadeau » pleine : récupérer (app/pet_bar.py)


class PetAct(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    action: PET_ACTIONS
    score: int = Field(default=0, ge=0, le=pet.PLAY_SCORE_MAX)   # ancien score déclaré : ignoré (voir game, hits)
    game: str = Field(default="", max_length=120, pattern=r"^[0-9a-f.]*$")   # jeton de partie (/api/pet/game)
    hits: int = Field(default=0, ge=0, le=200)                             # notes attrapées (vérifiées)
    name: str = Field(default="", max_length=60)
    outfit: str = Field(default="", pattern=r"^[a-z]{0,20}$")
    item: str = Field(default="", pattern=r"^[a-z]{0,20}$")   # goûter rare du sac (action treat)


class PetMe(AccountToken):
    # D'où vient l'ouverture (mesure, table pet_opens) : onglet Jeux, notification, widget, lien direct.
    # « none » : relecture dans le même panneau (après l'éclosion…), pas une nouvelle ouverture.
    src: Literal["tab", "notif", "notification", "widget", "link", "none"] = "tab"


class PetFriend(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    friend: str = Field(pattern=UUID)


class PetGift(PetFriend):
    kind: Literal["hug", "snack", "feast_pizza", "feast_fondue"]   # festin : payé en pièces par celui qui offre


pet_rate = pet_store.AccountRate()


def pet_call(request: Request, work, token: str = ""):
    """Appel au nom du compte : mêmes garde-fous que Méninges (limite par adresse, jeton vérifié), plus un débit
    maximal par compte (60 appels par minute)."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    if token and not pet_rate.allow(pet_store.rate_key(token)):
        raise HTTPException(429, "Doucement 🙂 Ton Zicou reprend son souffle, réessaie dans une minute.")
    try:
        result = account_call(work, 401)
    except pet_store.PetUnavailable as e:
        raise HTTPException(503, str(e))
    except pet_store.PetConflict as e:
        raise HTTPException(409, str(e))
    except pet.PetError as e:
        raise HTTPException(400, str(e))
    account_limiter.success(ip)
    return result


# Clé du serveur Party pour le Compagnon : PET_SECRET, sinon une clé créée une fois dans DATA_DIR (0600) et enrôlée.
PET_SECRET, PET_SECRET_FROM_ENV = pet_store.load_secret(DATA_DIR)


def pet_service() -> pet_store.PetStore:
    return pet_store.PetStore(accounts, pet_party_log, secret=PET_SECRET, enroll=not PET_SECRET_FROM_ENV)


@app.post("/api/pet/me")
def pet_me(body: PetMe, request: Request):
    """Mon compagnon, vécu jusqu'à maintenant (sans Zicou : {"adopted": false}, rien n'est pondu ; l'œuf ne vient
    que de l'action « adopt »), avec les nouvelles (bonus, cadeaux, évolution)
    et la boucle du jour (coffre, série, missions, rituels). Compte une ouverture (src) pour la mesure."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    return pet_call(request, lambda: pet_service().me(body.token, body.src), body.token)


@app.post("/api/pet/status")
def pet_status(body: AccountToken, request: Request):
    """Pastille Zicou (en-tête de chaque onglet, onglet Zicou) : humeur et besoin, sans pondre d'œuf ni rien enregistrer."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    return pet_call(request, lambda: pet_service().status(body.token), body.token)


# 🪩 Réactions de Zicou (app/pet_reactions.py) : petits bandeaux « +5 🪙 pour Zicou » après un titre ajouté, une partie
# terminée, une partie de Méninges. Jamais de notification push ; coupables dans Réglages › Compagnon. Une réponse de
# l'API porte l'en-tête X-Zicou quand un bandeau attend : la page (app/static/pet/reactions.js) vient alors le chercher.
ACCOUNT_GID = r"^acct-[0-9a-f]{40}$"
ZICOU_HEADER = "X-Zicou"


class ZicouReactions(BaseModel):
    guest_id: str = Field(pattern=ACCOUNT_GID)
    token: str = Field(default="", max_length=4095)   # facultatif : sert une fois, à savoir s'il a déjà un Zicou


class ZicouReactionsPrefs(BaseModel):
    guest_id: str = Field(pattern=ACCOUNT_GID)
    on: bool | None = None   # None : simple lecture du choix (écran Réglages)


def zicou_react(gid: str, kind: str, key: str) -> None:
    """Bonus de Zicou (bandeau) : rien ne se calcule quand le Compagnon est éteint (production, voir app/features.py)."""
    if compagnon_enabled():
        pet_party_log.react(gid, kind, key)


def zicou_now(response: Response, gid: str) -> list[dict]:
    """Bandeaux à montrer tout de suite, dans la réponse même (file, Méninges ; l'écran Musique natif de l'iPhone les
    lit aussi). Un bandeau qui attend encore (Zicou pas encore connu du serveur) : en-tête X-Zicou, la page ira le
    chercher avec son jeton."""
    if not gid.startswith("acct-") or not compagnon_enabled():
        return []
    items = pet_party_log.take(gid)
    if pet_party_log.has_pending(gid):
        response.headers[ZICOU_HEADER] = "1"
    return items


def zicou_known(gid: str, token: str) -> None:
    """Premier bandeau d'un compte que le serveur ne connaît pas encore : a-t-il un Zicou ? (lecture seule, une fois)"""
    if pet_party_log.known(gid) or not 20 < len(token) < 4096 or accounts.gid(accounts._uid(token)) != gid:
        return
    pet_service().status(token)   # note l'état du Zicou (ou son absence) dans pet_party_log


@app.post("/api/pet/reactions")
def zicou_reactions(body: ZicouReactions, request: Request):
    """Bandeaux de Zicou à montrer maintenant (retirés de la file) et choix « réactions activées »."""
    if not pet_rate.allow("zicou:" + body.guest_id):
        raise HTTPException(429, "Doucement 🙂")
    if pet_party_log.has_pending(body.guest_id):
        with contextlib.suppress(AccountError, pet.PetError):   # base injoignable : les bandeaux attendent
            zicou_known(body.guest_id, body.token)
    return {"enabled": pet_party_log.enabled(body.guest_id), "items": pet_party_log.take(body.guest_id)}


@app.post("/api/pet/reactions/prefs")
def zicou_reactions_prefs(body: ZicouReactionsPrefs):
    """Réglages › Compagnon : « Réactions de Zicou » (bandeaux dans l'app, jamais de notification)."""
    if body.on is None:
        return {"enabled": pet_party_log.enabled(body.guest_id)}
    return {"enabled": pet_party_log.set_enabled(body.guest_id, body.on)}


# Chemins du Compagnon : tous répondent 404 quand il est éteint (production tant qu'il est en bêta, app/features.py).
COMPAGNON_PATHS = ("/api/pet/", "/api/tv/zicou", "/zicou/", "/static/pet/")


# Discussions éteintes (production) : leurs routes répondent 404 ; le blocage d'une personne reste (toute l'app).
DISCUSSIONS_PATHS = ("/api/account/chats",)
DISCUSSIONS_KEPT = ("/api/account/chats/block",)
DISCUSSIONS_OFF = "Les discussions ne sont pas disponibles."


@app.middleware("http")
async def discussions_off(request: Request, call_next):
    path = request.url.path
    if path.startswith(DISCUSSIONS_PATHS) and not path.startswith(DISCUSSIONS_KEPT) and not discussions_enabled():
        return JSONResponse({"detail": DISCUSSIONS_OFF}, status_code=404, headers=NO_CACHE)
    return await call_next(request)


@app.middleware("http")
async def compagnon_off(request: Request, call_next):
    """Compagnon éteint : aucune de ses routes ne répond (404 « Le Compagnon arrive bientôt. »), rien ne se calcule."""
    if request.url.path.startswith(COMPAGNON_PATHS) and not compagnon_enabled():
        return JSONResponse({"detail": COMPAGNON_SOON}, status_code=404, headers=NO_CACHE)
    return await call_next(request)


@app.middleware("http")
async def zicou_reaction_header(request: Request, call_next):
    """En-tête X-Zicou sur les réponses de l'API d'un compte dont un bandeau attend (guest_id dans l'adresse ; la file
    et Méninges les renvoient elles-mêmes, voir zicou_now)."""
    response = await call_next(request)
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/pet/") and compagnon_enabled():
        gid = request.query_params.get("guest_id", "")
        if gid.startswith("acct-") and pet_party_log.has_pending(gid):
            response.headers[ZICOU_HEADER] = "1"
    return response


@app.post("/api/pet/act")
def pet_act(body: PetAct, request: Request):
    """Une action : nourrir, jouer (score du micro-jeu), câliner, lumière, soigner, nom, tenue, nouvel œuf ; coffre du
    jour, coffre bonus, coucher, goûter rare."""
    return pet_call(request, lambda: pet_service().act(body.token, body.action, body.score, body.name, body.outfit,
                                                       body.item, body.game, body.hits), body.token)


@app.post("/api/pet/game")
def pet_game(body: AccountToken, request: Request):
    """Une partie du jeu des notes commence : jeton signé par le serveur (le score sera calculé par lui à la fin)."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    return pet_call(request, lambda: pet_service().game(body.token), body.token)


@app.post("/api/pet/friends")
def pet_friends(body: AccountToken, request: Request):
    """Compagnons des membres de mes groupes (ce qui est montrable seulement)."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    return pet_call(request, lambda: pet_service().friends(body.token), body.token)


@app.post("/api/pet/friend")
def pet_friend(body: PetFriend, request: Request):
    return pet_call(request, lambda: pet_service().friend(body.token, body.friend), body.token)


class PetProfile(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    member: str = Field(pattern=UUID)


@app.post("/api/pet/profile")
def pet_profile_card(body: PetProfile, request: Request):
    """Fiche profil d'un membre (jeux, Événements, Discussions, app iPhone) : l'apparence publique de son Zicou, ou
    « pas encore de Zicou ». Lecture seule. 404 si le membre est introuvable ou bloqué (et quand le Zicou est éteint)."""
    card = pet_call(request, lambda: pet_service().profile(body.token, body.member), body.token)
    if card is None:
        raise HTTPException(404, "Profil indisponible")
    return JSONResponse(card, headers=NO_CACHE)


@app.post("/api/pet/gift")
def pet_gift(body: PetGift, request: Request):
    """Câlin, goûter ou festin (payé en pièces gagnées) pour le Zicou d'un ami : un par ami et par jour (la base y
    veille). Un festin offre un EFFET, jamais des pièces."""
    return pet_call(request, lambda: pet_service().gift(body.token, body.friend, body.kind), body.token)


# 🪙 Caisse commune du groupe (app/pet_pot.py) : sans classement, pièces gagnées seulement.
class PetPotGive(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    coins: int = Field(ge=10, le=250)


@app.post("/api/pet/pot")
def pet_pot_view(body: AccountToken, request: Request):
    return pet_call(request, lambda: pet_pot.get(pet_service(), body.token), body.token)


@app.post("/api/pet/pot/give")
def pet_pot_give(body: PetPotGive, request: Request):
    return pet_call(request, lambda: pet_pot.give(pet_service(), body.token, body.coins), body.token)


# 🌟 Zicou en vedette à l'Apple TV (app/tv_star.py) : 150 pièces, une fois par soirée, file d'attente ; la musique et
# l'accès aux parties ne sont jamais touchés.
tv_stars = tv_star.TvStars()
pet_public_pot = pet_pot.PublicPot(accounts)
STAR_SEEN_SECONDS = 3 * 3600   # « présent » : passé par la soirée dans les 3 dernières heures (ou accès sans code)


def soiree_key() -> str:
    s = store.session
    return f"{int(s.started_at or 0)}" if s.active else ""


def star_present(uid: str) -> bool:
    """Présent à la soirée en cours : accès sans code (événement lié) ou invité actif avec ce compte."""
    if uid in tv_present_accounts():
        return True
    seen = store.last_seen.get(accounts.gid(uid))
    return bool(seen and time.time() - seen < STAR_SEEN_SECONDS)


def star_call(token: str, book: bool) -> dict:
    uid = accounts._uid(token)
    soiree = soiree_key()
    if not soiree:
        return {"open": False, "price": tv_star.PRICE, "booked": None}
    if not star_present(uid):
        if book:
            raise pet.PetError("Le passage à l'Apple TV, c'est pour les présents de la soirée 🪩")
        return {"open": False, "price": tv_star.PRICE, "booked": None, "present": False}
    tv_stars.keep_only(soiree)
    booked = tv_star.book(tv_stars, pet_service(), accounts, token, uid, soiree) if book else tv_stars.status(uid, soiree)
    return {"open": True, "price": tv_star.PRICE, "booked": booked, "seconds": tv_star.SECONDS}


@app.post("/api/pet/star")
def pet_star_status(body: AccountToken, request: Request):
    return pet_call(request, lambda: star_call(body.token, False), body.token)


@app.post("/api/pet/star/book")
def pet_star_book(body: AccountToken, request: Request):
    return pet_call(request, lambda: star_call(body.token, True), body.token)


# Collection (lot A, app/pet_collection.py, app/pet_coll_store.py) : Zicoudex, boutique, atelier, vitrine, certificats.
class PetColl(BaseModel):
    token: str = Field(min_length=21, max_length=4095)
    action: Literal["equip", "buy", "craft", "showcase", "feast", "dye", "dye_wear", "room"]
    item: str = Field(default="", max_length=40, pattern=r"^(snack:)?[a-z0-9-]{0,30}$")
    slot: str = Field(default="", pattern=r"^[a-z]{0,10}$")
    items: list[str] = Field(default_factory=list, max_length=3)
    title: str = Field(default="", max_length=80)


@app.post("/api/pet/collection")
def pet_collection_view(body: AccountToken, request: Request):
    """Écran Collection : Zicoudex (Mythiques masqués tant qu'on n'en a pas), boutique du jour, décor, atelier,
    chances du coffre, vitrine, certificats de ses Légendaires et Mythiques."""
    if not 20 < len(body.token) < 4096:
        raise HTTPException(400, "Jeton invalide")
    return pet_call(request, lambda: pet_service().collection(body.token), body.token)


@app.post("/api/pet/coll")
def pet_coll(body: PetColl, request: Request):
    """Porter un accessoire, acheter (pièces gagnées seulement), fabriquer (poussière), composer sa vitrine."""
    if any(not isinstance(i, str) or len(i) > 30 for i in body.items):
        raise HTTPException(422, "Objets illisibles")
    return pet_call(request, lambda: pet_coll_store.act(pet_service(), body.token, body.action, body.item, body.slot,
                                                         body.items, body.title), body.token)


@app.get("/api/pet/certificats/cle")
def pet_cert_key():
    """Clé publique (Ed25519) des certificats d'authenticité : chacun peut vérifier une signature."""
    return pet_coll_store.public_key(pet_service())


@app.get("/api/pet/verifier")
def pet_verify(request: Request, code: str = Query(default="", max_length=40)):
    """Vérifier un objet (code ZC-…) : certificat signé, numéro, provenance anonyme. Même sans compte."""
    ip = client_ip(request)
    if msg := account_limiter.blocked(ip):
        raise HTTPException(429, msg)
    try:
        return pet_coll_store.verify(pet_service(), code)
    except pet.PetError as e:
        raise HTTPException(400, str(e))


@app.get("/zicou/certificat")
def pet_certificate_page():
    """Page d'authenticité d'un objet du Compagnon (?code=ZC-…)."""
    return page("pet/verify.html")


@app.get("/qr/game/{code}.svg")
def game_qr(code: str):
    g = get_game(code)
    buf = io.BytesIO()
    segno.make(f"{guest_url()}?game={g['code']}", error="m").save(buf, kind="svg", scale=8, border=2, dark="#111", light="#fff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})


@app.post("/api/admin/games/close", dependencies=[Depends(require_admin)])
def admin_close_game(body: GameAction, request: Request):
    """L'hôte de la soirée peut fermer n'importe quelle partie (body.target = code)."""
    with GAMES_LOCK:
        end_game(body.target, "admin")
    log_admin(request, "admin.close_game", {"id": str(body.target), "name": ""})
    return admin_state()


# --- Invités ---

def public_sonos(snap: dict, guest_id: str = "", mine_of: set[str] | None = None) -> dict:
    """mine_of : demandes « à moi » (rid renvoyé) ; par défaut celles de guest_id."""
    names = {r.track_id: r.guest_name for r in store.session.requests if r.status != "removed"}
    owned = mine_of if mine_of is not None else ({guest_id} if guest_id else set())
    by_pos = requests_by_position(snap["upcoming"], store.pending())

    def view(t, eta):
        req = by_pos.get(t.get("pos"))  # la demande de CET exemplaire (doublons distincts)
        return {"title": t["title"], "artist": t["artist"], "art": art_url(t["art"]), "track_id": t["track_id"],
                "by": req.guest_name if req else names.get(t["track_id"]),
                "rid": req.id if req and req.guest_id in owned else None, "eta": eta,
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


class FeedbackIn(BaseModel):
    guest_id: str
    name: str = ""
    kind: str = "idea"
    text: str
    context: dict = {}
    # Jeton du compte : seul un compte avec le droit « Écrire un avis » (Guest+ et au-dessus) envoie un avis.
    token: str = Field(default="", max_length=4096)
    # Avis reformulé par l'IA et validé par la personne (« Oui, envoyer ») : revalidé ici, il pré-remplit le classement.
    ai: dict | None = None


FEEDBACK_RIGHT = "feedback.write"
FEEDBACK_CONTEXT = ("tab", "game", "platform", "os", "app")  # onglet, jeu ouvert, appareil (rempli par l'app)


def may_write_feedback(request: Request, token: str) -> bool:
    """Hôte (session admin) ou compte avec le droit « Écrire un avis » ; jamais un Guest ni un non connecté."""
    if is_admin(request):
        return True
    if not token:
        return False
    try:
        return FEEDBACK_RIGHT in accounts._perms(token)
    except AccountError:
        return False


FEEDBACK_MIN_LENGTH = 30  # assez pour qu'une idée ou un bug soit compréhensible
FEEDBACK_AI_MIN_LENGTH = 8  # reformulé par l'IA (titre et description clairs) : une phrase courte dictée suffit
FEEDBACK_ADMIN_MIN_LENGTH = 5  # l'admin note pour lui-même : un titre court suffit


@app.post("/api/feedback")
def send_feedback(body: FeedbackIn, request: Request):
    """Un invité propose une idée ou signale un bug (pas besoin du code de la soirée)."""
    check_guest_id(body.guest_id)
    if msg := ban_message(body.guest_id, client_ip(request)):
        raise HTTPException(403, msg)
    if not may_write_feedback(request, body.token):
        raise HTTPException(403, "Ton avis est réservé aux comptes Guest+ et plus : connecte-toi avec ton numéro, "
                                 "puis demande l'accès à un admin.")
    text = " ".join(body.text.split())[:1000]
    if body.kind not in FEEDBACK_KINDS:
        raise HTTPException(400, "Type de retour inconnu")
    # Pas de limite d'envoi : une personne peut écrire plusieurs avis à la suite (demande de l'admin, 29.10).
    context = {k: str(v)[:40] for k, v in body.context.items() if k in FEEDBACK_CONTEXT}
    kind, structured = body.kind, None
    if body.ai is not None:  # texte d'origine gardé tel quel + version structurée (type, zone, titre…)
        try:
            structured = ai_feedback.clean_draft(body.ai, games.GAMES, context)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        kind = structured["kind"]
        context["ai"] = structured
    minimum = FEEDBACK_AI_MIN_LENGTH if structured else FEEDBACK_MIN_LENGTH
    if len(text) < minimum:
        raise HTTPException(400, f"Écris au moins {minimum} caractères pour bien expliquer ton idée")
    context["site"] = feedback_site()[0]  # liste commune aux deux sites : d'où vient l'avis
    # Pas de prénom (invité qui n'a encore rien ajouté) : « Anonyme ». clean_name refuserait un prénom vide.
    name = " ".join(body.name.split())[:30] or "Anonyme"
    feedback.add(body.guest_id, name, kind, text, context)
    summary = structured["title"] if structured else text[:140]
    notify_admin({"title": f"{FEEDBACK_KINDS[kind]} de {name}", "body": summary, "url": "/admin#feedback", "tag": "feedback"},
                 kind="feedback")
    store.save()  # l'admin ouvert reçoit la mise à jour (pastille « Retours »)
    return {"mine": feedback.mine(body.guest_id)}


class FeedbackAiIn(BaseModel):
    guest_id: str
    token: str = Field(default="", max_length=4096)


class FeedbackAiConsent(FeedbackAiIn):
    accept: bool


class FeedbackAiRewrite(FeedbackAiIn):
    name: str = Field(default="", max_length=60)
    turns: list[Annotated[str, Field(max_length=ai_feedback.MAX_TURN * 2)]] = Field(min_length=1, max_length=ai_feedback.MAX_TURNS)
    context: dict = {}


def feedback_ai_subject(request: Request, body: FeedbackAiIn) -> str:
    """Qui écrit l'avis (accord, limite du jour, plafond) : son compte, sinon l'invité. Mêmes conditions que l'envoi
    d'un avis (droit « Écrire un avis » ou hôte) ; aucun droit « ai.use » n'est demandé."""
    check_guest_id(body.guest_id)
    if msg := ban_message(body.guest_id, client_ip(request)):
        raise HTTPException(403, msg)
    if not may_write_feedback(request, body.token):
        raise HTTPException(403, "Ton avis est réservé aux comptes Guest+ et plus.")
    if body.token:
        with contextlib.suppress(AccountError):
            return "acct:" + accounts._uid(body.token)
    return "guest:" + body.guest_id


@app.post("/api/feedback/ai/status")
def feedback_ai_status(body: FeedbackAiIn, request: Request):
    """L'IA peut-elle aider (configurée, accord donné ou à demander, reformulations restantes aujourd'hui) ?"""
    return feedback_writer.status(feedback_ai_subject(request, body))


@app.post("/api/feedback/ai/consent")
def feedback_ai_consent(body: FeedbackAiConsent, request: Request):
    """« J'accepte » / « Écrire sans l'IA » (feuille d'accord), ou retrait de l'accord dans Réglages."""
    subject = feedback_ai_subject(request, body)
    feedback_writer.consents.set(subject, body.accept)
    return feedback_writer.status(subject)


@app.post("/api/feedback/ai/rewrite")
def feedback_ai_rewrite(body: FeedbackAiRewrite, request: Request):
    """Texte dit ou écrit (puis précisions ou corrections) → avis structuré, ou une question courte.
    status « unavailable » (IA éteinte, budget, limite du jour, panne) : l'app laisse écrire l'avis sans l'IA."""
    subject = feedback_ai_subject(request, body)
    context = {k: str(v)[:40] for k, v in body.context.items() if k in FEEDBACK_CONTEXT}
    try:
        return feedback_writer.rewrite(subject, body.name, body.turns, context)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except ai_feedback.Unavailable as e:
        return {"status": "unavailable", "message": str(e)}


class FeedbackEdit(BaseModel):
    guest_id: str
    id: str = Field(max_length=40)
    text: str = Field(max_length=4000)
    token: str = Field(default="", max_length=4096)


FEEDBACK_CLOSED = "Cet avis est fermé"


@app.post("/api/feedback/edit")
def edit_feedback(body: FeedbackEdit, request: Request):
    """L'auteur réécrit son avis à tout moment (retour de l'admin, 08.11) : l'ancien texte et l'heure restent dans sa
    trace. Mêmes droits que pour l'écrire ; un avis terminé ou pas retenu ne change plus."""
    check_guest_id(body.guest_id)
    if msg := ban_message(body.guest_id, client_ip(request)):
        raise HTTPException(403, msg)
    if not may_write_feedback(request, body.token):
        raise HTTPException(403, "Modifier un avis est réservé aux comptes Guest+ et plus : connecte-toi avec ton numéro.")
    text = " ".join(body.text.split())[:1000]
    if len(text) < FEEDBACK_AI_MIN_LENGTH:
        raise HTTPException(400, f"Écris au moins {FEEDBACK_AI_MIN_LENGTH} caractères")
    try:
        item = feedback.edit_text(body.guest_id, body.id, text)
    except FeedbackUnavailable as e:
        raise HTTPException(503, str(e)) from None
    except ValueError as e:  # avis fermé (ici ou dit par la production)
        raise HTTPException(409 if str(e).startswith(FEEDBACK_CLOSED) else 400, str(e)) from None
    if item is None:
        raise HTTPException(404, "Avis introuvable")
    return {"mine": feedback.mine(body.guest_id)}


@app.get("/api/feedback")
def my_feedback(guest_id: str = ""):
    check_guest_id(guest_id)
    return {"mine": feedback.mine(guest_id)}


class FeedbackAction(BaseModel):
    ids: list[str] = Field(max_length=100)
    action: str
    note: str = Field(default="", max_length=10000)  # « note » : précisions / instructions de l'admin pour Claude
    reply: str = Field(default="", max_length=2000)  # « done » / « declined » : mot de l'admin pour l'invité
    priority: str = Field(default="", max_length=10)  # « priority » : high | medium | low | "" (retirée)
    # « edit » : champs de classement (statut, priorité, zone, plateformes, effort, étiquettes, liens, note, mot).
    fields: dict = Field(default_factory=dict)
    # « comment » : message du fil admin ↔ Claude, son auteur, et un statut à poser en même temps (facultatif).
    text: str = Field(default="", max_length=4000)
    author: str = Field(default="admin", max_length=10)
    status: str = Field(default="", max_length=12)


class FeedbackNew(BaseModel):
    """Avis écrit par l'admin (formulaire « Mon avis » ou « ＋ Nouvel avis », scripts de Claude) : classé dès la création."""
    kind: str = "idea"
    text: str = Field(max_length=4000)
    name: str = Field(default="", max_length=60)
    guest_id: str = Field(default="", max_length=80)  # l'admin le retrouve aussi dans « Mes retours »
    context: dict = Field(default_factory=dict)
    fields: dict = Field(default_factory=dict)  # status, priority, area, platforms, effort, tags, note, liens
    author: str = Field(default="admin", max_length=10)


MIN_CLAUDE_NOTE = 10  # Claude ne part pas sans instructions claires de l'admin


def feedback_payload() -> dict:
    """Avis (anciens complétés par les valeurs par défaut) et « meta » : statuts, zones, efforts… lus par le web et l'iOS."""
    return {"items": [feedback_with_defaults(i) for i in feedback.all()], "kinds": FEEDBACK_KINDS,
            "claude_ready": github.configured, "games": games.GAMES, "meta": feedback_meta()}


def sync_claude_fixes():
    """Retours confiés à Claude : l'état de leur issue (corrigé, échoué) revient dans l'admin."""
    for item in feedback.all():
        claude = item.get("claude") or {}
        # En cours, ou échoué sans raison connue (envoyé avant que le workflow ne la publie).
        if claude.get("state") != "pending" and not (claude.get("state") == "failed" and not claude.get("error")):
            continue
        try:
            state = github.state(claude["number"])
            error = github.failure_reason(claude["number"]) if state == "failed" else ""
            sha = github.fix_commit(claude["number"]) if state == "fixed" else ""
            migrations = github.migrations(claude["number"]) if state == "fixed" else []
            if state != claude["state"] or error:
                feedback.set_claude_state(item["id"], state, error, sha, migrations)
        except GitHubError as e:
            log.warning("Suivi de l'issue #%s impossible : %s", item["claude"]["number"], e)
            return  # GitHub injoignable : on réessaiera au prochain affichage


def feedback_site() -> tuple[str, str]:
    """D'où vient le retour : site de test (partytest…) ou production, avec son adresse."""
    url = configured_public_url()
    return ("Test" if "test" in (urlparse(url).hostname or "") else "Prod"), url


def feedback_prompt(item: dict) -> str:
    label, url = feedback_site()
    origin = (item.get("context") or {}).get("site") or label
    return build_prompt(item, f"{origin} ({url})" if origin == label else origin)


class FeedbackSync(BaseModel):
    op: str
    args: dict = {}


@app.post("/api/feedback-sync")
def feedback_sync(body: FeedbackSync, request: Request):
    """Production : le site de test lit et écrit la liste commune des avis (secret partagé, opérations des avis seules)."""
    given = request.headers.get(FEEDBACK_SYNC_HEADER, "")
    if len(FEEDBACK_SYNC_SECRET) < FEEDBACK_SYNC_MIN_SECRET or not hmac.compare_digest(given, FEEDBACK_SYNC_SECRET):
        raise HTTPException(403, "Synchronisation des avis refusée")
    if feedback is not local_feedback:
        raise HTTPException(409, "Ce serveur n'est pas celui qui garde les avis")
    operation = getattr(local_feedback, body.op, None) if body.op in FEEDBACK_SYNC_OPS else None
    if operation is None:  # inconnue, ou pas encore connue de ce serveur (version plus ancienne que le site de test)
        raise HTTPException(400, "Opération inconnue")
    try:
        result = operation(**body.args)
    except TypeError:
        raise HTTPException(400, "Paramètres invalides")
    except ValueError as e:  # message de validation, montré tel quel sur le site de test
        raise HTTPException(400, str(e) or "Paramètres invalides")
    if body.op in FEEDBACK_SYNC_WRITES:
        store.save()  # l'admin ouvert ici reçoit la mise à jour (pastille « Retours »)
    return {"result": result}


def feedback_item(fid: str) -> dict:
    item = feedback.get(fid)
    if item is None:
        raise HTTPException(404, "Retour introuvable")
    return item


@app.get("/api/admin/feedback", dependencies=[Depends(require_admin)])
def admin_feedback():
    sync_claude_fixes()
    return feedback_payload()


@app.post("/api/admin/feedback", dependencies=[Depends(require_admin)])
def admin_feedback_action(body: FeedbackAction):
    if body.action == "note":
        if len(body.ids) != 1:
            raise HTTPException(400, "Un seul retour à la fois")
        feedback_item(body.ids[0])
        feedback.set_note(body.ids[0], body.note)
        return feedback_payload()
    if body.action == "priority":
        try:
            feedback.set_priority(body.ids, body.priority)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return feedback_payload()
    if body.action == "edit":
        return feedback_edit(body.ids, body.fields)
    if body.action == "comment":
        return feedback_comment(body)
    if body.action not in FEEDBACK_STATUSES + ("delete",):
        raise HTTPException(400, "Action inconnue")
    if body.action == "declined" and not body.reply.strip():
        raise HTTPException(400, "Écris un mot pour l'invité : il verra pourquoi ce n'est pas retenu")
    try:
        finished = feedback.update(body.ids, body.action, body.reply)
    except ValueError as e:
        raise HTTPException(400, str(e))
    for item in finished:
        notify_feedback_finished(item)
    store.save()
    return feedback_payload()


def check_declined_reply(ids: list[str], fields: dict):
    """« Pas retenu » demande un mot pour l'invité : celui qu'on envoie, ou celui déjà écrit."""
    if fields.get("status") != "declined" or str(fields.get("reply", "")).strip():
        return
    if any(not (feedback_item(fid).get("reply") or "").strip() for fid in ids):
        raise HTTPException(400, "Écris un mot pour l'invité : il verra pourquoi ce n'est pas retenu")


def feedback_edit(ids: list[str], fields: dict) -> dict:
    """Classement d'un ou plusieurs avis en une fois (action générique « edit »)."""
    if not ids:
        raise HTTPException(400, "Choisis au moins un avis")
    check_declined_reply(ids, fields)
    try:
        finished = feedback.set_fields(ids, fields)
    except ValueError as e:
        raise HTTPException(400, str(e))
    for item in finished:
        notify_feedback_finished(item)
    store.save()
    return feedback_payload()


def feedback_comment(body: FeedbackAction) -> dict:
    """Fil admin ↔ Claude sur un avis (les scripts de Claude écrivent en « claude »)."""
    if len(body.ids) != 1:
        raise HTTPException(400, "Un seul retour à la fois")
    feedback_item(body.ids[0])
    if body.status in ("done", "declined"):
        raise HTTPException(400, "Terminé et Pas retenu se posent avec ✅ / 🚫 (l'invité est averti)")
    try:
        feedback.comment(body.ids[0], body.author, body.text, body.status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    store.save()
    return feedback_payload()


@app.post("/api/admin/feedback/new", dependencies=[Depends(require_admin)])
def admin_feedback_new(body: FeedbackNew, request: Request):
    """L'admin (ou Claude par ses scripts) écrit un avis et le classe tout de suite : statut, priorité, zone…
    Renvoie l'avis créé et la liste à jour."""
    if body.guest_id:
        check_guest_id(body.guest_id)
    if body.author not in FEEDBACK_AUTHORS:
        raise HTTPException(400, "Auteur inconnu")
    text = " ".join(body.text.split())[:1000]
    if len(text) < FEEDBACK_ADMIN_MIN_LENGTH:
        raise HTTPException(400, f"Écris au moins {FEEDBACK_ADMIN_MIN_LENGTH} caractères")
    if body.fields.get("status") in ("done", "declined"):
        raise HTTPException(400, "Un nouvel avis ne peut pas être déjà terminé")
    context = {k: str(v)[:40] for k, v in body.context.items() if k in ("tab", "game")}
    context["site"] = feedback_site()[0]
    name = " ".join(body.name.split())[:30] or ("Claude 🤖" if body.author == "claude" else "Admin")
    try:
        item = feedback.create_admin(body.guest_id or "admin", name, body.kind, text, context, body.fields, body.author)
    except ValueError as e:
        raise HTTPException(400, str(e))
    store.save()
    return {"item": feedback_with_defaults(item), **feedback_payload()}


def notify_feedback_finished(item: dict):
    """Retour terminé ou pas retenu : notification à l'invité (s'il les a autorisées) ; sa pastille s'allume aussi."""
    done = item["status"] == "done"
    notify_guest(item["guest_id"], {
        "title": "✅ Ton retour est terminé" if done else "💬 Réponse à ton retour",
        "body": item.get("reply") or item["text"][:120], "url": "/?tab=feedback", "tag": f"feedback-{item['id']}"},
        kind="feedback")


class FeedbackSeen(BaseModel):
    guest_id: str


@app.post("/api/feedback/seen")
def feedback_seen(body: FeedbackSeen):
    """L'invité a ouvert « Ton avis » : ses retours terminés ne sont plus signalés par la pastille."""
    check_guest_id(body.guest_id)
    feedback.mark_seen(body.guest_id)
    return {"mine": feedback.mine(body.guest_id)}


@app.get("/api/admin/feedback/{fid}/prompt", dependencies=[Depends(require_admin)])
def admin_feedback_prompt(fid: str):
    """Le prompt tel qu'il partira à Claude (aperçu, ou à copier quand GitHub n'est pas configuré)."""
    return {"prompt": feedback_prompt(feedback_item(fid))}


@app.post("/api/admin/feedback/{fid}/claude", dependencies=[Depends(require_admin)])
def admin_feedback_to_claude(fid: str):
    """Confie le retour à Claude : issue GitHub « claude-fix » → correction commitée sur develop."""
    item = feedback_item(fid)
    if item.get("claude", {}).get("state") == "pending":
        raise HTTPException(409, "Déjà confié à Claude : la correction est en cours")
    if len(item.get("note", "")) < MIN_CLAUDE_NOTE:
        raise HTTPException(400, "Ajoute d'abord tes instructions pour Claude (✏️)")
    if not github.configured:
        raise HTTPException(503, "GITHUB_TOKEN n'est pas configuré sur le serveur : copie le prompt à la place")
    title = f"[{feedback_site()[0]}] {FEEDBACK_KINDS.get(item['kind'], '')} {item['text'][:70]}".strip()
    try:
        issue = github.create(title, feedback_prompt(item))
    except GitHubError as e:
        log.warning("Envoi du retour %s à Claude refusé : %s", fid, e)
        raise HTTPException(502, str(e))
    feedback.mark_sent(fid, issue["number"], issue["url"])
    store.save()
    return feedback_payload()


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
        # Invité sans compte : titres encore possibles ce soir (None : compte, sans cette limite).
        "guest_tracks": guest_tracks(guest_id, request) if guest_id else None,
    }
    try:
        return {**base, **public_sonos(snapshot(), guest_id, owners(request, guest_id))}
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
    try:  # affiché aux autres joueurs et sur la TV : même filtre que les surnoms (app/moderation.py)
        return require_clean(name, "name")
    except ContentRefused as e:
        raise HTTPException(400, str(e))


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
def enqueue(body: Enqueue, request: Request, response: Response):
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
    if (tracks := guest_tracks(body.guest_id, request)) and tracks["left"] <= 0:
        raise HTTPException(403, {"message": tracks_refused_text(tracks["limit"]), "account_required": "music", **tracks})

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
    # 🪩 Titre accepté dans la file : petit bonus pour son Zicou (une fois par titre, plafonné par jour).
    zicou_react(body.guest_id, "music", track["id"])
    return {"ok": True, "track": track, "source": s.source, "zicou": zicou_now(response, body.guest_id)}


def guest_tracks(gid: str, request: Request) -> dict | None:
    """Titres proposés en invité ce soir (demandes de la soirée, même retirées) ; None : compte, hôte ou admin,
    sans autre limite que les règles existantes."""
    if gate_free(gid, request) or native_host(request):
        return None
    limit = guest_gate.settings()["tracks"]
    used = sum(1 for r in store.session.requests if r.guest_id == gid)
    return {"used": used, "limit": limit, "left": max(0, limit - used)}


def tracks_refused_text(limit: int) -> str:
    if limit == 0:
        return "Crée ton compte pour proposer des titres : 30 secondes, juste ton numéro."
    return (f"Tu as proposé tes {limit} titre{'s' if limit > 1 else ''} de la soirée en invité. "
            "Crée ton compte (juste ton numéro) pour en proposer d'autres.")


class GuestRemove(BaseModel):
    request_id: str
    guest_id: str


@app.post("/api/queue/remove", dependencies=[Depends(require_guest)])
def guest_remove(body: GuestRemove, request: Request):
    """Un invité retire un de ses propres titres encore en attente (l'hôte, dans l'app, aussi les siens d'hôte)."""
    require_active()
    mine = owners(request, body.guest_id)
    req = next((r for r in store.pending() if r.id == body.request_id and r.guest_id in mine), None)
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
    # Réglages natifs : l'iPhone s'abonne sans toucher aux types choisis. Sinon (bouton « Préviens-moi quand mon
    # titre passe ») l'abonnement allume aussi « Mon titre passe ».
    keep_prefs: bool = False


def checked_subscription(sub: dict) -> dict:
    if not valid_subscription(sub):
        raise HTTPException(400, "Abonnement invalide")
    return sub


@app.post("/api/push/subscribe", dependencies=[Depends(require_guest)])
def push_subscribe(body: PushSubscribe, request: Request):
    """L'invité veut être prévenu quand son titre passe. L'hôte dans l'app est aussi abonné pour ses titres
    ajoutés en tant qu'hôte (HOST_ID), avec les mêmes choix."""
    check_guest_id(body.guest_id)
    others = tuple(owners(request, body.guest_id) - {body.guest_id})
    if not body.keep_prefs:
        set_guest_pref((body.guest_id, *others), "track", True)
    store.add_push(body.guest_id, checked_subscription(body.subscription), also=others)
    return {"ok": True}


def set_guest_pref(guest_ids, kind: str, on: bool):
    for gid in guest_ids:
        store.session.guest_notify[gid] = {**store.session.guest_notify.get(gid, {}), kind: on}


@app.post("/api/admin/push/subscribe", dependencies=[Depends(require_admin)])
def admin_push_subscribe(body: PushSubscribe):
    """L'hôte veut être prévenu des nouveaux messages."""
    store.add_push(None, checked_subscription(body.subscription))
    return {"ok": True}


class AdminNotify(BaseModel):
    kind: str  # un type de ADMIN_NOTIFY_DEFAULTS
    on: bool


def admin_notify_payload() -> dict:
    return {"admin_notify": {**ADMIN_NOTIFY_DEFAULTS, **store.session.admin_notify}}


@app.get("/api/admin/notify", dependencies=[Depends(require_admin)])
def admin_notify_prefs():
    return admin_notify_payload()


@app.post("/api/admin/notify", dependencies=[Depends(require_admin)])
def admin_notify(body: AdminNotify):
    if body.kind not in ADMIN_NOTIFY_DEFAULTS:
        raise HTTPException(400, "Type inconnu")
    store.session.admin_notify[body.kind] = body.on
    store.save(notify=False)
    return admin_notify_payload()


def guest_notify_payload(guest_id: str) -> dict:
    return {"prefs": guest_prefs(guest_id), "subscribed": bool(store.session.push.get(guest_id))}


@app.get("/api/notify", dependencies=[Depends(require_guest)])
def guest_notify_prefs(guest_id: str):
    """Réglages › Notifications de l'invité : ce qu'il reçoit, et si un de ses appareils est abonné."""
    check_guest_id(guest_id)
    return guest_notify_payload(guest_id)


class GuestNotify(BaseModel):
    guest_id: str
    kind: str  # un type de GUEST_NOTIFY_DEFAULTS
    on: bool


@app.post("/api/notify", dependencies=[Depends(require_guest)])
def guest_notify(body: GuestNotify, request: Request):
    check_guest_id(body.guest_id)
    if body.kind not in GUEST_NOTIFY_DEFAULTS:
        raise HTTPException(400, "Type inconnu")
    set_guest_pref(owners(request, body.guest_id), body.kind, body.on)
    store.save(notify=False)
    return guest_notify_payload(body.guest_id)


APNS_HEX = r"^[0-9a-f]{64,200}$"


class ActivityToken(BaseModel):
    guest_id: str
    request_id: str = Field(max_length=64)
    token: str = Field("", pattern=r"^([0-9a-f]{64,200})?$")  # vide : l'activité n'est plus suivie
    environment: Literal["production", "sandbox"] = "production"
    topic: str = ""


@app.post("/api/activity", dependencies=[Depends(require_guest)])
def activity_token(body: ActivityToken, request: Request):
    """L'app a démarré la Live Activity d'un de ses titres : le serveur la tient à jour (app fermée comprise)."""
    check_guest_id(body.guest_id)
    if not body.token:
        store.session.activities.pop(body.request_id, None)
        _live.pop(body.request_id, None)
        store.save(notify=False)
        return {"ok": True}
    if body.topic not in TOPICS:
        raise HTTPException(400, "App inconnue")
    req = next((r for r in store.session.requests if r.id == body.request_id), None)
    if req is None or req.guest_id not in owners(request, body.guest_id):
        raise HTTPException(404, "Titre introuvable")
    store.session.activities[req.id] = {"token": body.token, "environment": body.environment, "topic": body.topic,
                                         "track_id": req.track_id, "owner": req.guest_id}
    _live.pop(req.id, None)  # la prochaine vue part tout de suite
    store.save(notify=False)
    return {"ok": True}


class ActivityStartToken(BaseModel):
    guest_id: str
    token: str = Field("", pattern=r"^([0-9a-f]{64,200})?$")  # vide : plus de démarrage par push (réglage coupé)
    environment: Literal["production", "sandbox"] = "production"
    topic: str = ""


@app.post("/api/activity/start", dependencies=[Depends(require_guest)])
def activity_start_token(body: ActivityStartToken, request: Request):
    """Jeton de démarrage (iOS 17.2+) : un titre ajouté pendant que l'app est fermée démarre sa Live Activity."""
    check_guest_id(body.guest_id)
    if body.token and body.topic not in TOPICS:
        raise HTTPException(400, "App inconnue")
    for owner in owners(request, body.guest_id):
        if body.token:
            store.session.activity_start_tokens[owner] = {"token": body.token, "environment": body.environment,
                                                          "topic": body.topic}
        else:
            store.session.activity_start_tokens.pop(owner, None)
    store.save(notify=False)
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


_pages: dict[tuple[str, bool, bool, bool], str] = {}
# Morceaux de page du Compagnon (onglet, pastilles, scripts) : retirés de la page quand il est éteint.
COMPAGNON_BLOCK = re.compile(r"[ \t]*<!-- compagnon -->.*?<!-- /compagnon -->\n?", re.S)


def compagnon_page(html: str) -> str:
    """Compagnon éteint : <html data-compagnon="off"> (lu par les scripts et le module Événements), morceaux retirés."""
    if compagnon_enabled():
        return html
    return COMPAGNON_BLOCK.sub("", html.replace("<html", '<html data-compagnon="off"', 1))


def discussions_page(html: str) -> str:
    """Discussions éteintes (production) : <html data-discussions="off">, lu par la page et le module Événements
    (ni onglet, ni « Écrire » sur les fiches, ni pastille)."""
    if discussions_enabled():
        return html
    return html.replace("<html", '<html data-discussions="off"', 1)


def invites_page(html: str) -> str:
    """Invitations v2 éteintes (production) : <html data-invites="off">, lu par le module Événements (ancienne carte
    « Lien d'invitation », inviter par numéro dans « Modifier »)."""
    if invites_v2_enabled():
        return html
    return html.replace("<html", '<html data-invites="off"', 1)


def features_page(html: str) -> str:
    return discussions_page(compagnon_page(invites_page(html)))


def page(name: str) -> Response:
    """Page HTML avec des adresses de scripts et de styles versionnées (mises en cache jusqu'au prochain déploiement)."""
    key = (name, compagnon_enabled(), discussions_enabled(), invites_v2_enabled())
    if key not in _pages:
        html = features_page((STATIC / name).read_text(encoding="utf-8"))
        _pages[key] = re.sub(r'(/static/[\w./-]+\.(?:js|css))(?=")', rf"\1?v={BUILD_ID}", html)
    return Response(_pages[key], media_type="text/html; charset=utf-8", headers=NO_CACHE)


@app.get("/")
def index(tab: str = Query("", max_length=20), event: str = Query("", max_length=40)):
    """Page de Party. Lien de « Partager le lien » d'un événement (/?tab=events&event=<id>) : aperçu de l'événement
    s'il est public (titre, date, image), rien sinon."""
    response = page("index.html")
    event_id = event_preview.event_id_of_query(tab, event)
    if not event_id:
        return response
    html = event_preview.with_preview(response.body.decode(), accounts, event_id, configured_public_url())
    return Response(html, media_type="text/html; charset=utf-8", headers=NO_CACHE)


@app.get("/admin")
def admin_page():
    return page("admin.html")


@app.get("/tv")
def tv_page():
    return page("tv.html")


TV_UPCOMING = 6  # prochains titres lisibles de loin sur la télé


@app.get("/api/tv", dependencies=[Depends(require_admin)])
def tv_state():
    """Écran TV de l'hôte (Apple TV via AirPlay) : titre en cours, prochaines demandes et qui les a faites,
    code et QR pour entrer, événement lié, parties de jeu en cours. Réservé à l'hôte : il affiche le code."""
    s = store.session
    base = {"active": s.active, "pin": s.guest_pin, "url": guest_url(), "event": s.event_title or None,
            "games": [{"code": g["code"], "name": g["name"], "players": len(g["players"])}
                      for g in map(games.summary, (prune_games() or s.games).values())]}
    if not s.active:
        return base
    try:
        music = public_sonos(snapshot())
    except Exception:
        return {**base, "error": "La musique est injoignable pour le moment"}
    return {**base, "room": s.room_name, "state": music["state"], "now": music["now"],
            "upcoming": [{k: t[k] for k in ("title", "artist", "art", "by")} for t in music["upcoming"][:TV_UPCOMING]]}


@app.get("/api/tv/game/{code}", dependencies=[Depends(require_admin)])
def tv_game(code: str):
    """App Apple TV : la partie vue en SPECTATEUR (aucun mot secret, aucune main cachée, aucun rôle avant la fin),
    rafraîchie chaque seconde par la télé. Mêmes avancées automatiques que pour les téléphones (fin d'une question…)."""
    with GAMES_LOCK:
        g = get_game(code)
        if not g.get("paused") and quiz.tick(g):
            g["updated_at"] = time.time()
            save_games(g["code"], g.get("room") or "")
        for engine in (heist, island, neon):
            if not g.get("paused") and engine.tick(g):
                save_games(g["code"])
        view = full_view(g, "")
        if g["type"] == "room" and (child := room_child(g)) is not None:
            view["current"] = full_view(child, "")  # Salle de jeux : le jeu lancé dans la salle
        return view


# 🪩 Les Zicou de la soirée sur l'Apple TV (app/tv_zicou.py) : aspect relu quand un présent revérifie son accès.
soiree_zicous = tv_zicou.SoireeZicous()


def refresh_soiree_zicou(token: str, uid: str) -> None:
    try:
        name, life = tv_zicou.read_member(accounts, pet_service(), token, uid)
    except (AccountError, pet.PetError):
        return   # base injoignable ou jeton expiré : l'ancien aspect reste (ou rien), réessayé au prochain passage
    soiree_zicous.note(uid, name, life)


def tv_present_accounts() -> set[str]:
    """Comptes notés « Présent » qui ont un accès sans code valide à la soirée en cours."""
    s = store.session
    if not (s.active and s.event_id):
        return set()
    revoked = set(s.revoked)
    return {uid for uid, nonce in s.event_passes.items() if nonce not in revoked}


def tv_watched_games(code: str) -> list[dict]:
    """La partie regardée par la télé et, pour une salle de jeux, le jeu qui y est lancé."""
    g = store.session.games.get(code) if code else None
    if not g:
        return []
    return [x for x in (g, room_child(g) if g.get("type") == "room" else None) if x]


def tv_player_accounts(code: str) -> set[str]:
    """Comptes (avec compte Party relié) qui jouent à la partie regardée, avec ou sans événement lié à la soirée."""
    uids = set()
    for game in tv_watched_games(code):
        for p in game.get("players", []):
            if p.get("manual"):
                continue
            uids |= {uid for gid in seat_ids(game, p["id"]) if gid.startswith("acct-") and (uid := accounts.uid_of(gid))}
    return uids


def tv_pid_finder(code: str):
    """Place (pid) d'un compte dans la partie regardée par la télé (et le jeu lancé dans une salle de jeux)."""
    seats = tv_watched_games(code)
    if not seats:
        return lambda gid: None

    def pid_of(gid: str) -> str | None:
        for game in reversed(seats):   # le jeu en cours de la salle d'abord : c'est lui qui annonce les gagnants
            for p in game.get("players", []):
                if not p.get("manual") and gid in seat_ids(game, p["id"]):
                    return p.get("pid")
        return None
    return pid_of


@app.get("/api/tv/zicou", dependencies=[Depends(require_admin)])
def tv_zicou_state(game: str = Query("", pattern=r"^\d{0,4}$")):
    """App Apple TV : les Zicou des présents de la soirée ET des joueurs avec compte de la partie regardée, même sans
    événement lié, sans doublon (aspect seulement : stade, humeur, tenue, shiny ; surnom modéré ou rien). `game` : la
    partie regardée, pour reconnaître le Zicou d'un gagnant (pid)."""
    present = tv_present_accounts()
    with GAMES_LOCK:
        pid_of = tv_pid_finder(game)
        shown = present | tv_player_accounts(game)   # un ensemble : un présent qui joue n'apparaît qu'une fois
        zicous = soiree_zicous.listed(shown, accounts.gid, pid_of) if shown else []
    star, waiting = tv_stars.on_air(soiree_key()) if store.session.active else (None, 0)
    return {"zicous": zicous, "count": len(zicous), "star": star, "star_waiting": waiting,
            "salon": pet_public_pot.reached()}


@app.get("/api/calendar.ics")
def calendar_file(
    uid: str = Query(max_length=36),
    title: str = Query(max_length=1000),
    start: str = Query(max_length=40),
    end: str | None = Query(default=None, max_length=40),
    location: str = Query(default="", max_length=2000),
    description: str = Query(default="", max_length=8000),
    url: str = Query(default="", max_length=500),
):
    """Événement au format iCalendar. Le client transmet ce qu'il affiche déjà : iOS ouvre
    alors directement « Ajouter au calendrier » et Android l'importe dans l'agenda choisi.
    Titre, lieu (+ adresse) et description trop longs sont tronqués par calendar_ics.build (200 / 300 / 2000),
    jamais refusés (campagne 2) ; seule une taille absurde est refusée (422)."""
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


def join_page_meta(invite: str) -> str:
    """Lien personnel d'invitation : « X t'invite sur Party » dans l'aperçu (WhatsApp, iMessage…). Base injoignable :
    aperçu générique, la page s'ouvre quand même."""
    try:
        preview = app_invites.preview(invite)
    except AccountError:
        preview = None
    base = configured_public_url()
    return join_meta((preview or {}).get("inviter"), f"{base}/events/join/{invite}", base)


@app.get("/events/{resource:path}")
def events_web(resource: str):
    """Module web local ; l'accès aux données reste protégé par Supabase Auth/RLS."""
    root = EVENTS_WEB.resolve()
    try:
        if any(part.startswith(".") for part in Path(resource).parts):
            raise HTTPException(404, "Page introuvable")
        requested = (root / resource).resolve()
    except ValueError:
        # Chemin invalide (ex. octet nul « %00 ») : Path.resolve lève ValueError → 404, pas 500.
        raise HTTPException(404, "Page introuvable") from None
    if not requested.is_relative_to(root):
        raise HTTPException(404, "Page introuvable")
    if requested.is_file():
        headers = {"Cache-Control": "public, max-age=31536000, immutable"} if resource.startswith(("_expo/", "assets/")) else NO_CACHE
        response = FileResponse(requested, headers=headers)
    elif resource.startswith(("_expo/", "assets/")) or Path(resource).suffix:
        raise HTTPException(404, "Ressource introuvable")
    elif (root / "index.html").is_file():
        html = features_page((root / "index.html").read_text(encoding="utf-8"))
        if invite := APP_JOIN_PAGE.match(resource):
            html = html.replace("</head>", join_page_meta(invite.group(1)) + "</head>", 1)
        elif invites_v2_enabled() and (event_invite := event_invites.INVITE_PAGE.match(resource)):
            # Lien d'invitation à un événement : « Ludo t'invite : … », la date et l'affiche dans l'aperçu.
            meta = event_invites.page_meta(accounts, event_invite.group(1), configured_public_url())
            html = html.replace("</head>", meta + "</head>", 1)
        elif event_id := event_preview.event_id_of_page(resource):
            # Fiche ou page de partage d'un événement PUBLIC : titre, date et image dans l'aperçu ; rien sinon.
            html = event_preview.with_preview(html, accounts, event_id, configured_public_url())
        response = Response(html, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})
    else:
        return Response("Les événements sont momentanément indisponibles. Réessaie dans un instant.", status_code=503, headers=NO_CACHE)
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/sw.js")
def service_worker():
    # À la racine du site : le service worker couvre la page invités et l'admin.
    return FileResponse(STATIC / "sw.js", media_type="text/javascript", headers=NO_CACHE)


# Apps iOS natives (ios/) : identifiant d'équipe Apple + identifiant de l'app (pas un secret).
# VendrediParty (App Store) pour le site principal, VendrediPartyBETA (TestFlight) pour le site de test.
IOS_APP_ID = "GS2B6GA9JA.ch.bobycharbon.party"
IOS_BETA_APP_ID = "GS2B6GA9JA.ch.bobycharbon.party.beta"


@app.get("/api/features")
def features():
    """Fonctions en bêta pour les apps natives (la page web les lit sur <html data-compagnon> / data-discussions) :
    Compagnon (Zicou) et Discussions (groupes, messages directs)."""
    return JSONResponse({"compagnon": compagnon_enabled(), "discussions": discussions_enabled(),
                         "invites_v2": invites_v2_enabled()}, headers=NO_CACHE)


@app.get("/.well-known/apple-app-site-association")
def apple_app_site_association():
    # Liens universels : un QR code ou un lien Party ouvre l'app iOS si elle est installée, sinon le site.
    beta = urlparse(configured_public_url()).hostname == TEST_SITE_HOST
    app_id = IOS_BETA_APP_ID if beta else IOS_APP_ID
    return JSONResponse({"applinks": {"details": [{"appIDs": [app_id], "components": [{"/": "/*"}]}]}},
                        headers=NO_CACHE)


# Apps Android (android/, Trusted Web Activity) : empreintes SHA-256 des certificats qui signent l'app.
# Clé d'envoi (APK installés à la main) + clé de signature Google Play (à ajouter quand Play Console la donne).
# Sans ce fichier, Chrome affiche une barre d'adresse en haut de l'app.
ANDROID_UPLOAD_KEY_SHA256 = ("89:0B:78:22:B0:04:63:38:60:AD:9B:0F:D4:6D:08:04:"
                             "2E:52:FF:3A:06:CC:5F:FD:1B:16:A0:DA:6F:0A:D4:73")
ANDROID_PLAY_SIGNING_SHA256: tuple[str, ...] = ()


@app.get("/.well-known/assetlinks.json")
def android_asset_links():
    beta = urlparse(configured_public_url()).hostname == TEST_SITE_HOST
    package = "ch.bobycharbon.party.beta" if beta else "ch.bobycharbon.party"
    return JSONResponse([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": package,
                   "sha256_cert_fingerprints": [ANDROID_UPLOAD_KEY_SHA256, *ANDROID_PLAY_SIGNING_SHA256]},
    }], headers=NO_CACHE)


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
        body.guest_id = canonical_gid(g, body.guest_id)
        if g["type"] != "neon":
            raise HTTPException(400, "Ce jeu n'est pas Néon Knockout")
        if body.guest_id in g.get("kicked", []):
            raise HTTPException(403, "Tu as été banni de cette partie")
        paused = bool(g.get("paused"))  # pause de l'animateur : rien ne bouge
        changed = False if paused else neon.tick(g)
        try:
            None if paused else neon.input_state(g, body.guest_id, body.x, body.y, body.charging, cancel=body.cancel)
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
        body.guest_id = canonical_gid(g, body.guest_id)
        if g["type"] != "island":
            raise HTTPException(400, "Ce jeu n’est pas L’île qui s’effondre")
        if body.guest_id in g.get("kicked", []) or (body.guest_id in g.get("removed", []) and not games.player(g, body.guest_id)):
            raise HTTPException(403, "Tu ne participes plus à cette partie")
        paused = bool(g.get("paused"))  # pause de l'animateur : rien ne bouge
        changed = False if paused else island.tick(g)
        try:
            None if paused else island.input_state(g, body.guest_id, body.x, body.y, body.jump, cancel=body.cancel)
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
        body.guest_id = canonical_gid(g, body.guest_id)
        if g["type"] != "heist":
            raise HTTPException(400, "Ce jeu n’est pas un braquage")
        if body.guest_id in g.get("kicked", []) or (body.guest_id in g.get("removed", []) and not games.player(g, body.guest_id)):
            raise HTTPException(403, "Tu ne participes plus à cette partie")
        phase = g["phase"]
        paused = bool(g.get("paused"))  # pause de l'animateur : rien ne bouge
        changed = False if paused else heist.tick(g)
        try:
            None if paused else heist.input_state(g, body.guest_id, body.x, body.y, body.action, cancel=body.cancel)
        except heist.HeistError as e:
            raise HTTPException(400, str(e))
        if changed or phase != g["phase"]:
            g["updated_at"] = time.time()
            save_games(g["code"])
        return heist.view(g, body.guest_id)
