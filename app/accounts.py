"""Comptes Party (Supabase) reliés aux jeux : le serveur vérifie lui-même la connexion auprès de Supabase,
puis donne au compte un identifiant de joueur stable et secret, le même sur tous ses appareils."""
import hashlib
import hmac
import os
import threading
import time
from urllib.parse import quote

import httpx

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "https://gsuetixzobooggeaubvb.supabase.co").rstrip("/")
# Clé publique (déjà livrée au navigateur par le module Événements) : elle n'ouvre rien sans jeton de membre.
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or "sb_publishable_DJJSW8NYvEfA7DUDoXSwkw_wTF1fnoK"
PHOTO_TTL = 7 * 24 * 3600   # lien de photo visible par les autres joueurs
CACHE_TTL = 300             # un même jeton n'est revérifié qu'au bout de 5 min


class AccountError(Exception):
    pass


class Accounts:
    def __init__(self, secret: bytes, client: httpx.Client | None = None):
        self.secret = secret
        self.client = client or httpx.Client(timeout=6)
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[float, dict]] = {}   # empreinte du jeton → (instant, compte)
        self.by_gid: dict[str, dict] = {}                # identifiant de joueur → compte (surnom, photo)

    def gid(self, user_id: str) -> str:
        return "acct-" + hmac.new(self.secret, f"account:{user_id}".encode(), hashlib.sha256).hexdigest()[:40]

    def _get(self, method: str, path: str, token: str, **kw) -> httpx.Response:
        try:
            return self.client.request(method, SUPABASE_URL + path, headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}, **kw)
        except httpx.HTTPError as e:
            raise AccountError("Le service des comptes ne répond pas. Réessaie dans un instant.") from e

    def link(self, token: str) -> dict:
        """Jeton de session Supabase → compte vérifié : identifiant de joueur, surnom, lien de photo."""
        key = hashlib.sha256(token.encode()).hexdigest()
        now = time.time()
        with self.lock:
            hit = self.cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        r = self._get("GET", "/auth/v1/user", token)
        if r.status_code != 200 or not r.json().get("id"):
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        uid = r.json()["id"]
        r = self._get("GET", f"/rest/v1/rpc/get_member_directory?id=eq.{uid}&select=display_name,avatar_url,status", token)
        rows = r.json() if r.status_code == 200 else []
        profile = rows[0] if isinstance(rows, list) and rows else {}
        if profile.get("status") == "banned":
            raise AccountError("Ce compte n'a plus accès à Party.")
        photo = None
        if profile.get("avatar_url"):
            s = self._get("POST", f"/storage/v1/object/sign/profile-photos/{quote(profile['avatar_url'])}", token, json={"expiresIn": PHOTO_TTL})
            signed = s.json().get("signedURL") if s.status_code == 200 else None
            if signed:
                photo = SUPABASE_URL + "/storage/v1" + signed
        account = {"guest_id": self.gid(uid), "name": " ".join((profile.get("display_name") or "").split())[:30], "photo": photo}
        with self.lock:
            self.cache = {k: v for k, v in self.cache.items() if now - v[0] < CACHE_TTL}
            self.cache[key] = (now, account)
            self.by_gid[account["guest_id"]] = account
        return account

    def photo(self, gid: str) -> str | None:
        return (self.by_gid.get(gid) or {}).get("photo")
