"""Agendas ajoutés avec un lien (.ics, adresse secrète de la personne) : lus côté serveur, avec la session de la
personne, pour elle seule (règle 5 de la conformité du 17.11) ; rien n'est gardé ici.

Lecture prudente : https seulement (webcal:// → https://), aucune adresse privée ou locale (le serveur ne sert jamais de
relais vers le réseau interne), 2 Mo au plus, 8 s au plus, 3 redirections vérifiées une à une. Lecture des VEVENT :
DTSTART / DTEND / DURATION (date, date-heure UTC, TZID ou flottante = heure de Suisse), SUMMARY, LOCATION, TRANSP,
STATUS, RRULE courantes (DAILY, WEEKLY + BYDAY, MONTHLY + BYMONTHDAY / BYDAY ordinal, YEARLY ; INTERVAL, COUNT, UNTIL),
EXDATE et RECURRENCE-ID (date déplacée)."""
import ipaddress
import re
import socket
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx

SWISS = ZoneInfo("Europe/Zurich")
MAX_BYTES = 2_000_000
TIMEOUT = 8.0
MAX_EVENTS = 2000
MAX_STEPS = 5000
WINDOWS_TZ = {"W. Europe Standard Time": "Europe/Zurich", "Romance Standard Time": "Europe/Paris",
              "Central Europe Standard Time": "Europe/Budapest", "GMT Standard Time": "Europe/London",
              "Eastern Standard Time": "America/New_York", "Pacific Standard Time": "America/Los_Angeles",
              "UTC": "UTC", "Coordinated Universal Time": "UTC"}
DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


class IcsError(Exception):
    """Phrase pour la personne (« Ce lien ne donne pas d'agenda… »)."""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise IcsError("Ce lien ne donne pas d'agenda. Vérifie qu'il commence par https:// ou webcal://")
    return urlunsplit(parts)


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(infos)


def fetch(url: str, client: httpx.Client | None = None) -> str:
    """Le texte de l'agenda, ou IcsError avec la raison à montrer."""
    url = normalize_url(url)
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": "VendrediParty-Agenda/1"})
    try:
        for _ in range(4):
            host = urlsplit(url).hostname or ""
            if not _public_host(host):
                raise IcsError("Ce lien ne donne pas d'agenda (adresse introuvable).")
            with client.stream("GET", url) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = normalize_url(str(httpx.URL(url).join(r.headers["location"])))
                    continue
                if r.status_code != 200:
                    raise IcsError(f"L'agenda ne répond pas (erreur {r.status_code}). Le lien est-il encore valable ?")
                data = b""
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > MAX_BYTES:
                        raise IcsError("Cet agenda est trop grand (2 Mo au plus).")
                text = data.decode("utf-8", errors="replace")
                if "BEGIN:VCALENDAR" not in text[:2000].upper():
                    raise IcsError("Ce lien ne donne pas d'agenda. Vérifie qu'il commence par https:// ou webcal://")
                return text
        raise IcsError("Trop de redirections.")
    except httpx.HTTPError:
        raise IcsError("L'agenda ne répond pas. Réessaie plus tard.") from None
    finally:
        if own:
            client.close()


def _lines(text: str) -> list[tuple[str, dict, str]]:
    """Lignes dépliées : (NOM, paramètres, valeur)."""
    raw = re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n"))
    out = []
    for line in raw.split("\n"):
        if ":" not in line:
            continue
        head, value = line.split(":", 1)
        name, *params = head.split(";")
        p = {}
        for item in params:
            if "=" in item:
                k, v = item.split("=", 1)
                p[k.upper()] = v.strip('"')
        out.append((name.upper(), p, value.strip()))
    return out


def _zone(tzid: str | None):
    if not tzid:
        return SWISS
    tzid = WINDOWS_TZ.get(tzid, tzid)
    try:
        return ZoneInfo(tzid)
    except Exception:  # noqa: BLE001 - fuseau inconnu : heure de Suisse
        return SWISS


def _when(value: str, params: dict) -> tuple[datetime, bool]:
    """(instant UTC, journée entière)."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        d = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(d, time(0), SWISS).astimezone(timezone.utc), True
    utc = value.endswith("Z")
    dt = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if utc:
        return dt.replace(tzinfo=timezone.utc), False
    return dt.replace(tzinfo=_zone(params.get("TZID"))).astimezone(timezone.utc), False


def _duration(value: str) -> timedelta:
    m = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value.strip())
    if not m:
        return timedelta(hours=1)
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    return timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


def _events(text: str) -> list[dict]:
    events, cur = [], None
    for name, params, value in _lines(text):
        if name == "BEGIN" and value.upper() == "VEVENT":
            cur = {"exdates": set()}
        elif name == "END" and value.upper() == "VEVENT" and cur is not None:
            if "start" in cur:
                events.append(cur)
            cur = None
        elif cur is None:
            continue
        elif name in ("DTSTART", "DTEND", "RECURRENCE-ID"):
            try:
                at, all_day = _when(value, params)
            except ValueError:
                continue
            key = {"DTSTART": "start", "DTEND": "end", "RECURRENCE-ID": "recurrence_id"}[name]
            cur[key] = at
            if name == "DTSTART":
                cur["all_day"] = all_day
                cur["zone"] = _zone(params.get("TZID"))  # répétitions à heure locale fixe (heure de Suisse sans TZID)
        elif name == "DURATION":
            cur["duration"] = _duration(value)
        elif name in ("SUMMARY", "LOCATION"):
            cur[name.lower()] = value.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")[:200]
        elif name == "UID":
            cur["uid"] = value[:200]
        elif name == "RRULE":
            cur["rrule"] = dict(x.split("=", 1) for x in value.upper().split(";") if "=" in x)
        elif name == "EXDATE":
            for v in value.split(","):
                try:
                    cur["exdates"].add(_when(v, params)[0])
                except ValueError:
                    pass
        elif name == "TRANSP":
            cur["transparent"] = value.upper() == "TRANSPARENT"
        elif name == "STATUS":
            cur["cancelled"] = value.upper() == "CANCELLED"
    return events


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date | None:
    first = date(year, month, 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    days = [first + timedelta(days=i) for i in range((nxt - first).days) if (first + timedelta(days=i)).weekday() == weekday]
    try:
        return days[n - 1] if n > 0 else days[n]
    except IndexError:
        return None


def _occurrences(ev: dict, end: datetime):
    """Débuts (UTC) d'une série, dans l'ordre, jusqu'à `end`."""
    start: datetime = ev["start"]
    rule = ev.get("rrule")
    if not rule:
        yield start
        return
    zone = ev.get("zone") or SWISS
    local = start.astimezone(zone)
    freq = rule.get("FREQ")
    interval = max(1, int(rule.get("INTERVAL", "1") or 1))
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = None
    if rule.get("UNTIL"):
        try:
            until = _when(rule["UNTIL"], {})[0]
        except ValueError:
            until = None
    byday = [d for d in rule.get("BYDAY", "").split(",") if d]
    n = 0

    def at(d: date) -> datetime:
        return datetime.combine(d, local.timetz().replace(tzinfo=None), zone).astimezone(timezone.utc)

    for step in range(MAX_STEPS):
        if freq == "DAILY":
            cands = [at(local.date() + timedelta(days=step * interval))]
        elif freq == "WEEKLY":
            monday = local.date() - timedelta(days=local.weekday()) + timedelta(weeks=step * interval)
            wds = sorted(DAYS[d[-2:]] for d in byday if d[-2:] in DAYS) or [local.weekday()]
            cands = [at(monday + timedelta(days=w)) for w in wds]
        elif freq == "MONTHLY":
            m0 = local.month - 1 + step * interval
            y, m = local.year + m0 // 12, m0 % 12 + 1
            cands = []
            if byday:
                for d in byday:
                    mm = re.fullmatch(r"([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)", d)
                    if mm:
                        day = _nth_weekday(y, m, DAYS[mm.group(2)], int(mm.group(1) or 1))
                        if day:
                            cands.append(at(day))
            else:
                md = int(rule.get("BYMONTHDAY", str(local.day)).split(",")[0])
                try:
                    cands = [at(date(y, m, md))]
                except ValueError:
                    cands = []
        elif freq == "YEARLY":
            try:
                cands = [at(local.date().replace(year=local.year + step * interval))]
            except ValueError:
                cands = []
        else:
            yield start
            return
        for c in sorted(cands):
            if c < start:
                continue
            if (until and c > until) or c > end or (count is not None and n >= count):
                return
            n += 1
            yield c


def events_between(text: str, f: datetime, t: datetime) -> list[dict]:
    """Rendez-vous de l'agenda qui touchent [f, t) : titre, lieu, début, fin, journée entière, compte comme « pris »."""
    evs = _events(text)
    moved = {(e.get("uid"), e["recurrence_id"]) for e in evs if e.get("recurrence_id")}
    out = []
    for ev in evs:
        if ev.get("cancelled"):
            continue
        length = (ev["end"] - ev["start"]) if ev.get("end") and ev["end"] > ev["start"] else \
            ev.get("duration") or (timedelta(days=1) if ev.get("all_day") else timedelta(hours=1))
        for s in _occurrences(ev, t):
            if s in ev["exdates"] or (not ev.get("recurrence_id") and (ev.get("uid"), s) in moved):
                continue
            if s + length <= f:
                continue
            out.append({"uid": ev.get("uid"), "title": ev.get("summary") or "Occupé", "place": ev.get("location") or None,
                        "starts_at": s.isoformat(), "ends_at": (s + length).isoformat(),
                        "all_day": bool(ev.get("all_day")), "busy": not ev.get("transparent")})
            if len(out) >= MAX_EVENTS:
                return sorted(out, key=lambda x: x["starts_at"])
    return sorted(out, key=lambda x: x["starts_at"])
