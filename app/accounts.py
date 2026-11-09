"""Comptes Party (Supabase) reliés aux jeux : le serveur vérifie lui-même la connexion auprès de Supabase,
puis donne au compte un identifiant de joueur stable et secret, le même sur tous ses appareils."""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from datetime import datetime
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
# Un de ces droits ouvre Réglages › Administration du groupe (comme ADMIN_PERMS du module web).
GROUP_ADMIN_PERMS = {"events.approve", "members.approve", "members.roles", "members.ban", "members.view_identity",
                     "roles.manage", "taxonomy.manage", "group.settings", "announcements.publish",
                     "moderation.reports"}  # Administration › Signalements (modération commune)
PROFILE_FIELDS = "id,display_name,first_name,last_name,phone,avatar_url,role,status"
# Membre VIP : droit events.view (private.is_member). Sans lui, private.may_receive_push refuse toujours les types de
# ces réglages (notification_prefs) : l'écran les cache au lieu d'afficher des interrupteurs qui ne servent jamais
# (campagne 2). À tenir à jour avec may_receive_push.
MEMBER_PERM = "events.view"
NON_MEMBER_HIDDEN_PREFS = ("chat", "new_event", "poll_new", "poll_nudge", "proposal_result", "proposals", "rsvp_mine",
                           "rsvp_set", "ticket_issued", "ticket_pay_confirmed", "ticket_pay_declared")


class AccountError(Exception):
    pass


RETRY_LATER = "Le service des comptes ne répond pas. Réessaie dans un instant."


class ServiceUnavailable(AccountError):
    """Panne passagère de la base (réseau, 5xx, 429) : ce n'est PAS un refus. Réponse 503 « Réessaie dans un
    instant » (account_call) au lieu de « pas activé pour ton compte » ou « connexion expirée »."""

    def __init__(self, message: str = RETRY_LATER):
        super().__init__(message)


def transient(status: int) -> bool:
    """Réponse de la base qui dit « plus tard » (surcharge, délai dépassé), pas « non »."""
    return status >= 500 or status == 429


class TermsRequired(AccountError):
    """La base refuse la publication : CGU de Party pas encore acceptées alors que l'admin les exige
    (private.require_terms, réglage terms_enforced). Réponse 403 {"code": "terms_required"} : l'app ouvre la feuille
    des CGU puis relance l'action."""
    code = "terms_required"


# Refus de la base précédés d'une clé (« content_refused: Événement non enregistré… ») : la phrase est pour la personne.
DB_REFUSAL = re.compile(r"^(forbidden|blocked|content_refused|terms_required|terms_version|rate_limited|not_found|"
                        r"profile_incomplete|self|reason|days): (.+)$", re.DOTALL)


def db_refusal(r: httpx.Response, fallback: str) -> AccountError:
    """Réponse d'erreur de PostgREST → l'erreur à lever : TermsRequired pour terms_required, sinon la phrase de la base
    (refus de contenu, blocage…), ou le message général `fallback` (panne, erreur sans phrase lisible)."""
    try:
        body = r.json() if r.status_code < 500 else None
    except ValueError:  # réponse vide ou pas du JSON
        body = None
    message = str(body.get("message", "")) if isinstance(body, dict) else ""
    found = DB_REFUSAL.match(message.strip())
    if not found:
        return AccountError(fallback)
    key, text = found.group(1), found.group(2).strip()
    text = text[:1].upper() + text[1:]
    return TermsRequired(text) if key == "terms_required" else AccountError(text)


def pause_end(value) -> float:
    """Date de fin d'une pause (texte ISO de Supabase) → instant Unix ; 0 sans pause ou si illisible."""
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


class Accounts:
    def __init__(self, secret: bytes, client: httpx.Client | None = None):
        self.secret = secret
        self.client = client or httpx.Client(timeout=6)
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[float, str]] = {}    # empreinte du jeton → (instant, identifiant Supabase vérifié)
        self.by_gid: dict[str, dict] = {}                # identifiant de joueur → compte (surnom, photo)
        self.uid_by_gid: dict[str, str] = {}             # identifiant de joueur → compte Supabase (fiche profil des jeux)
        self.pauses: dict[str, float] = {}               # identifiant de joueur → fin de la pause des notifications (lune)

    def gid(self, user_id: str) -> str:
        return "acct-" + hmac.new(self.secret, f"account:{user_id}".encode(), hashlib.sha256).hexdigest()[:40]

    def _get(self, method: str, path: str, token: str, headers: dict | None = None, **kw) -> httpx.Response:
        auth = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}
        try:
            return self.client.request(method, SUPABASE_URL + path, headers={**auth, **(headers or {})}, **kw)
        except httpx.HTTPError as e:
            raise ServiceUnavailable() from e

    def _uid(self, token: str) -> str:
        """Identifiant Supabase du jeton ; seule cette vérification est gardée 5 min."""
        key = hashlib.sha256(token.encode()).hexdigest()
        now = time.time()
        with self.lock:
            hit = self.cache.get(key)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        r = self._get("GET", "/auth/v1/user", token)
        if transient(r.status_code):
            raise ServiceUnavailable()
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

    def _perms(self, token: str) -> set[str]:
        self._uid(token)
        r = self._get("POST", "/rest/v1/rpc/my_permissions", token, json={})
        if transient(r.status_code):
            # Hoquet de la base : surtout pas « aucun droit » (l'admin lisait « IA pas activée pour ton compte »).
            raise ServiceUnavailable()
        if r.status_code != 200:
            return set()
        try:
            perms = r.json()
        except ValueError:
            raise ServiceUnavailable() from None
        return set(perms) if isinstance(perms, list) else set()

    def is_party_admin(self, token: str) -> bool:
        """Droits « Ouvrir la page admin » et « Réglages du site » (root et admins) : mêmes pouvoirs que le code PIN."""
        return {"party.admin", "party.settings"} <= self._perms(token)

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
        beta = self.beta(token)
        perms = self._perms(token)
        account = {"guest_id": self.gid(uid), "name": " ".join((profile.get("display_name") or "").split())[:30], "photo": photo,
                   "beta": beta, "admin": {"party.admin", "party.settings"} <= perms,
                   "group_admin": bool(perms & GROUP_ADMIN_PERMS),
                   # « Ton avis » : Guest+ et au-dessus (droit réglable dans Rôles et droits).
                   "feedback": "feedback.write" in perms}
        with self.lock:
            self.by_gid[account["guest_id"]] = account
            self.uid_by_gid[account["guest_id"]] = uid
        # La lune mise depuis le web (module Événements) : Party l'apprend ici (la page se relie après chaque choix).
        n = self._get("GET", f"/rest/v1/notification_prefs?user_id=eq.{uid}&select=muted_until", token)
        rows = n.json() if n.status_code == 200 else []
        if isinstance(rows, list) and rows:
            self._remember_pause(uid, rows[0])
        return account

    def _remember_pause(self, uid: str, prefs: dict):
        """Pause de toutes les notifications (Réglages › lune) : les notifications de Party (titre qui passe, jeux,
        réponse à un avis, et celles de l'hôte pour un admin) arrivent alors sans son. Seule une date future compte."""
        until = pause_end(prefs.get("muted_until"))
        with self.lock:
            if until > time.time():
                self.pauses[self.gid(uid)] = until
            else:
                self.pauses.pop(self.gid(uid), None)

    def paused(self, guest_id: str) -> bool:
        with self.lock:
            return self.pauses.get(guest_id, 0) > time.time()

    def admin_paused(self) -> bool:
        """Lune d'un compte admin de la soirée : les notifications de l'hôte arrivent aussi en silence."""
        now = time.time()
        with self.lock:
            return any(self.pauses.get(g, 0) > now for g, a in self.by_gid.items() if a.get("admin"))

    def set_notification_pause(self, token: str, what: str, span: str) -> dict:
        """what : 'all' (lune), 'chats' (Discussions des groupes) ou 'event_chats' (discussions des événements) ;
        span : '30m', '1h', '2h', 'morning' (8 h, Zurich) ou 'off'.
        L'heure de fin est calculée par la base (fonction set_notification_pause)."""
        self._uid(token)
        r = self._get("POST", "/rest/v1/rpc/set_notification_pause", token, json={"what": what, "span": span})
        if r.status_code != 200:
            raise AccountError("La pause n'a pas été enregistrée. Réessaie dans un instant.")
        return self.notification_prefs(token)

    def beta(self, token: str) -> bool:
        """Bêta-testeur : en production, Événements et Discussions lui sont réservés."""
        b = self._get("POST", "/rest/v1/rpc/is_beta_tester", token, json={})
        return b.status_code == 200 and b.json() is True

    def notification_prefs(self, token: str) -> dict:
        """Préférences de notification du membre (table notification_prefs, protégée par RLS) et s'il valide
        les propositions d'événements (droit events.approve : réglage « Proposition à valider »)."""
        uid = self._uid(token)
        r = self._get("GET", f"/rest/v1/notification_prefs?user_id=eq.{uid}&select=*", token)
        rows = r.json() if r.status_code == 200 else []
        if not isinstance(rows, list) or not rows:
            raise AccountError("Préférences introuvables. Ouvre une fois les Événements, puis réessaie.")
        self._remember_pause(uid, rows[0])
        perms = self._perms(token)   # hoquet de la base : « Réessaie », jamais un écran sans droits
        member = MEMBER_PERM in perms
        # moderator : droit « Modérer les signalements » (réglage « Nouveau signalement ») ; hidden : réglages qui ne
        # servent jamais à ce compte (Membre, Guest), cachés par l'app et le web.
        return {"prefs": rows[0], "approver": "events.approve" in perms, "moderator": "moderation.reports" in perms,
                "member": member, "hidden": [] if member else sorted(NON_MEMBER_HIDDEN_PREFS)}

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

    def groups(self, token: str) -> dict:
        """Mes groupes (créés ou dont je fais partie), leurs membres, et les personnes que je peux y ajouter
        (annuaire : ce que mes droits me laissent voir). Lu avec la session du membre (règles de la base).
        others : les autres groupes, que la base ne montre qu'aux Admins du site (rang Admin et au-dessus, pas les
        Co-admins ; migration 20261104093000) ; vide pour tous les autres comptes. Un Admin les compose (mine)."""
        uid = self._uid(token)
        r = self._get("GET", "/rest/v1/member_groups?select=id,name,created_by,system_key,member_group_members(user_id)&order=name", token)
        rows = r.json() if r.status_code == 200 else None
        d = self._get("GET", "/rest/v1/rpc/get_member_directory?select=id,display_name,status", token)
        directory = d.json() if d.status_code == 200 else []
        if not isinstance(rows, list) or not isinstance(directory, list):
            raise AccountError("Tes groupes n'ont pas pu être lus. Réessaie dans un instant.")
        names = {p["id"]: p.get("display_name") or "Sans surnom" for p in directory}
        groups, others = [], []
        for g in rows:
            members = [m["user_id"] for m in g.get("member_group_members") or []]
            system = g.get("system_key") is not None
            outside = g.get("created_by") != uid and uid not in members
            (others if outside else groups).append({
                "id": g["id"], "name": g["name"], "system": system,
                "mine": not system and (outside or g.get("created_by") == uid),
                "inside": uid in members,  # j'en fais partie : je peux y montrer mon numéro
                "members": [{"id": m, "name": names.get(m, "Membre du groupe")} for m in members]})
        people = [{"id": p["id"], "name": names[p["id"]]} for p in directory if p["id"] != uid and p.get("status") == "active"]
        return {"groups": groups, "others": others, "people": sorted(people, key=lambda p: p["name"].lower())}

    def create_group(self, token: str, name: str, join: bool = False) -> dict:
        """Nouveau groupe (Réglages › Groupes, ou Discussions avec join : son créateur en fait partie d'office, pour
        écrire tout de suite dans sa discussion). « created » = son identifiant, pour l'ouvrir."""
        uid = self._uid(token)
        r = self._get("POST", "/rest/v1/member_groups", token, json={"name": name, "created_by": uid},
                      headers={"Prefer": "return=representation"})
        if r.status_code not in (200, 201, 204):
            raise db_refusal(r, "Le groupe n'a pas été créé. Réessaie.")
        rows = r.json() if r.content else []
        created = rows[0].get("id") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
        if join and created:
            m = self._get("POST", "/rest/v1/member_group_members", token, json={"group_id": created, "user_id": uid},
                          headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
            if m.status_code not in (200, 201, 204, 409):
                raise AccountError("Le groupe est créé, mais tu n'as pas pu y être ajouté. Ajoute-toi dans Réglages › Groupes.")
        return {**self.groups(token), "created": created}

    def set_group_member(self, token: str, group_id: str, user_id: str, on: bool) -> dict:
        self._uid(token)
        if on:
            r = self._get("POST", "/rest/v1/member_group_members", token, json={"group_id": group_id, "user_id": user_id},
                          headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        else:
            r = self._get("DELETE", f"/rest/v1/member_group_members?group_id=eq.{group_id}&user_id=eq.{user_id}", token)
        if r.status_code not in (200, 201, 204, 409):
            raise AccountError("La modification n'a pas été enregistrée. Réessaie.")
        return self.groups(token)

    def delete_group(self, token: str, group_id: str) -> dict:
        self._uid(token)
        r = self._get("DELETE", f"/rest/v1/member_groups?id=eq.{group_id}", token)
        if r.status_code not in (200, 204):
            raise AccountError("Le groupe n'a pas été supprimé. Réessaie.")
        return self.groups(token)

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
        # La table profiles ne laisse lire que les colonnes publiques ; l'annuaire donne au membre toute sa propre ligne.
        r = self._get("GET", f"/rest/v1/rpc/get_member_directory?id=eq.{uid}&select={PROFILE_FIELDS}", token)
        rows = r.json() if r.status_code == 200 else []
        if not isinstance(rows, list) or not rows:
            raise AccountError("Profil introuvable. Reconnecte-toi.")
        return {**rows[0], "photo": self._signed_photo(rows[0].get("avatar_url"), token),
                "role_label": self._role_label(rows[0].get("role"), token)}

    def _role_label(self, role: str | None, token: str) -> str | None:
        """Nom du rôle (table public.roles : rôles personnalisés) ; None si la base ne l'a pas encore."""
        if not role:
            return None
        r = self._get("GET", f"/rest/v1/roles?select=label&key=eq.{quote(role)}", token)
        rows = r.json() if r.status_code == 200 else None
        return rows[0].get("label") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None

    def update_profile(self, token: str, fields: dict, photo: bytes | None) -> dict:
        """Prénom, nom, surnom et, au besoin, nouvelle photo (JPEG déjà recadré par l'app) : la photo va dans le
        dossier du membre, puis le profil la désigne ; l'ancienne est effacée. Refusé : la photo envoyée est retirée.
        Les règles (prénom, nom, surnom obligatoires, photo facultative, surnom ≤ 40) sont aussi vérifiées par la base (trigger guard_profile)."""
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
            refusal = db_refusal(r, "")
            raise refusal if str(refusal) else AccountError(self._db_message(r))
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

    # MARK: Invitations aux groupes (lien, surnom ou numéro)

    def _rpc_json(self, token: str, name: str, args: dict, fallback: str):
        self._uid(token)
        r = self._get("POST", f"/rest/v1/rpc/{name}", token, json=args)
        if r.status_code == 204:  # fonction sans résultat (annuler un lien…)
            return None
        if r.status_code != 200:
            refusal = db_refusal(r, "")
            if str(refusal):
                raise refusal
            try:
                message = str(r.json().get("message", "")) if r.status_code < 500 else ""
            except ValueError:
                message = ""
            # « forbidden: … », « profile_incomplete: … » : la partie lisible ; sinon le message tel quel.
            raise AccountError(message.split(": ", 1)[-1] if message else fallback)
        return r.json()

    def group_invitations(self, token: str) -> list:
        return self._rpc_json(token, "my_group_invitations", {}, "Tes invitations n'ont pas pu être lues.")

    def answer_group_invitation(self, token: str, invitation: str, accept: bool) -> list:
        return self._rpc_json(token, "answer_group_invitation", {"inv": invitation, "accept": accept},
                              "Ta réponse n'a pas été enregistrée. Réessaie.")

    def group_invite_link(self, token: str, group_id: str, renew: bool) -> str:
        return self._rpc_json(token, "group_invite_link", {"grp": group_id, "renew": renew}, "Le lien n'a pas pu être créé.")

    def group_single_link(self, token: str, group_id: str) -> str:
        """Lien unique (une personne, une fois, 7 jours) : le choix par défaut pour inviter dans un groupe."""
        return self._rpc_json(token, "create_invite_link", {"k": "group", "target": group_id}, "Le lien n'a pas pu être créé.")

    def group_links(self, token: str, group_id: str) -> list:
        """Liens uniques créés pour ce groupe et leur état (en attente, utilisé par…, expiré, annulé)."""
        return self._rpc_json(token, "my_invite_links", {"k": "group", "target": group_id}, "Les liens n'ont pas pu être lus.") or []

    def revoke_link(self, token: str, link: str) -> None:
        self._rpc_json(token, "revoke_invite_link", {"tok": link}, "Le lien n'a pas pu être annulé.")

    def invite_to_group(self, token: str, group_id: str, member: str | None, phone: str | None) -> dict:
        return self._rpc_json(token, "invite_to_group", {"grp": group_id, "member": member, "phone": phone},
                              "L'invitation n'a pas été envoyée. Réessaie.")

    # MARK: Fiche profil et confidentialité (nom public, numéro montré à ses groupes)

    def member_card(self, token: str, member: str | None = None, guest_id: str | None = None) -> dict:
        """Fiche d'un compte : par son identifiant Supabase, ou par l'identifiant de joueur d'un compte relié (jeux).
        Lue avec la session de la personne qui regarde : la base applique les choix de confidentialité."""
        self._uid(token)
        if guest_id:
            with self.lock:
                member = self.uid_by_gid.get(guest_id)
        if not member:
            raise AccountError("Ce joueur n'a pas de compte Party.")
        r = self._get("POST", "/rest/v1/rpc/member_card", token, json={"target": member})
        card = r.json() if r.status_code == 200 else None
        if not isinstance(card, dict):
            raise AccountError("Ce profil n'est pas disponible.")
        return {**card, "photo": self._signed_photo(card.get("avatar_url"), token)}

    def privacy(self, token: str) -> dict:
        self._uid(token)
        r = self._get("POST", "/rest/v1/rpc/my_privacy", token, json={})
        if r.status_code != 200 or not isinstance(r.json(), dict):
            raise AccountError("Tes choix de confidentialité n'ont pas pu être lus.")
        return r.json()

    def set_name_public(self, token: str, on: bool) -> dict:
        self._uid(token)
        r = self._get("POST", "/rest/v1/rpc/set_name_public", token, json={"visible": on})
        if r.status_code != 200:
            raise AccountError("Ton choix n'a pas été enregistré. Réessaie.")
        return r.json()

    def set_group_phone_share(self, token: str, group_id: str, on: bool) -> dict:
        self._uid(token)
        r = self._get("POST", "/rest/v1/rpc/set_group_phone_share", token, json={"grp": group_id, "visible": on})
        if r.status_code != 200:
            raise AccountError(self._db_message(r) if r.status_code < 500 else "Ton choix n'a pas été enregistré. Réessaie.")
        return r.json()

    def uid_of(self, gid: str) -> str | None:
        """Compte Supabase d'un identifiant de joueur relié depuis le démarrage du serveur (None sinon)."""
        with self.lock:
            return self.uid_by_gid.get(gid)

    def is_linked(self, gid: str) -> bool:
        """Ce joueur a relié un compte vérifié depuis le démarrage du serveur (jeux réservés aux comptes)."""
        with self.lock:
            return gid in self.by_gid

    def photo(self, gid: str) -> str | None:
        return (self.by_gid.get(gid) or {}).get("photo")
