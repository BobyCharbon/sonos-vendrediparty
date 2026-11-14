"""Pyramide, avis 4c55c231a4d2, dans un vrai navigateur : après la distribution, chacun voit SES 4 cartes au moins
30 secondes (les autres restent cachées), puis l'animateur lance la pyramide et toutes les mains se retournent.
Dans l'app iPhone (PartyNative.secret), la page ne dessine pas les cartes : elle les confie à l'app, qui les montre dans
un panneau qu'une capture d'écran rend noir ; le panneau part dès que la mémorisation est finie."""
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from tests.e2e.helpers import Phone, Server, tap_act, wait_state

# L'app iPhone ajoute PartyNative au chargement ; ici, un faux qui note ce que la page lui confie.
FAKE_APP = """window.PartyNative = { platform: "ios", secret: { update: function (s) {
  (window.__secret = window.__secret || []).push(s); } } };"""


@pytest.fixture
def server():
    s = Server()
    yield s
    s.stop()


def deal_everything(host: Phone, guest: Phone):
    """Les 4 tours de la distribution, chacun répondant « rouge / plus / dedans / pique » depuis son téléphone."""
    players = {host.pid(): host, guest.pid(): guest}
    while (s := host.state())["phase"] == "deal":
        step, turn = s["pyr"]["step"], s["pyr"]["turn"]
        answer = {1: "red", 2: "plus", 3: "dedans", 4: "S"}[step]
        players[turn].act("pans", target=answer)


def test_everyone_memorises_their_own_cards_then_the_host_starts_the_pyramid(browser, server):
    host, guest = Phone(browser, server, "Hote"), Phone(browser, server, "Lea")
    guest.ctx.add_init_script(FAKE_APP)  # Léa joue dans l'app iPhone
    try:
        code = host.create("pyramid")
        guest.join(code)
        tap_act(host, "start")
        wait_state(host, lambda s: s["phase"] == "deal")
        deal_everything(host, guest)
        wait_state(host, lambda s: s["phase"] == "look")

        # Navigateur : ses 4 cartes à lui, pas celles de Léa ; le bouton reste bloqué pendant 30 s.
        expect(host.page.locator(".py-look-cards .py-card:not(.back)")).to_have_count(4, timeout=8000)
        expect(host.page.locator(".py-look-time")).to_contain_text("pour mémoriser")
        expect(host.page.locator('[data-gact="plook"]')).to_be_disabled()
        mine = {s["name"]: s["cards"] for s in host.state()["pyr"]["seats"]}
        assert all(c != "??" for c in mine["Hote"]) and mine["Lea"] == ["??"] * 4
        host.shot("pyramide-memorisation")

        # App iPhone : rien sur la page, les cartes vont au panneau protégé de l'app.
        expect(guest.page.locator(".py-look-app")).to_contain_text("en bas de l'écran", timeout=8000)
        expect(guest.page.locator(".py-look-cards")).to_have_count(0)
        sent = guest.page.evaluate("window.__secret")
        theirs = next(s["cards"] for s in guest.state()["pyr"]["seats"] if s["name"] == "Lea")
        assert sent[-1]["cards"] == theirs and len(theirs) == 4

        # 30 s plus tard, l'animateur lance la pyramide : plus personne ne voit ses cartes, le panneau part.
        expect(host.page.locator('[data-gact="plook"]')).to_be_enabled(timeout=35000)
        expect(host.page.locator(".py-look-time")).to_contain_text("peut commencer")
        tap_act(host, "plook")
        wait_state(host, lambda s: s["phase"] == "pyramid")
        expect(guest.page.locator('[data-key="board"]')).to_be_visible(timeout=8000)
        guest.page.wait_for_function("window.__secret[window.__secret.length - 1] === null", timeout=8000)
        assert all(c == "??" for s in guest.state()["pyr"]["seats"] for c in s["cards"])
        assert not host.errors and not guest.errors, "\n".join(host.errors + guest.errors)
        assert not server.errors()
    finally:
        host.close()
        guest.close()
