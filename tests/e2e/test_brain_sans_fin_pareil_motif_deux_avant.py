"""Méninges sans fin — Pareil ?, Même motif, Deux avant (vrai navigateur 390×844, horloge simulée).
Chaque jeu tourne dans un faux moteur v2 (3 vies, une vie rendue après 15 bonnes réponses d'affilée, arrêt à 0 vie) :
- robot parfait : dépasse le niveau 40 et la partie ne finit pas ;
- robot passif : perd ses 3 vies en quelques secondes (délai de réponse par carte) ;
- robot qui se trompe 1 fois sur 5 : finit après ~15 réponses ;
- stop() nettoie tout (plus aucun minuteur ni écouteur) ; départ à un palier élevé (Deux avant → 4 cartes avant)
  sans débordement horizontal ; aucune erreur console."""
from pathlib import Path

import pytest
pytest.importorskip('playwright.sync_api')

GAMES_DIR = Path(__file__).resolve().parents[2] / 'app' / 'static' / 'brain' / 'games'
GAMES = ('pareil', 'motif', 'deux_avant')
STEP_MS = 150
PASSIVE_LIMIT_MS = 15_000

HARNESS = """
window.Brain = { register(g) { window.__game = g; } };
window.__keys = [];
new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => {
  if (n.nodeType === 1 && n.dataset && n.dataset.k) window.__keys.push(n.dataset.k);
}))).observe(document.documentElement, { childList: true, subtree: true });
window.__run = (level) => {
  let seed = 4242;
  const rng = () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const log = window.__log = { hits: 0, misses: 0, lives: 3, run: 0, maxLevel: level, level, ended: false, answers: 0 };
  let handle = null;
  const ctx = Object.freeze({
    root: document.getElementById('root'), level, rng, esc, reducedMotion: false,
    hit() { if (log.ended) return; log.hits++; if (++log.run >= 15) { log.run = 0; log.lives = Math.min(3, log.lives + 1); } },
    miss() { if (log.ended) return; log.misses++; log.run = 0;
      if (--log.lives <= 0) { log.ended = true; log.endedAt = performance.now(); handle.stop(); } },
    slip() {},
    setLevel(n) { log.level = n; log.maxLevel = Math.max(log.maxLevel, n); },
    finish() { log.finished = true; },
    onTimeUp() {},
  });
  log.startedAt = performance.now();
  handle = window.__game.start(ctx);
  window.__handle = handle;
};
"""

# Le robot répond s'il y a une question ouverte ; errEvery = n → une réponse fausse toutes les n réponses.
ROBOT = """([game, errEvery]) => {
  const log = window.__log;
  let same;
  if (game === 'deux_avant') {
    const yes = document.querySelector('[data-ans="yes"]');
    if (!yes || yes.disabled) return false;
    const label = (sel) => document.querySelector(sel + ' svg')?.getAttribute('aria-label');
    same = label('.br-deux_avant-target') === label('.br-deux_avant-big');
  } else {
    const yes = document.querySelector('[data-a="yes"]');
    if (!yes || yes.disabled) return false;
    const k = window.__keys;
    same = k[k.length - 1] === k[k.length - 2];
  }
  log.answers++;
  const wrong = errEvery > 0 && log.answers % errEvery === 0;
  const key = (same !== wrong) ? 'ArrowRight' : 'ArrowLeft';
  document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  return true;
}"""


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
    pg = ctx.new_page()
    errors = []
    pg.on('console', lambda m: errors.append(f'{m.type}: {m.text}') if m.type in ('error', 'warning', 'log') else None)
    pg.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
    pg.clock.install()
    yield pg
    ctx.close()
    assert not errors, '\n'.join(errors)


def load(page, game, level=1):
    page.set_content('<!doctype html><html lang="fr"><head><meta charset="utf-8">'
                     '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
                     '<body style="margin:0;background:#1d1640;font-family:system-ui">'
                     '<div id="root" style="width:100%;min-height:640px"></div></body></html>')
    page.add_script_tag(content=HARNESS)
    page.add_script_tag(path=str(GAMES_DIR / f'{game}.js'))
    assert page.evaluate('window.__game.seconds') is None
    page.evaluate('(lv) => window.__run(lv)', level)


def log(page):
    return page.evaluate('window.__log')


def play(page, game, err_every, max_steps, until_level=None):
    for _ in range(max_steps):
        page.clock.run_for(STEP_MS)
        page.evaluate(ROBOT, [game, err_every])
        state = log(page)
        if state['ended'] or (until_level and state['maxLevel'] > until_level):
            return state
    return log(page)


@pytest.mark.parametrize('game', GAMES)
def test_perfect_robot_climbs_past_level_40_without_ending(page, game):
    load(page, game)
    state = play(page, game, 0, 3000, until_level=42)
    assert not state['ended'], state
    assert state['misses'] == 0, state
    assert state['maxLevel'] > 42, state
    page.clock.run_for(STEP_MS)
    page.evaluate(ROBOT, [game, 0])
    assert not log(page)['ended']
    page.screenshot(path=f'test-results/sans_fin_{game}_niv43.png')


@pytest.mark.parametrize('game', GAMES)
def test_passive_player_loses_three_lives_in_a_few_seconds(page, game):
    load(page, game)
    for _ in range(PASSIVE_LIMIT_MS // 500):
        page.clock.run_for(500)
        if log(page)['ended']:
            break
    state = log(page)
    assert state['ended'] and state['misses'] == 3, state
    assert state['endedAt'] - state['startedAt'] < PASSIVE_LIMIT_MS, state
    assert page.evaluate("document.getElementById('root').children.length") == 0


@pytest.mark.parametrize('game', GAMES)
def test_robot_wrong_one_time_in_five_ends_the_game(page, game):
    load(page, game)
    state = play(page, game, 5, 2000)
    assert state['ended'], state
    assert state['misses'] == 3 and 10 <= state['hits'] <= 14, state


@pytest.mark.parametrize('game', GAMES)
def test_stop_cleans_everything(page, game):
    load(page, game)
    play(page, game, 0, 40)
    before = log(page)
    page.evaluate('window.__handle.stop()')
    assert page.evaluate("document.getElementById('root').innerHTML") == ''
    page.keyboard.press('ArrowRight')
    page.clock.run_for(20_000)
    after = log(page)
    assert (after['hits'], after['misses']) == (before['hits'], before['misses'])


@pytest.mark.parametrize('game,level', [('pareil', 36), ('motif', 36), ('deux_avant', 36), ('deux_avant', 16)])
def test_high_tier_start_fits_the_phone(page, game, level):
    load(page, game, level)
    n = 4 if level > 30 else 3
    page.clock.run_for(n * 1000 + 200 if game == 'deux_avant' else 1300)  # présentation, sans laisser filer le délai
    if game == 'deux_avant':
        assert page.locator('.br-deux_avant-small').count() == n
        assert f'{n} cartes' in page.locator('[data-q]').inner_text()
    assert page.evaluate('document.documentElement.scrollWidth') <= 390
    state = play(page, game, 0, 200)
    assert not state['ended'] and state['maxLevel'] > level, state
    page.screenshot(path=f'test-results/sans_fin_{game}_depart{level}.png')


# ---------- Dans le vrai moteur (app servie, onglet Jeux → Méninges) ----------
KEYS_OBSERVER = """() => { window.__keys = []; window.__log = { answers: 0 };
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => {
    if (n.nodeType === 1 && n.dataset && n.dataset.k) window.__keys.push(n.dataset.k);
  }))).observe(document.body, { childList: true, subtree: true }); }"""


@pytest.fixture
def phone(browser):
    from tests.e2e.helpers import Phone, Server
    server = Server()
    p = Phone(browser, server, 'Boby')
    p.page.clock.install()
    yield p
    errors, server_errors = p.errors, server.errors()
    p.close()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)


def start_in_engine(phone, game):
    from playwright.sync_api import expect
    page = phone.page
    phone.open_games()
    page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
    root = page.locator('#brainRoot')
    expect(root.locator('.br-home')).to_be_visible(timeout=15000)
    root.locator(f'[data-br="play"][data-id="{game}"]').click()
    page.evaluate(KEYS_OBSERVER)
    root.locator('[data-br="go"]').click()
    page.clock.run_for(3000)  # 3-2-1
    expect(root.locator('.br-hud')).to_be_visible()
    return page, root


@pytest.mark.parametrize('game', GAMES)
def test_in_the_real_engine_perfect_never_ends_and_passive_does(phone, game):
    from playwright.sync_api import expect
    page, root = start_in_engine(phone, game)
    level = 1
    for _ in range(3000):
        page.clock.run_for(STEP_MS)
        page.evaluate(ROBOT, [game, 0])
        level = int(root.locator('.br-lvl').inner_text().split()[1])
        assert root.get_attribute('data-screen') == 'play'
        if level > 42:
            break
    assert level > 42, level
    assert root.locator('.br-lvl').inner_text().endswith('Palier 9')
    assert root.locator('.br-lives').get_attribute('aria-label').startswith('3 vies')
    # Puis plus rien : les 3 vies partent vite, l'écran de fin s'affiche.
    page.clock.run_for(PASSIVE_LIMIT_MS)
    expect(root.locator('.br-end')).to_be_visible()
    assert page.evaluate("document.getElementById('brStage')?.innerHTML || ''") == ''
