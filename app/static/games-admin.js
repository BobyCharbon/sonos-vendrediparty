// 🎮 Parties en cours de toute la soirée — en haut de l'onglet Jeux de l'app (compte admin), comme dans /admin :
// un bloc compact par partie (jeu, code, durée, animateur, joueurs) ; un toucher déplie le détail
// (réglages, gorgées, dernière activité) avec « Rejoindre » et « Fermer la partie ».
// Reçoit l'état admin partagé (music-admin.js le transmet : GamesAdmin.render) ; une fermeture renvoie le nouvel
// état à tout l'onglet (onState). Usage : GamesAdmin.mount(élément, { onState(état) }) ; GamesAdmin.render(état).
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const notify = (msg, kind) => (typeof toast === "function" ? toast(msg, kind) : alert(msg));
  const hhmm = (t) => new Date(t * 1000).toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
  const duration = (sec) => { const m = Math.max(0, Math.floor(sec / 60)); return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`; };
  const PHASES = { lobby: "Inscriptions", words: "Indices", vote: "Vote", white_guess: "Devinette de Mr. White",
    reveal: "Résultat de la manche", end: "Terminée", question: "Question", results: "Résultats",
    answer: "Réponse en secret", guess: "À voix haute", judge: "Points", scored: "Résultat du duo",
    bet: "Mises", play: "Partie en cours", spun: "Résultat", card: "En séance", deal: "Distribution", pyramid: "Pyramide",
    memory: "Test de mémoire", memres: "Résultats de mémoire", boatpick: "Qui fait le bateau ?", boat: "Le bateau", answering: "Réponses en secret" };
  const EMOJI = { undercover: "🕵️", whoof: "🙋", likely: "🫵", debate: "⚖️", never: "🍻", roulette: "🎡", blackjack: "🃏", casino: "🎰", divan: "🛋️", tmc: "💞",
    pyramid: "🔺", quiz: "🧠", purity: "😇", room: "🏠", president: "👑", neon: "🥊", island: "🏝️", heist: "💎", biskit: "🍪" };
  let root = null, onState = () => {}, games = [];
  const open = new Set();

  function card(g) {
    const isOpen = open.has(g.code), players = g.players_detail || [];
    const mine = typeof myGame !== "undefined" && myGame === g.code;
    const code = escape(g.code);
    return `<div class="gs-card ${isOpen ? "open" : ""}">
      <button type="button" class="gs-head" data-ga-open="${code}" aria-expanded="${isOpen}">
        <span class="gs-ico" aria-hidden="true">${EMOJI[g.type] || "🎮"}</span>
        <span class="gs-main"><b>${escape(g.name)}</b>
          <small>créée à ${hhmm(g.created_at)} · ⏱ <span data-ga-timer="${g.created_at}">${duration(Date.now() / 1000 - g.created_at)}</span> · par ${escape(g.host || "?")}</small>
          <small>${escape(PHASES[g.phase] || g.phase)}${g.round ? ` · n° ${g.round}` : ""} · ${players.length} joueur${players.length > 1 ? "s" : ""}</small></span>
        <span class="gs-code">${code}</span><span class="gs-chev" aria-hidden="true">▾</span>
      </button>
      <div class="gs-players">${players.map((p) => `<span class="pill">${p.host ? "🎲 " : ""}${escape(p.name)}${p.manual ? " ✍️" : ""}${p.pending ? " ⏳" : ""}</span>`).join("") || `<span class="artist">Personne pour l'instant</span>`}</div>
      ${isOpen ? `<div class="gs-more">
        ${g.facts?.length ? `<ul class="gs-facts">${g.facts.map((f) => `<li>${escape(f)}</li>`).join("")}</ul>` : ""}
        <div class="gs-table">${players.map((p) => `<div class="gs-row"><span class="grow">${p.host ? "🎲 " : ""}${escape(p.name)}${p.manual ? " <small>✍️ sans téléphone</small>" : ""}${p.pending ? " <small>⏳ attend l'animateur</small>" : ""}</span>
          <span>${p.extra ? escape(p.extra) + " · " : ""}🍻 ${p.drink} · 🎁 ${p.give}</span></div>`).join("")}</div>
        <div class="artist">Dernière activité à ${hhmm(g.updated_at)} · code ${code}</div>
        <div class="row" style="margin-top:8px">
          ${mine ? `<span class="pill live">ta partie</span>` : `<button type="button" class="secondary grow" data-ga-join="${code}">Rejoindre</button>`}
          <button type="button" class="danger grow" data-ga-close="${code}">Fermer la partie</button>
        </div></div>` : ""}
    </div>`;
  }

  function render(s) {
    if (!root || !s) return;
    games = s.games || [];
    root.classList.toggle("hidden", !games.length);
    root.innerHTML = games.length ? `<h2 class="ga-title">Parties en cours <span class="badge">${games.length}</span></h2>
      <div class="ga-list">${games.map(card).join("")}</div>` : "";
  }

  async function close(code, b) {
    if (!confirm(`Fermer la partie ${code} pour tous ses joueurs ?`)) return;
    b.disabled = true;
    try {
      const r = await fetch("/api/admin/games/close", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guest_id: "admin-console", action: "end", target: code }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Erreur, réessaie");
      onState(data);
      notify("Partie fermée", "ok");
    } catch (e) { notify(e.message, "err"); b.disabled = false; }
  }

  function onClick(ev) {
    const t = ev.target;
    const head = t.closest("[data-ga-open]");
    if (head) {
      const code = head.dataset.gaOpen;
      open.has(code) ? open.delete(code) : open.add(code);
      return render({ games });
    }
    const join = t.closest("[data-ga-join]");
    if (join && typeof setGame === "function") {
      // Comme un code tapé : on ouvre la partie et on la rejoint.
      setGame(join.dataset.gaJoin); autoJoin = true; refreshGame();
      return;
    }
    const c = t.closest("[data-ga-close]");
    if (c) close(c.dataset.gaClose, c);
  }

  window.GamesAdmin = {
    mount(el, opts = {}) {
      root = el;
      onState = opts.onState || onState;
      root.addEventListener("click", onClick);
      // Durée des parties : à jour chaque seconde.
      setInterval(() => root.querySelectorAll("[data-ga-timer]").forEach((x) => { x.textContent = duration(Date.now() / 1000 - +x.dataset.gaTimer); }), 1000);
    },
    render,
  };
})();
