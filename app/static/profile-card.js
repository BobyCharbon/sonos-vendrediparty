// 👤 Fiche profil d'un joueur (jeux) : on touche le nom ou la photo d'un joueur qui a un compte Party.
// Le serveur ne reçoit que la partie et le numéro du joueur ; la base applique les choix de la personne
// (nom et prénom seulement s'ils sont publics, numéro seulement aux membres de ses groupes).
// Usage : un élément avec data-profile-pid="<pid>" dans l'écran d'une partie (code dans data-profile-game).
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ROLES = { guest: "Guest", guestplus: "Guest+", basic: "Membre", member: "Membre VIP", organizer: "Organisateur", coadmin: "Co-admin", admin: "Admin" };
  let sheet = null;
  let shown = 0;  // numéro de la dernière fiche demandée : une réponse plus ancienne est ignorée
  let opener = null;  // élément qui avait le focus (nom du joueur) : il le retrouve à la fermeture (clavier, VoiceOver)
  const OUT_SAFETY_MS = 400;
  const CARD_FIT = "max-height:calc(100dvh - 32px - env(safe-area-inset-top) - env(safe-area-inset-bottom));overflow-y:auto";
  // Chargement : la silhouette de la fiche (photo ronde, lignes) plutôt qu'un texte d'attente.
  const LOADING = `<div class="pc-photo pc-skel" role="status" aria-label="Chargement du profil…"></div>
    <i class="pc-skel pc-skel-line"></i><i class="pc-skel pc-skel-line short"></i>`;

  // La fiche monte du bas ; « Fermer » ou le fond la font redescendre, puis elle est retirée.
  function close() {
    shown++;
    const leaving = sheet;
    sheet = null;
    if (!leaving) return;
    leaving.classList.add("pc-out");
    if (opener?.isConnected) opener.focus();
    opener = null;
    const done = () => leaving.remove();
    leaving.querySelector(".pc-card").addEventListener("animationend", done, { once: true });
    setTimeout(done, OUT_SAFETY_MS);
  }

  function show(html) {
    // Fiche déjà ouverte (chargement → profil) : seul le contenu change, en fondu ; la fiche ne remonte pas.
    if (sheet) {
      const body = sheet.querySelector(".pc-body");
      body.innerHTML = html;
      body.classList.remove("pc-swap");
      void body.offsetWidth;
      body.classList.add("pc-swap");
      return;
    }
    opener = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : null;
    sheet = document.createElement("div");
    sheet.className = "pc-backdrop";
    // Fiche plus haute que l'écran (iPhone SE, numéro + groupes + Méninges, texte agrandi) : elle défile en elle-même,
    // « Fermer » reste atteignable.
    sheet.innerHTML = `<div class="pc-card" role="dialog" aria-modal="true" aria-label="Profil" style="${CARD_FIT}"><div class="pc-body">${html}</div>
      <button type="button" class="secondary pc-close">Fermer</button></div>`;
    const mine = sheet;
    sheet.addEventListener("click", (ev) => {
      if (sheet !== mine) return;
      if (ev.target.closest(".pc-add-contact")) { if (current?.phone) addContact(current); return; }
      if (ev.target.closest(".pc-write")) { if (current?.id) write(current, ev.target.closest(".pc-write")); return; }
      if (ev.target === mine || ev.target.closest(".pc-close")) close();
    });
    document.body.append(sheet);
    sheet.querySelector(".pc-close").focus();
  }

  // 📇 Contacts (avis f780431defe7) : vCard 3.0 (FN, N, NICKNAME, TEL), échappée selon la RFC 2426.
  const vEsc = (v) => String(v ?? "").replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r\n|\r|\n/g, "\\n");
  function vcard(c) {
    const digits = String(c.phone || "").replace(/[^0-9]/g, "");
    if (digits.length < 6 || digits.length > 15) return null;
    const first = (c.first_name || "").trim(), last = (c.last_name || "").trim(), nick = (c.display_name || "").trim();
    const given = first || last ? first : nick;  // sans nom public : le pseudo, à renommer dans Contacts
    const full = [given, last].filter(Boolean).join(" ") || `+${digits}`;
    return ["BEGIN:VCARD", "VERSION:3.0", `N:${vEsc(last)};${vEsc(given)};;;`, `FN:${vEsc(full)}`,
      ...(nick && (first || last) ? [`NICKNAME:${vEsc(nick)}`] : []), `TEL;TYPE=CELL:+${digits}`, "END:VCARD"].join("\r\n") + "\r\n";
  }
  let current = null;  // fiche affichée (pour « Ajouter aux contacts »)

  // App iPhone : fiche Contacts d'Apple préremplie ; ailleurs, la vCard téléchargée que le téléphone propose d'ajouter.
  function addContact(c) {
    const bridge = window.PartyNative && window.PartyNative.contacts;
    if (bridge && bridge.add) {
      return bridge.add({ phone: `+${String(c.phone).replace(/[^0-9]/g, "")}`, firstName: c.first_name || null, lastName: c.last_name || null, nickname: c.display_name || null });
    }
    const card = vcard(c);
    if (!card) return;
    const url = URL.createObjectURL(new Blob([card], { type: "text/vcard;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${(c.display_name || "contact").normalize("NFD").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "contact"}.vcf` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  // 💬 Message direct (4.11) : Discussions ouvertes (bêta-testeurs en production), onglet présent dans la page.
  const canWrite = () => typeof showTab === "function" && !(window.PartyEvents && window.PartyEvents.soon);

  // « Écrire » : LA conversation privée à deux (créée au besoin) ; app iPhone : l'écran natif des Discussions
  // (l'app intercepte ?tab=chats&chat=…), ailleurs l'onglet Discussions de la page.
  async function write(c, button) {
    const ticket = shown;
    button.disabled = true;
    try {
      const token = typeof freshToken === "function" ? await freshToken() : null;
      const r = await fetch("/api/account/chats/direct", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, user_id: c.id }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !/^[0-9a-f-]{36}$/.test(data.id || "")) throw new Error(typeof data.detail === "string" ? data.detail : "Tu ne peux pas écrire à cette personne.");
      if (ticket !== shown) return;
      close();
      if (window.PartyNative && window.PartyNative.tabs) location.assign(`/?tab=chats&chat=${data.id}`);
      else showTab("chats", `/chats/${data.id}`);
    } catch (e) {
      button.disabled = false;
      if (ticket === shown && typeof toast === "function") toast(e.message, "err");
    }
  }

  // Nom de mon répertoire pour ce membre (app iPhone seulement ; ailleurs rien).
  async function contactName(id) {
    try {
      const bridge = window.PartyNative && window.PartyNative.contacts;
      const names = bridge && bridge.names ? await bridge.names() : null;
      const name = names && id ? names[id] : null;
      return typeof name === "string" && name.trim() ? name.trim() : null;
    } catch { return null; }
  }

  function cardHtml(c, contact = null) {
    const name = [c.first_name, c.last_name].filter(Boolean).join(" ");
    const phone = c.phone ? `+${String(c.phone).replace(/^\+/, "")}` : "";
    const initial = escape((contact || c.display_name || "?").trim().charAt(0).toUpperCase());
    const known = contact && !c.me ? contact : null;
    return `<div class="pc-photo">${c.photo ? `<img src="${escape(c.photo)}" alt="">` : initial}</div>
      <div class="pc-name">${escape(known || c.display_name || "Profil à compléter")}</div>
      ${known && c.display_name ? `<div class="artist">${escape(c.display_name)} · dans tes contacts</div>` : ""}
      ${name ? `<div class="artist">${escape(name)}</div>` : ""}
      <div class="artist">${c.root ? "👑 Root" : escape(c.role_label || ROLES[c.role] || c.role || "")}${c.me ? " · c'est toi" : ""}</div>
      ${!c.me && c.id && canWrite() ? `<button type="button" class="pc-btn pc-write">💬 Écrire</button>` : ""}
      ${phone ? `<div class="pc-phone"><b>${escape(phone)}</b>
        <a class="pc-btn" href="tel:${escape(phone)}">Appeler</a><a class="pc-btn secondary" href="sms:${escape(phone)}">Message</a>
        ${!c.me && !known ? `<button type="button" class="pc-btn secondary pc-add-contact">Ajouter aux contacts</button>` : ""}</div>`
        : !c.me ? `<p class="artist">${escape(c.display_name || "Ce membre")} ne montre pas son numéro dans vos groupes.</p>` : ""}
      ${c.groups?.length ? `<div class="pc-groups"><span class="artist">${c.me ? "Mes groupes" : "Groupes en commun"}</span><br>${c.groups.map(escape).join(" · ")}</div>` : ""}`;
  }

  // 🧠 Méninges : Température et domaines du membre face aux miens (agrégats seulement, /api/brain/compare).
  // Chaque ligne se lit d'un bloc (VoiceOver : « Température : toi 1 250 °M, Bob 1 100 °M ») ; les barres sont décoratives.
  const BRAIN_MAX = 2000;
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const pct = (v) => Math.round(100 * Math.min(Math.max(isNum(v) ? v : 0, 0), BRAIN_MAX) / BRAIN_MAX);
  const deg = (v) => (isNum(v) ? Math.round(v).toLocaleString("fr-CH") : "—");
  const spoken = (v) => (isNum(v) ? `${deg(v)} °M` : "pas encore joué");
  // Nom ou nombre très long, sans espace : il passe à la ligne au lieu d'élargir la fiche.
  const WRAP = 'style="min-width:0;overflow-wrap:anywhere"';
  const bar = (v, cls) => `<span class="pc-bar ${cls}" aria-hidden="true"><i style="width:${pct(v)}%"></i></span><b ${WRAP}>${escape(deg(v))}</b>`;

  function brainHtml(t) {
    if (!t || t.self) return "";
    const name = escape(t.name || "?");
    const head = `<div class="pc-brain-head"><span>🧠 Méninges</span></div>`;
    if (!t.played) return `<div class="pc-brain">${head}<p class="artist" ${WRAP}>${name} n'a pas encore joué.</p></div>`;
    const rows = [{ label: "Température", icon: "🌡️", me: t.me_played ? t.me_temperature : null, them: t.temperature },
      ...(Array.isArray(t.rows) ? t.rows.filter((r) => r && typeof r === "object") : [])];
    return `<div class="pc-brain">${head}
      <div class="pc-brain-legend" aria-hidden="true"><span class="pc-dot me"></span>Toi <span class="pc-dot them"></span><span ${WRAP}>${name}</span></div>
      ${rows.map((r) => `<div class="pc-brain-row"><span class="pc-brain-label" ${WRAP}>${escape(r.icon)} ${escape(r.label)}</span>
        <span class="pc-brain-bars" role="img" aria-label="${escape(`${r.label} : toi ${spoken(r.me)}, ${t.name || "?"} ${spoken(r.them)}`)}">${bar(r.me, "me")}${bar(r.them, "them")}</span></div>`).join("")}
      <p class="artist" ${WRAP}>${escape(t.verdict)}</p></div>`;
  }

  // La comparaison arrive après la fiche : elle n'est posée que si la fiche montre toujours ce membre
  // (fiche fermée, ou fiche d'un autre joueur ouverte entre-temps : réponse ignorée ; voir shown).
  async function addBrain(token, id, ticket) {
    try {
      const r = await fetch("/api/brain/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, target: id }) });
      if (!r.ok) return;
      const html = brainHtml((await r.json())?.target);
      if (html && sheet && ticket === shown) sheet.querySelector(".pc-body").insertAdjacentHTML("beforeend", html);
    } catch { /* Méninges indisponible : la fiche reste sans comparaison. */ }
  }

  async function open(game, pid) {
    const ticket = ++shown;
    const token = typeof freshToken === "function" ? await freshToken() : null;
    if (ticket !== shown) return;
    if (!token) return show(`<div class="pc-name">Profil</div><p class="artist">Connecte-toi avec ton numéro (Réglages) pour voir les profils.</p>`);
    show(LOADING);
    try {
      const r = await fetch("/api/account/card", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, game, pid }) });
      const data = await r.json().catch(() => ({}));
      if (ticket !== shown) return;
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Profil indisponible");
      const contact = data.me ? null : await contactName(data.id);
      if (ticket !== shown) return;
      current = data;
      show(cardHtml(data, contact));
      if (data.id && !data.me) addBrain(token, data.id, ticket);
    } catch (e) {
      if (ticket !== shown) return;
      show(`<div class="pc-name">Profil</div><p class="artist">${escape(e.message)}</p>`);
    }
  }

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-profile-pid]");
    if (!el) return;
    ev.preventDefault();
    open(el.dataset.profileGame, el.dataset.profilePid);
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && sheet) close();
    const el = ev.target.closest?.("[data-profile-pid]");
    if (el && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); open(el.dataset.profileGame, el.dataset.profilePid); }
  });

  window.ProfileCard = { open, cardHtml, brainHtml, vcard };
})();
