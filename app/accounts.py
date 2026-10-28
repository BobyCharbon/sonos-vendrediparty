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
EVENT_LOOKBACK = 12 * 3600  # un événement commencé depuis moins de 12 h peut encore être lié à la soirée
EVENT_CHOICES = 8


class AccountError(Exception):
    pass


class Accounts:
    def __init__(self, secret: bytes, client: httpx.Client | None = None):
        self.secret = secret
        self.client = client or httpx.Client(timeout=6)
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[float, str]] = {}    # empreinte du jeton → (instant, identifiant Supabase vérifié)
        self.by_gid: dict[str, dict] = {}                # identifiant de joueur → compte (surnom, photo)

    def gid(self, user_id: str) -> str:
        return "acct-" + hmac.new(self.secret, f"account:{user_id}".encode(), hashlib.sha256).hexdigest()[:40]

    def _get(self, method: str, path: str, token: str, headers: dict | None = None, **kw) -> httpx.Response:
        auth = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}
        try:
            return self.client.request(method, SUPABASE_URL + path, headers={**auth, **(headers or {})}, **kw)
        except httpx.HTTPError as e:
            raise AccountError("Le service des comptes ne répond pas. Réessaie dans un instant.") from e

    def _uid(self, token: str) -> str:
        """Identifiant Supabase du jeton ; seule cette vérification est gardée 5 min."""
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
        with self.lock:
            self.cache = {k: v for k, v in self.cache.items() if now - v[0] < CACHE_TTL}
            self.cache[key] = (now, uid)
        return uid

    def verified_gid(self, token: str) -> str:
        """Identifiant de joueur du compte, après la seule vérification du jeton (gardée 5 min) : pour lire ses propres données."""
        return self.gid(self._uid(token))

    def is_party_admin(self, token: str) -> bool:
        """Droits « Ouvrir la page admin » et « Réglages du site » (root et admins) : mêmes pouvoirs que le code PIN."""
        self._uid(token)
        r = self._get("POST", "/rest/v1/rpc/my_permissions", token, json={})
        perms = r.json() if r.status_code == 200 else []
        return isinstance(perms, list) and {"party.admin", "party.settings"} <= set(perms)

    def link(self, token: str) -> dict:
        """Jeton de session Supabase → compte vérifié : identifiant de joueur, surnom, lien de photo.
        Le surnom et la photo sont relus à chaque liaison, pour qu'un changement fait dans le profil
        arrive tout de suite dans les jeux."""
        uid = self._uid(token)
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
        b = self._get("POST", "/rest/v1/rpc/is_beta_tester", token, json={})
        beta = b.status_code == 200 and b.json() is True  # Événements en production : réservés aux bêta-testeurs
        account = {"guest_id": self.gid(uid), "name": " ".join((profile.get("display_name") or "").split())[:30], "photo": photo,
                   "beta": beta, "admin": self.is_party_admin(token)}
        with self.lock:
            self.by_gid[account["guest_id"]] = account
        return account

    def notification_prefs(self, token: str) -> dict:
        """Préférences de notification du membre (table notification_prefs, protégée par RLS) et s'il valide
        les propositions d'événements (droit events.approve : réglage « Proposition à valider »)."""
        uid = self._uid(token)
        r = self._get("GET", f"/rest/v1/notification_prefs?user_id=eq.{uid}&select=*", token)
        rows = r.json() if r.status_code == 200 else []
        if not isinstance(rows, list) or not rows:
            raise AccountError("Préférences introuvables. Ouvre une fois les Événements, puis réessaie.")
        p = self._get("POST", "/rest/v1/rpc/my_permissions", token, json={})
        perms = p.json() if p.status_code == 200 else []
        return {"prefs": rows[0], "approver": isinstance(perms, list) and "events.approve" in perms}

    def update_notification_prefs(self, token: str, patch: dict) -> dict:
        uid = self._uid(token)
        r = self._get("PATCH", f"/rest/v1/notification_prefs?user_id=eq.{uid}", token, json=patch,
                      headers={"Prefer": "return=minimal"})
        if r.status_code not in (200, 204):
            raise AccountError("Tes préférences n'ont pas été enregistrées. Réessaie dans un instant.")
        return self.notification_prefs(token)

    def refresh(self, refresh_token: str) -> dict:
        """Nouvelle session Supabase à partir du jeton de rafraîchissement (même format que celui gardé par le module)."""
        try:
            r = self.client.post(SUPABASE_URL + "/auth/v1/token", params={"grant_type": "refresh_token"},
                                 headers={"apikey": SUPABASE_ANON_KEY}, json={"refresh_token": refresh_token})
        except httpx.HTTPError as e:
            raise AccountError("Le service des comptes ne répond pas. Réessaie dans un instant.") from e
        session = r.json() if r.status_code == 200 else {}
        if not session.get("access_token"):
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        return session

    def attending(self, token: str, event_id: str) -> tuple[str, bool]:
        """(identifiant du compte, noté « Présent » à cet événement et pas en liste d'attente), lu avec son propre jeton."""
        uid = self._uid(token)
        r = self._get("GET", f"/rest/v1/rsvps?select=status,waitlisted&event_id=eq.{event_id}&user_id=eq.{uid}", token)
        rows = r.json() if r.status_code == 200 else []
        row = rows[0] if isinstance(rows, list) and rows else {}
        if row.get("status") != "yes" or row.get("waitlisted"):
            return uid, False
        p = self._get("GET", f"/rest/v1/rpc/get_member_directory?id=eq.{uid}&select=status", token)
        profile = p.json() if p.status_code == 200 else []
        return uid, isinstance(profile, list) and bool(profile) and profile[0].get("status") == "active"

    def upcoming_events(self, token: str) -> list[dict]:
        """Événements publiés à date fixe, du jour (commencés il y a moins de 12 h) et à venir, vus par ce compte."""
        self._uid(token)
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - EVENT_LOOKBACK))
        r = self._get("GET", "/rest/v1/events?select=id,title,starts_at&status=eq.published&date_mode=eq.fixed"
                      f"&starts_at=gte.{since}&order=starts_at&limit={EVENT_CHOICES}", token)
        rows = r.json() if r.status_code == 200 else []
        if not isinstance(rows, list):
            return []
        return [{"id": e["id"], "title": e["title"], "starts_at": e["starts_at"]} for e in rows]

    def is_linked(self, gid: str) -> bool:
        """Ce joueur a relié un compte vérifié depuis le démarrage du serveur (jeux réservés aux comptes)."""
        with self.lock:
            return gid in self.by_gid

    def photo(self, gid: str) -> str | None:
        return (self.by_gid.get(gid) or {}).get("photo")
