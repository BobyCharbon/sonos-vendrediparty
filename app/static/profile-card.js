// 👤 Fiche profil d'un joueur (jeux) : on touche le nom ou la photo d'un joueur qui a un compte Party.
// Le serveur ne reçoit que la partie et le numéro du joueur ; la base applique les choix de la personne
// (nom et prénom seulement s'ils sont publics, numéro seulement aux membres de ses groupes).
// Usage : un élément avec data-profile-pid="<pid>" dans l'écran d'une partie (code dans data-profile-game).
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ROLES = { guest: "Guest", guestplus: "Guest+", basic: "Membre", member: "Membre VIP", organizer: "Organisateur", coadmin: "Co-admin", admin: "Admin" };
  let sheet = null;

  function close() {
    sheet?.remove();
    sheet = null;
  }

  function show(html) {
    close();
    sheet = document.createElement("div");
    sheet.className = "pc-backdrop";
    sheet.innerHTML = `<div class="pc-card" role="dialog" aria-modal="true" aria-label="Profil">${html}
      <button type="button" class="secondary pc-close">Fermer</button></div>`;
    sheet.addEventListener("click", (ev) => { if (ev.target === sheet || ev.target.closest(".pc-close")) close(); });
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

  async function open(game, pid) {
    const token = typeof freshToken === "function" ? await freshToken() : null;
    if (!token) return show(`<div class="pc-name">Profil</div><p class="artist">Connecte-toi avec ton numéro (Réglages) pour voir les profils.</p>`);
    show(`<p class="artist" role="status">Chargement du profil…</p>`);
    try {
      const r = await fetch("/api/account/card", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, game, pid }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Profil indisponible");
      show(cardHtml(data));
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

  window.ProfileCard = { open, cardHtml };
})();
