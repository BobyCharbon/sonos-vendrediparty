// 🎁 Zicou — la scène d'ouverture d'une récompense (avis du 5.11 : « comme un booster : on l'ouvre, on le gratte, puis on
// découvre son cadeau, plus ou moins d'animation selon la rareté »). Panneau position: fixed par-dessus tout (jamais de
// règle sur html/body, voir CLAUDE.md). Le SERVEUR a déjà tiré : la scène ne fait que dévoiler un résultat connu.
// Règles stores (CLAUDE.md, revue Apple 4.11) : chances visibles dans le paquet (et « i » pour le détail), bouton
// « Passer » toujours visible, aucune quasi-victoire (la rareté montrée est la vraie, dès le début de la révélation,
// elle ne change jamais), ni rouleaux, ni levier, ni son de jackpot, ni flash rapide ; les pièces glissent calmement
// vers le compteur. Animations en transform/opacity, un petit canvas (grattage, confettis du Légendaire) arrêté à la fin.
// prefers-reduced-motion : version courte, en fondu.
(function () {
  "use strict";
  const RARITY = { common: "Commun", rare: "Rare", epic: "Épique", legendary: "Légendaire", mythic: "Mythique" };
  // Durée de la révélation (ms) avant « Continuer », selon la rareté : plus c'est rare, plus le moment dure.
  const SHOW_MS = { common: 650, rare: 1100, epic: 1600, legendary: 2400, mythic: 2300 };
  const CALM_MS = 280, INTRO_MS = 650, HOLD_MS = 650, TEAR_PART = 0.55, DOUBLE_TAP_MS = 320, SCRATCH_DONE = 0.6;
  const COINS_FLYING = 5, COIN_STAGGER_MS = 140, COUNT_MS = 900, CONFETTI_MS = 2200, CONFETTI_N = 70;
  const ODDS_SHORT = { coins: "🪙 Pièces", object: "🍪 Objet", piece: "🧩 Morceau", rare_outfit: "Tenue rare", common: "Commun",
    rare: "Rare", epic: "Épique", legendary: "Légendaire", mythic: "Objet mystère" };
  const PARTS = { common: 10, rare: 16, epic: 22, legendary: 26, mythic: 0 };   // éclats à la couleur de la rareté
  const GLINTS = 10, SHREDS = 12, TILT_MAX = 14;
  const PACK_ICON = { chest: "🎁", bonus: "🎁", event: "🎟️", gift: "💝", shop: "🛍️", craft: "🔨" };

  const esc = (s) => (window.PetUI?.esc ? window.PetUI.esc(s) : String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`));
  const calm = () => { try { return matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };
  const buzz = (p) => { try { window.PetUI ? window.PetUI.buzz(p) : navigator.vibrate?.(p); } catch { /* pas de vibreur */ } };
  const cue = (k) => { try { window.PetUI ? window.PetUI.cue(k) : window.GameAudio?.cue?.(k); } catch { /* son refusé */ } };

  let current = null, chain = Promise.resolve();   // une scène à la fois : les suivantes attendent leur tour

  /**
   * Joue la scène. spec : { rarity, kind ("coins"…), amount, label, icon (HTML sûr, fait par l'appelant), title, pack
   * (chest|bonus|event|gift|shop|craft), mode (tear|scratch|auto), odds [{kind,label,text}], oddsNote, guaranteed, from }.
   * Renvoie une promesse { skipped } résolue à la fermeture (Mythique : juste après les craquelures, la suite est à
   * l'appelant). Sans DOM utilisable : résolue tout de suite.
   */
  function play(spec) {
    if (!document.body) return Promise.resolve({ skipped: true });
    const turn = chain.then(() => new Promise((resolve) => {
      try { current = scene({ ...spec }, resolve); } catch { current = null; resolve({ skipped: true }); }   // la récompense reste affichée dessous
    }));
    chain = turn.catch(() => undefined);
    return turn;
  }

  function oddsHtml(spec) {
    const odds = Array.isArray(spec.odds) ? spec.odds : [];
    if (!odds.length) return { chips: "", full: spec.oddsNote ? `<p>${esc(spec.oddsNote)}</p>` : "" };
    const chips = odds.map((o) => `<li><span>${esc(ODDS_SHORT[o.kind] || o.label || o.kind)}</span> <b>${esc(o.text || "")}</b></li>`).join("");
    const rows = odds.map((o) => `<li><span>${esc(o.label || ODDS_SHORT[o.kind] || o.kind)}</span><b>${esc(o.text || "")}</b></li>`).join("");
    return { chips, full: `<ul>${rows}</ul>${spec.oddsNote ? `<p>${esc(spec.oddsNote)}</p>` : ""}` };
  }

  function cardHtml(spec) {
    const r = spec.rarity;
    if (r === "mythic") {
      return `<div class="zr-front zr-myth-front"><span class="zr-silhouette" aria-hidden="true">???</span>
        <svg class="zr-cracks" viewBox="0 0 100 140" aria-hidden="true"><path d="M50 0 L46 30 L58 52 L44 78 L54 104 L48 140"/>
        <path d="M46 30 L20 44 L8 70"/><path d="M58 52 L84 60 L96 88"/><path d="M44 78 L22 98"/><path d="M54 104 L80 122"/></svg>
        <b class="zr-name">Objet mystère</b><span class="pc-rar pc-mythic zr-tag">Mythique</span></div>`;
    }
    const tag = r ? `<span class="pc-rar pc-${esc(r)} zr-tag">${esc(RARITY[r] || r)}</span>` : "";
    const sub = spec.kind === "coins" ? `<small>Rangées dans ta tirelire</small>` : spec.sub ? `<small>${esc(spec.sub)}</small>` : "";
    return `<div class="zr-front"><i class="zr-sheen" aria-hidden="true"></i><div class="zr-icon">${spec.icon || esc(spec.emoji || "🎁")}</div>
      <b class="zr-name">${esc(spec.label || "")}</b>${tag}${sub}</div>`;
  }

  function packHtml(spec) {
    if (spec.mode === "scratch") {
      return `<div class="zr-scratch"><div class="zr-card zr-flat">${cardHtml(spec)}</div>
        <canvas class="zr-scratch-c" aria-hidden="true"></canvas></div>`;
    }
    const icon = PACK_ICON[spec.pack] || "🎁";
    return `<div class="zr-card"><div class="zr-flip"><div class="zr-back" aria-hidden="true"><span>Z</span></div>${cardHtml(spec)}</div></div>
      ${spec.mode === "auto" ? "" : `<div class="zr-pack" aria-hidden="true"><div class="zr-pack-top"><i></i></div>
        <div class="zr-pack-body"><i class="zr-shine"></i><span class="zr-pack-i">${icon}</span><b>${esc(spec.title || "Zicou")}</b>
        <span class="zr-brand">ZICOU · BOOSTER</span>${spec.guaranteed ? "<small>🛡️ Épique ou Légendaire garanti</small>" : ""}</div>
        <div class="zr-seam"></div><div class="zr-tear"></div><div class="zr-hold"></div>
        <div class="zr-shreds">${shreds()}</div></div>`}`;
  }

  function shreds() {
    return Array.from({ length: SHREDS }, (_, i) => `<i style="--x:${Math.round((i + 0.5) * (100 / SHREDS))}%;--a:${(i % 2 ? 1 : -1) * (20 + (i * 37) % 70)}deg;--dy:${-60 - (i * 23) % 70}px;--dx:${((i * 41) % 60) - 30}px"></i>`).join("");
  }
  function glints() {
    return Array.from({ length: GLINTS }, (_, i) => `<i style="--x:${(i * 53) % 100}%;--t:${(i * 470) % 4000}ms;--s:${3 + (i % 3)}px"></i>`).join("");
  }
  function sparks(n, cls) {
    return Array.from({ length: n }, (_, i) => `<i class="${cls}" style="--a:${Math.round((360 / n) * i + (i % 3) * 7)}deg;--d:${70 + (i % 4) * 26}px;--t:${(i % 5) * 40}ms"></i>`).join("");
  }

  function scene(spec, resolve) {
    const isCalm = calm();
    const r = spec.rarity || "";
    const mode = spec.mode || "tear";
    spec.mode = mode;
    const odds = oddsHtml(spec);
    const opener = document.activeElement;
    const el = document.createElement("div");
    el.className = `zr${isCalm ? " zr-calm" : ""}`;
    el.dataset.r = r || "none";
    el.dataset.kind = spec.kind || "";
    el.dataset.mode = mode;
    el.dataset.phase = "intro";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.setAttribute("aria-label", spec.title || "Ouverture");
    const hint = mode === "scratch" ? "Gratte la carte avec le doigt" : "Glisse le doigt en travers pour l'ouvrir, ou maintiens";
    el.innerHTML = `<div class="zr-dim"></div>
      <div class="zr-fx" aria-hidden="true"><div class="zr-rays"></div><div class="zr-halo"></div>
        <div class="zr-parts">${sparks(PARTS[r] ?? 8, "zr-part")}</div><div class="zr-glints">${glints()}</div>
        ${r === "legendary" && !isCalm ? '<canvas class="zr-confetti"></canvas>' : ""}</div>
      <div class="zr-top">${odds.chips || odds.full ? '<button type="button" class="zr-info" aria-expanded="false" aria-label="Chances">i</button>' : "<span></span>"}
        <span class="zr-title">${esc(spec.title || "")}</span><button type="button" class="zr-skip">Passer</button></div>
      ${spec.kind === "coins" ? `<div class="zr-coins" aria-hidden="true">🪙 <b>+0</b></div>` : ""}
      ${spec.from ? `<p class="zr-from">${esc(spec.from)}</p>` : ""}
      <div class="zr-stage">${packHtml(spec)}</div>
      <div class="zr-foot"><p class="zr-hint">${hint}</p>
        <button type="button" class="zr-open">Révéler</button>
        ${odds.chips ? `<ul class="zr-odds" aria-label="Chances">${odds.chips}</ul>` : ""}
        <button type="button" class="zr-done">Continuer</button></div>
      <div class="zr-full" hidden><h3>Chances</h3>${odds.full}<p>Le tirage est fait par Party avant l'ouverture : l'animation ne fait que le dévoiler.
        Rien ne s'achète avec de l'argent.</p><button type="button" class="zr-full-x">Fermer</button></div>
      <p class="zr-sr" aria-live="polite"></p>`;
    document.body.append(el);

    const timers = new Set();
    const later = (fn, ms) => { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; };
    let raf = 0, done = false, opened = false;
    const $ = (s) => el.querySelector(s);
    const setPhase = (p) => { el.dataset.phase = p; };

    later(() => { if (!opened) { setPhase("ready"); $(".zr-open")?.focus({ preventScroll: true }); } }, isCalm ? 60 : INTRO_MS);
    cue("card");

    // ── Ouverture ──
    function open() {
      if (opened) return;
      opened = true;
      setPhase("open");
      buzz(20);
      cue("turn");
      later(show, isCalm ? 60 : mode === "scratch" ? 120 : 420);
    }
    function show() {
      setPhase("show");
      const say = $(".zr-sr");
      if (say) say.textContent = r === "mythic" ? "Objet mystère : Mythique !" : `${RARITY[r] ? `${RARITY[r]} : ` : ""}${spec.label || ""}`;
      if (r === "legendary" || r === "epic" || r === "mythic") cue("win"); else cue("reveal");
      if (!isCalm) effects();
      if (spec.kind === "coins") coins();
      const ms = isCalm ? CALM_MS : SHOW_MS[r] || SHOW_MS.common;
      later(r === "mythic" ? () => finish(false) : toDone, ms);
    }
    function effects() {
      if (r === "epic") buzz(40);
      if (r === "legendary") { buzz([40, 80, 60, 80, 90]); confetti(); }
      if (r === "mythic") buzz([20, 50, 30, 50, 60]);
    }
    function toDone() {
      if (done) return;
      setPhase("done");
      $(".zr-done")?.focus({ preventScroll: true });
    }
    function skip() {
      if (done) return;
      timers.forEach(clearTimeout);
      timers.clear();
      opened = true;
      el.classList.add("zr-skipped");
      if (r === "mythic") return finish(true);
      const say = $(".zr-sr");
      if (say) say.textContent = `${RARITY[r] ? `${RARITY[r]} : ` : ""}${spec.label || ""}`;
      const count = $(".zr-coins b");
      if (count) count.textContent = `+${spec.amount || 0}`;
      stopCanvas();
      toDone();
    }
    function finish(skipped) {
      if (done) return;
      done = true;
      timers.forEach(clearTimeout);
      timers.clear();
      stopCanvas();
      if (current?.el === el) current = null;
      el.classList.add("zr-out");
      setTimeout(() => el.remove(), isCalm ? 0 : 220);
      try { if (opener?.isConnected) opener.focus({ preventScroll: true }); } catch { /* bouton disparu */ }
      resolve({ skipped });
    }
    function stopCanvas() { if (raf) cancelAnimationFrame(raf); raf = 0; }

    // ── Pièces : quelques-unes glissent calmement vers le compteur, qui monte ──
    function coins() {
      const counter = $(".zr-coins"), from = $(".zr-card"), n = Math.max(0, Number(spec.amount) || 0);
      const out = counter?.querySelector("b");
      if (!counter || !out) return;
      if (isCalm || !from) { out.textContent = `+${n}`; return; }
      const a = from.getBoundingClientRect(), b = counter.getBoundingClientRect();
      for (let i = 0; i < COINS_FLYING; i += 1) {
        const c = document.createElement("i");
        c.className = "zr-coin";
        c.textContent = "🪙";
        const x0 = a.left + a.width / 2 + (i - 2) * 14, y0 = a.top + a.height / 2;
        c.style.cssText = `left:${x0}px;top:${y0}px;--dx:${b.left + 18 - x0}px;--dy:${b.top + 6 - y0}px;animation-delay:${i * COIN_STAGGER_MS}ms`;
        el.append(c);
      }
      const t0 = performance.now();
      const tick = (t) => {
        const k = Math.min(1, (t - t0) / COUNT_MS);
        out.textContent = `+${Math.round(n * k)}`;
        if (k < 1 && !done) requestAnimationFrame(tick);
      };
      later(() => requestAnimationFrame(tick), COIN_STAGGER_MS * 2);
    }

    // ── Confettis (Légendaire seulement) : petit canvas, arrêté après CONFETTI_MS ──
    function confetti() {
      const cv = $(".zr-confetti");
      const ctx = cv?.getContext?.("2d");
      if (!ctx) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1), w = innerWidth, h = innerHeight;
      cv.width = w * dpr; cv.height = h * dpr;
      ctx.scale(dpr, dpr);
      const colors = ["#ffbf3c", "#ffe08a", "#fff6d8", "#a565ff", "#5ee7ff"];
      const bits = Array.from({ length: CONFETTI_N }, (_, i) => ({ x: w / 2, y: h * 0.42, vx: (Math.random() - 0.5) * 9,
        vy: -5 - Math.random() * 8, s: 6 + Math.random() * 5, a: Math.random() * 6, va: 0.04 + Math.random() * 0.08, c: colors[i % colors.length] }));
      const t0 = performance.now();
      const frame = (t) => {
        const age = t - t0;
        ctx.clearRect(0, 0, w, h);
        ctx.globalAlpha = Math.max(0, 1 - Math.max(0, age - CONFETTI_MS * 0.6) / (CONFETTI_MS * 0.4));
        for (const p of bits) {
          p.vy += 0.18; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.a += p.va;
          ctx.fillStyle = p.c;
          ctx.fillRect(p.x, p.y, p.s, p.s * Math.abs(Math.cos(p.a)) + 1);
        }
        raf = age < CONFETTI_MS && !done ? requestAnimationFrame(frame) : 0;
        if (!raf) ctx.clearRect(0, 0, w, h);
      };
      raf = requestAnimationFrame(frame);
    }

    // ── Déchirer (glisser en travers) ou maintenir ──
    function bindTear() {
      const pack = $(".zr-pack");
      if (!pack) return;
      let start = null, holdId = 0;
      const cancelHold = () => { clearTimeout(holdId); timers.delete(holdId); holdId = 0; pack.classList.remove("zr-holding"); };
      pack.addEventListener("pointerdown", (ev) => {
        if (opened) return;
        const box = pack.getBoundingClientRect();
        start = { x: ev.clientX, y: ev.clientY, w: box.width, left: box.left };
        pack.style.setProperty("--ox", `${Math.round(((ev.clientX - box.left) / box.width) * 100)}%`);
        try { pack.setPointerCapture(ev.pointerId); } catch { /* vieux navigateur */ }
        pack.classList.add("zr-holding");
        holdId = later(() => { holdId = 0; open(); }, HOLD_MS);
      });
      pack.addEventListener("pointermove", (ev) => {
        if (!start || opened) return;
        const dx = Math.abs(ev.clientX - start.x);
        if (dx > 12) cancelHold();
        const k = Math.min(1, dx / (start.w * TEAR_PART));
        const tilt = Math.max(-1, Math.min(1, (ev.clientX - start.left - start.w / 2) / (start.w / 2))) * TILT_MAX;
        pack.style.setProperty("--tear", k.toFixed(3));
        pack.style.setProperty("--tilt", `${tilt.toFixed(1)}deg`);
        if (k >= 1) { start = null; open(); }
      });
      const up = () => {
        cancelHold(); start = null;
        if (!opened) { pack.style.setProperty("--tear", "0"); pack.style.setProperty("--tilt", "0deg"); }
      };
      pack.addEventListener("pointerup", up);
      pack.addEventListener("pointercancel", up);
    }

    // ── Gratter : canvas au doigt ; ~60 % gratté (grille grossière, sans lire les pixels) = révélé ──
    function bindScratch() {
      const cv = $(".zr-scratch-c");
      const ctx = cv?.getContext?.("2d");
      if (!ctx) return;
      const box = { width: cv.offsetWidth || 240, height: cv.offsetHeight || 320 };   // sans la mise à l'échelle de l'entrée
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.max(1, box.width * dpr); cv.height = Math.max(1, box.height * dpr);
      ctx.scale(dpr, dpr);
      const g = ctx.createLinearGradient(0, 0, box.width, box.height);
      g.addColorStop(0, "#c9c2ea"); g.addColorStop(0.5, "#8f86b8"); g.addColorStop(1, "#c9c2ea");
      ctx.fillStyle = g; ctx.fillRect(0, 0, box.width, box.height);
      ctx.fillStyle = "rgba(255, 255, 255, .55)";   // petites étoiles sur la couche à gratter
      for (let i = 0; i < 28; i += 1) ctx.fillRect((i * 67) % box.width, (i * 113) % box.height, 2, 2);
      ctx.fillStyle = "#3a2f66"; ctx.font = "800 15px system-ui, sans-serif"; ctx.textAlign = "center";
      ctx.fillText("Gratte ici ✨", box.width / 2, box.height / 2);
      ctx.globalCompositeOperation = "destination-out";
      ctx.lineWidth = 34; ctx.lineCap = "round"; ctx.lineJoin = "round";
      const COLS = 12, ROWS = 16, cells = new Set();
      let last = null;
      const mark = (x, y) => {
        for (let dx = -1; dx <= 1; dx += 1) for (let dy = -1; dy <= 1; dy += 1) {
          const cx = Math.floor(((x / box.width) * COLS) + dx * 0.6), cy = Math.floor(((y / box.height) * ROWS) + dy * 0.6);
          if (cx >= 0 && cy >= 0 && cx < COLS && cy < ROWS) cells.add(cy * COLS + cx);
        }
      };
      const at = (ev) => {
        const b = cv.getBoundingClientRect();
        return { x: ((ev.clientX - b.left) / b.width) * box.width, y: ((ev.clientY - b.top) / b.height) * box.height };
      };
      cv.addEventListener("pointerdown", (ev) => {
        if (opened) return;
        try { cv.setPointerCapture(ev.pointerId); } catch { /* vieux navigateur */ }
        last = at(ev);
        setPhase("ready");
      });
      cv.addEventListener("pointermove", (ev) => {
        if (!last || opened) return;
        const p = at(ev);
        ctx.beginPath(); ctx.moveTo(last.x, last.y); ctx.lineTo(p.x, p.y); ctx.stroke();
        mark(p.x, p.y);
        last = p;
        if (cells.size / (COLS * ROWS) >= SCRATCH_DONE) { cv.classList.add("zr-cleared"); open(); }
      });
      const up = () => { last = null; };
      cv.addEventListener("pointerup", up);
      cv.addEventListener("pointercancel", up);
    }

    // ── Touchers communs : Passer, double toucher, « i », Révéler, Continuer, Échap ──
    // Double toucher = passer (un glissé ou un grattage n'est pas un toucher). Le clic qui suit ne referme pas aussitôt.
    let lastTap = 0, tapAt = null, downAt = null, skippedAt = 0, dragged = false;
    el.addEventListener("pointerdown", (ev) => { downAt = { x: ev.clientX, y: ev.clientY }; });
    el.addEventListener("pointerup", (ev) => {
      dragged = Boolean(downAt && Math.hypot(ev.clientX - downAt.x, ev.clientY - downAt.y) > 10);   // fin d'un glissé ou d'un grattage
      if (ev.target.closest("button, .zr-full") || el.dataset.phase === "done") return;
      if (dragged) { lastTap = 0; return; }
      const now = performance.now();
      const near = tapAt && Math.hypot(ev.clientX - tapAt.x, ev.clientY - tapAt.y) < 30;
      if (now - lastTap < DOUBLE_TAP_MS && near) { lastTap = 0; skippedAt = now; return skip(); }
      lastTap = now; tapAt = { x: ev.clientX, y: ev.clientY };
    });
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest("button");
      if (!b) {
        const fresh = performance.now() - skippedAt < 450 || dragged;
        if (el.dataset.phase === "done" && !fresh && !ev.target.closest(".zr-full, .zr-card")) finish(false);
        return;
      }
      if (b.classList.contains("zr-skip")) return el.dataset.phase === "done" ? finish(true) : skip();
      if (b.classList.contains("zr-open")) return mode === "scratch" ? ($(".zr-scratch-c")?.classList.add("zr-cleared"), open()) : open();
      if (b.classList.contains("zr-done")) return finish(false);
      if (b.classList.contains("zr-info") || b.classList.contains("zr-full-x")) {
        const full = $(".zr-full"), info = $(".zr-info");
        full.hidden = !full.hidden;
        info?.setAttribute("aria-expanded", String(!full.hidden));
        if (!full.hidden) full.querySelector("button")?.focus({ preventScroll: true });
      }
    });
    el.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      ev.preventDefault();
      el.dataset.phase === "done" ? finish(false) : skip();
    });

    if (mode === "tear") bindTear();
    if (mode === "scratch") bindScratch();
    if (mode === "auto") later(open, isCalm ? 60 : INTRO_MS + 150);
    return { el, finish };
  }

  /** Une ligne de nouvelles « X lui a offert … » (cadeau ou festin offert par un ami) → la scène du paquet cadeau. */
  async function gifts(news) {
    const list = (news || []).filter((n) => n.kind === "gift");
    for (const n of list) {
      const m = /^(\S+)\s+(.*)$/u.exec(String(n.text || ""));
      await play({ kind: "gift", pack: "gift", mode: "tear", title: "Un cadeau d'ami", emoji: m ? m[1] : "🎁", label: m ? m[2] : n.text,
        oddsNote: "Un cadeau d'ami n'est pas un tirage : c'est exactement ce que ton ami a offert." });
    }
  }

  window.PetReveal = Object.freeze({ play, gifts, rarities: RARITY });
})();
