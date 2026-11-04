// 🥚 Compagnon : personnage à entretenir (façon Tamagotchi). Panneau plein écran position: fixed (#petRoot), jamais de
// règle de hauteur ou de défilement sur html/body (bug iOS 26, voir CLAUDE.md). La vie est calculée par le serveur
// (/api/pet/*, app/pet.py) ; le dessin vient de la couche graphique remplaçable window.PetSkin (pet/skin.js).
// Compte requis (le personnage vit sur tous les appareils) ; sans compte : invitation à se connecter.
(function () {
  "use strict";
  const GAME_NAME = "Compagnon";
  const PLAY_MS = 20000, SPAWN_MS = 650, NOTE_MS = 1150, NOTE_MS_CALM = 1700, TICK_MS = 1000, NEWS_MS = 4200;
  const GAUGES = [["food", "Ventre", "🍕"], ["joy", "Humeur", "🎵"], ["energy", "Énergie", "⚡"], ["care", "Forme", "🧼"]];
  const STAGES = { egg: "Œuf", baby: "Bébé", teen: "Ado", adult: "Adulte", dead: "Envolé" };
  const VARIANTS = { star: "étoile ✨", classic: "", wild: "rebelle 😜" };
  const EMOTIONS = { egg: "dans son œuf", happy: "content", party: "en fête", hungry: "a faim", tired: "fatigué",
    sad: "s'ennuie", sick: "patraque", sleep: "endormi", ghost: "envolé" };
  const ACTIONS = [["feed", "Nourrir", "🍕"], ["play", "Jouer", "🎵"], ["cuddle", "Câlin", "🤗"], ["heal", "Soigner", "🧼"]];

  const escHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const e = typeof esc === "function" ? esc : escHtml;
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const buzz = (p) => { if (typeof haptic === "function") haptic(p); };
  const cue = (kind) => { try { window.GameAudio?.cue?.(kind); } catch { /* audio refusé : le jeu reste jouable */ } };
  const skin = () => window.PetSkin;
  const creatureName = () => skin()?.creatureName || "Paillou";

  // ── Minuteurs : tous arrêtés à la fermeture ──
  const timers = new Set();
  function later(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; }
  function every(fn, ms) { const id = setInterval(fn, ms); timers.add(id); return id; }
  function clearTimers() { for (const id of timers) { clearTimeout(id); clearInterval(id); } timers.clear(); }

  // ── Panneau ──
  let root = null, opener = null, pet = null, friends = null, busy = false, game = null, screenSeq = 0;
  function panel() {
    if (root) return root;
    root = document.createElement("div");
    root.id = "petRoot";
    root.className = "pt-root";
    root.hidden = true;
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", GAME_NAME);
    root.tabIndex = -1;
    root.addEventListener("click", onClick);
    root.addEventListener("submit", onSubmit);
    document.body.append(root);
    return root;
  }
  function show(html, screen) {
    const r = panel();
    screenSeq += 1;
    clearTimers();
    r.dataset.screen = screen;
    r.innerHTML = `${html}<div class="pt-live pt-sr" role="status" aria-live="polite"></div><div class="pt-news" aria-hidden="true"></div>`;
    r.scrollTop = 0;
    if (!r.hidden && !r.contains(document.activeElement)) r.focus({ preventScroll: true });
  }
  const loadingHtml = (text) => `<div class="pt-loading" role="status"><span class="pt-spin" aria-hidden="true"></span>${e(text)}</div>`;
  const top = (title, back) => `<div class="pt-top">
      <button type="button" class="pt-round" data-pt="${back ? "home" : "close"}" aria-label="${back ? "Retour" : "Fermer"}">${back ? "‹" : "✕"}</button>
      <h1 class="pt-title">${e(title)}</h1>
      ${window.GameAudio?.button ? window.GameAudio.button() : '<span class="pt-round-gap"></span>'}</div>`;

  async function open(fromEl) {
    opener = fromEl || document.activeElement;
    const r = panel();
    const wasHidden = r.hidden;
    r.hidden = false;
    document.documentElement.classList.add("pt-open");
    if (wasHidden) window.Nav?.open?.({ key: "pet", kind: "sheet", el: r, surface: r, gestures: false, selfAnimated: true, close: onBack });
    show(loadingHtml("Réveil de ton compagnon…"), "loading");
    r.focus({ preventScroll: true });
    await refresh();
  }
  function close(fromBack) {
    clearTimers();
    stopGame();
    screenSeq += 1;
    if (!root || root.hidden) return;
    root.hidden = true;
    root.innerHTML = "";
    document.documentElement.classList.remove("pt-open");
    if (!fromBack) window.Nav?.closed?.("pet");
    try { opener?.focus?.(); } catch { /* bouton disparu */ }
  }
  function onBack() {
    if (!root || root.hidden) return;
    const sub = ["outfits", "friends", "visit", "play", "rename"].includes(root.dataset.screen);
    if (!sub) return close(true);
    stopGame();
    root.dataset.screen === "visit" ? showFriends() : home();
    queueMicrotask(() => window.Nav?.open?.({ key: "pet", kind: "sheet", el: root, surface: root, gestures: false, selfAnimated: true, close: onBack }));
  }

  // ── Serveur ──
  async function token() {
    try { return typeof freshToken === "function" ? await freshToken() : null; } catch { return null; }
  }
  async function api(path, body) {
    const t = await token();
    if (!t) { const err = new Error("login"); err.login = true; throw err; }
    let r;
    try {
      r = await fetch(`/api/pet/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: t, ...body }) });
    } catch { throw new Error("Pas de réseau. Réessaie dans un instant."); }
    let data = null;
    try { data = await r.json(); } catch { /* réponse vide */ }
    if (r.status === 401) { const err = new Error("Ta connexion a expiré, reconnecte-toi."); err.login = true; throw err; }
    if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Ton compagnon ne répond pas. Réessaie dans un instant.");
    return data;
  }
  async function refresh() {
    const mine = screenSeq;
    try {
      const data = await api("me", {});
      if (!root || root.hidden || mine !== screenSeq) return;
      pet = data.pet;
      home();
      announce(data.news);
    } catch (err) {
      if (!root || root.hidden || mine !== screenSeq) return;
      err.login ? loginScreen() : errorScreen(err.message);
    }
  }

  // ── Écrans ──
  function art(p, cls = "") {
    const label = `${p.name}, ${STAGES[p.stage] || ""} ${EMOTIONS[p.emotion] || ""}`.trim();
    const svg = skin()?.render({ stage: p.stage, variant: p.variant, emotion: p.emotion, outfit: p.outfit, label }) || "";
    return `<div class="pt-art ${cls}" style="--pt-mood:${skin()?.moodColor(p.emotion) || "#5ee7ff"}">${svg}</div>`;
  }
  function loginScreen() {
    const preview = skin()?.render({ stage: "adult", variant: "star", emotion: "happy", outfit: "noeud", label: creatureName() }) || "";
    show(`${top(GAME_NAME)}<div class="pt-card pt-login">
      <div class="pt-art">${preview}</div>
      <h2>Adopte ton ${e(creatureName())}</h2>
      <p class="pt-muted">Un petit compagnon à faire grandir chaque jour : nourris-le, joue avec lui, rends visite à ceux de tes amis.
      Connecte-toi pour qu'il te suive sur tous tes appareils.</p>
      <button type="button" class="pt-cta" data-pt="login">Me connecter</button></div>`, "login");
  }
  function errorScreen(message) {
    show(`${top(GAME_NAME)}<div class="pt-card"><p>${e(message)}</p><button type="button" class="pt-cta" data-pt="retry">Réessayer</button></div>`, "error");
  }
  const hm = (hours) => {
    const h = Math.max(0, Math.floor(hours)), d = Math.floor(h / 24);
    return d ? `${d} j ${h % 24} h` : `${h} h`;
  };
  const countdown = (sec) => {
    const s = Math.max(0, Math.round(sec)), d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return d ? `${d} j ${h} h` : h ? `${h} h ${m} min` : m ? `${m} min ${String(s % 60).padStart(2, "0")} s` : `${s} s`;
  };

  function home() {
    if (!pet) return;
    if (pet.stage === "egg") return eggScreen();
    if (pet.stage === "dead") return memorialScreen();
    const p = pet, stage = [STAGES[p.stage], VARIANTS[p.variant]].filter(Boolean).join(" ");
    const gauges = GAUGES.map(([k, label, icon]) => {
      const v = p.gauges[k], low = v < 25 ? " pt-low" : "";
      return `<li class="pt-gauge${low}"><span class="pt-g-ico" aria-hidden="true">${icon}</span><span class="pt-g-l">${label}</span>
        <span class="pt-bar" role="meter" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${v}" aria-valuetext="${label} ${v} sur 100"><i style="--v:${v}%"></i></span></li>`;
    }).join("");
    const acts = ACTIONS.map(([a, label, icon]) => {
      const left = p.left[a], off = p.asleep || left <= 0;
      return `<button type="button" class="pt-act" data-pt="act" data-a="${a}" ${off ? 'aria-disabled="true"' : ""} aria-label="${label}, encore ${left} aujourd'hui">
        <span class="pt-act-i" aria-hidden="true">${icon}</span><span>${label}</span><small aria-hidden="true">${left}/${p.limits[a]}</small></button>`;
    }).join("");
    const light = p.asleep
      ? `<button type="button" class="pt-act pt-light" data-pt="act" data-a="wake"><span class="pt-act-i" aria-hidden="true">💡</span><span>Rallumer</span></button>`
      : `<button type="button" class="pt-act pt-light" data-pt="act" data-a="sleep"><span class="pt-act-i" aria-hidden="true">🌙</span><span>Dodo</span></button>`;
    const danger = p.danger ? `<p class="pt-danger" role="alert">💜 ${e(p.name)} a très faim depuis un moment : un repas et tout ira bien.</p>` : "";
    const next = p.next_stage_in != null ? `<span class="pt-chip">⏳ ${p.stage === "baby" ? "Ado" : "Adulte"} dans ${countdown(p.next_stage_in)}</span>` : "";
    show(`${top(p.name)}
      <div class="pt-hero${p.asleep ? " pt-night" : ""}">
        <div class="pt-chips"><span class="pt-chip">${e(stage)}</span><span class="pt-chip">🎂 ${hm(p.age_hours)}</span>
          <span class="pt-chip" aria-label="Série de ${p.streak} jours">🔥 ${p.streak}</span>${next}</div>
        <button type="button" class="pt-stage" data-pt="pet" aria-label="Caresser ${e(p.name)}">${art(p)}</button>
        <p class="pt-line">${e(p.line)}</p>${danger}
      </div>
      <ul class="pt-gauges">${gauges}</ul>
      <div class="pt-acts">${acts}${light}</div>
      <div class="pt-more">
        <button type="button" class="pt-ghost" data-pt="outfits">👕 Tenues</button>
        <button type="button" class="pt-ghost" data-pt="friends">👫 Amis</button>
        <button type="button" class="pt-ghost" data-pt="rename">✏️ Nom</button>
      </div>
      <p class="pt-muted pt-small">Bonus : une partie de Méninges, une partie de Party ou une soirée lui font plaisir.
        Record : ${hm(p.record_hours)} · meilleure série : ${p.best_streak} 🔥</p>`, "home");
    if (p.next_stage_in != null && p.next_stage_in < 3600) scheduleRefresh(p.next_stage_in);
  }
  function scheduleRefresh(sec) {
    const mine = screenSeq;
    later(() => { if (mine === screenSeq) refresh(); }, Math.max(1, sec) * 1000 + 500);
  }

  function eggScreen() {
    const p = pet;
    show(`${top(p.name)}<div class="pt-hero pt-egg">
      <div class="pt-stage pt-wobble">${art(p)}</div>
      <p class="pt-line">${e(p.line)}</p>
      <p class="pt-count" aria-live="off">Éclosion dans <b data-pt-count>${countdown(p.next_stage_in)}</b></p>
      <form class="pt-name" data-pt-form="rename"><label for="ptName">Son nom</label>
        <div class="pt-name-row"><input id="ptName" name="name" maxlength="20" autocomplete="off" value="${e(p.name)}">
        <button type="submit" class="pt-ghost">OK</button></div></form>
      <p class="pt-muted pt-small">Garde un œil sur lui : bébé pendant 1 jour, ado pendant 3, puis adulte. Selon tes soins, il deviendra
        « étoile » ✨, classique ou « rebelle » 😜.</p></div>`, "egg");
    let left = p.next_stage_in;
    every(() => {
      left -= 1;
      const el = root?.querySelector("[data-pt-count]");
      if (el) el.textContent = countdown(left);
      if (left <= 0) { clearTimers(); hatchLater(); }
    }, TICK_MS);
  }
  function hatchLater() {
    if (!calm()) root?.querySelector(".pt-stage")?.classList.add("pt-hatch");
    cue("win");
    buzz([30, 60, 30]);
    later(refresh, calm() ? 200 : 900);
  }

  function memorialScreen() {
    const p = pet;
    const list = (p.memorial || []).map((m) => `<li><b>${e(m.name)}</b> <span class="pt-muted">n° ${m.gen} · ${hm(m.hours)}</span></li>`).join("");
    show(`${top(p.name)}<div class="pt-hero pt-memo">
      <div class="pt-stage">${art(p)}</div>
      <h2>${e(p.name)} s'est envolé</h2>
      <p>Il a vécu <b>${hm(p.age_hours)}</b> à tes côtés. Merci pour tous ces moments ✨</p>
      <p class="pt-muted">Ton record : ${hm(p.record_hours)} · meilleure série : ${p.best_streak} 🔥<br>Tes tenues restent à toi.</p>
      <button type="button" class="pt-cta" data-pt="act" data-a="new_egg">🥚 Faire éclore un nouvel œuf</button>
      ${list ? `<h3>Souvenirs</h3><ul class="pt-memo-list">${list}</ul>` : ""}</div>`, "memorial");
  }

  function outfitsScreen() {
    const p = pet;
    const tiles = [{ id: "", label: "Sans tenue", emoji: "🚫", hint: "", unlocked: true }, ...p.outfits].map((o) => {
      const on = (p.outfit || "") === o.id;
      return `<button type="button" class="pt-tile${on ? " on" : ""}" data-pt="wear" data-o="${e(o.id)}" ${o.unlocked ? "" : 'aria-disabled="true"'} aria-pressed="${on}">
        <span class="pt-tile-i" aria-hidden="true">${o.unlocked ? o.emoji : "🔒"}</span><b>${e(o.label)}</b>${o.unlocked ? "" : `<small>${e(o.hint)}</small>`}</button>`;
    }).join("");
    show(`${top("Tenues", true)}<div class="pt-hero">${art(p, "pt-small-art")}</div><div class="pt-tiles">${tiles}</div>`, "outfits");
  }

  function renameScreen() {
    show(`${top("Son nom", true)}<div class="pt-card"><form class="pt-name" data-pt-form="rename"><label for="ptName">Comment s'appelle-t-il ?</label>
      <div class="pt-name-row"><input id="ptName" name="name" maxlength="20" autocomplete="off" value="${e(pet.name)}">
      <button type="submit" class="pt-cta">Valider</button></div></form></div>`, "rename");
    root.querySelector("#ptName")?.focus();
  }

  // ── Amis ──
  async function showFriends() {
    show(`${top("Les compagnons de tes amis", true)}${loadingHtml("Visite en cours…")}`, "friends");
    const mine = screenSeq;
    try {
      const data = await api("friends", {});
      if (mine !== screenSeq) return;
      friends = data.friends || [];
      const list = friends.map((f) => `<li><button type="button" class="pt-friend" data-pt="visit" data-id="${e(f.id)}">
        ${art(f.pet, "pt-mini")}<span><b>${e(f.pet.name)}</b><small>chez ${e(f.member)} · ${e(STAGES[f.pet.stage] || "")}</small></span>
        <span aria-hidden="true">${f.gifted ? "💜" : "›"}</span></button></li>`).join("");
      show(`${top("Les compagnons de tes amis", true)}${list ? `<ul class="pt-friends">${list}</ul>`
        : `<div class="pt-card"><p>Personne de tes groupes n'a encore de compagnon. Invite-les à adopter le leur !</p></div>`}
        <p class="pt-muted pt-small">Tu vois les compagnons des membres de tes groupes. Un câlin ou un goûter par ami et par jour.</p>`, "friends");
    } catch (err) {
      if (mine === screenSeq) err.login ? loginScreen() : errorScreen(err.message);
    }
  }
  function visitScreen(f) {
    const p = f.pet, alive = !["egg", "dead"].includes(p.stage);
    const gifts = !alive ? `<p class="pt-muted">${p.stage === "egg" ? "Il est encore dans son œuf." : "Il s'est envolé."}</p>`
      : f.gifted ? `<p class="pt-line pt-gifted">💜 Tu lui as déjà fait plaisir aujourd'hui. Reviens demain !</p>`
        : `<div class="pt-acts pt-acts-2"><button type="button" class="pt-act" data-pt="gift" data-k="hug" data-id="${e(f.id)}"><span class="pt-act-i" aria-hidden="true">🤗</span><span>Un câlin</span></button>
           <button type="button" class="pt-act" data-pt="gift" data-k="snack" data-id="${e(f.id)}"><span class="pt-act-i" aria-hidden="true">🍪</span><span>Un goûter</span></button></div>`;
    show(`${top(p.name, true)}<div class="pt-hero"><div class="pt-chips"><span class="pt-chip">chez ${e(f.member)}</span>
      <span class="pt-chip">${e([STAGES[p.stage], VARIANTS[p.variant]].filter(Boolean).join(" "))}</span><span class="pt-chip">🎂 ${hm(p.age_hours)}</span></div>
      <div class="pt-stage">${art(p)}</div><p class="pt-line">${e(p.line)}</p></div>${gifts}`, "visit");
  }

  // ── Mini-jeu : « Attrape les notes » (20 s) ──
  function startGame() {
    const name = pet.name;
    show(`${top(`Jouer avec ${name}`, true)}<div class="pt-game">
      <p class="pt-muted">Touche les notes avant qu'elles ne s'envolent ! ${e(name)} adore ça.</p>
      <div class="pt-timer" aria-hidden="true"><i></i></div>
      <div class="pt-field" data-pt-field aria-label="Terrain de jeu"></div>
      <p class="pt-score" aria-live="polite"><b data-pt-hits>0</b> note(s)</p></div>`, "play");
    const field = root.querySelector("[data-pt-field]"), bar = root.querySelector(".pt-timer i");
    game = { hits: 0, spawned: 0, end: Date.now() + PLAY_MS, seq: screenSeq };
    cue("start");
    bar.style.setProperty("--d", `${PLAY_MS}ms`);
    requestAnimationFrame(() => bar.classList.add("go"));
    every(() => spawnNote(field), SPAWN_MS);
    later(endGame, PLAY_MS);
  }
  function spawnNote(field) {
    if (!game || !field.isConnected) return;
    game.spawned += 1;
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pt-note";
    b.dataset.pt = "note";
    b.textContent = ["🎵", "🎶", "✨", "🪩"][game.spawned % 4];
    b.setAttribute("aria-label", "Note");
    b.style.left = `${8 + Math.random() * 76}%`;
    b.style.top = `${8 + Math.random() * 72}%`;
    field.append(b);
    later(() => b.remove(), calm() ? NOTE_MS_CALM : NOTE_MS);
  }
  function stopGame() { game = null; }
  async function endGame() {
    if (!game) return;
    const score = game.spawned ? Math.round(Math.min(100, (100 * game.hits) / Math.max(1, game.spawned * 0.8))) : 0;
    const hits = game.hits;
    stopGame();
    clearTimers();
    show(loadingHtml(`${hits} note(s) attrapée(s) !`), "loading");
    await doAct("play", { score });
  }

  // ── Actions ──
  async function doAct(action, extra = {}) {
    if (busy) return;
    busy = true;
    const mine = screenSeq;
    try {
      const data = await api("act", { action, ...extra });
      pet = data.pet;
      if (!root || root.hidden) return;
      home();
      react(action);
      announce(data.news);
    } catch (err) {
      if (err.login) return loginScreen();
      if (root?.dataset.screen === "loading" || mine !== screenSeq) home();   // fin du mini-jeu : retour à l'accueil
      say(err.message, true);
      cue("lose");
    } finally {
      busy = false;
    }
  }
  const REACT = { feed: ["😋 Miam !", "win", 40], play: ["🎉 Trop bien !", "win", [30, 50, 30]], cuddle: ["💜", "turn", 25],
    heal: ["✨ Tout propre !", "reveal", 40], sleep: ["🌙 Bonne nuit", "card", 20], wake: ["☀️ Debout !", "start", 20],
    new_egg: ["🥚 Un nouvel œuf !", "start", [30, 60, 30]], outfit: ["👕 Ça lui va bien !", "card", 20], rename: ["✏️ C'est noté", "card", 15] };
  function react(action) {
    const [text, sound, vib] = REACT[action] || ["", "turn", 20];
    cue(sound);
    buzz(vib);
    const stage = root?.querySelector(".pt-stage");
    if (stage && !calm()) { stage.classList.remove("pt-bounce"); void stage.offsetWidth; stage.classList.add("pt-bounce"); }
    if (text) burst(text);
  }
  function burst(text) {
    const box = root?.querySelector(".pt-news");
    if (!box) return;
    const el = document.createElement("div");
    el.className = "pt-burst";
    el.textContent = text;
    box.append(el);
    later(() => el.remove(), 1400);
  }
  function say(text, isError) {
    const live = root?.querySelector(".pt-live");
    if (live) live.textContent = text;
    const box = root?.querySelector(".pt-news");
    if (!box) return;
    const el = document.createElement("div");
    el.className = `pt-toast${isError ? " pt-err" : ""}`;
    el.textContent = text;
    box.append(el);
    later(() => el.remove(), NEWS_MS);
  }
  function announce(news) {
    (news || []).forEach((n, i) => later(() => {
      say(n.text);
      if (["evolved", "hatched", "unlocked"].includes(n.kind)) { cue("win"); buzz([30, 60, 30]); }
    }, 300 + i * 900));
  }

  // ── Touchers ──
  function onClick(ev) {
    const b = ev.target.closest("[data-pt]");
    if (!b || !root.contains(b)) return;
    if (b.getAttribute("aria-disabled") === "true") {
      const a = b.dataset.a;
      say(pet?.asleep && a ? "Chut, il dort 🌙 Rallume la lumière pour le réveiller." : b.dataset.pt === "wear" ? "Pas encore débloquée : " + (b.querySelector("small")?.textContent || "") : "C'est tout pour aujourd'hui, reviens demain 💜");
      return;
    }
    switch (b.dataset.pt) {
      case "close": return close();
      case "home": stopGame(); return root.dataset.screen === "visit" ? showFriends() : home();
      case "retry": show(loadingHtml("Réveil de ton compagnon…"), "loading"); return refresh();
      case "login": close(); return typeof showTab === "function" && showTab("account");
      case "act": return b.dataset.a === "play" ? startGame() : doAct(b.dataset.a);
      case "pet": return pet && !pet.asleep && pet.left.cuddle > 0 ? doAct("cuddle") : react("");
      case "outfits": return outfitsScreen();
      case "wear": return doAct("outfit", { outfit: b.dataset.o || "" }).then(() => root?.dataset.screen === "home" && outfitsScreen());
      case "rename": return renameScreen();
      case "friends": return showFriends();
      case "visit": { const f = friends?.find((x) => x.id === b.dataset.id); return f && visitScreen(f); }
      case "gift": return gift(b.dataset.id, b.dataset.k);
      case "note":
        if (!game) return;
        game.hits += 1;
        b.classList.add("pt-caught");
        b.disabled = true;
        later(() => b.remove(), 220);
        cue("card");
        buzz(10);
        root.querySelector("[data-pt-hits]").textContent = String(game.hits);
        return;
      default:
    }
  }
  function onSubmit(ev) {
    const form = ev.target.closest("[data-pt-form]");
    if (!form) return;
    ev.preventDefault();
    const name = String(new FormData(form).get("name") || "").trim();
    if (!name) return say("Choisis un nom (20 lettres au plus).", true);
    doAct("rename", { name });
  }
  async function gift(id, kind) {
    if (busy) return;
    busy = true;
    try {
      const card = await api("gift", { friend: id, kind });
      friends = (friends || []).map((f) => (f.id === id ? card : f));
      visitScreen(card);
      cue("win");
      buzz([20, 40, 20]);
      burst(kind === "hug" ? "🤗 Câlin envoyé !" : "🍪 Goûter offert !");
    } catch (err) {
      if (err.login) return loginScreen();
      say(err.message, true);
    } finally {
      busy = false;
    }
  }

  // Carte de l'onglet Jeux (data-pet-open) et lien direct (?pet=1, notifications).
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-pet-open]");
    if (b) open(b);
  });
  document.querySelectorAll("[data-pet-name]").forEach((el) => { el.textContent = GAME_NAME; });
  // Icône de la carte (games.js est chargé avant le skin) : dessinée par le skin en place.
  document.querySelectorAll(".g-pt-ico").forEach((el) => {
    if (skin()) el.innerHTML = skin().render({ stage: "adult", variant: "star", emotion: "party", outfit: "noeud" });
  });
  try {
    if (new URLSearchParams(location.search).get("pet") === "1") setTimeout(() => open(null), 300);
  } catch { /* adresse illisible */ }

  window.Pet = Object.freeze({ open, close, name: GAME_NAME });
})();
