// 👤 Fiche profil d'un joueur (jeux) : on touche le nom ou la photo d'un joueur qui a un compte Party.
// Le serveur ne reçoit que la partie et le numéro du joueur ; la base applique les choix de la personne
// (nom et prénom seulement s'ils sont publics, numéro seulement aux membres de ses groupes).
// Usage : un élément avec data-profile-pid="<pid>" dans l'écran d'une partie (code dans data-profile-game).
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ROLES = { guest: "Guest", guestplus: "Guest+", basic: "Membre", member: "Membre VIP", organizer: "Organisateur", coadmin: "Co-admin", admin: "Admin" };
  let sheet = null;
  const OUT_SAFETY_MS = 400;
  // Chargement : la silhouette de la fiche (photo ronde, lignes) plutôt qu'un texte d'attente.
  const LOADING = `<div class="pc-photo pc-skel" role="status" aria-label="Chargement du profil…"></div>
    <i class="pc-skel pc-skel-line"></i><i class="pc-skel pc-skel-line short"></i>`;

  // La fiche monte du bas ; « Fermer » ou le fond la font redescendre, puis elle est retirée.
  function close() {
    const leaving = sheet;
    sheet = null;
    if (!leaving) return;
    leaving.classList.add("pc-out");
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
    sheet = document.createElement("div");
    sheet.className = "pc-backdrop";
    sheet.innerHTML = `<div class="pc-card" role="dialog" aria-modal="true" aria-label="Profil"><div class="pc-body">${html}</div>
      <button type="button" class="secondary pc-close">Fermer</button></div>`;
    const mine = sheet;
    sheet.addEventListener("click", (ev) => { if (sheet === mine && (ev.target === mine || ev.target.closest(".pc-close"))) close(); });
    document.body.append(sheet);
    sheet.querySelector(".pc-close").focus();
  }

  function cardHtml(c) {
    const name = [c.first_name, c.last_name].filter(Boolean).join(" ");
    const phone = c.phone ? `+${String(c.phone).replace(/^\+/, "")}` : "";
    const initial = escape((c.display_name || "?").trim().charAt(0).toUpperCase());
    return `<div class="pc-photo">${c.photo ? `<img src="${escape(c.photo)}" alt="">` : initial}</div>
      <div class="pc-name">${escape(c.display_name || "Profil à compléter")}</div>
      ${name ? `<div class="artist">${escape(name)}</div>` : ""}
      <div class="artist">${c.root ? "👑 Root" : escape(ROLES[c.role] || c.role || "")}${c.me ? " · c'est toi" : ""}</div>
      ${phone ? `<div class="pc-phone"><b>${escape(phone)}</b>
        <a class="pc-btn" href="tel:${escape(phone)}">Appeler</a><a class="pc-btn secondary" href="sms:${escape(phone)}">Message</a></div>` : ""}
      ${c.groups?.length ? `<div class="pc-groups"><span class="artist">${c.me ? "Mes groupes" : "Groupes en commun"}</span><br>${c.groups.map(escape).join(" · ")}</div>` : ""}`;
  }

  // 🧠 Méninges : Température et domaines du membre face aux miens (agrégats seulement, /api/brain/compare).
  const BRAIN_MAX = 2000;
  const pct = (v) => Math.round(100 * Math.min(Math.max(v || 0, 0), BRAIN_MAX) / BRAIN_MAX);
  const bar = (v, cls) => `<span class="pc-bar ${cls}"><i style="width:${pct(v)}%"></i></span><b>${v == null ? "—" : escape(v)}</b>`;

  function brainHtml(t) {
    if (!t || t.self) return "";
    const head = `<div class="pc-brain-head"><span>🧠 Méninges</span></div>`;
    if (!t.played) return `<div class="pc-brain">${head}<p class="artist">${escape(t.name)} n'a pas encore joué.</p></div>`;
    const rows = [{ label: "Température", icon: "🌡️", me: t.me_played ? t.me_temperature : null, them: t.temperature }, ...t.rows];
    return `<div class="pc-brain">${head}
      <div class="pc-brain-legend"><span class="pc-dot me"></span>Toi <span class="pc-dot them"></span>${escape(t.name)}</div>
      ${rows.map((r) => `<div class="pc-brain-row"><span class="pc-brain-label">${escape(r.icon)} ${escape(r.label)}</span>
        <span class="pc-brain-bars">${bar(r.me, "me")}${bar(r.them, "them")}</span></div>`).join("")}
      <p class="artist">${escape(t.verdict)}</p></div>`;
  }

  async function addBrain(token, id) {
    const target = sheet;
    try {
      const r = await fetch("/api/brain/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, target: id }) });
      if (!r.ok) return;
      const html = brainHtml((await r.json()).target);
      if (html && sheet === target) sheet.querySelector(".pc-body").insertAdjacentHTML("beforeend", html);
    } catch { /* Méninges indisponible : la fiche reste sans comparaison. */ }
  }

  async function open(game, pid) {
    const token = typeof freshToken === "function" ? await freshToken() : null;
    if (!token) return show(`<div class="pc-name">Profil</div><p class="artist">Connecte-toi avec ton numéro (Réglages) pour voir les profils.</p>`);
    show(LOADING);
    try {
      const r = await fetch("/api/account/card", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, game, pid }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Profil indisponible");
      show(cardHtml(data));
      if (data.id && !data.me) addBrain(token, data.id);
    } catch (e) {
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

  window.ProfileCard = { open, cardHtml, brainHtml };
})();
