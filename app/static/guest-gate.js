// 🔐 Compte progressivement obligatoire (décision de l'admin du 04.11, serveur : app/guest_gate.py).
// Invité sans compte : message doux après sa 1re partie (« Garde tes scores… »), puis au-delà de N parties
// (réglé par l'admin) une nouvelle partie demande un compte : écran clair, « Créer mon compte » ouvre le parcours SMS
// (Réglages › Se connecter), puis on revient directement dans la partie. Musique : au plus M titres par soirée.
// Le serveur décide de tout (compteur par identifiant d'invité) ; cette page ne fait qu'afficher.
// Usage : GuestGate.gameSeen(partie) à chaque rendu, GuestGate.refused(erreur) après un refus,
// GuestGate.music(state.guest_tracks), GuestGate.accountLinked() une fois le compte relié.
(function () {
  const RETURN_KEY = "vp_gate_return";   // partie à rejoindre une fois le compte créé
  const session = {
    get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { v ? sessionStorage.setItem(k, v) : sessionStorage.removeItem(k); } catch { /* stockage bloqué */ } },
  };
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const plural = (n, word) => `${n} ${word}${n > 1 ? "s" : ""}`;
  const signedIn = () => (typeof account !== "undefined" && !!account) || (typeof guestId === "string" && guestId.startsWith("acct-"));
  let prev = null;
  const nudged = new Set(), asked = new Set();

  function sheet() {
    let el = document.getElementById("gateModal");
    if (!el) {
      el = document.createElement("div");
      el.id = "gateModal";
      el.className = "g-modal hidden";
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-modal", "true");
      el.setAttribute("aria-labelledby", "gateTitle");
      document.body.appendChild(el);
    }
    return el;
  }
  function close() { sheet().classList.add("hidden"); }

  // Écran « compte requis » (jeux) ou « garde tes scores » (doux) : même feuille, textes différents.
  function open({ kind, played, limit, code }) {
    const el = sheet();
    const title = kind === "soft" ? "Garde tes scores 🏆"
      : kind === "music" ? "Encore plus de musique 🎶" : "Crée ton compte pour continuer 🎮";
    const text = kind === "soft" ? "Crée ton compte en 30 secondes, juste ton numéro : tes scores de ce soir te suivent."
      : kind === "music" ? (limit ? `Tu as proposé tes ${plural(limit, "titre")} de la soirée en invité.` : "Proposer des titres demande un compte ce soir.")
        + " Crée ton compte en 30 secondes, juste ton numéro, pour en proposer d'autres."
      : (limit ? `Tu as joué tes ${plural(limit, "partie")} en invité.` : "Ce soir, jouer demande un compte.")
        + " Crée ton compte en 30 secondes, juste ton numéro : tes scores de ce soir te suivent, et tu reviens directement dans la partie.";
    el.innerHTML = `<div class="g-sheet gate-sheet" data-gate="${escape(kind)}">
      <div class="g-sheet-grab" aria-hidden="true"></div>
      <h2 id="gateTitle">${escape(title)}</h2>
      <p class="sub">${escape(text)}</p>
      ${kind === "games" && played ? `<p class="artist">${escape(plural(played, "partie"))} jouée${played > 1 ? "s" : ""} en invité</p>` : ""}
      <button type="button" data-gate-create>Créer mon compte</button>
      <button type="button" class="secondary" data-gate-later>${kind === "games" ? "Pas maintenant" : "Plus tard"}</button>
    </div>`;
    el.dataset.code = code || "";
    el.dataset.kind = kind;
    el.classList.remove("hidden");
    el.querySelector("[data-gate-create]").focus();
  }

  document.addEventListener("click", (ev) => {
    const el = document.getElementById("gateModal");
    if (!el || el.classList.contains("hidden")) return;
    if (ev.target.closest("[data-gate-create]")) {
      // Partie à rejoindre après la création du compte (la musique, elle, reste sur l'onglet Musique).
      session.set(RETURN_KEY, el.dataset.kind === "music" ? "music" : el.dataset.code || "games");
      close();
      if (typeof showTab === "function") showTab("account");
    } else if (ev.target.closest("[data-gate-later]") || ev.target === el) close();
  });
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") close(); });

  window.GuestGate = Object.freeze({
    /** Chaque rendu d'une partie : message doux à la fin d'une partie, écran « compte requis » sur une nouvelle. */
    gameSeen(g) {
      const gate = g?.gate;
      const ended = prev && g && prev.id === g.id && prev.me && prev.phase !== "end" && g.phase === "end";
      prev = g ? { id: g.id, me: !!g.me, phase: g.phase } : null;
      if (!gate || signedIn()) return;
      if (gate.blocked && !g.me && !g.is_owner && g.type !== "room" && !asked.has(g.code)) {
        asked.add(g.code);
        return open({ kind: "games", played: gate.played, limit: gate.limit, code: g.code });
      }
      if (ended && gate.nudge && !nudged.has(g.id)) {
        nudged.add(g.id);
        open({ kind: "soft", code: "" });
      }
    },
    /** Erreur du serveur : true si c'était « compte requis » (l'écran s'est ouvert à la place d'un message). */
    refused(e, code) {
      const d = e?.detail;
      if (!d || typeof d !== "object" || !d.account_required) return false;
      if (d.account_required === "music") open({ kind: "music", limit: d.limit });
      else { if (d.code) asked.add(d.code); open({ kind: "games", played: d.played, limit: d.limit, code: d.code || code || "" }); }
      return true;
    },
    /** Onglet Musique : titres encore possibles ce soir en invité (null : compte, sans cette limite). */
    music(t) {
      const el = document.getElementById("guestTracks");
      if (!el) return;
      const show = !!t && !signedIn();
      el.classList.toggle("hidden", !show);
      if (!show) return;
      el.innerHTML = t.left > 0
        ? `En invité : encore <b>${escape(plural(t.left, "titre"))}</b> à proposer ce soir. <button type="button" class="gate-link" data-gate-music>Créer mon compte</button> pour en proposer plus.`
        : `${t.limit ? `Tu as proposé tes ${escape(plural(t.limit, "titre"))} de la soirée en invité.` : "Proposer des titres demande un compte ce soir."} <button type="button" class="gate-link" data-gate-music>Créer mon compte</button> (juste ton numéro) pour en proposer d'autres.`;
    },
    /** Compte relié (linkAccount) : retour direct dans la partie (ou la musique) d'où l'on venait. */
    accountLinked() {
      const back = session.get(RETURN_KEY);
      if (!back) return;
      session.set(RETURN_KEY, "");
      close();
      if (typeof showTab !== "function") return;
      if (back === "music") return showTab("music");
      showTab("games");
      if (/^\d{4}$/.test(back) && typeof setGame === "function") {
        setGame(back);
        autoJoin = true;   // games.js : la partie est rejointe au prochain chargement
        refreshGame();
      }
    },
  });

  document.addEventListener("click", (ev) => {
    if (!ev.target.closest("[data-gate-music]")) return;
    session.set(RETURN_KEY, "music");
    if (typeof showTab === "function") showTab("account");
  });
})();
