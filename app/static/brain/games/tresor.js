/* Méninges — « Jamais deux fois » (mémoire), SANS FIN (contrat v2).
   Dans le sous-bois, toucher à chaque tour une trouvaille pas encore choisie dans la manche.
   Entre les tours, tout se replace et une nouvelle trouvaille apparaît.
   Manche réussie (objectif atteint) → niveau +1 et manche suivante. Choisir deux fois la même, ou trop tarder,
   = ctx.miss (une vie), niveau −1 (pas sous le palier de départ), nouvelle manche.

   Table des niveaux (params(n)) :
     départ   : 3 + ⌊n/5⌋ trouvailles au début de la manche (max 12)
     objectif : 4 + ⌊n/3⌋ bons choix pour réussir la manche (4 au niv. 1, 17 au niv. 40, max 30 au niv. 78)
                → jusqu'à 28 trouvailles à l'écran au niv. 40, 42 au-delà
     sosies   : dès le niv. 11, chaque nouvelle trouvaille a (n−10)×3 % de chances d'être de la même famille qu'une
                trouvaille déjà là (champignon/noisette, fleurs, insectes, baies…), jusqu'à 85 %
     délai    : par choix 900 + 3000·e^(−n/20) + 45 × trouvailles ms (3,9 s au niv. 1 ; ≈ 2,5 s au niv. 40)
   Au-delà du niveau 78, l'objectif et le départ sont au maximum ; le délai et les sosies continuent de se resserrer. */
(function () {
  'use strict';

  var ID = 'tresor';
  var FAMILIES = [
    ['🍄', '🌰', '🥜', '🫘'],
    ['🍂', '🍁', '🍃', '🌿', '🍀', '🌱', '🌾'],
    ['🌸', '🌼', '🌺', '🌷', '🌻', '🌹', '🥀', '💮'],
    ['🐞', '🐝', '🐛', '🦋', '🐜', '🦗', '🪲', '🪳'],
    ['🦔', '🐁', '🐭', '🐹', '🐰', '🦡', '🦦'],
    ['🦊', '🐺', '🐶', '🐕', '🦝'],
    ['🦉', '🐦', '🐤', '🐥', '🦆', '🦅', '🪶'],
    ['🍓', '🍒', '🫐', '🍇', '🍎', '🍅', '🍑'],
    ['🌲', '🌳', '🌴', '🎄', '🌵'],
    ['🪨', '🪵', '🪺', '🐌'],
    ['🐸', '🐢', '🦎', '🐍', '🐊']
  ];
  var ITEMS = [].concat.apply([], FAMILIES);
  var SIMILAR_FROM = 10;
  var TURN_PAUSE_MS = 380;     // temps du « replacement » entre deux tours
  var REVIEW_MS = 1500;        // affichage de l'erreur avant la manche suivante
  var WIN_MS = 1000;
  var STYLE_ID = 'br-tresor-style';

  var CSS = [
    '.br-tresor-wrap{display:flex;flex-direction:column;height:100%;min-height:360px;box-sizing:border-box;',
    'padding:12px 14px 16px;color:#eef5e9;font-family:inherit;',
    'background:radial-gradient(120% 80% at 50% 0%,#2f5d3a 0%,#1d3b27 55%,#132619 100%);border-radius:18px}',
    '.br-tresor-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:15px;',
    'font-weight:600;min-height:28px}',
    '.br-tresor-clock{height:6px;border-radius:3px;background:rgba(238,245,233,.18);overflow:hidden;margin-top:4px}',
    '.br-tresor-clock i{display:block;height:100%;width:0;background:#f2d27a;border-radius:3px}',
    '.br-tresor-msg{text-align:center;font-size:15px;opacity:.9;margin:6px 0 10px;min-height:20px}',
    '.br-tresor-field{flex:1;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;align-content:center}',
    '.br-tresor-cell{aspect-ratio:1;min-height:44px;display:flex;align-items:center;justify-content:center}',
    '.br-tresor-item{width:100%;height:100%;min-width:44px;min-height:44px;border:0;border-radius:50%;',
    'background:rgba(255,255,255,.08);box-shadow:inset 0 -3px 0 rgba(0,0,0,.25);font-size:clamp(22px,8vw,36px);',
    'line-height:1;cursor:pointer;touch-action:manipulation;-webkit-tap-highlight-color:transparent;',
    'transition:transform .18s ease,opacity .18s ease,background .18s ease;color:inherit;padding:0}',
    '.br-tresor-field.is-dense .br-tresor-item{font-size:clamp(20px,6.5vw,30px)}',
    '.br-tresor-item:focus-visible{outline:3px solid #f2d27a;outline-offset:2px}',
    '.br-tresor-item:active{transform:scale(.92)}',
    '.br-tresor-item.is-new{animation:br-tresor-pop .35s ease}',
    '.br-tresor-item.is-good{background:rgba(154,209,107,.45)}',
    '.br-tresor-item.is-bad{background:rgba(232,90,79,.6);box-shadow:0 0 0 3px #e85a4f}',
    '.br-tresor-item.is-picked{box-shadow:0 0 0 3px rgba(255,255,255,.85)}',
    '.br-tresor-field.is-hidden .br-tresor-item{opacity:0;transform:scale(.6)}',
    '.br-tresor-field.is-calm .br-tresor-item{transition:none;animation:none}',
    '@keyframes br-tresor-pop{0%{transform:scale(.3)}70%{transform:scale(1.12)}100%{transform:scale(1)}}'
  ].join('');

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var el = document.createElement('style');
    el.id = STYLE_ID;
    el.textContent = CSS;
    document.head.appendChild(el);
  }

  function shuffled(list, rng) {
    var out = list.slice();
    for (var i = out.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var t = out[i]; out[i] = out[j]; out[j] = t;
    }
    return out;
  }

  function familyOf(item) {
    for (var i = 0; i < FAMILIES.length; i++) if (FAMILIES[i].indexOf(item) >= 0) return FAMILIES[i];
    return [];
  }

  /** Paramètres du niveau n (voir la table en tête de fichier). */
  function params(n) {
    var startCount = Math.min(12, 3 + Math.floor(n / 5));
    var goal = Math.min(30, 4 + Math.floor(n / 3));
    return {
      startCount: startCount,
      goal: goal,
      size: startCount + goal,
      similar: n <= SIMILAR_FROM ? 0 : Math.min(0.85, (n - SIMILAR_FROM) * 0.03),
      choiceBase: 900 + 3000 * Math.exp(-n / 20)
    };
  }

  function colsFor(size) { return size <= 12 ? 4 : size <= 24 ? 5 : 6; }

  function start(ctx) {
    injectStyle();
    var esc = ctx.esc;
    var timers = [];
    var stopped = false;
    var floor = Math.max(1, ctx.level | 0);
    var state = {
      round: 0,              // numéro de la manche (1, 2, …)
      p: null,               // paramètres de la manche
      pool: [],              // trouvailles présentes dans la manche
      picked: [],            // déjà choisies dans la manche
      shownAt: 0,
      deadline: null,
      locked: true,
      level: floor
    };

    ctx.root.innerHTML =
      '<div class="br-tresor-wrap">' +
      '<div class="br-tresor-head"><span class="br-tresor-round"></span><span class="br-tresor-lvl"></span></div>' +
      '<div class="br-tresor-clock" aria-hidden="true"><i></i></div>' +
      '<div class="br-tresor-msg" aria-live="polite"></div>' +
      '<div class="br-tresor-field" role="group" aria-label="Trouvailles du sous-bois"></div></div>';
    var field = ctx.root.querySelector('.br-tresor-field');
    var msg = ctx.root.querySelector('.br-tresor-msg');
    var roundEl = ctx.root.querySelector('.br-tresor-round');
    var lvlEl = ctx.root.querySelector('.br-tresor-lvl');
    var clock = ctx.root.querySelector('.br-tresor-clock i');
    if (ctx.reducedMotion) field.classList.add('is-calm');

    function later(fn, ms) {
      if (stopped) return null;
      var id = setTimeout(function () {
        timers = timers.filter(function (t) { return t !== id; });
        if (!stopped) fn();
      }, ms);
      timers.push(id);
      return id;
    }

    function cancel(id) {
      if (!id) return;
      clearTimeout(id);
      timers = timers.filter(function (t) { return t !== id; });
    }

    function runClock(ms) {
      clock.style.transition = 'none';
      clock.style.width = '100%';
      void clock.offsetWidth;
      clock.style.transition = 'width ' + ms + 'ms linear';
      clock.style.width = '0%';
    }

    function freezeClock() { clock.style.transition = 'none'; clock.style.width = '0%'; }

    function renderHead() {
      roundEl.textContent = 'Manche ' + state.round + ' · ' + state.picked.length + ' / ' + state.p.goal;
      lvlEl.textContent = 'Niveau ' + state.level;
    }

    function renderField(newItem) {
      var cols = colsFor(state.p.size);
      var total = Math.max(3, Math.ceil(state.p.size / cols)) * cols;
      var cells = shuffled(Array.from({ length: total }, function (_, i) { return i; }), ctx.rng);
      var slots = new Array(total).fill(null);
      state.pool.forEach(function (item, i) { slots[cells[i]] = item; });
      field.style.gridTemplateColumns = 'repeat(' + cols + ',1fr)';
      field.classList.toggle('is-dense', cols > 4);
      field.innerHTML = slots.map(function (item) {
        if (!item) return '<div class="br-tresor-cell"></div>';
        var cls = 'br-tresor-item' + (item === newItem ? ' is-new' : '');
        return '<div class="br-tresor-cell"><button type="button" class="' + cls + '" data-item="' +
          esc(item) + '" aria-label="Trouvaille">' + esc(item) + '</button></div>';
      }).join('');
    }

    /** Nouvelle trouvaille absente du sous-bois ; aux niveaux hauts, souvent sosie d'une trouvaille présente. */
    function nextItem(pool) {
      var left = ITEMS.filter(function (it) { return pool.indexOf(it) < 0; });
      if (pool.length && ctx.rng() < state.p.similar) {
        var fam = familyOf(pool[Math.floor(ctx.rng() * pool.length)]);
        var close = fam.filter(function (it) { return pool.indexOf(it) < 0; });
        if (close.length) return close[Math.floor(ctx.rng() * close.length)];
      }
      return left[Math.floor(ctx.rng() * left.length)];
    }

    function showTurn(newItem) {
      renderHead();
      renderField(newItem);
      field.classList.remove('is-hidden');
      state.shownAt = performance.now();
      state.locked = false;
      var ms = Math.round(state.p.choiceBase + 45 * state.pool.length);
      runClock(ms);
      state.deadline = later(onSlow, ms);
    }

    function startRound() {
      state.round += 1;
      state.p = params(state.level);
      var pool = [];
      while (pool.length < state.p.startCount) pool = pool.concat([nextItem(pool)]);
      state.pool = pool;
      state.picked = [];
      msg.textContent = state.round === 1
        ? 'Touche une trouvaille que tu n’as pas encore choisie.'
        : 'Nouvelle manche : objectif ' + state.p.goal + ' trouvailles.';
      showTurn(null);
    }

    function changeLevel(n) {
      state.level = Math.max(floor, n);
      ctx.setLevel(state.level);
    }

    function lose(text, rt) {
      state.locked = true;
      cancel(state.deadline);
      freezeClock();
      changeLevel(state.level - 1);
      msg.textContent = text;
      later(startRound, REVIEW_MS);
      ctx.miss({ rt: rt });
    }

    function onSlow() {
      lose('Trop lent ! ' + state.picked.length + ' trouvailles dans cette manche.', Math.round(performance.now() - state.shownAt));
    }

    function onGood(btn, item, rt) {
      btn.classList.add('is-good');
      state.picked = state.picked.concat([item]);
      ctx.hit({ rt: rt });
      if (stopped) return;
      var count = state.picked.length;
      if (count >= state.p.goal) {
        renderHead();
        msg.textContent = 'Manche réussie ! Niveau suivant.';
        changeLevel(state.level + 1);
        later(startRound, WIN_MS);
        return;
      }
      var added = nextItem(state.pool);
      state.pool = state.pool.concat([added]);
      msg.textContent = count + (count > 1 ? ' bonnes' : ' bonne') + ' · tout se replace…';
      field.classList.add('is-hidden');
      later(function () { showTurn(added); }, ctx.reducedMotion ? 120 : TURN_PAUSE_MS);
    }

    function onBad(btn, rt) {
      btn.classList.add('is-bad');
      field.querySelectorAll('.br-tresor-item').forEach(function (b) {
        if (b !== btn && state.picked.indexOf(b.getAttribute('data-item')) >= 0) b.classList.add('is-picked');
      });
      lose('Déjà choisie ! ' + state.picked.length + ' trouvailles dans cette manche.', rt);
    }

    function onPointer(ev) {
      var btn = ev.target.closest('.br-tresor-item');
      if (!btn || state.locked || stopped) return;
      ev.preventDefault();
      state.locked = true;
      cancel(state.deadline);
      freezeClock();
      var item = btn.getAttribute('data-item');
      var rt = Math.round(performance.now() - state.shownAt);
      if (state.picked.indexOf(item) >= 0) onBad(btn, rt);
      else onGood(btn, item, rt);
    }

    function onKey(ev) {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      if (!ev.target.closest || !ev.target.closest('.br-tresor-item')) return;
      onPointer(ev);
    }

    field.addEventListener('pointerdown', onPointer);
    field.addEventListener('keydown', onKey);
    ctx.setLevel(state.level);
    startRound();

    return {
      stop: function () {
        stopped = true;
        state.locked = true;
        timers.forEach(clearTimeout);
        timers = [];
        field.removeEventListener('pointerdown', onPointer);
        field.removeEventListener('keydown', onKey);
      }
    };
  }

  window.Brain.register({
    id: ID,
    name: 'Jamais deux fois',
    domain: 'memoire',
    icon: '🍄',
    color: '#5aa469',
    seconds: null,
    howto: [
      'Le sous-bois regorge de trouvailles. À chaque tour, touche vite une trouvaille pas encore choisie.',
      'Entre deux tours, tout se replace et une nouvelle apparaît. Objectif atteint : manche suivante, plus chargée.',
      'Deux fois la même, ou trop lent : une vie perdue. Sans fin, jusqu’à la dernière vie.'
    ],
    start: start
  });
})();
