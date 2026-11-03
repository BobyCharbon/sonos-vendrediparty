/* Méninges — « Pareil ? » (vitesse) : le symbole est-il le même que celui de la carte d'avant ?
   Une carte glisse de droite à gauche ; Oui / Non en bas (clavier : → = Oui, ← = Non). Partie SANS FIN : le moteur
   gère les 3 vies ; chaque carte a un délai de réponse (trop lent = une vie).

   Niveaux (cfgOf) :
     1-2   4 symboles en couleurs          3-4   6 symboles en couleurs
     5-7   8 symboles, tous de la même couleur (plus d'indice de couleur)
     8-10  10 symboles, faux « pareil » proches (carré/losange, hexagone…)
     11-15 14 symboles proches             16-25 tous les symboles (24), familles de quasi-jumeaux
     26+   « Piège couleur » : couleurs au hasard, seule la forme compte ; la couleur trompe de plus en plus.
   Délai : 2500 ms au niveau 1, × 0,94 par niveau vers 550 ms (≈ 1670 ms niv. 10, 1150 niv. 20, 725 niv. 40).
   Faux symboles proches : 0 → 95 % (atteint au niveau 29) ; piège couleur 50 % (niv. 26) → 90 % (niv. 40+).
   Au-delà du niveau 40 : le délai continue de raccourcir (≈ 600 ms niv. 60), sans jamais descendre sous 550 ms. */
(function () {
  'use strict';

  const ID = 'pareil';
  const P = 'br-pareil-';
  const COLOR = '#4f8cff';
  const P_MATCH = 0.45;          // part des cartes « pareilles »
  const MAX_RUN = 3;             // jamais plus de 3 réponses identiques d'affilée
  const UP_AFTER = 6;            // bonnes réponses d'affilée pour monter d'un niveau
  const DOWN_AFTER = 2;          // erreurs d'affilée pour descendre d'un niveau
  const FIRST_MEMO_MS = 1100;
  const MEMO_MS = 900;
  const LEAVE_MS = 420;
  const PRESS_MS = 160;
  const WIN_START = 2500;        // délai de réponse au niveau 1
  const WIN_FLOOR = 550;         // limite humaine visée
  const WIN_DECAY = 0.94;
  const LURE_LEVEL = 26;         // début du piège couleur

  // ---------- Symboles (SVG originaux, viewBox 0 0 100 100) ----------
  function polyPoints(n, r, rotDeg, inner) {
    const pts = [];
    const steps = inner ? n * 2 : n;
    for (let i = 0; i < steps; i++) {
      const a = (rotDeg + (360 / steps) * i) * Math.PI / 180;
      const rr = inner && i % 2 ? inner : r;
      pts.push((50 + rr * Math.cos(a)).toFixed(1) + ',' + (50 + rr * Math.sin(a)).toFixed(1));
    }
    return pts.join(' ');
  }
  const poly = (n, r, rot, inner) => (c) => `<polygon fill="${c}" points="${polyPoints(n, r, rot, inner)}"/>`;
  const path = (d, extra) => (c) => `<path fill="${c}" ${extra || ''} d="${d}"/>`;
  const ringPath = (r) => `M10 50a40 40 0 1 0 80 0a40 40 0 1 0-80 0zM${50 - r} 50a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0-${2 * r} 0z`;
  const PLUS = 'M38 10h24v28h28v24H62v28H38V62H10V38h28z';

  const SHAPES = {
    circle: (c) => `<circle cx="50" cy="50" r="40" fill="${c}"/>`,
    ring: path(ringPath(19), 'fill-rule="evenodd"'),
    ringThin: path(ringPath(28), 'fill-rule="evenodd"'),
    tri: poly(3, 46, -90),
    triDown: poly(3, 46, 90),
    triL: poly(3, 46, 180),
    triR: poly(3, 46, 0),
    square: poly(4, 50, 45),
    diamond: poly(4, 46, -90),
    pent: poly(5, 44, -90),
    pentDown: poly(5, 44, 90),
    hex: poly(6, 44, 0),
    hexV: poly(6, 44, -90),
    hept: poly(7, 44, -90),
    oct: poly(8, 44, 22.5),
    star4: poly(4, 46, -90, 17),
    star5: poly(5, 46, -90, 20),
    star6: poly(6, 46, -90, 24),
    star7: poly(7, 46, -90, 26),
    star8: poly(8, 46, -90, 28),
    plus: path(PLUS),
    cross: path(PLUS, 'transform="rotate(45 50 50)"'),
    heart: path('M50 88C20 66 8 50 8 33C8 19 19 10 31 10c9 0 15 5 19 12c4-7 10-12 19-12c12 0 23 9 23 23c0 17-12 33-42 55z'),
    moon: path('M60 8A42 42 0 1 0 92 66A33 33 0 1 1 60 8z'),
    bolt: path('M58 4L18 56h26l-8 40l46-56H56z'),
  };
  const PALETTE = {
    circle: '#e5484d', tri: '#30a46c', square: '#4f8cff', star5: '#f5a524', heart: '#d6409f',
    plus: '#12a594', moon: '#8e4ec6', bolt: '#e5484d',
  };
  const LURE_COLORS = ['#e5484d', '#30a46c', '#4f8cff', '#f5a524', '#d6409f', '#8e4ec6'];
  // Familles de symboles faciles à confondre (choisis comme « faux pareil »).
  const NEAR = [
    ['tri', 'triDown', 'triL', 'triR'], ['square', 'diamond'], ['pent', 'pentDown', 'hex', 'hexV', 'hept', 'oct'],
    ['star4', 'star5', 'star6', 'star7', 'star8'], ['circle', 'ring', 'ringThin', 'oct'], ['plus', 'cross'],
    ['heart', 'moon'],
  ];
  function nearOf(key) {
    return NEAR.filter((g) => g.includes(key)).flat().filter((k) => k !== key);
  }

  const BASE4 = ['circle', 'tri', 'square', 'star5'];
  const BASE6 = BASE4.concat(['heart', 'plus']);
  const BASE8 = BASE6.concat(['moon', 'bolt']);
  const MID = BASE6.concat(['diamond', 'hex', 'triDown', 'star6']);
  const HARD = MID.concat(['cross', 'ring', 'pent', 'star4']);
  const ALL = Object.keys(SHAPES);
  // [premier niveau, symboles, mode] ; mode : couleurs (chaque symbole sa couleur), mono, leurre (couleur au hasard).
  const STAGES = [
    [1, BASE4, 'couleurs'], [3, BASE6, 'couleurs'], [5, BASE8, 'mono'], [8, MID, 'mono'],
    [11, HARD, 'mono'], [16, ALL, 'mono'], [LURE_LEVEL, ALL, 'leurre'],
  ];

  function cfgOf(lv) {
    const stage = STAGES.filter((s) => lv >= s[0]).pop();
    return {
      pool: stage[1],
      mode: stage[2],
      near: lv < 3 ? 0 : Math.min(0.95, 0.1 + 0.03 * lv),
      trap: stage[2] === 'leurre' ? Math.min(0.9, 0.5 + 0.03 * (lv - LURE_LEVEL)) : 0,
      win: Math.round(WIN_FLOOR + (WIN_START - WIN_FLOOR) * Math.pow(WIN_DECAY, lv - 1)),
      d: Math.max(110, 300 - 6 * (lv - 1)),
    };
  }

  function svgFor(key, color) {
    return `<svg viewBox="0 0 100 100" aria-hidden="true">${SHAPES[key](color)}</svg>`;
  }

  // ---------- Styles (injectés une fois) ----------
  const CSS = `
.${P}wrap{display:flex;flex-direction:column;align-items:center;gap:14px;box-sizing:border-box;width:100%;height:100%;
  min-height:440px;padding:10px 16px calc(14px + env(safe-area-inset-bottom,0px));user-select:none;-webkit-user-select:none;
  -webkit-touch-callout:none}
.${P}prompt{margin:0;min-height:46px;font-size:17px;font-weight:650;text-align:center;line-height:1.35}
.${P}stage{position:relative;flex:1;align-self:stretch;margin:0 -16px;min-height:250px;overflow:hidden}
.${P}card{position:absolute;left:50%;top:50%;width:min(66vw,260px);aspect-ratio:4/5;margin:0;border-radius:24px;
  background:#fff;box-shadow:0 10px 30px rgba(20,30,60,.18),0 1px 0 rgba(0,0,0,.04);display:flex;align-items:center;
  justify-content:center;transform:translate(-50%,-50%);transition:transform var(--d,260ms) cubic-bezier(.2,.8,.2,1),
  opacity var(--d,260ms) ease}
.${P}card svg{width:62%;height:auto;display:block}
.${P}enter{transform:translate(70%,-50%) rotate(7deg);opacity:0}
.${P}out{transform:translate(-170%,-50%) rotate(-8deg);opacity:0}
.${P}rm .${P}card{transition:opacity 120ms linear}
.${P}rm .${P}enter,.${P}rm .${P}out{transform:translate(-50%,-50%)}
.${P}mark{position:absolute;top:10px;right:10px;width:34px;height:34px;border-radius:50%;display:none;align-items:center;
  justify-content:center;color:#fff;font-size:19px;font-weight:800;font-style:normal}
.${P}ok .${P}mark{display:flex;background:#30a46c}
.${P}ok .${P}mark::after{content:'✓'}
.${P}ko .${P}mark{display:flex;background:#e5484d}
.${P}ko .${P}mark::after{content:'✕'}
.${P}slow .${P}mark{display:flex;background:#e5484d}
.${P}slow .${P}mark::after{content:'⏱'}
.${P}bar{position:absolute;left:16px;right:16px;bottom:14px;height:5px;border-radius:3px;background:${COLOR};
  transform-origin:left center;animation:${P}shrink linear forwards}
@keyframes ${P}shrink{from{transform:scaleX(1)}to{transform:scaleX(0)}}
.${P}btns{display:flex;gap:12px;width:100%;max-width:420px}
.${P}btn{flex:1;min-height:68px;border:0;border-radius:20px;color:#fff;font:inherit;font-size:21px;font-weight:750;
  display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer;touch-action:manipulation;
  -webkit-tap-highlight-color:transparent;transition:transform 90ms ease,opacity 150ms ease,filter 90ms ease}
.${P}btn i{font-style:normal;font-size:22px}
.${P}btn kbd{display:none;font:inherit;font-size:12px;font-weight:600;opacity:.8;border:1px solid rgba(255,255,255,.6);
  border-radius:6px;padding:1px 6px}
@media (hover:hover) and (pointer:fine){.${P}btn kbd{display:inline-block}}
.${P}no{background:#e5484d}
.${P}yes{background:#30a46c}
.${P}btn:disabled{opacity:.4;cursor:default}
.${P}press{transform:scale(.95);filter:brightness(1.12)}
@media (prefers-color-scheme:dark){.${P}card{background:#22283a;box-shadow:0 10px 30px rgba(0,0,0,.45)}}
`;
  function injectStyle() {
    if (document.getElementById(P + 'style')) return;
    const s = document.createElement('style');
    s.id = P + 'style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ---------- Partie ----------
  function start(ctx) {
    injectStyle();
    const rng = ctx.rng;
    const esc = ctx.esc;
    const rm = !!ctx.reducedMotion;
    const floorLevel = Math.max(1, Math.floor(Number(ctx.level) || 1));
    let level = floorLevel;
    let streak = 0;
    let missRun = 0;
    let prevKey = null;
    let curKey = null;
    let prevColor = null;
    let curColor = null;
    let curMode = null;
    let phase = 'memo';           // memo | ask | over
    let shownAt = 0;
    let deadline = 0;
    let card = null;
    let answers = [];
    const timers = new Set();

    const later = (fn, ms) => {
      const t = setTimeout(() => { timers.delete(t); if (phase !== 'over') fn(); }, ms);
      timers.add(t);
      return t;
    };
    const cancel = (t) => { if (t) { clearTimeout(t); timers.delete(t); } };
    const pick = (arr) => arr[Math.floor(rng() * arr.length) % arr.length];

    ctx.root.innerHTML = `
<div class="${P}wrap${rm ? ' ' + P + 'rm' : ''}">
  <p class="${P}prompt" aria-live="polite"></p>
  <div class="${P}stage"></div>
  <div class="${P}btns">
    <button type="button" class="${P}btn ${P}no" data-a="no" disabled><i>✕</i>${esc('Non')}<kbd>←</kbd></button>
    <button type="button" class="${P}btn ${P}yes" data-a="yes" disabled><i>✓</i>${esc('Oui')}<kbd>→</kbd></button>
  </div>
</div>`;
    const wrap = ctx.root.querySelector('.' + P + 'wrap');
    const prompt = wrap.querySelector('.' + P + 'prompt');
    const stage = wrap.querySelector('.' + P + 'stage');
    const btns = Array.from(wrap.querySelectorAll('[data-a]'));

    const setPrompt = (text) => { prompt.innerHTML = esc(text); };
    const setButtons = (on) => btns.forEach((b) => { b.disabled = !on; });

    function showCard(key, color, cfg, asking) {
      const el = document.createElement('div');
      el.className = P + 'card ' + P + 'enter';
      el.dataset.k = key;
      el.style.setProperty('--d', cfg.d + 'ms');
      const bar = asking ? `<b class="${P}bar" style="animation-duration:${cfg.win}ms"></b>` : '';
      el.innerHTML = svgFor(key, color) + `<i class="${P}mark"></i>` + bar;
      stage.appendChild(el);
      void el.offsetWidth; // force le départ de la transition
      el.classList.remove(P + 'enter');
      if (card) leave(card);
      card = el;
    }
    function leave(el) {
      el.classList.add(P + 'out');
      el.removeAttribute('data-k');
      later(() => el.remove(), LEAVE_MS);
    }

    function distractor(prev, cfg) {
      const close = nearOf(prev).filter((k) => cfg.pool.includes(k));
      if (close.length && rng() < cfg.near) return pick(close);
      return pick(cfg.pool.filter((k) => k !== prev));
    }
    // Piège couleur : la couleur dit souvent le contraire de la bonne réponse.
    function colorFor(key, match, cfg) {
      if (cfg.mode === 'couleurs') return PALETTE[key] || COLOR;
      if (cfg.mode === 'mono') return COLOR;
      if (!prevColor) return pick(LURE_COLORS);
      const others = LURE_COLORS.filter((c) => c !== prevColor);
      if (rng() >= cfg.trap) return pick(LURE_COLORS);
      return match ? pick(others) : prevColor;
    }
    function decideMatch() {
      let match = rng() < P_MATCH;
      const last = answers.slice(-MAX_RUN);
      if (last.length === MAX_RUN && last.every((v) => v === match)) match = !match;
      answers = answers.concat([match]).slice(-MAX_RUN);
      return match;
    }

    function memoText(first, mode) {
      if (mode === 'leurre') return 'Piège : seule la forme compte, pas la couleur. Retiens ce symbole…';
      return first ? 'Retiens ce symbole…' : 'Nouveau niveau : retiens ce symbole…';
    }

    function beginMemo(first) {
      phase = 'memo';
      setButtons(false);
      const cfg = cfgOf(level);
      curMode = cfg.mode;
      curKey = pick(cfg.pool);
      prevColor = null;
      curColor = colorFor(curKey, false, cfg);
      showCard(curKey, curColor, cfg, false);
      setPrompt(memoText(first, cfg.mode));
      later(nextAsk, (first ? FIRST_MEMO_MS : MEMO_MS) + (cfg.mode === 'leurre' ? MEMO_MS : 0));
    }

    function nextAsk() {
      const cfg = cfgOf(level);
      if (cfg.mode !== curMode) { beginMemo(false); return; }
      prevKey = curKey;
      prevColor = curColor;
      const match = decideMatch();
      curKey = match ? prevKey : distractor(prevKey, cfg);
      curColor = colorFor(curKey, match, cfg);
      showCard(curKey, curColor, cfg, true);
      phase = 'ask';
      setButtons(true);
      setPrompt('Même symbole que la carte d’avant ?');
      shownAt = performance.now();
      deadline = later(onSlow, cfg.win);
    }

    function adapt(ok) {
      if (ok) {
        missRun = 0;
        streak += 1;
        if (streak >= UP_AFTER) { level += 1; streak = 0; ctx.setLevel(level); }
        return;
      }
      streak = 0;
      missRun += 1;
      if (missRun >= DOWN_AFTER && level > floorLevel) { level -= 1; missRun = 0; ctx.setLevel(level); }
    }

    function answer(yes) {
      if (phase !== 'ask') return;
      cancel(deadline);
      const rt = Math.round(performance.now() - shownAt);
      const ok = yes === (curKey === prevKey);
      card.classList.add(P + (ok ? 'ok' : 'ko'));
      const btn = btns[yes ? 1 : 0];
      btn.classList.add(P + 'press');
      later(() => btn.classList.remove(P + 'press'), PRESS_MS);
      if (ok) ctx.hit({ rt }); else ctx.miss({ rt });
      adapt(ok);
      if (phase !== 'over') nextAsk();
    }

    function onSlow() {
      if (phase !== 'ask') return;
      card.classList.add(P + 'slow');
      ctx.miss({ rt: cfgOf(level).win });
      adapt(false);
      if (phase !== 'over') nextAsk();
    }

    function onPointer(e) {
      const b = e.target.closest('[data-a]');
      if (!b || b.disabled) return;
      e.preventDefault();
      answer(b.dataset.a === 'yes');
    }
    function onClick(e) { // activation au clavier (Entrée / Espace sur un bouton) : pas de pointerdown
      if (e.detail !== 0) return;
      const b = e.target.closest('[data-a]');
      if (b && !b.disabled) answer(b.dataset.a === 'yes');
    }
    function onKey(e) {
      if (e.repeat || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); answer(true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); answer(false); }
    }

    wrap.addEventListener('pointerdown', onPointer);
    wrap.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);

    ctx.setLevel(level);
    beginMemo(true);

    return {
      stop() {
        phase = 'over';
        timers.forEach((t) => clearTimeout(t));
        timers.clear();
        window.removeEventListener('keydown', onKey);
        wrap.removeEventListener('pointerdown', onPointer);
        wrap.removeEventListener('click', onClick);
        ctx.root.innerHTML = '';
      },
    };
  }

  window.Brain.register({
    id: ID,
    name: 'Pareil ?',
    domain: 'vitesse',
    icon: '⚡',
    color: COLOR,
    seconds: null,
    howto: [
      'Une carte apparaît, puis une autre la remplace. Le symbole est-il le même que sur la carte d’avant ? Oui ou Non (au clavier : → Oui, ← Non).',
      'Réponds avant la fin de la barre : trop lent ou faux, tu perds une vie. Sans fin : la partie s’arrête quand tu n’as plus de vie.',
      'Plus tu montes, plus les symboles se ressemblent et plus ça va vite. Plus loin, la couleur te piège : seule la forme compte.',
    ],
    start,
  });
})();
