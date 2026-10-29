"""Navigation façon iOS (nav.js) : chaque écran poussé, feuille ou menu se referme de quatre façons —
‹ Retour, bouton retour d'Android / du navigateur, glisser depuis le bord gauche (écrans), tirer vers le bas
(feuilles) — et ne laisse jamais d'entrée d'historique en trop (sinon « retour » ne ferait plus rien)."""
import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.helpers import Phone, Server


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture(params=["iphone", "android"])
def phone(browser, server, request):
    p = Phone(browser, server, "Alice", request.param)
    yield p
    errors = p.errors
    p.close()
    assert not errors, "\n".join(errors)


def nav_depth(page) -> int:
    return page.evaluate("Nav.depth")


def settled(page, selector: str):
    """Le ressort est arrivé : plus aucune transformation en ligne sur la surface."""
    page.wait_for_function(f"!document.querySelector('{selector}')?.style.transform", timeout=3000)


def no_stale_history(page):
    page.wait_for_function("(history.state?.navDepth || 0) === 0", timeout=3000)


def open_stats(page):
    page.evaluate("showTab('stats')")
    expect(page.locator('[data-view="stats"]')).to_be_visible()
    settled(page, '[data-view="stats"]')
    assert nav_depth(page) == 1


def drag(page, x0, y0, x1, y1, steps=6):
    page.mouse.move(x0, y0)
    page.mouse.down()
    page.mouse.move(x1, y1, steps=steps)
    page.mouse.up()


def test_settings_page_closes_with_the_back_button_the_system_back_and_an_edge_swipe(phone):
    page = phone.page
    page.goto("/")
    # ‹ Réglages
    open_stats(page)
    page.locator('[data-view="stats"] [data-host-back]').click()
    expect(page.locator("body")).to_have_attribute("data-tab", "account")
    expect(page.locator('[data-view="stats"]')).to_be_hidden()
    assert nav_depth(page) == 0
    # Retour d'Android / du navigateur
    open_stats(page)
    page.go_back()
    expect(page.locator("body")).to_have_attribute("data-tab", "account")
    assert nav_depth(page) == 0
    # Glisser depuis le bord gauche : l'écran suit le doigt puis part à droite
    open_stats(page)
    drag(page, 4, 420, 300, 425)
    expect(page.locator("body")).to_have_attribute("data-tab", "account")
    assert nav_depth(page) == 0
    no_stale_history(page)


def test_a_tap_right_after_a_back_swipe_is_not_swallowed(phone):
    page = phone.page
    page.goto("/")
    open_stats(page)
    drag(page, 4, 420, 300, 425)
    page.locator('#tabs [data-tab="games"]').click()   # aussitôt, pendant le ressort
    expect(page.locator("body")).to_have_attribute("data-tab", "games")
    expect(page.locator(".events-panel")).to_be_hidden()
    no_stale_history(page)


def test_a_short_slow_edge_drag_springs_back_and_keeps_the_page(phone):
    page = phone.page
    page.goto("/")
    open_stats(page)
    page.mouse.move(4, 420)
    page.mouse.down()
    page.mouse.move(60, 420, steps=4)
    moved = page.evaluate("document.querySelector('[data-view=stats]').style.transform")
    assert "translate3d" in moved, "l'écran doit suivre le doigt pendant le glisser"
    page.wait_for_timeout(200)   # pause avant de lâcher : pas d'élan
    page.mouse.up()
    settled(page, '[data-view="stats"]')
    expect(page.locator("body")).to_have_attribute("data-tab", "stats")
    assert nav_depth(page) == 1


def test_a_vertical_scroll_near_the_edge_is_not_a_back_gesture(phone):
    page = phone.page
    page.goto("/")
    open_stats(page)
    drag(page, 6, 600, 12, 300)
    page.wait_for_timeout(300)
    expect(page.locator("body")).to_have_attribute("data-tab", "stats")


def test_switching_tab_from_a_settings_page_leaves_no_stale_history(phone):
    page = phone.page
    page.goto("/")
    open_stats(page)
    page.locator('#tabs [data-tab="games"]').click()
    expect(page.locator('[data-view="stats"]')).to_be_hidden()
    no_stale_history(page)
    assert nav_depth(page) == 0


def test_rules_sheet_closes_with_system_back_and_by_pulling_it_down(phone):
    phone.open_games()
    page = phone.page
    rules = page.locator("#rulesModal")
    page.locator("#gHome [data-rules]").first.click()
    expect(rules).to_be_visible()
    assert nav_depth(page) == 1
    page.go_back()
    expect(rules).to_be_hidden()
    assert nav_depth(page) == 0
    page.locator("#gHome [data-rules]").first.click()
    expect(rules).to_be_visible()
    page.wait_for_timeout(600)   # fin de l'apparition
    box = page.locator("#rulesModal .g-sheet").bounding_box()
    x = box["x"] + box["width"] / 2
    drag(page, x, box["y"] + 20, x, box["y"] + 420, steps=4)
    expect(rules).to_be_hidden()
    no_stale_history(page)
    # Rouverte ensuite : elle repart d'en haut, sans garder le décalage du geste
    page.locator("#gHome [data-rules]").first.click()
    expect(rules).to_be_visible()
    assert page.evaluate("document.querySelector('#rulesModal .g-sheet').style.transform") == ""


def test_game_back_closes_the_menu_then_minimizes_and_the_top_bar_pulls_down(phone):
    page = phone.page
    phone.create("undercover")
    page.wait_for_function("document.body.classList.contains('pyr-full')")
    assert nav_depth(page) == 1
    # Menu latéral, puis retour : seul le menu se ferme
    page.locator('#gTop [data-gdrawer="open"]').click()
    expect(page.locator("#gDrawer")).to_be_visible()
    assert nav_depth(page) == 2
    page.go_back()
    expect(page.locator("#gDrawer")).to_be_hidden()
    assert page.evaluate("document.body.classList.contains('pyr-full')")
    # Retour encore : le jeu se réduit dans la mini-barre (il n'est pas quitté)
    page.go_back()
    page.wait_for_function("!document.body.classList.contains('pyr-full')")
    expect(page.locator("#gMini")).to_be_visible()
    assert nav_depth(page) == 0
    # Reprendre, puis tirer la barre du haut vers le bas : réduit aussi
    page.locator("#gMini").click()
    page.wait_for_function("document.body.classList.contains('pyr-full')")
    page.wait_for_timeout(500)
    box = page.locator("#gTop .g-top-mid").bounding_box()
    drag(page, box["x"] + 10, box["y"] + 10, box["x"] + 10, box["y"] + 500, steps=4)
    page.wait_for_function("!document.body.classList.contains('pyr-full')")
    expect(page.locator("#gMini")).to_be_visible()
    no_stale_history(page)


def test_segmented_thumb_glides_under_the_chosen_option(phone):
    page = phone.page
    page.goto("/")
    page.evaluate("account = { name: 'Léa', feedback: true }; fbSyncAccess();")  # « Ton avis » : Guest+ et au-dessus
    page.locator('#tabs [data-tab="feedback"]').click()
    page.wait_for_function("document.querySelector('#fbForm .fb-kinds').classList.contains('seg-glide')")

    def thumb_under(kind):
        page.wait_for_function("""(kind) => {
            const t = document.querySelector('#fbForm .seg-thumb'), b = document.querySelector(`[data-fb-kind="${kind}"]`);
            const a = t.getBoundingClientRect(), c = b.getBoundingClientRect();
            return Math.abs(a.left - c.left) < 1 && Math.abs(a.width - c.width) < 1;
        }""", arg=kind, timeout=3000)

    thumb_under("idea")
    page.locator('[data-fb-kind="bug"]').click()
    page.locator('[data-fb-kind="other"]').click()   # redirigée en plein vol
    thumb_under("other")
    expect(page.locator('[data-fb-kind="other"]')).to_have_attribute("aria-checked", "true")
