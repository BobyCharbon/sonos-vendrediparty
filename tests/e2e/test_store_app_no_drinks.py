"""Refus Apple 1.4.3 (25.11) : l'app App Store (« PartyStore ») ne montre AUCUN mot ni emoji de boisson, de drogue, ni
mode Hot — écran Jeux, cartes, règles « ? », salle de jeux, feuilles de réglages. Décision de l'admin du 25.11 : les jeux à
boire (Pyramide, Je n'ai jamais, Qui de nous ?, Roulette, Beer pong, Biskit, Purify Test) et toute option de gorgées (aucun
« ⭐ Mode points » à la place) sont absents ; l'onglet Musique est caché et rejoint par Jeux › Code (6 chiffres). Le
navigateur garde tout."""
import re

import pytest
pytest.importorskip("playwright.sync_api")

from app import store_app
from tests.e2e.helpers import Server

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0")
IPHONE = {"viewport": {"width": 390, "height": 760}, "is_mobile": True, "has_touch": True, "locale": "fr-CH"}
INIT = 'localStorage.setItem("vp_install_dismissed", "1"); localStorage.setItem("vp_name", "Léa");'
KEPT = ["undercover", "likely", "quiz", "debate", "divan", "tmc", "masque", "reflet", "psy", "president", "neon", "island", "heist"]


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
    return sorted({m.group(0) for m in store_app.DRINK_RE.finditer(text)} | set(re.findall("[🍻🍺🥃🍸🍹🍷🍬]", text))
                  | set(re.findall(r"(?i)bonbons?", text)))


def test_store_app_games_screen_rules_and_room_have_no_drinking(browser, server):
    ctx, page = open_games(browser, server, store=True)
    # Toutes les cartes (sections cachées comprises : la salle les recopie) et leurs réglages.
    assert drinks_in(page.evaluate("document.getElementById('gamesRoot').textContent")) == []
    assert page.evaluate("[...document.querySelectorAll('#gHome [data-create]')].map((b) => b.dataset.create)")
    for kind in store_app.HIDDEN_GAMES:
        assert page.locator(f'#gHome [data-create="{kind}"]').count() == 0
    assert page.locator('#gHome [data-opt-group="mode"] [data-val="hot"]').count() == 0
    # Aucune option de gorgées, ni « ⭐ Mode points » à la place, ni thème WTF, ni paquet « Entre amis ».
    assert page.locator('#gHome .g-opt', has_text="Mode points").count() == 0
    for sel in ('[data-opt="qzsips"]', '[data-opt="lkalcohol"]', '[data-opt="lkfriends"]', '[data-opt-group="lksips"]',
                '[data-opt-group="sips"]', '.g-db [data-val="wtf"]'):
        assert page.locator(f"#gHome {sel}").count() == 0, sel
    assert page.locator("#gHome section.g-cat[data-cat=drinks]").count() == 0  # pas de catégorie vide
    assert "Trou du cul" not in page.evaluate("rulesFor('president', null)")
    # Règles « ? » de chaque jeu gardé, de la salle comprise.
    for kind in KEPT + ["room"]:
        html = page.evaluate("(t) => rulesFor(t, null) || ''", kind)
        text = re.sub(r"<[^>]+>", " ", html)
        assert drinks_in(text) == [], kind
        assert "Hot" not in text and "Mix" not in text or kind not in ("whoof", "never"), kind
    # Salle de jeux : catégories et feuille de réglages de chaque jeu gardé.
    page.locator('#gHome [data-create="room"]').click()
    page.wait_for_selector('[data-room-pick="quiz"]', state="visible")
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


def test_store_app_refuses_pyramid_even_by_code(browser, server):
    """Pyramide créée sur le web (ou dans l'app) : refusée à l'app, même par code ; message neutre, retour à l'accueil."""
    import httpx
    ctx, page = open_games(browser, server, store=True)
    ua = {"User-Agent": UA + " PartyStore"}
    assert httpx.post(server.url + "/api/games", headers=ua, json={"guest_id": "store-pyr-01", "name": "Léa", "type": "pyramid"}).status_code == 403
    web = httpx.post(server.url + "/api/games", json={"guest_id": "web-pyr-host1", "name": "Tom", "type": "pyramid"}).json()
    page.fill("#gCode", web["code"])
    page.click("#gJoinForm .g-code-go")
    page.wait_for_timeout(1500)
    assert "Ce jeu n'est pas disponible dans l'app." in page.inner_text("body")
    assert "sur le site" not in page.inner_text("body")
    ctx.close()


def test_store_app_hides_the_music_tab_and_joins_a_music_party_by_a_six_digit_code(browser, server):
    """Onglet Musique caché (barre web, donc barre native) ; Musique ne s'ouvre qu'après le code à 6 chiffres de Jeux."""
    import json
    from pathlib import Path
    pin = json.loads((Path(server.data) / "session.json").read_text())["guest_pin"]  # code de la soirée (6 chiffres)
    ctx, page = open_games(browser, server, store=True)
    assert page.locator('#tabs [data-tab="music"]').is_hidden()
    page.evaluate("showTab('music')")  # action rapide « Ajouter un titre », notification…
    assert page.evaluate("document.body.dataset.tab") == "games"
    assert page.get_attribute("#gCode", "maxlength") == "6"
    assert len(pin) == 6
    page.fill("#gCode", pin)
    page.wait_for_function("document.body.dataset.tab === 'music'", timeout=5000)
    assert page.locator('#tabs [data-tab="music"]').is_hidden()
    page.evaluate("showTab('games')")
    assert page.locator("#gMusicBack").is_visible()
    ctx.close()
    # Le navigateur garde son onglet Musique.
    ctx, page = open_games(browser, server, store=False)
    assert page.locator('#tabs [data-tab="music"]').is_visible()
    assert page.get_attribute("#gCode", "maxlength") == "4"
    ctx.close()
