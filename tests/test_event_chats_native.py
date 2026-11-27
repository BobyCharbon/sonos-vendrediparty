"""Discussion d'un événement pour l'app iPhone native (16.11.2026) : relais vers Supabase avec la session du membre,
même forme qu'une discussion de groupe (event = True) ; la base décide des droits (migration 20261116180000).
17.11 (migration 20261117190000) : niveau Tout / Mentions / Rien, sourdine, non-lus, « Qui peut écrire », description,
carte de l'événement, médias / liens, recherche, messages plus anciens."""
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, event_chats as ec, group_admin as ga, group_chats as gc, main

ME, LEA, TOM, VAL = "u-me", "u-lea", "u-tom", "u-val"
EV = "22222222-2222-2222-2222-222222222222"
M1, M2, M3 = ("bbbbbbbb-0000-0000-0000-00000000000" + str(i) for i in (1, 2, 3))
M0 = "bbbbbbbb-0000-0000-0000-000000000000"
COVER = "https://party.example/covers/0123456789abcdef01234567.jpg"
REFUSED = {"code": "P0001", "message": "forbidden: Seule l'organisation peut changer ces réglages."}


def fake(staff=False, write=True, muted=False, blocked=(), patched=True, forum=True, state=None, refuse=(), event=True):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else None
        query = str(request.url.query, "ascii")
        seen.append((request.method, request.url.path, query, body))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path.rsplit("/", 1)[-1] in refuse:
            return httpx.Response(400, json=REFUSED)
        if path == "/rest/v1/rpc/event_chat_state":
            return httpx.Response(200, json={"title": "Raclette", "forum": forum, "status": "published", "write": write,
                                             "staff": staff, "moderate": False, "muted": muted, **(state or {})})
        if path == "/rest/v1/rpc/event_chat_people":
            return httpx.Response(200, json=[
                {"id": ME, "display_name": "Boby", "avatar_url": "me.jpg", "rsvp": "yes", "organizer": False, "invited": False},
                {"id": LEA, "display_name": "Léa", "avatar_url": None, "rsvp": "maybe", "organizer": True, "invited": False},
                {"id": TOM, "display_name": "Tom", "avatar_url": None, "rsvp": None, "organizer": False, "invited": staff}])
        if path == "/rest/v1/rpc/event_chat_taggable":  # Léa (Peut-être) et Val (invitée sans réponse), migration 20261122131000
            return httpx.Response(200, json=[{"id": VAL, "display_name": "Val", "avatar_url": "val.jpg"},
                                             {"id": LEA, "display_name": "Léa", "avatar_url": None}])
        if path == "/rest/v1/rpc/event_chat_set_level":
            return httpx.Response(200, json={"level": body["level"]})
        if path == "/rest/v1/rpc/event_chat_mute":
            return httpx.Response(200, json={"muted_until": body["until"]})
        if path == "/rest/v1/rpc/event_chat_mark_read":
            return httpx.Response(200, json={"unread": 0})
        if path == "/rest/v1/rpc/event_chat_set_settings":
            return httpx.Response(200, json={"write_mode": body["write"] or "all", "description": body["description"]})
        if path == "/rest/v1/rpc/event_chat_media":
            return httpx.Response(200, json=[
                {"message_id": M2, "kind": "photo", "path": f"{EV}/2-abcdef0123.jpg", "at": "2026-11-16T10:01:00Z", "author": ME},
                {"message_id": M3, "kind": "audio", "path": f"{EV}/3-abcdef0123.m4a", "at": "2026-11-16T10:02:00Z", "author": TOM},
                {"message_id": M1, "kind": "link", "url": "https://maps.app/parking", "at": "2026-11-16T10:00:00Z", "author": LEA},
                {"message_id": M1, "kind": "link", "body": "Plan : http://a.ch/x. et javascript:alert(1)",
                 "at": "2026-11-16T10:00:00Z", "author": LEA},
                {"message_id": M1, "kind": "link", "url": "javascript:alert(1)", "at": "2026-11-16T10:00:00Z", "author": LEA}])
        if path == "/rest/v1/rpc/event_chat_search":
            return httpx.Response(200, json=[
                {"message_id": M1, "at": "2026-11-16T10:00:00Z", "author": LEA, "snippet": "… Parking derrière"},
                {"message_id": M3, "at": "2026-11-16T10:02:00Z", "author": TOM, "snippet": "… parking ?"}])
        if path == "/rest/v1/events" and request.method == "GET":
            if not event:
                return httpx.Response(404)
            return httpx.Response(200, json=[{"title": "Raclette chez Léa", "starts_at": "2026-11-21T18:00:00Z",
                                              "ends_at": None, "location_name": "Chalet", "cover_url": COVER, "created_by": LEA}])
        if path == "/rest/v1/messages" and request.method == "GET":
            if "pinned=is.true" in query:
                return httpx.Response(200, json=[{"id": M1, "user_id": LEA, "body": "@annonce Parking derrière", "pinned": True,
                                                  "announcement": True, "created_at": "2026-11-16T10:00:00Z", "deleted_at": None}])
            if "select=id,created_at" in query:  # message de référence de /older
                return httpx.Response(200, json=[{"id": M2, "created_at": "2026-11-16T10:01:00+00:00"}] if M2 in query else [])
            if "id=in." in query:  # message cité hors de la page
                return httpx.Response(200, json=[{"id": M0, "user_id": TOM, "body": "Qui amène le fromage ?", "photo_path": None,
                                                  "created_at": "2026-11-15T10:00:00Z", "deleted_at": None}])
            if "or=" in query:  # page précédente
                return httpx.Response(200, json=[
                    {"id": M1, "user_id": LEA, "body": "Moi !", "photo_path": None, "reply_to": M0, "pinned": False,
                     "created_at": "2026-11-16T10:00:00Z", "deleted_at": None}])
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


def rpc(seen, name):
    return [b for m, p, _, b in seen if p == f"/rest/v1/rpc/{name}"]


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
    assert c["members"][0]["photo"].endswith("/profile-photos/me.jpg?t=1")
    # @toutlemonde, @present, @annonce : proposés seulement à l'organisation (la base décide de toute façon).
    assert c["tags"] == []
    assert [t["tag"] for t in fake(staff=True)[0].conversation("jeton", EV)["tags"]] == ["toutlemonde", "present", "annonce"]


def test_conversation_has_level_mute_unread_write_mode_and_the_event_card():
    c = fake(state={"level": "all", "muted_until": None, "unread": 4, "write_mode": "staff",
                    "description": "Apporte ta luge", "can_write": False})[0].conversation("jeton", EV)
    assert (c["level"], c["muted_until"], c["unread"], c["write_mode"], c["description"], c["can_write"]) == \
        ("all", None, 4, "staff", "Apporte ta luge", False)
    assert c["event_card"] == {"title": "Raclette chez Léa", "starts_at": "2026-11-21T18:00:00Z", "ends_at": None,
                               "place": "Chalet", "cover": COVER, "going": 1, "maybe": 1, "organizer_name": "Léa"}
    # Base d'avant la migration du 17.11 (champs absents) et événement illisible : valeurs par défaut, carte de l'état.
    c = fake(event=False)[0].conversation("jeton", EV)
    assert (c["level"], c["unread"], c["write_mode"], c["description"], c["can_write"]) == ("mentions", 0, "all", None, True)
    assert c["event_card"]["title"] == "Raclette" and c["event_card"]["cover"] is None and c["event_card"]["going"] == 1


def test_old_apps_still_read_notify_all_or_none():
    assert fake(state={"level": "mentions"})[0].conversation("jeton", EV)["notify"] == "all"
    assert fake(state={"level": "none"})[0].conversation("jeton", EV)["notify"] == "none"
    assert fake(state={"level": "all", "muted_until": "infinity"})[0].conversation("jeton", EV)["notify"] == "none"
    assert fake(state={"level": "all", "muted_until": "2999-01-01T00:00:00+00:00"})[0].conversation("jeton", EV)["notify"] == "none"
    assert fake(state={"level": "all", "muted_until": "2000-01-01T00:00:00+00:00"})[0].conversation("jeton", EV)["notify"] == "all"
    assert fake(muted=True)[0].conversation("jeton", EV)["notify"] == "none"  # événement coupé depuis la fiche


def test_blocked_people_are_masked_and_a_closed_discussion_is_refused():
    c = fake(blocked=(TOM,))[0].conversation("jeton", EV)
    assert c["messages"][2]["body"] == gc.BLOCKED_TEXT and c["messages"][2]["audio"] is None and c["messages"][2]["audio_seconds"] is None
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


def test_any_participant_can_cite_the_people_the_base_allows():
    """Avis f0e2fd838ab8 (22.11) : les suggestions de l'@ sont celles de la base (event_chat_taggable : organisation,
    Présent, Peut-être, invités sans réponse hors événement public), jamais une personne bloquée."""
    c = fake()[0].conversation("jeton", EV)
    assert [(t["id"], t["name"]) for t in c["taggable"]] == [(LEA, "Léa"), (VAL, "Val")]
    assert c["taggable"][1]["photo"].endswith("/profile-photos/val.jpg?t=1")
    assert VAL not in [m["id"] for m in c["members"]]  # la liste des participants ne change pas
    assert [t["id"] for t in fake(blocked=(VAL,))[0].conversation("jeton", EV)["taggable"]] == [LEA]
    # Envoi sans liste (ancienne app) : les citations se cherchent parmi les personnes permises.
    chats, seen = fake()
    chats.send("jeton", EV, "@Val tu viens ? @Tom", None, None, None, None, None, None, False)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/messages")
    assert row["mentions"] == [VAL]
    # Base d'avant la migration : Présent, Peut-être et organisation.
    c = fake(refuse=("event_chat_taggable",))[0].conversation("jeton", EV)
    assert [t["id"] for t in c["taggable"]] == [LEA]


def test_pin_delete_react():
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
    assert ("POST", "/rest/v1/message_reactions") in [(m, p) for m, p, _, _ in seen]


def test_notify_sets_the_level_and_all_also_unmutes_the_event_like_before():
    chats, seen = fake()
    assert chats.notify("jeton", EV, "mentions") == {"level": "mentions", "notify": "all"}
    assert chats.notify("jeton", EV, "none") == {"level": "none", "notify": "none"}
    assert not [p for m, p, _, _ in seen if p == "/rest/v1/event_mutes"]  # « Rien » ne coupe plus tout l'événement
    assert chats.notify("jeton", EV, "all")["notify"] == "all"
    assert [b["level"] for b in rpc(seen, "event_chat_set_level")] == ["mentions", "none", "all"]
    assert all(b["e"] == EV for b in rpc(seen, "event_chat_set_level"))
    # Ancienne app restée sur « Rien » (event_mutes du 16.11) : « Tout » la rend, comme avant.
    assert [(m, q) for m, p, q, _ in seen if p == "/rest/v1/event_mutes"] == [("DELETE", f"event_id=eq.{EV}&user_id=eq.{ME}")]
    try:
        chats.notify("jeton", EV, "souvent")
        raise AssertionError("niveau inconnu accepté")
    except accounts_mod.AccountError:
        pass


def test_mute_read_and_settings_relay_to_the_base():
    chats, seen = fake()
    assert chats.mute("jeton", EV, "always") == {"muted_until": "infinity"}
    chats.mute("jeton", EV, "2026-11-18T08:00:00Z")
    chats.mute("jeton", EV, "2026-11-18T08:00:00")  # sans fuseau : UTC
    chats.mute("jeton", EV, None)
    assert [b["until"] for b in rpc(seen, "event_chat_mute")] == ["infinity", "2026-11-18T08:00:00+00:00",
                                                                  "2026-11-18T08:00:00+00:00", None]
    try:
        chats.mute("jeton", EV, "demain")
        raise AssertionError("date illisible acceptée")
    except accounts_mod.AccountError:
        pass
    assert chats.read("jeton", EV) == {"unread": 0} and rpc(seen, "event_chat_mark_read") == [{"e": EV}]
    assert chats.settings("jeton", EV, "staff", None) == {"write_mode": "staff", "description": None}
    chats.settings("jeton", EV, None, "Apporte ta luge")
    assert rpc(seen, "event_chat_set_settings") == [{"e": EV, "write": "staff", "description": None},
                                                    {"e": EV, "write": None, "description": "Apporte ta luge"}]


def test_settings_refused_by_the_base_give_its_sentence():
    try:
        fake(refuse=("event_chat_set_settings",))[0].settings("jeton", EV, "staff", None)
        raise AssertionError("réglage accepté")
    except accounts_mod.AccountError as e:
        assert str(e) == "Seule l'organisation peut changer ces réglages."


def test_media_signs_files_keeps_only_http_links_and_hides_blocked_people():
    chats, seen = fake()
    items = chats.media("jeton", EV, None)["items"]
    assert [(i["kind"], i["author_name"]) for i in items] == [("photo", "Boby"), ("audio", "Tom"), ("link", "Léa"), ("link", "Léa")]
    assert items[0]["url"].endswith(f"/chat-photos/{EV}/2-abcdef0123.jpg?t=1") and items[0]["message_id"] == M2
    assert items[1]["url"].endswith(f"/chat-photos/{EV}/3-abcdef0123.m4a?t=1")
    assert [i["url"] for i in items[2:]] == ["https://maps.app/parking", "http://a.ch/x"]  # jamais javascript:
    assert rpc(seen, "event_chat_media") == [{"e": EV}]
    chats, seen = fake(blocked=(TOM,))
    items = chats.media("jeton", EV, "2026-11-16T10:00:00Z")["items"]
    assert "Tom" not in [i["author_name"] for i in items]
    assert rpc(seen, "event_chat_media") == [{"e": EV, "before": "2026-11-16T10:00:00Z"}]


def test_search_names_authors_and_hides_blocked_people():
    chats, seen = fake()
    assert chats.search("jeton", EV, "  parking ")["results"] == [
        {"message_id": M1, "at": "2026-11-16T10:00:00Z", "author_name": "Léa", "snippet": "… Parking derrière"},
        {"message_id": M3, "at": "2026-11-16T10:02:00Z", "author_name": "Tom", "snippet": "… parking ?"}]
    assert rpc(seen, "event_chat_search") == [{"e": EV, "q": "parking"}]
    assert [r["author_name"] for r in fake(blocked=(TOM,))[0].search("jeton", EV, "parking")["results"]] == ["Léa"]
    assert fake()[0].search("jeton", EV, "   ") == {"results": []}


def test_older_gives_the_previous_page_with_the_same_shape_and_quotes_outside_the_page():
    chats, seen = fake(blocked=(TOM,))
    page = chats.older("jeton", EV, M2)
    assert page["more"] is False and [m["id"] for m in page["messages"]] == [M1]
    m = page["messages"][0]
    assert m["author_name"] == "Léa" and m["reactions"] == [{"emoji": "🔥", "count": 1, "mine": False}]
    # Citation d'un message plus ancien que la page, d'une personne bloquée : masquée.
    assert m["reply"] == {"id": M0, "author": TOM, "name": "Tom", "text": gc.BLOCKED_TEXT}
    q = next(q for meth, p, q, _ in seen if p == "/rest/v1/messages" and "or=" in q)
    assert "created_at.lt.2026-11-16T10%3A01%3A00%2B00%3A00" in q and f"id.lt.{M2}" in q
    try:
        chats.older("jeton", EV, M3)
        raise AssertionError("message inconnu accepté")
    except accounts_mod.AccountError:
        pass


def test_routes_relay_to_the_event_chats_and_stay_open_without_discussions(monkeypatch):
    chats, seen = fake()
    monkeypatch.setattr(main, "event_chats", chats)
    monkeypatch.setenv("DISCUSSIONS_ENABLED", "0")
    client = TestClient(main.app)
    ref = {"token": "jeton", "event_id": EV}
    r = client.post("/api/account/event-chat/open", json=ref)
    assert r.status_code == 200 and r.json()["event"] and r.json()["event_card"]["cover"] == COVER
    r = client.post("/api/account/event-chat/send", json={**ref, "body": "Salut", "announcement": False})
    assert r.status_code == 200
    for level in ("all", "mentions", "none"):  # anciennes apps : all / none ; nouvelles : mentions aussi
        assert client.post("/api/account/event-chat/notify", json={**ref, "level": level}).status_code == 200
    assert client.post("/api/account/event-chat/notify", json={**ref, "level": "souvent"}).status_code == 422
    assert client.post("/api/account/event-chat/mute", json={**ref, "until": "always"}).json() == {"muted_until": "infinity"}
    assert client.post("/api/account/event-chat/mute", json={**ref, "until": None}).status_code == 200
    assert client.post("/api/account/event-chat/read", json=ref).json() == {"unread": 0}
    assert client.post("/api/account/event-chat/settings", json={**ref, "write": "staff"}).status_code == 200
    assert client.post("/api/account/event-chat/settings", json={**ref, "write": "admins"}).status_code == 422
    assert client.post("/api/account/event-chat/settings", json={**ref, "description": "x" * 501}).status_code == 422
    assert len(client.post("/api/account/event-chat/media", json=ref).json()["items"]) == 4
    assert len(client.post("/api/account/event-chat/search", json={**ref, "q": "parking"}).json()["results"]) == 2
    assert client.post("/api/account/event-chat/search", json={**ref, "q": ""}).status_code == 422
    r = client.post("/api/account/event-chat/older", json={**ref, "before_id": M2})
    assert r.status_code == 200 and [m["id"] for m in r.json()["messages"]] == [M1]
    assert client.post("/api/account/event-chat/older", json={**ref, "before_id": "pas-un-id"}).status_code == 422


def test_routes_give_the_base_refusal(monkeypatch):
    monkeypatch.setattr(main, "event_chats", fake(refuse=("event_chat_set_settings", "event_chat_set_level"))[0])
    client = TestClient(main.app)
    ref = {"token": "jeton", "event_id": EV}
    for path, extra in (("settings", {"write": "staff"}), ("notify", {"level": "mentions"})):
        r = client.post(f"/api/account/event-chat/{path}", json={**ref, **extra})
        assert r.status_code == 400 and r.json()["detail"] == "Seule l'organisation peut changer ces réglages."
