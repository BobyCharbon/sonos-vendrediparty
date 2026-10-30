"""Discussions natives (avis n°10) : relais vers Supabase avec la session du membre, mis en forme pour l'app."""
import base64
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, group_admin as ga, group_chats as gc, main

ME, LEA, TOM = "u-me", "u-lea", "u-tom"
GRP = "11111111-1111-1111-1111-111111111111"
M1, M2, M3 = ("aaaaaaaa-0000-0000-0000-00000000000" + str(i) for i in (1, 2, 3))
JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


def fake(admin=False, rank=1, creator=LEA, write_status=201):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else None
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), body))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path == "/rest/v1/rpc/my_permissions":
            return httpx.Response(200, json=[])
        if path == "/rest/v1/rpc/my_rank":
            return httpx.Response(200, json=rank)
        if path == "/rest/v1/rpc/my_chats":
            return httpx.Response(200, json=[{"id": GRP, "name": "Les amis", "member": True, "admin": admin, "notify": "mentions",
                                              "unread": 2, "last": "Léa : Salut", "last_at": "2026-10-29T10:00:00Z"}])
        if path == "/rest/v1/member_groups":
            return httpx.Response(200, json=[{"id": GRP, "name": "Les amis", "created_by": creator,
                                              "member_group_members": [{"user_id": ME}, {"user_id": LEA}, {"user_id": TOM}]}])
        if path == "/rest/v1/group_messages" and request.method == "GET":
            return httpx.Response(200, json=[  # du plus récent au plus ancien, comme la base
                {"id": M3, "user_id": LEA, "body": "", "photo_path": None, "reply_to": None, "pinned": True,
                 "created_at": "2026-10-29T10:02:00Z", "deleted_at": "2026-10-29T10:03:00Z", "deleted_by_admin": True},
                {"id": M2, "user_id": ME, "body": "Oui !", "photo_path": f"{GRP}/1-abc.jpg", "reply_to": M1, "pinned": False,
                 "created_at": "2026-10-29T10:01:00Z", "deleted_at": None, "edited_at": "2026-10-29T10:01:30Z"},
                {"id": M1, "user_id": LEA, "body": "Tu viens ?", "photo_path": None, "reply_to": None, "pinned": True,
                 "created_at": "2026-10-29T10:00:00Z", "deleted_at": None}])
        if path == "/rest/v1/group_messages":
            return httpx.Response(write_status, json={"message": "new row violates row-level security policy"} if write_status >= 400 else None)
        if path == "/rest/v1/group_message_reactions" and request.method == "GET":
            return httpx.Response(200, json=[{"message_id": M1, "user_id": ME, "emoji": "👍"},
                                             {"message_id": M1, "user_id": TOM, "emoji": "👍"},
                                             {"message_id": M1, "user_id": TOM, "emoji": "😂"}])
        if path == "/rest/v1/group_message_reactions":
            return httpx.Response(201 if request.method == "POST" else 204)
        if path == "/rest/v1/group_admins":
            return httpx.Response(200, json=[{"user_id": TOM}])
        if path in ("/rest/v1/profiles", "/rest/v1/rpc/group_chat_people"):
            return httpx.Response(200, json=[{"id": ME, "display_name": "Boby", "avatar_url": "me.jpg", "member": True},
                                             {"id": LEA, "display_name": "Léa", "avatar_url": None, "member": True},
                                             {"id": TOM, "display_name": "Tom", "avatar_url": None, "member": True},
                                             {"id": "u-autre", "display_name": "Autre", "avatar_url": None, "member": False}])
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        if path.startswith("/storage/v1/object/chat-photos/"):
            return httpx.Response(200, json={"Key": path})
        if path == "/rest/v1/rpc/group_chat_phones":
            return httpx.Response(200, json=[{"id": LEA, "phone": "41790000001"}])
        if path == "/rest/v1/rpc/pin_group_message" and not admin:
            return httpx.Response(403, json={"message": "forbidden: réservé aux admins du groupe"})
        if path.startswith("/rest/v1/rpc/"):
            return httpx.Response(204)
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    return gc.GroupChats(ga.GroupAdmin(acc)), seen


def test_conversation_is_oldest_first_with_names_photos_replies_and_reactions():
    chats, _ = fake()
    c = chats.conversation("jeton", GRP)
    assert [m["id"] for m in c["messages"]] == [M1, M2, M3]
    first, mine, removed = c["messages"]
    assert first["author_name"] == "Léa" and first["pinned"] and not first["mine"]
    assert first["reactions"] == [{"emoji": "👍", "count": 2, "mine": True}, {"emoji": "😂", "count": 1, "mine": False}]
    assert mine["mine"] and mine["edited"] and mine["photo"].endswith(f"/chat-photos/{GRP}/1-abc.jpg?t=1")
    assert mine["reply"] == {"name": "Léa", "text": "Tu viens ?"}
    assert mine["author_photo"].endswith("/profile-photos/me.jpg?t=1")
    # Supprimé par un admin : le texte le dit, plus d'épingle ni de photo
    assert removed["deleted"] and removed["body"] == "Message supprimé par un admin" and not removed["pinned"]
    assert [m["name"] for m in c["members"]] == ["Boby", "Léa", "Tom"]
    assert [m["creator"] for m in c["members"]] == [False, True, False] and c["members"][2]["admin"]
    assert [m["phone"] for m in c["members"]] == [None, "+41790000001", None]  # seul le numéro montré dans ce groupe
    assert gc.dialable("+41 79 000 00 01") == "+41790000001" and gc.dialable("12") is None and gc.dialable(None) is None
    assert c["notify"] == "mentions" and c["member"] and not c["admin"] and not c["can_name_admins"]
    assert c["reactions"] == list(gc.REACTIONS)


def test_creator_and_site_admins_name_group_admins():
    assert fake(creator=ME)[0].conversation("jeton", GRP)["can_name_admins"]
    assert fake(rank=3)[0].conversation("jeton", GRP)["can_name_admins"]


def test_send_cites_members_and_keeps_everyone_tag_for_admins():
    chats, seen = fake()
    chats.send("jeton", GRP, "@léa et @tout : ce soir", None, None)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/group_messages")
    # @tout transmis tel quel : la base (guard_group_message) l'efface si l'auteur n'est pas admin du groupe.
    assert row["mentions"] == [LEA] and row["mention_all"] is True
    chats, seen = fake()
    chats.send("jeton", GRP, "Salut", M1, None, mentions=[TOM], message_id=M2)
    posts = [(p, b) for m, p, _, b in seen if m == "POST" or m == "GET"]
    assert [p for p, _ in posts] == ["/rest/v1/group_messages"]  # citations fournies par l'app : un seul appel
    assert posts[0][1]["mentions"] == [TOM] and posts[0][1]["id"] == M2 and posts[0][1]["reply_to"] == M1


def test_send_refuses_empty_messages_foreign_photos_and_reports_denials():
    chats, _ = fake()
    for body, photo in (("", None), ("x", "autre-groupe/1-abc.jpg")):
        try:
            chats.send("jeton", GRP, body, None, photo)
            raise AssertionError("refus attendu")
        except accounts_mod.AccountError:
            pass
    chats, _ = fake(write_status=403)
    try:
        chats.send("jeton", GRP, "Salut", None, None)
        raise AssertionError("refus attendu")
    except accounts_mod.AccountError as e:
        assert "row-level" in str(e) or "envoy" in str(e)


def test_photo_upload_goes_to_the_group_folder_and_rejects_non_images():
    chats, seen = fake()
    path = chats.upload_photo("jeton", GRP, JPEG)["path"]
    assert path.startswith(f"{GRP}/") and path.endswith(".jpg")
    assert any(p == f"/storage/v1/object/chat-photos/{path}" for _, p, _, _ in seen)
    for data in (b"", b"<svg>", JPEG[:3] + b"\0" * (gc.PHOTO_MAX)):
        try:
            chats.upload_photo("jeton", GRP, data)
            raise AssertionError("refus attendu")
        except accounts_mod.AccountError:
            pass


def test_reactions_pin_delete_notify_admin_and_read():
    chats, seen = fake()
    chats.react("jeton", M1, "🔥", True)
    chats.react("jeton", M1, "👍", False)
    delete = next(q for m, p, q, _ in seen if m == "DELETE")
    assert "user_id=eq.u-me" in delete and f"message_id=eq.{M1}" in delete
    try:
        chats.react("jeton", M1, "🍆", True)
        raise AssertionError("refus attendu")
    except accounts_mod.AccountError:
        pass
    try:
        chats.pin("jeton", M1, True)
        raise AssertionError("refus attendu")
    except accounts_mod.AccountError as e:
        assert "admins du groupe" in str(e)
    chats.delete("jeton", M1)
    assert chats.notify("jeton", GRP, "all") == {"notify": "all"}
    chats.set_admin("jeton", GRP, TOM, True)
    chats.read("jeton", GRP)
    rpcs = [(p.rsplit("/", 1)[1], b) for m, p, _, b in seen if p.startswith("/rest/v1/rpc/") and p.rsplit("/", 1)[1] not in ("my_chats",)]
    assert ("delete_group_message", {"msg": M1}) in rpcs
    assert ("set_group_chat_notify", {"grp": GRP, "level": "all"}) in rpcs
    assert ("set_group_admin", {"grp": GRP, "member": TOM, "admin": True}) in rpcs
    assert ("mark_group_read", {"grp": GRP}) in rpcs


def test_routes_validate_input_and_relay(monkeypatch):
    chats, _ = fake()
    monkeypatch.setattr(main, "group_chats", chats)
    client = TestClient(main.app)
    assert client.post("/api/account/chats", json={"token": "jeton"}).json()["chats"][0]["unread"] == 2
    assert client.post("/api/account/chats/open", json={"token": "jeton", "group_id": "pas-un-id"}).status_code == 422
    assert client.post("/api/account/chats/notify", json={"token": "jeton", "group_id": GRP, "level": "parfois"}).status_code == 422
    bad = client.post("/api/account/chats/send", json={"token": "jeton", "group_id": GRP, "body": "x", "photo_path": "../../etc"})
    assert bad.status_code == 422
    assert client.post("/api/account/chats/send", json={"token": "jeton", "group_id": GRP, "body": "Salut"}).json() == {"ok": True}
    photo = base64.b64encode(JPEG).decode()
    assert client.post("/api/account/chats/photo", json={"token": "jeton", "group_id": GRP, "photo": photo}).json()["path"].startswith(GRP)
    assert client.post("/api/account/chats/photo", json={"token": "jeton", "group_id": GRP, "photo": "@@@"}).status_code == 400
    assert client.post("/api/account/chats/open", json={"token": "jeton", "group_id": GRP}).json()["name"] == "Les amis"


M4A = b"\x00\x00\x00\x1cftypM4A " + b"\x00" * 32


def test_voice_messages_are_uploaded_and_sent():
    assert gc.audio_kind(M4A) == ("audio/mp4", "m4a")
    assert gc.audio_kind(b"\x1a\x45\xdf\xa3" + b"\x00" * 8) == ("audio/webm", "webm")
    assert gc.audio_kind(b"OggS\x00") == ("audio/ogg", "ogg") and gc.audio_kind(JPEG) is None
    chats, seen = fake()
    path = chats.upload_audio("jeton", GRP, M4A)["path"]
    assert path.startswith(f"{GRP}/") and path.endswith(".m4a")
    try:
        chats.upload_audio("jeton", GRP, JPEG)
        raise AssertionError("refus attendu")
    except accounts_mod.AccountError:
        pass
    chats.send("jeton", GRP, "", None, None, mentions=[], audio_path=path, audio_seconds=7.26)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/group_messages")
    assert row["audio_path"] == path and row["audio_seconds"] == 7.3 and row["body"] == ""
    try:
        chats.send("jeton", GRP, "", None, None, mentions=[], audio_path="autre/1-abc.m4a")
        raise AssertionError("refus attendu")
    except accounts_mod.AccountError:
        pass
