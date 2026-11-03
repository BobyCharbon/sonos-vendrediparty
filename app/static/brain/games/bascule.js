/* Méninges — « Bascule » (flexibilité, changement de règle), SANS FIN.
   Une carte « chiffre + lettre » tombe dans une des zones ; chaque zone a sa question. Oui (→) / Non (←), avant la fin
   de la barre de temps.
   Table des niveaux (L = niveau) :
     délai        950 + 2550 × 0,95^(L−1) ms (L1 3,5 s · L10 2,5 · L20 1,9 · L30 1,55 · L40 1,3 · L60 1,07 → 0,95)
     zones        2 (pair ? / voyelle ?) L1-10 · 3 (+ couleur chaude ?) L11-20 · 4 (+ consonne ?) L21+
     alternance   L1-3 séries régulières (4, 3, 2 cartes) ; L4+ changement de zone au hasard 30 % → 80 % (L24+)
     consignes    visibles jusqu'à L7, puis effacées (montrées 4 cartes après chaque nouvelle zone ou changement)
     carte colorée  dès L11 (chaude ou froide), même hors de la zone « couleur chaude ? » : un piège de plus
     règles qui tournent  dès L31 : les règles changent de zone toutes les 12 cartes (8 dès L41, 6 dès L51)
   Au-delà : le délai continue de raccourcir vers 0,95 s, alternance et rotation des règles au maximum.
   Pas de réponse à temps ou mauvaise réponse = ctx.miss ; 8 bonnes d'affilée = niveau +1 ; 2 erreurs dans un niveau
   = niveau −1 (jamais sous le palier de départ). */
(function () {
  'use strict';

  const ID = 'bascule';
  const DIGITS = [2, 3, 4, 5, 6, 7, 8, 9];
  const VOWELS = ['A', 'E', 'I', 'O', 'U'];
  const CONSONANTS = ['B', 'C', 'D', 'F', 'G', 'K', 'M', 'N', 'P', 'R', 'S', 'T'];
  const WARM = ['#ff8a5c', '#ffcf4a', '#ff6b8b'];
  const COLD = ['#6fb6ff', '#5fe0a0', '#b49bff'];
  const RULES = {
    pair: { badge: '2', text: 'Le chiffre est-il pair ?', test: (c) => c.digit % 2 === 0 },
    voyelle: { badge: 'A', text: 'La lettre est-elle une voyelle ?', test: (c) => VOWELS.includes(c.letter) },
    chaude: { badge: '🔥', text: 'La carte est-elle de couleur chaude ?', test: (c) => c.warm === true },
    consonne: { badge: 'B', text: 'La lettre est-elle une consonne ?', test: (c) => !VOWELS.includes(c.letter) },
  };
  const RULE_ORDER = ['pair', 'voyelle', 'chaude', 'consonne'];
  const ZONE_TINTS = ['#5fe0c8', '#ffa184', '#ff7ac8', '#7fb2ff'];
  const LEVELS_PER_TIER = 5;
  const HITS_TO_LEVEL_UP = 8;
  const MISSES_TO_LEVEL_DOWN = 2;
  const HIDE_RULES_FROM_LEVEL = 8;
  const COLORED_CARDS_FROM_LEVEL = 11;
  const ROTATE_RULES_FROM_LEVEL = 31;
  const REVEAL_CARDS = 4;
  const FEEDBACK_MS = 220;
  const FEEDBACK_MS_REDUCED = 120;

  const STYLE = `
.br-bascule { display:flex; flex-direction:column; gap:12px; padding:12px 16px 16px; min-height:100%;
  box-sizing:border-box; color:var(--text,#f4f1fa); font-family:inherit; user-select:none; -webkit-user-select:none; }
.br-bascule-time { height:6px; border-radius:3px; background:rgba(255,255,255,.1); }
.br-bascule-time i { display:block; height:100%; border-radius:3px; background:#38c9b0; transform-origin:left center; }
.br-bascule-board { flex:1; display:flex; flex-direction:column; border-radius:24px; min-height:300px;
  border:1px solid rgba(255,255,255,.1); background:#1d1a2c; }
.br-bascule-zone { --t:#5fe0c8; flex:1; position:relative; display:flex; align-items:center; justify-content:center;
  padding:30px 12px 10px; min-height:96px; background:linear-gradient(180deg, color-mix(in srgb, var(--t) 16%, transparent), transparent); }
.br-bascule-zone:first-child { border-radius:24px 24px 0 0; }
.br-bascule-zone:last-child { border-radius:0 0 24px 24px; }
.br-bascule-zone + .br-bascule-zone { border-top:2px dashed rgba(255,255,255,.16); }
.br-bascule-rule { position:absolute; top:8px; left:14px; right:14px; display:flex; align-items:center; gap:8px;
  font-size:14px; font-weight:700; color:var(--t); }
.br-bascule-rule em { font-style:normal; transition:opacity .3s ease; }
.br-bascule-rule span { display:inline-flex; width:22px; height:22px; border-radius:7px; align-items:center;
  justify-content:center; font-size:13px; color:#1d1a2c; background:var(--t); }
.br-bascule-hide .br-bascule-rule em { opacity:0; }
.br-bascule-note { text-align:center; font-size:14px; font-weight:800; color:#ffd60a; min-height:18px; margin:0; }
.br-bascule-card { display:flex; align-items:center; justify-content:center; gap:4px; width:150px; height:84px;
  border-radius:20px; background:#f6f3ff; color:#1d1828; font-size:48px; font-weight:900; letter-spacing:.02em;
  box-shadow:0 3px 0 rgba(0,0,0,.25), 0 12px 24px rgba(0,0,0,.3); }
.br-bascule-many .br-bascule-card { height:66px; width:128px; font-size:38px; border-radius:16px; }
.br-bascule-card b { color:#14806f; }
.br-bascule-card i { font-style:normal; color:#c4462a; }
.br-bascule-card.br-bascule-tinted b, .br-bascule-card.br-bascule-tinted i { color:#1d1828; }
.br-bascule-card[hidden] { display:none; }
.br-bascule-card.br-bascule-ok { box-shadow:0 0 0 4px #3ddc97, 0 12px 24px rgba(0,0,0,.3); }
.br-bascule-card.br-bascule-ko { box-shadow:0 0 0 4px #ff6b6b, 0 12px 24px rgba(0,0,0,.3); }
.br-bascule-motion .br-bascule-card.br-bascule-in { animation:br-bascule-drop .18s ease-out; }
.br-bascule-motion .br-bascule-card.br-bascule-ko { transform:rotate(-4deg); }
@keyframes br-bascule-drop { from { transform:scale(.85); opacity:.3; } to { transform:none; opacity:1; } }
.br-bascule-btns { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.br-bascule-btn { min-height:64px; border:0; border-radius:18px; font:inherit; font-size:20px; font-weight:800;
  color:#fff; cursor:pointer; touch-action:manipulation; display:flex; align-items:center; justify-content:center; gap:8px; }
.br-bascule-btn:active { transform:scale(.97); }
.br-bascule-no { background:#c7364f; }
.br-bascule-yes { background:#1f9e68; }
.br-bascule-btn small { font-size:14px; opacity:.75; font-weight:600; }
/* Écran bas (téléphone en paysage, ~290 px de jeu) : zones côte à côte, cartes plus petites. */
@media (max-height:520px) {
  .br-bascule { gap:6px; padding:4px 12px 8px; }
  .br-bascule-note { min-height:16px; font-size:13px; }
  .br-bascule-board { flex-direction:row; min-height:0; }
  .br-bascule-zone { min-height:0; padding:30px 6px 8px; }
  .br-bascule-zone:first-child { border-radius:24px 0 0 24px; }
  .br-bascule-zone:last-child { border-radius:0 24px 24px 0; }
  .br-bascule-zone + .br-bascule-zone { border-top:0; border-left:2px dashed rgba(255,255,255,.16); }
  .br-bascule-rule { font-size:12px; left:8px; right:8px; }
  .br-bascule-card, .br-bascule-many .br-bascule-card { width:min(110px, 100%); height:62px; font-size:34px; border-radius:16px; }
  .br-bascule-btn { min-height:52px; }
}
`;

  function deadlineMs(level) { return Math.round(950 + 2550 * Math.pow(0.95, level - 1)); }
  function zoneCount(level) { return level >= 21 ? 4 : level >= 11 ? 3 : 2; }
  function switchRate(level) { return Math.min(0.8, 0.3 + (level - 4) * 0.025); }
  function rotateEvery(level) { return level >= 51 ? 6 : level >= 41 ? 8 : 12; }
  function pick(rng, list) { return list[Math.min(list.length - 1, Math.floor(rng() * list.length))]; }

  function shuffled(rng, list) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }

  // Alternance : niveaux 1-3 = séries régulières (4, 3 puis 2 cartes de suite dans la même zone, puis zone suivante) ;
  // ensuite, changement de zone au hasard, de plus en plus fréquent.
  function nextZone(rng, level, prev, runCount, count) {
    if (prev === null || prev >= count) return Math.floor(rng() * count);
    if (level <= 3) return runCount >= 5 - level ? (prev + 1) % count : prev;
    if (rng() >= switchRate(level)) return prev;
    const others = [];
    for (let z = 0; z < count; z++) if (z !== prev) others.push(z);
    return pick(rng, others);
  }

  // Carte pour la règle de sa zone : la réponse (Oui / Non) est tirée d'abord, le reste au hasard.
  function makeCard(rng, rule, colored) {
    const yes = rng() < 0.5;
    for (;;) {
      const warm = colored ? rng() < 0.5 : null;
      const card = { digit: pick(rng, DIGITS), letter: pick(rng, rng() < 0.45 ? VOWELS : CONSONANTS), warm,
        tint: colored ? pick(rng, warm ? WARM : COLD) : '' };
      if (RULES[rule].test(card) === yes) return { ...card, rule, yes };
    }
  }

  function start(ctx) {
    const root = ctx.root;
    const esc = ctx.esc;
    const motion = !ctx.reducedMotion;
    let level = Math.max(1, Math.floor(ctx.level) || 1);
    const floorLevel = level - ((level - 1) % LEVELS_PER_TIER);
    let streak = 0;
    let levelMisses = 0;
    let zoneRules = [];
    let zone = null;
    let runCount = 0;
    let reveal = 0;
    let sinceRotate = 0;
    let card = null;
    let shownAt = 0;
    let deadline = 0;
    let locked = true;
    let stopped = false;
    let timer = 0;
    let limitTimer = 0;

    root.innerHTML = `<style>${STYLE}</style>
<div class="br-bascule${motion ? ' br-bascule-motion' : ''}" data-role="game">
  <div class="br-bascule-time" aria-hidden="true"><i data-role="time"></i></div>
  <p class="br-bascule-note" data-role="note" aria-live="polite"></p>
  <div class="br-bascule-board" data-role="board"></div>
  <div class="br-bascule-btns">
    <button type="button" class="br-bascule-btn br-bascule-no" data-answer="no" aria-label="Non (flèche gauche)">Non <small>←</small></button>
    <button type="button" class="br-bascule-btn br-bascule-yes" data-answer="yes" aria-label="Oui (flèche droite)">Oui <small>→</small></button>
  </div>
</div>`;

    const game = root.querySelector('[data-role="game"]');
    const board = root.querySelector('[data-role="board"]');
    const note = root.querySelector('[data-role="note"]');
    const timeBar = root.querySelector('[data-role="time"]');
    let slots = [];

    function drawBoard(rules, message) {
      zoneRules = rules;
      board.innerHTML = rules.map((r, i) => `<div class="br-bascule-zone" data-zone="${i}" data-rule="${esc(r)}" style="--t:${ZONE_TINTS[RULE_ORDER.indexOf(r)]}">
      <div class="br-bascule-rule"><span>${esc(RULES[r].badge)}</span><em>${esc(RULES[r].text)}</em></div>
      <div class="br-bascule-card" hidden></div></div>`).join('');
      slots = [...board.querySelectorAll('.br-bascule-card')];
      game.classList.toggle('br-bascule-many', rules.length >= 4);
      note.textContent = message || '';
      reveal = REVEAL_CARDS;
      sinceRotate = 0;
      zone = null;
    }

    function syncBoard() {
      const count = zoneCount(level);
      if (count !== zoneRules.length) {
        const added = count > zoneRules.length && zoneRules.length > 0;
        drawBoard(RULE_ORDER.slice(0, count), added ? 'Nouvelle règle : ' + RULES[RULE_ORDER[count - 1]].text : '');
        return;
      }
      if (level >= ROTATE_RULES_FROM_LEVEL && sinceRotate >= rotateEvery(level)) {
        let next = shuffled(ctx.rng, zoneRules);
        while (next.every((r, i) => r === zoneRules[i])) next = shuffled(ctx.rng, zoneRules);
        drawBoard(next, 'Les règles changent de place !');
      }
    }

    function runTimeBar(ms) {
      timeBar.style.transition = 'none';
      timeBar.style.transform = 'scaleX(1)';
      void timeBar.offsetWidth;
      timeBar.style.transition = `transform ${ms}ms linear`;
      timeBar.style.transform = 'scaleX(0)';
    }

    function render() {
      syncBoard();
      const next = nextZone(ctx.rng, level, zone, runCount, zoneRules.length);
      runCount = next === zone ? runCount + 1 : 1;
      zone = next;
      card = makeCard(ctx.rng, zoneRules[zone], level >= COLORED_CARDS_FROM_LEVEL);
      slots.forEach((s) => { s.hidden = true; s.textContent = ''; s.className = 'br-bascule-card'; s.style.background = ''; });
      const slot = slots[zone];
      slot.innerHTML = `<b>${esc(String(card.digit))}</b><i>${esc(card.letter)}</i>`;
      slot.dataset.digit = String(card.digit);
      slot.dataset.letter = card.letter;
      slot.dataset.warm = card.warm === null ? '' : String(card.warm);
      if (card.tint) { slot.style.background = card.tint; slot.classList.add('br-bascule-tinted'); }
      slot.hidden = false;
      if (motion) slot.classList.add('br-bascule-in');
      game.classList.toggle('br-bascule-hide', level >= HIDE_RULES_FROM_LEVEL && reveal <= 0);
      if (reveal > 0) reveal -= 1; else note.textContent = '';
      sinceRotate += 1;
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
      if (stopped || locked || !card) return;
      locked = true;
      if (limitTimer) clearTimeout(limitTimer);
      limitTimer = 0;
      root.dataset.state = 'wait';
      const rt = saysYes === null ? deadline : Math.round(performance.now() - shownAt);
      const correct = saysYes === card.yes;
      if (correct) ctx.hit({ rt }); else ctx.miss({ rt });
      if (stopped) return;
      adapt(correct);
      timeBar.style.transition = 'none';
      const slot = slots[zone];
      slot.classList.remove('br-bascule-in');
      slot.classList.add(correct ? 'br-bascule-ok' : 'br-bascule-ko');
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

    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : la carte est retirée sans
    // compter (aucune vie perdue loin de l'écran) ; au retour, nouvelle carte au même niveau.
    function pause() {
      if (stopped) return;
      locked = true;
      if (timer) clearTimeout(timer);
      if (limitTimer) clearTimeout(limitTimer);
      timer = 0;
      limitTimer = 0;
      timeBar.style.transition = 'none';
      root.dataset.state = 'paused';
    }
    function resume() { if (!stopped) render(); }

    root.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    if (ctx.onPause) ctx.onPause(pause);
    if (ctx.onResume) ctx.onResume(resume);
    if (typeof ctx.onTimeUp === 'function') ctx.onTimeUp(stop);
    ctx.setLevel(level);
    render();
    return { stop };
  }

  Brain.register({
    id: ID,
    name: 'Bascule',
    domain: 'flexibilite',
    icon: '🔀',
    color: '#38c9b0',
    seconds: null,
    howto: [
      'Une carte « chiffre + lettre » apparaît dans une zone ; chaque zone a sa question (chiffre pair ? voyelle ?…).',
      'Réponds Oui (→) ou Non (←) avant la fin de la barre. Une erreur ou un retard coûte une vie.',
      'Plus tu montes, plus c\'est rapide : les consignes s\'effacent, de nouvelles règles arrivent, puis elles changent de zone.',
    ],
    start,
  });
})();
