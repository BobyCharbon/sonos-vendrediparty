/* Méninges — « Trois voies » : un panneau annonce le danger (ou la voie à prendre) caché dans la brume ;
   on change de voie à temps. Vitesse croissante tant qu'on évite tout. */
(function () {
  'use strict';

  var ID = 'autoroute';
  var COLOR = '#7a5cff';
  var MAX_LEVEL = 12;
  var UP_STREAK = 5;          // obstacles évités d'affilée pour accélérer d'un niveau
  var DOWN_ERRORS = 2;        // chocs (sans réussite entre) pour ralentir d'un niveau
  var FIRST_WAVE_S = 0.9;
  var MAX_DT = 0.05;
  var CRASH_SLOW = 0.45;      // vitesse restante juste après un choc
  var CRASH_RECOVER_S = 1.3;
  var LANE_SPEED = 9;         // voies par seconde (glissement latéral de la voiture)
  var FOG = 0.42;             // la brume cache le haut de la route (fraction de la hauteur)
  var CAR_Y = 0.8;
  var KMH = 260;              // affichage : hauteur d'écran/s → km/h

  var CSS = [
    '.br-autoroute{position:relative;width:100%;height:100%;min-height:460px;display:flex;flex-direction:column;',
    'user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}',
    '.br-autoroute-cv{flex:1;width:100%;min-height:420px;display:block;border-radius:22px;touch-action:none;cursor:pointer}',
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
    seconds: 60,
    howto: [
      'La route est noyée dans la brume : fie-toi au panneau du haut.',
      '⚠️ rouge = danger sur cette voie, quitte-la. Flèche verte = la seule voie libre, prends-la.',
      'Touche à gauche ou à droite de l\'écran (ou les flèches) pour changer de voie. Plus tu évites, plus tu vas vite !',
    ],
    start: function (ctx) {
      injectStyle();
      var rng = ctx.rng;
      var calm = !!ctx.reducedMotion;
      var level = Math.max(1, Math.min(MAX_LEVEL, ctx.level | 0 || 1));
      var streak = 0, errors = 0;
      var alive = true, frozen = false;
      var raf = 0, last = 0;
      var W = 360, H = 560, dpr = 1;
      var waves = [], untilWave = FIRST_WAVE_S, scroll = 0, slow = 1, shake = 0;
      var car = { lane: 1, x: 1, lastInput: 0 };

      ctx.root.innerHTML = '<div class="br-autoroute"><canvas class="br-autoroute-cv" ' +
        'aria-label="Route à trois voies : touche à gauche ou à droite pour changer de voie"></canvas>' +
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

      var road = function () { var l = W * 0.08, w = W * 0.84; return { l: l, w: w, lane: w / 3 }; };
      function laneX(i) { var r = road(); return r.l + r.lane * (i + 0.5); }
      function speed() { return H * (0.3 + 0.055 * (level - 1)) * slow; }
      function spacing() { return Math.max(0.85, 1.75 - 0.08 * (level - 1)); }

      function spawnWave() {
        var kinds = ['danger'];
        if (level >= 3) kinds.push('route');
        if (level >= 5) kinds.push('trafic');
        var kind = kinds[rint(rng, kinds.length)];
        var blocked;
        if (kind === 'route') { var open = rint(rng, 3); blocked = [0, 1, 2].filter(function (l) { return l !== open; }); }
        else blocked = [rint(rng, 3)];
        waves.push({
          kind: kind, blocked: blocked, y: -40, done: false, crashed: -1, seenAt: 0,
          looks: blocked.map(function () { return rint(rng, 3); }),
        });
      }

      function signWave() {
        for (var i = 0; i < waves.length; i++) if (!waves[i].done && waves[i].kind !== 'trafic') return waves[i];
        return null;
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

      function resolve(w, now) {
        w.done = true;
        var rt = w.seenAt && car.lastInput > w.seenAt ? Math.round(car.lastInput - w.seenAt) : undefined;
        if (w.blocked.indexOf(car.lane) >= 0) {
          w.crashed = car.lane; slow = CRASH_SLOW; shake = calm ? 0 : 0.35;
          ctx.miss(rt ? { rt: rt } : {});
          adapt(false);
        } else {
          ctx.hit(rt ? { rt: rt } : {});
          adapt(true);
        }
      }

      function update(dt, now) {
        var v = speed();
        scroll = (scroll + v * dt) % 60;
        slow = Math.min(1, slow + dt * (1 - CRASH_SLOW) / CRASH_RECOVER_S);
        shake = Math.max(0, shake - dt);
        car.x = calm ? car.lane : car.x + Math.max(-1, Math.min(1, car.lane - car.x)) * Math.min(1, dt * LANE_SPEED);
        if (Math.abs(car.lane - car.x) < 0.02) car.x = car.lane;
        untilWave -= dt;
        if (untilWave <= 0) { spawnWave(); untilWave = spacing(); }
        var sw = signWave();
        if (sw && !sw.seenAt) sw.seenAt = now;
        var carTop = H * CAR_Y - road().lane * 0.45;
        waves.forEach(function (w) {
          w.y += v * dt;
          if (!w.done && w.y + 18 >= carTop) resolve(w, now);
        });
        waves = waves.filter(function (w) { return w.y < H + 60; });
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
        var w = signWave(), top = 12, hgt = Math.min(64, r.lane * 0.62);
        g.fillStyle = 'rgba(16,24,48,.92)';
        g.beginPath(); g.roundRect ? g.roundRect(r.l, top, r.w, hgt, 12) : g.rect(r.l, top, r.w, hgt); g.fill();
        g.fillStyle = '#ffffff33'; g.fillRect(r.l + r.w * 0.2, top + hgt, 4, 14); g.fillRect(r.l + r.w * 0.8 - 4, top + hgt, 4, 14);
        for (var i = 0; i < 3; i++) {
          var cx = laneX(i), cy = top + hgt / 2, s = hgt * 0.36;
          if (!w) continue;
          var isBlocked = w.blocked.indexOf(i) >= 0;
          if (w.kind === 'danger' && isBlocked) {
            g.fillStyle = '#ff4757';
            g.beginPath(); g.moveTo(cx, cy - s); g.lineTo(cx + s * 1.1, cy + s * 0.8); g.lineTo(cx - s * 1.1, cy + s * 0.8); g.closePath(); g.fill();
            g.fillStyle = '#fff'; g.font = 'bold ' + Math.round(s * 1.1) + 'px system-ui,sans-serif';
            g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('!', cx, cy + s * 0.12);
          } else if (w.kind === 'route' && !isBlocked) {
            g.fillStyle = '#2ed47a';
            g.beginPath(); g.moveTo(cx - s * 0.35, cy - s); g.lineTo(cx + s * 0.35, cy - s); g.lineTo(cx + s * 0.35, cy);
            g.lineTo(cx + s * 0.85, cy); g.lineTo(cx, cy + s); g.lineTo(cx - s * 0.85, cy); g.lineTo(cx - s * 0.35, cy); g.closePath(); g.fill();
          } else {
            g.fillStyle = '#ffffff22'; g.beginPath(); g.arc(cx, cy, s * 0.35, 0, Math.PI * 2); g.fill();
          }
        }
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
        for (var lane = 1; lane < 3; lane++) {
          for (var d = -1; d < H / 60 + 1; d++) g.fillRect(r.l + r.lane * lane - 2, d * 60 + scroll, 4, 30);
        }
        var s = r.lane * 0.78;
        waves.forEach(function (w) {
          if (w.kind === 'trafic') return;
          w.blocked.forEach(function (l, j) { drawObstacle(laneX(l), w.y, s, w.looks[j], w.crashed === l); });
        });
        var fog = g.createLinearGradient(0, 0, 0, H * FOG);                       // brume
        fog.addColorStop(0, 'rgba(214,222,236,1)'); fog.addColorStop(0.72, 'rgba(214,222,236,.96)'); fog.addColorStop(1, 'rgba(214,222,236,0)');
        g.fillStyle = fog; g.fillRect(-10, 0, W + 20, H * FOG);
        waves.forEach(function (w) {                                                // voitures visibles malgré la brume
          if (w.kind === 'trafic') drawCar(laneX(w.blocked[0]), w.y, r.lane, '#f2c94c', w.crashed >= 0);
        });
        drawSign(r);
        var cx = r.l + r.lane * (car.x + 0.5);
        drawCar(cx, H * CAR_Y, r.lane, COLOR, false);
        g.fillStyle = 'rgba(255,255,255,.8)'; g.font = '600 13px system-ui,sans-serif';
        g.textAlign = 'left'; g.textBaseline = 'alphabetic';
        g.fillText(Math.round(speed() / H * KMH) + ' km/h', r.l + 8, H - 12);
        g.restore();
      }

      function loop(now) {
        raf = 0;
        if (!alive) return;
        var dt = last ? Math.min(MAX_DT, (now - last) / 1000) : 0;
        last = now;
        if (!frozen) update(dt, now);
        draw();
        if (!frozen) raf = requestAnimationFrame(loop);
      }

      function move(delta) {
        if (!alive || frozen) return;
        var next = Math.max(0, Math.min(2, car.lane + delta));
        if (next === car.lane) return;
        car.lane = next;
        car.lastInput = performance.now();
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
      ctx.onTimeUp(function () { frozen = true; });
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
