// 🎮 Jeux, partagés par la page invités et l'admin.
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
const GAME_THEME = { undercover: "g-uc", whoof: "g-wh", never: "g-nv", roulette: "g-rl", blackjack: "g-bj", casino: "g-cs" };
const isBJ = (g) => g.type === "blackjack";
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
  reveal: "Résultat de la manche", end: "Partie terminée", question: "Question", results: "Résultats", spun: "Résultat", bet: "Mises", play: "Partie" };
const phaseLabel = (g) => (g.type === "roulette" || isBJ(g) || g.type === "casino") && g.phase === "lobby" ? "Préparation"
  : g.type === "casino" && g.phase === "bet" ? "Faites vos jeux" : GAME_PHASES[g.phase];
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
  if (!guestName) {
    $("gHome").classList.add("hidden"); $("gamePlay").classList.add("hidden");
    if (typeof maybeInstallSheet === "function") maybeInstallSheet();
    return;
  }
  $("gHello").textContent = guestName;
  if (!myGame) return renderGame(null);
  try {
    const g = await gapi(`/api/games/${myGame}?guest_id=${encodeURIComponent(guestId)}`);
    if (autoJoin && !g.me && !g.is_host) { autoJoin = false; return gameAction("join"); }
    renderGame(g);
  } catch (e) {
    // Partie introuvable, ou erreur du serveur : on revient à l'accueil des jeux plutôt que de rester sur une page vide.
    if (e.status === 404) { setGame(""); toast("Cette partie n'existe plus", "err"); }
    else if (!game) toast("Impossible de charger la partie, réessaie", "err");
    if (e.status === 404 || !game) renderGame(null);
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
  renderCasino(g);  // avant le texte : il dépend de l'état de la bille (en train de rouler ou arrêtée)
  const title = `<div class="g-head g-play-head"><div class="g-icon">${GAME_ICONS[g.type] || ""}</div>
    <div class="g-meta"><div class="g-title">${esc(g.name)}</div>
    <div class="g-tag">${g.mode ? esc(g.mode) + " · " : ""}${phaseLabel(g)}${g.round && g.phase !== "lobby" ? ` · ${{ undercover: "manche", roulette: "tirage", blackjack: "main", casino: "tour" }[g.type] || "question"} ${g.round}` : ""}</div></div>
    ${helpBtn(g.type, true)}</div>`;
  const lastLine = g.last?.name ? `<p class="sub" style="margin:8px 0">${esc(g.last.name)} était <b>${esc(g.last.role)}</b>.${g.last.guess ? ` Mr. White a proposé « ${esc(g.last.guess)} »… raté !` : ""}</p>` : "";
  let body = "";

  if (g.type === "casino") {
    body = casinoStatusHtml(g);
  } else if (isBJ(g)) {
    body = bjTableHtml(g);
  } else if (g.type === "roulette") {
    body = g.is_host
      ? `<div class="artist">${g.names.length < 2 ? "Note au moins 2 noms ci-dessous, puis lance la roue." : "Prêt ? Lance la roue !"}</div>`
      : `<div class="artist">${g.phase === "spun" ? "La roue a parlé…" : `${esc(g.host_name)} prépare la roue…`}</div>
         ${!me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:10px">Je participe (l'animateur pourra m'ajouter à la roue)</button>` : ""}`;
  } else if (g.kicked) {
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
  renderRoulette(g);
  renderHud(g);
  bjOutcomeFx(g);
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
  navigator.vibrate?.({ win: [80, 60, 80], blackjack: [100, 50, 100, 50, 220], jackpot: [100, 50, 100, 50, 100, 50, 300],
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
  $("gameHud").innerHTML = items.join("");
  $("gameHud").className = "g-hud " + (GAME_THEME[g.type] || "") + (items.length ? "" : " hidden");
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
  if (t.my_turn && bjTurnSeen !== g.id + g.round) { bjTurnSeen = g.id + g.round; navigator.vibrate?.(120); }
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
  $("gameHost").innerHTML = `
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
        ${g.is_host && x.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(x.pid)}" title="Exclure de la table">✕</button>` : ""}
      </div>`;
    }).join("") || `<p class="empty" style="padding:12px">Personne à la table : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.is_host && !g.me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
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
    bet: btn("cspin", `🎲 Rien ne va plus ! (${bettors}/${g.players.length} ont misé)`, "grow cs-spin", bettors ? "" : "disabled"),
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
  $("gameHost").innerHTML = `
    ${controls ? `<div class="row" style="margin-top:10px">${controls}</div>` : ""}
    ${!me ? (g.phase !== "lobby" ? `<button data-gact="join" style="width:100%;margin-top:10px">S'asseoir à la table</button>` : "") : `
      ${open ? `<div class="cs-chips" role="group" aria-label="Valeur du jeton">${values.map((v) => `<button type="button" class="cs-chip v${values.indexOf(v)} ${v === casinoChip ? "on" : ""}" data-cchip="${v}" ${v > left ? "disabled" : ""}>${c.drinks ? `🍻${v}` : v}</button>`).join("")}
        <button type="button" class="secondary cs-clear" data-gact="cclear" ${me.staked ? "" : "disabled"}>Effacer</button></div>` : ""}
      ${!c.drinks && me.chips < 1 && !me.staked && open ? `<button data-gact="crebuy" style="width:100%;margin-top:8px">Recharger ${c.start_chips} jetons</button>` : ""}`}
    <div class="rt ${open && me ? "" : "rt-closed"}">${grid}</div>
    <div class="rt rt-outside ${open && me ? "" : "rt-closed"}">${outside}</div>
    <h2>À la table (${g.players.length})</h2>
    <div class="list">${c.table.map((t) => `
      <div class="track">
        <div class="meta"><div class="title">${esc(t.name)}${c.drinks ? "" : `<span class="artist"> · 💰 ${t.chips}${t.rebuys ? ` (rechargé ${t.rebuys}×)` : ""}</span>`}${sipsBadge(g.players.find((p) => p.pid === t.pid) || {})}</div>
          <div class="artist" style="white-space:normal">${t.staked ? summary(t) : g.phase === "bet" ? "réfléchit…" : "n'a pas misé"}${resultTxt(t) ? ` · <b>${resultTxt(t)}</b>` : ""}</div></div>
        ${g.is_host && t.pid !== g.me?.pid ? `<button class="secondary" data-gact="remove" data-target="${esc(t.pid)}" title="Exclure de la table">✕</button>` : ""}
      </div>`).join("") || `<p class="empty" style="padding:12px">Personne à la table : fais scanner le QR ci-dessous.</p>`}</div>
    ${g.is_host && !g.me ? `<button class="secondary" data-gact="join" style="width:100%;margin-top:8px">Je joue aussi</button>` : ""}`;
}
document.addEventListener("click", (ev) => {
  const chip = ev.target.closest("[data-cchip]");
  if (chip) { casinoChip = +chip.dataset.cchip; return renderGameHost(game); }
  const cell = ev.target.closest("[data-cbet]");
  if (cell && game?.type === "casino") {
    navigator.vibrate?.(15);
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
      spinningUntil = Date.now() + left * 1000;
      setWheel(wheelRot, left);
      setTimeout(() => {
        wheelShown = sp.id;
        if (game?.spin?.id === sp.id) { showRouletteResult(game); renderGameHost(game); }
        navigator.vibrate?.(150);
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
  $("gameHost").innerHTML = `
    ${g.is_host ? `
      <div class="row" style="margin-top:10px">${btn("spin", spinning ? "La roue tourne…" : "🎡 Lancer la roue", "grow g-spin", g.names.length < 2 || spinning ? "disabled" : "")}</div>
      ${loser && g.names.includes(loser) ? `<button class="secondary" data-gact="dropname" data-name="${esc(loser)}" style="width:100%;margin-top:8px">Retirer ${esc(loser)} de la roue</button>` : ""}
      <h2>Sur la roue (${g.names.length})</h2>
      <form data-gform="addname" class="row">
        <input class="grow" type="text" id="rouletteName" maxlength="20" placeholder="Ajouter un nom" autocomplete="off">
        <button>Ajouter</button>
      </form>
      <div class="chips" style="margin-top:8px">${g.names.map((n) => `<span class="pill name-chip">${esc(n)}<button type="button" class="chip-x" data-gact="dropname" data-name="${esc(n)}" aria-label="Retirer ${esc(n)}">✕</button></span>`).join("") || `<span class="artist">Aucun nom pour l'instant</span>`}</div>
      ${joined.length ? `<button class="secondary" data-gact="addplayers" style="width:100%;margin-top:8px">👥 Ajouter les joueurs inscrits (${joined.length})</button>` : ""}` : ""}
    ${g.history?.length ? `<h2>Derniers perdants</h2><div class="chips">${g.history.slice(0, 10).map((n, i) => `<span class="pill" style="${i === 0 ? "color:var(--text)" : ""}">${esc(n)}</span>`).join("")}</div>` : ""}
    ${g.players.length ? `<h2>Spectateurs (${g.players.length})</h2><div class="chips">${g.players.map((p) => `<span class="pill">${esc(p.name)}</span>`).join("")}</div>` : ""}`;
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
  if (g.type === "roulette") return renderRouletteHost(g, btn);
  if (isBJ(g)) return renderBJHost(g, btn);
  if (g.type === "casino") return renderCasinoHost(g, btn);
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
        <div class="meta"><div class="title" ${p.waiting ? 'title="Joue à la prochaine partie"' : ""}>${speaking && p.alive ? `${i + 1}. ` : ""}${p.waiting ? "⏳ " : p.alive ? "" : "✝︎ "}${esc(p.name)}${p.host ? " 🎲" : ""}${(g.phase === "vote" || g.phase === "question") && p.voted ? " ✓" : ""}${sipsBadge(p)}</div>
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
  if (a === "dropname") return gameAction("names", { names: game.names.filter((n) => n !== b.dataset.name) });
  if (a === "addplayers") return gameAction("names", { names: game.names.concat(game.players.map((p) => p.name)) });
  if (a === "eliminate" && !confirm("Éliminer ce joueur ?")) return;
  if (a === "remove" && !confirm("Exclure ce joueur de la partie ? Il ne pourra pas revenir.")) return;
  gameAction(a, { target: b.dataset.target || "", amount: +(b.dataset.amount || 0) });
});
document.addEventListener("submit", (ev) => {
  if (!ev.target.closest("[data-gform=addname]")) return;
  ev.preventDefault();
  const name = $("rouletteName").value.trim();
  if (!name) return;
  gameAction("names", { names: game.names.concat([name]) }).then(() => $("rouletteName")?.focus());
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
      white: card.querySelector("[data-opt=white]")?.checked ?? true, plays: card.querySelector("[data-opt=plays]")?.checked ?? false,
      mode: card.querySelector("[data-opt-group=mode] .on")?.dataset.val || "soft",
      // Blackjack : gorgées seulement si « Alcool » est coché.
      sips: card.querySelector("[data-opt=alcohol]") && !card.querySelector("[data-opt=alcohol]").checked ? 0
        : +(card.querySelector("[data-opt-group=sips] [data-val-out]")?.textContent || 0) });
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
// Dans une partie : les réglages choisis en tête, et seulement les règles du mode joué.
function rulesFor(type, g) {
  if (!g) return GAME_RULES[type];
  const sips = g.options?.sips || 0, facts = [];
  if (g.mode) facts.push(`Questions : <b>${esc(g.mode)}</b>`);
  if (type === "undercover") facts.push(g.options?.white ? "Avec <b>Mr. White</b> (dès 5 joueurs)" : "<b>Sans</b> Mr. White");
  if (type === "blackjack") facts.push(sips ? `Mode <b>gorgées</b> · mise de 1 à <b>${sipWord(sips)}</b>` : "Mode <b>jetons</b> · 100 jetons au départ");
  if (type === "casino") facts.push(sips ? `Mode <b>gorgées</b> · jusqu'à <b>${sipWord(sips)}</b> misées par tour` : "Mode <b>jetons</b> · 100 jetons au départ");
  else if (type === "whoof" || type === "never") facts.push(sips ? `<b>${sipWord(sips)}</b> ${type === "whoof" ? "pour la personne désignée" : "pour ceux qui l'ont fait"}` : "<b>Sans alcool</b>");
  facts.push(`Animée par <b>${esc(g.host_name || "?")}</b> · code <b>${esc(g.code)}</b>`);
  let body = GAME_RULES[type];
  if (type === "casino") body = CASINO_RULES_COMMON + (sips ? CASINO_RULES_DRINKS : CASINO_RULES_CHIPS);
  if (type === "blackjack") body = BJ_RULES_COMMON + (sips ? BJ_RULES_DRINKS : GAME_RULES.blackjack.slice(BJ_RULES_COMMON.length).replace(BJ_RULES_DRINKS, ""));
  return `<div class="g-facts"><h3>Cette partie</h3><ul>${facts.map((f) => `<li>${f}</li>`).join("")}</ul></div>` + body;
}

// « ? » : règles détaillées du jeu.
const GAME_NAMES = { undercover: "Undercover", whoof: "Qui de nous ?", never: "Je n'ai jamais", roulette: "Roulette",
  blackjack: "Blackjack", casino: "Casino" };
document.addEventListener("click", (ev) => {
  const open = ev.target.closest("[data-rules]");
  if (open) {
    const t = open.dataset.rules;
    $("rulesModal").querySelector(".g-sheet").className = "g-sheet " + GAME_THEME[t];
    $("rulesIcon").innerHTML = GAME_ICONS[t];
    $("rulesTitle").textContent = GAME_NAMES[t];
    $("rulesBody").innerHTML = rulesFor(t, open.hasAttribute("data-ingame") ? game : null);
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

// Blackjack : le réglage des gorgées n'apparaît qu'avec « Alcool ».
document.addEventListener("change", (ev) => {
  if (ev.target.dataset?.opt !== "alcohol") return;
  ev.target.closest(".gcard").querySelector("[data-alcohol-only]").hidden = !ev.target.checked;
});

// Options de création : mode (boutons) et gorgées (− / +).
document.addEventListener("click", (ev) => {
  const opt = ev.target.closest("[data-opt-group=mode] [data-val]");
  if (opt) opt.parentElement.querySelectorAll("[data-val]").forEach((b) => b.classList.toggle("on", b === opt));
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
  refreshGame();
  if (typeof refresh === "function") refresh();
});

