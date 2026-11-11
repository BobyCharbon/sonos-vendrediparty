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


# Sondage de dates (avis 9ddbdea7fe8f, 10.11.2026) : toutes les dates proposées en un seul fichier, une entrée par date.
# iOS propose alors « Tout ajouter » ; chaque entrée est provisoire (garder le créneau, rien n'est encore fixé).
MAX_DATES = 20
TENTATIVE_PREFIX = "À confirmer · "


def build_dates(*, uid: str, title: str, dates: list[tuple[str, str, str | None]], location: str = "",
                description: str = "", url: str = "", now: datetime | None = None) -> str:
    """dates : (identifiant de la date proposée, début, fin facultative)."""
    try:
        str(uuid.UUID(uid))
    except (TypeError, ValueError):
        raise CalendarError("Identifiant invalide") from None
    title = title.strip()
    if not title:
        raise CalendarError("Titre manquant")
    if not dates:
        raise CalendarError("Aucune date proposée")
    if len(dates) > MAX_DATES:
        raise CalendarError(f"{MAX_DATES} dates au plus")
    if url and not re.fullmatch(r"https?://[^\s\"<>]{1,500}", url):
        url = ""
    note = (f"Date proposée dans le sondage de « {title[:120]} » : rien n'est encore fixé. Garde le créneau ; "
            "quand la date sera choisie, supprime les autres.")
    details = "\n\n".join(part for part in (note, description.strip()[:1500], url) if part)
    stamp = _stamp((now or datetime.now(timezone.utc)).astimezone(timezone.utc))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Vendredi Party//Evenements//FR", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH"]
    for option, start, end in dates:
        try:
            option_id = str(uuid.UUID(option))
        except (TypeError, ValueError):
            raise CalendarError("Date proposée invalide") from None
        begin = _instant(start, "Début")
        finish = _instant(end, "Fin") if end else begin + DEFAULT_DURATION
        if finish <= begin or finish - begin > MAX_DURATION:
            finish = begin + DEFAULT_DURATION
        lines += ["BEGIN:VEVENT", f"UID:{option_id}@vendredi-party", f"DTSTAMP:{stamp}", f"DTSTART:{_stamp(begin)}",
                  f"DTEND:{_stamp(finish)}", f"SUMMARY:{_text(TENTATIVE_PREFIX + title, 200)}", "STATUS:TENTATIVE",
                  f"DESCRIPTION:{_text(details, 2600)}"]
        if location.strip():
            lines.append(f"LOCATION:{_text(location.strip(), 300)}")
        if url:
            lines.append(f"URL:{url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# Agenda abonné « Vendredi Party » (retours de l'admin du 11.11.2026) : un calendrier par personne, que son agenda relit
# tout seul. Chaque événement ajouté suit ses changements (date, lieu, titre, description). Sondage ouvert : ses dates
# « À confirmer » ; date fixée : la seule bonne, sous le vrai titre ; Non, annulé ou plus concerné : rien.
FEED_REFRESH = "PT1H"
FEED_NAME = "Vendredi Party"


def build_feed(feed: dict | None, *, base_url: str = "", now: datetime | None = None) -> str:
    """feed : réponse de la fonction calendar_feed de la base (None : lien inconnu → calendrier vide)."""
    stamp = _stamp((now or datetime.now(timezone.utc)).astimezone(timezone.utc))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Vendredi Party//Evenements//FR", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{FEED_NAME}", "X-WR-TIMEZONE:Europe/Zurich",
             f"REFRESH-INTERVAL;VALUE=DURATION:{FEED_REFRESH}", f"X-PUBLISHED-TTL:{FEED_REFRESH}"]
    events = (feed or {}).get("events") or []
    for event in events[:150] if isinstance(events, list) else []:
        if isinstance(event, dict):
            lines += _event_entries(event, base_url, stamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _event_url(base_url: str, event_id: str) -> str:
    url = f"{base_url.rstrip('/')}/events/event/{event_id}" if base_url else ""
    return url if re.fullmatch(r"https?://[^\s\"<>]{1,500}", url) else ""


def _event_entries(event: dict, base_url: str, stamp: str) -> list[str]:
    title = str(event.get("title") or "").strip()[:200]
    try:
        event_id = str(uuid.UUID(str(event.get("event_id"))))
    except ValueError:
        return []
    if not event.get("active") or not title:
        return []
    location = str(event.get("location") or "").strip()
    url = _event_url(base_url, event_id)
    description = str(event.get("description") or "").strip()[:1500]
    if event.get("date_mode") == "fixed":
        if not event.get("starts_at") or event.get("my_rsvp") == "no":
            return []  # date pas encore connue, ou la personne ne vient pas
        slots = [(event_id, event["starts_at"], event.get("ends_at"))]
        summary, status, note = title, "CONFIRMED", ""
    else:
        slots = [(str(d.get("id")), d.get("starts_at"), d.get("ends_at")) for d in (event.get("dates") or [])][:MAX_DATES]
        summary, status = TENTATIVE_PREFIX + title, "TENTATIVE"
        note = "Date proposée : rien n'est encore fixé. Quand la date sera choisie, ton agenda gardera la bonne et retirera les autres."
    details = "\n\n".join(p for p in (note, description, url) if p)
    modified = _modified(event.get("updated_at")) or stamp
    out: list[str] = []
    for slot, start, end in slots:
        try:
            slot_id = str(uuid.UUID(slot))
            begin = _instant(str(start), "Début")
            finish = _instant(str(end), "Fin") if end else begin + DEFAULT_DURATION
        except (CalendarError, ValueError):
            continue
        if finish <= begin or finish - begin > MAX_DURATION:
            finish = begin + DEFAULT_DURATION
        out += ["BEGIN:VEVENT", f"UID:{slot_id}@vendredi-party-agenda", f"DTSTAMP:{stamp}", f"LAST-MODIFIED:{modified}",
                f"DTSTART:{_stamp(begin)}", f"DTEND:{_stamp(finish)}", f"SUMMARY:{_text(summary, 200)}",
                f"STATUS:{status}"]
        if details:
            out.append(f"DESCRIPTION:{_text(details, 2600)}")
        if location:
            out.append(f"LOCATION:{_text(location, 300)}")
        if url:
            out.append(f"URL:{url}")
        if status == "CONFIRMED":
            out += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_text(title, 200)}", "TRIGGER:-PT2H", "END:VALARM"]
        out.append("END:VEVENT")
    return out


def _modified(value: object) -> str | None:
    try:
        return _stamp(_instant(str(value), "Modifié")) if value else None
    except CalendarError:
        return None
