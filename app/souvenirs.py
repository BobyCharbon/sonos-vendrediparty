"""Souvenirs (avis 74d36b93e7bd, 24.11.2026) : le serveur de l'appareil photo de la soirée.

Fichiers sur le DISQUE du serveur Party (décision de l'admin du 24.11, migration 20261124150000), jamais dans Supabase
Storage (plan Free : 1 Go, 5 Go de sortie par mois) ; la base garde métadonnées, droits, signalements, blocages, ticket.
Dossier DATA_DIR/souvenirs/<événement>/<auteur>/ :
- <id>.orig.jpg : l'ORIGINAL, gardé 7 jours (SOUVENIRS_ORIGINAL_DAYS). Jamais réencodé : seuls le GPS et les numéros de
  série de l'appareil sont retirés de l'EXIF (date et orientation gardées), les octets de l'image sont recopiés tels quels ;
- <id>.screen.jpg : la version écran (2048 px, JPEG 85), montrée par la story et les grilles ;
- <id>.jpg : au bout des 7 jours, l'original est remplacé par une version de 2560 px (JPEG 90), gardée 13 mois.

- POST /api/account/souvenirs/photo?event_id=<id> : la photo brute (corps, JPEG / PNG / WebP, 25 Mo au plus), jeton du
  compte dans Authorization. Ticket à usage unique (souvenir_upload_ticket, avec la clé du serveur SOUVENIRS_SECRET =
  secret « souvenirs_server_key » du coffre : un client seul ne crée jamais de photo), souvenir_take (la base décide :
  cercle, fenêtre, 3 photos, CGU), puis écriture des fichiers ; disque en panne : la photo est annulée (souvenir_cancel).
- POST /api/account/souvenirs/rpc : relais des fonctions souvenir_* (liste blanche) ; chaque photo que la base me laisse
  lire (souvenir_readable, avec MON jeton) reçoit « url » (version écran) et « original », liens signés par le serveur
  (HMAC, ~10 min) : GET /api/souvenirs/file/<jeton>?v=screen|original (Cache-Control: private, ETag).
- POST /api/account/souvenirs/links : les mêmes liens pour une liste de chemins (écran Signalements de la modération).
- Effacement : toute ligne effacée met son chemin dans la corbeille de la base ; le serveur la vide toutes les 5 minutes
  (souvenir_trash_take / souvenir_trash_done, clé du serveur) et efface les fichiers ; la copie de nuit vers le NAS
  (rsync --delete, deploy/souvenirs-nas.md) suit."""
import base64
import hashlib
import hmac
import io
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

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
PATH = re.compile(r"^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$")
RAW_MAX = 25 * 1024 * 1024     # une photo envoyée, contre les abus (pas de plafond par soirée : 3 par personne)
MAX_PIXELS = 60_000_000        # au-delà : refusée (image piégée) ; 48 Mpx d'un iPhone passent
SCREEN_SIDE, SCREEN_QUALITY = 2048, 85   # version écran : story et grilles
KEEP_SIDE, KEEP_QUALITY = 2560, 90       # après les jours de l'original : ce qui reste 13 mois
NEW_JPEG_QUALITY = 95                    # PNG / WebP : l'original devient un JPEG (rien à préserver octet par octet)
ORIGINAL_DAYS_ENV = "SOUVENIRS_ORIGINAL_DAYS"
ORIGINAL_DAYS = 7
LINK_STEP = 300                # lien d'une photo : valable 10 à 15 min, stable 5 min (le cache du navigateur sert)
DISK_RESERVE = 1024 ** 3       # moins de 1 Go libre : plus de photo (le disque sert aussi au reste de Party)
CHORES_EVERY = 300             # corbeille et originaux trop vieux : toutes les 5 minutes
CHORES_FIRST_DELAY = 60
NAS_STAMP = ".derniere-copie-nas"   # écrit par la copie de nuit (deploy/souvenirs-nas.md), lu par l'admin
SECRET_ENV = "SOUVENIRS_SECRET"     # clé du serveur Party : secret « souvenirs_server_key » du coffre de la base
NOT_READY = "L'appareil photo n'est pas encore prêt. Réessaie plus tard."

# EXIF : ce qui part (GPS, numéros de série, propriétaire, note du fabricant qui en contient). Tout le reste reste.
GPS_IFD, EXIF_IFD = 0x8825, 0x8769
GONE_IN_EXIF = (0xA430, 0xA431, 0xA435, 0x927C)   # CameraOwnerName, BodySerialNumber, LensSerialNumber, MakerNote
GONE_IN_MAIN = (0xC62F, 0xA431)                    # CameraSerialNumber (DNG), BodySerialNumber mal rangé
KEPT_DATES = (0x9003, 0x9004, 0x9010, 0x9011)      # DateTimeOriginal, DateTimeDigitized, OffsetTime(Original)


class RelayBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    fn: str = Field(min_length=1, max_length=60)
    args: dict[str, Any] = Field(default_factory=dict)


class LinksBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    paths: list[str] = Field(max_length=200)


def original_days() -> float:
    try:
        return max(0.0, float(os.environ.get(ORIGINAL_DAYS_ENV, ORIGINAL_DAYS)))
    except ValueError:
        return ORIGINAL_DAYS


# ───────────────────────── Images ─────────────────────────
def _clean_exif(segment: bytes) -> bytes | None:
    """Le bloc EXIF (APP1, « Exif\\0\\0… ») sans GPS ni numéro de série ; date, orientation et réglages de prise gardés.
    Illisible : un EXIF minimal (orientation et dates) ; rien à garder : None."""
    exif = Image.Exif()
    try:
        exif.load(segment)
        sub = exif.get_ifd(EXIF_IFD)
        for tag in GONE_IN_EXIF:
            sub.pop(tag, None)
        for tag in (GPS_IFD, *GONE_IN_MAIN):
            if tag in exif:
                del exif[tag]
        exif._ifds.pop(GPS_IFD, None)
        out = exif.tobytes()
        check = Image.Exif()
        check.load(out)
        if GPS_IFD in check or any(t in check.get_ifd(EXIF_IFD) for t in GONE_IN_EXIF):
            raise ValueError("gps")
        return out
    except Exception:  # EXIF abîmé ou exotique : on ne garde que l'essentiel, jamais le reste
        return _minimal_exif(exif)


def _minimal_exif(exif: Image.Exif) -> bytes | None:
    keep = Image.Exif()
    try:
        orientation = exif.get(0x0112)
        dates = {t: v for t, v in exif.get_ifd(EXIF_IFD).items() if t in KEPT_DATES and isinstance(v, str)}
    except Exception:
        return None
    if orientation in range(1, 9):
        keep[0x0112] = orientation
    if dates:
        keep[EXIF_IFD] = dates
    return keep.tobytes() if len(keep) else None


def strip_jpeg(data: bytes) -> bytes:
    """Le JPEG tel quel, sauf le bloc EXIF nettoyé (GPS, numéros de série) et un XMP qui porte une position : les octets
    de l'image (de l'en-tête SOS à la fin, image secondaire HDR comprise) sont recopiés sans y toucher."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("jpeg")
    out, i, exif_done = [b"\xff\xd8"], 2, False
    while i < len(data):
        if data[i] != 0xFF:
            raise ValueError("jpeg")
        start = i
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            raise ValueError("jpeg")
        marker = data[i]
        i += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            out.append(data[start:i])
            continue
        if marker == 0xD9:
            out.append(data[start:])
            break
        if marker == 0xDA:  # début de l'image : tout le reste, octet pour octet
            out.append(data[start:])
            break
        length = int.from_bytes(data[i:i + 2], "big")
        if length < 2 or i + length > len(data):
            raise ValueError("jpeg")
        body = data[i + 2:i + length]
        i += length
        if marker == 0xE1 and body.startswith(b"Exif\x00\x00"):
            if not exif_done:
                exif_done = True
                clean = _clean_exif(body)
                if clean and len(clean) + 2 <= 0xFFFF:
                    out.append(b"\xff\xe1" + (len(clean) + 2).to_bytes(2, "big") + clean)
            continue  # un 2e bloc EXIF : jamais gardé
        if marker == 0xE1 and body.startswith(b"http://ns.adobe.com/") and b"GPS" in body:
            continue  # XMP avec une position
        out.append(data[start:i])
    else:
        raise ValueError("jpeg")
    return b"".join(out)


def _open(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP") or img.width * img.height > MAX_PIXELS:
            raise ValueError("format")
        return img
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("Photo illisible : envoie un JPEG, un PNG ou un WebP.") from None


def _resized(img: Image.Image, side: int, quality: int, exif: bytes | None = None) -> bytes:
    """Redressée (orientation EXIF appliquée), au plus `side` px, JPEG ; profil de couleur gardé (P3 de l'iPhone)."""
    icc = img.info.get("icc_profile")
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((side, side), Image.LANCZOS)
    out = io.BytesIO()
    extra = {"icc_profile": icc} if icc else {}
    if exif:
        extra["exif"] = exif
    img.save(out, "JPEG", quality=quality, optimize=True, progressive=True, **extra)
    return out.getvalue()


def prepare(data: bytes) -> tuple[bytes, bytes]:
    """(original, version écran). JPEG : l'original garde ses octets d'image (EXIF nettoyé). PNG / WebP : un JPEG 95 neuf,
    sans métadonnées."""
    img = _open(data)
    try:
        if img.format == "JPEG":
            try:
                original = strip_jpeg(data)
            except ValueError:
                raise ValueError("Photo illisible : envoie un JPEG, un PNG ou un WebP.") from None
            img.draft("RGB", (SCREEN_SIDE, SCREEN_SIDE))  # décodage réduit : rapide même pour 48 Mpx
        else:
            original = _resized(img, max(img.size), NEW_JPEG_QUALITY)
        screen = _resized(img, SCREEN_SIDE, SCREEN_QUALITY)
    except (OSError, Image.DecompressionBombError):
        raise ValueError("Photo illisible : envoie un JPEG, un PNG ou un WebP.") from None
    finally:
        img.close()
    return original, screen


def long_term(original: bytes) -> bytes:
    """Ce qui reste après les jours de l'original : 2560 px, JPEG 90, avec la date de prise (orientation appliquée)."""
    with Image.open(io.BytesIO(original)) as img:
        dates = None
        try:
            found = {t: v for t, v in img.getexif().get_ifd(EXIF_IFD).items() if t in KEPT_DATES and isinstance(v, str)}
            if found:
                keep = Image.Exif()
                keep[EXIF_IFD] = found
                dates = keep.tobytes()
        except Exception:
            dates = None
        return _resized(img, KEEP_SIDE, KEEP_QUALITY, dates)


# ───────────────────────── Disque ─────────────────────────
class Files:
    """DATA_DIR/souvenirs : <e>/<auteur>/<id>.orig.jpg (original), .screen.jpg (écran), .jpg (2560 px, après 7 jours)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _stem(self, path: str) -> Path:
        if not isinstance(path, str) or not PATH.match(path):
            raise ValueError("chemin")
        return self.root / path[:-4]

    def variants(self, path: str) -> dict[str, Path]:
        stem = self._stem(path)
        return {"original": stem.with_name(stem.name + ".orig.jpg"), "kept": stem.with_name(stem.name + ".jpg"),
                "screen": stem.with_name(stem.name + ".screen.jpg")}

    def room_left(self) -> bool:
        self.root.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(self.root).free > DISK_RESERVE

    def write(self, path: str, original: bytes, screen: bytes) -> None:
        v = self.variants(path)
        v["original"].parent.mkdir(parents=True, exist_ok=True)
        for name, data in (("screen", screen), ("original", original)):
            tmp = v[name].with_name(v[name].name + f".{uuid.uuid4().hex}.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, v[name])

    def find(self, path: str, view: str) -> Path | None:
        """screen : la version écran ; original : l'original tant qu'il existe, sinon la version de 2560 px."""
        v = self.variants(path)
        order = ("screen", "original", "kept") if view == "screen" else ("original", "kept", "screen")
        return next((v[k] for k in order if v[k].is_file()), None)

    def remove(self, path: str) -> int:
        try:
            v = self.variants(path)
        except ValueError:
            return 0
        n = 0
        for f in v.values():
            try:
                f.unlink()
                n += 1
            except FileNotFoundError:
                pass
        for folder in (v["kept"].parent, v["kept"].parent.parent):  # dossiers vides de l'auteur puis de l'événement
            try:
                folder.rmdir()
            except OSError:
                break
        return n

    def shrink_old(self, days: float | None = None, now: float | None = None) -> int:
        """Originaux de plus de `days` jours : remplacés par la version de 2560 px (JPEG 90). Rend le nombre traité."""
        limit = (now or time.time()) - (original_days() if days is None else days) * 86400
        done = 0
        for orig in sorted(self.root.glob("*/*/*.orig.jpg")):
            try:
                if orig.stat().st_mtime > limit:
                    continue
                kept = orig.with_name(orig.name[:-len(".orig.jpg")] + ".jpg")
                data = long_term(orig.read_bytes())
                tmp = kept.with_name(kept.name + f".{uuid.uuid4().hex}.tmp")
                tmp.write_bytes(data)
                os.replace(tmp, kept)
                orig.unlink()
                done += 1
            except FileNotFoundError:
                continue  # effacée entre-temps (corbeille)
            except Exception:
                log.exception("Souvenirs : %s n'a pas pu être réduite", orig.name)
        return done

    def stats(self) -> dict:
        photos, size = 0, 0
        if self.root.is_dir():
            for f in self.root.glob("*/*/*.jpg"):
                try:
                    size += f.stat().st_size
                except FileNotFoundError:
                    continue
                if not f.name.endswith(".screen.jpg"):
                    photos += 1
        stamp = self.root / NAS_STAMP
        nas = None
        if stamp.is_file():
            text = stamp.read_text(encoding="utf-8", errors="replace").strip()[:40]
            nas = text or datetime.fromtimestamp(stamp.stat().st_mtime, timezone.utc).isoformat()
        return {"photos": photos, "bytes": size, "nas": nas}


# ───────────────────────── Liens signés ─────────────────────────
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Links:
    """Jeton = chemin + expiration, signés HMAC-SHA256 par le serveur ; valable 10 à 15 min."""

    def __init__(self, secret: bytes):
        self.key = hashlib.sha256(b"party-souvenirs-file|" + secret).digest()

    def _sig(self, payload: bytes) -> bytes:
        return hmac.new(self.key, payload, hashlib.sha256).digest()[:18]

    def token(self, path: str, now: float | None = None) -> str:
        exp = (int(now or time.time()) // LINK_STEP + 3) * LINK_STEP
        payload = f"{path}|{exp}".encode()
        return f"{_b64(payload)}.{_b64(self._sig(payload))}"

    def url(self, path: str, view: str = "screen", now: float | None = None) -> str:
        return f"/api/souvenirs/file/{self.token(path, now)}?v={view}"

    def check(self, token: str, now: float | None = None) -> str | None:
        """Le chemin si le jeton est signé par ce serveur et pas expiré ; sinon None."""
        try:
            raw, sig = token.split(".", 1)
            payload = _unb64(raw)
            if not hmac.compare_digest(self._sig(payload), _unb64(sig)):
                return None
            path, exp = payload.decode().rsplit("|", 1)
            if int(exp) < (now or time.time()) or not PATH.match(path):
                return None
            return path
        except (ValueError, UnicodeDecodeError):
            return None


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
    def __init__(self, accounts: Accounts, root: Path, link_secret: bytes, secret: str | None = None):
        self.accounts = accounts
        self.db = Db(accounts)
        self.files = Files(root)
        self.links = Links(link_secret)
        self.secret = secret  # None : lue dans l'environnement à chaque usage

    def key(self) -> str:
        return (os.environ.get(SECRET_ENV, "") if self.secret is None else self.secret).strip()

    def readable(self, paths: list[str], token: str) -> set[str]:
        """Les chemins que la base me laisse lire (souvenir_readable, avec MON jeton : cercle, blocages, signalements,
        organisation, modération)."""
        paths = sorted({p for p in paths if isinstance(p, str) and PATH.match(p)})
        if not paths:
            return set()
        status, body = self.db.call("souvenir_readable", {"paths": paths}, token)
        return {p for p in body if p in paths} if status == 200 and isinstance(body, list) else set()

    def link_map(self, paths: list[str], token: str) -> dict[str, str]:
        return {p: self.links.url(p, "screen") for p in self.readable(paths, token)}

    def sign(self, data: Any, token: str) -> Any:
        """Chaque photo lisible reçoit « url » (écran) et « original » ; sinon null. Chaque auteur : « photo » (profil)."""
        photos = photos_in(data)
        ok = self.readable([p["path"] for p in photos], token)
        authors = [p["author"] for p in photos if isinstance(p.get("author"), dict)]
        faces = self._profile_photos([a.get("avatar_url") for a in authors], token)
        for p in photos:
            mine = p["path"] in ok
            p["url"] = self.links.url(p["path"], "screen") if mine else None
            p["original"] = self.links.url(p["path"], "original") if mine else None
        for a in authors:
            a["photo"] = faces.get(a.get("avatar_url") or "")
        return data

    def _profile_photos(self, paths: list, token: str) -> dict[str, str]:
        paths = sorted({p for p in paths if p})
        if not paths:
            return {}
        try:
            r = self.accounts._get("POST", "/storage/v1/object/sign/profile-photos", token,
                                   json={"expiresIn": 600, "paths": paths}, timeout=6.0)
            rows = r.json() if r.status_code == 200 else []
        except (AccountError, ValueError):
            rows = []
        return {row["path"]: SUPABASE_URL + "/storage/v1" + row["signedURL"]
                for row in rows if isinstance(row, dict) and row.get("signedURL") and row.get("path")}

    def take(self, token: str, event_id: str, data: bytes) -> tuple[int, dict]:
        self.accounts._uid(token)
        original, screen = prepare(data)
        key = self.key()
        if not key:
            log.error("Souvenirs : %s manquant, aucune photo ne peut être prise", SECRET_ENV)
            raise ServiceUnavailable(NOT_READY)
        if not self.files.room_left():
            log.error("Souvenirs : disque presque plein, photo refusée")
            raise ServiceUnavailable(NOT_READY)
        # Ticket à usage unique (la base vérifie cercle, fenêtre, 3 photos, CGU) : seul le serveur crée une photo.
        status, body = self.db.call("souvenir_upload_ticket", {"e": event_id, "p_key": key}, token)
        if status != 200 or not isinstance(body, dict) or not body.get("path"):
            return self._refused(status, body)
        photo_id, path = str(body["id"]), str(body["path"])
        status, taken = self.db.call("souvenir_take", {"e": event_id, "id": photo_id}, token)
        if status != 200:
            return self._refused(status, taken)
        try:
            self.files.write(path, original, screen)
        except (OSError, ValueError):
            log.exception("Souvenirs : la photo %s n'a pas pu être écrite", photo_id)
            self.db.call("souvenir_cancel", {"id": photo_id}, token)  # jamais une photo sans fichier
            self.files.remove(path)
            raise AccountError("La photo n'a pas pu être enregistrée. Réessaie.") from None
        return 200, taken

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

    # ───────── Tâches du serveur ─────────
    def empty_trash(self, batch: int = 200) -> int:
        """Corbeille de la base (photos effacées) : fichiers retirés du disque, puis chemins rendus à la base."""
        key, removed = self.key(), 0
        if not key:
            return 0
        for _ in range(50):
            status, paths = self.db.call("souvenir_trash_take", {"p_key": key, "n": batch})
            if status != 200 or not isinstance(paths, list) or not paths:
                if status != 200:
                    log.warning("Souvenirs : corbeille illisible (%s)", status)
                break
            for p in paths:
                removed += self.files.remove(p)
            self.db.call("souvenir_trash_done", {"p_key": key, "paths": paths})
            if len(paths) < batch:
                break
        if removed:
            log.info("Souvenirs : %s fichiers effacés", removed)
        return removed

    def chores(self) -> None:
        self.empty_trash()
        self.files.shrink_old()


def souvenirs_router(s: Souvenirs) -> APIRouter:
    router = APIRouter()

    @router.post("/api/account/souvenirs/photo")
    async def photo(request: Request, event_id: str):
        if not re.match(UUID, event_id):
            raise HTTPException(400, "Événement invalide")
        token = bearer(request)
        size = request.headers.get("content-length", "")
        if size.isdigit() and int(size) > RAW_MAX:
            raise HTTPException(413, "Photo trop volumineuse (25 Mo au plus).")
        data = await request.body()
        if not data or len(data) > RAW_MAX:
            raise HTTPException(413, "Photo trop volumineuse (25 Mo au plus).")
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

    @router.post("/api/account/souvenirs/links")
    def links(body: LinksBody):
        """Liens des photos signalées (écran Signalements) : la base dit si MON compte peut les voir (modération)."""
        return {"links": s.link_map(body.paths, body.token)}

    @router.get("/api/souvenirs/file/{token}")
    def file(token: str, request: Request, v: str = "screen", download: str | None = None):
        path = s.links.check(token)
        if not path:
            raise HTTPException(403, "Ce lien a expiré. Rouvre la photo.")
        found = s.files.find(path, "original" if v == "original" else "screen")
        if not found:
            raise HTTPException(404, "Photo introuvable")
        st = found.stat()
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
        headers = {"Cache-Control": "private, max-age=900", "ETag": etag, "X-Content-Type-Options": "nosniff",
                   "Referrer-Policy": "no-referrer"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        if download is not None:
            name = re.sub(r"[^A-Za-z0-9._-]", "", download)[:80] or "souvenir.jpg"
            headers["Content-Disposition"] = f'attachment; filename="{name if name.endswith(".jpg") else name + ".jpg"}"'
        return FileResponse(found, media_type="image/jpeg", headers=headers)

    return router


def chores_loop(s: Souvenirs, every: float = CHORES_EVERY, first: float = CHORES_FIRST_DELAY) -> None:
    time.sleep(first)
    while True:
        try:
            s.chores()
        except Exception:  # jamais d'arrêt de la boucle pour une panne passagère
            log.exception("Souvenirs : passage raté")
        time.sleep(every)


def start_chores(s: Souvenirs) -> threading.Thread:
    thread = threading.Thread(target=chores_loop, args=(s,), daemon=True, name="souvenirs-chores")
    thread.start()
    return thread
