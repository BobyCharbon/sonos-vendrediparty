/* Méninges — « Mot ou encre » (flexibilité, effet Stroop), SANS FIN.
   Carte « Sens » : un nom de couleur (on lit son SENS). Carte « Encre » : un nom de couleur écrit dans une encre (on
   regarde l'ENCRE). Le sens = la couleur d'encre ? Oui (→) / Non (←), avant la fin de la barre de temps.
   Table des niveaux (L = niveau) :
     délai          850 + 2650 × 0,95^(L−1) ms (L1 3,5 s · L10 2,4 · L20 1,85 · L30 1,45 · L40 1,2 · L60 0,98 → 0,85)
     couleurs       4 (L1-2), 5 (L3-5), 6 (L6-11), 7 avec rose (L12-19), 8 avec marron (L20+)
     piège          quand c'est Non, le mot « Encre » dit la couleur du sens : 28 % (L1) → 85 % (L20+)
     mot Sens coloré  dès L4 : 30 % → 90 % (L24+), dans une autre encre que son sens
     cartes croisées  dès L21 : les cartes Sens / Encre échangent leur place, 5 % → 50 % (L44+)
   Au-delà : le délai continue de raccourcir vers 0,85 s, pièges et cartes croisées au maximum.
   Pas de réponse à temps ou mauvaise réponse = ctx.miss ; 8 bonnes d'affilée = niveau +1 ; 2 erreurs dans un niveau
   = niveau −1 (jamais sous le palier de départ). */
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
    { name: 'rose', ink: '#ff7ac8' },
    { name: 'marron', ink: '#c08a5a' },
  ];
  const LEVELS_PER_TIER = 5;
  const HITS_TO_LEVEL_UP = 8;
  const MISSES_TO_LEVEL_DOWN = 2;
  const FEEDBACK_MS = 220;
  const FEEDBACK_MS_REDUCED = 120;

  const STYLE = `
.br-encre { display:flex; flex-direction:column; gap:14px; padding:12px 16px 16px; min-height:100%;
  box-sizing:border-box; color:var(--text,#f4f1fa); font-family:inherit; user-select:none; -webkit-user-select:none; }
.br-encre-q { text-align:center; font-size:15px; line-height:1.35; color:var(--muted,#a79fba); margin:2px 0 0; }
.br-encre-q b { color:var(--text,#f4f1fa); font-weight:700; }
.br-encre-time { height:6px; border-radius:3px; background:rgba(255,255,255,.1); }
.br-encre-time i { display:block; height:100%; border-radius:3px; background:#4c9dff; transform-origin:left center; }
.br-encre-cards { flex:1; display:flex; flex-direction:column; gap:12px; justify-content:center; }
.br-encre-cards.br-encre-swap { flex-direction:column-reverse; }
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

  function deadlineMs(level) { return Math.round(850 + 2650 * Math.pow(0.95, level - 1)); }
  function paletteSize(level) { return level >= 20 ? 8 : level >= 12 ? 7 : level >= 6 ? 6 : level >= 3 ? 5 : 4; }
  function trapRate(level) { return Math.min(0.85, 0.25 + level * 0.03); }
  function topInkRate(level) { return level < 4 ? 0 : Math.min(0.9, 0.3 + (level - 4) * 0.03); }
  function swapRate(level) { return level < 21 ? 0 : Math.min(0.5, 0.05 + (level - 21) * 0.02); }

  function pickIndex(rng, n) { return Math.min(n - 1, Math.floor(rng() * n)); }
  function pickOther(rng, n, avoid) {
    const choices = [];
    for (let i = 0; i < n; i++) if (avoid.indexOf(i) < 0) choices.push(i);
    return choices[pickIndex(rng, choices.length)];
  }

  // Une manche : meaning = sens du mot Sens, topInk = encre du mot Sens (-1 = neutre), word = mot de la carte Encre,
  // ink = encre de ce mot, swap = cartes échangées, yes = bonne réponse.
  function makeTrial(rng, level) {
    const n = paletteSize(level);
    const yes = rng() < 0.5;
    const meaning = pickIndex(rng, n);
    const ink = yes ? meaning : pickOther(rng, n, [meaning]);
    // Piège : quand la réponse est Non, le mot Encre dit souvent la couleur du sens (on lit au lieu de regarder).
    let word;
    if (!yes && rng() < trapRate(level)) word = meaning;
    else word = pickOther(rng, n, level >= 2 ? [ink] : []);
    const topInk = rng() < topInkRate(level) ? pickOther(rng, n, [meaning]) : -1;
    const swap = rng() < swapRate(level);
    return { meaning, topInk, word, ink, swap, yes };
  }

  function start(ctx) {
    const root = ctx.root;
    const motion = !ctx.reducedMotion;
    let level = Math.max(1, Math.floor(ctx.level) || 1);
    const floorLevel = level - ((level - 1) % LEVELS_PER_TIER);
    let streak = 0;
    let levelMisses = 0;
    let trial = null;
    let shownAt = 0;
    let deadline = 0;
    let locked = true;
    let stopped = false;
    let timer = 0;
    let limitTimer = 0;

    root.innerHTML = `<style>${STYLE}</style>
<div class="br-encre${motion ? ' br-encre-motion' : ''}">
  <p class="br-encre-q">Le <b>sens</b> du mot « Sens » est-il la <b>couleur</b> d'encre du mot « Encre » ?</p>
  <div class="br-encre-time" aria-hidden="true"><i data-role="time"></i></div>
  <div class="br-encre-cards" data-role="cards">
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

    const cardsBox = root.querySelector('[data-role="cards"]');
    const topCard = root.querySelector('[data-role="top"]');
    const bottomCard = root.querySelector('[data-role="bottom"]');
    const topWord = root.querySelector('[data-role="topWord"]');
    const bottomWord = root.querySelector('[data-role="bottomWord"]');
    const timeBar = root.querySelector('[data-role="time"]');
    const cards = [topCard, bottomCard];

    function setCardsClass(cls) {
      cards.forEach((c) => {
        c.classList.remove('br-encre-ok', 'br-encre-ko', 'br-encre-in');
        if (cls) c.classList.add(cls);
      });
    }

    function runTimeBar(ms) {
      timeBar.style.transition = 'none';
      timeBar.style.transform = 'scaleX(1)';
      void timeBar.offsetWidth;
      timeBar.style.transition = `transform ${ms}ms linear`;
      timeBar.style.transform = 'scaleX(0)';
    }

    function render() {
      trial = makeTrial(ctx.rng, level);
      topWord.textContent = COLORS[trial.meaning].name;
      topWord.style.color = trial.topInk >= 0 ? COLORS[trial.topInk].ink : '';
      bottomWord.textContent = COLORS[trial.word].name;
      bottomWord.style.color = COLORS[trial.ink].ink;
      topCard.dataset.meaning = COLORS[trial.meaning].name;
      bottomCard.dataset.ink = COLORS[trial.ink].name;
      cardsBox.classList.toggle('br-encre-swap', trial.swap);
      setCardsClass(motion ? 'br-encre-in' : '');
      deadline = deadlineMs(level);
      root.dataset.deadline = String(deadline);
      runTimeBar(deadline);
      shownAt = performance.now();
      locked = false;
      root.dataset.state = 'ready';
      limitTimer = setTimeout(() => { limitTimer = 0; resolve(null); }, deadline);
    }

    function changeLevel(n) {
      streak = 0;
      levelMisses = 0;
      const next = Math.max(floorLevel, n);
      if (next === level) return;
      level = next;
      ctx.setLevel(level);
    }

    function adapt(correct) {
      if (correct) {
        if (++streak >= HITS_TO_LEVEL_UP) changeLevel(level + 1);
        return;
      }
      streak = 0;
      if (++levelMisses >= MISSES_TO_LEVEL_DOWN) changeLevel(level - 1);
    }

    // saysYes = null : temps écoulé.
    function resolve(saysYes) {
      if (stopped || locked || !trial) return;
      locked = true;
      if (limitTimer) clearTimeout(limitTimer);
      limitTimer = 0;
      root.dataset.state = 'wait';
      const rt = saysYes === null ? deadline : Math.round(performance.now() - shownAt);
      const correct = saysYes === trial.yes;
      if (correct) ctx.hit({ rt }); else ctx.miss({ rt });
      if (stopped) return;
      adapt(correct);
      timeBar.style.transition = 'none';
      setCardsClass(correct ? 'br-encre-ok' : 'br-encre-ko');
      timer = setTimeout(() => { timer = 0; if (!stopped) render(); }, motion ? FEEDBACK_MS : FEEDBACK_MS_REDUCED);
    }

    function onPointer(e) {
      const btn = e.target.closest('[data-answer]');
      if (!btn || !root.contains(btn)) return;
      e.preventDefault();
      resolve(btn.dataset.answer === 'yes');
    }
    function onKey(e) {
      if (e.key === 'ArrowRight') { e.preventDefault(); resolve(true); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); resolve(false); }
    }

    function stop() {
      if (stopped) return;
      stopped = true;
      locked = true;
      if (timer) clearTimeout(timer);
      if (limitTimer) clearTimeout(limitTimer);
      timer = 0;
      limitTimer = 0;
      timeBar.style.transition = 'none';
      root.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
      root.dataset.state = 'stopped';
    }

    root.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    if (typeof ctx.onTimeUp === 'function') ctx.onTimeUp(stop);
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
    seconds: null,
    howto: [
      'Carte « Sens » : lis le mot, c\'est son SENS qui compte. Carte « Encre » : regarde seulement la COULEUR de l\'encre.',
      'Le sens = l\'encre ? Oui (→) ou Non (←) avant la fin de la barre. Une erreur ou un retard coûte une vie.',
      'Plus tu montes, plus c\'est rapide, avec plus de couleurs ; plus tard, les deux cartes échangent leur place.',
    ],
    start,
  });
})();
