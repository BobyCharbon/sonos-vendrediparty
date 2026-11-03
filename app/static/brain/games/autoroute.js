/* Méninges — « Trois voies » : un panneau annonce le danger (ou la voie à prendre) caché dans la brume ;
   on change de voie à temps. Route SANS FIN (contrat v2) : un choc = une vie, la vitesse ne cesse de croître.

   Table des niveaux (n = niveau ; palier P = 5 niveaux). Le « délai » est l'écart entre deux vagues, donc le temps
   pour lire le panneau et changer de voie :
     P1 n 1-5    3 voies, ⚠️ danger sur une voie (70 % du temps sur la tienne), délai 1,9 → 1,6 s, brume 42 → 46 %
     P2 n 6-10   + flèche verte (seule voie libre), délai 1,53 → 1,31 s
     P3 n 11-15  + voitures jaunes sans panneau (à voir soi-même), délai 1,27 → 1,11 s
     P4 n 16-20  + double danger (deux voies bloquées), délai 1,08 → 0,97 s, brume 53 → 54 %
     P5 n 21-25  4 VOIES (annonce « 4 voies ! ») ; + voiture qui change de voie (clignotant), délai 0,94 → 0,86 s
     P6 n 26-30  voitures cachées dans la brume : seuls leurs phares la percent, délai 0,85 → 0,79 s
     P7 n 31-40  5 VOIES ; flèche verte à deux voies ; + vagues combinées (panneau + voiture), délai 0,78 → 0,70 s
     n > 40      délai 0,63 s à n 60 → 0,6 s ; brume 59 % → 62 % ; trajet d'une vague 0,99 s à n 40 → 0,85 s.
   La vitesse affichée suit le temps de trajet d'une vague (2,45 s au niveau 1).
   Montée : 5 vagues évitées d'affilée. Descente : 2 chocs de suite, jamais sous le niveau de départ. */
(function () {
  'use strict';

  var ID = 'autoroute';
  var COLOR = '#7a5cff';
  var UP_STREAK = 5;          // obstacles évités d'affilée pour accélérer d'un niveau
  var DOWN_ERRORS = 2;        // chocs (sans réussite entre) pour ralentir d'un niveau
  var FIRST_WAVE_S = 0.9;
  var REBUILD_PAUSE_S = 1.4;  // répit quand la route gagne ou perd des voies
  var MAX_DT = 0.05;
  var CRASH_SLOW = 0.45;      // vitesse restante juste après un choc
  var CRASH_RECOVER_S = 1.3;
  var LANE_SPEED = 9;         // voies par seconde (glissement latéral de la voiture)
  var CAR_Y = 0.8;
  var KMH = 260;              // affichage : hauteur d'écran/s → km/h
  var AIM_CAR = 0.7;          // part des dangers posés sur la voie du joueur (sinon il suffirait de ne rien faire)
  var BANNER_S = 1.6;

  /** Paramètres d'un niveau, sans borne haute : tout tend vers une limite humaine. */
  function levelConfig(n) {
    var kinds = ['danger'];
    if (n >= 6) kinds.push('route');
    if (n >= 11) kinds.push('trafic');
    if (n >= 16) kinds.push('double');
    if (n >= 21) kinds.push('zigzag');
    if (n >= 31) kinds.push('combo');
    return {
      lanes: n >= 31 ? 5 : n >= 21 ? 4 : 3,
      kinds: kinds,
      interval: 0.6 + 1.3 * Math.exp(-(n - 1) / 15),   // s entre deux vagues
      travel: 0.85 + 1.6 * Math.exp(-(n - 1) / 16),    // s pour qu'une vague descende jusqu'à la voiture
      fog: 0.42 + 0.2 * (1 - Math.exp(-(n - 1) / 20)), // part de la route noyée dans la brume
      hidden: n >= 26,                                  // voitures sous la brume (phares seulement)
    };
  }

  var CSS = [
    '.br-autoroute{position:relative;flex:1;width:100%;height:100%;min-height:460px;display:flex;flex-direction:column;',
    'user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}',
    '.br-autoroute-box{position:relative;flex:1;min-height:420px}',
    '.br-autoroute-cv{position:absolute;inset:0;width:100%;height:100%;display:block;border-radius:22px;touch-action:none;cursor:pointer}',
    '.br-autoroute-hint{text-align:center;font-size:14px;opacity:.75;padding:10px 8px 2px}',
  ].join('');

  function injectStyle() {
    if (document.getElementById('br-autoroute-style')) return;
    var st = document.createElement('style');
    st.id = 'br-autoroute-style';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function rint(rng, n) { return Math.floor(rng() * n) % n; }

  Brain.register({
    id: ID,
    name: 'Trois voies',
    domain: 'attention',
    icon: '🚗',
    color: COLOR,
    seconds: null,
    howto: [
      'La route est noyée dans la brume : fie-toi au panneau du haut. ⚠️ rouge = danger sur cette voie, quitte-la.',
      'Flèche verte = voie libre, prends-la. Plus loin : voitures, clignotants, phares dans la brume… et des voies en plus.',
      'Touche à gauche ou à droite (ou les flèches). 3 vies : un choc en coûte une, la route accélère sans fin.',
    ],
    start: function (ctx) {
      injectStyle();
      var rng = ctx.rng;
      var calm = !!ctx.reducedMotion;
      var floor = Math.max(1, ctx.level | 0 || 1);   // jamais sous le niveau de départ (1er niveau du palier)
      var level = floor, cfg = levelConfig(level), lanes = cfg.lanes;
      var streak = 0, errors = 0;
      var alive = true, frozen = false;
      var raf = 0, last = 0, clock = 0, passed = 0;
      var W = 360, H = 560, dpr = 1;
      var waves = [], untilWave = FIRST_WAVE_S, scroll = 0, slow = 1, shake = 0, banner = null;
      var car = { lane: Math.floor(lanes / 2), x: Math.floor(lanes / 2), lastInput: 0 };

      ctx.root.innerHTML = '<div class="br-autoroute"><div class="br-autoroute-box"><canvas class="br-autoroute-cv" ' +
        'aria-label="Route : touche à gauche ou à droite pour changer de voie"></canvas></div>' +
        '<div class="br-autoroute-hint">◀ touche à gauche · touche à droite ▶</div></div>';
      var cv = ctx.root.querySelector('canvas');
      var g = cv.getContext('2d');

      function resize() {
        var r = cv.getBoundingClientRect();
        W = Math.max(280, Math.round(r.width || 360));
        H = Math.max(420, Math.round(r.height || 560));
        dpr = Math.min(3, window.devicePixelRatio || 1);
        cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
        g.setTransform(dpr, 0, 0, dpr, 0, 0);
      }

      var road = function () { var l = W * 0.08, w = W * 0.84; return { l: l, w: w, lane: w / lanes }; };
      function laneX(i) { var r = road(); return r.l + r.lane * (i + 0.5); }
      function carTop() { return H * CAR_Y - road().lane * 0.45; }
      function speed() { return (carTop() + 40) / cfg.travel * slow; }

      function otherLane(not) { var l = rint(rng, lanes - 1); return l >= not ? l + 1 : l; }
      function aimLane() { return rng() < AIM_CAR ? car.lane : rint(rng, lanes); }
      function unique(blocked) { return blocked.filter(function (l, i) { return blocked.indexOf(l) === i; }); }

      function spawnWave() {
        var kind = cfg.kinds[rint(rng, cfg.kinds.length)];
        var w = { kind: kind, y: -40, done: false, crashed: -1, seenAt: 0, sign: [], cars: [], from: -1 };
        var a = aimLane();
        if (kind === 'danger') w.sign = [a];
        else if (kind === 'double') w.sign = [a, otherLane(a)];
        else if (kind === 'route') {
          var open = [rint(rng, lanes)];
          if (lanes >= 5) open.push(otherLane(open[0]));
          w.sign = []; w.open = open;
        } else if (kind === 'trafic') w.cars = [a];
        else if (kind === 'zigzag') {
          var to = a, from = to === 0 ? 1 : to === lanes - 1 ? lanes - 2 : (rng() < 0.5 ? to - 1 : to + 1);
          w.cars = [to]; w.from = from;
        } else { w.sign = [a]; w.cars = [otherLane(a)]; }      // combo
        var blocked = w.open ? [] : w.sign.concat(w.cars);
        if (w.open) for (var l = 0; l < lanes; l++) if (w.open.indexOf(l) < 0) blocked.push(l);
        w.blocked = unique(blocked);
        w.looks = w.blocked.map(function () { return rint(rng, 3); });
        waves.push(w);
      }

      function hasSign(w) { return w.sign.length > 0 || !!w.open; }
      function signWave() {
        for (var i = 0; i < waves.length; i++) if (!waves[i].done && hasSign(waves[i])) return waves[i];
        return null;
      }
      function nextWave() {
        var best = null;
        waves.forEach(function (w) { if (!w.done && (!best || w.y > best.y)) best = w; });
        return best;
      }

      function setLanes(n) {
        if (n === lanes) return;
        lanes = n;
        waves = [];                               // la route se reconstruit : répit et annonce
        untilWave = REBUILD_PAUSE_S;
        car.lane = Math.min(car.lane, lanes - 1); car.x = car.lane;
        banner = { text: lanes + ' voies !', t: BANNER_S };
      }

      function adapt(ok) {
        if (ok) {
          errors = 0; streak += 1;
          if (streak >= UP_STREAK) { level += 1; streak = 0; ctx.setLevel(level); }
        } else {
          streak = 0; errors += 1;
          if (errors >= DOWN_ERRORS && level > floor) { level -= 1; errors = 0; ctx.setLevel(level); }
        }
        cfg = levelConfig(level);
        setLanes(cfg.lanes);
      }

      function resolve(w) {
        w.done = true;
        passed += 1;
        cv.dataset.passed = String(passed);
        var rt = w.seenAt && car.lastInput > w.seenAt ? Math.round(car.lastInput - w.seenAt) : undefined;
        var crash = w.blocked.indexOf(car.lane) >= 0;
        if (crash) { w.crashed = car.lane; slow = CRASH_SLOW; shake = calm ? 0 : 0.35; }
        adapt(!crash);
        if (crash) ctx.miss(rt ? { rt: rt } : {}); else ctx.hit(rt ? { rt: rt } : {});
      }

      function update(dt) {
        clock += dt;
        var v = speed();
        scroll = (scroll + v * dt) % 60;
        slow = Math.min(1, slow + dt * (1 - CRASH_SLOW) / CRASH_RECOVER_S);
        shake = Math.max(0, shake - dt);
        if (banner) { banner.t -= dt; if (banner.t <= 0) banner = null; }
        car.x = calm ? car.lane : car.x + Math.max(-1, Math.min(1, car.lane - car.x)) * Math.min(1, dt * LANE_SPEED);
        if (Math.abs(car.lane - car.x) < 0.02) car.x = car.lane;
        untilWave -= dt;
        if (untilWave <= 0) { spawnWave(); untilWave = cfg.interval; }
        var sw = signWave();
        if (sw && !sw.seenAt) sw.seenAt = performance.now();
        var top = carTop(), list = waves.slice();
        for (var i = 0; i < list.length && alive; i++) {
          var w = list[i];
          w.y += v * dt;
          if (w.from >= 0 && w.y > H * cfg.fog) w.from = -1;           // le clignotant a fini : la voiture a changé
          if (!w.done && w.y + 18 >= top) resolve(w);
        }
        waves = waves.filter(function (w) { return w.y < H + 60; });
        var nw = nextWave();
        cv.dataset.level = String(level);
        cv.dataset.lanes = String(lanes);
        cv.dataset.lane = String(car.lane);
        cv.dataset.blocked = nw ? nw.blocked.join(',') : '';
      }

      // ---------- dessin ----------
      function drawObstacle(x, y, s, look, faded) {
        g.save(); g.globalAlpha = faded ? 0.3 : 1; g.translate(x, y);
        if (look === 0) {          // cône de chantier
          g.fillStyle = '#ff7a1a';
          g.beginPath(); g.moveTo(0, -s * 0.5); g.lineTo(s * 0.32, s * 0.38); g.lineTo(-s * 0.32, s * 0.38); g.closePath(); g.fill();
          g.fillStyle = '#fff'; g.fillRect(-s * 0.17, -s * 0.05, s * 0.34, s * 0.11);
          g.fillStyle = '#3a3a3a'; g.fillRect(-s * 0.42, s * 0.36, s * 0.84, s * 0.1);
        } else if (look === 1) {   // rocher
          g.fillStyle = '#7d7f86';
          g.beginPath(); g.moveTo(-s * 0.42, s * 0.3); g.lineTo(-s * 0.3, -s * 0.2); g.lineTo(0, -s * 0.38);
          g.lineTo(s * 0.34, -s * 0.18); g.lineTo(s * 0.44, s * 0.3); g.closePath(); g.fill();
          g.fillStyle = 'rgba(255,255,255,.25)'; g.beginPath(); g.moveTo(-s * 0.2, -s * 0.15); g.lineTo(0, -s * 0.3); g.lineTo(s * 0.05, -s * 0.05); g.fill();
        } else {                   // barrière rayée
          g.fillStyle = '#fff'; g.fillRect(-s * 0.45, -s * 0.18, s * 0.9, s * 0.3);
          g.fillStyle = '#e53950';
          for (var i = 0; i < 4; i++) g.fillRect(-s * 0.45 + i * s * 0.24, -s * 0.18, s * 0.11, s * 0.3);
          g.fillStyle = '#444'; g.fillRect(-s * 0.4, s * 0.12, s * 0.08, s * 0.25); g.fillRect(s * 0.32, s * 0.12, s * 0.08, s * 0.25);
        }
        g.restore();
      }

      function drawCar(x, y, s, body, faded) {
        g.save(); g.globalAlpha = faded ? 0.35 : 1; g.translate(x, y);
        var w = s * 0.52, h = s * 0.86;
        g.fillStyle = '#111'; g.fillRect(-w / 2 - 3, -h * 0.34, 5, h * 0.2); g.fillRect(w / 2 - 2, -h * 0.34, 5, h * 0.2);
        g.fillRect(-w / 2 - 3, h * 0.16, 5, h * 0.2); g.fillRect(w / 2 - 2, h * 0.16, 5, h * 0.2);
        g.fillStyle = body;
        g.beginPath(); g.moveTo(-w / 2, -h / 2 + 8); g.quadraticCurveTo(0, -h / 2 - 6, w / 2, -h / 2 + 8);
        g.lineTo(w / 2, h / 2 - 4); g.quadraticCurveTo(0, h / 2 + 4, -w / 2, h / 2 - 4); g.closePath(); g.fill();
        g.fillStyle = 'rgba(200,235,255,.85)'; g.fillRect(-w * 0.36, -h * 0.26, w * 0.72, h * 0.18);
        g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(-w * 0.36, h * 0.12, w * 0.72, h * 0.12);
        g.restore();
      }

      function drawSign(r) {
        var w = signWave(), top = 12, hgt = Math.min(64, r.w / 3 * 0.62);
        g.fillStyle = 'rgba(16,24,48,.92)';
        g.beginPath(); g.roundRect ? g.roundRect(r.l, top, r.w, hgt, 12) : g.rect(r.l, top, r.w, hgt); g.fill();
        g.fillStyle = '#ffffff33'; g.fillRect(r.l + r.w * 0.2, top + hgt, 4, 14); g.fillRect(r.l + r.w * 0.8 - 4, top + hgt, 4, 14);
        for (var i = 0; i < lanes; i++) {
          var cx = laneX(i), cy = top + hgt / 2, s = Math.min(hgt * 0.36, r.lane * 0.3);
          if (!w) continue;
          if (w.sign.indexOf(i) >= 0) {
            g.fillStyle = '#ff4757';
            g.beginPath(); g.moveTo(cx, cy - s); g.lineTo(cx + s * 1.1, cy + s * 0.8); g.lineTo(cx - s * 1.1, cy + s * 0.8); g.closePath(); g.fill();
            g.fillStyle = '#fff'; g.font = 'bold ' + Math.round(s * 1.1) + 'px system-ui,sans-serif';
            g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('!', cx, cy + s * 0.12);
          } else if (w.open && w.open.indexOf(i) >= 0) {
            g.fillStyle = '#2ed47a';
            g.beginPath(); g.moveTo(cx - s * 0.35, cy - s); g.lineTo(cx + s * 0.35, cy - s); g.lineTo(cx + s * 0.35, cy);
            g.lineTo(cx + s * 0.85, cy); g.lineTo(cx, cy + s); g.lineTo(cx - s * 0.85, cy); g.lineTo(cx - s * 0.35, cy); g.closePath(); g.fill();
          } else {
            g.fillStyle = '#ffffff22'; g.beginPath(); g.arc(cx, cy, s * 0.35, 0, Math.PI * 2); g.fill();
          }
        }
      }

      function trafficX(w) { return laneX(w.from >= 0 ? w.from : w.cars[0]); }
      function drawTraffic(w, r) {
        var x = trafficX(w);
        drawCar(x, w.y, r.lane, '#f2c94c', w.crashed >= 0);
        if (w.from >= 0 && Math.floor(clock * 6) % 2 === 0) {            // clignotant vers la voie visée
          var side = w.cars[0] > w.from ? 1 : -1;
          g.fillStyle = '#ffb020';
          g.beginPath(); g.arc(x + side * r.lane * 0.3, w.y - r.lane * 0.3, 5, 0, Math.PI * 2); g.fill();
          g.beginPath(); g.arc(x + side * r.lane * 0.3, w.y + r.lane * 0.3, 5, 0, Math.PI * 2); g.fill();
        }
      }
      function drawHeadlights(w, r) {
        var x = trafficX(w), dx = r.lane * 0.16, y = w.y + r.lane * 0.4;
        g.fillStyle = 'rgba(255,244,190,.95)';
        g.beginPath(); g.arc(x - dx, y, 4, 0, Math.PI * 2); g.arc(x + dx, y, 4, 0, Math.PI * 2); g.fill();
        g.fillStyle = 'rgba(255,244,190,.25)';
        g.beginPath(); g.arc(x - dx, y, 11, 0, Math.PI * 2); g.arc(x + dx, y, 11, 0, Math.PI * 2); g.fill();
      }

      function draw() {
        var r = road(), sx = shake > 0 ? Math.sin(shake * 80) * 6 * shake : 0;
        g.save(); g.clearRect(0, 0, W, H); g.translate(sx, 0);
        g.fillStyle = '#3f7d5a'; g.fillRect(-10, 0, W + 20, H);                    // bas-côtés
        g.fillStyle = '#4d9068';
        for (var k = -1; k < H / 60 + 1; k++) { g.fillRect(0, k * 60 + scroll, r.l * 0.5, 30); g.fillRect(W - r.l * 0.5, k * 60 + scroll + 30, r.l * 0.5, 30); }
        g.fillStyle = '#34363f'; g.fillRect(r.l, 0, r.w, H);                       // bitume
        g.fillStyle = '#f2f2f2'; g.fillRect(r.l, 0, 4, H); g.fillRect(r.l + r.w - 4, 0, 4, H);
        g.fillStyle = '#e9e3c9';
        for (var lane = 1; lane < lanes; lane++) {
          for (var d = -1; d < H / 60 + 1; d++) g.fillRect(r.l + r.lane * lane - 2, d * 60 + scroll, 4, 30);
        }
        var s = r.lane * 0.78, hidden = cfg.hidden;
        waves.forEach(function (w) {
          w.sign.forEach(function (l) { drawObstacle(laneX(l), w.y, s, w.looks[w.blocked.indexOf(l)], w.crashed === l); });
          if (w.open) w.blocked.forEach(function (l, j) { drawObstacle(laneX(l), w.y, s, w.looks[j], w.crashed === l); });
          if (hidden && w.kind === 'trafic') drawTraffic(w, r);                    // sous la brume
        });
        var fog = g.createLinearGradient(0, 0, 0, H * cfg.fog);                   // brume
        fog.addColorStop(0, 'rgba(214,222,236,1)'); fog.addColorStop(0.72, 'rgba(214,222,236,.96)'); fog.addColorStop(1, 'rgba(214,222,236,0)');
        g.fillStyle = fog; g.fillRect(-10, 0, W + 20, H * cfg.fog);
        waves.forEach(function (w) {                                                // voitures visibles malgré la brume
          if (!w.cars.length) return;
          if (hidden && w.kind === 'trafic') drawHeadlights(w, r); else drawTraffic(w, r);
        });
        drawSign(r);
        var cx = r.l + r.lane * (car.x + 0.5);
        drawCar(cx, H * CAR_Y, r.lane, COLOR, false);
        g.fillStyle = 'rgba(255,255,255,.8)'; g.font = '600 13px system-ui,sans-serif';
        g.textAlign = 'left'; g.textBaseline = 'alphabetic';
        g.fillText(Math.round(speed() / H * KMH) + ' km/h', r.l + 8, H - 12);
        if (banner) {
          g.globalAlpha = Math.min(1, banner.t * 2);
          g.fillStyle = 'rgba(16,24,48,.85)'; g.fillRect(r.l, H * 0.5 - 26, r.w, 52);
          g.fillStyle = '#fff'; g.font = '700 24px system-ui,sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
          g.fillText(banner.text, W / 2, H * 0.5);
          g.globalAlpha = 1;
        }
        g.restore();
      }

      function loop(now) {
        raf = 0;
        if (!alive) return;
        var dt = last ? Math.min(MAX_DT, (now - last) / 1000) : 0;
        last = now;
        if (!frozen) update(dt);
        if (!alive) return;                     // le moteur a pu arrêter la partie pendant update (plus de vie)
        draw();
        if (!frozen) raf = requestAnimationFrame(loop);
      }

      function move(delta) {
        if (!alive || frozen) return;
        var next = Math.max(0, Math.min(lanes - 1, car.lane + delta));
        if (next === car.lane) return;
        car.lane = next;
        car.lastInput = performance.now();
        cv.dataset.lane = String(car.lane);
      }
      function onDown(e) {
        e.preventDefault();
        var rect = cv.getBoundingClientRect();
        move(e.clientX - rect.left < rect.width / 2 ? -1 : 1);
      }
      function onKey(e) {
        if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); move(1); }
      }

      resize();
      cv.addEventListener('pointerdown', onDown);
      window.addEventListener('keydown', onKey);
      window.addEventListener('resize', resize);
      if (ctx.onTimeUp) ctx.onTimeUp(function () { frozen = true; });
      ctx.setLevel(level);
      raf = requestAnimationFrame(loop);

      return {
        stop: function () {
          if (!alive) return;
          alive = false; frozen = true;
          if (raf) cancelAnimationFrame(raf);
          raf = 0;
          cv.removeEventListener('pointerdown', onDown);
          window.removeEventListener('keydown', onKey);
          window.removeEventListener('resize', resize);
        },
      };
    },
  });
})();
