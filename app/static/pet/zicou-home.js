// 🪩 Zicou dans l'app (décision de l'admin du 4.11, maquettes « Où vit Zicou ») :
// · pastille : sa petite tête vivante dans l'en-tête (humeur = couleur, antennes), toucher = onglet Zicou ; point rouge
//   RARE (il a faim, un ami lui a offert quelque chose), jamais de chiffre ; masquée pendant une partie (pyr-full) ;
// · pastille de l'onglet Zicou (●) quand il a besoin de toi : faim, coffre du jour prêt, cadeau d'ami ;
// · accueil après la 1re connexion : feuille « Quelqu'un t'attend… » (fermable d'un geste, « Plus tard »), nom,
//   éclosion de 3 min en continuant d'utiliser l'app, premier cadeau garanti, PUIS la demande de notifications ;
//   rappel doux (carte masquable, 3 fois au plus sur 2 semaines) ; invité sans compte : « Adopte ton Zicou » une
//   seule fois, après sa première partie (jamais pendant, jamais après un jeu d'alcool).
// Aucune pression, aucun mur : tout se ferme, rien ne bloque l'app. Le serveur fait foi (/api/pet/status, /api/pet/me).
(function () {
  "use strict";
  const STATUS_EVERY_MS = 180000;          // relu toutes les 3 min (et au retour dans l'app)
  const STATUS_MIN_GAP_MS = 20000;         // jamais plus d'une lecture toutes les 20 s (changements d'onglet)
  const REMIND_MAX = 3;                    // rappel doux : 3 fois au plus…
  const REMIND_WINDOW_MS = 14 * 86400000;  // … sur 2 semaines après « Plus tard »
  const REMIND_GAP_MS = 20 * 3600000;      // au plus une fois par jour, jamais le jour même
  const GUEST_INVITE_DELAY_MS = 1500;      // après la fin de la partie, le temps de voir le classement
  const BUBBLE_MS = 4500;
  const NAME_MAX = 16;
  const NAMES = ["Paillette", "Disco", "Bobby", "Zicou", "Néon", "Pixel", "Groove", "Biscotte", "Boogie", "Tempo"];
  const DRINK_GAMES = ["beerpong", "whoof", "never", "roulette", "biskit", "casino", "purity"];
  const WEB_TABS = ["games", "pet", "events"];   // onglets toujours affichés par la page (l'app iOS dessine les autres)
  const KEY = "zc_onb", GUEST_KEY = "zc_guest_invite", BUBBLE_KEY = "zc_bubble", SEEN_KEY = "zc_seen";

  const $ = (id) => document.getElementById(id);
  const e = typeof esc === "function" ? esc : (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const skin = () => window.PetSkin;
  const today = () => new Date().toLocaleDateString("fr-CA", { timeZone: "Europe/Zurich" });
  const local = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* navigation privée */ } },
  };
  const now = () => Date.now();
  const signedIn = () => typeof account !== "undefined" && !!account;
  const native = () => document.documentElement.classList.contains("native-tabs");
  const currentTab = () => document.body.dataset.tab || "music";
  // L'app iOS dessine Musique, Discussions et Réglages en natif : la feuille attend un onglet affiché par la page.
  const pageVisible = () => !native() || WEB_TABS.includes(currentTab());
  const inGame = () => document.body.classList.contains("pyr-full");

  function onb() {
    try { return { step: "new", ...(JSON.parse(local.get(KEY) || "{}")) }; } catch { return { step: "new" }; }
  }
  function saveOnb(patch) {
    const next = { ...onb(), ...patch };
    local.set(KEY, JSON.stringify(next));
    queueMicrotask(render);   // le point de l'onglet suit l'étape de l'accueil
    return next;
  }

  // ── Serveur ──
  async function token() {
    try { return typeof freshToken === "function" ? await freshToken() : null; } catch { return null; }
  }
  async function post(path, body) {
    const t = await token();
    if (!t) throw new Error("login");
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: t, ...body }) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Zicou ne répond pas. Réessaie dans un instant.");
    return data;
  }

  // ── État ──
  let status = null, statusAt = 0, statusBusy = false, hatchTimer = 0, hatchSaved = false;
  async function refreshStatus(force) {
    if (!signedIn()) { status = null; render(); return; }
    if (statusBusy || (!force && now() - statusAt < STATUS_MIN_GAP_MS)) return;
    statusBusy = true;
    try {
      status = await post("/api/pet/status", {});
      statusAt = now();
    } catch { /* hors ligne : la pastille garde son dernier état */ }
    statusBusy = false;
    render();
    flow();
  }
  /** Le panneau du Compagnon a relu son personnage (pet.js) : la pastille suit sans attendre. */
  function petChanged(p, news) {
    if (!p) return;
    const chest = p.daily?.chest?.state === "ready";
    status = { ...(status || {}), adopted: true, name: p.name, stage: p.stage, variant: p.variant, emotion: p.emotion,
      asleep: p.asleep, next_stage_in: p.next_stage_in, gen: p.gen, acc: p.coll?.acc || {}, shiny: !!p.coll?.shiny,
      need: !["egg", "dead"].includes(p.stage) && p.alert ? "alert" : chest && p.stage !== "egg" && p.stage !== "dead" ? "chest" : null };
    statusAt = now();
    if ((news || []).some((n) => n.kind === "welcome")) welcomeGift = news.find((n) => n.kind === "welcome");
    render();
    flow();
  }

  // ── Pastille (en-tête) et pastille de l'onglet ──
  function headSvg(st) {
    const s = skin();
    if (!s) return "🥚";
    const svg = s.render({ stage: st.stage || "egg", variant: st.variant || "classic", emotion: st.emotion || "egg",
      accessories: st.acc || {}, shiny: !!st.shiny });
    return svg.replace('viewBox="0 0 200 200"', `viewBox="${HEAD_BOX[st.stage] || HEAD_BOX.egg}"`);
  }
  // Cadrage de la tête (et des antennes) dans le dessin 200 × 200 de pet/skin.js, stade par stade.
  const HEAD_BOX = { egg: "25 40 150 150", baby: "55 90 90 90", teen: "41 52 118 118", adult: "27 18 146 146", dead: "27 18 146 146" };
  let shownKey = "";
  function render() {
    const chips = [$("zicouChip"), $("zicouFloat")].filter(Boolean);
    const tabBadge = $("petBadge");
    const st = status;
    const visible = signedIn() && !!st;
    const egg = !st?.adopted;
    const view = egg ? { stage: "egg", emotion: "egg" } : st;
    const red = !egg && ["alert", "gift"].includes(st?.need);
    const key = visible ? JSON.stringify([view.stage, view.emotion, view.variant, view.acc, view.shiny, red]) : "";
    chips.forEach((chip) => {
      chip.classList.toggle("hidden", !visible);
      if (!visible || key === shownKey) return;
      chip.querySelector(".zc-head").innerHTML = headSvg(view);
      chip.style.setProperty("--zc-mood", skin()?.moodColor(view.emotion) || "#5ee7ff");
      chip.classList.toggle("zc-egg", view.stage === "egg");
      chip.classList.toggle("zc-sleep", !!st?.asleep);
      chip.querySelector(".zc-dot").classList.toggle("hidden", !red);
      chip.setAttribute("aria-label", egg ? "Zicou : un œuf t'attend" : `${st.name} : ${moodWord(st)}${red ? ", il a besoin de toi" : ""}`);
    });
    if (visible) shownKey = key;
    // Onglet Zicou : un point, jamais un chiffre (faim, coffre du jour, cadeau d'ami ; œuf éclos qui attend).
    const hatchedWaiting = ["hatching", "naming"].includes(onb().step) && st?.adopted && st.stage !== "egg";
    // Compte tout neuf, accueil pas encore vu (app iOS : Musique et Réglages sont natifs, la feuille attend un onglet
    // de la page) : le même point, jusqu'à ce que l'accueil s'ouvre une fois.
    const welcomeWaiting = visible && egg && onb().step === "new";
    if (tabBadge) tabBadge.classList.toggle("hidden", !(welcomeWaiting || (visible && !egg && (st.need || hatchedWaiting))));
    if (visible && !local.get(SEEN_KEY) && !calm()) {
      local.set(SEEN_KEY, "1");
      chips.forEach((chip) => chip.classList.add("zc-hello"));   // la toute première fois : un petit salut pour qu'on la remarque
    }
    maybeBubble();
  }
  const MOODS = { happy: "content", party: "en fête", hungry: "a faim", tired: "fatigué", sad: "s'ennuie", sick: "patraque",
    sleep: "endormi", egg: "dans son œuf", ghost: "envolé" };
  const moodWord = (st) => MOODS[st.emotion] || "";
  // « Psst… ton cadeau du jour ! » : une fois par jour au plus, seulement pour le coffre (les urgences ont le point rouge).
  function maybeBubble() {
    const chip = $("zicouChip");
    if (!chip || chip.classList.contains("hidden") || status?.need !== "chest" || local.get(BUBBLE_KEY) === today()) return;
    if (currentTab() === "pet" || inGame() || sheetStep || !chip.offsetParent) return;
    local.set(BUBBLE_KEY, today());
    const b = document.createElement("div");
    b.className = "zc-bubble";
    b.setAttribute("role", "status");
    b.textContent = "Psst… ton cadeau du jour ! 🎁";
    chip.after(b);
    setTimeout(() => b.remove(), BUBBLE_MS);
  }
  function openZicou() {
    // Pas encore d'œuf : la 1re fois l'accueil, ensuite directement le choix du nom.
    if (signedIn() && status && !status.adopted) return openSheet(onb().step === "new" ? "intro" : "name");
    if (typeof showTab === "function") showTab("pet");
  }

  // ── Feuille d'accueil (5 écrans) ──
  let sheet = null, sheetStep = null, welcomeGift = null, countdown = 0, pendingStep = null;
  function sheetEl() {
    if (sheet) return sheet;
    sheet = document.createElement("div");
    sheet.id = "zicouSheet";
    sheet.className = "zc-modal hidden";
    sheet.setAttribute("role", "dialog");
    sheet.setAttribute("aria-modal", "true");
    sheet.setAttribute("aria-labelledby", "zcTitle");
    sheet.dataset.nav = "sheet";
    sheet.dataset.navSurface = ".zc-sheet";
    sheet.dataset.navClose = "[data-zc-close]";
    sheet.addEventListener("click", onSheetClick);
    sheet.addEventListener("input", onSheetInput);
    sheet.addEventListener("submit", (ev) => { ev.preventDefault(); chooseName(); });
    document.body.append(sheet);
    return sheet;
  }
  const dots = (i) => `<div class="zc-dots" aria-hidden="true">${[0, 1, 2, 3, 4].map((k) => `<i class="${k === i ? "on" : ""}"></i>`).join("")}</div>`;
  const art = (opts, cls = "") => `<div class="zc-art ${cls}" style="--zc-mood:${skin()?.moodColor(opts.emotion) || "#5ee7ff"}">${skin()?.render(opts) || "🥚"}</div>`;
  const petName = () => status?.name || onb().name || "Zicou";

  function openSheet(step) {
    if (inGame()) { pendingStep = step; return; }   // jamais par-dessus une partie : à la fin
    pendingStep = null;
    const el = sheetEl();
    sheetStep = step;
    clearInterval(countdown);
    el.innerHTML = `<div class="zc-sheet" data-step="${step}">${STEPS[step]()}</div>`;
    el.classList.remove("hidden", "zc-out");
    document.documentElement.classList.add("zc-sheet-open");
    if (step === "hatch") startCountdown();
    if (step === "name") setTimeout(() => el.querySelector("#zcName")?.focus({ preventScroll: true }), 350);
    else {   // VoiceOver : la feuille est annoncée dès qu'elle s'ouvre
      const surface = el.querySelector(".zc-sheet");
      surface.tabIndex = -1;
      surface.focus({ preventScroll: true });
    }
  }
  function closeSheet() {
    if (!sheet || sheet.classList.contains("hidden")) return;
    clearInterval(countdown);
    const was = sheetStep;
    sheetStep = null;
    sheet.classList.add("hidden");
    document.documentElement.classList.remove("zc-sheet-open");
    sheetClosed(was);
  }
  /** Fermée d'un geste, par « Plus tard », « Explorer l'app »… : rien n'est perdu, on reprendra au bon moment. */
  function sheetClosed(step) {
    const st = onb();
    // Pas encore d'œuf : « Plus tard » (ou fermée au choix du nom) → seulement le rappel doux, 3 fois au plus.
    if (["intro", "name"].includes(step) && ["new", "naming"].includes(st.step) && !status?.adopted) {
      saveOnb({ step: "later", laterAt: st.laterAt || now(), reminders: st.reminders || 0 });
    }
    if (step === "gift" || step === "notif") saveOnb({ step: "done" });
    if (step === "guest") local.set(GUEST_KEY, "1");
  }

  const STEPS = {
    intro: () => `${dots(0)}${art({ stage: "egg", emotion: "egg" }, "zc-wobble")}
      <h2 id="zcTitle">Quelqu'un t'attend…</h2>
      <p class="zc-muted">Un petit Zicou va éclore rien que pour toi. Il grandit avec tes soirées, tes parties et ta musique.</p>
      <button type="button" class="zc-cta" data-zc="discover">Le découvrir</button>
      <button type="button" class="zc-link" data-zc-close>Plus tard</button>`,
    name: () => {
      const name = onb().name || NAMES[Math.floor(Math.random() * 3)];
      const chips = [...new Set([name, ...NAMES.slice(0, 4)])].slice(0, 4);
      return `${dots(1)}${art({ stage: "egg", emotion: "egg" }, "zc-small")}
      <h2 id="zcTitle">Comment va-t-il s'appeler ?</h2>
      <form class="zc-name" novalidate><label class="zc-sr" for="zcName">Son nom</label>
        <div class="zc-input"><input id="zcName" name="name" maxlength="${NAME_MAX}" autocomplete="off" spellcheck="false" value="${e(name)}">
        <span class="zc-count" aria-hidden="true">${name.length}/${NAME_MAX}</span></div>
        <div class="zc-chips" role="group" aria-label="Suggestions">${chips.map((n) => `<button type="button" data-zc="pick" data-n="${e(n)}" class="${n === name ? "on" : ""}">${e(n)}</button>`).join("")}
          <button type="button" data-zc="random">🎲 Au hasard</button></div>
        <p class="zc-muted zc-small">Tu pourras le changer quand tu veux. Ses amis le verront.</p>
        <p class="zc-err hidden" role="alert"></p>
        <button type="submit" class="zc-cta">Continuer</button></form>
      <button type="button" class="zc-link" data-zc-close>Plus tard</button>`;
    },
    hatch: () => `${dots(2)}<div class="zc-ring" style="--zc-p:0">${art({ stage: "egg", emotion: "egg" }, "zc-small zc-wobble")}</div>
      <p class="zc-clock" aria-live="off" data-zc-clock>3:00</p>
      <h2 id="zcTitle">${e(petName())} éclot bientôt</h2>
      <p class="zc-muted">Pas besoin d'attendre ici. Pendant ce temps :</p>
      <div class="zc-list">
        <button type="button" data-zc="go" data-tab="music"><span aria-hidden="true">🎵</span><span><b>Ajoute un titre à la file</b><small>${e(petName())} l'entendra dans sa coquille</small></span></button>
        <button type="button" data-zc="go" data-tab="games"><span aria-hidden="true">🎮</span><span><b>Découvre les jeux</b></span></button>
      </div>
      <button type="button" class="zc-ghost" data-zc-close>Explorer l'app</button>`,
    gift: () => {
      const acc = { neck: "noeud", ...(status?.acc || {}) };
      return `${dots(3)}<div class="zc-confetti" aria-hidden="true"></div>${art({ stage: "baby", emotion: "party", accessories: acc, shiny: !!status?.shiny, label: petName() }, "zc-pop")}
      <h2 id="zcTitle">Coucou, je suis ${e(petName())} !</h2>
      <p class="zc-muted">Merci de m'avoir attendu. J'ai un premier cadeau pour toi.</p>
      <div class="zc-gift"><span aria-hidden="true">🎁</span><span><b>Cadeau de bienvenue</b><small>Nœud papillon · ${welcomeGift?.coins || 50} pièces · garanti</small></span></div>
      <button type="button" class="zc-cta" data-zc="open-gift">Ouvrir mon cadeau</button>`;
    },
    notif: () => `${dots(4)}${art({ stage: "baby", emotion: "happy", accessories: { neck: "noeud", ...(status?.acc || {}) }, shiny: !!status?.shiny }, "zc-small")}
      <h2 id="zcTitle">Je te préviens quand j'ai besoin de toi ?</h2>
      <p class="zc-muted">Rarement : son cadeau du jour, un cadeau d'un ami, ou s'il a vraiment faim. Rien d'autre.</p>
      <div class="zc-list zc-prefs">
        ${pref("pet_daily", "🎁", "Cadeau du jour", "Au plus une fois par jour")}
        ${pref("pet_gifts", "💜", "Cadeau d'un ami", "Un câlin ou un goûter pour lui")}
        ${pref("pet_alerts", "🍕", "Il a très faim", "Deux alertes au plus, avant qu'il ne s'envole")}
      </div>
      <p class="zc-err hidden" role="alert"></p>
      <button type="button" class="zc-cta" data-zc="notif-yes">Oui, préviens-moi</button>
      <button type="button" class="zc-link" data-zc-close>Pas maintenant</button>
      <p class="zc-muted zc-small">Modifiable dans Réglages › Notifications › Zicou</p>`,
    guest: () => `${art({ stage: "baby", emotion: "party", accessories: { neck: "noeud" } }, "zc-pop")}
      <h2 id="zcTitle">Adopte ton Zicou</h2>
      <p class="zc-muted">${guestGame ? `Il a vu ta partie de ${e(guestGame)} ce soir.` : "Il a vu ta partie ce soir."} Crée ton compte pour l'emmener chez toi.</p>
      <button type="button" class="zc-cta" data-zc="signup">Créer mon compte</button>
      <button type="button" class="zc-link" data-zc-close>Non merci, je joue en invité</button>
      <p class="zc-muted zc-small">Gratuit · avec ton numéro · ton prénom de ce soir est gardé</p>`,
  };
  const pref = (key, icon, label, hint) => `<label class="zc-pref"><span aria-hidden="true">${icon}</span><span><b>${label}</b><small>${hint}</small></span>
    <input type="checkbox" class="switch" data-pref="${key}" checked></label>`;

  function onSheetClick(ev) {
    if (ev.target === sheet) return closeSheet();   // toucher le fond : comme « Plus tard »
    if (ev.target.closest("[data-zc-close]")) return closeSheet();
    const b = ev.target.closest("[data-zc]");
    if (!b) return;
    const act = b.dataset.zc;
    if (act === "discover") { saveOnb({ step: "naming" }); return openSheet("name"); }
    if (act === "pick" || act === "random") {
      const input = sheet.querySelector("#zcName");
      const pool = NAMES.filter((n) => n !== input.value);
      input.value = act === "pick" ? b.dataset.n : pool[Math.floor(Math.random() * pool.length)];
      onSheetInput();
      return;
    }
    if (act === "go") { closeSheet(); return typeof showTab === "function" && showTab(b.dataset.tab); }
    if (act === "open-gift") return openGift(b);
    if (act === "notif-yes") return notifYes(b);
    if (act === "signup") { closeSheet(); return typeof showTab === "function" && showTab("account"); }
  }
  function onSheetInput() {
    const input = sheet?.querySelector("#zcName");
    if (!input) return;
    sheet.querySelector(".zc-count").textContent = `${input.value.length}/${NAME_MAX}`;
    sheet.querySelectorAll("[data-zc=pick]").forEach((c) => c.classList.toggle("on", c.dataset.n === input.value));
    sheet.querySelector(".zc-err").classList.add("hidden");
  }
  // Le nom passe par la même modération que les prénoms (serveur : moderation.require_clean).
  async function chooseName() {
    const input = sheet.querySelector("#zcName"), err = sheet.querySelector(".zc-err"), btn = sheet.querySelector("[type=submit]");
    const name = input.value.trim().slice(0, NAME_MAX);
    if (!name) { err.textContent = "Choisis-lui un nom."; err.classList.remove("hidden"); return; }
    btn.disabled = true;
    try {
      // Adoption explicite : SEUL moment où l'œuf est pondu (3 min d'éclosion). Fermer la feuille ne pond rien.
      let me = await post("/api/pet/act", { action: "adopt", name });
      if (me.pet.name !== name) me = await post("/api/pet/act", { action: "rename", name });   // déjà adopté ailleurs
      saveOnb({ step: "hatching", name });
      petChanged(me.pet, me.news);
      openSheet("hatch");
      if (currentTab() === "pet") window.Pet?.open?.(null, "none");   // l'onglet Zicou quitte l'écran d'adoption
    } catch (error) {
      err.textContent = error.message === "login" ? "Ta connexion a expiré, reconnecte-toi." : error.message;
      err.classList.remove("hidden");
    }
    btn.disabled = false;
  }
  function startCountdown() {
    const left0 = Math.max(0, Number(status?.next_stage_in ?? 180));
    const end = now() + left0 * 1000, total = 180;
    const tick = () => {
      const left = Math.max(0, Math.ceil((end - now()) / 1000));
      const clock = sheet?.querySelector("[data-zc-clock]");
      if (clock) clock.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
      sheet?.querySelector(".zc-ring")?.style.setProperty("--zc-p", String(Math.min(1, 1 - left / total)));
      if (left <= 0) { clearInterval(countdown); hatchNow(); }
    };
    tick();
    countdown = setInterval(tick, 1000);
  }
  /** L'éclosion à l'heure dite, que la feuille soit ouverte ou non (minuteur de la page). */
  function scheduleHatch() {
    clearTimeout(hatchTimer);
    if (!status?.adopted || status.stage !== "egg" || onb().step !== "hatching") return;
    hatchTimer = setTimeout(hatchNow, Math.max(1, status.next_stage_in || 0) * 1000 + 600);
  }
  async function hatchNow() {
    clearTimeout(hatchTimer);
    try {
      const me = await post("/api/pet/me", { src: "none" });   // le serveur fait éclore et donne le cadeau (pet_welcome)
      petChanged(me.pet, me.news);
    } catch { /* hors ligne : on réessaiera au prochain passage (status) */ }
  }
  async function openGift(btn) {
    btn.disabled = true;
    const box = sheet.querySelector(".zc-gift");
    box.classList.add("zc-opened");
    box.querySelector("small").textContent = `Il le porte déjà ! +${welcomeGift?.coins || 50} pièces dans sa tirelire 🪙`;
    if (!calm()) sheet.querySelector(".zc-art")?.classList.add("zc-bounce");
    window.haptic?.([30, 60, 30]);
    window.GameAudio?.cue?.("win");
    saveOnb({ step: "notif" });
    setTimeout(() => { if (sheetStep === "gift") openSheet("notif"); }, calm() ? 400 : 1300);
  }
  // Notifications APRÈS le premier cadeau : explication, choix par catégorie, puis seulement la demande système.
  async function notifYes(btn) {
    const prefs = Object.fromEntries([...sheet.querySelectorAll("[data-pref]")].map((i) => [i.dataset.pref, i.checked]));
    const err = sheet.querySelector(".zc-err");
    const wantsAny = Object.values(prefs).some(Boolean);
    // Web : la demande système doit partir du toucher lui-même, avant tout appel réseau.
    const webAsk = !window.PartyNative?.push && wantsAny && "Notification" in window && window.isSecureContext
      ? Notification.requestPermission().catch(() => "default") : null;
    btn.disabled = true;
    try {
      await post("/api/account/notifications/update", { patch: prefs });
      if (wantsAny) await enablePush(webAsk);
      saveOnb({ step: "done", notif: true });
      closeSheet();
      if (typeof toast === "function") toast(`C'est noté, ${petName()} te fera signe 💜`, "ok");
    } catch (error) {
      err.textContent = error.message === "login" ? "Ta connexion a expiré, reconnecte-toi." : error.message;
      err.classList.remove("hidden");
      btn.disabled = false;
    }
  }
  async function enablePush(webAsk) {
    const bridge = window.PartyNative?.push;
    if (bridge) {   // app iOS : l'alerte du système arrive maintenant, après l'explication
      const device = await bridge.register().catch(() => null);
      if (!device?.token) throw new Error("Notifications refusées : tu peux les autoriser pour Party ! dans les réglages de l'iPhone.");
      await post("/api/account/push", { device: device.token, on: true });
      return;
    }
    const permission = webAsk ? await webAsk : "default";
    if (permission !== "granted") {
      const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) && navigator.standalone !== true;
      throw new Error(ios ? "Sur iPhone, ajoute d'abord Party à ton écran d'accueil, puis ouvre-la depuis son icône."
        : "Notifications non autorisées : tu peux les autoriser dans les réglages du navigateur.");
    }
    // Abonnement du compte : le module Événements l'enregistre (même origine, autorisation déjà donnée).
    if (typeof frameRoute === "function" && !$("eventsFrame")?.getAttribute("src")) frameRoute(null);
    $("eventsFrame")?.contentWindow?.postMessage({ type: "party-shell:enable-push" }, location.origin);
  }

  // ── Quand montrer quoi ──
  function flow() {
    if (!signedIn() || !status) return;
    const st = onb();
    if (status.adopted) {
      if (status.stage === "egg") {
        if (["new", "later", "naming"].includes(st.step)) saveOnb({ step: "hatching" });
        scheduleHatch();
        return;
      }
      if (["hatching", "naming"].includes(onb().step) && status.gen === 1 && status.stage !== "dead") {
        // La pastille a vu l'éclosion (lecture seule) : on l'enregistre, avec le cadeau de bienvenue, une fois.
        if (!hatchSaved) { hatchSaved = true; hatchNow(); }
        if (sheetStep !== "gift" && pageVisible()) openSheet("gift");
        return;
      }
      if (st.step === "notif" && sheetStep !== "notif" && pageVisible()) return openSheet("notif");
      if (!["done", "notif"].includes(st.step)) saveOnb({ step: "done" });   // adopté avant cet accueil
      return;
    }
    if (st.step === "new" && pageVisible() && !sheetStep) openSheet("intro");
    else if (st.step === "later") reminder();
  }
  // Rappel doux : une carte en tête de Musique ou de Jeux, masquable, 3 fois au plus sur 2 semaines, jamais le jour même.
  // Une fois comptée, la carte suit l'onglet (Musique ↔ Jeux) jusqu'à ce qu'on la masque ou qu'on la touche.
  let reminderActive = false;
  function reminder() {
    const st = onb();
    const hostNow = currentTab() === "games" ? $("gamesRoot") : document.querySelector('[data-view="music"]');
    document.querySelectorAll(".zc-remind").forEach((c) => { if (!reminderActive || c.parentElement !== hostNow) c.remove(); });
    if (st.step !== "later" || status?.adopted || inGame()) return;
    const host = currentTab() === "games" ? $("gamesRoot") : currentTab() === "music" && pageVisible() ? document.querySelector('[data-view="music"]') : null;
    if (!host) return;
    if (reminderActive && host.querySelector(":scope > .zc-remind")) return;   // déjà là : pas de clignement
    if (!reminderActive) {
      if ((st.reminders || 0) >= REMIND_MAX || now() - (st.laterAt || 0) > REMIND_WINDOW_MS) return;
      if (now() - (st.laterAt || 0) < REMIND_GAP_MS || now() - (st.remindedAt || 0) < REMIND_GAP_MS) return;
      reminderActive = true;
      saveOnb({ reminders: (st.reminders || 0) + 1, remindedAt: now() });
    }
    const card = document.createElement("div");
    card.className = "zc-remind card";
    card.setAttribute("role", "region");
    card.setAttribute("aria-label", "Ton œuf Zicou");
    card.innerHTML = `${art({ stage: "egg", emotion: "egg" }, "zc-mini zc-wobble")}
      <div class="zc-remind-t"><b>Ton œuf a bougé…</b><small>Il t'attend depuis hier. 3 min pour le faire éclore.</small>
      <button type="button" class="zc-cta zc-cta-s" data-zc-remind="open">Le découvrir</button></div>
      <button type="button" class="zc-x" data-zc-remind="close" aria-label="Masquer">✕</button>`;
    host.prepend(card);
  }
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-zc-remind]");
    if (b) {
      reminderActive = false;
      b.closest(".zc-remind")?.remove();
      if (b.dataset.zcRemind === "open") { saveOnb({ step: "naming" }); openSheet("name"); }
      return;
    }
    if (ev.target.closest("#zicouChip, #zicouFloat")) openZicou();
  });

  // ── Invité sans compte : « Adopte ton Zicou », une seule fois, après sa première partie ──
  let guestGame = "", guestPrev = null;
  function gameSeen(g) {
    const ended = guestPrev && guestPrev.me && guestPrev.phase !== "end" && g?.id === guestPrev.id && g.phase === "end";
    guestPrev = g ? { id: g.id, me: !!g.me, phase: g.phase } : null;
    if (!ended || signedIn() || local.get(GUEST_KEY) || DRINK_GAMES.includes(g.type)) return;
    local.set(GUEST_KEY, "1");
    guestGame = g.name || "";
    setTimeout(() => { if (!signedIn()) showGuestSheet(); }, GUEST_INVITE_DELAY_MS);
  }
  function showGuestSheet() {
    // Fin de partie en plein écran : la feuille passe au-dessus du classement, sans rien interrompre.
    const el = sheetEl();
    sheetStep = "guest";
    el.innerHTML = `<div class="zc-sheet" data-step="guest">${STEPS.guest()}</div>`;
    el.classList.remove("hidden");
  }

  // ── Branchements ──
  function tabChanged(tab) {
    document.querySelectorAll(".zc-remind").forEach((c) => c.remove());
    if (sheetStep && ["hatch", "intro", "name"].includes(sheetStep) && native() && !WEB_TABS.includes(tab)) closeSheet();
    setTimeout(() => { refreshStatus(false); flow(); maybeBubble(); });
  }
  new MutationObserver(() => {
    if (!inGame() && pendingStep) openSheet(pendingStep);
  }).observe(document.body, { attributes: true, attributeFilter: ["class"] });
  setInterval(() => { if (!document.hidden) refreshStatus(true); }, STATUS_EVERY_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshStatus(false); });
  // Compte relié (ou perdu) : linkAccount prévient le module ; on suit avec un léger retard.
  window.addEventListener("message", (ev) => {
    if (ev.origin === location.origin && ev.data?.type === "party-events:account") setTimeout(() => refreshStatus(true), 1500);
  });
  addEventListener("DOMContentLoaded", () => setTimeout(() => refreshStatus(true), 800));
  // Compte relié, changé ou déconnecté (index.html, showAccount) : la pastille et l'accueil suivent tout de suite.
  let accountKey = null;
  function accountChanged() {
    const key = signedIn() ? account.guest_id || account.name || "?" : "";
    if (key === accountKey) return;
    accountKey = key;
    if (!key) { status = null; closeSheet(); render(); return; }
    refreshStatus(true);
  }

  window.ZicouHome = Object.freeze({ refresh: refreshStatus, accountChanged, petChanged, tabChanged, gameSeen, open: openSheet, close: closeSheet,
    state: () => ({ status, onb: onb(), step: sheetStep }) });
})();
