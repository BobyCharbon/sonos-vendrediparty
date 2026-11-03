"""Méninges sans fin (contrat v2), vrai moteur, vrai navigateur iPhone, horloge simulée :
Cases lumineuses, Jamais deux fois, L'intrus.
- un robot parfait monte de niveau et la partie ne s'arrête pas tant qu'il ne se trompe pas ;
- un joueur qui ne touche à rien perd ses 3 vies sur les délais de réponse : écran de fin en quelques secondes ;
- après la fin, le jeu ne tourne plus (plus rien ne change dans la page)."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server

GAMES = ('grille', 'tresor', 'intrus')
# Niveau affiché par chaque jeu (lu dans sa zone de jeu).
LEVEL_JS = {
    'grille': "+document.querySelector('.br-grille-top [data-level]').textContent",
    'tresor': r"+document.querySelector('.br-tresor-lvl').textContent.replace(/\D+/g, '')",
    'intrus': r"+document.querySelector('.br-intrus-msg').textContent.replace(/^.*Niveau /, '').replace(/\D+/g, '') || 0",
}
# Robot en page : agit toutes les 150 ms (horloge simulée). mode = perfect | passive | err5
ROBOT = r"""
window.startRobot = function (game, mode) {
  const R = window.robot = { acts: 0, wrong: 0 };
  const bad = () => mode === 'err5' && (R.acts % 5 === 4);
  const fire = (el) => el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
  let shown = [], seenOn = false, picked = new Set(), roundTxt = '';
  function tick() {
    if (mode === 'passive') return;
    if (game === 'grille') {
      const on = [...document.querySelectorAll('.br-grille-cell.br-grille-on')].map(e => +e.dataset.i);
      if (on.length) { shown = on; return; }
      const free = [...document.querySelectorAll('.br-grille-cell:not(:disabled)')];
      if (!free.length) return;
      const todo = free.filter(c => shown.includes(+c.dataset.i) && !c.classList.contains('br-grille-ok'));
      const wrong = free.filter(c => !shown.includes(+c.dataset.i) && !c.classList.contains('br-grille-bad'));
      if (bad() && wrong.length) { R.wrong++; wrong[0].click(); } else if (todo.length) todo[0].click(); else return;
      R.acts++;
    } else if (game === 'tresor') {
      const head = document.querySelector('.br-tresor-round');
      const m = head && head.textContent.match(/Manche (\d+)/);
      if (m && m[1] !== roundTxt) { roundTxt = m[1]; picked = new Set(); }
      const f = document.querySelector('.br-tresor-field');
      if (!f || f.classList.contains('is-hidden')) return;
      const btns = [...document.querySelectorAll('.br-tresor-item:not(.is-good):not(.is-bad)')];
      if (!btns.length || document.querySelector('.br-tresor-item.is-good,.br-tresor-item.is-bad')) return;
      let b;
      if (bad() && picked.size) { b = btns.find(x => picked.has(x.dataset.item)); R.wrong++; }
      else b = btns.find(x => !picked.has(x.dataset.item));
      if (!b) return;
      picked.add(b.dataset.item); fire(b); R.acts++;
    } else if (game === 'intrus') {
      const btns = [...document.querySelectorAll('.br-intrus-item')];
      if (!btns.length || document.querySelector('.br-intrus-item.is-good,.br-intrus-item.is-bad,.br-intrus-item.is-answer')) return;
      const n = {}; btns.forEach(x => { n[x.dataset.sig] = (n[x.dataset.sig] || 0) + 1; });
      const odd = btns.find(x => n[x.dataset.sig] === 1);
      const b = bad() ? (R.wrong++, btns.find(x => x !== odd)) : odd;
      fire(b); R.acts++;
    }
  }
  R.timer = setInterval(tick, 150);
};
"""
PERFECT_LEVEL = 12


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


def start_game(phone, game):
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
    return root


@pytest.mark.parametrize('game', GAMES)
def test_perfect_player_never_ends_and_keeps_climbing(phone, game):
    page = phone.page
    root = start_game(phone, game)
    page.evaluate('([g, m]) => startRobot(g, m)', [game, 'perfect'])
    level = 0
    for _ in range(120):  # jusqu'à 10 min de jeu simulé
        page.clock.run_for(5000)
        assert root.get_attribute('data-screen') != 'end', f'{game} : la partie a fini alors que le robot ne se trompe pas'
        level = page.evaluate(LEVEL_JS[game])
        if level >= PERFECT_LEVEL:
            break
    assert level >= PERFECT_LEVEL, f'{game} : niveau {level} seulement'
    expect(root.locator('.br-end')).to_have_count(0)


@pytest.mark.parametrize('game', GAMES)
def test_passive_player_loses_three_lives_and_the_game_stops(phone, game):
    page = phone.page
    root = start_game(phone, game)
    page.clock.run_for(30_000)
    expect(root.locator('.br-end')).to_be_visible()
    stage = root.locator('#brStage')
    before = stage.inner_html() if stage.count() else ''
    page.clock.run_for(20_000)
    after = stage.inner_html() if stage.count() else ''
    assert before == after, f'{game} : la zone de jeu bouge encore après la fin'
