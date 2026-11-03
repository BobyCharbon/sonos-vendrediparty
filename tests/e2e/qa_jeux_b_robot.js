// Robots QA de Méninges (zone « jeux B ») : jouent dans le VRAI moteur (core.js) par de vrais événements.
// window.qaRobot(game, {mode, input, rt}) : mode = parfait | passif | errant ; input = touch | key.
// Les réponses sont calculées à partir de ce qui est AFFICHÉ (texte, couleur), avec un évaluateur indépendant des jeux.
(function () {
  'use strict';
  const SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';

  // ── Évaluateur de calculs tels qu'un humain les lit : « de » (fraction de) > puissance > × ÷ > + − ──
  function tokens(text) {
    const s = text.replace(/[  ]/g, ' ');
    const out = [];
    let i = 0;
    while (i < s.length) {
      const c = s[i];
      if (c === ' ') { i++; continue; }
      if (/\d/.test(c)) {
        let j = i;
        while (j < s.length && (/\d/.test(s[j]) || (s[j] === ' ' && /^ \d{3}(?!\d)/.test(s.slice(j))))) j++;
        out.push({ t: 'n', v: Number(s.slice(i, j).replace(/ /g, '')) });
        i = j; continue;
      }
      if (SUP.includes(c)) {
        let j = i, e = '';
        while (j < s.length && SUP.includes(s[j])) { e += SUP.indexOf(s[j]); j++; }
        out.push({ t: '^', v: Number(e) }); i = j; continue;
      }
      if (s.startsWith('de ', i)) { out.push({ t: 'de' }); i += 2; continue; }
      if ('+−×÷()/'.includes(c)) { out.push({ t: c }); i++; continue; }
      throw new Error(`caractère inattendu « ${c} » dans « ${text} »`);
    }
    return out;
  }
  function evaluate(text) {
    const tk = tokens(text);
    let p = 0;
    const peek = () => tk[p] || { t: 'end' };
    function atom() {
      const k = tk[p++];
      if (!k) throw new Error(`fin inattendue : ${text}`);
      let v;
      if (k.t === 'n') {
        v = k.v;
        if (peek().t === '/') {           // fraction n/d (éventuellement « de X »)
          p++;
          const d = tk[p++];
          if (!d || d.t !== 'n') throw new Error(`fraction illisible : ${text}`);
          v = { n: k.v, d: d.v };
          if (peek().t === 'de') { p++; const x = tk[p++]; v = (v.n * x.v) / v.d; if (x.t !== 'n') throw new Error(text); }
        }
      } else if (k.t === '(') {
        v = sum();
        if (tk[p++]?.t !== ')') throw new Error(`parenthèse : ${text}`);
      } else throw new Error(`jeton ${k.t} : ${text}`);
      while (peek().t === '^') v = Math.pow(typeof v === 'object' ? v.n / v.d : v, tk[p++].v);
      return v;
    }
    const num = (v) => (typeof v === 'object' ? v.n / v.d : v);
    function prod() {
      let v = atom();
      while (peek().t === '×' || peek().t === '÷') {
        const op = tk[p++].t, w = num(atom());
        v = op === '×' ? num(v) * w : num(v) / w;
      }
      return v;
    }
    function sum() {
      let v = prod();
      while (peek().t === '+' || peek().t === '−') {
        const op = tk[p++].t, w = num(prod());
        v = op === '+' ? num(v) + w : num(v) - w;
      }
      return v;
    }
    const v = num(sum());
    if (p !== tk.length) throw new Error(`reste illisible : ${text}`);
    return v;
  }

  // ── Encre : palette du jeu (nom → couleur d'encre affichée) ──
  const INKS = { rouge: '#ff4d4d', bleu: '#4c9dff', vert: '#2fd36b', jaune: '#ffd60a', violet: '#bf86ff',
    orange: '#ff9233', rose: '#ff7ac8', marron: '#c08a5a' };
  const rgb = (hex) => `rgb(${parseInt(hex.slice(1, 3), 16)}, ${parseInt(hex.slice(3, 5), 16)}, ${parseInt(hex.slice(5, 7), 16)})`;
  const INK_BY_RGB = Object.fromEntries(Object.entries(INKS).map(([n, h]) => [rgb(h), n]));
  const WARM = ['#ff8a5c', '#ffcf4a', '#ff6b8b'].map(rgb), COLD = ['#6fb6ff', '#5fe0a0', '#b49bff'].map(rgb);

  window.qaEvaluate = evaluate;

  window.qaRobot = function (game, opts) {
    const o = { mode: 'parfait', input: 'touch', rt: 280, ...opts };
    const Q = window.__qa = { acts: 0, wrongOnPurpose: 0, blocked: [], mismatch: [], truths: [], minLives: 3,
      level: 0, maxLevel: 0, typed: [], errors: [], queue: [] };
    const $ = (s) => document.querySelector(s);
    const stage = () => $('#brStage');
    const now = () => performance.now();
    const errNow = () => o.mode === 'errant' && Q.acts % 5 === 4;
    let seen = null, armed = true;

    // Toucher : la cible doit être visible et à l'écran (elementFromPoint), sinon c'est noté comme « bloqué ».
    function tap(el, label) {
      const r = el.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      const hit = document.elementFromPoint(x, y);
      if (!hit || !(el === hit || el.contains(hit))) { Q.blocked.push(`${label} (${Math.round(x)},${Math.round(y)})`); return false; }
      if (r.width < 44 || r.height < 44) Q.blocked.push(`${label} trop petit ${Math.round(r.width)}×${Math.round(r.height)}`);
      if (o.input === 'reel') { Q.queue.push(['tap', x, y]); return true; }   // Playwright touche vraiment l'écran
      const base = { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 7, pointerType: 'touch', isPrimary: true };
      hit.dispatchEvent(new PointerEvent('pointerdown', base));
      hit.dispatchEvent(new PointerEvent('pointerup', base));
      hit.dispatchEvent(new MouseEvent('click', base));
      return true;
    }
    const key = (k) => document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
    function hud() {
      const m = ($('.br-lvl')?.textContent || '').match(/Niv\. (\d+)/);
      if (m) { Q.level = +m[1]; Q.maxLevel = Math.max(Q.maxLevel, Q.level); }
      const lost = document.querySelectorAll('.br-lives .br-heart.lost').length;
      if ($('.br-lives')) Q.minLives = Math.min(Q.minLives, 3 - lost);
    }
    // Attend `rt` ms de « réflexion » après l'apparition d'une question.
    function ready(isReady) {
      if (!isReady) { seen = null; return false; }
      if (seen === null) { seen = now(); return false; }
      if (now() - seen < o.rt) return false;
      seen = null;
      return true;
    }
    function yesNo(yes, label) {
      Q.acts++;
      if (o.input === 'key') key(yes ? 'ArrowRight' : 'ArrowLeft');
      else tap($(`#brStage [data-answer="${yes ? 'yes' : 'no'}"]`), label);
    }
    function decide(right) { if (errNow()) { Q.wrongOnPurpose++; return !right; } return right; }

    const play = {
      encre() {
        if (!ready(stage().dataset.state === 'ready')) return;
        const top = $('[data-role="topWord"]').textContent;
        const ink = INK_BY_RGB[getComputedStyle($('[data-role="bottomWord"]')).color];
        if (!ink) Q.mismatch.push(`encre inconnue ${getComputedStyle($('[data-role="bottomWord"]')).color}`);
        const right = top === ink;
        Q.truths.push(right ? 1 : 0);
        yesNo(decide(right), 'encre');
      },
      bascule() {
        if (!ready(stage().dataset.state === 'ready')) return;
        const slot = [...document.querySelectorAll('.br-bascule-card')].find((s) => !s.hidden);
        const digit = +slot.querySelector('b').textContent, letter = slot.querySelector('i').textContent;
        const bg = slot.style.background ? getComputedStyle(slot).backgroundColor : '';
        const rule = slot.parentElement.dataset.rule;
        const vowel = 'AEIOU'.includes(letter);
        const right = rule === 'pair' ? digit % 2 === 0 : rule === 'voyelle' ? vowel : rule === 'consonne' ? !vowel
          : WARM.includes(bg) ? true : COLD.includes(bg) ? false : (Q.mismatch.push(`couleur ${bg}`), false);
        Q.truths.push(right ? 1 : 0);
        yesNo(decide(right), 'bascule');
      },
      courant() {
        const field = $('.br-courant-field'), leaf = $('.br-courant-leaf');
        if (!field || !leaf) return;
        const fresh = leaf !== Q.lastLeaf && !field.classList.contains('is-ok') && !field.classList.contains('is-ko');
        if (!fresh) { seen = null; return; }
        if (seen === null) {      // couleur lue dès l'apparition (elle s'efface aux niveaux hauts)
          Q.ruleSeen = leaf.querySelector('.br-courant-body').getAttribute('fill').toLowerCase() === '#3fb950' ? 'pointe' : 'bouge';
          if (Q.ruleSeen !== field.dataset.rule) Q.mismatch.push(`couleur ≠ règle (${field.dataset.rule})`);
        }
        if (!ready(true)) return;
        Q.lastLeaf = leaf;
        const dirs = ['droite', 'bas', 'gauche', 'haut'];
        let d = dirs.indexOf(Q.ruleSeen === 'pointe' ? field.dataset.point : field.dataset.move);
        Q.truths.push(d);
        if (errNow()) { Q.wrongOnPurpose++; d = (d + 2) % 4; }
        Q.acts++;
        if (o.input === 'key') { key(['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'][d]); return; }
        const r = field.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
        const hit = document.elementFromPoint(x, y);
        if (!hit || !field.contains(hit)) { Q.blocked.push('courant'); return; }
        const [dx, dy] = [[70, 0], [0, 70], [-70, 0], [0, -70]][d];
        if (o.input === 'reel') { Q.queue.push(['swipe', x, y, x + dx, y + dy]); return; }
        const ev = (t, ex, ey) => new PointerEvent(t, { bubbles: true, cancelable: true, clientX: ex, clientY: ey, pointerId: 7, pointerType: 'touch' });
        hit.dispatchEvent(ev('pointerdown', x, y));
        hit.dispatchEvent(ev('pointerup', x + dx, y + dy));
      },
      balance() {
        const L = $('[data-side="l"]'), R = $('[data-side="r"]'), btn = $('.br-balance-btn');
        if (!L) return;
        if (btn.disabled) { armed = true; seen = null; return; }
        if (!armed || !ready(true)) return;
        armed = false;
        let a, b;
        try { a = evaluate(L.textContent); b = evaluate(R.textContent); } catch (e) { Q.mismatch.push(String(e.message)); return; }
        let ans = Math.abs(a - b) < 1e-9 ? 0 : a > b ? 1 : -1;
        Q.truths.push(ans);
        Q.lastRound = `${L.textContent} | ${R.textContent} → ${ans}`;
        if (errNow()) { Q.wrongOnPurpose++; ans = ans === 1 ? -1 : 1; }
        Q.acts++;
        if (o.input === 'key') key({ 1: 'ArrowLeft', 0: 'ArrowDown', '-1': 'ArrowRight' }[ans]);
        else tap($(`.br-balance-btn[data-answer="${ans}"]`), 'balance');
      },
      gouttes() {
        Q.born = Q.born || new WeakMap();
        const y = (d) => new DOMMatrix(getComputedStyle(d).transform).m42;
        const drops = [...document.querySelectorAll('.br-gouttes-drop:not(.pop):not(.splash)')];
        drops.forEach((d) => { if (!Q.born.has(d)) Q.born.set(d, now()); });
        const ripe = drops.filter((d) => now() - Q.born.get(d) >= o.rt && !d.dataset.qaDone).sort((p, q) => y(q) - y(p));
        if (!ripe.length || $('.br-gouttes-pad.frozen')) return;
        const d = ripe[0];
        let v;
        try { v = evaluate(d.textContent); } catch (e) { Q.mismatch.push(String(e.message)); d.dataset.qaDone = '1'; return; }
        if (!Number.isInteger(v) || v < 0 || String(v).length > 6) Q.mismatch.push(`réponse impossible ${d.textContent} = ${v}`);
        Q.acts++;
        if (o.mode === 'errant' && Q.acts % 5 === 4) { Q.wrongOnPurpose++; d.dataset.qaDone = '1'; return; }  // on la laisse tomber
        Q.truths.push(v);
        d.dataset.qaDone = '1';
        const digits = String(v).split('');
        if (o.input === 'key') { digits.forEach(key); key('Enter'); }
        else { digits.forEach((c) => tap($(`.br-gouttes-key[data-key="${c}"]`), `touche ${c}`)); tap($('.br-gouttes-key[data-key="ok"]'), 'ok'); }
        Q.lastDrop = `${d.textContent} = ${v}`;
      },
      aiguillage() {
        const cv = $('canvas.br-aiguillage-canvas');
        if (!cv || !cv.brSnapshot) return;
        const s = cv.brSnapshot(), r = cv.getBoundingClientRect(), best = {};
        Q.snap = { stations: s.stations, tier: s.tier, level: s.level, hitRadius: s.hitRadius, minGap: s.minGap, rows: s.rows };
        Q.mis = Q.mis || new Set();
        for (const w of s.wagons) if (w.next >= 0 && (!best[w.next] || w.remaining < best[w.next].remaining)) best[w.next] = w;
        for (const k in best) {
          const w = best[k];
          if (o.mode === 'errant' && w.id % 5 === 0 && !Q.mis.has(w.id)) { Q.mis.add(w.id); Q.wrongOnPurpose++; }
          const want = Q.mis.has(w.id) ? 1 - w.want : w.want, sw = s.switches[k];
          if (sw.state === want) continue;
          Q.pend = Q.pend || {};
          if (now() - (Q.pend[k] || -1e9) < 120) continue;   // un toucher par aiguillage, pas une rafale
          Q.pend[k] = now();
          Q.acts++;
          const x = r.left + sw.x + 5, yy = r.top + sw.y - 5;
          const hit = document.elementFromPoint(x, yy);
          if (hit !== cv) { Q.blocked.push(`aiguillage ${k} (${Math.round(x)},${Math.round(yy)})`); continue; }
          if (o.input === 'reel') { Q.queue.push(['tap', x, yy]); continue; }
          cv.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, clientX: x, clientY: yy, pointerId: 7, pointerType: 'touch' }));
        }
      },
    };
    Q.timer = setInterval(() => {
      try {
        hud();
        if (o.mode === 'passif' || !stage() || document.querySelector('#brainRoot').dataset.screen !== 'play') return;
        if (play[game]) play[game]();
      } catch (e) { Q.errors.push(String(e && e.stack || e)); }
    }, 16);
  };
})();
