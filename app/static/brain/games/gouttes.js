/* Méninges — « Gouttes » (calcul) : des gouttes portant un calcul tombent vers l'étang ; taper le résultat
   (pavé à l'écran ou clavier) avant qu'elles touchent l'eau. Partie SANS FIN : une goutte dans l'eau = une vie
   (3 vies du moteur) ; un mauvais résultat tapé = petite erreur sans vie. Gouttes bonus : dorée ☀ (fait éclater
   toutes les gouttes), glacée ❄ (ralentit la pluie). Vitesse, nombre de gouttes et calculs croissent sans limite. */
(function () {
  'use strict';
  const ID = 'gouttes';
  const UP_EVERY = 4;           // gouttes résolues pour monter d'un niveau
  const FREEZE_AFTER = 3;       // erreurs d'affilée avant le gel du pavé
  const FREEZE_MS = 1000;
  const MAX_DIGITS = 6;
  const DROP_W = 88;
  const DROP_H = 70;
  const LANES = 4;
  const SUN_CHANCE = 0.07;      // dès le niveau 2
  const ICE_CHANCE = 0.06;      // dès le niveau 8
  const ICE_FROM = 8;
  const ICE_SECONDS = 5;
  const ICE_SLOW = 0.35;        // vitesse pendant le gel
  const MAX_DT = 0.1;           // s : évite un saut après un onglet en arrière-plan
  const EMPTY_SKY_WAIT = 0.5;   // s : ciel vide → nouvelle goutte presque tout de suite
  // Chute : 9,2 s au niveau 1, ~5,1 s au niveau 20, ~3,7 s au niveau 40, jamais sous 3,2 s.
  const fallSeconds = (lv) => 3.2 + 6 * Math.pow(0.94, lv - 1);
  // Une goutte toutes les 3,8 s au niveau 1, ~2,1 s au niveau 20, ~1,4 s au niveau 40, jamais moins de 1 s.
  const spawnEvery = (lv) => 1 + 2.8 * Math.pow(0.95, lv - 1);
  // Gouttes en même temps : 2 (niv. 1-5), +1 par palier, 7 dès le niveau 26.
  const maxDrops = (lv) => Math.min(7, 2 + Math.floor((lv - 1) / 5));
  const scaleOf = (lv, from) => Math.min(3, 1 + Math.max(0, lv - from) * 0.04);

  const CSS = `
.br-gouttes-wrap{display:flex;flex-direction:column;flex:1 1 auto;min-height:440px;gap:8px;padding:6px 2px;box-sizing:border-box;
  color:var(--text,#f5f0ff);user-select:none;-webkit-user-select:none}
.br-gouttes-sky{flex:1;position:relative;min-height:240px;border-radius:18px;overflow:hidden;transition:filter .3s;
  background:linear-gradient(#1e3a5f,#12304a 60%,#0c2236)}
.br-gouttes-sky.icy{filter:hue-rotate(-20deg) saturate(.6) brightness(1.25)}
.br-gouttes-water{position:absolute;left:0;right:0;bottom:0;height:34px;z-index:2;
  background:linear-gradient(rgba(56,189,248,.85),rgba(14,116,144,.95));box-shadow:0 -3px 0 rgba(186,230,253,.55)}
.br-gouttes-drop{position:absolute;top:0;width:${DROP_W}px;height:${DROP_H}px;z-index:1;display:flex;align-items:center;justify-content:center;
  border-radius:50% 50% 46% 46% / 62% 62% 38% 38%;background:radial-gradient(circle at 35% 30%,#e0f2fe,#38bdf8 55%,#0284c7);
  color:#062033;font:800 18px/1.05 system-ui,sans-serif;text-align:center;box-shadow:0 4px 10px rgba(0,0,0,.25);will-change:transform}
.br-gouttes-drop.long{font-size:14px}
.br-gouttes-drop.sun{background:radial-gradient(circle at 35% 30%,#fffbeb,#fbbf24 55%,#d97706);color:#3b2300}
.br-gouttes-drop.sun::after{content:'☀';position:absolute;top:-12px;font-size:16px}
.br-gouttes-drop.ice{background:radial-gradient(circle at 35% 30%,#ffffff,#c7d2fe 55%,#818cf8);color:#1e1b4b}
.br-gouttes-drop.ice::after{content:'❄';position:absolute;top:-12px;font-size:16px}
.br-gouttes-drop.pop{transition:transform .22s,opacity .22s;opacity:0}
.br-gouttes-drop.splash{background:#7dd3fc;opacity:.4}
.br-gouttes-entry{height:48px;display:flex;align-items:center;justify-content:center;border-radius:14px;background:var(--card,#221a3d);
  font:800 28px/1 system-ui,sans-serif;letter-spacing:2px;border:2px solid transparent;transition:border-color .15s}
.br-gouttes-entry.ko{border-color:var(--err,#ff6b6b)}
.br-gouttes-entry.ok{border-color:var(--ok,#3ddc97)}
.br-gouttes-entry:empty::before{content:'?';opacity:.3}
.br-gouttes-pad{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.br-gouttes-key{min-height:48px;border:0;border-radius:12px;background:#0e7490;color:#fff;font:700 22px system-ui,sans-serif;
  touch-action:manipulation;cursor:pointer}
.br-gouttes-key[data-key="ok"]{background:#0ea5e9}.br-gouttes-key[data-key="del"]{background:#164e63}
.br-gouttes-key:active{transform:scale(.96)}
.br-gouttes-pad.frozen .br-gouttes-key{opacity:.4}
@media (max-height:520px){.br-gouttes-wrap{display:grid;grid-template-columns:1fr 168px;grid-template-rows:auto 1fr;min-height:0}
  .br-gouttes-sky{grid-row:1 / 3;min-height:0}.br-gouttes-entry{grid-column:2}.br-gouttes-pad{grid-column:2;align-content:end}
  .br-gouttes-key{min-height:44px}}`;

  function injectStyle() {
    if (document.getElementById('br-gouttes-style')) return;
    const st = document.createElement('style');
    st.id = 'br-gouttes-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // ---- Calculs : { text, answer } (résultat entier ≥ 0) ----
  const int = (rng, a, b) => a + Math.floor(rng() * (b - a + 1));
  const pick = (rng, list) => list[Math.floor(rng() * list.length)];
  const I = (r, lo, hi, s) => int(r, lo, Math.max(lo, Math.round(hi * s)));
  const SUP = ['⁰', '¹', '²', '³', '⁴', '⁵', '⁶', '⁷', '⁸', '⁹'];
  const pq = (text, answer) => ({ text, answer });
  const add = (a, b) => pq(`${a} + ${b}`, a + b);
  const sub = (a, b) => pq(`${Math.max(a, b)} − ${Math.min(a, b)}`, Math.abs(a - b));
  const mul = (a, b) => pq(`${a} × ${b}`, a * b);
  const div = (q, b) => pq(`${q * b} ÷ ${b}`, q);
  const coprime = (a, b) => { while (b) [a, b] = [b, a % b]; return a === 1; };
  const numer = (r, d) => { let n = int(r, 1, d - 1); while (!coprime(n, d)) n = int(r, 1, d - 1); return n; };

  // Familles débloquées au niveau `from` ; `s` agrandit les nombres avec le niveau.
  const FAMILIES = [
    { from: 1, gen: (r) => add(int(r, 1, 5), int(r, 1, 5)) },
    { from: 2, gen: (r) => add(int(r, 1, 9), int(r, 1, 9)) },
    { from: 3, gen: (r) => sub(int(r, 6, 18), int(r, 1, 5)) },
    { from: 4, gen: (r, s) => (r() < 0.5 ? add(I(r, 3, 15, s), int(r, 2, 9)) : sub(I(r, 2, 20, s), I(r, 2, 20, s))) },
    { from: 5, gen: (r) => mul(int(r, 2, 5), int(r, 2, 9)) },
    { from: 6, gen: (r, s) => (r() < 0.5 ? add(I(r, 10, 50, s), I(r, 5, 40, s)) : sub(I(r, 10, 60, s), I(r, 10, 60, s))) },
    { from: 7, gen: (r) => mul(int(r, 2, 9), int(r, 2, 9)) },
    { from: 8, gen: (r) => div(int(r, 2, 9), int(r, 2, 9)) },
    { from: 9, gen: (r) => mul(int(r, 6, 12), int(r, 3, 9)) },
    { from: 10, gen: (r, s) => add(I(r, 25, 99, s), I(r, 15, 99, s)) },
    { from: 11, gen: (r, s) => sub(I(r, 30, 150, s), I(r, 30, 150, s)) },
    { from: 12, gen: (r) => mul(int(r, 11, 19), int(r, 3, 9)) },
    { from: 13, gen: (r, s) => { const a = I(r, 2, 20, s), b = int(r, 2, 9), c = int(r, 2, 9); return pq(`${a} + ${b} × ${c}`, a + b * c); } },
    { from: 14, gen: (r) => div(int(r, 6, 15), int(r, 6, 15)) },
    { from: 15, gen: (r) => { const a = int(r, 2, 15); return pq(`${a}²`, a * a); } },
    { from: 16, gen: (r) => { const a = int(r, 2, 9), b = int(r, 1, 9), c = int(r, 2, 9); return pq(`(${a} + ${b}) × ${c}`, (a + b) * c); } },
    { from: 17, gen: (r) => { const a = int(r, 3, 12), b = int(r, 3, 9), c = int(r, 1, a * b - 1); return pq(`${a} × ${b} − ${c}`, a * b - c); } },
    { from: 18, gen: (r, s) => add(I(r, 100, 999, s), I(r, 11, 99, s)) },
    { from: 19, gen: (r) => mul(int(r, 12, 25), int(r, 4, 9)) },
    { from: 20, gen: (r, s) => { const d = int(r, 2, 6), n = numer(r, d), k = I(r, 2, 20, s); return pq(`${n}/${d} de ${d * k}`, n * k); } },
    { from: 21, gen: (r, s) => { const a = int(r, 3, 15), b = I(r, 2, 40, s); return pq(`${a}² + ${b}`, a * a + b); } },
    { from: 22, gen: (r) => mul(int(r, 11, 19), int(r, 11, 19)) },
    { from: 23, gen: (r, s) => sub(I(r, 100, 999, s), I(r, 100, 999, s)) },
    { from: 24, gen: (r) => { const a = int(r, 2, 9); return pq(`${a}³`, a ** 3); } },
    { from: 25, gen: (r) => { const a = int(r, 2, 9), b = int(r, 2, 9), c = int(r, 2, 9), d = int(r, 2, 9); return pq(`${a}×${b} + ${c}×${d}`, a * b + c * d); } },
    { from: 26, gen: (r) => { const b = int(r, 1, 9), a = b + int(r, 2, 12), c = int(r, 3, 9); return pq(`(${a} − ${b}) × ${c}`, (a - b) * c); } },
    { from: 27, gen: (r) => { const n = int(r, 4, 12); return pq(`2${String(n).split('').map((c) => SUP[c]).join('')}`, 2 ** n); } },
    { from: 28, gen: (r, s) => div(I(r, 3, 30, s), int(r, 11, 25)) },
    { from: 29, gen: (r) => { const a = int(r, 6, 20), b = int(r, 2, a - 1); return pq(`${a}² − ${b}²`, a * a - b * b); } },
    { from: 30, gen: (r, s) => mul(I(r, 101, 999, s), int(r, 3, 9)) },
    { from: 31, gen: (r) => { const a = int(r, 2, 9), b = int(r, 2, 9), c = int(r, 2, 9); return pq(`${a} × ${b} × ${c}`, a * b * c); } },
    { from: 32, gen: (r, s) => { const d = int(r, 3, 12), n = numer(r, d), k = I(r, 12, 60, s); return pq(`${n}/${d} de ${d * k}`, n * k); } },
    { from: 33, gen: (r, s) => sub(I(r, 1000, 9999, s), I(r, 100, 999, s)) },
    { from: 34, gen: (r) => { const a = int(r, 3, 12), b = int(r, 2, 9); return pq(`(${a} + ${b})²`, (a + b) ** 2); } },
    { from: 35, gen: (r) => mul(int(r, 21, 49), int(r, 21, 49)) },
    { from: 36, gen: (r, s) => { const a = int(r, 3, 9), b = I(r, 11, 99, s); return pq(`${a}³ + ${b}`, a ** 3 + b); } },
    { from: 37, gen: (r) => { const a = int(r, 2, 12), b = int(r, 2, 12), d = int(r, 1, 8), c = d + int(r, 2, 9); return pq(`(${a}+${b}) × (${c}−${d})`, (a + b) * (c - d)); } },
    { from: 38, gen: (r, s) => add(I(r, 1000, 4999, s), I(r, 1000, 4999, s)) },
    { from: 39, gen: (r) => { const a = int(r, 3, 12), b = int(r, 3, 9); return pq(`${a}² × ${b}`, a * a * b); } },
    { from: 40, gen: (r) => { const c = int(r, 2, 9), d = int(r, 2, 9), a = int(r, 5, 19), b = int(r, Math.ceil((c * d + 1) / a), 19); return pq(`${a}×${b} − ${c}×${d}`, a * b - c * d); } },
  ];

  function problem(rng, lv) {
    const open = FAMILIES.filter((f) => f.from <= lv);
    const fam = rng() < 0.65 ? pick(rng, open.slice(-5)) : pick(rng, open);
    return fam.gen(rng, scaleOf(lv, fam.from));
  }

  function start(ctx) {
    injectStyle();
    const rng = ctx.rng;
    const slip = ctx.slip || (() => {});
    const floor = Math.max(1, ctx.level | 0 || 1);
    let level = floor;
    let drops = [];
    let typed = '';
    let sinceUp = 0;
    let wrongRow = 0;
    let frozenUntil = 0;
    let spawnClock = 0;
    let iceLeft = 0;
    let lastTs = 0;
    let raf = 0;
    let stopped = false;
    let paused = false;
    const timers = new Set();

    ctx.root.innerHTML = `
      <div class="br-gouttes-wrap">
        <div class="br-gouttes-sky"><div class="br-gouttes-water"></div></div>
        <div class="br-gouttes-entry" aria-live="polite"></div>
        <div class="br-gouttes-pad">
          ${['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((k) => `<button type="button" class="br-gouttes-key" data-key="${k}">${k}</button>`).join('')}
          <button type="button" class="br-gouttes-key" data-key="del" aria-label="Effacer">⌫</button>
          <button type="button" class="br-gouttes-key" data-key="0">0</button>
          <button type="button" class="br-gouttes-key" data-key="ok" aria-label="Valider">✓</button>
        </div>
      </div>`;
    const sky = ctx.root.querySelector('.br-gouttes-sky');
    const water = ctx.root.querySelector('.br-gouttes-water');
    const entry = ctx.root.querySelector('.br-gouttes-entry');
    const pad = ctx.root.querySelector('.br-gouttes-pad');

    function later(fn, ms) {
      const t = setTimeout(() => { timers.delete(t); if (!stopped) fn(); }, ms);
      timers.add(t);
    }

    function freeLane() {
      const busy = new Set(drops.filter((d) => d.y < DROP_H * 1.6).map((d) => d.lane));
      const free = Array.from({ length: LANES }, (_, i) => i).filter((i) => !busy.has(i));
      return free.length ? free[Math.floor(rng() * free.length)] : -1;
    }

    function bonusKind() {
      if (!drops.length || drops.some((d) => d.kind)) return '';
      const roll = rng();
      if (level >= 2 && roll < SUN_CHANCE) return 'sun';
      if (level >= ICE_FROM && roll < SUN_CHANCE + ICE_CHANCE && iceLeft <= 0) return 'ice';
      return '';
    }

    function spawn() {
      const lane = freeLane();
      if (lane < 0) return;
      const p = problem(rng, level);
      const kind = bonusKind();
      const el = document.createElement('div');
      el.className = `br-gouttes-drop${kind ? ` ${kind}` : ''}${p.text.length > 8 ? ' long' : ''}`;
      el.textContent = p.text;
      const laneW = (sky.clientWidth - DROP_W) / (LANES - 1);
      el.style.left = `${Math.max(0, Math.round(lane * laneW))}px`;
      sky.appendChild(el);
      const d = { el, y: -DROP_H * 0.2, lane, answer: p.answer, kind, born: performance.now() };
      drops = drops.concat([d]);
      place(d);
    }

    function place(d) { d.el.style.transform = `translateY(${d.y}px)`; }

    function removeDrop(d, cls) {
      drops = drops.filter((x) => x !== d);
      if (ctx.reducedMotion) { d.el.remove(); return; }
      d.el.classList.add(cls);
      later(() => d.el.remove(), 240);
    }

    function changeLevel(nl) {
      if (nl === level) return;
      level = nl;
      ctx.setLevel(level);
    }

    function lose(d) {
      if (stopped) return;
      removeDrop(d, 'splash');
      changeLevel(Math.max(floor, level - 1));
      ctx.miss({});
    }

    function frame(ts) {
      if (stopped) return;
      const dt = lastTs ? Math.min(MAX_DT, (ts - lastTs) / 1000) : 0;
      lastTs = ts;
      if (iceLeft > 0) { iceLeft -= dt; if (iceLeft <= 0) sky.classList.remove('icy'); }
      const waterTop = sky.clientHeight - water.offsetHeight;
      const speed = ((waterTop + DROP_H) / fallSeconds(level)) * (iceLeft > 0 ? ICE_SLOW : 1);
      drops.forEach((d) => { d.y += speed * dt; place(d); });
      const fallen = drops.filter((d) => d.y + DROP_H >= waterTop);
      for (const d of fallen) { lose(d); if (stopped) return; }
      spawnClock = drops.length ? spawnClock - dt : Math.min(spawnClock - dt, EMPTY_SKY_WAIT);
      if (spawnClock <= 0 && drops.length < maxDrops(level)) { spawn(); spawnClock = spawnEvery(level); }
      raf = requestAnimationFrame(frame);
    }

    function flash(cls) {
      entry.classList.remove('ok', 'ko');
      entry.classList.add(cls);
      later(() => entry.classList.remove(cls), 260);
    }

    function freezePad() {
      wrongRow = 0;
      frozenUntil = performance.now() + FREEZE_MS;
      pad.classList.add('frozen');
      later(() => pad.classList.remove('frozen'), FREEZE_MS);
    }

    function submit() {
      if (!typed) return;
      const value = Number(typed);
      typed = '';
      entry.textContent = '';
      const matched = drops.filter((d) => d.answer === value);
      if (!matched.length) {
        slip({});
        flash('ko');
        wrongRow += 1;
        if (wrongRow >= FREEZE_AFTER) freezePad();
        return;
      }
      wrongRow = 0;
      if (matched.some((d) => d.kind === 'ice')) { iceLeft = ICE_SECONDS; sky.classList.add('icy'); }
      const popped = matched.some((d) => d.kind === 'sun') ? drops.slice() : matched;
      const now = performance.now();
      flash('ok');
      for (const d of popped) {
        if (stopped) return;
        removeDrop(d, 'pop');
        sinceUp += 1;
        if (sinceUp >= UP_EVERY) { sinceUp = 0; changeLevel(level + 1); }
        ctx.hit({ rt: Math.round(now - d.born) });
      }
    }

    function press(key) {
      if (stopped || paused || performance.now() < frozenUntil) return;
      if (key === 'ok') { submit(); return; }
      if (key === 'del') typed = typed.slice(0, -1);
      else if (/^[0-9]$/.test(key) && typed.length < MAX_DIGITS) typed = typed === '0' ? key : typed + key;
      entry.textContent = typed;
    }

    function onClick(ev) {
      const btn = ev.target.closest('[data-key]');
      if (btn) press(btn.dataset.key);
    }
    function onKey(ev) {
      if (/^[0-9]$/.test(ev.key)) press(ev.key);
      else if (ev.key === 'Backspace') press('del');
      else if (ev.key === 'Enter') press('ok');
      else return;
      ev.preventDefault();
    }

    function halt() {
      stopped = true;
      cancelAnimationFrame(raf);
      timers.forEach(clearTimeout);
      timers.clear();
      pad.removeEventListener('click', onClick);
      window.removeEventListener('keydown', onKey);
    }

    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : la pluie s'arrête net
    // (aucune goutte ne tombe loin de l'écran) et reprend au retour, là où elle était.
    function pause() {
      paused = true;
      cancelAnimationFrame(raf);
      raf = 0;
    }
    function resume() {
      paused = false;
      if (stopped || raf) return;
      lastTs = 0;
      raf = requestAnimationFrame(frame);
    }

    pad.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);
    if (ctx.onPause) ctx.onPause(pause);
    if (ctx.onResume) ctx.onResume(resume);
    ctx.setLevel(level);
    raf = requestAnimationFrame(frame);

    return { stop: halt };
  }

  window.Brain.register({
    id: ID,
    name: 'Gouttes',
    domain: 'calcul',
    icon: '💧',
    color: '#0ea5e9',
    seconds: null,
    howto: [
      'Des gouttes portant un calcul tombent : tape le résultat puis ✓ avant qu’elles touchent l’eau.',
      'Une goutte dans l’eau coûte une vie (trois en tout). Dorée ☀ : tout éclate ; glacée ❄ : la pluie ralentit.',
      'Sans fin : la pluie s’accélère, les gouttes se multiplient et les calculs se corsent.',
    ],
    start,
  });
})();
