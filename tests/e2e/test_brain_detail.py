"""Méninges, statistiques par jeu (vrai navigateur, iPhone, sans compte : parties gardées sur le téléphone).
Deux parties faibles déjà jouées → la tuile du jeu ouvre sa fiche (record, parties, courbe, Jouer) ; on joue une
partie (horloge simulée, le joueur ne répond plus : il perd ses 3 vies) → l'écran de fin compare à la moyenne et au record (nouveau record), montre la
mini-courbe et l'indice du jeu ; la fiche compte ensuite 3 parties."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server
from tests.e2e.test_brain import KEYBOARD_GAMES

SEED = """([game, now]) => {
  const at = (h) => new Date(now - h * 3600e3).toISOString();
  const s = (score, h, level) => ({ game, score, accuracy: 0.5, avg_rt_ms: 900, level, duration_ms: 45000, played_at: at(h) });
  localStorage.setItem('brain_local', JSON.stringify([s(100, 48, 1), s(140, 24, 2)]));
  localStorage.setItem('brain_best', JSON.stringify({ [game]: 140 }));
}"""


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


def open_brain(page):
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    return root


def test_game_sheet_and_enriched_end_screen(phone):
    page = phone.page
    phone.open_games()
    root = open_brain(page)
    ids = page.evaluate('Brain.list().map(g => g.id)')
    game = next((g for g in KEYBOARD_GAMES if g in ids), None)
    assert game, f'aucun jeu chronométré chargé : {ids}'
    page.evaluate(SEED, [game, page.evaluate('Date.now()')])
    root.locator('.br-top [data-br="close"]').click()
    root = open_brain(page)

    # Fiche du jeu, ouverte depuis la liste des jeux de l'accueil
    root.locator(f'[data-br="play"][data-id="{game}"]').click()
    sheet = root.locator('.bd-sheet')
    expect(sheet).to_be_visible()
    assert root.get_attribute('data-screen') == 'detail'
    stats = sheet.locator('.br-stat')
    expect(stats.filter(has_text='Record')).to_contain_text('140')
    expect(stats.filter(has_text='Parties')).to_contain_text('2')
    expect(stats.filter(has_text='Niveau max')).to_contain_text('2')
    expect(stats.filter(has_text='Palier max')).to_contain_text('1')
    expect(stats.filter(has_text='Précision moyenne')).to_contain_text('50 %')
    expect(stats.filter(has_text='Réaction moyenne')).to_contain_text('900 ms')
    expect(stats.filter(has_text='Indice du jeu')).to_contain_text('°M')
    expect(sheet.locator('.bd-curve polyline')).to_have_count(1)

    # Jouer → explication → partie courte
    sheet.locator('[data-br="again"]').click()
    expect(root.locator('.br-howto .br-rules li').first).to_be_visible()
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)
    expect(root.locator('.br-hud')).to_be_visible()
    page.keyboard.press('ArrowRight')
    page.clock.run_for(70_000)

    end = root.locator('.br-end')
    expect(end).to_be_visible()
    cmp = end.locator('.bd-cmp')
    expect(cmp).to_contain_text('sur ta moyenne')  # le bonus final seul (≥ 250) dépasse la moyenne de 120
    expect(cmp).to_contain_text('Nouveau record')
    expect(end.locator('.bd-end.bd-record')).to_be_visible()
    expect(end.locator('.bd-curve-box .bd-curve polyline')).to_have_count(1)
    idx = end.locator('.bd-idx')
    expect(idx).to_be_visible(timeout=10000)
    expect(idx).to_contain_text('°M')
    expect(idx.locator('.bd-delta')).to_contain_text('▲')
    points = end.locator('.bd-curve polyline').get_attribute('points').split()
    assert len(points) == 3

    # Retour à l'accueil : la fiche compte la nouvelle partie
    end.locator('[data-br="home"]').click()
    root.locator(f'[data-br="play"][data-id="{game}"]').click()
    expect(root.locator('.bd-sheet .br-stat').filter(has_text='Parties')).to_contain_text('3')
    root.locator('.bd-sheet .br-top [data-br="home"]').click()
    expect(root.locator('.br-home')).to_be_visible()
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'


def test_first_game_is_the_reference(phone):
    page = phone.page
    phone.open_games()
    root = open_brain(page)
    ids = page.evaluate('Brain.list().map(g => g.id)')
    game = next((g for g in KEYBOARD_GAMES if g in ids), None)
    root.locator(f'[data-br="play"][data-id="{game}"]').click()  # jamais joué : directement l'explication
    expect(root.locator('.br-howto')).to_be_visible()
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)
    page.clock.run_for(70_000)
    end = root.locator('.br-end')
    expect(end.locator('.bd-cmp')).to_contain_text('Première partie')
    expect(end.locator('.bd-end.bd-record')).to_have_count(0)
