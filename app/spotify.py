"""Recherche Spotify (Client Credentials : aucun compte requis côté invités)."""

import base64
import threading
import time

import httpx


class Spotify:
    def __init__(self, client_id: str, client_secret: str, market: str = "CH"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.market = market
        self._token = ""
        self._expires = 0.0
        self._lock = threading.Lock()
        self._http = httpx.Client(timeout=10)

    def _auth(self) -> str:
        with self._lock:
            if time.time() < self._expires - 60:
                return self._token
            basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            r = self._http.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                headers={"Authorization": f"Basic {basic}"},
            )
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._expires = time.time() + data["expires_in"]
            return self._token

    def search(self, query: str, limit: int = 10) -> list[dict]:
        r = self._http.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": "track", "limit": limit, "market": self.market},
            headers={"Authorization": f"Bearer {self._auth()}"},
        )
        r.raise_for_status()
        return [self._track(t) for t in r.json()["tracks"]["items"] if t]

    def track(self, track_id: str) -> dict:
        r = self._http.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            params={"market": self.market},
            headers={"Authorization": f"Bearer {self._auth()}"},
        )
        r.raise_for_status()
        return self._track(r.json())

    @staticmethod
    def _track(t: dict) -> dict:
        images = t.get("album", {}).get("images") or []
        return {
            "id": t["id"],
            "title": t["name"],
            "artist": ", ".join(a["name"] for a in t.get("artists", [])),
            "album": t.get("album", {}).get("name", ""),
            # Spotify trie les images de la plus grande à la plus petite.
            "image": images[-2]["url"] if len(images) > 1 else (images[0]["url"] if images else ""),
            "duration_ms": t.get("duration_ms", 0),
            "explicit": t.get("explicit", False),
        }
