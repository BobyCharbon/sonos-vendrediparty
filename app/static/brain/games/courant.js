/* Méninges — « Contre-courant » (flexibilité).
   Feuilles vertes : répondre la direction où elles POINTENT. Feuilles orange : la direction où elles BOUGENT.
   Jeu SANS FIN (contrat v2) : chaque vague de feuilles a un délai de réponse qui raccourcit ; trop lent = une vie.

   Table des niveaux (n = niveau, palier = 5 niveaux ; « délai » = temps pour répondre à une vague de feuilles) :
     n 1-5   4 → 6 feuilles, 36 → 61 px/s, 49 → 57 % à contre-sens, règle stable 2-5 vagues, délai 3,0 → 2,5 s
     n 6-10  7 → 9 feuilles, règle qui change toutes les 1-3 vagues, délai 2,4 → 2,1 s
     n 11-15 10 → 12 feuilles qui tanguent (±8 → 10°), délai 2,0 → 1,7 s
     n 16-20 13 → 15 feuilles à vitesses inégales, 79 → 87 % à contre-sens, délai 1,66 → 1,47 s
     n 21-30 16 feuilles ; la couleur s'efface après 1,2 → 0,93 s (retenir la règle) ; délai 1,43 → 1,16 s
     n 31-40 règle qui change à chaque vague ou presque, couleur visible 0,9 → 0,63 s, délai 1,14 → 0,99 s
     n > 40  vitesse 211 px/s à n 60 → 240 ; délai 0,86 s à n 60 → 0,8 s ; couleur visible 0,35 s dès n 50.
   Montée : 5 bonnes d'affilée. Descente : 2 erreurs de suite, jamais sous le niveau de départ. */
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
  var DOWN_ERRORS = 2;
  var DEADLINE_MIN = 800, DEADLINE_SPAN = 2200, DEADLINE_DECAY = 16;   // ms, ms, niveaux
  var FADE_FROM = 21;            // niveau dès lequel la couleur des feuilles s'efface
  var GREY = '#8fa3a8';
  var COLS = 4, ROWS = 4;        // grille de placement (16 cases)
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
    '.br-courant-time{position:absolute;left:14px;right:14px;top:8px;height:5px;border-radius:3px;z-index:2;',
    'background:rgba(255,255,255,.18);pointer-events:none;}',
    '.br-courant-time i{display:block;height:100%;border-radius:3px;background:#eaf6f4;transform-origin:left center;}',
    '.br-courant-leaf path.br-courant-body{transition:fill .25s;}',
    '.br-courant-hint{text-align:center;font-size:13px;opacity:.75;}'
  ].join('');

  // Feuille dessinée pointe vers la droite (0°) ; on la fait tourner selon sa direction.
  function leafSvg(color) {
    return '<svg viewBox="0 0 46 30" width="' + LEAF_W + '" height="' + LEAF_H + '" aria-hidden="true">' +
      '<path d="M2 15 L9 15" stroke="#6b4a2b" stroke-width="3" stroke-linecap="round"/>' +
      '<path class="br-courant-body" d="M8 15 C16 1 34 2 44 15 C34 28 16 29 8 15 Z" fill="' + color + '" stroke="rgba(0,0,0,.35)" stroke-width="1.5"/>' +
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

  /** Paramètres d'un niveau : aucune borne de niveau, chaque valeur tend vers une limite humaine. */
  function levelConfig(n) {
    var minRun = n >= 31 ? 1 : n >= 6 ? 1 : 2;
    var spanRun = n >= 31 ? 1 : n >= 16 ? 2 : n >= 6 ? 3 : 4;
    return {
      leaves: Math.min(COLS * ROWS, 3 + Math.ceil(n * 0.6)),
      speed: Math.round(240 - 204 * Math.exp(-(n - 1) / 30)),
      incongruence: Math.min(0.9, 0.47 + n * 0.02),
      wobble: n >= 11 ? Math.min(20, 8 + (n - 11) * 0.4) : 0,      // degrés de tangage
      uneven: n >= 16 ? Math.min(0.5, 0.15 + (n - 16) * 0.02) : 0,  // écart de vitesse entre feuilles
      fade: n >= FADE_FROM ? Math.round(Math.max(350, 1200 - (n - FADE_FROM) * 30)) : 0,
      runMin: minRun, runSpan: spanRun,                             // vagues avant un changement de règle
      deadline: Math.round(DEADLINE_MIN + DEADLINE_SPAN * Math.exp(-(n - 1) / DEADLINE_DECAY)),
    };
  }

  function start(ctx) {
    injectStyle();
    var rng = ctx.rng;
    var wrap = document.createElement('div');
    wrap.className = 'br-courant';
    wrap.innerHTML =
      '<div class="br-courant-legend">' +
      '<span class="br-courant-chip" data-chip="pointe"><i style="background:' + GREEN + '"></i>Vertes : où elles pointent</span>' +
      '<span class="br-courant-chip" data-chip="bouge"><i style="background:' + ORANGE + '"></i>Orange : où elles vont</span>' +
      '</div><div class="br-courant-field" role="application" aria-label="Glisse dans la bonne direction">' +
      '<div class="br-courant-time"><i></i></div></div>' +
      '<div class="br-courant-hint">Glisse le doigt dans la bonne direction (ou flèches du clavier)</div>';
    ctx.root.appendChild(wrap);
    var field = wrap.querySelector('.br-courant-field');
    var bar = wrap.querySelector('.br-courant-time i');
    var chips = { pointe: wrap.querySelector('[data-chip="pointe"]'), bouge: wrap.querySelector('[data-chip="bouge"]') };

    var floor = Math.max(1, ctx.level | 0 || 1);    // jamais sous le niveau de départ (1er niveau du palier)
    var level = floor;
    var rule = rng() < 0.5 ? 'pointe' : 'bouge';
    var ruleLeft = 2 + Math.floor(rng() * 4);
    var trial = null, leaves = [];
    var locked = true, streak = 0, missRow = 0;
    var stopped = false, raf = 0, last = 0, timer = 0, limitTimer = 0, fadeTimer = 0, swipe = null;
    var motionFactor = ctx.reducedMotion ? 0.6 : 1;

    function pickDir() { return Math.floor(rng() * 4); }

    function clearTimers() {
      clearTimeout(timer); clearTimeout(limitTimer); clearTimeout(fadeTimer);
      timer = 0; limitTimer = 0; fadeTimer = 0;
    }

    function newTrial() {
      timer = 0;
      if (stopped) return;
      var c = levelConfig(level);
      ruleLeft--;
      if (ruleLeft < 0) {
        rule = rule === 'pointe' ? 'bouge' : 'pointe';
        ruleLeft = c.runMin - 1 + Math.floor(rng() * c.runSpan);
      }
      var point = pickDir(), move = point;
      if (rng() < c.incongruence) {
        move = (point + 1 + Math.floor(rng() * 3)) % 4;
      }
      trial = { point: point, move: move, rule: rule, cfg: c, t0: performance.now() };
      field.dataset.rule = rule;
      field.dataset.point = DIRS[point].name;
      field.dataset.move = DIRS[move].name;
      field.dataset.level = String(level);
      showRule(true);
      buildLeaves();
      field.classList.remove('is-ok', 'is-ko');
      startBar(c.deadline);
      locked = false;
      limitTimer = setTimeout(tooSlow, c.deadline);
      if (c.fade) fadeTimer = setTimeout(function () { fadeTimer = 0; if (!stopped && !locked) showRule(false); }, c.fade);
    }

    // Couleur et légende visibles (ou effacées aux niveaux hauts : il faut retenir la règle).
    function showRule(visible) {
      chips.pointe.classList.toggle('is-on', visible && rule === 'pointe');
      chips.bouge.classList.toggle('is-on', visible && rule === 'bouge');
      var color = !visible ? GREY : rule === 'pointe' ? GREEN : ORANGE;
      leaves.forEach(function (lf) { var b = lf.el.querySelector('.br-courant-body'); if (b) b.setAttribute('fill', color); });
    }

    function startBar(ms) {
      bar.style.transition = 'none';
      bar.style.transform = 'scaleX(1)';
      void bar.offsetWidth;
      bar.style.transition = 'transform ' + ms + 'ms linear';
      bar.style.transform = 'scaleX(0)';
    }

    function buildLeaves() {
      field.querySelectorAll('.br-courant-leaf').forEach(function (n) { n.remove(); });
      var w = field.clientWidth || 340, h = field.clientHeight || 340;
      var c = trial.cfg, cells = [];
      for (var k = 0; k < COLS * ROWS; k++) cells.push(k);
      for (var i = cells.length - 1; i > 0; i--) {
        var j = Math.floor(rng() * (i + 1));
        var t = cells[i]; cells[i] = cells[j]; cells[j] = t;
      }
      var color = rule === 'pointe' ? GREEN : ORANGE;
      var cw = w / COLS, ch = h / ROWS;
      leaves = cells.slice(0, c.leaves).map(function (cell) {
        var el = document.createElement('div');
        el.className = 'br-courant-leaf';
        el.innerHTML = leafSvg(color);
        field.appendChild(el);
        return {
          el: el,
          x: cw * (cell % COLS + 0.25 + rng() * 0.5),
          y: ch * (Math.floor(cell / COLS) + 0.25 + rng() * 0.5),
          v: 1 + (rng() * 2 - 1) * c.uneven,
          tilt: (rng() * 2 - 1) * c.wobble,
          ph: rng() * Math.PI * 2,
        };
      });
      placeLeaves(0);
    }

    function placeLeaves(time) {
      if (!trial) return;
      var ang = trial.point * 90, wob = trial.cfg.wobble && !ctx.reducedMotion;
      leaves.forEach(function (lf) {
        var a = ang + (wob ? lf.tilt * Math.sin(time * 3 + lf.ph) : 0);
        lf.el.style.transform = 'translate(' + lf.x.toFixed(1) + 'px,' + lf.y.toFixed(1) + 'px) rotate(' + a.toFixed(1) + 'deg)';
      });
    }

    function frame(t) {
      raf = 0;
      if (stopped) return;
      var dt = last ? Math.min(0.05, (t - last) / 1000) : 0;
      last = t;
      if (trial) {
        var d = DIRS[trial.move], v = trial.cfg.speed * motionFactor * dt;
        var w = field.clientWidth || 340, h = field.clientHeight || 340;
        leaves.forEach(function (lf) {
          lf.x += d.dx * v * lf.v; lf.y += d.dy * v * lf.v;
          if (lf.x > w + EDGE) lf.x -= w + 2 * EDGE;
          if (lf.x < -EDGE) lf.x += w + 2 * EDGE;
          if (lf.y > h + EDGE) lf.y -= h + 2 * EDGE;
          if (lf.y < -EDGE) lf.y += h + 2 * EDGE;
        });
        placeLeaves(t / 1000);
      }
      raf = requestAnimationFrame(frame);
    }

    function adapt(ok) {
      if (ok) {
        streak++; missRow = 0;
        if (streak >= LEVEL_UP_STREAK) { level++; streak = 0; ctx.setLevel(level); }
        return;
      }
      streak = 0; missRow++;
      if (missRow >= DOWN_ERRORS && level > floor) { level--; missRow = 0; ctx.setLevel(level); }
    }

    function settle(ok, rt) {
      locked = true;
      clearTimers();
      showRule(true);
      field.classList.add(ok ? 'is-ok' : 'is-ko');
      bar.style.transition = 'none';
      adapt(ok);
      if (ok) ctx.hit({ rt: rt }); else ctx.miss({ rt: rt });
      if (stopped) return;                         // plus de vie : le moteur a arrêté la partie
      timer = setTimeout(newTrial, FEEDBACK_MS);
    }

    function tooSlow() {
      limitTimer = 0;
      if (stopped || locked || !trial) return;
      settle(false, trial.cfg.deadline);
    }

    function answer(dir) {
      if (stopped || locked || !trial) return;
      var expected = trial.rule === 'pointe' ? trial.point : trial.move;
      settle(dir === expected, Math.round(performance.now() - trial.t0));
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
        raf = 0;
        clearTimers();
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
    seconds: null,
    howto: [
      'Des feuilles dérivent sur l’eau. Feuilles vertes : glisse vers là où elles POINTENT. Orange : vers là où elles BOUGENT.',
      'La couleur change sans prévenir, et plus tard elle s’efface : retiens-la !',
      'Réponds avant la fin de la barre. 3 vies : le courant accélère sans fin tant que tu tiens.'
    ],
    start: start
  });
})();
