/* Méninges — « L'intrus » (attention), SANS FIN (contrat v2).
   Un champ de formes : toutes ont au moins une jumelle, sauf une. La trouver et la toucher avant la fin du délai.
   3 plateaux justes d’affilée → niveau +1. Mauvaise forme ou trop lent = ctx.miss (une vie), niveau −1
   (pas sous le palier de départ).

   Table des niveaux (settings(n)) :
     formes        : 6 + n (7 au niv. 1, 36 dès le niv. 30 ; grille 4 → 5 → 6 colonnes)
     différences   : 1 caractéristique au départ, +1 tous les 4 niveaux : forme, couleur, remplissage, sens,
                     puis la TAILLE dès le niv. 30 (5 en tout)
     sortes        : ⌊(n+1)/2⌋ sortes de jumelles (limité par le nombre de formes)
     subtilité     : couleur voisine dès le niv. 15 (écart de teinte 60° → 14°), remplissage pointillé dès 18,
                     sens par huitième de tour dès 20 puis écart 45° → 15° dès 28, forme presque identique dès 25,
                     taille proche dès 30 (écart 25 % → 8 %) ; la part de différences subtiles monte avec le niveau
     délai         : 1800 + 3500·e^(−n/15) + 70 × formes ms (5,6 s au niv. 1 ; 4,6 s pour 36 formes au niv. 40)
   Au-delà, le nombre de formes reste à 36 et les écarts (teinte, sens, taille) se resserrent jusqu'à leur minimum. */
(function () {
  'use strict';

  var ID = 'intrus';
  var STYLE_ID = 'br-intrus-style';
  var NEXT_MS = 260;
  var STREAK_UP = 3;
  var MAX_COUNT = 36;
  var HUES = [0, 210, 48, 130, 270];
  var FILLS = ['plein', 'creux', 'raye'];
  var SIZES = [1, 0.78];
  var FROM = { color: 15, dotted: 18, eighth: 20, shape: 25, turn: 28, size: 30 };
  // Formes toutes asymétriques par quart de tour ; chaque forme a une sosie presque identique.
  var SHAPES = {
    pointe: 'M50 10 L88 86 L50 70 L12 86 Z',
    pointe2: 'M50 10 L88 86 L50 60 L12 86 Z',
    fleche: 'M50 8 L86 46 L64 46 L64 90 L36 90 L36 46 L14 46 Z',
    fleche2: 'M50 8 L86 46 L60 46 L60 90 L40 90 L40 46 L14 46 Z',
    goutte: 'M50 8 C70 36 84 52 84 66 A34 30 0 0 1 16 66 C16 52 30 36 50 8 Z',
    goutte2: 'M50 14 C66 36 80 52 80 66 A30 30 0 0 1 20 66 C20 52 34 36 50 14 Z',
    lune: 'M68 10 A40 40 0 0 0 68 90 A16 40 0 0 1 68 10 Z',
    lune2: 'M68 10 A40 40 0 0 0 68 90 A24 40 0 0 1 68 10 Z',
    drapeau: 'M22 8 L30 8 L30 22 L84 22 L70 42 L84 62 L30 62 L30 92 L22 92 Z',
    drapeau2: 'M22 8 L30 8 L30 22 L84 22 L76 42 L84 62 L30 62 L30 92 L22 92 Z'
  };
  var BASE_SHAPES = ['pointe', 'fleche', 'goutte', 'lune', 'drapeau'];

  var CSS = [
    '.br-intrus-wrap{display:flex;flex-direction:column;height:100%;min-height:360px;box-sizing:border-box;',
    'padding:12px 10px 16px;color:#e9ecf8;background:radial-gradient(110% 70% at 50% 10%,#2a2f5a 0%,#171a36 60%,#0f1126 100%);',
    'border-radius:18px;font-family:inherit}',
    '.br-intrus-msg{text-align:center;font-size:15px;min-height:22px;margin:2px 0 6px;opacity:.9}',
    '.br-intrus-clock{height:6px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden;margin:0 0 10px}',
    '.br-intrus-clock i{display:block;height:100%;width:0;background:#b197fc;border-radius:3px}',
    '.br-intrus-field{flex:1;display:grid;gap:6px;align-content:center;justify-content:center}',
    '.br-intrus-item{min-width:44px;min-height:44px;aspect-ratio:1;border:0;padding:5px;border-radius:12px;',
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

  function sig(f) { return f.shape + '|' + f.hue + '|' + f.fill + '|' + f.turn + '|' + f.size; }

  function colorOf(hue) { return 'hsl(' + hue + ',82%,64%)'; }

  /** Réglages du niveau n (voir la table en tête de fichier). */
  function settings(n) {
    var count = Math.min(6 + n, MAX_COUNT);
    var dims = ['shape', 'color', 'fill', 'turn'].concat(n >= FROM.size ? ['size'] : []);
    return {
      count: count,
      dimCount: Math.min(1 + Math.floor((n - 1) / 4), dims.length),
      dims: dims,
      kinds: Math.max(1, Math.min(Math.floor((n + 1) / 2), Math.floor((count - 1) / 2))),
      fills: n >= FROM.dotted ? FILLS.concat(['pointille']) : FILLS,
      turns: n >= FROM.eighth ? [0, 45, 90, 135, 180, 225, 270, 315] : [0, 90, 180, 270],
      subtle: Math.min(0.9, 0.3 + 0.025 * Math.max(0, n - FROM.color)),
      hueGap: Math.max(14, 60 - 1.2 * Math.max(0, n - FROM.color)),
      turnGap: Math.max(15, 45 - Math.max(0, n - FROM.turn)),
      sizeGap: Math.max(0.08, 0.25 - 0.005 * Math.max(0, n - FROM.size)),
      ms: Math.round(1800 + 3500 * Math.exp(-n / 15) + 70 * count),
      cols: count > 25 ? 6 : count > 16 ? 5 : 4
    };
  }

  function values(dim, s) {
    if (dim === 'shape') return BASE_SHAPES;
    if (dim === 'color') return HUES;
    if (dim === 'fill') return s.fills;
    if (dim === 'turn') return s.turns;
    return SIZES;
  }

  /** Variante « subtile » d'une caractéristique, si le niveau la permet ; sinon null. */
  function nearValue(dim, from, n, s, rng) {
    var sign = rng() < 0.5 ? -1 : 1;
    if (dim === 'color' && n >= FROM.color) return (from.hue + sign * Math.round(s.hueGap) + 360) % 360;
    if (dim === 'shape' && n >= FROM.shape) return from.shape + '2';
    if (dim === 'turn' && n >= FROM.turn) return (from.turn + sign * s.turnGap + 360) % 360;
    if (dim === 'size' && n >= FROM.size) return Math.round((from.size - s.sizeGap) * 100) / 100;
    return null;
  }

  function keyOf(dim) { return dim === 'color' ? 'hue' : dim; }

  /** Plateau : `kinds` sortes en double ou plus, et un intrus qui diffère d'une sorte par UNE caractéristique. */
  function buildBoard(n, rng) {
    var s = settings(n);
    var dims = shuffled(s.dims, rng).slice(0, s.dimCount);
    var base = { shape: pick(BASE_SHAPES, rng), hue: pick(HUES, rng), fill: 'plein', turn: 0, size: 1 };
    if (dims.indexOf('fill') < 0) base = Object.assign({}, base, { fill: pick(FILLS, rng) });
    var kinds = [];
    var seen = {};
    for (var tries = 0; kinds.length < s.kinds && tries < 300; tries++) {
      var k = Object.assign({}, base);
      dims.forEach(function (d) { k[keyOf(d)] = pick(values(d, s), rng); });
      if (!seen[sig(k)]) { seen[sig(k)] = true; kinds.push(k); }
    }
    var odd = null;
    for (var t = 0; !odd && t < 300; t++) {
      var from = pick(kinds, rng);
      var dim = pick(dims, rng);
      var near = rng() < s.subtle ? nearValue(dim, from, n, s, rng) : null;
      var cand = Object.assign({}, from);
      cand[keyOf(dim)] = near !== null ? near : pick(values(dim, s), rng);
      if (!seen[sig(cand)]) odd = cand;
    }
    if (!odd) odd = Object.assign({}, kinds[0], { hue: (kinds[0].hue + 180) % 360 });
    var items = [];
    kinds.forEach(function (k) { items.push(k, k); });
    for (var i = items.length; i < s.count - 1; i++) items.push(pick(kinds, rng));
    items.push(odd);
    return { items: shuffled(items, rng), odd: sig(odd), cols: s.cols, ms: s.ms };
  }

  function fillDef(f, uid) {
    var c = colorOf(f.hue);
    if (f.fill === 'plein') return { attr: 'fill="' + c + '"', defs: '' };
    if (f.fill === 'creux') return { attr: 'fill="none" stroke="' + c + '" stroke-width="8"', defs: '' };
    if (f.fill === 'pointille') return { attr: 'fill="none" stroke="' + c + '" stroke-width="8" stroke-dasharray="8 7"', defs: '' };
    var pid = 'br-intrus-p' + uid;
    return {
      attr: 'fill="url(#' + pid + ')" stroke="' + c + '" stroke-width="5"',
      defs: '<defs><pattern id="' + pid + '" width="12" height="12" patternUnits="userSpaceOnUse"' +
        ' patternTransform="rotate(45)"><rect width="6" height="12" fill="' + c + '"/></pattern></defs>'
    };
  }

  function svgFor(f, uid) {
    var fd = fillDef(f, uid);
    return '<svg viewBox="0 0 100 100" aria-hidden="true">' + fd.defs +
      '<path d="' + SHAPES[f.shape] + '" ' + fd.attr + ' stroke-linejoin="round" transform="rotate(' +
      f.turn + ' 50 50) translate(50 50) scale(' + f.size + ') translate(-50 -50)"/></svg>';
  }

  function start(ctx) {
    injectStyle();
    var esc = ctx.esc;
    var timers = [];
    var stopped = false;
    var floor = Math.max(1, ctx.level | 0);
    var level = floor;
    var streak = 0;
    var board = null;
    var shownAt = 0;
    var deadline = null;
    var locked = true;
    var uid = 0;

    ctx.root.innerHTML = '<div class="br-intrus-wrap"><div class="br-intrus-msg" aria-live="polite"></div>' +
      '<div class="br-intrus-clock" aria-hidden="true"><i></i></div>' +
      '<div class="br-intrus-field" role="group" aria-label="Formes"></div></div>';
    var field = ctx.root.querySelector('.br-intrus-field');
    var msg = ctx.root.querySelector('.br-intrus-msg');
    var clock = ctx.root.querySelector('.br-intrus-clock i');
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

    function render() {
      board = buildBoard(level, ctx.rng);
      field.style.gridTemplateColumns = 'repeat(' + board.cols + ',minmax(44px,' +
        (board.cols === 6 ? 56 : board.cols === 5 ? 64 : 76) + 'px))';
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
      runClock(board.ms);
      deadline = later(function () { fail(null, 'Trop lent : l’intrus est entouré en vert.'); }, board.ms);
    }

    function changeLevel(n) {
      level = Math.max(floor, n);
      ctx.setLevel(level);
    }

    function showAnswer() {
      field.querySelectorAll('.br-intrus-item').forEach(function (b) {
        if (b.getAttribute('data-sig') === board.odd) b.classList.add('is-answer');
      });
    }

    function fail(btn, text) {
      locked = true;
      cancel(deadline);
      freezeClock();
      if (btn) btn.classList.add('is-bad');
      showAnswer();
      streak = 0;
      changeLevel(level - 1);
      msg.textContent = text;
      later(render, ctx.reducedMotion ? 600 : 900);
      ctx.miss({ rt: Math.round(performance.now() - shownAt) });
    }

    function answer(btn) {
      if (!btn || locked || stopped) return;
      if (btn.getAttribute('data-sig') !== board.odd) { fail(btn, 'Raté : l’intrus est entouré en vert.'); return; }
      locked = true;
      cancel(deadline);
      freezeClock();
      btn.classList.add('is-good');
      streak += 1;
      if (streak >= STREAK_UP) { streak = 0; changeLevel(level + 1); }
      later(render, NEXT_MS);
      ctx.hit({ rt: Math.round(performance.now() - shownAt) });
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
    seconds: null,
    howto: [
      'Toutes les formes ont au moins une jumelle, sauf une : l’intrus. Touche-le avant la fin de la barre.',
      'La différence peut être la forme, la couleur, le remplissage, le sens, puis la taille — de plus en plus subtile.',
      'Mauvaise forme ou trop lent : une vie perdue. Sans fin, jusqu’à la dernière vie.'
    ],
    start: start
  });
})();
