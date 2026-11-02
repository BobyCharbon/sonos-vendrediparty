/* Méninges — « Aiguillages » (attention partagée).
   Des wagons de couleur sortent du tunnel ; toucher les aiguillages pour que chacun arrive à la gare de sa couleur. */
(function () {
  'use strict';

  var GAME_COLOR = '#2f9e8f';
  var STATION_COLORS = ['#e5484d', '#3e8ef7', '#30a46c', '#f5d90a', '#8e4ec6', '#e93d82'];
  var SWITCH_RADIUS = 22;          // disque dessiné : 44 px
  var SWITCH_HIT_RADIUS = 34;      // zone tactile : 68 px
  var TUNNEL_Y = 34;
  var STATION_H = 36;
  var BATCH_SIZE = 8;              // arrivées avant de réévaluer le niveau
  var MAX_LEVEL = 14;
  var FLASH_MS = 700;
  var MIN_SPACING = 70;            // px entre deux wagons à la sortie du tunnel

  var STYLE = [
    '.br-aiguillage{position:relative;width:100%;height:100%;min-height:440px;touch-action:manipulation;',
    '-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent;}',
    '.br-aiguillage-canvas{display:block;width:100%;height:100%;border-radius:18px;}',
    '.br-aiguillage-hud{position:absolute;top:8px;right:10px;display:flex;gap:10px;font:600 14px system-ui,sans-serif;',
    'color:#e8f3ef;background:rgba(10,30,26,.55);padding:4px 10px;border-radius:999px;pointer-events:none;}',
    '.br-aiguillage-hud b{font-variant-numeric:tabular-nums;}'
  ].join('');

  function injectStyle() {
    if (document.getElementById('br-aiguillage-style')) return;
    var s = document.createElement('style');
    s.id = 'br-aiguillage-style';
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function stationsFor(level) { return Math.min(6, 2 + Math.floor(level / 2)); }
  function travelSeconds(level) { return Math.max(4.4, 8 - Math.min(level, MAX_LEVEL) * 0.3); }
  function spawnInterval(level) { return Math.max(1.2, 3 - level * 0.15); }

  // Arbre binaire à n feuilles (gares), profondeur ≤ 3 : chaque sous-arbre a au plus 3 gares.
  function buildTree(n, rng) {
    var slot = 0;
    function make(k, depth) {
      if (k === 1) return { leaf: true, slot: slot++, depth: depth };
      var lo = Math.max(1, k - 3), hi = Math.min(k - 1, 3);
      var a = lo + Math.floor(rng() * (hi - lo + 1));
      return { leaf: false, depth: depth, state: rng() < 0.5 ? 0 : 1, kids: [make(a, depth + 1), make(k - a, depth + 1)] };
    }
    return make(n, 0);
  }

  function walk(node, fn) {
    fn(node);
    if (!node.leaf) { walk(node.kids[0], fn); walk(node.kids[1], fn); }
  }

  function makeSegment(from, to, bend) {
    var pts = from.x === to.x ? [from, { x: to.x, y: to.y }]
      : [from, { x: to.x, y: from.y + bend }, { x: to.x, y: to.y }];
    var cum = [0];
    for (var i = 1; i < pts.length; i++) {
      cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
    }
    return { to: to, pts: pts, cum: cum, len: cum[cum.length - 1] };
  }

  function pointAt(seg, d) {
    for (var i = 1; i < seg.pts.length; i++) {
      if (d <= seg.cum[i] || i === seg.pts.length - 1) {
        var a = seg.pts[i - 1], b = seg.pts[i];
        var span = seg.cum[i] - seg.cum[i - 1] || 1;
        var t = Math.max(0, Math.min(1, (d - seg.cum[i - 1]) / span));
        return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, ang: Math.atan2(b.y - a.y, b.x - a.x) };
      }
    }
    return { x: seg.pts[0].x, y: seg.pts[0].y, ang: Math.PI / 2 };
  }

  function strokePath(g, pts) {
    g.beginPath();
    g.moveTo(pts[0].x, pts[0].y);
    for (var i = 1; i < pts.length; i++) g.lineTo(pts[i].x, pts[i].y);
    g.stroke();
  }

  function roundRect(g, x, y, w, h, r) {
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }

  function start(ctx) {
    injectStyle();
    var rng = ctx.rng;
    var wrap = document.createElement('div');
    wrap.className = 'br-aiguillage';
    wrap.innerHTML = '<canvas class="br-aiguillage-canvas" aria-label="Réseau de rails : touche les aiguillages"></canvas>' +
      '<div class="br-aiguillage-hud"><span>✔ <b data-ok>0</b></span><span>✖ <b data-ko>0</b></span></div>';
    ctx.root.appendChild(wrap);
    var canvas = wrap.querySelector('canvas');
    var g = canvas.getContext('2d');
    var okEl = wrap.querySelector('[data-ok]'), koEl = wrap.querySelector('[data-ko]');

    var level = Math.max(1, Math.min(MAX_LEVEL, ctx.level || 1));
    var W = 0, H = 0, dpr = 1;
    var tree = null, switches = [], leaves = [], rootSeg = null, rowH = 60;
    var wagons = [], flashes = [];
    var spawnAcc = 0, nextSpawn = 1.2, pendingRebuild = false;
    var batch = 0, batchMiss = 0, totalOk = 0, totalKo = 0;
    var stopped = false, raf = 0, last = 0, now = 0;

    function rebuild() {
      var n = stationsFor(level);
      tree = buildTree(n, rng);
      switches = []; leaves = [];
      walk(tree, function (node) { (node.leaf ? leaves : switches).push(node); });
      var colors = STATION_COLORS.slice(0, n);
      for (var i = colors.length - 1; i > 0; i--) {
        var j = Math.floor(rng() * (i + 1));
        var t = colors[i]; colors[i] = colors[j]; colors[j] = t;
      }
      leaves.forEach(function (lf) { lf.color = lf.slot; lf.hex = colors[lf.slot]; });
      walk(tree, function (node) { node.colors = {}; });
      leaves.forEach(function (lf) { markColors(tree, lf); });
      layout();
    }

    function markColors(node, lf) {
      if (node.leaf) return node === lf;
      for (var k = 0; k < 2; k++) {
        if (markColors(node.kids[k], lf)) { node.colors[lf.color] = k; return true; }
      }
      return false;
    }

    function place(node, maxDepth) {
      if (node.leaf) {
        var slotW = (W - 16) / leaves.length;
        node.x = 8 + slotW * (node.slot + 0.5);
        node.y = H - 14 - STATION_H;
        node.w = Math.min(slotW - 10, 58);
        return;
      }
      place(node.kids[0], maxDepth); place(node.kids[1], maxDepth);
      node.x = (node.kids[0].x + node.kids[1].x) / 2;
      node.y = TUNNEL_Y + (node.depth + 1) * rowH;
    }

    function layout() {
      if (!tree || !W) return;
      var maxDepth = 0;
      switches.forEach(function (s) { maxDepth = Math.max(maxDepth, s.depth); });
      rowH = (H - 14 - STATION_H - TUNNEL_Y - 40) / (maxDepth + 1.6);
      place(tree, maxDepth);
      var bend = Math.min(rowH * 0.6, 70);
      rootSeg = makeSegment({ x: tree.x, y: TUNNEL_Y }, tree, bend);
      switches.forEach(function (s) { s.out = [makeSegment(s, s.kids[0], bend), makeSegment(s, s.kids[1], bend)]; });
      // Les wagons en route gardent leur distance relative sur leur segment.
      wagons.forEach(function (w) { w.seg = w.segOf(); w.d = Math.min(w.d, w.seg.len); });
    }

    function resize() {
      var r = wrap.getBoundingClientRect();
      W = Math.max(200, r.width); H = Math.max(360, r.height);
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      layout();
    }

    function spawn() {
      var lf = leaves[Math.floor(rng() * leaves.length)];
      var w = { color: lf.color, hex: lf.hex, d: 0, owner: null, branch: 0 };
      w.seg = rootSeg;
      w.segOf = function () { return w.owner ? w.owner.out[w.branch] : rootSeg; };
      wagons.push(w);
    }

    function arrive(w, station) {
      var ok = station.color === w.color;
      flashes.push({ x: station.x, y: station.y, ok: ok, t: now });
      if (ok) { totalOk++; ctx.hit({}); } else { totalKo++; batchMiss++; ctx.miss({}); }
      okEl.textContent = totalOk; koEl.textContent = totalKo;
      batch++;
      if (batch < BATCH_SIZE) return;
      var before = level;
      if (batchMiss <= 1) level = Math.min(MAX_LEVEL, level + 1);
      else if (batchMiss >= 3) level = Math.max(1, level - 1);
      batch = 0; batchMiss = 0;
      if (level !== before) {
        ctx.setLevel(level);
        if (stationsFor(level) !== leaves.length) pendingRebuild = true;
      }
    }

    function update(dt) {
      var speed = H / travelSeconds(level);
      for (var i = wagons.length - 1; i >= 0; i--) {
        var w = wagons[i];
        w.d += speed * dt;
        while (w.d >= w.seg.len) {
          var node = w.seg.to, over = w.d - w.seg.len;
          if (node.leaf) { wagons.splice(i, 1); arrive(w, node); break; }
          w.owner = node; w.branch = node.state; w.seg = node.out[node.state]; w.d = over;
        }
      }
      if (pendingRebuild) {
        if (!wagons.length) { pendingRebuild = false; rebuild(); spawnAcc = 0; nextSpawn = 1; }
        return;
      }
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
      var ang = Math.atan2(tip.y - s.y, tip.x - s.x);
      g.translate(s.x, s.y); g.rotate(ang);
      g.fillStyle = '#ffe9a8';
      g.beginPath(); g.moveTo(12, 0); g.lineTo(-6, -9); g.lineTo(-2, 0); g.lineTo(-6, 9); g.closePath(); g.fill();
      g.restore();
    }

    function drawStation(lf) {
      var x = lf.x - lf.w / 2, y = lf.y;
      g.fillStyle = 'rgba(0,0,0,.25)'; roundRect(g, x + 2, y + 4, lf.w, STATION_H, 7); g.fill();
      g.fillStyle = lf.hex; roundRect(g, x, y, lf.w, STATION_H, 7); g.fill();
      g.fillStyle = 'rgba(255,255,255,.85)';
      roundRect(g, lf.x - 7, y + 12, 14, STATION_H - 12, 3); g.fill();
      g.fillStyle = 'rgba(0,0,0,.28)'; g.fillRect(x, y, lf.w, 6);
    }

    function drawWagon(w) {
      var p = pointAt(w.seg, w.d);
      g.save(); g.translate(p.x, p.y); g.rotate(p.ang);
      g.fillStyle = 'rgba(0,0,0,.3)'; roundRect(g, -13, -7, 28, 18, 5); g.fill();
      g.fillStyle = w.hex; roundRect(g, -15, -9, 30, 18, 5); g.fill();
      g.strokeStyle = 'rgba(0,0,0,.45)'; g.lineWidth = 1.5; g.stroke();
      g.fillStyle = 'rgba(255,255,255,.75)'; g.fillRect(-9, -5, 6, 10); g.fillRect(1, -5, 6, 10);
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
      draw();
      raf = requestAnimationFrame(frame);
    }

    function onPointer(e) {
      if (stopped) return;
      var r = canvas.getBoundingClientRect();
      var x = e.clientX - r.left, y = e.clientY - r.top;
      var best = null, bestD = SWITCH_HIT_RADIUS;
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
        level: level,
        stations: leaves.length,
        switches: switches.map(function (s) { return { x: s.x, y: s.y, state: s.state }; }),
        wagons: wagons.map(function (w) {
          var to = w.seg.to;
          return to.leaf ? { next: -1, remaining: w.seg.len - w.d, want: -1 }
            : { next: switches.indexOf(to), remaining: w.seg.len - w.d, want: to.colors[w.color] };
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

    return {
      stop: function () {
        if (stopped) return;
        stopped = true;
        cancelAnimationFrame(raf);
        if (ro) ro.disconnect();
        window.removeEventListener('resize', resize);
        canvas.removeEventListener('pointerdown', onPointer);
        canvas.brSnapshot = null;
      }
    };
  }

  Brain.register({
    id: 'aiguillage',
    name: 'Aiguillages',
    domain: 'attention',
    icon: '🚂',
    color: GAME_COLOR,
    seconds: 120,
    howto: [
      'Des wagons de couleur sortent du tunnel et roulent sur les rails.',
      'Touche les aiguillages (les ronds) pour envoyer chaque wagon vers la gare de sa couleur.',
      'Anticipe : plusieurs wagons roulent en même temps, et le réseau grandit avec ton niveau.'
    ],
    start: start
  });
})();
