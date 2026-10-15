// 🧠 Quiz : 14 thèmes, 5 modes, seul ou à plusieurs. Chargé après games.js (utilise renderGame, gameAction, pyrFlash…).
GAME_THEME.quiz = "g-qz";
GAME_NAMES.quiz = "Quiz";
GAME_RULES.quiz = `
  <h3>Le principe</h3>
  <p>Des milliers de questions à 4 choix, sur 14 thèmes (culture générale, géographie, histoire, sciences, corps humain, animaux, espace, cinéma & séries, musique, jeux vidéo, BD & mangas, sport, cuisine, Suisse). On joue <b>seul ou à plusieurs</b>, chacun sur son téléphone. L'animateur choisit le mode, les thèmes et la difficulté.</p>
  <h3>🏆 Classique</h3>
  <p>Tout le monde reçoit la même question en même temps. Bonne réponse : <b>500 points + jusqu'à 500 selon la rapidité</b>, et un bonus de série (+50 par bonne réponse d'affilée, jusqu'à +250).</p>
  <h3>⚡ Rapidité</h3>
  <p>Le <b>premier qui trouve</b> gagne la question (1000 points). Une mauvaise réponse te bloque jusqu'à la question suivante : ne réponds pas au hasard !</p>
  <h3>❤️ Survie</h3>
  <p>Chacun a des vies (3 par défaut). Une erreur ou un temps écoulé coûte une vie ; les questions deviennent de plus en plus dures. Le dernier en vie gagne. Seul : tiens le plus longtemps possible.</p>
  <h3>⏱️ Contre-la-montre</h3>
  <p>Chacun à son rythme, le plus de bonnes réponses avant la fin du temps (60 s par défaut). 100 points par bonne réponse, et un bonus quand on enchaîne.</p>
  <h3>🪜 Paliers</h3>
  <p>15 questions de plus en plus difficiles, 30 s chacune. Les paliers <b>1 000</b> et <b>32 000</b> sont assurés : en cas d'erreur, tu redescends au dernier palier atteint. Deux jokers : <b>50/50</b> (retire deux mauvaises réponses) et <b>🔄 Changer</b> la question. Tu peux t'arrêter à tout moment et garder ce que tu as.</p>
  <h3>🌍 Classement général</h3>
  <p>Chaque partie compte : les points, les victoires et les records s'additionnent d'une partie à l'autre dans le classement général.</p>
  <h3>🍻 Option alcool</h3>
  <p>Si l'animateur l'active, chaque mauvaise réponse se boit.</p>`;

const QZ_COLORS = ["qz-a", "qz-b", "qz-c", "qz-d"];
const QZ_SHAPES = ["▲", "◆", "●", "■"];
const QZ_MODE_DESC = {
  classic: "Même question pour tous, points selon la rapidité",
  speed: "Le premier qui trouve gagne, une erreur bloque",
  survival: "Des vies, des questions de plus en plus dures",
  chrono: "Chacun à son rythme, le plus possible en un temps",
  ladder: "15 paliers, jokers, comme à la télé",
};
// Drapeaux (emoji) : affichés en grand, dans la question comme dans les réponses.
const QZ_FLAG = /([\u{1F1E6}-\u{1F1FF}]{2})/gu;
const qzText = (t) => esc(t).replace(QZ_FLAG, '<span class="qz-flag">$1</span>');
const fmtPts = (n) => Number(n || 0).toLocaleString("fr-CH").replace(/[’']/g, " ");
let qzSeen = { key: "", end: "" }, qzTimer = null, qzRefreshAt = 0, qzAnimKey = "";
// Signature de ce qui s'affiche, sans les compteurs de temps (qui changent à chaque requête).
const QZ_TIME_KEYS = new Set(["left", "next_in", "deadline_in", "server_now", "age", "elapsed", "between_in"]);
const qzPauseBtn = (paused) => `<button type="button" class="py-sub qz-pause ${paused ? "on" : ""}" data-qz-pause>${paused ? "▶ Continuer" : "⏸ Pause"}</button>`;
function quizSig(g) {
  return JSON.stringify([g.phase, g.is_host, g.me?.pid, g.players.map((p) => p.name + p.pid), pyrFull,
    JSON.stringify(g.quiz, (k, v) => (QZ_TIME_KEYS.has(k) ? undefined : v))]);
}
// Les animations d'entrée ne se jouent qu'à l'arrivée d'une nouvelle question, d'une révélation ou d'un nouvel écran.
function quizAnimKey(g) {
  const v = g.quiz;
  return [g.id, g.phase, v.n, v.q?.text || "", v.me?.q?.text || "", v.me?.done || false].join("|");
}

// --- Lobby : réglages (animateur) et classement général ---
function qzSettingsHtml(g) {
  const v = g.quiz, s = v.settings, cat = v.catalog;
  if (!cat) return "";
  const lead = g.is_host;
  const dis = lead ? "" : "disabled";
  const total = cat.themes.reduce((n, t) => n + t.count, 0);
  const themes = cat.themes.map((t) => `<button type="button" class="qz-theme ${s.themes.includes(t.id) ? "on" : ""}" data-qz-theme="${t.id}" ${dis}>
      <span class="qz-theme-i">${t.icon}</span><span class="qz-theme-n">${esc(t.name)}</span><small>${fmtPts(t.count)}</small></button>`).join("");
  const solo = g.players.length < 2;
  const modes = cat.modes.map((m) => {
    const off = m.id === "speed" && solo;  // la Rapidité n'a de sens qu'à plusieurs
    return `<button type="button" class="qz-mode ${s.mode === m.id ? "on" : ""} ${off ? "off" : ""}" data-qz-set="mode" data-val="${m.id}" ${dis || (off ? "disabled" : "")}>
      <span class="qz-mode-i">${m.icon}</span><b>${esc(m.name)}</b><small>${off ? "2 joueurs minimum" : QZ_MODE_DESC[m.id]}</small></button>`;
  }).join("");
  const chips = (key, vals, fmt) => `<div class="qz-chips">${vals.map((x) => `<button type="button" class="${String(s[key]) === String(x) ? "on" : ""}" data-qz-set="${key}" data-val="${x}" ${dis}>${fmt(x)}</button>`).join("")}</div>`;
  const extra = {
    classic: `<div class="g-label">Questions</div>${chips("count", [10, 15, 20, 30, 50], (x) => x)}<div class="g-label">Temps par question</div>${chips("time", [10, 15, 20, 30], (x) => x + " s")}`,
    speed: `<div class="g-label">Questions</div>${chips("count", [10, 15, 20, 30, 50], (x) => x)}<div class="g-label">Temps par question</div>${chips("time", [10, 15, 20, 30], (x) => x + " s")}`,
    survival: `<div class="g-label">Vies</div>${chips("lives", [1, 2, 3, 5], (x) => "❤️".repeat(Math.min(x, 3)) + (x > 3 ? `×${x}` : ""))}<div class="g-label">Temps par question</div>${chips("time", [10, 15, 20, 30], (x) => x + " s")}`,
    chrono: `<div class="g-label">Durée</div>${chips("chrono", [30, 60, 90, 120, 180], (x) => x < 120 ? x + " s" : x / 60 + " min")}`,
    ladder: `<p class="artist" style="margin:6px 0 0">15 questions de plus en plus dures · 30 s chacune · paliers assurés à 1 000 et 32 000 · jokers 50/50 et 🔄.</p>`,
  }[s.mode];
  return `<div class="qz-setup">
    <div class="g-label">Mode</div><div class="qz-modes">${modes}</div>
    ${extra}
    ${s.mode !== "ladder" && s.mode !== "survival" ? `<div class="g-label">Difficulté</div>${chips("diff", Object.keys(cat.diffs), (x) => cat.diffs[x])}` : ""}
    <div class="g-label">Thèmes <small>${s.themes.length ? `${s.themes.length} choisi${s.themes.length > 1 ? "s" : ""}` : `tous · ${fmtPts(total)} questions`}</small></div>
    <div class="qz-themes"><button type="button" class="qz-theme all ${s.themes.length ? "" : "on"}" data-qz-theme="" ${dis}><span class="qz-theme-i">🎲</span><span class="qz-theme-n">Tous les thèmes</span><small>${fmtPts(total)}</small></button>${themes}</div>
  </div>`;
}

function qzLeaderboardHtml(lb, title = "🌍 Classement général") {
  if (!lb || !lb.top.length) return `<div class="qz-lb"><h3>${title}</h3><p class="artist">Aucune partie terminée pour l'instant : à vous de marquer les premiers points !</p></div>`;
  const rec = Object.entries(lb.records).map(([m, r]) => {
    const label = { classic: "🏆 Classique", speed: "⚡ Rapidité", survival: "❤️ Survie", chrono: "⏱️ Chrono", ladder: "🪜 Paliers" }[m];
    const val = { survival: `${r.value} bonnes`, chrono: `${r.value} bonnes`, ladder: `palier ${r.value}/15` }[m] || `${fmtPts(r.value)} pts`;
    return `<span class="qz-rec">${label} · <b>${esc(r.name)}</b> ${val}</span>`;
  }).join("");
  return `<div class="qz-lb"><h3>${title}</h3>
    <ol>${lb.top.slice(0, 10).map((x, i) => `<li><span class="qz-rank r${i + 1}">${i + 1}</span><b>${esc(x.name)}</b>
      <span class="qz-lb-pts">${fmtPts(x.pts)}</span><small>${x.games} partie${x.games > 1 ? "s" : ""} · ${x.wins} 🏆 · ${x.rate} % juste${x.streak > 2 ? ` · 🔥${x.streak}` : ""}</small></li>`).join("")}</ol>
    ${rec ? `<div class="qz-recs">${rec}</div>` : ""}</div>`;
}

// --- Question (commune à tous les modes) ---
function qzQuestionHtml(q, opts = {}) {
  const { mine = null, correct = null, locked = false, cut = [], dist = null, act = "qans", disabled = false } = opts;
  const answered = mine !== null && mine !== undefined;
  const btns = q.choices.map((c, i) => {
    let cls = QZ_COLORS[i];
    if (correct !== null) cls += i === correct ? " right" : i === mine ? " wrong" : " dim";
    else if (answered) cls += i === mine ? " picked" : " dim";
    if (cut.includes(i)) cls += " cut";
    const off = disabled || answered || locked || correct !== null || cut.includes(i);
    return `<button type="button" class="qz-ans ${cls}" data-qz-ans="${i}" ${off ? "disabled" : ""}>
      <span class="qz-shape">${QZ_SHAPES[i]}</span><span class="qz-txt">${qzText(c)}</span>${dist ? `<span class="qz-count">${dist[i]}</span>` : ""}</button>`;
  }).join("");
  const stars = "★".repeat(q.d) + "☆".repeat(3 - q.d);
  return `<div class="qz-qcard">
      <div class="qz-qmeta"><span>${q.icon} ${esc(q.theme)}</span><span class="qz-stars" title="Difficulté">${stars}</span></div>
      <div class="qz-qtext ${q.text.length > 90 ? "long" : ""}">${qzText(q.text)}</div>
    </div>
    <div class="qz-answers ${q.choices.some((c) => c.length > 26) ? "long" : ""}">${btns}</div>`;
}

function qzTimerHtml(left, dur, id = "qzBar") {
  const pct = Math.max(0, Math.min(100, (left / dur) * 100));
  return `<div class="qz-timer"><div class="qz-bar" id="${id}" style="width:${pct}%;transition-duration:0s"></div><span class="qz-sec" id="${id}S">${Math.ceil(left)}</span></div>`;
}

// --- Rendu principal ---
function quizHtml(g) {
  const v = g.quiz, s = v.settings, me = g.me;
  const lead = g.is_host;
  if (g.phase === "lobby") {
    const n = g.players.length;
    return `<div class="qz-hero"><div class="qz-hero-i">${v.mode_icon}</div><div><div class="qz-hero-t">${esc(v.mode_label)}</div>
        <div class="artist">${v.theme_labels.map(esc).join(" · ")}${s.mode !== "ladder" && s.mode !== "survival" ? ` · ${esc(v.diff_label)}` : ""}</div></div></div>
      ${lead ? (s.mode === "speed" && n < 2 ? `<div class="py-wait">⚡ La Rapidité se joue à 2 au moins : attends un deuxième joueur ou choisis un autre mode.</div>`
        : `<button class="py-main qz-go" data-gact="start" ${n < 1 ? "disabled" : ""}>▶︎ ${n <= 1 ? "Jouer en solo" : `Lancer le quiz · ${n} joueurs`}</button>`)
        : me ? `<div class="py-wait">Tu es inscrit·e ✓ L'animateur choisit les réglages et lance…</div>` : `<button class="py-main" data-gact="join">Rejoindre le quiz</button>`}
      ${qzSettingsHtml(g)}
      ${qzLeaderboardHtml(v.leaderboard)}`;
  }
  if (g.phase === "end") return qzEndHtml(g);
  if (g.phase === "run") return s.mode === "ladder" ? qzLadderHtml(g) : qzChronoHtml(g);
  // Modes synchronisés : question en cours ou révélation.
  const q = v.q;
  const myRow = v.board.find((r) => r.me);
  const total = s.mode === "survival" ? "" : `/${s.count}`;
  const top = `<div class="qz-top"><span class="qz-num">Question <b>${v.n}${total}</b></span>
    ${s.mode === "survival" && myRow ? `<span class="qz-lives">${"❤️".repeat(Math.max(0, myRow.lives))}${"🖤".repeat(Math.max(0, s.lives - myRow.lives))}</span>` : ""}
    ${myRow ? `<span class="qz-mypts">${fmtPts(myRow.pts)} pts${myRow.streak > 1 ? ` · 🔥${myRow.streak}` : ""}</span>` : ""}</div>`;
  if (g.phase === "q") {
    const status = q.out ? `<div class="qz-status out">💀 Éliminé·e : regarde les autres jouer</div>`
      : q.locked ? `<div class="qz-status bad">❌ Raté ! Bloqué·e jusqu'à la prochaine question</div>`
      : q.mine !== null ? `<div class="qz-status ok">✓ Réponse envoyée · ${q.answered}/${q.players} ont répondu</div>`
      : !me ? `<div class="qz-status">👀 Tu regardes la partie</div>` : `<div class="qz-status">${q.answered}/${q.players} ont répondu</div>`;
    const canPause = lead || g.players.length <= 1;
    const prePause = canPause && (q.mine !== null || q.locked)
      ? `<button type="button" class="py-sub qz-pause ${v.paused ? "on" : ""}" data-qz-pause>${v.paused ? "✓ Pause après la réponse (annuler)" : "⏸ Pause après la réponse"}</button>` : "";
    return top + qzTimerHtml(q.left, q.dur) + qzQuestionHtml(q, { mine: q.mine, locked: q.locked, disabled: !me || q.out })
      + status + prePause + (lead ? `<button class="py-sub" data-gact="next" data-guess="${esc(v.token)}">⏭ Révéler maintenant</button>` : "");
  }
  // Révélation
  const mine = q.res.find((r) => r.me);
  const verdict = !me ? "" : mine ? (mine.ok ? `<div class="qz-verdict ok">✓ Bonne réponse${mine.pts ? ` · <b>+${fmtPts(mine.pts)}</b>` : ""}</div>`
      : s.mode === "speed" && q.winner ? `<div class="qz-verdict bad">⚡ Trop lent : ${esc(q.winner)} a été plus rapide</div>` : `<div class="qz-verdict bad">✗ Raté !</div>`)
    : `<div class="qz-verdict bad">⏰ Pas de réponse</div>`;
  const winner = s.mode === "speed" ? `<div class="qz-speedwin">${q.winner ? `⚡ <b>${esc(q.winner)}</b> a trouvé en premier !` : "Personne n'a trouvé…"}</div>` : "";
  return top + verdict + winner + qzQuestionHtml(q, { mine: q.mine, correct: q.correct, dist: q.dist })
    + qzMiniBoard(v.board, s.mode)
    + `<div class="qz-next">${v.paused ? `<span class="qz-paused">⏸ En pause${lead || g.players.length <= 1 ? "" : " (l'animateur reprendra)"}</span>`
        : `<span>Question suivante dans <b id="qzNextS">${Math.ceil(q.next_in)}</b> s</span>`}
      <span class="qz-next-btns">${lead || g.players.length <= 1 ? qzPauseBtn(v.paused) : ""}${lead && !v.paused ? `<button class="py-sub" data-gact="next" data-guess="${esc(v.token)}">Suivante ▶</button>` : ""}</span></div>`;
}

function qzMiniBoard(board, mode, n = 5) {
  if (board.length < 2) return "";
  return `<div class="qz-mini">${board.slice(0, n).map((r, i) => `<div class="qz-mini-row ${r.me ? "me" : ""} ${r.out ? "out" : ""}">
      <span class="qz-rank r${i + 1}">${i + 1}</span><b>${esc(r.name)}</b>
      ${mode === "survival" ? `<span class="qz-l">${r.out ? "💀" : "❤️".repeat(Math.max(0, r.lives))}</span>` : ""}
      <span class="qz-p">${mode === "ladder" ? `palier ${r.level || 0}` : fmtPts(r.pts)}</span></div>`).join("")}</div>`;
}

function qzChronoHtml(g) {
  const v = g.quiz, m = v.me;
  const myRow = v.board.find((r) => r.me);
  const head = `<div class="qz-top"><span class="qz-num">⏱️ <b id="qzChronoS">${Math.ceil(v.deadline_in || 0)}</b> s</span>
    <span class="qz-mypts">${m ? `${m.i} répondue${m.i > 1 ? "s" : ""}` : ""}</span>
    <span class="qz-mypts">${fmtPts(myRow?.pts || 0)} pts${m?.streak > 1 ? ` · 🔥${m.streak}` : ""}</span></div>`
    + qzTimerHtml(v.deadline_in || 0, v.settings.chrono, "qzChronoBar");
  if (!m) return head + `<div class="py-wait">👀 Tu regardes la partie</div>` + qzMiniBoard(v.board, "chrono", 10);
  const flash = m.last && m.last.age < 1.2 ? `<div class="qz-flash ${m.last.ok ? "ok" : "bad"}">${m.last.ok ? "✓" : `✗ ${esc(m.last.answer)}`}</div>` : "";
  return head + flash + qzQuestionHtml(m.q, {}) + qzMiniBoard(v.board, "chrono", 4);
}

function qzLadderHtml(g) {
  const v = g.quiz, m = v.me;
  const steps = v.ladder.map((val, i) => {
    const cls = [m && i === m.i && !m.done ? "cur" : "", m && i < m.level ? "won" : "", v.safe.includes(i) ? "safe" : ""].join(" ");
    return `<li class="${cls}"><span>${i + 1}</span><b>${fmtPts(val)}</b></li>`;
  }).reverse().join("");
  const ladder = `<ol class="qz-ladder">${steps}</ol>`;
  if (!m) return `<div class="py-wait">👀 Tu regardes la partie</div>` + qzMiniBoard(v.board, "ladder", 10);
  if (m.done) {
    const gain = m.level ? v.ladder[m.level - 1] : 0;
    const title = m.level >= 15 ? "🏆 1 000 000 ! Tu as tout gagné !" : m.stopped ? `🛑 Tu t'arrêtes avec ${fmtPts(gain)}` : `💥 Raté… tu repars avec ${fmtPts(gain)}`;
    return `<div class="qz-done"><div class="qz-done-t">${title}</div>
      ${m.last && !m.last.ok ? `<div class="artist">${esc(m.last.text)}<br>Il fallait répondre : <b>${esc(m.last.answer)}</b></div>` : ""}
      <div class="py-wait">En attente des autres joueurs…</div></div>` + qzMiniBoard(v.board, "ladder", 10);
  }
  if (m.between_in !== undefined && m.q) {
    const won = v.ladder[m.level - 1];
    return `<div class="qz-verdict ok">✓ Bonne réponse ! <b>${fmtPts(won)}</b></div>`
      + `<div class="qz-ladwrap"><div class="qz-ladmain">${qzQuestionHtml(m.q, { mine: m.last?.c, correct: m.last?.ans })}
        <div class="qz-next">${m.paused ? `<span class="qz-paused">⏸ En pause</span>` : `<span>Palier suivant dans <b id="qzBetweenS">${Math.ceil(m.between_in)}</b> s</span>`}
          <span class="qz-next-btns">${qzPauseBtn(m.paused)}</span></div>
        <div class="qz-jokers"><button type="button" class="qz-joker stop" data-qz-stop>🛑 Garder ${fmtPts(won)}</button></div></div>${ladder}</div>`;
  }
  const cur = v.ladder[m.i], safe = m.level ? v.ladder[Math.max(...v.safe.filter((x) => x < m.level), -1)] || 0 : 0;
  const jok = `<div class="qz-jokers">
      <button type="button" class="qz-joker" data-qz-joker="5050" ${m.jokers.includes("5050") ? "" : "disabled"}>50 / 50</button>
      <button type="button" class="qz-joker" data-qz-joker="swap" ${m.jokers.includes("swap") ? "" : "disabled"}>🔄 Changer</button>
      ${m.level ? `<button type="button" class="qz-joker stop" data-qz-stop>🛑 Garder ${fmtPts(v.ladder[m.level - 1])}</button>` : ""}</div>`;
  return `<div class="qz-top"><span class="qz-num">Palier <b>${m.i + 1}/15</b></span><span class="qz-mypts">pour <b>${fmtPts(cur)}</b></span>
      <span class="qz-mypts">assuré : ${fmtPts(safe)}</span></div>`
    + qzTimerHtml(m.q.left, m.q.dur) + `<div class="qz-ladwrap"><div class="qz-ladmain">${qzQuestionHtml(m.q, { cut: m.q.cut })}${jok}</div>${ladder}</div>`;
}

function qzEndHtml(g) {
  const v = g.quiz, s = v.settings, b = v.board;
  const val = (r) => s.mode === "ladder" ? fmtPts(v.ladder?.[(r.level || 0) - 1] || 0) : `${fmtPts(r.pts)} pts`;
  const podium = b.length > 1 ? `<div class="qz-podium">${[1, 0, 2].filter((i) => b[i]).map((i) => `<div class="qz-pod p${i + 1}">
      <div class="qz-pod-name">${esc(b[i].name)}</div><div class="qz-pod-pts">${val(b[i])}</div>
      <div class="qz-pod-step"><span>${["🥇", "🥈", "🥉"][i]}</span></div></div>`).join("")}</div>` : "";
  const mine = b.find((r) => r.me);
  const solo = b.length === 1 && mine ? `<div class="qz-solo"><div class="qz-solo-k">Ton score</div><div class="qz-solo-v">${val(mine)}</div>
      <div class="artist">${mine.ok}/${mine.n} bonnes réponses${mine.best > 1 ? ` · meilleure série 🔥${mine.best}` : ""}</div></div>` : "";
  const rows = b.map((r, i) => `<div class="qz-mini-row ${r.me ? "me" : ""}"><span class="qz-rank r${i + 1}">${i + 1}</span><b>${esc(r.name)}</b>
      <small>${r.ok}/${r.n} ✓${r.best > 1 ? ` · 🔥${r.best}` : ""}</small><span class="qz-p">${val(r)}</span></div>`).join("");
  return `<div class="qz-end-t">🏁 Fin du quiz</div>${podium}${solo}
    ${b.length > 1 ? `<div class="qz-mini">${rows}</div>` : ""}
    ${g.is_host ? `<button class="py-main" data-gact="restart">🔁 Rejouer avec les mêmes réglages</button>
      <details class="qz-more"><summary>⚙️ Changer les réglages</summary>${qzSettingsHtml({ ...g, quiz: { ...v, catalog: v.catalog || qzCatalog } })}</details>` : ""}
    ${qzLeaderboardHtml(v.leaderboard)}`;
}
let qzCatalog = null;

// Après le rendu : chronomètres, rafraîchissement à la fin du temps, annonces plein écran.
function quizAfter(g, fresh = true) {
  const v = g.quiz;
  if (v.catalog) qzCatalog = v.catalog;
  clearInterval(qzTimer);
  const t0 = Date.now();
  const bars = [];
  if (g.phase === "q" && v.q) bars.push(["qzBar", v.q.left, v.q.dur]);
  if (g.phase === "run" && v.me?.q && v.settings.mode === "ladder") bars.push(["qzBar", v.me.q.left, v.me.q.dur]);
  if (g.phase === "run" && v.settings.mode === "chrono") bars.push(["qzChronoBar", v.deadline_in || 0, v.settings.chrono]);
  // La barre se vide en continu (transition CSS), le nombre se met à jour chaque seconde.
  if (fresh) requestAnimationFrame(() => bars.forEach(([id, left]) => {
    const el = $(id);
    if (el) { el.style.transitionDuration = left + "s"; el.style.width = "0%"; }
  }));
  let wake = Infinity;
  bars.forEach(([, left]) => { wake = Math.min(wake, left); });
  if (g.phase === "rev" && v.q && !v.paused) wake = Math.min(wake, v.q.next_in);
  const between = v.me?.between_in !== undefined && !v.me?.paused ? v.me.between_in : null;
  if (between !== null) { bars.length = 0; wake = between; }
  qzTimer = setInterval(() => {
    const dt = (Date.now() - t0) / 1000;
    bars.forEach(([id, left]) => { const s = $(id + "S"); if (s) s.textContent = Math.max(0, Math.ceil(left - dt)); });
    const cs = $("qzChronoS");
    if (cs) cs.textContent = Math.max(0, Math.ceil((v.deadline_in || 0) - dt));
    const bs = $("qzBetweenS");
    if (bs && between !== null) bs.textContent = Math.max(0, Math.ceil(between - dt));
    const ns = $("qzNextS");
    if (ns && v.q) ns.textContent = Math.max(0, Math.ceil(v.q.next_in - dt));
    const urgent = bars.some(([, left]) => left - dt < 5 && left - dt > 0);
    document.querySelector(".qz-timer")?.classList.toggle("urgent", urgent);
    // Temps écoulé : on demande au serveur la suite (une fois).
    if (dt >= wake + 0.25 && Date.now() - qzRefreshAt > 1500) { qzRefreshAt = Date.now(); refreshGame(); }
  }, 250);
  // Annonces : bonne / mauvaise réponse, gagnant de la partie.
  const key = `${g.id}|${g.phase}|${v.n}`;
  if (qzSeen.key && qzSeen.key !== key) {
    if (g.phase === "rev" && v.q && g.me) {
      const mine = v.q.res.find((r) => r.me);
      navigator.vibrate?.(mine?.ok ? [40, 30, 40] : [200]);
    }
    if (g.phase === "end" && v.board.length) {
      const w = v.board[0];
      if (v.board.length > 1) pyrFlash("summit", `🏆 ${esc(w.name)} gagne !`, `${fmtPts(w.pts)} points`, "", 3500);
      else pyrFlash("good", "🏁 Terminé !", `${w.ok}/${w.n} bonnes réponses · ${fmtPts(w.pts)} points`, "", 3000);
    }
    if (g.phase === "rev" && v.settings.mode === "speed" && v.q?.winner) pyrFlash("good", `⚡ ${esc(v.q.winner)}`, "a trouvé en premier !", "", 1600);
  }
  qzSeen.key = key;
}

// Réponse : envoyée dès que le doigt touche le bouton (sans attendre qu'il se relève), une seule fois,
// avec le jeton de la question : une réponse en retard ne compte jamais pour la question suivante.
function qzAnswer(a) {
  if (!a || a.disabled || !game?.quiz) return;
  a.classList.add("picked");
  document.querySelectorAll("[data-qz-ans]").forEach((b) => { b.disabled = true; if (b !== a) b.classList.add("dim"); });
  navigator.vibrate?.(30);
  gameAction("qans", { amount: +a.dataset.qzAns, guess: game.quiz.token }, { quiet: true });
}
document.addEventListener("pointerdown", (ev) => {
  if (ev.button !== 0) return;
  const a = ev.target.closest("[data-qz-ans]");
  if (a) { ev.preventDefault(); qzAnswer(a); }
});
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("[data-qz-ans]");
  if (a) return qzAnswer(a);  // clavier (ou navigateur sans pointerdown)
  const j = ev.target.closest("[data-qz-joker]");
  if (j && !j.disabled) return pressed(j, gameAction("qjoker", { guess: j.dataset.qzJoker }));
  const st = ev.target.closest("[data-qz-stop]");
  if (st) return pressed(st, gameAction("qstop"));
  const pa = ev.target.closest("[data-qz-pause]");
  if (pa) return pressed(pa, gameAction("qpause"));
  const set = ev.target.closest("[data-qz-set]");
  if (set && !set.disabled) {
    // Effet immédiat à l'écran, confirmé par le serveur juste après.
    set.parentElement.querySelectorAll("[data-qz-set]").forEach((x) => x.classList.toggle("on", x === set));
    const raw = set.dataset.val;
    return gameAction("qset", { settings: { [set.dataset.qzSet]: /^\d+$/.test(raw) && set.dataset.qzSet !== "diff" ? +raw : raw } });
  }
  const th = ev.target.closest("[data-qz-theme]");
  if (th && !th.disabled && game?.quiz) {
    const id = th.dataset.qzTheme;
    let cur = [...game.quiz.settings.themes];
    cur = !id ? [] : cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
    th.classList.toggle("on");
    if (!id) document.querySelectorAll("[data-qz-theme]").forEach((x) => x.classList.toggle("on", !x.dataset.qzTheme));
    return gameAction("qset", { settings: { themes: cur } });
  }
});
