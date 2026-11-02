/* Méninges — « Gouttes » (calcul) : des gouttes portant un calcul tombent vers l'étang ; taper le résultat
   (pavé à l'écran ou clavier) avant qu'elles touchent l'eau. 3 gouttes dans l'eau = fin. Goutte dorée ☀ : la
   résoudre fait éclater toutes les gouttes. Vitesse et nombre de gouttes croissent avec le niveau. */
(function () {
  'use strict';
  const ID = 'gouttes';
  const LIVES = 3;
  const MAX_LEVEL = 12;
  const UP_EVERY = 4;           // bonnes réponses pour monter d'un niveau
  const FREEZE_AFTER = 3;       // erreurs d'affilée avant le gel du pavé
  const FREEZE_MS = 1000;
  const MAX_DIGITS = 4;
  const DROP_W = 84;
  const DROP_H = 70;
  const LANES = 4;
  const SUN_CHANCE = 0.08;
  const MAX_DT = 0.1;           // s : évite un saut après un onglet en arrière-plan

  const CSS = `
.br-gouttes-wrap{display:flex;flex-direction:column;height:100%;min-height:440px;gap:8px;padding:6px 2px;box-sizing:border-box;
  color:var(--text,#f5f0ff);user-select:none;-webkit-user-select:none}
.br-gouttes-sky{flex:1;position:relative;min-height:240px;border-radius:18px;overflow:hidden;
  background:linear-gradient(#1e3a5f,#12304a 60%,#0c2236)}
.br-gouttes-lives{position:absolute;top:8px;right:10px;font-size:18px;letter-spacing:2px;z-index:3}
.br-gouttes-lives .lost{opacity:.22;filter:grayscale(1)}
.br-gouttes-water{position:absolute;left:0;right:0;bottom:0;height:34px;z-index:2;transition:height .4s;
  background:linear-gradient(rgba(56,189,248,.85),rgba(14,116,144,.95));box-shadow:0 -3px 0 rgba(186,230,253,.55)}
.br-gouttes-drop{position:absolute;top:0;width:${DROP_W}px;height:${DROP_H}px;z-index:1;display:flex;align-items:center;justify-content:center;
  border-radius:50% 50% 46% 46% / 62% 62% 38% 38%;background:radial-gradient(circle at 35% 30%,#e0f2fe,#38bdf8 55%,#0284c7);
  color:#062033;font:800 19px/1 system-ui,sans-serif;box-shadow:0 4px 10px rgba(0,0,0,.25);will-change:transform}
.br-gouttes-drop.sun{background:radial-gradient(circle at 35% 30%,#fffbeb,#fbbf24 55%,#d97706);color:#3b2300}
.br-gouttes-drop.sun::after{content:'☀';position:absolute;top:-12px;font-size:16px}
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
.br-gouttes-pad.frozen .br-gouttes-key{opacity:.4}`;

  function injectStyle() {
    if (document.getElementById('br-gouttes-style')) return;
    const st = document.createElement('style');
    st.id = 'br-gouttes-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  const int = (rng, a, b) => a + Math.floor(rng() * (b - a + 1));
  const add = (a, b) => ({ text: `${a} + ${b}`, answer: a + b });
  const sub = (a, b) => ({ text: `${a} − ${b}`, answer: a - b });
  const mul = (a, b) => ({ text: `${a} × ${b}`, answer: a * b });
  const div = (q, b) => ({ text: `${q * b} ÷ ${b}`, answer: q });
  const subOrdered = (rng, lo, hi) => { const a = int(rng, lo, hi), b = int(rng, lo, hi); return sub(Math.max(a, b), Math.min(a, b)); };

  // Calculs par niveau (résultats entiers ≥ 0, 3 chiffres au plus).
  const PROBLEMS = [
    (r) => add(int(r, 1, 5), int(r, 1, 5)),
    (r) => add(int(r, 1, 9), int(r, 1, 9)),
    (r) => sub(int(r, 6, 18), int(r, 1, 5)),
    (r) => (r() < 0.5 ? add(int(r, 3, 15), int(r, 2, 9)) : subOrdered(r, 2, 20)),
    (r) => mul(int(r, 2, 5), int(r, 2, 9)),
    (r) => (r() < 0.5 ? add(int(r, 10, 50), int(r, 5, 40)) : subOrdered(r, 10, 60)),
    (r) => mul(int(r, 2, 9), int(r, 2, 9)),
    (r) => div(int(r, 2, 9), int(r, 2, 9)),
    (r) => (r() < 0.5 ? mul(int(r, 6, 12), int(r, 3, 9)) : add(int(r, 25, 99), int(r, 15, 99))),
    (r) => (r() < 0.5 ? div(int(r, 3, 12), int(r, 3, 12)) : subOrdered(r, 30, 150)),
    (r) => mul(int(r, 11, 19), int(r, 3, 9)),
    (r) => (r() < 0.5 ? mul(int(r, 12, 25), int(r, 4, 9)) : div(int(r, 6, 15), int(r, 6, 15))),
  ];

  function problem(rng, level) {
    const lv = Math.max(1, Math.min(MAX_LEVEL, level));
    const idx = lv > 2 && rng() < 0.35 ? int(rng, 0, lv - 2) : lv - 1;
    return PROBLEMS[idx](rng);
  }

  const fallSeconds = (lv) => Math.max(3.4, 10 - lv * 0.55);
  const spawnEvery = (lv) => Math.max(1.2, 3.6 - lv * 0.22);
  const maxDrops = (lv) => Math.min(5, 2 + Math.floor(lv / 3));
  const EMPTY_SKY_WAIT = 0.5;   // s : ciel vide → nouvelle goutte presque tout de suite

  function start(ctx) {
    injectStyle();
    const rng = ctx.rng;
    let level = Math.max(1, Math.min(MAX_LEVEL, ctx.level | 0 || 1));
    let drops = [];
    let typed = '';
    let lives = LIVES;
    let solved = 0;
    let sinceUp = 0;
    let wrongRow = 0;
    let frozenUntil = 0;
    let spawnClock = 0;
    let lastTs = 0;
    let raf = 0;
    let stopped = false;
    const timers = new Set();

    ctx.root.innerHTML = `
      <div class="br-gouttes-wrap">
        <div class="br-gouttes-sky"><div class="br-gouttes-lives" aria-label="Gouttes ratées"></div><div class="br-gouttes-water"></div></div>
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
    const livesEl = ctx.root.querySelector('.br-gouttes-lives');
    const entry = ctx.root.querySelector('.br-gouttes-entry');
    const pad = ctx.root.querySelector('.br-gouttes-pad');

    function later(fn, ms) {
      const t = setTimeout(() => { timers.delete(t); if (!stopped) fn(); }, ms);
      timers.add(t);
    }

    function drawLives() {
      livesEl.innerHTML = Array.from({ length: LIVES }, (_, i) => `<span class="${i < LIVES - lives ? 'lost' : ''}">💧</span>`).join('');
      water.style.height = `${34 + (LIVES - lives) * 14}px`;
    }

    function freeLane() {
      const busy = new Set(drops.filter((d) => d.y < DROP_H * 1.6).map((d) => d.lane));
      const free = Array.from({ length: LANES }, (_, i) => i).filter((i) => !busy.has(i));
      return free.length ? free[Math.floor(rng() * free.length)] : -1;
    }

    function spawn() {
      const lane = freeLane();
      if (lane < 0) return;
      const p = problem(rng, level);
      const sun = level >= 2 && drops.length >= 1 && rng() < SUN_CHANCE;
      const el = document.createElement('div');
      el.className = `br-gouttes-drop${sun ? ' sun' : ''}`;
      el.textContent = p.text;
      const laneW = (sky.clientWidth - DROP_W) / (LANES - 1);
      el.style.left = `${Math.round(lane * laneW)}px`;
      sky.appendChild(el);
      drops = drops.concat([{ el, y: -DROP_H * 0.2, lane, answer: p.answer, sun, born: performance.now() }]);
      place(drops[drops.length - 1]);
    }

    function place(d) { d.el.style.transform = `translateY(${d.y}px)`; }

    function removeDrop(d, cls) {
      drops = drops.filter((x) => x !== d);
      if (ctx.reducedMotion) { d.el.remove(); return; }
      d.el.classList.add(cls);
      later(() => d.el.remove(), 240);
    }

    function changeLevel(delta) {
      const nl = Math.max(1, Math.min(MAX_LEVEL, level + delta));
      if (nl !== level) { level = nl; ctx.setLevel(level); }
    }

    function lose(d) {
      if (stopped) return;
      removeDrop(d, 'splash');
      lives -= 1;
      drawLives();
      ctx.miss({});
      changeLevel(-1);
      if (lives <= 0) {
        halt();
        ctx.finish({ detail: `${solved} goutte${solved > 1 ? 's' : ''} résolue${solved > 1 ? 's' : ''}` });
      }
    }

    function frame(ts) {
      if (stopped) return;
      const dt = lastTs ? Math.min(MAX_DT, (ts - lastTs) / 1000) : 0;
      lastTs = ts;
      const waterTop = sky.clientHeight - water.offsetHeight;
      const speed = (waterTop + DROP_H) / fallSeconds(level);
      drops.forEach((d) => { d.y += speed * dt; place(d); });
      drops.filter((d) => d.y + DROP_H >= waterTop).forEach(lose);
      if (stopped) return;
      spawnClock = drops.length ? spawnClock - dt : Math.min(spawnClock - dt, EMPTY_SKY_WAIT);
      if (spawnClock <= 0 && drops.length < maxDrops(level)) { spawn(); spawnClock = spawnEvery(level); }
      raf = requestAnimationFrame(frame);
    }

    function flash(cls) {
      entry.classList.remove('ok', 'ko');
      entry.classList.add(cls);
      later(() => entry.classList.remove(cls), 260);
    }

    function submit() {
      if (!typed) return;
      const value = Number(typed);
      typed = '';
      entry.textContent = '';
      const matched = drops.filter((d) => d.answer === value);
      if (!matched.length) {
        ctx.miss({});
        flash('ko');
        wrongRow += 1;
        if (wrongRow >= FREEZE_AFTER) { wrongRow = 0; frozenUntil = performance.now() + FREEZE_MS; pad.classList.add('frozen'); later(() => pad.classList.remove('frozen'), FREEZE_MS); }
        return;
      }
      wrongRow = 0;
      const popped = matched.some((d) => d.sun) ? drops.slice() : matched;
      const now = performance.now();
      popped.forEach((d) => {
        removeDrop(d, 'pop');
        solved += 1;
        ctx.hit({ rt: Math.round(now - d.born) });
        sinceUp += 1;
        if (sinceUp >= UP_EVERY) { sinceUp = 0; changeLevel(1); }
      });
      flash('ok');
    }

    function press(key) {
      if (stopped || performance.now() < frozenUntil) return;
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

    pad.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);
    drawLives();
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
      'La goutte dorée ☀ fait éclater toutes les gouttes d’un coup.',
      'Trois gouttes dans l’eau et la partie s’arrête.',
    ],
    start,
  });
})();
