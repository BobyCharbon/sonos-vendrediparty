"""Discussion d'un événement pour l'app iPhone native (demande de l'admin du 16.11.2026, migration 20261116180000).
Même forme qu'une discussion de groupe (app/group_chats.py) : l'app la montre avec le même écran, « event » = True.
Tout passe par la session du membre : la base (règles de messages, garde guard_message_change, fonctions
event_chat_state / event_chat_people) décide de qui lit, écrit, épingle, annonce et cite @toutlemonde / @present."""
from datetime import datetime, timezone

from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError
from .group_admin import OK, refusal
from .group_chats import AUDIO_MAX_SECONDS, BLOCKED_TEXT, HIGHLIGHTS, PAGE, POOL, REACTIONS, GroupChats, mentions_in

# Citations spéciales de la discussion d'un événement (organisation seulement) : nom tapé après l'@ et explication.
TAGS = ({"tag": "toutlemonde", "hint": "Tout le monde : invités et participants"},
        {"tag": "present", "hint": "Les présents et les peut-être"},
        {"tag": "annonce", "hint": "Annonce épinglée en haut, envoyée à tous"})


def preview(m: dict) -> str:
    return m.get("body") or ("🎤 Message vocal" if m.get("audio_path") else "📷 Photo")


class EventChats:
    def __init__(self, chats: GroupChats):
        self.chats = chats
        self.admin = chats.admin

    def _rows(self, path: str, token: str) -> list:
        return self.admin._rows(path, token)

    def _people(self, token: str, event_id: str) -> list:
        return self.admin._rpc(token, "event_chat_people", {"e": event_id}, "Les participants n'ont pas pu être lus.") or []

    def conversation(self, token: str, event_id: str) -> dict:
        me = self.admin.accounts._uid(token)  # jeton vérifié une fois, avant les lectures parallèles
        jobs = {
            "state": POOL.submit(self.admin._rpc, token, "event_chat_state", {"e": event_id}, "Cette discussion n'est pas accessible."),
            "messages": POOL.submit(self._rows, f"/rest/v1/messages?select=*&event_id=eq.{event_id}"
                                                f"&order=created_at.desc,id.desc&limit={PAGE}", token),
            # Annonces et messages épinglés : le bandeau du haut, même au-delà des derniers messages.
            "highlights": POOL.submit(self._rows, f"/rest/v1/messages?select=*&event_id=eq.{event_id}&pinned=is.true"
                                                  f"&deleted_at=is.null&order=created_at.desc&limit={HIGHLIGHTS}", token),
            "people": POOL.submit(self._people, token, event_id),
            "blocks": POOL.submit(self._rows, "/rest/v1/direct_blocks?select=blocked_id", token),
        }
        got = {k: f.result() for k, f in jobs.items()}
        state = got["state"] or {}
        if not state.get("forum", True):
            raise AccountError("La discussion de cet événement est fermée.")
        # Personnes que j'ai bloquées (App Store 1.2) : texte, photo et vocal masqués, épinglés retirés.
        hidden = {b.get("blocked_id") for b in got["blocks"] or []}
        messages = [{**m, "body": BLOCKED_TEXT, "photo_path": None, "audio_path": None} if m.get("user_id") in hidden else m
                    for m in reversed(got["messages"] or [])]
        people = {p["id"]: p for p in got["people"] or []}
        ids = ",".join(m["id"] for m in messages)
        second = {
            "reactions": POOL.submit(self._rows, f"/rest/v1/message_reactions?select=message_id,user_id,emoji"
                                                 f"&message_id=in.({ids})", token) if ids else None,
            "photos": POOL.submit(self.chats._cached_sign, "chat-photos",
                                  [p for m in messages if not m.get("deleted_at") for p in (m.get("photo_path"), m.get("audio_path"))],
                                  lambda paths: self.chats._sign(paths, token)),
            "faces": POOL.submit(self.chats._cached_sign, "profile-photos", [p.get("avatar_url") for p in people.values()],
                                 lambda paths: self.admin._photos(paths, token)),
        }
        reactions = second["reactions"].result() if second["reactions"] else []
        photos, faces = second["photos"].result(), second["faces"].result()

        def name(uid: str) -> str:
            return (people.get(uid) or {}).get("display_name") or "?"

        def face(uid: str) -> str | None:
            return faces.get((people.get(uid) or {}).get("avatar_url") or "")

        by_id = {m["id"]: m for m in messages}
        staff = bool(state.get("staff"))
        out = [GroupChats._message({**m, "deleted_by_admin": False}, by_id, me, name, face, photos, reactions) for m in messages]
        highlights = [{"id": m["id"], "author_name": name(m["user_id"]), "at": m["created_at"], "text": preview(m),
                       "announcement": bool(m.get("announcement"))}
                      for m in reversed(got["highlights"] or []) if not m.get("deleted_at") and m.get("user_id") not in hidden]
        return {
            "id": event_id, "name": state.get("title") or "Événement", "me": me, "event": True,
            "member": bool(state.get("write")), "admin": staff, "organizer": staff, "everyone": "staff",
            "moderate": bool(state.get("moderate")),
            "notify": "none" if state.get("muted") else "all", "can_name_admins": False, "reactions": list(REACTIONS),
            "tags": list(TAGS) if staff else [],
            "members": [{"id": u, "name": name(u), "photo": face(u), "admin": False, "creator": False,
                         "organizer": bool(p.get("organizer")), "phone": None,
                         "rsvp": p.get("rsvp"), "invited": bool(p.get("invited"))}
                        for u, p in sorted(people.items(), key=lambda kv: (kv[1].get("display_name") or "").lower())],
            "messages": out,
            "highlights": highlights,
            # Temps réel : le signal de l'événement (canal public event:<id>, migration 20261116140000), sans contenu.
            "realtime": {"url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket", "key": SUPABASE_ANON_KEY},
        }

    def send(self, token: str, event_id: str, body: str, reply_to: str | None, photo_path: str | None,
             mentions: list[str] | None, message_id: str | None, audio_path: str | None, audio_seconds: float | None,
             announcement: bool) -> dict:
        """Envoi d'un message ; la base garde seulement les citations et les annonces permises (guard_message_change)."""
        if not body and not photo_path and not audio_path:
            raise AccountError("Écris un message, choisis une photo ou enregistre un vocal.")
        for path in (photo_path, audio_path):
            if path and not path.startswith(f"{event_id}/"):
                raise AccountError("Fichier invalide.")
        me = self.admin.accounts._uid(token)
        if mentions is None:
            people = {p["id"]: p.get("display_name") or "" for p in self._people(token, event_id)}
            mentions = mentions_in(body, people, me)
        row = {"event_id": event_id, "user_id": me, "body": body, "reply_to": reply_to, "photo_path": photo_path,
               "mentions": mentions, "announcement": announcement}
        if audio_path:
            row.update(audio_path=audio_path, audio_seconds=round(min(max(audio_seconds or 0, 0), AUDIO_MAX_SECONDS), 1))
        if message_id:
            row["id"] = message_id
        r = self.admin._call("POST", "/rest/v1/messages", token, json=row, headers={"Prefer": "return=minimal"})
        if r.status_code not in OK:
            raise refusal(r, "Le message n'a pas pu être envoyé. Réessaie.")
        return {"ok": True}

    def react(self, token: str, message_id: str, emoji: str, on: bool) -> dict:
        if emoji not in REACTIONS:
            raise AccountError("Réaction inconnue.")
        if on:
            r = self.admin._call("POST", "/rest/v1/message_reactions", token, json={"message_id": message_id, "emoji": emoji,
                                                                                       "user_id": self.admin.accounts._uid(token)},
                                 headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        else:
            r = self.admin._call("DELETE", "/rest/v1/message_reactions", token,
                                 params={"message_id": f"eq.{message_id}", "user_id": f"eq.{self.admin.accounts._uid(token)}",
                                         "emoji": f"eq.{emoji}"})
        if r.status_code not in OK:
            raise refusal(r, "La réaction n'a pas pu être enregistrée.")
        return {"ok": True}

    def _update(self, token: str, message_id: str, change: dict, fallback: str) -> dict:
        r = self.admin._call("PATCH", "/rest/v1/messages", token, params={"id": f"eq.{message_id}"}, json=change,
                             headers={"Prefer": "return=representation"})
        if r.status_code not in OK:
            raise refusal(r, fallback)
        if not r.json():  # la règle de la base n'a laissé passer aucune ligne
            raise AccountError(fallback)
        return {"ok": True}

    def pin(self, token: str, message_id: str, pin: bool) -> dict:
        return self._update(token, message_id, {"pinned": pin}, "Épingler est réservé à l'organisation de l'événement.")

    def delete(self, token: str, message_id: str) -> dict:
        """Son message, ou n'importe lequel pour l'organisation (comme la page web)."""
        when = datetime.now(timezone.utc).isoformat()
        return self._update(token, message_id, {"deleted_at": when}, "Ce message n'a pas pu être supprimé.")

    def notify(self, token: str, event_id: str, level: str) -> dict:
        """« Rien » = notifications coupées pour cet événement (event_mutes, le même réglage que sa fiche)."""
        if level not in ("all", "none"):
            raise AccountError("Choix inconnu.")
        me = self.admin.accounts._uid(token)
        if level == "none":
            r = self.admin._call("POST", "/rest/v1/event_mutes", token, json={"event_id": event_id, "user_id": me},
                                 headers={"Prefer": "return=minimal,resolution=ignore-duplicates"})
        else:
            r = self.admin._call("DELETE", "/rest/v1/event_mutes", token, params={"event_id": f"eq.{event_id}", "user_id": f"eq.{me}"})
        if r.status_code not in OK:
            raise refusal(r, "Le réglage n'a pas pu être enregistré.")
        return {"notify": level}

    def upload_photo(self, token: str, event_id: str, data: bytes) -> dict:
        return self.chats.upload_photo(token, event_id, data)

    def upload_audio(self, token: str, event_id: str, data: bytes) -> dict:
        return self.chats.upload_audio(token, event_id, data)
