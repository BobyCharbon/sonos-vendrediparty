"""« 🚩 Signaler ce prénom » (contrôle Apple 1.2, 27.11) dans l'app App Store : menu ☰ › Participants, 🚩 à côté du prénom
d'un AUTRE joueur, confirmation courte (« Traité sous 24 h · support@vendrediparty.ch »), puis « Joueur N » aussitôt."""
import os

import httpx
import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import IGNORED_CONSOLE, Server, show_game_cards

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0 PartyStore")
IPHONE = {"viewport": {"width": 390, "height": 760}, "is_mobile": True, "has_touch": True, "locale": "fr-CH"}


@pytest.fixture(scope="module")
def server():
    s = Server(compagnon=False)
    yield s
    s.stop()


def test_a_player_reports_another_players_name_and_the_table_sees_joueur_n(browser, server):
    ctx = browser.new_context(base_url=server.url, user_agent=UA, **IPHONE)
    ctx.add_init_script('localStorage.setItem("vp_install_dismissed", "1"); localStorage.setItem("vp_name", "Tom");'
                        'localStorage.setItem("vp_games_terms", "1");')
    page = ctx.new_page()
    errors, dialogs = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not any(x in m.text for x in IGNORED_CONSOLE) and errors.append(m.text))
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.goto("/")
    page.evaluate("showTab('games')")
    page.wait_for_selector("#gHome:not(.hidden)")
    show_game_cards(page)
    page.click('#gHome [data-create="likely"]')
    page.wait_for_function("game && game.type === 'likely'")
    code = page.evaluate("myGame")
    r = httpx.post(f"{server.url}/api/games/{code}", headers={"User-Agent": UA},
                   json={"guest_id": "e2e-namerep-bad", "name": "Kevin le roi", "action": "join", "terms": True})
    assert r.status_code == 200, r.text
    page.evaluate("refreshGame()")
    page.wait_for_function("game.players.some((p) => p.name === 'Kevin le roi')")
    page.evaluate("openDrawer()")
    flag = page.locator('#gDrawerPlayers [data-gact="nreport"]')
    flag.wait_for(state="visible")
    assert flag.count() == 1  # jamais à côté de son propre prénom
    assert flag.get_attribute("aria-label") == "Signaler le prénom Kevin le roi"
    assert "Un prénom déplacé" in page.inner_text("#gDrawerPlayers")
    shots = os.environ.get("PARTY_SHOTS")
    if shots:
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(shots, "signaler-prenom-avant.png"))
    flag.click()
    page.wait_for_function("game.players.some((p) => p.name.startsWith('Joueur '))")
    assert dialogs and "Signaler ce prénom" in dialogs[0] and "Traité sous 24 h · support@vendrediparty.ch" in dialogs[0]
    text = page.inner_text("#gDrawerPlayers")
    assert "Kevin le roi" not in text and "Joueur 1" in text
    assert page.locator('#gDrawerPlayers [data-gact="nreport"]').count() == 0
    if shots:
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(shots, "signaler-prenom-apres.png"))
    # L'autre téléphone (et toute la table) le lit aussi « Joueur 1 ».
    other = httpx.get(f"{server.url}/api/games/{code}?guest_id=e2e-namerep-bad", headers={"User-Agent": UA}).json()
    assert "Kevin le roi" not in [p["name"] for p in other["players"]]
    assert errors == [], errors
    assert not server.errors()
    ctx.close()
