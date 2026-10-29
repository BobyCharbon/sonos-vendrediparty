"""Réglages natifs : connexion par SMS, déconnexion, suppression du compte ; annonces et catégories côté admin."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import account_auth, accounts as accounts_mod, group_admin as ga, main


def fake(verify_status=200, delete_status=204, sign=None):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), body, request.headers.get("authorization")))
        path = request.url.path
        if path == "/auth/v1/otp":
            return httpx.Response(200, json={})
        if path == "/auth/v1/verify":
            return httpx.Response(verify_status, json={"access_token": "a" * 40, "refresh_token": "r", "expires_in": 3600, "user": {"id": "u1"}}
                                  if verify_status == 200 else {"msg": "Token has expired or is invalid"})
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u1"})
        if path == "/rest/v1/rpc/delete_my_account":
            return httpx.Response(delete_status, json={"message": "last_admin"} if delete_status >= 400 else None)
        if path == "/rest/v1/admin_announcements":
            return httpx.Response(200, json=[{"id": f"{i}", "title": "T", "body": "B", "created_at": "2026-10-29"} for i in range(21)])
        if path in ("/rest/v1/categories", "/rest/v1/tags"):
            if request.method == "POST":
                return httpx.Response(409, json={"message": "duplicate key value violates unique constraint"}) if body["name"] == "techno" \
                    else httpx.Response(201, json=[body])
            return httpx.Response(200, json=[{"id": "c1", "name": "Soirée", "color": "#FF7A59", "archived": False}])
        if path in ("/rest/v1/rpc/my_permissions", "/rest/v1/rpc/my_rank"):
            return httpx.Response(200, json=["taxonomy.manage"] if "perm" in path else 4)
        return httpx.Response(204)

    acc = accounts_mod.Accounts(b"s", httpx.Client(transport=httpx.MockTransport(handler)))
    return acc, seen


def test_code_and_session_with_the_storage_key_of_the_page(monkeypatch):
    monkeypatch.setattr(accounts_mod, "SUPABASE_URL", "https://ewromq.supabase.co")
    acc, seen = fake()
    auth = account_auth.AccountAuth(acc)
    auth.send_code("+41790000003")
    assert seen[0][3] == {"phone": "+41790000003"}
    out = auth.verify("+41790000003", "123456")
    assert out["storage_key"] == "sb-ewromq-auth-token"
    assert out["session"]["access_token"] and out["session"]["expires_at"] > 0


@pytest.mark.parametrize("phone", ["0790000003", "+41", "41790000003", "+41 79 000 00 03"])
def test_invalid_numbers_never_reach_supabase(phone):
    acc, seen = fake()
    with pytest.raises(accounts_mod.AccountError):
        account_auth.AccountAuth(acc).send_code(phone)
    assert seen == []


def test_wrong_code_is_a_plain_message():
    acc, _ = fake(verify_status=403)
    with pytest.raises(accounts_mod.AccountError, match="Code incorrect"):
        account_auth.AccountAuth(acc).verify("+41790000003", "000000")


def test_delete_needs_the_word_then_signs_out_and_explains_last_admin():
    acc, seen = fake()
    auth = account_auth.AccountAuth(acc)
    with pytest.raises(accounts_mod.AccountError, match="SUPPRIMER"):
        auth.delete_account("t" * 30, "supprimer")
    auth.delete_account("t" * 30, "SUPPRIMER")
    assert any(s[1] == "/auth/v1/logout" and s[2] == "scope=local" for s in seen)
    acc, _ = fake(delete_status=400)
    with pytest.raises(accounts_mod.AccountError, match="dernier administrateur"):
        account_auth.AccountAuth(acc).delete_account("t" * 30, "SUPPRIMER")


def test_announcements_pages_and_taxonomy_names():
    acc, seen = fake()
    admin = ga.GroupAdmin(acc)
    page = admin.announcements("tok")
    assert len(page["announcements"]) == 20 and page["more"] is True
    admin.announcements("tok", "2026-10-29T10:00:00Z", "11111111-1111-1111-1111-111111111111")
    assert "or=(created_at.lt.2026-10-29T10:00:00Z" in seen[-1][2]
    admin.save_topic("tok", "tags", None, {"name": " #House ", "color": "#7AA7FF"})
    post = next(s for s in seen if s[0] == "POST" and s[1] == "/rest/v1/tags")
    assert post[3] == {"name": "house", "color": "#7AA7FF"}
    with pytest.raises(accounts_mod.AccountError, match="existe déjà"):
        admin.save_topic("tok", "tags", None, {"name": "techno"})
    admin.save_topic("tok", "categories", None, {"name": "Sport", "color": "#7AA7FF"})
    cat = [s for s in seen if s[0] == "POST" and s[1] == "/rest/v1/categories"][-1]
    assert cat[3]["sort"] == 2


class Fake:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, *args))
            return {"session": {}, "storage_key": "k"} if name == "verify" else None
        return call


def test_routes_validate_and_limit(monkeypatch):
    f = Fake()
    monkeypatch.setattr(main, "account_auth", f)
    monkeypatch.setattr(main, "otp_limiter", main.Limiter(per_ip=2, ip_lock=60, global_max=50, global_window=60, global_lock=60))
    c = TestClient(main.app)
    assert c.post("/api/account/otp", json={"phone": " +41790000003 "}).json() == {"ok": True}
    assert f.calls[-1] == ("send_code", "+41790000003")
    assert c.post("/api/account/verify", json={"phone": "+41790000003", "code": "123456"}).json()["storage_key"] == "k"
    c.post("/api/account/otp", json={"phone": "+41790000003"})
    c.post("/api/account/otp", json={"phone": "+41790000003"})
    assert c.post("/api/account/otp", json={"phone": "+41790000003"}).status_code == 429
    assert c.post("/api/account/delete", json={"token": "t", "confirm": "SUPPRIMER"}).json() == {"ok": True}
    assert c.post("/api/account/group-admin/taxonomy/save", json={"token": "t", "kind": "tags"}).status_code == 400
    assert c.post("/api/account/group-admin/taxonomy/save", json={"token": "t", "kind": "lieux", "name": "x"}).status_code == 422
