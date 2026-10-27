// Président : seul le serveur connaît les mains adverses et valide les coups.
window.President = (() => {
  let selected = new Set(), dealKey = "", hidden = false, busy = false;
  const crown = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m7 16 9 7 8-14 8 14 9-7-5 22H12z"/><path d="M14 43h20"/><circle cx="24" cy="6" r="2"/></svg>`;
  const rules = `<h3>Le premier sans cartes devient Président</h3>
    <p>De <b>3 à 6 joueurs</b>, chacun sur son téléphone. Les 54 cartes sont distribuées, avec deux jokers. Tes cartes restent privées, même pour l'animateur.</p>
    <h3>Jouer plus fort</h3><p>Pose une carte, une paire, un brelan ou un carré. Le suivant doit poser <b>le même nombre de cartes, d'une valeur égale ou supérieure</b>, ou passer.</p>
    <h3>Le 2 ferme le pli</h3><p>Un <b>2</b>, seul, en paire, en brelan ou en carré (jokers compris), ferme le pli aussitôt : celui qui l'a posé rouvre. S'il vient de poser ses dernières cartes, c'est le joueur suivant qui ouvre.</p>
    <h3>Compléter la famille</h3><p>Tu peux poser <b>la même valeur</b> (un valet sur un valet, deux valets sur deux valets). Dès lors, c'est « <b>valet ou rien</b> » : les suivants posent la même valeur, ou passent. Quand les <b>quatre cartes</b> de la valeur sont sur le pli (jokers joués comme elle compris), la famille est complète : le pli est ramassé et celui qui l'a complétée rouvre. Celui qui a les cartes qui manquent peut compléter la famille <b>même si ce n'est pas son tour</b>.</p>
    <p>Du plus faible au plus fort : <b>3, 4, 5, 6, 7, 8, 9, 10, Valet, Dame, Roi, As, 2</b>. Les couleurs ne départagent pas les cartes.</p>
    <h3>Vos jokers</h3><p>Un joker seul vaut un <b>3</b>. Avec d'autres cartes de même valeur, il les duplique : deux Rois et un joker font un brelan de Rois. Deux jokers seuls font une paire de 3. Pas de combinaison de plus de quatre cartes.</p>
    <h3>Passer et reprendre la main</h3><p>Tu peux rejouer à ton prochain tour, même après avoir passé. Quand tous les autres passent après un coup, le pli est écarté. La dernière personne à avoir joué ouvre un nouveau pli, ou le joueur suivant si elle a terminé. On ne peut pas passer pour ouvrir un pli.</p>
    <p>La première manche commence chez la personne qui possède le 3 de trèfle. Après les échanges, le Trou du cul commence. Tu peux finir avec un 2 ou un joker. Pas de révolution.</p>
    <h3>Les places et les échanges</h3><p>Le premier devient Président, le dernier Trou du cul. À partir de quatre joueurs, il y a aussi un Vice-président et un Vice-trou du cul.</p>
    <p>À la donne suivante, le Trou du cul donne ses <b>deux meilleures cartes</b> au Président, qui en choisit deux à lui rendre. Les vice échangent une carte. <b>Les jokers comptent comme des 3</b> pour choisir les meilleures cartes. Les choix restent secrets et tous les échanges se font ensemble.</p>
    <p>Le premier marque autant de points qu'il a d'adversaires, puis un point de moins par place, jusqu'à zéro pour le dernier. Les points s'ajoutent au tableau de la salle.</p>
    <h3>Arrivées et départs</h3><p>Un retardataire attend la prochaine donne. Un joueur qui quitte la manche est classé en dernier et ses cartes sont écartées. Après un changement de joueurs, la prochaine donne commence sans échange. Une simple déconnexion conserve la main : reviens avec le même navigateur.</p>`;

  function card(c, interactive = false, effective = "") {
    const picked = selected.has(c.id), tag = interactive ? "button" : "span";
    const attr = interactive ? ` type="button" data-pr-card="${esc(c.id)}" aria-pressed="${picked}"` : ` role="img"`;
    const name = c.label + (effective && c.joker ? `, joué comme ${effective}` : "");
    return `<${tag}${attr} class="pr-card ${c.red ? "pr-red" : ""} ${c.joker ? "pr-joker" : ""} ${interactive && picked ? "pr-selected" : ""}" aria-label="${esc(name)}">
      <span class="pr-card-corner" aria-hidden="true">${c.joker ? "Jkr" : esc(c.rank)}<small>${c.suit || "✦"}</small></span>
      <span class="pr-card-center" aria-hidden="true">${c.joker ? "✦" : c.suit}</span>
      ${interactive && picked ? `<span class="pr-card-check" aria-hidden="true">✓</span>` : ""}
      ${c.joker ? `<span class="pr-card-joker" aria-hidden="true">${effective ? "Vaut " + esc(effective) : "Joker"}</span>` : ""}
    </${tag}>`;
  }

  function decision(g) {
    const v = g.president, cards = v.hand.filter(c => selected.has(c.id)), x = v.exchange;
    if (g.phase === "exchange") {
      if (!x.count || x.sent) return {ok: false, text: "En attente des autres échanges…"};
      return {ok: cards.length === x.count, text: `Choisis ${x.count} carte${x.count > 1 ? "s" : ""} à donner à ${x.to}.`};
    }
    if (!cards.length) return {ok: false, text: v.pile ? `À battre : ${v.pile.cards.length} carte${v.pile.cards.length > 1 ? "s" : ""} de valeur ${v.pile.rank}.` : "Choisis une carte ou plusieurs cartes de même valeur."};
    const values = [...new Set(cards.filter(c => !c.joker).map(c => c.value))], value = values[0] ?? 0;
    if (values.length > 1) return {ok: false, text: "Choisis une seule valeur ; les jokers peuvent la compléter."};
    if (v.pile && cards.length !== v.pile.cards.length) return {ok: false, text: `Il faut exactement ${v.pile.cards.length} carte${v.pile.cards.length > 1 ? "s" : ""}.`};
    const same = !!v.pile && value === v.pile.value, completes = same && v.pile.family + cards.length >= 4;
    if (v.pile?.locked && !same) return {ok: false, text: `${v.pile.rank} ou rien : pose la même valeur, ou passe.`};
    if (v.pile && !same && value < v.pile.value) return {ok: false, text: `Choisis une valeur égale ou supérieure à ${v.pile.rank}, ou passe.`};
    if (!v.my_turn && !completes) return {ok: false, text: same ? `Hors tour, tu ne peux poser que si ça complète la famille de ${v.pile.rank}.` : "Attends ton tour."};
    if (completes) return {ok: true, out: !v.my_turn, text: `Tu complètes la famille de ${v.pile.rank} : le pli est pour toi !`};
    if (value === 12) return {ok: true, text: `${cards.length > 1 ? `${cards.length} × 2` : "Un 2"} : tu fermes le pli et tu rouvres.`};
    return {ok: true, text: `${["", "Une carte", "Une paire", "Un brelan", "Un carré"][cards.length]} de ${["3", "4", "5", "6", "7", "8", "9", "10", "Valets", "Dames", "Rois", "As", "2"][value]}.`};
  }

  function html(g) {
    const v = g.president, key = `${g.id}:${g.round}`;
    if (dealKey !== key) { dealKey = key; selected.clear(); hidden = false; }
    selected = new Set([...selected].filter(id => v.hand.some(c => c.id === id)));
    const join = !g.me && g.players.length < 6 ? `<button type="button" class="secondary" data-gact="join">${g.phase === "lobby" || g.phase === "end" ? "Prendre place" : "Rejoindre à la prochaine donne"}</button>` : "";
    if (g.phase === "lobby") return `<section class="pr-lobby">
      <h2>La présidence se joue aux cartes.</h2><p>Vide ta main avant les autres. À la prochaine donne, les places changent les cartes.</p>
      <div class="pr-rule-note"><b>Votre variante</b><span>54 cartes. Un joker seul vaut un 3 ; accompagné, il duplique une carte.</span></div>
      ${v.notice ? `<p class="pr-note" role="status">${esc(v.notice)}</p>` : ""}
      <p class="pr-ready">${g.players.length < 3 ? `Encore ${3 - g.players.length} joueur${g.players.length < 2 ? "s" : ""} pour distribuer.` : `${g.players.length} joueurs prêts. Chacun garde sa main sur son téléphone.`}</p>
      ${g.is_host ? `<button type="button" class="pr-primary" data-gact="start" ${g.players.length < 3 ? "disabled" : ""}>Distribuer les 54 cartes</button>` : `<p class="pr-note">${esc(g.host_name)} distribuera les cartes.</p>`}${join}</section>`;

    if (g.phase === "end") return `<section class="pr-finish">
      <div class="pr-crown" aria-hidden="true">${crown}</div><h2>${esc(v.ranking[0]?.name || "Manche terminée")}</h2>
      <p class="pr-winner-label">Président de la manche ${g.round}</p>
      <ol class="pr-ranking">${v.ranking.map(r => `<li class="${r.me ? "pr-is-me" : ""}"><span class="pr-place">${r.place}</span><span><b>${esc(r.name)}${r.me ? " (toi)" : ""}</b><small>${esc(r.role)}${r.departed ? " · abandon" : ""}</small></span><strong>${r.points}<small>pts</small></strong></li>`).join("")}</ol>
      <p class="pr-note">Points cumulés. Les échanges commencent à la prochaine distribution si les joueurs restent les mêmes.</p>
      ${g.is_host ? `<button type="button" class="pr-primary" data-gact="next" ${g.players.length < 3 ? "disabled" : ""}>${g.players.length < 3 ? "En attente de 3 joueurs" : "Distribuer la manche suivante"}</button>` : `<p class="pr-note">${esc(g.host_name)} peut lancer la prochaine manche.</p>`}${join}</section>`;

    const x = v.exchange, canChoose = g.phase === "play" || (x?.count && !x.sent);
    const turn = v.seats.find(p => p.pid === v.turn);
    const title = x ? "Les cartes changent de mains" : v.my_turn ? "À toi de jouer" : `Au tour de ${turn?.name || "…"}`;
    const mine = v.seats.find(p => p.me), d = decision(g);
    const waiting = !!g.me?.waiting;
    const status = waiting ? "Tu prendras place à la prochaine donne." : mine?.place ? `Tu as terminé à la place ${mine.place}.` : !g.me ? "Tu regardes la partie. Les mains restent privées." : "";
    const seats = `<div class="pr-seats" aria-label="Autour de la table">${v.seats.map(p => `<div class="pr-seat ${p.turn ? "pr-turn" : ""} ${p.me ? "pr-is-me" : ""}" data-key="seat-${esc(p.pid)}">
      <span class="pr-seat-name">${esc(p.name)}${p.me ? " · toi" : ""}</span><b>${p.departed ? "Parti" : p.place ? `${p.place}${p.place === 1 ? "er" : "e"}` : `${p.count} cartes`}</b><small>${p.passed ? "Passe" : p.turn ? "Joue" : esc(p.role || "À table")}</small></div>`).join("")}</div>`;
    const table = x ? `<div class="pr-exchange">
      <p>${x.count ? x.sent ? `${x.automatic ? "Tes meilleures cartes sont réservées" : "Ton choix est enregistré"} pour <b>${esc(x.to)}</b>.` : `Tu donnes <b>${x.count} carte${x.count > 1 ? "s" : ""}</b> à <b>${esc(x.to)}</b>. Choisis avant de recevoir.` : "Ta place ne demande aucun échange."}</p>
      ${x.cards.length ? `<div class="pr-pile">${x.cards.map(c => card(c)).join("")}</div>` : ""}
      <p class="pr-note" role="status">En attente de ${x.pending.map(esc).join(", ")}.</p></div>`
      : `<div class="pr-table" data-key="pile-${g.round}-${v.trick}">
          <p class="pr-table-caption">${v.pile ? `${esc(v.pile.name)} a posé` : `Pli ${v.trick} · table libre`}</p>
          <div class="pr-pile">${v.pile ? v.pile.cards.map(c => card(c, false, v.pile.rank)).join("") : `<span class="pr-empty-pile" aria-hidden="true">♣</span>`}</div>
          <p class="pr-note">${v.pile ? `${v.pile.cards.length} carte${v.pile.cards.length > 1 ? "s" : ""} de valeur ${esc(v.pile.rank)}` : "Une nouvelle combinaison peut ouvrir le pli."}</p>
          ${v.pile?.locked ? `<p class="pr-family" role="status"><b>${esc(v.pile.rank)} ou rien</b> · famille ${v.pile.family}/4</p>` : ""}</div>`;
    const hand = v.hand.length && !waiting && !mine?.place ? `<section class="pr-hand-section">
      <div class="pr-hand-heading"><h3>Ta main <span>${v.hand.length}</span></h3><button type="button" class="pr-privacy" data-pr="privacy" aria-pressed="${hidden}">${hidden ? "Voir mes cartes" : "Masquer"}</button></div>
      ${hidden ? `<div class="pr-hidden-hand"><span aria-hidden="true">${crown}</span><p>Tes cartes sont masquées.</p><button type="button" class="secondary" data-pr="privacy">Voir mes cartes</button></div>` : `<div class="pr-hand" role="group" aria-label="Cartes de ta main">${v.hand.map(c => card(c, !!canChoose)).join("")}</div>`}
    </section>` : "";
    const controls = !status && g.me && canChoose ? `<div class="pr-controls">
      <p class="pr-selection-note" role="status">${hidden ? "Affiche tes cartes pour choisir." : esc(d.text)}</p>
      <div class="pr-action-row"><button type="button" class="pr-primary" data-pr="${x ? "exchange" : "play"}" ${busy || hidden || !d.ok || (!x && !v.my_turn && !d.out) ? "disabled" : ""}>${busy ? "Envoi…" : x ? `Donner ${x.count} carte${x.count > 1 ? "s" : ""}` : selected.size ? `Jouer ${selected.size} carte${selected.size > 1 ? "s" : ""}` : "Jouer"}</button>
      ${!x ? `<button type="button" class="secondary" data-pr="pass" ${busy || !v.my_turn || !v.pile ? "disabled" : ""}>Passer</button>` : ""}
      ${selected.size ? `<button type="button" class="pr-reset" data-pr="clear" aria-label="Annuler la sélection">Effacer</button>` : ""}</div>
    </div>` : "";
    return `<section class="pr-game">${seats}<h2 class="pr-turn-title ${v.my_turn ? "pr-your-turn" : ""}" aria-live="polite">${esc(title)}</h2>${table}
      ${status ? `<p class="pr-status" role="status">${esc(status)}</p>` : ""}${hand}${controls}
      ${!x && v.notice ? `<p class="pr-notice">${esc(v.notice)}</p>` : ""}${join}</section>`;
  }

  document.addEventListener("click", async ev => {
    const b = ev.target.closest("[data-pr], [data-pr-card]");
    if (!b || game?.type !== "president" || busy) return;
    if (b.dataset.prCard) {
      const id = b.dataset.prCard, limit = game.phase === "exchange" ? game.president.exchange.count : 4;
      if (selected.has(id)) selected.delete(id);
      else if (selected.size < limit) selected.add(id);
      else { toast(`Choisis au maximum ${limit} cartes`, "err"); return; }
      haptic(20); renderGame(game); return;
    }
    const action = b.dataset.pr;
    if (action === "privacy") { hidden = !hidden; renderGame(game); return; }
    if (action === "clear") { selected.clear(); renderGame(game); return; }
    const code = myGame, v = game.president;
    if (action === "pass") selected.clear();
    busy = true; renderGame(game);
    try {
      await gameAction({play: "prplay", pass: "prpass", exchange: "prexchange"}[action],
        {values: [...selected], guess: action === "exchange" ? v.exchange.token : v.token});
    } finally {
      busy = false;
      if (myGame === code && game?.type === "president") renderGame(game);
    }
  });
  return {html, rules, crown};
})();
