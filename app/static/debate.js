// ⚖️ Pour ou contre : un dilemme, chacun se place en secret sur 5 crans ; on découvre la répartition, on débat, et
// l'animateur décide de faire revoter ou de passer au suivant. Les joueurs proposent leurs dilemmes, l'animateur les
// valide. Pas de points ni de gorgées : un bilan à la fin. Chargé après games.js (utilise gameAction, pressed, esc, toast…).
GAME_THEME.debate = "g-db";
GAME_RULES.debate = `
  <h3>Le principe</h3>
  <p>Un dilemme s'affiche (« Faut-il dire à un ami que son ou sa partenaire le trompe ? »). Chacun se place <b>en secret</b>, sur son téléphone, sur une échelle de cinq crans : de <b>Totalement contre</b> à <b>Totalement pour</b>. Un vote est définitif.</p>
  <h3>La révélation</h3>
  <p>Quand tout le monde a voté, la répartition s'affiche. L'animateur a choisi avant la partie : <b>votes anonymes</b> (on ne voit que les chiffres) ou <b>votes publics</b> (chaque prénom sur son cran).</p>
  <h3>Le débat</h3>
  <p>Discutez librement : pourquoi êtes-vous pour, contre, partagés ? Personne n'est obligé de se justifier.</p>
  <h3>Le revote</h3>
  <p>Après le débat, l'animateur choisit : <b>faire revoter</b> (une fois) pour voir combien ont changé d'avis, ou passer au dilemme suivant.</p>
  <h3>Les thèmes</h3>
  <p>L'animateur coche les thèmes du soir : ⚖️ Morale, 🏛️ Société, 💞 Relations & couple, 🍍 Léger… et <b>🤪 WTF 🔞</b> (absurde, idiot, osé, entre adultes), qui n'est <b>jamais</b> proposé d'office.</p>
  <h3>Vos dilemmes</h3>
  <p>Chacun peut proposer un dilemme (« ✍️ Proposer »). L'animateur le valide : il passe alors avant ceux de l'app, avec le prénom de son auteur.</p>
  <h3>Sans téléphone ?</h3>
  <p>L'animateur ajoute les participants sans téléphone : son écran dit à qui le passer. La personne touche « C'est moi », vote, et l'écran se cache aussitôt.</p>
  <h3>La fin</h3>
  <p>Après 10, 20 ou 30 dilemmes, le bilan : le dilemme le plus divisant, le plus unanime, et celui qui a fait changer le plus d'avis. Pas de gagnant, pas de gorgées : juste de belles discussions.</p>`;

const DB_EMOJI = ["👎", "🙁", "🤔", "🙂", "👍"];
let dbReadyKey = "";  // le votant sans téléphone a touché « C'est moi » : l'échelle s'affiche pour lui
let dbDraft = "";  // dilemme en cours d'écriture (gardé si la feuille se ferme)
let dbSending = "";  // vote envoyé, réponse attendue : l'échelle reste bloquée même si l'écran se rafraîchit

const dbVoterKey = (g) => `${g.id}:${g.debate.n}:${g.debate.round}:${g.debate.voter?.pid || ""}`;
const dbBallotKey = (g, who) => `${g.id}:${g.debate.n}:${g.debate.round}:${who}`;
const dbFor = (h) => h.counts[3] + h.counts[4];
const dbAgainst = (h) => h.counts[0] + h.counts[1];

function dbQuestion(v, small = false) {
  const q = v.q || {};
  const tag = q.by ? `✍️ Proposé par ${esc(q.by)}` : esc(q.theme || "");
  return `<div class="db-q ${small ? "small" : ""}"><div class="db-q-n">Dilemme ${v.n}/${v.count}${v.round === 2 ? " · revote" : ""}</div>
    <div class="db-q-t">${esc(q.text || "")}</div>${tag ? `<div class="db-q-tag">${tag}</div>` : ""}</div>`;
}

function dbDots(v) {
  return `<div class="lk-dots" role="img" aria-label="${v.done.length} sur ${v.total} ont voté">${Array.from({ length: v.total }, (_, i) =>
    `<i class="${i < v.done.length ? "on" : ""}"></i>`).join("")}</div>`;
}

function dbSettingsHtml(g) {
  const v = g.debate;
  const themes = v.theme_list.map((t) => `<button type="button" class="${v.themes.includes(t.id) ? "on" : ""}" data-db-theme="${t.id}" aria-pressed="${v.themes.includes(t.id)}">${esc(t.label)}${t.adult ? " 🔞" : ""} <small>${t.size}</small></button>`).join("");
  const counts = v.counts.map((n) => `<button type="button" class="${v.count === n ? "on" : ""}" data-db-count="${n}" aria-pressed="${v.count === n}">${n}</button>`).join("");
  const pub = [[false, "🙈 Anonymes"], [true, "👀 Prénoms affichés"]].map(([val, label]) =>
    `<button type="button" class="${v.public === val ? "on" : ""}" data-db-public="${val}" aria-pressed="${v.public === val}">${label}</button>`).join("");
  return `<div class="lk-setup db-setup">
    <div class="g-label">Thèmes</div><div class="lk-chips">${themes}</div>
    <div class="g-label">Nombre de dilemmes</div><div class="lk-chips">${counts}</div>
    <div class="g-label">À la révélation, les votes sont…</div><div class="lk-chips">${pub}</div>
  </div>`;
}

// Proposer un dilemme : bouton pour tous les joueurs ; l'animateur voit en plus les propositions à valider.
function dbProposeHtml(g) {
  if (!g.me) return "";
  const v = g.debate;
  const mine = v.my_pending ? `<span class="db-pending">${v.my_pending} en attente de validation</span>` : "";
  return `<div class="db-propose-row"><button type="button" class="lk-sub" data-db-compose>✍️ Proposer un dilemme</button>${mine}</div>`;
}

function dbInboxHtml(g) {
  const v = g.debate;
  if (!g.is_host || !v.proposals.length) return "";
  return `<div class="db-inbox"><div class="db-inbox-h">📬 Dilemmes proposés (${v.proposals.length})</div>
    ${v.proposals.map((p) => `<div class="db-prop"><div class="db-prop-t">${esc(p.text)}<small>par ${esc(p.by)}</small></div>
      <button type="button" class="db-ok" data-db-accept="${p.id}" aria-label="Accepter le dilemme de ${esc(p.by)}">✓</button>
      <button type="button" class="db-no" data-db-refuse="${p.id}" aria-label="Refuser le dilemme de ${esc(p.by)}">✕</button></div>`).join("")}
    ${v.queued ? `<div class="artist">${v.queued} dilemme(s) validé(s) à venir</div>` : ""}</div>`;
}

function dbLobbyHtml(g) {
  const n = g.players.length;
  const hero = `<div class="lk-hero db-hero"><div class="lk-hero-i">⚖️</div><div><div class="lk-hero-t">Pour ou contre</div>
    <div class="lk-hero-s">Un dilemme, chacun se place en secret, puis on en parle.</div></div></div>`;
  if (!g.is_host) {
    return `${hero}<div class="lk-card"><div class="title">${g.me ? "Tu es inscrit ✓" : `Partie de ${esc(g.host_name || "quelqu'un")}`}</div>
      <p class="artist">${esc(g.host_name || "L'animateur")} va lancer le premier dilemme : tu voteras sur ton téléphone.</p>
      ${g.me ? "" : `<button class="lk-main" data-gact="join">Je joue aussi</button>`}</div>${dbProposeHtml(g)}`;
  }
  return `${hero}${dbSettingsHtml(g)}${dbInboxHtml(g)}${dbProposeHtml(g)}
    <p class="artist lk-help">${n < 2 ? "Ajoute les prénoms de tout le monde plus bas (au moins 2 joueurs)." : `${n} joueurs : chacun vote sur son téléphone ; le tien passe à ceux qui n'en ont pas, dans l'ordre de la liste.`}</p>
    <button class="lk-main" data-gact="start" ${n < 2 ? "disabled" : ""}>▶︎ Premier dilemme</button>`;
}

function dbScaleHtml(g, who, title) {
  const v = g.debate, key = dbBallotKey(g, who), off = dbSending === key ? "disabled" : "";
  return `<div class="lk-who">🤫 ${title}</div>
    <div class="db-scale">${v.scale.map((label, i) => `<button type="button" class="db-pick db-c${i}" data-db-vote="${i}" data-db-who="${esc(who)}" data-db-key="${esc(key)}" ${off}>
      <span aria-hidden="true">${DB_EMOJI[i]}</span>${esc(label)}</button>`).join("")}</div>`;
}

// Téléphone de l'animateur : il passe aux participants sans téléphone, dans l'ordre de la table.
function dbPassHtml(g) {
  const v = g.debate;
  if (!v.voter) return "";
  if (dbReadyKey === dbVoterKey(g)) return dbScaleHtml(g, v.voter.pid, `${esc(v.voter.name)}, où te places-tu&nbsp;?`);
  return `<div class="lk-pass">
      <div class="lk-pass-k">📱 Passe le téléphone à</div><div class="lk-name">${esc(v.voter.name)}</div>
      <button class="lk-main" data-db-ready="${esc(dbVoterKey(g))}">C'est moi, ${esc(v.voter.name)} 👋</button>
      <button class="lk-sub" data-gact="dbskip">⏭ Passer ${esc(v.voter.name)} (absent)</button>
    </div>`;
}

// Animateur : ceux qui ont leur téléphone et n'ont pas encore voté (on peut passer un absent).
function dbWaitingHtml(g) {
  const v = g.debate, phones = v.waiting.filter((x) => !x.manual && x.pid !== g.me?.pid);
  if (!g.is_host || !phones.length) return "";
  return `<div class="lk-card lk-waiting"><div class="artist">Réfléchissent encore…</div>
    <div class="lk-row">${phones.map((x) => `<button class="lk-sub" data-gact="dbskip" data-target="${esc(x.pid)}" title="Passer ${esc(x.name)} (absent)">⏭ ${esc(x.name)}</button>`).join("")}</div></div>`;
}

function dbAskHtml(g) {
  const v = g.debate;
  const again = v.round === 2 ? `<div class="db-again">🔁 Après le débat : as-tu changé d'avis&nbsp;?</div>` : "";
  // Chacun vote sur son propre téléphone, en même temps ; une fois voté, l'échelle disparaît (vote secret et définitif).
  const late = g.me && !g.is_host && !v.done.includes(g.me.pid) && !v.waiting.some((x) => x.pid === g.me.pid);
  const mine = v.can_vote ? dbScaleHtml(g, g.me.pid, "Où te places-tu&nbsp;? C'est secret.")
    : v.mine != null ? `<div class="lk-card lk-done"><div class="lk-name db-mine">${DB_EMOJI[v.mine]} ${esc(v.scale[v.mine])}</div><div class="artist">Ton vote est enregistré. Résultat quand tout le monde a voté.</div></div>`
    : late ? `<div class="lk-card lk-done"><div class="artist">Tu es arrivé pendant ce vote : tu voteras au prochain dilemme.</div></div>` : "";
  const host = g.is_host && !v.can_vote ? dbPassHtml(g) + dbWaitingHtml(g) : "";
  return `${dbQuestion(v)}${again}${mine}${host}${dbDots(v)}
    ${g.is_host && !v.voted && v.round === 1 ? `<div class="lk-row"><button class="lk-sub" data-gact="dbswap">🔀 Autre dilemme</button></div>` : ""}`;
}

function dbBarsHtml(v) {
  const r = v.result, max = Math.max(1, ...r.counts);
  return `<div class="db-bars">${v.scale.map((label, i) => `<div class="db-bar db-c${i}">
      <span class="db-bar-l">${DB_EMOJI[i]} ${esc(label)}</span><i style="--w:${Math.round((r.counts[i] / max) * 100)}%"></i>
      <b>${r.counts[i]}${r.before ? `<small> (avant ${r.before[i]})</small>` : ""}</b>
      ${r.names && r.names[i].length ? `<div class="db-names">${r.names[i].map(esc).join(", ")}</div>` : ""}</div>`).join("")}</div>`;
}

function dbVerdict(r) {
  if (!r.votes) return `<div class="lk-win-t">Personne n'a voté</div>`;
  const lead = r.pour > r.contre ? "Plutôt pour" : r.contre > r.pour ? "Plutôt contre" : "Le groupe est partagé";
  return `<div class="lk-win-k">${r.votes} vote${r.votes > 1 ? "s" : ""}</div><div class="lk-win-t">${lead}</div>
    <div class="db-split"><span>👍 ${r.pour} pour</span><span>🤔 ${r.partage} partagé${r.partage > 1 ? "s" : ""}</span><span>👎 ${r.contre} contre</span></div>`;
}

function dbRevealHtml(g) {
  const v = g.debate, r = v.result;
  const moved = r.moved == null ? "" : `<div class="db-moved">${r.moved ? `🔄 ${r.moved} personne${r.moved > 1 ? "s ont" : " a"} changé d'avis` : "🪨 Personne n'a changé d'avis"}</div>`;
  const canRevote = v.round === 1 && r.votes > 0;
  const host = g.is_host ? `<div class="db-actions">
      ${canRevote ? `<button class="lk-main" data-gact="dbrevote">🔁 Faire revoter</button>` : ""}
      <button class="${canRevote ? "lk-sub db-next" : "lk-main"}" data-gact="next">${v.n >= v.count ? "📊 Voir le bilan" : "▶︎ Dilemme suivant"}</button></div>` : "";
  const talk = v.round === 1 ? `<p class="db-talk">💬 À vous : pourquoi pour, contre, partagé&nbsp;? Débattez librement.</p>` : "";
  return `${dbQuestion(v, true)}<div class="lk-win">${dbVerdict(r)}</div>${moved}${dbBarsHtml(v)}${talk}${host}${dbInboxHtml(g)}${dbProposeHtml(g)}`;
}

function dbAward(icon, title, h, detail) {
  if (!h) return "";
  return `<div class="db-award"><div class="db-award-k">${icon} ${title}</div><div class="db-award-t">${esc(h.text)}</div><div class="artist">${detail}</div></div>`;
}

function dbEndHtml(g) {
  const v = g.debate, s = v.summary || {};
  const split = (h) => h ? `👍 ${dbFor(h)} · 🤔 ${h.counts[2]} · 👎 ${dbAgainst(h)}` : "";
  const recap = v.history.map((h) => `<li>${esc(h.text)} <span>👍 ${dbFor(h)} · 👎 ${dbAgainst(h)}${h.moved ? ` · 🔄 ${h.moved}` : ""}</span></li>`).join("");
  const moved = s.moved ? `${s.moved.moved} personne${s.moved.moved > 1 ? "s ont" : " a"} changé d'avis` : "";
  return `<div class="lk-end-k">Bilan de la partie</div>
    ${dbAward("🔥", "Le plus divisant", s.divisive, split(s.divisive))}
    ${dbAward("🤝", "Le plus unanime", s.unanimous, split(s.unanimous))}
    ${dbAward("🔄", "A fait changer le plus d'avis", s.moved, moved)}
    <details class="lk-recap"><summary>Revoir les ${v.history.length} dilemmes</summary><ol>${recap}</ol></details>
    ${g.is_host ? `${dbSettingsHtml(g)}${dbInboxHtml(g)}<button class="lk-main" data-gact="restart">🔁 Rejouer avec les mêmes joueurs</button>` : ""}${dbProposeHtml(g)}`;
}

function debateHtml(g) {
  if (!g.debate) return "";
  if (g.phase === "ask") return dbAskHtml(g);
  if (g.phase === "reveal" && g.debate.result) return dbRevealHtml(g);
  if (g.phase === "end") return dbEndHtml(g);
  return dbLobbyHtml(g);
}

// Liste des joueurs (ordre de passage du téléphone pour ceux qui n'en ont pas) et ajout des prénoms, avant la partie.
function renderDebateHost(g) {
  if (g.phase !== "lobby" || !g.is_host) { patch.gameHost = ""; return; }
  const n = g.players.length;
  patch.gameHost = `<h2>Autour de la table (${n})</h2>
    <div class="list">${g.players.map((p, i) => `<div class="track"><div class="meta"><div class="title">${i + 1}. ${esc(p.name)}${p.host ? " 🎲" : ""}${playerTag(g, p)}</div></div>
      <div class="icon-btns">
        ${i > 0 ? `<button class="secondary" data-gact="up" data-target="${esc(p.pid)}" title="Monter" aria-label="Monter ${esc(p.name)}">⬆</button>` : ""}
        ${i < n - 1 ? `<button class="secondary" data-gact="down" data-target="${esc(p.pid)}" title="Descendre" aria-label="Descendre ${esc(p.name)}">⬇</button>` : ""}
        ${p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Retirer" aria-label="Retirer ${esc(p.name)}">✕</button>` : ""}
      </div></div>`).join("") || `<p class="empty" style="padding:12px">Ajoute les prénoms ci-dessous.</p>`}</div>
    ${manualForm(g)}
    ${!g.me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// Feuille « Proposer un dilemme » : hors de #game, pour que les rafraîchissements n'effacent pas ce qu'on écrit.
function dbCloseSheet() {
  document.querySelector(".db-sheet-modal")?.remove();
}

function dbOpenSheet() {
  const v = game?.debate;
  if (!v) return;
  dbCloseSheet();
  const wrap = document.createElement("div");
  wrap.className = "g-modal db-sheet-modal";
  Object.assign(wrap.dataset, { nav: "sheet", navSurface: ".db-sheet", navClose: "self" });
  wrap.innerHTML = `<form class="g-sheet db-sheet g-db" role="dialog" aria-modal="true" aria-labelledby="dbSheetTitle">
      <div class="g-sheet-grab" aria-hidden="true"></div>
      <h2 id="dbSheetTitle">✍️ Proposer un dilemme</h2>
      <p class="artist">Une question à laquelle on peut répondre pour ou contre. L'animateur la valide avant qu'elle soit posée, avec ton prénom.</p>
      <textarea name="text" rows="3" minlength="${v.min_text}" maxlength="${v.max_text}" required placeholder="Faut-il… ?" aria-label="Ton dilemme"></textarea>
      <div class="db-sheet-row"><button type="button" class="lk-sub" data-db-cancel>Annuler</button><button type="submit" class="lk-main">Envoyer à l'animateur</button></div>
    </form>`;
  const area = wrap.querySelector("textarea");
  area.value = dbDraft;
  area.addEventListener("input", () => { dbDraft = area.value; });
  wrap.addEventListener("click", (ev) => { if (ev.target === wrap || ev.target.closest("[data-db-cancel]")) dbCloseSheet(); });
  wrap.querySelector("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = area.value.trim();
    if (text.length < v.min_text) return toast(`Au moins ${v.min_text} caractères`, "err");
    const ok = await pressed(ev.submitter, gameAction("dbpropose", { guess: text }));
    if (ok) { dbDraft = ""; dbCloseSheet(); toast("Envoyé : l'animateur va le valider ✓"); }
  });
  document.body.append(wrap);
  area.focus();
}

function dbVote(b) {
  if (!game.debate) return;
  dbReadyKey = "";  // l'écran se cache tout de suite pour le prochain votant
  b.closest(".db-scale")?.querySelectorAll("button").forEach((x) => { x.disabled = true; });  // un seul vote
  b.classList.add("on");
  haptic(30);
  dbSending = b.dataset.dbKey;
  pressed(b, gameAction("dbvote", { who: b.dataset.dbWho, amount: +b.dataset.dbVote })).finally(() => { dbSending = ""; });
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "debate") return;
  const pick = ev.target.closest("[data-db-vote]");
  if (pick) return dbVote(pick);
  const ready = ev.target.closest("[data-db-ready]");
  if (ready) { dbReadyKey = ready.dataset.dbReady; haptic(20); return renderGame(game); }
  if (ev.target.closest("[data-db-compose]")) return dbOpenSheet();
  const ok = ev.target.closest("[data-db-accept]");
  if (ok) return pressed(ok, gameAction("dbaccept", { amount: +ok.dataset.dbAccept }));
  const no = ev.target.closest("[data-db-refuse]");
  if (no) return pressed(no, gameAction("dbrefuse", { amount: +no.dataset.dbRefuse }));
  const v = game.debate;
  const theme = ev.target.closest("[data-db-theme]");
  if (theme) {
    const id = theme.dataset.dbTheme, themes = v.themes.includes(id) ? v.themes.filter((t) => t !== id) : [...v.themes, id];
    if (!themes.length) return toast("Garde au moins un thème", "err");
    return pressed(theme, gameAction("dbset", { settings: { themes } }));
  }
  const count = ev.target.closest("[data-db-count]");
  if (count) return pressed(count, gameAction("dbset", { settings: { count: +count.dataset.dbCount } }));
  const pub = ev.target.closest("[data-db-public]");
  if (pub) return pressed(pub, gameAction("dbset", { settings: { public: pub.dataset.dbPublic === "true" } }));
});
