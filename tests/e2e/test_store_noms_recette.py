"""Recette simulateur du 28.11 (décision Q1 choix b, prénoms de la liste) : ce que l'iPhone a montré.
1. La case des 18 ans / CGU des jeux reste visible au-dessus de la barre d'onglets (native et web) quand on touche un
   prénom sans l'avoir cochée, écran 390×844.
2. ☰ › Participants : avec ⬆ ⬇ 🚩 ✕, « Joueur N » n'est jamais coupé (le numéro se voit).
5. La pastille du prénom (en haut à droite) dit le prénom de la TABLE (« Joueur N » si le prénom choisi était pris) ;
   le sélecteur rouvert a « Annuler »."""
import httpx
import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import IGNORED_CONSOLE, Server, show_game_cards

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "PartyApp-iOS/1.0.0 PartyStore")
IPHONE = {"viewport": {"width": 390, "height": 844}, "screen": {"width": 390, "height": 844}, "is_mobile": True,
          "has_touch": True, "device_scale_factor": 3, "locale": "fr-CH"}
NATIVE_TAB_TOP = 765  # UITabBar de l'iPhone 390×844 (recette du 28.11) : la vue web passe dessous
NATIVE_BRIDGE = """
Object.defineProperty(navigator, "standalone", { get: () => true, configurable: true });
window.PartyNative = { platform: "ios", tabs: { update: () => {} } };
"""


@pytest.fixture(scope="module")
def server():
    s = Server(compagnon=False)
    yield s
    s.stop()


def phone(browser, server, init="", native=False):
    ctx = browser.new_context(base_url=server.url, user_agent=UA, **IPHONE)
    ctx.add_init_script((NATIVE_BRIDGE if native else "") + 'localStorage.setItem("vp_install_dismissed", "1");' + init)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not any(x in m.text for x in IGNORED_CONSOLE) and page.errors.append(m.text))
    page.on("dialog", lambda d: d.accept())
    page.goto("/")
    page.evaluate("showTab('games')")
    return ctx, page


@pytest.mark.parametrize("native", [True, False], ids=["barre-native", "barre-web"])
def test_the_terms_box_shows_above_the_tab_bar_when_a_name_is_touched_first(browser, server, native):
    ctx, page = phone(browser, server, native=native)
    page.wait_for_selector('#gName:not(.hidden) [data-pick-name="Zoé"]')
    if native:
        assert page.evaluate("document.documentElement.classList.contains('native-tabs')")
    page.locator('#gName [data-pick-name="Zoé"]').scroll_into_view_if_needed()
    page.click('#gName [data-pick-name="Zoé"]')
    page.wait_for_function("document.getElementById('gTermsBox').classList.contains('warn')")
    page.wait_for_timeout(700)  # défilement doux
    bar = NATIVE_TAB_TOP if native else page.evaluate("document.getElementById('tabs').getBoundingClientRect().top")
    for sel in ("#gTermsBox", "#gTermsNote"):
        r = page.evaluate(f"(() => {{ const r = document.querySelector('{sel}').getBoundingClientRect(); return [r.top, r.bottom]; }})()")
        assert r[0] >= 0 and r[1] <= bar, (sel, r, bar)
    assert "coche d'abord la case" in page.inner_text("#gTermsNote")
    # L'ordre se lit : la case vient avant la liste des prénoms.
    assert page.evaluate("!!(document.getElementById('gTermsBox').compareDocumentPosition(document.querySelector('#gName [data-name-pick]')) & Node.DOCUMENT_POSITION_FOLLOWING)")
    assert page.errors == [], page.errors
    ctx.close()


def test_joueur_n_is_never_cut_in_the_participants_menu(browser, server):
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Léa"); localStorage.setItem("vp_games_terms", "1");')
    page.wait_for_selector("#gHome:not(.hidden)")
    show_game_cards(page)
    page.click('#gHome [data-create="likely"]')
    page.wait_for_function("game && game.type === 'likely'")
    code = page.evaluate("myGame")
    for i in range(12):  # jusqu'à « Joueur 12 » : le numéro le plus large
        r = httpx.post(f"{server.url}/api/games/{code}", headers={"User-Agent": UA},
                       json={"guest_id": f"e2e-cut-{i:04d}", "name": "Joueur", "action": "join", "terms": True})
        assert r.status_code == 200, r.text
    page.evaluate("refreshGame()")
    page.wait_for_function("game.players.some((p) => p.name === 'Joueur 12')")
    # Texte agrandi comme le fait l'app (ios/Party/TextScale.swift, Taille du texte d'iOS) : la police de l'iPhone est
    # plus large que celle de Chromium, « Joueur 1… » s'y voyait déjà coupé à la taille normale (recette du 28.11).
    page.add_style_tag(content="html { -webkit-text-size-adjust: 125% !important; text-size-adjust: 125% !important; }")
    page.evaluate("openDrawer()")
    page.wait_for_selector('#gDrawerPlayers [data-gact="remove"]', state="visible")
    page.wait_for_timeout(400)
    cut = page.evaluate("""() => [...document.querySelectorAll('#gDrawerPlayers .track')].map((row) => {
        const title = row.querySelector('.title'), name = game.players.map((p) => p.name).filter((n) => title.textContent.includes(n)).sort((a, b) => b.length - a.length)[0];
        if (!name) return null;
        const walker = document.createTreeWalker(title, NodeFilter.SHOW_TEXT);
        let node; while ((node = walker.nextNode()) && !node.data.includes(name));
        const range = document.createRange(), at = node.data.indexOf(name);
        range.setStart(node, at); range.setEnd(node, at + name.length);
        const r = range.getBoundingClientRect(), box = title.getBoundingClientRect(), btns = row.querySelector('.icon-btns').getBoundingClientRect();
        const clipped = r.right > box.right + 1 || r.bottom > box.bottom + 1 || (r.right > btns.left + 1 && r.bottom > btns.top + 1 && r.top < btns.bottom - 1);
        return clipped ? name : null;
      }).filter(Boolean)""")
    assert cut == [], cut
    assert page.locator('#gDrawerPlayers [data-gact="up"]').count() >= 10  # les 4 boutons sont bien là
    assert page.errors == [], page.errors
    ctx.close()


def test_the_name_chip_says_the_name_of_the_table_and_the_picker_has_cancel(browser, server):
    ctx, page = phone(browser, server, init='localStorage.setItem("vp_name", "Léa"); localStorage.setItem("vp_games_terms", "1");')
    page.wait_for_selector("#gHome:not(.hidden)")
    show_game_cards(page)
    page.click('#gHome [data-create="likely"]')
    page.wait_for_function("game && game.type === 'likely'")
    code = page.evaluate("myGame")
    r = httpx.post(f"{server.url}/api/games/{code}", headers={"User-Agent": UA},
                   json={"guest_id": "e2e-chip-tom1", "name": "Tom", "action": "join", "terms": True})
    assert r.status_code == 200, r.text
    # Sélecteur rouvert : « Annuler » le referme sans rien changer.
    page.evaluate("changeName()")
    page.wait_for_selector('#gName:not(.hidden) [data-gname-cancel]')
    page.click('[data-gname-cancel]')
    page.wait_for_selector("#gName", state="hidden")
    assert page.evaluate("guestName") == "Léa"
    # Tom est déjà pris à cette table : elle y devient « Joueur N », et la pastille le dit.
    page.evaluate("changeName()")
    page.wait_for_selector('#gName:not(.hidden) [data-pick-name="Tom"]')
    page.click('#gName [data-pick-name="Tom"]')
    page.wait_for_function("game && game.me && /^Joueur \\d+$/.test(game.players.find((p) => p.pid === game.me.pid).name)")
    seat = page.evaluate("game.players.find((p) => p.pid === game.me.pid).name")
    page.wait_for_function("(s) => document.getElementById('nameChip').textContent.includes(s)", arg=seat)
    assert "Tom" not in page.text_content("#nameChip")
    assert page.errors == [], page.errors
    ctx.close()
