"""Méninges sans fin (contrat v2) : Le vol (nuee), Trois voies (autoroute), Contre-courant (courant).

Chaque jeu tourne dans un vrai navigateur iPhone (390×844) avec un faux moteur v2 (3 vies, ctx.miss = une vie,
15 bonnes d'affilée rendent une vie, stop() à 0 vie) et une horloge simulée. Des robots jouent dans la page :
- parfait : dépasse le niveau 40 sans jamais finir la partie ;
- passif : perd ses 3 vies en quelques secondes (délai de réponse / obstacles sur sa voie) ;
- un sur cinq faux : finit par perdre ;
puis on vérifie qu'après stop() plus rien ne tourne et que la console est propre."""
from pathlib import Path

import pytest
pytest.importorskip('playwright.sync_api')

ROOT = Path(__file__).resolve().parents[2]
GAMES = ROOT / 'app' / 'static' / 'brain' / 'games'
IDS = ('nuee', 'autoroute', 'courant')

HARNESS = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#101418;color:#eee;font-family:system-ui}
#root{display:flex;flex-direction:column;width:100%;height:700px}</style></head><body><div id="root"></div>
<script>
window.__defs = {};
window.Brain = { register: function (d) { __defs[d.id] = d; } };
Math.random = function () { throw new Error('Math.random interdit'); };
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
window.__log = { hit: 0, miss: 0, slip: 0, lives: 3, run: 0, level: 0, maxLevel: 0, ended: false, endAt: 0,
  afterStop: 0 };
var rawRaf = window.requestAnimationFrame.bind(window), rawTo = window.setTimeout.bind(window);
window.requestAnimationFrame = function (f) {
  return rawRaf(function (t) { if (__log.ended) __log.afterStop++; f(t); }); };
window.setTimeout = function (f, ms) {
  return rawTo(function () { if (__log.ended) __log.afterStop++; f(); }, ms); };
window.startGame = function (id, level) {
  var t0 = performance.now();
  function lose() {
    __log.lives -= 1; __log.run = 0;
    if (__log.lives <= 0 && !__log.ended) {
      window.__game.stop(); __log.ended = true; __log.endAt = performance.now() - t0;
      clearInterval(window.__robot);
    }
  }
  var ctx = { root: document.getElementById('root'), level: level, rng: mulberry32(7), reducedMotion: false,
    hit: function () { __log.hit++; __log.run++; if (__log.run >= 15) { __log.run = 0; __log.lives = Math.min(3, __log.lives + 1); } },
    miss: function () { __log.miss++; lose(); },
    slip: function () { __log.slip++; __log.run = 0; },
    setLevel: function (n) { __log.level = n; __log.maxLevel = Math.max(__log.maxLevel, n); },
    finish: function () { throw new Error('finish() ne doit plus finir une partie'); },
    onTimeUp: function () {},
    esc: function (s) { return String(s).replace(/[&<>"']/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); } };
  window.__game = __defs[id].start(ctx);
};
</script></body></html>"""

# Robots : `mode` = 'parfait' | 'passif' | 'cinq' (une réponse fausse sur cinq). Ils jouent toutes les 40 ms.
ROBOT = """([id, mode]) => {
  const KEY = { droite: 'ArrowRight', gauche: 'ArrowLeft', haut: 'ArrowUp', bas: 'ArrowDown' };
  const WRONG = { droite: 'gauche', gauche: 'droite', haut: 'bas', bas: 'haut' };
  const press = (k) => window.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  let answered = 0, seenAt = 0;
  const swipeGame = (expected, pending) => {
    if (!pending) { seenAt = 0; return; }
    if (!seenAt) { seenAt = performance.now(); return; }
    if (performance.now() - seenAt < 250) return;   // temps de réaction humain du robot
    answered++;
    press(KEY[mode === 'cinq' && answered % 5 === 0 ? WRONG[expected] : expected]);
    seenAt = 0;
  };
  const step = {
    nuee: () => {
      const mid = document.querySelector('.br-nuee-bird.is-mid');
      const flock = document.querySelector('.br-nuee-flock');
      if (!flock) return;
      swipeGame(mid && mid.dataset.dir,
        !!mid && !flock.classList.contains('is-ok') && !flock.classList.contains('is-ko'));
    },
    courant: () => {
      const f = document.querySelector('.br-courant-field');
      if (!f) return;
      const pending = !!f.dataset.rule && !f.classList.contains('is-ok') && !f.classList.contains('is-ko');
      swipeGame(f.dataset.rule === 'pointe' ? f.dataset.point : f.dataset.move, pending);
    },
    autoroute: () => {
      const cv = document.querySelector('.br-autoroute-cv');
      if (!cv || !cv.dataset.lanes) return;
      const lanes = +cv.dataset.lanes, lane = +cv.dataset.lane;
      const blocked = cv.dataset.blocked ? cv.dataset.blocked.split(',').map(Number) : [];
      const crash = mode === 'cinq' && (+cv.dataset.passed || 0) % 5 === 4;
      const want = [];
      for (let l = 0; l < lanes; l++) if (crash === blocked.includes(l)) want.push(l);
      if (!want.length || want.includes(lane)) return;
      const target = want.reduce((a, b) => Math.abs(b - lane) < Math.abs(a - lane) ? b : a);
      press(target < lane ? 'ArrowLeft' : 'ArrowRight');
    },
  }[id];
  if (mode !== 'passif') window.__robot = setInterval(step, 40);
}"""


@pytest.fixture
def page(browser):
    # Écran iPhone 390×844 ; densité 1 pour que des minutes de jeu simulé (canvas) tournent vite.
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                              is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    errors = []
    pg.on('console', lambda m: errors.append(m.text) if m.type in ('error', 'log', 'warning') else None)
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.clock.install()
    pg.set_content(HARNESS)
    pg.errors = errors
    yield pg
    ctx.close()
    assert not errors, '\n'.join(errors)


CHUNK_S = 20
TARGET_LEVEL = 42


def play(page, game_id: str, mode: str, seconds: int, level: int = 1, until_level: int = 0) -> dict:
    """Lance le jeu et fait avancer l'horloge par tranches, jusqu'à la fin de partie, au niveau visé ou `seconds`."""
    page.add_script_tag(path=str(GAMES / f'{game_id}.js'))
    page.evaluate('([id, l]) => startGame(id, l)', [game_id, level])
    page.evaluate(ROBOT, [game_id, mode])
    log = page.evaluate('__log')
    for _ in range(0, seconds, CHUNK_S):
        page.clock.run_for(CHUNK_S * 1000)
        log = page.evaluate('__log')
        if log['ended'] or (until_level and log['maxLevel'] >= until_level):
            break
    return log


@pytest.mark.parametrize('game_id', IDS)
def test_perfect_robot_climbs_past_level_40_and_never_ends(page, game_id):
    log = play(page, game_id, 'parfait', 420, until_level=TARGET_LEVEL)
    assert not log['ended'], log
    assert log['miss'] == 0, log
    assert log['maxLevel'] >= TARGET_LEVEL, log
    assert page.evaluate('__defs[%r].seconds' % game_id) is None
    page.clock.run_for(20_000)  # au-delà du niveau 40, la partie continue tant qu'on ne se trompe pas
    log = page.evaluate('__log')
    assert not log['ended'] and log['miss'] == 0 and log['maxLevel'] > TARGET_LEVEL, log
    if game_id == 'autoroute':
        assert page.locator('.br-autoroute-cv').get_attribute('data-lanes') == '5'
    page.evaluate('__game.stop(); __log.ended = true; clearInterval(window.__robot)')
    page.clock.run_for(5000)
    assert page.evaluate('__log.afterStop') == 0, 'un minuteur ou une image tourne encore après stop()'


@pytest.mark.parametrize('game_id', IDS)
def test_passive_robot_loses_three_lives_in_a_few_seconds(page, game_id):
    log = play(page, game_id, 'passif', 30)
    assert log['ended'] and log['miss'] == 3, log
    assert log['endAt'] < 15000, log
    assert log['hit'] <= 3, log
    page.clock.run_for(5000)
    assert page.evaluate('__log.afterStop') == 0


@pytest.mark.parametrize('game_id', IDS)
def test_one_mistake_in_five_ends_the_game_without_climbing_far(page, game_id):
    log = play(page, game_id, 'cinq', 300)
    assert log['ended'], log
    assert log['maxLevel'] < 15, log


@pytest.mark.parametrize('game_id', IDS)
def test_high_tier_start_never_drops_below_its_first_level(page, game_id):
    log = play(page, game_id, 'passif', 30, level=36)
    assert log['ended'], log
    assert log['maxLevel'] == 36 and log['level'] == 36, log
    box = page.locator('#root').bounding_box()
    assert box['width'] == 390
    assert page.evaluate("getComputedStyle(document.body).overflow") == 'visible'
