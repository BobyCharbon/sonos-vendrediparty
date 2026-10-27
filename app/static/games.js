// 🎮 Jeux, partagés par la page invités et l'admin.
// iOS Safari n'applique :active (enfoncement des boutons au toucher) que si la page écoute touchstart.
document.addEventListener("touchstart", () => {}, { passive: true });
// Vibration : l'API Vibration (Android) ; sur iPhone, Safari 18+ donne un retour haptique quand on bascule
// un interrupteur natif (<input type=checkbox switch>) : on en garde un invisible pour s'en servir.
let hapticSwitch = null;
function haptic(pattern = 60) {
  if (navigator.vibrate) { try { navigator.vibrate(pattern); return; } catch {} }
  try {
    if (!hapticSwitch) {
      hapticSwitch = document.createElement("label");
      hapticSwitch.setAttribute("aria-hidden", "true");
      hapticSwitch.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0;pointer-events:none";
      const i = document.createElement("input"); i.type = "checkbox"; i.setAttribute("switch", ""); i.tabIndex = -1;
      hapticSwitch.append(i); document.body.append(hapticSwitch);
    }
    hapticSwitch.click();
  } catch {}
}
// « C'est ton tour » : une clé par tour (vide si ce n'est pas à toi) ; le téléphone vibre quand elle change.
function myTurnKey(g) {
  const me = g?.me?.pid;
  if (!me || g.kicked) return "";
  switch (g.type) {
    case "blackjack": return g.bj?.my_turn ? `bj${g.round}-${g.bj.turn}` : "";
    case "divan": return g.divan?.my_turn ? `dv${g.divan.n}` : "";
    case "biskit": return g.bk?.my_turn ? `bk${g.bk.drawn}` : "";
    case "pyramid": return g.phase === "deal" && g.pyr?.turn === me ? `py${g.pyr.step}-${g.pyr.turn}` : "";
    case "tmc": return g.tmc?.duo?.role && ["answer", "guess"].includes(g.phase) ? `tm${g.round}-${g.phase}-${g.tmc.duo.role}` : "";
    case "undercover": return g.phase === "vote" && g.me.alive ? `uc${g.round}` : "";
    case "whoof": case "never": return g.phase === "question" ? `q${g.round}` : "";
    case "likely": return g.phase === "ask" && g.likely?.voter?.mine ? `lk${g.likely.n}` : "";
    case "debate": return g.phase === "ask" && g.debate?.can_vote ? `db${g.debate.n}-${g.debate.round}` : "";
    case "purity": return g.phase === "answering" && g.purity?.playing && !g.purity.submitted ? "pu" : "";
    case "quiz": return g.phase === "q" && !g.quiz?.q?.out ? `qz${g.quiz.n}` : "";
    case "president": return g.president?.my_turn && (!navigator.userActivation || navigator.userActivation.hasBeenActive) ? `pr${g.round}-${g.president.token}` : "";
    case "casino": return g.phase === "bet" ? `cs${g.round}` : "";
    default: return "";
  }
}
let lastTurnKey = "";
function turnSignal(g) {
  const k = g ? `${g.id}:${myTurnKey(g)}` : "";
  if (k && !k.endsWith(":") && k !== lastTurnKey) {
    haptic([70, 50, 70]);
    document.getElementById("gTop")?.classList.remove("g-turn"); void document.getElementById("gTop")?.offsetWidth;
    document.getElementById("gTop")?.classList.add("g-turn");
  }
  lastTurnKey = k;
}
// Utilise les globales de la page : $, esc, store, toast, guestId, guestName (chargé après le script de la page).
// Icônes des jeux (traits, couleur héritée) : chapeau et lunettes d'espion, deux personnes et un « ? ».
const GAME_ICONS = {
  undercover: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 22h38"/><path d="M12 22l3-11h18l3 11"/><circle cx="16" cy="32" r="5.5"/><circle cx="32" cy="32" r="5.5"/><path d="M21.5 32h5"/></svg>`,
  whoof: `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="13" cy="24" r="5"/><circle cx="35" cy="24" r="5"/><path d="M4 41c1-6 4.5-9 9-9s8 3 9 9"/><path d="M26 41c1-6 4.5-9 9-9s8 3 9 9"/><path d="M20 9.5a4 4 0 1 1 5.5 3.7c-1.2.5-1.5 1.3-1.5 2.8"/><path d="M24 20.5v.1"/></svg>`,
};
GAME_ICONS.never = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 7h13l-1.6 14a4.9 4.9 0 0 1-9.8 0z"/><path d="M14.5 26v12"/><path d="M9.5 38h10"/><path d="M27 7h13l-1.6 14a4.9 4.9 0 0 1-9.8 0z"/><path d="M33.5 26v12"/><path d="M28.5 38h10"/><path d="M9 14h11M28 14h11"/></svg>`;
GAME_ICONS.roulette = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="27" r="17"/><circle cx="24" cy="27" r="3"/><path d="M24 10v14M24 30v14M7 27h14M27 27h14M12 15l10 10M26 29l10 10M36 15L26 25M22 29L12 39"/><path d="M20 3h8l-4 6z"/></svg>`;
GAME_ICONS.blackjack = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="21" height="29" rx="3" transform="rotate(-10 15.5 25.5)"/><rect x="21" y="8" width="21" height="29" rx="3" transform="rotate(8 31.5 22.5)"/><path d="M31.5 15.5c-2.8 2.8-5.5 4.6-5.5 7.2a2.7 2.7 0 0 0 4.6 1.9l-.9 3h3.6l-.9-3a2.7 2.7 0 0 0 4.6-1.9c0-2.6-2.7-4.4-5.5-7.2z"/></svg>`;
GAME_ICONS.casino = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="24" r="19"/><circle cx="24" cy="24" r="10"/><path d="M24 5v9M24 34v9M5 24h9M34 24h9M10.6 10.6l6.3 6.3M31.1 31.1l6.3 6.3M37.4 10.6l-6.3 6.3M16.9 31.1l-6.3 6.3"/><circle cx="24" cy="24" r="2.5" fill="currentColor"/><circle cx="36" cy="8" r="3" fill="currentColor" stroke="none"/></svg>`;
GAME_ICONS.divan = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 24v-7a5 5 0 0 1 5-5h18a5 5 0 0 1 5 5v7"/><path d="M6 24a4 4 0 0 1 8 0v4h20v-4a4 4 0 0 1 8 0v10H6z"/><path d="M10 34v4M38 34v4"/></svg>`;
GAME_ICONS.tmc = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="15" cy="15" r="6"/><circle cx="33" cy="15" r="6"/><path d="M4 38c1-7 5-11 11-11 3 0 5 1 7 3M44 38c-1-7-5-11-11-11-3 0-5 1-7 3"/><path d="M24 44s-6-3.6-6-7.6a3 3 0 0 1 6-1 3 3 0 0 1 6 1c0 4-6 7.6-6 7.6z"/></svg>`;
GAME_ICONS.pyramid = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="19" y="5" width="10" height="12" rx="2"/><rect x="12" y="19" width="10" height="12" rx="2"/><rect x="26" y="19" width="10" height="12" rx="2"/><rect x="5" y="33" width="10" height="12" rx="2"/><rect x="19" y="33" width="10" height="12" rx="2"/><rect x="33" y="33" width="10" height="12" rx="2"/></svg>`;
GAME_ICONS.biskit = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 18l6 6 10-12 10 12 6-6-3 16H11z"/><rect x="15" y="34" width="18" height="10" rx="3"/><circle cx="21" cy="39" r="1" fill="currentColor"/><circle cx="27" cy="39" r="1" fill="currentColor"/></svg>`;
GAME_ICONS.quiz = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M24 4a15 15 0 0 1 9 27c-2 1.6-3 3.4-3 6v1H18v-1c0-2.6-1-4.4-3-6A15 15 0 0 1 24 4z"/><path d="M19 43h10"/><path d="M20 17a4 4 0 1 1 6 3.4c-1.3.8-2 1.7-2 3.1"/><circle cx="24" cy="29" r="0.6" fill="currentColor"/></svg>`;
GAME_ICONS.purity = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="24" cy="9" rx="11" ry="4"/><circle cx="24" cy="27" r="11"/><path d="M19 25h.01M29 25h.01"/><path d="M19.5 31c2.5 2.5 6.5 2.5 9 0"/><path d="M15 44c2-3 5-4.5 9-4.5s7 1.5 9 4.5"/></svg>`;
GAME_ICONS.room = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 22L24 8l17 14"/><path d="M11 19v21h26V19"/><rect x="19" y="27" width="10" height="13" rx="2"/><path d="M30 13V9h5v8"/></svg>`;
GAME_ICONS.likely = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="16" y="9" width="16" height="27" rx="3.5"/><path d="M22 31h4"/><path d="M24 15.5a3.5 3.5 0 1 1 2.6 3.4c-1 .3-1.6 1-1.6 2v1"/><path d="M25 25.5h.01"/><path d="M8 18a17 17 0 0 0 3 19"/><path d="M8 31l3 6 6-2"/><path d="M40 30a17 17 0 0 0-3-19"/><path d="M40 17l-3-6-6 2"/></svg>`;
GAME_ICONS.debate = `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M24 6v34"/><path d="M15 42h18"/><path d="M8 12h32"/><path d="M8 12l-5 13a5 5 0 0 0 10 0z"/><path d="M40 12l-5 13a5 5 0 0 0 10 0z"/></svg>`;
const GAME_THEME = { room: "g-rm", biskit: "g-bk", pyramid: "g-py", undercover: "g-uc", whoof: "g-wh", never: "g-nv", roulette: "g-rl", blackjack: "g-bj", casino: "g-cs", divan: "g-dv", tmc: "g-tm" };
const isBJ = (g) => g.type === "blackjack";
GAME_ICONS.heist = Heist.icon;
GAME_THEME.heist = "g-hs";
GAME_ICONS.island = Island.icon;
GAME_THEME.island = "g-is";
GAME_ICONS.neon = Neon.icon;
GAME_THEME.neon = "g-nk";
GAME_ICONS.president = President.crown;
GAME_THEME.president = "g-pr";
// Jeux récents : étiquette « NEW » sur leur carte et leur tuile dans la salle de jeux (retirer le type pour l'enlever).
const NEW_GAMES = ["debate"];
const newBadge = (type) => NEW_GAMES.includes(type) ? `<span class="g-new" aria-label="Nouveau jeu">NEW</span>` : "";
// Catégories de l'écran Jeux et de la salle de jeux : [id, titre, jeux dans l'ordre d'affichage].
// Tout nouveau jeu doit y figurer (tests/test_game_categories.py le vérifie).
const GAME_CATEGORIES = [
  ["drinks", "🍻 Alcool", ["whoof", "never", "roulette", "biskit", "casino", "purity"]],
  ["three", "🎮 Jeux 3D", ["neon", "island", "heist"]],
  ["talk", "💞 Parler vrai", ["divan", "debate", "tmc"]],
  ["cards", "🃏 Jeux de cartes", ["pyramid", "blackjack", "president"]],
  ["mood", "🎉 Ambiance", ["quiz", "undercover", "likely"]]
];
// Jeux rangés hors « Alcool » qui se jouent aussi avec des gorgées : étiquette 🍻 (chaque jeu n'apparaît qu'une fois).
const DRINK_TAG_GAMES = ["pyramid", "blackjack", "quiz", "likely"];
const drinkTag = (type) => DRINK_TAG_GAMES.includes(type) ? `<span class="g-drink" title="Se joue aussi avec de l'alcool" aria-label="Se joue aussi avec de l'alcool">🍻</span>` : "";
const helpBtn = (type, inGame = false) => `<button type="button" class="g-help" data-rules="${type}" ${inGame ? "data-ingame" : ""} aria-label="Règles du jeu">?</button>`;

// Règles détaillées, ouvertes par le « ? » de chaque jeu.
const BJ_RULES_COMMON = `
    <h3>Le but</h3>
    <p>Battre le <b>croupier</b> (l'app) : avoir un total plus proche de 21 que lui, <b>sans dépasser 21</b>.</p>
    <h3>La valeur des cartes</h3>
    <ul>
      <li>De 2 à 10 : leur valeur. Valet, Dame, Roi : 10.</li>
      <li>As : 11, ou 1 si 11 ferait dépasser 21.</li>
      <li><b>Blackjack</b> : un As et une carte à 10 avec les 2 premières cartes (21 d'office).</li>
    </ul>
    <h3>Une main</h3>
    <ol>
      <li><b>Les mises</b> : chacun mise. Dès que tout le monde a misé, les cartes sont distribuées (l'animateur peut aussi distribuer sans attendre les retardataires).</li>
      <li><b>La distribution</b> : 2 cartes visibles pour chaque joueur ; le croupier a une carte visible et une cachée.</li>
      <li><b>Chacun son tour</b> : <b>Carte</b> pour tirer une carte, <b>Rester</b> pour garder sa main, <b>Doubler</b> (avec ses 2 premières cartes seulement) pour doubler sa mise et recevoir une seule dernière carte. Au-delà de 21, c'est perdu.</li>
      <li><b>Le croupier</b> retourne sa carte cachée et tire jusqu'à avoir au moins 17.</li>
      <li><b>Résultat</b> : plus proche de 21 que le croupier, ou croupier au-dessus de 21 : gagné. Même total : égalité. Si le croupier a un blackjack d'entrée, la main s'arrête aussitôt.</li>
    </ol>
    <p>Pas de partage de paires (split) ni d'assurance, pour garder le jeu simple. Si quelqu'un traîne, l'animateur peut passer son tour (il reste sur sa main). On peut rejoindre la table à tout moment : on joue dès les mises suivantes.</p>`;
const BJ_RULES_DRINKS = `
    <h3>Mode gorgées 🍻</h3>
    <p>On ne mise pas de jetons mais des <b>gorgées</b>, de 1 jusqu'à la mise maximale choisie par l'animateur.</p>
    <ul>
      <li><b>Perdu</b> (ou plus de 21, ou blackjack du croupier) : tu <b>bois ta mise</b>.</li>
      <li><b>Gagné</b> : tu <b>distribues le double</b> de ta mise, à qui tu veux.</li>
      <li><b>Blackjack</b> : tu <b>distribues le triple</b>.</li>
      <li><b>Égalité</b> : personne ne boit.</li>
      <li><b>Doubler</b> double ta mise : perdu, tu bois le double ; gagné, tu distribues le quadruple. À toi de voir…</li>
    </ul>
    <p>Exemple : tu mises 2 gorgées. Perdu : tu bois 2. Gagné : tu en distribues 4. Blackjack : tu en distribues 6.</p>
    <p>Personne n'est obligé de boire de l'alcool : un verre d'eau compte aussi. Buvez avec modération !</p>`;
const CASINO_RULES_COMMON = `
    <h3>Le principe</h3>
    <p>Une roulette européenne : 37 cases, de 0 à 36 (18 rouges, 18 noires et le 0 vert). On mise sur le tapis, l'animateur lance la bille… et on regarde où elle tombe.</p>
    <h3>Un tour</h3>
    <ol>
      <li><b>Faites vos jeux</b> : choisis un jeton, puis touche une case du tapis. Tu peux miser sur plusieurs cases, et toucher plusieurs fois la même pour ajouter. « Effacer » retire toutes tes mises.</li>
      <li><b>Rien ne va plus</b> : l'animateur lance la bille. La roue tourne sur tous les téléphones et la bille s'arrête sur un numéro.</li>
      <li>Les mises sont réglées, et l'animateur lance le tour suivant.</li>
    </ol>
    <h3>Les mises</h3>
    <ul>
      <li><b>Plein</b> : un numéro (0 à 36).</li>
      <li><b>Douzaine</b> : 1-12, 13-24 ou 25-36.</li>
      <li><b>Chances simples</b> : rouge ou noir, pair ou impair, 1-18 (manque) ou 19-36 (passe).</li>
      <li>Quand le <b>0</b> sort, toutes les douzaines et chances simples perdent.</li>
    </ul>
    <p>Sur le tapis, ta mise est en doré ; les mises des autres joueurs en blanc. Les derniers numéros sortis s'affichent sous la roue.</p>`;
const CASINO_RULES_CHIPS = `
    <h3>Mode jetons</h3>
    <ul>
      <li>Chacun démarre avec <b>100 jetons</b>.</li>
      <li><b>Plein</b> gagnant : 35 fois la mise. <b>Douzaine</b> : 2 fois. <b>Chance simple</b> : 1 fois (la mise est rendue en plus).</li>
      <li>Plus de jetons ? « Recharger » redonne 100 jetons, et tout le monde voit les recharges…</li>
    </ul>`;
const CASINO_RULES_DRINKS = `
    <h3>Mode gorgées 🍻</h3>
    <p>On mise des <b>gorgées</b>, au total jusqu'à la mise maximale choisie par l'animateur pour chaque tour.</p>
    <ul>
      <li><b>Mise perdue</b> : tu bois les gorgées misées sur les cases perdantes.</li>
      <li><b>Chance simple gagnée</b> : tu distribues le <b>double</b> de ta mise.</li>
      <li><b>Douzaine gagnée</b> : tu distribues le <b>triple</b>.</li>
      <li><b>Plein gagné : JACKPOT</b>, tu distribues <b>10 fois</b> ta mise, à répartir comme tu veux.</li>
      <li><b>Le 0 sort</b> : la maison gagne, chaque joueur qui a misé boit <b>1 gorgée de plus</b>… sauf ceux qui avaient misé sur le 0.</li>
    </ul>
    <p>Exemple : 2 gorgées sur Rouge et 1 sur le 17. Le 17 (noir) sort : tu bois 2 (Rouge perdu) et tu distribues 10 (jackpot) !</p>
    <p>Personne n'est obligé de boire de l'alcool : un verre d'eau compte aussi. Buvez avec modération !</p>`;
const GAME_RULES = {
  neon: Neon.rules,
  island: Island.rules,
  heist: Heist.rules,
  president: President.rules,
  room: `
    <h3>Le principe</h3>
    <p>Une <b>salle de jeux</b> réunit tout le monde pour la soirée, avec <b>un seul code</b> (et un seul QR). On la rejoint une fois.</p>
    <h3>Pour l'animateur</h3>
    <p>Choisis un jeu dans la salle, règle ses options, puis <b>« Lancer pour toute la salle »</b> : chaque téléphone bascule tout seul dans le jeu, avec tous les joueurs déjà inscrits (y compris ceux sans téléphone).</p>
    <p>Quand le jeu est fini, <b>☰ → « Terminer ce jeu et revenir à la salle »</b> : tout le monde revient à la salle, prêt pour le suivant.</p>
    <h3>Le tableau de la soirée</h3>
    <p>Les points du Quiz et les gorgées de tous les jeux s'additionnent d'un jeu à l'autre.</p>
    <h3>Arriver en retard</h3>
    <p>Scanner le QR de la salle suffit : on rejoint la salle et le jeu en cours.</p>`,
  get biskit() { return bkRulesHtml(); },
  pyramid: `
    <h3>Le principe</h3>
    <p>Un jeu de cartes à boire, autour de la même table : chacun reçoit 4 cartes, les retourne face cachée… et doit s'en souvenir jusqu'au bout. Chaque téléphone montre la même partie.</p>
    <h3>1. La distribution</h3>
    <p>À tour de rôle, chacun répond à 4 questions et reçoit une carte à chaque fois :</p>
    <ol>
      <li><b>Rouge ou noir ?</b></li>
      <li><b>Plus ou moins</b> que ta 1re carte ?</li>
      <li><b>Dedans ou dehors</b> : entre tes 2 premières cartes, ou à l'extérieur ?</li>
      <li><b>Quel symbole</b> : ♠ ♥ ♦ ♣ ?</li>
    </ol>
    <p><b>Poteau !</b> Si tu reçois une carte de même valeur qu'une carte que tu as déjà (au bateau aussi) : en mode soft, <b>tout le monde boit 1 gorgée</b> ; en mode hard, <b>celui qui l'a tirée boit cul sec</b>.</p>
    <p>Raté : tu bois ; réussi : tu distribues. En mode <b>soft</b>, 1 gorgée à chaque carte ; en mode <b>hard</b>, 1, 2, 3 puis 4 gorgées selon le tour. Une égalité (même valeur, ou carte « sur le poteau ») compte comme ratée. <b>L'As est la carte la plus forte.</b> Ensuite, toutes les mains se retournent : <b>plus personne ne voit ses cartes</b>.</p>
    <h3>2. La pyramide</h3>
    <ul>
      <li>L'animateur retourne les cartes une par une, de la base vers le sommet. Étage 1 : 1 gorgée, étage 2 : 2 gorgées… (ou 2, 4, 6… si l'animateur a choisi les gorgées doublées).</li>
      <li>Si tu penses avoir la même valeur, touche <b>« Je donne N gorgées »</b> et distribue-les à voix haute (tu peux les partager). <b>Le bluff est permis !</b></li>
      <li>L'animateur tranche : <b>bu</b>, ou quelqu'un crie <b>« menteur ! »</b>. L'accusé retourne alors une de ses cartes : tout le monde la voit 3 secondes, puis elle se recache. « Il dit la vérité » ou « Bouuuh, menteur ! » : à vous de vous arranger pour les gorgées.</li>
      <li>Oublié tes cartes ? Demande à <b>en revoir</b> 1 à 4 (2 gorgées par carte) : l'animateur accepte et tu les vois 5 secondes, en privé.</li>
      <li><b>Le sommet, c'est cul sec</b>, sans bluff : annonce si tu as la carte. Si tu l'as, tu le sais en privé et tu distribues ton cul sec. Sinon, tout le monde le sait… et tu passes par la roulette du bateau.</li>
    </ul>
    <h3>3. Le test de mémoire</h3>
    <p>Chacun tape les valeurs de ses 4 cartes, de gauche à droite. L'app retourne les vraies cartes et compte les erreurs.</p>
    <h3>4. Le bateau</h3>
    <p>Si l'animateur a gardé le bateau : celui qui a fait le plus d'erreurs le fait (égalité, ou menteurs au sommet : la roulette décide). Il refait les 4 questions avec <b>un paquet neuf</b> : à chaque erreur, 1 gorgée et retour au début. Ça s'arrête quand il réussit les 4 d'affilée… ou quand le paquet est vide.</p>
    <h3>Arriver en cours de partie</h3>
    <p>Demande à rejoindre : l'animateur accepte, et tu fais ta propre distribution (les 4 questions), sous les yeux de tous. Puis tes cartes se retournent et la pyramide reprend. Après la pyramide, tu regardes la fin de la partie.</p>
    <h3>L'animateur</h3>
    <p>Il peut exclure un joueur à tout moment (✕, depuis la vue normale : touche ‹ en haut). Il distribue, retourne les cartes, valide « bu » ou « menteur », accepte les demandes pour revoir ses cartes, lance le test de mémoire et le bateau. Il peut répondre à la place d'un joueur (participant sans téléphone, ou qui a laissé son téléphone).</p>
    <p>Buvez avec modération : un verre d'eau compte aussi.</p>`,
  tmc: `
    <h3>Le principe</h3>
    <p>Qui te connaît le mieux ? À chaque tour, <b>deux joueurs</b> sont tirés au sort : l'un répond à une question sur lui-même, l'autre doit <b>deviner sa réponse</b>.</p>
    <h3>Un tour</h3>
    <ol>
      <li>Une question s'affiche, par exemple « Quelle est ta voiture de rêve ? ».</li>
      <li>La personne interrogée écrit <b>sa vraie réponse</b>, en secret : impossible de tricher ensuite.</li>
      <li>L'autre joueur du duo devine <b>à voix haute</b>.</li>
      <li>L'animateur révèle la réponse écrite sur tous les téléphones, puis attribue les points : <b>✅ 1 point</b>, <b>🤏 ½ point</b> ou <b>❌ 0</b>.</li>
      <li>L'animateur passe au duo suivant. L'app fait tourner les duos : chacun devine chacun, dans les deux sens, avant qu'un duo ne revienne.</li>
    </ol>
    <h3>Les points</h3>
    <ul>
      <li><b>Classement général</b> : les points de chaque joueur quand il devine.</li>
      <li><b>Tes amitiés</b> : qui tu connais le mieux, et qui te connaît le mieux (en % de bonnes réponses).</li>
      <li><b>Meilleurs duos</b> : les paires qui se connaissent le mieux dans les deux sens.</li>
    </ul>
    <p>Quand vous voulez, l'animateur termine la partie pour afficher le bilan. Pas de nombre de joueurs maximum (à partir de 2).</p>`,
  divan: `
    <h3>Le principe</h3>
    <p>Un jeu de cartes pour parler de soi : chacun passe à son tour <b>sur le divan</b> et répond à une question. Pas de points, pas de gagnant : juste de vraies conversations.</p>
    <h3>Une séance</h3>
    <ol>
      <li>L'animateur choisit les catégories et ouvre la séance.</li>
      <li>Une carte s'affiche sur tous les téléphones. La personne <b>sur le divan</b> y répond à voix haute, aussi longuement qu'elle le veut.</li>
      <li>Elle a <b>un joker par tour</b> : une autre carte si celle-ci ne lui parle pas.</li>
      <li>Les autres écoutent, peuvent poser une question de relance… et envoyer du <b>soutien ❤️</b>.</li>
      <li>« Au suivant » : le divan passe au joueur suivant, avec une nouvelle carte.</li>
      <li>Sur le téléphone de la personne sur le divan (et de l'animateur), on peut aussi <b>glisser la carte</b> : vers la gauche pour « Au suivant », vers la droite pour le joker.</li>
      <li>Erreur de manipulation ? « ↩︎ Retour » revient à la carte précédente (et à la personne précédente).</li>
    </ol>
    <h3>Les catégories</h3>
    <ul>
      <li><b>🌄 Expériences</b> : moments marquants, choix, fiertés, regrets.</li>
      <li><b>💗 Émotions</b> : ce qui te touche, te pèse ou te rend heureux.</li>
      <li><b>🤝 Relations</b> : amitié, amour, famille, les autres et toi.</li>
      <li><b>🧸 Enfance</b> : souvenirs, famille, l'enfant que tu étais.</li>
      <li><b>🌠 Rêves & avenir</b> : projets, envies, la personne que tu veux devenir.</li>
      <li><b>🔮 Et si…</b> : questions imaginaires (« Si tu pouvais… ») qui en disent long sur toi.</li>
      <li><b>💞 Mode couple</b> (à part, remplace les autres) : à deux ou entre couples. Votre histoire, vos souvenirs, et « devine comment l'autre réagirait ». Rien de gênant : « l'autre », c'est la personne avec qui tu es.</li>
    </ul>
    <h3>Les règles d'or</h3>
    <ul>
      <li><b>Bienveillance</b> : on écoute sans juger, sans se moquer, sans interrompre.</li>
      <li><b>Liberté</b> : on a toujours le droit de passer ou de rester en surface.</li>
      <li><b>Confidentialité</b> : ce qui se dit sur le divan reste sur le divan.</li>
    </ul>
    <p>C'est un jeu de discussion, pas une vraie thérapie : si un sujet réveille quelque chose de lourd, parles-en à un professionnel.</p>`,
  casino: CASINO_RULES_COMMON + CASINO_RULES_CHIPS + CASINO_RULES_DRINKS,
  blackjack: BJ_RULES_COMMON + `
    <h3>Mode jetons</h3>
    <ul>
      <li>Chacun commence avec <b>100 jetons</b> et mise de 5 jusqu'à tout son tapis.</li>
      <li>Gagné : tu touches 1 pour 1. <b>Blackjack</b> : 3 pour 2. Égalité : ta mise t'est rendue. Perdu : ta mise est perdue.</li>
      <li>Plus de jetons ? « Recharger » te redonne 100 jetons, et tout le monde voit combien de fois tu as rechargé…</li>
    </ul>` + BJ_RULES_DRINKS,
  roulette: `
    <h3>Le principe</h3>
    <p>Une roue avec des noms. On la lance, elle tourne… et celui sur qui elle s'arrête <b>a perdu</b>.</p>
    <h3>Comment jouer</h3>
    <ol>
      <li>L'animateur note les participants : en tapant leurs noms, ou en un geste avec « Ajouter les joueurs inscrits ». Il faut au moins 2 noms.</li>
      <li>Il lance la roue. Elle tourne en même temps sur tous les téléphones de la partie, et tout le monde voit le même résultat.</li>
      <li>Le nom désigné a perdu ! L'animateur peut le retirer de la roue pour un tirage par élimination, ou relancer tel quel.</li>
    </ol>
    <h3>Des idées</h3>
    <ul>
      <li>Qui boit (ou qui boit cul sec).</li>
      <li>Qui paie la prochaine tournée.</li>
      <li>Qui fait la vaisselle ou va chercher les pizzas.</li>
      <li>Qui choisit la prochaine musique, qui commence un jeu, qui relève un défi.</li>
    </ul>
    <p>Pas besoin d'être inscrit pour regarder : il suffit d'ouvrir la partie avec son code ou son QR. Les derniers perdants restent affichés.</p>`,
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
        <input id="gNameInput" class="grow" type="text" aria-label="Ton prénom" spellcheck="false" maxlength="30" placeholder="Ton prénom" autocomplete="given-name" required>
        <button>OK</button>
      </form>
    </div>

    <div id="gHome" class="hidden">
      <div class="g-hello">Salut <span id="gHello"></span></div>
      <h1 class="g-h1">On joue à quoi&nbsp;?</h1>
      <div id="gamesAdmin" class="admin-games hidden"></div>

      <form id="gJoinForm" class="g-code">
        <label for="gCode">Code d'une partie</label>
        <input id="gCode" type="text" spellcheck="false" inputmode="numeric" pattern="[0-9]*" maxlength="4" placeholder="• • • •" autocomplete="off">
      </form>

      <div class="gcard g-rm g-room-card">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.room}</div>
          <div class="g-meta"><div class="g-title">Salle de jeux</div><div class="g-tag">Un seul code pour toute la soirée.</div></div>
          ${helpBtn("room")}
        </div>
        <p class="g-desc">Tout le monde rejoint une fois. L'animateur lance les jeux les uns après les autres : chaque téléphone bascule tout seul, puis revient à la salle, avec le tableau de la soirée.</p>
        <div class="g-chips"><span>✨ Recommandé</span><span>Tous les jeux</span><span>Tableau de la soirée</span></div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="room">Ouvrir une salle</button>
      </div>
      <div class="g-sep"><span>ou une partie seule</span></div>

      <div class="gcard g-hs">
        <div class="g-head"><div class="g-icon">${GAME_ICONS.heist}</div><div class="g-meta"><div class="g-title">Braquage en miniature</div><div class="g-tag">Petits voleurs. Grand coup.</div></div>${helpBtn("heist")}</div>
        <p class="g-desc">Infiltre le musée, évite les gardiens et rapporte les trésors. En équipe, personne ne reste derrière les barreaux.</p>
        <div class="g-chips"><span>1–8 joueurs</span><span>3 musées en 3D</span><span>Solo ou coopération</span></div>
        <button class="g-go" data-create="heist">Préparer le braquage</button>
      </div>
      <div class="gcard g-is">
        <div class="g-head"><div class="g-icon">${GAME_ICONS.island}</div><div class="g-meta"><div class="g-title">L’île qui s’effondre</div><div class="g-tag">Un dernier saut. Un dernier survivant.</div></div>${helpBtn("island")}</div>
        <p class="g-desc">Une île tropicale en 3D qui tombe morceau par morceau. Saute au bon moment et reste au sec !</p>
        <div class="g-chips"><span>1–8 joueurs</span><span>Vraie 3D</span><span>Solo ou chacun pour soi</span></div>
        <button class="g-go" data-create="island">Explorer l’île</button>
      </div>
      <div class="gcard g-nk">
        <div class="g-head"><div class="g-icon">${GAME_ICONS.neon}</div><div class="g-meta"><div class="g-title">Néon Knockout</div><div class="g-tag">Charge. Vise. Éjecte.</div></div>${helpBtn("neon")}</div>
        <p class="g-desc">Une arène suspendue, un dash chargé et une bordure qui se referme. Reste debout, seul ou avec ton duo.</p>
        <div class="g-chips"><span>2–8 joueurs</span><span>Solo ou équipes de 2</span><span>Arcade tactile</span></div>
        <button class="g-go" data-create="neon">Ouvrir l’arène</button>
      </div>

      <div class="gcard g-pr">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.president}</div>
          <div class="g-meta"><div class="g-title">Président</div><div class="g-tag">… ou Trou du cul. À toi de jouer.</div></div>
          ${helpBtn("president")}
        </div>
        <p class="g-desc">Vide ta main avant les autres. Gagne ta place, échange tes cartes et défends la présidence à la manche suivante.</p>
        <div class="g-chips"><span>3 à 6 joueurs</span><span>54 cartes</span><span>Mains privées</span></div>
        <p class="g-desc">Un joker seul vaut un 3. Avec une autre carte, il la duplique.</p>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="president">Créer une table</button>
      </div>

      <div class="gcard g-qz">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.quiz}</div>
          <div class="g-meta"><div class="g-title">Quiz</div><div class="g-tag">Des milliers de questions, 14 thèmes.</div></div>
          ${helpBtn("quiz")}
        </div>
        <p class="g-desc">Culture générale, géo, histoire, sciences, cinéma, musique, sport, Suisse… Classique, Rapidité, Survie, Contre-la-montre ou Paliers : seul ou à plusieurs, avec un classement général entre les parties.</p>
        <div class="g-chips"><span>Solo ou 2+ joueurs</span><span>5 modes</span><span>Classement général</span></div>
        <label class="g-opt"><span>🍻 Une erreur = une gorgée</span><input type="checkbox" class="switch" data-opt="qzsips"></label>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="quiz">Créer un quiz</button>
      </div>

      <div class="gcard g-pu">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.purity}</div>
          <div class="g-meta"><div class="g-title">Purify Test</div><div class="g-tag">Qui est le plus pur de la soirée ?</div></div>
          ${helpBtn("purity")}
        </div>
        <p class="g-desc">Le vrai test de pureté : 100 questions sans filtre (sexe, alcool, drogues, infractions…). Chacun répond en secret ; à la fin, le classement du plus pur au plus sulfureux et ton profil par catégorie. Personne ne voit tes réponses.</p>
        <div class="g-chips"><span>🔞 Adultes</span><span>🔒 Compte connecté</span><span>Réponses secrètes</span><span>Radar par catégorie</span></div>
        <label class="g-opt"><span>🍻 Le plus sulfureux boit</span><input type="checkbox" class="switch" data-opt="pualcohol"></label>
        <div class="g-modes" data-opt-group="pusips">
          <button type="button" data-val="1">1 gorgée</button><button type="button" data-val="2" class="on">2</button><button type="button" data-val="3">3</button><button type="button" data-val="5">5</button>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="purity">Lancer le test</button>
      </div>

      <div class="gcard g-uc">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.undercover}</div>
          <div class="g-meta"><div class="g-title">Undercover</div><div class="g-tag">Trouve l'intrus avant qu'il ne te trouve.</div></div>
          ${helpBtn("undercover")}
        </div>
        <p class="g-desc">Chacun reçoit un mot secret. Les undercovers ont un mot proche, Mr. White n'en a pas. Indices à voix haute, puis on vote pour éliminer.</p>
        <div class="g-chips"><span>3+ joueurs</span><span>Mot secret</span><span>Bluff</span></div>
        <label class="g-opt"><span>Avec Mr. White <small>dès 5 joueurs</small></span><input type="checkbox" class="switch" data-opt="white" checked></label>
        <div class="g-label">Imposteurs</div>
        <div class="g-modes" data-opt-group="impostors">
          <button type="button" data-val="0" class="on">Auto</button><button type="button" data-val="1">1</button><button type="button" data-val="2">2</button><button type="button" data-val="3">3</button>
        </div>
        <label class="g-opt"><span>Les imposteurs savent qu'ils le sont <small>sinon chacun le devine en écoutant</small></span><input type="checkbox" class="switch" data-opt="reveal"></label>
        <label class="g-opt"><span>💡 Indice pour Mr. White <small>la catégorie du mot : « un fruit », « un sport »…</small></span><input type="checkbox" class="switch" data-opt="white_hint"></label>
        <label class="g-opt"><span>💡 Indice pour les imposteurs <small>seulement s'ils savent qu'ils le sont</small></span><input type="checkbox" class="switch" data-opt="hint"></label>
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

      <div class="gcard g-lk">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.likely}</div>
          <div class="g-meta"><div class="g-title">Qui est le plus…&nbsp;?</div><div class="g-tag">Chacun vote sur son téléphone. Tout le monde joue.</div></div>
          ${helpBtn("likely")}
        </div>
        <p class="g-desc">« Qui est le plus mauvais perdant ? » Tout le monde désigne quelqu'un en secret, en même temps, puis on découvre le plus désigné : il prend un point… ou une petite gorgée. Sans téléphone ? On vote sur celui de l'animateur.</p>
        <div class="g-chips"><span>👨‍👩‍👧 Avec les parents aussi</span><span>2+ joueurs</span><span>Sans téléphone : OK</span><span>365 questions</span></div>
        <label class="g-opt"><span>😏 Paquet « Entre amis » <small>en plus : soirées, ex, petits secrets (jamais sexuel)</small></span><input type="checkbox" class="switch" data-opt="lkfriends"></label>
        <label class="g-opt"><span>🍻 Le plus désigné boit <small>sinon il prend un point</small></span><input type="checkbox" class="switch" data-opt="lkalcohol"></label>
        <div class="g-modes" data-opt-group="lksips">
          <button type="button" data-val="1" class="on">1 gorgée</button><button type="button" data-val="2">2</button><button type="button" data-val="3">3</button>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="likely">Créer une partie</button>
      </div>

      <div class="gcard g-db">
        ${newBadge("debate")}
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.debate}</div>
          <div class="g-meta"><div class="g-title">Pour ou contre</div><div class="g-tag">Un dilemme, vos avis, un vrai débat.</div></div>
          ${helpBtn("debate")}
        </div>
        <p class="g-desc">« Faut-il dire à un ami que son ou sa partenaire le trompe ? » Chacun se place en secret de « Totalement contre » à « Totalement pour », on découvre la répartition, puis on en parle. Après le débat, on peut revoter pour voir qui a changé d'avis.</p>
        <div class="g-chips"><span>2+ joueurs</span><span>Sans alcool</span><span>Sans téléphone : OK</span><span>540 dilemmes + les vôtres</span></div>
        <div class="g-label">Thèmes</div>
        <div class="g-modes" data-opt-group="cats">
          <button type="button" data-val="moral" class="on">⚖️ Morale</button><button type="button" data-val="society" class="on">🏛️ Société</button>
          <button type="button" data-val="relations" class="on">💞 Relations</button><button type="button" data-val="light" class="on">🍍 Léger</button>
          <button type="button" data-val="wtf">🤪 WTF 🔞</button>
        </div>
        <label class="g-opt"><span>👀 Prénoms affichés à la révélation <small>sinon les votes restent anonymes</small></span><input type="checkbox" class="switch" data-opt="dbpublic"></label>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="debate">Créer une partie</button>
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

      <div class="gcard g-rl">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.roulette}</div>
          <div class="g-meta"><div class="g-title">Roulette</div><div class="g-tag">La roue a parlé.</div></div>
          ${helpBtn("roulette")}
        </div>
        <p class="g-desc">Note les participants, lance la roue : celui qu'elle désigne a perdu. Pour savoir qui boit, qui paie la tournée, qui fait la vaisselle… La roue tourne sur tous les téléphones.</p>
        <div class="g-chips"><span>2+ noms</span><span>Hasard</span><span>Pour tout trancher</span></div>
        <button class="g-go" data-create="roulette">Créer une roulette</button>
      </div>

      <div class="gcard g-bk">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.biskit}</div>
          <div class="g-meta"><div class="g-title">Biskit Royal</div><div class="g-tag">Chaque carte a son effet. Le Roi a sa coupe.</div></div>
          ${helpBtn("biskit")}
        </div>
        <p class="g-desc">Le Roi des cartes et les dés du Biskit réunis : tire une carte, rouge ou noire, chacune a son effet (cascade, duel, potes de boisson, règles inventées, réflexes…). Le 4e Roi boit la coupe !</p>
        <div class="g-chips"><span>2+ joueurs, même table</span><span>52 cartes + dés</span><span>Plein écran</span></div>
        <label class="g-opt"><span>🍻 Avec alcool <small>sinon des points de gage</small></span><input type="checkbox" class="switch" data-opt="bkalcohol" checked></label>
        <div class="g-label">Gorgées</div>
        <div class="g-modes" data-opt-group="bkmult">
          <button type="button" data-val="1" class="on">×1 · normal</button><button type="button" data-val="2">×2 · hard</button>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="biskit">Ouvrir la table</button>
      </div>

      <div class="gcard g-py">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.pyramid}</div>
          <div class="g-meta"><div class="g-title">Pyramide</div><div class="g-tag">Mémoire, bluff… et cul sec.</div></div>
          ${helpBtn("pyramid")}
        </div>
        <p class="g-desc">Rouge ou noir, plus ou moins, dedans ou dehors, symbole : 4 cartes chacun, puis on les retourne face cachée. La pyramide se dévoile, on donne des gorgées (bluff permis !), cul sec au sommet… et celui qui a la pire mémoire fait le bateau.</p>
        <div class="g-chips"><span>2+ joueurs, même table</span><span>Plein écran</span><span>Bluff</span></div>
        <div class="g-label">Gorgées à la distribution</div>
        <div class="g-modes" data-opt-group="pmode">
          <button type="button" data-val="soft" class="on">😇 Soft · 1 par carte</button><button type="button" data-val="hard">🔥 Hard · 1, 2, 3, 4</button>
        </div>
        <div class="g-label">Poteau (deux fois la même carte)</div>
        <div class="g-modes" data-opt-group="poteau">
          <button type="button" data-val="soft" class="on">😇 Tout le monde boit 1</button><button type="button" data-val="hard">🥃 Le tireur boit cul sec</button>
        </div>
        <div class="g-label">Gorgées par étage de la pyramide</div>
        <div class="g-modes" data-opt-group="floorsips">
          <button type="button" data-val="1" class="on">1, 2, 3, 4…</button><button type="button" data-val="2">2, 4, 6, 8…</button>
        </div>
        <label class="g-opt"><span>🚢 Avec le bateau <small>pour celui qui a la pire mémoire</small></span><input type="checkbox" class="switch" data-opt="boat" checked></label>
        <div class="g-opt"><span>Étages de la pyramide <small>5 étages : 9 joueurs max · 8 étages : 4 joueurs max</small></span>
          <div class="g-stepper" data-opt-group="floors"><button type="button" data-step="-1" aria-label="Moins">−</button><b data-val-out>5</b><button type="button" data-step="1" aria-label="Plus">+</button></div>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="pyramid">Ouvrir la table</button>
      </div>

      <div class="gcard g-tm">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.tmc}</div>
          <div class="g-meta"><div class="g-title">Tu me connais ?</div><div class="g-tag">Qui te connaît le mieux ?</div></div>
          ${helpBtn("tmc")}
        </div>
        <p class="g-desc">Deux joueurs sont tirés au sort : l'un écrit en secret sa réponse à une question sur lui, l'autre la devine à voix haute. Points au classement général… et par duo, pour savoir qui connaît le mieux qui.</p>
        <div class="g-chips"><span>2+ joueurs</span><span>334 questions</span><span>Points d'amitié</span></div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="tmc">Créer une partie</button>
      </div>

      <div class="gcard g-dv">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.divan}</div>
          <div class="g-meta"><div class="g-title">Le Divan</div><div class="g-tag">Des cartes pour parler vrai.</div></div>
          ${helpBtn("divan")}
        </div>
        <p class="g-desc">Chacun passe à son tour sur le divan : une carte est tirée et tu y réponds à voix haute. Souvenirs, émotions, relations, enfance, rêves, « et si… » et un mode couple pour (re)découvrir l'autre. Pour se découvrir autrement, avec bienveillance.</p>
        <div class="g-chips"><span>2+ joueurs</span><span>7 000 cartes</span><span>Sans alcool</span></div>
        <div class="g-label">Catégories</div>
        <div class="g-modes dv-cats" data-opt-group="cats">
          <button type="button" data-val="experiences" class="on">🌄 Expériences</button><button type="button" data-val="emotions" class="on">💗 Émotions</button>
          <button type="button" data-val="relations" class="on">🤝 Relations</button><button type="button" data-val="childhood" class="on">🧸 Enfance</button>
          <button type="button" data-val="dreams" class="on">🌠 Rêves & avenir</button><button type="button" data-val="whatif" class="on">🔮 Et si…</button>
          <button type="button" data-val="couple">💞 Mode couple</button>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="divan">Ouvrir une séance</button>
      </div>

      <div class="gcard g-cs">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.casino}</div>
          <div class="g-meta"><div class="g-title">Casino</div><div class="g-tag">Faites vos jeux, rien ne va plus !</div></div>
          ${helpBtn("casino")}
        </div>
        <p class="g-desc">Une vraie roulette européenne : chacun mise sur le tapis (numéro, rouge ou noir, pair ou impair, douzaines…), l'animateur lance la bille, et la roue tourne sur tous les téléphones.</p>
        <div class="g-chips"><span>1+ joueur</span><span>Plein ×35</span><span>Jetons ou gorgées</span></div>
        <label class="g-opt"><span>🍻 Alcool : on mise des gorgées <small>perdu : tu bois · gagné : tu distribues</small></span><input type="checkbox" class="switch" data-opt="alcohol"></label>
        <div class="g-opt" data-alcohol-only hidden><span>Mise maximale <small>en gorgées, par tour</small></span>
          <div class="g-stepper" data-opt-group="sips"><button type="button" data-step="-1" aria-label="Moins">−</button><b data-val-out>3</b><button type="button" data-step="1" aria-label="Plus">+</button></div>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="casino">Ouvrir la table</button>
      </div>

      <div class="gcard g-bj">
        <div class="g-head">
          <div class="g-icon">${GAME_ICONS.blackjack}</div>
          <div class="g-meta"><div class="g-title">Blackjack</div><div class="g-tag">Approche-toi de 21 sans le dépasser.</div></div>
          ${helpBtn("blackjack")}
        </div>
        <p class="g-desc">Tout le monde joue contre le croupier (l'app) : on mise, puis on tire des cartes ou on reste. Avec des jetons (100 au départ), ou avec des gorgées : perdu, tu bois ta mise ; gagné, tu distribues le double ; blackjack, le triple.</p>
        <div class="g-chips"><span>1+ joueur</span><span>Jetons ou gorgées</span><span>Contre le croupier</span></div>
        <label class="g-opt"><span>🍻 Alcool : on mise des gorgées <small>sinon, des jetons</small></span><input type="checkbox" class="switch" data-opt="alcohol"></label>
        <div class="g-opt" data-alcohol-only hidden><span>Mise maximale <small>en gorgées, par main</small></span>
          <div class="g-stepper" data-opt-group="sips"><button type="button" data-step="-1" aria-label="Moins">−</button><b data-val-out>3</b><button type="button" data-step="1" aria-label="Plus">+</button></div>
        </div>
        <label class="g-opt"><span>Je joue aussi</span><input type="checkbox" class="switch" data-opt="plays" checked></label>
        <button class="g-go" data-create="blackjack">Ouvrir une table</button>
      </div>
    </div>

    <div id="gamePlay" class="hidden">
      <div id="gTop" class="g-top"></div>
      <div id="gameHud" class="g-hud hidden" aria-live="polite"></div>
      <div id="game" class="card game"></div>
      <div id="casinoWheel" class="cwheel hidden">
        <div class="cw-wrap">
          <svg id="cwSvg" viewBox="-110 -110 220 220" role="img" aria-label="Roulette"></svg>
          <div class="cw-orbit" id="cwOrbit"><div class="cw-ball" id="cwBall"></div></div>
        </div>
        <div id="cwResult" class="cw-result" aria-live="polite"></div>
        <div id="cwHistory" class="cw-history"></div>
      </div>
      <div id="roulette" class="roulette hidden">
        <div class="wheel-wrap"><div class="wheel-pointer" aria-hidden="true"></div><svg id="wheel" viewBox="-100 -100 200 200" role="img" aria-label="Roue"></svg></div>
        <div id="rouletteResult" class="roulette-result" aria-live="polite"></div>
      </div>
      <div id="gameHost"></div>
    </div>

    <aside id="gDrawer" class="g-drawer hidden" aria-label="Menu de la partie" data-nav="drawer" data-nav-surface=".g-drawer-panel" data-nav-close="[data-gdrawer=close]">
      <div class="g-drawer-panel" role="dialog" aria-modal="true" aria-labelledby="gDrawerTitle">
        <div class="g-drawer-head"><b id="gDrawerTitle">Menu de la partie</b>
          <button type="button" class="py-icon g-close" data-gdrawer="close" aria-label="Fermer le menu"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg></button></div>
        <div class="card" id="gameInvite" style="text-align:center">
          <div class="artist">Pour rejoindre : scanne ce QR ou entre le code</div>
          <div class="big-pin" id="gameCode"></div>
          <img class="qr" id="gameQr" width="220" height="220" alt="QR code pour rejoindre la partie">
        </div>
        <div id="gDrawerPlayers"></div>
        <button type="button" class="secondary g-drawer-min" data-gdrawer="minimize" aria-label="Réduire le jeu et revenir aux onglets"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>Réduire le jeu</button>
        <div id="gDrawerExit"></div>
      </div>
    </aside>

    <div id="rulesModal" class="g-modal hidden" role="dialog" aria-modal="true" aria-labelledby="rulesTitle" data-nav="sheet" data-nav-surface=".g-sheet" data-nav-close="[data-rules-close]">
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
// Range les cartes de l'accueil par catégorie (une section titrée par catégorie, sous la carte de la salle de jeux).
(function groupHomeCards() {
  const home = document.getElementById("gHome");
  let after = home.querySelector(".g-room-card");
  for (const [id, label, types] of GAME_CATEGORIES) {
    const sec = document.createElement("section");
    sec.className = "g-cat";
    sec.dataset.cat = id;
    sec.setAttribute("aria-labelledby", `gCat-${id}`);
    sec.innerHTML = `<h2 class="g-cat-h" id="gCat-${id}">${label}</h2>`;
    for (const type of types) {
      const card = home.querySelector(`[data-create="${type}"]`)?.closest(".gcard");
      if (!card) continue;
      card.querySelector(".g-title")?.insertAdjacentHTML("beforeend", drinkTag(type));
      sec.append(card);
    }
    after.after(sec);
    after = sec;
  }
})();

// 🎮 Jeux : n'importe qui crée une partie (code + QR) et l'anime ; les autres la rejoignent avec son code.
let myRoom = store("vp_room") || "";
// Salle de jeux : si l'animateur a lancé un jeu, on y bascule tout seul ; true si on a changé de partie.
function routeRoom(g) {
  if (g?.type === "room") {
    myRoom = g.code; store("vp_room", g.code);
    const cur = g.room_info?.current;
    if (cur && (g.me || g.is_host)) { setGame(cur.code); refreshGame(); return true; }
  } else if (g?.room) { myRoom = g.room; store("vp_room", g.room); }
  return false;
}
let myGame = store("vp_game") || "", game = null, wordShown = "", wordUntil = 0, guessDraft = "", showRoles = false, autoJoin = false;
const GAME_PHASES = { countdown: "Départ imminent", lobby: "Inscriptions", words: "Indices", vote: "Vote", white_guess: "Devinette de Mr. White",
  reveal: "Résultat de la manche", end: "Partie terminée", question: "Question", results: "Résultats", spun: "Résultat", bet: "Mises", play: "Partie", card: "En séance",
  answer: "Réponse en secret", guess: "À voix haute", judge: "Points", scored: "Résultat du duo", q: "Question", rev: "Réponse", run: "En jeu" };
const phaseLabel = (g) => (g.type === "roulette" || isBJ(g) || g.type === "casino") && g.phase === "lobby" ? "Préparation"
  : g.type === "president" && g.phase === "exchange" ? "Échange des cartes"
  : g.type === "president" && g.phase === "end" ? "Classement"
  : g.type === "casino" && g.phase === "bet" ? "Faites vos jeux" : GAME_PHASES[g.phase];
const WINNERS = { civils: "Les civils ont gagné 🎉", impostors: "Les undercovers ont gagné 🕵️", white: "Mr. White a trouvé le mot et gagne 🎩" };

async function gapi(path, body) {
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: controller.signal } : {signal: controller.signal});
    const data = await r.json().catch(e => { if (e.name === "AbortError") throw e; return null; });
    if (!r.ok) {
      const e = new Error(typeof data?.detail === "string" ? data.detail : data?.detail?.message || "Erreur");
      e.status = r.status; e.detail = data?.detail;
      throw e;
    }
    return data;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("Le serveur ne répond pas. Réessaie dans un instant.");
    throw e;
  } finally { clearTimeout(timeout); }
}

function setGame(code) {
  // Une nouvelle partie (créée, rejointe par code ou par QR) s'ouvre toujours en plein écran.
  if (code && code !== myGame) pyrFull = true;
  if (code !== myGame) gSeq++;
  myGame = code; store("vp_game", code); $("gameDot")?.classList.toggle("hidden", !code);
  if (!code) syncGameChrome();
}
// ── Plein écran / mini-barre (comme le mini-lecteur d'Apple Music) ──
// Plein écran : une partie est ouverte, non réduite, et l'onglet Jeux est affiché.
// Sinon, tant qu'une partie est en cours, une mini-barre flottante permet d'y revenir depuis n'importe quel onglet.
const gamesTabShown = () => !document.querySelector('[data-view="games"]')?.classList.contains("hidden");
function goGamesTab() {
  if (typeof showTab === "function") showTab("games");
  else if (typeof showView === "function") showView("games");
}
function syncGameChrome() {
  const g = myGame ? game : null;
  const full = !!g && pyrFull && gamesTabShown();
  document.body.classList.toggle("pyr-full", full);
  if (full && !document.body.classList.contains("g-leave")) window.Nav?.open({ key: "game", kind: "sheet", el: $("gamePlay"), surface: $("gamePlay"), handle: "#gTop",
    selfAnimated: true, close: minimizeGame });
  else window.Nav?.closed("game");
  let mini = $("gMini");
  if (!mini) {
    mini = document.createElement("button");
    mini.type = "button"; mini.id = "gMini"; mini.className = "g-mini hidden";
    mini.setAttribute("aria-label", "Reprendre la partie en plein écran");
    mini.addEventListener("click", () => openGameFull());
    document.body.append(mini);
  }
  const show = !!g && !full;
  mini.classList.toggle("hidden", !show);
  document.body.classList.toggle("has-mini", show);
  if (show) {
    const phase = g.type === "pyramid" && g.pyr ? pyrPhase(g) : phaseLabel(g);
    mini.className = "g-mini " + (GAME_THEME[g.type] || "");
    mini.innerHTML = `<span class="g-mini-ico" aria-hidden="true">${GAME_ICONS[g.type] || "🎮"}</span>
      <span class="g-mini-txt"><b>${esc(g.name)}</b><small>${esc(phase || "")} · code ${esc(g.code)}</small></span>
      <span class="g-mini-go">Reprendre ⌃</span>`;
  }
}
// Reprendre : le jeu « ressort » de la mini-barre (même chemin que pour s'y réduire).
function openGameFull() {
  pyrFull = true;
  if (!gamesTabShown()) goGamesTab();
  document.body.classList.add("g-enter");
  setTimeout(() => document.body.classList.remove("g-enter"), 500);
  if (game) renderGame(game); else syncGameChrome();
}
// Réduire : le jeu se replie vers la mini-barre, puis on retrouve les onglets (musique, etc.).
function minimizeGame() {
  closeDrawer?.();
  document.body.classList.add("g-leave");
  setTimeout(() => {
    document.body.classList.remove("g-leave");
    pyrFull = false;
    if (game) renderGame(game); else syncGameChrome();
  }, 260);
}
// Changement d'onglet (page invités ou admin) : on remet le plein écran / la mini-barre à jour.
document.addEventListener("click", (ev) => { if (ev.target.closest("button[data-tab]")) setTimeout(syncGameChrome, 0); });

let gSeq = 0;  // numéro du dernier chargement de la partie demandé
async function refreshGame() {
  $("gName").classList.toggle("hidden", !!guestName);
  if (!guestName) {
    $("gHome").classList.add("hidden"); $("gamePlay").classList.add("hidden");
    if (typeof maybeInstallSheet === "function") maybeInstallSheet();
    return;
  }
  $("gHello").textContent = guestName;
  if (!myGame) return renderGame(null);
  const seq = ++gSeq, code = myGame;
  try {
    const g = await gapi(`/api/games/${myGame}?guest_id=${encodeURIComponent(guestId)}&name=${encodeURIComponent(guestName)}`);
    // Deux rechargements presque simultanés : une réponse plus ancienne n'écrase jamais une plus récente.
    if (seq !== gSeq || code !== myGame) return;
    // Lien ou QR d'une partie : on rejoint une seule fois (déjà inscrit ou retiré par l'animateur : on ne réessaie pas).
    // L'admin (droits d'animateur) qui rejoint par le code devient joueur ; seul le créateur « maître du jeu » ne l'est pas.
    if (autoJoin && (g.me || g.is_owner || g.kicked)) autoJoin = false;
    if (autoJoin && !g.me && !g.is_owner) { autoJoin = false; return gameAction("join"); }
    if (routeRoom(g)) return;
    renderGame(g);
  } catch (e) {
    if (seq !== gSeq || code !== myGame) return;
    // Partie introuvable, ou erreur du serveur : on revient à l'accueil des jeux plutôt que de rester sur une page vide.
    if (e.status === 404) {
      // Jeu terminé dans une salle : tout le monde revient à la salle.
      const back = e.detail?.ended?.room || (myRoom && myGame !== myRoom ? myRoom : "");
      if (back) { setGame(back); toast("🏠 Retour à la salle", "ok"); return refreshGame(); }
      if (myRoom && myRoom === myGame) { myRoom = ""; store("vp_room", ""); }
      setGame("");
      if (e.detail?.ended) showGameEnded(e.detail.ended);
      else toast("Cette partie n'existe plus", "err");
    }
    else if (!game) toast("Impossible de charger la partie, réessaie", "err");
    if (e.status === 404 || !game) renderGame(null);
  }
}

// ⏱ Durée de la partie : « 4:07 », ou « 1:02:33 » au-delà d'une heure.
function fmtDuration(sec) {
  const t = Math.max(0, Math.floor(sec || 0)), h = Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = String(t % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}
let gameT0 = 0;  // début de la partie, sur l'horloge de ce téléphone
setInterval(() => { if (game && $("gTimer")) $("gTimer").textContent = fmtDuration(Date.now() / 1000 - gameT0); }, 1000);

// Pas de nouveau rendu si l'écran est identique : plus de clignotement ni d'animation rejouée à chaque mise à jour.
// Met à jour un élément vers un nouveau HTML en ne modifiant que ce qui diffère : les nœuds identiques restent
// en place (pas de flash, pas d'appui perdu, champ en cours de saisie conservé). data-key différent = nœud remplacé.
function morph(el, html) {
  const tpl = document.createElement("template");
  tpl.innerHTML = html;
  morphKids(el, tpl.content);
}
function morphKids(a, b) {
  const an = [...a.childNodes], bn = [...b.childNodes];
  bn.forEach((y, i) => {
    const x = an[i];
    if (!x) a.appendChild(y);
    else if (x.nodeType !== y.nodeType || x.nodeName !== y.nodeName
      || (x.nodeType === 1 && x.getAttribute("data-key") !== y.getAttribute("data-key"))) a.replaceChild(y, x);
    else morphNode(x, y);
  });
  for (let i = bn.length; i < an.length; i++) an[i].remove();
}
function morphNode(x, y) {
  if (x.nodeType !== 1) { if (x.nodeValue !== y.nodeValue) x.nodeValue = y.nodeValue; return; }
  if (x.isEqualNode(y)) return;
  const field = /^(INPUT|TEXTAREA|SELECT)$/.test(x.nodeName);
  for (const { name } of [...x.attributes]) if (!y.hasAttribute(name) && !(field && name === "value")) x.removeAttribute(name);
  for (const { name, value } of [...y.attributes]) if (x.getAttribute(name) !== value && !(field && name === "value")) x.setAttribute(name, value);
  if (!field) morphKids(x, y);
}
const QUESTION_TYPES = ["whoof", "never"];  // jeux à questions (« Qui de nous ? », « Je n'ai jamais »)
// Raccourci : patch.gameHost = html  ⇔  morph($("gameHost"), html)
const patch = new Proxy({}, { set(_, id, html) { morph($(id), html); return true; } });
// Retiré de la partie par l'animateur ou l'admin : message 5 secondes, puis retour à l'accueil des jeux.
let kickTimer = 0, kickCode = "";
function renderKicked(g) {
  $("gTop").innerHTML = gameTopBar(g);
  patch.gameHost = ""; patch.gameHud = "";
  const code = myGame;
  if (kickCode !== code) {
    kickCode = code;
    clearInterval(kickTimer);
    const until = Date.now() + 5000;
    kickTimer = setInterval(() => {
      const left = Math.ceil((until - Date.now()) / 1000);
      if (left > 0 && myGame === code) { if ($("kickLeft")) $("kickLeft").textContent = left; return; }
      clearInterval(kickTimer); kickCode = "";
      if (myGame !== code) return;  // déjà parti ailleurs entre-temps
      myRoom = ""; store("vp_room", "");
      closeDrawer(); setGame(""); renderGame(null);
    }, 250);
    haptic([80, 60, 80]);
  }
  setGameHtml(`<div class="kicked" role="alert">
    <div class="kicked-ico" aria-hidden="true">${g.kicked ? "🚫" : "👋"}</div>
    <div class="kicked-t">${g.kicked ? "Tu as été banni·e de" : "L'animateur t'a retiré·e de"} ${g.type === "room" ? "la salle" : "la partie"}</div>
    <p class="kicked-s">${g.kicked ? "Tu ne peux plus la rejoindre avec ce code." : `Tu pourras la rejoindre à nouveau avec le code <b>${esc(g.room || g.code)}</b>.`}</p>
    <p class="kicked-s">Retour à l'accueil dans <b id="kickLeft">5</b> s</p>
    <button type="button" class="secondary" data-exit="away">Revenir maintenant</button>
  </div>`);
}
function setGameHtml(html) {
  const el = $("game");
  if (el.dataset.html === html && el.firstChild) return false;
  el.innerHTML = html;
  el.dataset.html = html;
  return true;
}
function renderGame(g) {
  if (dvDrag && g) { dvPending = g; return; }  // pas de rafraîchissement pendant qu'on tient la carte
  if (g && g !== game) gameT0 = Date.now() / 1000 - (g.elapsed || 0);  // recalé à chaque réponse du serveur
  if (g?.type !== "neon" || !pyrFull || g.kicked || g.excluded) Neon.stop();
  if (g?.type !== "heist" || !pyrFull || g.kicked || g.excluded) Heist.stop();
  if (g?.type !== "island" || !pyrFull || g.kicked || g.excluded) Island.stop();
  game = g;
  GameAudio.observe(g, g ? myTurnKey(g) : "");
  $("gHome").classList.toggle("hidden", !!g);
  $("gamePlay").classList.toggle("hidden", !g);
  // Un jeu se joue toujours en plein écran ; « Réduire » (menu) revient aux onglets sans quitter la partie.
  syncGameChrome();
  if (!g) { closeDrawer(); return; }
  const me = g.me;
  const nameOf = (pid) => esc(g.players.find((p) => p.pid === pid)?.name || "?");
  $("game").className = "card game " + (GAME_THEME[g.type] || "");
  if (g.me || g.is_owner || g.kicked) autoJoin = false;  // déjà dans la partie (ou banni) : plus de « rejoindre » automatique
  if (g.kicked || (g.excluded && !autoJoin)) return renderKicked(g);
  renderCasino(g);  // avant le texte : il dépend de l'état de la bille (en train de rouler ou arrêtée)
  const title = `<div class="g-head g-play-head"><div class="g-icon">${GAME_ICONS[g.type] || ""}</div>
    <div class="g-meta"><div class="g-title">${esc(g.name)}</div>
    <div class="g-tag">${g.mode ? esc(g.mode) + " · " : ""}${phaseLabel(g)}${g.round && g.phase !== "lobby" ? ` · ${{ undercover: "manche", roulette: "tirage", blackjack: "main", casino: "tour", divan: "carte", tmc: "duo" }[g.type] || "question"} ${g.round}` : ""} · ⏱ <span id="gTimer">${fmtDuration(g.elapsed)}</span></div></div>
    ${helpBtn(g.type, true)}</div>`;
  const lastLine = g.last?.name ? `<p class="sub" style="margin:8px 0">${esc(g.last.name)} était <b>${esc(g.last.role)}</b>.${g.last.guess ? ` Mr. White a proposé « ${esc(g.last.guess)} »… raté !` : ""}</p>` : "";
  let body = "";

  if (g.type === "room") {
    body = roomHtml(g);
  } else if (g.type === "president") {
    body = President.html(g);
  } else if (g.type === "purity") {
    body = purityHtml(g);
  } else if (g.type === "divan") {
    body = divanHtml(g);
  } else if (g.type === "tmc" && g.phase !== "lobby" && (me || g.master) && !g.kicked) {
    body = tmcHtml(g);
  } else if (g.type === "casino") {
    body = casinoStatusHtml(g);
  } else if (isBJ(g)) {
    body = bjTableHtml(g);
  } else if (g.type === "roulette") {
    body = g.is_host
      ? `<div class="artist">${g.names.length < 2 ? "Note au moins 2 noms ci-dessous, puis lance la roue." : "Prêt ? Lance la roue !"}</div>`
      : `<div class="artist">${g.phase === "spun" ? "La roue a parlé…" : `${esc(g.host_name)} prépare la roue…`}</div>
         ${!me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:10px">Je participe (l'animateur pourra m'ajouter à la roue)</button>` : ""}`;
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
    const hint = me?.hint ? `<div class="artist" style="margin-top:6px">💡 Indice : c'est ${esc(me.hint)}</div>` : "";
    const secret = me?.role === "Mr. White" ? `<div class="word">🎩 Tu es Mr. White</div><div class="artist">Tu n'as pas de mot : écoute les autres et bluffe !</div>${hint}`
      : me?.role === "Undercover" ? `<div class="word">🕵️ Tu es imposteur</div><div class="artist">Ton mot : <b>${esc(me?.word)}</b> · celui des civils est proche. Fonds-toi dans la masse !</div>${hint}`
      : `<div class="artist">Ton mot</div><div class="word">${esc(me?.word)}</div>`;
    const wordBox = !me?.dealt ? "" : wordShown === key && Date.now() < wordUntil
      ? `<button type="button" data-gact="hide" class="secret">${secret}<div class="artist" style="margin-top:4px">Se cache dans <b id="wordCountdown">${Math.ceil((wordUntil - Date.now()) / 1000)}</b> s · touche pour cacher</div></button>`
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
           <form data-gform="guess" class="row" style="margin-top:8px"><input class="grow" type="text" id="guessInput" maxlength="40" aria-label="Le mot des civils" placeholder="Le mot des civils…" autocomplete="off"><button>Valider</button></form>`
        : `<div class="title">${esc(g.last.name)} était Mr. White !</div><div class="artist">Il tente de deviner le mot des civils…</div>`;
    } else if (g.phase === "reveal") {
      body = `${lastLine}<div class="artist">${g.is_host ? "Lance la manche suivante quand vous êtes prêts." : "L'animateur lance la manche suivante…"}</div>`;
    }
  } else if (g.phase === "question" && QUESTION_TYPES.includes(g.type)) {
    body = questionHtml(g, me);
  } else if (g.phase === "results") {
    body = `<div class="qs" data-key="r${g.round}"><div class="question qs-q qs-small">${esc(g.question)}</div>${resultsHtml(g)}</div>`;
  }
  patch.gTop = gameTopBar(g);
  if (!pyrFull) {
    // Jeu réduit : un bandeau pour revenir dedans.
    setGameHtml(`<button class="py-main" data-pyr="enter">⛶ Reprendre ${esc(g.name)} en plein écran</button>`);
  } else if (g.type === "heist") {
    Heist.mount(g);
  } else if (g.type === "island") {
    Island.mount(g);
  } else if (g.type === "neon") {
    Neon.mount(g);
  } else if (g.type === "quiz") {
    // Pas de nouveau rendu (ni d'animation) si rien n'a changé : sinon l'écran « flashe » à chaque rafraîchissement.
    const sig = quizSig(g), el = $("game");
    const fresh = el.dataset.qzSig !== sig || !el.querySelector(".qz-root");
    if (fresh) {
      const key = quizAnimKey(g);
      el.dataset.html = "";
      el.innerHTML = lobbyInvite(g) + `<div class="qz-root ${key !== qzAnimKey ? "anim" : ""} ${g.quiz.settings.mode === "chrono" ? "fast" : ""}">${quizHtml(g)}</div>`;
      el.dataset.qzSig = sig;
      qzAnimKey = key;
    }
    quizAfter(g, fresh);
  } else if (g.type === "likely") {
    setGameHtml(likelyHtml(g));
  } else if (g.type === "debate") {
    setGameHtml(debateHtml(g));
  } else if (g.type === "pyramid" || g.type === "biskit") {
    setGameHtml(lobbyInvite(g) + (g.type === "biskit" ? bkHtml(g) : pyrHtml(g)));
    if (g.type === "pyramid") pyrWheel(g);
  } else {
    const el = $("game"), html = lobbyInvite(g) + body;
    if (el.dataset.html !== html || !el.firstChild) { morph(el, html); el.dataset.html = html; }
  }
  renderDrawer(g);
  gameFlashes(g);
  if (g.type === "purity") puAnnounce(g);
  if (g.type === "likely") lkAnnounce(g);
  turnSignal(g);
  const input = $("guessInput");
  if (input && !input._vp) { input._vp = 1; input.value = guessDraft; input.addEventListener("input", () => { guessDraft = input.value; }); }
  renderRoulette(g);
  renderHud(g);
  bjOutcomeFx(g);
  renderGameHost(g);
  const joinCode = g.room || g.code;  // dans une salle : on invite à rejoindre la salle (puis le jeu suit)
  $("gameCode").textContent = joinCode;
  const qr = `/qr/game/${joinCode}.svg`;
  if ($("gameQr").getAttribute("src") !== qr) $("gameQr").src = qr;
}

// Pastille ronde avec l'initiale, d'une couleur stable par joueur.
function avatar(p, cls = "") {
  let h = 0;
  for (const c of p.pid || p.name || "") h = (h * 31 + c.charCodeAt(0)) % 360;
  const initial = esc((p.name || "?").trim().charAt(0).toUpperCase());
  // Compte Party : sa photo de profil ; l'initiale reste dessous si l'image ne charge pas.
  return `<span class="qs-av ${cls}" style="--h:${h}" aria-hidden="true">${initial}${p.photo ? `<img src="${esc(p.photo)}" alt="" loading="lazy" onerror="this.remove()">` : ""}</span>`;
}
// « Qui de nous ? » et « Je n'ai jamais » : la question, une consigne, les choix, et qui a déjà répondu.
function questionHtml(g, me) {
  const n = g.votes_count, total = g.players.length, mine = me?.vote;
  const sips = g.options?.sips || 0;
  const help = !me ? "Tu regardes la partie : les réponses s'affichent à la fin."
    : g.type === "never"
      ? (mine ? "Réponse enregistrée. Tu peux encore changer d'avis." : "Réponds en secret : tout est révélé quand tout le monde a répondu.")
      : (mine ? "✓ Vote enregistré. Résultat quand tout le monde a voté."
              : "Vote pour la personne qui correspond le mieux. C'est anonyme et définitif.");
  // Qui de nous ? : une fois voté, la grille disparaît sans rappeler le choix (personne ne le lit par-dessus l'épaule).
  const choices = !me || (g.type !== "never" && mine) ? "" : g.type === "never"
    ? `<div class="qs-yn" role="group" aria-label="Ta réponse">
        <button type="button" class="qs-opt ${mine === "yes" ? "on" : ""}" data-gact="vote" data-target="yes" aria-pressed="${mine === "yes"}">
          <span class="qs-emo" aria-hidden="true">🍻</span><b>Je l'ai déjà fait</b>${sips ? `<small>Je bois ${sips} gorgée${sips > 1 ? "s" : ""}</small>` : ""}</button>
        <button type="button" class="qs-opt ${mine === "no" ? "on" : ""}" data-gact="vote" data-target="no" aria-pressed="${mine === "no"}">
          <span class="qs-emo" aria-hidden="true">😇</span><b>Jamais</b>${sips ? `<small>Je ne bois pas</small>` : ""}</button>
      </div>`
    : `<div class="qs-grid" role="group" aria-label="Ton vote">${g.players.map((p) => `
        <button type="button" class="qs-pick" data-gact="vote" data-target="${esc(p.pid)}">
          ${avatar(p)}<span class="qs-name">${p.pid === me.pid ? "Moi" : esc(p.name)}</span></button>`).join("")}</div>`;
  const who = g.players.map((p) => `<span class="qs-who ${p.voted ? "ok" : ""}" title="${esc(p.name)}${p.voted ? " a répondu" : " réfléchit…"}">${avatar(p)}</span>`).join("");
  return `<div class="qs" data-key="q${g.round}">
    <div class="question qs-q">${esc(g.question)}</div>
    <p class="qs-help" role="status">${help}</p>
    ${choices}
    <div class="qs-progress"><div class="qs-whos">${who}</div>
      <span><b>${n}</b> sur ${total} ${n > 1 ? "ont" : "a"} ${g.type === "never" ? "répondu" : "voté"}</span></div>
  </div>`;
}

function resultsHtml(g) {
  if (!g.results) return "";
  if (g.type === "never") return neverResultsHtml(g);
  const max = Math.max(1, ...g.results.map((r) => r.count));
  const sips = g.options?.sips || 0;
  const top = g.results.filter((r) => r.count === max && r.count > 0);
  if (!top.length) return `<p class="qs-help">Personne n'a voté.</p>`;
  const drink = sips ? `<div class="qs-drink">🍻 ${top.length > 1 ? "Ils boivent" : "Boit"} ${sips} gorgée${sips > 1 ? "s" : ""}</div>` : "";
  const rest = g.results.filter((r) => !top.includes(r));
  return `<div class="qs-win">
      <div class="qs-win-names">${top.map((r) => `<span>👑 ${esc(r.name)}</span>`).join("")}</div>
      <div class="qs-win-n">${max} vote${max > 1 ? "s" : ""} sur ${g.players.length}</div>${drink}
    </div>
    ${rest.length ? `<div class="list qs-bars">${rest.map((r) => `<div class="bar" style="--w:${Math.round(100 * r.count / max)}%">
      <span>${esc(r.name)}</span><b>${r.count}</b></div>`).join("")}</div>` : ""}`;
}

// 🎆 Animation de fin de main, seulement sur l'écran du joueur concerné.
let fxSeen = "";
function bjOutcomeFx(g) {
  if (!isBJ(g) || !g.me) return;
  const h = g.bj.seats.find((x) => x.pid === g.me.pid)?.hand;
  const key = g.id + ":" + g.round;
  if (!h || fxSeen === key) return;
  // Sauté (plus de 21) : le joueur sait déjà qu'il a perdu, on l'affiche tout de suite (une seule fois par main).
  if (g.phase === "play" && h.status === "bust") {
    fxSeen = key;
    return playFx("bust", drinks(g) ? `🍻 Bois ${sipWord(h.bet)}` : `-${h.bet} jetons`);
  }
  if (g.phase !== "results" || !h.result) return;
  fxSeen = key;
  // Page en arrière-plan, ou main terminée depuis longtemps (page rechargée) : pas d'animation en différé.
  if (document.hidden || (g.bj.finished_age ?? 0) > 12) return;
  const kind = h.status === "bust" ? "bust" : h.result;
  const sub = drinks(g)
    ? { win: `🎉 Distribue ${sipWord(h.sips)}`, blackjack: `🃏 Distribue ${sipWord(h.sips)}`, push: "Personne ne boit",
        lose: `🍻 Bois ${sipWord(-h.sips)}`, bust: `🍻 Bois ${sipWord(-h.sips)}` }[kind]
    : { win: `+${h.delta} jetons`, blackjack: `+${h.delta} jetons`, push: "Mise rendue", lose: `${h.delta} jetons`, bust: `${h.delta} jetons` }[kind];
  playFx(kind, sub);
}
function playFx(kind, sub) {
  GameAudio.play(["win", "blackjack", "jackpot"].includes(kind) ? "win" : ["lose", "bust"].includes(kind) ? "lose" : "reveal");
  document.querySelector(".fx")?.remove();
  const title = { win: "GAGNÉ !", blackjack: "BLACKJACK !", jackpot: "JACKPOT !", push: "ÉGALITÉ", mixed: "MITIGÉ", lose: "PERDU", bust: "SAUTÉ !" }[kind];
  const good = ["win", "blackjack", "jackpot"].includes(kind), bad = kind === "lose" || kind === "bust";
  const fx = document.createElement("div");
  fx.className = `fx fx-${good ? "good" : bad ? "bad" : "even"}${kind === "blackjack" || kind === "jackpot" ? " fx-bj" : ""}`;
  fx.setAttribute("role", "status");
  let bits = "";
  if (good) {
    // Confettis : chaque morceau part dans une direction au hasard, puis retombe.
    const colors = ["#ffd166", "#ff4f9a", "#4fd1c5", "#8b7bff", "#ffffff", "#3ddc97"];
    const n = kind === "win" ? 70 : 120;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, d = 25 + Math.random() * 45;
      bits += `<i class="fx-c" style="--x:${(Math.cos(a) * d).toFixed(1)}vmax;--y:${(Math.sin(a) * d - 10).toFixed(1)}vmax;--r:${Math.round(Math.random() * 720 - 360)}deg;--c:${colors[i % colors.length]};--d:${(Math.random() * 0.25).toFixed(2)}s;--w:${6 + Math.round(Math.random() * 6)}px"></i>`;
    }
  } else if (bad) {
    for (let i = 0; i < 14; i++) {
      bits += `<i class="fx-drop" style="--x:${Math.round(Math.random() * 100)}vw;--d:${(0.2 + Math.random() * 1.2).toFixed(2)}s;--s:${(0.8 + Math.random() * 0.8).toFixed(2)}">${drinks(game) ? "🍻" : "💸"}</i>`;
    }
  }
  fx.innerHTML = `${good ? `<div class="fx-rays"></div>` : ""}${bits}
    <div class="fx-box">
      ${kind === "blackjack" ? `<div class="fx-cards"><span class="pcard">A<i>♠</i></span><span class="pcard red">K<i>♥</i></span></div>` : ""}
      <div class="fx-title" data-text="${title}">${title}</div>
      <div class="fx-sub">${esc(sub)}</div>
    </div>`;
  const close = () => { fx.classList.add("fx-out"); setTimeout(() => fx.remove(), 350); };
  fx.addEventListener("click", close);
  document.body.append(fx);
  haptic({ win: [80, 60, 80], blackjack: [100, 50, 100, 50, 220], jackpot: [100, 50, 100, 50, 100, 50, 300],
    push: [60], mixed: [60, 60, 60], lose: [320], bust: [120, 60, 320] }[kind]);
  setTimeout(close, kind === "blackjack" || kind === "jackpot" ? 3800 : 3000);
}

// Compteur fixe en haut à droite : mes jetons (blackjack) et mes gorgées (bues / distribuées).
function renderHud(g) {
  const me = g.me, sips = (g.options?.sips || 0) > 0;
  const chips = !me || sips ? null : isBJ(g) ? g.bj.seats.find((x) => x.pid === me.pid)?.chips
    : g.type === "casino" ? g.casino.me?.chips : null;
  const items = [];
  if (chips != null) items.push(`<div class="hud-item"><span>💰</span><b>${chips}</b><small>jetons</small></div>`);
  if (sips && me) {
    items.push(`<div class="hud-item"><span>🍻</span><b>${me.drink || 0}</b><small>bue${me.drink > 1 ? "s" : ""}</small></div>`);
    if (isBJ(g)) items.push(`<div class="hud-item"><span>🎁</span><b>${me.give || 0}</b><small>donnée${me.give > 1 ? "s" : ""}</small></div>`);
  }
  patch.gameHud = items.join("");
  $("gameHud").className = "g-hud " + (GAME_THEME[g.type] || "") + (items.length && g.phase !== "lobby" ? "" : " hidden");
}
const sipsBadge = (p) => p.drink || p.give ? ` <span class="artist">· 🍻 ${p.drink || 0}${p.give ? ` · 🎁 ${p.give}` : ""}</span>` : "";

// 🃏 Blackjack : table (croupier, ma main, mes boutons) et liste des joueurs.
const SUITS = { S: "♠", H: "♥", D: "♦", C: "♣" };
function cardHtml(c, small = false) {
  if (c === "??") return `<span class="pcard back ${small ? "sm" : ""}" aria-label="Carte cachée"></span>`;
  const rank = c[0] === "T" ? "10" : c[0];
  return `<span class="pcard ${"HD".includes(c[1]) ? "red" : ""} ${small ? "sm" : ""}">${rank}<i>${SUITS[c[1]]}</i></span>`;
}
const drinks = (g) => (g.options?.sips || 0) > 0;
const sipWord = (n) => `${n} gorgée${n > 1 ? "s" : ""}`;
function bjResultText(g, h) {
  if (!h?.result) return "";
  if (drinks(g)) return { lose: `🍻 Perdu : bois ${sipWord(-h.sips)}`, win: `🎉 Gagné : distribue ${sipWord(h.sips)}`,
    blackjack: `🃏 Blackjack ! Distribue ${sipWord(h.sips)}`, push: "🤝 Égalité : personne ne boit" }[h.result];
  return { lose: `Perdu (${h.delta})`, win: `Gagné (+${h.delta})`, blackjack: `Blackjack ! (+${h.delta})`, push: "Égalité (mise rendue)" }[h.result];
}
const betLabel = (g, n) => drinks(g) ? `🍻 ${sipWord(n)}` : `${n}`;
let bjTurnSeen = "";
function bjTableHtml(g) {
  const t = g.bj, me = g.me, mine = t.seats.find((x) => x.pid === me?.pid), h = mine?.hand;
  const turnName = t.seats.find((x) => x.pid === t.turn)?.name;
  const dealer = t.dealer.length ? `<div class="bj-dealer"><div class="artist">Croupier ${t.dealer_total != null ? `· <b>${t.dealer_total}</b>` : t.dealer_up != null ? `· ${t.dealer_up} + ?` : ""}</div>
    <div class="bj-cards">${t.dealer.map((c) => cardHtml(c)).join("")}</div></div>` : "";
  let status = "", zone = "";
  if (g.phase === "lobby") status = g.is_host ? "Ouvre la table quand tout le monde est assis." : "La table va ouvrir…";
  else if (g.phase === "bet") status = "Faites vos jeux !";
  else if (g.phase === "play") status = t.my_turn ? "À toi de jouer !" : `Au tour de ${esc(turnName || "…")}`;
  else if (g.phase === "results") status = "Résultats de la main";
  if (!me) {
    zone = `<button data-gact="join" style="width:100%;margin-top:12px">S'asseoir à la table</button>`;
  } else if (g.phase === "bet") {
    const amounts = drinks(g) ? Array.from({ length: t.max_bet }, (_, i) => i + 1)
      : [5, 10, 25, 50].filter((a) => a <= mine.chips).concat(mine.chips >= t.min_bet ? [mine.chips] : []);
    zone = `<div class="artist">${drinks(g) ? "Perdu : tu bois ta mise · gagné : tu distribues le double · blackjack : le triple"
        : `Tes jetons : <b>${mine.chips}</b>${mine.rebuys ? ` · rechargé ${mine.rebuys}×` : ""}`}</div>
      <div class="artist" style="margin-top:6px">${h ? `Mise : <b>${betLabel(g, h.bet)}</b> ✓ — en attente des autres (tu peux changer)` : "Ta mise :"}</div>
      <div class="chips" style="margin-top:8px">${[...new Set(amounts)].map((a) => `<button class="${h?.bet === a ? "" : "secondary"}" data-gact="bet" data-amount="${a}">${drinks(g) ? `🍻 ${a}` : a === mine.chips && a > 50 ? `Tapis (${a})` : a}</button>`).join("")}</div>
      ${!drinks(g) && mine.chips < t.min_bet ? `<button data-gact="rebuy" style="width:100%;margin-top:8px">Recharger ${t.start_chips} jetons</button>` : ""}`;
  } else if (h && h.cards.length) {
    zone = `<div class="bj-me"><div class="artist">Ta main · <b>${h.total}</b> · mise ${betLabel(g, h.bet)}${h.doubled ? " (doublée)" : ""}</div>
      <div class="bj-cards big">${h.cards.map((c) => cardHtml(c)).join("")}</div>
      ${h.status === "bust" && g.phase === "play" ? `<div class="title">Plus de 21 !</div>` : ""}
      ${h.status === "blackjack" && g.phase === "play" ? `<div class="title">Blackjack ! 🃏</div>` : ""}
      ${g.phase === "results" ? `<div class="bj-result ${h.result}">${bjResultText(g, h)}</div>` : ""}</div>
      ${t.my_turn ? `<div class="bj-actions"><button data-gact="hit">Carte</button><button class="secondary" data-gact="stand">Rester</button>
        ${h.cards.length === 2 && (drinks(g) || mine.chips >= h.bet) ? `<button class="secondary" data-gact="double">Doubler</button>` : ""}</div>` : ""}`;
  } else if (g.phase === "play" || g.phase === "results") {
    zone = `<div class="artist" style="margin-top:10px">Tu joues à la prochaine main.</div>`;
  }
  // Tout le monde voit la main du joueur en cours, carte par carte.
  const current = t.seats.find((x) => x.pid === t.turn);
  const spot = g.phase === "play" && current && !t.my_turn && current.hand
    ? `<div class="bj-spot"><div class="artist">🎯 Au tour de <b>${esc(current.name)}</b> · mise ${betLabel(g, current.hand.bet)}</div>
        <div class="bj-cards big">${current.hand.cards.map((c) => cardHtml(c)).join("")}<span class="bj-total">${current.hand.total}</span></div></div>` : "";
  return `<div class="title">${status}</div>${dealer}${spot}${zone}${bjLogHtml(t)}`;
}
let bjLogSeen = 0;
function bjLogHtml(t) {
  const log = (t.log || []).slice(-3).reverse();
  if (!log.length) return "";
  const fresh = log[0].n > bjLogSeen;
  bjLogSeen = Math.max(bjLogSeen, log[0].n);
  return `<div class="bj-log">${log.map((e, i) => `<div class="${i === 0 ? "last" : ""} ${i === 0 && fresh ? "fresh" : ""}"><b>${esc(e.name)}</b> ${esc(e.text)}</div>`).join("")}</div>`;
}
function renderBJHost(g, btn) {
  const t = g.bj, bets = t.seats.filter((x) => x.hand).length, turnName = t.seats.find((x) => x.pid === t.turn)?.name;
  const controls = !g.is_host ? "" : {
    lobby: btn("start", "▶︎ Ouvrir la table", "grow", g.players.length ? "" : "disabled"),
    bet: btn("deal", `🃏 Distribuer (${bets}/${g.players.length} mises)`, "grow", bets ? "" : "disabled"),
    play: turnName ? btn("skip", `⏭ Passer le tour de ${esc(turnName)}`, "secondary grow") : "",
    results: btn("next", "▶︎ Main suivante", "grow"),
  }[g.phase] || "";
  patch.gameHost = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    <h2>À la table (${g.players.length})</h2>
    <div class="list">${t.seats.map((x) => {
      const h = x.hand;
      const info = !h ? (g.phase === "bet" ? "mise en cours…" : "attend la prochaine main")
        : g.phase === "bet" ? `a misé ${betLabel(g, h.bet)}`
        : `${h.total}${h.status === "bust" ? " · sauté" : h.status === "blackjack" ? " · blackjack" : ""} · mise ${betLabel(g, h.bet)}`;
      return `<div class="track ${x.pid === t.turn ? "bj-turn" : ""}">
        <div class="meta"><div class="title">${esc(x.name)}${x.pid === t.turn ? " ⏳" : ""}${drinks(g) ? "" : `<span class="artist"> · 💰 ${x.chips}${x.rebuys ? ` (rechargé ${x.rebuys}×)` : ""}</span>`}${sipsBadge(g.players.find((p) => p.pid === x.pid) || {})}</div>
          <div class="artist">${info}${g.phase === "results" && h?.result ? ` · <b>${bjResultText(g, h)}</b>` : ""}</div>
          ${h?.cards.length ? `<div class="bj-cards" style="margin-top:4px">${h.cards.map((c) => cardHtml(c, true)).join("")}</div>` : ""}</div>
        ${g.is_host && x.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(x.pid)}" title="Exclure de la table" aria-label="Exclure de la table">✕</button>` : ""}
      </div>`;
    }).join("") || `<p class="empty" style="padding:12px">Personne à la table : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.is_host && !g.me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// 🔺 Pyramide : plein écran néon ; tout le monde suit la même table, l'animateur mène la partie.
const PYR_Q = {
  1: { q: "Rouge ou noir ?", opts: [["red", "Rouge", "♥ ♦", "py-red"], ["black", "Noir", "♠ ♣", "py-black"]] },
  2: { q: "Plus ou moins ?", opts: [["plus", "Plus", "▲", "py-cyan"], ["moins", "Moins", "▼", "py-pink"]] },
  3: { q: "Dedans ou dehors ?", opts: [["dedans", "Dedans", "→ ←", "py-cyan"], ["dehors", "Dehors", "← →", "py-pink"]] },
  4: { q: "Quel symbole ?", opts: [["S", "Pique", "♠", "py-black"], ["H", "Cœur", "♥", "py-red"], ["D", "Carreau", "♦", "py-red"], ["C", "Trèfle", "♣", "py-black"]] },
};
const PYR_ANS = { red: "rouge", black: "noir", plus: "plus", moins: "moins", dedans: "dedans", dehors: "dehors", S: "pique ♠", H: "cœur ♥", D: "carreau ♦", C: "trèfle ♣" };
const PYR_VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
let pyrFull = true, pyrSeen = { last: 0, reveal: 0, liars: 0, flip: 0, peek: 0, top: null }, pyrPeekSel = [], pyrMem = ["", "", "", ""], pyrMemSlot = 0,
  pyrMemFor = "", pyrTimer = null, pyrWheelSpin = "", pyrWheelRot = 0, pyrWheelShown = "";
const cardLabel = (c) => (c[0] === "T" ? "10" : c[0]) + SUITS[c[1]];
function pyCard(c, size = "", extra = "") {
  if (!c || c === "??") return `<span class="py-card back ${size}" ${extra}><i></i></span>`;
  return `<span class="py-card ${"HD".includes(c[1]) ? "red" : ""} ${size}" ${extra}><b>${c[0] === "T" ? "10" : c[0]}</b><i>${SUITS[c[1]]}</i></span>`;
}
// Grande annonce animée, la même sur tous les téléphones (réponse, menteur, cul sec…).
function pyrFlash(kind, title, sub = "", card = "", ms = 2300) {
  GameAudio.play(["bad", "liar"].includes(kind) ? "lose" : kind === "summit" ? "win" : "reveal");
  document.querySelector(".py-flash")?.remove();
  const el = document.createElement("div");
  el.className = `py-flash py-${kind}`;
  el.setAttribute("role", "status");
  el.innerHTML = `<div class="py-flash-box">${card ? `<div class="py-flash-card">${pyCard(card, "xl")}</div>` : ""}
    <div class="py-flash-title">${title}</div>${sub ? `<div class="py-flash-sub">${sub}</div>` : ""}</div>`;
  el.addEventListener("click", () => el.remove());
  document.body.append(el);
  haptic(kind === "bad" || kind === "liar" ? [200] : [60, 40, 60]);
  setTimeout(() => el.classList.add("out"), ms);
  setTimeout(() => el.remove(), ms + 400);
}
function pyrEvents(g) {
  const v = g.pyr;
  if (!v.event) return;
  const first = pyrSeen.init !== g.id;  // première vue (page rechargée) : pas d'annonce en différé
  if (first) {
    pyrSeen = { init: g.id, last: v.last?.n || 0, reveal: v.reveal?.n || 0, liars: v.liars.length, flip: v.flipped, peek: 0, top: v.top_me ?? null };
    return;
  }
  if (v.last && v.last.n > pyrSeen.last) {
    pyrSeen.last = v.last.n;
    const l = v.last, mine = l.pid === g.me?.pid;
    pyrFlash(l.ok ? "good" : "bad", l.ok ? `${mine ? "Bien joué" : esc(l.name)} !` : `Raté${mine ? "" : ` pour ${esc(l.name)}`} !`,
      `${esc(PYR_ANS[l.value])} · ${l.ok ? `distribue ${sipWord(l.sips)}` : `boit ${sipWord(l.sips)}`}`, l.card);
    if (l.poteau) setTimeout(() => pyrFlash("summit", "POTEAU !", v.poteau_hard ? `${esc(l.name)} a deux fois la même carte · cul sec ! 🥃`
      : `${esc(l.name)} a deux fois la même carte · tout le monde boit 1 gorgée 🍻`, l.card), 2500);
  }
  const lateName = v.late?.name || "";
  if (pyrSeen.lateName && !lateName && g.phase === "pyramid") setTimeout(() => pyrFlash("good", "Cartes retournées !", `${esc(pyrSeen.lateName)} est dans la partie`), 2600);
  pyrSeen.lateName = lateName;
  if (v.flipped > pyrSeen.flip) {
    pyrSeen.flip = v.flipped;
    if (v.is_top) pyrFlash("summit", "CUL SEC !", "Dernière carte : pas de bluff. Tu l'as ? Annonce-le.", v.current);
  }
  if (v.reveal && v.reveal.n > pyrSeen.reveal) {
    pyrSeen.reveal = v.reveal.n;
    const r = v.reveal;
    setTimeout(() => pyrFlash(r.truth ? "good" : "liar", r.truth ? "Il dit la vérité !" : "Bouuuh, menteur !",
      `${esc(r.name)} a retourné ${r.card ? cardLabel(r.card) : "sa carte"}`), 900);
    clearTimeout(pyrTimer); pyrTimer = setTimeout(refreshGame, 3200);  // la carte se recache après 3 s
  }
  if (v.liars.length > pyrSeen.liars) {
    pyrSeen.liars = v.liars.length;
    pyrFlash("liar", "Bouuuh, menteur !", `${esc(v.liars[v.liars.length - 1])} n'a pas la carte : direction la roulette du bateau`);
  }
  if (v.top_me != null && pyrSeen.top !== v.top_me) {
    pyrSeen.top = v.top_me;
    if (v.top_me) pyrFlash("good", "Tu as la carte !", "Distribue ton cul sec… en privé 🤫");
  }
  const peek = v.peeks.find((r) => r.mine && r.status === "ok" && r.age < 5);
  if (peek && peek.id !== pyrSeen.peek) {
    pyrSeen.peek = peek.id;
    clearTimeout(pyrTimer); pyrTimer = setTimeout(refreshGame, Math.max(500, (5 - peek.age) * 1000));  // les cartes se recachent
  }
}

function pyrPhase(g) {
  const v = g.pyr;
  return { lobby: "Préparation", deal: `Distribution · tour ${v.step || 1}/4`, pyramid: `Pyramide · ${v.flipped || 0}/${v.size}`,
    memory: "Test de mémoire", memres: "Résultats", boatpick: "Qui fait le bateau ?", boat: "Le bateau", end: "Fin" }[g.phase] || "";
}
function pyrSeats(g, opts = {}) {
  const v = g.pyr;
  return `<div class="py-seats">${v.seats.map((s) => `
    <div class="py-seat ${s.pid === v.turn ? "on" : ""} ${s.pid === g.me?.pid ? "me" : ""}">
      <div class="py-seat-name">${esc(s.name)}${s.manual ? " ✍️" : ""}${sipsBadge(g.players.find((p) => p.pid === s.pid) || {})}</div>
      <div class="py-seat-cards">${s.cards.map((c, i) => pyCard(c, "sm", opts.memory && s.memory ? `data-ok="${s.memory[i] === c[0]}"` : "")).join("") || `<span class="artist">—</span>`}</div>
      ${opts.memory && s.memory ? `<div class="py-guess">${s.memory.map((m, i) => `<span class="${m === s.cards[i]?.[0] ? "ok" : "ko"}">${m === "T" ? "10" : m}</span>`).join("")}<b>${s.errors} erreur${s.errors > 1 ? "s" : ""}</b></div>` : ""}
    </div>`).join("")}</div>`;
}
function pyrQuestion(g, step, ref, actFor, action) {
  const Q = PYR_Q[step];
  return `<div class="py-q">${Q.q}</div>
    ${ref.length ? `<div class="py-ref">${ref.map((c) => pyCard(c, "md")).join("")}<span class="py-card ghost md"><b>?</b></span></div>` : ""}
    <div class="py-opts n${Q.opts.length}">${Q.opts.map(([val, label, sym, cls]) =>
      `<button type="button" class="py-opt ${cls}" data-pyr="${action}" data-val="${val}" ${actFor ? `data-who="${esc(actFor)}"` : ""}><span>${sym}</span><b>${label}</b></button>`).join("")}</div>`;
}

function pyrHtml(g) {
  const v = g.pyr, me = g.me, host = g.is_host;
  pyrEvents(g);
  let body = "";
  if (g.phase === "lobby") {
    body = `<div class="py-hero"><div class="py-hero-k">🔺 Pyramide</div><div class="py-hero-t">${v.floors} étages · ${v.size} cartes</div>
      <div class="artist">${v.hard ? "🔥 Hard : 1, 2, 3, 4 gorgées" : "😇 Soft : 1 gorgée par carte"} · ${v.boat_on ? "avec le bateau 🚢" : "sans bateau"}</div>
      <div class="artist">${g.players.length} joueur${g.players.length > 1 ? "s" : ""} · ${v.max_players} au plus (un seul paquet)</div></div>
      ${host ? `<button class="py-main" data-gact="start" ${g.players.length < 2 || g.players.length > v.max_players ? "disabled" : ""}>▶︎ Distribuer les cartes</button>`
        : `<div class="py-wait">${me ? "Tu es à la table ✓ L'animateur va distribuer…" : ""}</div>`}
      ${!me && !g.master ? `<button class="py-main" data-gact="join">S'asseoir à la table</button>` : ""}`;
  } else if (g.phase === "deal") {
    const cur = v.seats.find((s) => s.pid === v.turn), mine = cur && cur.pid === me?.pid;
    const ref = v.step === 2 ? cur.cards.slice(0, 1) : v.step === 3 ? cur.cards.slice(0, 2) : [];
    const canAct = mine || host;
    body = `<div class="py-steps">${[1, 2, 3, 4].map((i) => `<span class="${i < v.step ? "done" : i === v.step ? "on" : ""}">${i}</span>`).join("<i></i>")}</div>
      <div class="py-turn ${mine ? "me" : ""}"><div class="py-turn-k">${mine ? "C'est ton tour" : "C'est au tour de"}</div>
        <div class="py-turn-name">${mine ? "À TOI !" : esc(cur?.name || "…")}</div></div>
      <div class="py-stake">Raté : bois <b>${sipWord(v.step_sips)}</b> · Réussi : distribue <b>${v.step_sips}</b></div>
      ${canAct ? pyrQuestion(g, v.step, ref, mine ? "" : cur.pid, "pans") + (mine ? "" : `<div class="py-proxy">Tu réponds pour ${esc(cur.name)}${cur.manual ? " (sans téléphone)" : ""}</div>`)
        : `<div class="py-q">${PYR_Q[v.step].q}</div>${ref.length ? `<div class="py-ref">${ref.map((c) => pyCard(c, "md")).join("")}<span class="py-card ghost md"><b>?</b></span></div>` : ""}
           <div class="py-wait">${esc(cur?.name)} réfléchit…</div>`}
      <h3 class="py-h">Les mains</h3>${pyrSeats(g)}`;
  } else if (g.phase === "pyramid" && v.late) {
    const L = v.late, seat = v.seats.find((s) => s.pid === L.pid), mine = L.pid === me?.pid;
    const ref = L.step === 2 ? seat.cards.slice(0, 1) : L.step === 3 ? seat.cards.slice(0, 2) : [];
    body = `<div class="py-hero"><div class="py-hero-k">🆕 Nouveau joueur</div><div class="py-hero-t">${esc(L.name)} rejoint la partie</div>
        <div class="artist">Sa distribution, puis ses cartes se retournent et la pyramide reprend</div></div>
      <div class="py-steps">${[1, 2, 3, 4].map((i) => `<span class="${i < L.step ? "done" : i === L.step ? "on" : ""}">${i}</span>`).join("<i></i>")}</div>
      <div class="py-turn ${mine ? "me" : ""}"><div class="py-turn-name">${mine ? "À TOI !" : esc(L.name)}</div></div>
      <div class="py-stake">Raté : bois <b>${sipWord(L.step_sips)}</b> · Réussi : distribue <b>${L.step_sips}</b></div>
      ${(mine || host) ? pyrQuestion(g, L.step, ref, mine ? "" : L.pid, "pans") + (mine ? "" : `<div class="py-proxy">Tu réponds pour ${esc(L.name)}</div>`)
        : `<div class="py-q">${PYR_Q[L.step].q}</div>${ref.length ? `<div class="py-ref">${ref.map((c) => pyCard(c, "md")).join("")}<span class="py-card ghost md"><b>?</b></span></div>` : ""}<div class="py-wait">${esc(L.name)} réfléchit…</div>`}
      ${pyrBoard(g)}`;
  } else if (g.phase === "pyramid") {
    body = pyrBoard(g) + pyrCurrent(g) + pyrHand(g);
  } else if (g.phase === "memory") {
    body = pyrMemory(g);
  } else if (g.phase === "memres") {
    const worst = v.candidates;
    body = `<div class="py-hero"><div class="py-hero-k">🧠 Test de mémoire</div><div class="py-hero-t">Les vraies cartes</div></div>
      ${pyrSeats(g, { memory: true })}
      <div class="py-cands"><div class="py-turn-k">Candidats au bateau</div>${worst.map((c) => `<span class="pill">${esc(c.name)} · ${c.errors} err.${c.liar ? " · menteur au cul sec" : ""}</span>`).join("")}</div>
      ${host ? `<button class="py-main" data-gact="pboat">🚢 Qui fait le bateau ?${worst.length > 1 ? " (roulette)" : ""}</button>` : ""}`;
  } else if (g.phase === "boatpick") {
    const sp = v.spin, shown = !sp || pyrWheelShown === sp.id;
    body = `<div class="py-hero"><div class="py-hero-k">🚢 Le bateau</div><div class="py-hero-t">${sp ? "La roulette décide…" : "Désigné d'office"}</div></div>
      ${sp ? `<div class="wheel-wrap py-wheel"><div class="wheel-pointer" aria-hidden="true"></div><svg id="pyrWheel" viewBox="-100 -100 200 200" role="img" aria-label="Roue">${wheelSvg(sp.names)}</svg></div>` : ""}
      <div class="py-boat-name ${shown ? "show" : ""}">${shown ? `${esc(v.boat.name)} fait le bateau !` : ""}</div>
      ${host && shown ? `<button class="py-main" data-gact="pboatgo">⛵ Lancer le bateau</button>` : ""}`;
  } else if (g.phase === "end" && !v.boat) {
    body = `<div class="py-hero"><div class="py-hero-k">🏁 Partie terminée</div><div class="py-hero-t">Les vraies cartes</div>
      <div class="artist">Pire mémoire : ${v.candidates.map((c) => esc(c.name)).join(", ") || "personne"}</div></div>
      ${pyrSeats(g, { memory: true })}
      ${g.is_host ? `<button class="py-main" data-gact="restart">🔁 Rejouer avec les mêmes joueurs</button>` : ""}`;
  } else if (g.phase === "boat" || g.phase === "end") {
    body = pyrBoat(g);
  }
  // Arrivées en cours de partie : l'animateur accepte ou refuse ; le nouveau venu patiente.
  const peekReqs = host ? (v.peeks || []).filter((r) => r.status === "pending") : [];
  if (peekReqs.length && pyrSeen.peekAlert !== peekReqs[0].id) { pyrSeen.peekAlert = peekReqs[0].id; haptic([120, 60, 120]); }
  const peekAlert = peekReqs.length ? `<div class="py-panel py-pend py-alert">${peekReqs.map((r) => `
      <div class="py-claim"><span>👀 <b>${esc(r.name)}</b> veut revoir ${r.count} carte${r.count > 1 ? "s" : ""} <small>(+${2 * r.count} gorgées)</small></span><span class="py-claim-act">
        <button class="py-mini ok" data-gact="ppeek_ok" data-target="${r.id}">Accepter</button><button class="py-mini bad" data-gact="ppeek_no" data-target="${r.id}">Refuser</button></span></div>`).join("")}</div>` : "";
  const pend = peekAlert + (g.phase !== "lobby" && host && v.pending?.length ? `<div class="py-panel py-pend">${v.pending.map((p) => `
      <div class="py-claim"><span>🙋 <b>${esc(p.name)}</b> veut rejoindre</span><span class="py-claim-act">
        <button class="py-mini ok" data-gact="paccept" data-target="${esc(p.pid)}">Accepter</button><button class="py-mini bad" data-gact="prefuse" data-target="${esc(p.pid)}">Refuser</button></span></div>`).join("")}</div>` : "");
  const outsider = g.phase !== "lobby" && !g.master && (!me || (v.me && v.me.seat == null && !v.me.pending && !(v.queue || []).length));
  const wait = g.phase !== "lobby" && v.me?.pending ? `<div class="py-panel py-pend"><div class="py-wait">⏳ L'animateur doit accepter ton arrivée…</div></div>`
    : !me && outsider ? `<button class="py-sub" data-gact="join">🙋 Demander à rejoindre la partie</button>` : "";
  return `<div class="py-body">${pend}${wait}${body}</div>`;
}

function pyrBoard(g) {
  const v = g.pyr, rows = [];
  let i = 0;
  for (let f = 1; f <= v.floors; f++) {
    const w = v.floors - f + 1, cards = [];
    for (let k = 0; k < w; k++, i++) cards.push({ c: v.pyramid[i], i, cur: i === v.flipped - 1 });
    rows.push({ f, cards });
  }
  const size = v.floors >= 7 ? "xs" : v.floors === 6 ? "sm" : "";
  return `<div class="py-board">${rows.reverse().map((r) => `
    <div class="py-row ${r.f === v.floor ? "now" : ""}"><span class="py-mult f${Math.min(r.f, 5)}">${r.f === v.floors ? "🥃" : `×${v.double ? r.f * 2 : r.f}`}</span>
      <div class="py-row-cards">${r.cards.map((x) => pyCard(x.c, size, `data-i="${x.i}"${x.cur ? ` data-cur="1"` : ""}`)).join("")}</div></div>`).join("")}</div>`;
}

function pyrCurrent(g) {
  const v = g.pyr, me = g.me, host = g.is_host;
  const next = host ? (v.flipped < v.size ? `<button class="py-main" data-gact="pflip">${v.flipped ? "Retourner la carte suivante ▶︎" : "▶︎ Retourner la première carte"}</button>`
    : `<button class="py-main" data-gact="pmemory">🧠 Lancer le test de mémoire</button>`) : "";
  if (!v.flipped) return `<div class="py-panel"><div class="py-turn-k">Mémorisez bien vos cartes…</div><div class="py-panel-t">La pyramide va commencer</div>${next}</div>`;
  const label = cardLabel(v.current);
  const claims = v.claims.map((c) => {
    const status = { pending: host ? `<button class="py-mini ok" data-gact="pbu" data-target="${c.id}">Bu ✓</button><button class="py-mini bad" data-gact="pliar" data-target="${c.id}">Menteur !</button>` : `<span class="py-tag">bu ?</span>`,
      drunk: `<span class="py-tag ok">bu ✓</span>`, accused: `<span class="py-tag bad">accusé·e !</span>`,
      truth: `<span class="py-tag ok">vérité ✓</span>`, lie: `<span class="py-tag bad">menteur ✗</span>` }[c.status];
    return `<div class="py-claim ${c.status}"><span><b>${esc(c.name)}</b> donne ${sipWord(c.sips)}</span><span class="py-claim-act">${status}</span></div>`;
  }).join("");
  const accused = v.claims.find((c) => c.status === "accused" && (c.mine || host));
  const mySeat = v.seats.find((s) => s.pid === me?.pid);
  const pick = accused ? `<div class="py-pick"><div class="py-turn-k">${accused.mine ? "On t'accuse ! Retourne la carte qui le prouve" : `${esc(accused.name)} est accusé·e : retourner sa carte pour lui`}</div>
    <div class="py-pick-cards">${[0, 1, 2, 3].map((k) => `<button type="button" class="py-pick-btn" data-pyr="reveal" data-slot="${k}" ${accused.mine ? "" : `data-who="${esc(accused.pid)}"`}>${pyCard("??", "md")}<small>${k + 1}</small></button>`).join("")}</div></div>` : "";
  let mine = "";
  if (me && mySeat) {
    if (v.is_top) mine = v.top_me == null ? `<button class="py-main py-cul" data-gact="ptop">🥃 J'ai cette carte !</button>`
      : v.top_me ? `<div class="py-ok">Tu as la carte : distribue ton cul sec en privé 🤫</div>` : `<div class="py-bad">Raté… tu iras à la roulette du bateau</div>`;
    else if (!v.claims.some((c) => c.mine)) mine = `<button class="py-main py-give" data-gact="pclaim">🍻 Je donne ${sipWord(v.floor_sips)}</button>`;
  }
  const manualGive = host && !v.is_top ? v.seats.filter((s) => s.manual && !v.claims.some((c) => c.pid === s.pid))
    .map((s) => `<button class="py-mini" data-pyr="claimfor" data-who="${esc(s.pid)}">${esc(s.name)} donne</button>`).join("") : "";
  return `<div class="py-panel ${v.is_top ? "top" : ""}">
    <div class="py-now">${pyCard(v.current, "lg", 'data-flip="1"')}
      <div><div class="py-turn-k">${v.is_top ? "Le sommet" : `Étage ${v.floor}`}</div>
        <div class="py-panel-t">${v.is_top ? "CUL SEC" : `Un ${esc(label)} !`}</div>
        <div class="artist">${v.is_top ? "Pas de bluff : seul celui qui l'a vraiment distribue" : `${sipWord(v.floor_sips)} à donner · bluff permis`}</div></div></div>
    ${mine}${manualGive ? `<div class="py-manual">${manualGive}</div>` : ""}
    ${claims ? `<div class="py-claims">${claims}</div>` : ""}${pick}
    ${v.is_top && v.top_done.length ? `<div class="artist" style="margin-top:6px">Ont annoncé : ${v.top_done.map(esc).join(", ")}</div>` : ""}
    ${next}</div>`;
}

function pyrHand(g) {
  const v = g.pyr, me = g.me, host = g.is_host, seat = v.seats.find((s) => s.pid === me?.pid);
  const pending = v.peeks.filter((r) => r.status === "pending");
  const hostReqs = "";  // affichées en haut de l'écran de l'animateur (voir pyrHtml)
  const recent = v.peeks.filter((r) => r.status === "ok" && !r.mine && r.age < 8).map((r) => `<div class="artist">👀 ${esc(r.name)} revoit ${r.count} carte${r.count > 1 ? "s" : ""} : +${2 * r.count} gorgées</div>`).join("");
  if (!seat) return hostReqs ? `<div class="py-panel">${hostReqs}</div>` : "";
  const myPending = pending.some((r) => r.mine);
  const seeing = v.peeks.some((r) => r.mine && r.status === "ok" && r.age < 5);
  return `<div class="py-panel py-hand">
    <div class="py-turn-k">Ta main ${seeing ? "· regarde vite !" : "· face cachée"}</div>
    <div class="py-hand-cards">${seat.cards.map((c, k) => `<button type="button" class="py-pick-btn ${pyrPeekSel.includes(k) ? "sel" : ""}" data-pyr="peeksel" data-slot="${k}" ${myPending || c !== "??" ? "disabled" : ""}>${pyCard(c, "md")}<small>${k + 1}</small></button>`).join("")}</div>
    ${myPending ? `<div class="artist">Demande envoyée à l'animateur…</div>`
      : `<button class="py-sub" data-pyr="peek" ${pyrPeekSel.length ? "" : "disabled"}>👀 Revoir ${pyrPeekSel.length ? `${pyrPeekSel.length} carte${pyrPeekSel.length > 1 ? "s" : ""} (+${2 * pyrPeekSel.length} gorgées)` : "des cartes : touche-les d'abord"}</button>`}
    ${hostReqs}${recent}</div>`;
}

function pyrMemory(g) {
  const v = g.pyr, me = g.me, host = g.is_host, seat = v.seats.find((s) => s.pid === me?.pid);
  const manual = host ? v.seats.filter((s) => s.manual && !s.answered) : [];
  const forSeat = pyrMemFor ? v.seats.find((s) => s.pid === pyrMemFor) : seat;
  const done = forSeat ? forSeat.answered : true;
  return `<div class="py-hero"><div class="py-hero-k">🧠 Test de mémoire</div><div class="py-hero-t">Tes 4 cartes, de gauche à droite</div>
      <div class="artist">${v.memory_done}/${v.seats.length} ont répondu · seule la valeur compte</div></div>
    ${manual.length ? `<div class="py-manual">${manual.map((s) => `<button class="py-mini ${pyrMemFor === s.pid ? "ok" : ""}" data-pyr="memfor" data-who="${esc(s.pid)}">✍️ ${esc(s.name)}</button>`).join("")}${pyrMemFor ? `<button class="py-mini" data-pyr="memfor" data-who="">Moi</button>` : ""}</div>` : ""}
    ${forSeat && !done ? `<div class="py-panel">
      ${pyrMemFor ? `<div class="py-proxy">Tu réponds pour ${esc(forSeat.name)}</div>` : ""}
      <div class="py-mem-slots">${pyrMem.map((m, k) => `<button type="button" class="py-mem ${k === pyrMemSlot ? "on" : ""}" data-pyr="memslot" data-slot="${k}"><b>${m || "?"}</b><small>${k + 1}</small></button>`).join("")}</div>
      <div class="py-keys">${PYR_VALUES.map((x) => `<button type="button" data-pyr="memkey" data-val="${x}">${x}</button>`).join("")}</div>
      <button class="py-main" data-pyr="memsend" ${pyrMem.every(Boolean) ? "" : "disabled"}>Valider mes 4 cartes</button></div>`
      : `<div class="py-wait">${forSeat ? "C'est noté ✓ En attente des autres…" : "Les joueurs fouillent leur mémoire…"}</div>`}
    ${host ? `<button class="py-sub" data-gact="presults">Voir les résultats maintenant</button>` : ""}`;
}

function pyrBoat(g) {
  const v = g.pyr, b = v.bstate || {}, me = g.me, host = g.is_host, mine = v.boat?.pid === me?.pid;
  const steps = [1, 2, 3, 4].map((i) => `<span class="${i < b.step ? "done" : i === b.step && g.phase === "boat" ? "on" : ""}">${i}</span>`).join("<i></i>");
  if (b.last && b.last.n > (pyrSeen.boat || 0)) {
    const first = pyrSeen.boat === undefined;
    pyrSeen.boat = b.last.n;
    if (!first) {
      pyrFlash(b.last.ok ? "good" : "bad", b.last.ok ? "Bien vu !" : "Raté ! Retour au début", b.last.ok ? esc(PYR_ANS[b.last.value]) : "1 gorgée", b.last.card);
      if (b.last.poteau) setTimeout(() => pyrFlash("summit", "POTEAU !", v.poteau_hard ? `Deux fois la même carte · ${esc(v.boat?.name)} boit cul sec ! 🥃` : "Deux fois la même carte · tout le monde boit 1 gorgée 🍻", b.last.card), 2500);
    }
  }
  const ref = b.step === 2 ? b.cards.slice(0, 1) : b.step === 3 ? b.cards.slice(0, 2) : [];
  const end = g.phase === "end" ? `<div class="py-hero"><div class="py-hero-k">${b.result === "won" ? "🏆 Bateau réussi" : "🌊 Paquet terminé"}</div>
      <div class="py-hero-t">${esc(v.boat.name)} : ${sipWord(b.sips)} en ${b.tries} essai${b.tries > 1 ? "s" : ""}</div></div>
      ${host ? `<button class="py-main" data-gact="restart">🔁 Rejouer avec les mêmes joueurs</button>` : ""}` : "";
  return `<div class="py-turn ${mine ? "me" : ""}"><div class="py-turn-k">🚢 Le bateau</div><div class="py-turn-name">${mine ? "C'EST TOI !" : esc(v.boat?.name || "")}</div></div>
    <div class="py-steps">${steps}</div>
    <div class="py-stake">Essai ${b.tries || 1} · ${sipWord(b.sips || 0)} bue${(b.sips || 0) > 1 ? "s" : ""} · ${v.deck_left} cartes restantes</div>
    <div class="py-ref">${b.cards?.map((c) => pyCard(c, "md")).join("") || ""}</div>
    ${end || ((mine || host) ? pyrQuestion(g, b.step, ref, mine ? "" : v.boat.pid, "pbans") : `<div class="py-q">${PYR_Q[b.step].q}</div><div class="py-wait">${esc(v.boat.name)} réfléchit…</div>`)}`;
}

// Roue du bateau (égalité au test de mémoire) : même tirage sur tous les écrans.
function pyrWheel(g) {
  const sp = g.pyr?.spin;
  if (g.phase !== "boatpick" || !sp || !$("pyrWheel")) return;
  const w = $("pyrWheel"), n = sp.names.length, target = (sp.index + 0.5 + (sp.jitter || 0)) * (360 / n);
  if (pyrWheelSpin === sp.id) { w.style.transform = `rotate(${pyrWheelRot}deg)`; return; }
  pyrWheelSpin = sp.id;
  const left = Math.max(0, 4.8 - sp.age), base = 360 * (left ? 6 : 1);
  pyrWheelRot = base - ((target % 360) + 360) % 360;
  if (left > 0.3) {
    w.style.transition = "none"; w.style.transform = "rotate(0deg)"; void w.getBoundingClientRect();
    w.style.transition = `transform ${left}s cubic-bezier(.12,.8,.12,1)`; w.style.transform = `rotate(${pyrWheelRot}deg)`;
    setTimeout(() => { pyrWheelShown = sp.id; if (game?.pyr?.spin?.id === sp.id) { renderGame(game); pyrFlash("bad", `${esc(game.pyr.boat.name)} fait le bateau !`, "🚢 Bon courage…"); } }, left * 1000 + 100);
  } else { w.style.transform = `rotate(${pyrWheelRot}deg)`; pyrWheelShown = sp.id; }
}

document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-pyr]");
  if (!b || !game) return;
  const a = b.dataset.pyr, who = b.dataset.who || "";
  if (a === "exit") { pyrFull = false; return renderGame(game); }
  if (a === "enter") return openGameFull();
  if (a === "pans" || a === "pbans") { haptic(20); return gameAction(a, { target: b.dataset.val, who }); }
  if (a === "reveal") return gameAction("preveal", { amount: +b.dataset.slot, who });
  if (a === "claimfor") return gameAction("pclaim", { who });
  if (a === "peeksel") { const k = +b.dataset.slot; pyrPeekSel = pyrPeekSel.includes(k) ? pyrPeekSel.filter((x) => x !== k) : [...pyrPeekSel, k]; return renderGame(game); }
  if (a === "peek") { const slots = pyrPeekSel; pyrPeekSel = []; return gameAction("ppeek", { slots }); }
  if (a === "memfor") { pyrMemFor = who; pyrMem = ["", "", "", ""]; pyrMemSlot = 0; return renderGame(game); }
  if (a === "memslot") { pyrMemSlot = +b.dataset.slot; return renderGame(game); }
  if (a === "memkey") { pyrMem[pyrMemSlot] = b.dataset.val; pyrMemSlot = Math.min(3, pyrMemSlot + 1); return renderGame(game); }
  if (a === "memsend") {
    const values = pyrMem.slice(), forWho = pyrMemFor;
    pyrMem = ["", "", "", ""]; pyrMemSlot = 0; pyrMemFor = "";
    return gameAction("pmem", { values, who: forWho });
  }
});

function renderPyrHost(g) {
  patch.gameHost = `<h2>À la table (${g.players.length})</h2>
    <div class="list">${g.players.map((p) => `<div class="track"><div class="meta"><div class="title">${esc(p.name)}${p.host ? " 🎲" : ""}${playerTag(g, p)}${sipsBadge(p)}</div></div>
      ${g.is_host && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure de la partie" aria-label="Exclure de la partie">✕</button>` : ""}</div>`).join("")
      || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.phase === "lobby" ? manualForm(g) : ""}
    ${g.is_host && !g.me && g.phase === "lobby" ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// 🎲👑 Biskit Royal : chaque carte (rouge ou noire) a son effet ; certaines font rouler les dés du Biskit.
const BK_RANKS = [["A", "As"], ["2", "2"], ["3", "3"], ["4", "4"], ["5", "5"], ["6", "6"], ["7", "7"], ["8", "8"], ["9", "9"], ["T", "10"], ["J", "Valet"], ["Q", "Dame"], ["K", "Roi"]];
const BK_RULES = {
  "A-red": ["🌊", "Cascade", "Tu commences à boire, tout le monde suit dans l'ordre de la table. Chacun peut s'arrêter seulement quand son voisin de droite s'est arrêté."],
  "A-black": ["🌊", "Cascade inversée", "Ton voisin de gauche commence, toute la table suit… et toi tu t'arrêtes en dernier."],
  "2-red": ["🎁", "Distribue 2", "Tu distribues 2 gorgées à qui tu veux."],
  "2-black": ["🍻", "Bois 2", "Tu bois 2 gorgées."],
  "3-red": ["🎁", "Distribue 3", "Tu distribues 3 gorgées à qui tu veux."],
  "3-black": ["🍻", "Bois 3", "Tu bois 3 gorgées."],
  "4-red": ["🎲", "Biskit", "Tu lances les dés. Un 3 : le Biskit boit (un double 3 : tu deviens le Biskit). Total 7 : ton voisin de gauche boit 2. Total 11 : ton voisin de droite boit 2. Total 9 : tu inventes une mini-règle ou tu choisis qui boit 2. Un double : tu distribues la valeur d'un dé."],
  "4-black": ["🎲", "Biskit contre toi", "Ton voisin de gauche lance les dés pour toi : c'est toi la cible. Total 7 ou 11 : tu bois 2. Total 9 : tu bois 1. Un double : tu bois la valeur d'un dé. Un 3 : le Biskit boit quand même (double 3 : tu deviens le Biskit)."],
  "5-red": ["🙅", "Je n'ai jamais", "Tu dis « Je n'ai jamais… » : tous ceux qui l'ont déjà fait boivent."],
  "5-black": ["🙅", "Je n'ai jamais (contre toi)", "Les autres te posent un « Je n'ai jamais… » : si tu l'as déjà fait, tu bois."],
  "6-red": ["👭", "Les filles boivent", "Toutes les filles de la table boivent."],
  "6-black": ["👬", "Les gars boivent", "Tous les garçons de la table boivent."],
  "7-red": ["☝️", "Paradis", "Un bouton apparaît sur tous les téléphones : lève la main ET touche-le. Le dernier boit."],
  "7-black": ["👃", "Doigt sur le nez", "Un bouton apparaît sur tous les téléphones : doigt sur le nez ET touche-le. Le dernier boit."],
  "8-red": ["🤝", "Pote de boisson", "Choisis ton pote : chaque fois que l'un de vous boit, l'autre boit aussi, jusqu'au prochain 8."],
  "8-black": ["🤝", "Pote imposé", "Ton voisin de droite devient ton pote de boisson, jusqu'au prochain 8."],
  "9-red": ["🗂️", "Catégories", "Choisis un thème (marques de bière, pays…) : chacun cite un mot à tour de rôle. Le premier qui sèche ou se répète boit."],
  "9-black": ["🎤", "Rimes", "Dis un mot : chacun trouve une rime à tour de rôle. Le premier qui sèche boit."],
  "T-red": ["🤐", "Maître des questions", "Jusqu'au prochain 10 rouge : quiconque répond à une de tes questions boit."],
  "T-black": ["👍", "Maître du pouce", "Jusqu'au prochain 10 noir : quand tu poses ton pouce sur la table, le dernier à t'imiter boit."],
  "J-red": ["📜", "Invente une règle", "Écris une règle (« interdit de dire boire »…) : elle s'affiche sur tous les écrans. Qui l'enfreint boit."],
  "J-black": ["❌", "Supprime une règle", "Choisis une règle en cours et supprime-la."],
  "Q-red": ["💃", "La Reine désigne", "Tu désignes quelqu'un : il boit 2."],
  "Q-black": ["🎯", "Duel", "Choisis un adversaire : chacun lance un dé, le plus petit boit 2 (égalité : les deux boivent 1)."],
  "K-red": ["👑", "Coupe du Roi", "Verse un peu de ton verre dans la coupe du Roi. Le 4e Roi tiré boit la coupe entière… et la partie s'arrête !"],
  "K-black": ["👑", "Coupe du Roi", "Verse un peu de ton verre dans la coupe du Roi. Le 4e Roi tiré boit la coupe entière… et la partie s'arrête !"],
};
const BK_DICE = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
let bkSeen = { n: -1, reflex: "", turnBuzz: "" }, bkRuleDraft = "";

function bkRulesHtml() {
  return `
    <h3>Le principe</h3>
    <p>Chacun son tour, on tire une carte (elle s'affiche sur tous les téléphones). <b>Chaque valeur a deux effets selon sa couleur</b> : ♥♦ rouge plutôt « tu donnes », ♠♣ noir plutôt « tu prends ». La table tourne vers la <b>gauche</b> (le voisin de gauche est le joueur suivant).</p>
    <p>Les gorgées indiquées sont doublées si l'animateur a choisi ×2. Sans alcool, ce sont des points de gage.</p>
    <h3>Les cartes</h3>
    <div class="bk-rules">${BK_RANKS.map(([r, label]) => `
      <div class="bk-rule-rank"><div class="bk-rule-name">${label}</div>
        ${["red", "black"].map((c) => { const [ic, t, txt] = BK_RULES[`${r}-${c}`]; return `<div class="bk-rule ${c}" data-rule="${r}-${c}">
          <span class="bk-rule-col">${c === "red" ? "♥♦" : "♠♣"}</span><div><b>${ic} ${t}</b><div>${txt}</div></div></div>`; }).join("")}
      </div>`).join("")}</div>
    <h3>🍪 Le Biskit</h3>
    <p>Un joueur tiré au sort au début porte le titre de <b>Biskit</b> (affiché en permanence). Chaque fois qu'un dé fait 3, il boit. Un double 3 fait changer le Biskit de main.</p>
    <h3>Fin de partie</h3>
    <p>Au <b>4e Roi</b> (qui boit la coupe) ou quand le paquet est vide. Les règles inventées, les potes de boisson et les maîtres sont affichés en permanence sur tous les écrans.</p>
    <p>Buvez avec modération : un verre d'eau compte aussi.</p>`;
}

// Bouton « Tirer » : bloqué quelques secondes après chaque carte, le temps que tout le monde lise le gage.
function bkDrawBtn(cls, label, wait, who) {
  const at = Date.now() + (wait || 0) * 1000;
  return `<button class="${cls}" data-bk="draw" ${who ? `data-who="${esc(who)}"` : ""} data-ready-at="${at}" data-label="${esc(label)}"
    ${wait > 0 ? "disabled" : ""}>${wait > 0 ? `⏳ Lis le gage… ${Math.ceil(wait)} s` : label}</button>`;
}
setInterval(() => {
  document.querySelectorAll("[data-ready-at]").forEach((b) => {
    const left = Number(b.dataset.readyAt) - Date.now();
    if (left > 0) { b.disabled = true; b.textContent = `⏳ Lis le gage… ${Math.ceil(left / 1000)} s`; }
    else if (b.disabled) { b.disabled = false; b.innerHTML = b.dataset.label; b.removeAttribute("data-ready-at"); haptic(60); }
  });
}, 250);

function bkHtml(g) {
  const v = g.bk, me = g.me, host = g.is_host;
  const seat = (pid) => v.seats?.find((s) => s.pid === pid);
  const top = `<div class="py-top">
    <button type="button" class="py-icon" data-pyr="exit" aria-label="Quitter le plein écran (code, joueurs)">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button>
    <div class="py-top-mid"><div class="py-phase">Biskit Royal${v.drawn ? ` · carte ${v.drawn}` : ""}</div><div class="py-code">code <b>${esc(g.code)}</b></div></div>
    ${helpBtn("biskit", true)}</div>`;
  if (g.phase === "lobby") {
    return `<div class="py-hero"><div class="py-hero-k">🎲👑 Biskit Royal</div><div class="py-hero-t">${g.players.length} joueur${g.players.length > 1 ? "s" : ""}</div>
      <div class="artist">${v.alcohol ? `Avec alcool · gorgées ×${v.mult}` : "Sans alcool (points de gage)"} · l'ordre des joueurs = l'ordre autour de la table</div></div>
      ${host ? `<button class="py-main" data-gact="start" ${g.players.length < 2 ? "disabled" : ""}>▶︎ Commencer la partie</button>`
        : me ? `<div class="py-wait">Tu es à la table ✓ L'animateur va lancer…</div>` : `<button class="py-main" data-gact="join">S'asseoir à la table</button>`}`;
  }
  // Événements : vibration quand c'est ton tour ou qu'un réflexe démarre.
  const turnKey = `${v.drawn}-${v.turn}`;
  if (v.reflex && !v.reflex.done && bkSeen.reflex !== v.reflex.id) { bkSeen.reflex = v.reflex.id; haptic([200, 80, 200]); }
  // Nouvelle carte : le gage en plein écran sur tous les téléphones (pas en différé après un rechargement).
  if (bkSeen.game !== g.id) { bkSeen.game = g.id; bkSeen.drawn = v.drawn; }
  else if (v.drawn > (bkSeen.drawn || 0) && v.card && v.key) {
    bkSeen.drawn = v.drawn;
    const r = BK_RULES[v.key], o = v.outcomes.find((x) => typeof x === "object" && x.tone !== "info") || v.outcomes[0];
    const head = o ? esc(typeof o === "string" ? o : o.head) : "";
    pyrFlash(o?.tone === "give" ? "good" : o?.tone === "drink" || o?.tone === "all" ? "bad" : "summit",
      `${r[0]} ${r[1]}`, `${me && v.drawer === me.pid ? "Ta carte" : `Carte de ${esc(v.drawer_name)}`}${head ? `<br><b class="bk-flash-who">${head}</b>` : ""}`, v.card, 4300);
  }
  const fresh = v.event !== bkSeen.n;
  bkSeen.n = v.event;
  const cur = seat(v.turn);
  const status = `<div class="bk-status">
    <span class="bk-chip">👑 Coupe <b>${v.kings}/4</b></span><span class="bk-chip">🍪 Biskit <b>${esc(v.biskit)}</b></span>
    ${v.qmaster ? `<span class="bk-chip">🤐 <b>${esc(v.qmaster)}</b></span>` : ""}${v.thumb ? `<span class="bk-chip">👍 <b>${esc(v.thumb)}</b></span>` : ""}
    ${v.mates.map(([a, b]) => `<span class="bk-chip">🤝 <b>${esc(a)} + ${esc(b)}</b></span>`).join("")}
    <span class="bk-chip">🃏 ${v.deck_left}</span></div>`;
  const rule = v.key ? BK_RULES[v.key] : null;
  const card = v.card ? `<div class="bk-card ${v.key?.endsWith("red") ? "red" : "black"}">
      <div class="bk-card-face">${pyCard(v.card, "xl")}</div>
      <div class="bk-effect"><div class="bk-effect-t">${rule[0]} ${rule[1]}</div><div class="bk-effect-d">${rule[2]}</div>
        </div></div>` : "";
  const dice = v.dice ? `<div class="bk-dice ${v.dice.age < 2 ? "roll" : ""}"><span>${BK_DICE[v.dice.d[0]]}</span><span>${BK_DICE[v.dice.d[1]]}</span>
      <small>lancés par ${esc(v.dice.roller_name)} · total ${v.dice.d[0] + v.dice.d[1]}</small></div>` : "";
  const duel = v.duel ? `<div class="bk-duel ${v.duel.age < 2 ? "roll" : ""}"><b>${esc(v.duel.a_name)}</b> <span>${BK_DICE[v.duel.da]}</span> contre <span>${BK_DICE[v.duel.db]}</span> <b>${esc(v.duel.b_name)}</b></div>` : "";
  // Qui boit ? En très gros, une couleur par type d'effet (boit, distribue, tout le monde, info).
  const outs = v.outcomes.length ? `<div class="bk-who">${v.outcomes.map((o) => typeof o === "string" ? `<div class="bk-o info"><b>${esc(o)}</b></div>`
    : `<div class="bk-o ${esc(o.tone)}"><b>${esc(o.head)}</b>${o.head !== o.text ? `<span>${esc(o.text)}</span>` : ""}${(o.extra || []).map((x) => `<span class="bk-x">${esc(x)}</span>`).join("")}</div>`).join("")}</div>` : "";
  let reflex = "";
  if (v.reflex && !v.reflex.done) {
    const label = v.reflex.kind === "paradis" ? "☝️ PARADIS !" : "👃 DOIGT SUR LE NEZ !";
    reflex = `<div class="bk-reflex">${me && v.seats.some((s) => s.pid === me.pid) && !v.reflex.me_tapped
      ? `<button class="bk-tap" data-gact="btap">${label}<small>${v.reflex.kind === "paradis" ? "main levée + touche vite !" : "doigt sur le nez + touche vite !"}</small></button>`
      : `<div class="py-wait">✓ ${v.reflex.tapped.length}/${v.seats.length} ont touché…</div>`}
      ${host ? `<button class="py-sub" data-gact="bclose">Clore : ceux qui n'ont pas touché boivent</button>` : ""}</div>`;
  }
  let action = "";
  if (v.await) {
    const canDo = v.await.mine || host, others = v.seats.filter((s) => s.pid !== v.await.pid);
    const who = canDo && !v.await.mine ? `<div class="py-proxy">Tu choisis pour ${esc(v.await.name)}</div>` : "";
    if (!canDo) action = `<div class="py-wait">${esc(v.await.name)} choisit…</div>`;
    else if (["mate", "queen", "duel"].includes(v.await.kind)) action = `<div class="py-panel"><div class="py-turn-k">${{ mate: "Choisis ton pote de boisson", queen: "Qui boit 2 ?", duel: "Contre qui ce duel ?" }[v.await.kind]}</div>
        <div class="chips bk-pick">${others.map((s) => `<button class="py-mini" data-bk="pick" data-target="${esc(s.pid)}" ${v.await.mine ? "" : `data-who="${esc(v.await.pid)}"`}>${esc(s.name)}</button>`).join("")}</div>${who}</div>`;
    else if (v.await.kind === "rule") action = `<div class="py-panel"><div class="py-turn-k">Écris ta règle</div>
        <form data-bk-form="rule" class="row"><input class="grow" type="text" id="bkRule" maxlength="120" aria-label="Ta règle" placeholder="Ex. : interdit de dire « boire »" autocomplete="off"><button class="py-mini ok">OK</button></form>${who}</div>`;
    else action = `<div class="py-panel"><div class="py-turn-k">Quelle règle supprimer ?</div>
        <div class="bk-pick">${v.rules.map((r) => `<button class="py-sub" data-bk="pick" data-target="${esc(r.id)}" ${v.await.mine ? "" : `data-who="${esc(v.await.pid)}"`}>❌ ${esc(r.text)}</button>`).join("")}</div>${who}</div>`;
  }
  // La carte est résolue (plus de choix ni de réflexe en attente) : elle devient « la carte précédente »,
  // et le tour suivant s'affiche à part, pour ne jamais confondre l'action d'un autre avec la sienne.
  const resolved = g.phase === "play" && !v.await && (!v.reflex || v.reflex.done);
  let next = "";
  if (resolved) {
    next = v.my_turn ? `<div class="bk-now me"><div class="bk-now-k">C'est ton tour</div><div class="bk-now-t">À TOI !</div>
        ${bkDrawBtn("py-main", "🃏 Tirer une carte", v.wait, "")}</div>`
      : `<div class="bk-now"><div class="bk-now-k">Au tour de</div><div class="bk-now-t">${esc(cur?.name || "…")}</div>
        ${host && cur ? bkDrawBtn("py-sub", `🃏 Tirer pour ${esc(cur.name)}`, v.wait, cur.pid) : `<div class="artist">Attends qu'il ou elle tire…</div>`}</div>`;
  }
  const mineCard = me && v.drawer === me.pid;
  const last = v.card ? `<section class="bk-last ${resolved ? "past" : "live"}">
      <div class="bk-last-k">${resolved ? `🕘 Carte précédente · ${mineCard ? "c'était la tienne" : `tirée par ${esc(v.drawer_name)}`}`
        : mineCard ? "🃏 Ta carte" : `🃏 Carte de ${esc(v.drawer_name)}`}</div>
      ${card}${dice}${duel}${outs}${reflex}${action}</section>` : (g.phase === "play" ? `<div class="py-wait">Personne n'a encore tiré de carte…</div>` : "");
  const end = g.phase === "end" ? `<div class="py-hero"><div class="py-hero-k">🏁 Fin de la partie</div>
      <div class="py-hero-t">${v.final ? `${esc(v.final)} boit la coupe du Roi 👑` : "Le paquet est vide"}</div></div>
      ${host ? `<button class="py-main" data-gact="restart">🔁 Rejouer</button>` : ""}` : "";
  const rules = v.rules.length ? `<div class="py-panel bk-active"><div class="py-turn-k">📜 Règles en cours</div>${v.rules.map((r) => `<div>« ${esc(r.text)} » <small>par ${esc(r.by)}</small></div>`).join("")}</div>` : "";
  const table = `<h3 class="py-h">La table (vers la gauche ↓)</h3><div class="py-seats">${v.seats.map((s) => `
    <div class="py-seat ${s.pid === v.turn && g.phase === "play" ? "on" : ""} ${s.pid === me?.pid ? "me" : ""}">
      <div class="py-seat-name">${esc(s.name)}${s.manual ? " ✍️" : ""}${s.biskit ? " 🍪" : ""}${s.qmaster ? " 🤐" : ""}${s.thumb ? " 👍" : ""}${s.mate ? " 🤝" : ""}</div>
      <span class="artist">🍻 ${s.drink} · 🎁 ${s.give}</span></div>`).join("")}</div>`;
  return `<div class="py-body">${status}${end}${next}${last}${rules}</div>`;
}
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-bk]");
  if (!b || !game) return;
  if (b.dataset.bk === "draw") { haptic(20); return gameAction("bdraw", { who: b.dataset.who || "" }); }
  if (b.dataset.bk === "pick") return gameAction("bpick", { target: b.dataset.target, who: b.dataset.who || "" });
});
document.addEventListener("submit", (ev) => {
  const f = ev.target.closest("[data-bk-form]");
  if (!f || !game) return;
  ev.preventDefault();
  const text = $("bkRule").value.trim();
  if (text) gameAction("bpick", { guess: text, who: game.bk.await && !game.bk.await.mine ? game.bk.await.pid : "" });
});
function renderBkHost(g) {
  const movable = g.is_host && g.phase === "lobby";
  patch.gameHost = `<h2>Autour de la table (${g.players.length})</h2>
    ${movable ? `<p class="artist" style="margin:-4px 0 8px">Range les joueurs dans l'ordre où ils sont assis (vers la gauche) avec ⬆ ⬇.</p>` : ""}
    <div class="list">${g.players.map((p, i) => `<div class="track"><div class="meta"><div class="title">${i + 1}. ${esc(p.name)}${p.host ? " 🎲" : ""}${playerTag(g, p)}${sipsBadge(p)}</div></div>
      <div class="icon-btns">
        ${movable && i > 0 ? `<button class="secondary" data-gact="up" data-target="${esc(p.pid)}" title="Monter" aria-label="Monter">⬆</button>` : ""}
        ${movable && i < g.players.length - 1 ? `<button class="secondary" data-gact="down" data-target="${esc(p.pid)}" title="Descendre" aria-label="Descendre">⬇</button>` : ""}
        ${g.is_host && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure" aria-label="Exclure">✕</button>` : ""}
      </div></div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.phase === "lobby" ? manualForm(g) : ""}
    ${g.is_host && !g.me && g.phase === "lobby" ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// 🛋️ Le Divan : une grande carte de couleur, retournée à chaque tirage.
const DV_ICONS = { experiences: "🌄", emotions: "💗", relations: "🤝", childhood: "🧸", dreams: "🌠", whatif: "🔮", couple: "💞" };
let dvSeen = 0;
function divanHtml(g) {
  const d = g.divan;
  if (g.phase === "lobby") return `<div class="title">${g.is_host ? "Ouvre la séance quand tout le monde est installé." : "La séance va commencer…"}</div>
    <div class="artist" style="margin-top:6px">Catégories : ${d.cats.map((c) => `${DV_ICONS[c]} ${d.labels[c]}`).join(" · ")}</div>
    ${!g.me && !g.master ? `<button data-gact="join" style="width:100%;margin-top:12px">Rejoindre la séance</button>` : ""}`;
  // Nouvelle carte (ou retour en arrière) : on la retourne à l'écran.
  const c = d.card, fresh = c && c.id !== dvSeen;
  if (c) dvSeen = c.id;
  if (fresh && d.my_turn) haptic(80);
  const who = d.current?.name || "…";
  return `<div class="dv-who ${d.my_turn ? "me" : ""} ${fresh ? "dv-new" : ""}">
      <div class="dv-avatar" aria-hidden="true">${esc([...who][0]?.toUpperCase() || "?")}</div>
      <div class="dv-who-text"><div class="dv-who-label">${d.my_turn ? "🛋️ C'est ton tour !" : "🛋️ Sur le divan"}</div>
        <div class="dv-who-name">${d.my_turn ? "À toi de répondre" : esc(who)}</div></div>
    </div>
    ${c ? `<div class="dv-card dv-${c.cat} ${fresh ? "dv-flip" : ""} ${d.can_lead ? "dv-swipe" : ""}">
      ${d.can_lead ? `<div class="dv-stamp dv-stamp-next">Au suivant ▶︎</div><div class="dv-stamp dv-stamp-joker">${d.joker ? "Joker utilisé" : "🃏 Joker"}</div>` : ""}
      <div class="dv-cat">${DV_ICONS[c.cat]} ${d.labels[c.cat]}</div>
      <div class="dv-q">${esc(c.text)}</div>
      <div class="dv-foot">Le Divan · carte ${c.id}</div></div>
    ${d.can_lead ? `<div class="dv-hint">← Glisse : au suivant · ${d.joker ? "joker déjà utilisé" : "joker : glisse →"}</div>` : ""}` : ""}
    <div class="dv-actions">
      ${!d.my_turn && g.me ? `<button class="${d.hearted ? "" : "secondary"}" data-gact="dheart" ${d.hearted ? "disabled" : ""}>${d.hearted ? "❤️ Soutien envoyé" : "🤍 Envoyer du soutien"}</button>` : ""}
      ${d.hearts ? `<div class="dv-hearts" aria-label="${d.hearts} soutiens">${"❤️".repeat(Math.min(d.hearts, 12))}</div>` : ""}
    </div>
    ${!g.me && !g.master ? `<button data-gact="join" style="width:100%;margin-top:12px">Rejoindre la séance</button>` : ""}`;
}
// Glisser la carte, comme Tinder : vers la gauche = au suivant, vers la droite = joker.
let dvDrag = null, dvPending = null;
document.addEventListener("pointerdown", (ev) => {
  const card = ev.target.closest(".dv-swipe");
  if (!card || ev.button > 0) return;
  dvDrag = { card, x: ev.clientX, y: ev.clientY, dx: 0, id: ev.pointerId };
  card.setPointerCapture(ev.pointerId);
  card.classList.remove("dv-flip", "dv-back");
});
document.addEventListener("pointermove", (ev) => {
  if (!dvDrag || ev.pointerId !== dvDrag.id) return;
  const dx = ev.clientX - dvDrag.x, dy = ev.clientY - dvDrag.y;
  dvDrag.dx = dx;
  dvDrag.card.style.transform = `translate(${dx}px, ${dy * 0.15}px) rotate(${dx / 18}deg)`;
  dvDrag.card.style.setProperty("--next", Math.max(0, Math.min(1, -dx / 100)));
  dvDrag.card.style.setProperty("--joker", Math.max(0, Math.min(1, dx / 100)));
});
async function dvRelease(ev) {
  if (!dvDrag || ev.pointerId !== dvDrag.id) return;
  const { card, dx } = dvDrag, d = game?.divan;
  dvDrag = null;
  const limit = Math.min(110, card.offsetWidth * 0.3);
  const action = dx < -limit ? "dnext" : dx > limit && d && !d.joker ? "djoker" : "";
  if (dx > limit && d?.joker) toast("Le joker de ce tour a déjà été utilisé", "err");
  card.style.removeProperty("--next"); card.style.removeProperty("--joker");
  if (!action) {
    card.classList.add("dv-back"); card.style.transform = "";
    if (dvPending) { const g = dvPending; dvPending = null; renderGame(g); }
    return;
  }
  haptic(30);
  card.classList.add("dv-back");
  card.style.transform = `translateX(${Math.sign(dx) * 150}%) rotate(${Math.sign(dx) * 25}deg)`;
  card.style.opacity = "0";
  dvPending = null;
  await gameAction(action);
  if (game && document.contains(card)) renderGame(game);  // erreur : la carte revient
}
document.addEventListener("pointerup", dvRelease);
document.addEventListener("pointercancel", dvRelease);

// 📵 Participants sans téléphone : l'animateur les ajoute à la main et agit pour eux.
const MANUAL_GAMES = ["divan", "tmc", "never", "pyramid", "biskit", "likely", "debate", "room"];
const playerTag = (g, p) => !MANUAL_GAMES.includes(g.type) ? "" : p.manual
  ? ` <span class="pill tag-manual" title="Ajouté·e à la main par l'animateur">✍️ sans téléphone</span>`
  : ` <span class="tag-phone" title="Joue sur son téléphone">📱</span>`;
const manualForm = (g) => !g.is_host || !MANUAL_GAMES.includes(g.type) || g.phase === "end" ? "" : `
  <form data-gform="addguest" class="row" style="margin-top:8px"><input class="grow" type="text" name="manualName" maxlength="30" aria-label="Prénom d'un participant sans téléphone" spellcheck="false" placeholder="Prénom (sans téléphone)" autocomplete="off"><button class="secondary">＋ Ajouter</button></form>
  <div class="artist" style="margin-top:4px">Pour quelqu'un qui joue sans téléphone : c'est toi qui agiras pour lui ou elle.</div>`;

function renderDivanHost(g, btn) {
  const d = g.divan;
  const controls = g.phase === "lobby"
    ? (g.is_host ? btn("start", "▶︎ Ouvrir la séance", "grow", g.players.length ? "" : "disabled") : "")
    : d.can_lead || d.can_back ? (d.can_back ? btn("dback", "↩︎ Retour", "secondary") : "") + (!d.can_lead ? "" : btn("djoker", d.joker ? "Joker utilisé" : "🃏 Joker : autre carte", "secondary grow", d.joker ? "disabled" : "") + btn("dnext", "Au suivant ▶︎", "grow")) : "";
  patch.gameHost = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    <h2>Autour du divan (${g.players.length})</h2>
    <div class="list">${g.players.map((p) => `
      <div class="track ${p.pid === d.current?.pid && g.phase === "card" ? "bj-turn" : ""}">
        <div class="meta"><div class="title">${p.pid === d.current?.pid && g.phase === "card" ? "🛋️ " : ""}${esc(p.name)}${p.host ? " 🎲" : ""}${playerTag(g, p)}</div></div>
        ${g.is_host && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure de la séance" aria-label="Exclure de la séance">✕</button>` : ""}
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${manualForm(g)}
    ${g.is_host && !g.me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// 💞 Tu me connais ? : le sujet répond en secret, le devin devine, le sujet juge.
const tmcPts = (x) => Number.isInteger(x) ? String(x) : `${Math.floor(x) || ""}½`;
const TMC_VERDICT = { 1: ["✅", "Juste !"], 0.5: ["🤏", "Presque !"], 0: ["❌", "Raté !"] };
let tmSeen = "";
function tmcHtml(g) {
  const t = g.tmc, d = t.duo;
  if (!d) return "";
  // Animation seulement quand l'étape change (pas à chaque rafraîchissement).
  const key = `${g.id}:${g.round}:${g.phase}`, anim = key !== tmSeen ? "tm-anim" : "";
  tmSeen = key;
  const G = esc(d.guesser.name), S = esc(d.subject.name);
  const duo = `<div class="tm-duo"><span class="tm-who ${d.role === "guesser" ? "me" : ""}">🔮 ${d.role === "guesser" ? "Toi" : G}<small>devine</small></span>
    <span class="tm-arrow">→</span><span class="tm-who ${d.role === "subject" ? "me" : ""}">🎯 ${d.role === "subject" ? "Toi" : S}<small>répond</small></span></div>`;
  const q = `<div class="tm-q">${esc(d.question)}</div>`;
  const form = (ph) => `<form data-gform="tanswer" class="row" style="margin-top:10px"><input class="grow" type="text" id="guessInput" maxlength="80" aria-label="${ph}" placeholder="${ph}" autocomplete="off"><button>Valider</button></form>`;
  if (g.phase === "answer") {
    let zone;
    if (d.proxy) zone = `<div class="tm-speak" style="font-size:1rem">📵 ${S} n'a pas de téléphone : passe-lui le tien pour qu'il ou elle écrive sa réponse en secret.</div>${form(`Réponse de ${S}`)}`;
    else if (d.role === "subject") zone = d.mine ? "" : `<div class="artist" style="margin-top:8px">Écris <b>ta vraie réponse</b>, en secret. Elle sera révélée après que ${G} aura deviné à voix haute.</div>${form("Ta vraie réponse")}`;
    else if (d.role === "guesser") zone = `<div class="artist" style="margin-top:8px">${S} écrit sa réponse en secret… Prépare-toi : tu devras la deviner <b>à voix haute</b>.</div>`;
    else zone = `<div class="artist" style="margin-top:8px">${S} écrit sa réponse en secret…</div>`;
    return duo + q + zone;
  }
  if (g.phase === "guess") {
    const mine = d.role === "subject" ? `<div class="tm-sent">✓ Ta réponse : « ${esc(d.mine)} »</div>` : "";
    return duo + q + mine + `<div class="tm-speak ${anim}">🗣 ${d.role === "guesser" ? "À toi ! Dis à voix haute ce que" : `${G}, à toi ! Dis à voix haute ce que`} ${S} a répondu.</div>
      <div class="artist" style="margin-top:6px">${g.is_host ? "Quand c'est dit, révèle la réponse." : "L'animateur va révéler la réponse…"}</div>`;
  }
  const reveal = `<div class="tm-answer ${g.phase === "judge" ? anim : ""}"><small>${S} avait écrit</small><b>${esc(d.answer || "—")}</b></div>`;
  let zone = "";
  if (g.phase === "judge") {
    zone = d.can_judge
      ? `<div class="artist" style="margin-top:10px">Est-ce que ${G} a vu juste ?</div>
        <div class="tm-judge"><button data-gact="tjudge" data-amount="2">✅ 1 point</button><button class="secondary" data-gact="tjudge" data-amount="1">🤏 ½ point</button><button class="secondary" data-gact="tjudge" data-amount="0">❌ 0</button></div>`
      : `<div class="artist" style="margin-top:10px">L'animateur attribue les points…</div>`;
  } else if (d.verdict !== null && d.verdict !== undefined) {
    const [icon, word] = TMC_VERDICT[d.verdict];
    zone = `<div class="tm-verdict ${anim} v${String(d.verdict).replace(".", "")}">${icon} ${word} ${d.verdict ? `+${tmcPts(d.verdict)} pour ${d.role === "guesser" ? "toi" : G}` : ""}</div>`;
  }
  if (g.phase === "end") return `<div class="title">🏁 Bilan de la partie</div>${tmcPodium(g)}${tmcMine(g)}`;
  return duo + q + reveal + zone;
}
function tmcPodium(g) {
  const r = g.tmc.ranking.filter((x) => x.asked);
  const medal = ["🥇", "🥈", "🥉"];
  return r.length ? `<div class="list" style="margin-top:10px">${r.map((x, i) => `<div class="bar ${i === 0 ? "top" : ""}" style="--w:${Math.round(100 * x.pts / Math.max(1, r[0].pts))}%">
    <span>${medal[i] || ""} ${esc(x.name)}</span><b>${tmcPts(x.pts)}/${x.asked}</b></div>`).join("")}</div>` : `<div class="artist">Aucun point pour l'instant.</div>`;
}
// Mes amitiés : qui je connais le mieux, qui me connaît le mieux.
function tmcMine(g) {
  const me = g.me?.pid;
  if (!me) return "";
  const best = (rows) => rows.sort((a, b) => b.pct - a.pct || b.pts - a.pts)[0];
  const k = best(g.tmc.pairs.filter((p) => p.guesser.pid === me)), b = best(g.tmc.pairs.filter((p) => p.subject.pid === me));
  if (!k && !b) return "";
  return `<div class="tm-mine">${k ? `<div>🔮 Tu connais le mieux <b>${esc(k.subject.name)}</b> <span>${tmcPts(k.pts)}/${k.asked} · ${k.pct} %</span></div>` : ""}
    ${b ? `<div>🎯 Te connaît le mieux : <b>${esc(b.guesser.name)}</b> <span>${tmcPts(b.pts)}/${b.asked} · ${b.pct} %</span></div>` : ""}</div>`;
}
function renderTmcHost(g, btn) {
  const t = g.tmc;
  const controls = !g.is_host ? "" : {
    lobby: btn("start", "▶︎ Premier duo", "grow", g.players.length < 2 ? "disabled" : ""),
    answer: btn("tq", "🔄 Autre question", "secondary") + btn("next", "⏭ Autre duo", "secondary grow"),
    guess: btn("treveal", "👁 Révéler la réponse", "grow") + btn("next", "⏭", "secondary", `title="Passer ce duo"`),
    judge: btn("next", "⏭ Passer", "secondary grow"),
    scored: btn("next", "▶︎ Duo suivant", "grow"),
    end: btn("restart", "🔁 Rejouer (scores à zéro)", "grow"),
  }[g.phase] || "";
  const finish = g.is_host && !["lobby", "end"].includes(g.phase) ? `<button class="secondary" data-gact="finish" style="width:100%;margin-top:8px">🏁 Terminer et voir le bilan</button>` : "";
  const playing = g.phase !== "lobby";
  patch.gameHost = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}${finish}
    ${playing && g.phase !== "end" ? tmcMine(g) : ""}
    ${playing && g.phase !== "end" ? `<h2>Classement</h2>${tmcPodium(g)}` : ""}
    ${playing && t.duos.length ? `<h2>Meilleurs duos</h2><div class="list">${t.duos.slice(0, 5).map((x, i) => `<div class="track"><div class="meta">
      <div class="title">${i === 0 ? "💞 " : ""}${esc(x.a.name)} & ${esc(x.b.name)}</div><div class="artist">${tmcPts(x.pts)}/${x.asked} · ${x.pct} % de bonnes réponses</div></div></div>`).join("")}</div>` : ""}
    <h2>Joueurs (${g.players.length})</h2>
    <div class="list">${g.players.map((p) => `
      <div class="track ${t.duo && g.phase !== "end" && [t.duo.guesser.pid, t.duo.subject.pid].includes(p.pid) ? "bj-turn" : ""}">
        <div class="meta"><div class="title">${esc(p.name)}${p.host ? " 🎲" : ""}${playerTag(g, p)}</div></div>
        ${g.is_host && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure de la partie" aria-label="Exclure de la partie">✕</button>` : ""}
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${manualForm(g)}
    ${g.is_host && !g.me && (g.phase === "lobby" || g.phase === "end") ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// 🎰 Casino : roue européenne en SVG ; la roue et la bille tournent en sens inverse, même tirage sur tous les écrans.
const WHEEL = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
const RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
const numColor = (n) => n === 0 ? "green" : RED.has(n) ? "red" : "black";
const BET_LABELS = { "color:red": "Rouge", "color:black": "Noir", "parity:even": "Pair", "parity:odd": "Impair",
  "half:low": "1-18", "half:high": "19-36", "dozen:1": "1-12", "dozen:2": "13-24", "dozen:3": "25-36" };
const betLabel2 = (key) => BET_LABELS[key] || key.split(":")[1];
function casinoWins(key, n) {
  const [kind, t] = key.split(":");
  if (kind === "n") return +t === n;
  if (n === 0) return false;
  return { color: () => RED.has(n) === (t === "red"), parity: () => (n % 2 === 0) === (t === "even"),
    half: () => (n <= 18) === (t === "low"), dozen: () => Math.floor((n - 1) / 12) + 1 === +t }[kind]();
}
let cwBuilt = false, cwSpin = "", cwRot = 0, cbRot = 0, cwShown = "", casinoChip = 0, cwSpinningUntil = 0;

function casinoWheelSvg() {
  const a = 360 / 37, rad = (d) => (d - 90) * Math.PI / 180;
  const pt = (r, d) => `${(r * Math.cos(rad(d))).toFixed(2)} ${(r * Math.sin(rad(d))).toFixed(2)}`;
  let out = `<defs><radialGradient id="cwGold" cx="40%" cy="35%"><stop offset="0" stop-color="#fff3c4"/><stop offset=".5" stop-color="#e2b04a"/><stop offset="1" stop-color="#7a5418"/></radialGradient>
    <radialGradient id="cwWood" cx="50%" cy="50%"><stop offset=".8" stop-color="#4a2a12"/><stop offset="1" stop-color="#2a170a"/></radialGradient></defs>
    <circle r="108" fill="url(#cwWood)" stroke="#c9973a" stroke-width="2"/><circle r="94" fill="#1a1012" stroke="#c9973a" stroke-width="1"/>`;
  WHEEL.forEach((n, i) => {
    const d0 = (i - 0.5) * a, d1 = (i + 0.5) * a;
    const fill = { green: "#0f7b3e", red: "#c8102e", black: "#16121f" }[numColor(n)];
    out += `<path d="M${pt(92, d0)} A92 92 0 0 1 ${pt(92, d1)} L${pt(62, d1)} A62 62 0 0 0 ${pt(62, d0)} Z" fill="${fill}" stroke="#c9973a" stroke-width=".6"/>`;
    out += `<text transform="rotate(${(i * a).toFixed(2)}) translate(0 -81)" text-anchor="middle" dominant-baseline="middle" fill="#fff" font-size="8.5" font-weight="800" font-family="system-ui">${n}</text>`;
  });
  out += `<circle r="62" fill="#2a170a" stroke="#c9973a" stroke-width="1.2"/><circle r="50" fill="url(#cwGold)" opacity=".9"/>`;
  for (let i = 0; i < 8; i++) out += `<path d="M0 0 L${pt(46, i * 45)}" stroke="#7a5418" stroke-width="3" stroke-linecap="round"/>`;
  return out + `<circle r="14" fill="url(#cwGold)" stroke="#7a5418" stroke-width="2"/><circle r="5" fill="#fff3c4"/>`;
}

function revealCasino(g) {
  const sp = g.casino.spin;
  const show = g.phase === "results" && sp && cwShown === sp.id;
  $("cwResult").innerHTML = show
    ? `<div class="cw-num ${numColor(sp.number)}">${sp.number}</div><div class="cw-desc">${sp.number === 0 ? "Zéro ! La maison gagne" : `${RED.has(sp.number) ? "Rouge" : "Noir"} · ${sp.number % 2 ? "Impair" : "Pair"} · ${sp.number <= 18 ? "1-18" : "19-36"}`}</div>` : "";
  // Derniers numéros (le tout dernier n'apparaît qu'une fois la bille arrêtée).
  const hist = (show || g.phase !== "results" ? g.casino.history : g.casino.history.slice(1)).slice(0, 14);
  $("cwHistory").innerHTML = hist.map((n) => `<span class="cw-h ${numColor(n)}">${n}</span>`).join("");
}

function casinoFx(g) {
  const r = g.casino.me?.result, sp = g.casino.spin;
  if (!r || fxSeen === "c" + sp.id || (sp.age ?? 0) > 20) return;
  fxSeen = "c" + sp.id;
  if (document.hidden) return;
  if (drinks(g)) {
    const kind = r.give && r.drink ? "mixed" : r.give ? (r.jackpot ? "jackpot" : "win") : "lose";
    const sub = [r.drink ? `🍻 Bois ${sipWord(r.drink)}` : "", r.give ? `🎉 Distribue ${sipWord(r.give)}` : ""].filter(Boolean).join(" · ");
    return playFx(kind, sub);
  }
  const kind = r.net > 0 ? (r.jackpot ? "jackpot" : "win") : r.net < 0 ? "lose" : "push";
  playFx(kind, r.net > 0 ? `+${r.net} jetons` : r.net < 0 ? `${r.net} jetons` : "Ni gagné ni perdu");
}

function renderCasino(g) {
  const box = $("casinoWheel");
  box.className = "cwheel " + (g.type === "casino" ? GAME_THEME.casino : "hidden");
  if (g.type !== "casino") return;
  if (!cwBuilt) { $("cwSvg").innerHTML = casinoWheelSvg(); cwBuilt = true; }
  const sp = g.casino.spin;
  if (g.phase === "results" && sp && sp.id !== cwSpin) {
    cwSpin = sp.id;
    const a = 360 / 37, k = WHEEL.indexOf(sp.number), left = Math.max(0, 7 - sp.age);
    const fresh = left > 0.4;
    const W = cwRot + (fresh ? 720 : 0) + (((sp.wheel - cwRot) % 360) + 360) % 360;
    const P = ((k * a + W) % 360 + 360) % 360;
    const B = cbRot - (fresh ? 360 * 4 : 0) - (((cbRot - P) % 360) + 360) % 360;
    cwRot = W; cbRot = B;
    const svg = $("cwSvg"), orbit = $("cwOrbit"), ball = $("cwBall");
    svg.style.transition = fresh ? `transform ${left}s cubic-bezier(.15,.6,.2,1)` : "none";
    orbit.style.transition = fresh ? `transform ${left}s cubic-bezier(.2,.62,.25,1)` : "none";
    svg.style.transform = `rotate(${W}deg)`;
    orbit.style.transform = `rotate(${B}deg)`;
    ball.style.animation = "none"; void ball.offsetWidth;
    ball.style.animation = fresh ? `cw-drop ${left}s linear forwards` : "none";
    ball.classList.toggle("landed", !fresh);
    if (fresh) {
      GameAudio.play("spin");
      cwSpinningUntil = Date.now() + left * 1000;
      setTimeout(() => {
        cwShown = sp.id;
        if (game?.casino?.spin?.id === sp.id) renderGame(game);  // résultat, tapis et animation personnelle
      }, left * 1000 + 150);
    } else cwShown = sp.id;
  }
  if (g.phase === "bet" && !sp) { $("cwBall").classList.remove("landed"); }
  revealCasino(g);
  if (cwShown === sp?.id) casinoFx(g);
}

function casinoStatusHtml(g) {
  const c = g.casino, me = c.me, sp = c.spin;
  const rolling = g.phase === "results" && sp && cwShown !== sp.id;
  if (g.phase === "lobby") return `<div class="title">${g.is_host ? "Ouvre la table quand tout le monde est installé." : "La table va ouvrir…"}</div>`;
  if (rolling) return `<div class="title">Rien ne va plus… la bille roule ! 🎲</div>`;
  if (g.phase === "bet") {
    const limit = c.drinks || me?.chips || 0;
    return `<div class="title">Faites vos jeux !</div>
      <div class="artist">${!me ? "Assieds-toi pour miser." : `Ta mise : <b>${me.staked}</b> / ${limit} ${c.drinks ? "gorgée" + (limit > 1 ? "s" : "") : "jetons"}`}</div>
      ${c.drinks ? `<div class="artist" style="font-size:.8rem;margin-top:4px">Perdu : tu bois ta mise · chance simple : distribue ×2 · douzaine : ×3 · plein : ×10 · zéro : +1 pour tous</div>` : ""}`;
  }
  const r = me?.result;
  const mine = !r ? (me ? "Tu n'avais rien misé." : "")
    : c.drinks ? [r.drink ? `🍻 tu bois ${sipWord(r.drink)}` : "", r.give ? `🎉 tu distribues ${sipWord(r.give)}` : ""].filter(Boolean).join(" · ") || "Rien à boire"
    : r.net > 0 ? `Gagné : +${r.net} jetons${r.jackpot ? " 🎯" : ""}` : r.net < 0 ? `Perdu : ${r.net} jetons` : "Ni gagné ni perdu";
  return `<div class="title">Le ${sp.number} ${sp.number === 0 ? "vert" : RED.has(sp.number) ? "rouge" : "noir"} est sorti !</div><div class="artist">${mine}</div>`;
}

function renderCasinoHost(g, btn) {
  const c = g.casino, me = c.me, sp = c.spin, open = g.phase === "bet";
  const revealed = g.phase === "results" && sp && cwShown === sp.id, rolling = g.phase === "results" && !revealed;
  const n = revealed ? sp.number : null;
  const bettors = c.table.filter((t) => t.staked).length;
  const controls = !g.is_host ? "" : {
    lobby: btn("start", "▶︎ Ouvrir la table", "grow", g.players.length ? "" : "disabled"),
    bet: btn("cspin", `🎲 Lancer sans attendre (${c.table.filter((t) => t.ready).length}/${g.players.length} prêts)`, "grow cs-spin", bettors ? "" : "disabled"),
    results: btn("next", rolling ? "La bille roule…" : "▶︎ Nouveau tour", "grow cs-spin", rolling ? "disabled" : ""),
  }[g.phase] || "";
  // Jetons : valeurs utiles selon le mode ; on garde le dernier choisi.
  const values = c.drinks ? Array.from({ length: Math.min(c.drinks, 5) }, (_, i) => i + 1) : [1, 5, 10, 25, 50];
  if (!values.includes(casinoChip)) casinoChip = values[c.drinks ? 0 : 2] ?? values[0];
  const left = me ? (c.drinks || me.chips) - me.staked : 0;
  const mineOn = (key) => me?.bets.find((b) => `${b.kind}:${b.target}` === key)?.amount || 0;
  const cell = (key, label, cls = "") => {
    const mine = mineOn(key), others = (c.board[key] || 0) - mine;
    return `<button type="button" class="rt-cell ${cls} ${n != null && casinoWins(key, n) ? "rt-win" : ""}" data-cbet="${key}" ${open && me ? "" : "disabled"}>
      <span>${label}</span>${mine ? `<i class="rt-chip">${mine}</i>` : ""}${others > 0 ? `<i class="rt-others">${others}</i>` : ""}</button>`;
  };
  let grid = cell("n:0", "0", "rt-zero");
  for (let i = 1; i <= 36; i++) grid += cell(`n:${i}`, i, `rt-${numColor(i)}`);
  const outside = ["dozen:1", "dozen:2", "dozen:3", "half:low", "parity:even", "color:red", "color:black", "parity:odd", "half:high"]
    .map((k) => cell(k, BET_LABELS[k], k.startsWith("color") ? `rt-${k.split(":")[1]}` : "rt-out")).join("");
  const summary = (t) => t.bets.map((b) => `${betLabel2(`${b.kind}:${b.target}`)} ×${b.amount}`).join(" · ");
  const resultTxt = (t) => !t.result || !revealed ? "" : c.drinks
    ? [t.result.drink ? `🍻 ${t.result.drink}` : "", t.result.give ? `🎁 ${t.result.give}` : ""].filter(Boolean).join(" · ") || "rien"
    : (t.result.net > 0 ? `+${t.result.net}` : `${t.result.net}`) + (t.result.jackpot ? " 🎯" : "");
  patch.gameHost = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    ${!me ? (g.phase !== "lobby" ? `<button data-gact="join" style="width:100%;margin-top:10px">S'asseoir à la table</button>` : "") : `
      ${open ? `<div class="cs-chips" role="group" aria-label="Valeur du jeton">${values.map((v) => `<button type="button" class="cs-chip v${values.indexOf(v)} ${v === casinoChip ? "on" : ""}" data-cchip="${v}" ${v > left ? "disabled" : ""}>${c.drinks ? `🍻${v}` : v}</button>`).join("")}
        </div>
        <div class="row cs-edit"><button type="button" class="secondary grow" data-gact="cundo" ${me.can_undo ? "" : "disabled"}>↶ Annuler</button>
          <button type="button" class="secondary grow" data-gact="cclear" ${me.staked ? "" : "disabled"}>✕ Tout effacer</button></div>
        <button type="button" class="cs-ready ${me.ready ? "on" : ""}" data-gact="cready">${me.ready
          ? `✓ Prêt · en attente des autres (${c.table.filter((t) => t.ready).length}/${c.table.length})` : "✓ Je suis prêt"}</button>` : ""}
      ${!c.drinks && me.chips < 1 && !me.staked && open ? `<button data-gact="crebuy" style="width:100%;margin-top:8px">Recharger ${c.start_chips} jetons</button>` : ""}`}
    <div class="rt ${open && me ? "" : "rt-closed"}">${grid}</div>
    <div class="rt rt-outside ${open && me ? "" : "rt-closed"}">${outside}</div>
    <h2>À la table (${g.players.length})</h2>
    <div class="list">${c.table.map((t) => `
      <div class="track">
        <div class="meta"><div class="title">${esc(t.name)}${open && t.ready ? ` <span class="pill live">prêt ✓</span>` : ""}${c.drinks ? "" : `<span class="artist"> · 💰 ${t.chips}${t.rebuys ? ` (rechargé ${t.rebuys}×)` : ""}</span>`}${sipsBadge(g.players.find((p) => p.pid === t.pid) || {})}</div>
          <div class="artist" style="white-space:normal">${t.staked ? summary(t) : g.phase === "bet" ? "réfléchit…" : "n'a pas misé"}${resultTxt(t) ? ` · <b>${resultTxt(t)}</b>` : ""}</div></div>
        ${g.is_host && t.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(t.pid)}" title="Exclure de la table" aria-label="Exclure de la table">✕</button>` : ""}
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne à la table : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.is_host && !g.me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}
document.addEventListener("click", (ev) => {
  const chip = ev.target.closest("[data-cchip]");
  if (chip) { casinoChip = +chip.dataset.cchip; return renderGameHost(game); }
  const cell = ev.target.closest("[data-cbet]");
  if (cell && game?.type === "casino") {
    haptic(15);
    gameAction("cbet", { target: cell.dataset.cbet, amount: casinoChip });
  }
});

// 🎡 Roulette : roue dessinée en SVG, tournée en CSS ; même tirage (index + décalage) sur tous les téléphones.
const WHEEL_COLORS = ["#ff4f9a", "#ffb347", "#4fd1c5", "#8b7bff", "#ffe14d", "#3ddc97", "#ff7a59", "#5ab0ff"];
let wheelSig = null, wheelSpinId = "", wheelRot = 0, wheelShown = "", spinningUntil = 0;

function wheelSvg(names) {
  const n = names.length, r = 96;
  if (!n) return `<circle r="${r}" fill="#241d35"/><text y="5" text-anchor="middle" fill="#a79fba" font-size="12">Ajoute des noms</text>`;
  const fs = Math.max(7, Math.min(13, 150 / n));
  let out = "";
  names.forEach((name, i) => {
    const a0 = (i / n) * 2 * Math.PI - Math.PI / 2, a1 = ((i + 1) / n) * 2 * Math.PI - Math.PI / 2;
    const color = WHEEL_COLORS[i % WHEEL_COLORS.length] === WHEEL_COLORS[0] && i === n - 1 && n > 1 ? WHEEL_COLORS[2] : WHEEL_COLORS[i % WHEEL_COLORS.length];
    out += n === 1 ? `<circle r="${r}" fill="${color}"/>`
      : `<path d="M0 0 L${(r * Math.cos(a0)).toFixed(2)} ${(r * Math.sin(a0)).toFixed(2)} A${r} ${r} 0 ${1 / n > 0.5 ? 1 : 0} 1 ${(r * Math.cos(a1)).toFixed(2)} ${(r * Math.sin(a1)).toFixed(2)} Z" fill="${color}" stroke="#0e0b16" stroke-width="1"/>`;
    const mid = ((i + 0.5) / n) * 360;
    const label = name.length > 14 ? name.slice(0, 13) + "…" : name;
    out += `<text transform="rotate(${mid.toFixed(2)}) translate(0 ${-r * 0.56}) rotate(-90)" text-anchor="middle" dominant-baseline="middle" fill="#1a1020" font-size="${fs}" font-weight="700">${esc(label)}</text>`;
  });
  return out + `<circle r="11" fill="#0e0b16" stroke="#fff" stroke-width="2"/>`;
}

function setWheel(rot, seconds) {
  const w = $("wheel");
  w.style.transition = seconds ? `transform ${seconds}s cubic-bezier(.12,.8,.12,1)` : "none";
  w.style.transform = `rotate(${rot}deg)`;
}

function showRouletteResult(g) {
  const sp = g.spin;
  const show = g.phase === "spun" && sp && wheelShown === sp.id;
  $("rouletteResult").innerHTML = show
    ? `<div class="roulette-loser">🎯 ${esc(sp.names[sp.index])}</div><div class="artist">a perdu !</div>` : "";
}

function renderRoulette(g) {
  $("roulette").classList.toggle("hidden", g.type !== "roulette");
  $("roulette").className = "roulette " + (g.type === "roulette" ? GAME_THEME.roulette : "hidden");
  if (g.type !== "roulette") return;
  const sp = g.phase === "spun" ? g.spin : null;
  const names = sp ? sp.names : g.names;
  const sig = names.join("|");
  if (sig !== wheelSig) {
    wheelSig = sig;
    $("wheel").innerHTML = wheelSvg(names);
    if (!sp && Date.now() > spinningUntil) { wheelRot = 0; setWheel(0, 0); }
  }
  if (sp && sp.id !== wheelSpinId) {
    wheelSpinId = sp.id;
    const n = sp.names.length, target = (sp.index + 0.5 + (sp.jitter || 0)) * (360 / n);
    const left = Math.max(0, 4.8 - sp.age);
    const base = wheelRot + 360 * (left ? 6 : 1);
    wheelRot = base - (((base + target) % 360) + 360) % 360;
    if (left > 0.3) {
      // Tirage tout frais : la roue tourne, le perdant s'affiche à l'arrêt.
      GameAudio.play("spin");
      spinningUntil = Date.now() + left * 1000;
      setWheel(wheelRot, left);
      setTimeout(() => {
        wheelShown = sp.id;
        if (game?.spin?.id === sp.id) { GameAudio.play("reveal"); showRouletteResult(game); renderGameHost(game); }
        haptic(150);
      }, left * 1000 + 100);
    } else {
      setWheel(wheelRot, 0);
      wheelShown = sp.id;
    }
  }
  showRouletteResult(g);
}

function renderRouletteHost(g, btn) {
  const sp = g.spin, spinning = Date.now() < spinningUntil;
  const loser = g.phase === "spun" && sp && wheelShown === sp.id ? sp.names[sp.index] : "";
  const joined = g.players.map((p) => p.name).filter((n) => !g.names.some((x) => x.toLowerCase() === n.toLowerCase()));
  const host = $("gameHost"), kind = "roulette:" + g.id + ":" + g.is_host;
  // Squelette posé une seule fois : le champ « Ajouter un nom » n'est jamais recréé, le clavier reste ouvert.
  if (host.dataset.kind !== kind) {
    host.dataset.kind = kind;
    host.innerHTML = `
      <div id="rlControls"></div>
      ${g.is_host ? `<h2 id="rlTitle"></h2>
        <form data-gform="addname" class="row">
          <input class="grow" type="text" id="rouletteName" maxlength="20" aria-label="Ajouter un nom" spellcheck="false" placeholder="Ajouter un nom…" autocomplete="off" autocapitalize="words" enterkeyhint="enter">
          <button type="submit" id="rouletteAdd">Ajouter</button>
        </form>
        <div class="chips" id="rlNames" style="margin-top:8px"></div>
        <div id="rlPlayers"></div>` : ""}
      <div id="rlHistory"></div>
      <div id="rlSpect"></div>`;
    // Toucher « Ajouter » ne doit pas retirer le focus du champ (sinon le clavier se ferme).
    $("rouletteAdd")?.addEventListener("pointerdown", (ev) => ev.preventDefault());
  }
  $("rlControls").innerHTML = g.is_host ? `<div class="row" style="margin-top:10px">${btn("spin", spinning ? "La roue tourne…" : "🎡 Lancer la roue", "grow g-spin", g.names.length < 2 || spinning ? "disabled" : "")}</div>
    ${loser && g.names.includes(loser) ? `<button class="secondary" data-gact="dropname" data-name="${esc(loser)}" style="width:100%;margin-top:8px">Retirer ${esc(loser)} de la roue</button>` : ""}` : "";
  if (g.is_host) {
    $("rlTitle").textContent = `Sur la roue (${g.names.length})`;
    $("rlNames").innerHTML = g.names.map((n) => `<span class="pill name-chip">${esc(n)}<button type="button" class="chip-x" data-gact="dropname" data-name="${esc(n)}" aria-label="Retirer ${esc(n)}">✕</button></span>`).join("") || `<span class="artist">Aucun nom pour l'instant</span>`;
    $("rlPlayers").innerHTML = joined.length ? `<button class="secondary" data-gact="addplayers" style="width:100%;margin-top:8px">👥 Ajouter les joueurs inscrits (${joined.length})</button>` : "";
  }
  $("rlHistory").innerHTML = g.history?.length ? `<h2>Derniers perdants</h2><div class="chips">${g.history.slice(0, 10).map((n, i) => `<span class="pill" style="${i === 0 ? "color:var(--text)" : ""}">${esc(n)}</span>`).join("")}</div>` : "";
  $("rlSpect").innerHTML = g.players.length ? `<h2>Spectateurs (${g.players.length})</h2><div class="chips">${g.players.map((p) => `<span class="pill">${esc(p.name)}</span>`).join("")}</div>` : "";
}

// « Je n'ai jamais » : ceux qui l'ont déjà fait boivent.
function neverResultsHtml(g) {
  const did = g.results.filter((r) => r.answer === "yes"), never = g.results.filter((r) => r.answer === "no");
  const sips = g.options?.sips || 0;
  const drink = sips && did.length
    ? `<div class="drink">🍻 ${did.map((r) => esc(r.name)).join(", ")} boi${did.length > 1 ? "vent" : "t"} ${sips} gorgée${sips > 1 ? "s" : ""} !</div>`
    : !did.length ? `<div class="drink">😇 Personne ne l'a fait… tout le monde est sage ?</div>` : "";
  const col = (emo, label, list, cls) => `<div class="never-col ${cls}"><div class="never-head"><span aria-hidden="true">${emo}</span><b>${list.length}</b></div>
    <div class="never-lbl">${label}</div>
    <div class="chips">${list.map((r) => `<span class="pill">${esc(r.name)}</span>`).join("") || `<span class="artist">personne</span>`}</div></div>`;
  return drink + `<div class="never-res">${col("🍻", "L'ont déjà fait", did, "did")}${col("😇", "Jamais", never, "nev")}</div>`;
}

// Commandes de l'animateur (créateur de la partie) et liste des joueurs.
function renderGameHost(g) {
  const btn = (action, label, cls = "", extra = "") => `<button class="${cls}" data-gact="${action}" ${extra}>${label}</button>`;
  if (g.type !== "roulette") delete $("gameHost").dataset.kind;  // un autre jeu redessine tout
  const alive = g.players.filter((p) => p.alive);
  const controls = !g.is_host ? "" : {
    lobby: btn("start", g.type === "undercover" ? "▶︎ Distribuer les mots" : "▶︎ Première question", "grow", g.players.length < (g.type === "undercover" ? 3 : 2) ? "disabled" : ""),
    words: btn("vote_start", "🗳 Passer au vote", "grow"),
    vote: btn("close_vote", `Clore le vote (${g.votes_count}/${alive.length})`, "grow"),
    white_guess: btn("skip_guess", "Passer la devinette", "secondary grow"),
    reveal: btn("next", "▶︎ Manche suivante", "grow"),
    question: btn("close_vote", g.votes_count >= g.players.length ? "Voir les résultats" : `Voir les résultats (${g.votes_count}/${g.players.length})`, "grow") + btn("next", "Autre question", "secondary", `title="Passer cette question sans résultat"`),
    results: btn("next", "▶︎ Question suivante", "grow"),
    end: btn("restart", "🔁 Rejouer avec les mêmes joueurs", "grow"),
  }[g.phase] || "";
  if (g.type === "roulette") return renderRouletteHost(g, btn);
  if (isBJ(g)) return renderBJHost(g, btn);
  if (g.type === "casino") return renderCasinoHost(g, btn);
  if (g.type === "divan") return renderDivanHost(g, btn);
  if (g.type === "likely") return renderLikelyHost(g);
  if (g.type === "debate") return renderDebateHost(g);
  if (["pyramid", "biskit", "quiz", "purity", "room", "president", "neon", "island", "heist"].includes(g.type)) { patch.gameHost = ""; return; }
  if (g.type === "tmc") return renderTmcHost(g, btn);
  const canEliminate = g.is_host && g.type === "undercover" && (g.phase === "words" || g.phase === "vote");
  const canRemove = g.is_host;
  const seeRoles = g.phase === "end" || (g.master && showRoles);
  const speaking = g.type === "undercover" && g.phase === "words";
  const canMove = g.is_host && (speaking || g.phase === "lobby");
  // Pendant les questions, la liste est dans le menu ☰ ; ici, seulement ceux qui jouent sans téléphone (l'animateur répond pour eux).
  if (QUESTION_TYPES.includes(g.type) && (g.phase === "question" || g.phase === "results")) {
    const manual = g.type === "never" && g.phase === "question" ? g.players.filter((p) => p.manual) : [];
    patch.gameHost = `${controls ? `<div class="row qs-host">${controls}</div>` : ""}
      ${manual.length ? `<h2>Sans téléphone : réponds pour eux</h2><div class="list">${manual.map((p) => `<div class="track"><div class="meta"><div class="title">${esc(p.name)}</div></div>
        <div class="icon-btns">
          <button class="${p.answer === "yes" ? "" : "secondary"}" data-gact="mvote" data-target="${esc(p.pid)}" data-guess="yes" aria-pressed="${p.answer === "yes"}">🍻 Déjà fait</button>
          <button class="${p.answer === "no" ? "" : "secondary"}" data-gact="mvote" data-target="${esc(p.pid)}" data-guess="no" aria-pressed="${p.answer === "no"}">😇 Jamais</button>
        </div></div>`).join("")}</div>` : ""}`;
    return;
  }
  const list = speaking ? g.order_pids.map((pid) => g.players.find((p) => p.pid === pid)).filter(Boolean)
    .concat(g.players.filter((p) => !g.order_pids.includes(p.pid))) : g.players;
  patch.gameHost = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    <h2>${speaking ? "Ordre de parole" : "Joueurs"} (${g.players.length})${g.master && g.type === "undercover" ? ` <button class="secondary" data-gact="roles" style="padding:2px 8px">${showRoles ? "🙈 Cacher" : "👁 Rôles"}</button>` : ""}</h2>
    <div class="list">${list.map((p, i) => `
      <div class="track" style="${p.alive ? "" : "opacity:.55"}">
        <div class="meta"><div class="title" ${p.waiting ? 'title="Joue à la prochaine partie"' : ""}>${speaking && p.alive ? `${i + 1}. ` : ""}${p.waiting ? "⏳ " : p.alive ? "" : "✝︎ "}${esc(p.name)}${p.host ? " 🎲" : ""}${(g.phase === "vote" || g.phase === "question") && p.voted ? " ✓" : ""}${sipsBadge(p)}${playerTag(g, p)}</div>
          ${p.role && (seeRoles || !p.alive) ? `<div class="artist">${esc(p.role)}${seeRoles && p.word ? " · " + esc(p.word) : ""}</div>` : ""}</div>
        <div class="icon-btns">
          ${g.is_host && p.manual && g.type === "never" && g.phase === "question" ? `
            <button class="${p.answer === "yes" ? "" : "secondary"}" data-gact="mvote" data-target="${esc(p.pid)}" data-guess="yes" title="L'a déjà fait" aria-label="L'a déjà fait">🍻</button>
            <button class="${p.answer === "no" ? "" : "secondary"}" data-gact="mvote" data-target="${esc(p.pid)}" data-guess="no" title="Jamais" aria-label="Jamais">😇</button>` : ""}
          ${canMove && p.alive && i > 0 ? `<button class="secondary" data-gact="up" data-target="${esc(p.pid)}" title="Monter" aria-label="Monter">⬆</button>` : ""}
          ${canMove && p.alive && i < (speaking ? g.order_pids.length : list.length) - 1 ? `<button class="secondary" data-gact="down" data-target="${esc(p.pid)}" title="Descendre" aria-label="Descendre">⬇</button>` : ""}
          ${canEliminate && p.alive ? `<button class="danger" data-gact="eliminate" data-target="${esc(p.pid)}" title="Éliminer (vote à main levée)" aria-label="Éliminer (vote à main levée)">Éliminer</button>` : ""}
          ${canRemove && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure de la partie" aria-label="Exclure de la partie">✕</button>` : ""}
        </div>
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR ci-dessous.</p>`}</div>
    ${manualForm(g)}
    ${g.is_host && !g.me && (g.phase === "lobby" || g.phase === "end") ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}

// Compte à rebours du mot affiché : 3, 2, 1… puis on le cache.
setInterval(() => {
  if (!wordShown) return;
  const left = Math.ceil((wordUntil - Date.now()) / 1000);
  if (left <= 0) { wordShown = ""; renderGame(game); }
  else if ($("wordCountdown")) $("wordCountdown").textContent = left;
}, 200);

// Moments forts en plein écran (annonce animée sur tous les téléphones), pour les jeux qui n'ont pas la leur.
const gfSeen = {};
function gameFlashes(g) {
  const sig = [g.phase, g.round, g.last?.name || "", g.winner || ""].join("|");
  const prev = gfSeen[g.id];
  gfSeen[g.id] = sig;
  if (!prev || prev === sig) return;  // première vue (page rechargée) : pas d'annonce en différé
  const [pPhase, , pLast] = prev.split("|");
  if (g.type === "undercover") {
    const win = { civils: "Les civils gagnent !", impostors: "Les undercovers gagnent !", white: "Mr. White gagne !" }[g.winner];
    if (g.phase === "end" && pPhase !== "end" && win) return pyrFlash("summit", `🏆 ${win}`, g.words ? `Civils : ${esc(g.words.civil)} · Undercover : ${esc(g.words.undercover)}` : "");
    if (g.last?.name && g.last.name !== pLast) return pyrFlash(g.last.role === "Civil" ? "bad" : "good", `${esc(g.last.name)} est éliminé·e`, `C'était ${esc(g.last.role)} !`);
  }
  if (g.type === "whoof" && g.phase === "results" && pPhase !== "results" && g.results?.length) {
    const max = Math.max(...g.results.map((r) => r.count)), top = g.results.filter((r) => r.count === max).map((r) => esc(r.name));
    return pyrFlash("summit", `👑 ${top.join(" et ")}`, `${esc(g.question || "")}${g.options?.sips ? ` · ${sipWord(g.options.sips)} !` : ""}`);
  }
  if (g.type === "never" && g.phase === "results" && pPhase !== "results" && g.results) {
    const did = g.results.filter((r) => r.answer === "yes").map((r) => esc(r.name));
    return pyrFlash(did.length ? "good" : "summit", did.length ? `🍻 ${did.length} l'ont déjà fait` : "😇 Personne ne l'a fait", did.join(", "));
  }
}

// Partie créée mais pas lancée : le QR et le code au premier plan, pour que tout le monde rejoigne facilement.
// Dès le lancement, l'écran n'affiche plus que le jeu (le QR reste dans le menu ☰).
function lobbyInvite(g) {
  if (g.phase !== "lobby") return "";
  const n = g.players.length;
  return `<div class="g-lobby">
    <div class="g-lobby-k">Scannez pour rejoindre</div>
    <img class="g-lobby-qr" width="240" height="240" src="/qr/game/${esc(g.room || g.code)}.svg" alt="QR code pour rejoindre la partie">
    <div class="g-lobby-code">${esc(g.room || g.code)}</div>
    <div class="artist g-lobby-hint">ou onglet 🎮 Jeux → entre ce code</div>
    <div class="g-lobby-players">${n ? g.players.map((p) => `<span class="pill g-pill-av">${p.photo ? avatar(p, "qs-av-xs") : ""}${p.host ? "🎲 " : ""}${esc(p.name)}</span>`).join("") : `<span class="artist">En attente des joueurs…</span>`}</div>
  </div>`;
}

// ── Salle de jeux ──
function roomTileHtml(c) {
  return `<button type="button" class="g-room-tile ${GAME_THEME[c.type] || ""}" data-room-pick="${c.type}">${newBadge(c.type)}
    <span class="g-room-tile-i">${GAME_ICONS[c.type] || ""}</span><b>${esc(c.name)}${drinkTag(c.type)}</b></button>`;
}
// Tuiles groupées par catégorie, dans le même ordre que l'écran Jeux ; un jeu sans catégorie va à la fin.
function roomCatalogHtml(catalog) {
  const byType = new Map(catalog.map((c) => [c.type, c]));
  const known = new Set(GAME_CATEGORIES.flatMap(([, , types]) => types));
  const groups = [...GAME_CATEGORIES.map(([id, label, types]) => [id, label, types.filter((t) => byType.has(t)).map((t) => byType.get(t))]),
    ["other", "Autres jeux", catalog.filter((c) => !known.has(c.type))]];
  return groups.filter(([, , list]) => list.length).map(([id, label, list]) => `<div class="g-room-cat" data-cat="${id}">
      <div class="g-room-cat-h">${label}</div><div class="g-room-grid">${list.map(roomTileHtml).join("")}</div></div>`).join("");
}
function roomHtml(g) {
  const R = g.room_info || {}, lead = g.is_host;
  const cur = R.current;
  const resume = cur ? `<button class="py-main g-room-resume" data-room-goto="${esc(cur.code)}">🎮 ${esc(cur.name)} en cours · rejoindre</button>` : "";
  const pick = lead && !cur ? `<div class="g-room-block"><div class="g-room-h">Lancer un jeu pour la salle</div>
      ${roomCatalogHtml(R.catalog || [])}</div>`
    : !cur ? `<div class="g-room-wait"><span class="g-room-dots"><i></i><i></i><i></i></span>${esc(g.host_name || "L'animateur")} choisit le prochain jeu…</div>` : "";
  const board = (R.board || []).filter((r) => r.pts || r.drink || r.give);
  const tally = board.length ? `<div class="g-room-block"><div class="g-room-h">🏆 Tableau de la soirée</div>
      ${board.map((r, i) => `<div class="g-room-row ${r.me ? "me" : ""}"><span class="qz-rank r${i + 1}">${i + 1}</span><b>${esc(r.name)}</b>
        ${r.pts ? `<span class="g-room-pts">${r.pts.toLocaleString("fr-CH")} pts</span>` : ""}${r.drink ? `<span class="g-room-sips">🍻 ${r.drink}</span>` : ""}</div>`).join("")}</div>` : "";
  const hist = (R.history || []).length ? `<div class="g-room-block"><div class="g-room-h">Déjà joué ce soir</div><div class="g-room-hist">
      ${R.history.map((h) => `<span class="g-room-chip ${GAME_THEME[h.type] || ""}"><i>${GAME_ICONS[h.type] || ""}</i>${esc(h.name)}${h.winner ? ` · 🏆 ${esc(h.winner)}` : ""}</span>`).join("")}</div></div>` : "";
  return resume + pick + tally + hist;
}
function openRoomSheet(type) {
  const src = [...document.querySelectorAll("#gHome .gcard")].find((c) => c.querySelector(`[data-create="${type}"]`));
  if (!src) return;
  closeRoomSheet(true);
  const card = src.cloneNode(true);
  const go = card.querySelector("[data-create]");
  go.textContent = "▶ Lancer pour toute la salle";
  const wrap = document.createElement("div");
  wrap.className = "g-modal g-room-modal";
  Object.assign(wrap.dataset, { nav: "sheet", navSurface: ".g-room-sheet", navClose: "self" });
  wrap.innerHTML = `<div class="g-sheet g-room-sheet" role="dialog" aria-modal="true" aria-label="Lancer un jeu"><div class="g-sheet-grab" aria-hidden="true"></div></div>`;
  wrap.firstElementChild.append(card);
  wrap.addEventListener("click", (ev) => { if (ev.target === wrap) closeRoomSheet(); });
  document.body.append(wrap);
}
// ✕ sur un joueur : l'exclure (il peut revenir quand il veut) ou le bannir (ce code lui est refusé).
// Présence d'un joueur : « en ligne » / « hors ligne · 3 min », et numéro quand deux joueurs portent le même prénom.
function since(sec) {
  if (sec == null) return "";
  return sec < 90 ? "à l'instant" : sec < 3600 ? `${Math.round(sec / 60)} min` : `${Math.round(sec / 3600)} h`;
}
function presenceTag(p) {
  if (p.manual || p.online === undefined) return "";
  const twin = p.twin ? ` <span class="g-twin" title="Deux joueurs portent ce prénom">#${p.twin}</span>` : "";
  const state = p.online ? `<span class="g-pres on" title="En ligne"><i aria-hidden="true"></i>en ligne</span>`
    : `<span class="g-pres off" title="Plus vu depuis ${since(p.seen_ago)}"><i aria-hidden="true"></i>hors ligne${p.seen_ago != null ? ` · ${since(p.seen_ago)}` : ""}</span>`;
  return twin + " " + state;
}
function openKickSheet(pid) {
  const p = game?.players.find((x) => x.pid === pid);
  if (!p) return;
  if (p.manual) return gameAction("remove", { target: pid });  // sans téléphone : on le retire simplement
  closeRoomSheet(true);
  const name = esc(p.name);
  const wrap = document.createElement("div");
  wrap.className = "g-modal g-room-modal g-kick-modal";
  Object.assign(wrap.dataset, { nav: "sheet", navSurface: ".g-room-sheet", navClose: "self" });
  wrap.innerHTML = `<div class="g-sheet g-room-sheet g-kick" role="dialog" aria-modal="true" aria-labelledby="kickTitle">
    <div class="g-sheet-grab" aria-hidden="true"></div>
    <div class="g-kick-who">${avatar(p)}<b id="kickTitle">Retirer ${name}${p.twin ? ` #${p.twin}` : ""} ?</b></div>
    ${p.online !== undefined ? `<p class="g-kick-pres">${presenceTag(p)}${p.twin && !p.online ? `<br>Hors ligne alors qu'un autre ${name} est là : c'est sans doute un doublon (reconnexion depuis un autre navigateur).` : ""}</p>` : ""}
    <button type="button" class="g-kick-opt" data-kick="remove"><span class="g-kick-ico" aria-hidden="true">👋</span>
      <span><b>Exclure</b><small>${name} quitte la partie et pourra revenir avec le code. Pratique en cas d'absence.</small></span></button>
    <button type="button" class="g-kick-opt ban" data-kick="ban"><span class="g-kick-ico" aria-hidden="true">🚫</span>
      <span><b>Bannir</b><small>${name} ne pourra plus rejoindre cette partie avec ce code.</small></span></button>
    <button type="button" class="secondary" data-kick="cancel">Annuler</button>
  </div>`;
  wrap.addEventListener("click", (ev) => {
    const k = ev.target.closest("[data-kick]")?.dataset.kick;
    if (ev.target !== wrap && !k) return;
    closeRoomSheet();
    if (k === "remove" || k === "ban") gameAction(k, { target: pid }).then(() => toast(k === "ban" ? `🚫 ${p.name} : banni·e de la partie` : `👋 ${p.name} : retiré·e (retour possible avec le code)`, "ok"));
  });
  document.body.append(wrap);
  wrap.querySelector("[data-kick=remove]").focus();
}
function closeRoomSheet(now = false) {
  const w = document.querySelector(".g-room-modal");
  if (!w) return;
  if (now) return w.remove();
  w.classList.add("out");
  setTimeout(() => w.remove(), 260);
}
document.addEventListener("click", (ev) => {
  const t = ev.target.closest("[data-room-pick]");
  if (t) return openRoomSheet(t.dataset.roomPick);
  const go = ev.target.closest("[data-room-goto]");
  if (go) { setGame(go.dataset.roomGoto); autoJoin = true; refreshGame(); }
});

// Barre du haut commune à tous les jeux : ☰ menu, nom + phase + chrono, ? règles.
function gameTopBar(g) {
  const phase = g.type === "pyramid" && g.pyr ? pyrPhase(g) : phaseLabel(g);
  const round = g.round && g.phase !== "lobby" && !["pyramid", "quiz"].includes(g.type)
    ? ` · ${{ heist: "braquage", island: "manche", neon: "manche", president: "manche", undercover: "manche", roulette: "tirage", blackjack: "main", casino: "tour", divan: "carte", tmc: "duo", biskit: "carte", quiz: "question" }[g.type] || "question"} ${g.round}` : "";
  const alerts = (g.pyr?.pending?.length || 0) + (g.is_host ? (g.pyr?.peeks || []).filter((r) => r.status === "pending").length : 0);
  return `<button type="button" class="py-icon g-burger" data-gdrawer="open" aria-label="Menu : joueurs, code, QR"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>${alerts ? `<i class="badge">${alerts}</i>` : ""}</button>
    <div class="g-top-mid"><div class="g-top-name"><span class="g-top-ico" aria-hidden="true">${GAME_ICONS[g.type] || ""}</span>${esc(g.name)}</div>
      <div class="g-top-sub">${g.mode ? esc(g.mode) + " · " : ""}${QUESTION_TYPES.includes(g.type) && g.round && g.phase !== "lobby" && g.phase !== "end" ? `Question ${g.round}` : (g.type === "room" ? "Soirée" : phase) + round} · ${g.room || g.type === "room" ? "salle" : "code"} <b>${esc(g.room || g.code)}</b> · ⏱ <span id="gTimer">${fmtDuration(g.elapsed)}</span></div></div>
    ${GameAudio.button()}
    <button type="button" class="py-icon g-min" data-gdrawer="minimize" aria-label="Réduire le jeu (revenir à la musique)">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg></button>
    ${helpBtn(g.type, true)}
    ${["island","neon","heist"].includes(g.type) ? '<button type="button" class="g-quit" data-gdrawer="exit" aria-label="Quitter la partie">✕ Quitter</button>' : ""}`;
}
// Menu latéral : code, QR, participants (et outils de l'animateur ou de l'admin), réduire, quitter.
function renderDrawer(g) {
  const lead = g.is_host, movable = lead && g.phase === "lobby";
  patch.gDrawerPlayers = `<h2>Participants (${g.players.length})</h2>
    <div class="list">${g.players.map((p, i) => `<div class="track ${p.online === false ? "g-away" : ""}">${avatar(p, "qs-av-sm")}<div class="meta"><div class="title">${esc(p.name)}${p.host ? " 🎲" : ""}${p.pid === g.me?.pid ? " (toi)" : ""}${presenceTag(p)}${playerTag(g, p)}${p.pending ? " ⏳" : ""}${sipsBadge(p)}</div></div>
      <div class="icon-btns">
        ${movable && i > 0 ? `<button class="secondary" data-gact="up" data-target="${esc(p.pid)}" title="Monter" aria-label="Monter">⬆</button>` : ""}
        ${movable && i < g.players.length - 1 ? `<button class="secondary" data-gact="down" data-target="${esc(p.pid)}" title="Descendre" aria-label="Descendre">⬇</button>` : ""}
        ${lead && p.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(p.pid)}" title="Exclure de la partie" aria-label="Exclure de la partie">✕</button>` : ""}
      </div></div>`).join("") || `<p class="empty" style="padding:12px">Personne pour l'instant : fais scanner le QR.</p>`}</div>
    ${movable && ["biskit", "pyramid"].includes(g.type) ? `<p class="artist" style="margin-top:6px">Range les joueurs dans l'ordre où ils sont assis (vers la gauche).</p>` : ""}
    ${(g.type !== "pyramid" || g.phase === "lobby") ? manualForm(g) : ""}
    ${lead && !g.me && (g.phase === "lobby" || g.phase === "end") ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">🙋 Je joue aussi</button>` : ""}`;
  patch.gDrawerExit = exitHtml(g);
}
function realtimeControlsActive() {
  return !document.hidden && pyrFull && gamesTabShown() &&
    !document.querySelector('.g-drawer:not(.hidden), .g-modal:not(.hidden)');
}
// Jeux à joystick (Île, Néon, Braquage) : au toucher, la moitié gauche de l'écran de jeu amène le joystick
// sous le doigt, la moitié droite le bouton d'action ; chacun reprend sa place au relâchement.
function floatControl(e, root, stick, button, startStick, startButton, ignore) {
  if (e.pointerType === "mouse" || ignore) return;
  const r = root.getBoundingClientRect(), left = e.clientX < r.left + r.width / 2, el = left ? stick : button;
  if ((!left && button.disabled) || el.style.translate) return;  // bouton désactivé, ou déjà tenu par un autre doigt
  const b = el.getBoundingClientRect();
  el.style.translate = `${e.clientX - b.left - b.width / 2}px ${e.clientY - b.top - b.height / 2}px`;
  (left ? startStick : startButton)(e);
}
function openDrawer() { $("gDrawer").classList.remove("hidden"); requestAnimationFrame(() => $("gDrawer").classList.add("open")); }
// Masqué après l'animation de fermeture… sauf s'il a été rouvert entre-temps.
function closeDrawer() { $("gDrawer").classList.remove("open"); setTimeout(() => { if (!$("gDrawer").classList.contains("open")) $("gDrawer").classList.add("hidden"); }, 250); }
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-gdrawer]");
  if (b) {
    const a = b.dataset.gdrawer;
    if (a === "open" || a === "exit") { openDrawer(); $("gDrawer").querySelector(".g-drawer-panel").scrollTop = 0; }
    else if (a === "close") closeDrawer();
    else if (a === "minimize") minimizeGame();
    return;
  }
  if (ev.target.id === "gDrawer") closeDrawer();  // toucher à côté du menu le ferme
});

// 🏁 Partie fermée par l'animateur (ou par l'hôte de la soirée) : on prévient pendant 5 secondes.
function showGameEnded(info) {
  document.querySelector(".g-ended")?.remove();
  const el = document.createElement("div");
  el.className = "g-ended";
  el.setAttribute("role", "alert");
  const who = info.by === "admin" ? "par l'organisateur de la soirée" : `par l'hôte${info.host ? ` (${esc(info.host)})` : ""}`;
  el.innerHTML = `<div class="g-ended-card"><div class="g-ended-icon">🏁</div>
    <div class="g-ended-title">Partie terminée</div>
    <div class="g-ended-sub">${info.game ? `${esc(info.game)} · ` : ""}${who}</div>
    <div class="g-ended-bar"><i></i></div></div>`;
  const close = () => { el.classList.add("out"); setTimeout(() => el.remove(), 300); };
  el.addEventListener("click", close);
  document.body.append(el);
  haptic([80, 60, 80]);
  setTimeout(close, 5000);
}

// Une même action n'est envoyée qu'une fois à la fois (double toucher, réseau lent).
const gInflight = new Set();
async function gameAction(action, extra = {}, opts = {}) {
  if (!myGame) return;
  if (action === "join") extra = { ...extra, token: (typeof freshToken === "function" && await freshToken()) || "" };
  const key = myGame + ":" + action + JSON.stringify(extra);
  if (gInflight.has(key)) return;
  gInflight.add(key);
  const actionCode = myGame;
  try {
    const room = game?.room;
    const seq = ++gSeq;
    const g = await gapi(`/api/games/${myGame}`, { guest_id: guestId, name: guestName, action, ...extra });
    if (actionCode !== myGame) return false;
    if (action === "end" && room) { setGame(room); refreshGame(); return; }  // fin d'un jeu de la salle : retour à la salle
    if (action === "end" || (action === "leave" && !g?.is_host)) {
      if (action === "leave" || game?.type === "room") { myRoom = ""; store("vp_room", ""); }
      setGame(""); renderGame(null); return;
    }
    if (routeRoom(g)) return;
    if (seq === gSeq) renderGame(g);
    else refreshGame();  // un rechargement est parti entre-temps : on se recale sur l'état le plus récent
    return true;
  } catch (e) {
    if (actionCode !== myGame) return false;
    if (e.status === 404 && e.detail?.ended) showGameEnded(e.detail.ended);
    else if (opts.quiet && e.status === 409) refreshGame();  // arrivé trop tard : on se recale sans message
    else toast(e.message, "err");
    if (e.status === 404) { setGame(""); renderGame(null); }
    return false;
  } finally {
    gInflight.delete(key);
  }
}
// Bouton touché : il s'enfonce et patiente tout de suite, jusqu'à la réponse du serveur.
function pressed(b, promise) {
  if (!b) return promise;
  b.classList.add("busy");
  Promise.resolve(promise).finally(() => b.classList.remove("busy"));
  return promise;
}
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-gact]");
  if (!b) return;
  const a = b.dataset.gact;
  if (a === "show") { wordShown = b.dataset.key; wordUntil = Date.now() + 3000; return renderGame(game); }
  if (a === "hide") { wordShown = ""; wordUntil = 0; return renderGame(game); }
  if (a === "roles") { showRoles = !showRoles; return renderGame(game); }
  if (a === "dropname") return gameAction("names", { names: game.names.filter((n) => n !== b.dataset.name) });
  if (a === "addplayers") return gameAction("names", { names: game.names.concat(game.players.map((p) => p.name)) });
  if (a === "eliminate" && !confirm("Éliminer ce joueur ?")) return;
  if (a === "remove") return openKickSheet(b.dataset.target);
  pressed(b, gameAction(a, { target: b.dataset.target || "", amount: +(b.dataset.amount || 0), guess: b.dataset.guess || "" }));
});
// Toucher « + Ajouter » ne retire pas le focus du champ : le clavier reste ouvert et l'iPhone ne fait pas défiler la page.
document.addEventListener("pointerdown", (ev) => { if (ev.target.closest("[data-gform=addguest] button")) ev.preventDefault(); });
document.addEventListener("submit", (ev) => {
  if (!ev.target.closest("[data-gform=addguest]")) return;
  ev.preventDefault();
  // Le formulaire existe à deux endroits (écran et menu ☰) : on lit le champ de celui qui a été envoyé,
  // on y revient sans faire défiler, et on garde la position de lecture (sinon la page remonte tout en haut).
  const form = ev.target.closest("[data-gform=addguest]"), input = form.querySelector("input");
  const name = input.value.trim(), where = form.closest("#gDrawer") ? "#gDrawer" : "#gameHost";
  const scrollers = [$("gamePlay"), document.querySelector("#gDrawer .g-drawer-panel"), document.scrollingElement].filter(Boolean);
  const pos = scrollers.map((el) => el.scrollTop);
  const restore = () => scrollers.forEach((el, i) => { if (el.scrollTop !== pos[i]) el.scrollTop = pos[i]; });
  if (!name) return;
  input.value = "";
  gameAction("addguest", { guess: name }).then(() => {
    restore();
    const field = document.querySelector(`${where} [data-gform=addguest] input`);
    field?.focus({ preventScroll: true });
    requestAnimationFrame(restore);
  });
});
let nameQueue = Promise.resolve();
document.addEventListener("submit", (ev) => {
  if (!ev.target.closest("[data-gform=addname]")) return;
  ev.preventDefault();
  const input = $("rouletteName"), name = input.value.trim();
  if (!name) return;
  // On vide le champ tout de suite (le focus reste dedans) : on peut enchaîner les prénoms.
  input.value = "";
  // Envois en file : chaque prénom part avec la liste à jour, aucun ne se perd si on tape vite.
  nameQueue = nameQueue.then(() => gameAction("names", { names: game.names.concat([name]) }));
});
$("game").addEventListener("submit", (ev) => {
  if (!ev.target.closest("[data-gform]")) return;
  ev.preventDefault();
  if (!guessDraft.trim()) return;
  gameAction(ev.target.closest("[data-gform]").dataset.gform === "tanswer" ? "tanswer" : "guess", { guess: guessDraft.trim() });
  guessDraft = "";
});
// Menu ☰ : l'animateur passe la main à un joueur de son choix (il reste joueur) ; quitter est un bouton à part.
let handoverOpen = false;
function exitHtml(g) {
  const cands = g.players.filter((p) => p.pid !== g.me?.pid && !p.manual && !p.pending && !p.host);
  const out = [];
  if (g.is_owner && cands.length) {
    out.push(`<button type="button" class="secondary g-exit" data-exit="pick">👑 Passer la main</button>`);
    if (handoverOpen) out.push(`<div class="g-handover"><div class="artist">Qui devient l'animateur ? ${g.me ? "Tu restes dans la partie." : ""}</div>
      ${cands.map((p) => `<button type="button" class="secondary" data-exit="to" data-target="${esc(p.pid)}">👑 ${esc(p.name)}</button>`).join("")}</div>`);
  }
  // Le maître du jeu (créateur qui ne joue pas) part en passant la main ou en fermant la partie.
  if (g.me && !g.kicked) out.push(`<button type="button" class="secondary g-exit" data-exit="leave">🚪 Quitter la partie</button>`);
  else if (!g.is_owner) out.push(`<button type="button" class="secondary g-exit" data-exit="away">🚪 Quitter</button>`);
  if (g.is_host) out.push(g.room ? `<button type="button" class="secondary g-exit" data-exit="end">🏠 Terminer ce jeu et revenir à la salle</button>`
    : `<button type="button" class="danger g-exit" data-exit="end">${g.type === "room" ? "Fermer la salle pour tout le monde" : g.players.length <= 1 ? "Quitter et fermer la partie" : "Fermer la partie pour tout le monde"}</button>`);
  return out.join("");
}
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-exit]");
  if (!b || !game) return;
  const a = b.dataset.exit;
  if (a === "pick") { handoverOpen = !handoverOpen; return renderDrawer(game); }
  if (a === "to") {
    const p = game.players.find((x) => x.pid === b.dataset.target);
    const stays = !!game.me;
    if (!p || !confirm(`${p.name} devient l'animateur${stays ? " ; tu restes joueur" : ""}. Continuer ?`)) return;
    handoverOpen = false;
    closeDrawer();
    if (!await gameAction("handover", { target: p.pid })) return;
    if (!stays) { setGame(""); renderGame(null); }
    return toast(`${p.name} anime maintenant la partie`, "ok");
  }
  if (a === "end") {
    const msg = game.room ? "Terminer ce jeu ? Tout le monde revient à la salle." : game.type === "room" ? "Fermer la salle pour tout le monde ?" : "Fermer la partie pour tout le monde ?";
    if (confirm(msg)) { closeDrawer(); gameAction("end"); }
    return;
  }
  if (a === "leave") { if (confirm("Quitter la partie ?")) { closeDrawer(); gameAction("leave"); } return; }
  if (a === "away") {
    if (game?.kicked || game?.excluded) { clearInterval(kickTimer); kickCode = ""; myRoom = ""; store("vp_room", ""); }
    closeDrawer(); setGame(""); renderGame(null);
  }
});
// Options choisies sur la carte d'un jeu (création directe, ou lancement depuis la salle de jeux).
function gamePayload(card, type) {
  const q = (sel) => card.querySelector(sel);
  let sips = q("[data-opt=alcohol]") && !q("[data-opt=alcohol]").checked ? 0 : +(q("[data-opt-group=sips] [data-val-out]")?.textContent || 0);
  if (type === "quiz") sips = q("[data-opt=qzsips]")?.checked ? 1 : 0;
  if (type === "purity") sips = q("[data-opt=pualcohol]")?.checked ? +(q("[data-opt-group=pusips] .on")?.dataset.val || 2) : 0;
  if (type === "biskit") sips = q("[data-opt=bkalcohol]")?.checked ? +(q("[data-opt-group=bkmult] .on")?.dataset.val || 1) : 0;
  if (type === "likely") sips = q("[data-opt=lkalcohol]")?.checked ? +(q("[data-opt-group=lksips] .on")?.dataset.val || 1) : 0;
  return {
    type, sips, white: q("[data-opt=white]")?.checked ?? true, plays: q("[data-opt=plays]")?.checked ?? true,
    mode: q("[data-opt-group=mode] .on")?.dataset.val || "soft",
    cats: type === "likely" ? ["family", ...(q("[data-opt=lkfriends]")?.checked ? ["friends"] : [])]
      : [...card.querySelectorAll("[data-opt-group=cats] .on")].map((x) => x.dataset.val),
    floors: +(q("[data-opt-group=floors] [data-val-out]")?.textContent || 5),
    pmode: q("[data-opt-group=pmode] .on")?.dataset.val || "soft",
    poteau: q("[data-opt-group=poteau] .on")?.dataset.val || "soft",
    double: q("[data-opt-group=floorsips] .on")?.dataset.val === "2",
    boat: q("[data-opt=boat]")?.checked ?? true,
    impostors: +(q("[data-opt-group=impostors] .on")?.dataset.val || 0),
    reveal: q("[data-opt=reveal]")?.checked ?? false,
    hint: q("[data-opt=hint]")?.checked ?? false,
    white_hint: q("[data-opt=white_hint]")?.checked ?? false,
    public: q("[data-opt=dbpublic]")?.checked ?? false,
  };
}
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-create]");
  if (!b) return;
  const card = b.closest(".gcard");
  const payload = gamePayload(card, b.dataset.create);
  // Dans la salle de jeux : le jeu est lancé pour tout le monde (personne ne retape de code).
  if (b.closest(".g-room-sheet")) {
    closeRoomSheet();
    return pressed(b, gameAction("launch", { settings: payload }));
  }
  if (payload.type === "purity") {
    payload.token = (typeof freshToken === "function" && await freshToken()) || "";
    if (!payload.token) { toast("🔒 Connecte-toi avec ton numéro pour lancer le Purify Test", "err"); return showTab("account"); }
  }
  b.disabled = true;
  try {
    const g = await gapi("/api/games", { guest_id: guestId, name: guestName, ...payload });
    setGame(g.code); renderGame(g);
    toast(g.type === "room" ? `Salle ouverte : code ${g.code}` : `Partie créée : code ${g.code}`, "ok");
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
// Dans une partie : les réglages choisis en tête, et seulement les règles du mode joué.
function rulesFor(type, g) {
  if (!g) return GAME_RULES[type];
  const sips = g.options?.sips || 0;
  let facts = [];
  if (g.mode) facts.push(`Questions : <b>${esc(g.mode)}</b>`);
  if (type === "undercover") facts.push(g.options?.white ? "Avec <b>Mr. White</b> (dès 5 joueurs)" : "<b>Sans</b> Mr. White");
  if (type === "blackjack") facts.push(sips ? `Mode <b>gorgées</b> · mise de 1 à <b>${sipWord(sips)}</b>` : "Mode <b>jetons</b> · 100 jetons au départ");
  if (type === "pyramid") facts.push(`${g.pyr?.floors || g.options?.floors || 5} étages`,
    g.pyr?.hard ? "Distribution <b>hard</b> : 1, 2, 3, 4 gorgées" : "Distribution <b>soft</b> : 1 gorgée par carte",
    g.pyr?.poteau_hard ? "Poteau <b>hard</b> : cul sec pour le tireur" : "Poteau <b>soft</b> : tout le monde boit 1",
    g.pyr?.double ? "Étages : <b>2, 4, 6…</b> gorgées" : "Étages : <b>1, 2, 3…</b> gorgées", g.pyr?.boat_on ? "<b>Avec</b> le bateau" : "<b>Sans</b> bateau");
  if (type === "biskit") facts.push(g.bk?.alcohol ? `Avec alcool · gorgées <b>×${g.bk.mult}</b>` : "<b>Sans alcool</b> (points de gage)",
    g.bk?.biskit ? `Le Biskit : <b>${esc(g.bk.biskit)}</b>` : "", g.bk?.key ? `Dernière carte : <b>${esc(BK_RULES[g.bk.key][1])}</b> (surlignée plus bas)` : "");
  if (type === "casino") facts.push(sips ? `Mode <b>gorgées</b> · jusqu'à <b>${sipWord(sips)}</b> misées par tour` : "Mode <b>jetons</b> · 100 jetons au départ");
  else if (type === "whoof" || type === "never") facts.push(sips ? `<b>${sipWord(sips)}</b> ${type === "whoof" ? "pour la personne désignée" : "pour ceux qui l'ont fait"}` : "<b>Sans alcool</b>");
  facts.push(`Animée par <b>${esc(g.host_name || "?")}</b> · code <b>${esc(g.code)}</b>`);
  facts = facts.filter(Boolean);
  let body = GAME_RULES[type];
  if (type === "casino") body = CASINO_RULES_COMMON + (sips ? CASINO_RULES_DRINKS : CASINO_RULES_CHIPS);
  if (type === "blackjack") body = BJ_RULES_COMMON + (sips ? BJ_RULES_DRINKS : GAME_RULES.blackjack.slice(BJ_RULES_COMMON.length).replace(BJ_RULES_DRINKS, ""));
  return `<div class="g-facts"><h3>Cette partie</h3><ul>${facts.map((f) => `<li>${f}</li>`).join("")}</ul></div>` + body;
}

// « ? » : règles détaillées du jeu.
const GAME_NAMES = { undercover: "Undercover", whoof: "Qui de nous ?", likely: "Qui est le plus… ?", debate: "Pour ou contre", never: "Je n'ai jamais", roulette: "Roulette",
  blackjack: "Blackjack", casino: "Casino", divan: "Le Divan", tmc: "Tu me connais ?", pyramid: "Pyramide", biskit: "Biskit Royal", quiz: "Quiz", purity: "Purify Test", room: "Salle de jeux", president: "Président", neon: "Néon Knockout", island: "L’île qui s’effondre", heist: "Braquage en miniature" };
document.addEventListener("click", (ev) => {
  const open = ev.target.closest("[data-rules]");
  if (open) {
    const t = open.dataset.rules;
    $("rulesModal").querySelector(".g-sheet").className = "g-sheet " + GAME_THEME[t];
    $("rulesIcon").innerHTML = GAME_ICONS[t];
    $("rulesTitle").textContent = GAME_NAMES[t];
    $("rulesBody").innerHTML = rulesFor(t, open.hasAttribute("data-ingame") ? game : null);
    $("rulesBody").scrollTop = 0;
    // Biskit Royal en pleine partie : la ligne de la carte tirée est surlignée, et on y va directement.
    if (t === "biskit" && open.hasAttribute("data-ingame") && game?.bk?.key) {
      const row = $("rulesBody").querySelector(`[data-rule="${game.bk.key}"]`);
      if (row) { row.classList.add("hl"); setTimeout(() => row.scrollIntoView({ block: "center", behavior: "smooth" }), 250); }
    }
    $("rulesModal").classList.remove("hidden");
    document.body.style.overflow = "hidden";
    return;
  }
  if (ev.target.closest("[data-rules-close]") || ev.target.id === "rulesModal") {
    $("rulesModal").classList.add("hidden");
    document.body.style.overflow = "";
  }
});

// Blackjack : le réglage des gorgées n'apparaît qu'avec « Alcool ».
document.addEventListener("change", (ev) => {
  if (ev.target.dataset?.opt !== "alcohol") return;
  ev.target.closest(".gcard").querySelector("[data-alcohol-only]").hidden = !ev.target.checked;
});

// Options de création : mode (boutons) et gorgées (− / +).
document.addEventListener("click", (ev) => {
  const cat = ev.target.closest("[data-opt-group=cats] [data-val]");
  if (cat) {
    const on = cat.parentElement.querySelectorAll(".on");
    if (!(cat.classList.contains("on") && on.length === 1)) cat.classList.toggle("on");
    // Le mode couple remplace les autres catégories (et inversement).
    const couple = cat.parentElement.querySelector("[data-val=couple]");
    if (cat === couple && cat.classList.contains("on")) on.forEach((b) => b !== cat && b.classList.remove("on"));
    else if (cat !== couple && cat.classList.contains("on")) couple?.classList.remove("on");
  }
  const pm = ev.target.closest("[data-opt-group=pmode] [data-val], [data-opt-group=poteau] [data-val], [data-opt-group=floorsips] [data-val], [data-opt-group=bkmult] [data-val], [data-opt-group=impostors] [data-val], [data-opt-group=pusips] [data-val], [data-opt-group=lksips] [data-val]");
  if (pm) pm.parentElement.querySelectorAll("[data-val]").forEach((x) => x.classList.toggle("on", x === pm));
  const opt = ev.target.closest("[data-opt-group=mode] [data-val]");
  if (opt) opt.parentElement.querySelectorAll("[data-val]").forEach((b) => b.classList.toggle("on", b === opt));
  const fl = ev.target.closest("[data-opt-group=floors] [data-step]");
  if (fl) {
    const out = fl.parentElement.querySelector("[data-val-out]");
    out.textContent = Math.max(5, Math.min(8, +out.textContent + +fl.dataset.step));
  }
  const step = ev.target.closest("[data-opt-group=sips] [data-step]");
  if (step) {
    const out = step.parentElement.querySelector("[data-val-out]");
    const min = step.closest("[data-alcohol-only]") ? 1 : 0;  // mise max du blackjack : au moins 1 gorgée
    out.textContent = Math.max(min, Math.min(10, +out.textContent + +step.dataset.step));
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
  if (typeof renderNameChip === "function") renderNameChip();
  // L'hôte voit la personne dans ses Réglages dès qu'elle a donné son prénom.
  gapi("/api/presence", { guest_id: guestId, name: guestName }).catch(() => {});
  refreshGame();
  if (typeof refresh === "function") refresh();
});

