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
        self._tracks: dict[str, dict] = {}

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
        # Petit cache : le mode extérieur relit les titres pour la file (pochette, durée).
        if track_id in self._tracks:
            return self._tracks[track_id]
        r = self._http.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            params={"market": self.market},
            headers={"Authorization": f"Bearer {self._auth()}"},
        )
        r.raise_for_status()
        t = self._tracks[track_id] = self._track(r.json())
        if len(self._tracks) > 2000:
            self._tracks.pop(next(iter(self._tracks)))
        return t

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


# --- Compte Spotify de l'hôte (mode « Party extérieur ») : pilotage de la lecture sur son téléphone ---

import json
import urllib.parse
from pathlib import Path

USER_SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"


class SpotifyError(Exception):
    pass


class SpotifyUser:
    """Autorisation OAuth de l'hôte (une seule fois), gardée sur le serveur et renouvelée toute seule."""

    def __init__(self, client_id: str, client_secret: str, path: Path, redirect_uri: str):
        self.client_id, self.client_secret = client_id, client_secret
        self.path, self.redirect_uri = path, redirect_uri
        self._lock = threading.Lock()
        self._http = httpx.Client(timeout=10)
        try:
            self.data = json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            self.data = {}

    @property
    def connected(self) -> bool:
        return bool(self.data.get("refresh_token"))

    @property
    def name(self) -> str:
        return self.data.get("name", "")

    def auth_url(self, state: str) -> str:
        return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
            "client_id": self.client_id, "response_type": "code", "redirect_uri": self.redirect_uri,
            "scope": USER_SCOPES, "state": state, "show_dialog": "true"})

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data))
        tmp.chmod(0o600)
        tmp.replace(self.path)

    def _token_request(self, data: dict) -> dict:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = self._http.post("https://accounts.spotify.com/api/token", data=data, headers={"Authorization": f"Basic {basic}"})
        if r.status_code != 200:
            raise SpotifyError("Spotify a refusé la connexion : " + r.text[:200])
        return r.json()

    def exchange(self, code: str):
        """Fin de la connexion : on garde les jetons et le nom du compte."""
        tok = self._token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri})
        with self._lock:
            self.data = {"access_token": tok["access_token"], "refresh_token": tok["refresh_token"],
                         "expires_at": time.time() + tok["expires_in"]}
        me = self.api("GET", "/me") or {}
        self.data["name"] = me.get("display_name") or me.get("id", "")
        self.data["premium"] = me.get("product") == "premium"
        self._save()

    def disconnect(self):
        self.data = {}
        self.path.unlink(missing_ok=True)

    def _access(self) -> str:
        with self._lock:
            if not self.connected:
                raise SpotifyError("Connecte d'abord ton compte Spotify (Réglages de l'admin)")
            if time.time() > self.data.get("expires_at", 0) - 60:
                tok = self._token_request({"grant_type": "refresh_token", "refresh_token": self.data["refresh_token"]})
                self.data["access_token"] = tok["access_token"]
                self.data["expires_at"] = time.time() + tok["expires_in"]
                if tok.get("refresh_token"):
                    self.data["refresh_token"] = tok["refresh_token"]
                self._save()
            return self.data["access_token"]

    def api(self, method: str, path: str, **kw):
        r = self._http.request(method, "https://api.spotify.com/v1" + path, headers={"Authorization": f"Bearer {self._access()}"}, **kw)
        if r.status_code == 204 or not r.content:
            return None
        if r.status_code >= 400:
            try:
                err = r.json().get("error", {})
            except ValueError:
                err = {}
            reason, msg = err.get("reason", ""), err.get("message", r.text[:120])
            if reason == "NO_ACTIVE_DEVICE" or r.status_code == 404:
                raise SpotifyError("Aucun appareil Spotify actif : lance une musique sur ton téléphone")
            if reason == "PREMIUM_REQUIRED":
                raise SpotifyError("Spotify Premium est nécessaire pour piloter la lecture")
            if reason == "VOLUME_CONTROL_DISALLOW":
                raise SpotifyError("Ce téléphone ne laisse pas régler le volume à distance : utilise ses boutons")
            raise SpotifyError(f"Spotify : {msg}")
        return r.json()

    # Lecture
    def playback(self) -> dict | None:
        return self.api("GET", "/me/player", params={"additional_types": "track"})

    def queue(self, track_id: str):
        self.api("POST", "/me/player/queue", params={"uri": f"spotify:track:{track_id}"})

    def play(self, context_uri: str | None = None):
        self.api("PUT", "/me/player/play", json={"context_uri": context_uri} if context_uri else None)

    def pause(self):
        self.api("PUT", "/me/player/pause")

    def next(self):
        self.api("POST", "/me/player/next")

    def shuffle(self, on: bool):
        self.api("PUT", "/me/player/shuffle", params={"state": "true" if on else "false"})

    def volume(self, percent: int):
        self.api("PUT", "/me/player/volume", params={"volume_percent": percent})
