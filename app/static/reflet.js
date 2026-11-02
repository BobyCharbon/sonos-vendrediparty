// 🪞 Le Reflet : à tour de rôle, un joueur choisit une affirmation sur lui-même et parie combien d'amis seront
// d'accord ; les autres votent oui ou non en secret ; on révèle le compteur et l'écart, puis on en parle.
// Chargé après games.js (utilise gameAction, pressed, esc, toast, haptic, GameFx…).
GAME_THEME.reflet = "g-rf";
GAME_RULES.reflet = `
  <h3>Le principe</h3>
  <p>À tour de rôle, un joueur passe <b>devant le miroir</b>. Il choisit une affirmation sur lui-même parmi trois (« On me confie facilement ses secrets ») et parie <b>en secret</b> combien de ses amis diront « oui, c'est vrai ».</p>
  <h3>Le vote</h3>
  <p>Les autres votent <b>oui ou non</b>, chacun sur son téléphone. Le vote est anonyme : on ne saura jamais qui a voté quoi, seulement combien. Avec moins de deux votes, le résultat reste secret. Il faut au moins 4 joueurs.</p>
  <h3>La révélation</h3>
  <p>Le compteur des « oui » monte, puis l'écart avec le pari. <b>Pile</b> : 3 points ; <b>à un près</b> : 1 point. Ensuite, qui veut dit pourquoi : c'est le meilleur moment.</p>
  <h3>La fin</h3>
  <p>Après un ou deux passages devant le miroir pour chacun : le plus lucide, la plus grande surprise et les affirmations qui ont fait l'unanimité.</p>`;


let rfPick = null;    // affirmation choisie (devant le miroir)
let rfBet = null;     // pari en cours
let rfRoundKey = "";
let rfOptions = "";

function rfSave() {
  try { sessionStorage.setItem("vp_reflet", JSON.stringify({ key: rfRoundKey, pick: rfPick, bet: rfBet, options: rfOptions })); } catch { /* rien */ }
}   // affirmations affichées : en changer remet le choix à zéro

const rfKey = (g, part) => `rf:${g.id}:${g.round}:${part}`;

function rfSyncRound(g) {
  const key = `${g.id}:${g.round}`;
  if (key !== rfRoundKey) {
    rfRoundKey = key; rfPick = null; rfBet = null;
    try {  // page rechargée pendant le choix : l'affirmation et le pari reviennent
      const saved = JSON.parse(sessionStorage.getItem("vp_reflet") || "null");
      if (saved?.key === key) { rfPick = saved.pick; rfBet = saved.bet; rfOptions = saved.options || ""; }
    } catch { /* stockage indisponible : on repart de zéro */ }
  }
  // « Trois autres » : nouvelles affirmations, aucune n'est choisie à la place du joueur.
  const opts = (g.reflet.options || []).join("\u0001");
  if (opts !== rfOptions) { rfOptions = opts; rfPick = null; }
}

function rfHero(sub) {
  return `<div class="lk-hero rf-hero"><div class="lk-hero-i">🪞</div><div><div class="lk-hero-t">Le Reflet</div>
    <div class="lk-hero-s">${sub}</div></div></div>`;
}

function rfSettingsHtml(g) {
  const v = g.reflet;
  const turns = v.turn_list.map((n) => `<button type="button" class="${v.turns === n ? "on" : ""}" data-rf-turns="${n}" aria-pressed="${v.turns === n}">${n === 1 ? "Un passage chacun" : "Deux passages chacun"}</button>`).join("");
  return `<div class="lk-setup"><div class="g-label">Devant le miroir</div><div class="lk-chips">${turns}</div></div>`;
}

function rfLobbyHtml(g) {
  const v = g.reflet, n = g.players.length;
  if (!g.is_host) {
    return `${rfHero("Te vois-tu comme les autres te voient ?")}<div class="lk-card"><div class="title">${g.me ? "Tu es inscrit ✓" : `Partie de ${esc(g.host_name || "quelqu'un")}`}</div>
      <p class="artist">${esc(g.host_name || "L'animateur")} lance la partie : chacun passera devant le miroir.</p>
      ${g.me ? "" : `<button class="lk-main" data-gact="join">Je joue aussi</button>`}</div>`;
  }
  return `${rfHero("Te vois-tu comme les autres te voient ?")}${rfSettingsHtml(g)}
    <p class="artist lk-help">${n < v.min_players ? `Il faut au moins ${v.min_players} joueurs, chacun avec son téléphone.` : `${n} joueurs : chacun passe devant le miroir, les autres votent en secret.`}</p>
    <button class="lk-main" data-gact="start" ${n < v.min_players ? "disabled" : ""}>▶︎ Commencer</button>`;
}

function rfTurn(v, done = false) {
  // Au résultat, le passage qu'on vient de jouer est déjà compté : on n'ajoute pas le suivant.
  return `<div class="rf-turn">Passage ${Math.max(1, Math.min(v.done_turns + (done ? 0 : 1), v.total))}/${v.total}</div>`;
}

function rfPickHtml(g) {
  const v = g.reflet;
  if (!v.is_mirror) {
    return `${rfTurn(v)}<div class="rf-mirror"${GameFx.fx("pop", rfKey(g, "who"))}><div class="rf-mirror-k">Devant le miroir</div><div class="lk-name">${esc(v.mirror?.name || "")}</div>
      <p class="artist">choisit une affirmation sur soi et parie en secret…</p></div>
      ${v.can_swap_lead ? `<button class="lk-sub" data-gact="rfswap" style="width:100%">🔀 Lui proposer d'autres affirmations</button>` : ""}`;
  }
  const opts = v.options.map((t, i) => `<button type="button" class="ps-opt ${rfPick === i ? "on" : ""}" data-rf-pick="${i}" aria-pressed="${rfPick === i}"${GameFx.fx("rise", rfKey(g, `opt${i}`), 100 * i)}>« ${esc(t)} »</button>`).join("");
  const bets = Array.from({ length: v.voters + 1 }, (_, n) => `<button type="button" class="${rfBet === n ? "on" : ""}" data-rf-bet="${n}" aria-pressed="${rfBet === n}">${n}</button>`).join("");
  return `${rfTurn(v)}<div class="rf-mirror"><div class="rf-mirror-k">🪞 À toi devant le miroir</div><p class="artist">Choisis une affirmation sur toi :</p></div>
    <div class="ps-opts">${opts}</div>
    ${v.can_swap ? `<button class="lk-sub" data-gact="rfswap" style="width:100%;margin-top:8px">🔀 Trois autres</button>` : ""}
    <div class="g-label rf-bet-l">Combien de tes ${v.voters} amis diront « oui » ? C'est secret.</div><div class="lk-chips rf-bets">${bets}</div>
    <button class="lk-main" data-rf-go ${rfPick != null && rfBet != null ? "" : "disabled"}>🪞 Montrer l'affirmation</button>`;
}

function rfCard(g, v) {
  return `<div class="rf-card"${GameFx.fx("flip", rfKey(g, "card"))}><div class="rf-card-k">${esc(v.mirror?.name || "")} pense que…</div><div class="rf-card-t">« ${esc(v.card || "")} »</div></div>`;
}

function rfVoteHtml(g) {
  const v = g.reflet;
  const ask = v.can_vote ? `<div class="lk-who"${GameFx.fx("rise", rfKey(g, "ask"))}>🤫 Es-tu d'accord ? Personne ne saura ce que tu as voté.</div>
      <div class="rf-votes"><button type="button" class="rf-yes" data-rf-vote="1">👍 Oui, c'est vrai</button><button type="button" class="rf-no" data-rf-vote="0">👎 Non</button></div>`
    : v.is_mirror ? `<div class="lk-card lk-done"><div class="artist">Ton pari, gardé secret</div><div class="lk-name">${v.bet} « oui »</div></div>`
    : v.my_vote ? `<div class="lk-card lk-done"${GameFx.fx("pop", rfKey(g, "voted"))}><div class="lk-name">🤫 Vote enregistré</div><div class="artist">Résultat quand tout le monde a voté.</div></div>`
    : v.late ? `<div class="lk-card lk-done"><div class="artist">Tu es arrivé après le pari : tu voteras au prochain tour.</div></div>` : "";
  const dots = `<div class="lk-dots" role="img" aria-label="${v.done} sur ${v.voters} ont voté">${Array.from({ length: v.voters }, (_, i) => `<i class="${i < v.done ? "on" : ""}"></i>`).join("")}</div>`;
  const host = g.is_host && v.waiting?.length ? `<div class="lk-card lk-waiting"><div class="artist">Votent encore…</div><div class="lk-row">${v.waiting.map((x) => `<button class="lk-sub" data-rf-skip="${esc(x.pid)}" data-rf-name="${esc(x.name)}" aria-label="Ne plus attendre le vote de ${esc(x.name)}">⏭ Passer ${esc(x.name)}</button>`).join("")}</div></div>` : "";
  return `${rfTurn(v)}${rfCard(g, v)}${ask}${dots}${host}`;
}

function rfResultHtml(g) {
  const v = g.reflet, r = v.result;
  const verdict = r.gap === 0 ? "🎯 Pile dans le mille !" : r.gap === 1 ? "👌 À un près" : `🤯 ${r.gap} d'écart`;
  const last = v.done_turns >= v.total;
  const next = g.is_host ? `<button class="lk-main" data-gact="next">${last ? "📊 Voir le bilan" : "▶︎ Au suivant"}</button>` : "";
  if (r.hidden) {
    return `${rfTurn(v, true)}${rfCard(g, v)}<div class="lk-win"><div class="lk-win-t">🤫 Trop peu de votes</div>
      <div class="artist">Avec moins de deux votes, le résultat dévoilerait qui a voté quoi : il reste secret, sans point.</div></div>${next}`;
  }
  return `${rfTurn(v, true)}${rfCard(g, v)}
    <div class="rf-count"${GameFx.fx("pop", rfKey(g, "count"))}><div class="rf-count-n"><span${GameFx.num(rfKey(g, "yes"), r.yes, 0)}>${r.yes}</span><small>/${r.voters}</small></div>
      <div class="artist">disent « oui, c'est vrai »</div></div>
    <div class="lk-win"${GameFx.fx("land", rfKey(g, "verdict"), 700)}><div class="lk-win-k">Pari : ${r.bet}</div><div class="lk-win-t">${verdict}</div>${r.points ? `<div class="artist">+${r.points} point${r.points > 1 ? "s" : ""} pour ${esc(v.mirror?.name || "")}</div>` : ""}</div>
    <p class="db-talk">💬 Qui veut dire pourquoi ? Personne n'est obligé.</p>${next}`;
}

function rfEndHtml(g) {
  const v = g.reflet, s = v.summary || {};
  const ranking = rankingHtml(s.ranking || []);
  const lucid = s.lucid?.length ? `<div class="db-award"${GameFx.fx("rise", `rf:${g.id}:end:l`)}><div class="db-award-k">🔮 Le plus lucide</div><div class="db-award-t">${s.lucid.map(esc).join(", ")}</div><div class="artist">Se voit comme les autres le voient</div></div>` : "";
  const sur = s.surprise && s.surprise.gap ? `<div class="db-award"${GameFx.fx("rise", `rf:${g.id}:end:s`, 250)}><div class="db-award-k">🤯 La plus grande surprise</div><div class="db-award-t">« ${esc(s.surprise.text)} »</div><div class="artist">${esc(s.surprise.name)} pariait ${s.surprise.bet}, réponse ${s.surprise.yes}/${s.surprise.voters}</div></div>` : "";
  const una = s.unanimous?.length ? `<div class="db-award"${GameFx.fx("rise", `rf:${g.id}:end:u`, 500)}><div class="db-award-k">🤝 À l'unanimité</div>${s.unanimous.map((u) => `<div class="artist"><b>${esc(u.name)}</b> : « ${esc(u.text)} »</div>`).join("")}</div>` : "";
  return `<div class="lk-end-k">Bilan du miroir</div>${lucid}${sur}${una}<div class="list">${ranking}</div>
    ${g.is_host ? `${rfSettingsHtml(g)}<button class="lk-main" data-gact="restart">🔁 Rejouer avec les mêmes joueurs</button>` : ""}`;
}

function refletHtml(g) {
  if (!g.reflet) return "";
  rfSyncRound(g);
  if (g.phase === "pick") return rfPickHtml(g);
  if (g.phase === "vote") return rfVoteHtml(g);
  if (g.phase === "result" && g.reflet.result) return rfResultHtml(g);
  if (g.phase === "end") return rfEndHtml(g);
  return rfLobbyHtml(g);
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "reflet") return;
  const pick = ev.target.closest("[data-rf-pick]");
  if (pick) { rfPick = +pick.dataset.rfPick; rfSave(); haptic(12); return renderGame(game); }
  const bet = ev.target.closest("[data-rf-bet]");
  if (bet) { rfBet = +bet.dataset.rfBet; rfSave(); haptic(12); return renderGame(game); }
  const go = ev.target.closest("[data-rf-go]");
  if (go) return pressed(go, gameAction("rfpick", { settings: { i: rfPick, bet: rfBet } }));
  const vote = ev.target.closest("[data-rf-vote]");
  if (vote) {
    vote.closest(".rf-votes")?.querySelectorAll("button").forEach((b) => { b.disabled = true; });  // un seul vote
    haptic(30);
    return pressed(vote, gameAction("rfvote", { done: vote.dataset.rfVote === "1" })).then((ok) => {
      if (ok === false || ok === undefined) { $("game").dataset.html = ""; renderGame(game); }  // échec : on peut revoter
    });
  }
  const skip = ev.target.closest("[data-rf-skip]");
  if (skip) {
    if (!confirm(`Ne plus attendre le vote de ${skip.dataset.rfName} ?`)) return;
    return pressed(skip, gameAction("rfskip", { target: skip.dataset.rfSkip }));
  }
  const turns = ev.target.closest("[data-rf-turns]");
  if (turns) return pressed(turns, gameAction("rfset", { settings: { turns: +turns.dataset.rfTurns } }));
});
