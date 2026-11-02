/* Méninges — « Jamais deux fois » (mémoire)
   Dans le sous-bois, toucher à chaque tour une trouvaille pas encore choisie dans la manche.
   Entre les tours, tout se replace et une nouvelle trouvaille apparaît. Choisir deux fois la même
   = fin de la manche. 3 manches, puis fin de partie. */
(function () {
  'use strict';

  var ID = 'tresor';
  var ITEMS = ['🍄', '🌰', '🦔', '🐌', '🍂', '🦉', '🐞', '🌸', '🪶', '🍓', '🦊', '🐿️', '🌲', '🪨',
    '🦋', '🍁', '🐸', '🫐', '🌼', '🪺', '🐝', '🍀', '🦌', '🪵', '🐛', '🌾', '🥀', '🦡'];
  var ROUNDS = 3;
  var MAX_ITEMS = 20;          // au-delà, la manche est gagnée (écran de téléphone)
  var COLS = 4;
  var TURN_PAUSE_MS = 380;     // temps du « replacement » entre deux tours
  var REVIEW_MS = 1500;        // affichage de l'erreur avant la manche suivante
  var STYLE_ID = 'br-tresor-style';

  var CSS = [
    '.br-tresor-wrap{display:flex;flex-direction:column;height:100%;min-height:360px;box-sizing:border-box;',
    'padding:12px 14px 16px;color:#eef5e9;font-family:inherit;',
    'background:radial-gradient(120% 80% at 50% 0%,#2f5d3a 0%,#1d3b27 55%,#132619 100%);border-radius:18px}',
    '.br-tresor-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:15px;',
    'font-weight:600;min-height:28px}',
    '.br-tresor-dots{display:flex;gap:6px}',
    '.br-tresor-dot{width:10px;height:10px;border-radius:50%;background:rgba(238,245,233,.25)}',
    '.br-tresor-dot.is-done{background:#9ad16b}.br-tresor-dot.is-now{background:#f2d27a}',
    '.br-tresor-msg{text-align:center;font-size:15px;opacity:.9;margin:6px 0 10px;min-height:20px}',
    '.br-tresor-field{flex:1;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;align-content:center}',
    '.br-tresor-cell{aspect-ratio:1;min-height:48px;display:flex;align-items:center;justify-content:center}',
    '.br-tresor-item{width:100%;height:100%;min-width:48px;min-height:48px;border:0;border-radius:50%;',
    'background:rgba(255,255,255,.08);box-shadow:inset 0 -3px 0 rgba(0,0,0,.25);font-size:clamp(26px,9vw,38px);',
    'line-height:1;cursor:pointer;touch-action:manipulation;-webkit-tap-highlight-color:transparent;',
    'transition:transform .18s ease,opacity .18s ease,background .18s ease;color:inherit;padding:0}',
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

  function startCount(level) {
    return Math.min(2 + Math.ceil(level / 2), 8);
  }

  function start(ctx) {
    injectStyle();
    var esc = ctx.esc;
    var timers = [];
    var stopped = false;
    var state = {
      round: 0,              // manche en cours (0..ROUNDS-1)
      pool: [],              // trouvailles présentes dans la manche
      picked: [],            // déjà choisies dans la manche
      bestCount: 0,          // plus grand nombre de trouvailles justes sur une manche
      shownAt: 0,
      locked: true,
      level: Math.max(1, ctx.level | 0)
    };

    ctx.root.innerHTML =
      '<div class="br-tresor-wrap">' +
      '<div class="br-tresor-head"><span class="br-tresor-round"></span>' +
      '<span class="br-tresor-dots" aria-hidden="true"></span></div>' +
      '<div class="br-tresor-msg" aria-live="polite"></div>' +
      '<div class="br-tresor-field" role="group" aria-label="Trouvailles du sous-bois"></div></div>';
    var field = ctx.root.querySelector('.br-tresor-field');
    var msg = ctx.root.querySelector('.br-tresor-msg');
    var roundEl = ctx.root.querySelector('.br-tresor-round');
    var dotsEl = ctx.root.querySelector('.br-tresor-dots');
    if (ctx.reducedMotion) field.classList.add('is-calm');

    function later(fn, ms) {
      var id = setTimeout(function () {
        timers = timers.filter(function (t) { return t !== id; });
        if (!stopped) fn();
      }, ms);
      timers.push(id);
    }

    function renderHead() {
      roundEl.textContent = 'Manche ' + (state.round + 1) + ' / ' + ROUNDS + ' · ' + state.picked.length + ' trouvées';
      var dots = '';
      for (var i = 0; i < ROUNDS; i++) {
        var cls = i < state.round ? ' is-done' : (i === state.round ? ' is-now' : '');
        dots += '<span class="br-tresor-dot' + cls + '"></span>';
      }
      dotsEl.innerHTML = dots;
    }

    function renderField(newItem) {
      var rows = Math.max(3, Math.ceil(state.pool.length / COLS));
      var cells = shuffled(Array.from({ length: rows * COLS }, function (_, i) { return i; }), ctx.rng);
      var slots = new Array(rows * COLS).fill(null);
      state.pool.forEach(function (item, i) { slots[cells[i]] = item; });
      field.innerHTML = slots.map(function (item) {
        if (!item) return '<div class="br-tresor-cell"></div>';
        var cls = 'br-tresor-item' + (item === newItem ? ' is-new' : '');
        return '<div class="br-tresor-cell"><button type="button" class="' + cls + '" data-item="' +
          esc(item) + '" aria-label="Trouvaille">' + esc(item) + '</button></div>';
      }).join('');
    }

    function nextItem() {
      var left = ITEMS.filter(function (it) { return state.pool.indexOf(it) < 0; });
      return left[Math.floor(ctx.rng() * left.length)];
    }

    function showTurn(newItem) {
      renderHead();
      renderField(newItem);
      field.classList.remove('is-hidden');
      state.shownAt = performance.now();
      state.locked = false;
    }

    function startRound() {
      state.pool = shuffled(ITEMS, ctx.rng).slice(0, startCount(state.level));
      state.picked = [];
      msg.textContent = state.round === 0
        ? 'Touche une trouvaille que tu n’as pas encore choisie.'
        : 'Nouvelle manche : tout repart de zéro.';
      showTurn(null);
    }

    function endRound() {
      state.bestCount = Math.max(state.bestCount, state.picked.length);
      state.round += 1;
      if (state.round >= ROUNDS) {
        ctx.finish({ detail: state.bestCount + ' trouvailles au max sur une manche' });
        return;
      }
      later(startRound, REVIEW_MS);
    }

    function onGood(btn, item, rt) {
      btn.classList.add('is-good');
      state.picked = state.picked.concat([item]);
      ctx.hit({ rt: rt });
      var count = state.picked.length;
      if (count % 3 === 0) {
        state.level += 1;
        ctx.setLevel(state.level);
      }
      if (state.pool.length >= MAX_ITEMS) {
        msg.textContent = 'Manche parfaite !';
        endRound();
        return;
      }
      var added = nextItem();
      state.pool = state.pool.concat([added]);
      msg.textContent = count + (count > 1 ? ' bonnes' : ' bonne') + ' · tout se replace…';
      field.classList.add('is-hidden');
      later(function () { showTurn(added); }, ctx.reducedMotion ? 120 : TURN_PAUSE_MS);
    }

    function onBad(btn, rt) {
      btn.classList.add('is-bad');
      ctx.miss({ rt: rt });
      state.level = Math.max(1, state.level - 1);
      ctx.setLevel(state.level);
      field.querySelectorAll('.br-tresor-item').forEach(function (b) {
        if (b !== btn && state.picked.indexOf(b.getAttribute('data-item')) >= 0) b.classList.add('is-picked');
      });
      msg.textContent = 'Déjà choisie ! ' + state.picked.length + ' trouvailles dans cette manche.';
      endRound();
    }

    function onPointer(ev) {
      var btn = ev.target.closest('.br-tresor-item');
      if (!btn || state.locked || stopped) return;
      ev.preventDefault();
      state.locked = true;
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
      'Le sous-bois regorge de trouvailles. À chaque tour, touche-en une que tu n’as pas encore choisie.',
      'Entre deux tours, tout se replace et une nouvelle trouvaille apparaît.',
      'Choisir deux fois la même termine la manche. 3 manches en tout.'
    ],
    start: start
  });
})();
