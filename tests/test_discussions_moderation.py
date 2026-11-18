"""Discussions v2 — modération (revue de conformité du 18.11 : 🔴 2 et 6, 🟠 7, 8 et 9) côté serveur et dans la
migration : case « 10 messages précédents », preuve photo / vocal montrée aux modérateurs, envoi avec carte de soirée et
citation, tâche des fichiers orphelins. La base est testée pour de vrai : tests/supabase_live/test_discussions_moderation_live.py."""
import contextlib
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app import accounts as accounts_mod, chat_rpc, main
from tests.test_group_chats_native import GRP, fake
from tests.test_moderation import REPORT, relay

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261118121000_discussions_moderation.sql").read_text(encoding="utf-8")
EVENT = "eeeeeeee-0000-4000-8000-000000000001"


def test_the_ten_previous_messages_are_asked_only_when_the_box_is_ticked():
    client, seen = relay()
    body = {"token": "t", "kind": "direct_message", "target": REPORT, "reason": "harassment"}
    assert client.post("/api/account/moderation/report", json=body).status_code == 200
    assert "p_context" not in seen[-1][2]  # case décochée : rien de plus (et une base d'avant la migration répond encore)
    assert client.post("/api/account/moderation/report", json={**body, "context": True}).status_code == 200
    assert seen[-1][2]["p_context"] is True


def test_moderators_see_the_kept_photo_the_voice_message_and_the_context():
    queue = [{"id": REPORT, "kind": "direct_message", "target_id": REPORT, "reason": "shocking", "comment": None,
              "snapshot": {"text": "", "photo_path": None, "place": "Message direct",
                           "evidence": {"photo": f"{REPORT}/photo-1-abc.jpg", "audio": f"{REPORT}/audio-2-def.m4a"},
                           "context": [{"author": "Léa", "at": "2026-11-18T09:00:00Z", "text": "salut"}]},
              "status": "open", "created_at": "2026-11-18T10:00:00Z", "reporter": {"id": "x", "name": "Tom"},
              "target_user": None, "same_target": 1, "user_reports": 1, "sanctions": []}]
    client, seen = relay(queue=queue)
    item = client.post("/api/account/moderation/queue", json={"token": "t"}).json()["reports"][0]
    assert item["photo"].endswith(f"/moderation-evidence/{REPORT}/photo-1-abc.jpg?t=1")
    assert item["audio"].endswith(f"/moderation-evidence/{REPORT}/audio-2-def.m4a?t=1")
    assert item["context"] == [{"author": "Léa", "at": "2026-11-18T09:00:00Z", "text": "salut"}]
    signed = [b["paths"] for m, p, b in seen if p == "/storage/v1/object/sign/moderation-evidence"]
    assert signed == [[f"{REPORT}/audio-2-def.m4a", f"{REPORT}/photo-1-abc.jpg"]]  # signés avec la session du modérateur


def test_a_message_can_carry_an_event_card_and_a_private_reply_quote():
    chats, seen = fake()
    quote = {"from": "group", "title": "Ski", "author": "Léa", "excerpt": "On part à 7 h ?"}
    with contextlib.suppress(accounts_mod.AccountError):  # le faux Supabase ne connaît que les groupes : on lit l'envoi
        chats.send("jeton", GRP, "", None, None, direct=True, event_id=EVENT, quote=quote)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/direct_messages")
    assert row["event_id"] == EVENT and row["quote"] == quote and row["body"] == ""  # la carte seule suffit
    chats, seen = fake()
    chats.send("jeton", GRP, "Regarde", None, None, mentions=[], event_id=EVENT, quote=quote)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/group_messages")
    assert row["event_id"] == EVENT and "quote" not in row  # citation « en privé » : messages directs seulement
    chats, seen = fake()
    chats.send("jeton", GRP, "Salut", None, None, mentions=[])
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/group_messages")
    assert "event_id" not in row and "quote" not in row  # rien de neuf envoyé à une base d'avant


def test_the_send_route_validates_the_card_and_the_quote(monkeypatch):
    chats, seen = fake()
    monkeypatch.setattr(main, "group_chats", chats)
    client = TestClient(main.app)
    base = {"token": "jeton", "group_id": GRP, "direct": True, "body": "Vu"}
    assert client.post("/api/account/chats/send", json={**base, "event_id": "../x"}).status_code == 422
    assert client.post("/api/account/chats/send", json={**base, "quote": {"from": "web", "excerpt": "x"}}).status_code == 422
    assert client.post("/api/account/chats/send", json={**base, "quote": {"from": "event", "excerpt": "x" * 141}}).status_code == 422
    ok = client.post("/api/account/chats/send", json={**base, "event_id": EVENT,
                                                     "quote": {"from": "event", "title": "Fondue", "author": "Tom", "excerpt": "On amène quoi ?"}})
    assert ok.status_code != 422  # accepté par le serveur (le faux Supabase ne connaît que les groupes)
    row = next(b for m, p, _, b in seen if m == "POST" and p == "/rest/v1/direct_messages")
    assert row["quote"] == {"from": "event", "title": "Fondue", "author": "Tom", "excerpt": "On amène quoi ?"}
    # Carte de soirée seule (W2 / I2 : {body: '', event_id}) : envoyée, pas « Écris un message ».
    card = client.post("/api/account/chats/send", json={"token": "jeton", "group_id": GRP, "body": "", "event_id": EVENT})
    assert card.json() == {"ok": True}
    assert client.post("/api/account/chats/send", json={"token": "jeton", "group_id": GRP, "body": ""}).status_code == 400


def test_the_message_requests_switch_is_saved(monkeypatch):
    from tests.test_notify_prefs import FakeAccounts
    monkeypatch.setattr(main, "accounts", FakeAccounts())
    r = TestClient(main.app).post("/api/account/notifications/update", json={"token": "ok", "patch": {"message_requests": False}})
    assert r.status_code == 200 and r.json()["prefs"]["message_requests"] is False


def test_messages_tell_the_app_about_their_card_and_quote():
    chats, _ = fake()
    m = chats._message({"id": "m", "user_id": "u", "created_at": "x", "body": "a", "event_id": EVENT,
                        "quote": {"from": "group"}}, {}, "u", lambda u: "?", lambda u: None, {}, [])
    assert m["event_id"] == EVENT and m["quote"] == {"from": "group"}
    gone = chats._message({"id": "m", "user_id": "u", "created_at": "x", "deleted_at": "y", "event_id": EVENT},
                          {}, "u", lambda u: "?", lambda u: None, {}, [])
    assert gone["event_id"] is None and gone["quote"] is None


def test_the_orphan_files_task_asks_the_database_and_never_runs_in_tests():
    calls = []

    class Db:
        def call(self, fn, args, token=accounts_mod.SUPABASE_ANON_KEY):
            calls.append((fn, args, token))
            return 200, {"chat-photos": 3, "group-photos": 0, "moderation-evidence": 1}

    assert chat_rpc.files_gc(Db()) == {"chat-photos": 3, "group-photos": 0, "moderation-evidence": 1}
    assert calls == [("chat_files_gc", {}, accounts_mod.SUPABASE_ANON_KEY)]  # sans compte : la base décide de tout

    class Down:
        def call(self, *a, **k):
            return 503, None
    assert chat_rpc.files_gc(Down()) is None
    assert "pytest" in sys.modules and not any(t.name == "chat-files-gc" for t in __import__("threading").enumerate())


def test_the_loop_survives_a_failure(monkeypatch):
    sleeps = []

    class Boom:
        def call(self, *a, **k):
            raise RuntimeError("panne")

    def sleep(s):
        sleeps.append(s)
        if len(sleeps) > 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(chat_rpc.time, "sleep", sleep)
    try:
        chat_rpc.files_gc_loop(Boom(), every=6 * 3600, first=60)
    except KeyboardInterrupt:
        pass
    assert sleeps == [60, 6 * 3600, 6 * 3600]


def test_the_migration_keeps_evidence_for_moderators_only_and_files_safe():
    # Preuves : lecture par le droit des modérateurs, aucune écriture par l'API publique.
    policies = re.findall(r'create policy "[^"]+" on storage\.objects for (\w+) to \w+\s+using \(bucket_id = \'moderation-evidence\'([^;]+);', MIGRATION)
    assert [p[0] for p in policies] == ["select"] and "has_perm('moderation.reports')" in policies[0][1]
    # Fichiers orphelins : jamais un fichier de moins d'une heure, jamais un fichier encore désigné.
    assert "o.created_at < now() - interval '1 hour'" in MIGRATION
    for ref in ("public.group_messages", "public.direct_messages", "public.messages", "public.member_groups"):
        assert ref in MIGRATION.split("create or replace function private.chat_files_orphans")[1].split("$$;")[0]
    assert "interval '10 minutes'" in MIGRATION  # au plus une fois toutes les 10 minutes
    # report_content : ancienne signature retirée (sinon deux candidats pour les appels à 4 paramètres).
    assert "drop function if exists public.report_content(text, text, text, text);" in MIGRATION
    assert "p_context boolean default false" in MIGRATION


def test_invite_by_number_never_tells_if_the_number_has_an_account():
    body = MIGRATION.split("create or replace function public.invite_to_group")[1].split("$$;")[0]
    phone_branch = body.split("if by_phone then")[1].split("end if;\n  if exists")[0]
    assert phone_branch.count("return jsonb_build_object('invited', 'phone');") == 2
    assert "raise" not in phone_branch  # ni « déjà dans le groupe », ni « bloqué » par numéro
    assert ">= 30" in body and "'1 day'" in body
    assert "link_required:" in body and "invite_link(auth.uid(), target)" in body


def test_hiding_notifies_the_author_through_the_moderation_switch():
    assert "perform private.notify_content_hidden(r);" in MIGRATION
    assert "when 'content_hidden' then coalesce(prefs.moderation_notices, true)" in MIGRATION
    assert "''moderation_notice'', ''content_hidden'', ''report_new''" in MIGRATION
