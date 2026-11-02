/* Méninges — « Cases lumineuses » (mémoire spatiale).
   Des cases s'allument puis s'éteignent ; on retouche celles qui étaient allumées.
   Escalier : sans faute → +1 case ; 1 faute → même nombre ; 2 fautes ou plus → −1 case.
   Aux niveaux hauts, la grille pivote d'un quart de tour après l'extinction : on touche les cases à leur nouvelle place. */
(function () {
  'use strict';

  const ID = 'grille';
  const TRIALS = 12;
  const MIN_TILES = 3;
  const MAX_TILES = 16;
  const ROTATE_FROM = 7;          // nombre de cases à partir duquel la grille peut pivoter
  const ROTATE_CHANCE = 0.45;
  const PAUSE_BEFORE_MS = 450;
  const SHOW_BASE_MS = 900;
  const SHOW_PER_TILE_MS = 90;
  const ROTATE_MS = 650;
  const RESULT_MS = 1100;

  const CSS = `
.br-grille-wrap{display:flex;flex-direction:column;align-items:center;gap:14px;padding:12px 16px 20px;
  color:#eef1ff;font:inherit;user-select:none;-webkit-user-select:none}
.br-grille-top{display:flex;justify-content:space-between;width:100%;max-width:360px;font-size:15px;opacity:.9}
.br-grille-top b{font-variant-numeric:tabular-nums}
.br-grille-msg{min-height:22px;font-size:16px;font-weight:600;text-align:center}
.br-grille-stage{width:min(88vw,360px);aspect-ratio:1;display:flex;align-items:center;justify-content:center}
.br-grille-board{display:grid;gap:8px;width:100%;height:100%;padding:10px;border-radius:22px;
  background:radial-gradient(circle at 30% 20%,#2b2f5e,#141632);box-shadow:0 10px 30px rgba(0,0,0,.35);
  transition:transform .65s cubic-bezier(.4,.1,.2,1)}
.br-grille-board.br-grille-calm{transition:none}
.br-grille-cell{appearance:none;border:0;border-radius:12px;min-width:44px;min-height:44px;padding:0;
  background:#2a2e57;box-shadow:inset 0 -3px 0 rgba(0,0,0,.25);cursor:pointer;touch-action:manipulation;
  transition:background .18s,transform .12s,box-shadow .18s;position:relative}
.br-grille-cell:disabled{cursor:default}
.br-grille-cell:focus-visible{outline:3px solid #ffd65c;outline-offset:2px}
.br-grille-cell.br-grille-on{background:#38e0c4;box-shadow:0 0 18px rgba(56,224,196,.65),inset 0 -3px 0 rgba(0,0,0,.15)}
.br-grille-cell.br-grille-ok{background:#38e0c4}
.br-grille-cell.br-grille-bad{background:#4a2140}
.br-grille-cell.br-grille-bad::after{content:'✕';position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;color:#ff7a59;font-size:22px;font-weight:800}
.br-grille-cell.br-grille-lost{background:#2a2e57;box-shadow:inset 0 0 0 3px #38e0c4}
.br-grille-cell.br-grille-pop{transform:scale(.92)}
.br-grille-dots{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;max-width:360px}
.br-grille-dot{width:10px;height:10px;border-radius:50%;background:#3a3f72}
.br-grille-dot.br-grille-done{background:#38e0c4}
.br-grille-dot.br-grille-miss{background:#ff7a59}
`;

  function injectStyle() {
    if (document.getElementById('br-grille-style')) return;
    const style = document.createElement('style');
    style.id = 'br-grille-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function clampTiles(n) {
    return Math.max(MIN_TILES, Math.min(MAX_TILES, Math.round(n) || MIN_TILES));
  }

  function sideFor(tiles) {
    if (tiles <= 4) return 3;
    if (tiles <= 7) return 4;
    if (tiles <= 11) return 5;
    return 6;
  }

  function pickTiles(rng, cellCount, count) {
    const pool = Array.from({ length: cellCount }, (_, i) => i);
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    return new Set(pool.slice(0, count));
  }

  function nextTiles(tiles, errors) {
    if (errors === 0) return clampTiles(tiles + 1);
    if (errors === 1) return tiles;
    return clampTiles(tiles - 1);
  }

  function start(ctx) {
    injectStyle();
    const esc = ctx.esc;
    const timers = new Set();
    let stopped = false;
    let tiles = clampTiles(ctx.level + 2);
    let best = 0;          // plus grand nombre de cases retrouvées sans faute
    let shownMax = tiles;  // repli si aucun essai parfait
    let trial = 0;
    let round = null;   // { targets:Set, found:Set, taps, errors, open, t0 }
    let rotation = 0;

    const wrap = document.createElement('div');
    wrap.className = 'br-grille-wrap';
    wrap.innerHTML =
      '<div class="br-grille-top"><span>Essai <b data-trial></b></span><span>Cases <b data-tiles></b></span></div>' +
      '<div class="br-grille-msg" data-msg aria-live="polite"></div>' +
      '<div class="br-grille-stage"><div class="br-grille-board" data-board></div></div>' +
      '<div class="br-grille-dots" data-dots></div>';
    ctx.root.appendChild(wrap);
    const board = wrap.querySelector('[data-board]');
    const msg = wrap.querySelector('[data-msg]');
    const dots = wrap.querySelector('[data-dots]');
    if (ctx.reducedMotion) board.classList.add('br-grille-calm');
    dots.innerHTML = Array.from({ length: TRIALS }, () => '<span class="br-grille-dot"></span>').join('');

    function later(fn, ms) {
      const t = setTimeout(() => { timers.delete(t); if (!stopped) fn(); }, ms);
      timers.add(t);
    }

    function setMsg(text) { msg.textContent = text; }

    function updateTop() {
      wrap.querySelector('[data-trial]').innerHTML = esc(`${Math.min(trial + 1, TRIALS)} / ${TRIALS}`);
      wrap.querySelector('[data-tiles]').innerHTML = esc(String(tiles));
    }

    function buildBoard(side) {
      board.style.gridTemplateColumns = `repeat(${side}, 1fr)`;
      board.style.transform = '';
      rotation = 0;
      board.innerHTML = Array.from({ length: side * side }, (_, i) =>
        `<button type="button" class="br-grille-cell" data-i="${i}" aria-label="Case ${i + 1}" disabled></button>`
      ).join('');
    }

    function cells() { return board.querySelectorAll('.br-grille-cell'); }

    function setEnabled(on) { cells().forEach((c) => { c.disabled = !on; }); }

    function beginTrial() {
      if (trial >= TRIALS) { finishGame(); return; }
      updateTop();
      const side = sideFor(tiles);
      buildBoard(side);
      round = { targets: pickTiles(ctx.rng, side * side, tiles), found: new Set(), taps: 0, errors: 0, open: false, t0: 0 };
      setMsg('Regarde bien…');
      later(showTargets, PAUSE_BEFORE_MS);
    }

    function showTargets() {
      const list = cells();
      round.targets.forEach((i) => list[i].classList.add('br-grille-on'));
      later(hideTargets, SHOW_BASE_MS + SHOW_PER_TILE_MS * tiles);
    }

    function hideTargets() {
      cells().forEach((c) => c.classList.remove('br-grille-on'));
      const turns = tiles >= ROTATE_FROM && ctx.rng() < ROTATE_CHANCE;
      if (!turns) { openInput(); return; }
      rotation = ctx.rng() < 0.5 ? -90 : 90;
      setMsg(rotation > 0 ? 'La grille pivote ↻' : 'La grille pivote ↺');
      later(() => { board.style.transform = `rotate(${rotation}deg)`; }, 120);
      later(openInput, ctx.reducedMotion ? 300 : ROTATE_MS + 200);
    }

    function openInput() {
      round.open = true;
      round.t0 = performance.now();
      setMsg(`Retrouve les ${tiles} cases`);
      setEnabled(true);
    }

    function onTap(cell) {
      if (!round || !round.open || stopped) return;
      const i = Number(cell.dataset.i);
      if (round.found.has(i) || cell.classList.contains('br-grille-bad')) return;
      const rt = Math.round(performance.now() - round.t0);
      round.t0 = performance.now();
      round.taps += 1;
      if (round.targets.has(i)) {
        round.found.add(i);
        cell.classList.add('br-grille-ok');
        ctx.hit({ rt });
      } else {
        round.errors += 1;
        cell.classList.add('br-grille-bad');
        ctx.miss({ rt });
      }
      if (round.found.size === round.targets.size || round.taps >= tiles) endTrial();
    }

    function endTrial() {
      round.open = false;
      setEnabled(false);
      const list = cells();
      round.targets.forEach((i) => { if (!round.found.has(i)) list[i].classList.add('br-grille-lost'); });
      const errors = round.errors;
      const dot = dots.children[trial];
      if (dot) dot.classList.add(errors === 0 ? 'br-grille-done' : 'br-grille-miss');
      setMsg(errors === 0 ? 'Parfait ! Une case de plus' : errors === 1 ? 'Presque ! On garde le même nombre' : 'Une case de moins');
      if (errors === 0) best = Math.max(best, tiles);
      shownMax = Math.max(shownMax, tiles);
      tiles = nextTiles(tiles, errors);
      ctx.setLevel(Math.max(1, tiles - 2));
      trial += 1;
      later(beginTrial, RESULT_MS);
    }

    function finishGame() {
      setMsg('Terminé !');
      round = null;
      ctx.finish({ detail: `${best || shownMax} cases au max` });
    }

    function onClick(e) {
      const cell = e.target.closest('.br-grille-cell');
      if (cell && board.contains(cell)) onTap(cell);
    }

    board.addEventListener('click', onClick);
    if (typeof ctx.onTimeUp === 'function') ctx.onTimeUp(() => { round = null; });
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
      'Des cases s’allument un instant puis s’éteignent : retouche toutes celles qui étaient allumées.',
      'Sans faute, une case de plus ; deux fautes, une de moins. Parfois la grille pivote : vise leur nouvelle place.',
      '12 essais. Ton record : le plus grand nombre de cases atteint.',
    ],
    start,
  });
})();
