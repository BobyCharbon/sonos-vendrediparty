"""Fichier iCalendar d'une sortie, généré à partir des champs envoyés par le client.

Aucune donnée n'est lue côté serveur : le client authentifié transmet ce qu'il affiche
déjà. Le serveur ne fait que valider, borner et formater, pour que iOS ouvre la feuille
« Ajouter au calendrier » sur une vraie réponse HTTP text/calendar.
"""
from datetime import datetime, timedelta, timezone
import re
import unicodedata
import uuid

MAX_DURATION = timedelta(days=14)
DEFAULT_DURATION = timedelta(hours=3)


class CalendarError(ValueError):
    pass


def _instant(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise CalendarError(f"{name} invalide") from None
    if parsed.tzinfo is None:
        raise CalendarError(f"{name} doit préciser le fuseau horaire")
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def _text(value: str, limit: int) -> str:
    value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value.replace("\r\n", "\n").replace("\r", "\n"))[:limit]
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Plie les lignes à 75 octets (RFC 5545 §3.1) sans couper un caractère UTF-8."""
    out, current = [], ""
    for char in line:
        if len((current + char).encode()) > (75 if not out else 74):
            out.append(current)
            current = char
        else:
            current += char
    out.append(current)
    return "\r\n ".join(out)


def filename(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-").lower()
    return f"{slug[:40] or 'evenement'}.ics"


def build(*, uid: str, title: str, start: str, end: str | None = None, location: str = "",
          description: str = "", url: str = "", now: datetime | None = None) -> str:
    try:
        event_id = str(uuid.UUID(uid))
    except (TypeError, ValueError):
        raise CalendarError("Identifiant invalide") from None
    title = title.strip()
    if not title:
        raise CalendarError("Titre manquant")
    begin = _instant(start, "Début")
    finish = _instant(end, "Fin") if end else begin + DEFAULT_DURATION
    if finish <= begin or finish - begin > MAX_DURATION:
        finish = begin + DEFAULT_DURATION
    if url and not re.fullmatch(r"https?://[^\s\"<>]{1,500}", url):
        url = ""
    details = "\n\n".join(part for part in (description.strip()[:2000], url) if part)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Vendredi Party//Evenements//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{event_id}@vendredi-party",
        f"DTSTAMP:{_stamp((now or datetime.now(timezone.utc)).astimezone(timezone.utc))}",
        f"DTSTART:{_stamp(begin)}",
        f"DTEND:{_stamp(finish)}",
        f"SUMMARY:{_text(title, 200)}",
    ]
    if details:
        lines.append(f"DESCRIPTION:{_text(details, 2600)}")
    if location.strip():
        lines.append(f"LOCATION:{_text(location.strip(), 300)}")
    if url:
        lines.append(f"URL:{url}")
    lines += [
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_text(title, 200)}",
        "TRIGGER:-PT2H",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
