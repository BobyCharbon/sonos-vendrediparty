"""Pronos entre amis (avis f071c5f46e3d, 17.11.2026, migration 20261117180000) : pour l'honneur, jamais d'argent.

- Membres (app iPhone, écrans natifs) : POST /api/account/pronos/rpc relaie les fonctions prono_* (la base vérifie le
  compte, les droits, le blocage et garde les réponses cachées jusqu'au dévoilement).
- Lien partagé : GET /prono/<jeton> → page du module Événements qui fait se connecter puis jouer.
Toute adresse se construit depuis l'adresse publique du site : jamais un domaine écrit en dur."""
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .accounts import SUPABASE_ANON_KEY, SUPABASE_URL, AccountError, Accounts
from .agenda import ERROR_STATUS, Db, refusal
from .features import PATATES_SOON, patates_enabled

TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,40}$")
# Fonctions que l'app iPhone appelle par le serveur.
RELAY = {
    "prono_list", "prono_get", "prono_badge", "prono_suggestions", "prono_create", "prono_update", "prono_invite",
    "prono_set_link", "prono_link_info", "prono_join", "prono_answer", "prono_close_now", "prono_result", "prono_cancel",
    "prono_delete", "prono_board", "prono_board_reset", "prono_report_answer", "report_content",
    "my_groups_overview",  # « Qui joue » : mes groupes
    # Pronos v2 (18.11) : sac de patates, saison, contestation, réactions, trophée (se retirer), modèles.
    "prono_bag", "prono_bag_history", "prono_season", "prono_contest", "prono_contest_vote", "prono_react",
    "prono_optout", "prono_templates",
}
# Drapeau « patates » éteint : ces fonctions n'existent pas pour l'app, et aucune patate n'entre par les autres.
PATATES_ONLY = {"prono_bag", "prono_bag_history", "prono_season"}
PATATES_KEYS = {"prono_answer": ("answer", "stake"), "prono_create": ("body", "patates"), "prono_update": ("body", "patates")}
STATUS = {**ERROR_STATUS, "locked": 409, "profile_required": 403}
SIGNED_TTL = 3600       # lien d'une photo de profil
SIGNED_REUSE = 40 * 60  # le même lien d'une réponse à l'autre (pas de rechargement des photos)


def faces_in(value: Any) -> list[dict]:
    """Tous les visages {id, name, avatar_url} d'une réponse de la base, où qu'ils soient."""
    found: list[dict] = []
    if isinstance(value, dict):
        if "avatar_url" in value and "id" in value:
            found.append(value)
        for v in value.values():
            found += faces_in(v)
    elif isinstance(value, list):
        for v in value:
            found += faces_in(v)
    return found


class RelayBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    fn: str = Field(min_length=1, max_length=60)
    args: dict[str, Any] = Field(default_factory=dict)


def pronos_router(accounts: Accounts) -> APIRouter:
    db = Db(accounts)
    router = APIRouter()
    signed: dict[str, tuple[float, str]] = {}

    def sign_faces(data: Any, token: str) -> None:
        """L'app iPhone ne lit pas le compartiment privé des photos : chaque visage reçoit « photo », un lien signé
        (comme dans les Discussions)."""
        faces = faces_in(data)
        now = time.time()
        missing = sorted({f["avatar_url"] for f in faces if f.get("avatar_url")
                          and not (f["avatar_url"] in signed and now - signed[f["avatar_url"]][0] < SIGNED_REUSE)})
        if missing:
            try:
                r = accounts._get("POST", "/storage/v1/object/sign/profile-photos", token,
                                  json={"expiresIn": SIGNED_TTL, "paths": missing}, timeout=6.0)
                rows = r.json() if r.status_code == 200 else []
            except (AccountError, ValueError):
                rows = []
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict) and row.get("signedURL") and row.get("path"):
                    signed[row["path"]] = (now, SUPABASE_URL + "/storage/v1" + row["signedURL"])
            if len(signed) > 5000:
                for key in sorted(signed, key=lambda k: signed[k][0])[:1000]:
                    signed.pop(key, None)
        for f in faces:
            hit = signed.get(f.get("avatar_url") or "")
            f["photo"] = hit[1] if hit else None

    @router.post("/api/account/pronos/rpc")
    def relay(body: RelayBody):
        if body.fn not in RELAY:
            raise HTTPException(404, "Fonction inconnue")
        if body.fn == "report_content" and not str(body.args.get("p_kind", "")) == "prono":
            raise HTTPException(404, "Fonction inconnue")  # signaler un prono seulement (le reste a ses écrans)
        if not patates_enabled():
            if body.fn in PATATES_ONLY:
                raise HTTPException(404, PATATES_SOON)
            if body.fn in PATATES_KEYS:
                inner, key = PATATES_KEYS[body.fn]
                body.args.pop(key, None)
                if isinstance(body.args.get(inner), dict):
                    body.args[inner].pop(key, None)
        status, data = db.call(body.fn, body.args, body.token)
        if status in (200, 204):
            sign_faces(data, body.token)
            if body.fn == "prono_badge":  # l'app écoute ensuite les signaux prono:<id> / pronos:<groupe>
                return JSONResponse({"result": data, "realtime": {
                    "url": SUPABASE_URL.replace("https://", "wss://", 1) + "/realtime/v1/websocket", "key": SUPABASE_ANON_KEY}})
            return JSONResponse({"result": data})
        if status == 401:
            raise HTTPException(401, "Ta connexion a expiré. Reconnecte-toi.")
        code, text = refusal(data)
        if code == "error":
            raise HTTPException(503 if status >= 500 else 400, "Ça n'a pas marché. Réessaie dans un instant.")
        return JSONResponse({"code": code, "detail": text}, status_code=STATUS.get(code, 400))

    @router.get("/prono/{token}")
    def link(token: str):
        """Lien partagé (WhatsApp…) : la page du module Événements fait se connecter, puis jouer."""
        if not TOKEN.match(token):
            raise HTTPException(404, "Lien invalide")
        return RedirectResponse(f"/events/prono-invite/{token}", status_code=302, headers={"Cache-Control": "no-store"})

    return router
