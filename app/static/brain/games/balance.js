/* Méninges — « Plus lourd » (calcul) : deux plateaux portent chacun un calcul ; quel côté pèse le plus ?
   Gauche / Égal / Droite. Partie SANS FIN (vies du moteur) : chaque calcul a un délai qui raccourcit ; pas de
   réponse à temps = une vie. Les calculs se corsent sans limite : priorités, parenthèses, puissances, fractions,
   grands nombres, écarts de plus en plus serrés. */
(function () {
  'use strict';
  const ID = 'balance';
  const UP_AFTER = 3;          // bonnes réponses d'affilée pour monter d'un niveau
  const DOWN_AFTER = 2;        // erreurs d'affilée pour redescendre d'un niveau
  const FEEDBACK_MS = 380;     // la balance penche, puis calcul suivant
  const EQUAL_SHARE = 0.2;     // part des égalités
  const TILT_DEG = 9;
  const TRIES = 40;
  // Délai par calcul : 6,5 s au niveau 1, ~4,2 s au niveau 20, ~3,3 s au niveau 40, jamais sous 2,8 s.
  const answerMs = (lv) => Math.round(1000 * (2.8 + 3.7 * Math.pow(0.95, lv - 1)));
  // Écart entre les plateaux (part de la valeur) : 30 % au début, ~2 % au niveau 40, 1 % ensuite.
  const closeness = (lv) => Math.max(0.01, 0.3 * Math.pow(0.93, lv - 1));
  // Les nombres d'une famille grandissent avec les niveaux passés depuis son apparition (×2 après 25 niveaux).
  const scaleOf = (lv, from) => Math.min(6, 1 + Math.max(0, lv - from) * 0.04);

  const CSS = `
.br-balance-wrap{display:flex;flex-direction:column;flex:1 1 auto;min-height:360px;gap:12px;padding:12px 4px;
  box-sizing:border-box;color:var(--text,#f5f0ff);user-select:none;-webkit-user-select:none}
.br-balance-time{height:6px;border-radius:4px;background:rgba(139,92,246,.18);overflow:hidden}
.br-balance-time i{display:block;height:100%;width:100%;background:#a78bfa;border-radius:4px}
.br-balance-time.low i{background:var(--err,#ff6b6b)}
.br-balance-stage{flex:1;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:220px}
.br-balance-beam{position:relative;width:min(94%,360px);height:10px;border-radius:6px;background:linear-gradient(#c4b5fd,#7c3aed);
  transition:transform .32s cubic-bezier(.22,1,.36,1);transform-origin:50% 50%}
.br-balance-pan{position:absolute;top:10px;width:46%;display:flex;flex-direction:column;align-items:center}
.br-balance-pan.l{left:0}.br-balance-pan.r{right:0}
.br-balance-cord{width:2px;height:26px;background:#a78bfa}
.br-balance-plate{min-width:100%;box-sizing:border-box;padding:14px 6px 12px;border-radius:12px 12px 26px 26px;
  background:var(--card,#221a3d);border:2px solid #8b5cf6;font:700 clamp(16px,4.8vw,22px)/1.15 system-ui,sans-serif;
  text-align:center;overflow-wrap:anywhere;transition:transform .32s cubic-bezier(.22,1,.36,1),border-color .2s,box-shadow .2s}
.br-balance-plate.long{font-size:clamp(14px,4vw,18px)}
.br-balance-post{width:12px;height:120px;margin-top:-6px;background:linear-gradient(#7c3aed,#4c1d95);border-radius:6px 6px 0 0}
.br-balance-foot{width:120px;height:14px;border-radius:10px;background:#4c1d95}
.br-balance-pivot{position:absolute;left:50%;top:50%;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:#ede9fe;
  box-shadow:0 0 0 4px #7c3aed}
.br-balance-plate.ok{border-color:var(--ok,#3ddc97);box-shadow:0 0 0 4px rgba(61,220,151,.25)}
.br-balance-plate.ko{border-color:var(--err,#ff6b6b);box-shadow:0 0 0 4px rgba(255,107,107,.25)}
.br-balance-btns{display:grid;grid-template-columns:1fr .8fr 1fr;gap:10px}
.br-balance-btn{min-height:60px;border-radius:16px;border:0;font:700 18px system-ui,sans-serif;color:#fff;background:#6d28d9;
  touch-action:manipulation;cursor:pointer}
.br-balance-btn.eq{background:#4c1d95;font-size:26px}
.br-balance-btn:active{transform:scale(.96)}
.br-balance-btn:disabled{opacity:.55}
.br-balance-still .br-balance-beam,.br-balance-still .br-balance-plate{transition:none}
@media (max-height:520px){.br-balance-wrap{min-height:0;gap:8px;padding:6px 4px}.br-balance-stage{min-height:0;justify-content:flex-start;padding-top:8px}
  .br-balance-post{height:56px}.br-balance-btn{min-height:52px}}`;

  function injectStyle() {
    if (document.getElementById('br-balance-style')) return;
    const st = document.createElement('style');
    st.id = 'br-balance-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // ---- Calculs : { text, value } (valeur ≥ 0 ; entière sauf les fractions pures) ----
  const int = (rng, a, b) => a + Math.floor(rng() * (b - a + 1));
  const pick = (rng, list) => list[Math.floor(rng() * list.length)];
  const fmt = (n) => (Math.abs(n) >= 1000 ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : String(n));
  const SUP = { 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
  const pow = (n) => String(n).split('').map((c) => SUP[c]).join('');
  const ex = (text, value) => ({ text, value });
  const num = (v) => ex(fmt(v), v);
  const sum = (a, b) => ex(`${fmt(a)} + ${fmt(b)}`, a + b);
  const diff = (a, b) => ex(`${fmt(Math.max(a, b))} − ${fmt(Math.min(a, b))}`, Math.abs(a - b));
  const prod = (a, b) => ex(`${fmt(a)} × ${fmt(b)}`, a * b);
  const quot = (q, b) => ex(`${fmt(q * b)} ÷ ${b}`, q);
  const coprime = (a, b) => { while (b) [a, b] = [b, a % b]; return a === 1; };
  const fracOf = (n, d, k) => ex(`${n}/${d} de ${fmt(d * k)}`, n * k);
  const numer = (r, d) => { let n = int(r, 1, d - 1); while (!coprime(n, d)) n = int(r, 1, d - 1); return n; };
  const frac = (n, d) => Object.assign(ex(`${n}/${d}`, n / d), { frac: [n, d] });

  function fraction(r, dmax) {
    const d = int(r, 2, dmax);
    return frac(numer(r, d), d);
  }
  function fractionEqual(r, e) { const k = int(r, 2, 5); return frac(e.frac[0] * k, e.frac[1] * k); }
  function fractionNear(r, e, dmax) {
    const all = [];
    for (let d = 2; d <= dmax; d++) for (let n = 1; n < d; n++) {
      if (coprime(n, d) && Math.abs(n / d - e.value) > 1e-9) all.push([Math.abs(n / d - e.value), n, d]);
    }
    all.sort((a, b) => a[0] - b[0]);
    const [, n, d] = pick(r, all.slice(0, 4));
    return frac(n, d);
  }
  const pure = (from, dmax) => ({ from, pure: true, dmax,
    gen: (r) => fraction(r, dmax), eq: fractionEqual, near: (r, e) => fractionNear(r, e, dmax) });

  // Familles de calculs, débloquées au niveau `from` ; `s` agrandit les nombres avec le niveau.
  const I = (r, lo, hi, s) => int(r, lo, Math.max(lo, Math.round(hi * s)));
  const FAMILIES = [
    { from: 1, gen: (r, s) => num(I(r, 1, 20, s)) },
    { from: 1, gen: (r, s) => sum(I(r, 1, 9, s), I(r, 1, 9, s)) },
    { from: 3, gen: (r, s) => diff(I(r, 10, 20, s), I(r, 1, 9, s)) },
    { from: 4, gen: (r, s) => sum(I(r, 5, 40, s), I(r, 5, 40, s)) },
    { from: 5, gen: (r) => prod(int(r, 2, 5), int(r, 2, 9)) },
    { from: 6, gen: (r) => prod(int(r, 2, 9), int(r, 2, 9)) },
    { from: 7, gen: (r, s) => diff(I(r, 30, 99, s), I(r, 10, 29, s)) },
    { from: 8, gen: (r) => quot(int(r, 2, 12), int(r, 2, 9)) },
    { from: 9, gen: (r, s) => { const a = I(r, 2, 20, s), b = int(r, 2, 9), c = int(r, 2, 9); return ex(`${a} + ${b} × ${c}`, a + b * c); } },
    { from: 10, gen: (r) => { const a = int(r, 3, 9), b = int(r, 3, 9), c = int(r, 1, a * b - 1); return ex(`${a} × ${b} − ${c}`, a * b - c); } },
    { from: 12, gen: (r, s) => { const a = I(r, 2, 9, s), b = int(r, 1, 9), c = int(r, 2, 6); return ex(`(${a} + ${b}) × ${c}`, (a + b) * c); } },
    { from: 13, gen: (r) => { const a = int(r, 2, 9), b = int(r, 2, 9), c = int(r, 2, 9), d = int(r, 2, 9); return ex(`${a} × ${b} + ${c} × ${d}`, a * b + c * d); } },
    { from: 14, gen: (r) => { const b = int(r, 2, 9), c = int(r, 2, 9), a = b * c + int(r, 1, 40); return ex(`${a} − ${b} × ${c}`, a - b * c); } },
    { from: 15, gen: (r, s) => { const q = int(r, 2, 9), d = int(r, 2, 9), e = I(r, 2, 15, s); return ex(`${q * d} ÷ ${d} + ${e}`, q + e); } },
    { from: 16, gen: (r, s) => { const a = I(r, 2, 12, s); return ex(`${a}²`, a * a); } },
    { from: 17, gen: (r, s) => sum(I(r, 100, 500, s), I(r, 100, 500, s)) },
    { from: 18, gen: (r, s) => { const a = int(r, 3, 15), b = I(r, 2, 40, s); return ex(`${a}² + ${b}`, a * a + b); } },
    { from: 19, gen: (r) => { const n = int(r, 3, 10); return ex(`2${pow(n)}`, 2 ** n); } },
    { from: 20, gen: (r) => { const a = int(r, 2, 6); return ex(`${a}³`, a ** 3); } },
    { from: 21, gen: (r, s) => { const d = int(r, 2, 6); return fracOf(numer(r, d), d, I(r, 2, 15, s)); } },
    { from: 22, gen: (r, s) => diff(I(r, 300, 999, s), I(r, 100, 299, s)) },
    pure(23, 9),
    { from: 24, gen: (r) => { const a = int(r, 2, 9), b = int(r, 1, 7); return ex(`(${a} + ${b})²`, (a + b) ** 2); } },
    { from: 25, gen: (r, s) => prod(I(r, 11, 30, s), int(r, 3, 9)) },
    { from: 26, gen: (r) => { const a = int(r, 5, 15), b = int(r, 2, a - 1); return ex(`${a}² − ${b}²`, a * a - b * b); } },
    { from: 27, gen: (r) => { const b = int(r, 1, 9), a = b + int(r, 2, 9), c = int(r, 2, 9), d = int(r, 1, 9); return ex(`(${a} − ${b}) × (${c} + ${d})`, (a - b) * (c + d)); } },
    { from: 28, gen: (r, s) => { const d = int(r, 3, 8), n = numer(r, d), k = I(r, 3, 20, s), e = int(r, 2, 30); return ex(`${n}/${d} de ${d * k} + ${e}`, n * k + e); } },
    { from: 29, gen: (r) => { const a = int(r, 2, 9), b = int(r, 2, 9); return ex(`${a}² × ${b}`, a * a * b); } },
    { from: 30, gen: (r, s) => sum(I(r, 1000, 4999, s), I(r, 1000, 4999, s)) },
    { from: 31, gen: (r, s) => prod(I(r, 11, 39, s), int(r, 11, 39)) },
    { from: 32, gen: (r) => { const a = int(r, 2, 6), b = int(r, 2, 12); return ex(`${a}³ + ${b}²`, a ** 3 + b * b); } },
    { from: 33, gen: (r, s) => diff(I(r, 5000, 9999, s), I(r, 1000, 4999, s)) },
    { from: 34, gen: (r) => { const a = int(r, 2, 15), b = int(r, 2, 15), c = int(r, 3, 9), d = int(r, 1, 30); return ex(`(${a} + ${b}) × ${c} − ${d}`, (a + b) * c - d); } },
    pure(35, 16),
    { from: 36, gen: (r, s) => prod(I(r, 101, 999, s), int(r, 3, 9)) },
    { from: 37, gen: (r) => { const a = int(r, 2, 9), b = int(r, 2, 9), c = int(r, 2, 9); return ex(`${a} × ${b} × ${c}`, a * b * c); } },
    { from: 38, gen: (r) => { const a = int(r, 6, 20), c = int(r, 2, 9), q = int(r, 1, Math.floor(a * a / c)); return ex(`(${a}² − ${a * a - q * c}) ÷ ${c}`, q); } },
    { from: 39, gen: (r, s) => { const d = int(r, 3, 12); return fracOf(numer(r, d), d, I(r, 20, 99, s)); } },
    { from: 40, gen: (r) => { const a = int(r, 5, 15), b = int(r, 2, 9), c = int(r, 2, 9), d = int(r, 2, 9); return ex(`(${a} + ${b})² − ${c} × ${d}`, (a + b) ** 2 - c * d); } },
  ];

  const unlocked = (lv) => FAMILIES.filter((f) => f.from <= lv);
  function familyFor(rng, lv) {
    const open = unlocked(lv);
    return rng() < 0.65 ? pick(rng, open.slice(-5)) : pick(rng, open);
  }
  const genIn = (rng, fam, lv) => fam.gen(rng, scaleOf(lv, fam.from));
  function genAny(rng, lv) {
    let fam = familyFor(rng, lv);
    for (let i = 0; fam.pure && i < 8; i++) fam = familyFor(rng, lv);
    return fam.pure ? num(int(rng, 1, 20)) : genIn(rng, fam, lv);
  }
  const same = (x, y) => Math.abs(x - y) < 1e-9;

  function equalTo(rng, fam, lv, a) {
    if (fam.pure) return fam.eq(rng, a);
    for (let i = 0; i < TRIES; i++) {
      const e = i % 2 ? genIn(rng, fam, lv) : genAny(rng, lv);
      if (same(e.value, a.value) && e.text !== a.text) return e;
    }
    const v = a.value;
    const divisors = [];
    for (let p = 2; p * p <= v; p++) if (v % p === 0) divisors.push(p);
    if (divisors.length && rng() < 0.5) { const p = pick(rng, divisors); return prod(v / p, p); }
    if (v >= 2 && rng() < 0.6) { const x = int(rng, 1, v - 1); return sum(x, v - x); }
    const y = int(rng, 2, Math.max(9, Math.round(v * 0.3)));
    return ex(`${fmt(v + y)} − ${fmt(y)}`, v);
  }

  function nearTo(rng, fam, lv, a) {
    if (fam.pure) return fam.near(rng, a);
    const span = Math.max(1, Math.round(a.value * closeness(lv)));
    let best = null;
    for (let i = 0; i < TRIES * 2; i++) {
      const e = i < TRIES ? genIn(rng, fam, lv) : genAny(rng, lv);
      const gap = Math.abs(e.value - a.value);
      if (gap === 0 || e.text === a.text) continue;
      if (gap <= span) return e;
      if (!best || gap < Math.abs(best.value - a.value)) best = e;
    }
    // Aucun calcul assez proche : on ajuste le plus proche d'un « + m » / « − m » (m entier).
    const base = best || num(int(rng, 1, 20));
    const k = int(rng, 1, span);
    const m = a.value + (a.value - k < 0 || rng() < 0.5 ? k : -k) - base.value;
    return m >= 0 ? ex(`${base.text} +\u00a0${fmt(m)}`, base.value + m) : ex(`${base.text} −\u00a0${fmt(-m)}`, base.value + m);
  }

  function makeRound(rng, lv) {
    const fam = familyFor(rng, lv);
    const a = genIn(rng, fam, lv);
    const b = rng() < EQUAL_SHARE ? equalTo(rng, fam, lv, a) : nearTo(rng, fam, lv, a);
    return rng() < 0.5 ? { left: a, right: b } : { left: b, right: a };
  }

  // 1 gauche, 0 égal, −1 droite
  const answerOf = (round) => (same(round.left.value, round.right.value) ? 0 : Math.sign(round.left.value - round.right.value));

  // ---- Jeu ----
  function start(ctx) {
    injectStyle();
    const rng = ctx.rng;
    const floor = Math.max(1, ctx.level | 0 || 1);
    let level = floor;
    let streak = 0;
    let missRow = 0;
    let round = null;
    let shownAt = 0;
    let busy = false;
    let stopped = false;
    let timer = 0;
    let deadline = 0;
    let lowTimer = 0;

    ctx.root.innerHTML = `
      <div class="br-balance-wrap${ctx.reducedMotion ? ' br-balance-still' : ''}">
        <div class="br-balance-time" aria-hidden="true"><i></i></div>
        <div class="br-balance-stage">
          <div class="br-balance-beam">
            <div class="br-balance-pan l"><span class="br-balance-cord"></span><div class="br-balance-plate" data-side="l"></div></div>
            <div class="br-balance-pan r"><span class="br-balance-cord"></span><div class="br-balance-plate" data-side="r"></div></div>
            <span class="br-balance-pivot"></span>
          </div>
          <div class="br-balance-post"></div><div class="br-balance-foot"></div>
        </div>
        <div class="br-balance-btns">
          <button type="button" class="br-balance-btn" data-answer="1" aria-label="Gauche plus lourd">◀ Gauche</button>
          <button type="button" class="br-balance-btn eq" data-answer="0" aria-label="Égal">=</button>
          <button type="button" class="br-balance-btn" data-answer="-1" aria-label="Droite plus lourd">Droite ▶</button>
        </div>
      </div>`;
    const beam = ctx.root.querySelector('.br-balance-beam');
    const plateL = ctx.root.querySelector('[data-side="l"]');
    const plateR = ctx.root.querySelector('[data-side="r"]');
    const bar = ctx.root.querySelector('.br-balance-time');
    const barFill = bar.firstElementChild;
    const buttons = Array.from(ctx.root.querySelectorAll('.br-balance-btn'));

    function setTilt(sign) {
      // Le côté le plus lourd descend : gauche lourd → rotation négative.
      const deg = -sign * TILT_DEG;
      beam.style.transform = `rotate(${deg}deg)`;
      const counter = `rotate(${-deg}deg)`;
      plateL.style.transform = counter;
      plateR.style.transform = counter;
    }

    function clearClocks() { clearTimeout(timer); clearTimeout(deadline); clearTimeout(lowTimer); }

    function runBar(ms) {
      bar.classList.remove('low');
      barFill.style.transition = 'none';
      barFill.style.width = '100%';
      void barFill.offsetWidth; // repart de 100 %
      barFill.style.transition = `width ${ms}ms linear`;
      barFill.style.width = '0%';
      lowTimer = setTimeout(() => bar.classList.add('low'), Math.round(ms * 0.7));
    }

    function showPlate(el, e) {
      el.textContent = e.text;
      el.className = `br-balance-plate${e.text.length > 11 ? ' long' : ''}`;
    }

    function next() {
      if (stopped) return;
      round = makeRound(rng, level);
      showPlate(plateL, round.left);
      showPlate(plateR, round.right);
      setTilt(0);
      buttons.forEach((b) => { b.disabled = false; });
      busy = false;
      shownAt = performance.now();
      const ms = answerMs(level);
      runBar(ms);
      deadline = setTimeout(() => answer(null), ms);
    }

    function changeLevel(nl) {
      if (nl === level) return;
      level = nl;
      ctx.setLevel(level);
    }

    function answer(choice) {
      if (stopped || busy || !round) return;
      busy = true;
      clearClocks();
      const rt = Math.round(performance.now() - shownAt);
      const good = answerOf(round);
      const ok = choice === good;
      setTilt(good);
      const mark = ok ? 'ok' : 'ko';
      if (good >= 0) plateL.classList.add(mark);
      if (good <= 0) plateR.classList.add(mark);
      buttons.forEach((b) => { b.disabled = true; });
      if (ok) {
        missRow = 0;
        streak += 1;
        if (streak >= UP_AFTER) { streak = 0; changeLevel(level + 1); }
        ctx.hit({ rt });
      } else {
        streak = 0;
        missRow += 1;
        if (missRow >= DOWN_AFTER) { missRow = 0; changeLevel(Math.max(floor, level - 1)); }
        ctx.miss(choice === null ? {} : { rt });
      }
      if (!stopped) timer = setTimeout(next, ctx.reducedMotion ? 150 : FEEDBACK_MS);
    }

    function onClick(ev) {
      const btn = ev.target.closest('[data-answer]');
      if (btn) answer(Number(btn.dataset.answer));
    }
    function onKey(ev) {
      const map = { ArrowLeft: 1, ArrowRight: -1, ArrowDown: 0, ArrowUp: 0, '=': 0, ' ': 0 };
      if (!(ev.key in map)) return;
      ev.preventDefault();
      answer(map[ev.key]);
    }

    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : la pesée est retirée sans
    // compter (aucune vie perdue loin de l'écran) ; au retour, nouvelle pesée au même niveau.
    function pause() {
      if (stopped) return;
      busy = true;
      clearClocks();
      buttons.forEach((b) => { b.disabled = true; });
      barFill.style.transition = 'none';
    }
    function resume() {
      if (stopped) return;
      plateL.classList.remove('ok', 'ko');
      plateR.classList.remove('ok', 'ko');
      next();
    }

    ctx.root.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);
    if (ctx.onPause) ctx.onPause(pause);
    if (ctx.onResume) ctx.onResume(resume);
    ctx.setLevel(level);
    next();

    return {
      stop() {
        stopped = true;
        clearClocks();
        ctx.root.removeEventListener('click', onClick);
        window.removeEventListener('keydown', onKey);
        buttons.forEach((b) => { b.disabled = true; });
        barFill.style.transition = 'none';
      },
    };
  }

  window.Brain.register({
    id: ID,
    name: 'Plus lourd',
    domain: 'calcul',
    icon: '⚖️',
    color: '#8b5cf6',
    seconds: null,
    howto: [
      'Chaque plateau porte un calcul : lequel pèse le plus ? Touche Gauche, = ou Droite (au clavier : ←, ↓ ou →).',
      'Réponds avant la fin de la barre : une erreur ou un temps écoulé coûte une vie, et il n’y en a que trois.',
      'Sans fin : priorités, parenthèses, puissances, fractions, grands nombres… et de moins en moins de temps.',
    ],
    start,
  });
})();
