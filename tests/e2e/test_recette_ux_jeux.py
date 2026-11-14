"""Recette UX du 14.11 (un ado tape un mauvais code) : « Cette partie n'existe plus » laissait croire que la partie
avait été arrêtée. Un code tapé qui ne mène à rien dit de vérifier le code."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, 'Leo')
    yield p
    p.close()
    server.stop()


def test_a_typed_code_that_leads_nowhere_says_to_check_the_code(phone):
    phone.open_games()
    phone.page.locator('#gCode').fill('9999')
    expect(phone.page.get_by_text('Aucune partie avec le code 9999. Vérifie-le auprès de l’animateur.')).to_be_visible()


def test_the_game_mini_bar_never_covers_the_events_module(phone):
    """Recette UX du 14.11 : une salle de jeux ouverte, la mini-barre « Reprendre » se posait sur le module Événements et
    cachait « + Proposer » et « ✨ Avec l'IA ». Le module s'arrête au-dessus d'elle (rien ne le recouvre)."""
    page = phone.page
    phone.create('room')
    page.goto('/?tab=events')  # comme en vrai : l'app rouverte sur Événements, la salle toujours ouverte
    mini = page.locator('#gMini')
    expect(mini).to_be_visible()
    panel = page.locator('.events-panel').bounding_box()
    assert panel['y'] + panel['height'] <= mini.bounding_box()['y'] + 0.5
