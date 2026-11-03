/* Méninges — « Deux avant » (mémoire de travail, N-back : 2, puis 3, puis 4 cartes avant).
   Une carte arrive ; les précédentes sont retournées. Le symbole de la carte actuelle est-il le même que celui
   d'il y a N cartes ? Oui (→) / Non (←). Erreur → les cartes cachées se révèlent jusqu'à la bonne réponse suivante.
   Partie SANS FIN : le moteur gère les 3 vies ; chaque carte a un délai de réponse (trop lent = une vie).

   Niveaux (N = cartes en arrière, s = niveau dans la série) :
     1-15  2 avant : 4 → 10 formes (niv. 1-7), monochrome dès le niv. 6, leurres dès le niv. 9 (10 % → 40 %)
     16-30 3 avant : 5 → 10 formes (niv. 16-21), monochrome dès le niv. 21, leurres dès le niv. 22 (10 % → 45 %)
     31+   4 avant : 6 → 10 formes (niv. 31-35), monochrome dès le niv. 34, leurres 15 % → 60 % (niv. 40+)
   Un leurre = une forme vue N−1 ou N+1 cartes avant (piège classique du N-back).
   Délai par carte, qui redémarre plus large à chaque nouveau N : 3000 ms → ≈ 1690 (niv. 15) ; 3200 → ≈ 1660
   (niv. 30) ; 3000 → ≈ 1710 (niv. 40), ≈ 1180 (niv. 50), ≈ 1000 (niv. 60), jamais sous 900 ms.
   Changer de N (en montant ou en descendant) relance la présentation des N premières cartes. */
(function () {
  'use strict';

  const ID = 'deux_avant';
  const P = 'br-deux_avant-';
  const MATCH_CHANCE = 0.4;
  const INTRO_STEP_MS = 1000;
  const FEEDBACK_MS = 260;
  const LEVEL_UP_STREAK = 5;
  const LEVEL_DOWN_ERRORS = 2;
  const WIN_DECAY = 0.9;
  // Séries : premier niveau, N, formes au départ, niveau (dans la série) du passage en monochrome,
  // début des leurres, leurres max, délai de départ, délai plancher.
  const TIERS = [
    { from: 1, n: 2, pool: 4, mono: 5, lureAt: 8, lureMax: 0.4, st: 3000, fl: 1300 },
    { from: 16, n: 3, pool: 5, mono: 5, lureAt: 6, lureMax: 0.45, st: 3200, fl: 1200 },
    { from: 31, n: 4, pool: 6, mono: 3, lureAt: 0, lureMax: 0.6, st: 3000, fl: 900 },
  ];

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

  function cfgOf(level) {
    const tier = TIERS.filter((t) => level >= t.from).pop();
    const s = level - tier.from;
    return {
      n: tier.n,
      pool: Math.min(SHAPES.length, tier.pool + s),
      mono: s >= tier.mono,
      lure: s < tier.lureAt ? 0 : Math.min(tier.lureMax, (tier.n === 4 ? 0.15 : 0.1) + 0.05 * (s - tier.lureAt)),
      win: Math.round(tier.fl + (tier.st - tier.fl) * Math.pow(WIN_DECAY, s)),
    };
  }

  const CSS = `
.${P}wrap{display:flex;flex-direction:column;align-items:center;gap:18px;padding:14px 16px 22px;box-sizing:border-box;
  width:100%;overflow-x:clip;color:var(--br-text,#f3efff);user-select:none;-webkit-user-select:none}
.${P}q{font-size:17px;font-weight:600;text-align:center;min-height:46px;line-height:1.35}
.${P}row{--sw:74px;--sh:100px;--bw:132px;--bh:178px;--gap:12px;display:flex;align-items:flex-end;justify-content:center;
  gap:var(--gap);width:100%;max-width:380px;min-height:190px}
.${P}n3{--sw:60px;--sh:82px;--bw:120px;--bh:162px;--gap:10px}
.${P}n4{--sw:50px;--sh:68px;--bw:108px;--bh:146px;--gap:8px}
.${P}card{position:relative;flex:none;border-radius:16px;display:flex;align-items:center;justify-content:center;
  background:#fbf8ff;box-shadow:0 8px 22px rgba(0,0,0,.3)}
.${P}card svg{width:72%;height:72%}
.${P}small{width:var(--sw);height:var(--sh)}
.${P}big{box-sizing:border-box;width:var(--bw);height:var(--bh);border:4px solid transparent;transition:border-color .15s}
.${P}back{background:repeating-linear-gradient(45deg,#3b2a6e 0 10px,#4a3685 10px 20px)}
.${P}back svg{display:none}
.${P}back.${P}shown{background:#e9e1ff}
.${P}back.${P}shown svg{display:block;opacity:.85}
.${P}target{outline:3px dashed #ffd25c;outline-offset:4px}
.${P}tag{position:absolute;bottom:-24px;left:-6px;right:-6px;text-align:center;font-size:12px;opacity:.75;white-space:nowrap}
.${P}n4 .${P}tag{font-size:11px}
.${P}empty{background:transparent;box-shadow:inset 0 0 0 2px rgba(255,255,255,.15)}
.${P}in{animation:${P}slide .22s ease-out}
@keyframes ${P}slide{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}
.${P}good{border-color:#5be38a}
.${P}wrong{border-color:#ff5c6c}
.${P}timer{width:100%;max-width:380px;height:6px;margin-top:14px;border-radius:3px;background:rgba(255,255,255,.12)}
.${P}timer b{display:block;height:100%;border-radius:3px;background:#7c5cff;transform-origin:left center;transform:scaleX(0)}
.${P}timer b.${P}run{animation:${P}shrink linear forwards}
@keyframes ${P}shrink{from{transform:scaleX(1)}to{transform:scaleX(0)}}
.${P}btns{display:flex;gap:14px;width:100%;max-width:380px}
.${P}btn{flex:1;min-height:64px;border:0;border-radius:18px;font:inherit;font-size:20px;font-weight:700;
  color:#fff;cursor:pointer;touch-action:manipulation;transition:transform .1s,opacity .15s}
.${P}btn:active{transform:scale(.96)}
.${P}btn:disabled{opacity:.4;cursor:default}
.${P}btn:focus-visible{outline:3px solid #ffd25c;outline-offset:2px}
.${P}no{background:#5a4a8a}
.${P}yes{background:#7c5cff}
.${P}btn small{display:block;font-size:12px;font-weight:500;opacity:.75}
/* Écran bas (téléphone en paysage, ~300 px de jeu) : cartes et boutons plus petits, tout reste visible. */
@media (max-height:520px){.${P}wrap{gap:8px;padding:4px 12px 8px}.${P}q{min-height:0;font-size:15px}
  .${P}row{--sw:46px;--sh:62px;--bw:84px;--bh:112px;--gap:8px;min-height:116px}
  .${P}n3{--sw:42px;--sh:56px;--bw:80px;--bh:106px}.${P}n4{--sw:38px;--sh:50px;--bw:76px;--bh:100px;--gap:6px}
  .${P}tag{font-size:10px;bottom:-17px}.${P}timer{margin-top:12px}.${P}btn{min-height:50px}}
`;

  function injectStyle() {
    if (document.getElementById(P + 'style')) return;
    const style = document.createElement('style');
    style.id = P + 'style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function start(ctx) {
    injectStyle();
    const esc = ctx.esc;
    const timers = new Set();
    const floorLevel = Math.max(1, Math.round(Number(ctx.level) || 1));
    let stopped = false;
    let level = floorLevel;
    let curN = cfgOf(level).n;
    let seq = [];          // indices de formes déjà distribuées (les N+2 dernières)
    let open = false;
    let revealed = false;
    let streak = 0;
    let errorsAtLevel = 0;
    let t0 = 0;
    let deadline = 0;

    const wrap = document.createElement('div');
    wrap.className = P + 'wrap';
    wrap.innerHTML =
      `<div class="${P}q" data-q aria-live="polite"></div>` +
      `<div class="${P}row" data-row></div>` +
      `<div class="${P}timer" aria-hidden="true"><b data-bar></b></div>` +
      `<div class="${P}btns">` +
      `<button type="button" class="${P}btn ${P}no" data-ans="no" disabled>Non<small>←</small></button>` +
      `<button type="button" class="${P}btn ${P}yes" data-ans="yes" disabled>Oui<small>→</small></button>` +
      '</div>';
    ctx.root.appendChild(wrap);
    const row = wrap.querySelector('[data-row]');
    const q = wrap.querySelector('[data-q]');
    const bar = wrap.querySelector('[data-bar]');
    const buttons = wrap.querySelectorAll('[data-ans]');

    function later(fn, ms) {
      const t = setTimeout(() => { timers.delete(t); if (!stopped) fn(); }, ms);
      timers.add(t);
      return t;
    }
    function cancel(t) { if (t) { clearTimeout(t); timers.delete(t); } }

    function setButtons(on) { buttons.forEach((b) => { b.disabled = !on; }); }

    function colorFor(shapeIdx) { return cfgOf(level).mono ? MONO : COLORS[shapeIdx % COLORS.length]; }

    function shapeSvg(shapeIdx) {
      const shape = SHAPES[shapeIdx];
      return `<svg viewBox="0 0 100 100" role="img" aria-label="${esc(shape.name)}">` +
        `<g fill="${esc(colorFor(shapeIdx))}" stroke="#2a1d55" stroke-width="3">${shape.svg}</g></svg>`;
    }

    function drawSymbol() {
      const cfg = cfgOf(level);
      const n = curN;
      const k = seq.length;
      const target = k >= n ? seq[k - n] : -1;
      if (target >= 0 && ctx.rng() < MATCH_CHANCE) return target;
      if (target >= 0 && cfg.lure && ctx.rng() < cfg.lure) {
        const lures = [seq[k - n + 1], seq[k - n - 1]].filter((s) => s !== undefined && s !== target);
        if (lures.length) return lures[Math.floor(ctx.rng() * lures.length) % lures.length];
      }
      const size = Math.max(cfg.pool, target + 1);
      let pick = Math.floor(ctx.rng() * size) % size;
      if (pick === target) pick = (pick + 1 + Math.floor(ctx.rng() * (size - 1))) % size;
      return pick;
    }

    function cardHtml(shapeIdx, cls, tag) {
      if (shapeIdx === undefined) return `<div class="${P}card ${P}small ${P}empty">${tag}</div>`;
      return `<div class="${P}card ${cls}">${shapeSvg(shapeIdx)}${tag}</div>`;
    }

    function render(animate) {
      const k = seq.length;
      const hiddenCls = `${P}small ${P}back${revealed ? ' ' + P + 'shown' : ''}`;
      let html = '';
      for (let i = curN; i >= 1; i--) {
        const cls = hiddenCls + (i === curN ? ' ' + P + 'target' : '');
        html += cardHtml(k - 1 - i >= 0 ? seq[k - 1 - i] : undefined, cls, `<span class="${P}tag">il y a ${i}</span>`);
      }
      html += cardHtml(seq[k - 1], `${P}big${animate && !ctx.reducedMotion ? ' ' + P + 'in' : ''}`, '');
      row.className = `${P}row ${P}n${curN}`;
      row.innerHTML = html;
    }

    function deal() {
      seq = [...seq.slice(-(curN + 1)), drawSymbol()];
      render(true);
    }

    function intro(announce) {
      curN = cfgOf(level).n;
      seq = [];
      revealed = false;
      for (let s = 0; s < curN; s++) {
        later(() => {
          const first = s === 0;
          q.textContent = first ? (announce ? `Maintenant : ${curN} cartes avant ! Retiens cette forme…` : 'Retiens cette forme…')
            : 'Et celle-ci…';
          seq = [...seq, drawSymbol()];
          render(true);
        }, s * INTRO_STEP_MS);
      }
      later(() => { deal(); openAnswer(); }, curN * INTRO_STEP_MS);
    }

    function openAnswer() {
      const win = cfgOf(level).win;
      q.textContent = `Même forme qu’il y a ${curN} cartes ?`;
      open = true;
      t0 = performance.now();
      setButtons(true);
      bar.classList.remove(P + 'run');
      void bar.offsetWidth; // relance l'animation de la barre
      bar.style.animationDuration = win + 'ms';
      bar.classList.add(P + 'run');
      deadline = later(() => answer(null), win);
    }

    function adjustLevel(correct) {
      if (correct) {
        streak += 1;
        if (streak >= LEVEL_UP_STREAK) { level += 1; streak = 0; errorsAtLevel = 0; ctx.setLevel(level); }
        return;
      }
      streak = 0;
      errorsAtLevel += 1;
      if (errorsAtLevel >= LEVEL_DOWN_ERRORS && level > floorLevel) {
        level -= 1; errorsAtLevel = 0; ctx.setLevel(level);
      }
    }

    function next() {
      if (cfgOf(level).n !== curN) { intro(true); return; }
      deal();
      openAnswer();
    }

    // saysYes : true (Oui), false (Non) ou null (délai dépassé).
    function answer(saysYes) {
      if (!open || stopped) return;
      open = false;
      cancel(deadline);
      setButtons(false);
      bar.classList.remove(P + 'run');
      const k = seq.length;
      const isMatch = seq[k - 1] === seq[k - 1 - curN];
      const correct = saysYes === isMatch;
      const slow = saysYes === null;
      const rt = slow ? cfgOf(level).win : Math.round(performance.now() - t0);
      const big = row.querySelector('.' + P + 'big');
      if (big) big.classList.add(correct ? P + 'good' : P + 'wrong');
      if (!correct) {
        revealed = true;
        row.querySelectorAll('.' + P + 'back').forEach((c) => c.classList.add(P + 'shown'));
        q.textContent = (slow ? 'Trop lent ! ' : '') + (isMatch ? 'C’était la même forme' : 'Ce n’était pas la même forme');
      } else {
        revealed = false;
      }
      if (correct) ctx.hit({ rt }); else ctx.miss({ rt });
      if (stopped) return;
      adjustLevel(correct);
      later(next, correct ? FEEDBACK_MS : FEEDBACK_MS * 3);
    }

    function onClick(e) {
      const btn = e.target.closest('[data-ans]');
      if (btn && wrap.contains(btn)) answer(btn.dataset.ans === 'yes');
    }

    function onKey(e) {
      if (e.repeat || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); answer(true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); answer(false); }
    }

    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : tout s'arrête (aucune vie perdue loin de l'écran) ; au retour, les N cartes
    // sont présentées à nouveau.
    let away = false;
    function onPauseChange(paused) {
      if (stopped) return;
      if (paused) {
        timers.forEach((t) => clearTimeout(t));
        timers.clear();
        open = false;
        away = true;
        setButtons(false);
        bar.classList.remove(P + 'run');
      } else if (away) {
        away = false;
        intro(false);
      }
    }

    wrap.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey);
    if (ctx.onPause) ctx.onPause(function () { onPauseChange(true); });
    if (ctx.onResume) ctx.onResume(function () { onPauseChange(false); });
    ctx.setLevel(level);
    intro(false);

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
    seconds: null,
    howto: [
      'Une nouvelle carte arrive à chaque réponse ; les précédentes se retournent. La forme est-elle la même que celle d’il y a DEUX cartes ? Oui (→) ou Non (←).',
      'Réponds avant la fin de la barre : trop lent ou faux, tu perds une vie. Sans fin : la partie s’arrête quand tu n’as plus de vie.',
      'Plus tu montes, plus il y a de formes et de pièges ; aux paliers élevés, il faut se souvenir de 3, puis 4 cartes avant.',
    ],
    start,
  });
})();
