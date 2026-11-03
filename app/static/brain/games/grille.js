/* Méninges — « Cases lumineuses » (mémoire spatiale), SANS FIN (contrat v2).
   Des cases s'allument puis s'éteignent ; on retouche celles qui étaient allumées.
   Mauvaise case = ctx.slip (sans vie) ; essai raté (trop de fautes ou trop lent) = ctx.miss (une vie).
   Essai parfait → niveau +1 ; essai avec fautes → même niveau, mais deux essais de suite avec fautes = le second est raté ;
   essai raté → niveau −1 (pas sous le palier de départ).

   Table des niveaux (params(n)) :
     cases   : n ≤ 10 → n + 2 (3…12) ; 11…40 → 12 + ⌊(n−10)/3⌋ (… 22 au niv. 40) ; au-delà +1 tous les 6 niveaux, max 30
     grille  : plus petit côté s (3…7) tel que s² ≥ 2,2 × cases → 3×3 (3-4), 4×4 (5-7), 5×5 (8-11), 6×6 (12-16), 7×7 (17+)
     affichage : cases × (25 + 70·e^(−n/30)) + 250 + 700·e^(−n/25) ms  (1,2 s au niv. 1 ; 1,35 s pour 22 cases au niv. 40)
     rotation : dès le niv. 8 (35 % puis +2 %/niv., max 90 %) ; ±90° avant 20 ; ±90° ou 180° de 20 à 31 ;
                dès 32, DEUX quarts de tour enchaînés (résultat 0°, ±180°…) ; pivot de plus en plus rapide (650 → 280 ms)
     délai   : par toucher 700 + 2300·e^(−n/25) ms (3 s au niv. 1, 1,15 s au niv. 40, → 0,7 s), +0,8 s pour le premier
     fautes  : l'essai est raté à 2 + ⌊cases/12⌋ mauvaises cases, ou s'il a des fautes alors que le précédent en avait déjà
   Au-delà du niveau 88 (30 cases), l'affichage et le délai continuent de raccourcir vers leur limite. */
(function () {
  'use strict';

  const ID = 'grille';
  const MAX_TILES = 30;
  const MAX_SIDE = 7;
  const ROTATE_FROM = 8;
  const HALF_TURN_FROM = 20;
  const DOUBLE_TURN_FROM = 32;
  const PAUSE_BEFORE_MS = 450;
  const RESULT_MS = 1100;
  const FIRST_TAP_BONUS_MS = 800;
  const HISTORY = 10;

  const CSS = `
.br-grille-wrap{display:flex;flex-direction:column;align-items:center;gap:12px;padding:12px 8px 20px;
  color:var(--br-text,#eef1ff);font:inherit;user-select:none;-webkit-user-select:none}
.br-grille-top{display:flex;justify-content:space-between;width:100%;max-width:380px;font-size:15px;opacity:.9;padding:0 6px;box-sizing:border-box}
.br-grille-top b{font-variant-numeric:tabular-nums}
.br-grille-msg{min-height:22px;font-size:16px;font-weight:600;text-align:center}
.br-grille-clock{width:100%;max-width:380px;height:6px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden}
.br-grille-clock i{display:block;height:100%;width:0;background:#38e0c4;border-radius:3px}
.br-grille-stage{width:min(100%,400px);aspect-ratio:1;display:flex;align-items:center;justify-content:center}
.br-grille-board{display:grid;gap:8px;width:100%;height:100%;padding:10px;box-sizing:border-box;border-radius:22px;
  background:radial-gradient(circle at 30% 20%,#2b2f5e,#141632);box-shadow:0 10px 30px rgba(0,0,0,.35);
  transition-property:transform;transition-timing-function:cubic-bezier(.4,.1,.2,1)}
.br-grille-board.br-grille-big{gap:5px;padding:8px}
.br-grille-board.br-grille-calm{transition:none}
.br-grille-cell{appearance:none;border:0;border-radius:12px;min-width:44px;min-height:44px;padding:0;
  background:#2a2e57;box-shadow:inset 0 -3px 0 rgba(0,0,0,.25);cursor:pointer;touch-action:manipulation;
  transition:background .18s,transform .12s,box-shadow .18s;position:relative}
.br-grille-big .br-grille-cell{min-width:0;min-height:0;border-radius:9px}
.br-grille-cell:disabled{cursor:default}
.br-grille-cell:focus-visible{outline:3px solid #ffd65c;outline-offset:2px}
.br-grille-cell.br-grille-on{background:#38e0c4;box-shadow:0 0 18px rgba(56,224,196,.65),inset 0 -3px 0 rgba(0,0,0,.15)}
.br-grille-cell.br-grille-ok{background:#38e0c4}
.br-grille-cell.br-grille-bad{background:#4a2140}
.br-grille-cell.br-grille-bad::after{content:'✕';position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;color:#ff7a59;font-size:20px;font-weight:800}
.br-grille-cell.br-grille-lost{background:#2a2e57;box-shadow:inset 0 0 0 3px #38e0c4}
.br-grille-dots{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;max-width:360px;min-height:10px}
.br-grille-dot{width:10px;height:10px;border-radius:50%;background:#3a3f72}
.br-grille-dot.br-grille-done{background:#38e0c4}
.br-grille-dot.br-grille-half{background:#ffd65c}
.br-grille-dot.br-grille-miss{background:#ff7a59}
`;

  function injectStyle() {
    if (document.getElementById('br-grille-style')) return;
    const style = document.createElement('style');
    style.id = 'br-grille-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function tilesFor(n) {
    if (n <= 10) return n + 2;
    if (n <= 40) return 12 + Math.floor((n - 10) / 3);
    return Math.min(MAX_TILES, 22 + Math.floor((n - 40) / 6));
  }

  function sideFor(tiles) {
    let s = 3;
    while (s < MAX_SIDE && s * s < tiles * 2.2) s += 1;
    return s;
  }

  /** Paramètres du niveau n (voir la table en tête de fichier). */
  function params(n) {
    const tiles = tilesFor(n);
    return {
      tiles,
      side: sideFor(tiles),
      showMs: Math.round(tiles * (25 + 70 * Math.exp(-n / 30)) + 250 + 700 * Math.exp(-n / 25)),
      tapMs: Math.round(700 + 2300 * Math.exp(-n / 25)),
      rotateChance: n < ROTATE_FROM ? 0 : Math.min(0.9, 0.35 + 0.02 * (n - ROTATE_FROM)),
      rotateMs: Math.max(280, 650 - 10 * Math.max(0, n - ROTATE_FROM)),
      maxErrors: 2 + Math.floor(tiles / 12),
    };
  }

  function pickTiles(rng, cellCount, count) {
    const pool = Array.from({ length: cellCount }, (_, i) => i);
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    return new Set(pool.slice(0, count));
  }

  /** Suite de quarts de tour (en degrés) pour l'essai, selon le niveau. */
  function turnsFor(n, rng, p) {
    if (rng() >= p.rotateChance) return [];
    const quarter = () => (rng() < 0.5 ? -90 : 90);
    if (n >= DOUBLE_TURN_FROM) return [quarter(), quarter()];
    if (n >= HALF_TURN_FROM && rng() < 0.35) return [180];
    return [quarter()];
  }

  function start(ctx) {
    injectStyle();
    const esc = ctx.esc;
    const timers = new Set();
    const floor = Math.max(1, Math.floor(ctx.level) || 1);
    let stopped = false;
    let level = floor;
    let history = [];
    let round = null;   // { p, targets, found, errors, open, t0, deadline }

    const wrap = document.createElement('div');
    wrap.className = 'br-grille-wrap';
    wrap.innerHTML =
      '<div class="br-grille-top"><span>Niveau <b data-level></b></span><span>Cases <b data-tiles></b></span></div>' +
      '<div class="br-grille-msg" data-msg aria-live="polite"></div>' +
      '<div class="br-grille-clock" aria-hidden="true"><i data-clock></i></div>' +
      '<div class="br-grille-stage"><div class="br-grille-board" data-board></div></div>' +
      '<div class="br-grille-dots" data-dots></div>';
    ctx.root.appendChild(wrap);
    const board = wrap.querySelector('[data-board]');
    const msg = wrap.querySelector('[data-msg]');
    const dots = wrap.querySelector('[data-dots]');
    const clock = wrap.querySelector('[data-clock]');
    if (ctx.reducedMotion) board.classList.add('br-grille-calm');

    function later(fn, ms) {
      if (stopped) return null;
      const t = setTimeout(() => { timers.delete(t); if (!stopped) fn(); }, ms);
      timers.add(t);
      return t;
    }

    function cancel(t) { if (t) { clearTimeout(t); timers.delete(t); } }

    function setMsg(text) { msg.textContent = text; }

    function runClock(ms) {
      clock.style.transition = 'none';
      clock.style.width = '100%';
      void clock.offsetWidth;
      clock.style.transition = `width ${ms}ms linear`;
      clock.style.width = '0%';
    }

    function freezeClock() { clock.style.transition = 'none'; clock.style.width = '0%'; }

    function renderTop(p) {
      wrap.querySelector('[data-level]').innerHTML = esc(String(level));
      wrap.querySelector('[data-tiles]').innerHTML = esc(String(p.tiles));
      dots.innerHTML = history.map((h) => `<span class="br-grille-dot br-grille-${esc(h)}"></span>`).join('');
    }

    function buildBoard(side) {
      board.style.gridTemplateColumns = `repeat(${side}, 1fr)`;
      board.style.transitionDuration = '0ms';
      board.style.transform = '';
      board.classList.toggle('br-grille-big', side >= 6);
      board.innerHTML = Array.from({ length: side * side }, (_, i) =>
        `<button type="button" class="br-grille-cell" data-i="${i}" aria-label="Case ${i + 1}" disabled></button>`
      ).join('');
    }

    function cells() { return board.querySelectorAll('.br-grille-cell'); }

    function setEnabled(on) { cells().forEach((c) => { c.disabled = !on; }); }

    function beginTrial() {
      const p = params(level);
      renderTop(p);
      buildBoard(p.side);
      freezeClock();
      round = { p, targets: pickTiles(ctx.rng, p.side * p.side, p.tiles), found: new Set(), errors: 0,
        open: false, t0: 0, deadline: null };
      setMsg('Regarde bien…');
      later(showTargets, PAUSE_BEFORE_MS);
    }

    function showTargets() {
      const list = cells();
      round.targets.forEach((i) => list[i].classList.add('br-grille-on'));
      later(hideTargets, round.p.showMs);
    }

    function hideTargets() {
      cells().forEach((c) => c.classList.remove('br-grille-on'));
      const turns = turnsFor(level, ctx.rng, round.p);
      if (!turns.length) { openInput(); return; }
      const stepMs = ctx.reducedMotion ? 0 : round.p.rotateMs;
      let angle = 0;
      turns.forEach((deg, k) => {
        later(() => {
          angle += deg;
          setMsg(deg > 0 ? 'La grille pivote ↻' : 'La grille pivote ↺');
          board.style.transitionDuration = `${stepMs}ms`;
          board.style.transform = `rotate(${angle}deg)`;
        }, 120 + k * (stepMs + 120));
      });
      later(openInput, 120 + turns.length * (stepMs + 120) + (ctx.reducedMotion ? 200 : 80));
    }

    function armDeadline(extra) {
      cancel(round.deadline);
      const ms = round.p.tapMs + extra;
      runClock(ms);
      round.deadline = later(() => endTrial('slow'), ms);
    }

    function openInput() {
      round.open = true;
      round.t0 = performance.now();
      setMsg(`Retrouve les ${round.p.tiles} cases`);
      setEnabled(true);
      armDeadline(FIRST_TAP_BONUS_MS);
    }

    function onTap(cell) {
      if (!round || !round.open || stopped) return;
      const i = Number(cell.dataset.i);
      if (round.found.has(i) || cell.classList.contains('br-grille-bad')) return;
      const rt = Math.round(performance.now() - round.t0);
      round.t0 = performance.now();
      if (round.targets.has(i)) {
        round.found.add(i);
        cell.classList.add('br-grille-ok');
        ctx.hit({ rt });
        if (stopped) return;
        if (round.found.size === round.targets.size) { endTrial('done'); return; }
      } else {
        round.errors += 1;
        cell.classList.add('br-grille-bad');
        if (round.errors >= round.p.maxErrors) { endTrial('fail'); return; }
        (ctx.slip || (() => {}))({ rt });
        if (stopped) return;
      }
      armDeadline(0);
    }

    function changeLevel(n) {
      level = Math.max(floor, n);
      ctx.setLevel(level);
    }

    function endTrial(how) {
      round.open = false;
      cancel(round.deadline);
      freezeClock();
      setEnabled(false);
      const list = cells();
      round.targets.forEach((i) => { if (!round.found.has(i)) list[i].classList.add('br-grille-lost'); });
      const perfect = how === 'done' && round.errors === 0;
      const repeated = how === 'done' && !perfect && history[history.length - 1] === 'half';
      const failed = how !== 'done' || repeated;
      history = history.concat([perfect ? 'done' : failed ? 'miss' : 'half']).slice(-HISTORY);
      setMsg(perfect ? 'Parfait ! Niveau suivant' : failed ? (how === 'slow' ? 'Trop lent !' : repeated ? 'Encore une faute : essai raté' : 'Essai raté')
        : 'Presque ! On garde le même niveau');
      if (perfect) changeLevel(level + 1);
      if (failed) changeLevel(level - 1);
      later(beginTrial, RESULT_MS);
      if (failed) ctx.miss({ rt: Math.round(performance.now() - round.t0) });
    }

    function onClick(e) {
      const cell = e.target.closest('.br-grille-cell');
      if (cell && board.contains(cell)) onTap(cell);
    }

    board.addEventListener('click', onClick);
    ctx.setLevel(level);
    beginTrial();

    return {
      stop() {
        stopped = true;
        timers.forEach((t) => clearTimeout(t));
        timers.clear();
        board.removeEventListener('click', onClick);
        round = null;
        wrap.remove();
      },
    };
  }

  Brain.register({
    id: ID,
    name: 'Cases lumineuses',
    domain: 'memoire',
    icon: '🟩',
    color: '#38e0c4',
    seconds: null,
    howto: [
      'Des cases s’allument un instant puis s’éteignent : retouche toutes celles qui étaient allumées, sans traîner.',
      'Sans faute, niveau suivant : plus de cases, une grille plus grande, un affichage plus court, des rotations.',
      'Trop de fautes ou trop lent : une vie perdue. Sans fin, jusqu’à la dernière vie.',
    ],
    start,
  });
})();
