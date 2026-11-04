"""Discussions de groupe (avis n°10) pour l'app iOS native : liste, conversation, envoi, photos, réactions, épinglage,
suppression, notifications et admins du groupe. Tout passe par la session du membre : la base (règles RLS, garde
guard_group_message, fonctions) décide ; le serveur relaie et met en forme, comme group_admin.py."""
import re
import time
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor

from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError
from .group_admin import OK, GroupAdmin, readable

PAGE = 150
PHOTO_TTL = 3600
SIGNED_REUSE = 2400                  # un lien signé (1 h) resservi 40 min : les images ne se rechargent pas à chaque mise à jour
PHOTO_MAX = 8 * 1024 * 1024          # même limite que le stockage chat-photos
REACTIONS = ("👍", "❤️", "😂", "😮", "😢", "🔥")
LEVELS = ("all", "mentions", "none")
DIRECT_LEVELS = ("all", "none")      # message direct : tout ou rien (pas de citation à deux)
EVERYONE_BY = ("all", "staff")       # qui écrit @tout dans un groupe : tous les membres, ou admins et organisateurs
SITE_ADMIN_RANK = 3                  # (anciens rangs, si access() ne donne pas site_admin) Co-admin et au-dessus : admins d'office des groupes dont ils font partie
EVERYONE = re.compile(r"(^|\s)@tout(\s|$|[!?.,])", re.I)
HIGHLIGHTS = 20                      # annonces et messages épinglés gardés en tête, même plus anciens que la page
IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG")
AUDIO_MAX_SECONDS = 600              # 10 minutes par message vocal (même borne que la base)


def audio_kind(data: bytes) -> tuple[str, str] | None:
    """Format d'un message vocal d'après ses premiers octets : (type, extension) ; None si ce n'est pas de l'audio connu."""
    if data[4:8] == b"ftyp":
        return "audio/mp4", "m4a"          # iPhone (AAC) et Safari
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm", "webm"        # Chrome, Firefox (Opus)
    if data.startswith(b"OggS"):
        return "audio/ogg", "ogg"
    return None
# Lectures indépendantes faites en parallèle : une conversation s'ouvre en un aller-retour vers la base, pas huit.
POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="chats")


def dialable(phone: str | None) -> str | None:
    """« 41790000001 » → « +41790000001 » (lien tel: dans l'app) ; rien si le numéro est absent ou invalide."""
    digits = re.sub(r"\D", "", phone or "")
    return f"+{digits}" if len(digits) >= 6 else None


def deleted_label(m: dict) -> str:
    return "Message supprimé par un admin" if m.get("deleted_by_admin") else "Message supprimé"


def fold(text: str) -> str:
    """Sans accents ni casse : « @lea » cite Léa, comme les suggestions de l'app."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)).lower()


def mentions_in(body: str, people: dict[str, str], me: str) -> list[str]:
    """« @Léa » (ou « @lea ») dans le texte → Léa est citée (la base ne garde que les membres du groupe)."""
    folded = fold(body)
    return [uid for uid, name in people.items() if uid != me and name and f"@{fold(name)}" in folded]


def reactions_of(message_id: str, reactions: list, me: str) -> list[dict]:
    counts: dict[str, dict] = {}
    for r in reactions:
        if r["message_id"] == message_id:
            c = counts.setdefault(r["emoji"], {"emoji": r["emoji"], "count": 0, "mine": False})
            c["count"] += 1
            c["mine"] = c["mine"] or r["user_id"] == me
    return list(counts.values())


class GroupChats:
    def __init__(self, admin: GroupAdmin):
        self.admin = admin
        self.signed: dict[tuple[str, str], tuple[float, str]] = {}  # (compartiment, chemin) → (instant, lien signé)

    def _cached_sign(self, bucket: str, paths: list, sign) -> dict[str, str]:
        """Liens signés gardés 40 min par chemin (le même lien d'une mise à jour à l'autre : pas de rechargement)."""
        now = time.time()
        wanted = sorted({p for p in paths if p})
        fresh = {p: self.signed[(bucket, p)][1] for p in wanted
                 if (bucket, p) in self.signed and now - self.signed[(bucket, p)][0] < SIGNED_REUSE}
        missing = [p for p in wanted if p not in fresh]
        if missing:
            new = sign(missing)
            self.signed.update({(bucket, p): (now, url) for p, url in new.items()})
            fresh.update(new)
            if len(self.signed) > 5000:  # borne : on oublie les plus anciens
                for key in sorted(self.signed, key=lambda k: self.signed[k][0])[:1000]:
                    self.signed.pop(key, None)
        return fresh

    def _rows(self, path: str, token: str) -> list:
        return self.admin._rows(path, token)

    def _sign(self, paths: list, token: str) -> dict[str, str]:
        paths = sorted({p for p in paths if p})
        if not paths:
            return {}
        r = self.admin._call("POST", "/storage/v1/object/sign/chat-photos", token, json={"expiresIn": PHOTO_TTL, "paths": paths})
        rows = r.json() if r.status_code == 200 else []
        return {row["path"]: SUPABASE_URL + "/storage/v1" + row["signedURL"]
                for row in rows if isinstance(row, dict) and row.get("signedURL") and row.get("path")}

    def chats(self, token: str) -> dict:
        rows = self.admin._rpc(token, "my_chats", {}, "Les discussions n'ont pas pu être chargées.") or []
        # Messages directs : la photo de l'autre personne (lien signé, comme les auteurs des messages).
        faces = self._cached_sign("profile-photos", [c.get("avatar_url") for c in rows if c.get("kind") == "direct"],
                                  lambda paths: self.admin._photos(paths, token))
        rows = [{**c, "photo": faces.get(c.get("avatar_url") or "")} if c.get("kind") == "direct" else c for c in rows]
        # Temps réel (adresse et clé publiques de Supabase) : l'app reçoit les nouveaux messages sans attendre.
        return {"chats": rows, "realtime": {"url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket",
                                            "key": SUPABASE_ANON_KEY}}

    def _chat(self, token: str, group_id: str) -> dict:
        rows = self.admin._rpc(token, "my_chats", {}, "Les discussions n'ont pas pu être chargées.") or []
        chat = next((c for c in rows if c.get("id") == group_id), None)
        if chat is None:
            raise AccountError("Cette discussion n'est pas accessible.")
        return chat

    def _is_direct(self, token: str, chat_id: str) -> bool:
        """Conversation directe dont je fais partie (la règle de lecture ne répond qu'à ses deux personnes)."""
        try:
            return bool(self._rows(f"/rest/v1/direct_chats?select=id&id=eq.{chat_id}", token))
        except AccountError:
            return False

    def _organizers(self, token: str, group_id: str) -> set[str]:
        """Organisateurs du groupe (vide tant que la migration n'est pas en place : rien ne casse)."""
        try:
            return {o["user_id"] for o in self._rows(f"/rest/v1/group_organizers?select=user_id&group_id=eq.{group_id}", token)}
        except AccountError:
            return set()

    def _people(self, token: str, group_id: str, ids: set[str] | None) -> dict[str, dict]:
        """Membres du groupe (ids=None) ou personnes choisies : surnom et photo, via group_chat_people."""
        rows = self.admin._rpc(token, "group_chat_people", {"grp": group_id}, "Les membres n'ont pas pu être lus.") or []
        return {p["id"]: p for p in rows if (p.get("member") if ids is None else p["id"] in ids)}

    def start_direct(self, token: str, user_id: str, contact_hash: str | None = None) -> dict:
        """« Écrire » : LA conversation privée avec cette personne (créée au besoin, une seule par paire)."""
        args = {"target": user_id} | ({"contact_hash": contact_hash} if contact_hash else {})
        chat = self.admin._rpc(token, "start_direct_chat", args, "Tu ne peux pas écrire à cette personne.")
        if not isinstance(chat, str):
            raise AccountError("Tu ne peux pas écrire à cette personne.")
        return {"id": chat}

    def block(self, token: str, user_id: str, on: bool) -> dict:
        self.admin._rpc(token, "set_direct_block", {"target": user_id, "blocked": on}, "Le blocage n'a pas pu être enregistré.")
        return {"blocked": on}

    def _direct_conversation(self, token: str, chat_id: str) -> dict:
        """Conversation privée à deux : même forme qu'un groupe (l'app la montre avec le même écran), sans admins,
        organisateurs, @tout ni @annonce ; direct = True, user_id = l'autre personne."""
        me_id = self.admin.accounts._uid(token)
        # Lue directement (pas par my_chats) : une conversation tout juste ouverte, sans message, n'y figure pas encore.
        jobs = {
            "chat": POOL.submit(self._rows, f"/rest/v1/direct_chats?select=user_a,user_b&id=eq.{chat_id}", token),
            "settings": POOL.submit(self._rows, f"/rest/v1/direct_chat_settings?select=notify&chat_id=eq.{chat_id}", token),
            "blocks": POOL.submit(self._rows, "/rest/v1/direct_blocks?select=blocked_id", token),
            "messages": POOL.submit(self._rows, f"/rest/v1/direct_messages?select=*&chat_id=eq.{chat_id}"
                                                f"&order=created_at.desc&limit={PAGE}", token),
            "highlights": POOL.submit(self._rows, f"/rest/v1/direct_messages?select=*&chat_id=eq.{chat_id}&pinned=is.true"
                                                  f"&deleted_at=is.null&order=created_at.desc&limit={HIGHLIGHTS}", token),
            "profiles": POOL.submit(self.admin._rpc, token, "direct_chat_people", {"chat": chat_id}, "La conversation n'a pas pu être lue."),
        }
        got = {k: f.result() for k, f in jobs.items()}
        if not got["chat"]:
            raise AccountError("Cette discussion n'est pas accessible.")
        pair = got["chat"][0]
        other = pair["user_b"] if pair["user_a"] == me_id else pair["user_a"]
        notify = (got["settings"] or [{}])[0].get("notify") or "all"
        blocked = any(b.get("blocked_id") == other for b in got["blocks"] or [])
        messages = list(reversed(got["messages"]))
        people = {p["id"]: p for p in got["profiles"] or []}
        ids = ",".join(m["id"] for m in messages)
        reactions = self._rows(f"/rest/v1/direct_message_reactions?select=message_id,user_id,emoji&message_id=in.({ids})",
                               token) if ids else []
        photos = self._cached_sign("chat-photos", [p for m in messages if not m.get("deleted_at")
                                                   for p in (m.get("photo_path"), m.get("audio_path"))],
                                   lambda paths: self._sign(paths, token))
        faces = self._cached_sign("profile-photos", [p.get("avatar_url") for p in people.values()],
                                  lambda paths: self.admin._photos(paths, token))

        def name(uid: str) -> str:
            return (people.get(uid) or {}).get("display_name") or "?"

        def face(uid: str) -> str | None:
            return faces.get((people.get(uid) or {}).get("avatar_url") or "")

        by_id = {m["id"]: m for m in messages}
        return {
            "id": chat_id, "name": name(other) if name(other) != "?" else "Profil à compléter", "me": me_id, "direct": True,
            "user_id": other, "photo": face(other), "blocked": blocked,
            "member": True, "admin": False, "notify": notify, "organizer": False, "everyone": "staff",
            "can_name_admins": False, "reactions": list(REACTIONS),
            "members": [{"id": u, "name": name(u), "photo": face(u), "admin": False, "creator": False, "organizer": False,
                         "phone": None} for u in people],
            "messages": [self._message(m, by_id, me_id, name, face, photos, reactions) for m in messages],
            "highlights": [{"id": m["id"], "author_name": name(m["user_id"]), "at": m["created_at"],
                            "text": m.get("body") or ("🎤 Message vocal" if m.get("audio_path") else "📷 Photo"), "announcement": False}
                           for m in reversed(got["highlights"] or []) if m.get("pinned") and not m.get("deleted_at")],
        }

    def conversation(self, token: str, group_id: str, direct: bool = False) -> dict:
        if direct:
            return self._direct_conversation(token, group_id)
        try:
            return self._group_conversation(token, group_id)
        except AccountError:
            # Toucher d'une notification (id seul) : un message direct se reconnaît ici, l'app n'a pas à le savoir.
            if self._is_direct(token, group_id):
                return self._direct_conversation(token, group_id)
            raise

    def _group_conversation(self, token: str, group_id: str) -> dict:
        self.admin.accounts._uid(token)  # jeton vérifié une fois (gardé 5 min), avant les lectures parallèles
        jobs = {
            "me": POOL.submit(self.admin.access, token),
            "chat": POOL.submit(self._chat, token, group_id),
            "group": POOL.submit(self._rows, f"/rest/v1/member_groups?select=id,name,created_by,everyone_tag,member_group_members(user_id)"
                                             f"&id=eq.{group_id}", token),
            "messages": POOL.submit(self._rows, f"/rest/v1/group_messages?select=*&group_id=eq.{group_id}"
                                                f"&order=created_at.desc&limit={PAGE}", token),
            "admins": POOL.submit(self._rows, f"/rest/v1/group_admins?select=user_id&group_id=eq.{group_id}", token),
            "organizers": POOL.submit(self._organizers, token, group_id),
            # Annonces (@annonce) et messages épinglés : le bandeau du haut, même au-delà des derniers messages.
            "highlights": POOL.submit(self._rows, f"/rest/v1/group_messages?select=*&group_id=eq.{group_id}&pinned=is.true"
                                                  f"&deleted_at=is.null&order=created_at.desc&limit={HIGHLIGHTS}", token),
            # Numéros que les membres montrent dans ce groupe : l'app les rend appelables d'un toucher.
            "phones": POOL.submit(self.admin._rpc, token, "group_chat_phones", {"grp": group_id}, "Les membres n'ont pas pu être lus."),
            # Surnoms et photos des personnes du groupe (fonction dédiée : un Guest ne lit pas le profil d'un admin).
            "profiles": POOL.submit(self.admin._rpc, token, "group_chat_people", {"grp": group_id}, "Les membres n'ont pas pu être lus."),
        }
        got = {k: f.result() for k, f in jobs.items()}
        me, chat, group = got["me"], got["chat"], got["group"]
        if not group:
            raise AccountError("Cette discussion n'est pas accessible.")
        messages = list(reversed(got["messages"]))
        admins = {a["user_id"] for a in got["admins"]}
        organizers = got["organizers"]
        phones = {p["id"]: p["phone"] for p in got["phones"] or []}
        # Membres : d'après group_chat_people (un Guest ne voit pas les autres appartenances dans member_group_members).
        inside = [p["id"] for p in got["profiles"] or [] if p.get("member")] or \
            [m["user_id"] for m in group[0].get("member_group_members") or []]
        wanted = {m["user_id"] for m in messages} | set(inside)
        people = {p["id"]: p for p in got["profiles"] or [] if p["id"] in wanted}
        ids = ",".join(m["id"] for m in messages)
        second = {
            "reactions": POOL.submit(self._rows, f"/rest/v1/group_message_reactions?select=message_id,user_id,emoji"
                                                 f"&message_id=in.({ids})", token) if ids else None,
            "photos": POOL.submit(self._cached_sign, "chat-photos",
                                  [p for m in messages if not m.get("deleted_at") for p in (m.get("photo_path"), m.get("audio_path"))],
                                  lambda paths: self._sign(paths, token)),
            "faces": POOL.submit(self._cached_sign, "profile-photos", [p.get("avatar_url") for p in people.values()],
                                 lambda paths: self.admin._photos(paths, token)),
        }
        reactions = second["reactions"].result() if second["reactions"] else []
        photos, faces = second["photos"].result(), second["faces"].result()

        def name(uid: str) -> str:
            return (people.get(uid) or {}).get("display_name") or "?"

        def face(uid: str) -> str | None:
            return faces.get((people.get(uid) or {}).get("avatar_url") or "")

        by_id = {m["id"]: m for m in messages}
        creator = group[0].get("created_by")
        out = [self._message(m, by_id, me["me"], name, face, photos, reactions) for m in messages]
        highlights = [{"id": m["id"], "author_name": name(m["user_id"]), "at": m["created_at"],
                       "text": m.get("body") or ("🎤 Message vocal" if m.get("audio_path") else "📷 Photo"),
                       "announcement": bool(m.get("announcement"))}
                      for m in reversed(got["highlights"] or []) if m.get("pinned") and not m.get("deleted_at")]
        admin = bool(chat.get("admin"))
        return {
            "id": group_id, "name": group[0].get("name") or "Groupe", "me": me["me"],
            "member": bool(chat.get("member")), "admin": admin, "notify": chat.get("notify") or "mentions",
            # Organisateur (ou admin) : fait des annonces, les retire ; « everyone » : qui peut écrire @tout.
            "organizer": admin or (me["me"] in organizers and bool(chat.get("member"))),
            "everyone": group[0].get("everyone_tag") or "all",
            "can_name_admins": creator == me["me"] or me.get("site_admin", me["rank"] >= SITE_ADMIN_RANK),
            "reactions": list(REACTIONS),
            "members": [{"id": u, "name": name(u), "photo": face(u), "admin": u in admins, "creator": u == creator,
                         "organizer": u in organizers, "phone": dialable(phones.get(u))} for u in inside],
            "messages": out,
            "highlights": highlights,
        }

    @staticmethod
    def _message(m: dict, by_id: dict, me: str, name, face, photos: dict, reactions: list) -> dict:
        """Un message mis en forme pour l'app (supprimé : son libellé seulement)."""
        deleted = bool(m.get("deleted_at"))
        quoted = by_id.get(m.get("reply_to") or "")
        return {
            "id": m["id"], "author": m["user_id"], "author_name": name(m["user_id"]), "author_photo": face(m["user_id"]),
            "mine": m["user_id"] == me, "at": m["created_at"], "edited": bool(m.get("edited_at")) and not deleted,
            "body": deleted_label(m) if deleted else m.get("body") or "", "deleted": deleted,
            "photo": None if deleted else photos.get(m.get("photo_path") or ""),
            "audio": None if deleted else photos.get(m.get("audio_path") or ""),
            "audio_seconds": float(m["audio_seconds"]) if m.get("audio_seconds") is not None and not deleted else None,
            "pinned": bool(m.get("pinned")) and not deleted,
            "announcement": bool(m.get("announcement")) and bool(m.get("pinned")) and not deleted,
            "reply": None if not quoted or deleted else {
                "name": name(quoted["user_id"]),
                "text": deleted_label(quoted) if quoted.get("deleted_at") else quoted.get("body") or "📷 Photo"},
            "reactions": reactions_of(m["id"], reactions, me),
        }

    def send(self, token: str, group_id: str, body: str, reply_to: str | None, photo_path: str | None,
             mentions: list[str] | None = None, message_id: str | None = None,
             audio_path: str | None = None, audio_seconds: float | None = None, direct: bool = False) -> dict:
        """Envoi. mentions fournies par l'app (elle connaît les membres) : un seul appel à la base, le plus rapide ;
        la base ne garde que les membres du groupe ; @tout cite tout le groupe (selon le choix du groupe) ; « @annonce »
        d'un admin ou d'un organisateur épingle le message en annonce et le notifie à tous (guard_group_message)."""
        if not body and not photo_path and not audio_path:
            raise AccountError("Écris un message, choisis une photo ou enregistre un vocal.")
        if photo_path and not photo_path.startswith(f"{group_id}/"):
            raise AccountError("Photo invalide.")
        if audio_path and not audio_path.startswith(f"{group_id}/"):
            raise AccountError("Message vocal invalide.")
        if direct:  # message direct (conversation à deux) : ni citation, ni @tout, ni @annonce
            row = {"chat_id": group_id, "body": body, "photo_path": photo_path, "reply_to": reply_to}
        else:
            if mentions is None:
                me = self.admin.accounts._uid(token)
                people = {uid: p.get("display_name") or "" for uid, p in self._people(token, group_id, None).items()}
                mentions = mentions_in(body, people, me)
            row = {"group_id": group_id, "body": body, "photo_path": photo_path, "reply_to": reply_to,
                   "mentions": mentions, "mention_all": bool(EVERYONE.search(body))}
        if audio_path:
            row.update(audio_path=audio_path, audio_seconds=round(min(max(audio_seconds or 0, 0), AUDIO_MAX_SECONDS), 1))
        if message_id:
            row["id"] = message_id  # identifiant choisi par l'app : le message affiché tout de suite garde sa place
        table = "direct_messages" if direct else "group_messages"
        r = self.admin._call("POST", f"/rest/v1/{table}", token, json=row, headers={"Prefer": "return=minimal"})
        if r.status_code not in OK:
            raise AccountError(readable(r, "Le message n'a pas pu être envoyé. Réessaie."))
        return {"ok": True}

    def upload_photo(self, token: str, group_id: str, data: bytes) -> dict:
        if not data or len(data) > PHOTO_MAX:
            raise AccountError("Photo trop volumineuse (8 Mo au plus).")
        if not data.startswith(IMAGE_MAGIC):
            raise AccountError("Choisis une photo (JPEG ou PNG).")
        png = data.startswith(b"\x89PNG")
        path = f"{group_id}/{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}.{'png' if png else 'jpg'}"
        r = self.admin._call("POST", f"/storage/v1/object/chat-photos/{path}", token, content=data,
                             headers={"Content-Type": "image/png" if png else "image/jpeg"})
        if r.status_code not in OK:
            raise AccountError("La photo n'a pas pu être envoyée. Réessaie.")
        return {"path": path}

    def upload_audio(self, token: str, group_id: str, data: bytes) -> dict:
        """Message vocal (AAC de l'iPhone, Opus du navigateur) dans le dossier du groupe ; la base vérifie le membre."""
        if not data or len(data) > PHOTO_MAX:
            raise AccountError("Message vocal trop long (8 Mo au plus).")
        kind = audio_kind(data)
        if not kind:
            raise AccountError("Enregistrement illisible : réessaie.")
        path = f"{group_id}/{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}.{kind[1]}"
        r = self.admin._call("POST", f"/storage/v1/object/chat-photos/{path}", token, content=data, headers={"Content-Type": kind[0]})
        if r.status_code not in OK:
            raise AccountError("Le message vocal n'a pas pu être envoyé. Réessaie.")
        return {"path": path}

    def react(self, token: str, message_id: str, emoji: str, on: bool, direct: bool = False) -> dict:
        if emoji not in REACTIONS:
            raise AccountError("Réaction inconnue.")
        table = "/rest/v1/direct_message_reactions" if direct else "/rest/v1/group_message_reactions"
        if on:
            r = self.admin._call("POST", table, token, json={"message_id": message_id, "emoji": emoji},
                                 headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        else:
            me = self.admin.accounts._uid(token)
            r = self.admin._call("DELETE", table, token,
                                 params={"message_id": f"eq.{message_id}", "user_id": f"eq.{me}", "emoji": f"eq.{emoji}"})
        if r.status_code not in OK:
            raise AccountError(readable(r, "La réaction n'a pas pu être enregistrée."))
        return {"ok": True}

    def pin(self, token: str, message_id: str, pin: bool, direct: bool = False) -> dict:
        if direct:
            self.admin._rpc(token, "pin_direct_message", {"msg": message_id, "pin": pin}, "Ce message n'a pas pu être épinglé.")
        else:
            self.admin._rpc(token, "pin_group_message", {"msg": message_id, "pin": pin}, "Réservé aux admins du groupe.")
        return {"ok": True}

    def delete(self, token: str, message_id: str, direct: bool = False) -> dict:
        self.admin._rpc(token, "delete_direct_message" if direct else "delete_group_message", {"msg": message_id},
                        "Ce message n'a pas pu être supprimé.")
        return {"ok": True}

    def notify(self, token: str, group_id: str, level: str, direct: bool = False) -> dict:
        if level not in (DIRECT_LEVELS if direct else LEVELS):
            raise AccountError("Choix inconnu.")
        if direct:
            self.admin._rpc(token, "set_direct_chat_notify", {"chat": group_id, "level": level}, "Le réglage n'a pas pu être enregistré.")
            return {"notify": level}
        self.admin._rpc(token, "set_group_chat_notify", {"grp": group_id, "level": level}, "Le réglage n'a pas pu être enregistré.")
        return {"notify": level}

    def set_admin(self, token: str, group_id: str, member: str, on: bool) -> dict:
        self.admin._rpc(token, "set_group_admin", {"grp": group_id, "member": member, "admin": on},
                        "Seul le créateur du groupe nomme les admins.")
        return {"ok": True}

    def set_organizer(self, token: str, group_id: str, member: str, on: bool) -> dict:
        self.admin._rpc(token, "set_group_organizer", {"grp": group_id, "member": member, "organizer": on},
                        "Seuls les admins du groupe nomment les organisateurs.")
        return {"ok": True}

    def set_everyone(self, token: str, group_id: str, who: str) -> dict:
        if who not in EVERYONE_BY:
            raise AccountError("Choix inconnu.")
        self.admin._rpc(token, "set_group_everyone_tag", {"grp": group_id, "who": who}, "Réservé aux admins du groupe.")
        return {"everyone": who}

    def read(self, token: str, group_id: str, direct: bool = False) -> dict:
        if direct:
            self.admin._rpc(token, "mark_direct_read", {"chat": group_id}, "La discussion n'a pas pu être marquée comme lue.")
            return {"ok": True}
        self.admin._rpc(token, "mark_group_read", {"grp": group_id}, "La discussion n'a pas pu être marquée comme lue.")
        return {"ok": True}
