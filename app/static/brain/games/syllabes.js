/* Méninges — « Débuts de mots » (logique / langage) : 3 lettres de départ ; taper un maximum de vrais mots
   français qui commencent par elles, en 60 s. Dictionnaire local (mots_fr.js, chargé à la demande) ; saisie
   acceptée avec ou sans accents. Mot long = points en plus ; mot inconnu ou déjà donné = erreur. */
(function () {
  'use strict';
  const ID = 'syllabes';
  const PREFIX_LEN = 3;
  const LONG_WORD = 7;          // ≥ 7 lettres : un point de plus
  const VERY_LONG_WORD = 9;     // ≥ 9 lettres : encore un de plus
  const UP_EVERY = 5;           // mots valides pour monter d'un niveau
  const MAX_LEVEL = 10;
  const NOTE_MS = 1400;
  const SELF = (document.currentScript && document.currentScript.src) || '/static/brain/games/syllabes.js';
  const DICT_URL = SELF.replace(/syllabes\.js(\?.*)?$/, 'mots_fr.js');

  const CSS = `
.br-syllabes-wrap{display:flex;flex-direction:column;height:100%;min-height:320px;gap:12px;padding:10px 4px;box-sizing:border-box;
  color:var(--text,#f5f0ff)}
.br-syllabes-tiles{display:flex;justify-content:center;gap:8px}
.br-syllabes-tile{width:54px;height:62px;display:flex;align-items:center;justify-content:center;border-radius:14px;
  background:linear-gradient(160deg,#fb7185,#e11d48);color:#fff;font:800 32px/1 system-ui,sans-serif;text-transform:uppercase;
  box-shadow:0 4px 0 #9f1239}
.br-syllabes-form{display:flex;gap:8px}
.br-syllabes-field{flex:1;display:flex;align-items:center;min-width:0;border-radius:14px;background:var(--card,#221a3d);
  border:2px solid #fb7185;padding:0 12px;transition:border-color .15s}
.br-syllabes-field.ko{border-color:var(--err,#ff6b6b)}.br-syllabes-field.ok{border-color:var(--ok,#3ddc97)}
.br-syllabes-pre{font:700 18px system-ui,sans-serif;color:#fb7185;text-transform:lowercase}
.br-syllabes-wrap input.br-syllabes-input{flex:1;min-width:0;width:auto;height:50px;margin:0;border:0;border-radius:0;outline:0;
  box-shadow:none;background:transparent;color:inherit;-webkit-appearance:none;appearance:none;
  font:600 18px system-ui,sans-serif;padding:0 0 0 1px}
.br-syllabes-send{min-width:64px;min-height:54px;border:0;border-radius:14px;background:#e11d48;color:#fff;font:800 18px system-ui,sans-serif;
  touch-action:manipulation;cursor:pointer}
.br-syllabes-note{min-height:22px;text-align:center;font:600 15px system-ui,sans-serif;color:var(--muted,#a69cc6)}
.br-syllabes-note.ko{color:var(--err,#ff6b6b)}.br-syllabes-note.ok{color:var(--ok,#3ddc97)}
.br-syllabes-list{flex:1;display:flex;flex-wrap:wrap;align-content:flex-start;gap:6px;overflow-y:auto;min-height:80px}
.br-syllabes-word{padding:6px 10px;border-radius:999px;background:rgba(251,113,133,.16);font:600 15px system-ui,sans-serif}
.br-syllabes-word b{color:#fb7185;font-size:12px;margin-left:4px}`;

  function injectStyle() {
    if (document.getElementById('br-syllabes-style')) return;
    const st = document.createElement('style');
    st.id = 'br-syllabes-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // Chargement unique du dictionnaire (partagé entre les parties).
  let dictPromise = null;
  function loadDict() {
    if (window.BrainMotsFr) return Promise.resolve(window.BrainMotsFr);
    if (!dictPromise) {
      dictPromise = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = DICT_URL;
        s.async = true;
        s.onload = () => (window.BrainMotsFr ? resolve(window.BrainMotsFr) : reject(new Error('dictionnaire vide')));
        s.onerror = () => { dictPromise = null; reject(new Error('dictionnaire introuvable')); };
        document.head.appendChild(s);
      });
    }
    return dictPromise;
  }

  /** Minuscules, sans accents ni espaces : « Été » → « ete », « cœur » → « coeur ». */
  function normalize(s) {
    return String(s).trim().toLowerCase().replace(/œ/g, 'oe').replace(/æ/g, 'ae')
      .normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[’']/g, '');
  }

  /** Choisit un début : plus le niveau monte, moins il y a de mots courants. */
  function choosePrefix(dict, level, rng) {
    const all = Object.keys(dict).sort((a, b) => dict[b][0] - dict[a][0]);
    const share = Math.min(1, Math.max(0, (level - 1) / (MAX_LEVEL - 1)));
    const span = Math.max(8, Math.round(all.length / 3));
    const from = Math.round(share * (all.length - span));
    return all[from + Math.floor(rng() * span)];
  }

  const pointsFor = (word) => 1 + (word.length >= LONG_WORD ? 1 : 0) + (word.length >= VERY_LONG_WORD ? 1 : 0);

  function start(ctx) {
    injectStyle();
    let level = Math.max(1, Math.min(MAX_LEVEL, ctx.level | 0 || 1));
    let stopped = false;
    let prefix = '';
    let words = null;              // Set des mots valides pour ce début
    let found = [];                // [{ shown, key, pts }]
    let lastAt = 0;
    let noteTimer = 0;

    ctx.root.innerHTML = `
      <div class="br-syllabes-wrap">
        <div class="br-syllabes-tiles" aria-label="Lettres de départ"></div>
        <form class="br-syllabes-form" autocomplete="off">
          <label class="br-syllabes-field"><span class="br-syllabes-pre"></span>
            <input class="br-syllabes-input" type="text" inputmode="text" autocapitalize="off" autocorrect="off"
              spellcheck="false" autocomplete="off" enterkeyhint="send" maxlength="30" aria-label="Mot" disabled></label>
          <button type="submit" class="br-syllabes-send" disabled>OK</button>
        </form>
        <div class="br-syllabes-note" aria-live="polite">Chargement du dictionnaire…</div>
        <div class="br-syllabes-list"></div>
      </div>`;
    const tiles = ctx.root.querySelector('.br-syllabes-tiles');
    const form = ctx.root.querySelector('.br-syllabes-form');
    const field = ctx.root.querySelector('.br-syllabes-field');
    const pre = ctx.root.querySelector('.br-syllabes-pre');
    const input = ctx.root.querySelector('.br-syllabes-input');
    const send = ctx.root.querySelector('.br-syllabes-send');
    const note = ctx.root.querySelector('.br-syllabes-note');
    const list = ctx.root.querySelector('.br-syllabes-list');

    function say(text, cls) {
      note.textContent = text;
      note.className = `br-syllabes-note ${cls || ''}`;
      field.classList.remove('ok', 'ko');
      if (cls) field.classList.add(cls);
      clearTimeout(noteTimer);
      noteTimer = setTimeout(() => { if (!stopped) { note.textContent = ''; field.classList.remove('ok', 'ko'); } }, NOTE_MS);
    }

    function setup(dict) {
      if (stopped) return;
      prefix = choosePrefix(dict, level, ctx.rng);
      words = new Set(dict[prefix][1].split(' ').map((end) => prefix + end));
      tiles.innerHTML = prefix.split('').map((c) => `<span class="br-syllabes-tile">${ctx.esc(c)}</span>`).join('');
      pre.textContent = prefix;
      input.disabled = false;
      send.disabled = false;
      note.textContent = 'Tape des mots qui commencent par ces lettres';
      lastAt = performance.now();
      input.focus({ preventScroll: true });
    }

    function render() {
      list.innerHTML = found.slice().reverse()
        .map((w) => `<span class="br-syllabes-word">${ctx.esc(w.shown)}${w.pts > 1 ? `<b>+${w.pts - 1}</b>` : ''}</span>`).join('');
    }

    function submitWord(raw) {
      const typed = String(raw).trim();
      if (!typed || !words) return;
      const typedKey = normalize(typed);
      // Le joueur peut taper le mot entier ou seulement la suite des 3 lettres.
      const full = typedKey.startsWith(prefix) && typedKey.length > PREFIX_LEN;
      const key = full ? typedKey : prefix + typedKey;
      const shown = full ? typed.toLowerCase() : prefix + typed.toLowerCase();
      const now = performance.now();
      const rt = Math.round(now - lastAt);
      lastAt = now;
      if (typedKey === prefix || key.length <= PREFIX_LEN) { say('Trop court : ajoute des lettres'); return; }
      if (found.some((w) => w.key === key)) { ctx.miss({ rt }); say(`« ${shown} » est déjà trouvé`, 'ko'); return; }
      if (!words.has(key)) { ctx.miss({ rt }); say(`« ${shown} » : mot inconnu`, 'ko'); return; }
      const pts = pointsFor(key);
      for (let i = 0; i < pts; i += 1) ctx.hit({ rt });
      found = found.concat([{ shown, key, pts }]);
      render();
      say(pts > 1 ? `Bravo ! Mot long : +${pts - 1}` : 'Bien vu !', 'ok');
      if (found.length % UP_EVERY === 0 && level < MAX_LEVEL) { level += 1; ctx.setLevel(level); }
    }

    function onSubmit(ev) {
      ev.preventDefault();
      if (stopped) return;
      submitWord(input.value);
      input.value = '';
      input.focus({ preventScroll: true });
    }

    form.addEventListener('submit', onSubmit);
    ctx.setLevel(level);
    loadDict().then(setup).catch(() => {
      if (!stopped) note.textContent = 'Dictionnaire indisponible : réessaie plus tard.';
    });

    return {
      stop() {
        stopped = true;
        clearTimeout(noteTimer);
        form.removeEventListener('submit', onSubmit);
        input.disabled = true;
        send.disabled = true;
        input.blur();
      },
    };
  }

  window.Brain.register({
    id: ID,
    name: 'Débuts de mots',
    domain: 'logique',
    icon: '🔤',
    color: '#e11d48',
    seconds: 60,
    howto: [
      'Trois lettres s’affichent : écris un maximum de vrais mots français qui commencent par elles.',
      'Les accents sont facultatifs ; tu peux taper le mot entier ou juste la suite.',
      'Les mots longs rapportent plus ; un mot inconnu ou déjà donné compte comme une erreur.',
    ],
    start,
  });
})();
