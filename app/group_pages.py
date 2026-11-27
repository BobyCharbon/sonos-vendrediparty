"""Groupes en natif dans l'app iPhone (demande de l'admin du 18.11 : « Je veux tout en natif ») : la liste, la page, les
réglages, la création et la photo d'un groupe, comme les pages web du module Événements (web/events/src/app/groups.tsx,
group/[id]/index.tsx, settings.tsx, group/new.tsx), par le relais POST /api/account/chats/rpc.

Le web écrit directement dans les tables (member_groups, member_group_members) avec la session du membre ; ici le
serveur fait EXACTEMENT les mêmes lectures et écritures, avec la même session : la base décide de tout (règles RLS,
gardes group_look_guard / group_photo_guard, filtre des noms, CGU, Membres Vendredi Party jamais renommé, jamais quitté,
jamais de photo). Une réponse vide d'une écriture (règle RLS qui ne laisse rien passer) devient « forbidden »."""
import re
import time
import unicodedata
import uuid
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from . import store_app
from .accounts import AccountError
from .group_admin import OK, GroupAdmin

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# Mêmes listes fermées que la base (member_groups_emoji_check / _color_check) et web/events/src/lib/groups.ts.
EMOJIS = ("👯", "🎉", "🪩", "⚽", "🏡", "🎲", "🥾", "🎸", "🍕", "🍻", "🍷", "🎂", "🌴", "🎮", "🎤", "🏀")
COLORS = ("pink", "coral", "mint", "sky", "lavender", "lemon")
NAME_MAX = 60
PHOTO_MAX = 5 * 1024 * 1024        # même limite que le compartiment group-photos
IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG")
EVENT_CARDS_MAX = 100              # chat_event_cards : 100 identifiants au plus
POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="groups")
GONE = "not_found: Ce groupe n'existe plus, ou tu n'en fais pas partie."


class Refused(Exception):
    """Refus à rendre tel quel par le relais : (statut HTTP, corps de la base « code: phrase »)."""

    def __init__(self, status: int, body: Any):
        super().__init__(status)
        self.status = status
        self.body = body


def refused(code: str, text: str, status: int = 403) -> Refused:
    return Refused(status, {"message": f"{code}: {text}"})


def group_id(args: dict, key: str = "grp") -> str:
    value = str(args.get(key) or "")
    if not UUID_RE.match(value):
        raise refused("invalid", "Groupe inconnu.", 400)
    return value.lower()


def missing_function(e: "Refused") -> bool:
    """Fonction absente de la base (migration du 23.11 pas encore appliquée) : PostgREST PGRST202 (404)."""
    return e.status == 404 or (isinstance(e.body, dict) and e.body.get("code") == "PGRST202")


def clean_name(value: Any) -> str:
    """« Soirées   du  vendredi » → « Soirées du vendredi » (60 caractères au plus, comme l'écran web)."""
    return " ".join(str(value or "").split())[:NAME_MAX]


def member_order(members: list[dict], creator: str | None) -> list[dict]:
    """Créateur d'abord, puis par surnom (comme la page web)."""
    return sorted(members, key=lambda m: (m["id"] != creator, (m.get("name") or "").casefold()))


class GroupPages:
    def __init__(self, admin: GroupAdmin, invite_url: Callable[[str], str] | None = None):
        self.admin = admin
        self.accounts = admin.accounts
        self.invite_url = invite_url or (lambda token: token)

    # ── Accès à la base (session du membre) ──

    def _req(self, method: str, path: str, token: str, **kw) -> Any:
        try:
            r = self.accounts._get(method, path, token, **kw)
        except AccountError:
            raise Refused(503, None) from None
        try:
            body = r.json() if r.content else None
        except ValueError:
            body = None
        if r.status_code not in OK:
            raise Refused(r.status_code, body)
        return body

    def _rpc(self, token: str, name: str, args: dict) -> Any:
        return self._req("POST", f"/rest/v1/rpc/{name}", token, json=args)

    def _rows(self, path: str, token: str) -> list:
        rows = self._req("GET", path, token)
        return rows if isinstance(rows, list) else []

    def _quiet(self, job: Callable[[], Any], default: Any) -> Any:
        """Lecture accessoire (droits, confidentialité) : sa panne n'empêche jamais la page de s'ouvrir."""
        try:
            return job()
        except (Refused, AccountError):
            return default

    def call(self, fn: str, args: dict, token: str, store: bool = False) -> Any:
        if fn == "group_page":
            return self.page(token, args, store)
        return getattr(self, LOCAL[fn])(token, args)

    # ── Lectures ──

    def home(self, token: str, args: dict) -> dict:
        """Réglages › Groupes : mes groupes (my_groups_overview), invitations reçues, et pour les Admins du site les autres
        groupes (la base ne les montre qu'à eux ; jamais les groupes privés de « Nouveau message »)."""
        self.accounts._uid(token)
        jobs = {
            "groups": POOL.submit(self._rpc, token, "my_groups_overview", {}),
            "invitations": POOL.submit(self._quiet, lambda: self._rpc(token, "my_group_invitations", {}), []),
            "all": POOL.submit(self._quiet, lambda: self._rows(
                "/rest/v1/member_groups?select=id,name,emoji,color,photo_path,system_key,member_group_members(user_id)&order=name",
                token), []),
        }
        got = {k: f.result() for k, f in jobs.items()}
        groups = got["groups"] or []
        mine = {g.get("id") for g in groups}
        others = [{"id": g["id"], "name": g.get("name") or "", "emoji": g.get("emoji") or "👯", "color": g.get("color"),
                   "photo": None if g.get("system_key") else g.get("photo_path"), "system": g.get("system_key") is not None,
                   "members": len(g.get("member_group_members") or [])}
                  for g in got["all"] if g.get("id") not in mine]
        return {"groups": groups, "invitations": got["invitations"] or [], "others": others}

    def page(self, token: str, args: dict, store: bool = False) -> dict:
        """Page du groupe et ses réglages : le groupe, mes droits, ses membres, ses événements visibles (group_events puis
        chat_event_cards : seulement ceux que je peux voir), mon numéro montré ou non dans ce groupe."""
        grp = group_id(args)
        uid = self.accounts._uid(token)
        jobs = {
            "group": POOL.submit(self._rows, "/rest/v1/member_groups?select=id,name,emoji,color,photo_path,created_by,created_at,"
                                             "system_key,private_chat,events_need_approval,announce_mode,members_invite,"
                                             f"member_group_members(user_id)&id=eq.{grp}", token),
            "people": POOL.submit(self._quiet, lambda: self._rpc(token, "group_chat_people", {"grp": grp}), None),
            "overview": POOL.submit(self._quiet, lambda: self._rpc(token, "my_groups_overview", {}), []),
            "events": POOL.submit(self._quiet, lambda: self._rpc(token, "group_events", {"grp": grp}), []),
            "privacy": POOL.submit(self._quiet, lambda: self._rpc(token, "my_privacy", {}), {}),
            "access": POOL.submit(self._quiet, lambda: self.admin.access(token), {}),
        }
        got = {k: f.result() for k, f in jobs.items()}
        if not got["group"]:
            raise Refused(404, {"message": GONE})
        g = got["group"][0]
        system = g.get("system_key") is not None
        creator = g.get("created_by")
        ids = [m["user_id"] for m in g.get("member_group_members") or []]
        access = got["access"] or {}
        perms = set(access.get("perms") or [])
        member = uid in ids
        # Mêmes droits que les pages web : gérer = créateur ou Admin du site (jamais Membres Vendredi Party) ;
        # règles des événements = qui gère, ou Co-admin et plus pour Membres Vendredi Party (set_group_event_rules).
        overview = next((o for o in got["overview"] or [] if o.get("id") == grp), {})
        # Gérer (23.11) : créateur, co-admins du groupe, Admin du site → la base (my_groups_overview.manage) ; sinon comme avant.
        manage = not system and bool(overview.get("manage", creator == uid or bool(access.get("full"))))
        # Surnoms et photos (group_chat_people : un Guest ne lit pas le profil d'un admin) ; sinon la table profiles.
        people = {p["id"]: p for p in got["people"] or [] if p.get("id") in ids}
        missing = [i for i in ids if i not in people]
        if missing:
            rows = self._quiet(lambda: self._rows(
                f"/rest/v1/profiles?select=id,display_name,avatar_url&id=in.({','.join(missing)})", token), [])
            people.update({p["id"]: p for p in rows})
        members = member_order([{"id": i, "name": (people.get(i) or {}).get("display_name") or "Membre du groupe",
                                 "avatar_url": (people.get(i) or {}).get("avatar_url"), "creator": i == creator, "me": i == uid}
                                for i in ids], creator)
        listed = [e for e in got["events"] or [] if isinstance(e, dict) and e.get("id")][:EVENT_CARDS_MAX]
        cards = self._quiet(lambda: self._rpc(token, "chat_event_cards", {"ids": [e["id"] for e in listed]}), []) if listed else []
        by_id = {c["id"]: c for c in cards or [] if isinstance(c, dict) and c.get("id")}
        if store and by_id:
            by_id = self._store_cards(token, uid, by_id)
        upcoming = [by_id[e["id"]] for e in listed if e.get("upcoming") and e["id"] in by_id]
        past = [by_id[e["id"]] for e in listed if not e.get("upcoming") and e["id"] in by_id]
        creator_name = (people.get(creator) or {}).get("display_name") if creator else None
        return {
            "group": {"id": g["id"], "name": g.get("name") or "", "emoji": g.get("emoji") or "👯", "color": g.get("color"),
                      "photo": None if system else g.get("photo_path"), "system": system, "private": bool(g.get("private_chat")),
                      "created_by": creator, "created_by_name": creator_name, "created_at": g.get("created_at"),
                      "events_need_approval": bool(g.get("events_need_approval")), "announce_mode": g.get("announce_mode") or "request",
                      "members_invite": g.get("members_invite") is not False},
            "me": uid, "member": member, "manage": manage, "creator": creator == uid,
            # Inviter (« Tous les membres peuvent inviter », 22.11) : la base décide (my_groups_overview.invite).
            "can_invite": bool(overview.get("invite", manage)) and not system,
            # « Créer un événement pour le groupe » : son droit dans le groupe aussi (23.11, my_groups_overview.events).
            "can_create_event": member and "events.create" in perms and bool(overview.get("events", True)),
            "can_set_rules": manage or (system and bool(access.get("site_admin"))),
            "phone_shared": grp in set((got["privacy"] or {}).get("phone_groups") or []),
            "unread": int(overview.get("unread") or 0),
            "members": members, "upcoming": upcoming, "past": past,
        }

    def _store_cards(self, token: str, uid: str, by_id: dict) -> dict:
        """App App Store (refus Apple 1.4.3) : comme la liste du web (web/events/src/lib/storeEvents.ts), un événement
        PUBLIC « à boisson » (titre, description, lieu, mini-sondages, « qui amène quoi ») n'est montré qu'à ses invités,
        participants et organisateurs. Lecture impossible : on ne garde que les cartes sans boisson (jamais de fuite)."""
        ids = ",".join(by_id)
        rows = self._quiet(lambda: self._rows(
            "/rest/v1/events?select=id,visibility,title,description,location_name,location_address,created_by,"
            f"event_organizers(user_id),event_invites(user_id),event_groups(group_id),polls(question,poll_options(label)),bring_items(label)&id=in.({ids})", token), [])
        info = {r["id"]: r for r in rows if isinstance(r, dict) and r.get("id")}
        # Membres Vendredi Party (lisible par ses seuls membres) : ses événements comptent comme publics (contrôle Apple tour 7).
        vip = self._quiet(lambda: self._rows("/rest/v1/member_groups?select=id&system_key=eq.vip", token), [])
        vip_id = vip[0].get("id") if vip and isinstance(vip[0], dict) else None

        def hidden(card: dict) -> bool:
            e = info.get(card["id"])
            if card.get("mine") or (e and (e.get("created_by") == uid
                                           or any(o.get("user_id") == uid for o in (e.get("event_organizers") or []) + (e.get("event_invites") or [])))):
                return False
            if e and e.get("visibility") != "all" and not any(g.get("group_id") == vip_id for g in e.get("event_groups") or []):
                return False
            texts = [card.get("title"), card.get("place")]
            if e:
                texts += [e.get("title"), e.get("description"), e.get("location_name"), e.get("location_address")]
                texts += [t for p in e.get("polls") or [] for t in [p.get("question")] + [o.get("label") for o in p.get("poll_options") or []]]
                texts += [b.get("label") for b in e.get("bring_items") or []]
            # Texte ramené en NFC : « apéro » en lettres décomposées passait le filtre (contrôle Apple tour 7).
            return any(store_app.drinky(unicodedata.normalize("NFC", t)) for t in texts if t)

        return {k: c for k, c in by_id.items() if not hidden(c)}

    # ── Écritures (mêmes requêtes que le web, session du membre) ──

    def _look(self, args: dict) -> dict:
        name = clean_name(args.get("name"))
        if not name:
            raise refused("invalid", "Donne un nom au groupe.", 400)
        emoji = args.get("emoji") if args.get("emoji") in EMOJIS else "🪩"
        color = args.get("color") if args.get("color") in COLORS else "pink"
        return {"name": name, "emoji": emoji, "color": color}

    def create(self, token: str, args: dict) -> dict:
        """Nouveau groupe (étape 1 du web) : nom filtré et CGU (base), emoji et couleur ; le créateur en fait partie."""
        uid = self.accounts._uid(token)
        rows = self._req("POST", "/rest/v1/member_groups", token, json={**self._look(args), "created_by": uid},
                         headers={"Prefer": "return=representation"})
        created = rows[0].get("id") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
        if not created:
            raise refused("error", "Le groupe n'a pas été créé. Réessaie.", 400)
        try:  # la base l'ajoute aussi (member_groups_creator_joins) : doublon ignoré
            self._req("POST", "/rest/v1/member_group_members", token, json={"group_id": created, "user_id": uid},
                      headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        except Refused as e:
            if e.status != 409:
                raise refused("error", "Le groupe est créé, mais tu n'as pas pu y être ajouté. Réessaie depuis sa page.", 400) from None
        return {"group": created}

    def update(self, token: str, args: dict) -> dict:
        """Modifier le groupe : nom, emoji, couleur (« Modifier le nom, l'emoji et la photo », 23.11 : update_group_look, la
        base vérifie le droit ; base d'avant : la table, son créateur ou un Admin du site). Jamais Membres Vendredi Party."""
        grp = group_id(args)
        look = self._look(args)
        try:
            self._rpc(token, "update_group_look", {"grp": grp, "group_name": look["name"], "group_emoji": look["emoji"],
                                                   "group_color": look["color"]})
            return {"ok": True}
        except Refused as e:
            if not missing_function(e):
                raise
        rows = self._req("PATCH", f"/rest/v1/member_groups?id=eq.{grp}", token, json=look,
                         headers={"Prefer": "return=representation"})
        if not rows:
            raise refused("forbidden", "Seul le créateur du groupe change son nom, son emoji, sa couleur et sa photo.")
        return {"ok": True}

    def _set_photo_path(self, token: str, grp: str, path: str | None) -> None:
        """Photo posée sur le groupe : set_group_photo (droit « Modifier… », 23.11) ; base d'avant : la table."""
        try:
            self._rpc(token, "set_group_photo", {"grp": grp, "path": path})
            return
        except Refused as e:
            if not missing_function(e):
                raise
        rows = self._req("PATCH", f"/rest/v1/member_groups?id=eq.{grp}", token, json={"photo_path": path},
                         headers={"Prefer": "return=representation"})
        if not rows:
            raise refused("forbidden", "Seul le créateur du groupe change sa photo.")

    def remove_member(self, token: str, args: dict) -> dict:
        grp, who = group_id(args), group_id(args, "member")
        rows = self._req("DELETE", f"/rest/v1/member_group_members?group_id=eq.{grp}&user_id=eq.{who}", token,
                         headers={"Prefer": "return=representation"})
        if not rows:
            raise refused("forbidden", "Seul le créateur du groupe retire un membre.")
        return {"ok": True}

    def leave(self, token: str, args: dict) -> dict:
        """Quitter soi-même (politique « quitter le groupe ») : jamais Membres Vendredi Party, jamais son créateur."""
        grp = group_id(args)
        uid = self.accounts._uid(token)
        rows = self._req("DELETE", f"/rest/v1/member_group_members?group_id=eq.{grp}&user_id=eq.{uid}", token,
                         headers={"Prefer": "return=representation"})
        if not rows:
            raise refused("forbidden", "Tu ne peux pas quitter ce groupe.")
        return {"ok": True}

    def _photo_of(self, token: str, grp: str) -> str | None:
        rows = self._rows(f"/rest/v1/member_groups?select=photo_path&id=eq.{grp}", token)
        if not rows:
            raise Refused(404, {"message": GONE})
        return rows[0].get("photo_path")

    def _drop_file(self, token: str, path: str | None) -> None:
        """Ancien fichier de la photo : retiré (sinon le ménage des fichiers orphelins s'en charge, toutes les 6 h)."""
        if path:
            self._quiet(lambda: self._req("DELETE", "/storage/v1/object/group-photos", token, json={"prefixes": [path]}), None)

    def delete(self, token: str, args: dict) -> dict:
        grp = group_id(args)
        photo = self._quiet(lambda: self._photo_of(token, grp), None)
        rows = self._req("DELETE", f"/rest/v1/member_groups?id=eq.{grp}", token, headers={"Prefer": "return=representation"})
        if not rows:
            raise refused("forbidden", "Seul le créateur du groupe le supprime.")
        self._drop_file(token, photo)  # la photo part avec le groupe
        return {"ok": True}

    def remove_photo(self, token: str, args: dict) -> dict:
        grp = group_id(args)
        old = self._photo_of(token, grp)
        self._set_photo_path(token, grp, None)
        self._drop_file(token, old)
        return {"photo": None}

    def set_photo(self, token: str, grp: str, data: bytes) -> dict:
        """Photo du groupe (facultative) : déposée dans group-photos/<groupe>/ (règle : qui gère le groupe), posée sur le
        groupe (garde group_photo_guard : chemin, fichier présent, CGU), puis l'ancienne part. Rend le chemin."""
        grp = group_id({"grp": grp})
        if not data or len(data) > PHOTO_MAX:
            raise refused("invalid", "La photo est trop volumineuse. Choisis-en une autre.", 400)
        if not data.startswith(IMAGE_MAGIC):
            raise refused("invalid", "Choisis une photo (JPEG ou PNG).", 400)
        old = self._photo_of(token, grp)
        png = data.startswith(b"\x89PNG")
        path = f"{grp}/{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}.{'png' if png else 'jpg'}"
        try:
            self._req("POST", f"/storage/v1/object/group-photos/{path}", token, content=data,
                      headers={"Content-Type": "image/png" if png else "image/jpeg"})
        except Refused as e:
            # Règle du compartiment (seul qui gère le groupe y écrit) : Storage répond 400 {"statusCode": "403", …}.
            body = e.body if isinstance(e.body, dict) else {}
            if e.status in (401, 403) or str(body.get("statusCode")) in ("401", "403") or "security" in str(body).lower():
                raise refused("forbidden", "Seul le créateur du groupe change sa photo.") from None
            raise refused("error", "La photo n'a pas pu être envoyée. Vérifie ta connexion puis réessaie.", 400) from None
        try:
            self._set_photo_path(token, grp, path)
        except Refused:
            self._drop_file(token, path)
            raise
        if old and old != path:
            self._drop_file(token, old)
        return {"kind": "group", "photo": path}  # kind : le relais signe dans group-photos

    # ── Liens d'invitation : l'adresse publique, comme /api/account/groups/link ──

    def invite_link(self, token: str, args: dict) -> dict:
        """Lien réutilisable du groupe (group_invite_link ; renew : l'ancien ne marche plus)."""
        link = self._rpc(token, "group_invite_link", {"grp": group_id(args), "renew": bool(args.get("renew"))})
        if not link:
            raise refused("error", "Le lien n'a pas pu être créé. Réessaie.", 400)
        return {"token": link, "url": self.invite_url(str(link))}

    def single_link(self, token: str, args: dict) -> dict:
        """Lien unique (une personne, une fois, 7 jours)."""
        link = self._rpc(token, "create_invite_link", {"k": "group", "target": group_id(args)})
        if not link:
            raise refused("error", "Le lien n'a pas pu être créé. Réessaie.", 400)
        return {"token": link, "url": self.invite_url(str(link))}

    def links(self, token: str, args: dict) -> list:
        return self._rpc(token, "my_invite_links", {"k": "group", "target": group_id(args)}) or []

    def find_person(self, token: str, args: dict) -> dict | None:
        """« Inviter le surnom … » (comme le web) : un compte actif dont le surnom est EXACTEMENT celui-là (sans casse) ;
        jamais une recherche par morceau ni par numéro (le numéro passe par invite_to_group)."""
        typed = str(args.get("q") or "").strip().lstrip("@").strip()[:NAME_MAX]
        if not typed:
            return None
        uid = self.accounts._uid(token)
        exact = re.sub(r"([\\%_])", r"\\\1", typed)
        rows = self._rows("/rest/v1/profiles?select=id,display_name&status=eq.active"
                          f"&display_name=ilike.{quote(exact, safe='')}&limit=1", token)
        found = rows[0] if rows else None
        if not found or found.get("id") == uid:
            return None
        return {"id": found["id"], "name": found.get("display_name") or ""}


# Fonctions du relais faites par le serveur (lectures composées, écritures dans les tables) → méthode de GroupPages.
LOCAL = {
    "groups_home": "home", "group_page": "page", "group_create": "create", "group_update": "update",
    "group_remove_member": "remove_member", "group_leave": "leave", "group_delete": "delete",
    "group_photo_remove": "remove_photo", "group_link": "invite_link", "group_single_link": "single_link",
    "group_links": "links", "group_find_person": "find_person",
}
