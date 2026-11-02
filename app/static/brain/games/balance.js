/* Méninges — « Plus lourd » (calcul) : deux plateaux portent chacun un calcul ; quel côté pèse le plus ?
   Gauche / Égal / Droite, 45 s. Les calculs se corsent avec le niveau (addition → priorités et parenthèses). */
(function () {
  'use strict';
  const ID = 'balance';
  const MAX_LEVEL = 12;
  const UP_AFTER = 4;          // bonnes réponses d'affilée pour monter d'un niveau
  const FEEDBACK_MS = 380;     // la balance penche, puis calcul suivant
  const EQUAL_SHARE = 0.22;    // part des égalités
  const TILT_DEG = 9;

  const CSS = `
.br-balance-wrap{display:flex;flex-direction:column;height:100%;min-height:360px;gap:14px;padding:12px 4px;
  box-sizing:border-box;color:var(--text,#f5f0ff);user-select:none;-webkit-user-select:none}
.br-balance-stage{flex:1;position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:220px}
.br-balance-beam{position:relative;width:min(94%,360px);height:10px;border-radius:6px;background:linear-gradient(#c4b5fd,#7c3aed);
  transition:transform .32s cubic-bezier(.22,1,.36,1);transform-origin:50% 50%}
.br-balance-pan{position:absolute;top:10px;width:46%;display:flex;flex-direction:column;align-items:center}
.br-balance-pan.l{left:0}.br-balance-pan.r{right:0}
.br-balance-cord{width:2px;height:26px;background:#a78bfa}
.br-balance-plate{min-width:100%;box-sizing:border-box;padding:14px 6px 12px;border-radius:12px 12px 26px 26px;
  background:var(--card,#221a3d);border:2px solid #8b5cf6;font:700 clamp(16px,4.8vw,22px)/1.15 system-ui,sans-serif;
  text-align:center;white-space:nowrap;transition:transform .32s cubic-bezier(.22,1,.36,1),border-color .2s,box-shadow .2s}
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
.br-balance-still .br-balance-beam,.br-balance-still .br-balance-plate{transition:none}`;

  function injectStyle() {
    if (document.getElementById('br-balance-style')) return;
    const st = document.createElement('style');
    st.id = 'br-balance-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // ---- Calculs ----
  const int = (rng, a, b) => a + Math.floor(rng() * (b - a + 1));
  const pick = (rng, list) => list[Math.floor(rng() * list.length)];
  const num = (v) => ({ text: String(v), value: v });
  const sum = (a, b) => ({ text: `${a} + ${b}`, value: a + b });
  const diff = (a, b) => ({ text: `${a} − ${b}`, value: a - b });
  const prod = (a, b) => ({ text: `${a} × ${b}`, value: a * b });
  const quot = (q, b) => ({ text: `${q * b} ÷ ${b}`, value: q });

  // Un modèle par niveau : chacun renvoie { text, value } (valeur entière ≥ 0).
  const TEMPLATES = [
    (r) => [num(int(r, 1, 20))],
    (r) => [num(int(r, 2, 18)), sum(int(r, 1, 9), int(r, 1, 9))],
    (r) => [sum(int(r, 1, 9), int(r, 1, 9))],
    (r) => [sum(int(r, 2, 20), int(r, 1, 9)), diff(int(r, 10, 20), int(r, 1, 9))],
    (r) => [sum(int(r, 5, 40), int(r, 5, 40)), diff(int(r, 20, 60), int(r, 1, 19)), prod(int(r, 2, 5), int(r, 2, 9))],
    (r) => [prod(int(r, 2, 9), int(r, 2, 9)), sum(int(r, 10, 60), int(r, 10, 40))],
    (r) => [prod(int(r, 2, 9), int(r, 2, 9)), quot(int(r, 2, 12), int(r, 2, 9)), diff(int(r, 30, 99), int(r, 10, 29))],
    (r) => { const a = int(r, 2, 20), b = int(r, 2, 9), c = int(r, 2, 9);
      return [{ text: `${a} + ${b} × ${c}`, value: a + b * c }, prod(int(r, 3, 12), int(r, 3, 9))]; },
    (r) => { const a = int(r, 2, 9), b = int(r, 1, 9), c = int(r, 2, 6);
      return [{ text: `(${a} + ${b}) × ${c}`, value: (a + b) * c }, { text: `${a * c} + ${b * c - 1} + 1`, value: a * c + b * c }]; },
    (r) => { const a = int(r, 3, 9), b = int(r, 3, 9), c = int(r, 1, a * b - 1);
      return [{ text: `${a} × ${b} − ${c}`, value: a * b - c }, quot(int(r, 4, 15), int(r, 3, 12))]; },
    (r) => { const q = int(r, 2, 9), d = int(r, 2, 6), e = int(r, 2, 15);
      return [{ text: `${q * d} ÷ ${d} + ${e}`, value: q + e }, { text: `(${e + q} − ${q}) × ${d}`, value: e * d }]; },
    (r) => { const a = int(r, 11, 25), b = int(r, 3, 9), c = int(r, 10, 99);
      return [{ text: `${a} × ${b} − ${c}`, value: a * b - c }, prod(int(r, 11, 19), int(r, 3, 9)), sum(int(r, 100, 250), int(r, 20, 99))]; },
  ];

  function randomExpr(rng, level) {
    const lv = Math.max(1, Math.min(MAX_LEVEL, level));
    // Mélange du niveau courant et du précédent pour varier.
    const tpl = TEMPLATES[(lv > 1 && rng() < 0.3 ? lv - 2 : lv - 1)];
    const e = pick(rng, tpl(rng));
    return e.value >= 0 ? e : num(Math.abs(e.value));
  }

  function sameValueExpr(rng, level, target, avoidText) {
    for (let i = 0; i < 60; i++) {
      const e = randomExpr(rng, level);
      if (e.value === target && e.text !== avoidText) return e;
    }
    if (target >= 2) { const a = int(rng, 1, target - 1); return sum(a, target - a); }
    return diff(target + 3, 3);
  }

  function nearExpr(rng, level, ref) {
    const span = Math.max(3, Math.round(Math.abs(ref.value) * 0.25));
    let best = null;
    for (let i = 0; i < 60; i++) {
      const e = randomExpr(rng, level);
      if (e.value === ref.value) continue;
      if (Math.abs(e.value - ref.value) <= span) return e;
      if (!best || Math.abs(e.value - ref.value) < Math.abs(best.value - ref.value)) best = e;
    }
    return best || num(ref.value + 1);
  }

  function makeRound(rng, level) {
    const a = randomExpr(rng, level);
    const b = rng() < EQUAL_SHARE ? sameValueExpr(rng, level, a.value, a.text) : nearExpr(rng, level, a);
    return rng() < 0.5 ? { left: a, right: b } : { left: b, right: a };
  }

  const answerOf = (round) => Math.sign(round.left.value - round.right.value); // 1 gauche, 0 égal, −1 droite

  // ---- Jeu ----
  function start(ctx) {
    injectStyle();
    const rng = ctx.rng;
    let level = Math.max(1, Math.min(MAX_LEVEL, ctx.level | 0 || 1));
    let streak = 0;
    let round = null;
    let shownAt = 0;
    let busy = false;
    let stopped = false;
    let timer = 0;

    ctx.root.innerHTML = `
      <div class="br-balance-wrap${ctx.reducedMotion ? ' br-balance-still' : ''}">
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
    const buttons = Array.from(ctx.root.querySelectorAll('.br-balance-btn'));

    function setTilt(sign) {
      // Le côté le plus lourd descend : gauche lourd → rotation négative.
      const deg = -sign * TILT_DEG;
      beam.style.transform = `rotate(${deg}deg)`;
      const counter = `rotate(${-deg}deg)`;
      plateL.style.transform = counter;
      plateR.style.transform = counter;
    }

    function next() {
      if (stopped) return;
      round = makeRound(rng, level);
      plateL.textContent = round.left.text;
      plateR.textContent = round.right.text;
      plateL.className = plateR.className = 'br-balance-plate';
      setTilt(0);
      buttons.forEach((b) => { b.disabled = false; });
      busy = false;
      shownAt = performance.now();
    }

    function answer(choice) {
      if (stopped || busy || !round) return;
      busy = true;
      const rt = Math.round(performance.now() - shownAt);
      const good = answerOf(round);
      const ok = choice === good;
      setTilt(good);
      const mark = ok ? 'ok' : 'ko';
      if (good >= 0) plateL.classList.add(mark);
      if (good <= 0) plateR.classList.add(mark);
      if (ok) {
        ctx.hit({ rt });
        streak += 1;
        if (streak >= UP_AFTER && level < MAX_LEVEL) { level += 1; streak = 0; ctx.setLevel(level); }
      } else {
        ctx.miss({ rt });
        streak = 0;
        if (level > 1) { level -= 1; ctx.setLevel(level); }
      }
      buttons.forEach((b) => { b.disabled = true; });
      timer = setTimeout(next, ctx.reducedMotion ? 150 : FEEDBACK_MS);
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

    ctx.root.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);
    ctx.setLevel(level);
    next();

    return {
      stop() {
        stopped = true;
        clearTimeout(timer);
        ctx.root.removeEventListener('click', onClick);
        window.removeEventListener('keydown', onKey);
        buttons.forEach((b) => { b.disabled = true; });
      },
    };
  }

  window.Brain.register({
    id: ID,
    name: 'Plus lourd',
    domain: 'calcul',
    icon: '⚖️',
    color: '#8b5cf6',
    seconds: 45,
    howto: [
      'Chaque plateau porte un calcul : lequel pèse le plus ?',
      'Touche Gauche, = ou Droite (au clavier : ←, ↓ ou →).',
      'Les calculs se corsent à mesure que tu enchaînes les bonnes réponses.',
    ],
    start,
  });
})();
