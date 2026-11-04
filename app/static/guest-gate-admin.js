// 🔐 Réglages de l'admin « Parties en invité avant compte » et « Titres en invité par soirée » (app/guest_gate.py).
// Même carte dans l'app (people-admin.js, sous la musique) et dans /admin (Réglages). Chaque changement est
// enregistré tout de suite et noté dans le journal de la soirée.
// Usage : GuestGateAdmin.mount(élément) ; GuestGateAdmin.render(état.guest_gate) à chaque état de l'admin.
(function () {
  const MAX = 50;
  const FIELDS = {
    games: { label: "🎮 Parties en invité avant compte",
      help: (n) => n === 0 ? "Compte obligatoire pour jouer dès l'arrivée."
        : `Après ${n} partie${n > 1 ? "s" : ""}, une nouvelle partie demande un compte (numéro + SMS). Une partie commencée n'est jamais interrompue ; message doux dès la 1re partie.` },
    tracks: { label: "🎶 Titres en invité par soirée",
      help: (n) => n === 0 ? "Compte requis pour proposer des titres (la musique reste visible)."
        : `Un invité propose au plus ${n} titre${n > 1 ? "s" : ""} par soirée ; avec un compte, sans cette limite.` },
  };
  const roots = [];
  let current = null;

  const card = () => `<div class="card gate-admin" style="margin-top:8px">
    <h3 style="margin:0 0 4px">Comptes des invités</h3>
    <p class="artist" style="margin:0 0 8px;white-space:normal">Rejoindre la soirée avec le code et un prénom reste possible sans compte.</p>
    ${Object.entries(FIELDS).map(([key, f]) => `<div class="switch-row" style="margin-top:8px;align-items:flex-start">
      <span class="grow"><span>${f.label}</span><span class="artist" data-gga-help="${key}" style="display:block;white-space:normal"></span></span>
      <span class="stepper" style="display:flex;gap:6px;align-items:center">
        <button type="button" class="secondary" data-gga-step="${key}" data-d="-1" aria-label="Moins">−</button>
        <b data-gga-val="${key}" aria-live="polite" style="min-width:2ch;text-align:center">·</b>
        <button type="button" class="secondary" data-gga-step="${key}" data-d="1" aria-label="Plus">+</button>
      </span></div>`).join("")}
  </div>`;

  function paint(root) {
    if (!current) return;
    for (const key of Object.keys(FIELDS)) {
      root.querySelector(`[data-gga-val="${key}"]`).textContent = current[key];
      root.querySelector(`[data-gga-help="${key}"]`).textContent = FIELDS[key].help(current[key]);
    }
  }

  async function step(b) {
    if (!current) return;
    const key = b.dataset.ggaStep, next = Math.max(0, Math.min(MAX, current[key] + +b.dataset.d));
    if (next === current[key]) return;
    const before = current;
    current = { ...current, [key]: next };
    roots.forEach(paint);
    try {
      const r = await fetch("/api/admin/guest-gate", { method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [key]: next }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Réglage non enregistré, réessaie");
      current = data.guest_gate;
    } catch (e) {
      current = before;
      if (typeof toast === "function") toast(e.message, "err");
    }
    roots.forEach(paint);
  }

  window.GuestGateAdmin = Object.freeze({
    mount(el) {
      if (!el) return;
      el.innerHTML = card();
      el.addEventListener("click", (ev) => { const b = ev.target.closest("[data-gga-step]"); if (b) step(b); });
      roots.push(el);
      paint(el);
    },
    render(settings) {
      if (!settings) return;
      current = { games: settings.games, tracks: settings.tracks };
      roots.forEach(paint);
    },
  });
})();
