"""Refus Apple 1.4.3 (25.11) : l'app App Store (« PartyStore ») ne montre AUCUN jeu à boire, gorgée, boisson, drogue ni
mode Hot — écran Jeux, cartes, règles « ? », salle de jeux et ses feuilles de réglages. Le navigateur garde tout."""
import re

import pytest
pytest.importorskip("playwright.sync_api")

from app import store_app
from tests.e2e.helpers import Server

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0")
IPHONE = {"viewport": {"width": 390, "height": 760}, "is_mobile": True, "has_touch": True, "locale": "fr-CH"}
INIT = 'localStorage.setItem("vp_install_dismissed", "1"); localStorage.setItem("vp_name", "Léa");'
KEPT = ["whoof", "never", "roulette", "undercover", "likely", "quiz", "debate", "divan", "tmc", "masque", "reflet", "psy",
        "president", "neon", "island", "heist"]


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    s.stop()


def open_games(browser, server, store: bool):
    ctx = browser.new_context(base_url=server.url, user_agent=UA + (" PartyStore" if store else ""), **IPHONE)
    ctx.add_init_script(INIT)
    page = ctx.new_page()
    page.goto("/")
    page.evaluate("showTab('games')")
    page.wait_for_selector("#gHome .g-room-card", state="attached")
    return ctx, page


def drinks_in(text: str) -> list[str]:
    return sorted({m.group(0) for m in store_app.DRINK_RE.finditer(text)} | set(re.findall("[🍻🍺🥃🍸🍹🍷]", text)))


def test_store_app_games_screen_rules_and_room_have_no_drinking(browser, server):
    ctx, page = open_games(browser, server, store=True)
    # Toutes les cartes (sections cachées comprises : la salle les recopie) et leurs réglages.
    assert drinks_in(page.evaluate("document.getElementById('gamesRoot').textContent")) == []
    assert page.evaluate("[...document.querySelectorAll('#gHome [data-create]')].map((b) => b.dataset.create)")
    for kind in store_app.HIDDEN_GAMES:
        assert page.locator(f'#gHome [data-create="{kind}"]').count() == 0
    assert page.locator('#gHome [data-opt-group="mode"] [data-val="hot"]').count() == 0
    assert "M8 7h13" not in page.evaluate("GAME_ICONS.never")  # pas l'icône aux deux verres de Je n'ai jamais
    assert page.locator('#gHome [data-opt-group="sips"], #gHome [data-opt="qzsips"], #gHome [data-opt="lkalcohol"]').count() == 0
    # Règles « ? » de chaque jeu gardé, de la salle comprise.
    for kind in KEPT + ["room"]:
        html = page.evaluate("(t) => { const r = GAME_RULES[t]; return typeof r === 'string' ? r : ''; }", kind)
        text = re.sub(r"<[^>]+>", " ", html)
        assert drinks_in(text) == [], kind
        assert "Hot" not in text and "Mix" not in text or kind not in ("whoof", "never"), kind
    # Salle de jeux : catégories et feuille de réglages de chaque jeu gardé.
    page.locator('#gHome [data-create="room"]').click()
    page.wait_for_selector('[data-room-pick="whoof"]', state="visible")
    assert "🍻" not in page.inner_text("body") and "Alcool" not in page.inner_text("body")
    for kind in store_app.HIDDEN_GAMES:
        assert page.locator(f'[data-room-pick="{kind}"]').count() == 0
    for kind in KEPT:
        if page.locator(f'[data-room-pick="{kind}"]').count():
            page.evaluate("(t) => openRoomSheet(t)", kind)
            assert drinks_in(page.evaluate("document.body.innerText")) == [], kind
            page.evaluate("closeRoomSheet(true)")
    ctx.close()


def test_the_browser_keeps_its_games(browser, server):
    ctx, page = open_games(browser, server, store=False)
    text = page.evaluate("document.getElementById('gamesRoot').textContent")
    assert "🍻 Alcool" in text and "Beer pong" in text
    assert page.locator('#gHome [data-create="pyramid"]').count() == 1
    assert page.locator('#gHome [data-opt-group="mode"] [data-val="hot"]').count() == 2
    ctx.close()
