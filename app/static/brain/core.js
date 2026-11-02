// 🧠 Méninges : moteur des mini-jeux d'entraînement (solo). Panneau plein écran position: fixed (#brainRoot), jamais de
// règle de hauteur ou de défilement sur html/body (bug iOS 26, voir CLAUDE.md). Chaque mini-jeu (games/<id>.js) appelle
// Brain.register({...}) ; le moteur gère l'accueil, l'Échauffement, l'explication, le 3-2-1, le chrono, le score
// (50 × multiplicateur, jauge de 4, ×1…×10, bonus final 250 × multiplicateur), l'écran de fin et l'envoi du résultat.
(function () {
  "use strict";
  const BRAIN_NAME = "Méninges";
  const BRAIN_GAMES = ["pareil", "motif", "autoroute", "grille", "deux_avant", "tresor", "nuee", "aiguillage",
    "intrus", "encre", "bascule", "courant", "balance", "gouttes", "syllabes"];
  // [id, libellé, emoji, couleur] ; les 5 premiers forment la Température, Calcul a son indice à part.
  const DOMAINS = [["vitesse", "Vitesse", "⚡", "#4f8cff"], ["memoire", "Mémoire", "🧠", "#b07cff"],
    ["attention", "Attention", "🎯", "#2ee6c5"], ["flexibilite", "Flexibilité", "🔀", "#ff6fb5"],
    ["logique", "Logique", "🧩", "#8be36b"], ["calcul", "Calcul", "➗", "#ff7a7a"]];
  const TEMP_DOMAINS = 5;
  const POINTS = 50, GAUGE = 4, MULT_MAX = 10, FINAL_BONUS = 250;
  const WARMUP_SIZE = 5, LOCAL_MAX = 300, SYNC_MAX = 30, INDEX_MAX = 2000;
  const COUNT_FROM = 3, COUNT_STEP_MS = 750, FLASH_MS = 260, TICK_MS = 100, WARN_S = 5, MIN_SEND_MS = 1000;
  const K = { sessions: "brain_local", levels: "brain_levels", best: "brain_best", warmup: "brain_warmup", sound: "vp-game-sounds" };

  const games = new Map();
  const escHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const e = typeof esc === "function" ? esc : escHtml;
  const fmt = (n) => Math.round(+n || 0).toLocaleString("fr-CH");
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const today = () => new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Zurich" });
  const domainOf = (id) => DOMAINS.find((d) => d[0] === id) || DOMAINS[0];

  // ── Stockage local (navigation privée, stockage plein : l'app marche sans) ──
  function read(key, fallback) {
    try { const v = JSON.parse(localStorage.getItem(key)); return v ?? fallback; } catch { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* stockage indisponible : rien n'est gardé */ }
  }

  // ── Aléatoire à graine (même graine = même partie, pour un futur duel) ──
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const hashSeed = (s) => [...String(s)].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0, 2166136261);
  function freshSeed() {
    try { return crypto.getRandomValues(new Uint32Array(1))[0]; } catch { return hashSeed(String(Date.now()) + performance.now()); }
  }

  // ── Sons (courts, synthétisés ; même réglage que les sons des jeux) et vibration ──
  let audio = null;
  const TONES = { ok: [[880, 0], [1320, 0.06]], miss: [[220, 0], [185, 0.07]], up: [[660, 0], [880, 0.07], [1175, 0.14]],
    tick: [[1000, 0]], end: [[523, 0], [659, 0.1], [784, 0.2], [1047, 0.3]] };
  function sound(kind) {
    try {
      if (localStorage.getItem(K.sound) === "off" || document.hidden) return;
    } catch { /* réglage illisible : on joue quand même */ }
    try {
      const A = window.AudioContext || window.webkitAudioContext;
      if (!A) return;
      audio ||= new A();
      if (audio.state !== "running") audio.resume().catch(() => {});
      for (const [freq, at] of TONES[kind] || []) {
        const o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime + at;
        o.type = kind === "miss" ? "triangle" : "sine";
        o.frequency.setValueAtTime(freq, t);
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(0.07, t + 0.006);
        g.gain.exponentialRampToValueAtTime(0.001, t + 0.13);
        o.connect(g); g.connect(audio.destination);
        o.onended = () => { o.disconnect(); g.disconnect(); };
        o.start(t); o.stop(t + 0.14);
      }
    } catch { /* audio refusé par le navigateur : le jeu reste jouable */ }
  }
  const buzz = (pattern) => { if (typeof haptic === "function") haptic(pattern); };

  // ── Minuteurs du moteur : tous arrêtés à la fermeture ──
  const timers = new Set();
  function later(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; }
  function every(fn, ms) { const id = setInterval(fn, ms); timers.add(id); return id; }
  function clearTimers() { for (const id of timers) { clearTimeout(id); clearInterval(id); } timers.clear(); }

  // ── Panneau ──
  let root = null, opener = null, run = null, profile = null, connected = false, loading = null;
  function panel() {
    if (root) return root;
    root = document.createElement("div");
    root.id = "brainRoot";
    root.className = "br-root";
    root.hidden = true;
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", BRAIN_NAME);
    root.addEventListener("click", onClick);
    document.body.append(root);
    return root;
  }
  function show(html, screen) {
    const r = panel();
    r.dataset.screen = screen;
    r.innerHTML = html;
    r.scrollTop = 0;
  }
  async function open(fromEl) {
    opener = fromEl || document.activeElement;
    const r = panel();
    r.hidden = false;
    document.documentElement.classList.add("br-open");
    show(`<div class="br-loading" role="status"><span class="br-spin" aria-hidden="true"></span>Chauffe en cours…</div>`, "loading");
    await loadGames();
    await refreshProfile();
    if (!r.hidden && !run) home();
  }
  function close() {
    stopRun();
    clearTimers();
    if (!root) return;
    root.hidden = true;
    root.innerHTML = "";
    document.documentElement.classList.remove("br-open");
    try { opener?.focus?.(); } catch { /* bouton disparu */ }
  }

  // ── Chargement des mini-jeux (un fichier absent est simplement ignoré) ──
  const base = (() => {
    const src = document.currentScript?.src || "/static/brain/core.js";
    const u = new URL(src, location.href);
    return { dir: u.pathname.replace(/core\.js$/, ""), query: u.search };
  })();
  function loadGames() {
    loading ||= Promise.all([...BRAIN_GAMES.map((id) => `games/${id}`), "detail"].map((id) => new Promise((done) => {
      const s = document.createElement("script");
      s.src = `${base.dir}${id}.js${base.query}`;
      s.async = true;
      s.onload = s.onerror = () => done();
      document.head.append(s);
    })));
    return loading;
  }
  function register(def) {
    if (!def || typeof def.id !== "string" || typeof def.start !== "function" || games.has(def.id)) return;
    const domain = DOMAINS.some((d) => d[0] === def.domain) ? def.domain : "attention";
    games.set(def.id, Object.freeze({ ...def, domain, name: String(def.name || def.id), icon: String(def.icon || "🧠"),
      color: String(def.color || domainOf(domain)[3]), seconds: def.seconds > 0 ? +def.seconds : null,
      howto: Array.isArray(def.howto) ? def.howto.map(String) : [] }));
  }
  const available = () => BRAIN_GAMES.filter((id) => games.has(id)).map((id) => games.get(id));

  // ── Compte et statistiques ──
  async function token() {
    try { return typeof freshToken === "function" ? await freshToken() : null; } catch { return null; }
  }
  async function post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) {
      const detail = (await r.json().catch(() => ({}))).detail;
      throw Object.assign(new Error(typeof detail === "string" ? detail : `Erreur ${r.status}`), { status: r.status });
    }
    return r.json();
  }
  async function refreshProfile() {
    const t = await token();
    connected = !!t;
    try {
      if (t) await syncLocal(t);
      profile = t ? await post("/api/brain/me", { token: t }) : await post("/api/brain/local", { sessions: read(K.sessions, []).slice(-LOCAL_MAX) });
    } catch { profile = null; }  // hors ligne : l'accueil se contente des records gardés sur ce téléphone
  }
  // Parties jouées sans connexion (ou hors ligne) : envoyées au compte dès qu'on est connecté.
  async function syncLocal(t) {
    const pending = read(K.sessions, []);
    if (!pending.length) return;
    const keep = [];
    for (const s of pending.slice(-SYNC_MAX)) {
      try { await post("/api/brain/result", { token: t, ...s, played_at: undefined }); } catch (err) {
        if (!err.status || [401, 429].includes(err.status) || err.status >= 500) keep.push(s);  // refus définitif (400, 422) : abandonnée
      }
    }
    write(K.sessions, keep);
  }
  const bestOf = (id) => Math.max(read(K.best, {})[id] || 0, profile?.games?.[id]?.best || 0);
  function startLevel(id) {
    const last = Math.max(read(K.levels, {})[id] || 0, profile?.games?.[id]?.last_level || 0);
    return Math.max(1, last - 1);
  }

  // ── L'Échauffement : 5 jeux du jour, un par domaine autant que possible ──
  function warmup() {
    const day = today(), saved = read(K.warmup, null);
    const ids = new Set(available().map((g) => g.id));
    if (saved?.day === day && saved.ids.every((id) => ids.has(id))) return saved;
    // Choix du serveur (domaines faibles en tête, jeux peu joués) ; le tirage local reste le secours hors ligne.
    const server = profile?.warmup;
    if (server?.length && server.every((id) => ids.has(id))) {
      const fresh = { day, ids: server.slice(0, WARMUP_SIZE), done: [] };
      write(K.warmup, fresh);
      return fresh;
    }
    const rng = mulberry32(hashSeed(day));
    const shuffle = (list) => list.map((x) => [rng(), x]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);
    const domains = [...shuffle(DOMAINS.slice(0, TEMP_DOMAINS)), DOMAINS[TEMP_DOMAINS]].map((d) => d[0]);
    const pick = [];
    for (const d of domains) {
      const options = shuffle(available().filter((g) => g.domain === d));
      if (options.length && pick.length < WARMUP_SIZE) pick.push(options[0].id);
    }
    for (const g of shuffle(available())) if (pick.length < WARMUP_SIZE && !pick.includes(g.id)) pick.push(g.id);
    const fresh = { day, ids: pick, done: [] };
    write(K.warmup, fresh);
    return fresh;
  }
  function markWarmup(id) {
    const w = warmup();
    if (w.ids.includes(id) && !w.done.includes(id)) write(K.warmup, { ...w, done: [...w.done, id] });
  }

  // ── Accueil ──
  const closeBtn = (label = "Fermer") => `<button type="button" class="br-round" data-br="close" aria-label="${label}">✕</button>`;
  function thermo(temp) {
    const ratio = Math.max(0, Math.min(1, temp / INDEX_MAX)), len = 251.3;
    return `<svg class="br-thermo" viewBox="0 0 200 120" aria-hidden="true">
      <defs><linearGradient id="brHeat" x1="0" x2="1"><stop offset="0" stop-color="#3fd0ff"/><stop offset=".55" stop-color="#8b5cff"/><stop offset="1" stop-color="#ff4f9a"/></linearGradient></defs>
      <path d="M20 105 A80 80 0 0 1 180 105" class="br-thermo-bg"/>
      <path d="M20 105 A80 80 0 0 1 180 105" class="br-thermo-fg" stroke-dasharray="${len}" stroke-dashoffset="${(len * (1 - ratio)).toFixed(1)}"/></svg>`;
  }
  function domainRows() {
    return DOMAINS.map(([id, label, icon, color], i) => {
      const v = profile?.domains?.[id]?.index || 0;
      return `<li class="br-dom${i === TEMP_DOMAINS ? " br-dom-apart" : ""}" style="--c:${color}">
        <span class="br-dom-i" aria-hidden="true">${icon}</span><span class="br-dom-l">${label}</span>
        <span class="br-bar"><i style="transform:scaleX(${(v / INDEX_MAX).toFixed(3)})"></i></span><b>${v ? fmt(v) : "–"}</b></li>`;
    }).join("");
  }
  function warmupCard() {
    const w = warmup();
    if (!w.ids.length) return `<section class="br-warm"><p class="br-muted">Les jeux arrivent bientôt.</p></section>`;
    const done = w.done.length, all = done >= w.ids.length;
    const label = all ? "Refaire l'Échauffement" : done ? `Continuer · ${done}/${w.ids.length}` : "Commencer";
    return `<section class="br-warm${all ? " br-warm-done" : ""}" aria-labelledby="brWarmH">
      <div class="br-warm-top"><h3 id="brWarmH">L'Échauffement</h3><span class="br-chip">${all ? "✓ Fait aujourd'hui" : `${w.ids.length} jeux · ~5 min`}</span></div>
      <p class="br-muted">Un jeu par domaine, choisi pour aujourd'hui.</p>
      <ol class="br-warm-row">${w.ids.map((id) => { const g = games.get(id); return `<li class="${w.done.includes(id) ? "on" : ""}" style="--c:${e(g.color)}" title="${e(g.name)}"><span aria-hidden="true">${e(g.icon)}</span><span class="br-sr">${e(g.name)}${w.done.includes(id) ? " (fait)" : ""}</span></li>`; }).join("")}</ol>
      <button type="button" class="br-cta" data-br="warmup">${label}</button></section>`;
  }
  function gameTiles() {
    return DOMAINS.map(([id, label, icon, color]) => {
      const list = available().filter((g) => g.domain === id);
      if (!list.length) return "";
      return `<section class="br-domain" style="--c:${color}"><h3><span aria-hidden="true">${icon}</span> ${label}</h3><div class="br-tiles">${list.map((g) => {
        const best = bestOf(g.id);
        return `<button type="button" class="br-tile" data-br="play" data-id="${e(g.id)}" style="--g:${e(g.color)}">
          <span class="br-tile-i" aria-hidden="true">${e(g.icon)}</span><span class="br-tile-n">${e(g.name)}</span>
          <span class="br-tile-s">${best ? `Record ${fmt(best)}` : "Pas encore joué"}</span></button>`;
      }).join("")}</div></section>`;
    }).join("");
  }
  function home() {
    const temp = profile?.temperature || 0, st = profile?.streak || { current: 0, best: 0 };
    const pct = profile?.percentile;
    const sub = !temp ? "Joue pour mesurer ta Température." : pct != null ? `Plus chaud que ${pct} % des joueurs Party` : "Ta Température du moment";
    const login = connected ? "" : `<div class="br-login"><span>🔒 Connecte-toi pour garder tes stats sur tous tes appareils.</span><button type="button" class="br-link" data-br="login">Me connecter</button></div>`;
    show(`<div class="br-home">
      <header class="br-top"><h2 class="br-title"><span aria-hidden="true">🧠</span> ${e(BRAIN_NAME)}</h2>${closeBtn()}</header>
      ${login}
      <section class="br-hero" aria-label="Température">
        <div class="br-gauge">${thermo(temp)}<div class="br-temp"><b>${fmt(temp)}</b><span>°M</span></div></div>
        <p class="br-hero-sub">${e(sub)}</p>
        <div class="br-streak${st.current ? " hot" : ""}"><span aria-hidden="true">🔥</span> ${st.current ? `${st.current} jour${st.current > 1 ? "s" : ""} d'affilée` : "Pas encore de série"}${st.best ? ` <small>· record ${st.best}</small>` : ""}</div>
        ${profile?.insight ? `<p class="br-insight">${e(profile.insight)}</p>` : ""}
        <ul class="br-doms">${domainRows()}</ul>
      </section>
      ${warmupCard()}
      <h3 class="br-h">Tous les jeux</h3>
      ${gameTiles() || `<p class="br-muted">Les jeux arrivent bientôt.</p>`}
    </div>`, "home");
  }

  // ── Explication, puis 3-2-1 ──
  function howto(id, inWarmup) {
    const g = games.get(id);
    if (!g) return home();
    const d = domainOf(g.domain);
    window.BrainDetail?.prefetch(id);  // stats du jeu avant la partie (écran de fin enrichi, detail.js)
    show(`<div class="br-howto" style="--g:${e(g.color)}">
      <header class="br-top">${inWarmup ? `<span class="br-chip">Échauffement · ${warmup().done.length + 1}/${warmup().ids.length}</span>` : "<span></span>"}${closeBtn("Retour")}</header>
      <div class="br-howto-i" aria-hidden="true">${e(g.icon)}</div>
      <h2 class="br-howto-n">${e(g.name)}</h2>
      <p class="br-chip br-chip-dom" style="--c:${d[3]}">${d[2]} ${d[1]} · ${g.seconds ? `${g.seconds} s` : "jusqu'à la fin"} · niveau ${startLevel(id)}</p>
      <ol class="br-rules">${g.howto.map((t) => `<li>${e(t)}</li>`).join("")}</ol>
      <p class="br-muted br-small">Bonne réponse : 50 points × multiplicateur. 4 bonnes d'affilée font monter le multiplicateur (jusqu'à ×10), une erreur le fait redescendre.</p>
      <button type="button" class="br-cta" data-br="go" data-id="${e(id)}" ${inWarmup ? "data-warmup" : ""}>C'est parti</button>
    </div>`, "howto");
    root.querySelector(".br-cta")?.focus();
  }
  function countdown(id, inWarmup) {
    const g = games.get(id);
    let n = COUNT_FROM;
    show(`<div class="br-count" style="--g:${e(g.color)}"><span class="br-count-n" aria-live="assertive">${n}</span><p>${e(g.name)}</p></div>`, "count");
    const tick = () => {
      n -= 1;
      if (n <= 0) return play(id, inWarmup);
      const el = root.querySelector(".br-count-n");
      if (el) { el.textContent = n; el.classList.remove("pop"); void el.offsetWidth; el.classList.add("pop"); }
      sound("tick");
      later(tick, COUNT_STEP_MS);
    };
    sound("tick");
    later(tick, COUNT_STEP_MS);
  }

  // ── Partie ──
  function hud() {
    if (!run) return;
    const q = (s) => root.querySelector(s);
    const left = run.def.seconds ? Math.max(0, Math.ceil(run.def.seconds - run.elapsed() / 1000)) : Math.floor(run.elapsed() / 1000);
    const time = q(".br-time");
    if (time) {
      time.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
      time.classList.toggle("warn", !!run.def.seconds && left <= WARN_S);
    }
    if (q(".br-score")) q(".br-score").textContent = fmt(run.score);
    if (q(".br-mult b")) q(".br-mult b").textContent = `×${run.mult}`;
    q(".br-gauge4")?.querySelectorAll("i").forEach((dot, i) => dot.classList.toggle("on", run.mult >= MULT_MAX || i < run.gauge));
  }
  function flash(kind, text) {
    const p = root?.querySelector(".br-play");
    if (!p) return;
    p.classList.remove("br-hit", "br-miss");
    void p.offsetWidth;
    p.classList.add(kind === "ok" ? "br-hit" : "br-miss");
    later(() => p.classList.remove("br-hit", "br-miss"), FLASH_MS);
    if (!text) return;
    const fly = document.createElement("span");
    fly.className = `br-fly ${kind}`;
    fly.textContent = text;
    root.querySelector(".br-hud")?.append(fly);
    later(() => fly.remove(), 700);
  }
  function play(id, inWarmup) {
    const def = games.get(id);
    const level = startLevel(id), seed = freshSeed(), t0 = performance.now();
    show(`<div class="br-play" style="--g:${e(def.color)}">
      <header class="br-hud">
        ${closeBtn("Quitter la partie").replace('data-br="close"', 'data-br="quit"')}
        <span class="br-time" aria-label="Temps">0:00</span>
        <span class="br-score" aria-live="polite">0</span>
        <span class="br-mult"><b>×1</b><span class="br-gauge4" aria-hidden="true">${"<i></i>".repeat(GAUGE)}</span></span>
      </header>
      <div class="br-stage" id="brStage"></div>
    </div>`, "play");
    run = { def, inWarmup, seed, level, maxLevel: level, score: 0, mult: 1, gauge: 0, hits: 0, misses: 0, rts: [],
      ended: false, handle: null, timeUp: [], elapsed: () => performance.now() - t0 };
    const current = run;
    const rt = (x) => { const v = +(x?.rt); return Number.isFinite(v) && v > 0 && v < 60000 ? v : null; };
    const ctx = Object.freeze({
      root: root.querySelector("#brStage"),
      level, reducedMotion: calm(), esc: e, rng: mulberry32(seed),
      hit(info) {
        if (current.ended) return;
        current.hits += 1;
        current.score += POINTS * current.mult;
        const v = rt(info);
        if (v) current.rts.push(v);
        flash("ok", `+${POINTS * current.mult}`);
        if (current.mult < MULT_MAX && ++current.gauge >= GAUGE) {
          current.mult += 1; current.gauge = 0; sound("up"); buzz(15);
        } else sound("ok");
        hud();
      },
      miss() {
        if (current.ended) return;
        current.misses += 1;
        if (current.gauge > 0 && current.mult < MULT_MAX) current.gauge = 0;
        else { current.mult = Math.max(1, current.mult - 1); current.gauge = 0; }
        flash("miss", "");
        sound("miss"); buzz(40);
        hud();
      },
      setLevel(n) { const v = Math.max(1, Math.floor(+n || 1)); current.level = v; current.maxLevel = Math.max(current.maxLevel, v); },
      finish(extra) { finishRun(current, extra); },
      onTimeUp(fn) { if (typeof fn === "function") current.timeUp.push(fn); },
    });
    try { run.handle = def.start(ctx) || null; } catch { return finishRun(current, { detail: "Le jeu n'a pas pu démarrer." }); }
    every(() => {
      if (current.ended) return;
      hud();
      if (current.def.seconds && current.elapsed() >= current.def.seconds * 1000) {
        for (const fn of current.timeUp) { try { fn(); } catch { /* un jeu fautif n'empêche pas la fin */ } }
        finishRun(current);
      }
    }, TICK_MS);
    hud();
  }
  function stopRun() {
    if (!run) return;
    run.ended = true;
    try { run.handle?.stop?.(); } catch { /* jeu déjà arrêté */ }
    run = null;
  }

  // ── Fin de partie ──
  function finishRun(current, extra) {
    if (current.ended || current !== run) return;
    current.ended = true;
    try { current.handle?.stop?.(); } catch { /* jeu déjà arrêté */ }
    run = null;
    clearTimers();
    const answers = current.hits + current.misses;
    const bonus = FINAL_BONUS * current.mult;
    const res = { id: current.def.id, base: current.score, bonus, mult: current.mult, score: current.score + bonus,
      accuracy: answers ? current.hits / answers : 0, avgRt: current.rts.length ? Math.round(current.rts.reduce((a, b) => a + b, 0) / current.rts.length) : 0,
      level: current.maxLevel, duration: Math.round(current.elapsed()), hits: current.hits, misses: current.misses,
      detail: extra && typeof extra.detail === "string" ? extra.detail : "", inWarmup: current.inWarmup };
    const previous = bestOf(res.id);
    res.record = res.score > previous;
    res.best = Math.max(previous, res.score);
    write(K.levels, { ...read(K.levels, {}), [res.id]: res.level });
    write(K.best, { ...read(K.best, {}), [res.id]: res.best });
    if (res.inWarmup) markWarmup(res.id);
    sound("end");
    endScreen(res);
    window.BrainDetail?.enrich(res);
    save(res).then(() => window.BrainDetail?.saved(res));
  }
  async function save(res) {
    const session = { game: res.id, score: res.score, accuracy: +res.accuracy.toFixed(4), avg_rt_ms: res.avgRt,
      level: res.level, duration_ms: res.duration };
    const keepLocal = () => write(K.sessions, [...read(K.sessions, []), { ...session, played_at: new Date().toISOString() }].slice(-LOCAL_MAX));
    const t = await token();
    const note = root?.querySelector(".br-save");
    if (!t || res.duration < MIN_SEND_MS) {
      keepLocal();
      if (note) note.innerHTML = `🔒 Partie gardée sur ce téléphone. <button type="button" class="br-link" data-br="login">Connecte-toi pour garder tes stats</button>`;
      return;
    }
    try {
      const r = await post("/api/brain/result", { token: t, ...session });
      if (!note?.isConnected) return;
      note.textContent = r.record ? "🏆 Nouveau record enregistré !" : "✓ Enregistré dans tes stats";
      const idx = root.querySelector(".br-index");
      if (idx) { idx.hidden = false; idx.querySelector("b").textContent = `${fmt(r.index)} °M`; }
    } catch (err) {
      keepLocal();
      if (note?.isConnected) note.textContent = `Pas enregistré (${err.message}). Gardé sur ce téléphone, renvoyé plus tard.`;
    }
  }
  function endScreen(res) {
    const g = games.get(res.id), w = warmup();
    const left = w.ids.filter((id) => !w.done.includes(id));
    const next = res.inWarmup && left.length ? left[0] : null;
    const stat = (label, value) => `<div class="br-stat"><span>${label}</span><b>${value}</b></div>`;
    show(`<div class="br-end" style="--g:${e(g.color)}">
      <header class="br-top"><span class="br-chip">${e(g.icon)} ${e(g.name)}</span>${closeBtn()}</header>
      ${res.record ? `<p class="br-record">🏆 Nouveau record</p>` : ""}
      <div class="br-big" data-count="${res.score}">${fmt(calm() ? res.score : 0)}</div>
      <p class="br-muted">points</p>
      <div class="br-bonus"><span>${fmt(res.base)} en jeu</span><span>+ ${fmt(res.bonus)} bonus ×${res.mult}</span></div>
      <div class="br-stats">
        ${stat("Précision", `${Math.round(res.accuracy * 100)} %`)}
        ${stat("Réaction moyenne", res.avgRt ? `${fmt(res.avgRt)} ms` : "–")}
        ${stat("Record", fmt(res.best))}
        ${stat("Niveau atteint", res.level)}
        ${stat("Bonnes / erreurs", `${res.hits} / ${res.misses}`)}
        <div class="br-stat br-index" hidden><span>Indice de la partie</span><b></b></div>
      </div>
      ${res.detail ? `<p class="br-detail">${e(res.detail)}</p>` : ""}
      <p class="br-save br-muted" aria-live="polite">Enregistrement…</p>
      <div class="br-actions">
        ${res.inWarmup && !next ? `<button type="button" class="br-cta" data-br="warmdone">Terminer l'Échauffement</button>` : ""}
        ${next ? `<button type="button" class="br-cta" data-br="next" data-id="${e(next)}">Jeu suivant · ${w.done.length + 1}/${w.ids.length}</button>` : ""}
        <button type="button" class="${res.inWarmup ? "br-ghost" : "br-cta"}" data-br="again" data-id="${e(res.id)}">Rejouer</button>
        <button type="button" class="br-ghost" data-br="home">Accueil ${e(BRAIN_NAME)}</button>
      </div>
    </div>`, "end");
    countUp(root.querySelector(".br-big"), res.score);
  }
  function countUp(el, to) {
    if (!el || calm()) return;
    const t0 = performance.now(), ms = 900;
    const step = (now) => {
      if (!el.isConnected) return;
      const k = Math.min(1, (now - t0) / ms);
      el.textContent = fmt(to * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  async function warmupDone() {
    show(`<div class="br-loading" role="status"><span class="br-spin" aria-hidden="true"></span>Mise à jour de ta Température…</div>`, "loading");
    await refreshProfile();
    const st = profile?.streak || { current: 0 };
    show(`<div class="br-end br-done">
      <header class="br-top"><span></span>${closeBtn()}</header>
      <div class="br-done-flame" aria-hidden="true">🔥</div>
      <h2 class="br-howto-n">Échauffement terminé</h2>
      <p class="br-muted">${st.current ? `${st.current} jour${st.current > 1 ? "s" : ""} d'affilée. Reviens demain pour la garder !` : "Bravo, reviens demain !"}</p>
      <div class="br-temp br-temp-done"><b>${fmt(profile?.temperature || 0)}</b><span>°M</span></div>
      <div class="br-actions"><button type="button" class="br-cta" data-br="home">Voir ma Température</button></div>
    </div>`, "done");
  }

  // ── Quitter une partie en cours ──
  function askQuit() {
    if (!run || root.querySelector(".br-confirm")) return;
    root.querySelector(".br-play")?.insertAdjacentHTML("beforeend", `<div class="br-confirm" role="alertdialog" aria-label="Quitter la partie ?">
      <p><b>Quitter la partie ?</b><br>Elle ne comptera pas.</p>
      <div class="br-actions"><button type="button" class="br-ghost" data-br="stay">Continuer</button><button type="button" class="br-cta br-danger" data-br="leave">Quitter</button></div></div>`);
  }

  // ── Toucher ──
  function onClick(ev) {
    const b = ev.target.closest("[data-br]");
    if (!b || !root.contains(b)) return;
    const id = b.dataset.id;
    switch (b.dataset.br) {
      case "close": return root.dataset.screen === "howto" ? home() : close();
      case "login": close(); return typeof showTab === "function" && showTab("account");
      case "play":  // jeu déjà joué : sa fiche d'abord (detail.js) ; sinon directement l'explication
        if (window.BrainDetail && bestOf(id) > 0) return window.BrainDetail.sheet(id);
        return howto(id, false);
      case "again": return howto(id, false);
      case "warmup": {
        const w = warmup();
        if (w.done.length >= w.ids.length) write(K.warmup, { ...w, done: [] });
        const first = warmup().ids.find((x) => !warmup().done.includes(x));
        return first && howto(first, true);
      }
      case "next": return howto(id, true);
      case "go": return countdown(id, b.hasAttribute("data-warmup"));
      case "quit": return askQuit();
      case "stay": return root.querySelector(".br-confirm")?.remove();
      case "leave": stopRun(); clearTimers(); return refreshProfile().then(home);
      case "warmdone": return warmupDone();
      case "home": return refreshProfile().then(home);
    }
  }
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-brain-open]");
    if (b) open(b);
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape" || !root || root.hidden) return;
    if (run) askQuit(); else if (root.dataset.screen === "howto") home(); else close();
  });
  document.querySelectorAll("[data-brain-name]").forEach((el) => { el.textContent = BRAIN_NAME; });

  window.BRAIN_NAME = BRAIN_NAME;
  window.Brain = Object.freeze({ name: BRAIN_NAME, games: BRAIN_GAMES, domains: DOMAINS, register, open, close,
    rng: mulberry32, list: available,
    // Pour detail.js (statistiques par jeu) : accès en lecture au moteur.
    api: Object.freeze({ post, token, show, esc: e, calm, game: (id) => games.get(id), domain: domainOf,
      localSessions: () => read(K.sessions, []) }) });
})();
