"""Administration du groupe pour l'app iOS native : demandes d'adhésion, propositions d'événements, membres,
rôles et droits, journal. Tout passe par la session du membre : la base (droits, règles RLS, fonctions) décide
de ce qu'il voit et peut faire ; le serveur ne fait que relayer et mettre en forme."""
import httpx

from .accounts import SUPABASE_URL, AccountError, Accounts

ROOT_ID = "298ff6e0-07b2-4127-bb69-d254dd63a3d5"
FULL_ACCESS_RANK = 4   # Root (99) et Admin (4) : liste complète, numéros, suppression, journal
JOURNAL_PAGE = 100
PHOTO_TTL = 3600
ROLES = ("guest", "basic", "member", "organizer", "coadmin", "admin")
RANKS = {"guest": 0, "basic": 0, "member": 1, "organizer": 2, "coadmin": 3, "admin": 4}
ROLE_LABELS = {"guest": "Guest", "basic": "Membre", "member": "Membre VIP", "organizer": "Organisateur",
               "coadmin": "Co-admin", "admin": "Admin"}
STATUS_LABELS = {"active": "actif", "banned": "accès retiré", "pending": "en attente"}
ERRORS = {  # exception de la base → phrase pour l'écran
    "last_admin": "Désigne d'abord un autre administrateur actif.",
    "profile_incomplete": "Ce compte doit d'abord renseigner son nom, son prénom, son surnom et sa photo.",
    "confirm": "Le surnom tapé ne correspond pas.",
}
OK = (200, 201, 204)


def complete(p: dict) -> bool:
    """Nom, prénom, surnom et photo : obligatoires pour passer au-dessus de Guest (même règle que guard_profile)."""
    return all((p.get(k) or "").strip() for k in ("first_name", "last_name", "display_name", "avatar_url"))


def readable(r: httpx.Response, fallback: str) -> str:
    try:
        message = str(r.json().get("message", ""))
    except (ValueError, AttributeError):
        message = ""
    for key, text in ERRORS.items():
        if key in message:
            return text
    return message.removeprefix("forbidden: ") or fallback


def _role(r) -> str:
    return ROLE_LABELS.get(str(r), str(r if r is not None else "?"))


def _status(s) -> str:
    return STATUS_LABELS.get(str(s), str(s if s is not None else "?"))


def describe(e: dict) -> str:
    """Ligne du journal en phrase : « Boby a passé Tom de Guest à Membre VIP » (comme le module web)."""
    who = e.get("actor_name") or ("Compte supprimé" if e.get("actor") else "Système")
    target = e.get("target_name") or ("compte supprimé" if e.get("target") else "")
    d = e.get("details") or {}
    action = e.get("action")
    if action == "account.created":
        return f"{target or 'Nouveau compte'} a créé son compte"
    if action == "account.login":
        device = f" ({str(d['device'])[:40]})" if d.get("device") else ""
        return f"{target or 'Un compte'} s'est connecté{device}"
    if action == "account.deleted":
        if d.get("by") == "self":
            return f"{target} a supprimé son compte"
        end = f" (numéro …{d['phone_end']})" if d.get("phone_end") else ""
        return f"{who} a supprimé le compte de {target}{end}"
    if action == "member.role":
        return f"{who} a passé {target} de {_role(d.get('from'))} à {_role(d.get('to'))}"
    if action == "member.status":
        return f"{who} : {target} {_status(d.get('from'))} → {_status(d.get('to'))}"
    if action == "member.beta":
        on = d.get("enabled")
        return f"{who} a {'ajouté' if on else 'retiré'} {target} {'aux' if on else 'des'} bêta-testeurs"
    if action == "group.add":
        return f"{who} a ajouté {target} au groupe « {d.get('group', '?')} »"
    if action == "group.remove":
        return f"{who} a retiré {target} du groupe « {d.get('group', '?')} »"
    if action == "members.viewed":
        return f"{who} a ouvert la liste des membres (numéros compris)"
    return f"{who} : {action}" + (f" · {target}" if target else "")


def event_summary(e: dict) -> str:
    """Ce qui suit la date (affichée par l'app dans le format du téléphone)."""
    parts = [f"Date à définir · {len(e.get('date_options') or [])} créneau(x)"] if e.get("date_mode") == "poll" else []
    if e.get("polls"):
        parts.append(f"{len(e['polls'])} sondage(s)")
    if e.get("max_participants"):
        parts.append(f"{e['max_participants']} places")
    return " · ".join(p for p in parts if p)


def _names(p: dict) -> dict:
    return {"id": p["id"], "name": (p.get("display_name") or "").strip(),
            "full_name": " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x),
            "phone": p.get("phone"), "complete": complete(p)}


class GroupAdmin:
    def __init__(self, accounts: Accounts):
        self.accounts = accounts

    def _call(self, method: str, path: str, token: str, **kw) -> httpx.Response:
        return self.accounts._get(method, path, token, **kw)

    def _rows(self, path: str, token: str) -> list:
        r = self._call("GET", path, token)
        rows = r.json() if r.status_code == 200 else None
        if not isinstance(rows, list):
            raise AccountError("L'administration n'a pas pu être lue. Réessaie dans un instant.")
        return rows

    def _rpc(self, token: str, name: str, args: dict, fallback: str = "La modification n'a pas été enregistrée. Réessaie."):
        r = self._call("POST", f"/rest/v1/rpc/{name}", token, json=args)
        if r.status_code not in OK:
            raise AccountError(readable(r, fallback))
        return r.json() if r.content else None

    def _write(self, method: str, path: str, token: str, body: dict, fallback: str) -> httpx.Response:
        r = self._call(method, path, token, json=body, headers={"Prefer": "return=representation"})
        if r.status_code not in OK:
            raise AccountError(readable(r, fallback))
        if r.status_code == 200 and r.json() == []:  # règles de la base : ligne hors de portée, rien n'a changé
            raise AccountError("Tu n'as pas le droit de faire cette modification.")
        return r

    def access(self, token: str) -> dict:
        """Mes droits et mon rang (invité 0 … admin 4, root 99) : ce que l'écran affiche."""
        uid = self.accounts._uid(token)
        perms = self._rpc(token, "my_permissions", {}, "Tes droits n'ont pas pu être lus.") or []
        rank = self._rpc(token, "my_rank", {}, "Tes droits n'ont pas pu être lus.")
        return {"me": uid, "perms": sorted(perms), "rank": rank if isinstance(rank, int) else -1}

    def _photos(self, paths: list, token: str) -> dict[str, str]:
        """Liens signés des photos de profil, en une seule requête."""
        paths = sorted({p for p in paths if p})
        if not paths:
            return {}
        r = self._call("POST", "/storage/v1/object/sign/profile-photos", token, json={"expiresIn": PHOTO_TTL, "paths": paths})
        rows = r.json() if r.status_code == 200 else []
        return {row["path"]: SUPABASE_URL + "/storage/v1" + row["signedURL"]
                for row in rows if isinstance(row, dict) and row.get("signedURL") and row.get("path")}

    def overview(self, token: str) -> dict:
        """Accueil : propositions à valider, demandes d'adhésion, règles du groupe, selon mes droits."""
        me = self.access(token)
        perms = set(me["perms"])
        out = {**me, "events": [], "requests": [], "require_approval": None}
        if "events.approve" in perms:
            rows = self._rows("/rest/v1/events?select=id,title,created_at,date_mode,starts_at,max_participants,"
                              "author:profiles!events_created_by_fkey(display_name),date_options(id),polls(id)"
                              "&status=eq.pending&order=created_at", token)
            out["events"] = [{"id": e["id"], "title": e.get("title") or "Sans titre", "at": e.get("created_at"),
                              "author": (e.get("author") or {}).get("display_name") or "?", "summary": event_summary(e),
                              "starts_at": e.get("starts_at") if e.get("date_mode") != "poll" else None}
                             for e in rows]
        if "members.approve" in perms:
            requests = self._rows("/rest/v1/join_requests?select=user_id,message,created_at&status=eq.pending&order=created_at", token)
            directory = {p["id"]: p for p in self._rows("/rest/v1/rpc/get_member_directory", token)}
            known = [(r, directory[r["user_id"]]) for r in requests if r["user_id"] in directory]
            photos = self._photos([p.get("avatar_url") for _, p in known], token)
            out["requests"] = [{**_names(p), "photo": photos.get(p.get("avatar_url") or ""),
                                "message": r.get("message"), "at": r.get("created_at")} for r, p in known]
        if "group.settings" in perms:
            rows = self._rows("/rest/v1/group_settings?select=require_approval", token)
            out["require_approval"] = bool(rows and rows[0].get("require_approval"))
        return out

    def decide_event(self, token: str, event_id: str, approve: bool, reason: str | None) -> dict:
        if approve:
            self._rpc(token, "approve_event", {"e": event_id})
        else:
            self._rpc(token, "reject_event", {"e": event_id, "reason": reason or None})
        return self.overview(token)

    def decide_request(self, token: str, member: str, accept: bool) -> dict:
        self._rpc(token, "decide_join_request", {"member": member, "accept": accept})
        return self.overview(token)

    def set_require_approval(self, token: str, on: bool) -> dict:
        self._write("PATCH", "/rest/v1/group_settings?id=eq.true", token, {"require_approval": on},
                    "La règle n'a pas été enregistrée. Réessaie.")
        return self.overview(token)

    def members(self, token: str) -> dict:
        """Membres par rôle. Root et Admin : liste complète (numéros, connexions ; consultation journalisée)."""
        me = self.access(token)
        full = me["rank"] >= FULL_ACCESS_RANK
        if full:
            people = self._rpc(token, "admin_member_list", {}, "La liste des membres n'a pas pu être lue.") or []
        else:
            people = self._rows("/rest/v1/rpc/get_member_directory?order=display_name", token)
            beta = {b["user_id"] for b in self._rows("/rest/v1/beta_testers?select=user_id", token)}
            people = [{**p, "beta": p["id"] in beta} for p in people]
        photos = self._photos([p.get("avatar_url") for p in people], token)
        rows = [{**_names(p), "photo": photos.get(p.get("avatar_url") or ""),
                 "role": p.get("role") or "guest", "status": p.get("status") or "pending",
                 "beta": bool(p.get("beta")), "root": p["id"] == ROOT_ID,
                 "created_at": p.get("created_at"), "last_sign_in_at": p.get("last_sign_in_at")}
                for p in people]
        return {**me, "full": full, "people": sorted(rows, key=lambda p: (p["name"] or "~").lower())}

    def update_member(self, token: str, member: str, role: str | None, status: str | None, beta: bool | None) -> dict:
        if beta is not None:
            self._rpc(token, "set_beta_tester", {"member": member, "enabled": beta})
        patch = {k: v for k, v in (("role", role), ("status", status)) if v is not None}
        if patch:
            self._write("PATCH", f"/rest/v1/profiles?id=eq.{member}", token, patch,
                        "La modification n'a pas été enregistrée. Réessaie.")
        return self.members(token)

    def delete_member(self, token: str, member: str, confirm_name: str) -> dict:
        self._rpc(token, "admin_delete_member", {"member": member, "confirm_name": confirm_name})
        return self.members(token)

    def roles(self, token: str) -> dict:
        me = self.access(token)
        catalog = self._rows("/rest/v1/permissions?select=key,grp,label,hint,sort&order=sort", token)
        grants = self._rows("/rest/v1/role_permissions?select=role,perm", token)
        editable = [r for r in reversed(ROLES) if RANKS[r] < me["rank"]]
        return {**me, "editable": editable, "catalog": catalog,
                "grants": {r: sorted(g["perm"] for g in grants if g["role"] == r) for r in ROLES}}

    def set_permission(self, token: str, role: str, perm: str, on: bool) -> dict:
        self._rpc(token, "set_role_permission", {"target": role, "perm": perm, "granted": on})
        return self.roles(token)

    def journal(self, token: str, member: str | None, before: int | None) -> dict:
        rows = self._rpc(token, "admin_member_audit", {"member": member, "before": before, "lim": JOURNAL_PAGE},
                         "Le journal n'a pas pu être lu.") or []
        return {"entries": [{"id": e["id"], "at": e.get("at"), "text": describe(e)} for e in rows],
                "more": len(rows) == JOURNAL_PAGE}
