// 😈 Purify Test : chacun coche en secret ce qu'il a déjà fait ; l'animateur révèle les scores d'impureté, jamais les réponses.
// Chargé après games.js (utilise gameAction, pressed, pyrFlash, supabaseToken, showTab…).
GAME_THEME.purity = "g-pu";
GAME_PHASES.answering = "Réponses en secret";
GAME_RULES.purity = `
  <h3>Le principe</h3>
  <p>Le « Purity Test » classique : 100 questions en 9 catégories (relations, sexualité, lieux insolites, à plusieurs, fétiches, alcool, drogues, infractions…). Chacun, sur son téléphone, répond « oui » en secret à tout ce qu'il a <b>déjà vécu au moins une fois</b>, puis valide.</p>
  <p>Les questions sexuelles concernent des expériences consenties entre adultes. Le score est un jeu, sans jugement de valeur.</p>
  <h3>Le score</h3>
  <p>Ton score d'impureté = ton nombre de « oui » sur 100 : 0 % = pur comme un ange, 100 % = tu as tout fait. Ton score te vaut un grade, de « 😇 Sainte-Nitouche certifiée » à « 👹 Le Diable en personne ». À la fin, ton <b>profil par catégorie</b> (radar) montre où tu es sage… et où tu l'es beaucoup moins. Il n'est visible que par toi, et tu le retrouves dans Réglages → « Mes stats de jeu ».</p>
  <h3>La révélation</h3>
  <p>Quand tout le monde a validé, l'animateur révèle les scores et le classement, du plus sulfureux au plus sage. <b>Les réponses ne sont jamais montrées</b>, à personne : seul le score compte.</p>
  <h3>🔒 Comptes connectés</h3>
  <p>Pour jouer, il faut être connecté avec son numéro (onglet « Se connecter ») : ton score est lié à ton compte.</p>
  <h3>🌍 Classement général</h3>
  <p>Chaque test révélé compte : ton record d'impureté est gardé d'une soirée à l'autre.</p>
  <h3>🍻 Option alcool</h3>
  <p>Si l'animateur l'active, le plus sulfureux de la tablée boit les gorgées choisies.</p>`;

const PU_SIPS = [1, 2, 3, 5];
let puSeen = "";

// Grades selon le score d'impureté (%) : premier plafond qui n'est pas dépassé, du plus sage au plus sulfureux.
const PU_GRADES = [
  [0, "😇", "Sainte-Nitouche certifiée"],
  [5, "👼", "Enfant de chœur"],
  [12, "🧸", "Bisounours en liberté"],
  [22, "🍵", "Tisane, plaid & Netflix"],
  [35, "😏", "Sage… en apparence"],
  [48, "🍷", "Bon vivant·e"],
  [60, "🌶️", "Épicé·e"],
  [72, "😈", "Sulfureux·se"],
  [84, "🔥", "Diablotin·e de compétition"],
  [94, "🚔", "Casier bien rempli"],
  [100, "👹", "Le Diable en personne"],
];
function puGrade(score) {
  const [, emoji, title] = PU_GRADES.find(([max]) => score <= max) || PU_GRADES[PU_GRADES.length - 1];
  return `${emoji} ${title}`;
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
  return `<div class="pu-hero"><div class="pu-hero-i">😇</div><div><div class="pu-hero-t">${v.total} questions</div>
    <div class="pu-hero-s">Réponds « oui » en secret à ce que tu as déjà vécu. Personne ne verra tes réponses.</div></div></div>
    <p class="artist pu-disclaimer">Les questions sexuelles concernent des expériences consenties entre adultes. Le score est un jeu, sans jugement de valeur.</p>
    ${g.is_host ? puSettingsHtml(g) : v.alcohol ? `<p class="artist">🍻 Le plus sulfureux boit ${v.sips} gorgée${v.sips > 1 ? "s" : ""}.</p>` : ""}
    ${g.is_host ? `<button class="py-main" data-gact="start" ${g.players.length ? "" : "disabled"}>▶︎ Ouvrir le test</button>`
      : `<div class="py-wait">Tu es inscrit ✓ L'animateur va ouvrir le test…</div>`}`;
}

function puProgressHtml(v) {
  const pct = v.count_players ? Math.round(100 * v.count_submitted / v.count_players) : 0;
  return `<div class="pu-progress"><span><b>${v.count_submitted}/${v.count_players}</b> ont validé</span>
    <div class="pu-bar"><i style="width:${pct}%"></i></div></div>`;
}

// Questions posées catégorie par catégorie, chacune sous son titre.
function puQuestionsHtml(v) {
  const sections = v.categories.map((c) => {
    const qs = v.questions.filter((q) => q.cat === c.id);
    const rows = qs.map((q) => {
      const on = !!v.mine?.[q.i];
      return `<button type="button" class="pu-q ${on ? "on" : ""}" data-pu-i="${q.i}" aria-pressed="${on}">
        <span class="pu-n">${q.i + 1}</span><span class="pu-t">${esc(q.text)}</span></button>`;
    }).join("");
    return `<section class="pu-sec"><h4 class="pu-cat"><span>${c.emoji}</span>${esc(c.label)}<small>${qs.length} questions</small></h4>${rows}</section>`;
  }).join("");
  return `<div class="pu-sticky"><span>Touche ce que tu as déjà vécu</span><span><b id="puCount">${v.answered}</b> oui</span></div>
    <div class="pu-list">${sections}</div>
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
      <span class="pu-lb-best">${r.best} %</span><small>record · ${r.plays} test${r.plays > 1 ? "s" : ""} · dernier ${r.last} %</small></li>`).join("")}</ol></div>`;
}

// Radar : un axe par catégorie, le centre = pur, le bord = 100 % impur. Chaque pointe porte l'emoji et l'impureté de la catégorie.
function puRadarSvg(rows) {
  const R = 100, n = rows.length;
  const at = (i, r) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return [r * Math.cos(a), r * Math.sin(a)].map((x) => x.toFixed(1));
  };
  const poly = (r) => rows.map((_, i) => at(i, r).join(",")).join(" ");
  const rings = [25, 50, 75, 100].map((p) => `<polygon class="pu-ring ${p === 100 ? "outer" : ""}" points="${poly(p)}"/>`).join("");
  const spokes = rows.map((_, i) => `<line class="pu-spoke" x1="0" y1="0" x2="${at(i, R)[0]}" y2="${at(i, R)[1]}"/>`).join("");
  const shape = rows.map((r, i) => at(i, Math.max(r.pct, 3)).join(",")).join(" ");
  const dots = rows.map((r, i) => { const [x, y] = at(i, Math.max(r.pct, 3)); return `<circle class="pu-dot" cx="${x}" cy="${y}" r="3.5"/>`; }).join("");
  const labels = rows.map((r, i) => {
    const [x, y] = at(i, R + 24);
    return `<text class="pu-ax-e" x="${x}" y="${y}" text-anchor="middle">${r.emoji}</text>
      <text class="pu-ax-v" x="${x}" y="${(+y + 15).toFixed(1)}" text-anchor="middle">${r.pct}%</text>`;
  }).join("");
  return `<svg class="pu-radar" viewBox="-140 -138 280 284" role="img" aria-label="Impureté par catégorie">
    ${rings}${spokes}<polygon class="pu-shape" points="${shape}"/>${dots}${labels}</svg>`;
}

// Profil par catégorie (radar + liste, de la plus impure à la plus sage) : fin de partie et Réglages.
function puProfileHtml(rows) {
  if (!rows?.length) return "";
  const sorted = [...rows].sort((a, b) => b.pct - a.pct || a.label.localeCompare(b.label));
  const list = sorted.map((r) => `<div class="pu-cat-row"><span class="pu-cat-e">${r.emoji}</span><b>${esc(r.label)}</b>
      <span class="pu-row-bar"><i style="width:${r.pct}%"></i></span><span class="pu-row-s">${r.yes}/${r.total}</span></div>`).join("");
  return `<div class="pu-profile"><h3>Ton profil d'impureté <small>🔒 toi seul le vois</small></h3>
    ${puRadarSvg(rows)}<div class="pu-cat-list">${list}</div></div>`;
}

function puScoreHtml(score, title) {
  return `<div class="pu-score"><div class="pu-score-k">${title}</div>
    <div class="pu-score-v">${score} %</div><div class="pu-score-l">${puGrade(score)}</div></div>`;
}

function puResultsHtml(g) {
  const v = g.purity, me = g.me?.pid;
  const mine = v.me_score != null ? puScoreHtml(v.me_score, "Ton score d'impureté") : "";
  const last = v.ranking.length - 1;
  const rows = v.ranking.map((r, i) => `<div class="pu-row ${r.pid === me ? "me" : ""}">
      <span class="pu-rank">${i === 0 && r.score ? "😈" : i === last ? "😇" : i + 1}</span><span class="pu-who"><b>${esc(r.name)}</b><small>${puGrade(r.score)}</small></span>
      <span class="pu-row-bar"><i style="width:${r.score}%"></i></span><span class="pu-row-s">${r.score} %</span></div>`).join("");
  const d = v.gorgees;
  const drinks = d.length ? `<div class="pu-drink">🍻 ${d.map((x) => esc(x.name)).join(", ")} ${d.length > 1 ? "boivent" : "boit"} ${d[0].sips} gorgée${d[0].sips > 1 ? "s" : ""} !</div>` : "";
  return `${mine}${puProfileHtml(v.me_categories)}<div class="pu-board"><h3>Du plus sulfureux au plus sage</h3>${rows}</div>${drinks}
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
    if (top.score) pyrFlash("summit", `😈 ${esc(top.name)}`, `le plus sulfureux · ${top.score} % impur`, "", 3200);
    else pyrFlash("summit", "😇 Que des anges", "0 % d'impureté pour tout le monde", "", 3200);
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

// 📊 Réglages → « Mes stats de jeu », onglet Purify Test : dernier test (score, grade, radar) et record, pour le seul titulaire du compte.
function puStatsHtml(me) {
  if (!me.plays) {
    return `<div class="pu-card"><div class="pu-big">😇</div><div class="title">Pas encore de test</div>
      <p class="artist">Passe le Purify Test dans l'onglet Jeux : ton dernier score et ton profil apparaîtront ici.</p>
      <button class="py-main" data-tab="games">🎮 Aller aux jeux</button></div>`;
  }
  const when = me.last_at ? new Date(me.last_at * 1000).toLocaleDateString("fr-CH", { day: "numeric", month: "long", year: "numeric" }) : "";
  return `${puScoreHtml(me.last, "Ton dernier score d'impureté")}
    <p class="artist pu-when">${when ? `Test du ${when} · ` : ""}🏆 Record : ${me.best} % · ${me.plays} test${me.plays > 1 ? "s" : ""} passé${me.plays > 1 ? "s" : ""}</p>
    ${puProfileHtml(me.categories)}`;
}

let puStatsLoading = false;
async function puStatsShow() {
  if (puStatsLoading) return;  // ouverture et chargement du fichier peuvent le demander en même temps
  const root = $("purityStats");
  const token = await freshToken();
  if (!token) {
    root.innerHTML = `<div class="pu-card"><div class="pu-big">🔒</div><div class="title">Réservé aux comptes connectés</div>
      <p class="artist">Connecte-toi avec ton numéro pour retrouver tes stats Purify Test.</p>
      <button class="py-main" data-pu-login>Se connecter</button></div>`;
    return;
  }
  root.innerHTML = `<p class="artist" role="status">Chargement de tes stats…</p>`;
  puStatsLoading = true;
  try {
    // fetch direct : api() prendrait un jeton expiré (401) pour une demande de code de soirée.
    const r = await fetch("/api/purity/me", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(r.status === 401 ? "ta connexion a expiré, reconnecte-toi" : data.detail || "erreur réseau");
    root.innerHTML = puStatsHtml(data);
  } catch (e) {
    root.innerHTML = `<div class="pu-card"><p class="artist">Impossible de charger tes stats : ${esc(e.message)}</p>
      <button class="py-sub" data-pu-stats-retry>Réessayer</button></div>`;
  } finally {
    puStatsLoading = false;
  }
}

document.addEventListener("click", (ev) => {
  if (ev.target.closest("[data-pu-login]")) return showTab("account");
  if (ev.target.closest("[data-pu-stats-retry]")) return puStatsShow();
  if (game?.type !== "purity") return;
  const q = ev.target.closest("[data-pu-i]");
  if (q) return puToggle(q);
  const act = ev.target.closest("[data-pu-act]");
  if (act && !act.disabled) return puRevealOk(act) && pressed(act, gameAction(act.dataset.puAct));
  const sips = ev.target.closest("[data-pu-sips]");
  if (sips && !sips.disabled) return pressed(sips, gameAction("puset", { settings: { sips: +sips.dataset.puSips } }));
});
document.addEventListener("change", (ev) => {
  if (ev.target.matches("[data-pu-alcohol]") && game?.type === "purity") gameAction("puset", { settings: { alcohol: ev.target.checked } });
});
// Onglet « Purify Test » de « Mes stats de jeu » ; app rouverte sur cette page : affiché dès que ce fichier est chargé.
STATS_TABS.purity = puStatsShow;
if (document.body.dataset.tab === "stats" && statsTab === "purity") puStatsShow();
