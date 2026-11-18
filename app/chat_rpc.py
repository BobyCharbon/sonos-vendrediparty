"""Discussions v2 (18.11.2026) pour l'app iPhone : POST /api/account/chats/rpc relaie les nouvelles fonctions de la base
(liste, demandes de message, personnes, mini-profil, groupes à plusieurs, lu, cartes d'événement, recherche, réglages),
avec la session du membre : la base décide de tout (qui écrit à qui, blocage, CGU, plafonds). Le serveur signe les photos
(l'app ne lit pas les compartiments privés). Sous /api/account/chats : coupé avec le drapeau des Discussions.

Fichiers orphelins (revue de conformité, 🔴 6) : le serveur n'a aucune clé Storage ; il demande à la base
(chat_files_gc) d'effacer, par l'API Storage, les fichiers de chat-photos, group-photos et moderation-evidence qu'aucune
ligne ne désigne plus, au démarrage puis toutes les 6 h."""
import logging
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError
from .agenda import ERROR_STATUS, Db, refusal
from .group_chats import GroupChats

log = logging.getLogger("party.chats")

# Fonctions publiques du contrat Discussions v2 que l'app iPhone appelle par le serveur.
RELAY = {
    "chat_link", "open_direct_chat", "accept_message_request", "decline_message_request",   # §1-2
    "chat_prefs_get", "chat_prefs_set",
    "chat_list", "set_chat_state", "chat_badge", "mark_event_chat_read",                    # §3
    "chat_people_suggestions", "chat_people_search", "member_mini", "contacts_match",       # §4
    "create_chat_group", "chat_group_with",                                                 # §5
    "direct_seen", "chat_event_cards", "edit_direct_message", "edit_group_message",         # §6
    "chat_search",                                                                          # §8
    "report_content",                                                                       # §7 (messages, profils)
}
# Signaler depuis les Discussions : messages, profils, photos ; le reste a ses propres écrans.
REPORT_KINDS = {"group_message", "direct_message", "event_message", "profile", "profile_photo", "group_photo"}
STATUS = {**ERROR_STATUS, "limit": 429, "pin_limit": 409, "request_pending": 409, "edit_window": 409, "locked": 409,
          "blocked": 403, "inactive": 403, "profile_required": 403, "link_required": 403}
WITH_REALTIME = {"chat_list", "chat_badge"}
GC_EVERY = 6 * 3600
GC_FIRST_DELAY = 60


class RelayBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    fn: str = Field(min_length=1, max_length=60)
    args: dict[str, Any] = Field(default_factory=dict)


def _bucket(item: dict) -> str | None:
    """Compartiment d'une « photo » rendue par la base : groupe → group-photos ; personne → profile-photos ; une soirée
    a une adresse complète (rien à signer)."""
    kind = item.get("kind")
    if kind == "event":
        return None
    if kind == "group" or (kind != "direct" and (item.get("emoji") or item.get("color"))):
        return "group-photos"
    return "profile-photos"


def photos_in(value: Any) -> list[tuple[dict, str, str, str]]:
    """(élément, clé à remplir, compartiment, chemin) de chaque photo encore à signer, où qu'elle soit dans la réponse."""
    found: list[tuple[dict, str, str, str]] = []
    if isinstance(value, dict):
        photo = value.get("photo")
        if isinstance(photo, str) and photo and not photo.startswith(("http://", "https://")) and _bucket(value):
            found.append((value, "photo", _bucket(value), photo))
        elif "avatar_url" in value and "id" in value and "photo" not in value:
            if value.get("avatar_url"):
                found.append((value, "photo", "profile-photos", value["avatar_url"]))
            else:
                value["photo"] = None
        for v in value.values():
            found += photos_in(v)
    elif isinstance(value, list):
        for v in value:
            found += photos_in(v)
    return found


def sign_photos(chats: GroupChats, data: Any, token: str) -> None:
    """Remplace chaque chemin de photo par un lien signé (gardé 40 min, comme les Discussions) ; illisible : None."""
    spots = photos_in(data)
    for bucket in {b for _, _, b, _ in spots}:
        paths = [p for _, _, b, p in spots if b == bucket]
        try:
            urls = chats._cached_sign(bucket, paths, lambda ps, b=bucket: chats.admin._photos(ps, token, b))
        except AccountError:
            urls = {}
        for item, key, b, path in spots:
            if b == bucket:
                item[key] = urls.get(path)


def chat_rpc_router(chats: GroupChats) -> APIRouter:
    db = Db(chats.admin.accounts)
    router = APIRouter()

    @router.post("/api/account/chats/rpc")
    def relay(body: RelayBody):
        if body.fn not in RELAY:
            raise HTTPException(404, "Fonction inconnue")
        args = dict(body.args)
        if body.fn == "report_content":
            if str(args.get("p_kind", "")) not in REPORT_KINDS:
                raise HTTPException(404, "Fonction inconnue")
            if "context" in args:  # « Joindre les 10 messages précédents » (contrat : context ; base : p_context)
                args["p_context"] = bool(args.pop("context"))
        status, data = db.call(body.fn, args, body.token)
        if status in (200, 204):
            sign_photos(chats, data, body.token)
            out: dict[str, Any] = {"result": data}
            if body.fn in WITH_REALTIME:  # l'app écoute ensuite les tables et signaux des Discussions
                out["realtime"] = {"url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket",
                                   "key": SUPABASE_ANON_KEY}
            return JSONResponse(out)
        if status == 401:
            raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
        code, text = refusal(data)
        if code == "error":
            raise HTTPException(503 if status >= 500 else 400, "Ça n'a pas marché. Réessaie dans un instant.")
        return JSONResponse({"code": code, "detail": text}, status_code=STATUS.get(code, 400))

    return router


def files_gc(db: Db) -> Any:
    """Un passage : la base efface les fichiers orphelins (vieux de plus d'une heure) ; None si elle ne répond pas."""
    status, data = db.call("chat_files_gc", {})
    if status != 200:
        log.warning("Fichiers orphelins des Discussions : la base a répondu %s", status)
        return None
    if isinstance(data, dict) and not data.get("skipped"):
        log.info("Fichiers orphelins des Discussions effacés : %s", data)
    return data


def files_gc_loop(db: Db, every: float = GC_EVERY, first: float = GC_FIRST_DELAY) -> None:
    time.sleep(first)
    while True:
        try:
            files_gc(db)
        except Exception:  # jamais d'arrêt de la boucle pour une panne passagère
            log.exception("Fichiers orphelins des Discussions : passage raté")
        time.sleep(every)


def start_files_gc(chats: GroupChats) -> threading.Thread:
    thread = threading.Thread(target=files_gc_loop, args=(Db(chats.admin.accounts),), daemon=True, name="chat-files-gc")
    thread.start()
    return thread
