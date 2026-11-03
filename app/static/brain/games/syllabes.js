/* Méninges — « Débuts de mots » (logique / langage), SANS FIN : 3 lettres de départ ; trouver en 30 s un nombre
   de vrais mots français qui commencent par elles. Objectif atteint = manche suivante (autres lettres, plus rares,
   objectif plus haut) ; objectif raté = une vie (ctx.miss). Dictionnaire complet (toutes les formes fléchies) servi
   en statique : mots/index.json puis seulement le fichier mots/<abc>.txt de la manche (préchargement de la suivante).
   Mot inconnu ou déjà donné = petite erreur (ctx.slip, sans vie).

   Niveaux (un niveau = une manche ; montée à chaque manche réussie, descente après une manche ratée) :
     objectif   = 3 + round(9 × (1 − e^(−(niv − 1) / 20)))  → niv 1 : 3, 5 : 4, 10 : 6, 20 : 9, 40 : 11, puis vers 12
     rareté     = rang d'index.json 2 (niv 1-10, + le rang 1), 3 (11-20), 4 (21-30), 5 (31+) : débuts aux mots courants
                  de plus en plus rares (toujours au moins objectif + 2 mots courants)
     longueur   = 4 lettres minimum, 5 dès le niv 30, 6 dès le niv 50
     au-delà du niv 50 : l'objectif continue de croître vers 12 mots, toujours en 30 s, débuts les plus rares. */
(function () {
  'use strict';
  const ID = 'syllabes';
  const PREFIX_LEN = 3;
  const ROUND_MS = 30000;
  const BREAK_MS = 1600;          // pause entre deux manches
  const TICK_MS = 100;
  const NOTE_MS = 1400;
  const LONG_WORD = 7;            // ≥ 7 lettres : un point de plus
  const VERY_LONG_WORD = 9;       // ≥ 9 lettres : encore un de plus
  const GOAL_BASE = 3, GOAL_SPAN = 9, GOAL_CURVE = 20;
  const RANK_FIRST = 2, RANK_EVERY = 10, RANK_MAX = 5;
  const MIN_LEN_STEPS = [[50, 6], [30, 5], [1, 4]];
  const MAX_INPUT = 40;
  // Débuts jamais proposés comme lettres de départ (les mots restent valides) : index.json les marque
  // « start: false » ; cette liste n'est qu'un filet si l'index l'oubliait.
  const RUDE = new Set(['con', 'cul', 'bit', 'put', 'nic', 'enc']);
  const SELF = (document.currentScript && document.currentScript.src) || '/static/brain/games/syllabes.js';
  const QUERY = (SELF.match(/\?[^#]*$/) || [''])[0];
  const MOTS_DIR = SELF.replace(/games\/syllabes\.js(\?.*)?$/, 'mots/');
  const noop = () => {};

  const CSS = `
.br-syllabes-wrap{display:flex;flex-direction:column;height:100%;min-height:320px;gap:10px;padding:10px 4px;box-sizing:border-box;
  color:var(--text,#f5f0ff)}
.br-syllabes-round{display:flex;justify-content:space-between;align-items:center;font:700 16px system-ui,sans-serif}
.br-syllabes-round b{color:#fb7185}
.br-syllabes-bar{height:8px;border-radius:99px;background:rgba(251,113,133,.18);overflow:hidden}
.br-syllabes-bar i{display:block;height:100%;width:100%;background:linear-gradient(90deg,#fb7185,#e11d48);transform-origin:left;
  border-radius:99px}
.br-syllabes-bar.warn i{background:var(--err,#ff6b6b)}
.br-syllabes-tiles{display:flex;justify-content:center;gap:8px;min-height:62px}
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
.br-syllabes-send:disabled{opacity:.5}
.br-syllabes-note{min-height:24px;text-align:center;font:600 16px system-ui,sans-serif;color:var(--muted,#a69cc6)}
.br-syllabes-note.ko{color:var(--err,#ff6b6b)}.br-syllabes-note.ok{color:var(--ok,#3ddc97)}
.br-syllabes-retry{display:block;margin:0 auto;min-height:44px;padding:0 18px;border:0;border-radius:12px;background:#e11d48;color:#fff;
  font:700 16px system-ui,sans-serif;cursor:pointer}
.br-syllabes-list{flex:1;display:flex;flex-wrap:wrap;align-content:flex-start;gap:6px;overflow-y:auto;min-height:80px}
.br-syllabes-word{padding:6px 10px;border-radius:999px;background:rgba(251,113,133,.16);font:600 16px system-ui,sans-serif}
.br-syllabes-word b{color:#fb7185;font-size:13px;margin-left:4px}`;

  function injectStyle() {
    if (document.getElementById('br-syllabes-style')) return;
    const st = document.createElement('style');
    st.id = 'br-syllabes-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  /** Normalisation du dictionnaire (dico_spec.md) : minuscules, sans accents, œ→oe, æ→ae, ’→', espaces en trop
      retirés. Plus la saisie iPhone : guillemets et tirets typographiques, point final ajouté par la double espace. */
  function normalize(s) {
    return String(s).toLowerCase().replace(/œ/g, 'oe').replace(/æ/g, 'ae')
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[’‘ʼ´`]/g, "'").replace(/[‐‑‒–—]/g, '-')
      .replace(/\s+/g, ' ').trim().replace(/[.\s]+$/, '');
  }

  // ── Chargement : index une fois, puis un fichier par début (cache mémoire partagé entre les parties) ──
  let indexPromise = null;
  const files = new Map();       // début → Promise<Set<string>>
  function fetchText(url) {
    return fetch(url, { credentials: 'same-origin' }).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.text();
    });
  }
  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetchText(`${MOTS_DIR}index.json${QUERY}`).then((text) => {
        const data = JSON.parse(text);
        if (!data || typeof data.prefixes !== 'object') throw new Error('index illisible');
        return data;
      });
      indexPromise.catch(() => { indexPromise = null; });   // nouvel essai possible
    }
    return indexPromise;
  }
  function loadPrefix(prefix) {
    if (!files.has(prefix)) {
      const p = fetchText(`${MOTS_DIR}${prefix}.txt${QUERY}`).then((text) => {
        const set = new Set(text.split('\n').map((l) => l.trim()).filter(Boolean));
        if (!set.size) throw new Error('fichier vide');
        return set;
      });
      files.set(prefix, p);
      p.catch(() => { if (files.get(prefix) === p) files.delete(prefix); });
    }
    return files.get(prefix);
  }

  // ── Table des niveaux ──
  const goalFor = (lv) => GOAL_BASE + Math.round(GOAL_SPAN * (1 - Math.exp(-(lv - 1) / GOAL_CURVE)));
  const rankFor = (lv) => Math.min(RANK_MAX, RANK_FIRST + Math.floor((lv - 1) / RANK_EVERY));
  const minLenFor = (lv) => MIN_LEN_STEPS.find(([from]) => lv >= from)[1];
  const pointsFor = (word) => 1 + (word.length >= LONG_WORD ? 1 : 0) + (word.length >= VERY_LONG_WORD ? 1 : 0);

  /** Début de la manche : rang de rareté du niveau (ou le voisin), assez de mots courants, jamais déjà joué. */
  function choosePrefix(index, lv, used, rng) {
    const goal = goalFor(lv), rank = rankFor(lv);
    const all = Object.entries(index.prefixes).filter(([abc, p]) => /^[a-z]{3}$/.test(abc) && p && !RUDE.has(abc)
      && p.start !== false && (+p.n || 0) >= goal * 3 && (+p.common || 0) >= goal + 2);
    const fresh = all.filter(([abc]) => !used.has(abc));
    const pools = [
      fresh.filter(([, p]) => (+p.rank || 1) === rank),
      fresh.filter(([, p]) => Math.abs((+p.rank || 1) - rank) <= 1),
      fresh, all,
    ];
    const pool = pools.find((list) => list.length) || [];
    if (!pool.length) return null;
    return pool[Math.floor(rng() * pool.length)][0];
  }

  function start(ctx) {
    injectStyle();
    const slip = typeof ctx.slip === 'function' ? ctx.slip : noop;
    const floor = Math.max(1, ctx.level | 0 || 1);  // premier niveau du palier de départ
    let level = floor;
    let round = 0;
    let stopped = false;
    let paused = false, leftAtPause = null;   // pause du moteur : temps restant de la manche figé
    let playing = false;           // manche en cours (fichier chargé, chrono lancé)
    let index = null;
    let prefix = '', words = null, goal = 0, minLen = 4;
    let found = [];                // [{ shown, key, pts }]
    let roundStart = 0, lastAt = 0;
    let next = { up: null, down: null };
    const used = new Set();
    const timeouts = new Set();
    let ticker = 0, noteTimer = 0;
    const later = (fn, ms) => { const id = setTimeout(() => { timeouts.delete(id); if (!stopped) fn(); }, ms); timeouts.add(id); };

    ctx.root.innerHTML = `
      <div class="br-syllabes-wrap">
        <div class="br-syllabes-round"><span class="br-syllabes-rn">Manche 1</span><span class="br-syllabes-goal"></span></div>
        <div class="br-syllabes-bar" aria-hidden="true"><i></i></div>
        <div class="br-syllabes-tiles" aria-label="Lettres de départ"></div>
        <form class="br-syllabes-form" autocomplete="off">
          <label class="br-syllabes-field"><span class="br-syllabes-pre"></span>
            <input class="br-syllabes-input" type="text" inputmode="text" autocapitalize="off" autocorrect="off"
              spellcheck="false" autocomplete="off" enterkeyhint="send" maxlength="${MAX_INPUT}" aria-label="Mot" disabled></label>
          <button type="submit" class="br-syllabes-send" disabled>OK</button>
        </form>
        <div class="br-syllabes-note" aria-live="polite">Chargement du dictionnaire…</div>
        <div class="br-syllabes-list"></div>
      </div>`;
    const q = (s) => ctx.root.querySelector(s);
    const tiles = q('.br-syllabes-tiles'), form = q('.br-syllabes-form'), field = q('.br-syllabes-field');
    const pre = q('.br-syllabes-pre'), input = q('.br-syllabes-input'), send = q('.br-syllabes-send');
    const note = q('.br-syllabes-note'), list = q('.br-syllabes-list');
    const rn = q('.br-syllabes-rn'), goalEl = q('.br-syllabes-goal'), bar = q('.br-syllabes-bar'), barFill = q('.br-syllabes-bar i');

    function say(text, cls, keep) {
      note.textContent = text;
      note.className = `br-syllabes-note ${cls || ''}`;
      field.classList.remove('ok', 'ko');
      if (cls) field.classList.add(cls);
      clearTimeout(noteTimer);
      if (!keep) noteTimer = setTimeout(() => { if (!stopped) { note.textContent = ''; field.classList.remove('ok', 'ko'); } }, NOTE_MS);
    }
    function enable(on) {
      input.disabled = !on;
      send.disabled = !on;
      if (on) input.focus({ preventScroll: true });
    }
    function showGoal() { goalEl.innerHTML = `<b>${found.length}</b> / ${goal} mots`; }
    function render() {
      list.innerHTML = found.slice().reverse()
        .map((w) => `<span class="br-syllabes-word">${ctx.esc(w.shown)}${w.pts > 1 ? `<b>+${w.pts - 1}</b>` : ''}</span>`).join('');
    }

    // Erreur réseau : message et bouton « Réessayer » ; la manche ne démarre (chrono compris) qu'une fois chargée.
    function offline(retry) {
      if (stopped) return;
      enable(false);
      say('Dictionnaire indisponible (connexion ?).', 'ko', true);
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'br-syllabes-retry';
      b.textContent = 'Réessayer';
      b.addEventListener('click', () => { b.remove(); say('Chargement du dictionnaire…', '', true); retry(); });
      note.appendChild(document.createElement('br'));
      note.appendChild(b);
    }

    function prepare(nextPrefix) {
      if (stopped) return;
      const chosen = nextPrefix || choosePrefix(index, level, used, ctx.rng);
      if (!chosen) { offline(() => prepare(null)); return; }
      used.add(chosen);
      loadPrefix(chosen).then((set) => begin(chosen, set)).catch(() => offline(() => prepare(chosen)));
    }

    function begin(chosen, set) {
      if (stopped) return;
      round += 1;
      prefix = chosen; words = set; goal = goalFor(level); minLen = minLenFor(level);
      found = [];
      render();
      rn.textContent = `Manche ${round}`;
      showGoal();
      tiles.innerHTML = prefix.split('').map((c) => `<span class="br-syllabes-tile">${ctx.esc(c)}</span>`).join('');
      pre.textContent = prefix;
      input.value = '';
      say(minLen > 4 ? `Mots de ${minLen} lettres et plus` : 'Tape des mots qui commencent par ces lettres', '', true);
      roundStart = lastAt = performance.now();
      playing = true;
      enable(true);
      // Préchargement des deux manches possibles (réussie : niveau + 1 ; ratée : niveau − 1).
      const pick = (lv) => choosePrefix(index, lv, new Set([...used, next.up, next.down].filter(Boolean)), ctx.rng);
      next = { up: pick(level + 1), down: null };
      next.down = level > floor ? pick(level - 1) : pick(level);
      for (const p of [next.up, next.down]) if (p) loadPrefix(p).catch(noop);
    }

    function endRound(won) {
      playing = false;
      // Le champ reste actif et sélectionné pendant la pause : sur iPhone, le désactiver ferme le clavier, et un
      // focus() lancé par un minuteur ne le rouvre pas (il faudrait retoucher le champ à chaque manche).
      send.disabled = true;
      barFill.style.transform = 'scaleX(0)';
      if (won) {
        level += 1;
        ctx.setLevel(level);
        say(`Manche réussie ! Niveau ${level}`, 'ok', true);
      } else {
        say(`Temps écoulé : ${found.length} / ${goal} mots`, 'ko', true);
        ctx.miss({});
        if (stopped) return;      // plus de vie : le moteur a arrêté le jeu
        if (level > floor) { level -= 1; ctx.setLevel(level); }
      }
      const chosen = won ? next.up : next.down;
      later(() => prepare(chosen && !used.has(chosen) ? chosen : null), BREAK_MS);
    }

    function tick() {
      if (stopped || paused || !playing) return;
      const left = Math.max(0, ROUND_MS - (performance.now() - roundStart));
      barFill.style.transform = `scaleX(${(left / ROUND_MS).toFixed(3)})`;
      bar.classList.toggle('warn', left <= 5000);
      if (left <= 0) endRound(false);
    }

    /** Clés possibles : le mot entier, ou la suite tapée après les 3 lettres (« ange » → « orange » avec « ora »).
        Une espace (correction automatique) peut aussi valoir un trait d'union ou rien. */
    const variants = (k) => [...new Set([k, k.replace(/ /g, '-'), k.replace(/ /g, '')])];

    function submitWord(raw) {
      const typed = normalize(raw);
      if (!typed || !playing) return;
      const now = performance.now();
      const rt = Math.round(now - lastAt);
      const whole = typed.startsWith(prefix) ? variants(typed) : [];
      const tail = variants(prefix + typed);
      const key = whole.find((k) => words.has(k)) || tail.find((k) => words.has(k));
      const asWhole = key ? whole.includes(key) : whole.length > 0;
      const shownKey = key || (asWhole ? whole[0] : tail[0]);
      const shown = String(raw).trim().toLowerCase().replace(/[.\s]+$/, '');
      const label = asWhole ? shown : prefix + shown;
      if (shownKey.length < minLen) { say(`Trop court : au moins ${minLen} lettres`); return; }
      lastAt = now;
      if (key && found.some((w) => w.key === key)) { slip({ rt }); say(`« ${label} » est déjà trouvé`, 'ko'); return; }
      if (!key) { slip({ rt }); say(`« ${label} » : mot inconnu`, 'ko'); return; }
      const pts = pointsFor(key);
      for (let i = 0; i < pts && !stopped; i += 1) ctx.hit({ rt });
      if (stopped) return;
      found = found.concat([{ shown: label, key, pts }]);
      render();
      showGoal();
      if (found.length >= goal) { endRound(true); return; }
      say(pts > 1 ? `Bravo ! Mot long : +${pts - 1}` : 'Bien vu !', 'ok');
    }

    function onSubmit(ev) {
      ev.preventDefault();
      if (stopped || paused) return;
      if (!playing) { if (input.value.trim()) say('Attends les lettres de la manche suivante…', '', false); return; }
      submitWord(input.value);
      input.value = '';
      if (playing) input.focus({ preventScroll: true });
    }

    function boot() {
      loadIndex().then((data) => { if (stopped) return; index = data; prepare(null); })
        .catch(() => offline(boot));
    }

    // Toucher OK ne retire pas le focus du champ (le clavier de l'iPhone reste ouvert).
    const keepFocus = (ev) => ev.preventDefault();
    form.addEventListener('submit', onSubmit);
    send.addEventListener('mousedown', keepFocus);
    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : le chrono de la manche
    // s'arrête (aucune vie perdue loin de l'écran) et repart au retour avec le temps qui restait.
    if (ctx.onPause) ctx.onPause(() => {
      if (paused) return;
      paused = true;
      leftAtPause = playing ? Math.max(0, ROUND_MS - (performance.now() - roundStart)) : null;
    });
    if (ctx.onResume) ctx.onResume(() => {
      if (!paused) return;
      paused = false;
      const now = performance.now();
      // Manche commencée pendant la pause (fin de l'entracte) : son chrono part maintenant.
      if (playing) roundStart = now - (leftAtPause === null ? 0 : ROUND_MS - leftAtPause);
      lastAt = now;
      leftAtPause = null;
    });
    ctx.setLevel(level);
    ticker = setInterval(tick, TICK_MS);
    boot();

    return {
      stop() {
        stopped = true;
        playing = false;
        clearInterval(ticker);
        clearTimeout(noteTimer);
        for (const id of timeouts) clearTimeout(id);
        timeouts.clear();
        form.removeEventListener('submit', onSubmit);
        send.removeEventListener('mousedown', keepFocus);
        input.disabled = true;
        send.disabled = true;
        input.blur();
      },
    };
  }

  window.BrainSyllabes = Object.freeze({ normalize, goalFor, rankFor, minLenFor });
  window.Brain.register({
    id: ID,
    name: 'Débuts de mots',
    domain: 'logique',
    icon: '🔤',
    color: '#e11d48',
    seconds: null,
    howto: [
      'Trois lettres s’affichent : trouve en 30 s le nombre de vrais mots français demandé qui commencent par elles.',
      'Objectif atteint : manche suivante, avec d’autres lettres et un objectif plus haut. Objectif raté : une vie en moins.',
      'Toutes les formes comptent (pluriels, féminins, conjugaisons) ; accents facultatifs ; mot entier ou juste la suite.',
      'Les mots longs rapportent plus ; un mot inconnu ou déjà donné casse la série.',
    ],
    start,
  });
})();
