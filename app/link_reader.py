"""Lire un lien d'événement pour l'assistant IA (« crée l'événement à partir de ce lien ») : titre, description, image,
données structurées (schema.org Event : date, lieu, prix), lien de billetterie et texte visible de la page.

Sécurité : seulement http(s) vers des adresses publiques (jamais le réseau local ni le serveur lui-même, même après une
redirection), 8 s et 1,5 Mo au plus, pages HTML ou texte seulement. Le contenu lu est une DONNÉE donnée à Claude, jamais
une instruction (le prompt le rappelle)."""
import ipaddress
import json
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

URL = re.compile(r"https?://[^\s<>\"'«»]+", re.I)
MAX_LINKS = 2
MAX_BYTES = 1_500_000
MAX_IMAGE = 8_000_000
MAX_TEXT = 6000
TIMEOUT = 8
MAX_REDIRECTS = 4
CACHE_SECONDS = 600
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Party/1.0"
TICKET = re.compile(r"\b(tickets?|billets?|billett[es]?|get ticket|buy|acheter|réserver|kaufen|vorverkauf)\b", re.I)
NOT_TICKET = re.compile(r"vendre|verkaufen|sell|organis|veranstalt|partenaire|partner|jobs?\b|gutschein|bon cadeau", re.I)
LOGO = re.compile(r"logo|icon|avatar|sprite|\.svg", re.I)
CACHE_MAX = 200

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
    # Une IPv6 qui cache une IPv4 (::ffff:127.0.0.1, 64:ff9b::…) est jugée sur l'IPv4 qu'elle cache.
    real = {getattr(ip, "ipv4_mapped", None) or getattr(ip, "sixtofour", None) or ip for ip in ips}
    return bool(real) and all(ip.is_global and not ip.is_multicast for ip in real | ips)


def _download(url: str, client: httpx.Client, accept, limit: int, cut: bool = False) -> tuple[str, bytes, httpx.Response]:
    """GET sûr : adresses publiques seulement, redirections revérifiées, taille bornée (cut : on garde le début au lieu
    de refuser) ; accept(content-type) décide."""
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.port not in (None, 80, 443):
            raise LinkError("lien invalide")
        if not _public(parts.hostname):
            raise LinkError("adresse non publique")
        with client.stream("GET", url, headers={"User-Agent": UA, "Accept-Language": "fr-CH,fr;q=0.9,de;q=0.7,en;q=0.6"}) as r:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            if r.status_code != 200:
                raise LinkError(f"la page répond {r.status_code}")
            if not accept(r.headers.get("content-type", "")):
                raise LinkError("type de contenu inattendu")
            body = b""
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > limit:
                    if cut:  # page HTML : on garde le début (l'événement y est)
                        return url, body[:limit], r
                    raise LinkError("trop lourd")
            return url, body, r
    raise LinkError("trop de redirections")


def _fetch(url: str, client: httpx.Client) -> tuple[str, str]:
    try:
        final, body, r = _download(url, client, lambda kind: "html" in kind or "text/plain" in kind, MAX_BYTES, cut=True)
    except LinkError as e:
        raise LinkError("ce n'est pas une page web") if str(e) == "type de contenu inattendu" else e
    return final, body.decode(r.encoding or "utf-8", errors="replace")


def fetch_image(url: str, client: httpx.Client | None = None) -> bytes:
    """L'image d'une page (affiche, flyer), téléchargée pour être gardée chez nous : 8 Mo au plus."""
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT, follow_redirects=False)
    try:
        return _download(url, client, lambda kind: kind.startswith("image/"), MAX_IMAGE)[1]
    except (httpx.HTTPError, ValueError) as e:
        raise LinkError("image injoignable") from e
    finally:
        if own:
            client.close()


class _Page(HTMLParser):
    """Lecture de la page en un seul passage (temps proportionnel à sa taille : aucune expression régulière qui
    s'emballe sur du HTML piégé) : balises meta, titre, données schema.org, liens, images et texte visible."""
    SKIP = {"script", "style", "noscript", "svg", "template", "head"}
    BREAK = {"br", "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title, self.ld, self.links, self.imgs, self.text = "", [], [], [], []
        self._skip = 0
        self._in_title = self._in_ld = False
        self._ld_buf: list[str] = []
        self._link: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and "ld+json" in a.get("type", "").lower() and len(self.ld) < 8:
            self._in_ld, self._ld_buf = True, []
        elif tag == "a" and a.get("href") and len(self.links) < 400:
            self._link = {"href": a["href"], "label": []}
        elif tag == "img" and a.get("src") and len(self.imgs) < 200:
            self.imgs.append(a)
        if tag in self.SKIP:
            self._skip += 1
        if tag in self.BREAK:
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld.append("".join(self._ld_buf))
        elif tag == "a" and self._link is not None:
            self.links.append((self._link["href"], " ".join("".join(self._link["label"]).split())))
            self._link = None
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in self.BREAK:
            self.text.append("\n")

    def handle_data(self, data):
        if self._in_ld:
            self._ld_buf.append(data)
        elif self._in_title:
            self.title += data
        elif not self._skip:
            self.text.append(data)
            if self._link is not None:
                self._link["label"].append(data)


def _events_ld(blocks: list[str]) -> list[dict]:
    """Données schema.org de type Event (souvent présentes : billetteries, Facebook, sites de clubs)."""
    out = []
    for raw in blocks:
        try:
            data = json.loads(raw.strip())
        except (ValueError, RecursionError):
            continue
        stack, seen = (data if isinstance(data, list) else [data]), 0
        while stack and seen < 5000:  # parcours borné : un JSON géant ou très imbriqué ne bloque rien
            seen += 1
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


def _main_image(imgs: list[dict]) -> str:
    """Sans og:image : l'image que la page charge en priorité, sinon la première grande image qui n'est pas un logo."""
    plain = [i for i in imgs if not LOGO.search(i["src"])]
    width = lambda i: int(i.get("width")) if str(i.get("width", "")).isdigit() else 0
    first = next((i for i in plain if i.get("fetchpriority") == "high"), None) or next((i for i in plain if width(i) >= 600), None)
    return first["src"] if first else ""


def _ticket_links(links: list[tuple[str, str]], base: str) -> list[str]:
    """Le vrai bouton de billetterie : un lien dont le TEXTE parle de billets (le nom du site ne suffit pas)."""
    found = []
    for href, label in links:
        if label and len(label) <= 40 and TICKET.search(label) and not NOT_TICKET.search(label):
            url = _join(base, href)
            if url.startswith("https://") and url not in found:
                found.append(url)
    return found[:3]


def _join(base: str, href: str) -> str:
    try:
        return urljoin(base, href.strip())
    except ValueError:
        return ""


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
    except LinkError:
        raise
    except ValueError as e:  # lien mal formé (« https://[::1 », port non numérique…)
        raise LinkError("lien invalide") from e
    finally:
        if own:
            client.close()
    parsed = _Page()
    try:
        parsed.feed(page)
        parsed.close()
    except (AssertionError, ValueError):
        pass  # HTML vraiment cassé : on garde ce qui a été lu
    meta = parsed.meta
    image = meta.get("og:image") or meta.get("twitter:image") or _main_image(parsed.imgs)
    title = meta.get("og:title") or meta.get("twitter:title") or parsed.title
    text = "".join(parsed.text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    info = {"url": final, "title": " ".join(title.split())[:200],
            "description": (meta.get("og:description") or meta.get("description") or meta.get("twitter:description") or "")[:600],
            "image": _join(final, image) if image else "", "events": _events_ld(parsed.ld),
            "tickets": _ticket_links(parsed.links, final),
            "text": "\n".join(line for line in lines if line)[:MAX_TEXT]}
    if len(_cache) > CACHE_MAX:  # mémoire bornée : on repart à vide
        _cache.clear()
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
    parts += ["Texte de la page :", info["text"]]
    body = "\n".join(parts[1:]).replace("</page>", "</ page>").replace("<page", "< page")  # la page ne sort pas du bloc
    return "\n".join([parts[0], body, "</page>"])


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
