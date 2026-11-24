"""Souvenirs (avis 74d36b93e7bd, 24.11.2026, migration 20261124090000) : le serveur de l'appareil photo de la soirée.

- POST /api/account/souvenirs/photo?event_id=<id> : la photo brute (corps de la requête, JPEG / PNG / WebP, 15 Mo au plus),
  jeton du compte dans l'en-tête Authorization. Le serveur la redresse, retire EXIF et GPS (une image neuve, sans
  métadonnées), la réduit à 1600 px au plus, demande un ticket de dépôt (souvenir_upload_ticket, avec la clé du serveur
  SOUVENIRS_SECRET = secret « souvenirs_server_key » du coffre de la base : un client seul ne peut rien déposer), la dépose
  en JPEG dans le compartiment privé « souvenirs » (<événement>/<moi>/<id>.jpg) puis appelle souvenir_take (la base décide
  de tout : cercle, fenêtre, 3 photos, CGU). Refusée : le fichier déposé est retiré aussitôt.
- POST /api/account/souvenirs/rpc : relais des fonctions souvenir_* (liste blanche) pour l'iPhone et le web ; chaque
  photo reçoit « url » (lien signé court) et chaque auteur « photo » (sa photo de profil signée).
- Fichiers effacés (corbeille de la base, envois jamais enregistrés) : la base les retire par l'API Storage
  (souvenir_files_gc), appelée au démarrage puis toutes les heures, et par la tâche souvenirs-tick."""
import io
import logging
import os
import re
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from .accounts import SUPABASE_URL, AccountError, Accounts, ServiceUnavailable
from .agenda import ERROR_STATUS, Db, refusal

log = logging.getLogger("party.souvenirs")

RELAY = {
    "souvenir_counter", "souvenir_story", "souvenir_mine", "souvenir_review", "souvenir_stories", "souvenir_mark_seen",
    "souvenir_cancel", "souvenir_delete", "souvenir_remove", "souvenir_restore", "souvenir_keep", "souvenir_unkeep",
    "souvenir_settings", "souvenir_reveal_now", "report_content",
}
STATUS = {**ERROR_STATUS, "locked": 409, "profile_required": 403, "too_early": 409, "closed": 409}
UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
RAW_MAX = 15 * 1024 * 1024     # photo envoyée (avant réduction)
MAX_SIDE = 1600                # côté le plus long, en pixels
MAX_PIXELS = 60_000_000        # au-delà : refusée (image piégée)
JPEG_QUALITY = 85
SIGNED_TTL = 600               # lien d'une photo : 10 minutes
GC_EVERY = 3600
GC_FIRST_DELAY = 90
SECRET_ENV = "SOUVENIRS_SECRET"   # clé du serveur Party : secret « souvenirs_server_key » du coffre de la base
NOT_READY = "L'appareil photo n'est pas encore prêt. Réessaie plus tard."


class RelayBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    fn: str = Field(min_length=1, max_length=60)
    args: dict[str, Any] = Field(default_factory=dict)


def clean_jpeg(data: bytes) -> bytes:
    """Image redressée (orientation EXIF appliquée), copiée pixel par pixel dans une image neuve : aucune métadonnée
    (EXIF, GPS, XMP, ICC, commentaires) ne passe ; 1600 px au plus ; JPEG."""
    try:
        with Image.open(io.BytesIO(data)) as raw:
            if raw.format not in ("JPEG", "PNG", "WEBP") or raw.width * raw.height > MAX_PIXELS:
                raise ValueError("format")
            img = ImageOps.exif_transpose(raw)
            img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("Photo illisible : envoie un JPEG, un PNG ou un WebP.") from None
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    bare = Image.new("RGB", img.size)
    bare.paste(img)
    out = io.BytesIO()
    bare.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


def photos_in(value: Any) -> list[dict]:
    """Toutes les photos {id, path, …} d'une réponse de la base, où qu'elles soient (story, mine, review…)."""
    found: list[dict] = []
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and "id" in value:
            found.append(value)
        for v in value.values():
            found += photos_in(v)
    elif isinstance(value, list):
        for v in value:
            found += photos_in(v)
    return found


def bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip()[:4096] if auth.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
    return token


class Souvenirs:
    def __init__(self, accounts: Accounts, secret: str | None = None):
        self.accounts = accounts
        self.db = Db(accounts)
        self.secret = secret  # None : lue dans l'environnement à chaque photo

    def _sign(self, bucket: str, paths: list[str], token: str) -> dict[str, str]:
        paths = sorted({p for p in paths if p})
        if not paths:
            return {}
        try:
            r = self.accounts._get("POST", f"/storage/v1/object/sign/{bucket}", token,
                                   json={"expiresIn": SIGNED_TTL, "paths": paths}, timeout=6.0)
            rows = r.json() if r.status_code == 200 else []
        except (AccountError, ValueError):
            rows = []
        return {row["path"]: SUPABASE_URL + "/storage/v1" + row["signedURL"]
                for row in rows if isinstance(row, dict) and row.get("signedURL") and row.get("path")}

    def sign(self, data: Any, token: str) -> Any:
        """Chaque photo reçoit « url » (lien signé court ; null si la base ne la montre plus), chaque auteur « photo »."""
        photos = photos_in(data)
        urls = self._sign("souvenirs", [p["path"] for p in photos], token)
        authors = [p["author"] for p in photos if isinstance(p.get("author"), dict)]
        faces = self._sign("profile-photos", [a.get("avatar_url") for a in authors], token)
        for p in photos:
            p["url"] = urls.get(p["path"])
        for a in authors:
            a["photo"] = faces.get(a.get("avatar_url") or "")
        return data

    def take(self, token: str, event_id: str, data: bytes) -> tuple[int, dict]:
        self.accounts._uid(token)
        jpeg = clean_jpeg(data)
        key = (os.environ.get(SECRET_ENV, "") if self.secret is None else self.secret).strip()
        if not key:
            log.error("Souvenirs : %s manquant, aucune photo ne peut être déposée", SECRET_ENV)
            raise ServiceUnavailable(NOT_READY)
        # Ticket à usage unique (la base vérifie cercle, fenêtre, 3 photos, CGU) : seul le serveur peut déposer.
        status, body = self.db.call("souvenir_upload_ticket", {"e": event_id, "p_key": key}, token)
        if status != 200 or not isinstance(body, dict) or not body.get("path"):
            return self._refused(status, body)
        photo_id, path = str(body["id"]), str(body["path"])
        r = self.accounts._get("POST", f"/storage/v1/object/souvenirs/{path}", token, content=jpeg,
                               headers={"Content-Type": "image/jpeg"}, timeout=20.0)
        if r.status_code not in (200, 201):
            raise AccountError("La photo n'a pas pu être envoyée. Réessaie.")
        status, body = self.db.call("souvenir_take", {"e": event_id, "id": photo_id}, token)
        if status == 200:
            return 200, body
        try:  # refusée par la base : le fichier déposé ne reste pas (sinon la corbeille de la base l'efface en 1 h)
            self.accounts._get("DELETE", f"/storage/v1/object/souvenirs/{path}", token, timeout=6.0)
        except AccountError:
            pass
        return self._refused(status, body)

    def _refused(self, status: int, body: Any) -> tuple[int, dict]:
        if status == 401:
            raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
        code, text = refusal(body)
        if code == "server":  # clé du serveur fausse (SOUVENIRS_SECRET) : panne de configuration, pas sa faute
            log.error("Souvenirs : la base refuse la clé du serveur (%s)", SECRET_ENV)
            raise ServiceUnavailable(NOT_READY)
        if code == "error":
            raise HTTPException(503 if status >= 500 else 400, "Ça n'a pas marché. Réessaie dans un instant.")
        return STATUS.get(code, 400), {"code": code, "detail": text}


def souvenirs_router(accounts: Accounts) -> APIRouter:
    s = Souvenirs(accounts)
    router = APIRouter()

    @router.post("/api/account/souvenirs/photo")
    async def photo(request: Request, event_id: str):
        if not re.match(UUID, event_id):
            raise HTTPException(400, "Événement invalide")
        token = bearer(request)
        data = await request.body()
        if not data or len(data) > RAW_MAX:
            raise HTTPException(413, "Photo trop volumineuse (15 Mo au plus).")
        try:
            status, body = await run_in_threadpool(s.take, token, event_id, data)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        except ServiceUnavailable as e:
            raise HTTPException(503, str(e)) from None
        except AccountError as e:
            raise HTTPException(400, str(e)) from None
        return JSONResponse(body, status_code=status)

    @router.post("/api/account/souvenirs/rpc")
    def relay(body: RelayBody):
        if body.fn not in RELAY:
            raise HTTPException(404, "Fonction inconnue")
        if body.fn == "report_content" and str(body.args.get("p_kind", "")) != "souvenir":
            raise HTTPException(404, "Fonction inconnue")  # signaler une photo Souvenirs seulement ici
        status, data = s.db.call(body.fn, body.args, body.token)
        if status in (200, 204):
            return JSONResponse({"result": s.sign(data, body.token)})
        if status == 401:
            raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
        code, text = refusal(data)
        if code == "error":
            raise HTTPException(503 if status >= 500 else 400, "Ça n'a pas marché. Réessaie dans un instant.")
        return JSONResponse({"code": code, "detail": text}, status_code=STATUS.get(code, 400))

    return router


def files_gc(db: Db) -> Any:
    """Un passage : la base efface les fichiers de la corbeille et les envois jamais enregistrés."""
    status, data = db.call("souvenir_files_gc", {})
    if status != 200:
        log.warning("Fichiers des Souvenirs : la base a répondu %s", status)
        return None
    if isinstance(data, dict) and data.get("removed"):
        log.info("Fichiers des Souvenirs effacés : %s", data["removed"])
    return data


def files_gc_loop(db: Db, every: float = GC_EVERY, first: float = GC_FIRST_DELAY) -> None:
    time.sleep(first)
    while True:
        try:
            files_gc(db)
        except Exception:  # jamais d'arrêt de la boucle pour une panne passagère
            log.exception("Fichiers des Souvenirs : passage raté")
        time.sleep(every)


def start_files_gc(accounts: Accounts) -> threading.Thread:
    thread = threading.Thread(target=files_gc_loop, args=(Db(accounts),), daemon=True, name="souvenirs-files-gc")
    thread.start()
    return thread
