// 😇 Purify Test : chacun coche en secret ce qu'il a déjà fait ; l'animateur révèle les scores, jamais les réponses.
// Chargé après games.js (utilise gameAction, pressed, pyrFlash, supabaseToken, showTab…).
GAME_THEME.purity = "g-pu";
GAME_PHASES.answering = "Réponses en secret";
GAME_RULES.purity = `
  <h3>Le principe</h3>
  <p>Une centaine d'affirmations, de la plus innocente à la plus osée. Chacun, sur son téléphone, coche en secret tout ce qu'il a <b>déjà fait</b>, puis valide.</p>
  <h3>Le score</h3>
  <p>Ton score de pureté est le pourcentage de choses que tu n'as <b>jamais faites</b> : 100 % = pur comme un ange, 0 % = tu as tout fait.</p>
  <h3>La révélation</h3>
  <p>Quand tout le monde a validé, l'animateur révèle les scores et le classement, du plus pur au plus sulfureux. <b>Les réponses ne sont jamais montrées</b>, à personne : seul le score compte.</p>
  <h3>🔒 Comptes connectés</h3>
  <p>Pour jouer, il faut être connecté avec son numéro (onglet « Se connecter ») : ton score est lié à ton compte.</p>
  <h3>🌍 Classement général</h3>
  <p>Chaque test révélé compte : ton meilleur score est gardé d'une soirée à l'autre.</p>
  <h3>🍻 Option alcool</h3>
  <p>Si l'animateur l'active, le plus sulfureux de la tablée boit les gorgées choisies.</p>`;

const PU_SIPS = [1, 2, 3, 5];
let puSeen = "";

function puVerdict(score) {
  if (score >= 90) return "😇 Pur comme un ange";
  if (score >= 70) return "🙂 Plutôt sage";
  if (score >= 50) return "😏 Ni saint ni démon";
  if (score >= 30) return "😈 Sulfureux";
  return "🔥 Diabolique";
}

function puSettingsHtml(g) {
  const v = g.purity;
  const sips = PU_SIPS.map((n) => `<button type="button" class="${v.sips === n ? "on" : ""}" data-pu-sips="${n}" ${v.alcohol ? "" : "disabled"}>${n}</button>`).join("");
  return `<div class="pu-setup">
    <label class="g-opt"><span>🍻 Le plus sulfureux boit</span><input type="checkbox" class="switch" data-pu-alcohol ${v.alcohol ? "checked" : ""}></label>
    <div class="pu-chips" aria-label="Gorgées">${sips}<small>gorgée${v.sips > 1 ? "s" : ""}</small></div>
  </div>`;
}

// Visiteur : participation réservée aux comptes Party connectés.
function puOutsiderHtml(g) {
  if (!supabaseToken()) {
    return `<div class="pu-card"><div class="pu-big">🔒</div>
      <div class="title">Réservé aux comptes connectés</div>
      <p class="artist">Connecte-toi avec ton numéro pour passer le test : ton score sera lié à ton compte.</p>
      <button class="py-main" data-pu-login>Se connecter</button></div>`;
  }
  return `<div class="pu-card"><div class="title">Test de ${esc(g.host_name || "quelqu'un")}</div>
    <p class="artist">${g.players.length} participant${g.players.length > 1 ? "s" : ""}</p>
    <button class="py-main" data-gact="join">😇 Passer le test</button></div>`;
}

function puLobbyHtml(g) {
  const v = g.purity;
  return `<div class="pu-hero"><div class="pu-hero-i">😇</div><div><div class="pu-hero-t">${v.total} affirmations</div>
    <div class="pu-hero-s">Coche en secret ce que tu as déjà fait. Personne ne verra tes réponses.</div></div></div>
    ${g.is_host ? puSettingsHtml(g) : v.alcohol ? `<p class="artist">🍻 Le plus sulfureux boit ${v.sips} gorgée${v.sips > 1 ? "s" : ""}.</p>` : ""}
    ${g.is_host ? `<button class="py-main" data-gact="start" ${g.players.length ? "" : "disabled"}>▶︎ Ouvrir le test</button>`
      : `<div class="py-wait">Tu es inscrit ✓ L'animateur va ouvrir le test…</div>`}`;
}

function puProgressHtml(v) {
  const pct = v.count_players ? Math.round(100 * v.count_submitted / v.count_players) : 0;
  return `<div class="pu-progress"><span><b>${v.count_submitted}/${v.count_players}</b> ont validé</span>
    <div class="pu-bar"><i style="width:${pct}%"></i></div></div>`;
}

function puQuestionsHtml(v) {
  const rows = v.questions.map((q) => {
    const on = !!v.mine?.[q.i];
    return `<button type="button" class="pu-q ${on ? "on" : ""}" data-pu-i="${q.i}" aria-pressed="${on}">
      <span class="pu-n">${q.i + 1}</span><span class="pu-t">${esc(q.text)}</span><span class="pu-lv" title="${q.level}">${q.emoji}</span></button>`;
  }).join("");
  return `<div class="pu-sticky"><span>Est-ce que tu as déjà…</span><span><b id="puCount">${v.answered}</b> coché(s)</span></div>
    <div class="pu-list">${rows}</div>
    <button class="py-main pu-submit" data-pu-act="pusub">✅ Valider mes réponses</button>
    <p class="artist pu-note">Tu pourras encore les modifier tant que l'animateur n'a pas révélé les scores.</p>`;
}

function puAnsweringHtml(g) {
  const v = g.purity;
  const filling = v.playing && !v.submitted;
  const waiting = v.playing && v.submitted
    ? `<div class="pu-card"><div class="pu-big">🔒</div><div class="title">Réponses envoyées</div>
      <p class="artist">Personne ne les verra. En attente de la révélation…</p>
      <button class="py-sub" data-pu-act="puunsub">✏️ Modifier mes réponses</button></div>` : "";
  const missing = v.count_players - v.count_submitted;
  const reveal = g.is_host ? `<button class="py-main pu-reveal" data-pu-act="pureveal" data-missing="${missing}" ${v.count_submitted ? "" : "disabled"}>🎉 Révéler les scores</button>` : "";
  return filling ? puProgressHtml(v) + puQuestionsHtml(v) + reveal : puProgressHtml(v) + waiting + reveal;
}

function puLeaderboardHtml(lb) {
  if (!lb?.rows?.length) return "";
  return `<div class="pu-lb"><h3>🌍 Classement général <small>${lb.total} compte${lb.total > 1 ? "s" : ""}</small></h3>
    <ol>${lb.rows.slice(0, 10).map((r, i) => `<li><span class="pu-rank">${i + 1}</span><b>${esc(r.name)}</b>
      <span class="pu-lb-best">${r.best} %</span><small>${r.plays} test${r.plays > 1 ? "s" : ""} · dernier ${r.last} %</small></li>`).join("")}</ol></div>`;
}

function puResultsHtml(g) {
  const v = g.purity, me = g.me?.pid;
  const mine = v.me_score != null ? `<div class="pu-score"><div class="pu-score-k">Ton score de pureté</div>
      <div class="pu-score-v">${v.me_score} %</div><div class="pu-score-l">${puVerdict(v.me_score)}</div></div>` : "";
  const last = v.ranking.length - 1;
  const rows = v.ranking.map((r, i) => `<div class="pu-row ${r.pid === me ? "me" : ""}">
      <span class="pu-rank">${i === 0 ? "😇" : i === last ? "😈" : i + 1}</span><b>${esc(r.name)}</b>
      <span class="pu-row-bar"><i style="width:${r.score}%"></i></span><span class="pu-row-s">${r.score} %</span></div>`).join("");
  const d = v.gorgees;
  const drinks = d.length ? `<div class="pu-drink">🍻 ${d.map((x) => esc(x.name)).join(", ")} ${d.length > 1 ? "boivent" : "boit"} ${d[0].sips} gorgée${d[0].sips > 1 ? "s" : ""} !</div>` : "";
  return `${mine}<div class="pu-board"><h3>Du plus pur au plus sulfureux</h3>${rows}</div>${drinks}
    ${g.is_host ? `<button class="py-main" data-gact="restart">🔁 Nouveau test</button>` : ""}
    ${puLeaderboardHtml(v.leaderboard)}`;
}

function purityHtml(g) {
  const v = g.purity;
  if (!v) return "";
  if (g.phase === "results") return puResultsHtml(g);
  if (!v.playing && !g.is_host) return puOutsiderHtml(g);
  return g.phase === "lobby" ? puLobbyHtml(g) : puAnsweringHtml(g);
}

// Révélation : annonce plein écran, une fois.
function puAnnounce(g) {
  const key = `${g.id}|${g.phase}`;
  if (puSeen && puSeen !== key && g.phase === "results" && g.purity?.ranking.length) {
    const top = g.purity.ranking[0];
    pyrFlash("summit", `😇 ${esc(top.name)}`, `le plus pur · ${top.score} %`, "", 3200);
    GameAudio.play("win");
  }
  puSeen = key;
}

// Case cochée / décochée : effet immédiat, puis envoyée (sans message si elle arrive trop tard).
function puToggle(b) {
  const on = !b.classList.contains("on");
  b.classList.toggle("on", on);
  b.setAttribute("aria-pressed", on);
  const c = $("puCount");
  if (c) c.textContent = document.querySelectorAll(".pu-q.on").length;
  haptic(15);
  gameAction("puans", { amount: +b.dataset.puI, done: on }, { quiet: true });
}

function puRevealOk(b) {
  const n = +(b.dataset.missing || 0);
  if (b.dataset.puAct !== "pureveal" || !n) return true;
  return confirm(n > 1 ? `${n} participants n'ont pas encore validé et ne seront pas classés. Révéler quand même ?`
    : "1 participant n'a pas encore validé et ne sera pas classé. Révéler quand même ?");
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "purity") return;
  const q = ev.target.closest("[data-pu-i]");
  if (q) return puToggle(q);
  const act = ev.target.closest("[data-pu-act]");
  if (act && !act.disabled) return puRevealOk(act) && pressed(act, gameAction(act.dataset.puAct));
  if (ev.target.closest("[data-pu-login]")) return showTab("account");
  const sips = ev.target.closest("[data-pu-sips]");
  if (sips && !sips.disabled) return pressed(sips, gameAction("puset", { settings: { sips: +sips.dataset.puSips } }));
});
document.addEventListener("change", (ev) => {
  if (ev.target.matches("[data-pu-alcohol]") && game?.type === "purity") gameAction("puset", { settings: { alcohol: ev.target.checked } });
});
