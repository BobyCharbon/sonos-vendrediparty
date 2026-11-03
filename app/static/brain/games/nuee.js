/* Méninges — « Le vol » : glisser dans la direction de l'oiseau du MILIEU (tâche de flanker).
   Jeu SANS FIN (contrat v2) : chaque volée a un délai de réponse qui raccourcit ; trop lent = une vie.

   Table des niveaux (n = niveau, palier = 5 niveaux ; « délai » = temps pour répondre à une volée) :
     n 1-5   ligne, puis colonne (3) et croix (4) ; 29 → 35 % de voisins trompeurs ; délai 2,5 → 2,1 s ; dérive dès n 5
     n 6-10  + sautoir, pente, vague ; voisins aux sens mélangés (20 → 26 %) ; délai 2,0 → 1,7 s
     n 11-15 + grande croix (8 voisins) ; 43 → 49 % trompeurs ; délai 1,6 → 1,4 s
     n 16-20 + carré (8 voisins) ; dérive 2× plus rapide qu'à n 10 ; délai 1,33 → 1,17 s
     n 21-30 oiseau du milieu de la MÊME couleur que les autres, oiseaux qui rapetissent ; délai 1,14 → 0,92 s
     n 31-40 jusqu'à 80 % de trompeurs dont 60 % mélangés, dérive maximale ; délai 0,90 → 0,79 s
     n > 40  le délai continue de baisser (0,69 s à n 60) vers 0,65 s ; oiseaux réduits jusqu'à 62 % (n 53).
   Montée : 4 bonnes d'affilée. Descente : 2 erreurs de suite, jamais sous le niveau de départ. */
(function () {
  'use strict';

  var ID = 'nuee';
  var COLOR = '#2fb3a3';
  var SWIPE_MIN = 24;        // px minimum pour qu'un glissé compte
  var NEXT_DELAY = 260;      // ms entre une réponse et la formation suivante
  var NEXT_DELAY_CALM = 160;
  var UP_STREAK = 4;         // bonnes d'affilée pour monter d'un niveau
  var DOWN_ERRORS = 2;       // erreurs (sans bonne entre) pour descendre
  var DEADLINE_MIN = 650;    // ms : délai plancher (limite humaine)
  var DEADLINE_SPAN = 1850;  // ms ajoutées au niveau 1 (2,5 s au total)
  var DEADLINE_DECAY = 15;   // niveaux pour réduire l'écart d'un facteur e
  var SAME_COLOR_FROM = 21;  // niveau dès lequel l'oiseau du milieu n'est plus plus foncé

  var DIRS = ['droite', 'bas', 'gauche', 'haut'];
  var ANGLE = { droite: 0, bas: 90, gauche: 180, haut: 270 };
  var KEYS = { ArrowRight: 'droite', ArrowDown: 'bas', ArrowLeft: 'gauche', ArrowUp: 'haut' };

  // Positions des voisins (unité = écart entre deux oiseaux), centre en (0,0).
  var FORMATIONS = {
    ligne: [[-2, 0], [-1, 0], [1, 0], [2, 0]],
    colonne: [[0, -2], [0, -1], [0, 1], [0, 2]],
    croix: [[-1, 0], [1, 0], [0, -1], [0, 1]],
    sautoir: [[-1, -1], [1, -1], [-1, 1], [1, 1]],
    pente: [[-1.4, -1.4], [-0.7, -0.7], [0.7, 0.7], [1.4, 1.4]],
    vague: [[-2, 0.7], [-1, -0.35], [1, -0.35], [2, 0.7]],
    grandeCroix: [[-2, 0], [-1, 0], [1, 0], [2, 0], [0, -2], [0, -1], [0, 1], [0, 2]],
    carre: [[-1, -1], [0, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [0, 1], [1, 1]],
  };
  // Formations débloquées : [niveau minimum, nom].
  var UNLOCK = [[1, 'ligne'], [3, 'colonne'], [4, 'croix'], [6, 'sautoir'], [7, 'pente'], [8, 'vague'],
    [11, 'grandeCroix'], [16, 'carre']];

  /** Paramètres d'un niveau (aucune borne haute : tout tend vers une limite). */
  function levelConfig(n, calm) {
    var forms = UNLOCK.filter(function (u) { return n >= u[0]; }).map(function (u) { return u[1]; });
    return {
      forms: forms,
      conflict: Math.min(0.8, 0.27 + n * 0.015),                          // part de volées trompeuses
      mixed: n >= 6 ? Math.min(0.6, 0.2 + (n - 6) * 0.015) : 0,          // voisins dans des sens différents
      drift: calm || n < 5 ? 0 : Math.min(1.6, 0.25 + (n - 5) * 0.05),   // vitesse de dérive
      wander: n >= 3,                                                     // position de départ variable
      sameColor: n >= SAME_COLOR_FROM,
      shrink: n >= SAME_COLOR_FROM ? Math.max(0.62, 1 - (n - SAME_COLOR_FROM) * 0.012) : 1,
      deadline: Math.round(DEADLINE_MIN + DEADLINE_SPAN * Math.exp(-(n - 1) / DEADLINE_DECAY)),
    };
  }

  var CSS = [
    '.br-nuee{position:relative;flex:1;width:100%;height:100%;min-height:420px;display:flex;flex-direction:column;',
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
    '.br-nuee-time{position:absolute;left:14px;right:14px;top:10px;height:5px;border-radius:3px;',
    'background:rgba(255,255,255,.3);pointer-events:none}',
    '.br-nuee-time i{display:block;height:100%;border-radius:3px;background:#fff;transform-origin:left center}',
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
    seconds: null,
    howto: [
      'Une nuée d\'oiseaux passe : regarde seulement celui du MILIEU.',
      'Glisse le doigt (ou appuie sur une flèche) dans la direction où il vole, avant qu\'il ne s\'envole.',
      'Ses voisins essaient de te tromper. 3 vies : la nuée accélère sans fin tant que tu tiens !',
    ],
    start: function (ctx) {
      injectStyle();
      var rng = ctx.rng;
      var calm = !!ctx.reducedMotion;
      var floor = Math.max(1, ctx.level | 0 || 1);    // jamais sous le niveau de départ (1er niveau du palier)
      var level = floor;
      var streak = 0, errors = 0;
      var alive = true, accepting = false;
      var trial = null, shownAt = 0;
      var raf = 0, nextTimer = 0, limitTimer = 0, startPt = null;

      ctx.root.innerHTML =
        '<div class="br-nuee' + (calm ? ' br-nuee-calm' : '') + '">' +
        '<div class="br-nuee-sky" role="application" aria-label="Zone de glissé : direction de l\'oiseau du milieu">' +
        '<div class="br-nuee-flock"></div><div class="br-nuee-time"><i></i></div></div>' +
        '<div class="br-nuee-hint">Glisse dans la direction de l\'oiseau du milieu</div></div>';
      var sky = ctx.root.querySelector('.br-nuee-sky');
      var flock = ctx.root.querySelector('.br-nuee-flock');
      var bar = ctx.root.querySelector('.br-nuee-time i');
      var hint = ctx.root.querySelector('.br-nuee-hint');

      function makeTrial() {
        var c = levelConfig(level, calm);
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
          center: center, conflict: conflict, neighbours: neighbours, cfg: c,
          drift: c.drift, phase: rng() * Math.PI * 2, wander: c.wander,
          ox: c.wander ? rng() * 2 - 1 : 0, oy: c.wander ? rng() * 2 - 1 : 0,
        };
      }

      function geometry() {
        var w = sky.clientWidth || 360, h = sky.clientHeight || 420;
        var shrink = trial ? trial.cfg.shrink : 1;
        var size = Math.round(Math.max(30, Math.min(54, Math.floor(w / 7.5)) * shrink));
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
        var same = trial.cfg.sameColor;
        flock.innerHTML = birds.map(function (b) {
          var fill = b.center && !same ? '#1b2b4a' : '#26476b';
          return '<div class="br-nuee-bird' + (b.center ? ' is-mid' : '') + '" data-dir="' + b.dir + '" style="left:' +
            (b.x * g.gap).toFixed(1) + 'px;top:' + (b.y * g.gap).toFixed(1) + 'px;transform:rotate(' + ANGLE[b.dir] +
            'deg)">' + birdSVG(fill, b.center && !same) + '</div>';
        }).join('');
        flock.classList.remove('is-ok', 'is-ko', 'is-in');
        if (!calm) { void flock.offsetWidth; flock.classList.add('is-in'); }
        bar.style.transition = 'none';
        bar.style.transform = 'scaleX(1)';
        void bar.offsetWidth;
        bar.style.transition = 'transform ' + trial.cfg.deadline + 'ms linear';
        bar.style.transform = 'scaleX(0)';
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
        sky.dataset.level = String(level);
        render();
        placeFlock(shownAt);
        accepting = true;
        limitTimer = setTimeout(tooSlow, trial.cfg.deadline);
        if (trial.drift && !raf) raf = requestAnimationFrame(loop);
      }

      function adapt(ok) {
        if (ok) {
          errors = 0; streak += 1;
          if (streak >= UP_STREAK) { level += 1; streak = 0; ctx.setLevel(level); }
          return;
        }
        streak = 0; errors += 1;
        if (errors >= DOWN_ERRORS && level > floor) { level -= 1; errors = 0; ctx.setLevel(level); }
      }

      function settle(ok, rt, text) {
        accepting = false;
        if (limitTimer) { clearTimeout(limitTimer); limitTimer = 0; }
        adapt(ok);
        if (ok) ctx.hit({ rt: rt }); else ctx.miss({ rt: rt });
        if (!alive) return;                        // le moteur a pu arrêter la partie (plus de vie)
        flock.classList.add(ok ? 'is-ok' : 'is-ko');
        bar.style.transition = 'none';
        hint.textContent = text;
        nextTimer = setTimeout(nextTrial, calm ? NEXT_DELAY_CALM : NEXT_DELAY);
      }

      function tooSlow() {
        limitTimer = 0;
        if (!alive || !accepting) return;
        settle(false, trial.cfg.deadline, 'Trop lent : il volait vers ' + article(trial.center) + trial.center);
      }

      function article(d) { return d === 'haut' || d === 'bas' ? 'le ' : 'la '; }

      function answer(dir) {
        if (!alive || !accepting || !trial) return;
        var rt = Math.round(performance.now() - shownAt);
        var ok = dir === trial.center;
        settle(ok, rt, ok ? 'Bien vu !' : 'Raté : il volait vers ' + article(trial.center) + trial.center);
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
      if (ctx.onTimeUp) ctx.onTimeUp(function () { accepting = false; });
      ctx.setLevel(level);
      nextTrial();

      return {
        stop: function () {
          if (!alive) return;
          alive = false; accepting = false; startPt = null;
          if (raf) cancelAnimationFrame(raf);
          if (nextTimer) clearTimeout(nextTimer);
          if (limitTimer) clearTimeout(limitTimer);
          raf = 0; nextTimer = 0; limitTimer = 0;
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
