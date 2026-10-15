"""Lien collé dans la recherche (Spotify, Deezer, YouTube, Apple Music) → le même titre sur Spotify.

Spotify : titre exact. Deezer : son ISRC (code unique de l'enregistrement) retrouve exactement le même
sur Spotify. YouTube / Apple Music : on lit le titre et l'artiste, puis on cherche ; l'invité choisit.
Seuls ces services sont contactés (liste fermée) : un lien collé ne fait jamais visiter n'importe quelle adresse.
"""

import re
from urllib.parse import urlparse

import httpx

URL_RE = re.compile(r"https?://\S+", re.I)
SPOTIFY_TRACK_RE = re.compile(r"(?:open\.spotify\.com/(?:intl-[a-z-]+/)?track/|spotify:track:)([A-Za-z0-9]{22})")
# Liens courts : on suit la redirection, seulement vers ces hôtes.
SHORT_HOSTS = {"spotify.link", "link.deezer.com", "deezer.page.link", "dzr.page.link"}
KNOWN_HOSTS = SHORT_HOSTS | {"open.spotify.com", "www.deezer.com", "deezer.com", "www.youtube.com", "youtube.com", "m.youtube.com",
                             "music.youtube.com", "youtu.be", "music.apple.com", "itunes.apple.com"}

NOISE_RE = re.compile(r"[\(\[][^\)\]]*(?:official|officiel|clip|lyrics?|paroles|audio|video|vidéo|visualizer|hd|4k|remaster(?:ed)?|live)[^\)\]]*[\)\]]", re.I)


class LinkError(Exception):
    pass


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _clean_title(title: str) -> str:
    """« Artiste - Titre (Clip officiel) [HD] » → « Artiste Titre »."""
    t = NOISE_RE.sub(" ", title)
    t = re.sub(r"\b(?:ft\.?|feat\.?|featuring)\b", " ", t, flags=re.I)
    t = t.replace(" - ", " ").replace("|", " ").replace("–", " ")
    return " ".join(t.split())[:100]


def resolve(text: str, spotify, http: httpx.Client | None = None) -> dict | None:
    """None si ce n'est pas un lien ; sinon {"via": "Deezer", "tracks": [...] }."""
    m = URL_RE.search(text)
    if not m and not SPOTIFY_TRACK_RE.search(text):
        return None
    url = m.group(0) if m else text.strip()
    http = http or httpx.Client(timeout=8)
    host = _host(url)
    if m and host not in KNOWN_HOSTS:
        raise LinkError("Lien non reconnu : colle un lien Spotify, Deezer, YouTube ou Apple Music")
    if host in SHORT_HOSTS:
        r = http.get(url, follow_redirects=False)
        loc = r.headers.get("location", "")
        if _host(loc) not in KNOWN_HOSTS - SHORT_HOSTS:
            # Certains liens courts redirigent en plusieurs étapes ou via une page : on lit la page.
            found = SPOTIFY_TRACK_RE.search(r.text) or re.search(r"deezer\.com/(?:[a-z]{2}/)?track/(\d+)", r.text)
            if not found:
                raise LinkError("Impossible d'ouvrir ce lien court")
            loc = f"https://open.spotify.com/track/{found.group(1)}" if found.re is SPOTIFY_TRACK_RE else f"https://www.deezer.com/track/{found.group(1)}"
        url, host = loc, _host(loc)

    if sp := SPOTIFY_TRACK_RE.search(url):
        return {"via": "Spotify", "tracks": [spotify.track(sp.group(1))]}

    if "deezer.com" in host:
        dz = re.search(r"/track/(\d+)", url)
        if not dz:
            raise LinkError("Colle le lien d'un titre Deezer (pas d'un album ou d'une playlist)")
        d = http.get(f"https://api.deezer.com/track/{dz.group(1)}").json()
        if d.get("error"):
            raise LinkError("Titre Deezer introuvable")
        tracks = spotify.search(f"isrc:{d['isrc']}", limit=3) if d.get("isrc") else []
        if not tracks:
            tracks = spotify.search(f"{d.get('artist', {}).get('name', '')} {d.get('title', '')}", limit=5)
        return {"via": "Deezer", "tracks": tracks}

    if host in ("youtu.be",) or "youtube.com" in host:
        r = http.get("https://www.youtube.com/oembed", params={"url": url.replace("music.youtube.com", "www.youtube.com"), "format": "json"})
        if r.status_code != 200:
            raise LinkError("Vidéo YouTube introuvable")
        o = r.json()
        title = o.get("title", "")
        # YouTube Music : la chaîne « Artiste - Topic » donne l'artiste.
        author = re.sub(r"\s*-\s*Topic$", "", o.get("author_name", ""))
        query = _clean_title(title if " - " in title else f"{author} {title}")
        return {"via": "YouTube", "tracks": spotify.search(query, limit=5), "query": query}

    if "apple.com" in host:
        tid = re.search(r"[?&]i=(\d+)", url) or re.search(r"/song/[^/]*/(\d+)", url)
        if not tid:
            raise LinkError("Colle le lien d'un titre Apple Music (pas d'un album entier)")
        res = http.get("https://itunes.apple.com/lookup", params={"id": tid.group(1)}).json().get("results") or []
        if not res:
            raise LinkError("Titre Apple Music introuvable")
        query = _clean_title(f"{res[0].get('artistName', '')} {res[0].get('trackName', '')}")
        return {"via": "Apple Music", "tracks": spotify.search(query, limit=5), "query": query}

    raise LinkError("Lien non reconnu : colle un lien Spotify, Deezer, YouTube ou Apple Music")
