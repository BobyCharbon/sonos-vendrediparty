"""Compagnon (Zicou) éteint, comme en production tant qu'il est en bêta (app/features.py) : aucune trace de Zicou dans
la page, ni dans la barre d'onglets web ni dans celle de l'app iOS ; ses liens retombent sur la musique ; « Ton avis »
reste une page des Réglages. Allumé (site de test) : voir test_native_tabs.py, test_zicou_home.py, test_pet_game.py."""
import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import Server
from tests.e2e.test_native_tabs import IPHONE, NATIVE_BRIDGE, as_guest_plus, last_state

TRACES = "document.querySelectorAll('[data-tab=pet], #petTab, #zicouChip, #zicouFloat, [data-pet-open], .g-pt, " \
         "script[src*=\"/static/pet/\"], link[href*=\"/static/pet/\"]').length"


@pytest.fixture(scope="module")
def server():
    s = Server(compagnon=False)
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def app(browser, server):
    ctx = browser.new_context(base_url=server.url, **IPHONE)
    ctx.add_init_script(NATIVE_BRIDGE)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("/")
    page.wait_for_function("window.__tabStates.length > 0")
    yield page
    ctx.close()
    assert not errors, errors


def visible_zicou_text(page) -> bool:
    return page.evaluate("/Zicou|Compagnon/.test(document.body.innerText)")


def test_native_tab_bar_has_no_zicou(app):
    as_guest_plus(app)
    state = last_state(app)
    # Production : ni Zicou, ni Discussions (même pour un compte connecté), Événements ouverts sans « Bientôt ».
    assert [t["id"] for t in state["tabs"]] == ["music", "games", "events", "account"]
    assert [t["label"] for t in state["tabs"]][:3] == ["Musique", "Jeux", "Événements"]
    assert not any(t["soon"] for t in state["tabs"])
    assert state["feedback"]["allowed"] is True   # « Ton avis » reste dans les Réglages
    assert app.evaluate(TRACES) == 0


def test_games_tab_has_no_companion_card_and_daily_keeps_only_brain(app):
    app.evaluate("PartyTabs.select('games')")
    app.wait_for_function("document.body.dataset.tab === 'games'")
    assert app.evaluate("[...document.querySelectorAll('.g-cat[data-cat=brain] .gcard')].map((c) => c.className)") \
        == ["gcard g-br"]
    assert app.evaluate(TRACES) == 0
    assert not visible_zicou_text(app)


@pytest.mark.parametrize("link", ["/?tab=pet", "/?tab=games&pet=1&src=notif", "/?pet=1"])
def test_companion_links_fall_back_to_music(app, link):
    app.goto(link)
    app.wait_for_function("document.body.dataset.tab")
    assert app.evaluate("document.body.dataset.tab") == "music"
    assert app.evaluate("document.getElementById('appTitle').textContent") == "Musique"


def test_a_remembered_zicou_tab_opens_events(app):
    """Ouverture : toujours l'onglet Événements (avis fb95d317cb64), jamais Zicou éteint."""
    app.evaluate("localStorage.setItem('vp_tab', 'pet')")
    app.reload()
    app.wait_for_function("document.body.dataset.tab")
    assert app.evaluate("document.body.dataset.tab") == "events"
    assert not visible_zicou_text(app)


def test_the_companion_api_is_closed(app):
    status = app.evaluate("fetch('/api/pet/status', {method: 'POST', headers: {'Content-Type': 'application/json'},"
                          " body: '{}'}).then((r) => r.status)")
    assert status == 404
    assert app.evaluate("fetch('/api/features').then((r) => r.json())") == {"compagnon": False, "discussions": False, "invites_v2": False, "bar": False}
