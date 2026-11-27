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


def fake(admin=False, rank=1, creator=LEA, write_status=201, organizer=LEA, blocked=(), embed=False, write_body=None):
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
                                              "unread": 2, "last": "Léa : Salut", "last_at": "2026-10-29T10:00:00Z",
                                              "kind": "group", "emoji": "⚽", "color": "mint"}])
        if path == "/rest/v1/member_groups":
            return httpx.Response(200, json=[{"id": GRP, "name": "Les amis", "created_by": creator, "everyone_tag": "staff",
                                              "member_group_members": [{"user_id": ME}, {"user_id": LEA}, {"user_id": TOM}]}])
        if path == "/rest/v1/group_messages" and request.method == "GET" and embed and "group_message_reactions(" in str(request.url.query, "ascii"):
            # Base réelle (PostgREST) : réactions jointes à chaque message, liste vide comprise.
            return httpx.Response(200, json=[
                {"id": M2, "user_id": ME, "body": "Oui !", "photo_path": None, "reply_to": M1, "pinned": False,
                 "created_at": "2026-10-29T10:01:00Z", "deleted_at": None, "group_message_reactions": []},
                {"id": M1, "user_id": LEA, "body": "Tu viens ?", "photo_path": None, "reply_to": None, "pinned": False,
                 "created_at": "2026-10-29T10:00:00Z", "deleted_at": None,
                 "group_message_reactions": [{"message_id": M1, "user_id": ME, "emoji": "👍"}, {"message_id": M1, "user_id": TOM, "emoji": "👍"}]}])
        if path == "/rest/v1/group_messages" and request.method == "GET":
            return httpx.Response(200, json=[  # du plus récent au plus ancien, comme la base
                {"id": M3, "user_id": LEA, "body": "", "photo_path": None, "reply_to": None, "pinned": True,
                 "created_at": "2026-10-29T10:02:00Z", "deleted_at": "2026-10-29T10:03:00Z", "deleted_by_admin": True},
                {"id": M2, "user_id": ME, "body": "Oui !", "photo_path": f"{GRP}/1-abc.jpg", "reply_to": M1, "pinned": False,
                 "created_at": "2026-10-29T10:01:00Z", "deleted_at": None, "edited_at": "2026-10-29T10:01:30Z"},
                {"id": M1, "user_id": LEA, "body": "Tu viens ?", "photo_path": None, "reply_to": None, "pinned": True,
                 "created_at": "2026-10-29T10:00:00Z", "deleted_at": None}])
        if path == "/rest/v1/group_messages":
            return httpx.Response(write_status, json=write_body or ({"message": "new row violates row-level security policy"} if write_status >= 400 else None))
        if path == "/rest/v1/group_message_reactions" and request.method == "GET":
            return httpx.Response(200, json=[{"message_id": M1, "user_id": ME, "emoji": "👍"},
                                             {"message_id": M1, "user_id": TOM, "emoji": "👍"},
                                             {"message_id": M1, "user_id": TOM, "emoji": "😂"}])
        if path == "/rest/v1/group_message_reactions":
            return httpx.Response(201 if request.method == "POST" else 204)
        if path == "/rest/v1/direct_blocks":
            return httpx.Response(200, json=[{"blocked_id": b} for b in blocked])
        if path == "/rest/v1/group_admins":
            return httpx.Response(200, json=[{"user_id": TOM}])
        if path == "/rest/v1/group_organizers":
            return httpx.Response(200, json=[{"user_id": organizer}] if organizer else [])
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
    assert mine["reply"] == {"id": M1, "author": LEA, "name": "Léa", "text": "Tu viens ?"}
    assert mine["author_photo"].endswith("/profile-photos/me.jpg?t=1")
    # Supprimé par un admin : le texte le dit, plus d'épingle ni de photo
    assert removed["deleted"] and removed["body"] == "Message supprimé par un admin" and not removed["pinned"]
    assert [m["name"] for m in c["members"]] == ["Boby", "Léa", "Tom"]
    assert [m["creator"] for m in c["members"]] == [False, True, False] and c["members"][2]["admin"]
    assert [m["phone"] for m in c["members"]] == [None, "+41790000001", None]  # seul le numéro montré dans ce groupe
    assert gc.dialable("+41 79 000 00 01") == "+41790000001" and gc.dialable("12") is None and gc.dialable(None) is None
    assert c["notify"] == "mentions" and c["member"] and not c["admin"] and not c["can_name_admins"]
    assert c["reactions"] == list(gc.REACTIONS)


def test_chat_list_keeps_the_group_emoji_and_color_for_the_app():
    """Nouveau graphisme des groupes (17.11) : la ligne de Discussions de l'app porte l'emoji et la couleur du groupe."""
    row = fake()[0].chats("jeton")["chats"][0]
    assert row["emoji"] == "⚽" and row["color"] == "mint" and row["unread"] == 2


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


def test_production_has_no_discussions_but_blocking_still_works(monkeypatch):
    """Décision du 04.11 : Discussions absentes hors site de test (DISCUSSIONS_ENABLED) ; leurs routes répondent 404,
    même pour un bêta-testeur. Bloquer une personne reste possible (commun à toute l'app)."""
    chats, _ = fake()
    monkeypatch.setattr(main, "group_chats", chats)
    monkeypatch.setenv("DISCUSSIONS_ENABLED", "0")
    client = TestClient(main.app)
    for path, body in (("/api/account/chats", {"token": "jeton"}), ("/api/account/chats/send", {"token": "jeton", "group_id": GRP, "body": "Salut"}),
                       ("/api/account/chats/direct", {"token": "jeton", "user_id": LEA})):
        refused = client.post(path, json=body)
        assert refused.status_code == 404 and refused.json()["detail"] == main.DISCUSSIONS_OFF
    assert client.post("/api/account/chats/block", json={"token": "jeton", "user_id": LEA, "on": True}).status_code != 404
    monkeypatch.setenv("DISCUSSIONS_ENABLED", "1")
    assert client.post("/api/account/chats", json={"token": "jeton"}).json()["chats"][0]["unread"] == 2


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


def test_mentions_ignore_accents_and_case():
    """Suggestions de l'@ (avis du 3.11) : « @lea » ou « @LÉA » citent Léa, comme l'app qui les insère."""
    people = {LEA: "Léa", TOM: "Tom", ME: "Boby"}
    assert gc.mentions_in("Salut @lea et @TOM", people, ME) == [LEA, TOM]
    assert gc.mentions_in("@Boby moi-même", people, ME) == []
    assert gc.fold("Élodie Çà") == "elodie ca"


def test_conversation_marks_announcements_and_keeps_highlights_on_top():
    """@annonce (avis du 3.11) : la base l'épingle ; l'app reçoit le drapeau et la liste du bandeau (sans les supprimés)."""
    chats, seen = fake()
    c = chats.conversation("jeton", GRP)
    assert all("announcement" in m for m in c["messages"])
    assert [h["id"] for h in c["highlights"]] == [M1]  # M3 épinglé mais supprimé : hors du bandeau
    assert c["highlights"][0] == {"id": M1, "author_name": "Léa", "at": "2026-10-29T10:00:00Z", "text": "Tu viens ?", "announcement": False}
    assert any("pinned=is.true" in q and "deleted_at=is.null" in q for m, p, q, _ in seen if p == "/rest/v1/group_messages")


def test_the_group_rights_tell_the_app_who_writes_and_pins():
    """« Qui peut… » du groupe (23.11) : écrire et épingler, d'après group_my_rights ; base d'avant : rien (comme avant)."""
    chats, seen = fake()
    c = chats.conversation("jeton", GRP)
    assert "can_write" not in c and "can_pin" not in c
    assert any(p.endswith("/rpc/group_my_rights") for _, p, _, _ in seen)
    chats._rights = lambda token, group: {"write": False, "pin": True}
    c = chats.conversation("jeton", GRP)
    assert c["can_write"] is False and c["can_pin"] is True


def test_everyone_tag_is_sent_for_any_member():
    chats, seen = fake(admin=False)
    chats.send("jeton", GRP, "@tout on part à 20h", None, None)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/group_messages")
    assert row["mention_all"] is True


def test_conversation_tells_organizers_and_who_may_write_everyone():
    """Rôle « Organisateur » et choix du groupe pour @tout (réponses de l'admin du 3.11)."""
    c = fake()[0].conversation("jeton", GRP)
    assert c["everyone"] == "staff" and c["organizer"] is False
    assert {m["id"]: m["organizer"] for m in c["members"]} == {ME: False, LEA: True, TOM: False}
    assert fake(organizer=ME)[0].conversation("jeton", GRP)["organizer"] is True
    assert fake(admin=True, organizer=None)[0].conversation("jeton", GRP)["organizer"] is True  # admin : organisateur d'office


def test_admins_name_organizers_and_choose_who_writes_everyone(monkeypatch):
    chats, seen = fake(admin=True)
    chats.set_organizer("jeton", GRP, LEA, True)
    chats.set_everyone("jeton", GRP, "all")
    rpcs = [(p, b) for m, p, _, b in seen if p.startswith("/rest/v1/rpc/set_group_")]
    assert rpcs == [("/rest/v1/rpc/set_group_organizer", {"grp": GRP, "member": LEA, "organizer": True}),
                    ("/rest/v1/rpc/set_group_everyone_tag", {"grp": GRP, "who": "all"})]
    calls = []
    monkeypatch.setattr(main, "group_chats", type("G", (), {
        "set_organizer": lambda self, *a: calls.append(("org",) + a) or {"ok": True},
        "set_everyone": lambda self, *a: calls.append(("all",) + a) or {"everyone": a[-1]}})())
    c = TestClient(main.app)
    member = "22222222-2222-2222-2222-222222222222"
    assert c.post("/api/account/chats/organizer", json={"token": "t", "group_id": GRP, "user_id": member, "on": True}).status_code == 200
    assert c.post("/api/account/chats/everyone", json={"token": "t", "group_id": GRP, "who": "staff"}).status_code == 200
    assert c.post("/api/account/chats/everyone", json={"token": "t", "group_id": GRP, "who": "moi"}).status_code == 422
    assert calls == [("org", "t", GRP, member, True), ("all", "t", GRP, "staff")]


def test_database_keys_never_show_before_the_sentence():
    """Recette du 27.11 : « request_pending: … » s'affichait tel quel ; toutes les clés de la base sont retirées."""
    for key in ("request_pending", "limit", "edit_window", "locked", "pin_limit", "forbidden"):
        r = httpx.Response(400, json={"message": f"{key}: Une phrase claire."})
        assert ga.readable(r, "x") == "Une phrase claire.", key


def test_messages_of_someone_i_blocked_are_masked_in_a_group():
    """App Store 1.2 : bloquer quelqu'un masque aussitôt ses messages (texte, photo, vocal) et ses épinglés dans les groupes."""
    chats, _seen = fake(blocked=(LEA,))
    conv = chats.conversation("tok", GRP)
    lea = [m for m in conv["messages"] if m.get("author_name") == "Léa" and not m.get("deleted")]
    assert lea and all(m["body"] == gc.BLOCKED_TEXT and not m.get("photo") and not m.get("audio") for m in lea), lea
    assert all(h["author_name"] != "Léa" for h in conv["highlights"])


def test_the_conversation_reads_reactions_with_the_messages_in_one_round_trip():
    """Vitesse (18.11) : réactions jointes aux messages (PostgREST), plus de deuxième vague de lectures pour elles."""
    chats, seen = fake(embed=True)
    c = chats.conversation("jeton", GRP)
    assert [m["id"] for m in c["messages"]] == [M1, M2]
    assert c["messages"][0]["reactions"] == [{"emoji": "👍", "count": 2, "mine": True}]
    assert "group_message_reactions" not in c["messages"][0]
    assert not [p for m, p, _, _ in seen if p == "/rest/v1/group_message_reactions"]


def test_a_preloaded_conversation_leaves_the_join_note_for_the_real_opening():
    """Préchargement par la liste (iPhone) : lecture seule, le bandeau « Tu es dans le groupe » n'est pas consommé."""
    chats, seen = fake()
    chats.conversation("jeton", GRP, prefetch=True)
    assert not [p for m, p, _, _ in seen if p.endswith("/take_group_join_note")]
    chats.conversation("jeton", GRP)
    assert [p for m, p, _, _ in seen if p.endswith("/take_group_join_note")]


def test_a_retried_message_already_saved_counts_as_sent():
    """Envoi optimiste : réponse perdue puis nouvel essai avec le même identifiant → la base dit « déjà là » = envoyé."""
    chats, _ = fake(write_status=409, write_body={"code": "23505", "message": "duplicate key value violates unique constraint"})
    assert chats.send("jeton", GRP, "Salut", None, None, mentions=[], message_id=M2) == {"ok": True}
    chats, _ = fake(write_status=409, write_body={"code": "23505", "message": "duplicate key"})
    try:
        chats.send("jeton", GRP, "Salut", None, None, mentions=[])  # sans identifiant : un vrai refus
        raise AssertionError("refus attendu")
    except Exception as e:  # noqa: BLE001
        assert "AssertionError" not in type(e).__name__
