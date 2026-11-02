/* Méninges — « Deux avant » (mémoire de travail, 2-back).
   Une carte arrive ; les deux précédentes sont retournées. Le symbole de la carte actuelle est-il le même que
   celui d'il y a DEUX cartes ? Oui (→) / Non (←). Erreur → les cartes cachées se révèlent jusqu'à la bonne réponse suivante. */
(function () {
  'use strict';

  const ID = 'deux_avant';
  const MATCH_CHANCE = 0.4;
  const INTRO_STEP_MS = 1000;
  const FEEDBACK_MS = 260;
  const LEVEL_UP_STREAK = 5;
  const LEVEL_DOWN_ERRORS = 2;
  const MAX_LEVEL = 8;

  // Formes originales (SVG 0..100) ; couleurs distinctes aux premiers niveaux, monochrome ensuite.
  const SHAPES = [
    { name: 'rond', svg: '<circle cx="50" cy="50" r="34"/>' },
    { name: 'carré', svg: '<rect x="18" y="18" width="64" height="64" rx="8"/>' },
    { name: 'triangle', svg: '<polygon points="50,14 88,84 12,84"/>' },
    { name: 'losange', svg: '<polygon points="50,10 88,50 50,90 12,50"/>' },
    { name: 'étoile', svg: '<polygon points="50,10 61,38 91,38 67,57 76,87 50,69 24,87 33,57 9,38 39,38"/>' },
    { name: 'hexagone', svg: '<polygon points="30,14 70,14 90,50 70,86 30,86 10,50"/>' },
    { name: 'croix', svg: '<polygon points="38,12 62,12 62,38 88,38 88,62 62,62 62,88 38,88 38,62 12,62 12,38 38,38"/>' },
    { name: 'lune', svg: '<path d="M62 12a38 38 0 1 0 0 76a30 30 0 1 1 0-76z"/>' },
    { name: 'goutte', svg: '<path d="M50 10C62 34 80 48 80 64a30 30 0 0 1-60 0C20 48 38 34 50 10z"/>' },
    { name: 'cœur', svg: '<path d="M50 86L16 52a20 20 0 0 1 34-26a20 20 0 0 1 34 26z"/>' },
  ];
  const COLORS = ['#ff8a5c', '#5cc8ff', '#b88cff', '#7be08a', '#ffd25c', '#ff6fa8', '#5ce0d0', '#f0f0f0', '#ffa94d', '#8fa2ff'];
  const MONO = '#c9b8ff';

  const CSS = `
.br-deux_avant-wrap{display:flex;flex-direction:column;align-items:center;gap:18px;padding:14px 16px 22px;
  color:var(--br-text,#f3efff);user-select:none;-webkit-user-select:none}
.br-deux_avant-q{font-size:17px;font-weight:600;text-align:center;min-height:24px}
.br-deux_avant-row{display:flex;align-items:flex-end;justify-content:center;gap:12px;width:100%;max-width:380px;min-height:190px}
.br-deux_avant-card{position:relative;border-radius:18px;display:flex;align-items:center;justify-content:center;
  background:#fbf8ff;box-shadow:0 8px 22px rgba(0,0,0,.3)}
.br-deux_avant-card svg{width:72%;height:72%}
.br-deux_avant-small{width:74px;height:100px}
.br-deux_avant-big{width:132px;height:178px;border:4px solid transparent;transition:border-color .15s}
.br-deux_avant-back{background:repeating-linear-gradient(45deg,#3b2a6e 0 10px,#4a3685 10px 20px)}
.br-deux_avant-back svg{display:none}
.br-deux_avant-back.br-deux_avant-shown{background:#e9e1ff}
.br-deux_avant-back.br-deux_avant-shown svg{display:block;opacity:.85}
.br-deux_avant-target{outline:3px dashed #ffd25c;outline-offset:4px}
.br-deux_avant-tag{position:absolute;bottom:-24px;left:0;right:0;text-align:center;font-size:12px;opacity:.75}
.br-deux_avant-empty{background:transparent;box-shadow:inset 0 0 0 2px rgba(255,255,255,.15)}
.br-deux_avant-in{animation:br-deux_avant-slide .22s ease-out}
@keyframes br-deux_avant-slide{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}
.br-deux_avant-good{border-color:#5be38a}
.br-deux_avant-wrong{border-color:#ff5c6c}
.br-deux_avant-btns{display:flex;gap:14px;width:100%;max-width:380px;margin-top:10px}
.br-deux_avant-btn{flex:1;min-height:64px;border:0;border-radius:18px;font:inherit;font-size:20px;font-weight:700;
  color:#fff;cursor:pointer;touch-action:manipulation;transition:transform .1s,opacity .15s}
.br-deux_avant-btn:active{transform:scale(.96)}
.br-deux_avant-btn:disabled{opacity:.4;cursor:default}
.br-deux_avant-btn:focus-visible{outline:3px solid #ffd25c;outline-offset:2px}
.br-deux_avant-no{background:#5a4a8a}
.br-deux_avant-yes{background:#7c5cff}
.br-deux_avant-btn small{display:block;font-size:12px;font-weight:500;opacity:.75}
`;

  function injectStyle() {
    if (document.getElementById('br-deux_avant-style')) return;
    const style = document.createElement('style');
    style.id = 'br-deux_avant-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function poolSize(level) { return Math.min(SHAPES.length, 3 + level); }

  function start(ctx) {
    injectStyle();
    const esc = ctx.esc;
    const timers = new Set();
    let stopped = false;
    let level = Math.max(1, Math.min(MAX_LEVEL, Math.round(ctx.level) || 1));
    let seq = [];          // indices de formes déjà distribuées
    let open = false;
    let revealed = false;
    let streak = 0;
    let errorsAtLevel = 0;
    let t0 = 0;

    const wrap = document.createElement('div');
    wrap.className = 'br-deux_avant-wrap';
    wrap.innerHTML =
      '<div class="br-deux_avant-q" data-q aria-live="polite"></div>' +
      '<div class="br-deux_avant-row" data-row></div>' +
      '<div class="br-deux_avant-btns">' +
      '<button type="button" class="br-deux_avant-btn br-deux_avant-no" data-ans="no" disabled>Non<small>←</small></button>' +
      '<button type="button" class="br-deux_avant-btn br-deux_avant-yes" data-ans="yes" disabled>Oui<small>→</small></button>' +
      '</div>';
    ctx.root.appendChild(wrap);
    const row = wrap.querySelector('[data-row]');
    const q = wrap.querySelector('[data-q]');
    const buttons = wrap.querySelectorAll('[data-ans]');

    function later(fn, ms) {
      const t = setTimeout(() => { timers.delete(t); if (!stopped) fn(); }, ms);
      timers.add(t);
    }

    function setButtons(on) { buttons.forEach((b) => { b.disabled = !on; }); }

    function colorFor(shapeIdx) { return level >= 4 ? MONO : COLORS[shapeIdx % COLORS.length]; }

    function shapeSvg(shapeIdx) {
      const shape = SHAPES[shapeIdx];
      return `<svg viewBox="0 0 100 100" role="img" aria-label="${esc(shape.name)}">` +
        `<g fill="${esc(colorFor(shapeIdx))}" stroke="#2a1d55" stroke-width="3">${shape.svg}</g></svg>`;
    }

    function drawSymbol() {
      const size = poolSize(level);
      const k = seq.length;
      if (k >= 2 && ctx.rng() < MATCH_CHANCE) return seq[k - 2];
      let pick = Math.floor(ctx.rng() * size);
      if (k >= 2 && pick === seq[k - 2]) pick = (pick + 1 + Math.floor(ctx.rng() * (size - 1))) % size;
      return pick;
    }

    function cardHtml(shapeIdx, cls, tag) {
      if (shapeIdx === undefined) return `<div class="br-deux_avant-card br-deux_avant-small br-deux_avant-empty">${tag}</div>`;
      return `<div class="br-deux_avant-card ${cls}">${shapeSvg(shapeIdx)}${tag}</div>`;
    }

    function render(animate) {
      const k = seq.length;
      const hiddenCls = `br-deux_avant-small br-deux_avant-back${revealed ? ' br-deux_avant-shown' : ''}`;
      const twoBack = k >= 3 ? seq[k - 3] : undefined;
      const oneBack = k >= 2 ? seq[k - 2] : undefined;
      row.innerHTML =
        cardHtml(twoBack, `${hiddenCls} br-deux_avant-target`, '<span class="br-deux_avant-tag">il y a 2</span>') +
        cardHtml(oneBack, hiddenCls, '<span class="br-deux_avant-tag">il y a 1</span>') +
        cardHtml(seq[k - 1], `br-deux_avant-big${animate && !ctx.reducedMotion ? ' br-deux_avant-in' : ''}`, '');
    }

    function deal() {
      seq = [...seq.slice(-2), drawSymbol()];
      render(true);
    }

    function intro() {
      q.textContent = 'Retiens cette forme…';
      seq = [drawSymbol()];
      row.innerHTML = cardHtml(undefined, '', '') + cardHtml(undefined, '', '') +
        cardHtml(seq[0], `br-deux_avant-big${ctx.reducedMotion ? '' : ' br-deux_avant-in'}`, '');
      later(() => {
        q.textContent = 'Et celle-ci…';
        seq = [...seq, drawSymbol()];
        row.innerHTML = cardHtml(undefined, '', '') +
          cardHtml(seq[0], 'br-deux_avant-small br-deux_avant-back', '<span class="br-deux_avant-tag">il y a 1</span>') +
          cardHtml(seq[1], `br-deux_avant-big${ctx.reducedMotion ? '' : ' br-deux_avant-in'}`, '');
      }, INTRO_STEP_MS);
      later(() => { deal(); openAnswer(); }, INTRO_STEP_MS * 2);
    }

    function openAnswer() {
      q.textContent = 'Même forme qu’il y a 2 cartes ?';
      open = true;
      t0 = performance.now();
      setButtons(true);
    }

    function adjustLevel(correct) {
      if (correct) {
        streak += 1;
        if (streak >= LEVEL_UP_STREAK && level < MAX_LEVEL) { level += 1; streak = 0; errorsAtLevel = 0; ctx.setLevel(level); }
        return;
      }
      streak = 0;
      errorsAtLevel += 1;
      if (errorsAtLevel >= LEVEL_DOWN_ERRORS && level > 1) { level -= 1; errorsAtLevel = 0; ctx.setLevel(level); }
    }

    function answer(saysYes) {
      if (!open || stopped) return;
      open = false;
      setButtons(false);
      const k = seq.length;
      const isMatch = seq[k - 1] === seq[k - 3];
      const correct = saysYes === isMatch;
      const rt = Math.round(performance.now() - t0);
      const big = row.querySelector('.br-deux_avant-big');
      if (correct) ctx.hit({ rt }); else ctx.miss({ rt });
      adjustLevel(correct);
      if (big) big.classList.add(correct ? 'br-deux_avant-good' : 'br-deux_avant-wrong');
      if (!correct) {
        revealed = true;
        row.querySelectorAll('.br-deux_avant-back').forEach((c) => c.classList.add('br-deux_avant-shown'));
        q.textContent = isMatch ? 'C’était la même forme' : 'Ce n’était pas la même forme';
      } else {
        revealed = false;
      }
      later(() => { deal(); openAnswer(); }, correct ? FEEDBACK_MS : FEEDBACK_MS * 3);
    }

    function onClick(e) {
      const btn = e.target.closest('[data-ans]');
      if (btn && wrap.contains(btn)) answer(btn.dataset.ans === 'yes');
    }

    function onKey(e) {
      if (e.key === 'ArrowRight') { e.preventDefault(); answer(true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); answer(false); }
    }

    wrap.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey);
    if (typeof ctx.onTimeUp === 'function') ctx.onTimeUp(() => { open = false; setButtons(false); });
    ctx.setLevel(level);
    intro();

    return {
      stop() {
        stopped = true;
        open = false;
        timers.forEach((t) => clearTimeout(t));
        timers.clear();
        wrap.removeEventListener('click', onClick);
        document.removeEventListener('keydown', onKey);
        wrap.remove();
      },
    };
  }

  Brain.register({
    id: ID,
    name: 'Deux avant',
    domain: 'memoire',
    icon: '🃏',
    color: '#7c5cff',
    seconds: 45,
    howto: [
      'Une nouvelle carte arrive à chaque réponse ; les précédentes se retournent.',
      'La forme est-elle la même que celle d’il y a DEUX cartes ? Oui (→) ou Non (←).',
      'Plus tu enchaînes, plus il y a de formes à distinguer.',
    ],
    start,
  });
})();
