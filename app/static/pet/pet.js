// 🥚 Compagnon : personnage à entretenir (façon Tamagotchi). Panneau plein écran position: fixed (#petRoot), jamais de
// règle de hauteur ou de défilement sur html/body (bug iOS 26, voir CLAUDE.md). La vie est calculée par le serveur
// (/api/pet/*, app/pet.py) ; le dessin vient de la couche graphique remplaçable window.PetSkin (pet/skin.js).
// Compte requis (le personnage vit sur tous les appareils) ; sans compte : invitation à se connecter.
// Boucle du jour (lot 1 « revenir tous les jours », app/pet_loop.py) : coffre du jour (tiré par le serveur), série 🔥
// protégée, missions, rituels du matin et du soir, pièces. Chaque ouverture dit d'où elle vient (src, mesure).
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
  const SPECIES = "Zicou";   // le nom de la mascotte (app/pet.py DEFAULT_NAME), quel que soit le skin
  const creatureName = () => skin()?.creatureName || SPECIES;
  const CHEST_MS = 900, CHEST_MS_CALM = 120;
  const ODDS = { coins: "Pièces (10 à 30)", object: "Objet : goûter rare ou sticker", piece: "Morceau de tenue (3 = une tenue)", rare: "Tenue rare" };
  const FOUND_HINT = { coins: "Rangées dans ta tirelire : la boutique arrive bientôt 🪙", snack: "Rangé dans ton sac : offre-le-lui quand il a un creux",
    sticker: "Collé dans ton album de stickers", piece: "Encore quelques morceaux et la tenue est à lui", outfit: "Une tenue rare ! Elle l'attend dans ses tenues" };
  const FAMILY_ICON = { care: "🧼", game: "🎮", social: "👫" };
  const COUNTER_ICON = { feed: "🍕", cuddle: "🤗", heal: "🧼", play: "🎵", score40: "🎵", brain: "🧠", visit: "👫", gift: "🎁" };
  const QUEUED = ["feed", "cuddle", "heal"];   // deux touchers rapides : le 2e attend son tour (jamais perdu en silence)
  const today = () => new Date().toLocaleDateString("fr-CA", { timeZone: "Europe/Zurich" });
  const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* navigation privée */ } } };

  // ── Minuteurs : tous arrêtés à la fermeture ──
  const timers = new Set();
  function later(fn, ms) { const id = setTimeout(() => { timers.delete(id); fn(); }, ms); timers.add(id); return id; }
  function every(fn, ms) { const id = setInterval(fn, ms); timers.add(id); return id; }
  function clearTimers() { for (const id of timers) { clearTimeout(id); clearInterval(id); } timers.clear(); }

  // ── Panneau ──
  let root = null, opener = null, pet = null, friends = null, busy = false, game = null, screenSeq = 0;
  let openSrc = "tab", counted = false;   // la 1re lecture après l'ouverture compte une ouverture (pet_opens), pas les suivantes
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
    r.innerHTML = `${html}<div class="pt-live pt-sr" role="status" aria-live="polite"></div><div class="pt-news" aria-hidden="true"></div>`
      + `<div class="pt-bursts" aria-hidden="true"></div>`;
    r.scrollTop = 0;
    if (!r.hidden && !r.contains(document.activeElement)) r.focus({ preventScroll: true });
  }
  const loadingHtml = (text) => `<div class="pt-loading" role="status"><span class="pt-spin" aria-hidden="true"></span>${e(text)}</div>`;
  const top = (title, back) => `<div class="pt-top">
      <button type="button" class="pt-round" data-pt="${back ? "home" : "close"}" aria-label="${back ? "Retour" : "Fermer"}">${back ? "‹" : "✕"}</button>
      <h1 class="pt-title">${e(title)}</h1>
      ${window.GameAudio?.button ? window.GameAudio.button() : '<span class="pt-round-gap"></span>'}</div>`;

  async function open(fromEl, src) {
    opener = fromEl || document.activeElement;
    openSrc = src || (fromEl ? "tab" : "link");
    counted = false;
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
    const sub = ["outfits", "friends", "visit", "play", "result", "rename", "streak", "treasures", "odds", "reveal", "coll", "report"].includes(root.dataset.screen);
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
      const src = counted ? "none" : openSrc;
      counted = true;
      const data = await api("me", { src });
      if (!root || root.hidden || mine !== screenSeq) return;
      pet = data.pet;
      home();
      announce(data.news);
      if (pet.coll?.reveals?.length && window.PetCollection) window.PetCollection.reveals(pet.coll.reveals);
    } catch (err) {
      if (!root || root.hidden || mine !== screenSeq) return;
      err.login ? loginScreen() : errorScreen(err.message);
    }
  }

  // ── Écrans ──
  function art(p, cls = "", extra) {
    const label = `${p.name}, ${STAGES[p.stage] || ""} ${EMOTIONS[p.emotion] || ""}`.trim();
    const acc = { ...(p.coll?.acc || p.acc || {}), ...(extra || {}) };   // collection : un accessoire par emplacement
    const shiny = Boolean(p.coll?.shiny ?? p.shiny);
    const svg = skin()?.render({ stage: p.stage, variant: p.variant, emotion: p.emotion, outfit: Object.keys(acc).length ? null : p.outfit,
      accessories: acc, shiny, label: shiny ? `${label}, shiny` : label }) || "";
    return `<div class="pt-art ${cls}" style="--pt-mood:${skin()?.moodColor(p.emotion) || "#5ee7ff"}">${svg}</div>`;
  }
  function loginScreen() {
    const preview = skin()?.render({ stage: "adult", variant: "star", emotion: "happy", outfit: "noeud", label: SPECIES }) || "";
    show(`${top(GAME_NAME)}<div class="pt-card pt-login">
      <div class="pt-art">${preview}</div>
      <h2>Adopte ton ${SPECIES}</h2>
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
      return `<li class="pt-gauge${low}"><span class="pt-g-ico" aria-hidden="true">${icon}</span><span class="pt-g-l">${label} <b class="pt-g-v" aria-hidden="true">${v}</b></span>
        <span class="pt-bar" role="meter" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${v}" aria-valuetext="${label} ${v} sur 100"><i style="--v:${v}%"></i></span></li>`;
    }).join("");
    const acts = ACTIONS.map(([a, label, icon]) => {
      const left = p.left[a], off = p.asleep || left <= 0;
      return `<button type="button" class="pt-act" data-pt="act" data-a="${a}" ${off ? 'aria-disabled="true"' : ""} aria-label="${label}, encore ${left} aujourd'hui">
        <span class="pt-act-i" aria-hidden="true">${icon}</span><span>${label}</span><small aria-hidden="true">reste ${left}</small></button>`;
    }).join("");
    const light = p.asleep
      ? `<button type="button" class="pt-act pt-light" data-pt="act" data-a="wake"><span class="pt-act-i" aria-hidden="true">💡</span><span>Rallumer</span></button>`
      : `<button type="button" class="pt-act pt-light" data-pt="act" data-a="sleep"><span class="pt-act-i" aria-hidden="true">🌙</span><span>Dodo</span></button>`;
    const danger = alertCard(p);
    const next = p.next_stage_in != null ? `<span class="pt-chip">⏳ ${p.stage === "baby" ? "Ado" : "Adulte"} dans ${countdown(p.next_stage_in)}</span>` : "";
    show(`${top(p.name)}
      <div class="pt-hero${p.asleep ? " pt-night" : ""}">
        <div class="pt-chips"><span class="pt-chip">${e(stage)}</span><span class="pt-chip">🎂 ${hm(p.age_hours)}</span>
          ${streakChip(p)}${coinChip(p)}${next}</div>
        <button type="button" class="pt-stage" data-pt="pet" aria-label="Caresser ${e(p.name)}">${art(p)}</button>
        <p class="pt-line${p.alert ? " pt-warn" : ""}">${e(p.line)}</p>
      </div>
      ${danger}
      <ul class="pt-gauges">${gauges}</ul>
      <div class="pt-acts">${acts}${light}</div>
      ${dailyTop(p)}
      ${dailyBottom(p)}
      <div class="pt-more">
        <button type="button" class="pt-ghost" data-pt="coll" data-s="wear">👕 Garde-robe</button>
        <button type="button" class="pt-ghost" data-pt="coll" data-s="dex">📖 Zicoudex${p.coll?.dex ? ` <small>${p.coll.dex.have}/${p.coll.dex.total}</small>` : ""}</button>
        <button type="button" class="pt-ghost" data-pt="coll" data-s="shop">🛍️ Boutique</button>
        <button type="button" class="pt-ghost" data-pt="coll" data-s="craft">🔨 Atelier</button>
        <button type="button" class="pt-ghost" data-pt="treasures">💎 Trésors</button>
        <button type="button" class="pt-ghost" data-pt="friends">👫 Amis</button>
        <button type="button" class="pt-ghost" data-pt="rename">✏️ Nom</button>
      </div>
      <p class="pt-muted pt-small">Bonus : une partie de Méninges, une partie de Party ou une soirée lui font plaisir.
        Record : ${hm(p.record_hours)} · meilleure série : ${p.best_streak} 🔥</p>`, "home");
    if (p.next_stage_in != null && p.next_stage_in < 3600) scheduleRefresh(p.next_stage_in);
  }
  // Avertissement AVANT l'envol, bien visible, avec le geste qui règle tout (playtest « Léa »). Jamais culpabilisant.
  function alertCard(p) {
    const a = p.alert;
    if (!a) return "";
    const feed = p.asleep || p.left.feed <= 0 ? "" : `<button type="button" class="pt-cta" data-pt="alert-feed">🍕 Nourrir ${e(p.name)}</button>`;
    if (a.kind === "starving") {
      const when = a.hours_left > 1 ? `dans environ ${a.hours_left} h` : "très bientôt";
      return `<div class="pt-card pt-danger" role="alert"><b>💜 ${e(p.name)} a très faim depuis un moment</b>
        <p>Sans repas, il s'envolera ${when}. Un repas et tout ira bien.</p>${feed}</div>`;
    }
    return "";   // petit creux : la ligne d'humeur, surlignée, le dit déjà (sans pousser les boutons hors de l'écran)
  }
  // ── Boucle du jour ──
  function streakChip(p) {
    const s = p.daily?.streak, n = s ? s.count : p.streak, ice = s?.freezes ? ` ❄️${s.freezes}` : "";
    return `<button type="button" class="pt-chip pt-chip-btn" data-pt="streak" aria-label="Série de ${n} jours${s?.freezes ? `, ${s.freezes} gel(s)` : ""}">🔥 ${n}${ice}</button>`;
  }
  const coinChip = (p) => p.daily ? `<button type="button" class="pt-chip pt-chip-btn" data-pt="treasures" aria-label="${p.daily.coins} pièces">🪙 ${p.daily.coins}</button>` : "";
  const dayLabel = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("fr-CH", { weekday: "long" });
  function dailyTop(p) {
    const d = p.daily;
    if (!d) return "";
    const morning = d.morning && store.get("pt_morning") !== today()
      ? `<div class="pt-card pt-morning"><button type="button" class="pt-x" data-pt="morning-close" aria-label="Fermer la carte du réveil">✕</button>
          <b>☀️ Bonjour !</b><p>${e(d.morning)}</p></div>` : "";
    const r = d.streak.repair;
    const repair = r ? `<p class="pt-repair">🔥 Ta série de <b>${r.was} jours</b> peut revenir : <span class="${r.brain ? "ok" : ""}">🧠 une partie de Méninges${r.brain ? " ✓" : ""}</span>
        + <span class="${r.care ? "ok" : ""}">🧼 un soin${r.care ? " ✓" : ""}</span>, jusqu'à ${e(dayLabel(r.until))} soir.</p>` : "";
    const f = d.chest.found;
    const chest = d.chest.state === "ready"
      ? `<div class="pt-chest-row"><button type="button" class="pt-chest" data-pt="chest"><span class="pt-chest-i" aria-hidden="true">🎁</span>
          <span><b>${e(p.name)} a trouvé un truc !</b><small>Touche pour l'ouvrir · jusqu'à minuit</small></span></button>
          <button type="button" class="pt-info" data-pt="odds" aria-label="Chances du coffre">i</button></div>`
      : `<p class="pt-chest-done">Coffre du jour : ${f ? `${e(f.emoji)} ${e(f.label)}` : "ouvert"} · un nouveau demain 🎁</p>`;
    const rule = d.streak.today ? "" : `<p class="pt-rule">🔥 Pour que la journée compte : un soin à ${e(p.name)} ou un cadeau à un ami</p>`;
    const alive = !["egg", "dead"].includes(p.stage);
    const evening = d.evening && alive ? (d.evening.tucked
      ? `<p class="pt-chest-done">🌙 Bordé pour la nuit : demain matin, nuit douce</p>`
      : `<button type="button" class="pt-cta pt-tuck" data-pt="act" data-a="tuck">🌙 Le coucher : border ${e(p.name)}</button>`) : "";
    return morning + repair + chest + rule + evening;
  }
  function dailyBottom(p) {
    const d = p.daily;
    if (!d || !d.missions.length) return "";
    const items = d.missions.map((m) => {
      const done = m.have >= m.need;
      return `<li class="${done ? "done" : ""}"><span aria-hidden="true">${done ? "✅" : COUNTER_ICON[m.counter] || FAMILY_ICON[m.family] || "🎯"}</span>
        <span>${e(m.text)}</span><small aria-label="${m.have} sur ${m.need}">${m.have}/${m.need}</small></li>`;
    }).join("");
    const bonus = d.bonus === "ready" ? `<button type="button" class="pt-cta pt-bonus" data-pt="bonus">🎁 Ouvrir le coffre bonus</button>`
      : d.bonus === "opened" ? `<p class="pt-muted">Coffre bonus : ${d.bonus_found ? `${e(d.bonus_found.emoji)} ${e(d.bonus_found.label)}` : "ouvert"}</p>`
        : `<p class="pt-muted pt-tiny">3 missions sur 3 → un coffre bonus 🎁</p>`;
    const w = d.week;
    const week = w ? `<div class="pt-week${w.done ? " done" : ""}"><b>Mission de la semaine</b><span>${e(w.text)}</span>
        <small>${w.done ? "✅ réussie" : `${w.have}/${w.need}`} · ${w.coins} pièces</small></div>` : "";
    const bag = d.bag.length ? `<div class="pt-bag"><b>Sac</b>${d.bag.map((b) => `<button type="button" class="pt-ghost" data-pt="treat" data-i="${e(b.id)}"
        aria-label="Donner : ${e(b.label)} (${b.n})">${e(b.emoji)} ×${b.n}</button>`).join("")}</div>` : "";
    return `<section class="pt-card pt-missions" aria-label="Missions du jour"><h2>🎯 Missions du jour</h2><ul>${items}</ul>${bonus}${week}</section>${bag}`;
  }
  function streakScreen() {
    const s = pet.daily?.streak;
    if (!s) return home();
    const ice = "❄️".repeat(s.freezes) + `<span class="pt-off">${"❄️".repeat(Math.max(0, s.max_freezes - s.freezes))}</span>`;
    const respite = s.respite === "friday" ? `<p class="pt-tip">🎉 C'est vendredi : passer aujourd'hui protège ta série demain samedi.</p>`
      : s.respite === "saturday" ? `<p class="pt-tip">😴 Samedi en répit : tu es passé hier, ta série est protégée aujourd'hui.</p>` : "";
    const miles = s.milestones.map((m) => `<li class="${m.reached ? "done" : ""}"><b>${m.days} j</b><span>${e(m.reward)}</span><span aria-hidden="true">${m.reached ? "✅" : "🔒"}</span></li>`).join("");
    show(`${top("Ta série", true)}<div class="pt-card pt-streak">
      <div class="pt-big" aria-label="${s.count} jours">🔥 ${s.count}</div>
      <p>${s.count ? "jours d'affilée avec lui" : "Ta série commence dès aujourd'hui"} · record ${s.best}</p>
      <p class="pt-freezes" aria-label="${s.freezes} gel(s) sur ${s.max_freezes}">${ice} <small>Gels : ${s.freezes}/${s.max_freezes} · +1 tous les 7 jours</small></p>
      ${respite}
      ${s.next ? `<p class="pt-next">Prochain palier : <b>${s.next.days} j</b> → ${e(s.next.reward)}</p>` : ""}
      <ol class="pt-miles">${miles}</ol>
      <p class="pt-muted pt-small">Un jour compte dès que tu t'occupes de lui (un repas, un jeu, un câlin, une toilette) ou que tu fais un cadeau à un ami :
        le coffre seul ne suffit pas.
        Chaque palier se gagne une fois. Un gel protège un jour de pause.
        Samedi en répit : passer le vendredi protège le samedi. Série cassée ? Elle peut revenir sous 48 h (une partie de Méninges + un soin), une fois par mois.</p></div>`, "streak");
  }
  function treasuresScreen() {
    const d = pet.daily;
    if (!d) return home();
    const pieces = d.pieces.map((x) => `<li><span aria-hidden="true">${e(x.emoji)}</span><span>${e(x.label)}</span><small>${x.have}/${x.need} morceaux</small></li>`).join("");
    const empty = Math.max(0, d.stickers.total - d.stickers.have.length);
    const album = d.stickers.have.map((x) => `<span>${e(x)}</span>`).join("") + `<span class="pt-off">?</span>`.repeat(empty);
    const bag = d.bag.length ? d.bag.map((b) => `${e(b.emoji)} ${e(b.label)} ×${b.n}`).join(" · ") : "Vide pour l'instant";
    show(`${top("Trésors", true)}<div class="pt-card pt-treasures">
      <div class="pt-big" aria-label="${d.coins} pièces">🪙 ${d.coins} <small aria-label="${pet.coll?.dust || 0} poussières d'étoile">✨ ${pet.coll?.dust || 0}</small></div>
      <div class="pt-acts pt-acts-2"><button type="button" class="pt-act" data-pt="coll" data-s="shop"><span class="pt-act-i" aria-hidden="true">🛍️</span><span>Boutique</span></button>
        <button type="button" class="pt-act" data-pt="coll" data-s="craft"><span class="pt-act-i" aria-hidden="true">🔨</span><span>Atelier</span></button></div>
      ${pieces ? `<h3>Morceaux de tenues</h3><ul class="pt-pieces">${pieces}</ul>` : ""}
      <h3>Album de stickers · ${d.stickers.have.length}/${d.stickers.total}</h3><div class="pt-album" aria-label="${d.stickers.have.length} stickers sur ${d.stickers.total}">${album}</div>
      <h3>Sac</h3><p>${bag}</p>
      <p class="pt-muted pt-small">Pièces, objets et tenues se gagnent en jouant : ils ne s'achètent pas et n'ont aucune valeur en argent.</p></div>`, "treasures");
  }
  const pct = (v) => `${String(v).replace(".", ",")} %`;
  function oddsScreen() {
    const d = pet.daily || {};
    const rows = (d.odds || []).map((o) => `<li class="pt-r-${e(o.kind)}"><span>${e(o.label || ODDS[o.kind] || o.kind)}</span><b>${pct(o.pct)}</b></li>`).join("");
    show(`${top("Le coffre du jour", true)}<div class="pt-card pt-odds"><h2>Chances de chaque coffre</h2><ul>${rows}</ul>
      <p class="pt-pity">🛡️ Épique garanti au plus tard dans <b>${d.pity_left ?? "?"}</b> coffre${d.pity_left > 1 ? "s" : ""} (au moins un tous les ${d.pity || 30}).</p>
      <p class="pt-muted">Même table pour le coffre du jour et le coffre bonus (pièces doublées). Un accessoire déjà à toi devient de la poussière d'étoile ✨
        (pour l'atelier). « Objet mystère » : un Mythique numéroté, en exemplaires limités. Zicou shiny : 1 chance sur 64 à l'éclosion.
        Le tirage est fait par Party, pas par ton téléphone. Rien ne s'achète avec de l'argent, rien n'a de valeur en argent.</p></div>`, "odds");
  }
  async function openChest(action) {
    if (busy) return;
    busy = true;
    const box = root?.querySelector(action === "chest" ? ".pt-chest" : ".pt-bonus");
    if (box && !calm()) box.classList.add("pt-shake");
    cue("card");
    buzz([20, 40, 20]);
    const started = Date.now(), mine = screenSeq;
    try {
      const data = await api("act", { action });
      const wait = Math.max(0, (calm() ? CHEST_MS_CALM : CHEST_MS) - (Date.now() - started));
      await new Promise((res) => setTimeout(res, wait));
      pet = data.pet;
      if (!root || root.hidden || mine !== screenSeq) return;
      reveal(data.effect?.found, data.news);
    } catch (err) {
      if (err.login) return loginScreen();
      home();
      say(err.message, true);
    } finally {
      busy = false;
    }
  }
  function reveal(found, news) {
    if (!found) return home();
    if (found.kind === "item" && window.PetCollection) { announce(news); return window.PetCollection.revealItem(found); }
    show(`${top("Surprise !", true)}<div class="pt-card pt-reveal">
      <div class="pt-reveal-i" aria-hidden="true">${e(found.emoji)}</div><h2>${e(found.label)}</h2>
      <p class="pt-muted">${e(FOUND_HINT[found.kind] || "")}</p>
      <button type="button" class="pt-cta" data-pt="home">Super !</button></div>`, "reveal");
    say(`Trouvé : ${found.label}`);
    cue("win");
    buzz([30, 60, 30]);
    announce(news);
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
    // Compté depuis l'heure d'éclosion (et non seconde par seconde) : sur iPhone, les minuteurs dorment quand l'app est
    // en arrière-plan ; au retour, le compte est juste et l'œuf éclot sans rouvrir (playtest « Léa »).
    const hatchAt = Date.now() + p.next_stage_in * 1000;
    every(() => {
      const left = Math.ceil((hatchAt - Date.now()) / 1000);
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
      <div class="pt-stage">${art(p)}</div><p class="pt-line">${e(p.line)}</p></div>${gifts}
      ${window.PetCollection ? window.PetCollection.visitExtras(f) : ""}`, "visit");
  }

  // ── Mini-jeu : « Attrape les notes » (20 s) ──
  // La partie est tirée par le serveur (/api/pet/game : jeton signé, heure de début) ; à la fin, on lui envoie le jeton et
  // le nombre de notes attrapées, et c'est LUI qui calcule le score (jamais un score déclaré par le téléphone).
  async function startGame() {
    if (busy) return;
    busy = true;
    let ticket;
    try {
      ticket = await api("game", {});
    } catch (err) {
      if (err.login) return loginScreen();
      say(err.message, true);
      return;
    } finally {
      busy = false;
    }
    if (!root || root.hidden) return;
    const name = pet.name;
    show(`${top(`Jouer avec ${name}`, true)}<div class="pt-game">
      <div class="pt-game-pet">${art(pet, "pt-mini")}<p class="pt-muted">Touche les notes avant qu'elles ne s'envolent ! ${e(name)} adore ça.</p></div>
      <div class="pt-timer" aria-hidden="true"><i></i></div>
      <div class="pt-field" data-pt-field aria-label="Terrain de jeu"></div>
      <p class="pt-score" aria-live="polite"><b data-pt-hits>0</b> note(s)</p></div>`, "play");
    const field = root.querySelector("[data-pt-field]"), bar = root.querySelector(".pt-timer i");
    const ms = Number(ticket?.ms) || PLAY_MS, notes = Number(ticket?.notes) || Math.floor(ms / SPAWN_MS);
    game = { hits: 0, spawned: 0, notes, ticket: String(ticket?.game || ""), end: Date.now() + ms, seq: screenSeq };
    cue("start");
    bar.style.setProperty("--d", `${ms}ms`);
    requestAnimationFrame(() => bar.classList.add("go"));
    every(() => spawnNote(field), SPAWN_MS);
    later(endGame, ms);
  }
  function spawnNote(field) {
    if (!game || !field.isConnected || game.spawned >= game.notes) return;
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
    const hits = Math.min(game.hits, game.notes), ticket = game.ticket;
    stopGame();
    clearTimers();
    show(loadingHtml(`${hits} note(s) attrapée(s) !`), "loading");
    await doAct("play", { game: ticket, hits });
  }

  // ── Actions ──
  const waiting = [];
  async function doAct(action, extra = {}) {
    if (busy) {
      if (QUEUED.includes(action) && waiting.length < 3) { waiting.push([action, extra]); burst("⏳"); }
      return;
    }
    busy = true;
    const mine = screenSeq;
    try {
      const data = await api("act", { action, ...extra });
      pet = data.pet;
      if (!root || root.hidden) return;
      if (action === "play" && data.effect?.score != null) { playResult(data.effect); cue("win"); buzz([30, 50, 30]); }
      else { home(); react(action); }   // (écran du score : pas de bandeau par-dessus le chiffre)
      if (data.effect?.text) say(data.effect.text);
      announce(data.news);
    } catch (err) {
      waiting.length = 0;
      if (err.login) return loginScreen();
      if (root?.dataset.screen === "loading" || mine !== screenSeq) home();   // fin du mini-jeu : retour à l'accueil
      say(err.message, true);
      cue("lose");
    } finally {
      busy = false;
      if (waiting.length && root && !root.hidden) { const [a, x] = waiting.shift(); doAct(a, x); }
    }
  }
  function playResult(fx) {
    const p = pet;
    show(`${top(`Jouer avec ${p.name}`, true)}<div class="pt-card pt-result">
      ${art(p, "pt-small-art")}
      <h2>${fx.hits} note${fx.hits > 1 ? "s" : ""} sur ${fx.notes}</h2>
      <p class="pt-big" aria-label="Score ${fx.score} sur 100">${fx.score}<small>/100</small></p>
      <p class="pt-muted">${fx.score >= 80 ? `${e(p.name)} danse de joie 🪩` : fx.score >= 40 ? `${e(p.name)} a adoré 🎵` : `${e(p.name)} s'est bien amusé 💜`}</p>
      <button type="button" class="pt-cta" data-pt="home">Super !</button></div>`, "result");
  }
  const REACT = { feed: ["😋 Miam !", "win", 40], play: ["🎉 Trop bien !", "win", [30, 50, 30]], cuddle: ["💜", "turn", 25],
    heal: ["✨ Tout propre !", "reveal", 40], sleep: ["🌙 Bonne nuit", "card", 20], wake: ["☀️ Debout !", "start", 20],
    new_egg: ["🥚 Un nouvel œuf !", "start", [30, 60, 30]], outfit: ["👕 Ça lui va bien !", "card", 20], rename: ["✏️ C'est noté", "card", 15],
    tuck: ["🌙 Bonne nuit", "card", 20], treat: ["😋 Un goûter rare !", "win", 40] };
  function react(action) {
    const [text, sound, vib] = REACT[action] || ["", "turn", 20];
    cue(sound);
    buzz(vib);
    const stage = root?.querySelector(".pt-stage");
    if (stage && !calm()) { stage.classList.remove("pt-bounce"); void stage.offsetWidth; stage.classList.add("pt-bounce"); }
    if (text) burst(text);
  }
  function burst(text) {
    const box = root?.querySelector(".pt-bursts");   // au-dessus du compagnon, jamais sur les pastilles du haut
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
    box.querySelectorAll(".pt-toast").forEach((old) => old.remove());   // un message à la fois, jamais empilés
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
      case "alert-feed": return doAct("feed");
      case "pet": return pet && !pet.asleep && pet.left.cuddle > 0 ? doAct("cuddle") : react("");
      case "outfits": return window.PetCollection ? window.PetCollection.open("wear") : outfitsScreen();
      case "coll": return window.PetCollection?.open(b.dataset.s || "dex");
      case "wear": return doAct("outfit", { outfit: b.dataset.o || "" }).then(() => root?.dataset.screen === "home" && outfitsScreen());
      case "rename": return renameScreen();
      case "friends": return showFriends();
      case "visit": { const f = friends?.find((x) => x.id === b.dataset.id); return f && visitScreen(f); }
      case "gift": return gift(b.dataset.id, b.dataset.k);
      case "chest": return openChest("chest");
      case "bonus": return openChest("bonus_chest");
      case "odds": return oddsScreen();
      case "streak": return streakScreen();
      case "treasures": return treasuresScreen();
      case "treat": return doAct("treat", { item: b.dataset.i || "" });
      case "morning-close": store.set("pt_morning", today()); b.closest(".pt-morning")?.remove(); return;
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
        window.PetCollection?.click(b, ev);   // écrans de la collection (pet/collection.js)
    }
  }
  function onSubmit(ev) {
    const form = ev.target.closest("[data-pt-form]");
    if (!form) return;
    ev.preventDefault();
    if (form.dataset.ptForm !== "rename") return window.PetCollection?.submit(form);
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
      say(kind === "hug" ? "🤗 Câlin envoyé !" : "🍪 Goûter offert !");   // en bas, jamais sur le visage de son compagnon
    } catch (err) {
      if (err.login) return loginScreen();
      say(err.message, true);
    } finally {
      busy = false;
    }
  }

  // Retour dans l'app (iPhone : minuteurs gelés en arrière-plan) : on relit l'état (œuf éclos, jauges, nouveau jour).
  document.addEventListener("visibilitychange", () => {
    if (document.hidden || !root || root.hidden || busy || game) return;
    if (["home", "egg", "memorial"].includes(root.dataset.screen)) refresh();
  });

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
    const q = new URLSearchParams(location.search);
    const src = { notif: "notif", widget: "widget" }[q.get("src")] || "link";
    if (q.get("pet") === "1") setTimeout(() => open(null, src), 300);
  } catch { /* adresse illisible */ }

  window.Pet = Object.freeze({ open, close, name: GAME_NAME });
  // Pour la collection (pet/collection.js) : mêmes écrans, même serveur, même dessin.
  window.PetUI = Object.freeze({ show, top, api, art, say, burst, cue, buzz, calm, esc: e, loadingHtml, home: () => home(),
    current: () => pet, set: (p) => { pet = p; }, root: () => root, login: () => loginScreen(), announce });
})();
