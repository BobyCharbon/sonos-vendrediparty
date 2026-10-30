"""App iOS native (ios/) : la barre d'onglets est une vraie UITabBar. La page reste la référence de son contenu :
elle masque sa propre barre et décrit ses onglets (libellés, onglet actif, badges, plein écran) à l'app, qui lui
renvoie les touchers via PartyTabs.select().

On simule le pont natif (window.PartyNative.tabs, injecté par NativeBridge.swift avant les scripts de la page)."""
import pytest
pytest.importorskip("playwright.sync_api")

from tests.e2e.helpers import Server

IPHONE = {"viewport": {"width": 390, "height": 760}, "screen": {"width": 390, "height": 844},
          "user_agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 "
                         "(KHTML, like Gecko) Mobile/15E148 PartyApp-iOS/1.0.0"),
          "is_mobile": True, "has_touch": True, "device_scale_factor": 3, "locale": "fr-CH"}
NATIVE_BRIDGE = """
Object.defineProperty(navigator, "standalone", { get: () => true, configurable: true });
window.__tabStates = [];
window.PartyNative = { platform: "ios", tabs: { update: (s) => window.__tabStates.push(JSON.parse(JSON.stringify(s))) } };
localStorage.setItem("vp_install_dismissed", "1"); localStorage.setItem("vp_name", "Léa");
"""


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def app(browser, server):
    ctx = browser.new_context(base_url=server.url, **IPHONE)
    ctx.add_init_script(NATIVE_BRIDGE)
    page = ctx.new_page()
    page.goto("/")
    page.wait_for_function("window.__tabStates.length > 0")
    yield page
    ctx.close()


def last_state(page):
    page.wait_for_timeout(150)  # les changements sont regroupés à l'image suivante
    return page.evaluate("window.__tabStates[window.__tabStates.length - 1]")


def active(state):
    return [t["id"] for t in state["tabs"] if t["active"]]


def as_guest_plus(page):
    """Compte Guest+ (droit « Écrire un avis ») : l'onglet « Ton avis » s'affiche (le droit lui-même est vérifié
    par le serveur, voir test_feedback_tab.py)."""
    page.evaluate("account = { name: 'Léa', feedback: true }; fbSyncAccess(); chatsSyncAccess();")


def test_page_hides_its_own_tab_bar_and_describes_the_tabs(app):
    state = last_state(app)
    # Non connecté : pas de « Ton avis » (réservé à Guest+ et au-dessus).
    assert [t["id"] for t in state["tabs"]] == ["music", "games", "events", "account"]
    as_guest_plus(app)
    state = last_state(app)
    assert [t["id"] for t in state["tabs"]] == ["music", "games", "events", "chats", "feedback", "account"]
    assert [t["label"] for t in state["tabs"]][3] == "Discussions"
    assert [t["label"] for t in state["tabs"]][:2] == ["Musique", "Jeux"]
    assert active(state) == ["music"] and state["hidden"] is False
    assert app.evaluate("document.documentElement.classList.contains('native-tabs')")
    assert app.evaluate("document.getElementById('tabs').getBoundingClientRect().height") == 0
    # Le bas de page n'est plus réservé à la barre web : la barre native est sous la vue web, pas par-dessus.
    assert app.evaluate("parseFloat(getComputedStyle(document.body).paddingBottom)") <= 32


def test_native_selection_switches_the_tab_like_a_touch(app):
    app.evaluate("PartyTabs.select('games')")
    app.wait_for_function("document.body.dataset.tab === 'games'")
    assert active(last_state(app)) == ["games"]
    as_guest_plus(app)
    app.evaluate("PartyTabs.select('feedback')")
    app.wait_for_function("document.body.dataset.tab === 'feedback'")
    assert active(last_state(app)) == ["feedback"]


def test_badges_follow_the_page(app):
    as_guest_plus(app)
    app.evaluate("document.getElementById('gameDot').classList.remove('hidden')")
    games = next(t for t in last_state(app)["tabs"] if t["id"] == "games")
    assert games["badge"] == ""  # un point (« ● ») : badge sans texte
    app.evaluate("const b = document.getElementById('fbTabBadge'); b.textContent = '3'; b.classList.remove('hidden')")
    feedback = next(t for t in last_state(app)["tabs"] if t["id"] == "feedback")
    assert feedback["badge"] == "3"
    app.evaluate("document.getElementById('gameDot').classList.add('hidden')")
    games = next(t for t in last_state(app)["tabs"] if t["id"] == "games")
    assert games["badge"] is None


def test_full_screen_game_hides_the_native_tab_bar(app):
    app.evaluate("document.body.classList.add('pyr-full')")
    assert last_state(app)["hidden"] is True
    app.evaluate("document.body.classList.remove('pyr-full')")
    assert last_state(app)["hidden"] is False


def test_events_coming_soon_is_reported(app):
    app.evaluate("document.documentElement.classList.add('events-soon')")
    events = next(t for t in last_state(app)["tabs"] if t["id"] == "events")
    assert events["soon"] is True


def test_native_shell_skips_the_home_screen_height_fix(app):
    # Le correctif « app installée » (ios-app.js) agrandit la page à la hauteur de l'écran physique ; dans l'app
    # native la vue web s'arrête au-dessus de la barre d'onglets : la page ne doit pas défiler pour rien.
    assert not app.evaluate("document.documentElement.classList.contains('ios-app')")


def test_without_the_native_bridge_nothing_changes(browser, server):
    ctx = browser.new_context(base_url=server.url, **IPHONE)
    page = ctx.new_page()
    page.goto("/")
    assert page.locator("#tabs").is_visible()
    assert not page.evaluate("document.documentElement.classList.contains('native-tabs')")
    assert page.evaluate("typeof window.PartyTabs") == "undefined"
    ctx.close()


def test_music_is_native_for_everyone_and_the_host_keeps_his_tools(app):
    # L'onglet Musique est natif pour tous ; l'app propose à l'hôte « Gérer la soirée » (page web et ses réglages).
    assert last_state(app)["native"] == ["music", "feedback", "chats", "account"] and last_state(app)["host"] is False
    # L'hôte : compte admin et session admin ouverte (fbIsAdmin) ; le libellé « Retours » relance la description.
    app.evaluate("() => { account = { ...(account || {}), admin: true }; adminSession = true;"
                 "        document.querySelector('#tabs [data-tab=feedback] span').textContent = 'Retours'; }")
    state = last_state(app)
    assert state["native"] == ["music", "feedback", "chats", "account"] and state["host"] is True


@pytest.mark.parametrize("store", [True, False])
def test_store_app_hides_simulated_gambling_games(browser, server, store):
    """App de l'App Store (« PartyStore » dans l'User-Agent) : ni Casino ni Blackjack. BETA : tous les jeux."""
    ua = IPHONE["user_agent"] + (" PartyStore" if store else "")
    ctx = browser.new_context(base_url=server.url, **{**IPHONE, "user_agent": ua})
    ctx.add_init_script(NATIVE_BRIDGE)
    page = ctx.new_page()
    page.goto("/")
    page.wait_for_function("window.__tabStates.length > 0")
    page.evaluate("PartyTabs.select('games')")
    page.wait_for_selector('[data-create="whoof"]', state="visible")
    for kind in ("casino", "blackjack"):
        assert page.locator(f'[data-create="{kind}"]').is_visible() is not store
    ctx.close()


def test_discussions_tab_opens_the_group_chats_of_the_events_module(app):
    # Avis n°10 : 6e onglet « Discussions », réservé aux comptes connectés ; il ouvre /chats dans le même module.
    assert "chats" not in [t["id"] for t in last_state(app)["tabs"]]
    as_guest_plus(app)
    app.evaluate("PartyTabs.select('chats')")
    app.wait_for_function("document.body.dataset.tab === 'chats'")
    assert active(last_state(app)) == ["chats"]
    assert app.evaluate("document.getElementById('appTitle').textContent") == "Discussions"
    assert app.evaluate("document.getElementById('eventsFrame').getAttribute('src')") == "/events/chats"
    assert app.evaluate("!document.querySelector('.events-panel').classList.contains('hidden')")
    # Retour aux Événements : la liste des événements, pas la discussion.
    app.evaluate("PartyTabs.select('events')")
    app.wait_for_function("document.body.dataset.tab === 'events'")
    assert app.evaluate("frameAt") == "/"
    # Déconnexion : l'onglet disparaît.
    app.evaluate("account = null; chatsSyncAccess();")
    assert "chats" not in [t["id"] for t in last_state(app)["tabs"]]


def test_discussions_badge_counts_unread_messages_of_all_groups(app):
    # La page lit /api/account/chats (relais de my_chats) et additionne les non-lus ; la barre native la reprend.
    app.route("**/api/account/chats", lambda route: route.fulfill(json={"chats": [{"id": "a", "unread": 2}, {"id": "b", "unread": 3}]}))
    app.evaluate("""account = { name: 'Léa' }; supabaseToken = () => 'jeton'; freshToken = async () => 'jeton';
                    chatsSyncAccess(); refreshChatsBadge();""")
    app.wait_for_function("!document.getElementById('chatsBadge').classList.contains('hidden')")
    chats = next(t for t in last_state(app)["tabs"] if t["id"] == "chats")
    assert chats["badge"] == "5"
