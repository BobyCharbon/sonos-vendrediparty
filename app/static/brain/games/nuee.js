/* Méninges — « Le vol » : glisser dans la direction de l'oiseau du MILIEU (tâche de flanker).
   Formations variées, voisins parfois trompeurs, formation qui dérive aux niveaux hauts. */
(function () {
  'use strict';

  var ID = 'nuee';
  var COLOR = '#2fb3a3';
  var MAX_LEVEL = 10;
  var SWIPE_MIN = 24;        // px minimum pour qu'un glissé compte
  var NEXT_DELAY = 260;      // ms entre une réponse et la formation suivante
  var NEXT_DELAY_CALM = 160;
  var UP_STREAK = 4;         // bonnes d'affilée pour monter d'un niveau
  var DOWN_ERRORS = 2;       // erreurs (sans bonne entre) pour descendre

  var DIRS = ['droite', 'bas', 'gauche', 'haut'];
  var ANGLE = { droite: 0, bas: 90, gauche: 180, haut: 270 };
  var KEYS = { ArrowRight: 'droite', ArrowDown: 'bas', ArrowLeft: 'gauche', ArrowUp: 'haut' };

  // Positions des 4 voisins (unité = écart entre deux oiseaux), centre en (0,0).
  var FORMATIONS = {
    ligne: [[-2, 0], [-1, 0], [1, 0], [2, 0]],
    colonne: [[0, -2], [0, -1], [0, 1], [0, 2]],
    croix: [[-1, 0], [1, 0], [0, -1], [0, 1]],
    sautoir: [[-1, -1], [1, -1], [-1, 1], [1, 1]],
    pente: [[-1.4, -1.4], [-0.7, -0.7], [0.7, 0.7], [1.4, 1.4]],
    vague: [[-2, 0.7], [-1, -0.35], [1, -0.35], [2, 0.7]],
  };
  var BY_LEVEL = [
    ['ligne'],
    ['ligne', 'colonne'],
    ['ligne', 'colonne', 'croix'],
    ['ligne', 'colonne', 'croix', 'sautoir'],
    ['ligne', 'colonne', 'croix', 'sautoir', 'pente'],
    ['ligne', 'colonne', 'croix', 'sautoir', 'pente', 'vague'],
  ];

  var CSS = [
    '.br-nuee{position:relative;width:100%;height:100%;min-height:420px;display:flex;flex-direction:column;',
    'user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}',
    '.br-nuee-sky{position:relative;flex:1;min-height:360px;border-radius:22px;touch-action:none;cursor:grab;',
    'background:radial-gradient(120% 80% at 50% 0%,#bfe9f2 0%,#7cc6d6 45%,#3d8ea6 100%);',
    'box-shadow:inset 0 0 0 1px rgba(255,255,255,.25)}',
    '.br-nuee-sky::before,.br-nuee-sky::after{content:"";position:absolute;border-radius:50%;background:rgba(255,255,255,.35);',
    'filter:blur(6px);pointer-events:none}',
    '.br-nuee-sky::before{width:46%;height:12%;left:6%;top:12%}',
    '.br-nuee-sky::after{width:38%;height:9%;right:4%;bottom:14%}',
    '.br-nuee-flock{position:absolute;left:0;top:0;width:0;height:0;will-change:transform}',
    '.br-nuee-bird{position:absolute;width:var(--br-nuee-size);height:var(--br-nuee-size);',
    'margin:calc(var(--br-nuee-size) / -2) 0 0 calc(var(--br-nuee-size) / -2)}',
    '.br-nuee-bird svg{width:100%;height:100%;display:block;overflow:visible}',
    '.br-nuee-flock.is-in .br-nuee-bird{animation:br-nuee-pop .18s ease-out both}',
    '.br-nuee-flock.is-ok{filter:drop-shadow(0 0 8px rgba(255,255,255,.9))}',
    '.br-nuee-flock.is-ko .br-nuee-bird{animation:br-nuee-shake .22s ease-in-out}',
    '.br-nuee-calm .br-nuee-flock .br-nuee-bird{animation:none!important}',
    '@keyframes br-nuee-pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:scale(1)}}',
    '@keyframes br-nuee-shake{0%,100%{translate:0 0}25%{translate:-5px 0}75%{translate:5px 0}}',
    '.br-nuee-hint{text-align:center;font-size:14px;opacity:.75;padding:10px 8px 2px;min-height:22px}',
  ].join('');

  function injectStyle() {
    if (document.getElementById('br-nuee-style')) return;
    var st = document.createElement('style');
    st.id = 'br-nuee-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  // Oiseau original : corps en goutte, deux ailes en croissant, queue fourchue ; pointe vers la droite.
  function birdSVG(fill, isCenter) {
    var eye = isCenter ? '#fff' : 'rgba(255,255,255,.85)';
    return '<svg viewBox="-50 -50 100 100" aria-hidden="true">' +
      '<path d="M-34 0 L-48 -12 L-40 0 L-48 12 Z" fill="' + fill + '" opacity=".85"/>' +
      '<path d="M-6 -4 C-18 -30 -34 -40 -44 -42 C-28 -30 -22 -16 -18 -2 Z" fill="' + fill + '" opacity=".9"/>' +
      '<path d="M-6 4 C-18 30 -34 40 -44 42 C-28 30 -22 16 -18 2 Z" fill="' + fill + '" opacity=".9"/>' +
      '<path d="M-38 0 C-26 -12 10 -14 26 -6 C34 -3 40 -1 46 0 C40 1 34 3 26 6 C10 14 -26 12 -38 0 Z" fill="' + fill + '"/>' +
      '<path d="M38 -2 L50 0 L38 2 Z" fill="#f5b041"/>' +
      '<circle cx="28" cy="-3" r="3.2" fill="' + eye + '"/></svg>';
  }

  function pick(rng, list) { return list[Math.floor(rng() * list.length) % list.length]; }

  function otherDir(rng, dir) {
    var rest = DIRS.filter(function (d) { return d !== dir; });
    return pick(rng, rest);
  }

  Brain.register({
    id: ID,
    name: 'Le vol',
    domain: 'attention',
    icon: '🐦',
    color: COLOR,
    seconds: 45,
    howto: [
      'Une nuée d\'oiseaux passe : regarde seulement celui du MILIEU.',
      'Glisse le doigt (ou appuie sur une flèche) dans la direction où il vole.',
      'Ses voisins essaient de te tromper : ne les écoute pas !',
    ],
    start: function (ctx) {
      injectStyle();
      var rng = ctx.rng;
      var calm = !!ctx.reducedMotion;
      var level = Math.max(1, Math.min(MAX_LEVEL, ctx.level | 0 || 1));
      var streak = 0, errors = 0;
      var alive = true, accepting = false;
      var trial = null, shownAt = 0;
      var raf = 0, nextTimer = 0, startPt = null;

      ctx.root.innerHTML =
        '<div class="br-nuee' + (calm ? ' br-nuee-calm' : '') + '">' +
        '<div class="br-nuee-sky" role="application" aria-label="Zone de glissé : direction de l\'oiseau du milieu">' +
        '<div class="br-nuee-flock"></div></div>' +
        '<div class="br-nuee-hint">Glisse dans la direction de l\'oiseau du milieu</div></div>';
      var sky = ctx.root.querySelector('.br-nuee-sky');
      var flock = ctx.root.querySelector('.br-nuee-flock');
      var hint = ctx.root.querySelector('.br-nuee-hint');

      function config() {
        var forms = BY_LEVEL[Math.min(BY_LEVEL.length - 1, Math.floor((level - 1) / 1.5))];
        return {
          forms: forms,
          conflict: Math.min(0.7, 0.3 + level * 0.04),        // part de volées trompeuses
          mixed: level >= 6 ? 0.35 : 0,                        // voisins dans des sens différents
          drift: calm ? 0 : (level >= 5 ? 0.25 + (level - 5) * 0.12 : 0), // vitesse de dérive
          wander: level >= 3,                                  // position de départ variable
        };
      }

      function makeTrial() {
        var c = config();
        var center = pick(rng, DIRS);
        var conflict = rng() < c.conflict;
        var flank = conflict ? otherDir(rng, center) : center;
        var mixed = conflict && rng() < c.mixed;
        var neighbours = FORMATIONS[pick(rng, c.forms)].map(function (p) {
          var d = mixed ? pick(rng, DIRS) : flank;
          return { x: p[0], y: p[1], dir: d };
        });
        if (mixed && neighbours.every(function (n) { return n.dir === center; })) neighbours[0].dir = otherDir(rng, center);
        return {
          center: center, conflict: conflict, neighbours: neighbours,
          drift: c.drift, phase: rng() * Math.PI * 2, wander: c.wander,
          ox: c.wander ? rng() * 2 - 1 : 0, oy: c.wander ? rng() * 2 - 1 : 0,
        };
      }

      function geometry() {
        var w = sky.clientWidth || 360, h = sky.clientHeight || 420;
        var size = Math.max(36, Math.min(54, Math.floor(w / 7.5)));
        var gap = size * 1.25;
        return { w: w, h: h, size: size, gap: gap };
      }

      function extent(t) {
        var mx = 0, my = 0;
        t.neighbours.forEach(function (n) { mx = Math.max(mx, Math.abs(n.x)); my = Math.max(my, Math.abs(n.y)); });
        return { x: mx, y: my };
      }

      function placeFlock(now) {
        if (!trial) return;
        var g = geometry(), e = extent(trial);
        var roomX = Math.max(0, g.w / 2 - (e.x * g.gap + g.size * 0.75));
        var roomY = Math.max(0, g.h / 2 - (e.y * g.gap + g.size * 0.75));
        var fx = trial.ox * roomX * 0.5, fy = trial.oy * roomY * 0.5;
        if (trial.drift) {
          var t = (now - shownAt) / 1000 * trial.drift * 2 + trial.phase;
          fx = Math.sin(t) * roomX * 0.8;
          fy = Math.sin(t * 1.3 + 1) * roomY * 0.6;
        }
        flock.style.transform = 'translate(' + (g.w / 2 + fx).toFixed(1) + 'px,' + (g.h / 2 + fy).toFixed(1) + 'px)';
      }

      function render() {
        var g = geometry();
        sky.style.setProperty('--br-nuee-size', g.size + 'px');
        var birds = [{ x: 0, y: 0, dir: trial.center, center: true }].concat(trial.neighbours);
        flock.innerHTML = birds.map(function (b) {
          var fill = b.center ? '#1b2b4a' : '#26476b';
          return '<div class="br-nuee-bird" style="left:' + (b.x * g.gap).toFixed(1) + 'px;top:' +
            (b.y * g.gap).toFixed(1) + 'px;transform:rotate(' + ANGLE[b.dir] + 'deg)">' + birdSVG(fill, b.center) + '</div>';
        }).join('');
        flock.classList.remove('is-ok', 'is-ko', 'is-in');
        if (!calm) { void flock.offsetWidth; flock.classList.add('is-in'); }
      }

      function loop(now) {
        raf = 0;
        if (!alive || !trial || !trial.drift) return;
        placeFlock(now);
        raf = requestAnimationFrame(loop);
      }

      function nextTrial() {
        nextTimer = 0;
        if (!alive) return;
        trial = makeTrial();
        shownAt = performance.now();
        render();
        placeFlock(shownAt);
        accepting = true;
        if (trial.drift && !raf) raf = requestAnimationFrame(loop);
      }

      function adapt(ok) {
        if (ok) {
          errors = 0; streak += 1;
          if (streak >= UP_STREAK && level < MAX_LEVEL) { level += 1; streak = 0; ctx.setLevel(level); }
          return;
        }
        streak = 0; errors += 1;
        if (errors >= DOWN_ERRORS && level > 1) { level -= 1; errors = 0; ctx.setLevel(level); }
      }

      function answer(dir) {
        if (!alive || !accepting || !trial) return;
        accepting = false;
        var rt = Math.round(performance.now() - shownAt);
        var ok = dir === trial.center;
        if (ok) ctx.hit({ rt: rt }); else ctx.miss({ rt: rt });
        adapt(ok);
        if (!alive) return;
        flock.classList.add(ok ? 'is-ok' : 'is-ko');
        hint.textContent = ok ? 'Bien vu !' : 'Raté : il volait vers ' + (trial.center === 'haut' || trial.center === 'bas' ? 'le ' : 'la ') + trial.center;
        nextTimer = setTimeout(nextTrial, calm ? NEXT_DELAY_CALM : NEXT_DELAY);
      }

      function dirOf(dx, dy) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) < SWIPE_MIN) return null;
        if (Math.abs(dx) >= Math.abs(dy)) return dx > 0 ? 'droite' : 'gauche';
        return dy > 0 ? 'bas' : 'haut';
      }

      function onDown(e) {
        if (!alive) return;
        startPt = { x: e.clientX, y: e.clientY, id: e.pointerId };
        try { sky.setPointerCapture(e.pointerId); } catch (_) { /* capture facultative */ }
        e.preventDefault();
      }
      function onMove(e) {
        if (!startPt || e.pointerId !== startPt.id) return;
        var d = dirOf(e.clientX - startPt.x, e.clientY - startPt.y);
        if (d) { startPt = null; answer(d); }
      }
      function onUp(e) {
        if (!startPt || e.pointerId !== startPt.id) return;
        var d = dirOf(e.clientX - startPt.x, e.clientY - startPt.y);
        startPt = null;
        if (d) answer(d);
      }
      function onCancel() { startPt = null; }
      function onKey(e) {
        var d = KEYS[e.key];
        if (!d || !alive) return;
        e.preventDefault();
        answer(d);
      }

      sky.addEventListener('pointerdown', onDown);
      sky.addEventListener('pointermove', onMove);
      sky.addEventListener('pointerup', onUp);
      sky.addEventListener('pointercancel', onCancel);
      window.addEventListener('keydown', onKey);
      ctx.onTimeUp(function () { accepting = false; });
      ctx.setLevel(level);
      nextTrial();

      return {
        stop: function () {
          if (!alive) return;
          alive = false; accepting = false; startPt = null;
          if (raf) cancelAnimationFrame(raf);
          if (nextTimer) clearTimeout(nextTimer);
          raf = 0; nextTimer = 0;
          sky.removeEventListener('pointerdown', onDown);
          sky.removeEventListener('pointermove', onMove);
          sky.removeEventListener('pointerup', onUp);
          sky.removeEventListener('pointercancel', onCancel);
          window.removeEventListener('keydown', onKey);
        },
      };
    },
  });
})();
