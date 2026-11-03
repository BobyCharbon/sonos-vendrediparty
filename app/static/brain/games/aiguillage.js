/* Méninges — « Aiguillages » (attention partagée), SANS FIN.
   Des wagons de couleur sortent du tunnel ; toucher les aiguillages pour que chacun arrive à la gare de sa couleur.
   Paliers (5 niveaux chacun) : palier P = P + 1 gares (2 → 10), réseau reconstruit et annoncé « Palier P · N gares ».
   Table des niveaux (L = niveau, P = palier = ⌈L / 5⌉) :
     gares          min(10, P + 1)
     traversée      2,4 + 6 × 0,965^(L−1) s pour la hauteur de l'écran (L1 8,4 s · L20 5,3 · L40 3,9 · L80 2,8 → 2,4)
     cadence        0,6 + 2,6 × 0,95^(L−1) s entre deux wagons (L1 3,2 s · L20 1,6 · L40 0,95 · L80 0,65 → 0,6)
     réseau tordu   probabilité 0,1 × (P − 1) (max 0,9) d'un partage déséquilibré (chaînes d'aiguillages profondes)
   Au-delà du palier 9 (10 gares) : vitesse et cadence continuent de croître vers leur limite, réseau de plus en plus
   tordu (jusqu'à 7 rangs d'aiguillages). Un wagon à la mauvaise gare = ctx.miss (une vie) ; 6 bons wagons d'affilée =
   niveau +1 ; 2 erreurs dans un niveau = niveau −1 (jamais sous le palier de départ). */
(function () {
  'use strict';

  var GAME_COLOR = '#2f9e8f';
  var LEVELS_PER_TIER = 5;
  var LEVEL_UP_HITS = 6;           // bons wagons d'affilée pour monter d'un niveau
  var LEVEL_DOWN_MISSES = 2;       // erreurs dans un niveau pour redescendre
  var SWITCH_RADIUS = 22;          // disque dessiné : 44 px
  var MAX_HIT_RADIUS = 34;         // zone tactile jusqu'à 68 px (réduite si deux aiguillages sont proches, ≥ 22)
  var MIN_ROW_H = 52;              // écart vertical minimal entre deux rangs d'aiguillages
  var MAX_ROWS = 7;
  var MIN_H = 220;                  // hauteur minimale du réseau (téléphone en paysage : ~290 px disponibles)
  var TUNNEL_Y = 34, STATION_H = 36, SIDE = 8;
  var FLASH_MS = 700, BANNER_MS = 1700;
  var MIN_SPACING = 48;            // px entre deux wagons à la sortie du tunnel

  var STYLE = [
    '.br-aiguillage{position:relative;width:100%;flex:1 1 auto;min-height:0;touch-action:manipulation;',
    '-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent;}',
    '.br-aiguillage-canvas{position:absolute;inset:0;display:block;width:100%;height:100%;border-radius:18px;}',
    '.br-aiguillage-hud{position:absolute;top:8px;right:10px;font:600 14px system-ui,sans-serif;color:#e8f3ef;',
    'background:rgba(10,30,26,.55);padding:4px 10px;border-radius:999px;pointer-events:none;}',
    '.br-aiguillage-hud b{font-variant-numeric:tabular-nums;}',
    '.br-aiguillage-banner{position:absolute;left:50%;top:52%;transform:translate(-50%,-50%) scale(.9);opacity:0;',
    'pointer-events:none;text-align:center;padding:16px 26px;border-radius:22px;background:rgba(8,28,24,.9);',
    'border:2px solid ' + GAME_COLOR + ';box-shadow:0 12px 34px rgba(0,0,0,.45);color:#fff;font-family:system-ui,sans-serif;',
    'transition:opacity .25s ease,transform .25s ease;white-space:nowrap;}',
    '.br-aiguillage-banner.on{opacity:1;transform:translate(-50%,-50%) scale(1);}',
    '.br-aiguillage-banner b{display:block;font-size:30px;font-weight:900;letter-spacing:.01em;}',
    '.br-aiguillage-banner span{display:block;margin-top:4px;font-size:17px;font-weight:700;color:#8ff0d8;}'
  ].join('');

  function injectStyle() {
    if (document.getElementById('br-aiguillage-style')) return;
    var s = document.createElement('style');
    s.id = 'br-aiguillage-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  // Table des niveaux, réseau et dessins : games/aiguillage-niveaux.js, chargé dès maintenant (bien avant la partie).
  var SELF = (document.currentScript && document.currentScript.src) || '/static/brain/games/aiguillage.js';
  var helperReady = new Promise(function (done) {
    if (window.BrainAiguillage) { done(); return; }
    var s = document.createElement('script');
    s.src = SELF.replace(/aiguillage\.js(\?.*)?$/, 'aiguillage-niveaux.js$1');
    s.onload = done; s.onerror = done;
    document.head.appendChild(s);
  });

  function start(ctx) {
    var inner = null, ended = false;
    function go() {
      if (ended) return;
      if (!window.BrainAiguillage) { ended = true; ctx.finish({ detail: 'Le jeu n\'a pas pu se charger.' }); return; }
      inner = play(ctx, window.BrainAiguillage);
    }
    if (window.BrainAiguillage) go(); else helperReady.then(go);
    return { stop: function () { ended = true; if (inner) inner.stop(); } };
  }

  function play(ctx, A) {
    var STATIONS = A.STATIONS, MAX_STATIONS = A.MAX_STATIONS, tierOf = A.tierOf, stationsFor = A.stationsFor;
    var travelSeconds = A.travelSeconds, spawnInterval = A.spawnInterval, twist = A.twist, depthNeeded = A.depthNeeded;
    var buildTree = A.buildTree, walk = A.walk, makeSegment = A.makeSegment, pointAt = A.pointAt;
    var strokePath = A.strokePath, roundRect = A.roundRect, shape = A.shape;
    injectStyle();
    var rng = ctx.rng;
    var wrap = document.createElement('div');
    wrap.className = 'br-aiguillage';
    wrap.innerHTML = '<canvas class="br-aiguillage-canvas" aria-label="Réseau de rails : touche les aiguillages"></canvas>' +
      '<div class="br-aiguillage-hud">🚉 <b data-st>2</b> gares</div>' +
      '<div class="br-aiguillage-banner" role="status" aria-live="polite"><b data-bt></b><span data-bs></span></div>';
    ctx.root.appendChild(wrap);
    var canvas = wrap.querySelector('canvas');
    var g = canvas.getContext('2d');
    var stEl = wrap.querySelector('[data-st]'), banner = wrap.querySelector('.br-aiguillage-banner');

    var level = Math.max(1, Math.floor(ctx.level) || 1);
    var floorLevel = level - (level - 1) % LEVELS_PER_TIER;   // premier niveau du palier de départ
    var W = 0, H = 0, dpr = 1;
    var tree = null, switches = [], leaves = [], rootSeg = null, rowH = 60, hitRadius = MAX_HIT_RADIUS, minGap = 0;
    var wagons = [], flashes = [];
    var spawnAcc = 0, nextSpawn = 1, pendingRebuild = false, pauseUntil = 0, bannerUntil = 0, needBanner = true;
    var run = 0, levelMisses = 0, wagonCount = 0, shownBanners = [], builtTier = 1;
    var stopped = false, paused = false, raf = 0, last = 0, now = 0;

    function rowsAvailable() {
      var room = H - 14 - STATION_H - TUNNEL_Y - 40;
      return Math.max(depthNeeded(stationsFor(level)), Math.min(MAX_ROWS, Math.floor(room / MIN_ROW_H - 1.6)));
    }

    function rebuild() {
      var n = stationsFor(level);
      builtTier = tierOf(level);
      tree = buildTree(n, rowsAvailable(), twist(level), rng);
      switches = []; leaves = [];
      walk(tree, function (node) { (node.leaf ? leaves : switches).push(node); });
      var picks = [];
      for (var i = 0; i < MAX_STATIONS; i++) picks.push(i);
      for (var j = picks.length - 1; j > 0; j--) {
        var r = Math.floor(rng() * (j + 1)), t = picks[j]; picks[j] = picks[r]; picks[r] = t;
      }
      leaves.forEach(function (lf) { var s = STATIONS[picks[lf.slot]]; lf.color = lf.slot; lf.hex = s[0]; lf.kind = s[1]; });
      walk(tree, function (node) { node.colors = {}; });
      leaves.forEach(function (lf) { markColors(tree, lf); });
      stEl.textContent = n;
      layout();
    }

    function markColors(node, lf) {
      if (node.leaf) return node === lf;
      for (var k = 0; k < 2; k++) {
        if (markColors(node.kids[k], lf)) { node.colors[lf.color] = k; return true; }
      }
      return false;
    }

    // Chaque aiguillage est posé à la frontière entre ses deux groupes de gares : deux aiguillages d'un même rang
    // sont donc séparés d'au moins deux largeurs de gare, et deux rangs de rowH (≥ 52 px).
    function layout() {
      if (!tree || !W) return;
      var slotW = (W - SIDE * 2) / leaves.length, maxDepth = 0;
      switches.forEach(function (s) { maxDepth = Math.max(maxDepth, s.depth); });
      rowH = (H - 14 - STATION_H - TUNNEL_Y - 40) / (maxDepth + 1.6);
      leaves.forEach(function (lf) {
        lf.x = SIDE + slotW * (lf.slot + 0.5); lf.y = H - 14 - STATION_H; lf.w = Math.min(slotW - 8, 58);
      });
      switches.forEach(function (s) { s.x = SIDE + slotW * s.split; s.y = TUNNEL_Y + (s.depth + 1) * rowH; });
      var bend = Math.min(rowH * 0.6, 70);
      rootSeg = makeSegment({ x: tree.x, y: TUNNEL_Y }, tree, bend);
      switches.forEach(function (s) { s.out = [makeSegment(s, s.kids[0], bend), makeSegment(s, s.kids[1], bend)]; });
      minGap = Infinity;
      switches.forEach(function (a, i) {
        for (var k = i + 1; k < switches.length; k++) minGap = Math.min(minGap, Math.hypot(a.x - switches[k].x, a.y - switches[k].y));
      });
      hitRadius = Math.max(SWITCH_RADIUS, Math.min(MAX_HIT_RADIUS, minGap / 2));
      // Les wagons en route gardent leur distance sur leur segment.
      wagons.forEach(function (w) { w.seg = w.owner ? w.owner.out[w.branch] : rootSeg; w.d = Math.min(w.d, w.seg.len); });
    }

    function resize() {
      var r = wrap.getBoundingClientRect();
      W = Math.max(200, r.width); H = Math.max(MIN_H, r.height);
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      layout();
    }

    function showBanner() {
      var title = 'Palier ' + tierOf(level), sub = leaves.length + ' gares' + (tierOf(level) > 1 ? ' · plus rapide' : '');
      banner.querySelector('[data-bt]').textContent = title;
      banner.querySelector('[data-bs]').textContent = sub;
      shownBanners.push(title + ' · ' + sub);
      banner.classList.add('on');
      bannerUntil = now + BANNER_MS;
      pauseUntil = now + BANNER_MS * 0.7;
    }

    function spawn() {
      var lf = leaves[Math.floor(rng() * leaves.length)];
      wagons.push({ id: ++wagonCount, color: lf.color, hex: lf.hex, kind: lf.kind, d: 0, owner: null, branch: 0, seg: rootSeg });
    }

    function changeLevel(n) {
      n = Math.max(floorLevel, n);
      run = 0; levelMisses = 0;
      if (n === level) return;
      var before = tierOf(level);
      level = n;
      ctx.setLevel(level);
      if (tierOf(level) !== before) pendingRebuild = true;   // nouveau réseau à chaque palier
    }

    function arrive(w, station) {
      var ok = station.color === w.color;
      flashes.push({ x: station.x, y: station.y, ok: ok, t: now });
      if (ok) {
        ctx.hit({});
        if (stopped) return;
        if (++run >= LEVEL_UP_HITS) changeLevel(level + 1);
      } else {
        ctx.miss({});
        if (stopped) return;
        run = 0;
        if (++levelMisses >= LEVEL_DOWN_MISSES) changeLevel(level - 1);
      }
    }

    function update(dt) {
      var speed = H / travelSeconds(level);
      for (var i = wagons.length - 1; i >= 0 && !stopped; i--) {
        var w = wagons[i];
        w.d += speed * dt;
        while (w.d >= w.seg.len) {
          var node = w.seg.to, over = w.d - w.seg.len;
          if (node.leaf) { wagons.splice(i, 1); arrive(w, node); break; }
          w.owner = node; w.branch = node.state; w.seg = node.out[node.state]; w.d = over;
        }
      }
      if (stopped) return;
      if (pendingRebuild) {
        if (wagons.length) return;
        pendingRebuild = false; rebuild(); needBanner = true;
      }
      if (needBanner) { needBanner = false; showBanner(); spawnAcc = 0; nextSpawn = 0.3; }
      if (bannerUntil && now >= bannerUntil) { bannerUntil = 0; banner.classList.remove('on'); }
      if (now < pauseUntil) return;
      spawnAcc += dt;
      var lastW = wagons[wagons.length - 1];
      var clear = !lastW || lastW.seg !== rootSeg || lastW.d > MIN_SPACING;
      if (spawnAcc >= nextSpawn && clear) {
        spawn(); spawnAcc = 0;
        nextSpawn = spawnInterval(level) * (0.8 + rng() * 0.4);
      }
    }

    function drawRails(seg) {
      g.lineCap = 'round'; g.lineJoin = 'round';
      g.setLineDash([3, 7]); g.strokeStyle = '#6b5640'; g.lineWidth = 16; strokePath(g, seg.pts);
      g.setLineDash([]); g.strokeStyle = '#b8c2cc'; g.lineWidth = 9; strokePath(g, seg.pts);
      g.strokeStyle = '#173a33'; g.lineWidth = 4; strokePath(g, seg.pts);
    }

    function drawSwitch(s) {
      var active = s.out[s.state];
      var tip = pointAt(active, Math.min(46, active.len));
      g.save();
      g.strokeStyle = '#ffe9a8'; g.lineWidth = 5; g.lineCap = 'round';
      g.beginPath(); g.moveTo(s.x, s.y); g.lineTo(tip.x, tip.y); g.stroke();
      g.beginPath(); g.arc(s.x, s.y, SWITCH_RADIUS, 0, Math.PI * 2);
      g.fillStyle = 'rgba(12,40,35,.92)'; g.fill();
      g.lineWidth = 3; g.strokeStyle = GAME_COLOR; g.stroke();
      g.translate(s.x, s.y); g.rotate(Math.atan2(tip.y - s.y, tip.x - s.x));
      g.fillStyle = '#ffe9a8';
      g.beginPath(); g.moveTo(12, 0); g.lineTo(-6, -9); g.lineTo(-2, 0); g.lineTo(-6, 9); g.closePath(); g.fill();
      g.restore();
    }

    function drawStation(lf) {
      var x = lf.x - lf.w / 2, y = lf.y;
      g.fillStyle = 'rgba(0,0,0,.25)'; roundRect(g, x + 2, y + 4, lf.w, STATION_H, 7); g.fill();
      g.fillStyle = lf.hex; roundRect(g, x, y, lf.w, STATION_H, 7); g.fill();
      g.fillStyle = 'rgba(0,0,0,.28)'; g.fillRect(x, y, lf.w, 6);
      g.save(); g.translate(lf.x, y + STATION_H / 2 + 3); shape(g, lf.kind, Math.min(8, lf.w / 3)); g.restore();
    }

    function drawWagon(w) {
      var p = pointAt(w.seg, w.d);
      g.save(); g.translate(p.x, p.y); g.rotate(p.ang);
      g.fillStyle = 'rgba(0,0,0,.3)'; roundRect(g, -13, -7, 28, 18, 5); g.fill();
      g.fillStyle = w.hex; roundRect(g, -15, -9, 30, 18, 5); g.fill();
      g.strokeStyle = 'rgba(0,0,0,.45)'; g.lineWidth = 1.5; g.stroke();
      g.rotate(-p.ang); shape(g, w.kind, 5.5);
      g.restore();
    }

    function drawTunnel() {
      var x = tree.x;
      g.fillStyle = '#3d4a46'; g.beginPath(); g.arc(x, TUNNEL_Y, 30, Math.PI, 0); g.lineTo(x + 30, TUNNEL_Y + 6);
      g.lineTo(x - 30, TUNNEL_Y + 6); g.closePath(); g.fill();
      g.fillStyle = '#05100e'; g.beginPath(); g.arc(x, TUNNEL_Y + 4, 20, Math.PI, 0); g.closePath(); g.fill();
    }

    function drawFlashes() {
      flashes = flashes.filter(function (f) { return now - f.t < FLASH_MS; });
      flashes.forEach(function (f) {
        var k = (now - f.t) / FLASH_MS;
        g.save(); g.globalAlpha = 1 - k;
        g.strokeStyle = f.ok ? '#7dffb2' : '#ff6b6b'; g.lineWidth = 4;
        g.beginPath(); g.arc(f.x, f.y + STATION_H / 2, 24 + k * 22, 0, Math.PI * 2); g.stroke();
        g.fillStyle = '#fff'; g.font = '700 22px system-ui,sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(f.ok ? '✓' : '✗', f.x, f.y - 16 - k * 16);
        g.restore();
      });
    }

    function draw() {
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      var bg = g.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, '#16352f'); bg.addColorStop(1, '#0d2420');
      g.fillStyle = bg; g.fillRect(0, 0, W, H);
      if (!tree) return;
      drawRails(rootSeg);
      switches.forEach(function (s) { drawRails(s.out[0]); drawRails(s.out[1]); });
      leaves.forEach(drawStation);
      drawTunnel();
      wagons.forEach(drawWagon);
      switches.forEach(drawSwitch);
      drawFlashes();
    }

    function frame(t) {
      if (stopped) return;
      now = t;
      var dt = last ? Math.min(0.05, (t - last) / 1000) : 0;
      last = t;
      update(dt);
      if (stopped) return;
      draw();
      raf = requestAnimationFrame(frame);
    }

    function onPointer(e) {
      if (stopped || paused) return;
      var r = canvas.getBoundingClientRect();
      var x = e.clientX - r.left, y = e.clientY - r.top;
      var best = null, bestD = hitRadius;
      switches.forEach(function (s) {
        var d = Math.hypot(s.x - x, s.y - y);
        if (d <= bestD) { best = s; bestD = d; }
      });
      if (!best) return;
      e.preventDefault();
      best.state = 1 - best.state;
    }

    // Lecture seule, pour les tests automatisés (joueur scripté).
    canvas.brSnapshot = function () {
      return {
        level: level, tier: builtTier, stations: leaves.length, hitRadius: hitRadius, minGap: minGap,
        rows: switches.reduce(function (m, s) { return Math.max(m, s.depth + 1); }, 0),
        banners: shownBanners.slice(),
        switches: switches.map(function (s) { return { x: s.x, y: s.y, state: s.state }; }),
        wagons: wagons.map(function (w) {
          var to = w.seg.to;
          return to.leaf ? { id: w.id, next: -1, remaining: w.seg.len - w.d, want: -1 }
            : { id: w.id, next: switches.indexOf(to), remaining: w.seg.len - w.d, want: to.colors[w.color] };
        })
      };
    };

    var ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
    if (ro) ro.observe(wrap);
    window.addEventListener('resize', resize);
    canvas.addEventListener('pointerdown', onPointer);
    resize();
    rebuild();
    ctx.setLevel(level);
    raf = requestAnimationFrame(frame);
    // Pause du moteur (application en arrière-plan, question « Quitter la partie ? ») : les wagons s'arrêtent net
    // (aucune vie perdue loin de l'écran) et repartent au retour, là où ils étaient.
    if (ctx.onPause) ctx.onPause(function () {
      paused = true;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    });
    if (ctx.onResume) ctx.onResume(function () {
      paused = false;
      if (stopped || raf) return;
      last = 0;
      raf = requestAnimationFrame(frame);
    });

    return {
      stop: function () {
        if (stopped) return;
        stopped = true;
        cancelAnimationFrame(raf);
        if (ro) ro.disconnect();
        window.removeEventListener('resize', resize);
        canvas.removeEventListener('pointerdown', onPointer);
        canvas.brSnapshot = null;
        banner.classList.remove('on');
      }
    };
  }

  Brain.register({
    id: 'aiguillage',
    name: 'Aiguillages',
    domain: 'attention',
    icon: '🚂',
    color: GAME_COLOR,
    seconds: null,
    howto: [
      'Touche les aiguillages (les ronds) pour envoyer chaque wagon vers la gare de sa couleur et de sa forme.',
      'Un wagon à la mauvaise gare coûte une vie ; sans faute, tu montes de niveau.',
      'Chaque palier ajoute une gare (jusqu\'à 10), des wagons plus rapides et un réseau plus tordu.'
    ],
    start: start
  });
})();
