// ✨ Zicou en mouvement (retour de l'admin, 5.11.2026 : « fade, pas d'animation »). Couche d'animation seule : elle ne
// décide rien, elle regarde ce que pet.js affiche (écran, Zicou, jauges, pièces, série, missions) et anime ce qui a
// CHANGÉ depuis la dernière fois. Tout passe par transform / opacity (60 fps sur un vieil iPhone, jamais de propriété de
// mise en page), chaque classe d'animation est retirée à la fin, rien ne bloque un toucher (pointer-events: none).
// « Réduire les animations » : aucune particule, aucun rebond ; seul un fondu court d'écran (pet/motion.css).
// Exigences Apple (revue du 5.11) : animations courtes, aucun flash rapide, une seule pièce qui glisse calmement vers le
// compteur (rien qui rappelle un casino), haptique par navigator.vibrate (l'app la rend en retour haptique système, qui
// suit le réglage de l'iPhone), jamais d'animation de récompense pour noter, partager ou boire.
// Branchement (pet.js) : PetMotion.before(root) juste avant de remplacer l'écran, puis la fonction rendue est appelée
// avec le nom du nouvel écran ; PetMotion.act(root, action) après un soin ; PetMotion.hatch(root) à l'éclosion.
(function () {
  "use strict";
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const buzz = (p) => { try { if (typeof haptic === "function") haptic(p); } catch { /* pas de vibreur */ } };
  const current = () => window.PetUI?.current?.() || null;
  const SUB = ["outfits", "friends", "visit", "play", "result", "rename", "streak", "treasures", "odds", "reveal", "coll", "report",
    "level", "room", "pot", "star"];
  const ENTER_MS = 650, PULSE_MS = 1100, FX_MS = 1500, COUNT_MS = 700, GLIDE_MS = 700, CASCADE_MAX = 12;
  const IDLE_MIN_MS = 6000, IDLE_SPREAD_MS = 4000, LOOK_PX = 7, LOOK_RESET_MS = 1600;
  const IDLES = { happy: ["hop", "sway", "look"], party: ["hop", "spin"], hungry: ["look", "sway"], tired: ["yawn"], sad: ["look", "sigh"],
    sick: ["sigh"], sleep: [], egg: ["rock"], ghost: [] };

  // ── Petits outils ──
  const timers = new Set();
  function later(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; }
  function clear() { for (const id of timers) clearTimeout(id); timers.clear(); }
  /** Ajoute une classe d'animation, la retire à la fin (relance possible tout de suite). */
  function pulse(el, cls, ms = PULSE_MS) {
    if (!el || calm()) return;
    el.classList.remove(cls);
    void el.offsetWidth;   // relance l'animation si la classe était déjà là
    el.classList.add(cls);
    later(() => el.classList.remove(cls), ms);
  }
  const rand = (a, b) => a + Math.random() * (b - a);

  /** Particules légères (emoji ou pastilles) autour d'un élément ; aria-hidden, sans toucher. */
  const FX = {
    feed: { n: 9, kind: "fall", items: ["", "", "🍕", ""], cls: "pt-m-crumb" },
    treat: { n: 7, kind: "fall", items: ["", "🍪", ""], cls: "pt-m-crumb" },
    play: { n: 6, kind: "rise", items: ["♪", "♫"], cls: "pt-m-note" },
    cuddle: { n: 6, kind: "rise", items: ["💜", "💗", "💖"], cls: "" },
    heal: { n: 9, kind: "rise", items: [""], cls: "pt-m-bubble" },
    sleep: { n: 3, kind: "drift", items: ["z", "Z", "z"], cls: "pt-m-zz" },
    tuck: { n: 4, kind: "drift", items: ["🌙", "⭐", "z"], cls: "pt-m-zz" },
    wake: { n: 6, kind: "ray", items: [""], cls: "pt-m-ray" },
    outfit: { n: 6, kind: "ray", items: [""], cls: "pt-m-star" },
    equip: { n: 6, kind: "ray", items: [""], cls: "pt-m-star" },
    born: { n: 10, kind: "ray", items: ["", "", "★"], cls: "pt-m-shell" },
    boop: { n: 1, kind: "rise", items: ["💜"], cls: "" },
    giggle: { n: 2, kind: "rise", items: ["♪", "✨"], cls: "pt-m-note" },
    level: { n: 6, kind: "ray", items: [""], cls: "pt-m-star" },
    evolve: { n: 10, kind: "ray", items: [""], cls: "pt-m-star" },
    // Petites surprises au repos (une ou deux, jamais de pluie) : selon l'humeur.
    "amb-happy": { n: 2, kind: "drift", items: ["♪", "♫"], cls: "pt-m-note" },
    "amb-party": { n: 3, kind: "ray", items: [""], cls: "pt-m-star" },
    "amb-hungry": { n: 1, kind: "drift", items: ["🍕"], cls: "pt-m-small" },
    "amb-sad": { n: 1, kind: "drift", items: ["💭"], cls: "pt-m-small" },
    mission: { n: 8, kind: "confetti", items: [""], cls: "pt-m-confetti" },
  };
  function particles(host, name) {
    const spec = FX[name];
    if (!host || !spec || calm()) return;
    const box = document.createElement("span");
    box.className = `pt-m-fx pt-m-fx-${spec.kind}`;
    box.setAttribute("aria-hidden", "true");
    for (let i = 0; i < spec.n; i += 1) {
      const p = document.createElement("span");
      p.className = `pt-m-p ${spec.cls}`.trim();
      p.textContent = spec.items[i % spec.items.length];
      const angle = (i / spec.n) * Math.PI * 2 + rand(-0.3, 0.3);
      const dist = rand(38, 70);
      const vec = {
        rise: [rand(-60, 60), rand(-120, -70)], fall: [rand(-70, 70), rand(40, 80)], drift: [18 + i * 14, -50 - i * 18],
        ray: [Math.cos(angle) * dist, Math.sin(angle) * dist], confetti: [rand(-60, 60), rand(-60, -20)],
      }[spec.kind];
      p.style.setProperty("--dx", `${vec[0].toFixed(0)}px`);
      p.style.setProperty("--dy", `${vec[1].toFixed(0)}px`);
      p.style.setProperty("--rot", `${rand(-40, 40).toFixed(0)}deg`);
      const spread = { rise: [34, 18], fall: [10, 4], drift: [0, 0], ray: [6, 6], confetti: [24, 6] }[spec.kind];   // départ autour du corps
      p.style.setProperty("--sx", `${rand(-spread[0], spread[0]).toFixed(0)}px`);
      p.style.setProperty("--sy", `${rand(-spread[1], spread[1]).toFixed(0)}px`);
      p.style.setProperty("--delay", `${(spec.kind === "drift" ? i * 220 : i * 45)}ms`);
      if (spec.kind === "confetti") p.style.setProperty("--c", ["#5ee7ff", "#b49bff", "#ff8cc0", "#ffd36b"][i % 4]);
      box.append(p);
    }
    host.append(box);
    later(() => box.remove(), FX_MS + 900);
  }

  // ── Mémoire : ce qui était affiché la dernière fois (pour animer seulement ce qui change) ──
  let last = null;           // { gen, stage, emotion, gauges, coins, streak, level, missions, acc, dye, room }
  let lastScreen = "", lastKey = "";
  function snapshot(p) {
    if (!p) return null;
    return {
      gen: p.gen ?? p.name, stage: p.stage, emotion: p.emotion, gauges: { ...(p.gauges || {}) },
      coins: p.daily?.coins ?? p.coll?.coins ?? null, streak: p.daily?.streak?.count ?? p.streak ?? null,
      level: p.xp?.level ?? null, missions: (p.daily?.missions || []).map((m) => m.have >= m.need),
      acc: JSON.stringify(p.coll?.acc || p.acc || {}), dye: JSON.stringify(p.coll?.dye || p.dye || {}), outfit: p.outfit || "",
      room: typeof p.coll?.room === "number" ? p.coll.room : p.coll?.room?.level ?? null,
    };
  }

  // ── Jauges (et toute barre role=meter) : la barre part de l'ancienne valeur ──
  function meterValues(root) {
    const out = {};
    root.querySelectorAll('[role="meter"]').forEach((m) => {
      const max = Number(m.getAttribute("aria-valuemax")) || 100;
      out[m.getAttribute("aria-label")] = Number(m.getAttribute("aria-valuenow")) / max;
    });
    return out;
  }
  function fillMeter(m, from, to) {
    const bar = m.querySelector("i");
    if (!bar || calm() || !(to > 0) || Math.abs(from - to) < 0.005) return;
    bar.style.setProperty("--from", String(Math.max(0, Math.min(from / to, 1 / to))));
    pulse(bar, "pt-m-fill", 950);
    const gauge = m.closest(".pt-gauge");
    if (!gauge) return;
    pulse(gauge, to > from ? "pt-m-up" : "pt-m-down", 950);
    const delta = Math.round((to - from) * 100);
    if (delta > 0) {
      const tag = document.createElement("span");
      tag.className = "pt-m-delta";
      tag.setAttribute("aria-hidden", "true");
      tag.textContent = `+${delta}`;
      gauge.append(tag);
      later(() => tag.remove(), 1300);
    }
  }

  // ── Pièces : le compteur défile, une seule pièce glisse calmement vers lui ──
  function coinDisplays(root) { return [...root.querySelectorAll('.pt-chip[data-pt="treasures"], .pc-wallet > span:first-child')]; }
  function countUp(el, from, to) {
    const text = el.textContent, label = el.getAttribute("aria-label");
    if (!text.includes(String(to)) || calm()) return;
    const start = performance.now();
    const step = (t) => {
      if (!el.isConnected) return;
      const k = Math.min(1, (t - start) / COUNT_MS), ease = 1 - (1 - k) ** 3;
      el.textContent = text.replace(String(to), String(Math.round(from + (to - from) * ease)));
      if (k < 1) requestAnimationFrame(step);
      else { el.textContent = text; if (label) el.setAttribute("aria-label", label); }
    };
    requestAnimationFrame(step);
  }
  function glideCoin(root, target) {
    if (calm() || !target) return;
    const from = root.querySelector(".pt-art")?.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    if (!from || !to.width) return;
    const coin = document.createElement("span");
    coin.className = "pt-m-coin";
    coin.setAttribute("aria-hidden", "true");
    coin.textContent = "🪙";
    const x0 = from.left + from.width / 2, y0 = from.top + from.height * 0.45;
    coin.style.left = `${x0}px`;
    coin.style.top = `${y0}px`;
    coin.style.setProperty("--tx", `${(to.left + to.width * 0.3 - x0).toFixed(0)}px`);
    coin.style.setProperty("--ty", `${(to.top + to.height / 2 - y0).toFixed(0)}px`);
    document.body.append(coin);   // position fixe, hors du panneau (jamais rognée ni décalée par un parent transformé)
    // Minuteur à part : un changement d'écran ne doit jamais laisser une pièce orpheline sur la page.
    setTimeout(() => { coin.remove(); if (target.isConnected) pulse(target, "pt-m-coin-in", 600); }, GLIDE_MS);
  }

  // ── Changements d'état de Zicou ──
  function changes(root, screen, prev, now) {
    const art = root.querySelector(".pt-stage .pt-art, .pt-hero .pt-art, .pc-wear-hero .pt-art, .pt-room .pt-art");
    if (!prev || !now || prev.gen !== now.gen) return;
    if (prev.stage === "egg" && now.stage !== "egg" && now.stage !== "dead") { pulse(art, "pt-m-born", 1300); particles(art, "born"); buzz([30, 60, 30]); }
    else if (prev.stage !== now.stage && now.stage === "dead") pulse(art, "pt-m-farewell", 2400);
    else if (prev.stage !== now.stage) { pulse(art, "pt-m-evolve", 1800); particles(art, "evolve"); buzz([30, 60, 30]); }
    else if (prev.emotion !== now.emotion) pulse(art, "pt-m-mood", 1200);
    if (prev.acc !== now.acc || prev.outfit !== now.outfit) { pulse(art, "pt-m-equip", 700); particles(art, "equip"); }
    if (prev.dye !== now.dye) { sweep(art); }
    if (screen === "home") {
      GAUGE_KEYS.forEach(([k, label]) => {
        const m = root.querySelector(`.pt-gauges [role="meter"][aria-label="${label}"]`);
        if (m && prev.gauges[k] != null && now.gauges[k] != null) fillMeter(m, prev.gauges[k] / 100, now.gauges[k] / 100);
      });
      if (now.streak > (prev.streak ?? now.streak)) pulse(root.querySelector('.pt-chip[data-pt="streak"]'), "pt-m-flame", 1300);
      if (now.level > (prev.level ?? now.level)) {
        const chip = root.querySelector('[data-pt="eco-level"]');
        pulse(chip, "pt-m-level", 1300);
        particles(chip, "level");
      }
      now.missions.forEach((done, i) => {
        if (!done || prev.missions[i] !== false) return;
        const li = root.querySelectorAll(".pt-missions li")[i];
        pulse(li, "pt-m-done", 1100);
        particles(li, "mission");
      });
    }
    if (now.room != null && prev.room != null && now.room > prev.room) pulse(root.querySelector(".pt-room"), "pt-m-room", 1400);
  }
  const GAUGE_KEYS = [["food", "Ventre"], ["joy", "Humeur"], ["energy", "Énergie"], ["care", "Forme"]];
  function sweep(art) {
    if (!art || calm()) return;
    const s = document.createElement("span");
    s.className = "pt-m-sweep";
    s.setAttribute("aria-hidden", "true");
    art.append(s);
    later(() => s.remove(), 1000);
  }

  const ENTER_CLASSES = ["pt-m-enter-open", "pt-m-enter-deeper", "pt-m-enter-back", "pt-m-enter-tab", "pt-m-fade"];
  let enterTimer = 0;
  // ── Entrée d'un écran : ouverture, page plus profonde, retour, onglet interne ──
  function enter(root, screen) {
    const key = `${screen}:${root.querySelector(".pc-tab.on")?.dataset.t || ""}`;
    let kind = "same";
    if (!lastScreen || lastScreen === "loading" || lastScreen === "error" || lastScreen === "login") kind = "open";
    else if (key === lastKey) kind = "same";
    else if (lastScreen === screen) kind = "tab";
    else if (SUB.includes(screen) && !SUB.includes(lastScreen)) kind = "deeper";
    else if (!SUB.includes(screen) && SUB.includes(lastScreen)) kind = "back";
    else kind = "deeper";
    lastScreen = screen;
    lastKey = key;
    if (screen === "loading" || kind === "same") return;
    root.querySelectorAll(".pc-grid, .pc-list, .pt-tiles, .pt-friends, .pt-gauges, .pt-acts, .pt-more, .pt-miles, .pt-album").forEach((list) => {
      [...list.children].slice(0, CASCADE_MAX).forEach((c, i) => c.style.setProperty("--i", String(i)));
    });
    // Le panneau reste d'un écran à l'autre : ses classes d'entrée ont leur propre minuteur (jamais annulé par clear()).
    root.classList.remove(...ENTER_CLASSES);
    void root.offsetWidth;
    const cls = calm() ? "pt-m-fade" : `pt-m-enter-${kind}`;
    root.classList.add(cls);
    clearTimeout(enterTimer);
    enterTimer = setTimeout(() => root.classList.remove(cls), calm() ? 260 : ENTER_MS + CASCADE_MAX * 35);
    if (calm()) return;
    if (kind === "open") pulse(root.querySelector(".pt-stage .pt-art, .pt-hero .pt-art"), "pt-m-hello", 1000);
  }

  // ── Zicou au repos : petites idles selon l'humeur, regard qui suit le doigt ──
  function idleLoop(root) {
    if (calm()) return;
    later(() => {
      const art = root.querySelector('.pt-stage .pt-art');
      const p = current();
      if (!art || !art.isConnected || root.hidden || !p || p.asleep) return;
      const list = IDLES[p.emotion] || [];
      if (list.length && !art.matches('[class*="pt-m-"]')) {
        const idle = list[Math.floor(Math.random() * list.length)];
        if (idle === "look") lookAround(art);
        else pulse(art, `pt-m-idle-${idle}`, 1400);
        if (Math.random() < 0.4) particles(art, `amb-${p.emotion}`);   // une petite surprise, de temps en temps
      }
      idleLoop(root);
    }, IDLE_MIN_MS + Math.random() * IDLE_SPREAD_MS);
  }
  /** Il regarde à gauche, puis à droite, puis revient (le regard glisse : transition de pt-face). */
  function lookAround(art) {
    const side = Math.random() < 0.5 ? -1 : 1;
    pulse(art, "pt-m-idle-look", 1500);
    art.style.setProperty("--lx", `${side * LOOK_PX}px`);
    later(() => art.style.setProperty("--lx", `${-side * LOOK_PX}px`), 600);
    later(() => art.style.removeProperty("--lx"), 1200);
  }
  let lookFrame = 0, lookReset = 0;
  function onPointer(ev) {
    const root = ev.currentTarget;
    const art = root.querySelector(".pt-stage .pt-art");
    if (!art || calm() || lookFrame) return;
    lookFrame = requestAnimationFrame(() => {
      lookFrame = 0;
      const r = art.getBoundingClientRect();
      const dx = (ev.clientX - (r.left + r.width / 2)) / Math.max(r.width, 1);
      const dy = (ev.clientY - (r.top + r.height * 0.4)) / Math.max(r.height, 1);
      const len = Math.hypot(dx, dy) || 1, k = Math.min(1, len * 1.6) / len;
      art.style.setProperty("--lx", `${(dx * k * LOOK_PX).toFixed(1)}px`);
      art.style.setProperty("--ly", `${(dy * k * LOOK_PX * 0.7).toFixed(1)}px`);
      clearTimeout(lookReset);
      lookReset = setTimeout(() => { art.style.removeProperty("--lx"); art.style.removeProperty("--ly"); }, LOOK_RESET_MS);
    });
  }
  const watched = new WeakSet();

  // ── API ──
  /** Avant de remplacer l'écran : on note les barres affichées ; la fonction rendue anime le nouvel écran. */
  function before(root) {
    const meters = root ? meterValues(root) : {};
    const prevScreen = root?.dataset.screen || "";
    return (screen) => {
      if (!root) return;
      clear();
      if (!watched.has(root)) { watched.add(root); root.addEventListener("pointermove", onPointer, { passive: true }); root.addEventListener("pointerdown", onPointer, { passive: true }); }
      if (screen !== "loading") enter(root, screen);
      const p = current(), now = ["login", "adopt", "error", "loading"].includes(screen) ? null : snapshot(p);
      if (now) {
        changes(root, screen, last, now);
        const coins = now.coins;
        if (last && coins != null && last.coins != null && coins !== last.coins) {
          coinDisplays(root).forEach((el) => countUp(el, last.coins, coins));
          if (coins > last.coins) glideCoin(root, coinDisplays(root)[0]);
        }
        last = now;
      }
      // Barres d'un même écran qui change (caisse commune, séries de la collection) : depuis l'ancienne valeur.
      if (prevScreen === screen && screen !== "home") {
        const after = meterValues(root);
        root.querySelectorAll('[role="meter"]').forEach((m) => {
          const k = m.getAttribute("aria-label");
          if (meters[k] != null && after[k] > meters[k]) fillMeter(m, meters[k], after[k]);
        });
        if (root.querySelector(".pt-pot") && Object.keys(after).some((k) => after[k] >= 1 && meters[k] != null && meters[k] < 1)) particles(root.querySelector(".pt-pot"), "mission");
      }
      if (screen === "home") idleLoop(root);
      if (screen === "egg") eggSoon(root, p);
    };
  }
  /** Œuf : dans la dernière minute, il tremble plus fort (le compte à rebours de pet.js garde la main). */
  function eggSoon(root, p) {
    if (!p || p.next_stage_in == null) return;
    const stage = root.querySelector(".pt-stage");
    later(() => stage?.isConnected && !calm() && stage.classList.add("pt-m-soon"), Math.max(0, (p.next_stage_in - 60) * 1000));
  }
  /** Un soin vient d'être fait : chaque geste son animation et ses particules. */
  const ACT_CLASS = { feed: "eat", treat: "eat", play: "hop", cuddle: "hug", heal: "wash", sleep: "sleep", tuck: "sleep", wake: "wake",
    outfit: "equip", rename: "boop", new_egg: "born", "": "boop" };
  const TAPS = ["boop", "giggle", "spin"];
  function act(root, action) {
    const art = root?.querySelector(".pt-stage .pt-art");
    if (!art || calm()) return;
    pulse(root.querySelector(`[data-a="${action}"] .pt-act-i`), "pt-m-press", 600);   // le bouton touché rebondit aussi
    if (action === "") {   // simple caresse (plus de câlins aujourd'hui, ou il dort) : une réaction au hasard
      const tap = TAPS[Math.floor(Math.random() * TAPS.length)];
      pulse(art, `pt-m-${tap}`, 900);
      particles(art, tap === "giggle" ? "giggle" : "boop");
      return;
    }
    pulse(art, `pt-m-${ACT_CLASS[action] ?? "boop"}`, 1000);
    particles(art, action === "rename" ? "boop" : action === "new_egg" ? "born" : action);
  }
  /** Éclosion : l'œuf tremble, se fissure, éclate (pet.js relit ensuite l'état : Zicou apparaît avec pt-m-born). */
  function hatch(root) {
    const stage = root?.querySelector(".pt-stage");
    if (!stage || calm()) return;
    stage.classList.remove("pt-m-soon");
    pulse(stage, "pt-m-crack", 900);
    const art = stage.querySelector(".pt-art");
    if (art) {
      const crack = document.createElement("span");
      crack.className = "pt-m-cracks";
      crack.setAttribute("aria-hidden", "true");
      crack.innerHTML = '<svg viewBox="0 0 100 100"><path d="M50 30 l-6 10 l8 6 l-7 9 l9 7 l-5 8"/><path d="M38 48 l-8 4 M60 52 l9 -3"/></svg>';
      art.append(crack);
    }
    buzz([15, 40, 15, 40, 30]);
  }
  /** Fin de session de l'onglet : la mémoire reste (au retour, ce qui a changé entre-temps s'anime). */
  function reset() { clear(); lastScreen = ""; lastKey = ""; }

  window.PetMotion = Object.freeze({ before, act, hatch, reset, pulse, particles });
})();
