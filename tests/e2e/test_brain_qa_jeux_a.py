"""QA de stabilité Méninges — jeux A : Pareil ?, Même motif, Deux avant, Cases lumineuses, Jamais deux fois, L'intrus,
Le vol, Trois voies. Tout se joue dans le VRAI moteur (app servie, onglet Jeux → Méninges), horloge simulée.

- robot « humain » (parfait, 450 ms de réaction) : niveau 60+ sans jamais finir, aucun élément impossible, score de
  l'écran = règles du moteur rejouées sur le journal des appels, page qui ne gonfle pas (DOM, minuteurs) ;
- robot passif : fin en quelques secondes ; robot qui se trompe une fois sur cinq : fin, rien après la fin ;
- départ au palier 9 (niveau 41) : jouable, jamais sous le niveau 41 ;
- vrai tactile (taps, glissés) et vrai clavier ;
- écrans 375×667, iPad, téléphone en paysage : tout ce qui se touche est dans l'écran ; reducedMotion ;
- quitter / relancer 20 fois : rien ne s'accumule ; arrière-plan puis retour : aucune vie perdue loin de l'écran.
Outils : tests/e2e/brain_qa_tools.py."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from tests.e2e.brain_qa_tools import SCORE_JS, Bench
from tests.e2e.helpers import Server

GAMES = ('pareil', 'motif', 'deux_avant', 'grille', 'tresor', 'intrus', 'nuee', 'autoroute')
HIGH_TIER = 9                      # palier 9 = niveau 41
STEP_MS = 5000
HIDE_JS = """(h) => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => h });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => h ? 'hidden' : 'visible' });
  document.dispatchEvent(new Event('visibilitychange'));
}"""


@pytest.fixture(scope='module')
def server():
    s = Server()
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def bench(browser, server):
    made = []

    def make(**opts):
        b = Bench(browser, server, **opts)
        made.append(b)
        return b
    yield make
    errors = [e for b in made for e in b.errors]
    for b in made:
        b.close()
    assert not errors, '\n'.join(errors)


def run_until(b, sim_ms, level=0, step=STEP_MS):
    """Fait tourner l'horloge par tranches ; s'arrête à la fin de partie ou au niveau visé."""
    t = 0
    while t < sim_ms:
        b.page.clock.run_for(step)
        t += step
        if b.screen() != 'play' or (level and b.hud_level() >= level):
            break
    return t


def end_score(b):
    expect(b.root.locator('.br-end')).to_be_visible()
    return int(b.root.locator('.br-big').get_attribute('data-count'))


# ---------- Robot parfait, longue partie ----------
@pytest.mark.parametrize('game', GAMES)
def test_human_speed_perfect_player_reaches_level_60_and_the_page_stays_light(bench, game):
    b = bench()
    b.start(game, 'human')
    samples = []
    t = 0
    while t < 15 * 60_000:
        b.page.clock.run_for(30_000)
        t += 30_000
        assert b.screen() == 'play', f'{game} : partie finie à {t // 1000} s pour un joueur parfait'
        samples.append((b.dom_size(), b.pending_timers()))
        if b.hud_level() >= 60 and t >= 120_000:
            break
    b.stop_robot()
    # Lu d'un seul coup (l'horloge simulée avance aussi un peu en temps réel entre deux lectures).
    hud, r = b.page.evaluate(f"() => [document.querySelector('.br-score').textContent, ({SCORE_JS})()]")
    assert r['misses'] == 0 and r['slips'] == 0, f'{game} : élément impossible pour un joueur parfait {r}'
    assert b.hud_level() >= 60 and b.lives() == 3, (b.hud_level(), b.lives())
    assert ''.join(ch for ch in hud if ch.isdigit()) == str(r['score']), (hud, r)
    dom, timers = zip(*samples)
    assert max(dom) <= 2 * min(dom) + 40, f'{game} : la page gonfle {dom}'
    assert max(timers) <= 20, f'{game} : minuteurs qui s’accumulent {timers}'
    assert b.layout()['hscroll'] <= 0


# ---------- Robot passif, robot qui se trompe ----------
@pytest.mark.parametrize('game', GAMES)
def test_passive_player_ends_quickly_and_the_score_matches_the_engine(bench, game):
    b = bench()
    b.open_brain()
    base_timers = b.pending_timers()
    b.start(game, 'passive')
    t = run_until(b, 30_000, step=1000)
    assert b.screen() == 'end' and t <= 20_000, f'{game} : {t} ms sans fin'
    r = b.replay()
    assert r['dead'] and r['after'] == 0, r
    assert end_score(b) == r['total']
    stage = b.page.evaluate("document.getElementById('brStage')?.innerHTML || ''")
    b.page.clock.run_for(20_000)
    assert b.page.evaluate("document.getElementById('brStage')?.innerHTML || ''") == stage
    assert b.page.evaluate('window.__qa.ev.length') == len(b.page.evaluate('window.__qa.ev'))
    assert b.pending_timers() <= base_timers, b.page.evaluate('window.__qaTimers.keys()')


@pytest.mark.parametrize('game', GAMES)
def test_player_wrong_one_time_in_five_ends_and_nothing_runs_after(bench, game):
    b = bench()
    b.start(game, 'err5')
    run_until(b, 600_000, step=2000)
    r = b.replay()
    assert b.screen() == 'end', f'{game} : la partie ne finit pas malgré les erreurs {r}'
    assert r['dead'] and r['after'] == 0, f'{game} : appels au moteur après la fin {r}'
    assert end_score(b) == r['total'], r
    before = len(b.page.evaluate('window.__qa.ev'))
    b.page.clock.run_for(15_000)
    assert len(b.page.evaluate('window.__qa.ev')) == before
    session = b.page.evaluate("JSON.parse(localStorage.getItem('brain_local') || '[]').pop()")
    assert session['game'] == game and session['score'] == r['total'], session


# ---------- Départ au palier max ----------
@pytest.mark.parametrize('game', GAMES)
def test_start_at_high_tier_is_playable_and_never_drops_below_it(bench, game):
    b = bench(tiers={game: HIGH_TIER})
    b.start(game, 'err5')
    assert b.root.locator('.br-lvl').inner_text() == 'Niv. 41 · Palier 9'
    run_until(b, 300_000, step=2000)
    levels = [v for k, v in b.page.evaluate('window.__qa.ev') if k == 'l']
    assert levels and min(levels) == 41, levels[:20]
    r = b.replay()
    assert r['hits'] >= 4, f'{game} : niveau 41 injouable même pour un robot {r}'


@pytest.mark.parametrize('game', GAMES)
def test_human_speed_player_keeps_going_from_the_highest_tier(bench, game):
    b = bench(tiers={game: HIGH_TIER})
    b.start(game, 'human')
    run_until(b, 180_000, step=STEP_MS)
    assert b.screen() == 'play'
    r = b.replay()
    assert r['misses'] == 0 and b.hud_level() > 41, (b.hud_level(), r)


# ---------- Arrière-plan ----------
@pytest.mark.parametrize('game', GAMES)
def test_background_then_back_costs_no_life_and_the_game_goes_on(bench, game):
    b = bench()
    b.start(game, 'perfect')
    b.page.clock.run_for(8000)
    b.pause_robot()
    before = b.replay()
    b.page.evaluate(HIDE_JS, True)
    b.page.clock.run_for(60_000)
    assert b.screen() == 'play', f'{game} : partie perdue pendant l’arrière-plan'
    b.page.evaluate(HIDE_JS, False)
    after = b.replay()
    assert after['misses'] == before['misses'], f'{game} : vie perdue loin de l’écran {before} → {after}'
    b.pause_robot(False)
    b.page.clock.run_for(8000)
    r = b.replay()
    assert r['hits'] > after['hits'] and r['misses'] == before['misses'], r
    assert b.lives() == 3


# ---------- Quitter et relancer ----------
@pytest.mark.parametrize('game', GAMES)
def test_quit_and_relaunch_20_times_leaves_nothing_behind(bench, game):
    b = bench()
    b.open_brain()
    cdp = b.page.context.new_cdp_session(b.page)

    def listeners():
        win = cdp.send('Runtime.evaluate', {'expression': 'window'})['result']['objectId']
        doc = cdp.send('Runtime.evaluate', {'expression': 'document'})['result']['objectId']
        found = [x['type'] for o in (win, doc) for x in cdp.send('DOMDebugger.getEventListeners', {'objectId': o})['listeners']]
        return sorted(found)
    before = listeners()
    counts = []
    for i in range(20):
        b.start(game, 'perfect')
        b.page.clock.run_for(1500 + 137 * i)
        b.stop_robot()
        b.root.locator('[data-br="quit"]').click()
        b.root.locator('[data-br="leave"]').click()
        expect(b.root.locator('.br-home')).to_be_visible()
        b.page.clock.run_for(2000)
        counts.append((b.pending_timers(), b.dom_size()))
    qa = b.page.evaluate('({ s: window.__qa.starts, t: window.__qa.stops })')
    assert qa['s'] == qa['t'] == 20, qa
    timers = [c[0] for c in counts]
    assert max(timers[5:]) <= max(timers[:5]) + 1, f'{game} : minuteurs laissés à chaque partie {timers}'
    after = listeners()
    assert after == before, f'{game} : écouteurs laissés après 20 parties : {set(after) ^ set(before) or (after, before)}'
    assert b.page.evaluate("document.querySelectorAll('style[id^=\"br-\"]').length") <= 20


# ---------- Écrans ----------
@pytest.mark.parametrize('screen', ['se', 'ipad', 'paysage'])
@pytest.mark.parametrize('game', GAMES)
def test_everything_to_touch_stays_on_screen(bench, game, screen):
    b = bench(screen=screen, tiers={game: HIGH_TIER})
    b.start(game, 'human')
    worst = []
    for _ in range(40):
        b.page.clock.run_for(500)
        if b.screen() != 'play':
            break
        lay = b.layout()
        worst += lay['out']
        assert lay['hscroll'] <= 0, lay
    assert not worst, f'{game} sur {screen} : hors écran {worst[:4]}'
    assert b.replay()['misses'] == 0, f'{game} sur {screen} : le robot rate (élément caché ?)'
    b.shot(f'{game}_{screen}_niv41')


@pytest.mark.parametrize('game', GAMES)
def test_reduced_motion_plays_the_same(bench, game):
    b = bench(reduced=True)
    b.start(game, 'human')
    run_until(b, 120_000, level=15)
    assert b.screen() == 'play' and b.replay()['misses'] == 0
    assert b.hud_level() >= 15


# ---------- Vrai tactile, vrai clavier ----------
SWIPE = {'ArrowRight': (1, 0), 'ArrowLeft': (-1, 0), 'ArrowUp': (0, -1), 'ArrowDown': (0, 1)}
ANSWER_BTN = {'pareil': '[data-a="{}"]', 'motif': '[data-a="{}"]', 'deux_avant': '[data-ans="{}"]'}


def center(page, selector):
    box = page.locator(selector).bounding_box()
    return box['x'] + box['width'] / 2, box['y'] + box['height'] / 2


def swipe(page, x, y, dx, dy, cdp):
    """Vrai glissé du doigt (événements tactiles du navigateur, pas des PointerEvent fabriqués)."""
    points = [(x + dx * k, y + dy * k) for k in (0, 12, 30, 60)]
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': points[0][0], 'y': points[0][1]}]})
    for px, py in points[1:]:
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': px, 'y': py}]})
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})


def perform(b, game, how, action, cdp):
    page = b.page
    if 'el' in action:
        x, y = action['el']['x'], action['el']['y']
        if how == 'touch':
            page.touchscreen.tap(x, y)
        else:
            page.evaluate('([x, y]) => document.elementFromPoint(x, y).closest("button").focus()', [x, y])
            page.keyboard.press('Enter')
        return
    k = action['key']
    if how == 'keyboard':
        page.keyboard.press(k)
    elif game in ANSWER_BTN:
        page.touchscreen.tap(*center(page, ANSWER_BTN[game].format('yes' if k == 'ArrowRight' else 'no')))
    elif game == 'nuee':
        x, y = center(page, '.br-nuee-sky')
        swipe(page, x, y, *SWIPE[k], cdp)
    else:  # autoroute : toucher la moitié gauche ou droite de la route
        box = page.locator('.br-autoroute-cv').bounding_box()
        page.touchscreen.tap(box['x'] + box['width'] * (0.2 if k == 'ArrowLeft' else 0.8), box['y'] + box['height'] * 0.6)


@pytest.mark.parametrize('how', ['touch', 'keyboard'])
@pytest.mark.parametrize('game', GAMES)
def test_real_touch_and_real_keyboard_play_without_error(bench, game, how):
    b = bench(touch=how == 'touch')
    b.page.evaluate('window.__qaManual = true')
    b.start(game, 'human')
    cdp = b.page.context.new_cdp_session(b.page)
    for _ in range(900):                       # 36 s de jeu
        b.page.clock.run_for(40)
        for action in b.page.evaluate('window.__qaRobot.queue.splice(0)'):
            perform(b, game, how, action, cdp)
        if b.screen() != 'play':
            break
    r = b.replay()
    assert b.screen() == 'play', f'{game} ({how}) : partie finie {r}'
    assert r['misses'] == 0 and r['hits'] >= 15, f'{game} ({how}) : {r}'


# ---------- L'intrus : jamais de plateau sans intrus visible ----------
INTRUS_SCAN = r"""
() => {
  const mul = (a) => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const parse = (s) => { const [shape, hue, fill, turn, size] = s.split('|'); return { shape, hue: +hue, fill, turn: +turn, size: +size }; };
  const ang = (a, b) => { const d = Math.abs(a - b) % 360; return Math.min(d, 360 - d); };
  // Un humain ne voit pas : 8° de teinte, 8° de rotation, 5 % de taille.
  const twin = (o, k) => {
    const d = [];
    if (o.shape !== k.shape) d.push(false);
    if (o.fill !== k.fill) d.push(false);
    if (o.hue !== k.hue) d.push(ang(o.hue, k.hue) < 10);
    if (o.turn !== k.turn) d.push(ang(o.turn, k.turn) < 10);
    if (o.size !== k.size) d.push(Math.abs(o.size - k.size) < 0.06);
    return d.length === 1 && d[0];
  };
  const root = document.getElementById('root'), bad = [];
  let boards = 0;
  for (let n = 15; n <= 60; n++) for (let seed = 1; seed <= 120; seed++) {
    const ctx = { root, level: n, rng: mul(seed * 7919 + n), reducedMotion: true, esc: (s) => String(s),
      hit() {}, miss() {}, slip() {}, setLevel() {}, finish() {}, onTimeUp() {} };
    const h = window.__defs.intrus.start(ctx);
    const sigs = [...root.querySelectorAll('.br-intrus-item')].map((b) => b.dataset.sig);
    h.stop(); root.innerHTML = ''; boards++;
    const count = {}; sigs.forEach((s) => { count[s] = (count[s] || 0) + 1; });
    const odd = sigs.filter((s) => count[s] === 1);
    if (odd.length !== 1) { bad.push(`niv. ${n} : ${odd.length} intrus`); continue; }
    const o = parse(odd[0]);
    for (const k of Object.keys(count).filter((s) => s !== odd[0]).map(parse))
      if (twin(o, k)) bad.push(`niv. ${n} : intrus ${odd[0]} ≈ sorte ${[k.shape, k.hue, k.fill, k.turn, k.size].join('|')}`);
  }
  return { boards, bad };
}
"""


def test_intrus_boards_always_have_one_visible_odd_one(page):
    from pathlib import Path
    games_dir = Path(__file__).resolve().parents[2] / 'app' / 'static' / 'brain' / 'games'
    page.set_content('<!doctype html><html><body><div id="root"></div></body></html>')
    page.add_script_tag(content='window.__defs = {}; window.Brain = { register(d) { window.__defs[d.id] = d; } };')
    page.add_script_tag(path=str(games_dir / 'intrus.js'))
    res = page.evaluate(INTRUS_SCAN)
    assert res['boards'] == 46 * 120
    assert not res['bad'], f"{len(res['bad'])} plateaux sans intrus visible : {res['bad'][:5]}"


# ---------- Cases lumineuses, mouvement réduit : la rotation doit rester lisible ----------
def test_reduced_motion_grid_says_how_it_turned_while_you_answer(bench):
    """Sans animation, une grille carrée tournée d'un quart de tour est identique à l'œil : pendant la réponse,
    le message doit dire de combien elle a tourné (sinon l'essai est impossible)."""
    b = bench(reduced=True, tiers={'grille': 7})        # niveau 31 : rotations quasi systématiques
    b.start('grille', 'perfect')
    seen = {'turned': 0, 'told': 0}
    for _ in range(600):
        b.page.clock.run_for(50)
        info = b.page.evaluate("""() => {
          const board = document.querySelector('.br-grille-board'), msg = document.querySelector('.br-grille-msg');
          const open = !!document.querySelector('.br-grille-cell:not(:disabled)');
          const a = (board && board.style.transform.match(/-?\\d+/)) ? ((+board.style.transform.match(/-?\\d+/)[0] % 360) + 360) % 360 : 0;
          return { open, a, msg: msg ? msg.textContent : '' };
        }""")
        if info['open'] and info['a']:
            seen['turned'] += 1
            if any(t in info['msg'] for t in ('↻', '↺', 'demi-tour')):
                seen['told'] += 1
    assert seen['turned'] > 5, seen
    assert seen['told'] == seen['turned'], f'rotation non signalée pendant la réponse : {seen}'


# ---------- Le vol : un glissé commencé avant la volée ne répond pas à sa place ----------
def test_nuee_swipe_started_between_two_flocks_does_not_answer_the_next_one(bench):
    b = bench(touch=True)
    b.start('nuee', 'passive')
    page = b.page
    cdp = page.context.new_cdp_session(page)
    flock = page.locator('.br-nuee-flock')
    for _ in range(100):                                  # première volée trop lente → entre deux volées
        page.clock.run_for(50)
        if 'is-ko' in (flock.get_attribute('class') or ''):
            break
    assert b.replay()['misses'] == 1
    x, y = center(page, '.br-nuee-sky')
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
    page.clock.run_for(400)                               # la volée suivante arrive, le doigt est encore posé
    assert 'is-ko' not in (flock.get_attribute('class') or '')
    for dx in (12, 40, 80):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x + dx, 'y': y}]})
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    r = b.replay()
    assert r['hits'] == 0 and r['misses'] == 1, f'le glissé d’avant a répondu à la nouvelle volée : {r}'
