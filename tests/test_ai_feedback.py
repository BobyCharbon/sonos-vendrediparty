"""« Ton avis » avec l'IA : accord avant tout appel, schéma JSON, limites (jour, longueur, budget), repli sans IA,
invité sans compte, avis envoyé avec sa version structurée (Claude simulé, aucun appel payant)."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import ai_feedback as aif, assistant as ai, feedback as fb, main
from app.accounts import AccountError
from app.feedback import FeedbackBox
from tests.test_features import admin  # noqa: F401 (fixture)

GAMES = {"quiz": "Quiz", "masque": "Le Masque"}
GUEST = "feedback-guest-0042"
PLUS = "t" * 30 + "plus"
BUG = {"status": "ready", "question": "", "kind": "bug", "area": "games", "game": "quiz",
       "title": "Le Quiz se fige après la 3e question", "description": "Quand je joue au Quiz, l'écran se fige.",
       "steps": ["Lancer un Quiz", "Répondre à 3 questions"], "expected": "La 4e question s'affiche",
       "actual": "L'écran reste figé", "need": "ne doit pas rester", "proposal": "ni ça"}


class FakeClient:
    def __init__(self, answer=BUG, stop="end_turn", fail=False):
        self.calls, self.answer, self.stop, self.fail = [], answer, stop, fail
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("réseau coupé")
        return SimpleNamespace(stop_reason=self.stop, usage=SimpleNamespace(input_tokens=800, output_tokens=300),
                               content=[SimpleNamespace(type="text", text=json.dumps(self.answer))])


def writer(tmp_path, client=None, budget=3.0, configured=True):
    client = client or FakeClient()
    a = ai.Assistant(None, ai.UsageLog(tmp_path / "ai.json"), (lambda: client) if configured else None, budget, ("CHF",))
    return aif.FeedbackWriter(a, aif.ConsentBox(tmp_path / "consent.json"), GAMES), client


def test_without_consent_nothing_is_sent_to_the_ai(tmp_path):
    w, client = writer(tmp_path)
    with pytest.raises(PermissionError):
        w.rewrite("guest:x", "", ["Le quiz plante tout le temps"], {})
    w.consents.set("guest:x", False)  # « Écrire sans l'IA »
    with pytest.raises(PermissionError):
        w.rewrite("guest:x", "", ["Le quiz plante tout le temps"], {})
    assert client.calls == [] and w.status("guest:x")["consent"] == "declined"


def test_consent_is_kept_per_person_and_can_be_revoked(tmp_path):
    w, _ = writer(tmp_path)
    w.consents.set("acct:u1", True)
    again = aif.ConsentBox(tmp_path / "consent.json")
    assert again.state("acct:u1") == "accepted" and again.state("acct:u2") == ""
    again.set("acct:u1", False)
    assert aif.ConsentBox(tmp_path / "consent.json").state("acct:u1") == "declined"
    again.forget("acct:u1")  # compte supprimé
    assert aif.ConsentBox(tmp_path / "consent.json").state("acct:u1") == "" and "acct:u1" not in again.items


def test_a_new_consent_text_asks_again(tmp_path, monkeypatch):
    w, _ = writer(tmp_path)
    w.consents.set("acct:u1", True)
    monkeypatch.setattr(aif, "CONSENT_VERSION", aif.CONSENT_VERSION + 1)
    assert w.consents.state("acct:u1") == ""


def test_rewrite_returns_a_clean_structured_review_and_is_logged(tmp_path):
    w, client = writer(tmp_path)
    w.consents.set("guest:x", True)
    r = w.rewrite("guest:x", "Léa", ["euh le quiz il bloque après la troisième question"],
                  {"tab": "games", "game": "quiz", "platform": "iphone", "os": "iOS 26.1", "app": "2.4 (51)"})
    d = r["draft"]
    assert r["status"] == "ready" and r["question"] == ""
    assert (d["kind"], d["area"], d["game"], d["title"]) == ("bug", "games", "quiz", "Le Quiz se fige après la 3e question")
    assert d["steps"] == ["Lancer un Quiz", "Répondre à 3 questions"] and d["need"] == d["proposal"] == ""  # champs d'idée vidés
    assert d["device"] == "iPhone · iOS 26.1 · app 2.4 (51)"  # rempli par l'app, jamais par l'IA
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"]["format"]["schema"]["additionalProperties"] is False
    prompt = call["system"] + json.dumps(call["messages"], ensure_ascii=False)
    assert "Léa" not in prompt and "iOS 26.1" not in prompt and "guest:x" not in prompt  # aucune donnée personnelle
    assert "<avis>" in call["messages"][0]["content"] and "Jeu ouvert : Quiz" in call["system"]
    assert "Ne promets jamais" in call["system"]
    entry = w.ai.usage.items[0]
    assert entry["feature"] == "feedback" and entry["uid"] == "guest:x" and "said" not in entry
    assert r["remaining"] == aif.DAILY_LIMIT - 1


def test_schema_lists_only_known_kinds_areas_and_games():
    s = aif.schema(GAMES)
    assert s["properties"]["kind"]["enum"] == ["idea", "bug", "other"]
    assert set(s["properties"]["area"]["enum"]) == set(fb.AREAS) and {"pet", "calendar"} <= set(fb.AREAS)
    assert s["properties"]["game"]["enum"] == ["quiz", "masque", "brain", ""]
    assert set(s["required"]) == set(s["properties"])


def test_clean_draft_rejects_unknown_values_and_bounds_lengths():
    d = aif.clean_draft({"kind": "hack", "area": "root", "game": "rm -rf", "title": "x" * 300,
                         "description": "Une idée", "steps": ["a"], "need": "Besoin"}, GAMES)
    assert (d["kind"], d["area"], d["game"], len(d["title"])) == ("other", "general", "", 80)
    assert d["steps"] == [] and d["need"] == ""
    with pytest.raises(ValueError):
        aif.clean_draft({"kind": "bug", "title": "", "description": ""}, GAMES)
    with pytest.raises(ValueError):
        aif.clean_draft("pas un objet", GAMES)
    idea = aif.clean_draft({"kind": "idea", "area": "pet", "title": "Plus de chapeaux", "description": "Des chapeaux.",
                            "need": "Varier Zicou", "proposal": "Un chapeau de cowboy", "expected": "x"}, GAMES)
    assert (idea["area"], idea["need"], idea["proposal"], idea["expected"]) == ("pet", "Varier Zicou", "Un chapeau de cowboy", "")


def test_one_short_question_when_something_essential_is_missing(tmp_path):
    w, client = writer(tmp_path, FakeClient({**BUG, "status": "needs_info", "game": "", "question": "Dans quel jeu ?"}))
    w.consents.set("guest:x", True)
    r = w.rewrite("guest:x", "", ["un jeu plante"], {})
    assert r["status"] == "needs_info" and r["question"] == "Dans quel jeu ?"
    w.rewrite("guest:x", "", ["un jeu plante", "le quiz"], {})
    assert "<precision>le quiz</precision>" in client.calls[1]["messages"][0]["content"]


def test_daily_limit_and_text_limits(tmp_path):
    w, client = writer(tmp_path)
    w.consents.set("guest:x", True)
    for _ in range(aif.DAILY_LIMIT):
        w.rewrite("guest:x", "", ["Le quiz plante"], {})
    with pytest.raises(aif.Unavailable, match="aujourd'hui"):
        w.rewrite("guest:x", "", ["Le quiz plante"], {})
    assert len(client.calls) == aif.DAILY_LIMIT and w.status("guest:x")["remaining"] == 0
    w.consents.set("guest:y", True)
    with pytest.raises(ValueError):
        w.rewrite("guest:y", "", ["x" * (aif.MAX_TURN + 1)], {})
    with pytest.raises(ValueError):
        w.rewrite("guest:y", "", ["a"] * (aif.MAX_TURNS + 1), {})
    with pytest.raises(ValueError):
        w.rewrite("guest:y", "", ["   "], {})


def test_the_host_is_never_stopped_by_the_daily_limit_or_the_personal_budget(tmp_path):
    """Retour de l'admin du 11.11 : « moi en tout cas je ne veux pas être bloqué »."""
    w, client = writer(tmp_path, budget=0.0)
    w.consents.set("acct:hote", True)
    for _ in range(aif.DAILY_LIMIT + 3):
        r = w.rewrite("acct:hote", "", ["Le quiz plante"], {}, host=True)
    assert r["remaining"] == aif.DAILY_LIMIT and w.status("acct:hote", host=True)["remaining"] == aif.DAILY_LIMIT
    assert len(client.calls) == aif.DAILY_LIMIT + 3
    with pytest.raises(aif.Unavailable):  # le même compte, hors session d'hôte, reste limité
        w.rewrite("acct:hote", "", ["Le quiz plante"], {})


def test_budget_reached_or_ai_off_or_down_means_write_without_it(tmp_path):
    w, client = writer(tmp_path, budget=0.0)
    w.consents.set("guest:x", True)
    with pytest.raises(aif.Unavailable, match="limite"):
        w.rewrite("guest:x", "", ["Le quiz plante"], {})
    assert client.calls == []
    off, _ = writer(tmp_path / "..", configured=False)
    off.consents.set("guest:x", True)
    with pytest.raises(aif.Unavailable):
        off.rewrite("guest:x", "", ["Le quiz plante"], {})
    assert off.status("guest:x")["configured"] is False
    down, _ = writer(tmp_path, FakeClient(fail=True))
    with pytest.raises(aif.Unavailable):
        down.rewrite("guest:x", "", ["Le quiz plante"], {})
    bad, _ = writer(tmp_path, FakeClient({"status": "ready"}))
    with pytest.raises(aif.Unavailable, match="reformuler"):
        bad.rewrite("guest:x", "", ["Le quiz plante"], {})


# ── Par l'API ─────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path, monkeypatch):
    client = FakeClient()
    a = ai.Assistant(main.accounts, ai.UsageLog(tmp_path / "ai.json"), lambda: client, 3.0, ("CHF",))
    monkeypatch.setattr(main, "feedback_writer", aif.FeedbackWriter(a, aif.ConsentBox(tmp_path / "c.json"), main.games.GAMES))
    monkeypatch.setattr(main, "feedback", FeedbackBox(tmp_path / "feedback.json"))

    def perms(token):
        if token == PLUS:
            return {"feedback.write"}
        raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
    monkeypatch.setattr(main.accounts, "_perms", perms)
    monkeypatch.setattr(main.accounts, "_uid", lambda token: "u-plus" if token == PLUS else (_ for _ in ()).throw(AccountError("x")))
    return TestClient(main.app), client


def test_api_needs_the_right_to_write_but_not_ai_use(api):
    c, client = api
    assert c.post("/api/feedback/ai/status", json={"guest_id": GUEST, "token": ""}).status_code == 403
    r = c.post("/api/feedback/ai/status", json={"guest_id": GUEST, "token": PLUS}).json()
    assert r["consent"] == "" and r["configured"] and r["remaining"] == aif.DAILY_LIMIT
    no = c.post("/api/feedback/ai/rewrite", json={"guest_id": GUEST, "token": PLUS, "turns": ["Le quiz plante"]})
    assert no.status_code == 403 and client.calls == []
    assert c.post("/api/feedback/ai/consent", json={"guest_id": GUEST, "token": PLUS, "accept": True}).json()["consent"] == "accepted"
    assert main.feedback_writer.consents.state("acct:u-plus") == "accepted"  # par compte, pas par appareil
    ok = c.post("/api/feedback/ai/rewrite", json={"guest_id": GUEST, "token": PLUS, "turns": ["Le quiz plante"],
                                                  "context": {"tab": "games", "platform": "web", "secret": "x"}}).json()
    assert ok["status"] == "ready" and ok["draft"]["device"] == "Web"
    assert c.post("/api/feedback/ai/consent", json={"guest_id": GUEST, "token": PLUS, "accept": False}).json()["consent"] == "declined"
    assert c.post("/api/feedback/ai/rewrite", json={"guest_id": GUEST, "token": PLUS, "turns": ["x y z"]}).status_code == 403


def test_api_host_without_account_is_a_guest_subject(api, admin):  # noqa: F811
    r = admin.post("/api/feedback/ai/consent", json={"guest_id": GUEST, "token": "", "accept": True})
    assert r.status_code == 200 and main.feedback_writer.consents.state("guest:" + GUEST) == "accepted"


def test_api_unavailable_ai_lets_the_review_be_written(api):
    c, client = api
    client.fail = True
    c.post("/api/feedback/ai/consent", json={"guest_id": GUEST, "token": PLUS, "accept": True})
    r = c.post("/api/feedback/ai/rewrite", json={"guest_id": GUEST, "token": PLUS, "turns": ["Le quiz plante"]})
    assert r.status_code == 200 and r.json()["status"] == "unavailable"
    plain = c.post("/api/feedback", json={"guest_id": GUEST, "name": "Léa", "kind": "bug", "token": PLUS,
                                          "text": "Le quiz plante après la troisième question, tout se fige"})
    assert plain.status_code == 200 and "ai" not in main.feedback.all()[0]["context"]


def test_sent_review_keeps_the_original_text_and_prefills_the_triage(api):
    c, _ = api
    r = c.post("/api/feedback", json={"guest_id": GUEST, "name": "Léa", "kind": "idea", "token": PLUS,
                                      "text": "euh le quiz il bloque",
                                      "context": {"tab": "music", "platform": "iphone", "os": "iOS 26.1"},
                                      "ai": {**BUG, "area": "games"}})
    assert r.status_code == 200 and r.json()["mine"][0]["title"] == BUG["title"]
    item = main.feedback.all()[0]
    assert item["text"] == "euh le quiz il bloque" and item["kind"] == "bug" and item["status"] == "new"
    assert item["area"] == "games" and item["platforms"] == ["iphone"]
    assert item["context"]["ai"]["device"] == "iPhone · iOS 26.1" and item["context"]["ai"]["need"] == ""
    prompt = fb.build_prompt(item)
    assert "Version reformulée par l'IA" in prompt and "> Titre : Le Quiz se fige" in prompt
    bad = c.post("/api/feedback", json={"guest_id": GUEST, "name": "Léa", "kind": "idea", "token": PLUS,
                                        "text": "euh le quiz il bloque", "ai": {"kind": "bug"}})
    assert bad.status_code == 400
    short = c.post("/api/feedback", json={"guest_id": GUEST, "name": "Léa", "kind": "idea", "token": PLUS, "text": "court"})
    assert short.status_code == 400  # sans l'IA, les 30 caractères restent la règle
