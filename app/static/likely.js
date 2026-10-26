// 🫵 Qui est le plus… ? : chacun désigne quelqu'un en secret sur son téléphone (en même temps) ; le téléphone de
// l'animateur fait voter ceux qui n'en ont pas. Le plus désigné prend un point (ou boit). Chargé après games.js (utilise gameAction, pressed, pyrFlash, manualForm, playerTag, patch…).
GAME_THEME.likely = "g-lk";
GAME_PHASES.ask = "Vote secret";
GAME_RULES.likely = `
  <h3>Le principe</h3>
  <p>Une question s'affiche (« Qui est le plus mauvais perdant ? ») et tout le monde vote <b>en même temps, en secret</b>, sur son téléphone : on touche le prénom de la personne qu'on désigne. On peut se désigner soi-même. Un vote est définitif.</p>
  <h3>Sans téléphone ?</h3>
  <p>L'animateur peut ajouter des participants sans téléphone : son écran dit à qui passer son téléphone. La personne touche « C'est moi », vote, et l'écran se cache aussitôt. Quelqu'un est absent ? L'animateur le passe.</p>
  <h3>La révélation</h3>
  <p>Quand tout le monde a voté, le téléphone révèle le plus désigné et le nombre de voix de chacun, <b>jamais qui a voté pour qui</b>. Il prend un point ; avec l'option alcool, il boit ses gorgées. En cas d'égalité, tous les ex æquo sont désignés.</p>
  <h3>Les questions</h3>
  <ul>
    <li><b>👨‍👩‍👧 Tous publics</b> : 365 questions, à jouer aussi avec les parents et les ados.</li>
    <li><b>😏 Entre amis</b> : en plus, une centaine de questions plus piquantes (soirées, ex, petits secrets), jamais sexuelles.</li>
  </ul>
  <p>Aucune question ne revient dans la partie. Avant le premier vote, l'animateur peut en tirer une autre (🔀).</p>
  <h3>La fin</h3>
  <p>Après 10, 20 ou 30 questions, le podium désigne « le plus susceptible de la soirée ». Personne n'est obligé de boire de l'alcool : un verre d'eau compte aussi.</p>`;

let lkReadyKey = "";  // le votant a touché « C'est moi » : la grille des prénoms s'affiche pour lui
let lkSeen = "";

const lkVoterKey = (g) => `${g.id}:${g.likely.n}:${g.likely.voter?.pid || ""}`;
const lkStake = (g) => g.options?.sips ? `boit ${sipWord(g.options.sips)}` : "prend 1 point";

function lkQuestion(v, small = false) {
  return `<div class="lk-q ${small ? "small" : ""}"><div class="lk-q-n">Question ${v.n}/${v.count}</div><div class="lk-q-t">${esc(v.q || "")}</div></div>`;
}

function lkDots(v) {
  return `<div class="lk-dots" role="img" aria-label="${v.done.length} sur ${v.total} ont voté">${Array.from({ length: v.total }, (_, i) =>
    `<i class="${i < v.done.length ? "on" : ""}"></i>`).join("")}</div>`;
}

function lkSettingsHtml(g) {
  const v = g.likely, sips = g.options?.sips || 0;
  const packs = v.pack_list.map((p) => `<button type="button" class="${v.packs.includes(p.id) ? "on" : ""}" data-lk-pack="${p.id}" aria-pressed="${v.packs.includes(p.id)}">${esc(p.label)} <small>${p.size}</small></button>`).join("");
  const counts = v.counts.map((n) => `<button type="button" class="${v.count === n ? "on" : ""}" data-lk-count="${n}" aria-pressed="${v.count === n}">${n}</button>`).join("");
  const stakes = [0, ...Array.from({ length: v.max_sips }, (_, i) => i + 1)].map((n) =>
    `<button type="button" class="${sips === n ? "on" : ""}" data-lk-sips="${n}" aria-pressed="${sips === n}">${n ? `🍻 ${sipWord(n)}` : "⭐ 1 point"}</button>`).join("");
  return `<div class="lk-setup">
    <div class="g-label">Questions</div><div class="lk-chips">${packs}</div>
    <div class="g-label">Nombre de questions</div><div class="lk-chips">${counts}</div>
    <div class="g-label">Le plus désigné…</div><div class="lk-chips">${stakes}</div>
  </div>`;
}

function lkLobbyHtml(g) {
  const n = g.players.length;
  const hero = `<div class="lk-hero"><div class="lk-hero-i">🫵</div><div><div class="lk-hero-t">Qui est le plus…&nbsp;?</div>
    <div class="lk-hero-s">Chacun désigne quelqu'un en secret, sur son téléphone.</div></div></div>`;
  if (!g.is_host) {
    return `${hero}<div class="lk-card"><div class="title">${g.me ? "Tu es inscrit ✓" : `Partie de ${esc(g.host_name || "quelqu'un")}`}</div>
      <p class="artist">${esc(g.host_name || "L'animateur")} va lancer la première question : tu voteras sur ton téléphone.</p>
      ${g.me ? "" : `<button class="lk-main" data-gact="join">Je joue aussi</button>`}</div>`;
  }
  return `${hero}${lkSettingsHtml(g)}
    <p class="artist lk-help">${n < 2 ? "Ajoute les prénoms de tout le monde plus bas (au moins 2 joueurs)." : `${n} joueurs : chacun vote sur son téléphone ; le tien passe à ceux qui n'en ont pas, dans l'ordre de la liste.`}</p>
    <button class="lk-main" data-gact="start" ${n < 2 ? "disabled" : ""}>▶︎ Première question</button>`;
}

function lkGridHtml(g, who, title) {
  const v = g.likely;
  return `<div class="lk-who">🤫 ${title}</div>
    <div class="lk-grid">${g.players.map((p) => `<button type="button" class="lk-pick" data-lk-vote="${esc(p.pid)}" data-lk-who="${esc(who)}">${esc(p.name)}${p.pid === who ? " <small>(moi)</small>" : ""}</button>`).join("")}</div>`;
}

// Téléphone de l'animateur : il passe aux participants sans téléphone, dans l'ordre de la table.
function lkPassHtml(g) {
  const v = g.likely;
  if (!v.voter) return "";
  if (lkReadyKey === lkVoterKey(g)) return lkGridHtml(g, v.voter.pid, `${esc(v.voter.name)}, qui désignes-tu&nbsp;?`);
  return `<div class="lk-pass">
      <div class="lk-pass-k">📱 Passe le téléphone à</div><div class="lk-name">${esc(v.voter.name)}</div>
      <button class="lk-main" data-lk-ready="${esc(lkVoterKey(g))}">C'est moi, ${esc(v.voter.name)} 👋</button>
      <button class="lk-sub" data-gact="lkskip">⏭ Passer ${esc(v.voter.name)} (absent)</button>
    </div>`;
}

// Animateur : ceux qui ont leur téléphone et n'ont pas encore voté (on peut passer un absent).
function lkWaitingHtml(g) {
  const v = g.likely, phones = v.waiting.filter((x) => !x.manual && x.pid !== g.me?.pid);
  if (!g.is_host || !phones.length) return "";
  return `<div class="lk-card lk-waiting"><div class="artist">Réfléchissent encore…</div>
    <div class="lk-row">${phones.map((x) => `<button class="lk-sub" data-gact="lkskip" data-target="${esc(x.pid)}" title="Passer ${esc(x.name)} (absent)">⏭ ${esc(x.name)}</button>`).join("")}</div></div>`;
}

function lkAskHtml(g) {
  const v = g.likely;
  // Chacun vote sur son propre téléphone, en même temps ; une fois voté, la grille disparaît (vote secret et définitif).
  const mine = v.can_vote ? lkGridHtml(g, g.me.pid, "Qui désignes-tu&nbsp;? C'est secret.")
    : g.me && v.done.includes(g.me.pid) ? `<div class="lk-card lk-done"><div class="lk-name">✓ Vote enregistré</div><div class="artist">Résultat quand tout le monde a voté.</div></div>` : "";
  const host = g.is_host && !v.can_vote ? lkPassHtml(g) + lkWaitingHtml(g) : "";
  return `${lkQuestion(v)}${mine}${host}${lkDots(v)}
    ${g.is_host && !v.voted ? `<div class="lk-row"><button class="lk-sub" data-gact="lkswap">🔀 Autre question</button></div>` : ""}`;
}

function lkBarsHtml(v) {
  const max = Math.max(1, ...v.result.rows.map((r) => r.count));
  return `<div class="lk-bars">${v.result.rows.map((r) => `<div class="lk-bar"><span>${esc(r.name)}</span>
    <i style="--w:${Math.round((r.count / max) * 100)}%"></i><b>${r.count}</b></div>`).join("")}</div>`;
}

function lkScoresHtml(v, limit) {
  return `<div class="lk-scores"><h3>Points</h3>${v.scores.slice(0, limit).map((r) =>
    `<div class="lk-score"><span>${esc(r.name)}</span><b>⭐ ${r.pts}</b></div>`).join("")}</div>`;
}

function lkRevealHtml(g) {
  const v = g.likely, w = v.result?.winners || [];
  const each = g.options?.sips ? `boivent ${sipWord(g.options.sips)} chacun` : "prennent 1 point chacun";
  const verdict = !w.length ? `<div class="lk-win-t">Personne n'a voté</div><p class="artist">Pas de point pour cette question.</p>`
    : `<div class="lk-win-k">${w.length > 1 ? "Égalité !" : "Le plus désigné"}</div><div class="lk-win-t">🫵 ${w.map((x) => esc(x.name)).join(" & ")}</div>
       <p class="lk-win-s">${w.length > 1 ? each : lkStake(g)}</p>`;
  return `${lkQuestion(v, true)}<div class="lk-win">${verdict}</div>${w.length ? lkBarsHtml(v) : ""}
    ${g.is_host ? `<button class="lk-main" data-gact="next">${v.n >= v.count ? "🏆 Voir le podium" : "▶︎ Question suivante"}</button>` : ""}
    ${lkScoresHtml(v, 5)}`;
}

function lkEndHtml(g) {
  const v = g.likely, [a, b, c] = v.scores;
  const step = (r, medal, cls) => r ? `<div class="lk-step ${cls}"><div class="lk-medal">${medal}</div><div class="lk-step-n">${esc(r.name)}</div><div class="lk-step-p">⭐ ${r.pts}</div></div>` : "";
  const recap = v.history.map((h) => `<li>${esc(h.q)} <span>→ ${h.winners.length ? h.winners.map(esc).join(" & ") : "personne"}</span></li>`).join("");
  return `<div class="lk-end-k">Le plus susceptible de la partie</div>
    <div class="lk-podium">${step(b, "🥈", "second")}${step(a, "🥇", "first")}${step(c, "🥉", "third")}</div>
    ${lkScoresHtml(v, v.scores.length)}
    <details class="lk-recap"><summary>Revoir les ${v.history.length} questions</summary><ol>${recap}</ol></details>
    ${g.is_host ? `${lkSettingsHtml(g)}<button class="lk-main" data-gact="restart">🔁 Rejouer avec les mêmes joueurs</button>` : ""}`;
}

function likelyHtml(g) {
  if (!g.likely) return "";
  if (g.phase === "ask") return lkAskHtml(g);
  if (g.phase === "reveal") return lkRevealHtml(g);
  if (g.phase === "end") return lkEndHtml(g);
  return lkLobbyHtml(g);
}

// Liste des joueurs (ordre de passage du téléphone pour ceux qui n'en ont pas) et ajout des prénoms, avant la première question.
function renderLikelyHost(g) {
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

// Révélation : annonce plein écran, une fois par question.
function lkAnnounce(g) {
  const key = `${g.id}|${g.phase}|${g.likely?.n}`;
  if (lkSeen && lkSeen !== key && g.phase === "reveal") {
    const w = g.likely.result?.winners || [];
    if (w.length) pyrFlash("summit", `🫵 ${w.map((x) => esc(x.name)).join(" & ")}`, w.length > 1 ? "Égalité !" : lkStake(g), "", 2600);
  }
  lkSeen = key;
}

function lkVote(b) {
  if (!game.likely) return;
  lkReadyKey = "";  // l'écran se cache tout de suite pour le prochain votant
  b.closest(".lk-grid")?.querySelectorAll("button").forEach((x) => { x.disabled = true; });  // un seul vote
  b.classList.add("on");
  haptic(30);
  pressed(b, gameAction("lkvote", { who: b.dataset.lkWho, target: b.dataset.lkVote }));
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "likely") return;
  const pick = ev.target.closest("[data-lk-vote]");
  if (pick) return lkVote(pick);
  const ready = ev.target.closest("[data-lk-ready]");
  if (ready) { lkReadyKey = ready.dataset.lkReady; haptic(20); return renderGame(game); }
  const v = game.likely;
  const pack = ev.target.closest("[data-lk-pack]");
  if (pack) {
    const id = pack.dataset.lkPack, packs = v.packs.includes(id) ? v.packs.filter((p) => p !== id) : [...v.packs, id];
    if (!packs.length) return toast("Garde au moins un paquet de questions", "err");
    return pressed(pack, gameAction("lkset", { settings: { packs } }));
  }
  const count = ev.target.closest("[data-lk-count]");
  if (count) return pressed(count, gameAction("lkset", { settings: { count: +count.dataset.lkCount } }));
  const sips = ev.target.closest("[data-lk-sips]");
  if (sips) return pressed(sips, gameAction("lkset", { settings: { sips: +sips.dataset.lkSips } }));
});
