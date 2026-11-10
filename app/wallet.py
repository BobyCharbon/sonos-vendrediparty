"""Billet d'un événement dans Apple Wallet (Cartes Apple) : fichier .pkpass signé.

Un .pkpass est un zip : pass.json (le billet), les images, manifest.json (SHA-1 de chaque fichier) et signature
(PKCS#7 détaché du manifeste, signé avec le certificat « Pass Type ID » et l'intermédiaire Apple WWDR G4).

Secrets : dossier WALLET_DIR (par défaut DATA_DIR/wallet) avec pass.key (clé privée PEM), pass.cer (certificat DER)
et wwdr_g4.cer (intermédiaire Apple, DER). Absents ou illisibles : le Wallet est simplement désactivé (jamais de
clé dans le dépôt ni dans les journaux)."""
import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

log = logging.getLogger(__name__)

PASS_TYPE_ID = "pass.ch.bobycharbon.party.ticket"
TEAM_ID = "GS2B6GA9JA"
MEDIA_TYPE = "application/vnd.apple.pkpass"
# Adresse du PassKit Web Service sous l'origine de Party (webServiceURL du pass).
SERVICE_PATH = "/api/wallet/passkit"
ZURICH = ZoneInfo("Europe/Zurich")
ASSETS = Path(__file__).parent / "wallet_assets"
IMAGE_NAMES = tuple(f"{name}{suffix}.png" for name in ("icon", "logo") for suffix in ("", "@2x", "@3x"))
FILES = ("pass.key", "pass.cer", "wwdr_g4.cer")
# Couleurs de Party (web/events/src/lib/theme.ts) : fond nuit, texte clair, étiquettes rose accent.
BACKGROUND, FOREGROUND, LABEL = "rgb(21, 16, 42)", "rgb(245, 240, 255)", "rgb(255, 79, 154)"
# Le billet reste valable un jour après la fin (comme ticketRelevant côté module Événements).
EXPIRES_AFTER = timedelta(days=1)
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre")
# Coordonnées dans un lien de carte : « ?q=46.2,6.1 », « ll=46.2,6.1 », « @46.2,6.1,17z », « /46.2,6.1 ».
COORDS = re.compile(r"(?:[?&](?:q|ll|query|daddr|destination|center|sll)=|@|/)(-?\d{1,2}\.\d+)\s*(?:,|%2C)\s*(-?\d{1,3}\.\d+)",
                    re.IGNORECASE)


class WalletError(Exception):
    """Billet impossible à préparer : message pour l'écran."""


@dataclass(frozen=True)
class Signer:
    key: object
    cert: x509.Certificate
    wwdr: x509.Certificate

    @classmethod
    def from_dir(cls, folder: Path) -> "Signer | None":
        """Les trois fichiers du dossier, ou None si le Wallet n'est pas (encore) configuré."""
        if not all((folder / name).is_file() for name in FILES):
            return None
        try:
            key = serialization.load_pem_private_key((folder / "pass.key").read_bytes(), None)
            cert = _load_cert((folder / "pass.cer").read_bytes())
            wwdr = _load_cert((folder / "wwdr_g4.cer").read_bytes())
        except (ValueError, TypeError) as e:
            # Jamais le contenu des fichiers : seulement le type d'erreur.
            log.error("Wallet : certificats illisibles dans %s (%s)", folder, type(e).__name__)
            return None
        return cls(key, cert, wwdr)

    def sign(self, manifest: bytes) -> bytes:
        options = [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary]
        return (pkcs7.PKCS7SignatureBuilder().set_data(manifest)
                .add_signer(self.cert, self.key, hashes.SHA256())
                .add_certificate(self.wwdr)
                .sign(serialization.Encoding.DER, options))


def _load_cert(raw: bytes) -> x509.Certificate:
    return x509.load_pem_x509_certificate(raw) if raw.lstrip().startswith(b"-----") else x509.load_der_x509_certificate(raw)


def images() -> dict[str, bytes]:
    return {name: (ASSETS / name).read_bytes() for name in IMAGE_NAMES}


def package(pass_json: dict, files: dict[str, bytes], signer: Signer) -> bytes:
    """pass.json + images → .pkpass signé (zip)."""
    content = {"pass.json": json.dumps(pass_json, ensure_ascii=False, indent=1).encode(), **files}
    manifest = json.dumps({name: hashlib.sha1(data).hexdigest() for name, data in content.items()}, indent=1).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in content.items():
            z.writestr(name, data)
        z.writestr("manifest.json", manifest)
        z.writestr("signature", signer.sign(manifest))
    return out.getvalue()


def coordinates(url: str | None) -> tuple[float, float] | None:
    """Latitude, longitude lues dans le lien de carte du lieu (Apple Plans, Google Maps…), sinon None."""
    match = COORDS.search(url or "")
    if not match:
        return None
    lat, lng = float(match[1]), float(match[2])
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat, lng) != (0, 0) else None


def _instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=ZURICH)


def long_day(moment: datetime) -> str:
    """« vendredi 14 novembre 2030 » (heure de Zurich)."""
    local = moment.astimezone(ZURICH)
    return f"{DAYS[local.weekday()]} {local.day}{'er' if local.day == 1 else ''} {MONTHS[local.month - 1]} {local.year}"


def clock(moment: datetime) -> str:
    return moment.astimezone(ZURICH).strftime("%H:%M")


def code_text(code: str) -> str:
    """Code court lisible : « K7M 2QX » (comme prettyCode côté module)."""
    return f"{code[:3]} {code[3:]}"


def ticket_link(origin: str, event_id: str, token: str) -> str:
    """Exactement le contenu du QR du billet dans l'app (ticketLink, web/events/src/lib/tickets.ts)."""
    return f"{origin}/?tab=events&event={event_id}&ticket={token}"


def _when(event: dict, start: datetime, end: datetime | None) -> str:
    when = long_day(start) + ("" if event.get("all_day") else f" à {clock(start)}")
    if end and not event.get("all_day"):
        same_day = end.astimezone(ZURICH).date() == start.astimezone(ZURICH).date()
        when += f" – {clock(end)}" if same_day else f" (fin {long_day(end)} à {clock(end)})"
    return when


def _status_fields(ticket: dict) -> list[dict]:
    """Arrivée et paiement : changent pendant la soirée (le pass se met à jour, Cartes l'annonce)."""
    fields = []
    price = ticket.get("price_chf")
    if price:
        amount = f"{int(price) if float(price).is_integer() else f'{float(price):.2f}'} CHF"
        fields.append({"key": "pay", "label": "PAIEMENT", "value": "Payé ✓" if ticket.get("paid") else f"À payer : {amount}",
                       "changeMessage": "Paiement : %@"})
    arrived = _instant(ticket.get("checked_in_at"))
    fields.append({"key": "arrival", "label": "ARRIVÉE", "value": f"✓ {clock(arrived)}" if arrived else "—",
                   "changeMessage": "Arrivée enregistrée : %@"})
    return fields


def _fields(event: dict, ticket: dict, holder: str) -> dict:
    title = (event.get("title") or "Événement").strip()
    start, end = _instant(event.get("starts_at")), _instant(event.get("ends_at"))
    place = (event.get("location_name") or "").strip()
    address = (event.get("location_address") or "").strip()
    plus_ones = int(ticket.get("plus_ones") or 0)
    secondary = []
    if start:
        secondary.append({"key": "date", "label": "DATE", "value": long_day(start), "changeMessage": "Nouvelle date : %@"})
        if not event.get("all_day"):
            secondary.append({"key": "time", "label": "HEURE", "value": clock(start), "changeMessage": "Nouvelle heure : %@"})
    if place or address:
        secondary.append({"key": "place", "label": "LIEU", "value": place or address, "changeMessage": "Nouveau lieu : %@"})
    auxiliary = [{"key": "holder", "label": "PARTICIPANT", "value": holder}]
    if plus_ones:
        auxiliary.append({"key": "plus", "label": "ACCOMPAGNANTS", "value": f"+{plus_ones}"})
    back = [{"key": "code", "label": "Code du billet (sans scanner)", "value": code_text(ticket["code"]) if ticket.get("code") else "—"}]
    if address:
        back.append({"key": "address", "label": "Adresse", "value": address})
    if start:
        back.append({"key": "when", "label": "Quand", "value": _when(event, start, end)})
    back.append({"key": "help", "label": "À l'entrée",
                 "value": "Montre ce QR à l'organisateur. Ce billet se met à jour tout seul (nouveau QR, date, lieu, "
                          "arrivée, paiement) : garde les mises à jour automatiques activées au dos du billet."})
    return {"primaryFields": [{"key": "event", "label": "ÉVÉNEMENT", "value": title, "changeMessage": "%@"}],
            "secondaryFields": secondary, "auxiliaryFields": auxiliary + _status_fields(ticket), "backFields": back}


def _chf(amount) -> str:
    value = round(float(amount or 0), 2)
    return f"{int(value)} CHF" if value == int(value) else f"{value:.2f} CHF"


def _bar_date(iso: str | None) -> str:
    """« 23 novembre 2026 » (date limite de remboursement), comme le texte d'engagement de la base."""
    months = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
    try:
        day = datetime.fromisoformat(iso).date() if iso else None
    except ValueError:
        day = None
    return f"{day.day} {months[day.month - 1]} {day.year}" if day else ""


def _with_bar(fields: dict, bar: dict) -> dict:
    """Bar de la soirée (maquette v6, écran 9) : « À REMBOURSER » en grand (« Nouveau solde : … » à chaque service),
    « À SERVIR » en tête ; le titre de l'événement passe en second ; les conditions de remboursement au dos."""
    pending = int(bar.get("pending") or 0)
    title = {**fields["primaryFields"][0], "key": "event"}
    due = _bar_date(bar.get("repay_by"))
    terms = f"À rembourser à {bar.get('payee') or 'l’organisateur'} par {bar.get('method') or 'Revolut'}" + (f", avant le {due}." if due else ", après la soirée.")
    return {**fields,
            "headerFields": [{"key": "bar_pending", "label": "À SERVIR", "value": f"{pending} article{'s' if pending > 1 else ''}",
                              "changeMessage": "À servir : %@"}],
            "primaryFields": [{"key": "bar_balance", "label": "À REMBOURSER", "value": _chf(bar.get("balance")),
                               "changeMessage": "Nouveau solde : %@"}],
            "secondaryFields": [title, *fields.get("secondaryFields", [])][:3],
            "backFields": [*fields.get("backFields", []), {"key": "bar_terms", "label": "Bar de la soirée", "value": terms}]}


def ticket_pass(*, origin: str, event: dict, ticket: dict, holder: str, user_id: str,
                auth_token: str | None = None, valid: bool = True, bar: dict | None = None) -> dict:
    """pass.json d'un billet (format eventTicket). Avec auth_token et une origine https : le pass se met à jour tout
    seul (PassKit Web Service sur <origine>/api/wallet/passkit). valid=False : pass annulé, sans QR (plus Présent,
    événement annulé, billet retiré ou option « Billets QR » éteinte)."""
    event_id = event["id"]
    title = (event.get("title") or "Événement").strip()
    start, end = _instant(event.get("starts_at")), _instant(event.get("ends_at"))
    data = {
        "formatVersion": 1,
        "passTypeIdentifier": PASS_TYPE_ID,
        "teamIdentifier": TEAM_ID,
        "serialNumber": f"{event_id}.{user_id}",
        "organizationName": "Party",
        "description": f"Billet · {title}",
        "logoText": "Party",
        "foregroundColor": FOREGROUND,
        "backgroundColor": BACKGROUND,
        "labelColor": LABEL,
        "sharingProhibited": True,
        "eventTicket": _with_bar(_fields(event, ticket, holder), bar) if bar else _fields(event, ticket, holder),
    }
    # Pass annulé (billet retiré, option « Billets QR » éteinte, plus Présent) : plus aucun QR utilisable dans Cartes.
    if valid and ticket.get("token") and ticket.get("code"):
        data["barcodes"] = [{"format": "PKBarcodeFormatQR", "message": ticket_link(origin, event_id, ticket["token"]),
                             "messageEncoding": "iso-8859-1", "altText": code_text(ticket["code"])}]
    if auth_token and origin.startswith("https://"):
        data["webServiceURL"] = f"{origin}{SERVICE_PATH}"
        data["authenticationToken"] = auth_token
    if not valid:
        data["voided"] = True
    if start:
        data["relevantDate"] = start.isoformat()
        data["expirationDate"] = ((end or start) + EXPIRES_AFTER).isoformat()
    if spot := coordinates(event.get("location_url")):
        data["locations"] = [{"latitude": spot[0], "longitude": spot[1], "relevantText": f"{title} : ton billet est prêt"}]
    return data
