"""Méninges dans Réglages → « Mes stats de jeu » (vrai navigateur, iPhone). Les réponses de /api/brain/me, /compare et
/local sont simulées (page.route) : profil complet (Température, domaines, courbe, jeux, classement avec ta ligne en
évidence), profil vide (invitation à l'Échauffement, qui ouvre Méninges), joueur non connecté (stats calculées à partir
des parties du téléphone), nom de joueur piégé échappé, erreur réseau puis « Réessayer »."""
import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import FakeSupabase, Phone, Server, sign_in  # noqa: E402

TOKEN = "jeton-de-test-guest-0001"
GAMES = ("pareil", "motif", "autoroute", "grille", "deux_avant", "tresor", "nuee", "aiguillage",
         "intrus", "encre", "bascule", "courant", "balance", "gouttes", "syllabes")
DOMAINS = ("vitesse", "memoire", "attention", "flexibilite", "logique", "calcul")
TRAP = '<img src=x onerror="window.__pwned=1">'


def profile(plays: bool = True) -> dict:
    games = {g: {"index": 0, "best": 0, "plays": 0, "last_level": 0} for g in GAMES}
    if plays:
        games["pareil"] = {"index": 1310, "best": 12450, "plays": 7, "last_level": 6}
        games["grille"] = {"index": 980, "best": 5400, "plays": 2, "last_level": 4}
    return {
        "name": "Méninges",
        "temperature": 1240 if plays else 0,
        "domains": {d: {"index": (1310 if d == "vitesse" else 980 if d == "memoire" else 0) if plays else 0,
                        "played": (7 if d == "vitesse" else 2 if d == "memoire" else 0) if plays else 0} for d in DOMAINS},
        "games": games,
        "streak": {"current": 3, "best": 5} if plays else {"current": 0, "best": 0},
        "history": [{"day": f"2026-10-{d:02d}", "temperature": 900 + d * 15} for d in range(20, 32)] if plays else [],
        "strengths": ["vitesse"] if plays else [],
        "weaknesses": ["memoire"] if plays else [],
        "insight": "Ta force : Vitesse (1 310 °M). À travailler : Mémoire (980 °M) — l'Échauffement en propose chaque jour."
        if plays else "Lance ton premier Échauffement pour mesurer ta Température.",
        "percentile": 72 if plays else None,
        "speed_vs_accuracy": {"speed": 80, "accuracy": 55} if plays else {"speed": 0, "accuracy": 0},
        "month_progress": 120 if plays else None,
    }


BOARD = {"board": [{"id": "u-1", "name": "Léa", "temperature": 1500, "me": False},
                   {"id": "u-guest", "name": "Tom", "temperature": 1240, "me": True},
                   {"id": "u-3", "name": TRAP, "temperature": 800, "me": False}],
         "rank": 2, "players": 3, "percentile": 72, "target": None}


@pytest.fixture(scope="module")
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


@pytest.fixture
def phone(browser, server):
    p = Phone(browser, server, "Tom")
    yield p
    errors, server_errors = p.errors, server.errors()
    p.close()
    assert not server_errors, server_errors[-3000:]
    assert not errors, "\n".join(errors)


def mock(page, me: dict | None = None, board: dict | None = None, local: dict | None = None, calls: list | None = None):
    def answer(data):
        def handler(route):
            if calls is not None:
                calls.append((route.request.url, route.request.post_data))
            if data is None:
                return route.abort()
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
        return handler
    page.route("**/api/brain/me", answer(me))
    page.route("**/api/brain/compare", answer(board))
    page.route("**/api/brain/local", answer(local))


def open_brain_stats(phone):
    page = phone.page
    page.evaluate("postMessage({type: 'party-events:open-tab', tab: 'stats'}, location.origin)")
    expect(page.locator("#appTitle")).to_have_text("Mes stats de jeu")
    tab = page.locator('[data-stats-tab="brain"]')
    expect(tab).to_contain_text("Méninges")
    tab.click()
    expect(tab).to_have_attribute("aria-selected", "true")
    expect(page.locator("#purityStats")).to_be_hidden()
    return page.locator("#brainStats")


def signed_in(phone):
    phone.page.goto("/")
    sign_in(phone, TOKEN)
    phone.page.wait_for_function("account && account.name === 'Tom'")


def test_full_profile_shows_temperature_domains_curve_games_and_ranking(phone):
    mock(phone.page, me=profile(), board=BOARD)
    signed_in(phone)
    stats = open_brain_stats(phone)

    expect(stats.locator(".brs-temp b")).to_have_text(phone.page.evaluate("(1240).toLocaleString('fr-CH')"))
    expect(stats.locator(".brs-temp")).to_contain_text("°M")
    expect(stats.locator(".brs-pct")).to_contain_text("Tu fais mieux que 72 % des joueurs Party")
    expect(stats.locator(".brs-hero")).to_contain_text("+120 °M en un mois")
    expect(stats.locator(".brs-hero")).to_contain_text("3 jours d'affilée")
    expect(stats.locator(".brs-hero")).to_contain_text("Meilleure série : 5 jours")
    expect(stats.locator(".brs-login")).to_have_count(0)

    expect(stats.locator(".brs-dom")).to_have_count(6)
    expect(stats.locator(".brs-radar .brs-dot")).to_have_count(5)
    expect(stats.locator(".brs-insight")).to_contain_text("Ta force : Vitesse")
    expect(stats.locator(".brs-sw.up")).to_contain_text("Vitesse")
    expect(stats.locator(".brs-sw.down")).to_contain_text("Mémoire")
    assert stats.locator(".brs-chart .brs-line").get_attribute("d").count("L") == 11
    expect(stats.locator("#brsSaH + .brs-sa.speed")).to_contain_text("80 %")
    expect(stats).to_contain_text("ta vitesse prend le pas sur ta précision")

    games = stats.locator(".brs-game")
    expect(games).to_have_count(15)
    pareil = games.filter(has_text="Pareil ?")
    expect(pareil).to_contain_text("niveau 6")
    expect(pareil).to_contain_text("7 parties")
    expect(pareil.locator(".brs-game-i")).to_have_text("⚡")
    expect(stats.locator(".brs-game.off")).to_have_count(13)

    board = stats.locator(".brs-board li")
    expect(board).to_have_count(3)
    me = stats.locator(".brs-board li.me")
    expect(me).to_have_count(1)
    expect(me).to_contain_text("Tom")
    expect(me).to_contain_text("(toi)")
    expect(me).to_have_attribute("aria-current", "true")
    expect(stats).to_contain_text("Tu es 2e sur 3 joueurs")
    assert "QI" not in stats.inner_text()
    assert phone.page.evaluate("getComputedStyle(document.body).overflowY") != "hidden"
    phone.shot("brain_stats_full")


def test_trapped_player_name_is_escaped_in_the_ranking(phone):
    mock(phone.page, me=profile(), board=BOARD)
    signed_in(phone)
    stats = open_brain_stats(phone)
    expect(stats.locator(".brs-board li").nth(2)).to_contain_text(TRAP)
    expect(stats.locator("img")).to_have_count(0)
    phone.page.wait_for_timeout(300)
    assert phone.page.evaluate("window.__pwned") is None


def test_empty_profile_invites_to_the_warmup_and_opens_brain(phone):
    mock(phone.page, me=profile(plays=False), board={"board": [], "rank": None, "players": 0, "percentile": None, "target": None},
         local=profile(plays=False))
    signed_in(phone)
    stats = open_brain_stats(phone)
    empty = stats.locator(".brs-empty")
    expect(empty).to_contain_text("Tes méninges sont encore froides")
    expect(stats.locator(".brs-hero")).to_have_count(0)
    empty.locator('[data-brs="open"]').click()
    expect(phone.page.locator("#brainRoot .br-home")).to_be_visible(timeout=15000)


def test_signed_out_player_sees_local_stats_and_an_invitation_to_sign_in(phone):
    calls: list = []
    mock(phone.page, me=None, board=None, local=profile(), calls=calls)
    phone.page.goto("/")
    session = {"game": "pareil", "score": 12450, "accuracy": 0.9, "avg_rt_ms": 700, "level": 6, "duration_ms": 45000,
               "played_at": "2026-11-01T10:00:00Z"}
    phone.page.evaluate(f"localStorage.setItem('brain_local', {json.dumps(json.dumps([session]))})")
    stats = open_brain_stats(phone)

    expect(stats.locator(".brs-login")).to_contain_text("Connecte-toi pour garder tes stats")
    expect(stats.locator(".brs-temp b")).to_have_text(phone.page.evaluate("(1240).toLocaleString('fr-CH')"))
    expect(stats).to_contain_text("Connecte-toi pour te comparer aux autres membres")
    expect(stats.locator(".brs-board")).to_have_count(0)
    assert [u for u, _ in calls if u.endswith("/api/brain/local")], calls
    assert not [u for u, _ in calls if u.endswith(("/api/brain/me", "/api/brain/compare"))], calls
    sent = json.loads(next(body for u, body in calls if u.endswith("/api/brain/local")))
    assert sent["sessions"][0]["game"] == "pareil"
    stats.locator('[data-brs="login"]').click()
    expect(phone.page.locator("body")).to_have_attribute("data-tab", "account")


def test_network_error_then_retry(phone):
    state = {"fail": True}

    def me(route):
        if state["fail"]:
            return route.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "Base indisponible"}))
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(profile()))
    phone.page.route("**/api/brain/me", me)
    phone.page.route("**/api/brain/compare", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(BOARD)))
    signed_in(phone)
    stats = open_brain_stats(phone)
    expect(stats.locator(".brs-error")).to_contain_text("Impossible de charger tes stats : Base indisponible")
    state["fail"] = False
    stats.locator('[data-brs="retry"]').click()
    expect(stats.locator(".brs-temp b")).to_be_visible()
