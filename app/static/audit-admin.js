// 📜 Journal de la soirée (Root et admins) : connexions admin, refus, invités renommés, déconnectés, bannis…
// Lecture seule : GET /api/admin/audit ; le serveur n'offre aucune route pour modifier ou effacer une entrée.
// Usage : AuditAdmin.mount(élément) ; AuditAdmin.refresh() à l'ouverture de la page.
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const PAGE = 50;
  const LABELS = {
    "admin.login": "s'est connecté à l'admin",
    "admin.login_failed": "code admin incorrect",
    "admin.denied": "accès admin refusé (compte sans droits)",
    "admin.logout": "s'est déconnecté de l'admin",
    "admin.pin": "a changé le code de la soirée",
    "admin.ban": "a bloqué",
    "admin.unban": "a débloqué",
    "admin.rename": "a renommé",
    "admin.kick": "a déconnecté",
    "admin.purge": "a retiré les titres de",
    "admin.stop": "a arrêté la soirée",
    "admin.close_game": "a fermé la partie",
    "account.link": "s'est connecté à son compte",
  };
  const when = (t) => new Date(t * 1000).toLocaleString("fr-CH", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  let root = null, entries = [], done = false;

  function detail(e) {
    const d = e.details || {};
    if (e.action === "admin.rename") return ` → « ${escape(d.to)} »`;
    if (e.action === "admin.ban") return d.minutes === "sans limite" ? " (sans limite)" : ` (${escape(d.minutes)} min)`;
    if (e.action === "admin.login") return d.method ? ` (${escape(d.method)})` : "";
    return "";
  }

  function row(e) {
    const target = e.target && e.action !== "account.link" && !["admin.login", "admin.denied"].includes(e.action)
      ? ` <b>${escape(e.target.name || e.target.id)}</b>` : "";
    return `<div class="track" data-audit-row><div class="meta">
      <div class="title"><b>${escape(e.actor)}</b> ${escape(LABELS[e.action] || e.action)}${target}${detail(e)}</div>
      <div class="artist">${when(e.at)}${e.ip ? ` · ${escape(e.ip)}` : ""}</div></div></div>`;
  }

  function render() {
    root.querySelector("[data-audit-list]").innerHTML = entries.length ? entries.map(row).join("") : `<p class="empty">Rien dans le journal pour l'instant</p>`;
    root.querySelector("[data-audit-more]").classList.toggle("hidden", done);
  }

  async function load(more) {
    const before = more && entries.length ? `&before=${encodeURIComponent(entries[entries.length - 1].id)}` : "";
    try {
      const r = await fetch(`/api/admin/audit?limit=${PAGE}${before}`, { credentials: "same-origin" });
      if (!r.ok) throw new Error();
      const page = (await r.json()).entries || [];
      entries = more ? entries.concat(page) : page;
      done = page.length < PAGE;
      render();
    } catch {
      root.querySelector("[data-audit-list]").innerHTML = `<p class="empty">Journal indisponible, réessaie</p>`;
    }
  }

  window.AuditAdmin = {
    mount(el) {
      root = el;
      root.innerHTML = `<h2>📜 Journal</h2>
        <p class="sub" style="margin-top:-4px;font-size:.85rem">Qui a fait quoi dans l'admin de la soirée. Rien n'y est modifiable.</p>
        <div data-audit-list class="list"></div>
        <button type="button" class="secondary hidden" data-audit-more style="width:100%;margin-top:8px">Plus ancien</button>`;
      root.querySelector("[data-audit-more]").addEventListener("click", () => load(true));
    },
    refresh() { if (root) load(false); },
  };
})();
