"""Méninges sans fin — Aiguillages, Mot ou encre, Bascule (vrai navigateur, iPhone 390 × 844, horloge simulée).

Chaque jeu tourne avec un faux moteur v2 (3 vies, ctx.miss = une vie, 15 bonnes d'affilée rendent une vie, arrêt à
0 vie) et des robots qui jouent par de vrais événements (pointerdown, clavier) :
- robot parfait : dépasse le niveau 40 et la partie ne finit pas ;
- robot passif : perd ses 3 vies en quelques secondes (délai de réponse / wagons mal aiguillés) ;
- robot qui se trompe 1 fois sur 5 : la partie finit ;
- stop() arrête tout (plus d'image, plus de minuteur, plus de réponse) ; aucune erreur console.
Aiguillages : chaque palier ajoute une gare (2 → 10), est annoncé (« Palier N · N+1 gares ») et garde des cibles ≥ 44 px."""
from pathlib import Path

import pytest
pytest.importorskip('playwright.sync_api')

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = 'http://banc.meninges.test'

HARNESS = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#111;color:#eee;font-family:system-ui}
#root{position:relative;width:100%;height:700px;display:flex;flex-direction:column}</style></head>
<body><div id="root"></div><script>
window.__log = {hit: 0, miss: 0, lives: 3, streak: 0, over: false, raf: 0, level: 0, maxLevel: 0, afterOver: 0};
var defs = {}; window.Brain = {register: function (d) { defs[d.id] = d; }};
Math.random = function () { throw new Error('Math.random interdit'); };
var raf0 = window.requestAnimationFrame.bind(window);
window.requestAnimationFrame = function (f) { __log.raf++; return raf0(f); };
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a);
  t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
window.__begin = function (id, level) {
  var L = __log;
  function end() { if (L.over) return; L.over = true; __game.stop(); }
  var ctx = {root: document.getElementById('root'), level: level, rng: mulberry32(7), reducedMotion: false,
    hit: function () { if (L.over) { L.afterOver++; return; } L.hit++; if (++L.streak >= 15) { L.streak = 0; L.lives = Math.min(3, L.lives + 1); } },
    miss: function () { if (L.over) { L.afterOver++; return; } L.miss++; L.streak = 0; if (--L.lives <= 0) end(); },
    slip: function () { L.streak = 0; },
    setLevel: function (n) { L.level = n; L.maxLevel = Math.max(L.maxLevel, n); },
    finish: function () { end(); }, onTimeUp: function () {},
    esc: function (s) { return String(s).replace(/[&<>"']/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); }};
  window.__def = defs[id];
  window.__game = defs[id].start(ctx);
};
</script>__SCRIPT__</body></html>"""

ROBOT = """([id, mode]) => {
  let n = 0, seenAt = null;
  const mis = new Set();
  const press = (yes) => {
    if (++n % 3 === 0) document.dispatchEvent(new KeyboardEvent('keydown', {key: yes ? 'ArrowRight' : 'ArrowLeft', bubbles: true}));
    else document.querySelector(`[data-answer="${yes ? 'yes' : 'no'}"]`).dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true}));
  };
  const truth = {
    encre: () => document.querySelector('[data-role="top"]').dataset.meaning === document.querySelector('[data-role="bottom"]').dataset.ink,
    bascule: () => {
      const slot = [...document.querySelectorAll('.br-bascule-card')].find((s) => !s.hidden);
      const rule = slot.parentElement.dataset.rule, c = slot.dataset;
      return rule === 'pair' ? +c.digit % 2 === 0 : rule === 'voyelle' ? 'AEIOU'.includes(c.letter)
        : rule === 'consonne' ? !'AEIOU'.includes(c.letter) : c.warm === 'true';
    },
  };
  function answer() {
    if (document.getElementById('root').dataset.state !== 'ready') { seenAt = null; return; }
    if (seenAt === null) { seenAt = performance.now(); return; }
    if (performance.now() - seenAt < 350) return;
    seenAt = null;
    const right = truth[id]();
    press(mode === 'errant' && (n + 1) % 5 === 0 ? !right : right);
  }
  function route() {
    const cv = document.querySelector('canvas');
    if (!cv || !cv.brSnapshot) return;
    const s = cv.brSnapshot(), r = cv.getBoundingClientRect(), best = {};
    for (const w of s.wagons) if (w.next >= 0 && (!best[w.next] || w.remaining < best[w.next].remaining)) best[w.next] = w;
    for (const k in best) {
      const w = best[k];
      if (mode === 'errant' && w.id % 5 === 0) mis.add(w.id);
      const want = mis.has(w.id) ? 1 - w.want : w.want, sw = s.switches[k];
      if (sw.state !== want) cv.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true,
        clientX: r.left + sw.x + 6, clientY: r.top + sw.y - 6}));
    }
  }
  window.__robot = setInterval(() => {
    if (mode === 'passif' || __log.over) return;
    if (id === 'aiguillage') route(); else answer();
  }, 16);
}"""

STATE = '() => ({...__log})'
SNAPSHOT = """() => { const c = document.querySelector('canvas'); if (!c || !c.brSnapshot) return null;
  const s = c.brSnapshot(); return {stations: s.stations, tier: s.tier, level: s.level, hitRadius: s.hitRadius,
  minGap: s.minGap, banners: s.banners}; }"""


def _serve(route):
    path = route.request.url.removeprefix(ORIGIN).split('?')[0]
    if path.startswith('/static/'):
        return route.fulfill(path=str(ROOT / 'app' / path.lstrip('/')), content_type='application/javascript')
    game = route.request.url.split('id=')[-1]
    script = f'<script src="/static/brain/games/{game}.js?v=test"></script>'
    return route.fulfill(body=HARNESS.replace('__SCRIPT__', script), content_type='text/html')


@pytest.fixture
def bench(browser):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True,
                              device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on('console', lambda m: errors.append(f'{m.type}: {m.text}'))
    page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
    page.route(f'{ORIGIN}/**', _serve)
    page.clock.install()

    def start(game, mode, level=1):
        page.goto(f'{ORIGIN}/banc?id={game}')
        page.wait_for_function('window.Brain && Object.keys(defs).length > 0')
        page.evaluate('([g, l]) => __begin(g, l)', [game, level])
        page.evaluate(ROBOT, [game, mode])
        return page

    yield start
    ctx.close()
    assert not errors, '\n'.join(errors)


def _play(page, seconds, step=5):
    for _ in range(int(seconds / step)):
        page.clock.run_for(step * 1000)
        if page.evaluate('__log.over'):
            break
    return page.evaluate(STATE)


def _assert_stop_cleans_up(page):
    page.evaluate('() => { clearInterval(__robot); if (!__log.over) { __log.over = true; __game.stop(); } '
                  '__log.rafAtStop = __log.raf; __log.eventsAtStop = __log.hit + __log.miss; }')
    page.keyboard.press('ArrowRight')
    page.mouse.click(195, 420)
    page.clock.run_for(10_000)
    after = page.evaluate(STATE)
    assert after['raf'] == after['rafAtStop'], 'une image est encore demandée après stop()'
    assert after['hit'] + after['miss'] == after['eventsAtStop'] and after['afterOver'] == 0


@pytest.mark.parametrize('game', ['encre', 'bascule', 'aiguillage'])
def test_passive_player_loses_three_lives_within_seconds(bench, game):
    page = bench(game, 'passif')
    state = _play(page, 40, step=1)
    assert state['over'] and state['lives'] == 0 and state['miss'] == 3
    assert page.evaluate('performance.now()') < (26_000 if game == 'aiguillage' else 13_000)
    assert page.evaluate('__def.seconds') is None
    _assert_stop_cleans_up(page)


@pytest.mark.parametrize('game', ['encre', 'bascule'])
def test_perfect_player_climbs_past_level_40_and_never_ends(bench, game):
    page = bench(game, 'parfait')
    state = _play(page, 300)
    assert not state['over'] and state['miss'] == 0 and state['lives'] == 3
    assert state['maxLevel'] >= 41, state
    deadline = int(page.get_attribute('#root', 'data-deadline'))
    assert deadline < 1400, f'délai encore long au niveau {state["level"]} : {deadline} ms'
    _assert_stop_cleans_up(page)


def _climb(page, until_tier, max_seconds):
    snap = None
    for _ in range(int(max_seconds / 2)):
        page.clock.run_for(2000)
        snap = page.evaluate(SNAPSHOT)
        assert snap, 'la partie s\'est arrêtée'
        assert snap['stations'] == min(10, snap['tier'] + 1)
        assert snap['hitRadius'] >= 22 and snap['minGap'] >= 44, snap
        if snap['tier'] >= until_tier:
            break
    return snap['banners'], snap


def test_aiguillage_each_tier_adds_a_station_and_is_announced(bench):
    page = bench('aiguillage', 'parfait')
    banners, snap = _climb(page, 3, 300)
    state = page.evaluate(STATE)
    assert not state['over'] and state['miss'] == 0, state
    assert snap['level'] >= 11 and snap['stations'] == 4
    assert banners[:3] == ['Palier 1 · 2 gares', 'Palier 2 · 3 gares · plus rapide', 'Palier 3 · 4 gares · plus rapide'], banners
    _assert_stop_cleans_up(page)


def test_aiguillage_perfect_player_goes_past_level_45_with_ten_stations(bench):
    page = bench('aiguillage', 'parfait', level=41)
    banners, snap = _climb(page, 10, 300)
    state = page.evaluate(STATE)
    assert not state['over'] and state['miss'] == 0, state
    assert state['maxLevel'] >= 46 and snap['stations'] == 10
    assert banners[:2] == ['Palier 9 · 10 gares · plus rapide', 'Palier 10 · 10 gares · plus rapide'], banners
    page.screenshot(path=str(ROOT / 'test-results' / 'aiguillage-10-gares.png'))
    _assert_stop_cleans_up(page)


@pytest.mark.parametrize('game', ['encre', 'bascule', 'aiguillage'])
def test_player_wrong_one_time_in_five_eventually_runs_out_of_lives(bench, game):
    page = bench(game, 'errant')
    state = _play(page, 300)
    assert state['over'] and state['lives'] == 0
    assert state['hit'] >= 8
    _assert_stop_cleans_up(page)


def test_bascule_high_levels_have_four_rules_that_change_places(bench):
    page = bench('bascule', 'parfait', level=31)
    rules = page.evaluate("[...document.querySelectorAll('.br-bascule-zone')].map(z => z.dataset.rule).join()")
    assert sorted(rules.split(',')) == ['chaude', 'consonne', 'pair', 'voyelle']
    layouts = {rules}
    for _ in range(20):
        page.clock.run_for(2000)
        layouts.add(page.evaluate("[...document.querySelectorAll('.br-bascule-zone')].map(z => z.dataset.rule).join()"))
    assert len(layouts) >= 2, 'les règles ne changent jamais de zone'
    assert not page.evaluate('__log.over')
    _assert_stop_cleans_up(page)
