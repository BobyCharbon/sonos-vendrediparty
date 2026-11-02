/* Méninges — « Bascule » (flexibilité, changement de règle).
   Une carte « chiffre + lettre » tombe soit dans la zone du haut (le chiffre est-il pair ?), soit dans celle du bas
   (la lettre est-elle une voyelle ?). Oui (→) / Non (←). L'alternance devient de moins en moins prévisible ; aux
   niveaux élevés, les consignes s'effacent : il faut se souvenir de la règle de chaque zone. 45 s. */
(function () {
  'use strict';

  const ID = 'bascule';
  const DIGITS = [2, 3, 4, 5, 6, 7, 8, 9];
  const VOWELS = ['A', 'E', 'I', 'O', 'U'];
  const CONSONANTS = ['B', 'C', 'D', 'F', 'G', 'K', 'M', 'N', 'P', 'R', 'S', 'T'];
  const MAX_LEVEL = 8;
  const HITS_TO_LEVEL_UP = 5;
  const MISSES_TO_LEVEL_DOWN = 2;
  const HIDE_RULES_FROM_LEVEL = 6;
  const FEEDBACK_MS = 220;
  const FEEDBACK_MS_REDUCED = 120;

  const STYLE = `
.br-bascule { display:flex; flex-direction:column; gap:12px; padding:12px 16px 16px; min-height:100%;
  box-sizing:border-box; color:var(--text,#f4f1fa); font-family:inherit; user-select:none; -webkit-user-select:none; }
.br-bascule-board { flex:1; display:flex; flex-direction:column; border-radius:24px; min-height:300px;
  border:1px solid rgba(255,255,255,.1); background:#1d1a2c; }
.br-bascule-zone { flex:1; position:relative; display:flex; align-items:center; justify-content:center;
  padding:30px 12px 12px; min-height:140px; }
.br-bascule-zone + .br-bascule-zone { border-top:2px dashed rgba(255,255,255,.16); }
.br-bascule-top { background:linear-gradient(180deg, rgba(56,201,176,.16), rgba(56,201,176,.04)); border-radius:24px 24px 0 0; }
.br-bascule-bottom { background:linear-gradient(0deg, rgba(255,128,92,.16), rgba(255,128,92,.04)); border-radius:0 0 24px 24px; }
.br-bascule-rule { position:absolute; top:10px; left:14px; right:14px; display:flex; align-items:center; gap:8px;
  font-size:14px; font-weight:700; transition:opacity .3s ease; }
.br-bascule-top .br-bascule-rule { color:#5fe0c8; }
.br-bascule-bottom .br-bascule-rule { color:#ffa184; }
.br-bascule-rule span { display:inline-flex; width:22px; height:22px; border-radius:7px; align-items:center;
  justify-content:center; font-size:13px; color:#1d1a2c; }
.br-bascule-top .br-bascule-rule span { background:#5fe0c8; }
.br-bascule-bottom .br-bascule-rule span { background:#ffa184; }
.br-bascule-hide .br-bascule-rule em { opacity:0; }
.br-bascule-card { display:flex; align-items:center; justify-content:center; gap:4px; width:150px; height:96px;
  border-radius:20px; background:#f6f3ff; color:#1d1828; font-size:52px; font-weight:900; letter-spacing:.02em;
  box-shadow:0 3px 0 rgba(0,0,0,.25), 0 12px 24px rgba(0,0,0,.3); }
.br-bascule-card b { color:#14806f; }
.br-bascule-card i { font-style:normal; color:#c4462a; }
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
`;

  function pick(rng, list) { return list[Math.min(list.length - 1, Math.floor(rng() * list.length))]; }

  // Alternance : niveaux 1-3 = séries régulières (4, 3 puis 2 cartes de suite dans la même zone) ;
  // ensuite, changement de zone au hasard, avec une probabilité qui monte jusqu'à 50 %.
  function nextZone(rng, level, prevZone, runCount) {
    if (prevZone === null) return rng() < 0.5 ? 'top' : 'bottom';
    const other = prevZone === 'top' ? 'bottom' : 'top';
    if (level <= 3) return runCount >= 5 - level ? other : prevZone;
    const switchRate = Math.min(0.5, 0.3 + (level - 4) * 0.05);
    return rng() < switchRate ? other : prevZone;
  }

  function makeCard(rng, zone) {
    const yes = rng() < 0.5;
    let digit;
    let letter;
    if (zone === 'top') {
      digit = pick(rng, DIGITS.filter((d) => (d % 2 === 0) === yes));
      letter = pick(rng, rng() < 0.5 ? VOWELS : CONSONANTS);
    } else {
      letter = pick(rng, yes ? VOWELS : CONSONANTS);
      digit = pick(rng, DIGITS);
    }
    return { zone, digit, letter, yes };
  }

  function start(ctx) {
    const root = ctx.root;
    const esc = ctx.esc;
    const motion = !ctx.reducedMotion;
    let level = Math.max(1, Math.min(MAX_LEVEL, Math.floor(ctx.level) || 1));
    let streak = 0;
    let missRun = 0;
    let zone = null;
    let runCount = 0;
    let card = null;
    let shownAt = 0;
    let locked = true;
    let stopped = false;
    let timer = 0;

    root.innerHTML = `<style>${STYLE}</style>
<div class="br-bascule${motion ? ' br-bascule-motion' : ''}" data-role="game">
  <div class="br-bascule-board">
    <div class="br-bascule-zone br-bascule-top" data-zone="top">
      <div class="br-bascule-rule"><span>1</span><em>Le chiffre est-il pair ?</em></div>
      <div class="br-bascule-card" hidden></div>
    </div>
    <div class="br-bascule-zone br-bascule-bottom" data-zone="bottom">
      <div class="br-bascule-rule"><span>A</span><em>La lettre est-elle une voyelle ?</em></div>
      <div class="br-bascule-card" hidden></div>
    </div>
  </div>
  <div class="br-bascule-btns">
    <button type="button" class="br-bascule-btn br-bascule-no" data-answer="no" aria-label="Non (flèche gauche)">Non <small>←</small></button>
    <button type="button" class="br-bascule-btn br-bascule-yes" data-answer="yes" aria-label="Oui (flèche droite)">Oui <small>→</small></button>
  </div>
</div>`;

    const game = root.querySelector('[data-role="game"]');
    const slots = {
      top: root.querySelector('[data-zone="top"] .br-bascule-card'),
      bottom: root.querySelector('[data-zone="bottom"] .br-bascule-card'),
    };

    function clearSlot(slot) {
      slot.hidden = true;
      slot.textContent = '';
      slot.classList.remove('br-bascule-ok', 'br-bascule-ko', 'br-bascule-in');
    }

    function render() {
      const next = nextZone(ctx.rng, level, zone, runCount);
      runCount = next === zone ? runCount + 1 : 1;
      zone = next;
      card = makeCard(ctx.rng, zone);
      clearSlot(slots.top);
      clearSlot(slots.bottom);
      const slot = slots[zone];
      slot.innerHTML = `<b>${esc(String(card.digit))}</b><i>${esc(card.letter)}</i>`;
      slot.dataset.digit = String(card.digit);
      slot.dataset.letter = card.letter;
      slot.hidden = false;
      if (motion) slot.classList.add('br-bascule-in');
      game.classList.toggle('br-bascule-hide', level >= HIDE_RULES_FROM_LEVEL);
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
      if (stopped || locked || !card) return;
      locked = true;
      root.dataset.state = 'wait';
      const rt = Math.round(performance.now() - shownAt);
      const correct = saysYes === card.yes;
      if (correct) ctx.hit({ rt }); else ctx.miss({ rt });
      adapt(correct);
      if (stopped) return;
      const slot = slots[card.zone];
      slot.classList.remove('br-bascule-in');
      slot.classList.add(correct ? 'br-bascule-ok' : 'br-bascule-ko');
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
    name: 'Bascule',
    domain: 'flexibilite',
    icon: '🔀',
    color: '#38c9b0',
    seconds: 45,
    howto: [
      'Une carte « chiffre + lettre » apparaît en haut ou en bas.',
      'En haut : le chiffre est-il pair ? En bas : la lettre est-elle une voyelle ?',
      'Réponds Oui (→) ou Non (←). Plus tard, les consignes s\'effacent : retiens la règle de chaque zone.',
    ],
    start,
  });
})();
