"""Accueil des jeux : régler une option ne ramène pas en haut de page ; les onglets changent toujours de vue."""
import pytest

pytest.importorskip("playwright.sync_api")
from tests.e2e.helpers import Phone, Server  # noqa: E402


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, "Ludo")
    yield p
    errors = p.errors
    p.close()
    server.stop()
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("kind, option", [("undercover", '[data-opt-group="impostors"] [data-val="2"]'),
                                          ("pyramid", '[data-opt-group="pmode"] [data-val="hard"]'),
                                          ("whoof", '[data-opt-group="mode"] [data-val="hot"]')])
def test_choosing_an_option_keeps_the_scroll_position(phone, kind, option):
    phone.open_games()
    el = phone.page.locator(f'#gHome .gcard:has([data-create="{kind}"]) {option}').first
    el.scroll_into_view_if_needed()
    before = phone.page.evaluate("scrollY")
    assert before > 300
    el.tap()
    phone.page.wait_for_timeout(500)
    assert phone.page.evaluate("scrollY") == before
    assert "on" in el.get_attribute("class")


def test_tabs_still_switch_views(phone):
    phone.open_games()
    phone.page.locator('button[data-tab="music"]').tap()
    assert phone.page.evaluate("document.body.dataset.tab") == "music"
    phone.page.locator('button[data-tab="games"]').tap()
    assert phone.page.evaluate("document.body.dataset.tab") == "games"
