"""Fiche profil (avis n°7 et n°8) : par compte, ou depuis un jeu par la partie et le numéro du joueur (jamais son
identifiant) ; choix de confidentialité relayés à la base avec la session de la personne."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, games, main

LEA_UID = "11111111-2222-3333-4444-555555555555"
GROUP = "22222222-3333-4444-5555-666666666666"
INV = "33333333-4444-5555-6666-777777777777"
TOKEN = "44444444-5555-6666-7777-888888888888"
CARD = {"id": LEA_UID, "display_name": "Léa", "avatar_url": "lea/photo.jpg", "role": "member", "root": False, "me": False,
        "first_name": None, "last_name": None, "phone": None, "groups": ["Vendredi Party"]}


def fake():
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.url.path, body))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-me"})
        if path == "/rest/v1/rpc/member_card":
            return httpx.Response(200, json=CARD if body["target"] == LEA_UID else None)
        if path == "/rest/v1/rpc/my_privacy":
            return httpx.Response(200, json={"show_name": False, "phone_groups": []})
        if path == "/rest/v1/rpc/set_name_public":
            return httpx.Response(200, json={"show_name": body["visible"], "phone_groups": []})
        if path == "/rest/v1/rpc/set_group_phone_share":
            return httpx.Response(200, json={"show_name": False, "phone_groups": [body["grp"]] if body["visible"] else []})
        if path == "/rest/v1/rpc/my_group_invitations":
            return httpx.Response(200, json=[{"id": INV, "group_id": GROUP, "group": "Les footeux", "invited_by": "Tom", "at": "2026-10-30"}])
        if path == "/rest/v1/rpc/answer_group_invitation":
            return httpx.Response(200, json=[])
        if path == "/rest/v1/rpc/group_invite_link":
            return httpx.Response(200, json=TOKEN)
        if path == "/rest/v1/rpc/invite_to_group":
            if body.get("member") == LEA_UID:
                return httpx.Response(400, json={"message": "Déjà dans le groupe"})
            return httpx.Response(200, json={"invited": "phone" if body.get("phone") else "member"})
        if path.startswith("/storage/v1/object/sign/"):
            return httpx.Response(200, json={"signedURL": "/object/sign/profile-photos/lea/photo.jpg?t=1"})
        return httpx.Response(404)

    return accounts_mod.Accounts(b"s", httpx.Client(transport=httpx.MockTransport(handler))), seen


@pytest.fixture
def world(monkeypatch):
    acc, seen = fake()
    monkeypatch.setattr(main, "accounts", acc)
    lea = acc.gid(LEA_UID)
    acc.by_gid[lea] = {"guest_id": lea, "name": "Léa", "photo": None}
    acc.uid_by_gid[lea] = LEA_UID
    g = games.new_game("undercover", host=lea, name="Léa", code="4321")
    games.join(g, lea, "Léa")
    games.join(g, "guest-tom-000001", "Tom")
    monkeypatch.setitem(main.store.session.games, g["code"], g)
    return acc, seen, g, lea


def pid_of(g, gid):
    return next(p["pid"] for p in g["players"] if p["id"] == gid)


def test_card_by_account_id_with_a_signed_photo(world):
    acc, seen, g, lea = world
    r = TestClient(main.app).post("/api/account/card", json={"token": "t" * 30, "id": LEA_UID})
    assert r.status_code == 200 and r.json()["display_name"] == "Léa"
    assert r.json()["photo"].endswith("lea/photo.jpg?t=1") and r.json()["phone"] is None


def test_card_from_a_game_by_player_number_never_by_identifier(world):
    acc, seen, g, lea = world
    c = TestClient(main.app)
    r = c.post("/api/account/card", json={"token": "t" * 30, "game": g["code"], "pid": pid_of(g, lea)})
    assert r.status_code == 200 and r.json()["id"] == LEA_UID
    assert ("/rest/v1/rpc/member_card", {"target": LEA_UID}) in seen
    tom = c.post("/api/account/card", json={"token": "t" * 30, "game": g["code"], "pid": pid_of(g, "guest-tom-000001")})
    assert tom.status_code == 404 and "pas de compte" in tom.json()["detail"]
    assert c.post("/api/account/card", json={"token": "t" * 30, "game": "9999", "pid": "x"}).status_code == 404
    assert c.post("/api/account/card", json={"token": "t" * 30}).status_code == 400
    assert c.post("/api/account/card", json={"token": "t" * 30, "guest_id": lea}).status_code == 400  # jamais par identifiant


def test_game_view_marks_players_with_an_account(world):
    acc, seen, g, lea = world
    v = main.full_view(g, lea)
    flags = {p["name"]: p.get("account", False) for p in v["players"]}
    assert flags == {"Léa": True, "Tom": False}
    assert lea not in json.dumps(v)  # l'identifiant du compte ne part jamais vers les téléphones


def test_privacy_choices_are_relayed(world):
    acc, seen, g, lea = world
    c = TestClient(main.app)
    assert c.post("/api/account/privacy", json={"token": "t" * 30}).json() == {"show_name": False, "phone_groups": []}
    assert c.post("/api/account/privacy/name", json={"token": "t" * 30, "on": True}).json()["show_name"] is True
    group = "99999999-8888-7777-6666-555555555555"
    assert c.post("/api/account/privacy/phone", json={"token": "t" * 30, "group_id": group, "on": True}).json()["phone_groups"] == [group]
    assert ("/rest/v1/rpc/set_group_phone_share", {"grp": group, "visible": True}) in seen
    assert c.post("/api/account/privacy/phone", json={"token": "t" * 30, "group_id": "pas-un-uuid", "on": True}).status_code == 422


def test_group_invitations_link_and_invite_are_relayed(world):
    acc, seen, g, lea = world
    c = TestClient(main.app)
    inv = c.post("/api/account/groups/invitations", json={"token": "t" * 30}).json()["invitations"]
    assert inv[0]["group"] == "Les footeux" and inv[0]["invited_by"] == "Tom"
    assert c.post("/api/account/groups/invitations/answer", json={"token": "t" * 30, "id": INV, "accept": True}).json() == {"invitations": []}
    assert ("/rest/v1/rpc/answer_group_invitation", {"inv": INV, "accept": True}) in seen
    url = c.post("/api/account/groups/link", json={"token": "t" * 30, "group_id": GROUP}).json()["url"]
    assert url.endswith(f"/events/group-invite/{TOKEN}")
    assert c.post("/api/account/groups/invite", json={"token": "t" * 30, "group_id": GROUP, "phone": "079 000 00 03"}).json() == {"invited": "phone"}
    refused = c.post("/api/account/groups/invite", json={"token": "t" * 30, "group_id": GROUP, "member": LEA_UID})
    assert refused.status_code == 400 and "Déjà dans le groupe" in refused.json()["detail"]
    assert c.post("/api/account/groups/invite", json={"token": "t" * 30, "group_id": GROUP}).status_code == 400
