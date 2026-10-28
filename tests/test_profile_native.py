"""Réglages natifs › Mon profil : prénom, nom, surnom et photo, avec la session du membre (ses droits Supabase)."""
import base64
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000
ROW = {"id": "u-7", "display_name": "Boby", "first_name": "Ludo", "last_name": "T", "phone": "+41765550000",
       "avatar_url": "u-7/old.jpg", "role": "admin", "status": "active"}


def fake_supabase(patch_status=204):
    seen = []

    def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.content))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-7"})
        if request.url.path == "/rest/v1/profiles" and request.method == "GET":
            return httpx.Response(200, json=[ROW])
        if request.url.path == "/rest/v1/profiles" and request.method == "PATCH":
            return httpx.Response(patch_status, json={"message": "profile_incomplete"} if patch_status >= 400 else None)
        if request.url.path.startswith("/storage/v1/object/sign/profile-photos/"):
            return httpx.Response(200, json={"signedURL": "/object/sign/profile-photos/x.jpg?token=t"})
        if request.url.path.startswith("/storage/v1/object/profile-photos/"):
            return httpx.Response(200, json={"Key": "ok"})
        if request.url.path == "/storage/v1/object/profile-photos" and request.method == "DELETE":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    return accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_profile_is_read_with_a_signed_photo_link():
    acc, _ = fake_supabase()
    p = acc.profile("tok")
    assert p["display_name"] == "Boby" and p["phone"] == "+41765550000" and p["photo"].endswith("token=t")


def test_new_photo_is_uploaded_in_the_members_folder_then_the_old_one_removed():
    acc, seen = fake_supabase()
    acc.update_profile("tok", {"first_name": "Ludo", "last_name": "T", "display_name": "Boby 2"}, JPEG)
    upload = next(s for s in seen if s[0] == "POST" and s[1].startswith("/storage/v1/object/profile-photos/u-7/"))
    patch = json.loads(next(s for s in seen if s[0] == "PATCH")[2])
    assert patch["display_name"] == "Boby 2" and patch["avatar_url"] == upload[1].removeprefix("/storage/v1/object/profile-photos/")
    removed = json.loads(next(s for s in seen if s[0] == "DELETE")[2])
    assert removed == {"prefixes": ["u-7/old.jpg"]}


def test_refused_update_removes_the_photo_just_sent():
    acc, seen = fake_supabase(patch_status=400)
    try:
        acc.update_profile("tok", {"first_name": "Ludo", "last_name": "T", "display_name": "Boby"}, JPEG)
        raise AssertionError("refus attendu")
    except accounts_mod.AccountError:
        pass
    sent = next(s for s in seen if s[0] == "POST" and s[1].startswith("/storage/v1/object/profile-photos/u-7/"))[1].removeprefix("/storage/v1/object/profile-photos/")
    assert json.loads(next(s for s in seen if s[0] == "DELETE")[2]) == {"prefixes": [sent]}


class FakeAccounts:
    def __init__(self):
        self.updates = []

    def profile(self, token):
        return {**ROW, "photo": None}

    def update_profile(self, token, fields, photo):
        self.updates.append((fields, photo))
        return {**ROW, **fields, "photo": None}


def test_api_validates_names_and_photo(monkeypatch):
    fake = FakeAccounts()
    monkeypatch.setattr(main, "accounts", fake)
    c = TestClient(main.app)
    assert c.post("/api/account/profile", json={"token": "tok"}).json()["display_name"] == "Boby"
    ok = {"token": "tok", "first_name": " Ludo ", "last_name": "T", "display_name": "Boby"}
    assert c.post("/api/account/profile/update", json=ok).status_code == 200
    assert fake.updates[-1] == ({"first_name": "Ludo", "last_name": "T", "display_name": "Boby"}, None)
    photo = base64.b64encode(JPEG).decode()
    assert c.post("/api/account/profile/update", json={**ok, "photo": photo}).status_code == 200
    assert fake.updates[-1][1] == JPEG
    for bad in ({"display_name": " "}, {"display_name": "x" * 41}, {"first_name": ""},
                {"photo": base64.b64encode(b"GIF89a....").decode()}, {"photo": "%%%"}):
        assert c.post("/api/account/profile/update", json={**ok, **bad}).status_code in (400, 422), bad
    assert len(fake.updates) == 2
