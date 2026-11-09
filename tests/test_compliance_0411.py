"""Corrections « bêta → main » du 04.11 (audit de conformité) côté serveur :
- A5 : assistant IA ouvert à tous, mais accord exprès avant tout envoi (le même accord que l'IA des avis), plafond
  mensuel global en plus du plafond par personne ;
- A4 : la suppression du compte efface tous les fichiers locaux liés au compte ;
- A6 : plus de « Cul sec » ; B3 : filtre « answer » ; Discussions derrière un drapeau serveur."""
import json

import pytest
from fastapi.testclient import TestClient

from app import account_data, ai_feedback, assistant as ai, features, main, moderation, purity, quiz
from app.accounts import AccountError
from app.feedback import FeedbackBox
from app.guest_gate import GuestGate
from app.pet_reactions import ActivityLog
from tests.test_assistant import JPEG, FakeAccounts, FakeClient

UID = "11111111-2222-3333-4444-555555555555"
GID = "acct-" + UID


def assistant_with_consents(tmp_path, budget=3.0, global_budget=30.0):
    consents = ai_feedback.ConsentBox(tmp_path / "consent.json")
    client = FakeClient()
    a = ai.Assistant(FakeAccounts(), ai.UsageLog(tmp_path / "ai.json"), lambda: client, budget, ("CHF",),
                     consents=consents, global_budget_usd=global_budget)
    return a, client, consents


# ── A5 : accord et plafonds ──
def test_no_call_to_anthropic_before_the_consent(tmp_path):
    a, client, consents = assistant_with_consents(tmp_path)
    assert a.status("ok")["consent"] == ""
    with pytest.raises(ai.ConsentRequired, match="accord"):
        a.read_receipt("ok", JPEG)  # scan d'un ticket du pot commun : même exigence
    assert not client.calls
    a.set_consent("ok", True)
    assert consents.state("acct:u1") == ai_feedback.ACCEPTED  # un seul accord : celui de l'IA des avis
    a.read_receipt("ok", JPEG)
    assert len(client.calls) == 1
    a.set_consent("ok", False)
    with pytest.raises(ai.ConsentRequired):
        a.read_receipt("ok", JPEG)


def test_the_avis_consent_opens_the_assistant_too(tmp_path):
    a, client, consents = assistant_with_consents(tmp_path)
    consents.set("acct:u1", True)  # accord donné sur la feuille de « Ton avis » (web ou iPhone)
    assert a.status("ok")["consent"] == ai_feedback.ACCEPTED
    a.read_receipt("ok", JPEG)
    assert client.calls


def test_global_monthly_budget_stops_everyone(tmp_path):
    a, client, consents = assistant_with_consents(tmp_path, budget=100, global_budget=0.01)
    consents.set("acct:u1", True)
    a.usage.add({"at": __import__("time").time(), "uid": "quelqu-un-d-autre", "feature": "event", "cost_usd": 0.02})
    assert a.status("ok")["global_full"] is True
    with pytest.raises(AccountError, match="toute l'app"):
        a.read_receipt("ok", JPEG)
    writer = ai_feedback.FeedbackWriter(a, consents, {})
    with pytest.raises(ai_feedback.Unavailable):
        writer.rewrite("acct:u1", "Léa", ["Le quiz plante à la 3e question"], {})
    assert not client.calls


def test_consent_routes_answer_403_then_accept(monkeypatch, tmp_path):
    a, client, consents = assistant_with_consents(tmp_path)
    monkeypatch.setattr(main, "assistant", a)
    c = TestClient(main.app)
    refused = c.post("/api/account/ai/receipt", json={"token": "ok", "photo": "/9j/4AAQSkZJRgABAQAAAQABAAD/2Q=="})
    assert refused.status_code == 403 and "accord" in refused.json()["detail"]
    assert c.post("/api/account/ai/consent", json={"token": "ok", "accept": True}).json()["consent"] == "accepted"
    assert c.post("/api/account/ai/status", json={"token": "ok"}).json()["consent"] == "accepted"


def test_ai_right_is_given_to_every_role_once():
    sql = open("supabase/migrations/20261105110000_ai_pour_tous.sql", encoding="utf-8").read()
    assert "select key, 'ai.use' from public.roles" in sql and "one_time_changes" in sql
    for name in ("2026-11-05-ia-pour-tous-apply.sql", "2026-11-05-ia-pour-tous-rollback.sql",
                 "2026-11-05-billets-paiement-apply.sql", "2026-11-05-billets-paiement-rollback.sql"):
        text = open(f"supabase/prod/{name}", encoding="utf-8").read()
        assert text.count("begin;") == 1 and "commit;" in text and "schema_migrations" in text


# ── A4 : suppression du compte ──
def test_account_deletion_forgets_every_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr(purity, "STATS_PATH", tmp_path / "purity.json")
    monkeypatch.setattr(quiz, "STATS_PATH", tmp_path / "quiz.json")
    (tmp_path / "purity.json").write_text(json.dumps({GID: {"v": 2, "name": "Léa", "plays": 1, "best": 40, "last": 40},
                                                       "acct-autre": {"v": 2, "name": "Bob", "plays": 1, "best": 3, "last": 3}}))
    (tmp_path / "quiz.json").write_text(json.dumps({"players": {GID: {"name": "Léa", "pts": 9}, "acct-autre": {"name": "Bob", "pts": 1}}}))
    usage = ai.UsageLog(tmp_path / "ai.json")
    for uid in (UID, "acct:" + UID, "autre"):
        usage.add({"at": 1, "uid": uid, "cost_usd": 0.1, "said": "dicté"})
    consents = ai_feedback.ConsentBox(tmp_path / "consent.json")
    consents.set("acct:" + UID, True)
    gate = GuestGate(tmp_path / "gate.json")
    gate.record(GID, "1234")
    box = FeedbackBox(tmp_path / "feedback.json")
    box.add(GID, "Léa", "idea", "Une idée", {"tab": "games"})
    box.add("acct-autre", "Bob", "bug", "Un bug", {})
    activity = ActivityLog(tmp_path / "pet_party.json")
    activity.note(GID, "partie-1")
    activity.mark_pet(GID, "Zizou", True)
    stores = account_data.LocalStores(purity_forget=purity.forget, quiz_forget=quiz.forget_player, usage_forget=usage.forget,
                                      consent_forget=consents.forget, gate_forget=gate.forget, feedback_forget=box.forget,
                                      activity_forget=account_data.activity_forgetter(activity))

    done = account_data.forget_local(stores, UID, (ai.assistant_consent_key(UID),))

    assert "error" not in done.values()
    assert purity.profile(GID)["plays"] == 0 and purity.profile("acct-autre")["plays"] == 1
    assert GID not in json.loads((tmp_path / "quiz.json").read_text())["players"]
    assert [i["uid"] for i in ai.UsageLog(tmp_path / "ai.json").items] == ["autre"]
    assert consents.state("acct:" + UID) == ""
    assert gate.played(GID) == 0
    kept = [i for i in FeedbackBox(tmp_path / "feedback.json").items if i["text"] == "Une idée"][0]
    assert kept["guest_id"] == "compte-supprime" and kept["name"] == "Compte supprimé"
    assert not ActivityLog(tmp_path / "pet_party.json").known(GID)


def test_a_broken_file_does_not_stop_the_others(tmp_path):
    calls = []

    def boom(_):
        raise OSError("disque plein")
    stores = account_data.LocalStores(purity_forget=boom, quiz_forget=lambda g: calls.append("quiz"), usage_forget=lambda s: 0,
                                      consent_forget=lambda k: None, gate_forget=lambda g: None, feedback_forget=lambda g: 0,
                                      activity_forget=lambda g: calls.append("pet"))
    done = account_data.forget_local(stores, UID, ())
    assert done["purity"] == "error" and calls == ["quiz", "pet"]


def test_delete_route_purges_local_data(monkeypatch):
    seen = []

    class Auth:
        def delete_account(self, token, confirm):
            seen.append("base")

    monkeypatch.setattr(main, "account_auth", Auth())
    monkeypatch.setattr(main.accounts, "_uid", lambda token: UID)
    monkeypatch.setattr(main, "forget_local", lambda stores, uid, keys: seen.append((uid, keys)))
    assert TestClient(main.app).post("/api/account/delete", json={"token": "t", "confirm": "SUPPRIMER"}).json() == {"ok": True}
    assert seen == ["base", (UID, ("acct:" + UID,))]


def test_web_account_deletion_goes_through_the_server():
    screen = open("web/events/src/app/settings/account.tsx", encoding="utf-8").read()
    assert "/api/account/delete" in screen and "rpc('delete_my_account')" not in screen


# ── A6, B3, Discussions ──
def test_no_bottoms_up_in_drinking_games():
    for path in ("app/beerpong.py", "app/static/games.js", "app/games.py"):
        assert "cul sec" not in open(path, encoding="utf-8").read().lower()
    assert "Un shot (ou un verre d'eau)" in open("app/beerpong.py", encoding="utf-8").read()


def test_answer_kind_masks_insults_and_refuses_links_and_numbers():
    assert moderation.check("Ma réponse sincère", "answer").ok
    assert not moderation.check("va sur www.exemple.ch", "answer").ok
    assert not moderation.check("079 123 45 67", "answer").ok
    assert moderation.check("va sur www.exemple.ch", "message").ok  # un message garde ses liens


@pytest.mark.parametrize("url,flag,expected", [
    ("https://party.bobycharbon.ch", None, False), ("https://partytest.bobycharbon.ch", None, True),
    ("https://party.bobycharbon.ch", "1", True), ("https://partytest.bobycharbon.ch", "0", False)])
def test_discussions_flag(monkeypatch, url, flag, expected):
    monkeypatch.setenv("PARTY_PUBLIC_URL", url)
    if flag is None:
        monkeypatch.delenv("DISCUSSIONS_ENABLED", raising=False)
    else:
        monkeypatch.setenv("DISCUSSIONS_ENABLED", flag)
    assert features.discussions_enabled() is expected
    assert TestClient(main.app).get("/api/features").json()["discussions"] is expected


# ── A3 : confidentialité, CGU, Signaler ──
def test_privacy_policy_names_the_controller_every_data_and_processor():
    page = open("web/events/src/app/privacy.tsx", encoding="utf-8").read()
    contact = open("web/events/src/lib/contact.ts", encoding="utf-8").read()
    assert "Ludovic Trombert" in contact and "support@vendrediparty.ch" in contact
    for word in ("téléphone", "photo", "Contacts", "vocaux", "micro", "Purify", "Anthropic", "Spotify", "Apple Wallet",
                 "IBAN", "Supabase", "Twilio", "Infomaniak", "90 jours", "PFPDT", "9 novembre 2026", "ticket", "Invitation par lien"):
        assert word in page, word
    for path in ("web/events/src/app/terms.tsx", "web/events/src/components/ReportSheet.tsx"):
        assert "SUPPORT_EMAIL" in open(path, encoding="utf-8").read()


def test_terms_never_mention_zicou_in_production():
    assert "Zicou" not in open("web/events/src/lib/terms.ts", encoding="utf-8").read()
