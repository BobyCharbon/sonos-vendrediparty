"""Refus Apple 1.4.3 (25.11) : l'app App Store (« PartyStore ») ne montre AUCUN mot ni emoji de boisson, de drogue, ni
mode Hot — écran Jeux, cartes, règles « ? », salle de jeux, feuilles de réglages et une partie de Pyramide. Les gorgées y
sont des ⭐ points (« ⭐ Mode points », Pyramide en points, ni bonbon ni nourriture : décision de l'admin du 25.11). Le navigateur garde tout."""
import re

import pytest
pytest.importorskip("playwright.sync_api")

from app import store_app
from tests.e2e.helpers import Server

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0")
IPHONE = {"viewport": {"width": 390, "height": 760}, "is_mobile": True, "has_touch": True, "locale": "fr-CH"}
INIT = 'localStorage.setItem("vp_install_dismissed", "1"); localStorage.setItem("vp_name", "Léa");'
KEPT = ["pyramid", "whoof", "never", "roulette", "undercover", "likely", "quiz", "debate", "divan", "tmc", "masque", "reflet", "psy",
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
    assert "M8 7h13" not in page.evaluate("GAME_ICONS.never")  # pas l'icône aux deux verres de Je n'ai jamais
    # ⭐ Mode points à la place des gorgées : Qui de nous ?, Je n'ai jamais, Quiz, Qui est le plus…
    assert page.locator('#gHome .g-opt', has_text="⭐ Mode points").count() == 4
    # Règles « ? » de chaque jeu gardé, de la salle comprise.
    for kind in KEPT + ["room"]:
        html = page.evaluate("(t) => rulesFor(t, null) || ''", kind)
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


def test_store_app_pyramid_plays_with_points(browser, server):
    """Pyramide dans l'app : distribution et mémorisation en points, tableau des points, sans un mot de boisson."""
    import httpx
    from app import games
    ctx, page = open_games(browser, server, store=True)
    ua = {"User-Agent": UA + " PartyStore"}
    me = page.evaluate("guestId")
    g = httpx.post(server.url + "/api/games", headers=ua, json={"guest_id": me, "name": "Léa", "type": "pyramid"}).json()
    act = lambda gid, action, **kw: httpx.post(server.url + f"/api/games/{g['code']}", headers=ua,
                                               json={"guest_id": gid, "action": action, **kw})
    assert act("store-tom-01", "join", name="Tom").status_code == 200
    assert act(me, "start").status_code == 200
    page.evaluate("(c) => { setGame(c); refreshGame(); }", g["code"])
    page.wait_for_timeout(1500)
    texts = [page.evaluate("document.body.innerText")]
    for step, value in ((1, "red"), (2, "plus"), (3, "dedans"), (4, games.PYR_SUITS[0])):
        for gid in (me, "store-tom-01"):
            r = act(gid, "pans", target=value)
            assert r.status_code == 200, r.text
            page.wait_for_timeout(700)
            texts.append(page.evaluate("document.body.innerText"))
    state = httpx.get(server.url + f"/api/games/{g['code']}?guest_id={me}", headers=ua).json()
    assert state["phase"] == "look"
    texts.append(page.evaluate("document.body.innerText"))
    joined = "\n".join(texts)
    assert "⭐ Tableau des points" in joined and " point" in joined
    assert drinks_in(joined) == [], drinks_in(joined)
    ctx.close()


def test_store_app_never_with_points_mode_shows_no_drinking(browser, server):
    """« Je n'ai jamais » avec le ⭐ Mode points allumé : les points donnés s'affichent (compteur du haut compris), sans un
    mot ni emoji de boisson (bug trouvé en recette simulateur le 25.11 : le compteur 🍻 du haut n'était pas traduit)."""
    import httpx
    ctx, page = open_games(browser, server, store=True)
    ua = {"User-Agent": UA + " PartyStore"}
    me = page.evaluate("guestId")
    g = httpx.post(server.url + "/api/games", headers=ua, json={"guest_id": me, "name": "Léa", "type": "never", "sips": 2}).json()
    act = lambda gid, action, **kw: httpx.post(server.url + f"/api/games/{g['code']}", headers=ua,
                                               json={"guest_id": gid, "action": action, **kw})
    assert act("store-tom-02", "join", name="Tom").status_code == 200
    assert act(me, "start").status_code == 200
    page.evaluate("(c) => { setGame(c); refreshGame(); }", g["code"])
    page.wait_for_timeout(1500)
    question = page.evaluate("document.body.innerText")
    for gid in (me, "store-tom-02"):
        assert act(gid, "vote", target="yes").status_code == 200
    page.wait_for_timeout(2500)
    shown = question + "\n" + page.evaluate("document.body.innerText")
    assert "2 points" in shown, shown[-800:]
    assert drinks_in(shown) == [], drinks_in(shown)
    ctx.close()
