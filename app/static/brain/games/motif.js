/* Méninges — « Même motif » (vitesse) : les spots allumés sont-ils disposés comme sur la carte d'avant ?
   Une carte glisse de droite à gauche ; Oui / Non en bas (clavier : → = Oui, ← = Non). Partie SANS FIN : le moteur
   gère les 3 vies ; chaque carte a un délai de réponse (trop lent = une vie).

   Niveaux (grille : spots allumés) :
     1 triangle:1 · 2 2×2:1 · 3 2×2:2 · 4-6 3×3:2→4 · 7-14 4×4:3→7 · 15-24 5×5:6→9 · 25-38 6×6:8→11 · 39+ 6×6:12
   Délai : 2800 ms au niveau 1, × 0,94 par niveau vers 650 ms (≈ 1900 ms niv. 10, 1310 niv. 20, 840 niv. 40).
   Faux motifs « proches » (un seul spot glisse d'une case) : 0 aux niveaux 1-2, puis 32 % → 95 % (niveau 28+).
   Au-delà du niveau 40 : 12 spots sur 36, faux motifs presque toujours proches, délai qui continue de raccourcir
   (≈ 700 ms niv. 60) sans descendre sous 650 ms. */
(function () {
  'use strict';

  const ID = 'motif';
  const P = 'br-motif-';
  const COLOR = '#14b8a6';
  const P_MATCH = 0.45;
  const MAX_RUN = 3;
  const UP_AFTER = 6;
  const DOWN_AFTER = 2;
  const FIRST_MEMO_MS = 1200;
  const MEMO_MS = 1000;
  const LEAVE_MS = 420;
  const PRESS_MS = 160;
  const MAX_TRIES = 12;
  const WIN_START = 2800;        // délai de réponse au niveau 1
  const WIN_FLOOR = 650;         // limite humaine visée
  const WIN_DECAY = 0.94;

  // ---------- Dispositions des spots (viewBox 0 0 100 100) ----------
  function grid(n, step) {
    const o = 50 - ((n - 1) * step) / 2;
    const cells = [];
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) cells.push({ x: o + c * step, y: o + r * step, r, c });
    return cells;
  }
  const LAYOUTS = {
    tri3: { spots: [{ x: 50, y: 24, r: 0, c: 1 }, { x: 25, y: 70, r: 1, c: 0 }, { x: 75, y: 70, r: 1, c: 2 }], rad: 14 },
    sq4: { spots: grid(2, 42), rad: 14 },
    g9: { spots: grid(3, 31), rad: 10.5 },
    g16: { spots: grid(4, 24), rad: 8.5 },
    g25: { spots: grid(5, 19.5), rad: 7 },
    g36: { spots: grid(6, 16), rad: 5.8 },
  };
  // [grille, spots allumés, nombre de niveaux] ; le dernier palier dure indéfiniment.
  const STEPS = [
    ['tri3', 1, 1], ['sq4', 1, 1], ['sq4', 2, 1], ['g9', 2, 1], ['g9', 3, 1], ['g9', 4, 1],
    ['g16', 3, 1], ['g16', 4, 1], ['g16', 5, 2], ['g16', 6, 2], ['g16', 7, 2],
    ['g25', 6, 2], ['g25', 7, 2], ['g25', 8, 3], ['g25', 9, 3],
    ['g36', 8, 3], ['g36', 9, 3], ['g36', 10, 4], ['g36', 11, 4], ['g36', 12, Infinity],
  ];
  function stepOf(lv) {
    let first = 1;
    for (const s of STEPS) { if (lv < first + s[2]) return s; first += s[2]; }
    return STEPS[STEPS.length - 1];
  }
  function cfgOf(lv) {
    const s = stepOf(lv);
    return {
      lay: s[0],
      lit: s[1],
      near: lv < 3 ? 0 : Math.min(0.95, 0.25 + 0.025 * lv),
      win: Math.round(WIN_FLOOR + (WIN_START - WIN_FLOOR) * Math.pow(WIN_DECAY, lv - 1)),
      d: Math.max(110, 300 - 6 * (lv - 1)),
    };
  }
  const cfgKey = (cfg) => cfg.lay + ':' + cfg.lit;
  const patKey = (pat) => pat.slice().sort((a, b) => a - b).join('-');

  function neighbours(spots, i) {
    const s = spots[i];
    return spots.map((t, j) => j).filter((j) => j !== i
      && Math.abs(spots[j].r - s.r) <= 1 && Math.abs(spots[j].c - s.c) <= 1);
  }

  function svgFor(pat, cfg) {
    const lay = LAYOUTS[cfg.lay];
    const on = new Set(pat);
    const dots = lay.spots.map((s, i) => (on.has(i)
      ? `<circle class="${P}halo" cx="${s.x}" cy="${s.y}" r="${lay.rad * 1.55}"/>`
        + `<circle class="${P}on" cx="${s.x}" cy="${s.y}" r="${lay.rad}"/>`
      : `<circle class="${P}off" cx="${s.x}" cy="${s.y}" r="${lay.rad}"/>`)).join('');
    return `<svg viewBox="0 0 100 100" aria-hidden="true">${dots}</svg>`;
  }

  // ---------- Styles (injectés une fois) ----------
  const CSS = `
.${P}wrap{display:flex;flex-direction:column;align-items:center;gap:14px;box-sizing:border-box;width:100%;height:100%;
  min-height:440px;padding:10px 16px calc(14px + env(safe-area-inset-bottom,0px));user-select:none;-webkit-user-select:none;
  -webkit-touch-callout:none}
.${P}prompt{margin:0;min-height:24px;font-size:17px;font-weight:650;text-align:center;line-height:1.35}
.${P}stage{position:relative;flex:1;align-self:stretch;margin:0 -16px;min-height:250px;overflow:hidden}
.${P}card{position:absolute;left:50%;top:50%;width:min(72vw,280px);aspect-ratio:1;border-radius:26px;
  background:radial-gradient(120% 90% at 50% 0%,#24305a 0%,#141a33 70%);box-shadow:0 12px 32px rgba(10,15,40,.35);
  display:flex;align-items:center;justify-content:center;transform:translate(-50%,-50%);
  transition:transform var(--d,260ms) cubic-bezier(.2,.8,.2,1),opacity var(--d,260ms) ease}
.${P}card svg{width:84%;height:auto;display:block}
.${P}off{fill:rgba(255,255,255,.07);stroke:rgba(255,255,255,.28);stroke-width:1.4}
.${P}on{fill:#7ff5e6;stroke:${COLOR};stroke-width:2.4}
.${P}halo{fill:${COLOR};opacity:.28}
.${P}enter{transform:translate(70%,-50%) rotate(7deg);opacity:0}
.${P}out{transform:translate(-170%,-50%) rotate(-8deg);opacity:0}
.${P}rm .${P}card{transition:opacity 120ms linear}
.${P}rm .${P}enter,.${P}rm .${P}out{transform:translate(-50%,-50%)}
.${P}mark{position:absolute;top:10px;right:10px;width:34px;height:34px;border-radius:50%;display:none;align-items:center;
  justify-content:center;color:#fff;font-size:19px;font-weight:800;font-style:normal}
.${P}ok .${P}mark{display:flex;background:#30a46c}
.${P}ok .${P}mark::after{content:'✓'}
.${P}ko .${P}mark,.${P}slow .${P}mark{display:flex;background:#e5484d}
.${P}ko .${P}mark::after{content:'✕'}
.${P}slow .${P}mark::after{content:'⏱'}
.${P}bar{position:absolute;left:18px;right:18px;bottom:12px;height:5px;border-radius:3px;background:${COLOR};
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
/* Écran bas (téléphone en paysage, ~300 px de jeu) : tout tient, la carte suit la hauteur disponible. */
@media (max-height:520px){.${P}wrap{min-height:0;gap:6px;padding:4px 12px 8px}
  .${P}prompt{min-height:0;font-size:15px}.${P}stage{min-height:0;container-type:size}
  .${P}card{width:min(72vw,280px,88cqh)}.${P}btn{min-height:50px;font-size:18px}}
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
    let prevPat = null;
    let curPat = null;
    let curCfgKey = null;
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
    const pickIndex = (n) => Math.floor(rng() * n) % n;

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

    function showCard(pat, cfg, asking) {
      const el = document.createElement('div');
      el.className = P + 'card ' + P + 'enter';
      el.dataset.k = cfgKey(cfg) + '|' + patKey(pat);
      el.style.setProperty('--d', cfg.d + 'ms');
      const bar = asking ? `<b class="${P}bar" style="animation-duration:${cfg.win}ms"></b>` : '';
      el.innerHTML = svgFor(pat, cfg) + `<i class="${P}mark"></i>` + bar;
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

    function randomPattern(cfg) {
      const free = LAYOUTS[cfg.lay].spots.map((s, i) => i);
      const chosen = [];
      for (let k = 0; k < cfg.lit; k++) chosen.push(free.splice(pickIndex(free.length), 1)[0]);
      return chosen;
    }
    // Faux motif « proche » : un seul spot allumé glisse vers une case voisine éteinte.
    function nearPattern(prev, cfg) {
      const spots = LAYOUTS[cfg.lay].spots;
      const from = prev[pickIndex(prev.length)];
      const dest = neighbours(spots, from).filter((j) => !prev.includes(j));
      if (!dest.length) return null;
      const to = dest[pickIndex(dest.length)];
      return prev.map((i) => (i === from ? to : i));
    }
    function distractor(prev, cfg) {
      const key = patKey(prev);
      for (let t = 0; t < MAX_TRIES; t++) {
        const cand = rng() < cfg.near ? (nearPattern(prev, cfg) || randomPattern(cfg)) : randomPattern(cfg);
        if (patKey(cand) !== key) return cand;
      }
      const spots = LAYOUTS[cfg.lay].spots;
      const off = spots.map((s, i) => i).filter((i) => !prev.includes(i));
      return prev.slice(1).concat([off[0]]); // repli sûr : toujours différent
    }
    function decideMatch() {
      let match = rng() < P_MATCH;
      const last = answers.slice(-MAX_RUN);
      if (last.length === MAX_RUN && last.every((v) => v === match)) match = !match;
      answers = answers.concat([match]).slice(-MAX_RUN);
      return match;
    }

    function beginMemo(first) {
      phase = 'memo';
      setButtons(false);
      const cfg = cfgOf(level);
      curCfgKey = cfgKey(cfg);
      curPat = randomPattern(cfg);
      showCard(curPat, cfg, false);
      setPrompt(first ? 'Retiens ce motif…' : 'Nouveau niveau : retiens ce motif…');
      later(nextAsk, first ? FIRST_MEMO_MS : MEMO_MS);
    }

    function nextAsk() {
      const cfg = cfgOf(level);
      if (cfgKey(cfg) !== curCfgKey) { beginMemo(false); return; }
      prevPat = curPat;
      curPat = decideMatch() ? prevPat.slice() : distractor(prevPat, cfg);
      showCard(curPat, cfg, true);
      phase = 'ask';
      setButtons(true);
      setPrompt('Même motif que la carte d’avant ?');
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
      const ok = yes === (patKey(curPat) === patKey(prevPat));
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

    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : tout s'arrête (aucune vie perdue loin de l'écran) ; au retour, nouvelle carte à retenir.
    function onPauseChange(paused) {
      if (phase === 'over') return;
      if (paused) {
        timers.forEach((t) => clearTimeout(t));
        timers.clear();
        phase = 'away';
        setButtons(false);
      } else if (phase === 'away') {
        stage.innerHTML = '';
        card = null;
        beginMemo('resume');
      }
    }

    wrap.addEventListener('pointerdown', onPointer);
    wrap.addEventListener('click', onClick);
    window.addEventListener('keydown', onKey);
    if (ctx.onPause) ctx.onPause(function () { onPauseChange(true); });
    if (ctx.onResume) ctx.onResume(function () { onPauseChange(false); });

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
    name: 'Même motif',
    domain: 'vitesse',
    icon: '💡',
    color: COLOR,
    seconds: null,
    howto: [
      'Chaque carte montre des spots, certains allumés. Sont-ils placés exactement comme sur la carte d’avant ? Oui ou Non (au clavier : → Oui, ← Non).',
      'Réponds avant la fin de la barre : trop lent ou faux, tu perds une vie. Sans fin : la partie s’arrête quand tu n’as plus de vie.',
      'Plus tu enchaînes, plus la grille grandit (jusqu’à 6×6), plus il y a de spots et plus ça va vite.',
    ],
    start,
  });
})();
