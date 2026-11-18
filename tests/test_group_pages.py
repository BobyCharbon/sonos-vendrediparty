"""Groupes en natif dans l'app iPhone (18.11, « tout en natif ») : app/group_pages.py par le relais
POST /api/account/chats/rpc — mêmes lectures et écritures que les pages web, avec la session du membre (la base décide),
photos signées, refus de la base gardés, liens à l'adresse publique, photo du groupe envoyée par le serveur.
La base est testée pour de vrai dans tests/supabase_live/test_groupes_natifs_live.py."""
import base64
import json

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, chat_rpc, group_admin as ga, group_chats as gc, group_pages

ME = "aaaaaaaa-0000-4000-8000-000000000001"
LEA = "bbbbbbbb-0000-4000-8000-000000000002"
NOE = "cccccccc-0000-4000-8000-000000000003"
GRP = "11111111-1111-4111-8111-111111111111"
EV1 = "e1e1e1e1-0000-4000-8000-000000000001"
EV2 = "e2e2e2e2-0000-4000-8000-000000000002"
JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


def fake(group=None, rpc=None, writes=None, perms=("events.create",), rank=1):
    """Faux Supabase : une ligne de member_groups, des réponses de fonctions, des écritures (méthode → réponse)."""
    seen = []
    rpc = {"my_permissions": list(perms), "my_rank": rank, "my_privacy": {"phone_groups": [GRP]}, **(rpc or {})}
    writes = writes or {}

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else None
        path, method = request.url.path, request.method
        seen.append((method, path + (f"?{request.url.query.decode()}" if request.url.query else ""), body))
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        if path.startswith("/rest/v1/rpc/"):
            name = path.removeprefix("/rest/v1/rpc/")
            value = rpc.get(name, [])
            return httpx.Response(value[0], json=value[1]) if isinstance(value, tuple) else httpx.Response(200, json=value)
        key = (method, path.split("/")[-1] if path.startswith("/storage/") is False else "storage")
        if key in writes:
            status, answer = writes[key]
            return httpx.Response(status, json=answer)
        if method == "GET" and path == "/rest/v1/member_groups":
            return httpx.Response(200, json=[group] if group else [])
        if method == "GET" and path == "/rest/v1/profiles":
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={})

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    admin = ga.GroupAdmin(acc)
    app = FastAPI()
    app.include_router(chat_rpc.chat_rpc_router(gc.GroupChats(admin), lambda t: f"https://party.example/events/group-invite/{t}"))
    return TestClient(app), seen


def call(client, fn, **args):
    return client.post("/api/account/chats/rpc", json={"token": "t", "fn": fn, "args": args})


def row(**kw):
    return {"id": GRP, "name": "La bande", "emoji": "🎸", "color": "mint", "photo_path": f"{GRP}/cover.jpg", "created_by": ME,
            "created_at": "2026-11-01T10:00:00Z", "system_key": None, "private_chat": False, "events_need_approval": False,
            "announce_mode": "request", "member_group_members": [{"user_id": ME}, {"user_id": LEA}, {"user_id": NOE}], **kw}


PEOPLE = [{"id": LEA, "display_name": "Léa", "avatar_url": f"{LEA}/me.jpg", "member": True},
          {"id": NOE, "display_name": "Noé", "avatar_url": None, "member": True},
          {"id": ME, "display_name": "Moi", "avatar_url": None, "member": True}]


def test_the_group_page_gives_rights_members_events_and_signed_photos():
    client, _ = fake(row(), rpc={
        "group_chat_people": PEOPLE,
        "my_groups_overview": [{"id": GRP, "unread": 4, "manage": True}],
        "group_events": [{"id": EV1, "upcoming": True}, {"id": EV2, "upcoming": False}, {"id": "invisible", "upcoming": True}],
        "chat_event_cards": [{"id": EV2, "title": "Bowling"}, {"id": EV1, "title": "Fondue", "cover": "https://x/c.jpg"}],
    })
    r = call(client, "group_page", grp=GRP)
    assert r.status_code == 200, r.text
    page = r.json()["result"]
    assert page["group"]["photo"].endswith(f"/group-photos/{GRP}/cover.jpg?t=1")
    assert page["member"] and page["manage"] and page["creator"] and page["can_create_event"] and page["can_set_rules"]
    assert page["phone_shared"] and page["unread"] == 4 and page["group"]["created_by_name"] == "Moi"
    # Créateur d'abord, puis par surnom ; photo de Léa signée dans profile-photos.
    assert [m["name"] for m in page["members"]] == ["Moi", "Léa", "Noé"]
    assert page["members"][1]["photo"].endswith(f"/profile-photos/{LEA}/me.jpg?t=1") and page["members"][2]["photo"] is None
    # Seulement les événements que chat_event_cards rend (ceux que je peux voir), dans l'ordre de group_events.
    assert [e["title"] for e in page["upcoming"]] == ["Fondue"] and [e["title"] for e in page["past"]] == ["Bowling"]


def test_members_vendredi_party_never_has_a_photo_nor_management_and_a_simple_member_cannot_manage():
    client, _ = fake(row(system_key="vip", created_by=None, photo_path="x/y.jpg"), rpc={"group_chat_people": PEOPLE})
    page = call(client, "group_page", grp=GRP).json()["result"]
    assert page["group"]["system"] and page["group"]["photo"] is None
    assert not page["manage"] and not page["creator"] and not page["can_set_rules"]  # rang 1 : pas Co-admin
    client, _ = fake(row(created_by=LEA), rpc={"group_chat_people": PEOPLE}, perms=())
    page = call(client, "group_page", grp=GRP).json()["result"]
    assert page["member"] and not page["manage"] and not page["can_create_event"]


def test_a_group_i_cannot_see_is_gone_and_a_bad_id_is_refused():
    client, _ = fake(None)
    r = call(client, "group_page", grp=GRP)
    assert r.status_code == 404 and r.json()["code"] == "not_found"
    assert call(client, "group_page", grp="pas-un-uuid").status_code == 400


def test_creating_a_group_uses_the_closed_lists_and_joins_its_creator():
    client, seen = fake(writes={("POST", "member_groups"): (201, [{"id": GRP}]), ("POST", "member_group_members"): (201, [])})
    r = call(client, "group_create", name="  Soirées   du vendredi ", emoji="💣", color="noir")
    assert r.status_code == 200 and r.json()["result"] == {"group": GRP}
    posts = [(p, b) for m, p, b in seen if m == "POST" and p.startswith("/rest/v1/member_group")]
    assert posts[0] == ("/rest/v1/member_groups", {"name": "Soirées du vendredi", "emoji": "🪩", "color": "pink", "created_by": ME})
    assert posts[1] == ("/rest/v1/member_group_members", {"group_id": GRP, "user_id": ME})
    assert call(client, "group_create", name="   ").json()["code"] == "invalid"


def test_the_terms_and_the_name_filter_of_the_base_keep_their_code():
    client, _ = fake(writes={("POST", "member_groups"): (403, {"message": "terms_required: Accepte les conditions d'utilisation."})})
    r = call(client, "group_create", name="Ski", emoji="🎸", color="sky")
    assert r.status_code == 403 and r.json()["code"] == "terms_required"
    client, _ = fake(writes={("PATCH", "member_groups"): (400, {"message": "content_refused: Ce nom n'est pas accepté."})})
    r = call(client, "group_update", grp=GRP, name="Gros mot", emoji="🎸", color="sky")
    assert r.status_code == 400 and r.json() == {"code": "content_refused", "detail": "Ce nom n'est pas accepté."}


def test_a_write_the_base_lets_nothing_through_is_forbidden():
    # Règle RLS : Membres Vendredi Party ou groupe d'un autre → aucune ligne touchée.
    client, _ = fake(writes={("PATCH", "member_groups"): (200, []), ("DELETE", "member_group_members"): (200, []),
                             ("DELETE", "member_groups"): (200, [])})
    assert call(client, "group_update", grp=GRP, name="Nouveau", emoji="🎸", color="sky").json()["code"] == "forbidden"
    assert call(client, "group_leave", grp=GRP).json()["code"] == "forbidden"
    assert call(client, "group_remove_member", grp=GRP, member=LEA).json()["code"] == "forbidden"
    assert call(client, "group_delete", grp=GRP).json()["code"] == "forbidden"


def test_leaving_and_removing_target_the_right_person():
    client, seen = fake(row(), writes={("DELETE", "member_group_members"): (200, [{"user_id": ME}])})
    assert call(client, "group_leave", grp=GRP).json()["result"] == {"ok": True}
    assert call(client, "group_remove_member", grp=GRP, member=LEA).json()["result"] == {"ok": True}
    deletes = [p for m, p, _ in seen if m == "DELETE"]
    assert deletes == [f"/rest/v1/member_group_members?group_id=eq.{GRP}&user_id=eq.{ME}",
                       f"/rest/v1/member_group_members?group_id=eq.{GRP}&user_id=eq.{LEA}"]


def test_invite_links_come_with_the_public_address_and_only_for_groups():
    client, seen = fake(rpc={"group_invite_link": "tok123", "create_invite_link": "one456", "my_invite_links": [{"token": "one456"}]})
    assert call(client, "group_link", grp=GRP, renew=True).json()["result"] == {
        "token": "tok123", "url": "https://party.example/events/group-invite/tok123"}
    assert call(client, "group_single_link", grp=GRP).json()["result"]["url"].endswith("/one456")
    assert call(client, "group_links", grp=GRP).json()["result"] == [{"token": "one456"}]
    rpcs = [(p.removeprefix("/rest/v1/rpc/"), b) for m, p, b in seen if p.startswith("/rest/v1/rpc/")]
    assert ("group_invite_link", {"grp": GRP, "renew": True}) in rpcs
    assert ("create_invite_link", {"k": "group", "target": GRP}) in rpcs  # jamais un lien d'événement par ici
    for fn in ("create_invite_link", "my_invite_links", "group_invite_link"):
        assert call(client, fn).status_code == 404, fn  # seulement par les fonctions du serveur


def test_the_group_functions_of_the_base_are_relayed():
    client, seen = fake(rpc={"group_invite_suggestions": [{"id": LEA, "display_name": "Léa", "avatar_url": f"{LEA}/me.jpg",
                                                           "together": 2, "invited": False}]})
    out = call(client, "group_invite_suggestions", grp=GRP).json()["result"]
    assert out[0]["photo"].endswith(f"/profile-photos/{LEA}/me.jpg?t=1")
    for fn in ("invite_to_group", "revoke_invite_link", "set_group_phone_share", "set_group_event_rules", "answer_group_invitation"):
        assert call(client, fn).status_code == 200, fn


def test_groups_home_lists_mine_invitations_and_for_admins_the_others():
    others = [{"id": GRP, "name": "La bande", "emoji": "🎸", "color": "mint", "photo_path": None, "system_key": None,
               "member_group_members": [{"user_id": ME}]},
              {"id": NOE, "name": "Autre", "emoji": "⚽", "color": "sky", "photo_path": f"{NOE}/p.jpg", "system_key": None,
               "member_group_members": [{"user_id": LEA}, {"user_id": NOE}]}]
    home = home_with(others)
    assert [g["id"] for g in home["others"]] == [NOE] and home["others"][0]["members"] == 2
    assert home["others"][0]["photo"].endswith(f"/group-photos/{NOE}/p.jpg?t=1")
    assert home["groups"][0]["photo"].endswith(f"/group-photos/{GRP}/c.jpg?t=1")
    assert home["groups"][0]["faces"][0]["photo"].endswith(f"/profile-photos/{LEA}/me.jpg?t=1")
    assert home["invitations"][0]["group"] == "Autre"


def home_with(all_groups):
    seen = []

    def handler(request: httpx.Request):
        path = request.url.path
        body = json.loads(request.content) if request.content else None
        seen.append(path)
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        if path == "/rest/v1/rpc/my_groups_overview":
            return httpx.Response(200, json=[{"id": GRP, "name": "La bande", "emoji": "🎸", "color": "mint", "photo": f"{GRP}/c.jpg",
                                              "faces": [{"id": LEA, "name": "Léa", "avatar_url": f"{LEA}/me.jpg"}]}])
        if path == "/rest/v1/rpc/my_group_invitations":
            return httpx.Response(200, json=[{"id": "inv", "group_id": NOE, "group": "Autre", "emoji": "⚽"}])
        if path == "/rest/v1/member_groups":
            return httpx.Response(200, json=all_groups)
        return httpx.Response(404, json={})

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(chat_rpc.chat_rpc_router(gc.GroupChats(ga.GroupAdmin(acc))))
    return call(TestClient(app), "groups_home").json()["result"]


def test_the_group_photo_is_uploaded_in_its_folder_then_set_and_the_old_one_removed():
    client, seen = fake(row(photo_path=f"{GRP}/old.jpg"), writes={("POST", "storage"): (200, {}),
                                                                 ("PATCH", "member_groups"): (200, [{"id": GRP}]),
                                                                 ("DELETE", "storage"): (200, [])})
    r = client.post("/api/account/chats/group-photo", json={"token": "t", "group_id": GRP, "photo": base64.b64encode(JPEG).decode()})
    assert r.status_code == 200, r.text
    assert "/group-photos/" in r.json()["result"]["photo"]
    upload = next(p for m, p, _ in seen if m == "POST" and p.startswith("/storage/v1/object/group-photos/"))
    assert upload.startswith(f"/storage/v1/object/group-photos/{GRP}/") and upload.endswith(".jpg")
    patch = next(b for m, p, b in seen if m == "PATCH")
    assert patch == {"photo_path": upload.removeprefix("/storage/v1/object/group-photos/")}
    assert ("DELETE", "/storage/v1/object/group-photos", {"prefixes": [f"{GRP}/old.jpg"]}) in seen
    bad = client.post("/api/account/chats/group-photo", json={"token": "t", "group_id": GRP, "photo": base64.b64encode(b"GIF89a").decode()})
    assert bad.status_code == 400 and bad.json()["code"] == "invalid"


def test_a_refused_photo_is_not_left_in_storage():
    client, seen = fake(row(photo_path=None), writes={("POST", "storage"): (200, {}),
                                                     ("PATCH", "member_groups"): (400, {"message": "terms_required: Accepte les CGU."}),
                                                     ("DELETE", "storage"): (200, [])})
    r = client.post("/api/account/chats/group-photo", json={"token": "t", "group_id": GRP, "photo": base64.b64encode(JPEG).decode()})
    assert r.status_code == 403 and r.json()["code"] == "terms_required"
    assert any(m == "DELETE" and p == "/storage/v1/object/group-photos" for m, p, _ in seen)


def test_only_who_manages_the_group_may_upload_its_photo():
    # Storage refuse par sa règle (400 {"statusCode": "403"}) : « forbidden », rien n'est posé sur le groupe.
    client, seen = fake(row(photo_path=None), writes={("POST", "storage"): (400, {"statusCode": "403", "error": "Unauthorized",
                                                                                "message": "new row violates row-level security policy"})})
    r = client.post("/api/account/chats/group-photo", json={"token": "t", "group_id": GRP, "photo": base64.b64encode(JPEG).decode()})
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    assert not any(m == "PATCH" for m, _, _ in seen)


def test_names_are_cleaned_like_the_web():
    assert group_pages.clean_name("  a   b ") == "a b" and len(group_pages.clean_name("x" * 80)) == 60
    assert group_pages.member_order([{"id": "b", "name": "zoé"}, {"id": "a", "name": "Albert"}, {"id": "c", "name": "Bea"}], "b") \
        == [{"id": "b", "name": "zoé"}, {"id": "a", "name": "Albert"}, {"id": "c", "name": "Bea"}]


def test_inviting_a_typed_nickname_looks_for_this_exact_nickname_only():
    seen = []

    def handler(request: httpx.Request):
        seen.append(str(request.url))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": ME})
        if request.url.path == "/rest/v1/profiles":
            return httpx.Response(200, json=[{"id": LEA, "display_name": "Léa_50%"}])
        return httpx.Response(404, json={})

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(chat_rpc.chat_rpc_router(gc.GroupChats(ga.GroupAdmin(acc))))
    client = TestClient(app)
    assert call(client, "group_find_person", q="@Léa_50%").json()["result"] == {"id": LEA, "name": "Léa_50%"}
    # Ni « % » ni « _ » ne servent de joker : le surnom exact, sans casse.
    assert "display_name=ilike.L%C3%A9a%5C_50%5C%25" in seen[-1] and "status=eq.active" in seen[-1]
    assert call(client, "group_find_person", q="  ").json()["result"] is None


def test_a_group_photo_can_be_reported_from_the_iphone():
    from app import moderation_api
    assert "group_photo" in moderation_api.KINDS
