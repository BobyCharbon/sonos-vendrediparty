"""Réglages natifs › Groupes : mes groupes (créés ou dont je fais partie), en créer, les composer, les supprimer."""
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main

ME, LEA, TOM = "u-me", "u-lea", "u-tom"
G1 = "11111111-1111-1111-1111-111111111111"
G2 = "22222222-2222-2222-2222-222222222222"
VIP = "33333333-3333-3333-3333-333333333333"


def fake_supabase():
    seen = []

    def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), request.content))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path == "/rest/v1/member_groups" and request.method == "GET":
            return httpx.Response(200, json=[
                {"id": G1, "name": "Les footeux", "created_by": ME, "system_key": None, "member_group_members": [{"user_id": LEA}]},
                {"id": G2, "name": "Rando", "created_by": TOM, "system_key": None, "member_group_members": [{"user_id": ME}]},
                {"id": VIP, "name": "Vendredi Party", "created_by": None, "system_key": "vip", "member_group_members": [{"user_id": TOM}]},
            ])
        if path == "/rest/v1/rpc/get_member_directory":
            return httpx.Response(200, json=[{"id": ME, "display_name": "Boby", "status": "active"},
                                             {"id": LEA, "display_name": "Léa", "status": "active"},
                                             {"id": TOM, "display_name": "Tom", "status": "active"}])
        if path == "/rest/v1/rpc/my_permissions":
            return httpx.Response(200, json=[])
        if request.method == "POST" and path == "/rest/v1/member_groups":
            return httpx.Response(201, json=[{"id": G1}])
        if request.method in ("POST", "DELETE"):
            return httpx.Response(201 if request.method == "POST" else 204)
        return httpx.Response(404)

    return accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_my_groups_are_the_ones_i_created_or_belong_to():
    acc, _ = fake_supabase()
    result = acc.groups("tok")
    assert [(g["name"], g["mine"]) for g in result["groups"]] == [("Les footeux", True), ("Rando", False)]
    assert result["groups"][0]["members"] == [{"id": LEA, "name": "Léa"}]
    assert {p["id"] for p in result["people"]} == {LEA, TOM}  # moi exclu


def test_create_compose_and_delete_with_the_member_session():
    acc, seen = fake_supabase()
    acc.create_group("tok", "Les footeux")
    post = next(s for s in seen if s[0] == "POST" and s[1] == "/rest/v1/member_groups")
    assert json.loads(post[3]) == {"name": "Les footeux", "created_by": ME}
    acc.set_group_member("tok", G1, TOM, True)
    add = next(s for s in seen if s[0] == "POST" and s[1] == "/rest/v1/member_group_members")
    assert json.loads(add[3]) == {"group_id": G1, "user_id": TOM}
    acc.set_group_member("tok", G1, TOM, False)
    rm = next(s for s in seen if s[0] == "DELETE" and s[1] == "/rest/v1/member_group_members")
    assert rm[2] == f"group_id=eq.{G1}&user_id=eq.{TOM}"
    acc.delete_group("tok", G1)
    assert any(s[0] == "DELETE" and s[1] == "/rest/v1/member_groups" and s[2] == f"id=eq.{G1}" for s in seen)


class Fake:
    def __init__(self):
        self.calls = []

    def groups(self, token):
        return {"groups": [], "people": []}

    def create_group(self, token, name):
        self.calls.append(("create", name))
        return self.groups(token)

    def set_group_member(self, token, group_id, user_id, on):
        self.calls.append(("member", group_id, user_id, on))
        return self.groups(token)

    def delete_group(self, token, group_id):
        self.calls.append(("delete", group_id))
        return self.groups(token)


def test_api_validates_names_and_identifiers(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(main, "accounts", fake)
    c = TestClient(main.app)
    assert c.post("/api/account/groups", json={"token": "tok"}).status_code == 200
    assert c.post("/api/account/groups/create", json={"token": "tok", "name": "  Les   footeux "}).status_code == 200
    assert c.post("/api/account/groups/create", json={"token": "tok", "name": "   "}).status_code == 400
    assert c.post("/api/account/groups/member", json={"token": "tok", "group_id": G1, "user_id": "x; drop", "on": True}).status_code == 422
    assert c.post("/api/account/groups/delete", json={"token": "tok", "group_id": G2}).status_code == 200
    assert fake.calls == [("create", "Les footeux"), ("delete", G2)]
