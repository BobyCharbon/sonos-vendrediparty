"""Modération commune pour l'app iOS native (Signaler, Personnes bloquées, conditions d'utilisation, écran admin
« Signalements ») : le serveur relaie avec la session du membre ; la base décide de tout (droits, RLS, filtre).
Le module web (Expo) appelle les mêmes fonctions de la base directement."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .accounts import AccountError
from .group_admin import GroupAdmin
from .group_chats import GroupChats

UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
KINDS = ("group_message", "direct_message", "event_message", "profile", "profile_photo", "event",
         "pet_name", "pet_item", "pet_offer", "pet_showcase", "pet_word")
REASONS = {
    "harassment": "Harcèlement",
    "shocking": "Contenu choquant",
    "spam": "Spam",
    "scam": "Arnaque ou vente",
    "other": "Autre",
}
ACTIONS = ("hide", "warn", "suspend", "ban", "dismiss")
STATUSES = ("open", "actioned", "dismissed", "all")
QUEUE_LIMIT = 150
TERMS_PATH = "/events/terms"


class MemberToken(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


class ReportBody(MemberToken):
    kind: Literal[KINDS]
    target: str = Field(min_length=1, max_length=100)
    reason: Literal[tuple(REASONS)]
    comment: str = Field(default="", max_length=500)


class BlockBody(MemberToken):
    user_id: str = Field(pattern=UUID)
    on: bool


class TermsBody(MemberToken):
    version: str = Field(min_length=1, max_length=20)


class QueueBody(MemberToken):
    status: Literal[STATUSES] = "open"


class ActBody(MemberToken):
    report_id: str = Field(pattern=UUID)
    action: Literal[ACTIONS]
    note: str = Field(default="", max_length=500)
    days: int | None = Field(default=None, ge=1, le=365)


class LiftBody(MemberToken):
    user_id: str = Field(pattern=UUID)


class SettingsBody(MemberToken):
    contact_email: str | None = Field(default=None, max_length=200)
    terms_enforced: bool | None = None


class Moderation:
    def __init__(self, admin: GroupAdmin, chats: GroupChats):
        self.admin = admin
        self.chats = chats

    def report(self, token: str, kind: str, target: str, reason: str, comment: str) -> dict:
        rid = self.admin._rpc(token, "report_content", {"p_kind": kind, "p_target": target, "p_reason": reason,
                                                        "p_comment": comment.strip() or None},
                              "Le signalement n'a pas pu être envoyé. Réessaie.")
        return {"id": rid, "ok": True}

    def blocks(self, token: str) -> dict:
        rows = self.admin._rpc(token, "my_blocks", {}, "La liste n'a pas pu être lue.") or []
        faces = self.admin._photos([r.get("avatar_url") for r in rows], token)
        return {"blocks": [{"id": r["id"], "name": (r.get("display_name") or "").strip() or "Profil à compléter",
                            "photo": faces.get(r.get("avatar_url") or ""), "at": r.get("at")} for r in rows]}

    def block(self, token: str, user_id: str, on: bool) -> dict:
        self.admin._rpc(token, "set_block", {"target": user_id, "blocked": on},
                        "Le blocage n'a pas pu être enregistré." if on else "Le déblocage n'a pas pu être enregistré.")
        return self.blocks(token)

    def terms(self, token: str | None = None) -> dict:
        info = (self.admin._rpc(token, "my_terms", {}, "Les conditions n'ont pas pu être lues.") if token else None) or {}
        return {**info, "url": TERMS_PATH}

    def accept(self, token: str, version: str) -> dict:
        info = self.admin._rpc(token, "accept_terms", {"p_version": version}, "L'acceptation n'a pas été enregistrée.") or {}
        return {**info, "url": TERMS_PATH}

    def queue(self, token: str, status: str) -> dict:
        rows = self.admin._rpc(token, "moderation_queue", {"p_status": status, "p_limit": QUEUE_LIMIT},
                               "Les signalements n'ont pas pu être lus.") or []
        snaps = [r.get("snapshot") or {} for r in rows]
        photos = self.chats._sign([p for s in snaps for p in (s.get("photo_path"),) if p and not s.get("place") == "Profil"], token)
        avatars = self.admin._photos([s.get("photo_path") for s in snaps if s.get("place") == "Profil"]
                                     + [(r.get("target_user") or {}).get("avatar_url") for r in rows], token)
        return {"reports": [self._report(r, photos, avatars) for r in rows],
                "settings": self.admin._rpc(token, "moderation_public_info", {}, "") or {}}

    @staticmethod
    def _report(r: dict, photos: dict, avatars: dict) -> dict:
        snap = r.get("snapshot") or {}
        user = r.get("target_user") or {}
        path = snap.get("photo_path")
        return {
            "id": r["id"], "kind": r["kind"], "target_id": r.get("target_id"), "reason": r["reason"],
            "reason_label": REASONS.get(r["reason"], r["reason"]), "comment": r.get("comment"),
            "status": r["status"], "resolution": r.get("resolution"), "note": r.get("note"),
            "created_at": r.get("created_at"), "handled_at": r.get("handled_at"), "handled_by": r.get("handled_by"),
            "reporter": (r.get("reporter") or {}).get("name") or "Compte supprimé",
            "text": snap.get("text") or "", "place": snap.get("place") or "",
            "photo": (avatars if snap.get("place") == "Profil" else photos).get(path or ""),
            "photo_path": path,
            "user": {"id": user.get("id"), "name": user.get("name") or "Compte supprimé",
                     "photo": avatars.get(user.get("avatar_url") or ""), "status": user.get("status")} if user else None,
            "same_target": r.get("same_target") or 1, "user_reports": r.get("user_reports") or 0,
            "sanctions": r.get("sanctions") or [],
        }

    def act(self, token: str, report_id: str, action: str, note: str, days: int | None, status: str) -> dict:
        done = self.admin._rpc(token, "moderation_act", {"p_report": report_id, "p_action": action,
                                                         "p_note": note.strip() or None, "p_days": days},
                               "L'action n'a pas été enregistrée.") or {}
        if done.get("remove_photo"):
            r = self.admin._call("DELETE", "/storage/v1/object/profile-photos", token, json={"prefixes": [done["remove_photo"]]})
            if r.status_code not in (200, 204):
                raise AccountError("La photo n'a pas pu être retirée. Réessaie.")
        return self.queue(token, status)

    def lift(self, token: str, user_id: str, status: str = "open") -> dict:
        self.admin._rpc(token, "moderation_lift", {"p_user": user_id}, "Le compte n'a pas pu être réintégré.")
        return self.queue(token, status)

    def settings(self, token: str, contact_email: str | None, terms_enforced: bool | None) -> dict:
        self.admin._rpc(token, "set_moderation_settings", {"p_contact_email": contact_email, "p_terms_enforced": terms_enforced},
                        "Le réglage n'a pas été enregistré.")
        return self.queue(token, "open")


def router(moderation: Moderation) -> APIRouter:
    api = APIRouter(prefix="/api/account/moderation")

    def call(work, status: int = 400):
        try:
            return work()
        except AccountError as e:
            raise HTTPException(status, str(e))

    @api.post("/report")
    def report(body: ReportBody):
        """« Signaler » : un message, un profil, une photo de profil (et bientôt le Compagnon)."""
        return call(lambda: moderation.report(body.token, body.kind, body.target, body.reason, body.comment))

    @api.post("/blocks")
    def blocks(body: MemberToken):
        """Réglages › Confidentialité › Personnes bloquées."""
        return call(lambda: moderation.blocks(body.token), 401)

    @api.post("/block")
    def block(body: BlockBody):
        """Bloquer / débloquer (blocage commun à toute l'app) ; renvoie la liste à jour."""
        return call(lambda: moderation.block(body.token, body.user_id, body.on))

    @api.post("/terms")
    def terms(body: MemberToken):
        return call(lambda: moderation.terms(body.token), 401)

    @api.post("/terms/accept")
    def accept(body: TermsBody):
        return call(lambda: moderation.accept(body.token, body.version))

    @api.post("/queue")
    def queue(body: QueueBody):
        """Écran admin « Signalements » (droit « Modérer les signalements »)."""
        return call(lambda: moderation.queue(body.token, body.status), 403)

    @api.post("/act")
    def act(body: ActBody, status: Literal[STATUSES] = "open"):
        return call(lambda: moderation.act(body.token, body.report_id, body.action, body.note, body.days, status))

    @api.post("/lift")
    def lift(body: LiftBody):
        return call(lambda: moderation.lift(body.token, body.user_id))

    @api.post("/settings")
    def settings(body: SettingsBody):
        return call(lambda: moderation.settings(body.token, body.contact_email, body.terms_enforced))

    return api
