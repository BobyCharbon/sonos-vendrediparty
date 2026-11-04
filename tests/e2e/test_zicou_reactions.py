"""Réactions de Zicou dans un vrai navigateur (app/static/pet/reactions.js) : une réponse marquée X-Zicou fait venir
le bandeau « +5 🪙 », la file renvoie le sien dans sa réponse, le texte n'est jamais du HTML, et l'offre d'adoption
mène au Zicou. Les décisions (plafonds, jeux d'alcool, sans Zicou) sont testées côté serveur (test_pet_reactions.py)."""
import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import FakeSupabase, Phone, Server  # noqa: E402

GID = "acct-" + "3" * 40


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


def member(browser, server):
    phone = Phone(browser, server, "Lea")
    phone.page.goto("/")
    phone.page.evaluate(f"localStorage.setItem('vp_guest', '{GID}')")
    return phone


def test_a_marked_response_brings_the_banner_and_text_is_never_html(browser, server):
    phone = member(browser, server)
    asked = []
    try:
        page = phone.page
        page.route("**/api/zicou-test", lambda r: r.fulfill(status=200, json={}, headers={"X-Zicou": "1"}))

        def reactions(route):
            asked.append(json.loads(route.request.post_data or "{}"))
            route.fulfill(status=200, json={"enabled": True, "items": [
                {"kind": "reward", "source": "party", "coins": 10, "text": "🎉 Bien joué ! +10 🪙 pour <b>Zicou</b>"}]})
        page.route("**/api/pet/reactions", reactions)
        page.evaluate("fetch('/api/zicou-test')")
        banner = page.locator("#zicouReaction")
        expect(banner).to_contain_text("+10 🪙 pour <b>Zicou</b>")   # affiché tel quel, jamais interprété
        assert page.locator("#zicouReaction b").count() == 0
        assert asked and asked[0]["guest_id"] == GID
        expect(banner).not_to_have_class("on", timeout=6000)          # éphémère
        assert not phone.errors, phone.errors
    finally:
        phone.close()


def test_the_queue_answer_shows_its_own_banner_and_adoption_leads_to_zicou(browser, server):
    phone = member(browser, server)
    try:
        page = phone.page
        page.route("**/api/queue", lambda r: r.fulfill(status=200, json={"ok": True, "zicou": [
            {"kind": "adopt", "text": "🥚 Adopte ton Zicou : il gagnera des pièces à chaque titre et chaque partie"}]}))
        page.evaluate("window.opened = 0; addEventListener('zicou:open', () => window.opened++)")
        page.evaluate("fetch('/api/queue', {method: 'POST', body: '{}'})")
        expect(page.locator("#zicouReaction")).to_contain_text("Adopte ton Zicou")
        page.locator("#zicouReaction button").click()
        assert page.evaluate("window.opened") == 1
        assert not phone.errors, phone.errors
    finally:
        phone.close()


def test_a_guest_without_an_account_never_asks(browser, server):
    phone = Phone(browser, server, "Tom")
    asked = []
    try:
        page = phone.page
        page.goto("/")
        page.route("**/api/zicou-test", lambda r: r.fulfill(status=200, json={}, headers={"X-Zicou": "1"}))
        page.route("**/api/pet/reactions", lambda r: (asked.append(1), r.fulfill(status=200, json={"items": []})))
        page.evaluate("fetch('/api/zicou-test')")
        page.wait_for_timeout(800)
        assert asked == [] and page.locator("#zicouReaction").count() == 0
    finally:
        phone.close()
