"""Réglages natifs › Abonnements : catégories et tags suivis (alertes « Si abonné » et filtre de la liste)."""
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main

CAT = "11111111-1111-1111-1111-111111111111"
TAG = "22222222-2222-2222-2222-222222222222"


def fake_supabase():
    seen = []

    def handler(request: httpx.Request):
        q = str(request.url.query, "ascii")
        seen.append((request.method, request.url.path, q, request.content))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-5"})
        if request.url.path == "/rest/v1/categories":
            assert "archived=eq.false" in q
            return httpx.Response(200, json=[{"id": CAT, "name": "Soirée", "color": "#ff0000", "icon": "🎉", "sort": 1}])
        if request.url.path == "/rest/v1/tags":
            return httpx.Response(200, json=[{"id": TAG, "name": "techno", "color": "#00ff00"}])
        if request.url.path == "/rest/v1/category_subscriptions" and request.method == "GET":
            return httpx.Response(200, json=[{"category_id": CAT}])
        if request.url.path == "/rest/v1/tag_subscriptions" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method in ("POST", "DELETE"):
            return httpx.Response(201 if request.method == "POST" else 204)
        return httpx.Response(404)

    return accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_reads_topics_and_what_the_member_follows():
    acc, _ = fake_supabase()
    s = acc.subscriptions("tok")
    assert s["categories"][0]["name"] == "Soirée" and s["tags"][0]["name"] == "techno"
    assert s["category_ids"] == [CAT] and s["tag_ids"] == []


def test_follow_and_unfollow_only_for_the_member():
    acc, seen = fake_supabase()
    acc.set_subscription("tok", "tag", TAG, True)
    post = next(s for s in seen if s[0] == "POST")
    assert post[1] == "/rest/v1/tag_subscriptions" and json.loads(post[3]) == {"user_id": "u-5", "tag_id": TAG}
    acc.set_subscription("tok", "category", CAT, False)
    delete = next(s for s in seen if s[0] == "DELETE")
    assert delete[1] == "/rest/v1/category_subscriptions" and delete[2] == f"user_id=eq.u-5&category_id=eq.{CAT}"


class FakeAccounts:
    def __init__(self):
        self.calls = []

    def subscriptions(self, token):
        return {"categories": [], "tags": [], "category_ids": [], "tag_ids": []}

    def set_subscription(self, token, kind, topic, on):
        self.calls.append((kind, topic, on))
        return self.subscriptions(token)


def test_api_checks_kind_and_identifier(monkeypatch):
    fake = FakeAccounts()
    monkeypatch.setattr(main, "accounts", fake)
    c = TestClient(main.app)
    assert c.post("/api/account/subscriptions", json={"token": "tok"}).status_code == 200
    assert c.post("/api/account/subscriptions/set", json={"token": "tok", "kind": "tag", "id": TAG, "on": True}).status_code == 200
    assert fake.calls == [("tag", TAG, True)]
    for bad in ({"kind": "group"}, {"id": "1; drop"}, {"id": "abc"}):
        body = {"token": "tok", "kind": "tag", "id": TAG, "on": True, **bad}
        assert c.post("/api/account/subscriptions/set", json=body).status_code == 422
    assert len(fake.calls) == 1
