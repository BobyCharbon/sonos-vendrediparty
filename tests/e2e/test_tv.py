"""Écran TV (/tv) dans un vrai navigateur en 1920×1080 : l'hôte entre son code une fois, puis la télé montre le titre
en cours, les prochaines demandes avec les prénoms, le code et le QR. Un prénom piégé reste du texte."""
import os

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, Server  # noqa: E402

TRAP = '<img src=x onerror="window.hacked=1">'
LIVE = {"active": True, "pin": "4821", "url": "https://party.example.ch/", "event": "Vendredi chez Boby", "room": "Salon",
        "state": "PLAYING", "games": [{"code": "1234", "name": "Undercover", "players": 5}],
        "now": {"title": "Get Lucky", "artist": "Daft Punk", "art": "", "by": "Léa"},
        "upcoming": [{"title": "One More Time", "artist": "Daft Punk", "art": "", "by": TRAP},
                     {"title": "Titre de la playlist", "artist": "Artiste", "art": "", "by": None}]}


@pytest.fixture
def server():
    s = Server()
    yield s
    s.stop()


def test_the_host_opens_the_tv_screen_once_and_it_shows_the_party(browser, server):
    ctx = browser.new_context(base_url=server.url, viewport={"width": 1920, "height": 1080})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto("/tv")
        expect(page.get_by_label("Code admin")).to_be_visible()
        page.get_by_label("Code admin").fill(ADMIN_PIN)
        page.get_by_role("button", name="Afficher").click()
        expect(page.locator("#nowTitle")).to_have_text("La soirée va commencer")  # vraie réponse du serveur
        expect(page.locator("#pinCode")).to_have_text(server_pin(page))

        page.route("**/api/tv", lambda route: route.fulfill(json=LIVE))
        page.reload()
        expect(page.locator("#nowTitle")).to_have_text("Get Lucky")
        expect(page.locator("#nowBy")).to_have_text("🙋 Demandé par Léa")
        expect(page.locator("#upcoming li")).to_have_count(2)
        expect(page.locator("#upcoming li").first).to_contain_text(TRAP)  # affiché tel quel, jamais interprété
        assert page.evaluate("window.hacked") is None
        expect(page.locator("#event")).to_have_text("🎉 Vendredi chez Boby")
        expect(page.locator("#games")).to_have_text("🎮 Undercover · 5 joueurs")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if os.environ.get("TV_SCREENSHOT"):
            page.screenshot(path=os.environ["TV_SCREENSHOT"])
        assert not errors
    finally:
        ctx.close()


def server_pin(page):
    return page.request.get("/api/tv").json()["pin"]
