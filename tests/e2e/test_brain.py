"""Méninges (vrai navigateur, iPhone) : la carte de l'onglet Jeux ouvre le panneau, l'accueil montre la Température,
l'Échauffement et les jeux ; on lance un jeu chronométré, on répond, le chrono (horloge avancée) arrive à 0 et l'écran
de fin s'affiche avec score, précision et bonus. Sans compte : la partie est gardée sur le téléphone."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server

TIMED = ('pareil', 'encre', 'bascule', 'courant', 'deux_avant', 'motif', 'intrus', 'nuee', 'balance', 'autoroute')


@pytest.fixture
def phone(browser):
    server = Server()
    p = Phone(browser, server, 'Boby')
    p.page.clock.install()
    yield p
    errors, server_errors = p.errors, server.errors()
    p.close()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def test_open_play_a_game_and_see_the_end_screen(phone):
    page = phone.page
    phone.open_games()
    card = page.locator('#gHome section[data-cat="brain"] .gcard.g-br')
    expect(card).to_be_visible()
    expect(card.locator('[data-brain-name]')).to_have_text('Méninges')
    card.locator('[data-brain-open]').click()

    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    expect(root.locator('.br-title')).to_contain_text('Méninges')
    expect(root.locator('.br-temp b')).to_have_text('0')
    expect(root.locator('.br-login')).to_contain_text('Connecte-toi')
    assert root.evaluate('el => getComputedStyle(el).position') == 'fixed'
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'
    ids = page.evaluate('Brain.list().map(g => g.id)')
    game = next((g for g in TIMED if g in ids), None)
    assert game, f'aucun jeu chronométré chargé : {ids}'
    assert 1 <= root.locator('.br-warm-row li').count() <= 5

    root.locator(f'[data-br="play"][data-id="{game}"]').click()
    expect(root.locator('.br-howto .br-rules li').first).to_be_visible()
    root.locator('[data-br="go"]').click()
    expect(root.locator('.br-count-n')).to_be_visible()
    page.clock.run_for(3000)  # 3-2-1
    expect(root.locator('.br-hud')).to_be_visible()
    expect(root.locator('#brStage')).not_to_be_empty()
    page.keyboard.press('ArrowRight')  # une réponse au clavier (Oui), juste ou fausse selon la partie
    page.clock.run_for(2000)
    page.keyboard.press('ArrowLeft')
    page.clock.run_for(70_000)  # le chrono arrive à 0

    end = root.locator('.br-end')
    expect(end).to_be_visible()
    expect(end.locator('.br-bonus')).to_contain_text('bonus ×')
    expect(end.locator('.br-stat').first).to_contain_text('Précision')
    expect(end.locator('.br-save')).to_contain_text('Connecte-toi', timeout=10000)
    assert page.evaluate("JSON.parse(localStorage.getItem('brain_local')).length") == 1
    assert page.evaluate(f"JSON.parse(localStorage.getItem('brain_levels'))['{game}']") >= 1

    end.locator('[data-br="home"]').click()
    expect(root.locator(f'[data-br="play"][data-id="{game}"] .br-tile-s')).to_contain_text('Record')
    root.locator('.br-top [data-br="close"]').click()
    expect(root).to_be_hidden()
    expect(page.locator('#gHome')).to_be_visible()
