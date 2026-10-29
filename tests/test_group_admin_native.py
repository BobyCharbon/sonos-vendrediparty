"""Réglages natifs › Administration du groupe : relais vers Supabase avec la session du membre, mis en forme pour l'app."""
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, group_admin as ga, main

ME, LEA, TOM = "u-me", "u-lea", "u-tom"
EV = "11111111-1111-1111-1111-111111111111"
LEA_ID = "22222222-2222-2222-2222-222222222222"


def fake(perms=("events.approve", "members.approve", "group.settings"), rank=4, patch_rows=None):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), body))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path == "/rest/v1/rpc/my_permissions":
            return httpx.Response(200, json=list(perms))
        if path == "/rest/v1/rpc/my_rank":
            return httpx.Response(200, json=rank)
        if path == "/rest/v1/events":
            return httpx.Response(200, json=[{"id": EV, "title": "Raclette", "created_at": "2026-10-29T10:00:00Z",
                                              "date_mode": "poll", "starts_at": None, "max_participants": 12,
                                              "author": {"display_name": "Tom"}, "date_options": [{"id": 1}, {"id": 2}], "polls": []}])
        if path == "/rest/v1/join_requests":
            return httpx.Response(200, json=[{"user_id": LEA, "message": "Coucou", "created_at": "2026-10-29T09:00:00Z"},
                                             {"user_id": "inconnu", "message": None, "created_at": "2026-10-29T09:00:00Z"}])
        if path == "/rest/v1/rpc/get_member_directory":
            return httpx.Response(200, json=[{"id": LEA, "display_name": "Léa", "first_name": "Léa", "last_name": "M",
                                              "avatar_url": "lea.jpg", "role": "guest", "status": "pending"},
                                             {"id": TOM, "display_name": "Tom", "role": "member", "status": "active"}])
        if path == "/rest/v1/group_settings":
            if request.method == "PATCH":
                return httpx.Response(200, json=[{"require_approval": body["require_approval"]}])
            return httpx.Response(200, json=[{"require_approval": True}])
        if path == "/storage/v1/object/sign/profile-photos":
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/profile-photos/{p}?t=1"} for p in body["paths"]])
        if path == "/rest/v1/rpc/admin_member_list":
            return httpx.Response(200, json=[{"id": ga.ROOT_ID, "display_name": "Boby", "role": "admin", "status": "active", "beta": True},
                                             {"id": LEA, "display_name": "Léa", "role": "basic", "status": "active"}])
        if path == "/rest/v1/beta_testers":
            return httpx.Response(200, json=[{"user_id": TOM}])
        if path == "/rest/v1/profiles" and request.method == "PATCH":
            return httpx.Response(200, json=patch_rows if patch_rows is not None else [{"id": LEA}])
        if path == "/rest/v1/permissions":
            return httpx.Response(200, json=[{"key": "events.approve", "grp": "Événements", "label": "Valider", "hint": None, "sort": 1}])
        if path == "/rest/v1/role_permissions":
            return httpx.Response(200, json=[{"role": "organizer", "perm": "events.approve"}])
        if path == "/rest/v1/rpc/admin_member_audit":
            return httpx.Response(200, json=[{"id": 9, "at": "2026-10-29T08:00:00Z", "action": "member.role", "actor": ME,
                                              "actor_name": "Boby", "target": LEA, "target_name": "Léa",
                                              "details": {"from": "guest", "to": "basic"}}])
        if path == "/rest/v1/rpc/decide_join_request" and body["member"] == "refuse":
            return httpx.Response(400, json={"message": "profile_incomplete: nom, prénom"})
        if path.startswith("/rest/v1/rpc/"):
            return httpx.Response(204)
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    return ga.GroupAdmin(acc), seen


def test_overview_lists_proposals_requests_and_rule_by_permission():
    admin, _ = fake()
    out = admin.overview("tok")
    assert out["rank"] == 4 and out["require_approval"] is True
    assert out["events"] == [{"id": EV, "title": "Raclette", "at": "2026-10-29T10:00:00Z", "author": "Tom",
                              "summary": "Date à définir · 2 créneau(x) · 12 places", "starts_at": None}]
    [lea] = out["requests"]  # demande d'une personne absente de l'annuaire : ignorée
    assert lea["name"] == "Léa" and lea["message"] == "Coucou" and lea["photo"].endswith("lea.jpg?t=1")
    assert lea["complete"] is True


def test_overview_without_rights_reads_nothing_more():
    admin, seen = fake(perms=(), rank=1)
    out = admin.overview("tok")
    assert out["events"] == [] and out["requests"] == [] and out["require_approval"] is None
    assert not any(s[1] in ("/rest/v1/events", "/rest/v1/join_requests", "/rest/v1/group_settings") for s in seen)


def test_decisions_call_the_database_functions():
    admin, seen = fake()
    admin.decide_event("tok", EV, False, "Trop tôt")
    admin.decide_request("tok", LEA, True)
    admin.set_require_approval("tok", False)
    calls = {s[1]: s[3] for s in seen if s[0] in ("POST", "PATCH")}
    assert calls["/rest/v1/rpc/reject_event"] == {"e": EV, "reason": "Trop tôt"}
    assert calls["/rest/v1/rpc/decide_join_request"] == {"member": LEA, "accept": True}
    assert calls["/rest/v1/group_settings"] == {"require_approval": False}


def test_database_refusal_becomes_a_readable_message():
    admin, _ = fake()
    try:
        admin.decide_request("tok", "refuse", True)
    except accounts_mod.AccountError as e:
        assert "nom, son prénom" in str(e)
    else:
        raise AssertionError("refus attendu")


def test_members_full_list_for_admins_marks_root_and_basic_role():
    admin, _ = fake()
    out = admin.members("tok")
    assert out["full"] is True
    assert [(p["name"], p["role"], p["root"], p["beta"]) for p in out["people"]] == [
        ("Boby", "admin", True, True), ("Léa", "basic", False, False)]


def test_members_directory_for_organizers_with_beta_flags():
    admin, seen = fake(perms=("members.roles",), rank=2)
    out = admin.members("tok")
    assert out["full"] is False and {p["name"]: p["beta"] for p in out["people"]} == {"Léa": False, "Tom": True}
    assert not any(s[1] == "/rest/v1/rpc/admin_member_list" for s in seen)


def test_member_role_change_only_reads_back_the_id():
    admin, seen = fake()
    admin.update_member("tok", LEA, "guestplus", None, None)
    patch = next(s for s in seen if s[0] == "PATCH" and s[1] == "/rest/v1/profiles")
    assert patch[2] == f"id=eq.{LEA}&select=id" and patch[3] == {"role": "guestplus"}


def test_member_update_out_of_reach_is_refused():
    admin, _ = fake(patch_rows=[])
    try:
        admin.update_member("tok", LEA, "member", None, None)
    except accounts_mod.AccountError as e:
        assert "pas le droit" in str(e)
    else:
        raise AssertionError("refus attendu")


def test_roles_only_below_my_rank_and_journal_in_words():
    admin, _ = fake(rank=3)
    roles = admin.roles("tok")
    assert roles["editable"] == ["organizer", "member", "basic", "guestplus", "guest"]
    assert roles["grants"]["organizer"] == ["events.approve"] and roles["grants"]["admin"] == []
    journal = admin.journal("tok", None, None)
    assert journal == {"entries": [{"id": 9, "at": "2026-10-29T08:00:00Z", "text": "Boby a passé Léa de Guest à Membre"}], "more": False}


def test_link_tells_the_app_about_group_admin_rights():
    admin, _ = fake(perms=("members.approve",))
    account = admin.accounts.link("tok")
    assert account["group_admin"] is True and account["admin"] is False


class Fake:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, *args[1:]))
            return {"ok": name}
        return call


def test_routes_validate_and_relay(monkeypatch):
    f = Fake()
    monkeypatch.setattr(main, "group_admin", f)
    client = TestClient(main.app)
    assert client.post("/api/account/group-admin", json={"token": "t"}).json() == {"ok": "overview"}
    assert client.post("/api/account/group-admin/member", json={"token": "t", "id": LEA_ID, "role": "basic"}).status_code == 200
    assert f.calls[-1] == ("update_member", LEA_ID, "basic", None, None)
    assert client.post("/api/account/group-admin/member", json={"token": "t", "id": LEA_ID, "role": "root"}).status_code == 422
    assert client.post("/api/account/group-admin/permission", json={"token": "t", "role": "admin", "perm": "x;drop", "on": True}).status_code == 422
    client.post("/api/account/group-admin/event", json={"token": "t", "id": LEA_ID, "yes": False, "reason": "  Non  "})
    assert f.calls[-1] == ("decide_event", LEA_ID, False, "Non")
    client.post("/api/account/group-admin/journal", json={"token": "t", "member": LEA_ID})
    assert f.calls[-1] == ("journal", LEA_ID, None)


def test_journal_group_without_name_never_shows_none():
    line = ga.describe({"action": "group.remove", "actor": "a", "actor_name": "Boby", "target": "t", "target_name": "Léa",
                        "details": {"group": None}})
    assert line == "Boby a retiré Léa du groupe « ? »"
