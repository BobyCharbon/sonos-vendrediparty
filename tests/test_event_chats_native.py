"""Discussion d'un événement pour l'app iPhone native (16.11.2026) : relais vers Supabase avec la session du membre,
même forme qu'une discussion de groupe (event = True) ; la base décide des droits (migration 20261116180000)."""
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, event_chats as ec, group_admin as ga, group_chats as gc, main

ME, LEA, TOM, VAL = "u-me", "u-lea", "u-tom", "u-val"
EV = "22222222-2222-2222-2222-222222222222"
M1, M2, M3 = ("bbbbbbbb-0000-0000-0000-00000000000" + str(i) for i in (1, 2, 3))


def fake(staff=False, write=True, muted=False, blocked=(), patched=True, forum=True):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else None
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), body))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path == "/rest/v1/rpc/event_chat_state":
            return httpx.Response(200, json={"title": "Raclette", "forum": forum, "status": "published", "write": write,
                                             "staff": staff, "moderate": False, "muted": muted})
        if path == "/rest/v1/rpc/event_chat_people":
            return httpx.Response(200, json=[
                {"id": ME, "display_name": "Boby", "avatar_url": "me.jpg", "rsvp": "yes", "organizer": False, "invited": False},
                {"id": LEA, "display_name": "Léa", "avatar_url": None, "rsvp": "maybe", "organizer": True, "invited": False},
                {"id": TOM, "display_name": "Tom", "avatar_url": None, "rsvp": None, "organizer": False, "invited": staff}])
        if path == "/rest/v1/messages" and request.method == "GET":
            if "pinned=is.true" in str(request.url.query, "ascii"):
                return httpx.Response(200, json=[{"id": M1, "user_id": LEA, "body": "@annonce Parking derrière", "pinned": True,
                                                  "announcement": True, "created_at": "2026-11-16T10:00:00Z", "deleted_at": None}])
            return httpx.Response(200, json=[
                {"id": M3, "user_id": TOM, "body": "", "audio_path": f"{EV}/3-abcdef0123.m4a", "audio_seconds": 4.2,
                 "photo_path": None, "reply_to": M1, "pinned": False, "created_at": "2026-11-16T10:02:00Z", "deleted_at": None},
                {"id": M2, "user_id": ME, "body": "", "photo_path": f"{EV}/2-abcdef0123.jpg", "reply_to": None, "pinned": False,
                 "created_at": "2026-11-16T10:01:00Z", "deleted_at": None},
                {"id": M1, "user_id": LEA, "body": "@annonce Parking derrière", "photo_path": None, "reply_to": None, "pinned": True,
                 "announcement": True, "created_at": "2026-11-16T10:00:00Z", "deleted_at": None}])
        if path == "/rest/v1/messages" and request.method == "PATCH":
            return httpx.Response(200, json=[{"id": M1}] if patched else [])
        if path == "/rest/v1/message_reactions" and request.method == "GET":
            return httpx.Response(200, json=[{"message_id": M1, "user_id": TOM, "emoji": "🔥"}])
        if path in ("/rest/v1/messages", "/rest/v1/message_reactions", "/rest/v1/event_mutes"):
            return httpx.Response(201 if request.method == "POST" else 204)
        if path == "/rest/v1/direct_blocks":
            return httpx.Response(200, json=[{"blocked_id": b} for b in blocked])
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    return ec.EventChats(gc.GroupChats(ga.GroupAdmin(acc))), seen


def test_conversation_has_the_shape_of_a_group_chat_with_photos_voices_announcements_and_people():
    chats, _ = fake()
    c = chats.conversation("jeton", EV)
    assert c["event"] and c["name"] == "Raclette" and c["member"] and not c["admin"] and c["notify"] == "all"
    assert [m["id"] for m in c["messages"]] == [M1, M2, M3]
    first, photo, voice = c["messages"]
    assert first["announcement"] and first["pinned"] and first["author_name"] == "Léa"
    assert photo["mine"] and photo["photo"].endswith(f"/chat-photos/{EV}/2-abcdef0123.jpg?t=1") and photo["body"] == ""
    assert voice["audio_seconds"] == 4.2 and voice["reply"] == {"id": M1, "author": LEA, "name": "Léa", "text": "@annonce Parking derrière"}
    assert c["highlights"] == [{"id": M1, "author_name": "Léa", "at": "2026-11-16T10:00:00Z",
                                "text": "@annonce Parking derrière", "announcement": True}]
    assert [(m["name"], m["rsvp"], m["organizer"]) for m in c["members"]] == [("Boby", "yes", False), ("Léa", "maybe", True), ("Tom", None, False)]
    # @toutlemonde, @present, @annonce : proposés seulement à l'organisation (la base décide de toute façon).
    assert c["tags"] == []
    assert [t["tag"] for t in fake(staff=True)[0].conversation("jeton", EV)["tags"]] == ["toutlemonde", "present", "annonce"]


def test_blocked_people_are_masked_and_a_closed_discussion_is_refused():
    c = fake(blocked=(TOM,))[0].conversation("jeton", EV)
    assert c["messages"][2]["body"] == gc.BLOCKED_TEXT and c["messages"][2]["audio"] is None
    assert fake(muted=True)[0].conversation("jeton", EV)["notify"] == "none"
    try:
        fake(forum=False)[0].conversation("jeton", EV)
        raise AssertionError("discussion fermée acceptée")
    except accounts_mod.AccountError as e:
        assert "fermée" in str(e)


def test_send_cites_people_and_passes_the_announcement_switch_to_the_base():
    chats, seen = fake(staff=True)
    chats.send("jeton", EV, "@léa et @toutlemonde : on avance", M1, None, None, M2, None, None, True)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/messages")
    assert row["mentions"] == [LEA] and row["announcement"] is True and row["id"] == M2 and row["reply_to"] == M1
    assert row["event_id"] == EV and row["user_id"] == ME
    chats, seen = fake()
    chats.send("jeton", EV, "", None, f"{EV}/9-abcdef0123.jpg", [TOM], None, None, None, False)
    assert [p for m, p, _, _ in seen if m in ("GET", "POST") and p.startswith("/rest")] == ["/rest/v1/messages"]  # un seul appel
    for body, photo in (("", None), ("x", "autre/1-abcdef0123.jpg")):
        try:
            chats.send("jeton", EV, body, None, photo, [], None, None, None, False)
            raise AssertionError("accepté")
        except accounts_mod.AccountError:
            pass


def test_pin_delete_react_and_mute():
    chats, seen = fake()
    chats.pin("jeton", M1, True)
    chats.delete("jeton", M1)
    patches = [b for m, p, _, b in seen if m == "PATCH"]
    assert patches[0] == {"pinned": True} and "deleted_at" in patches[1]
    try:
        fake(patched=False)[0].pin("jeton", M1, True)  # la règle de la base n'a rien laissé passer
        raise AssertionError("épinglé sans droit")
    except accounts_mod.AccountError as e:
        assert "organisation" in str(e)
    chats.react("jeton", M1, "👍", True)
    chats.notify("jeton", EV, "none")
    chats.notify("jeton", EV, "all")
    calls = [(m, p) for m, p, _, _ in seen]
    assert ("POST", "/rest/v1/message_reactions") in calls and ("POST", "/rest/v1/event_mutes") in calls
    assert ("DELETE", "/rest/v1/event_mutes") in calls


def test_routes_relay_to_the_event_chats_and_stay_open_without_discussions(monkeypatch):
    chats, _ = fake()
    monkeypatch.setattr(main, "event_chats", chats)
    monkeypatch.setenv("DISCUSSIONS_ENABLED", "0")
    client = TestClient(main.app)
    r = client.post("/api/account/event-chat/open", json={"token": "jeton", "event_id": EV})
    assert r.status_code == 200 and r.json()["event"]
    r = client.post("/api/account/event-chat/send", json={"token": "jeton", "event_id": EV, "body": "Salut", "announcement": False})
    assert r.status_code == 200
    r = client.post("/api/account/event-chat/notify", json={"token": "jeton", "event_id": EV, "level": "mentions"})
    assert r.status_code == 422  # « tout » ou « rien » pour un événement
