"""Discussions de groupe (avis n°10) pour l'app iOS native : liste, conversation, envoi, photos, réactions, épinglage,
suppression, notifications et admins du groupe. Tout passe par la session du membre : la base (règles RLS, garde
guard_group_message, fonctions) décide ; le serveur relaie et met en forme, comme group_admin.py."""
import re
import time
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
SITE_ADMIN_RANK = 3                  # Co-admin et au-dessus : admins d'office des groupes dont ils font partie
EVERYONE = re.compile(r"(^|\s)@tout(\s|$|[!?.,])", re.I)
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


def mentions_in(body: str, people: dict[str, str], me: str) -> list[str]:
    """« @Léa » dans le texte → Léa est citée (la base ne garde que les membres du groupe)."""
    lower = body.lower()
    return [uid for uid, name in people.items() if uid != me and name and f"@{name.lower()}" in lower]


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
        # Temps réel (adresse et clé publiques de Supabase) : l'app reçoit les nouveaux messages sans attendre.
        return {"chats": rows, "realtime": {"url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket",
                                            "key": SUPABASE_ANON_KEY}}

    def _chat(self, token: str, group_id: str) -> dict:
        chat = next((c for c in self.chats(token)["chats"] if c.get("id") == group_id), None)
        if chat is None:
            raise AccountError("Cette discussion n'est pas accessible.")
        return chat

    def _people(self, token: str, ids: set[str]) -> dict[str, dict]:
        rows = self._rows("/rest/v1/profiles?select=id,display_name,avatar_url&status=eq.active", token)
        return {p["id"]: p for p in rows if p["id"] in ids}

    def conversation(self, token: str, group_id: str) -> dict:
        self.admin.accounts._uid(token)  # jeton vérifié une fois (gardé 5 min), avant les lectures parallèles
        jobs = {
            "me": POOL.submit(self.admin.access, token),
            "chat": POOL.submit(self._chat, token, group_id),
            "group": POOL.submit(self._rows, f"/rest/v1/member_groups?select=id,name,created_by,member_group_members(user_id)"
                                             f"&id=eq.{group_id}", token),
            "messages": POOL.submit(self._rows, f"/rest/v1/group_messages?select=*&group_id=eq.{group_id}"
                                                f"&order=created_at.desc&limit={PAGE}", token),
            "admins": POOL.submit(self._rows, f"/rest/v1/group_admins?select=user_id&group_id=eq.{group_id}", token),
            # Numéros que les membres montrent dans ce groupe : l'app les rend appelables d'un toucher.
            "phones": POOL.submit(self.admin._rpc, token, "group_chat_phones", {"grp": group_id}, "Les membres n'ont pas pu être lus."),
            "profiles": POOL.submit(self._rows, "/rest/v1/profiles?select=id,display_name,avatar_url&status=eq.active", token),
        }
        got = {k: f.result() for k, f in jobs.items()}
        me, chat, group = got["me"], got["chat"], got["group"]
        if not group:
            raise AccountError("Cette discussion n'est pas accessible.")
        messages = list(reversed(got["messages"]))
        admins = {a["user_id"] for a in got["admins"]}
        phones = {p["id"]: p["phone"] for p in got["phones"] or []}
        inside = [m["user_id"] for m in group[0].get("member_group_members") or []]
        wanted = {m["user_id"] for m in messages} | set(inside)
        people = {p["id"]: p for p in got["profiles"] if p["id"] in wanted}
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
        out = []
        for m in messages:
            deleted = bool(m.get("deleted_at"))
            quoted = by_id.get(m.get("reply_to") or "")
            out.append({
                "id": m["id"], "author": m["user_id"], "author_name": name(m["user_id"]), "author_photo": face(m["user_id"]),
                "mine": m["user_id"] == me["me"], "at": m["created_at"], "edited": bool(m.get("edited_at")) and not deleted,
                "body": deleted_label(m) if deleted else m.get("body") or "", "deleted": deleted,
                "photo": None if deleted else photos.get(m.get("photo_path") or ""),
                "audio": None if deleted else photos.get(m.get("audio_path") or ""),
                "audio_seconds": float(m["audio_seconds"]) if m.get("audio_seconds") is not None and not deleted else None,
                "pinned": bool(m.get("pinned")) and not deleted,
                "reply": None if not quoted or deleted else {
                    "name": name(quoted["user_id"]),
                    "text": deleted_label(quoted) if quoted.get("deleted_at") else quoted.get("body") or "📷 Photo"},
                "reactions": reactions_of(m["id"], reactions, me["me"]),
            })
        return {
            "id": group_id, "name": group[0].get("name") or "Groupe", "me": me["me"],
            "member": bool(chat.get("member")), "admin": bool(chat.get("admin")), "notify": chat.get("notify") or "mentions",
            "can_name_admins": creator == me["me"] or me["rank"] >= SITE_ADMIN_RANK,
            "reactions": list(REACTIONS),
            "members": [{"id": u, "name": name(u), "photo": face(u), "admin": u in admins, "creator": u == creator,
                         "phone": dialable(phones.get(u))} for u in inside],
            "messages": out,
        }

    def send(self, token: str, group_id: str, body: str, reply_to: str | None, photo_path: str | None,
             mentions: list[str] | None = None, message_id: str | None = None,
             audio_path: str | None = None, audio_seconds: float | None = None) -> dict:
        """Envoi. mentions fournies par l'app (elle connaît les membres) : un seul appel à la base, le plus rapide ;
        la base ne garde que les membres du groupe et n'accepte @tout que d'un admin (guard_group_message)."""
        if not body and not photo_path and not audio_path:
            raise AccountError("Écris un message, choisis une photo ou enregistre un vocal.")
        if photo_path and not photo_path.startswith(f"{group_id}/"):
            raise AccountError("Photo invalide.")
        if audio_path and not audio_path.startswith(f"{group_id}/"):
            raise AccountError("Message vocal invalide.")
        if mentions is None:
            me = self.admin.accounts._uid(token)
            group = self._rows(f"/rest/v1/member_groups?select=member_group_members(user_id)&id=eq.{group_id}", token)
            inside = {m["user_id"] for m in (group[0].get("member_group_members") if group else None) or []}
            people = {uid: p.get("display_name") or "" for uid, p in self._people(token, inside).items()}
            mentions = mentions_in(body, people, me)
        row = {"group_id": group_id, "body": body, "photo_path": photo_path, "reply_to": reply_to,
               "mentions": mentions, "mention_all": bool(EVERYONE.search(body))}
        if audio_path:
            row.update(audio_path=audio_path, audio_seconds=round(min(max(audio_seconds or 0, 0), AUDIO_MAX_SECONDS), 1))
        if message_id:
            row["id"] = message_id  # identifiant choisi par l'app : le message affiché tout de suite garde sa place
        r = self.admin._call("POST", "/rest/v1/group_messages", token, json=row, headers={"Prefer": "return=minimal"})
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

    def react(self, token: str, message_id: str, emoji: str, on: bool) -> dict:
        if emoji not in REACTIONS:
            raise AccountError("Réaction inconnue.")
        if on:
            r = self.admin._call("POST", "/rest/v1/group_message_reactions", token, json={"message_id": message_id, "emoji": emoji},
                                 headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        else:
            me = self.admin.accounts._uid(token)
            r = self.admin._call("DELETE", "/rest/v1/group_message_reactions", token,
                                 params={"message_id": f"eq.{message_id}", "user_id": f"eq.{me}", "emoji": f"eq.{emoji}"})
        if r.status_code not in OK:
            raise AccountError(readable(r, "La réaction n'a pas pu être enregistrée."))
        return {"ok": True}

    def pin(self, token: str, message_id: str, pin: bool) -> dict:
        self.admin._rpc(token, "pin_group_message", {"msg": message_id, "pin": pin}, "Réservé aux admins du groupe.")
        return {"ok": True}

    def delete(self, token: str, message_id: str) -> dict:
        self.admin._rpc(token, "delete_group_message", {"msg": message_id}, "Ce message n'a pas pu être supprimé.")
        return {"ok": True}

    def notify(self, token: str, group_id: str, level: str) -> dict:
        if level not in LEVELS:
            raise AccountError("Choix inconnu.")
        self.admin._rpc(token, "set_group_chat_notify", {"grp": group_id, "level": level}, "Le réglage n'a pas pu être enregistré.")
        return {"notify": level}

    def set_admin(self, token: str, group_id: str, member: str, on: bool) -> dict:
        self.admin._rpc(token, "set_group_admin", {"grp": group_id, "member": member, "admin": on},
                        "Seul le créateur du groupe nomme les admins.")
        return {"ok": True}

    def read(self, token: str, group_id: str) -> dict:
        self.admin._rpc(token, "mark_group_read", {"grp": group_id}, "La discussion n'a pas pu être marquée comme lue.")
        return {"ok": True}
