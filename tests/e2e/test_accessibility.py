"""Accessibilité (WCAG 2.2 AA) des pages Party, réglages de la production (Zicou et Discussions éteints) :
- axe-core (tests/e2e/vendor/axe.min.js, v4.10.2, licence MPL-2.0) : aucune violation « sérieuse » ou « critique » ;
- au clavier, chaque élément atteint par Tab montre où est le focus (halo ou contour).

Seule exception : `meta-viewport` (zoom interdit). C'est un choix de l'app (« l'app doit se sentir native »,
tests/test_ios_app.py) ; la taille du texte suit les réglages du téléphone (Dynamic Type dans l'app iOS).
Module Événements (Expo web) : tests/supabase_live/test_accessibility_events_live.py (base de test)."""
from pathlib import Path

import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import DEVICES, Server

AXE = (Path(__file__).parent / "vendor/axe.min.js").read_text(encoding="utf-8")
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
ACCEPTED = {"meta-viewport"}


def serious_violations(page) -> list:
    page.add_script_tag(content=AXE)
    found = page.evaluate("""async (tags) => (await axe.run(document, {runOnly: {type: 'tag', values: tags}})).violations
        .filter((v) => v.impact === 'serious' || v.impact === 'critical')
        .map((v) => ({id: v.id, nodes: v.nodes.slice(0, 3).map((n) => n.html.slice(0, 120) + ' → ' + n.failureSummary.slice(0, 160))}))""", TAGS)
    return [v for v in found if v["id"] not in ACCEPTED]


FOCUS_SHOWN = """() => { const e = document.activeElement;
  if (!e || e === document.body) return null;
  const cs = getComputedStyle(e);
  return {name: (e.getAttribute('aria-label') || e.innerText || e.id || e.tagName).trim().slice(0, 40),
          shown: (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none'} }"""


def unmarked_focus(page, presses: int) -> list:
    page.mouse.click(1, 1)
    missing = []
    for _ in range(presses):
        page.keyboard.press("Tab")
        page.wait_for_timeout(250)  # fin de la transition du halo
        focus = page.evaluate(FOCUS_SHOWN)
        if focus and not focus["shown"]:
            missing.append(focus["name"])
    return missing


@pytest.fixture(scope="module")
def server():
    s = Server(compagnon=False)
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(base_url=server.url, locale="fr-CH", color_scheme="dark", **DEVICES["iphone"])
    page = ctx.new_page()
    yield page
    ctx.close()


@pytest.mark.parametrize("tab", ["music", "games", "events", "account"])
def test_party_tabs_have_no_serious_axe_violation(page, tab):
    page.goto("/")
    page.wait_for_function("typeof showTab === 'function'")
    page.evaluate(f"showTab('{tab}')")
    page.wait_for_timeout(800)
    assert page.evaluate("document.documentElement.lang") == "fr" and page.title() == "Vendredi Party"
    assert serious_violations(page) == []


@pytest.mark.parametrize("path, title", [("/admin", "Party Admin"), ("/tv", "Party TV")])
def test_admin_and_tv_have_no_serious_axe_violation(page, path, title):
    page.goto(path)
    page.wait_for_timeout(800)
    assert page.evaluate("document.documentElement.lang") == "fr" and page.title() == title
    assert serious_violations(page) == []


def test_keyboard_focus_is_always_visible(browser, server):
    """Les boutons de la barre d'onglets n'avaient aucun halo de focus (box-shadow: none l'écrasait)."""
    ctx = browser.new_context(base_url=server.url, locale="fr-CH", **DEVICES["desktop"])
    page = ctx.new_page()
    try:
        page.goto("/")
        page.wait_for_function("typeof showTab === 'function'")
        page.evaluate("showTab('music')")
        assert unmarked_focus(page, 8) == []
        page.evaluate("showTab('games')")
        page.wait_for_timeout(500)
        assert unmarked_focus(page, 12) == []
        page.goto("/admin")
        assert unmarked_focus(page, 4) == []
    finally:
        ctx.close()
