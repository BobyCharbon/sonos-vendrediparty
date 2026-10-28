"""Comptes Party (Supabase) reliés aux jeux : le serveur vérifie lui-même la connexion auprès de Supabase,
puis donne au compte un identifiant de joueur stable et secret, le même sur tous ses appareils."""
import hashlib
import hmac
import os
import secrets
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
PROFILE_PHOTOS = "profile-photos"
PROFILE_FIELDS = "id,display_name,first_name,last_name,phone,avatar_url,role,status"


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

    def register_push(self, token: str, device: str, on: bool):
        """App iOS native : cet iPhone reçoit (on) ou ne reçoit plus les notifications des événements du compte.
        Lié à la session du membre (une déconnexion le retire) ; envoi par la fonction send-push (APNs)."""
        self._uid(token)
        name = "apns:" + device
        r = (self._get("POST", "/rest/v1/rpc/register_device_push_token", token, json={"device_token": name, "device_platform": "ios"})
             if on else self._get("POST", "/rest/v1/rpc/unregister_device_push_token", token, json={"device_token": name}))
        if r.status_code not in (200, 204):
            raise AccountError("Cet iPhone n'a pas pu être enregistré pour les événements. Réessaie dans un instant.")

    def subscriptions(self, token: str) -> dict:
        """Catégories et tags actifs, et ceux que le membre suit (alertes « Si abonné », filtre de la liste)."""
        uid = self._uid(token)
        reads = {
            "categories": "/rest/v1/categories?select=id,name,color,icon&archived=eq.false&order=sort",
            "tags": "/rest/v1/tags?select=id,name,color&archived=eq.false&order=name",
            "category_ids": f"/rest/v1/category_subscriptions?select=category_id&user_id=eq.{uid}",
            "tag_ids": f"/rest/v1/tag_subscriptions?select=tag_id&user_id=eq.{uid}",
        }
        out = {}
        for key, path in reads.items():
            r = self._get("GET", path, token)
            rows = r.json() if r.status_code == 200 else None
            if not isinstance(rows, list):
                raise AccountError("Tes abonnements n'ont pas pu être lus. Réessaie dans un instant.")
            out[key] = [row[key.removesuffix("s")] for row in rows] if key.endswith("_ids") else rows
        return out

    def set_subscription(self, token: str, kind: str, topic: str, on: bool) -> dict:
        """Suivre (on) ou ne plus suivre une catégorie ou un tag ; kind : category | tag (vérifié par l'appelant)."""
        uid = self._uid(token)
        table, col = f"/rest/v1/{kind}_subscriptions", f"{kind}_id"
        if on:
            r = self._get("POST", table, token, json={"user_id": uid, col: topic},
                          headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        else:
            r = self._get("DELETE", f"{table}?user_id=eq.{uid}&{col}=eq.{topic}", token)
        if r.status_code not in (200, 201, 204, 409):
            raise AccountError("Ton choix n'a pas été enregistré. Vérifie ta connexion et réessaie.")
        return self.subscriptions(token)

    def _signed_photo(self, path: str | None, token: str) -> str | None:
        if not path:
            return None
        s = self._get("POST", f"/storage/v1/object/sign/{PROFILE_PHOTOS}/{quote(path)}", token, json={"expiresIn": PHOTO_TTL})
        signed = s.json().get("signedURL") if s.status_code == 200 else None
        return SUPABASE_URL + "/storage/v1" + signed if signed else None

    def profile(self, token: str) -> dict:
        """Mon profil (Réglages natifs) : la ligne profiles du membre, lue avec sa session, et un lien vers sa photo."""
        uid = self._uid(token)
        r = self._get("GET", f"/rest/v1/profiles?id=eq.{uid}&select={PROFILE_FIELDS}", token)
        rows = r.json() if r.status_code == 200 else []
        if not isinstance(rows, list) or not rows:
            raise AccountError("Profil introuvable. Reconnecte-toi.")
        return {**rows[0], "photo": self._signed_photo(rows[0].get("avatar_url"), token)}

    def update_profile(self, token: str, fields: dict, photo: bytes | None) -> dict:
        """Prénom, nom, surnom et, au besoin, nouvelle photo (JPEG déjà recadré par l'app) : la photo va dans le
        dossier du membre, puis le profil la désigne ; l'ancienne est effacée. Refusé : la photo envoyée est retirée.
        Les règles (tout obligatoire, surnom ≤ 40) sont aussi vérifiées par la base (trigger guard_profile)."""
        uid = self._uid(token)
        before = self.profile(token)
        uploaded = None
        if photo:
            uploaded = f"{uid}/{int(time.time() * 1000)}-{secrets.token_hex(4)}.jpg"
            up = self._get("POST", f"/storage/v1/object/{PROFILE_PHOTOS}/{uploaded}", token, content=photo,
                           headers={"Content-Type": "image/jpeg", "x-upsert": "false"})
            if up.status_code not in (200, 201):
                raise AccountError("La photo n'a pas pu être envoyée. Vérifie ta connexion puis réessaie.")
        patch = {**fields, **({"avatar_url": uploaded} if uploaded else {})}
        r = self._get("PATCH", f"/rest/v1/profiles?id=eq.{uid}", token, json=patch, headers={"Prefer": "return=minimal"})
        old = before.get("avatar_url")
        if r.status_code not in (200, 204):
            if uploaded:
                self._remove_photos([uploaded], token)
            raise AccountError(self._db_message(r))
        if uploaded and old:
            self._remove_photos([old], token)
        return self.profile(token)

    def _remove_photos(self, paths: list[str], token: str):
        try:
            self._get("DELETE", f"/storage/v1/object/{PROFILE_PHOTOS}", token, json={"prefixes": paths})
        except AccountError:
            pass  # photo orpheline : sans conséquence, le profil ne la désigne pas

    @staticmethod
    def _db_message(r: httpx.Response) -> str:
        """« profile_incomplete: nom, prénom… » (exception de la base) → la partie lisible ; sinon un message général."""
        try:
            message = str(r.json().get("message", ""))
        except ValueError:
            message = ""
        _, _, readable = message.partition(": ")
        return (readable[:1].upper() + readable[1:]) if readable else "Tes informations n'ont pas pu être enregistrées. Réessaie."

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
