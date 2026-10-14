// 🎮 Jeux, partagés par la page invités et l'admin.
// Utilise les globales de la page : $, esc, store, toast, guestId, guestName (chargé après le script de la page).
// Icônes des jeux (traits, couleur héritée) : chapeau et lunettes d'espion, deux personnes et un « ? ».
const GAME_ICONS = {
  undercover: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 22h38"/><path d="M12 22l3-11h18l3 11"/><circle cx="16" cy="32" r="5.5"/><circle cx="32" cy="32" r="5.5"/><path d="M21.5 32h5"/></svg>`,
  whoof: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="13" cy="24" r="5"/><circle cx="35" cy="24" r="5"/><path d="M4 41c1-6 4.5-9 9-9s8 3 9 9"/><path d="M26 41c1-6 4.5-9 9-9s8 3 9 9"/><path d="M20 9.5a4 4 0 1 1 5.5 3.7c-1.2.5-1.5 1.3-1.5 2.8"/><path d="M24 20.5v.1"/></svg>`,
};
GAME_ICONS.never = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 7h13l-1.6 14a4.9 4.9 0 0 1-9.8 0z"/><path d="M14.5 26v12"/><path d="M9.5 38h10"/><path d="M27 7h13l-1.6 14a4.9 4.9 0 0 1-9.8 0z"/><path d="M33.5 26v12"/><path d="M28.5 38h10"/><path d="M9 14h11M28 14h11"/></svg>`;
const GAME_THEME = { undercover: "g-uc", whoof: "g-wh", never: "g-nv" };
const helpBtn = (type) => `<button type="button" class="g-help" data-rules="${type}" aria-label="Règles du jeu">?</button>`;

// Règles détaillées, ouvertes par le « ? » de chaque jeu.
const GAME_RULES = {
  never: `
    <h3>Le but</h3>
    <p>Découvrir ce que vos amis ont (ou n'ont jamais) fait… et boire quand on avoue.</p>
    <h3>Une phrase</h3>
    <ol>
      <li>Une phrase s'affiche, par exemple « Je n'ai jamais dansé sur une table ».</li>
      <li>Chacun répond sur son téléphone : <b>🍻 Je l'ai déjà fait</b> ou <b>😇 Jamais</b>. Les réponses restent cachées tant que tout le monde n'a pas répondu (on peut changer d'avis jusque-là).</li>
      <li>Quand tout le monde a répondu (ou quand l'animateur le décide), les réponses sont <b>révélées</b> : on voit qui l'a déjà fait.</li>
      <li>Tous ceux qui l'ont fait <b>boivent le nombre de gorgées</b> choisi par l'animateur.</li>
      <li>On a le droit de demander des détails… et de raconter l'histoire ! Puis phrase suivante.</li>
    </ol>
    <h3>Les modes</h3>
    <ul>
      <li><b>😇 Soft</b> : souvenirs et expériences pour tout le monde.</li>
      <li><b>😬 Malaisant</b> : petites hontes, mensonges et secrets.</li>
      <li><b>🔥 Hot</b> : sexe et séduction, entre adultes consentants.</li>
      <li><b>🎲 Mix</b> : un peu de tout.</li>
    </ul>
    <p>Aucune phrase ne revient avant que toutes celles du mode soient passées. L'animateur peut changer de phrase avec ⏭.</p>
    <h3>À savoir</h3>
    <p>Il faut au moins 2 joueurs, et on peut rejoindre en cours de route. On joue honnêtement ! Personne n'est obligé de boire de l'alcool : un verre d'eau compte aussi. Avec 0 gorgée, c'est la version sans alcool.</p>`,
  undercover: `
    <h3>Le but</h3>
    <p>Les <b>civils</b> doivent démasquer les intrus. Les <b>undercovers</b> doivent se fondre dans la masse sans se faire repérer. <b>Mr. White</b> doit bluffer… et deviner le mot des civils.</p>
    <h3>Les rôles</h3>
    <ul>
      <li><b>Civils</b> (la majorité) : ils ont tous le même mot, par exemple « Raclette ».</li>
      <li><b>Undercover</b> : il a un mot proche, par exemple « Fondue ». Il ne sait pas qu'il est undercover !</li>
      <li><b>Mr. White</b> (option, dès 5 joueurs) : il n'a aucun mot et le sait.</li>
    </ul>
    <p>Nombre d'undercovers : 1 jusqu'à 6 joueurs, 2 de 7 à 9 joueurs, 3 au-delà. Il faut au moins 3 joueurs.</p>
    <h3>Une manche</h3>
    <ol>
      <li><b>Ton mot</b> : touche « Voir mon mot » en cachette. Il s'affiche 3 secondes puis se cache.</li>
      <li><b>Les indices</b> : dans l'ordre de parole affiché, chacun dit à voix haute <b>un indice</b> sur son mot (un mot ou une courte phrase), sans jamais le dire. Pas trop précis pour ne pas aider les intrus, pas trop vague pour ne pas paraître suspect. Mr. White ne commence jamais.</li>
      <li><b>Le vote</b> : chacun vote sur son téléphone pour la personne qu'il pense être un intrus. On peut changer son vote tant que tout le monde n'a pas voté.</li>
      <li><b>L'élimination</b> : le joueur qui a le plus de voix est éliminé et son rôle est révélé (pas son mot). En cas d'égalité, on revote entre les ex æquo ; nouvelle égalité, le hasard tranche.</li>
    </ol>
    <p>Un joueur éliminé ne parle plus et ne vote plus… et ne révèle rien !</p>
    <h3>Mr. White démasqué</h3>
    <p>S'il est éliminé, il a une dernière chance : deviner le mot des civils. S'il trouve (accents et majuscules ignorés), il gagne seul la partie.</p>
    <h3>Fin de la partie</h3>
    <ul>
      <li>Les <b>civils gagnent</b> quand tous les undercovers et Mr. White sont éliminés.</li>
      <li>Les <b>intrus gagnent</b> s'il ne reste plus qu'un seul civil.</li>
    </ul>
    <p>À la fin, tous les rôles et les deux mots sont dévoilés. « Rejouer » relance avec de nouveaux mots.</p>
    <h3>L'animateur</h3>
    <p>C'est la personne qui a créé la partie. Il distribue les mots, lance le vote et la manche suivante, peut changer l'ordre de parole, éliminer quelqu'un après un vote à main levée ou exclure un joueur. S'il ne joue pas, il est <b>maître du jeu</b> et peut voir les rôles.</p>
    <p>Arrivé en retard ? Rejoins quand même : tu joueras à la partie suivante.</p>`,
  whoof: `
    <h3>Le but</h3>
    <p>Découvrir ce que vos amis pensent vraiment de vous… et faire boire la personne désignée.</p>
    <h3>Une question</h3>
    <ol>
      <li>Une question s'affiche, par exemple « Qui de nous finira la soirée en pyjama ? ».</li>
      <li>Chacun vote sur son téléphone pour la personne qui correspond le mieux. On peut voter pour soi. Les votes sont <b>anonymes</b>.</li>
      <li>Quand tout le monde a voté (ou quand l'animateur le décide), le classement s'affiche.</li>
      <li>La personne la plus désignée <b>boit le nombre de gorgées</b> choisi par l'animateur. En cas d'égalité, tous les ex æquo boivent.</li>
      <li>Le désigné peut se défendre… ou raconter l'anecdote qui va avec. Puis question suivante !</li>
    </ol>
    <h3>Les modes</h3>
    <ul>
      <li><b>😇 Soft</b> : questions gentilles et drôles, pour tout le monde.</li>
      <li><b>😬 Malaisant</b> : questions gênantes, souvenirs embarrassants, secrets.</li>
      <li><b>🔥 Hot</b> : questions sur le sexe et la séduction, entre adultes consentants.</li>
      <li><b>🎲 Mix</b> : un peu de tout.</li>
    </ul>
    <p>Aucune question ne revient avant que toutes celles du mode soient passées. L'animateur peut changer de question avec ⏭.</p>
    <h3>À savoir</h3>
    <p>Il faut au moins 2 joueurs, et on peut rejoindre en cours de route. Personne n'est obligé de boire de l'alcool : un verre d'eau compte aussi. Avec 0 gorgée, c'est la version sans alcool.</p>`,
};

document.getElementById("gamesRoot").innerHTML = `
    <div id="gName" class="hidden">
      <p class="sub">Comment tu t'appelles ?</p>
      <form id="gNameForm" class="row">
        <input id="gNameInput" class="grow" type="text" maxlength="30" placeholder="Ton prénom" autocomplete="given-name" required>
        <button>OK</button>
      </form>
    </div>

    <div id="gHome" class="hidden">
      <div class="g-hello">Salut <span id="gHello"></span></div>
      <h1 class="g-h1">On joue à quoi&nbsp;?</h1>

      <form id="gJoinForm" class="g-code">
        <label for="gCode">Code d'une partie</label>
        <input id="gCode" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="4" placeholder="• • • •" autocomplete="off">
      </form>

      <div class="gcard g-uc">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.undercover}</div>
          <div class="g-meta"><div class="g-title">Undercover</div><div class="g-tag">Trouve l'intrus avant qu'il ne te trouve.</div></div>
          ${helpBtn("undercover")}
        </div>
        <p class="g-desc">Chacun reçoit un mot secret. Les undercovers ont un mot proche, Mr. White n'en a pas. Indices à voix haute, puis on vote pour éliminer.</p>
        <div class="g-chips"><span>3+ joueurs</span><span>Mot secret</span><span>Bluff</span></div>
        <label class="g-opt"><span>Avec Mr. White <small>dès 5 joueurs</small></span><input type="checkbox" class="switch" data-opt="white" checked></label>
        <label class="g-opt"><span>Je joue aussi <small>sinon tu es maître du jeu et tu vois les rôles</small></span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="undercover">Créer une partie</button>
      </div>

      <div class="gcard g-wh">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.whoof}</div>
          <div class="g-meta"><div class="g-title">Qui de nous&nbsp;?</div><div class="g-tag">Votez en secret, découvrez le classement.</div></div>
          ${helpBtn("whoof")}
        </div>
        <p class="g-desc">Une question tombe (« Qui de nous finira la soirée en pyjama ? »), chacun vote pour quelqu'un, puis on découvre qui a été désigné… et qui boit.</p>
        <div class="g-chips"><span>2+ joueurs</span><span>Soft → Hot</span><span>Gorgées</span></div>
        <div class="g-label">Type de questions</div>
        <div class="g-modes" data-opt-group="mode">
          <button type="button" data-val="soft" class="on">😇 Soft</button><button type="button" data-val="awkward">😬 Malaisant</button>
          <button type="button" data-val="hot">🔥 Hot</button><button type="button" data-val="mix">🎲 Mix</button>
        </div>
        <div class="g-opt"><span>Gorgées pour le désigné <small>0 = sans alcool</small></span>
          <div class="g-stepper" data-opt-group="sips"><button type="button" data-step="-1" aria-label="Moins">−</button><b data-val-out>2</b><button type="button" data-step="1" aria-label="Plus">+</button></div>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="whoof">Créer une partie</button>
      </div>

      <div class="gcard g-nv">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.never}</div>
          <div class="g-meta"><div class="g-title">Je n'ai jamais</div><div class="g-tag">Avoue… ou bois.</div></div>
          ${helpBtn("never")}
        </div>
        <p class="g-desc">Une phrase tombe (« Je n'ai jamais dansé sur une table »). Chacun répond en secret « déjà fait » ou « jamais », puis tout est révélé : ceux qui l'ont fait boivent.</p>
        <div class="g-chips"><span>2+ joueurs</span><span>Soft → Hot</span><span>Aveux</span></div>
        <div class="g-label">Type de phrases</div>
        <div class="g-modes" data-opt-group="mode">
          <button type="button" data-val="soft" class="on">😇 Soft</button><button type="button" data-val="awkward">😬 Malaisant</button>
          <button type="button" data-val="hot">🔥 Hot</button><button type="button" data-val="mix">🎲 Mix</button>
        </div>
        <div class="g-opt"><span>Gorgées pour ceux qui l'ont fait <small>0 = sans alcool</small></span>
          <div class="g-stepper" data-opt-group="sips"><button type="button" data-step="-1" aria-label="Moins">−</button><b data-val-out>1</b><button type="button" data-step="1" aria-label="Plus">+</button></div>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="never">Créer une partie</button>
      </div>
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

    <div id="rulesModal" class="g-modal hidden" role="dialog" aria-modal="true" aria-labelledby="rulesTitle">
      <div class="g-sheet">
        <div class="g-head">
          <div class="g-icon" id="rulesIcon"></div>
          <div class="g-meta"><div class="g-title" id="rulesTitle"></div><div class="g-tag">Règles du jeu</div></div>
          <button type="button" class="g-help" data-rules-close aria-label="Fermer">✕</button>
        </div>
        <div class="g-rules" id="rulesBody"></div>
        <button type="button" class="g-go" data-rules-close>J'ai compris</button>
      </div>
    </div>
`;

// 🎮 Jeux : n'importe qui crée une partie (code + QR) et l'anime ; les autres la rejoignent avec son code.
let myGame = store("vp_game") || "", game = null, wordShown = "", wordUntil = 0, guessDraft = "", showRoles = false, autoJoin = false;
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
  $("game").className = "card game " + (GAME_THEME[g.type] || "");
  const title = `<div class="g-head g-play-head"><div class="g-icon">${GAME_ICONS[g.type] || ""}</div>
    <div class="g-meta"><div class="g-title">${esc(g.name)}</div>
    <div class="g-tag">${g.mode ? esc(g.mode) + " · " : ""}${GAME_PHASES[g.phase]}${g.round && g.phase !== "lobby" ? ` · ${g.type === "undercover" ? "manche" : "question"} ${g.round}` : ""}</div></div>
    ${helpBtn(g.type)}</div>`;
  const lastLine = g.last?.name ? `<p class="sub" style="margin:8px 0">${esc(g.last.name)} était <b>${esc(g.last.role)}</b>.${g.last.guess ? ` Mr. White a proposé « ${esc(g.last.guess)} »… raté !` : ""}</p>` : "";
  let body = "";

  if (g.kicked) {
    body = `<div class="title">L'animateur t'a retiré de cette partie</div><div class="artist">Tu peux en créer ou en rejoindre une autre.</div>`;
  } else if (!me && !g.master) {
    // Visiteur : pas encore dans la partie (Undercover en cours : il attendra la prochaine).
    const running = g.type === "undercover" && g.phase !== "lobby" && g.phase !== "end";
    body = `<div class="title">Partie de ${esc(g.host_name || "quelqu'un")}</div>
      <div class="artist">${g.players.length} joueur${g.players.length > 1 ? "s" : ""}${running ? " · partie en cours, tu joueras à la suivante" : ""}</div>
      <button data-gact="join" style="width:100%;margin-top:10px">Rejoindre la partie</button>`;
  } else if (me?.waiting) {
    body = `<div class="title">Tu es inscrit ⏳</div><div class="artist">Une partie est en cours : tu recevras ton mot à la prochaine.</div>`;
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
    const wordBox = !me?.dealt ? "" : wordShown === key && Date.now() < wordUntil
      ? `<div data-gact="hide" class="secret">${secret}<div class="artist" style="margin-top:4px">Se cache dans <b id="wordCountdown">${Math.ceil((wordUntil - Date.now()) / 1000)}</b> s · touche pour cacher</div></div>`
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
  } else if (g.phase === "question" && g.type === "never") {
    body = `<div class="question">${esc(g.question)}</div>
      <div class="never-btns">
        <button class="${me.vote === "yes" ? "" : "secondary"}" data-gact="vote" data-target="yes">${me.vote === "yes" ? "✓ " : ""}🍻 Je l'ai déjà fait</button>
        <button class="${me.vote === "no" ? "" : "secondary"}" data-gact="vote" data-target="no">${me.vote === "no" ? "✓ " : ""}😇 Jamais</button>
      </div>
      <div class="artist" style="margin-top:8px">${g.votes_count}/${g.players.length} réponses · révélées à la fin</div>`;
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
  if (g.type === "never") return neverResultsHtml(g);
  const max = Math.max(1, ...g.results.map((r) => r.count));
  const sips = g.options?.sips || 0;
  const drinkers = g.results.filter((r) => r.count === max).map((r) => esc(r.name));
  const drink = sips && drinkers.length
    ? `<div class="drink">🍻 ${drinkers.join(" et ")} boi${drinkers.length > 1 ? "vent" : "t"} ${sips} gorgée${sips > 1 ? "s" : ""} !</div>` : "";
  return drink + `<div class="list" style="margin-top:10px">${g.results.map((r) => `<div class="bar ${r.count === max ? "top" : ""}" style="--w:${Math.round(100 * r.count / max)}%">
    <span>${r.count === max ? "👑 " : ""}${esc(r.name)}</span><b>${r.count}</b></div>`).join("") || `<div class="artist">Personne n'a voté</div>`}</div>`;
}

// « Je n'ai jamais » : ceux qui l'ont déjà fait boivent.
function neverResultsHtml(g) {
  const did = g.results.filter((r) => r.answer === "yes"), never = g.results.filter((r) => r.answer === "no");
  const sips = g.options?.sips || 0;
  const drink = sips && did.length
    ? `<div class="drink">🍻 ${did.map((r) => esc(r.name)).join(", ")} boi${did.length > 1 ? "vent" : "t"} ${sips} gorgée${sips > 1 ? "s" : ""} !</div>`
    : !did.length ? `<div class="drink">😇 Personne ne l'a fait… tout le monde est sage ?</div>` : "";
  const col = (label, list) => `<div class="never-col"><div class="artist">${label} (${list.length})</div>
    <div class="chips">${list.map((r) => `<span class="pill">${esc(r.name)}</span>`).join("") || `<span class="artist">personne</span>`}</div></div>`;
  return drink + `<div class="never-res">${col("🍻 Déjà fait", did)}${col("😇 Jamais", never)}</div>`;
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
  const canRemove = g.is_host;
  const seeRoles = g.phase === "end" || (g.master && showRoles);
  const speaking = g.type === "undercover" && g.phase === "words";
  const canMove = g.is_host && (speaking || g.phase === "lobby");
  const list = speaking ? g.order_pids.map((pid) => g.players.find((p) => p.pid === pid)).filter(Boolean)
    .concat(g.players.filter((p) => !g.order_pids.includes(p.pid))) : g.players;
  $("gameHost").innerHTML = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    <h2>${speaking ? "Ordre de parole" : "Joueurs"} (${g.players.length})${g.master && g.type === "undercover" ? ` <button class="secondary" data-gact="roles" style="padding:2px 8px">${showRoles ? "🙈 Cacher" : "👁 Rôles"}</button>` : ""}</h2>
    <div class="list">${list.map((p, i) => `
      <div class="track" style="${p.alive ? "" : "opacity:.55"}">
        <div class="meta"><div class="title" ${p.waiting ? 'title="Joue à la prochaine partie"' : ""}>${speaking && p.alive ? `${i + 1}. ` : ""}${p.waiting ? "⏳ " : p.alive ? "" : "✝︎ "}${esc(p.name)}${p.host ? " 🎲" : ""}${(g.phase === "vote" || g.phase === "question") && p.voted ? " ✓" : ""}</div>
          ${p.role && (seeRoles || !p.alive) ? `<div class="artist">${esc(p.role)}${seeRoles && p.word ? " · " + esc(p.word) : ""}</div>` : ""}</div>
        <div class="icon-btns">
          ${canMove && p.alive && i > 0 ? `<button class="secondary" data-gact="up" data-target="${esc(p.pid)}" title="Monter">⬆</button>` : ""}
          ${canMove && p.alive && i < (speaking ? g.order_pids.length : list.length) - 1 ? `<button class="secondary" data-gact="down" data-target="${esc(p.pid)}" title="Descendre">⬇</button>` : ""}
          ${canEliminate && p.alive ? `<button class="danger" data-gact="eliminate" data-target="${esc(p.pid)}" title="Éliminer (vote à main levée)">Éliminer</button>` : ""}
          ${canRemove && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure de la partie">✕</button>` : ""}
        </div>
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.is_host && !g.me && (g.phase === "lobby" || g.phase === "end") ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// Compte à rebours du mot affiché : 3, 2, 1… puis on le cache.
setInterval(() => {
  if (!wordShown) return;
  const left = Math.ceil((wordUntil - Date.now()) / 1000);
  if (left <= 0) { wordShown = ""; renderGame(game); }
  else if ($("wordCountdown")) $("wordCountdown").textContent = left;
}, 200);

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
  if (a === "show") { wordShown = b.dataset.key; wordUntil = Date.now() + 3000; return renderGame(game); }
  if (a === "hide") { wordShown = ""; wordUntil = 0; return renderGame(game); }
  if (a === "roles") { showRoles = !showRoles; return renderGame(game); }
  if (a === "eliminate" && !confirm("Éliminer ce joueur ?")) return;
  if (a === "remove" && !confirm("Exclure ce joueur de la partie ? Il ne pourra pas revenir.")) return;
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
  else if (!game.me || game.kicked) { setGame(""); renderGame(null); }
  else if (confirm("Quitter la partie ?")) gameAction("leave");
};
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-create]");
  if (!b) return;
  const card = b.closest(".gcard");
  b.disabled = true;
  try {
    const g = await gapi("/api/games", { guest_id: guestId, name: guestName, type: b.dataset.create,
      white: card.querySelector("[data-opt=white]")?.checked ?? true, plays: card.querySelector("[data-opt=plays]").checked,
      mode: card.querySelector("[data-opt-group=mode] .on")?.dataset.val || "soft",
      sips: +(card.querySelector("[data-opt-group=sips] [data-val-out]")?.textContent || 0) });
    setGame(g.code); renderGame(g);
    toast(`Partie créée : code ${g.code}`, "ok");
  } catch (e) { toast(e.message, "err"); }
  b.disabled = false;
});
async function joinByCode() {
  const code = $("gCode").value.trim();
  if (!/^\d{4}$/.test(code)) return;
  $("gCode").value = ""; $("gCode").blur();
  setGame(code); autoJoin = true;
  await refreshGame();
}
// « ? » : règles détaillées du jeu.
const GAME_NAMES = { undercover: "Undercover", whoof: "Qui de nous ?", never: "Je n'ai jamais" };
document.addEventListener("click", (ev) => {
  const open = ev.target.closest("[data-rules]");
  if (open) {
    const t = open.dataset.rules;
    $("rulesModal").querySelector(".g-sheet").className = "g-sheet " + GAME_THEME[t];
    $("rulesIcon").innerHTML = GAME_ICONS[t];
    $("rulesTitle").textContent = GAME_NAMES[t];
    $("rulesBody").innerHTML = GAME_RULES[t];
    $("rulesBody").scrollTop = 0;
    $("rulesModal").classList.remove("hidden");
    document.body.style.overflow = "hidden";
    return;
  }
  if (ev.target.closest("[data-rules-close]") || ev.target.id === "rulesModal") {
    $("rulesModal").classList.add("hidden");
    document.body.style.overflow = "";
  }
});

// Options de création : mode (boutons) et gorgées (− / +).
document.addEventListener("click", (ev) => {
  const opt = ev.target.closest("[data-opt-group=mode] [data-val]");
  if (opt) opt.parentElement.querySelectorAll("[data-val]").forEach((b) => b.classList.toggle("on", b === opt));
  const step = ev.target.closest("[data-opt-group=sips] [data-step]");
  if (step) {
    const out = step.parentElement.querySelector("[data-val-out]");
    out.textContent = Math.max(0, Math.min(10, +out.textContent + +step.dataset.step));
  }
});
$("gJoinForm").addEventListener("submit", (ev) => { ev.preventDefault(); joinByCode(); });
// On rejoint dès le 4ᵉ chiffre, comme pour le code de la musique.
$("gCode").addEventListener("input", () => {
  $("gCode").value = $("gCode").value.replace(/\D/g, "");
  if ($("gCode").value.length === 4) joinByCode();
});
$("gNameForm").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const name = $("gNameInput").value.trim().slice(0, 30);
  if (!name) return;
  guestName = name; store("vp_name", guestName);
  refreshGame();
  if (typeof refresh === "function") refresh();
});

