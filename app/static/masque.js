// 🎭 Le Masque : tout le monde répond en secret à la même question, les réponses s'affichent sans prénom, chacun devine
// qui a écrit quoi. L'organisateur choisit avant la partie, pour toute la table : masques levés (les auteurs et qui a
// voté quoi se dévoilent) ou masques gardés (personne ne saura qui a écrit quoi).
// Chargé après games.js (utilise gameAction, pressed, esc, toast, haptic, GameFx…).
GAME_THEME.masque = "g-ms";
GAME_RULES.masque = `
  <h3>Le principe</h3>
  <p>Une question profonde s'affiche. Chacun écrit <b>en secret</b> sa réponse sur son téléphone, en une phrase. Sois sincère : c'est tout le jeu.</p>
  <h3>Qui a écrit quoi ?</h3>
  <p>Quand tout le monde a écrit, les réponses des autres apparaissent <b>mélangées, sans prénom</b> (la tienne n'est pas dans ta liste : ton voisin ne peut pas la repérer). Touche un prénom sous chaque réponse pour deviner son auteur. Tu peux en laisser sans réponse.</p>
  <h3>Masques levés ou gardés</h3>
  <p>L'organisateur choisit avant la partie, pour toute la table. <b>🙋 Masques levés</b> : à la révélation, on voit qui a écrit chaque réponse et qui a voté pour qui, en vert si c'était juste, en rouge sinon. <b>🎭 Masques gardés</b> : l'app ne dira jamais qui a écrit quoi ; on voit seulement à qui le groupe a pensé.</p>
  <h3>Les points</h3>
  <p>Masques levés : 1 point par auteur trouvé. Une réponse drôle ne rapporte rien : on joue la sincérité. Masques gardés : pas de points, on parle.</p>
  <h3>Bienveillance</h3>
  <p>L'animateur peut retirer une réponse déplacée : elle sort du jeu sans que personne sache qui l'a écrite.</p>
  <h3>Les questions</h3>
  <p>Six catégories (souvenirs, toi en vrai, liens, valeurs, rêves et peurs, et si…) et trois niveaux : 🌤 léger, 🌊 profond et 🕯 intime, à cocher par l'animateur.</p>`;


let msDraft = "";      // réponse en cours d'écriture (gardée si la feuille se ferme)
let msPicks = {};      // devinettes en cours : numéro de réponse → pid
let msRoundKey = "";   // tout repart de zéro à chaque question

const msKey = (g, part) => `ms:${g.id}:${g.round}:${part}`;

function msSyncRound(g) {
  const key = `${g.id}:${g.round}`;
  if (key === msRoundKey) return;
  msRoundKey = key; msPicks = {}; msDraft = "";
  try {  // page rechargée en pleine devinette : les prénoms déjà choisis reviennent
    const saved = JSON.parse(sessionStorage.getItem("vp_masque") || "null");
    if (saved?.key === key) msPicks = saved.picks || {};
  } catch { /* stockage indisponible : on repart de zéro */ }
}

function msSave() {
  try { sessionStorage.setItem("vp_masque", JSON.stringify({ key: msRoundKey, picks: msPicks })); } catch { /* rien */ }
}

function msHero(sub) {
  return `<div class="lk-hero ms-hero"><div class="lk-hero-i">🎭</div><div><div class="lk-hero-t">Le Masque</div>
    <div class="lk-hero-s">${sub}</div></div></div>`;
}

function msQuestion(g, small = false) {
  const v = g.masque, q = v.q || {};
  return `<div class="ms-q ${small ? "small" : ""}"${small ? "" : GameFx.fx("flip", msKey(g, "q"))}>
    <div class="ms-q-n">Question ${v.n}/${v.count} · ${esc(q.cat_label || "")} · ${esc(q.level_label || "")}</div>
    <div class="ms-q-t">${esc(q.text || "")}</div></div>`;
}

function msChip(on, attr, label) {
  return `<button type="button" class="${on ? "on" : ""}" ${attr} aria-pressed="${on}">${label}</button>`;
}

function msSettingsHtml(g) {
  const v = g.masque;
  const cats = v.cat_list.map((c) => msChip(v.cats.includes(c.id), `data-ms-cat="${c.id}"`, `${esc(c.label)} <small>${c.size}</small>`)).join("");
  const levels = v.level_list.map((l) => msChip(v.levels.includes(l.id), `data-ms-level="${l.id}"`, esc(l.label))).join("");
  const counts = v.counts.map((n) => msChip(v.count === n, `data-ms-count="${n}"`, String(n))).join("");
  const masks = v.mask_list.map((m) => msChip(v.mask === m.id, `data-ms-mask="${m.id}"`, esc(m.label))).join("");
  return `<div class="lk-setup ms-setup">
    <div class="g-label">Les masques, pour toute la table</div><div class="lk-chips">${masks}</div>
    <p class="artist ms-mask-help">${msMaskHelp(v)}</p>
    <div class="g-label">Catégories</div><div class="lk-chips">${cats}</div>
    <div class="g-label">Profondeur</div><div class="lk-chips">${levels}</div>
    <div class="g-label">Nombre de questions</div><div class="lk-chips">${counts}</div>
  </div>`;
}

const msOpen = (v) => v.mask !== "closed";

function msMaskHelp(v) {
  return msOpen(v)
    ? "À la révélation : qui a écrit chaque réponse, et qui a voté pour qui."
    : "Personne ne saura jamais qui a écrit quoi : on voit seulement à qui on a pensé.";
}

function msLobbyHtml(g) {
  const v = g.masque, n = g.players.length;
  if (!g.is_host) {
    return `${msHero("Réponds en secret, devine qui a écrit quoi.")}<div class="lk-card"><div class="title">${g.me ? "Tu es inscrit ✓" : `Partie de ${esc(g.host_name || "quelqu'un")}`}</div>
      <p class="artist">${esc(g.host_name || "L'animateur")} va poser la première question : tu répondras en secret sur ton téléphone.</p>
      <div class="ms-mode">${esc(v.mask_list.find((m) => m.id === v.mask)?.label || "")}<span>${msMaskHelp(v)}</span></div>
      ${g.me ? "" : `<button class="lk-main" data-gact="join">Je joue aussi</button>`}</div>`;
  }
  return `${msHero("Réponds en secret, devine qui a écrit quoi.")}${msSettingsHtml(g)}
    <p class="artist lk-help">${n < v.min_players ? `Il faut au moins ${v.min_players} joueurs, chacun avec son téléphone (QR code ci-dessus).` : `${n} joueurs : chacun écrit et devine sur son téléphone.`}</p>
    <button class="lk-main" data-gact="start" ${n < v.min_players ? "disabled" : ""}>▶︎ Première question</button>`;
}

function msPeople(list, key) {
  return `<div class="ps-people">${list.map((p) => `<span class="ps-who ${p.done ? "on" : ""}"${p.done ? GameFx.fx("pop", `${key}:${p.pid}`) : ""}>${p.done ? "✓" : "…"} ${esc(p.name)}</span>`).join("")}</div>`;
}

function msWriteHtml(g) {
  const v = g.masque, done = v.wrote.filter((w) => w.done).length;
  const mine = !g.me ? "" : v.mine
    ? `<div class="lk-card ms-mine"${GameFx.fx("pop", msKey(g, "sent"))}><div class="artist">🤫 Ta réponse, envoyée en secret</div>
        <details class="ms-mine-t"><summary>👁 Revoir ma réponse</summary>« ${esc(v.mine)} »</details><button type="button" class="lk-sub" data-ms-compose>✏️ Modifier</button></div>`
    : `<button type="button" class="lk-main" data-ms-compose>✍️ Écrire ma réponse</button>`;
  const host = g.is_host ? `<div class="lk-row">
      ${!done ? `<button class="lk-sub" data-gact="msswap">🔀 Autre question</button>` : ""}
      ${v.can_show && done < v.wrote.length ? `<button class="lk-sub" data-gact="msshow">⏩ Montrer les ${done} réponses</button>` : ""}</div>` : "";
  return `${msQuestion(g)}${mine}<div class="lk-card"><div class="title">${done}/${v.wrote.length} ont écrit</div>${msPeople(v.wrote, msKey(g, "w"))}</div>${host}`;
}

function msKill(g, s) {
  return g.is_host ? `<button type="button" class="ms-kill" data-ms-hide="${s.i}" aria-label="Retirer cette réponse">🚫</button>` : "";
}

function msSlotsReadonly(g) {
  return `<div class="ms-slots">${g.masque.slots.map((s) => s.hidden ? "" : `<div class="ms-slot">${msKill(g, s)}
      <div class="ms-slot-t">« ${esc(s.text)} »</div></div>`).join("")}</div>`;
}

function msGuessHtml(g) {
  const v = g.masque;
  if (v.sent || !g.me) {
    const done = v.progress.filter((p) => p.done).length;
    const host = g.is_host ? `<button class="lk-main" data-gact="msreveal" ${v.can_reveal ? "" : "disabled"}>👁 Révéler${done < v.progress.length ? ` (${done}/${v.progress.length})` : ""}</button>
      ${v.can_reveal ? "" : `<p class="artist ms-help">Possible dès qu'un joueur a envoyé ses choix.</p>`}` : "";
    return `${msQuestion(g, true)}<div class="lk-card lk-done"${GameFx.fx("pop", msKey(g, "guessed"))}><div class="lk-name">${v.sent ? "🤫 Choix envoyés" : "👀 Ils devinent…"}</div>
      <div class="artist">Révélation quand tout le monde a choisi.</div>${msPeople(v.progress, msKey(g, "g"))}</div>${msSlotsReadonly(g)}${host}`;
  }
  const used = new Set(Object.values(msPicks));
  const slots = v.slots.map((s) => {
    if (s.hidden) return `<div class="ms-slot off"><div class="ms-slot-t">🚫 Réponse retirée par l'animateur</div></div>`;
    const names = v.authors.map((a) => {
      const on = msPicks[s.i] === a.pid;
      return `<button type="button" class="ms-name ${on ? "on" : used.has(a.pid) ? "used" : ""}" data-ms-slot="${s.i}" data-ms-pid="${esc(a.pid)}" aria-pressed="${on}" aria-label="${esc(a.name)} a écrit « ${esc(s.text)} »${used.has(a.pid) && !on ? " (déjà choisi pour une autre réponse)" : ""}">${esc(a.name)}</button>`;
    }).join("");
    return `<div class="ms-slot ${msPicks[s.i] ? "picked" : ""}"${GameFx.fx("rise", msKey(g, `slot${s.i}`), 80 * s.i)}>${msKill(g, s)}<div class="ms-slot-t">« ${esc(s.text)} »</div><div class="ms-names">${names}</div></div>`;
  }).join("");
  const picked = Object.keys(msPicks).length;
  const late = v.late ? `<p class="artist ms-help">Tu es arrivé pendant cette question : devine si tu veux, la révélation ne t'attend pas.</p>` : "";
  return `${msQuestion(g, true)}${late}<p class="artist ms-help">Touche le prénom de l'auteur sous chaque réponse. Un prénom ne va qu'avec une réponse.</p>
    <div class="ms-slots">${slots}</div>
    <button class="lk-main" data-ms-send>📨 Envoyer mes choix${picked ? ` (${picked} deviné${picked > 1 ? "s" : ""})` : ""}</button>
    <p class="artist ms-help">${msOpen(v) ? "🙋 Masques levés : les auteurs se dévoilent à la révélation." : "🎭 Masques gardés : personne ne saura qui a écrit quoi."}</p>
    ${g.is_host && v.can_reveal ? `<button class="lk-sub" data-gact="msreveal" style="width:100%;margin-top:8px">👁 Révéler sans attendre</button>` : ""}`;
}

// Qui a voté pour qui. Masques levés : chaque votant, en vert s'il a vu juste, en rouge sinon (« pensait Bob »).
// Masques gardés : seulement à qui on a pensé, en nombre (le prénom des votants trahirait l'auteur, seul absent).
function msVotes(r) {
  const votes = r.votes || [];
  if (!votes.length) return `<div class="ms-votes none">Personne n'a voté pour cette réponse</div>`;
  if (!r.open) {
    return `<div class="ms-votes"><span class="ms-votes-k">On a pensé à</span>${votes.map((x) =>
      `<span class="ms-vote">${esc(x.guess)}${x.n > 1 ? ` <b>×${x.n}</b>` : ""}</span>`).join("")}</div>`;
  }
  return `<div class="ms-votes">${votes.map((x) => x.right
    ? `<span class="ms-vote right" title="${esc(x.voter)} a trouvé">✓ ${esc(x.voter)}</span>`
    : `<span class="ms-vote wrong" title="${esc(x.voter)} s'est trompé">✗ ${esc(x.voter)} <small>pensait ${esc(x.guess)}</small></span>`).join("")}</div>`;
}

function msRevealHtml(g) {
  const v = g.masque, open = msOpen(v);
  const rows = v.result.map((r, i) => {
    if (r.hidden) return `<div class="ms-slot off"><div class="ms-slot-t">🚫 Réponse retirée</div></div>`;
    const mark = (v.my_marks || [])[i];  // ma devinette sur cette réponse : juste, fausse, ou aucune
    const badge = mark === "right" ? `<span class="ms-mark right" role="img" aria-label="Tu as trouvé">✓</span>`
      : mark === "wrong" ? `<span class="ms-mark wrong" role="img" aria-label="Tu t'es trompé">✗</span>` : "";
    const who = r.open
      ? `<div class="ms-author"${GameFx.fx("pop", msKey(g, `who${i}`), 400 + 260 * i)}>C'était <b>${esc(r.author)}</b></div>`
      : `<div class="ms-author masked"${GameFx.fx("pop", msKey(g, `who${i}`), 400 + 260 * i)}>🎭 Masque gardé</div>`;
    return `<div class="ms-slot ms-res ${mark || ""} ${r.open ? "" : "masked"}"${GameFx.fx("rise", msKey(g, `rev${i}`), 120 * i)}>${badge}
      ${who}<div class="ms-slot-t">« ${esc(r.text)} »</div>${msVotes(r)}</div>`;
  }).join("");
  const last = v.n >= v.count;
  const scores = [...v.scores].sort((a, b) => b.score - a.score).map((s) => `<span class="ps-who ${s.score ? "on" : ""}">${esc(s.name)} · ${s.score}</span>`).join("");
  return `${msQuestion(g, true)}<div class="ms-slots">${rows}</div>
    <p class="db-talk">${open ? "💬 Chacun raconte l'histoire derrière sa réponse." : "💬 Qui veut raconte… sans jamais rien avouer."}</p>
    ${open ? `<div class="lk-card"><div class="title">Points</div><div class="ps-people">${scores}</div></div>` : ""}
    ${g.is_host ? `<button class="lk-main" data-gact="next">${last ? "📊 Voir le bilan" : "▶︎ Question suivante"}</button>` : ""}`;
}

// Classement de fin (Masque et Reflet) : à score égal, même rang et même médaille.
function rankingHtml(rows) {
  return rows.map((r, i) => {
    const rank = rows.findIndex((x) => x.score === r.score);
    return `<div class="track"><div class="meta"><div class="title">${["🥇", "🥈", "🥉"][rank] || `${rank + 1}.`} ${esc(r.name)}</div></div><b>${r.score} pt${r.score > 1 ? "s" : ""}</b></div>`;
  }).join("");
}

function msAward(icon, title, names, detail, key) {
  if (!names?.length) return "";
  return `<div class="db-award"${GameFx.fx("rise", key)}><div class="db-award-k">${icon} ${title}</div><div class="db-award-t">${names.map(esc).join(", ")}</div><div class="artist">${detail}</div></div>`;
}

function msEndHtml(g) {
  const v = g.masque, s = v.summary || {};
  const ranking = rankingHtml(s.ranking || []);
  const recap = (v.history || []).map((h) => `<li>${esc(h.q)}<ul>${h.rows.filter((r) => !r.hidden).map((r) => `<li>« ${esc(r.text)} » <span>${r.open ? `— ${esc(r.author)}` : "— 🎭"}</span></li>`).join("")}</ul></li>`).join("");
  return `<div class="lk-end-k">Bilan · ${s.questions || 0} question${s.questions > 1 ? "s" : ""}</div>
    ${msAward("🔎", "Le plus perspicace", s.sharp, "A trouvé le plus d'auteurs", `ms:${g.id}:end:sharp`)}
    ${msAward("🎭", "Le plus mystérieux", s.mystery, "Le moins deviné de la table", `ms:${g.id}:end:mys`)}
    ${msOpen(v) ? `<div class="list">${ranking}</div>` : `<p class="artist ms-help">🎭 Masques gardés : aucun auteur dévoilé, aucun point.</p>`}
    <details class="lk-recap"><summary>Revoir les réponses</summary><ol>${recap}</ol></details>
    ${g.is_host ? `${msSettingsHtml(g)}<button class="lk-main" data-gact="restart">🔁 Rejouer avec les mêmes joueurs</button>` : ""}`;
}

function masqueHtml(g) {
  if (!g.masque) return "";
  msSyncRound(g);
  if (g.phase !== "write") msCloseSheet();  // les réponses sont apparues : la feuille d'écriture n'a plus lieu d'être
  if (g.phase === "guess" && g.masque.slots) {  // choix devenus impossibles (réponse retirée, prénom disparu) : oubliés
    const ok = new Set(g.masque.slots.filter((s) => !s.hidden).map((s) => String(s.i)));
    const names = new Set((g.masque.authors || []).map((a) => a.pid));
    msPicks = Object.fromEntries(Object.entries(msPicks).filter(([s, p]) => ok.has(s) && names.has(p)));
  }
  if (g.phase === "write") return msWriteHtml(g);
  if (g.phase === "guess") return msGuessHtml(g);
  if (g.phase === "reveal" && g.masque.result) return msRevealHtml(g);
  if (g.phase === "end") return msEndHtml(g);
  return msLobbyHtml(g);
}

// Feuille « Écrire ma réponse » : hors de #game, pour que les rafraîchissements n'effacent pas ce qu'on écrit.
function msCloseSheet() {
  document.querySelector(".ms-sheet-modal")?.remove();
}

function msOpenSheet() {
  const v = game?.masque;
  if (!v || game.phase !== "write") return;
  msCloseSheet();
  const wrap = document.createElement("div");
  wrap.className = "g-modal ms-sheet-modal";
  Object.assign(wrap.dataset, { nav: "sheet", navSurface: ".ms-sheet", navClose: "self" });
  wrap.innerHTML = `<form class="g-sheet ms-sheet g-ms" role="dialog" aria-modal="true" aria-labelledby="msSheetTitle">
      <div class="g-sheet-grab" aria-hidden="true"></div>
      <h2 id="msSheetTitle">✍️ Ta réponse</h2>
      <p class="ms-sheet-q">${esc(v.q?.text || "")}</p>
      <textarea name="text" rows="3" maxlength="${v.max_answer}" required placeholder="En une phrase, sincèrement…" aria-label="Ta réponse"></textarea>
      <div class="ms-count" aria-live="polite"></div>
      <p class="artist">${msOpen(v) ? "Personne ne le saura avant la révélation : les masques tombent à la fin de la question." : "Masques gardés : personne ne saura jamais que c'est toi."}</p>
      <div class="db-sheet-row"><button type="button" class="lk-sub" data-ms-cancel>Annuler</button><button type="submit" class="lk-main">Envoyer en secret</button></div>
    </form>`;
  const area = wrap.querySelector("textarea"), count = wrap.querySelector(".ms-count");
  const left = () => { count.textContent = `${area.value.length}/${v.max_answer}`; };
  area.value = msDraft || v.mine || "";
  left();
  area.addEventListener("input", () => { msDraft = area.value; left(); });
  wrap.addEventListener("click", (ev) => { if (ev.target === wrap || ev.target.closest("[data-ms-cancel]")) msCloseSheet(); });
  wrap.querySelector("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = area.value.trim();
    if (text.length < 2) return toast("Écris au moins quelques mots", "err");
    const ok = await pressed(ev.submitter, gameAction("mswrite", { guess: text }));
    if (ok) { msDraft = ""; msCloseSheet(); haptic(30); }
  });
  document.body.append(wrap);
  area.focus();
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "masque") return;
  const v = game.masque;
  if (ev.target.closest("[data-ms-compose]")) return msOpenSheet();
  const name = ev.target.closest("[data-ms-pid]");
  if (name) {
    const slot = name.dataset.msSlot, pid = name.dataset.msPid;
    // Un prénom ne va qu'avec une réponse : le choisir ailleurs le retire de l'ancienne ; le retoucher l'enlève.
    const next = Object.fromEntries(Object.entries(msPicks).filter(([s, p]) => p !== pid && s !== slot));
    if (msPicks[slot] !== pid) next[slot] = pid;
    msPicks = next;
    msSave();
    haptic(12);
    return renderGame(game);
  }
  const send = ev.target.closest("[data-ms-send]");
  if (send) return pressed(send, gameAction("msguess", { settings: { picks: msPicks } }));
  const hide = ev.target.closest("[data-ms-hide]");
  if (hide) {
    if (!confirm("Retirer cette réponse ? Elle sort du jeu, sans que personne sache qui l'a écrite.")) return;
    return pressed(hide, gameAction("mshide", { amount: +hide.dataset.msHide }));
  }
  const cat = ev.target.closest("[data-ms-cat]");
  if (cat) {
    const id = cat.dataset.msCat, cats = v.cats.includes(id) ? v.cats.filter((c) => c !== id) : [...v.cats, id];
    if (!cats.length) return toast("Garde au moins une catégorie", "err");
    return pressed(cat, gameAction("msset", { settings: { cats } }));
  }
  const level = ev.target.closest("[data-ms-level]");
  if (level) {
    const id = level.dataset.msLevel, levels = v.levels.includes(id) ? v.levels.filter((l) => l !== id) : [...v.levels, id];
    if (!levels.length) return toast("Garde au moins un niveau", "err");
    return pressed(level, gameAction("msset", { settings: { levels } }));
  }
  const mask = ev.target.closest("[data-ms-mask]");
  if (mask) return pressed(mask, gameAction("msset", { settings: { mask: mask.dataset.msMask } }));
  const count = ev.target.closest("[data-ms-count]");
  if (count) return pressed(count, gameAction("msset", { settings: { count: +count.dataset.msCount } }));
});
