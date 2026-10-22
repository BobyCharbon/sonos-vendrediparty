"""Barre d'onglets sur iPhone, app installée (bug iOS 26) : au lancement, iOS croit l'écran plus court (≈ 80 px)
et pose la barre d'onglets trop haut, avec une bande vide dessous, tant que la page n'est pas plus haute que
l'écran PHYSIQUE. Seul Jeux (page longue) la recalait. Les unités CSS (100vh, 100lvh…) suivent la hauteur erronée :
seule screen.height donne la vraie hauteur.

On reproduit cet état (écran 844 px, viewport 765 px, navigator.standalone) et on vérifie, sur CHAQUE onglet
trouvé dans la barre (les onglets futurs sont donc couverts d'office), que la page dépasse l'écran physique."""
import re

import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.helpers import ADMIN_PIN, Server

SCREEN = {"width": 390, "height": 844}       # iPhone : hauteur physique (screen.height)
BUGGY_VIEWPORT = {"width": 390, "height": 765}  # ce qu'iOS croit au lancement (bande vide de 79 px)
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")
STANDALONE = "Object.defineProperty(Navigator.prototype, 'standalone', { get: () => true });"


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


def ios_app(browser, server, standalone=True):
    ctx = browser.new_context(base_url=server.url, viewport=BUGGY_VIEWPORT, screen=SCREEN, user_agent=IPHONE_UA,
                              is_mobile=True, has_touch=True, device_scale_factor=3, locale="fr-CH")
    if standalone:
        ctx.add_init_script(STANDALONE)
    ctx.add_init_script("localStorage.setItem('vp_install_dismissed', '1'); localStorage.setItem('vp_name', 'Test');")
    return ctx


def page_height(page) -> dict:
    return page.evaluate("""() => ({ scroll: document.documentElement.scrollHeight, screen: screen.height,
                                      inner: innerHeight })""")


def check_every_tab(page):
    tabs = page.locator("#tabs button[data-tab]:visible")
    names = [tabs.nth(i).get_attribute("data-tab") for i in range(tabs.count())]
    assert len(names) >= 3, names
    for name in names:
        page.locator(f'#tabs button[data-tab="{name}"]').click()
        page.wait_for_timeout(250)
        h = page_height(page)
        # Plus haute que l'écran physique : c'est ce qui fait recaler la barre à iOS (comme sur Jeux).
        assert h["scroll"] > h["screen"], f"onglet {name} : page {h['scroll']} px ≤ écran {h['screen']} px"
        # La barre reste collée au bas de la zone visible.
        bottom = page.evaluate("document.getElementById('tabs').getBoundingClientRect().bottom")
        assert abs(bottom - h["inner"]) <= 1, f"onglet {name} : barre à {bottom}, bas de l'écran à {h['inner']}"
    return names


def test_installed_app_every_tab_exceeds_the_physical_screen(browser, server):
    ctx = ios_app(browser, server)
    page = ctx.new_page()
    page.goto("/")
    expect(page.locator("#tabs")).to_be_visible()
    names = check_every_tab(page)
    assert {"music", "games"} <= set(names)
    # Au lancement direct sur un onglet court (comme à l'ouverture de l'app), sans passer par Jeux.
    for name in ("music", "events", "account"):
        page.evaluate(f"localStorage.setItem('vp_tab', '{name}')")
        page.reload()
        page.wait_for_timeout(300)
        h = page_height(page)
        assert h["scroll"] > h["screen"], f"lancement sur {name} : page {h['scroll']} px ≤ écran {h['screen']} px"
    ctx.close()


def test_installed_admin_app_every_tab_exceeds_the_physical_screen(browser, server):
    ctx = ios_app(browser, server)
    page = ctx.new_page()
    page.goto("/admin")
    page.locator("input[type=password], #pin").first.fill(ADMIN_PIN)
    page.keyboard.press("Enter")
    expect(page.locator("#tabs")).to_be_visible()
    check_every_tab(page)
    ctx.close()


def test_regular_browser_keeps_short_pages_short(browser, server):
    """Hors app installée : pas de grand espace vide à faire défiler sous une page courte."""
    ctx = ios_app(browser, server, standalone=False)
    page = ctx.new_page()
    page.goto("/")
    page.locator('#tabs button[data-tab="music"]').click()
    page.wait_for_timeout(250)
    h = page_height(page)
    assert h["scroll"] - h["inner"] <= 2, h
    ctx.close()


def test_css_never_locks_page_scrolling_per_tab():
    """Règle anti-régression : aucun onglet ne bloque le défilement de html / body (ça aggrave le bug)."""
    from pathlib import Path
    css = (Path(__file__).resolve().parents[2] / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert not re.search(r"(html|body)[^{]*data-tab[^{]*\{[^}]*(overflow:\s*hidden|height:\s*100d?vh)", css)
