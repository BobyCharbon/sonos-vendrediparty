/* Méninges — « Aiguillages » : table des niveaux, générateur de réseau et dessins (aide de games/aiguillage.js).
   Chargé par aiguillage.js ; expose window.BrainAiguillage (aucun état, aucun minuteur). */
(function () {
  'use strict';

  var LEVELS_PER_TIER = 5;
  // 10 gares : couleur + forme (lisible même avec 10 gares ou pour un daltonien).
  var STATIONS = [['#e5484d', 'rond'], ['#3e8ef7', 'carre'], ['#30a46c', 'triangle'], ['#f5d90a', 'losange'],
    ['#8e4ec6', 'etoile'], ['#e93d82', 'croix'], ['#f76b15', 'hexa'], ['#12b5d4', 'anneau'], ['#eceff3', 'barre'],
    ['#9a6b45', 'pointe']];
  var MAX_STATIONS = STATIONS.length;

  function tierOf(level) { return Math.floor((level - 1) / LEVELS_PER_TIER) + 1; }
  function stationsFor(level) { return Math.min(MAX_STATIONS, tierOf(level) + 1); }
  function travelSeconds(level) { return 2.4 + 6 * Math.pow(0.965, level - 1); }
  function spawnInterval(level) { return 0.6 + 2.6 * Math.pow(0.95, level - 1); }
  function twist(level) { return Math.min(0.9, 0.1 * (tierOf(level) - 1)); }
  function depthNeeded(k) { return k <= 1 ? 0 : Math.ceil(Math.log2(k)); }

  // Arbre binaire à n feuilles (gares) ; « rows » = rangs d'aiguillages disponibles. Plus le réseau est tordu,
  // plus les partages sont déséquilibrés (longues chaînes d'aiguillages).
  function buildTree(n, rows, skew, rng) {
    var slot = 0;
    function make(k, depth) {
      if (k === 1) return { leaf: true, slot: slot++, depth: depth };
      var room = rows - depth - 1, lo = 1, hi = k - 1;
      while (lo < k - 1 && (depthNeeded(lo) > room || depthNeeded(k - lo) > room)) lo++;
      while (hi > lo && (depthNeeded(hi) > room || depthNeeded(k - hi) > room)) hi--;
      var a = rng() < skew ? lo + Math.floor(rng() * (hi - lo + 1)) : (rng() < 0.5 ? Math.floor(k / 2) : Math.ceil(k / 2));
      a = Math.max(lo, Math.min(hi, a));
      var node = { leaf: false, depth: depth, state: rng() < 0.5 ? 0 : 1 };
      node.kids = [make(a, depth + 1)];
      node.split = slot;           // première gare du sous-arbre de droite : l'aiguillage se place à cette frontière
      node.kids.push(make(k - a, depth + 1));
      return node;
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
    for (var i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
    return { to: to, pts: pts, cum: cum, len: cum[cum.length - 1] };
  }

  function pointAt(seg, d) {
    for (var i = 1; i < seg.pts.length; i++) {
      if (d <= seg.cum[i] || i === seg.pts.length - 1) {
        var a = seg.pts[i - 1], b = seg.pts[i];
        var t = Math.max(0, Math.min(1, (d - seg.cum[i - 1]) / (seg.cum[i] - seg.cum[i - 1] || 1)));
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
    g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r);
    g.closePath();
  }

  function poly(g, n, r, rot) {
    g.beginPath();
    for (var i = 0; i < n; i++) {
      var a = rot + i * Math.PI * 2 / n;
      g[i ? 'lineTo' : 'moveTo'](Math.cos(a) * r, Math.sin(a) * r);
    }
    g.closePath();
  }

  // Forme d'une gare, centrée en (0, 0), rayon r.
  function shape(g, kind, r) {
    g.fillStyle = '#fff'; g.strokeStyle = 'rgba(0,0,0,.55)'; g.lineWidth = 1.5;
    if (kind === 'rond') { g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); }
    else if (kind === 'carre') { g.beginPath(); g.rect(-r * 0.85, -r * 0.85, r * 1.7, r * 1.7); }
    else if (kind === 'triangle') poly(g, 3, r * 1.1, -Math.PI / 2);
    else if (kind === 'losange') poly(g, 4, r * 1.1, 0);
    else if (kind === 'hexa') poly(g, 6, r, 0);
    else if (kind === 'pointe') poly(g, 3, r * 1.1, Math.PI / 2);
    else if (kind === 'etoile') {
      g.beginPath();
      for (var i = 0; i < 10; i++) {
        var a = -Math.PI / 2 + i * Math.PI / 5, k = i % 2 ? r * 0.45 : r * 1.1;
        g[i ? 'lineTo' : 'moveTo'](Math.cos(a) * k, Math.sin(a) * k);
      }
      g.closePath();
    } else if (kind === 'croix') { g.beginPath(); g.rect(-r, -r * 0.35, r * 2, r * 0.7); g.rect(-r * 0.35, -r, r * 0.7, r * 2); }
    else if (kind === 'anneau') { g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.arc(0, 0, r * 0.45, 0, Math.PI * 2, true); }
    else { g.beginPath(); g.rect(-r, -r * 0.4, r * 2, r * 0.8); }
    g.fill('evenodd'); g.stroke();
  }

  window.BrainAiguillage = {
    STATIONS: STATIONS, MAX_STATIONS: MAX_STATIONS, LEVELS_PER_TIER: LEVELS_PER_TIER,
    tierOf: tierOf, stationsFor: stationsFor, travelSeconds: travelSeconds, spawnInterval: spawnInterval,
    twist: twist, depthNeeded: depthNeeded, buildTree: buildTree, walk: walk, makeSegment: makeSegment,
    pointAt: pointAt, strokePath: strokePath, roundRect: roundRect, shape: shape
  };
})();
