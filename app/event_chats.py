"""Discussion d'un événement pour l'app iPhone native (demande de l'admin du 16.11.2026, migration 20261116180000).
Même forme qu'une discussion de groupe (app/group_chats.py) : l'app la montre avec le même écran, « event » = True.
Tout passe par la session du membre : la base (règles de messages, garde guard_message_change, fonctions
event_chat_state / event_chat_people) décide de qui lit, écrit, épingle, annonce et cite @toutlemonde / @present.
17.11 (migration 20261117190000) : niveau de notification (Tout / Mentions seulement / Rien), sourdine, non-lus,
« Qui peut écrire », description, carte de l'événement, médias / liens, recherche, messages plus anciens."""
import re
from datetime import datetime, timezone
from urllib.parse import quote

from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError
from .group_admin import OK, refusal
from .group_chats import AUDIO_MAX_SECONDS, BLOCKED_TEXT, HIGHLIGHTS, PAGE, POOL, REACTIONS, GroupChats, already_sent, mentions_in

# Citations spéciales de la discussion d'un événement (organisation seulement) : nom tapé après l'@ et explication.
TAGS = ({"tag": "toutlemonde", "hint": "Tout le monde : invités et participants"},
        {"tag": "present", "hint": "Les présents et les peut-être"},
        {"tag": "annonce", "hint": "Annonce épinglée en haut, envoyée à tous"})
LEVELS = ("all", "mentions", "none")
LINK = re.compile(r"https?://[^\s<>\"']+", re.I)


def preview(m: dict) -> str:
    return m.get("body") or ("🎤 Message vocal" if m.get("audio_path") else "📷 Photo")


def links_in(text: str | None) -> list[str]:
    """Liens http(s) d'un message (ponctuation finale retirée) ; jamais un autre schéma."""
    return [u.rstrip(".,;:!?)»") for u in LINK.findall(text or "")]


def muted_now(until) -> bool:
    """Sourdine en cours : « infinity » (toujours) ou une date à venir."""
    if not until:
        return False
    if str(until) == "infinity":
        return True
    try:
        return datetime.fromisoformat(str(until).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except ValueError:
        return False


# Discussion d'un événement réservée à ceux qui viennent (décision de l'admin du 19.11).
CHAT_FOR_GUESTS = "La discussion est réservée à ceux qui viennent : réponds Présent ou Peut-être pour la rejoindre."

class EventChats:
    def __init__(self, chats: GroupChats):
        self.chats = chats
        self.admin = chats.admin

    def _rows(self, path: str, token: str) -> list:
        return self.admin._rows(path, token)

    def _people(self, token: str, event_id: str) -> list:
        return self.admin._rpc(token, "event_chat_people", {"e": event_id}, "Les participants n'ont pas pu être lus.") or []

    def _blocked(self, token: str) -> set:
        """Personnes que j'ai bloquées (App Store 1.2) : masquées partout dans la discussion."""
        return {b.get("blocked_id") for b in self._rows("/rest/v1/direct_blocks?select=blocked_id", token) or []}

    def _faces(self, token: str, people: dict) -> dict:
        return self.chats._cached_sign("profile-photos", [p.get("avatar_url") for p in people.values()],
                                       lambda paths: self.admin._photos(paths, token))

    def _event(self, token: str, event_id: str) -> dict:
        """Ligne de l'événement pour la carte du haut ; illisible : carte faite de l'état seul."""
        try:
            rows = self._rows(f"/rest/v1/events?select=title,starts_at,ends_at,location_name,cover_url,created_by"
                              f"&id=eq.{event_id}", token)
        except AccountError:
            return {}
        return rows[0] if rows and isinstance(rows[0], dict) else {}

    def _page(self, token: str, event_id: str, me: str, raw: list, people: dict, hidden: set) -> list[dict]:
        """Messages (ordre chronologique) mis en forme pour l'app : personnes bloquées masquées (texte, photo, vocal),
        citations (même d'un message plus ancien que la page), réactions, photos et vocaux signés."""
        def mask(m: dict) -> dict:
            return {**m, "body": BLOCKED_TEXT, "photo_path": None, "audio_path": None} if m.get("user_id") in hidden else m

        messages = [mask(m) for m in raw]
        by_id = {m["id"]: m for m in messages}
        quoted = sorted({m["reply_to"] for m in messages if m.get("reply_to") and m["reply_to"] not in by_id})
        ids = ",".join(m["id"] for m in messages)
        jobs = {
            "quoted": POOL.submit(self._rows, f"/rest/v1/messages?select=*&event_id=eq.{event_id}"
                                              f"&id=in.({','.join(quoted)})", token) if quoted else None,
            "reactions": POOL.submit(self._rows, f"/rest/v1/message_reactions?select=message_id,user_id,emoji"
                                                 f"&message_id=in.({ids})", token) if ids else None,
            "photos": POOL.submit(self.chats._cached_sign, "chat-photos",
                                  [p for m in messages if not m.get("deleted_at") for p in (m.get("photo_path"), m.get("audio_path"))],
                                  lambda paths: self.chats._sign(paths, token)),
            "faces": POOL.submit(self._faces, token, people),
        }
        got = {k: f.result() if f else [] for k, f in jobs.items()}
        by_id.update({m["id"]: mask(m) for m in got["quoted"] or [] if m.get("id")})
        photos, faces = got["photos"], got["faces"]

        def name(uid: str) -> str:
            return (people.get(uid) or {}).get("display_name") or "?"

        def face(uid: str) -> str | None:
            return faces.get((people.get(uid) or {}).get("avatar_url") or "")

        return [GroupChats._message({**m, "deleted_by_admin": False}, by_id, me, name, face, photos, got["reactions"] or [])
                for m in messages]

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
            "blocks": POOL.submit(self._blocked, token),
            "event": POOL.submit(self._event, token, event_id),
        }
        got = {k: f.result() for k, f in jobs.items()}
        state = got["state"] or {}
        if not state.get("forum", True):
            raise AccountError("La discussion de cet événement est fermée.")
        if state.get("open") is False:  # réservée à Présent / Peut-être et à l'organisation (19.11)
            raise AccountError(CHAT_FOR_GUESTS)
        hidden = got["blocks"]
        people = {p["id"]: p for p in got["people"] or []}
        out = self._page(token, event_id, me, list(reversed(got["messages"] or [])), people, hidden)
        faces = self._faces(token, people)  # déjà signées par _page (cache)

        def name(uid: str) -> str:
            return (people.get(uid) or {}).get("display_name") or "?"

        staff = bool(state.get("staff"))
        highlights = [{"id": m["id"], "author_name": name(m["user_id"]), "at": m["created_at"], "text": preview(m),
                       "announcement": bool(m.get("announcement"))}
                      for m in reversed(got["highlights"] or []) if not m.get("deleted_at") and m.get("user_id") not in hidden]
        level = state.get("level") if state.get("level") in LEVELS else "mentions"
        ev = got["event"]
        cover = str(ev.get("cover_url") or "")
        rsvps = [p.get("rsvp") for p in people.values()]
        return {
            "id": event_id, "name": state.get("title") or ev.get("title") or "Événement", "me": me, "event": True,
            "member": bool(state.get("write")), "admin": staff, "organizer": staff, "everyone": "staff",
            "moderate": bool(state.get("moderate")),
            # Anciennes apps (16.11) : « Tout » ou « Rien » seulement ; « Rien » aussi en sourdine ou événement coupé.
            "notify": "none" if level == "none" or muted_now(state.get("muted_until")) or state.get("muted") else "all",
            "level": level, "muted_until": state.get("muted_until"), "unread": int(state.get("unread") or 0),
            "write_mode": "staff" if state.get("write_mode") == "staff" else "all",
            "description": state.get("description") or None,
            "can_write": bool(state.get("can_write", state.get("write"))),
            "event_card": {
                "title": ev.get("title") or state.get("title") or "Événement",
                "starts_at": ev.get("starts_at"), "ends_at": ev.get("ends_at"), "place": ev.get("location_name") or None,
                # Couverture publique (app/covers.py ou image de la page lue) : https seulement, comme la fiche web.
                "cover": cover if cover.startswith("https://") else None,
                "going": rsvps.count("yes"), "maybe": rsvps.count("maybe"),
                "organizer_name": (people.get(ev.get("created_by")) or {}).get("display_name"),
            },
            "can_name_admins": False, "reactions": list(REACTIONS),
            "tags": list(TAGS) if staff else [],
            "members": [{"id": u, "name": name(u), "photo": faces.get(p.get("avatar_url") or ""), "admin": False,
                         "creator": False, "organizer": bool(p.get("organizer")), "phone": None,
                         "rsvp": p.get("rsvp"), "invited": bool(p.get("invited"))}
                        for u, p in sorted(people.items(), key=lambda kv: (kv[1].get("display_name") or "").lower())],
            "messages": out,
            "highlights": highlights,
            # Temps réel : le signal de l'événement (canal public event:<id>, migration 20261116140000), sans contenu.
            "realtime": {"url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket", "key": SUPABASE_ANON_KEY},
        }

    def older(self, token: str, event_id: str, before_id: str) -> dict:
        """Page précédente (avant before_id), même forme que les messages de l'ouverture ; « more » : encore avant."""
        me = self.admin.accounts._uid(token)
        ref = self._rows(f"/rest/v1/messages?select=id,created_at&event_id=eq.{event_id}&id=eq.{before_id}", token)
        if not ref:
            raise AccountError("Ce message n'existe plus.")
        at = quote(str(ref[0]["created_at"]), safe="")
        jobs = {
            "messages": POOL.submit(self._rows, f"/rest/v1/messages?select=*&event_id=eq.{event_id}"
                                                f"&or=(created_at.lt.{at},and(created_at.eq.{at},id.lt.{before_id}))"
                                                f"&order=created_at.desc,id.desc&limit={PAGE}", token),
            "people": POOL.submit(self._people, token, event_id),
            "blocks": POOL.submit(self._blocked, token),
        }
        got = {k: f.result() for k, f in jobs.items()}
        raw = got["messages"] or []
        people = {p["id"]: p for p in got["people"] or []}
        return {"messages": self._page(token, event_id, me, list(reversed(raw)), people, got["blocks"]),
                "more": len(raw) >= PAGE}

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
        if r.status_code not in OK and not already_sent(r, row.get("id")):
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
        """Niveau de notification de cette discussion (event_chat_set_level) : Tout, Mentions seulement ou Rien.
        Anciennes apps (16.11) : « all » / « none » marchent toujours ; « Tout » rend aussi les notifications coupées
        depuis la fiche (event_mutes), comme avant (sinon une ancienne app restait bloquée sur « Rien »)."""
        if level not in LEVELS:
            raise AccountError("Choix inconnu.")
        got = self.admin._rpc(token, "event_chat_set_level", {"e": event_id, "level": level},
                              "Le réglage n'a pas pu être enregistré.")
        if level == "all":
            me = self.admin.accounts._uid(token)
            r = self.admin._call("DELETE", "/rest/v1/event_mutes", token, params={"event_id": f"eq.{event_id}", "user_id": f"eq.{me}"})
            if r.status_code not in OK:
                raise refusal(r, "Le réglage n'a pas pu être enregistré.")
        return {**(got if isinstance(got, dict) else {}), "level": level, "notify": "none" if level == "none" else "all"}

    def mute(self, token: str, event_id: str, until: str | None) -> dict:
        """Sourdine jusqu'à une date (ISO), « always » (toujours) ou null (réactiver)."""
        if until == "always":
            until = "infinity"
        elif until is not None:
            try:
                when = datetime.fromisoformat(until.replace("Z", "+00:00"))
            except ValueError:
                raise AccountError("Date de sourdine illisible.") from None
            until = (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).isoformat()
        got = self.admin._rpc(token, "event_chat_mute", {"e": event_id, "until": until}, "La sourdine n'a pas pu être enregistrée.")
        return got if isinstance(got, dict) else {"muted_until": until}

    def read(self, token: str, event_id: str) -> dict:
        got = self.admin._rpc(token, "event_chat_mark_read", {"e": event_id}, "La lecture n'a pas pu être notée.")
        return got if isinstance(got, dict) else {"unread": 0}

    def settings(self, token: str, event_id: str, write: str | None, description: str | None) -> dict:
        """« Qui peut écrire » et description : l'organisation de l'événement seulement (la base décide et filtre)."""
        if write is None and description is None:
            raise AccountError("Rien à changer.")
        got = self.admin._rpc(token, "event_chat_set_settings", {"e": event_id, "write": write, "description": description},
                              "Les réglages de la discussion n'ont pas pu être enregistrés.")
        return got if isinstance(got, dict) else {"ok": True}

    def _names(self, token: str, event_id: str) -> tuple[dict, set]:
        people, blocks = POOL.submit(self._people, token, event_id), POOL.submit(self._blocked, token)
        return {p["id"]: p.get("display_name") or "?" for p in people.result() or []}, blocks.result()

    def media(self, token: str, event_id: str, before: str | None) -> dict:
        """Photos et vocaux (liens signés de chat-photos) et liens des messages ; jamais ceux des personnes bloquées."""
        args = {"e": event_id, **({"before": before} if before else {})}
        job = POOL.submit(self.admin._rpc, token, "event_chat_media", args, "Les médias n'ont pas pu être lus.")
        names, hidden = self._names(token, event_id)
        rows = [r for r in job.result() or [] if isinstance(r, dict) and r.get("author") not in hidden]
        files = self.chats._cached_sign("chat-photos", [r.get("path") for r in rows if r.get("kind") in ("photo", "audio")],
                                        lambda paths: self.chats._sign(paths, token))
        items = []
        for r in rows:
            base = {"message_id": r.get("message_id"), "at": r.get("at"),
                    "author_name": names.get(r.get("author")) or r.get("author_name") or "?", "text": r.get("text") or None}
            if r.get("kind") in ("photo", "audio"):
                if files.get(r.get("path") or ""):
                    items.append({**base, "kind": r["kind"], "url": files[r["path"]]})
            elif r.get("kind") == "link" or r.get("body"):
                # Lien donné par la base (http(s) seulement), sinon les liens http trouvés dans le texte du message.
                urls = [r["url"]] if LINK.fullmatch(str(r.get("url") or "")) else links_in(r.get("body") or r.get("text"))
                items += [{**base, "kind": "link", "url": u} for u in urls]
        return {"items": items}

    def search(self, token: str, event_id: str, q: str) -> dict:
        """Recherche dans les messages (la base : 50 au plus, ni supprimés ni bloqués ; ici les bloqués sont retirés aussi)."""
        q = q.strip()
        if not q:
            return {"results": []}
        job = POOL.submit(self.admin._rpc, token, "event_chat_search", {"e": event_id, "q": q}, "La recherche n'a pas abouti.")
        names, hidden = self._names(token, event_id)
        return {"results": [{"message_id": r.get("message_id"), "at": r.get("at"),
                             "author_name": names.get(r.get("author")) or r.get("author_name") or "?",
                             "snippet": r.get("snippet") or ""}
                            for r in job.result() or [] if isinstance(r, dict) and r.get("author") not in hidden]}

    def upload_photo(self, token: str, event_id: str, data: bytes) -> dict:
        return self.chats.upload_photo(token, event_id, data)

    def upload_audio(self, token: str, event_id: str, data: bytes) -> dict:
        return self.chats.upload_audio(token, event_id, data)
