"""Lire un lien d'événement pour l'assistant IA (« crée l'événement à partir de ce lien ») : titre, description, image,
données structurées (schema.org Event : date, lieu, prix), lien de billetterie et texte visible de la page.

Sécurité : seulement http(s) vers des adresses publiques (jamais le réseau local ni le serveur lui-même, même après une
redirection), 8 s et 1,5 Mo au plus, pages HTML ou texte seulement. Le contenu lu est une DONNÉE donnée à Claude, jamais
une instruction (le prompt le rappelle)."""
import html
import ipaddress
import json
import re
import socket
import time
from urllib.parse import urljoin, urlparse

import httpx

URL = re.compile(r"https?://[^\s<>\"'«»]+", re.I)
MAX_LINKS = 2
MAX_BYTES = 1_500_000
MAX_TEXT = 6000
TIMEOUT = 8
MAX_REDIRECTS = 4
CACHE_SECONDS = 600
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Party/1.0"
TICKET = re.compile(r"ticket|billet|billett|eventfrog|petzi|starticket|ticketcorner|eventbrite|ra\.co|shop|tix|kaufen|réserv",
                    re.I)

_cache: dict[str, tuple[float, dict]] = {}


class LinkError(ValueError):
    """Raison lisible (« page introuvable »), transmise à Claude pour qu'il demande les infos manquantes."""


def find_urls(text: str) -> list[str]:
    found = [u.rstrip(".,;:!?)]}") for u in URL.findall(text or "")]
    return list(dict.fromkeys(found))[:MAX_LINKS]


def _public(host: str) -> bool:
    """Toutes les adresses du nom sont publiques (pas de 127.0.0.1, 192.168…, métadonnées cloud, IPv6 locales)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    ips = {ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos}
    return bool(ips) and all(ip.is_global for ip in ips)


def _fetch(url: str, client: httpx.Client) -> tuple[str, str]:
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise LinkError("lien invalide")
        if not _public(parts.hostname):
            raise LinkError("adresse non publique")
        with client.stream("GET", url, headers={"User-Agent": UA, "Accept-Language": "fr-CH,fr;q=0.9,de;q=0.7,en;q=0.6"}) as r:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code != 200:
                raise LinkError(f"la page répond {r.status_code}")
            kind = r.headers.get("content-type", "")
            if "html" not in kind and "text/plain" not in kind:
                raise LinkError("ce n'est pas une page web")
            body = b""
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    break
            return url, body[:MAX_BYTES].decode(r.encoding or "utf-8", errors="replace")
    raise LinkError("trop de redirections")


def _meta(page: str, *names: str) -> str:
    for name in names:
        m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]*content=["\']([^"\']*)', page, re.I) \
            or re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(name)}["\']', page, re.I)
        if m and m.group(1).strip():
            return html.unescape(m.group(1).strip())
    return ""


def _events_ld(page: str) -> list[dict]:
    """Données schema.org de type Event (souvent présentes : billetteries, Facebook, sites de clubs)."""
    out = []
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I)[:8]:
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                kind = item.get("@type")
                kinds = kind if isinstance(kind, list) else [kind]
                if any(isinstance(k, str) and k.endswith("Event") for k in kinds):
                    out.append(item)
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)
    return out[:3]


def _text(page: str) -> str:
    page = re.sub(r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    page = re.sub(r"<(br|/p|/div|/li|/h\d|/tr)[^>]*>", "\n", page, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)[:MAX_TEXT]


def _main_image(page: str) -> str:
    """Sans og:image : l'image que la page charge en priorité, sinon la première grande image qui n'est pas un logo."""
    imgs = re.findall(r"<img\b[^>]*>", page, re.I)
    src = lambda tag: (re.search(r'\ssrc=["\']([^"\']+)', tag) or [None, ""])[1]
    width = lambda tag: int((re.search(r'\swidth=["\']?(\d+)', tag) or [None, "0"])[1])
    plain = [t for t in imgs if src(t) and not re.search(r"logo|icon|avatar|sprite|\.svg", src(t), re.I)]
    first = next((t for t in plain if "fetchpriority=\"high\"" in t), None) or next((t for t in plain if width(t) >= 600), None)
    return html.unescape(src(first)) if first else ""


def _ticket_links(page: str, base: str) -> list[str]:
    found = []
    for href, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        label = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", label)).split())
        if TICKET.search(href) or TICKET.search(label):
            url = urljoin(base, html.unescape(href))
            if url.startswith("https://") and url not in found:
                found.append(url)
    return found[:3]


def read(url: str, client: httpx.Client | None = None) -> dict:
    """Ce que la page dit de l'événement ; LinkError (raison lisible) si elle ne peut pas être lue."""
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
    try:
        final, page = _fetch(url, client)
    except httpx.HTTPError as e:
        raise LinkError("la page ne répond pas") from e
    finally:
        if own:
            client.close()
    image = _meta(page, "og:image", "twitter:image") or _main_image(page)
    title = _meta(page, "og:title", "twitter:title") or html.unescape(
        (re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I) or [None, ""])[1]).strip()
    info = {"url": final, "title": " ".join(title.split())[:200],
            "description": _meta(page, "og:description", "description", "twitter:description")[:600],
            "image": urljoin(final, image) if image else "", "events": _events_ld(page),
            "tickets": _ticket_links(page, final), "text": _text(page)}
    _cache[url] = (time.time(), info)
    return info


def as_prompt(url: str, info: dict | None, error: str = "") -> str:
    """Bloc de texte pour Claude : clairement délimité, et présenté comme des données à extraire."""
    if info is None:
        return f"[Lien {url} : illisible ({error}). Demande à la personne ce qui manque.]"
    parts = [f"<page url=\"{info['url']}\">", f"Titre : {info['title']}"]
    if info["description"]:
        parts.append(f"Résumé : {info['description']}")
    if info["events"]:
        parts.append("Données structurées (schema.org) : " + json.dumps(info["events"], ensure_ascii=False)[:3000])
    if info["tickets"]:
        parts.append("Liens de billetterie : " + ", ".join(info["tickets"]))
    parts += ["Texte de la page :", info["text"], "</page>"]
    return "\n".join(parts)


def cover(infos: list[dict]) -> str:
    """Image de couverture de l'événement : celle de la page (og:image ou schema.org), en https seulement."""
    for info in infos:
        candidates = [info.get("image", "")]
        for ev in info.get("events", []):
            img = ev.get("image")
            candidates += img if isinstance(img, list) else [img.get("url") if isinstance(img, dict) else img]
        for c in candidates:
            if isinstance(c, str) and c.startswith("https://") and len(c) < 1000:
                return c
    return ""
