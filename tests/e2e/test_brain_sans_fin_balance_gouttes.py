"""Méninges sans fin (contrat v2), vrai moteur, vrai navigateur iPhone, horloge simulée : Plus lourd, Gouttes.
- un robot qui calcule juste dépasse le niveau 40 et la partie ne s'arrête pas ;
- un joueur qui ne touche à rien perd ses 3 vies (délai par calcul / gouttes dans l'eau) : écran de fin rapide ;
- Gouttes : un mauvais résultat tapé est une petite erreur sans perte de vie ;
- après la fin, plus rien ne bouge dans la zone de jeu ; rien ne déborde en largeur sur un écran de 390 px."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server

GAMES = ('balance', 'gouttes')
TARGET_LEVEL = 41
# Robot en page (toutes les 150 ms, horloge simulée) : calcule le texte affiché. mode = perfect | passive | err5
ROBOT = r"""
window.startRobot = function (game, mode) {
  const R = window.robot = { acts: 0, last: '' };
  const SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';
  const calc = (t) => Function('return ' + t.replace(/[  ]/g, ' ').replace(/(\d) (?=\d)/g, '$1')
    .replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-').replace(/ de /g, '*')
    .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, (m) => '**' + [...m].map((c) => SUP.indexOf(c)).join('')))();
  const bad = () => mode === 'err5' && R.acts % 5 === 4;
  function balance() {
    const L = document.querySelector('[data-side="l"]'), Rt = document.querySelector('[data-side="r"]');
    const btn = document.querySelector('.br-balance-btn');
    if (!L || btn.disabled) return;
    const key = L.textContent + '|' + Rt.textContent;
    if (key === R.last) return;
    R.last = key;
    const a = calc(L.textContent), b = calc(Rt.textContent);
    let ans = Math.abs(a - b) < 1e-9 ? 0 : a > b ? 1 : -1;
    if (bad()) ans = ans === 1 ? -1 : 1;
    R.acts++;
    document.querySelector(`[data-answer="${ans}"]`).click();
  }
  function gouttes() {
    const y = (d) => new DOMMatrix(getComputedStyle(d).transform).m42;
    const drops = [...document.querySelectorAll('.br-gouttes-drop:not(.pop):not(.splash)')].sort((p, q) => y(q) - y(p));
    if (!drops.length) return;
    const v = bad() ? 999999 : Math.round(calc(drops[0].textContent));
    R.acts++;
    for (const c of String(v)) document.querySelector(`.br-gouttes-key[data-key="${c}"]`).click();
    document.querySelector('.br-gouttes-key[data-key="ok"]').click();
  }
  R.timer = setInterval(() => { if (mode !== 'passive') (game === 'balance' ? balance : gouttes)(); }, 150);
};
"""


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


def start_game(phone, game, mode):
    page = phone.page
    phone.open_games()
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    root.locator(f'[data-br="play"][data-id="{game}"]').click()
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)  # 3-2-1
    expect(root.locator('.br-hud')).to_be_visible()
    page.add_script_tag(content=ROBOT)
    page.evaluate('([g, m]) => startRobot(g, m)', [game, mode])
    return root


def hud_level(page):
    return page.evaluate(r"+document.querySelector('.br-lvl').textContent.match(/\d+/)[0]")


@pytest.mark.parametrize('game', GAMES)
def test_perfect_player_goes_past_level_40_without_ending(phone, game):
    page = phone.page
    root = start_game(phone, game, 'perfect')
    level = 0
    for _ in range(120):  # jusqu'à 10 min de jeu simulé
        page.clock.run_for(5000)
        assert root.get_attribute('data-screen') != 'end', f'{game} : la partie a fini alors que le robot ne se trompe pas'
        level = hud_level(page)
        if level >= TARGET_LEVEL:
            break
    assert level >= TARGET_LEVEL, f'{game} : niveau {level} seulement'
    expect(root.locator('.br-lives .br-heart.lost')).to_have_count(0)
    assert page.evaluate('document.documentElement.scrollWidth') <= 390


@pytest.mark.parametrize('game', GAMES)
def test_passive_player_loses_three_lives_and_the_game_stops(phone, game):
    page = phone.page
    root = start_game(phone, game, 'passive')
    page.clock.run_for(30_000)
    expect(root.locator('.br-end')).to_be_visible()
    stage = root.locator('#brStage')
    before = stage.inner_html() if stage.count() else ''
    page.clock.run_for(20_000)
    after = stage.inner_html() if stage.count() else ''
    assert before == after, f'{game} : la zone de jeu bouge encore après la fin'


def test_gouttes_wrong_answer_is_a_slip_not_a_life(phone):
    page = phone.page
    root = start_game(phone, 'gouttes', 'err5')
    for _ in range(12):  # 1 min de jeu simulé, un résultat faux sur cinq
        page.clock.run_for(5000)
        assert root.get_attribute('data-screen') != 'end'
    assert page.evaluate('robot.acts') >= 20
    expect(root.locator('.br-lives .br-heart.lost')).to_have_count(0)
    assert hud_level(page) > 1
