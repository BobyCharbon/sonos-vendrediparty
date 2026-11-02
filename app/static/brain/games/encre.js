/* Méninges — « Mot ou encre » (flexibilité, effet Stroop).
   En haut : un nom de couleur (on lit son SENS). En bas : un nom de couleur écrit dans une encre (on regarde l'ENCRE).
   Question : le sens du mot du haut = la couleur d'encre du mot du bas ? Oui (→) / Non (←). 45 s. */
(function () {
  'use strict';

  const ID = 'encre';
  // Teintes bien séparées, éclaircies pour rester lisibles sur les cartes sombres du jeu.
  const COLORS = [
    { name: 'rouge', ink: '#ff4d4d' },
    { name: 'bleu', ink: '#4c9dff' },
    { name: 'vert', ink: '#2fd36b' },
    { name: 'jaune', ink: '#ffd60a' },
    { name: 'violet', ink: '#bf86ff' },
    { name: 'orange', ink: '#ff9233' },
  ];
  const MAX_LEVEL = 8;
  const HITS_TO_LEVEL_UP = 5;
  const MISSES_TO_LEVEL_DOWN = 2;
  const FEEDBACK_MS = 220;
  const FEEDBACK_MS_REDUCED = 120;

  const STYLE = `
.br-encre { display:flex; flex-direction:column; gap:14px; padding:12px 16px 16px; min-height:100%;
  box-sizing:border-box; color:var(--text,#f4f1fa); font-family:inherit; user-select:none; -webkit-user-select:none; }
.br-encre-q { text-align:center; font-size:15px; line-height:1.35; color:var(--muted,#a79fba); margin:2px 0 0; }
.br-encre-q b { color:var(--text,#f4f1fa); font-weight:700; }
.br-encre-cards { flex:1; display:flex; flex-direction:column; gap:12px; justify-content:center; }
.br-encre-card { position:relative; border-radius:22px; padding:12px 14px 18px; text-align:center;
  background:#1f1a2e; border:1px solid rgba(255,255,255,.1); box-shadow:0 10px 26px rgba(0,0,0,.3);
  transition:transform .16s ease, box-shadow .16s ease; }
.br-encre-tag { display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:700; letter-spacing:.06em;
  text-transform:uppercase; color:#a79fba; }
.br-encre-tag i { width:10px; height:10px; border-radius:50%; display:inline-block;
  background:conic-gradient(#ff4d4d 0 25%,#4c9dff 0 50%,#2fd36b 0 75%,#ffd60a 0); }
.br-encre-tag i.br-encre-eye { background:#f4f1fa; }
.br-encre-word { font-size:clamp(40px, 13vw, 58px); font-weight:900; line-height:1.15; margin-top:6px;
  letter-spacing:.01em; color:#f4f1fa; min-height:1.15em; }
.br-encre-card.br-encre-ok { box-shadow:0 0 0 4px #3ddc97, 0 10px 26px rgba(0,0,0,.28); }
.br-encre-card.br-encre-ko { box-shadow:0 0 0 4px #ff6b6b, 0 10px 26px rgba(0,0,0,.28); }
.br-encre-motion .br-encre-card.br-encre-ko { transform:translateX(-6px); }
.br-encre-motion .br-encre-card.br-encre-in { animation:br-encre-pop .18s ease-out; }
@keyframes br-encre-pop { from { transform:scale(.96); opacity:.4; } to { transform:none; opacity:1; } }
.br-encre-btns { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.br-encre-btn { min-height:64px; border:0; border-radius:18px; font:inherit; font-size:20px; font-weight:800;
  color:#fff; cursor:pointer; touch-action:manipulation; display:flex; align-items:center; justify-content:center; gap:8px; }
.br-encre-btn:active { transform:scale(.97); }
.br-encre-no { background:#c7364f; }
.br-encre-yes { background:#1f9e68; }
.br-encre-btn small { font-size:14px; opacity:.75; font-weight:600; }
`;

  function pickIndex(rng, n) { return Math.min(n - 1, Math.floor(rng() * n)); }
  function pickOther(rng, n, avoid) {
    const choices = [];
    for (let i = 0; i < n; i++) if (avoid.indexOf(i) < 0) choices.push(i);
    return choices[pickIndex(rng, choices.length)];
  }
  function paletteSize(level) { return level >= 5 ? 6 : level >= 3 ? 5 : 4; }

  // Une manche : meaning = sens du mot du haut, topInk = encre du mot du haut (neutre aux premiers niveaux),
  // word = mot du bas, ink = encre du mot du bas, yes = bonne réponse.
  function makeTrial(rng, level) {
    const n = paletteSize(level);
    const yes = rng() < 0.5;
    const meaning = pickIndex(rng, n);
    const ink = yes ? meaning : pickOther(rng, n, [meaning]);
    // Piège : quand la réponse est Non, le mot du bas dit souvent la couleur du haut (on lit au lieu de regarder).
    const trapRate = Math.min(0.7, 0.25 + level * 0.06);
    let word;
    if (!yes && rng() < trapRate) word = meaning;
    else word = pickOther(rng, n, level >= 2 ? [ink] : []);
    // Dès le niveau 4, le mot du haut est lui aussi coloré (une autre couleur que son sens).
    const topInk = level >= 4 && rng() < 0.6 ? pickOther(rng, n, [meaning]) : -1;
    return { meaning, topInk, word, ink, yes };
  }

  function start(ctx) {
    const root = ctx.root;
    const motion = !ctx.reducedMotion;
    let level = Math.max(1, Math.min(MAX_LEVEL, Math.floor(ctx.level) || 1));
    let streak = 0;
    let missRun = 0;
    let trial = null;
    let shownAt = 0;
    let locked = true;
    let stopped = false;
    let timer = 0;

    root.innerHTML = `<style>${STYLE}</style>
<div class="br-encre${motion ? ' br-encre-motion' : ''}">
  <p class="br-encre-q">Le <b>sens</b> du mot du haut est-il la <b>couleur</b> d'encre du mot du bas ?</p>
  <div class="br-encre-cards">
    <div class="br-encre-card" data-role="top">
      <div class="br-encre-tag"><i class="br-encre-eye"></i>Sens</div>
      <div class="br-encre-word" data-role="topWord"></div>
    </div>
    <div class="br-encre-card" data-role="bottom">
      <div class="br-encre-tag"><i></i>Encre</div>
      <div class="br-encre-word" data-role="bottomWord"></div>
    </div>
  </div>
  <div class="br-encre-btns">
    <button type="button" class="br-encre-btn br-encre-no" data-answer="no" aria-label="Non (flèche gauche)">Non <small>←</small></button>
    <button type="button" class="br-encre-btn br-encre-yes" data-answer="yes" aria-label="Oui (flèche droite)">Oui <small>→</small></button>
  </div>
</div>`;

    const topCard = root.querySelector('[data-role="top"]');
    const bottomCard = root.querySelector('[data-role="bottom"]');
    const topWord = root.querySelector('[data-role="topWord"]');
    const bottomWord = root.querySelector('[data-role="bottomWord"]');
    const cards = [topCard, bottomCard];

    function setCardsClass(cls) {
      cards.forEach((c) => {
        c.classList.remove('br-encre-ok', 'br-encre-ko', 'br-encre-in');
        if (cls) c.classList.add(cls);
      });
    }

    function render() {
      trial = makeTrial(ctx.rng, level);
      topWord.textContent = COLORS[trial.meaning].name;
      topWord.style.color = trial.topInk >= 0 ? COLORS[trial.topInk].ink : '';
      bottomWord.textContent = COLORS[trial.word].name;
      bottomWord.style.color = COLORS[trial.ink].ink;
      topCard.dataset.meaning = COLORS[trial.meaning].name;
      bottomCard.dataset.ink = COLORS[trial.ink].name;
      setCardsClass(motion ? 'br-encre-in' : '');
      shownAt = performance.now();
      locked = false;
      root.dataset.state = 'ready';
    }

    function adapt(correct) {
      if (correct) {
        missRun = 0;
        streak += 1;
        if (streak >= HITS_TO_LEVEL_UP && level < MAX_LEVEL) { level += 1; streak = 0; ctx.setLevel(level); }
        return;
      }
      streak = 0;
      missRun += 1;
      if (missRun >= MISSES_TO_LEVEL_DOWN && level > 1) { level -= 1; missRun = 0; ctx.setLevel(level); }
    }

    function answer(saysYes) {
      if (stopped || locked || !trial) return;
      locked = true;
      root.dataset.state = 'wait';
      const rt = Math.round(performance.now() - shownAt);
      const correct = saysYes === trial.yes;
      if (correct) ctx.hit({ rt }); else ctx.miss({ rt });
      adapt(correct);
      if (stopped) return;
      setCardsClass(correct ? 'br-encre-ok' : 'br-encre-ko');
      timer = setTimeout(() => { timer = 0; if (!stopped) render(); }, motion ? FEEDBACK_MS : FEEDBACK_MS_REDUCED);
    }

    function onPointer(e) {
      const btn = e.target.closest('[data-answer]');
      if (!btn || !root.contains(btn)) return;
      e.preventDefault();
      answer(btn.dataset.answer === 'yes');
    }
    function onKey(e) {
      if (e.key === 'ArrowRight') { e.preventDefault(); answer(true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); answer(false); }
    }

    function stop() {
      if (stopped) return;
      stopped = true;
      locked = true;
      if (timer) clearTimeout(timer);
      timer = 0;
      root.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
      root.dataset.state = 'stopped';
    }

    root.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    ctx.onTimeUp(stop);
    ctx.setLevel(level);
    render();
    return { stop };
  }

  Brain.register({
    id: ID,
    name: 'Mot ou encre',
    domain: 'flexibilite',
    icon: '🖋️',
    color: '#4c9dff',
    seconds: 45,
    howto: [
      'En haut, lis le mot : c\'est son SENS qui compte.',
      'En bas, ignore le mot : regarde seulement la COULEUR de son encre.',
      'Le sens du haut = l\'encre du bas ? Oui (→) ou Non (←), le plus vite possible.',
    ],
    start,
  });
})();
