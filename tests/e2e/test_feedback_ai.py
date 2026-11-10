"""« Ton avis » avec l'IA, dans un vrai navigateur : feuille d'accord, dictée, reformulation, « C'est bien ça ? »,
Corriger, question de précision, texte tel quel. L'IA (et la reconnaissance vocale) sont simulées dans le navigateur ;
l'envoi final passe par le vrai serveur, qui revalide la version structurée."""
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import FakeSupabase, Phone, Server, sign_in  # noqa: E402

SHOTS = Path(os.environ.get("FEEDBACK_AI_SHOTS", "test-results/shots/ia-avis"))
TOKEN = "jeton-de-test-guest-plus-0001"

# Reconnaissance vocale simulée : chaque start() « entend » la phrase suivante, puis s'arrête au 2e toucher.
FAKE_SPEECH = """
window.__heard = [];
window.webkitSpeechRecognition = class {
  start() {
    const text = window.__heard.shift() || "";
    setTimeout(() => this.onresult && this.onresult({ results: [[{ transcript: text }]] }), 30);
  }
  stop() { setTimeout(() => this.onend && this.onend(), 10); }
};
window.SpeechRecognition = window.webkitSpeechRecognition;
"""

BUG = {"kind": "bug", "area": "games", "game": "quiz", "title": "Le Quiz se fige après la 3e question",
       "description": "Quand je joue au Quiz, l'écran se fige après la troisième question.",
       "steps": ["Lancer un Quiz", "Répondre à 3 questions"], "expected": "La 4e question s'affiche",
       "actual": "L'écran reste figé", "need": "", "proposal": "", "device": "Web · iPhone Safari"}


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


class FakeAI:
    """Routes /api/feedback/ai/* simulées : accord gardé, réponses de l'IA données dans l'ordre."""

    def __init__(self, page, answers):
        self.consent, self.answers, self.calls = "", list(answers), []
        page.route("**/api/feedback/ai/**", self.handle)

    def handle(self, route):
        path, body = route.request.url.rsplit("/", 1)[-1], json.loads(route.request.post_data or "{}")
        if path == "consent":
            self.consent = "accepted" if body["accept"] else "declined"
        if path == "rewrite":
            self.calls.append(body)
            return route.fulfill(json={**self.answers.pop(0), "remaining": 9})
        route.fulfill(json={"configured": True, "consent": self.consent, "remaining": 10, "daily_limit": 10,
                            "max_turn": 1500, "max_turns": 4})


def open_feedback(phone):
    phone.page.add_init_script(FAKE_SPEECH)
    phone.page.goto("/")
    sign_in(phone, TOKEN)
    phone.page.evaluate("showTab('feedback')")
    expect(phone.page.locator('[data-view="feedback"]')).to_be_visible()


def shot(phone, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    phone.page.screenshot(path=str(SHOTS / f"{name}.png"))


def test_dictation_then_rewrite_correct_and_send(browser, server):
    guest = Phone(browser, server, "Lea")
    try:
        ai = FakeAI(guest.page, [{"status": "ready", "question": "", "draft": {**BUG, "title": "Le Quiz bloque"}},
                                 {"status": "ready", "question": "", "draft": BUG}])
        open_feedback(guest)
        page = guest.page
        expect(page.locator("#fbMic")).to_be_visible()
        expect(page.locator("#fbMic")).to_contain_text("Dis-le à voix haute")
        expect(page.locator("#fbAiRow")).to_contain_text("L'IA peut t'aider")
        shot(guest, "1-formulaire")
        page.evaluate("window.__heard.push('euh le quiz il bloque après la troisième question')")
        page.locator("#fbMic").tap()
        expect(page.locator("#fbText")).to_have_value("euh le quiz il bloque après la troisième question")
        expect(page.locator("#fbMic")).to_contain_text("Je t'écoute")
        page.locator("#fbMic").tap()  # fini de parler : envoi
        expect(page.locator("#fbAiConsent")).to_be_visible()
        # Accord unique pour toute l'IA de Party (787b822) : ce qui part chez Anthropic est dit avant l'accord.
        expect(page.locator("#fbAiConsent")).to_contain_text(
            "Quand tu utilises l'IA, Party envoie ce que tu lui confies à Anthropic (Claude) : le texte de ton avis "
            "(et la transcription de ta voix)")
        expect(page.locator("#fbAiConsent")).to_contain_text("Jamais ton numéro.")
        assert ai.calls == []  # rien n'est parti avant l'accord
        shot(guest, "2-accord")
        page.locator("#fbAiYes").tap()
        expect(page.locator("#fbAiReview")).to_contain_text("Le Quiz bloque")
        expect(page.locator("#fbAiAsk")).to_have_text("C'est bien ça ?")
        assert ai.calls[0]["turns"] == ["euh le quiz il bloque après la troisième question"]
        assert ai.calls[0]["context"]["platform"] == "web" and "name" in ai.calls[0]
        shot(guest, "3-reformulation")
        page.locator("#fbAiFix").tap()
        page.locator("#fbAiMoreText").fill("le titre doit dire qu'il se fige")
        page.locator("#fbAiMoreText").press("Enter")
        expect(page.locator("#fbAiDraft")).to_contain_text("Le Quiz se fige après la 3e question")
        assert ai.calls[1]["turns"][-1] == "le titre doit dire qu'il se fige"
        expect(page.locator("#fbAiDraft")).to_contain_text("Lancer un Quiz")
        shot(guest, "4-corrige")
        page.locator("#fbAiOk").tap()
        expect(page.locator("#fbMine")).to_contain_text("Le Quiz se fige après la 3e question")  # titre de l'IA
        expect(page.locator("#fbAiReview")).to_be_hidden()
        expect(page.locator("#fbAiRow")).to_contain_text("L'IA t'aide")
        shot(guest, "5-envoye")
        assert not guest.errors, guest.errors
    finally:
        guest.close()
    item = json.loads((Path(server.data) / "feedback.json").read_text(encoding="utf-8"))[-1]  # texte d'origine + version IA
    assert item["text"].startswith("euh le quiz il bloque") and "il se fige" in item["text"]
    assert (item["kind"], item["area"], item["platforms"]) == ("bug", "games", ["web"])
    assert item["context"]["ai"]["title"] == "Le Quiz se fige après la 3e question"


def test_precision_question_then_send(browser, server):
    guest = Phone(browser, server, "Lea")
    try:
        ai = FakeAI(guest.page, [{"status": "needs_info", "question": "Dans quel jeu est-ce arrivé ?",
                                  "draft": {**BUG, "game": "", "title": "Un jeu se fige"}},
                                 {"status": "ready", "question": "", "draft": BUG}])
        ai.consent = "accepted"
        open_feedback(guest)
        page = guest.page
        page.locator("#fbText").fill("un jeu se fige")
        page.locator("#fbText").press("Enter")  # Entrée envoie
        expect(page.locator("#fbAiQuestion")).to_have_text("Dans quel jeu est-ce arrivé ?")
        expect(page.locator("#fbAiOk")).to_be_hidden()
        shot(guest, "6-question")
        page.evaluate("window.__heard.push('le quiz')")
        page.locator("#fbAiMoreMic").tap()
        expect(page.locator("#fbAiMoreText")).to_have_value("le quiz")
        page.locator("#fbAiMoreMic").tap()  # fin de la dictée : la précision part
        expect(page.locator("#fbAiAsk")).to_be_visible()
        assert ai.calls[1]["turns"] == ["un jeu se fige", "le quiz"]
        page.locator("#fbAiOk").tap()
        expect(page.locator("#fbMine")).to_contain_text("Le Quiz se fige")
        assert not guest.errors, guest.errors
    finally:
        guest.close()


def test_send_my_text_as_is_and_writing_without_ai(browser, server):
    guest = Phone(browser, server, "Lea")
    try:
        ai = FakeAI(guest.page, [{"status": "ready", "question": "", "draft": BUG}])
        open_feedback(guest)
        page = guest.page
        page.locator("#fbText").fill("Le quiz se bloque après la troisième question, plus rien ne bouge")
        page.locator("#fbSend").tap()
        page.locator("#fbAiYes").tap()
        expect(page.locator("#fbAiAsk")).to_be_visible()
        page.locator("#fbAiRaw").tap()  # « Envoyer mon texte tel quel »
        expect(page.locator("#fbMine")).to_contain_text("Le quiz se bloque après la troisième question")

        # Accord retiré (Réglages › Ton avis) : plus aucun appel, l'avis s'écrit comme avant.
        page.locator("#fbAiToggle").tap()
        expect(page.locator("#fbAiToggle")).to_have_text("Activer l'IA")
        page.locator("#fbText").fill("Plus de chapeaux pour Zicou, un chapeau de cowboy par exemple")
        page.locator("#fbSend").tap()
        expect(page.locator("#fbMine")).to_contain_text("Plus de chapeaux pour Zicou")
        assert len(ai.calls) == 1 and ai.consent == "declined"
        assert not guest.errors, guest.errors
    finally:
        guest.close()


def test_ai_at_its_daily_limit_still_sends_the_review_as_is(browser, server):
    """Retour de l'admin du 11.11 : « Tu as utilisé l'IA 10 fois aujourd'hui » s'affichait et l'avis ne partait pas."""
    guest = Phone(browser, server, "Lea")
    try:
        ai = FakeAI(guest.page, [{"status": "unavailable", "message": "Tu as utilisé l'IA 10 fois aujourd'hui : elle revient demain."}])
        open_feedback(guest)
        page = guest.page
        page.locator("#fbText").fill("Pouvoir agrandir la photo d'un joueur en touchant dessus, sans trop la dégrader")
        page.locator("#fbSend").tap()
        page.locator("#fbAiYes").tap()  # accord de la feuille
        expect(page.locator("#fbMine")).to_contain_text("Pouvoir agrandir la photo d'un joueur")
        expect(page.locator("#fbAiReview")).to_be_hidden()
        assert len(ai.calls) == 1
        assert not guest.errors, guest.errors
    finally:
        guest.close()


def test_declining_the_sheet_writes_without_ai(browser, server):
    guest = Phone(browser, server, "Lea")
    try:
        ai = FakeAI(guest.page, [])
        open_feedback(guest)
        page = guest.page
        page.locator("#fbText").fill("Un mode équipe au Quiz, avec deux camps")
        page.locator("#fbSend").tap()
        page.locator("#fbAiNo").tap()  # « Écrire sans l'IA »
        expect(page.locator("#fbMine")).to_contain_text("Un mode équipe au Quiz")
        assert ai.calls == [] and ai.consent == "declined"
        assert not guest.errors, guest.errors
    finally:
        guest.close()


def test_without_ai_configured_the_form_is_unchanged(browser, server):
    """Serveur réel sans clé Anthropic : pas de ligne IA, l'avis s'écrit comme avant (30 caractères)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("clé Anthropic présente : le serveur de test aurait l'IA allumée")
    guest = Phone(browser, server, "Lea")
    try:
        open_feedback(guest)
        page = guest.page
        expect(page.locator("#fbAiRow")).to_be_hidden()
        page.locator("#fbText").fill("Un mode équipe au Quiz, avec deux camps")
        page.locator("#fbSend").tap()
        expect(page.locator("#fbMine")).to_contain_text("Un mode équipe au Quiz")
        expect(page.locator("#fbAiConsent")).to_be_hidden()
        assert not guest.errors, guest.errors
    finally:
        guest.close()
