"""Discussions v2 (18.11) : relais de l'app iPhone POST /api/account/chats/rpc — liste blanche, erreurs de la base
(mêmes codes que les pronos, CGU → 403 terms_required), photos signées, coupé avec le drapeau des Discussions.
La base est testée pour de vrai dans tests/supabase_live/ (test_discussions_v2_live.py, test_discussions_moderation_live.py)."""
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, chat_rpc, group_admin as ga, group_chats as gc, main

LEA = "bbbbbbbb-0000-4000-8000-000000000002"
GRP = "11111111-1111-1111-1111-111111111111"
MSG = "aaaaaaaa-0000-4000-8000-000000000001"


def relay(answer=None, status: int = 200):
    """Faux Supabase : chaque fonction rend `answer` (ou un refus) ; les photos se signent par compartiment."""
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        path = request.url.path
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        if path.startswith("/rest/v1/rpc/"):
            return httpx.Response(status, json=answer)
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(chat_rpc.chat_rpc_router(gc.GroupChats(ga.GroupAdmin(acc))))
    return TestClient(app), seen


def call(client, fn, **args):
    return client.post("/api/account/chats/rpc", json={"token": "t", "fn": fn, "args": args})


def rpcs(seen):
    return [(p.removeprefix("/rest/v1/rpc/"), b) for m, p, b in seen if p.startswith("/rest/v1/rpc/")]


def test_only_the_functions_of_the_contract_are_relayed():
    client, seen = relay(answer=[])
    for fn in ("prono_list", "delete_my_account", "moderation_queue", "set_block", "agenda_links", "chat_files_gc"):
        assert call(client, fn).status_code == 404, fn
    assert seen == []
    for fn in ("chat_list", "chat_badge", "open_direct_chat", "accept_message_request", "decline_message_request", "chat_link",
               "chat_prefs_get", "chat_prefs_set", "set_chat_state", "chat_people_suggestions", "chat_people_search",
               "member_mini", "create_chat_group", "chat_group_with", "direct_seen", "chat_event_cards", "chat_search",
               "edit_direct_message", "edit_group_message", "mark_event_chat_read", "member_note_get", "member_note_set", "contacts_match"):
        assert call(client, fn).status_code == 200, fn
    assert [n for n, _ in rpcs(seen)][-1] == "contacts_match"


def test_reporting_from_the_chats_is_limited_to_messages_profiles_and_photos():
    client, seen = relay(answer=MSG)
    assert call(client, "report_content", p_kind="prono", p_target=MSG, p_reason="spam").status_code == 404
    assert call(client, "report_content", p_kind="booking_request", p_target=MSG, p_reason="spam").status_code == 404
    r = call(client, "report_content", p_kind="direct_message", p_target=MSG, p_reason="harassment", context=True)
    assert r.status_code == 200 and r.json()["result"] == MSG
    # Contrat « context » → paramètre de la base p_context (case « Joindre les 10 messages précédents »).
    assert rpcs(seen) == [("report_content", {"p_kind": "direct_message", "p_target": MSG, "p_reason": "harassment",
                                              "p_context": True})]


@pytest.mark.parametrize("message, status, code", [
    ("terms_required: Accepte les conditions d'utilisation.", 403, "terms_required"),
    ("limit: tu as envoyé beaucoup de demandes aujourd'hui", 429, "limit"),
    ("request_pending: attends sa réponse", 409, "request_pending"),
    ("pin_limit: 5 conversations épinglées au plus", 409, "pin_limit"),
    ("edit_window: plus de 15 minutes", 409, "edit_window"),
    ("link_required: écris-lui d'abord", 403, "link_required"),
    ("content_refused: Message non envoyé", 400, "content_refused"),
])
def test_refusals_keep_their_code_and_words(message, status, code):
    client, _ = relay(answer={"message": message}, status=400)
    r = call(client, "open_direct_chat", target=LEA)
    assert r.status_code == status and r.json()["code"] == code and r.json()["detail"] == message.split(": ", 1)[1]


def test_expired_session_and_unknown_failures_are_not_refusals():
    client, _ = relay(answer={"message": "JWT expired"}, status=401)
    assert call(client, "chat_list").status_code == 401
    client, _ = relay(answer={"message": "boom"}, status=500)
    r = call(client, "chat_list")
    assert r.status_code == 503 and "Réessaie" in r.json()["detail"]


def test_photos_are_signed_from_the_right_bucket_and_the_list_carries_realtime():
    rows = [
        {"kind": "direct", "id": "c1", "title": "Léa", "photo": f"{LEA}/a.jpg", "user_id": LEA, "emoji": None, "color": None},
        {"kind": "group", "id": GRP, "title": "Ski", "photo": f"{GRP}/cover.jpg", "emoji": "⛷️", "color": "mint"},
        {"kind": "group", "id": "vp", "title": "Membres Vendredi Party", "photo": None, "is_vp": True},
        {"kind": "event", "id": "e1", "title": "Fondue", "photo": "https://exemple.ch/cover.jpg"},
    ]
    client, _ = relay(answer=rows)
    out = call(client, "chat_list").json()
    got = {r["id"]: r["photo"] for r in out["result"]}
    assert got["c1"].endswith(f"/storage/v1/object/sign/profile-photos/{LEA}/a.jpg?t=1")
    assert got[GRP].endswith(f"/storage/v1/object/sign/group-photos/{GRP}/cover.jpg?t=1")
    assert got["vp"] is None and got["e1"] == "https://exemple.ch/cover.jpg"
    assert out["realtime"]["url"].endswith("/realtime/v1/websocket") and out["realtime"]["key"]


def test_a_mini_profile_signs_the_person_and_the_groups_in_common():
    mini = {"id": LEA, "name": "Léa", "photo": f"{LEA}/me.png", "link": "direct",
            "groups": [{"id": GRP, "name": "Ski", "emoji": "⛷️", "color": "mint", "photo": f"{GRP}/g.jpg"}],
            "met": [{"id": "e1", "title": "Fondue", "start": "2026-11-01T19:00:00Z"}]}
    client, _ = relay(answer=mini)
    out = call(client, "member_mini", target=LEA).json()["result"]
    assert "/profile-photos/" in out["photo"] and "/group-photos/" in out["groups"][0]["photo"]
    assert "realtime" not in call(client, "member_mini", target=LEA).json()


def test_the_relay_is_cut_with_the_discussions_flag(monkeypatch):
    monkeypatch.setattr(main, "discussions_enabled", lambda: False)
    r = TestClient(main.app).post("/api/account/chats/rpc", json={"token": "t", "fn": "chat_list"})
    assert r.status_code == 404 and r.json()["detail"] == main.DISCUSSIONS_OFF


def test_the_main_app_serves_the_relay(monkeypatch):
    monkeypatch.setattr(chat_rpc.Db, "call", lambda self, fn, args, token="": (200, 3))
    r = TestClient(main.app).post("/api/account/chats/rpc", json={"token": "t", "fn": "chat_badge"})
    assert r.status_code == 200 and r.json()["result"] == 3
