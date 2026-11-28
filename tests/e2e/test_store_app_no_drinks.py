"""Refus Apple 1.4.3 (25.11) : l'app App Store (« PartyStore ») ne montre AUCUN mot ni emoji de boisson, de drogue, ni
mode Hot — écran Jeux, cartes, règles « ? », salle de jeux, feuilles de réglages. Décision de l'admin du 25.11 : les jeux à
boire (Pyramide, Je n'ai jamais, Qui de nous ?, Roulette, Beer pong, Biskit, Purify Test) et toute option de gorgées (aucun
« ⭐ Mode points » à la place) sont absents ; l'onglet Musique n'apparaît qu'après Jeux › Code (6 chiffres), le temps
de la soirée. Le
navigateur garde tout."""
import re

import pytest
pytest.importorskip("playwright.sync_api")

from app import store_app
from tests.e2e.helpers import Server

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0")
IPHONE = {"viewport": {"width": 390, "height": 760}, "is_mobile": True, "has_touch": True, "locale": "fr-CH"}
INIT = ('localStorage.setItem("vp_install_dismissed", "1"); localStorage.setItem("vp_name", "Léa");'
        'localStorage.setItem("vp_games_terms", "1");')  # case des conditions des jeux déjà cochée
KEPT = ["undercover", "likely", "quiz", "debate", "divan", "reflet", "psy", "president", "neon", "island", "heist"]  # tmc, masque : cachés (28.11)


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
    assert "trou du cul" not in page.evaluate("rulesFor('president', null)").lower()
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


NATIVE_TABS = ('window.__tabStates = []; window.PartyNative = { platform: "ios", tabs: { update: (s) => '
               'window.__tabStates.push(JSON.parse(JSON.stringify(s))) } };')


def music_pin(server) -> str:
    import json
    from pathlib import Path
    return json.loads((Path(server.data) / "session.json").read_text())["guest_pin"]  # code de la soirée (6 chiffres)


def native_tabs(page) -> list[str]:
    page.wait_for_timeout(200)  # la barre native reçoit les changements à l'image suivante
    return [t["id"] for t in page.evaluate("window.__tabStates[window.__tabStates.length - 1]")["tabs"]]


def music_tab(page):
    return page.locator('#tabs [data-tab="music"]')


def music_tab_shown(page) -> bool:
    """Bouton de la barre web présent (la barre web elle-même est invisible quand la barre native la remplace)."""
    return not page.evaluate("""document.querySelector('#tabs [data-tab="music"]').classList.contains('hidden')""")


@pytest.fixture(scope="module")
def music_server():
    """Serveur dont la soirée Musique est « en cours » (sans Sonos : la file répond « injoignable ») ; l'état de session
    est celui du vrai serveur : 401 code changé ou invité déconnecté, « removed », soirée arrêtée."""
    import json
    from pathlib import Path
    s = Server()
    s.halt()
    path = Path(s.data) / "session.json"
    session = json.loads(path.read_text())
    path.write_text(json.dumps({**session, "active": True, "room_name": "Salon", "room_uid": "RINCON_TEST"}))
    s.start_again()
    yield s
    s.stop()


def open_store_app(browser, server):
    """App App Store, pont natif de la barre d'onglets simulé (NativeBridge.swift)."""
    ctx = browser.new_context(base_url=server.url, user_agent=UA + " PartyStore", **IPHONE)
    ctx.add_init_script(INIT + NATIVE_TABS)
    page = ctx.new_page()
    page.goto("/")
    page.evaluate("showTab('games')")
    page.wait_for_selector("#gHome .g-room-card", state="attached")
    return ctx, page


def test_store_app_music_tab_appears_with_the_six_digit_code_and_leaves_with_the_party(browser, music_server):
    """Décision de l'admin du 27.11 : pas d'onglet Musique → code à 6 chiffres dans Jeux → l'onglet apparaît (barre web ET
    barre native) → « Quitter la soirée » → plus d'onglet, retour sur Jeux. Relancer l'app ne le ramène pas."""
    server = music_server
    pin = music_pin(server)
    ctx, page = open_store_app(browser, server)
    assert not music_tab_shown(page) and "music" not in native_tabs(page)
    page.evaluate("showTab('music')")  # action rapide « Ajouter un titre », notification…
    assert page.evaluate("document.body.dataset.tab") == "games"
    assert "6 chiffres : la soirée Musique" in page.inner_text(".g-code-note")  # 2.5.19 : dit à l'écran
    assert page.get_attribute("#gCode", "maxlength") == "6"
    assert len(pin) == 6
    page.fill("#gCode", pin)
    page.wait_for_function("document.body.dataset.tab === 'music'", timeout=5000)
    assert music_tab_shown(page) and "music" in native_tabs(page)
    page.evaluate("showTab('games')")
    assert page.locator("#gMusicBack").is_visible()
    page.locator("#gMusicBack").click()
    page.wait_for_selector("#musicLeave", state="visible")
    page.locator("#musicLeave").click()
    page.wait_for_function("document.body.dataset.tab === 'games'", timeout=5000)
    assert not music_tab_shown(page) and "music" not in native_tabs(page)
    assert page.locator("#gMusicBack").is_hidden()
    # Le serveur a révoqué l'accès : relancer l'app ne ramène pas l'onglet.
    page.reload()
    page.wait_for_function("window.__tabStates.length > 0")
    page.wait_for_timeout(800)
    assert not music_tab_shown(page) and "music" not in native_tabs(page)
    ctx.close()
    # Le navigateur garde son onglet Musique.
    ctx, page = open_games(browser, music_server, store=False)
    assert music_tab(page).is_visible()
    assert page.get_attribute("#gCode", "maxlength") == "4"
    ctx.close()


def test_store_app_music_tab_leaves_when_the_host_removes_the_guest_changes_the_code_or_stops(browser, music_server):
    import httpx
    from tests.e2e.helpers import ADMIN_PIN
    server = music_server
    admin = httpx.Client(base_url=server.url)
    assert admin.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200
    for how in ("ban", "kick", "pin", "stop"):
        ctx, page = open_store_app(browser, server)
        page.fill("#gCode", music_pin(server))
        page.wait_for_function("document.body.dataset.tab === 'music'", timeout=5000)
        assert "music" in native_tabs(page)
        gid = page.evaluate("guestId")
        if how == "ban":  # retiré de la file sans limite par l'hôte
            assert admin.post("/api/admin/ban", json={"guest_id": gid}).status_code == 200
        elif how == "kick":  # « Déconnecter » de l'hôte
            assert admin.post("/api/admin/kick", json={"guest_id": gid}).status_code == 200
        elif how == "pin":  # nouveau code : tout le monde sort de la soirée
            assert admin.post("/api/admin/pin", json={}).status_code == 200
        else:  # l'hôte arrête la soirée
            assert admin.post("/api/admin/stop").status_code == 200
        page.evaluate("refresh()")  # le flux en direct le fait aussi ; ici on n'attend pas
        page.wait_for_function("document.body.dataset.tab === 'games'", timeout=5000)
        assert not music_tab_shown(page) and "music" not in native_tabs(page), how
        if how == "ban":
            assert admin.post("/api/admin/unban", json={"guest_id": gid}).status_code == 200
        ctx.close()
    # Soirée arrêtée = soirée quittée : à la suivante, l'onglet ne revient pas sans le code.
    session = __import__("json").loads((__import__("pathlib").Path(server.data) / "session.json").read_text())
    assert not session["active"] and len(session["revoked"]) >= 1


def test_store_app_code_without_a_running_party_says_so_and_shows_no_tab(browser, server):
    """Bon code, mais aucune soirée en cours (serveur de test sans Sonos) : on reste sur Jeux, sans onglet, et on le dit."""
    ctx, page = open_store_app(browser, server)
    page.fill("#gCode", music_pin(server))
    page.wait_for_selector("text=Pas de soirée Musique en cours pour le moment.", timeout=5000)
    assert page.evaluate("document.body.dataset.tab") == "games"
    assert not music_tab_shown(page) and "music" not in native_tabs(page)
    ctx.close()


def test_store_app_game_stats_show_only_brain_and_the_browser_keeps_purify(browser, server):
    # Tour 3 (25.11) : « Mes stats de jeu » ouvert par un lien (?tab=stats) dans l'app : Méninges seul, aucun Purify Test.
    for store in (True, False):
        ctx, page = open_games(browser, server, store=store)
        page.evaluate("showTab('stats')")
        page.wait_for_selector('[data-view="stats"]:not(.hidden)')
        purify = page.locator('[data-stats-tab="purity"]')
        if store:
            assert purify.count() == 0
            assert page.locator("#purityStats").is_hidden() and page.locator("#brainStats").is_visible()
            assert "Purify" not in page.evaluate("document.querySelector('[data-view=stats]').innerText")
        else:
            assert purify.count() == 1 and page.locator("#purityStats").is_visible()
        ctx.close()
