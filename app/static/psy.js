// 🔮 Qui es-tu vraiment ? : chacun répond en secret à 12 questions (personnalité et énigmes de logique) ; l'animateur
// révèle le profil de chacun, son score de logique, la répartition du groupe et les âmes sœurs (avis 49275b68240b).
// Chargé après games.js (utilise gameAction, pressed, esc, haptic…).
GAME_THEME.psy = "g-ps";
GAME_RULES.psy = `
  <h3>Le principe</h3>
  <p>Chacun répond <b>en secret</b>, sur son téléphone, à 12 questions : 9 sur sa façon d'être (relations, réactions, valeurs, pensées) et 3 petites <b>énigmes de logique</b>. Il n'y a pas de bonne ou de mauvaise réponse aux questions de personnalité : réponds spontanément.</p>
  <h3>Les quatre profils</h3>
  <p>🦁 <b>Le Meneur</b> (direct, décidé), 🎉 <b>L'Âme de la fête</b> (enthousiaste, sociable), 🧠 <b>Le Stratège</b> (réfléchi, logique) et 🌙 <b>Le Cœur tendre</b> (sensible, à l'écoute). Chaque réponse compte pour l'un d'eux.</p>
  <h3>La révélation</h3>
  <p>Quand tout le monde a validé, l'animateur révèle : le profil de chacun (et son second), son score de logique, la répartition du groupe, la personne la plus logique… et les deux <b>âmes sœurs</b>, celles qui ont répondu le plus pareil.</p>
  <p>Un jeu pour se découvrir et en parler, pas un vrai test psychologique.</p>`;


let psyAt = 0;        // question affichée sur ce téléphone
let psyRound = "";    // partie et manche : on repart de la première question à chaque nouveau test
let psySeen = "";     // la révélation ne s'anime qu'une fois

function psyHtml(g) {
  const v = g.psy;
  if (!v) return "";
  if (g.phase === "lobby") return psyLobbyHtml(g);
  if (g.phase === "results") return psyResultsHtml(g);
  if (v.playing && !v.done && v.questions) return psyAskHtml(g);
  return psyWaitHtml(g);
}

function psyHero(sub) {
  return `<div class="lk-hero ps-hero"><div class="lk-hero-i">🔮</div><div><div class="lk-hero-t">Qui es-tu vraiment ?</div>
    <div class="lk-hero-s">${sub}</div></div></div>`;
}

function psyLobbyHtml(g) {
  const n = g.players.length;
  if (!g.is_host) {
    return `${psyHero("Relations, pensées, logique : découvre ton profil.")}<div class="lk-card"><div class="title">${g.me ? "Tu es inscrit ✓" : `Partie de ${esc(g.host_name || "quelqu'un")}`}</div>
      <p class="artist">${esc(g.host_name || "L'animateur")} va lancer le test : tu répondras en secret sur ton téléphone.</p>
      ${g.me ? "" : `<button class="lk-main" data-gact="join">Je joue aussi</button>`}</div>`;
  }
  return `${psyHero("12 questions en secret, puis la révélation des profils.")}
    <p class="artist lk-help">${n ? `${n} joueur${n > 1 ? "s" : ""} : chacun répond sur son téléphone.` : "Fais scanner le QR code pour que chacun rejoigne avec son téléphone."}</p>
    <button class="lk-main" data-gact="start" ${n ? "" : "disabled"}>▶︎ Lancer le test</button>`;
}

function psyAskHtml(g) {
  const v = g.psy, key = `${g.id}:${g.round}`;
  if (key !== psyRound) { psyRound = key; psyAt = 0; }
  const answered = Object.keys(v.mine || {}).length;
  psyAt = Math.min(Math.max(0, psyAt), v.count - 1);
  const q = v.questions[psyAt], mine = v.mine?.[String(psyAt)];
  const options = q.options.map((o, j) => `<button type="button" class="ps-opt ${mine === j ? "on" : ""}" data-psy-a="${j}" data-psy-q="${psyAt}">${esc(o)}</button>`).join("");
  const all = answered === v.count;
  return `<div class="ps-top"><span>Question ${psyAt + 1}/${v.count}</span><span>${answered}/${v.count} répondue${answered > 1 ? "s" : ""}</span></div>
    <div class="ps-track"><i style="--w:${Math.round(100 * answered / v.count)}%"></i></div>
    <div class="ps-q ${q.kind === "logic" ? "logic" : ""}">${q.kind === "logic" ? `<div class="ps-kind">🧩 Énigme de logique</div>` : `<div class="ps-kind">🤫 Réponds spontanément</div>`}
      <div class="ps-q-t">${esc(q.text)}</div></div>
    <div class="ps-opts">${options}</div>
    <div class="ps-nav">
      <button type="button" class="lk-sub" data-psy-go="-1" ${psyAt ? "" : "disabled"}>‹ Précédente</button>
      <button type="button" class="lk-sub" data-psy-go="1" ${psyAt < v.count - 1 ? "" : "disabled"}>Suivante ›</button>
    </div>
    ${all ? `<button class="lk-main" data-gact="psysub">✅ Valider mes réponses</button>` : `<p class="artist ps-left">Encore ${v.count - answered} question${v.count - answered > 1 ? "s" : ""} avant de valider.</p>`}`;
}

function psyWaitHtml(g) {
  const v = g.psy, done = v.progress.filter((p) => p.done).length;
  const people = v.progress.map((p) => `<span class="ps-who ${p.done ? "on" : ""}">${p.done ? "✓" : "…"} ${esc(p.name)}</span>`).join("");
  const host = g.is_host
    ? `<button class="lk-main" data-gact="psyreveal" ${done ? "" : "disabled"}>👁 Révéler les profils${done < v.progress.length ? ` (${done}/${v.progress.length})` : ""}</button>`
    : `<p class="artist">L'animateur révèle les profils quand tout le monde a fini.</p>`;
  return `${psyHero(v.done ? "Tes réponses sont enregistrées. Chut !" : "Les joueurs répondent en secret…")}
    <div class="lk-card"><div class="title">${done}/${v.progress.length} ont fini</div><div class="ps-people">${people}</div></div>${host}`;
}

function psyBars(pct, profiles) {
  return Object.keys(profiles).map((k) => `<div class="ps-bar"><span>${profiles[k].emoji} ${esc(profiles[k].name)}</span>
    <i style="--w:${pct[k]}%;--c:${profiles[k].color}"></i><b>${pct[k]} %</b></div>`).join("");
}

function psyResultsHtml(g) {
  const v = g.psy, r = v.results, P = v.profiles, key = `${g.id}:${g.round}`;
  const anim = key !== psySeen ? "ps-anim" : "";
  psySeen = key;
  const me = v.me ? `<div class="ps-me ${anim}" style="--c:${P[v.me.profile].color}">
      <div class="ps-me-k">Ton profil</div><div class="ps-me-e">${P[v.me.profile].emoji}</div>
      <div class="ps-me-n">${esc(P[v.me.profile].name)}</div><p>${esc(P[v.me.profile].text)}</p>
      ${v.me.second ? `<div class="ps-me-s">Avec une touche de ${P[v.me.second].emoji} ${esc(P[v.me.second].name)}</div>` : ""}
      <div class="ps-bars">${psyBars(v.me.pct, P)}</div>
      <div class="ps-logic">🧩 Logique : <b>${v.me.logic}/${r.logic_count}</b></div></div>` : "";
  const dist = Object.keys(P).filter((k) => r.distribution[k]).map((k) => `<span class="ps-chip" style="--c:${P[k].color}">${P[k].emoji} ${r.distribution[k]}</span>`).join("");
  const people = r.people.map((x) => `<div class="track"><div class="meta"><div class="title">${P[x.profile].emoji} ${esc(x.name)}</div>
      <div class="artist">${esc(P[x.profile].name)}${x.second ? ` · ${P[x.second].emoji}` : ""} · 🧩 ${x.logic}/${r.logic_count}</div></div></div>`).join("");
  const facts = [
    r.most_logic.length ? `<div>🧠 Le plus logique : <b>${r.most_logic.map(esc).join(", ")}</b></div>` : "",
    r.pair ? `<div>💞 Âmes sœurs : <b>${esc(r.pair.a)} & ${esc(r.pair.b)}</b> <span>${r.pair.pct} % de réponses communes</span></div>` : "",
  ].join("");
  return `${me}<div class="lk-card ps-group"><div class="title">Le groupe</div><div class="ps-dist">${dist}</div>${facts}</div>
    <div class="list">${people}</div>
    ${g.is_host ? `<button class="lk-main" data-gact="next" style="margin-top:12px">🔁 Nouveau test</button>` : ""}`;
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "psy") return;
  const go = ev.target.closest("[data-psy-go]");
  if (go) { psyAt += +go.dataset.psyGo; return renderGame(game); }
  const pick = ev.target.closest("[data-psy-a]");
  if (!pick) return;
  const q = +pick.dataset.psyQ, a = +pick.dataset.psyA, v = game.psy;
  haptic(15);
  v.mine = { ...(v.mine || {}), [String(q)]: a };  // affiché tout de suite ; le serveur confirme
  if (q < v.count - 1) psyAt = q + 1;  // question suivante automatiquement
  renderGame(game);
  pressed(pick, gameAction("psyans", { settings: { q, a } }));
});
