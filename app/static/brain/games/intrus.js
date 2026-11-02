/* Méninges — « L'intrus » (attention)
   Un champ de formes : toutes ont au moins une jumelle, sauf une. La trouver et la toucher.
   Plus le niveau monte, plus il y a de formes, de sortes de formes et de caractéristiques
   (forme, couleur, remplissage, sens). Juste en 6 s ou moins : niveau +1, sinon −1. 45 s. */
(function () {
  'use strict';

  var ID = 'intrus';
  var STYLE_ID = 'br-intrus-style';
  var FAST_MS = 6000;
  var MAX_LEVEL = 20;
  var NEXT_MS = 260;
  var COLORS = ['#ff6b6b', '#4dabf7', '#ffd43b', '#69db7c', '#b197fc'];
  var FILLS = ['plein', 'creux', 'raye'];
  var TURNS = [0, 90, 180, 270];
  // Formes toutes asymétriques par quart de tour, pour que le « sens » se voie toujours.
  var SHAPES = {
    pointe: 'M50 10 L88 86 L50 70 L12 86 Z',
    fleche: 'M50 8 L86 46 L64 46 L64 90 L36 90 L36 46 L14 46 Z',
    goutte: 'M50 8 C70 36 84 52 84 66 A34 30 0 0 1 16 66 C16 52 30 36 50 8 Z',
    lune: 'M68 10 A40 40 0 0 0 68 90 A16 40 0 0 1 68 10 Z',
    drapeau: 'M22 8 L30 8 L30 22 L84 22 L70 42 L84 62 L30 62 L30 92 L22 92 Z'
  };
  var SHAPE_KEYS = Object.keys(SHAPES);
  var DIMS = ['shape', 'color', 'fill', 'turn'];
  var VALUES = { shape: SHAPE_KEYS, color: COLORS, fill: FILLS, turn: TURNS };

  var CSS = [
    '.br-intrus-wrap{display:flex;flex-direction:column;height:100%;min-height:360px;box-sizing:border-box;',
    'padding:12px 12px 16px;color:#e9ecf8;background:radial-gradient(110% 70% at 50% 10%,#2a2f5a 0%,#171a36 60%,#0f1126 100%);',
    'border-radius:18px;font-family:inherit}',
    '.br-intrus-msg{text-align:center;font-size:15px;min-height:22px;margin:2px 0 10px;opacity:.9}',
    '.br-intrus-field{flex:1;display:grid;gap:6px;align-content:center;justify-content:center}',
    '.br-intrus-item{min-width:48px;min-height:48px;aspect-ratio:1;border:0;padding:6px;border-radius:14px;',
    'background:rgba(255,255,255,.06);cursor:pointer;touch-action:manipulation;-webkit-tap-highlight-color:transparent;',
    'transition:transform .15s ease,background .15s ease}',
    '.br-intrus-item svg{width:100%;height:100%;display:block;pointer-events:none}',
    '.br-intrus-item:focus-visible{outline:3px solid #ffd43b;outline-offset:2px}',
    '.br-intrus-item:active{transform:scale(.92)}',
    '.br-intrus-item.is-good{background:rgba(105,219,124,.4)}',
    '.br-intrus-item.is-bad{background:rgba(255,107,107,.45)}',
    '.br-intrus-item.is-answer{box-shadow:0 0 0 3px #69db7c}',
    '.br-intrus-field.is-in .br-intrus-item{animation:br-intrus-in .22s ease}',
    '.br-intrus-field.is-calm .br-intrus-item{animation:none;transition:none}',
    '@keyframes br-intrus-in{from{opacity:0;transform:scale(.7)}to{opacity:1;transform:scale(1)}}'
  ].join('');

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var el = document.createElement('style');
    el.id = STYLE_ID;
    el.textContent = CSS;
    document.head.appendChild(el);
  }

  function pick(list, rng) { return list[Math.floor(rng() * list.length)]; }

  function shuffled(list, rng) {
    var out = list.slice();
    for (var i = out.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var t = out[i]; out[i] = out[j]; out[j] = t;
    }
    return out;
  }

  function sig(f) { return f.shape + '|' + f.color + '|' + f.fill + '|' + f.turn; }

  /** Réglages du niveau : nombre de formes, de sortes de jumelles, caractéristiques qui varient. */
  function settings(level) {
    var count = Math.min(5 + level, 25);
    var dimCount = Math.min(1 + Math.floor((level - 1) / 3), DIMS.length);
    var kinds = Math.max(1, Math.min(Math.floor((level + 1) / 2), Math.floor((count - 1) / 2)));
    return { count: count, dimCount: dimCount, kinds: kinds };
  }

  /** Construit un plateau : `kinds` sortes en double ou plus, et un intrus qui diffère d'une sorte par UNE caractéristique. */
  function buildBoard(level, rng) {
    var s = settings(level);
    var dims = shuffled(DIMS, rng).slice(0, s.dimCount);
    var base = { shape: pick(SHAPE_KEYS, rng), color: pick(COLORS, rng), fill: 'plein', turn: 0 };
    if (dims.indexOf('fill') < 0) base = Object.assign({}, base, { fill: pick(FILLS, rng) });
    var kinds = [];
    var seen = {};
    for (var tries = 0; kinds.length < s.kinds && tries < 200; tries++) {
      var k = Object.assign({}, base);
      dims.forEach(function (d) { k[d] = pick(VALUES[d], rng); });
      if (!seen[sig(k)]) { seen[sig(k)] = true; kinds.push(k); }
    }
    var odd = null;
    for (var t = 0; !odd && t < 200; t++) {
      var from = pick(kinds, rng);
      var dim = pick(dims, rng);
      var cand = Object.assign({}, from);
      cand[dim] = pick(VALUES[dim], rng);
      if (!seen[sig(cand)]) odd = cand;
    }
    if (!odd && level > 1) return buildBoard(level - 1, rng);
    var pairs = s.count - 1;
    var items = [];
    kinds.forEach(function (k) { items.push(k, k); });
    for (var i = items.length; i < pairs; i++) items.push(pick(kinds, rng));
    items.push(odd);
    return { items: shuffled(items, rng), odd: sig(odd), cols: s.count > 16 ? 5 : 4 };
  }

  function fillDef(f, uid) {
    if (f.fill === 'plein') return { attr: 'fill="' + f.color + '"', defs: '' };
    if (f.fill === 'creux') return { attr: 'fill="none" stroke="' + f.color + '" stroke-width="8"', defs: '' };
    var pid = 'br-intrus-p' + uid;
    return {
      attr: 'fill="url(#' + pid + ')" stroke="' + f.color + '" stroke-width="5"',
      defs: '<defs><pattern id="' + pid + '" width="12" height="12" patternUnits="userSpaceOnUse"' +
        ' patternTransform="rotate(45)"><rect width="6" height="12" fill="' + f.color + '"/></pattern></defs>'
    };
  }

  function svgFor(f, uid) {
    var fd = fillDef(f, uid);
    return '<svg viewBox="0 0 100 100" aria-hidden="true">' + fd.defs +
      '<path d="' + SHAPES[f.shape] + '" ' + fd.attr + ' stroke-linejoin="round" transform="rotate(' +
      f.turn + ' 50 50)"/></svg>';
  }

  function start(ctx) {
    injectStyle();
    var esc = ctx.esc;
    var timers = [];
    var stopped = false;
    var level = Math.max(1, Math.min(MAX_LEVEL, ctx.level | 0));
    var best = level;
    var board = null;
    var shownAt = 0;
    var locked = true;
    var uid = 0;

    ctx.root.innerHTML = '<div class="br-intrus-wrap"><div class="br-intrus-msg" aria-live="polite"></div>' +
      '<div class="br-intrus-field" role="group" aria-label="Formes"></div></div>';
    var field = ctx.root.querySelector('.br-intrus-field');
    var msg = ctx.root.querySelector('.br-intrus-msg');
    if (ctx.reducedMotion) field.classList.add('is-calm');

    function later(fn, ms) {
      var id = setTimeout(function () {
        timers = timers.filter(function (t) { return t !== id; });
        if (!stopped) fn();
      }, ms);
      timers.push(id);
    }

    function render() {
      board = buildBoard(level, ctx.rng);
      field.style.gridTemplateColumns = 'repeat(' + board.cols + ',minmax(48px,' + (board.cols === 5 ? 64 : 76) + 'px))';
      field.innerHTML = board.items.map(function (f) {
        uid += 1;
        return '<button type="button" class="br-intrus-item" data-sig="' + esc(sig(f)) +
          '" aria-label="Forme">' + svgFor(f, uid) + '</button>';
      }).join('');
      field.classList.remove('is-in');
      void field.offsetWidth;
      if (!ctx.reducedMotion) field.classList.add('is-in');
      msg.textContent = 'Touche la forme qui n’a pas de jumelle. · Niveau ' + level;
      shownAt = performance.now();
      locked = false;
    }

    function setLevel(n) {
      level = Math.max(1, Math.min(MAX_LEVEL, n));
      best = Math.max(best, level);
      ctx.setLevel(level);
    }

    function answer(btn) {
      if (!btn || locked || stopped) return;
      locked = true;
      var rt = Math.round(performance.now() - shownAt);
      if (btn.getAttribute('data-sig') === board.odd) {
        btn.classList.add('is-good');
        ctx.hit({ rt: rt });
        setLevel(rt <= FAST_MS ? level + 1 : level - 1);
        later(render, NEXT_MS);
        return;
      }
      btn.classList.add('is-bad');
      field.querySelectorAll('.br-intrus-item').forEach(function (b) {
        if (b.getAttribute('data-sig') === board.odd) b.classList.add('is-answer');
      });
      ctx.miss({ rt: rt });
      setLevel(level - 1);
      msg.textContent = 'Raté : l’intrus est entouré en vert.';
      later(render, ctx.reducedMotion ? 600 : 900);
    }

    function onPointer(ev) {
      var btn = ev.target.closest('.br-intrus-item');
      if (!btn) return;
      ev.preventDefault();
      answer(btn);
    }

    function onKey(ev) {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      var btn = ev.target.closest && ev.target.closest('.br-intrus-item');
      if (!btn) return;
      ev.preventDefault();
      answer(btn);
    }

    function stop() {
      stopped = true;
      locked = true;
      timers.forEach(clearTimeout);
      timers = [];
      field.removeEventListener('pointerdown', onPointer);
      field.removeEventListener('keydown', onKey);
    }

    field.addEventListener('pointerdown', onPointer);
    field.addEventListener('keydown', onKey);
    ctx.onTimeUp(stop);
    ctx.setLevel(level);
    render();

    return { stop: stop };
  }

  window.Brain.register({
    id: ID,
    name: 'L’intrus',
    domain: 'attention',
    icon: '🔭',
    color: '#7c6cf0',
    seconds: 45,
    howto: [
      'Toutes les formes ont au moins une jumelle, sauf une : l’intrus.',
      'Touche-le vite : la différence peut être la forme, la couleur, le remplissage ou le sens.',
      'Plus tu es rapide, plus il y a de formes. 45 secondes.'
    ],
    start: start
  });
})();
