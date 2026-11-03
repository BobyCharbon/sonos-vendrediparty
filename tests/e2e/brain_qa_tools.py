"""Outils des tests de stabilité Méninges (QA « jeux A ») : vrai moteur core.js servi par l'app, vrai navigateur.

- `Bench` ouvre l'app sur un écran donné (taille, tactile, reducedMotion), horloge simulée, puis lance un jeu par les
  vrais boutons (onglet Jeux → Méninges → tuile → « C'est parti » → 3-2-1).
- Avant le chargement des jeux, `Brain.register` est enveloppé : chaque appel ctx.hit / miss / slip / setLevel est
  journalisé (window.__qa.ev) pour recalculer le score selon les règles du moteur et vérifier qu'il colle à l'écran.
- Les minuteurs (setTimeout / setInterval / requestAnimationFrame) en attente sont comptés (window.__qa.pending()).
- Un robot en page (window.__qaRobot) joue tout seul toutes les ROBOT_MS : parfait, passif ou « faux une fois sur N »."""
import os
from pathlib import Path

from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(os.environ.get('BRAIN_QA_SHOTS', ROOT / 'test-results' / 'brain_qa'))

SCREENS = {
    'iphone': {'viewport': {'width': 390, 'height': 844}},
    'se': {'viewport': {'width': 375, 'height': 667}},
    'ipad': {'viewport': {'width': 820, 'height': 1180}},
    'paysage': {'viewport': {'width': 844, 'height': 390}},
}
UA_IPHONE = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
             'Version/18.0 Mobile/15E148 Safari/604.1')

# Compteur de minuteurs en attente (installé APRÈS l'horloge simulée, il enveloppe ses fonctions).
TIMERS_JS = r"""
(() => {
  const live = new Map();
  const st = window.setTimeout, ct = window.clearTimeout, si = window.setInterval, ci = window.clearInterval;
  const ra = window.requestAnimationFrame, ca = window.cancelAnimationFrame;
  window.setTimeout = function (fn, ms, ...a) {
    const id = st.call(window, (...b) => { live.delete('t' + id); if (typeof fn === 'function') fn(...b); }, ms, ...a);
    live.set('t' + id, 1); return id; };
  window.clearTimeout = function (id) { live.delete('t' + id); return ct.call(window, id); };
  window.setInterval = function (fn, ms, ...a) { const id = si.call(window, fn, ms, ...a); live.set('i' + id, 1); return id; };
  window.clearInterval = function (id) { live.delete('i' + id); return ci.call(window, id); };
  window.requestAnimationFrame = function (fn) {
    const id = ra.call(window, (t) => { live.delete('r' + id); fn(t); }); live.set('r' + id, 1); return id; };
  window.cancelAnimationFrame = function (id) { live.delete('r' + id); return ca.call(window, id); };
  window.__qaTimers = { count: () => live.size, keys: () => [...live.keys()] };
})();
"""

# Journal des appels du jeu au moteur : enveloppe Brain.register avant le chargement des jeux.
WRAP_JS = r"""
() => {
  const B = window.Brain;
  const qa = window.__qa = { ev: [], starts: 0, stops: 0 };
  const wrapped = Object.assign({}, B, { register(def) {
    B.register(Object.assign({}, def, { start(ctx) {
      qa.starts++;
      const proxy = {
        root: ctx.root, level: ctx.level, reducedMotion: ctx.reducedMotion, esc: ctx.esc, rng: ctx.rng,
        get lives() { return ctx.lives; },
        hit(i) { qa.ev.push(['h', performance.now()]); return ctx.hit(i); },
        miss(i) { qa.ev.push(['m', performance.now()]); return ctx.miss(i); },
        slip(i) { qa.ev.push(['s', performance.now()]); return ctx.slip(i); },
        setLevel(n) { qa.ev.push(['l', n]); return ctx.setLevel(n); },
        finish(x) { qa.ev.push(['f', 0]); return ctx.finish(x); },
        onTimeUp(fn) { return ctx.onTimeUp(fn); },
        get paused() { return ctx.paused; },
        onPause(fn) { return ctx.onPause(fn); },
        onResume(fn) { return ctx.onResume(fn); },
      };
      const h = def.start(Object.freeze(proxy));
      return h && { stop() { qa.stops++; return h.stop(); } };
    } }));
  } });
  window.Brain = wrapped;
}
"""

# Règles du moteur (core.js) rejouées sur le journal : score, multiplicateur, vies, fin.
SCORE_JS = r"""
() => {
  let score = 0, mult = 1, gauge = 0, streak = 0, lives = 3, dead = false, after = 0, maxLevel = 0;
  for (const [k, v] of window.__qa.ev) {
    if (k === 'l') { maxLevel = Math.max(maxLevel, v); continue; }
    if (dead) { after++; continue; }
    if (k === 'h') {
      score += 50 * mult;
      if (mult < 10 && ++gauge >= 4) { mult++; gauge = 0; }
      if (++streak >= 15) { streak = 0; if (lives < 3) lives++; }
    } else if (k === 'm') {
      streak = 0; mult = Math.max(1, mult - 1); gauge = 0; lives = Math.max(0, lives - 1); if (!lives) dead = true;
    } else if (k === 's') { streak = 0; gauge = 0; }
  }
  const ev = window.__qa.ev;
  return { score, mult, lives, dead, after, maxLevel, total: score + 250 * mult,
    hits: ev.filter((e) => e[0] === 'h').length, misses: ev.filter((e) => e[0] === 'm').length,
    slips: ev.filter((e) => e[0] === 's').length };
}
"""

# Robot en page. mode : 'perfect' | 'passive' | 'errN' (une réponse fausse sur N). via : 'synthetic' (événements JS)
ROBOT_JS = r"""
([game, mode]) => {
  if (window.__qaRobot) clearInterval(window.__qaRobot.timer);
  const R = window.__qaRobot = { acts: 0, wrong: 0, game, mode };
  const every = /^err(\d+)$/.test(mode) ? +mode.slice(3) : 0;
  // 'human' : parfait, mais n'agit que REACT_MS après l'apparition de l'élément (temps de réaction humain).
  // 'slow' : 450 ms de réaction ET au plus un geste toutes les 130 ms (un vrai pouce).
  const react = mode === 'human' || mode === 'slow' ? 450 : 0;
  const gapMs = mode === 'slow' ? 130 : 0;
  let cur = null, at = 0, lastAct = -1e9;
  const ready = (id) => {
    if (id !== cur) { cur = id; at = performance.now(); }
    if (performance.now() - at < react || performance.now() - lastAct < gapMs) return false;
    lastAct = performance.now();
    return true;
  };
  const bad = () => every > 0 && R.acts % every === every - 1;
  // manual : le robot ne fait que décider ; le test joue le geste avec le vrai tactile ou le vrai clavier.
  const manual = R.manual = window.__qaManual === true;
  R.queue = [];
  const mark = (el) => { const b = el.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; };
  const key = (k) => manual ? R.queue.push({ key: k })
    : (document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
  const down = (el) => manual ? R.queue.push({ el: mark(el), sel: el.dataset.item || el.dataset.sig || el.dataset.i })
    : el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
  const click = (el) => manual ? R.queue.push({ el: mark(el), sel: el.dataset.i }) : el.click();
  const keys = R.keys = [];
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => {
    if (n.nodeType === 1 && n.dataset && n.dataset.k) keys.push(n.dataset.k);
  }))).observe(document.getElementById('brainRoot'), { childList: true, subtree: true });
  let lastCard = null, shown = [], picked = new Set(), roundTxt = '', lastTrial = null;
  const steps = {
    pareil: () => {
      const yes = document.querySelector('[data-a="yes"]');
      const card = document.querySelector('.br-' + game + '-card[data-k]:last-child');
      if (!yes || yes.disabled || !card || card === lastCard || !ready(card)) return;
      lastCard = card;
      const same = keys[keys.length - 1] === keys[keys.length - 2];
      const w = bad(); if (w) R.wrong++;
      key(same !== w ? 'ArrowRight' : 'ArrowLeft'); R.acts++;
    },
    deux_avant: () => {
      const yes = document.querySelector('[data-ans="yes"]');
      if (!yes || yes.disabled || !ready(document.querySelector('.br-deux_avant-big'))) return;
      const label = (s) => document.querySelector(s + ' svg')?.getAttribute('aria-label');
      const same = label('.br-deux_avant-target') === label('.br-deux_avant-big');
      const w = bad(); if (w) R.wrong++;
      key(same !== w ? 'ArrowRight' : 'ArrowLeft'); R.acts++;
    },
    grille: () => {
      const on = [...document.querySelectorAll('.br-grille-cell.br-grille-on')].map((e) => +e.dataset.i);
      if (on.length) { shown = on; return; }
      const free = [...document.querySelectorAll('.br-grille-cell:not(:disabled)')];
      if (!free.length || !ready(free.length + ':' + document.querySelectorAll('.br-grille-ok,.br-grille-bad').length)) return;
      const todo = free.filter((c) => shown.includes(+c.dataset.i) && !c.classList.contains('br-grille-ok'));
      const wrong = free.filter((c) => !shown.includes(+c.dataset.i) && !c.classList.contains('br-grille-bad'));
      if (bad() && wrong.length) { R.wrong++; click(wrong[0]); } else if (todo.length) click(todo[0]); else return;
      R.acts++;
    },
    tresor: () => {
      const head = document.querySelector('.br-tresor-round');
      const m = head && head.textContent.match(/Manche (\d+)/);
      if (m && m[1] !== roundTxt) { roundTxt = m[1]; picked = new Set(); }
      const f = document.querySelector('.br-tresor-field');
      if (!f || f.classList.contains('is-hidden')) return;
      const btns = [...document.querySelectorAll('.br-tresor-item:not(.is-good):not(.is-bad)')];
      if (!btns.length || document.querySelector('.br-tresor-item.is-good,.br-tresor-item.is-bad') || !ready(btns[0])) return;
      let b;
      if (bad() && picked.size) { b = btns.find((x) => picked.has(x.dataset.item)); R.wrong++; }
      else b = btns.find((x) => !picked.has(x.dataset.item));
      if (!b) return;
      picked.add(b.dataset.item); down(b); R.acts++;
    },
    intrus: () => {
      const btns = [...document.querySelectorAll('.br-intrus-item')];
      if (!btns.length || document.querySelector('.br-intrus-item.is-good,.br-intrus-item.is-bad,.br-intrus-item.is-answer') || !ready(btns[0])) return;
      const n = {}; btns.forEach((x) => { n[x.dataset.sig] = (n[x.dataset.sig] || 0) + 1; });
      const odd = btns.find((x) => n[x.dataset.sig] === 1);
      const b = bad() ? (R.wrong++, btns.find((x) => x !== odd)) : odd;
      down(b); R.acts++;
    },
    nuee: () => {
      const mid = document.querySelector('.br-nuee-bird.is-mid');
      const flock = document.querySelector('.br-nuee-flock');
      if (!mid || !flock || flock.classList.contains('is-ok') || flock.classList.contains('is-ko')) return;
      if (lastTrial === mid || !ready(mid)) return;
      lastTrial = mid;
      const K = { droite: 'ArrowRight', gauche: 'ArrowLeft', haut: 'ArrowUp', bas: 'ArrowDown' };
      const W = { droite: 'gauche', gauche: 'droite', haut: 'bas', bas: 'haut' };
      const w = bad(); if (w) R.wrong++;
      key(K[w ? W[mid.dataset.dir] : mid.dataset.dir]); R.acts++;
    },
    autoroute: () => {
      const cv = document.querySelector('.br-autoroute-cv');
      if (!cv || !cv.dataset.lanes) return;
      const lanes = +cv.dataset.lanes, lane = +cv.dataset.lane;
      const blocked = cv.dataset.blocked ? cv.dataset.blocked.split(',').map(Number) : [];
      const crash = every > 0 && (+cv.dataset.passed || 0) % every === every - 1;
      const want = [];
      for (let l = 0; l < lanes; l++) if (crash === blocked.includes(l)) want.push(l);
      if (!want.length || want.includes(lane) || !ready(cv.dataset.blocked)) return;
      const t = want.reduce((a, b) => Math.abs(b - lane) < Math.abs(a - lane) ? b : a);
      key(t < lane ? 'ArrowLeft' : 'ArrowRight');
    },
  };
  steps.motif = steps.pareil;
  if (mode !== 'passive') R.timer = setInterval(() => { if (R.paused || R.queue.length) return; try { steps[game](); } catch (e) { R.err = String(e); } }, 40);
}
"""

# Tout ce qui se touche dans la zone de jeu doit être dans l'écran (le panneau de jeu ne défile pas : overflow hidden).
LAYOUT_JS = r"""
() => {
  const vw = innerWidth, vh = innerHeight, out = [];
  const stage = document.getElementById('brStage');
  if (!stage) return { out: ['pas de zone de jeu'], hscroll: 0 };
  const sel = 'button, canvas, .br-nuee-sky, .br-grille-board';
  // Grille en train de pivoter : sa boîte dépasse le temps du quart de tour (normal), on ne la mesure qu'à l'arrêt.
  const board = stage.querySelector('.br-grille-board');
  const m = board && getComputedStyle(board).transform.match(/matrix\(([^,]+),\s*([^,]+)/);
  const turning = m && Math.abs(Math.abs(+m[1]) + Math.abs(+m[2]) - 1) > 0.01;
  for (const el of stage.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || (turning && board.contains(el))) continue;
    if (r.left < -1 || r.top < -1 || r.right > vw + 1 || r.bottom > vh + 1)
      out.push(`${el.className || el.tagName} ${Math.round(r.left)},${Math.round(r.top)} → ${Math.round(r.right)},${Math.round(r.bottom)}`);
  }
  const play = document.querySelector('.br-play').getBoundingClientRect();
  const hud = document.querySelector('.br-hud').getBoundingClientRect();
  return { out: out.slice(0, 6), hscroll: document.documentElement.scrollWidth - vw,
    clipped: Math.round(stage.scrollHeight - stage.clientHeight), playH: Math.round(play.height), hudBottom: Math.round(hud.bottom) };
}
"""


class Bench:
    """Un téléphone (ou une tablette) avec l'app servie et l'horloge simulée."""

    def __init__(self, browser, server, screen='iphone', touch=False, reduced=False, tiers=None):
        opts = dict(SCREENS[screen])
        if touch:
            opts.update(has_touch=True, is_mobile=True, user_agent=UA_IPHONE, device_scale_factor=2)
        self.ctx = browser.new_context(base_url=server.url, locale='fr-CH',
                                       reduced_motion='reduce' if reduced else 'no-preference', **opts)
        seed_tiers = ''
        if tiers:
            import json
            seed_tiers = f'localStorage.setItem("brain_tiers", {json.dumps(json.dumps(tiers))});'
        self.ctx.add_init_script('if (!localStorage.getItem("vp_guest")) { localStorage.setItem("vp_guest", "qa-' + screen +
                                 '"); localStorage.setItem("vp_name", "Robot"); localStorage.setItem("vp_install_dismissed", "1");'
                                 + seed_tiers + '}')
        self.page = self.ctx.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(f'exception JS : {e}'))
        self.page.on('console', lambda m: m.type in ('error', 'warning') and 'Failed to load resource' not in m.text
                     and 'net::ERR' not in m.text and self.errors.append(f'console {m.type} : {m.text}'))
        self.page.clock.install()
        self.page.add_init_script(TIMERS_JS)
        self.root = self.page.locator('#brainRoot')
        self.page.goto('/')
        self.page.evaluate(WRAP_JS)
        self.page.locator('button[data-tab="games"]').first.click()
        expect(self.page.locator('#gHome')).to_be_visible()

    def open_brain(self):
        self.page.locator('#gHome section[data-cat="brain"] [data-brain-open]').click()
        expect(self.root.locator('.br-home')).to_be_visible(timeout=15000)

    def start(self, game, robot=None):
        """Accueil Méninges → jeu → (fiche du jeu si déjà joué) → explication → 3-2-1 → partie."""
        if not self.root.is_visible() or self.root.get_attribute('data-screen') != 'home':
            self.open_brain()
        self.root.locator(f'[data-br="play"][data-id="{game}"]').click()
        again = self.root.locator(f'[data-br="again"][data-id="{game}"]')
        go = self.root.locator('[data-br="go"]')
        expect(go.or_(again).first).to_be_visible()
        if not go.is_visible():
            again.click()
        if robot:  # avant le 3-2-1 : le robot voit la toute première carte
            self.robot(game, robot)
        go.click()
        self.page.clock.run_for(2400)
        expect(self.root.locator('.br-hud')).to_be_visible()

    def robot(self, game, mode):
        self.page.evaluate(ROBOT_JS, [game, mode])

    def stop_robot(self):
        self.page.evaluate('() => window.__qaRobot && clearInterval(window.__qaRobot.timer)')

    def pause_robot(self, paused=True):
        self.page.evaluate('(p) => { window.__qaRobot.paused = p; }', paused)

    def screen(self):
        return self.root.get_attribute('data-screen')

    def hud_level(self):
        return int(self.root.locator('.br-lvl').inner_text().split()[1])

    def lives(self):
        return int(self.root.locator('.br-lives').get_attribute('aria-label').split()[0])

    def replay(self):
        return self.page.evaluate(SCORE_JS)

    def layout(self):
        return self.page.evaluate(LAYOUT_JS)

    def dom_size(self):
        return self.page.evaluate("document.getElementById('brainRoot').getElementsByTagName('*').length")

    def pending_timers(self):
        return self.page.evaluate('window.__qaTimers.count()')

    def shot(self, name):
        SHOTS.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(SHOTS / f'{name}.png'))

    def close(self):
        self.ctx.close()
