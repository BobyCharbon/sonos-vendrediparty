/* Méninges — « Contre-courant » (flexibilité).
   Feuilles vertes : répondre la direction où elles POINTENT. Feuilles orange : la direction où elles BOUGENT. */
(function () {
  'use strict';

  var GAME_COLOR = '#2bb3a3';
  var GREEN = '#3fb950';
  var ORANGE = '#f0883e';
  var DIRS = [
    { name: 'droite', dx: 1, dy: 0, key: 'ArrowRight' },
    { name: 'bas', dx: 0, dy: 1, key: 'ArrowDown' },
    { name: 'gauche', dx: -1, dy: 0, key: 'ArrowLeft' },
    { name: 'haut', dx: 0, dy: -1, key: 'ArrowUp' }
  ];
  var SWIPE_MIN = 24;            // px pour qu'un glissé compte
  var FEEDBACK_MS = 260;
  var LEVEL_UP_STREAK = 5;
  var MAX_LEVEL = 12;
  var LEAF_W = 46, LEAF_H = 30;
  var EDGE = 30;                 // marge de rebouclage hors du champ

  var STYLE = [
    '.br-courant{position:relative;display:flex;flex-direction:column;gap:8px;width:100%;height:100%;min-height:440px;',
    'touch-action:none;-webkit-user-select:none;user-select:none;font-family:system-ui,sans-serif;color:#eaf6f4;}',
    '.br-courant-legend{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;font-size:13px;font-weight:600;}',
    '.br-courant-chip{display:flex;align-items:center;gap:6px;padding:5px 10px;border-radius:999px;',
    'background:rgba(255,255,255,.08);transition:background .2s,transform .2s;}',
    '.br-courant-chip i{width:12px;height:12px;border-radius:50%;display:inline-block;}',
    '.br-courant-chip.is-on{background:rgba(255,255,255,.2);transform:scale(1.04);}',
    '.br-courant-field{position:relative;flex:1;min-height:340px;border-radius:20px;overflow:hidden;',
    'background:radial-gradient(120% 90% at 30% 20%,#1d5b6b 0%,#0f3846 55%,#0a2833 100%);',
    'box-shadow:inset 0 0 0 3px transparent;transition:box-shadow .15s;}',
    '.br-courant-field::before{content:"";position:absolute;inset:0;opacity:.18;pointer-events:none;',
    'background:repeating-linear-gradient(165deg,transparent 0 22px,rgba(255,255,255,.35) 22px 24px,transparent 24px 46px);}',
    '.br-courant-field.is-ok{box-shadow:inset 0 0 0 4px #7dffb2;}',
    '.br-courant-field.is-ko{box-shadow:inset 0 0 0 4px #ff6b6b;}',
    '.br-courant-leaf{position:absolute;left:0;top:0;width:' + LEAF_W + 'px;height:' + LEAF_H + 'px;',
    'margin:-' + (LEAF_H / 2) + 'px 0 0 -' + (LEAF_W / 2) + 'px;will-change:transform;pointer-events:none;}',
    '.br-courant-hint{text-align:center;font-size:13px;opacity:.75;}'
  ].join('');

  // Feuille dessinée pointe vers la droite (0°) ; on la fait tourner selon sa direction.
  function leafSvg(color) {
    return '<svg viewBox="0 0 46 30" width="' + LEAF_W + '" height="' + LEAF_H + '" aria-hidden="true">' +
      '<path d="M2 15 L9 15" stroke="#6b4a2b" stroke-width="3" stroke-linecap="round"/>' +
      '<path d="M8 15 C16 1 34 2 44 15 C34 28 16 29 8 15 Z" fill="' + color + '" stroke="rgba(0,0,0,.35)" stroke-width="1.5"/>' +
      '<path d="M9 15 L40 15 M20 15 L27 8 M20 15 L27 22 M29 15 L34 10 M29 15 L34 20" stroke="rgba(255,255,255,.55)" ' +
      'stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>';
  }

  function injectStyle() {
    if (document.getElementById('br-courant-style')) return;
    var s = document.createElement('style');
    s.id = 'br-courant-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function leafCount(level) { return Math.min(10, 3 + level); }
  function speedFor(level) { return Math.min(130, 34 + level * 8); }
  function incongruence(level) { return Math.min(0.85, 0.5 + level * 0.04); }

  function start(ctx) {
    injectStyle();
    var rng = ctx.rng;
    var wrap = document.createElement('div');
    wrap.className = 'br-courant';
    wrap.innerHTML =
      '<div class="br-courant-legend">' +
      '<span class="br-courant-chip" data-chip="pointe"><i style="background:' + GREEN + '"></i>Vertes : où elles pointent</span>' +
      '<span class="br-courant-chip" data-chip="bouge"><i style="background:' + ORANGE + '"></i>Orange : où elles vont</span>' +
      '</div><div class="br-courant-field" role="application" aria-label="Glisse dans la bonne direction"></div>' +
      '<div class="br-courant-hint">Glisse le doigt dans la bonne direction (ou flèches du clavier)</div>';
    ctx.root.appendChild(wrap);
    var field = wrap.querySelector('.br-courant-field');
    var chips = { pointe: wrap.querySelector('[data-chip="pointe"]'), bouge: wrap.querySelector('[data-chip="bouge"]') };

    var level = Math.max(1, Math.min(MAX_LEVEL, ctx.level || 1));
    var rule = rng() < 0.5 ? 'pointe' : 'bouge';
    var ruleLeft = 2 + Math.floor(rng() * 4);
    var trial = null, leaves = [];
    var locked = true, streak = 0, missRow = 0;
    var stopped = false, raf = 0, last = 0, timer = 0, swipe = null;
    var motionFactor = ctx.reducedMotion ? 0.6 : 1;

    function pickDir() { return Math.floor(rng() * 4); }

    function newTrial() {
      if (stopped) return;
      ruleLeft--;
      if (ruleLeft < 0) {
        rule = rule === 'pointe' ? 'bouge' : 'pointe';
        ruleLeft = 1 + Math.floor(rng() * 4);
      }
      var point = pickDir(), move = point;
      if (rng() < incongruence(level)) {
        move = (point + 1 + Math.floor(rng() * 3)) % 4;
      }
      trial = { point: point, move: move, rule: rule, t0: performance.now() };
      field.dataset.rule = rule;
      field.dataset.point = DIRS[point].name;
      field.dataset.move = DIRS[move].name;
      chips.pointe.classList.toggle('is-on', rule === 'pointe');
      chips.bouge.classList.toggle('is-on', rule === 'bouge');
      buildLeaves();
      field.classList.remove('is-ok', 'is-ko');
      locked = false;
    }

    function buildLeaves() {
      field.querySelectorAll('.br-courant-leaf').forEach(function (n) { n.remove(); });
      var w = field.clientWidth || 340, h = field.clientHeight || 340;
      var n = leafCount(level), cols = 3, rows = Math.ceil(12 / cols);
      var cells = [];
      for (var c = 0; c < cols * rows; c++) cells.push(c);
      for (var i = cells.length - 1; i > 0; i--) {
        var j = Math.floor(rng() * (i + 1));
        var t = cells[i]; cells[i] = cells[j]; cells[j] = t;
      }
      var color = rule === 'pointe' ? GREEN : ORANGE;
      leaves = cells.slice(0, n).map(function (cell) {
        var el = document.createElement('div');
        el.className = 'br-courant-leaf';
        el.innerHTML = leafSvg(color);
        field.appendChild(el);
        var cw = w / cols, ch = h / rows;
        return {
          el: el,
          x: cw * (cell % cols + 0.25 + rng() * 0.5),
          y: ch * (Math.floor(cell / cols) + 0.25 + rng() * 0.5)
        };
      });
      placeLeaves();
    }

    function placeLeaves() {
      if (!trial) return;
      var ang = trial.point * 90;
      leaves.forEach(function (lf) {
        lf.el.style.transform = 'translate(' + lf.x.toFixed(1) + 'px,' + lf.y.toFixed(1) + 'px) rotate(' + ang + 'deg)';
      });
    }

    function frame(t) {
      if (stopped) return;
      var dt = last ? Math.min(0.05, (t - last) / 1000) : 0;
      last = t;
      if (trial) {
        var d = DIRS[trial.move], v = speedFor(level) * motionFactor * dt;
        var w = field.clientWidth || 340, h = field.clientHeight || 340;
        leaves.forEach(function (lf) {
          lf.x += d.dx * v; lf.y += d.dy * v;
          if (lf.x > w + EDGE) lf.x -= w + 2 * EDGE;
          if (lf.x < -EDGE) lf.x += w + 2 * EDGE;
          if (lf.y > h + EDGE) lf.y -= h + 2 * EDGE;
          if (lf.y < -EDGE) lf.y += h + 2 * EDGE;
        });
        placeLeaves();
      }
      raf = requestAnimationFrame(frame);
    }

    function answer(dir) {
      if (stopped || locked || !trial) return;
      locked = true;
      var expected = trial.rule === 'pointe' ? trial.point : trial.move;
      var rt = Math.round(performance.now() - trial.t0);
      var ok = dir === expected;
      field.classList.add(ok ? 'is-ok' : 'is-ko');
      if (ok) {
        ctx.hit({ rt: rt });
        streak++; missRow = 0;
        if (streak >= LEVEL_UP_STREAK && level < MAX_LEVEL) { level++; streak = 0; ctx.setLevel(level); }
      } else {
        ctx.miss({ rt: rt });
        streak = 0; missRow++;
        if (missRow >= 2 && level > 1) { level--; missRow = 0; ctx.setLevel(level); }
      }
      timer = setTimeout(newTrial, FEEDBACK_MS);
    }

    function onDown(e) {
      swipe = { x: e.clientX, y: e.clientY, id: e.pointerId };
      e.preventDefault();
    }

    function onUp(e) {
      if (!swipe || e.pointerId !== swipe.id) return;
      var dx = e.clientX - swipe.x, dy = e.clientY - swipe.y;
      swipe = null;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_MIN) return;
      if (Math.abs(dx) >= Math.abs(dy)) answer(dx > 0 ? 0 : 2);
      else answer(dy > 0 ? 1 : 3);
    }

    function onCancel() { swipe = null; }

    function onKey(e) {
      for (var i = 0; i < DIRS.length; i++) {
        if (e.key === DIRS[i].key) { e.preventDefault(); answer(i); return; }
      }
    }

    wrap.addEventListener('pointerdown', onDown);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onCancel);
    window.addEventListener('keydown', onKey);
    ctx.setLevel(level);
    raf = requestAnimationFrame(frame);
    timer = setTimeout(newTrial, 300);

    return {
      stop: function () {
        if (stopped) return;
        stopped = true;
        locked = true;
        cancelAnimationFrame(raf);
        clearTimeout(timer);
        wrap.removeEventListener('pointerdown', onDown);
        window.removeEventListener('pointerup', onUp);
        window.removeEventListener('pointercancel', onCancel);
        window.removeEventListener('keydown', onKey);
      }
    };
  }

  Brain.register({
    id: 'courant',
    name: 'Contre-courant',
    domain: 'flexibilite',
    icon: '🍃',
    color: GAME_COLOR,
    seconds: 45,
    howto: [
      'Des feuilles dérivent sur l’eau.',
      'Feuilles vertes : glisse vers là où elles POINTENT. Feuilles orange : glisse vers là où elles BOUGENT.',
      'La couleur change sans prévenir : reste attentif !'
    ],
    start: start
  });
})();
