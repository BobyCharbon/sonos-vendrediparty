"""Messages directs (4.11) dans le relais des Discussions (app iOS) : conversation à deux mise en forme comme un groupe,
envoi sans citation, actions sur les tables et fonctions direct_*, ouverture par « Écrire », blocage."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, group_admin as ga, group_chats as gc, main

ME, LEA = "u-me", "u-lea"
CHAT = "22222222-2222-2222-2222-222222222222"
M1, M2 = ("bbbbbbbb-0000-0000-0000-00000000000" + str(i) for i in (1, 2))
HASH = "ab" * 32


def fake(start_status=200, blocked=False):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else None
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), body))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path == "/rest/v1/direct_chats":
            return httpx.Response(200, json=[{"user_a": LEA, "user_b": ME}])
        if path == "/rest/v1/direct_chat_settings":
            return httpx.Response(200, json=[{"notify": "none"}])
        if path == "/rest/v1/direct_blocks":
            return httpx.Response(200, json=[{"blocked_id": LEA}] if blocked else [])
        if path == "/rest/v1/direct_messages" and request.method == "GET":
            if "pinned=is.true" in str(request.url.query, "ascii"):
                return httpx.Response(200, json=[{"id": M1, "user_id": LEA, "body": "Tu viens ?", "pinned": True,
                                                  "created_at": "2026-11-04T10:00:00Z", "deleted_at": None}])
            return httpx.Response(200, json=[
                {"id": M2, "user_id": ME, "body": "Oui !", "photo_path": f"{CHAT}/1-abc.jpg", "reply_to": M1, "pinned": False,
                 "created_at": "2026-11-04T10:01:00Z", "deleted_at": None},
                {"id": M1, "user_id": LEA, "body": "Tu viens ?", "photo_path": None, "reply_to": None, "pinned": True,
                 "created_at": "2026-11-04T10:00:00Z", "deleted_at": None}])
        if path == "/rest/v1/direct_messages":
            return httpx.Response(201)
        if path == "/rest/v1/direct_message_reactions" and request.method == "GET":
            return httpx.Response(200, json=[{"message_id": M1, "user_id": ME, "emoji": "❤️"}])
        if path == "/rest/v1/direct_message_reactions":
            return httpx.Response(201 if request.method == "POST" else 204)
        if path == "/rest/v1/rpc/direct_chat_people":
            return httpx.Response(200, json=[{"id": LEA, "display_name": "Léa", "avatar_url": "lea.jpg", "member": True},
                                             {"id": ME, "display_name": "Boby", "avatar_url": None, "member": True}])
        if path == "/rest/v1/rpc/start_direct_chat":
            if start_status >= 400:
                return httpx.Response(start_status, json={"message": "forbidden: tu ne peux pas écrire à cette personne"})
            return httpx.Response(200, json=CHAT)
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        if path.startswith("/rest/v1/rpc/"):
            return httpx.Response(204)
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    return gc.GroupChats(ga.GroupAdmin(acc)), seen


def rpcs(seen) -> list:
    return [(p.rsplit("/", 1)[1], b) for m, p, _, b in seen if p.startswith("/rest/v1/rpc/")]


def test_direct_conversation_looks_like_a_group_with_the_other_person_and_no_staff():
    chats, seen = fake()
    c = chats.conversation("jeton", CHAT, direct=True)
    assert c["direct"] is True and c["name"] == "Léa" and c["user_id"] == LEA and c["photo"].endswith("/profile-photos/lea.jpg?t=1")
    assert c["notify"] == "none" and not c["admin"] and not c["organizer"] and c["everyone"] == "staff" and not c["can_name_admins"]
    assert [m["id"] for m in c["messages"]] == [M1, M2]
    assert c["messages"][1]["reply"] == {"name": "Léa", "text": "Tu viens ?"} and c["messages"][1]["mine"]
    assert c["messages"][0]["reactions"] == [{"emoji": "❤️", "count": 1, "mine": True}]
    assert c["highlights"] == [{"id": M1, "author_name": "Léa", "at": "2026-11-04T10:00:00Z", "text": "Tu viens ?", "announcement": False}]
    assert {m["id"] for m in c["members"]} == {ME, LEA} and c["blocked"] is False
    # Jamais les tables des groupes, ni my_chats (une conversation neuve, sans message, n'y figure pas encore).
    assert not any("group_" in p or p.endswith("/my_chats") for _, p, _, _ in seen)
    assert fake(blocked=True)[0].conversation("jeton", CHAT, direct=True)["blocked"] is True


def test_direct_send_has_no_mentions_or_everyone_and_actions_use_direct_functions():
    chats, seen = fake()
    chats.send("jeton", CHAT, "@tout @Léa salut", None, None, mentions=[LEA], message_id=M2, direct=True)
    sent = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/direct_messages")
    assert sent == {"chat_id": CHAT, "body": "@tout @Léa salut", "photo_path": None, "reply_to": None, "id": M2}
    with pytest.raises(accounts_mod.AccountError):
        chats.send("jeton", CHAT, "x", None, "11111111-1111-1111-1111-111111111111/1-abc.jpg", direct=True)
    chats.react("jeton", M1, "🔥", True, direct=True)
    chats.react("jeton", M1, "🔥", False, direct=True)
    assert [m for m, p, _, _ in seen if p == "/rest/v1/direct_message_reactions"] == ["POST", "DELETE"]
    chats.pin("jeton", M1, True, direct=True)
    chats.delete("jeton", M1, direct=True)
    assert chats.notify("jeton", CHAT, "none", direct=True) == {"notify": "none"}
    with pytest.raises(accounts_mod.AccountError):
        chats.notify("jeton", CHAT, "mentions", direct=True)  # pas de « citations » à deux
    chats.read("jeton", CHAT, direct=True)
    assert rpcs(seen) == [("pin_direct_message", {"msg": M1, "pin": True}), ("delete_direct_message", {"msg": M1}),
                          ("set_direct_chat_notify", {"chat": CHAT, "level": "none"}), ("mark_direct_read", {"chat": CHAT})]


def test_write_button_opens_the_conversation_and_reports_refusals():
    chats, seen = fake()
    assert chats.start_direct("jeton", LEA, HASH) == {"id": CHAT}
    assert rpcs(seen)[-1] == ("start_direct_chat", {"target": LEA, "contact_hash": HASH})
    assert chats.start_direct("jeton", LEA) == {"id": CHAT} and rpcs(seen)[-1] == ("start_direct_chat", {"target": LEA})
    with pytest.raises(accounts_mod.AccountError) as e:
        fake(start_status=403)[0].start_direct("jeton", LEA)
    assert "écrire à cette personne" in str(e.value)
    assert chats.block("jeton", LEA, True) == {"blocked": True}
    assert rpcs(seen)[-1] == ("set_direct_block", {"target": LEA, "blocked": True})


def test_direct_routes_validate_input_and_relay(monkeypatch):
    chats, seen = fake()
    monkeypatch.setattr(main, "group_chats", chats)
    client = TestClient(main.app)
    assert client.post("/api/account/chats/direct", json={"token": "jeton", "user_id": LEA}).status_code == 422  # pas un uuid
    lea = "33333333-3333-3333-3333-333333333333"
    assert client.post("/api/account/chats/direct", json={"token": "jeton", "user_id": lea, "contact_hash": "zz"}).status_code == 422
    assert client.post("/api/account/chats/direct", json={"token": "jeton", "user_id": lea}).json() == {"id": CHAT}
    assert client.post("/api/account/chats/block", json={"token": "jeton", "user_id": lea, "on": True}).json() == {"blocked": True}
    opened = client.post("/api/account/chats/open", json={"token": "jeton", "group_id": CHAT, "direct": True}).json()
    assert opened["direct"] is True and opened["name"] == "Léa"
    assert client.post("/api/account/chats/send", json={"token": "jeton", "group_id": CHAT, "body": "Salut", "direct": True}).json() == {"ok": True}
    assert client.post("/api/account/chats/read", json={"token": "jeton", "group_id": CHAT, "direct": True}).status_code == 200
    assert client.post("/api/account/chats/pin", json={"token": "jeton", "id": M1, "pin": False, "direct": True}).status_code == 200
    assert ("mark_direct_read", {"chat": CHAT}) in rpcs(seen) and ("pin_direct_message", {"msg": M1, "pin": False}) in rpcs(seen)


def test_a_notification_id_alone_opens_the_direct_conversation_and_the_list_shows_the_person():
    chats, seen = fake()
    opened = chats.conversation("jeton", CHAT)  # sans direct : l'id n'est pas un de mes groupes (my_chats vide ici)
    assert opened["direct"] is True and opened["name"] == "Léa"


def test_chat_list_signs_the_photo_of_the_other_person():
    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/rest/v1/rpc/my_chats":
            return httpx.Response(200, json=[{"id": CHAT, "kind": "direct", "name": "Léa", "user_id": LEA, "avatar_url": "lea.jpg"},
                                             {"id": "g", "kind": "group", "name": "Les amis"}])
        if path.startswith("/storage/v1/object/sign/"):
            body = json.loads(request.content)
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/profile-photos/{p}?t=1"} for p in body["paths"]])
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    rows = gc.GroupChats(ga.GroupAdmin(acc)).chats("jeton")["chats"]
    assert rows[0]["photo"].endswith("/profile-photos/lea.jpg?t=1") and "photo" not in rows[1]
