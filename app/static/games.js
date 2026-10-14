// 🎮 Jeux, partagés par la page invités et l'admin.
// Utilise les globales de la page : $, esc, store, toast, guestId, guestName (chargé après le script de la page).
document.getElementById("gamesRoot").innerHTML = `
    <div id="gName" class="hidden">
      <p class="sub">Comment tu t'appelles ?</p>
      <form id="gNameForm" class="row">
        <input id="gNameInput" class="grow" type="text" maxlength="30" placeholder="Ton prénom" autocomplete="given-name" required>
        <button>OK</button>
      </form>
    </div>

    <div id="gHome" class="hidden">
      <p class="sub">Salut <b id="gHello"></b> ! Crée une partie et fais scanner son QR, ou rejoins celle d'un ami.</p>
      <div class="card" style="margin-bottom:10px">
        <div class="title" style="font-weight:700">🕵️ Undercover</div>
        <p class="sub" style="margin:6px 0 10px">Chacun reçoit un mot secret ; les undercovers ont un mot proche, Mr. White n'en a pas. Indices à voix haute, puis vote. 3 joueurs minimum.</p>
        <label class="switch-row" style="margin-bottom:8px"><span class="grow">🎩 Avec Mr. White (dès 5 joueurs)</span><input type="checkbox" class="switch" data-opt="white" checked></label>
        <label class="switch-row" style="margin-bottom:10px"><span class="grow">🙋 Je joue aussi<span class="artist" style="display:block">Sinon tu es maître du jeu : tu vois les rôles</span></span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button data-create="undercover" style="width:100%">Créer la partie</button>
      </div>
      <div class="card" style="margin-bottom:10px">
        <div class="title" style="font-weight:700">🙋 Qui de nous ?</div>
        <p class="sub" style="margin:6px 0 10px">Une question (« Qui de nous finira la soirée en pyjama ? »), tout le monde vote en secret, puis on découvre le classement. 2 joueurs minimum.</p>
        <label class="switch-row" style="margin-bottom:10px"><span class="grow">🙋 Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button data-create="whoof" style="width:100%">Créer la partie</button>
      </div>
      <h2>Rejoindre une partie</h2>
      <form id="gJoinForm" class="row">
        <input id="gCode" class="grow pin-input" type="text" maxlength="4" placeholder="CODE" autocapitalize="characters" autocomplete="off">
        <button>Rejoindre</button>
      </form>
    </div>

    <div id="gamePlay" class="hidden">
      <div id="game" class="card game"></div>
      <div id="gameHost"></div>
      <div class="card" style="text-align:center;margin-top:20px">
        <div class="artist">Pour rejoindre : scanne ce QR ou entre le code</div>
        <div class="big-pin" id="gameCode"></div>
        <img class="qr" id="gameQr" alt="QR code pour rejoindre la partie">
      </div>
      <button class="danger" id="gameLeave" style="width:100%;margin-top:16px">Quitter la partie</button>
    </div>
`;

// 🎮 Jeux : n'importe qui crée une partie (code + QR) et l'anime ; les autres la rejoignent avec son code.
let myGame = store("vp_game") || "", game = null, wordShown = "", guessDraft = "", showRoles = false, autoJoin = false;
const GAME_PHASES = { lobby: "Inscriptions", words: "Indices", vote: "Vote", white_guess: "Devinette de Mr. White",
  reveal: "Résultat de la manche", end: "Partie terminée", question: "Question", results: "Résultats" };
const WINNERS = { civils: "Les civils ont gagné 🎉", impostors: "Les undercovers ont gagné 🕵️", white: "Mr. White a trouvé le mot et gagne 🎩" };

async function gapi(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json().catch(() => null);
  if (!r.ok) { const e = new Error(data?.detail || "Erreur"); e.status = r.status; throw e; }
  return data;
}
function setGame(code) { myGame = code; store("vp_game", code); $("gameDot")?.classList.toggle("hidden", !code); }

async function refreshGame() {
  $("gName").classList.toggle("hidden", !!guestName);
  if (!guestName) { $("gHome").classList.add("hidden"); $("gamePlay").classList.add("hidden"); return; }
  $("gHello").textContent = guestName;
  if (!myGame) return renderGame(null);
  try {
    const g = await gapi(`/api/games/${myGame}?guest_id=${encodeURIComponent(guestId)}`);
    if (autoJoin && !g.me && !g.is_host) { autoJoin = false; return gameAction("join"); }
    renderGame(g);
  } catch (e) {
    if (e.status === 404) { setGame(""); renderGame(null); toast("Cette partie n'existe plus", "err"); }
  }
}

function renderGame(g) {
  game = g;
  $("gHome").classList.toggle("hidden", !!g);
  $("gamePlay").classList.toggle("hidden", !g);
  if (!g) return;
  const me = g.me;
  const nameOf = (pid) => esc(g.players.find((p) => p.pid === pid)?.name || "?");
  const title = `<div class="artist">🎮 ${esc(g.name)} · ${GAME_PHASES[g.phase]}${g.round && g.phase !== "lobby" ? ` · ${g.type === "whoof" ? "question" : "manche"} ${g.round}` : ""}</div>`;
  const lastLine = g.last?.name ? `<p class="sub" style="margin:8px 0">${esc(g.last.name)} était <b>${esc(g.last.role)}</b>.${g.last.guess ? ` Mr. White a proposé « ${esc(g.last.guess)} »… raté !` : ""}</p>` : "";
  let body = "";

  if (!me && !g.master) {
    // Visiteur : pas encore dans la partie.
    const canJoin = g.phase === "lobby" || g.phase === "end" || g.type === "whoof";
    body = canJoin
      ? `<div class="title">Partie de ${esc(g.host_name || "quelqu'un")}</div><div class="artist">${g.players.length} joueur${g.players.length > 1 ? "s" : ""}</div>
         <button data-gact="join" style="width:100%;margin-top:10px">Rejoindre la partie</button>`
      : `<div class="title">Partie déjà commencée</div><div class="artist">Tu pourras rejoindre la prochaine manche.</div>`;
  } else if (g.master && g.phase !== "end") {
    body = `<div class="title">Tu es maître du jeu 🎲</div><div class="artist">Tu ne joues pas : tu fais avancer la partie${g.type === "undercover" ? " et tu peux voir les rôles (👁)" : ""}.</div>
      ${g.question ? `<div class="question" style="margin-top:10px">${esc(g.question)}</div>` : ""}${lastLine}
      ${g.phase === "words" && g.order.length ? `<p class="sub" style="margin:8px 0 0">Ordre de parole : ${g.order.map(esc).join(" → ")}</p>` : ""}
      ${showRoles && g.words ? `<p class="sub" style="margin:8px 0 0">Civils : <b>${esc(g.words.civil)}</b> · Undercover : <b>${esc(g.words.undercover)}</b></p>` : ""}
      ${resultsHtml(g)}`;
  } else if (g.phase === "lobby") {
    body = `<div class="title">Tu es inscrit ✓</div><div class="artist">${g.is_host ? "Lance la partie quand tout le monde est là." : `En attente que ${esc(g.host_name)} lance la partie…`}</div>`;
  } else if (g.type === "undercover") {
    const key = g.id + ":" + g.round;
    const secret = me?.role ? `<div class="word">🎩 Tu es Mr. White</div><div class="artist">Tu n'as pas de mot : écoute les autres et bluffe !</div>`
      : `<div class="artist">Ton mot</div><div class="word">${esc(me?.word)}</div>`;
    const wordBox = !me?.dealt ? "" : wordShown === key
      ? `<div data-gact="hide" class="secret">${secret}<div class="artist" style="margin-top:4px">Touche pour cacher</div></div>`
      : `<button class="secondary" data-gact="show" data-key="${esc(key)}" style="width:100%">👁 Voir mon mot (en cachette)</button>`;
    if (g.phase === "end") {
      body = `<div class="title">${WINNERS[g.winner]}</div>
        <p class="sub" style="margin:6px 0">Mot des civils : <b>${esc(g.words.civil)}</b> · Mot undercover : <b>${esc(g.words.undercover)}</b>${g.last?.guess ? ` · Mr. White a proposé « ${esc(g.last.guess)} »` : ""}</p>
        <div class="artist">${g.is_host ? "Tu peux relancer une partie avec les mêmes joueurs." : "L'animateur peut relancer une partie."}</div>`;
    } else if (!me.alive && !(g.phase === "white_guess" && g.last?.me)) {
      body = `<div class="title">Tu es éliminé 👀</div><div class="artist">Regarde la suite… sans rien dire !</div>${lastLine}`;
    } else if (g.phase === "words") {
      body = `${wordBox}<p class="sub" style="margin:10px 0 0">Chacun donne un indice à voix haute, dans cet ordre :</p>
        <div class="order">${g.order.map(esc).join(" → ")}</div>${lastLine}`;
    } else if (g.phase === "vote") {
      const pool = g.players.filter((p) => p.alive && p.pid !== me.pid && (!g.candidates || g.candidates.includes(p.pid)));
      body = `${g.last?.tie ? `<div class="title">Égalité ! On revote entre ${g.candidates.map(nameOf).join(", ")}</div>` : `<div class="title">Qui est l'intrus ?</div>`}
        <div class="artist">${me.vote ? "Tu peux encore changer ton vote." : "Vote pour éliminer quelqu'un :"} (${g.votes_count}/${g.players.filter((p) => p.alive).length} votes)</div>
        <div class="chips" style="margin-top:8px">${pool.map((p) => `<button class="${me.vote === p.pid ? "" : "secondary"}" data-gact="vote" data-target="${esc(p.pid)}">${me.vote === p.pid ? "✓ " : ""}${esc(p.name)}</button>`).join("")}</div>
        <div style="margin-top:10px">${wordBox}</div>`;
    } else if (g.phase === "white_guess") {
      body = g.last?.me
        ? `<div class="title">Démasqué ! Dernière chance 🎩</div><div class="artist">Devine le mot des civils pour gagner :</div>
           <form data-gform="guess" class="row" style="margin-top:8px"><input class="grow" type="text" id="guessInput" maxlength="40" placeholder="Le mot des civils" autocomplete="off"><button>Valider</button></form>`
        : `<div class="title">${esc(g.last.name)} était Mr. White !</div><div class="artist">Il tente de deviner le mot des civils…</div>`;
    } else if (g.phase === "reveal") {
      body = `${lastLine}<div class="artist">${g.is_host ? "Lance la manche suivante quand vous êtes prêts." : "L'animateur lance la manche suivante…"}</div>`;
    }
  } else if (g.phase === "question") {  // Qui de nous ?
    body = `<div class="question">${esc(g.question)}</div>
      <div class="chips" style="margin-top:10px">${g.players.map((p) => `<button class="${me.vote === p.pid ? "" : "secondary"}" data-gact="vote" data-target="${esc(p.pid)}">${me.vote === p.pid ? "✓ " : ""}${p.pid === me.pid ? "Moi" : esc(p.name)}</button>`).join("")}</div>
      <div class="artist" style="margin-top:8px">${g.votes_count}/${g.players.length} votes · anonyme</div>`;
  } else if (g.phase === "results") {
    body = `<div class="question">${esc(g.question)}</div>${resultsHtml(g)}`;
  }
  $("game").innerHTML = title + body;
  const input = $("guessInput");
  if (input) { input.value = guessDraft; input.addEventListener("input", () => { guessDraft = input.value; }); }
  renderGameHost(g);
  $("gameCode").textContent = g.code;
  const qr = `/qr/game/${g.code}.svg`;
  if ($("gameQr").getAttribute("src") !== qr) $("gameQr").src = qr;
  $("gameLeave").textContent = g.is_host ? "Fermer la partie" : "Quitter la partie";
}

function resultsHtml(g) {
  if (!g.results) return "";
  const max = Math.max(1, ...g.results.map((r) => r.count));
  return `<div class="list" style="margin-top:10px">${g.results.map((r) => `<div class="bar ${r.count === max ? "top" : ""}" style="--w:${Math.round(100 * r.count / max)}%">
    <span>${r.count === max ? "👑 " : ""}${esc(r.name)}</span><b>${r.count}</b></div>`).join("") || `<div class="artist">Personne n'a voté</div>`}</div>`;
}

// Commandes de l'animateur (créateur de la partie) et liste des joueurs.
function renderGameHost(g) {
  const btn = (action, label, cls = "", extra = "") => `<button class="${cls}" data-gact="${action}" ${extra}>${label}</button>`;
  const alive = g.players.filter((p) => p.alive);
  const controls = !g.is_host ? "" : {
    lobby: btn("start", g.type === "undercover" ? "▶︎ Distribuer les mots" : "▶︎ Première question", "grow", g.players.length < (g.type === "undercover" ? 3 : 2) ? "disabled" : ""),
    words: btn("vote_start", "🗳 Passer au vote", "grow"),
    vote: btn("close_vote", `Clore le vote (${g.votes_count}/${alive.length})`, "grow"),
    white_guess: btn("skip_guess", "Passer la devinette", "secondary grow"),
    reveal: btn("next", "▶︎ Manche suivante", "grow"),
    question: btn("close_vote", `Voir les résultats (${g.votes_count}/${g.players.length})`, "grow") + btn("next", "⏭", "secondary", `title="Changer de question"`),
    results: btn("next", "▶︎ Question suivante", "grow"),
    end: btn("restart", "🔁 Rejouer avec les mêmes joueurs", "grow"),
  }[g.phase] || "";
  const canEliminate = g.is_host && g.type === "undercover" && (g.phase === "words" || g.phase === "vote");
  const canRemove = g.is_host && (g.phase === "lobby" || g.phase === "end" || g.type === "whoof");
  const seeRoles = g.phase === "end" || (g.master && showRoles);
  $("gameHost").innerHTML = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    <h2>Joueurs (${g.players.length})${g.master && g.type === "undercover" ? ` <button class="secondary" data-gact="roles" style="padding:2px 8px">${showRoles ? "🙈 Cacher" : "👁 Rôles"}</button>` : ""}</h2>
    <div class="list">${g.players.map((p) => `
      <div class="track" style="${p.alive ? "" : "opacity:.55"}">
        <div class="meta"><div class="title">${p.alive ? "" : "✝︎ "}${esc(p.name)}${p.host ? " 🎲" : ""}${(g.phase === "vote" || g.phase === "question") && p.voted ? " ✓" : ""}</div>
          ${p.role && (seeRoles || !p.alive) ? `<div class="artist">${esc(p.role)}${seeRoles && p.word ? " · " + esc(p.word) : ""}</div>` : ""}</div>
        <div class="icon-btns">
          ${canEliminate && p.alive ? `<button class="danger" data-gact="eliminate" data-target="${esc(p.pid)}" title="Éliminer (vote à main levée)">Éliminer</button>` : ""}
          ${canRemove && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Retirer de la partie">✕</button>` : ""}
        </div>
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.is_host && !g.me && (g.phase === "lobby" || g.phase === "end") ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

async function gameAction(action, extra = {}) {
  if (!myGame) return;
  try {
    const g = await gapi(`/api/games/${myGame}`, { guest_id: guestId, name: guestName, action, ...extra });
    if (action === "end" || (action === "leave" && !g?.is_host)) { setGame(""); renderGame(null); return; }
    renderGame(g);
  } catch (e) {
    toast(e.message, "err");
    if (e.status === 404) { setGame(""); renderGame(null); }
  }
}
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-gact]");
  if (!b) return;
  const a = b.dataset.gact;
  if (a === "show") { wordShown = b.dataset.key; return renderGame(game); }
  if (a === "hide") { wordShown = ""; return renderGame(game); }
  if (a === "roles") { showRoles = !showRoles; return renderGame(game); }
  if (a === "eliminate" && !confirm("Éliminer ce joueur ?")) return;
  gameAction(a, { target: b.dataset.target || "" });
});
$("game").addEventListener("submit", (ev) => {
  if (!ev.target.closest("[data-gform]")) return;
  ev.preventDefault();
  if (!guessDraft.trim()) return;
  gameAction("guess", { guess: guessDraft.trim() });
  guessDraft = "";
});
$("gameLeave").onclick = () => {
  if (!game) return;
  if (game.is_host) { if (confirm("Fermer la partie pour tout le monde ?")) gameAction("end"); }
  else if (!game.me) { setGame(""); renderGame(null); }
  else if (confirm("Quitter la partie ?")) gameAction("leave");
};
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-create]");
  if (!b) return;
  const card = b.closest(".card");
  b.disabled = true;
  try {
    const g = await gapi("/api/games", { guest_id: guestId, name: guestName, type: b.dataset.create,
      white: card.querySelector("[data-opt=white]")?.checked ?? true, plays: card.querySelector("[data-opt=plays]").checked });
    setGame(g.code); renderGame(g);
    toast(`Partie créée : code ${g.code}`, "ok");
  } catch (e) { toast(e.message, "err"); }
  b.disabled = false;
});
$("gJoinForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const code = $("gCode").value.trim().toUpperCase();
  if (code.length !== 4) return;
  setGame(code); autoJoin = true; $("gCode").value = "";
  await refreshGame();
});
$("gCode").addEventListener("input", () => { $("gCode").value = $("gCode").value.toUpperCase().replace(/[^A-Z]/g, ""); });
$("gNameForm").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const name = $("gNameInput").value.trim().slice(0, 30);
  if (!name) return;
  guestName = name; store("vp_name", guestName);
  refreshGame();
  if (typeof refresh === "function") refresh();
});

