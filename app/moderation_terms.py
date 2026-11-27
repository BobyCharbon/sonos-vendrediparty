"""Liste des mots refusés ou masqués (modération commune, Apple 1.2 / Google UGC) : FR, DE, IT, EN courants.

SOURCE UNIQUE : la base (private.moderation_patterns) reçoit EXACTEMENT les motifs produits par
app/moderation.py:patterns() ; la migration est vérifiée par tests/test_moderation.py. Après un changement ici :
`python -m app.moderation --sql` puis recopier le bloc dans une nouvelle migration (et le fichier prod).

Écriture d'une entrée (après normalisation : minuscules, sans accents, 0→o 1→i 3→e 4→a 5→s 7→t @→a $→s) :
- « mot »      : le mot entier, lettres répétées tolérées (« saloooope »), pluriel/féminin courts (s, x, e, es, en, n) ;
- « mot* »     : tous les mots qui commencent ainsi (« encul* » : enculé, enculer…) ;
- « =mot »     : le mot exact, sans lettres répétées ni pluriel (« =bite » ne touche pas l'allemand « bitte ») ;
- « re:… »     : motif brut (sous-ensemble commun à Python et PostgreSQL : [a-z], + ? * | ( ) {n,}) ;
- plusieurs mots séparés par une espace : l'expression entière (espaces et ponctuation tolérés entre les mots).

Choix : seuls les mots qui visent une personne ou sont explicitement sexuels ou haineux. Les jurons courants qui ne
visent personne (« merde », « putain », « scheisse », « shit », « cazzo ») restent permis : le groupe est entre amis.
Les mots à double sens trop fréquents sont exclus (« con » = « avec » en italien, « chatte », « tapette », « queue »,
« schwanz », « finocchio », « retard », « negroni »…)."""

HAINE = (
    # FR
    "negre", "bougnoul*", "bicot", "youpin", "youtre", "bamboula", "chinetoque", "niakoue", "pede", "pd", "gouine",
    "tarlouze", "sale arabe", "sale juif", "sale noir", "sale negre",
    # DE
    "neger", "kanake", "kanacke", "schwuchtel", "judensau", "heil hitler", "sieg heil",
    # IT
    "negro", "frocio", "ricchione",
    # EN
    "re:n+i+g{2,}(a|e+r)[a-z]*", "faggot*", "fag", "kike", "=spic", "chink", "tranny", "white power",
)

SEXUEL = (
    # FR
    "=bite", "teub", "zgeg", "porno*", "sodomi*", "fellation", "cunnilingus", "ejacul*", "masturb*", "partouze",
    "pedophil*", "zoophil*", "baiseu*", "baise moi", "suce moi", "suceu*", "gode",
    # DE
    "fotze", "ficken", "bumsen",
    # IT
    "pompino", "scopare", "figa",
    # EN
    "porn*", "blowjob*", "cumshot*", "handjob*", "dildo*", "pussy", "cock", "horny", "nudes", "sexting", "anal",
    "bukkake",
)

INSULTE = (
    # FR
    "conard*", "conasse", "re:con{2,}e", "gros con", "sale con", "pauvre con", "encul*", "salope", "salaud", "batard*",
    "pute", "fils de pute", "nique ta mere", "ntm", "fdp", "pouffiasse", "petasse", "branleur*", "enfoire*",
    "grognasse",
    # DE
    "arschloch*", "wichser", "hurensohn*", "missgeburt", "spast", "spasti", "fick dich", "schlampe", "hure",
    "drecksau",
    # IT
    "stronzo", "stronza", "vaffanculo", "fanculo", "coglione", "puttana", "troia", "bastardo", "figlio di puttana",
    "testa di cazzo",
    # EN
    "fuck*", "motherfuck*", "asshole*", "bitch*", "bastard", "cunt*", "dickhead*", "=dick", "slut*", "whore*",
    "wanker*", "twat*",
)

CATEGORIES = (("haine", HAINE), ("sexuel", SEXUEL), ("insulte", INSULTE))

# App App Store seulement (contrôle Apple du 26.11, 1.1 / 1.2 / 1.4.3) : refusés dans les prénoms et textes d'une partie
# de l'app, prénoms montrés « Joueur » à l'app. HORS de CATEGORIES : ni la base ni le web ne changent (les jurons
# courants y restent permis, voir plus haut). Mots entiers seulement (« Shitaké », « Matchatte », « Merdan », « Nazir »
# passent). Même écriture que plus haut.
STORE_ONLY = (
    # haine
    "hitler*", "nazi", "nazisme", "neonazi*", "fuhrer", "=heil",
    # drogue
    "ganja", "re:w+e{2,}d+", "beuh", "petard", "marijuana", "marihuana", "hasch*", "shit", "=bedo", "spliff", "=kush",
    # sexuel / insulte
    "chatte", "zizi", "trou du cul", "trouduc", "merde", "merdeux", "merdique", "emmerdeu*", "putain", "=ptn",
    "couille", "nichon",
    # Contrôle Apple, tour 5 (27.11) : par familles, une fois (textes des JOUEURS de l'app seulement, jamais les banques ni
    # le filtre des événements). « kkk », « ss » : forme « = » (sinon les lettres répétées donnent « k+ », « s+ ») ;
    # « 88 », « get 27 », « 1664 », « label 5 » : chiffres, lus sur le texte brut (store_app.RAW_TOKENS).
    # drogue
    "ketamine", "=keta", "=ketas", "meth", "methamphetamine*", "codeine", "poppers", "=xtc", "=hero", "heroinoman*",
    "champi", "champignons hallucinog*", "opiac*", "fentanyl", "=ghb",
    # ivresse
    "pochtron", "poivrot", "ivrogne", "murge", "gnole", "gniole", "schnaps", "ti punch", "cuba libre", "bloody mary",
    "beuverie", "alcoolo", "alcolo", "saoulard", "soulard", "vinasse", "piquette", "picrate", "williamine",
    # marques d'alcool
    "smirnoff", "jack daniel*", "jackdaniel*", "baileys", "desperados", "kronenbourg", "hennessy", "bacardi",
    "johnnie walker", "johnny walker", "jim beam", "ballantine*", "chivas", "jameson", "glenfiddich", "captain morgan",
    "budweiser", "carlsberg", "leffe", "stella artois", "hoegaarden", "grimbergen", "duvel", "chimay", "pelforth",
    "=moet", "dom perignon", "veuve clicquot", "ruinart", "tanqueray", "bombay sapphire", "havana club", "cointreau",
    "grand marnier", "jose cuervo", "william lawson*", "clan campbell", "four roses", "southern comfort", "kahlua",
    "passoa", "pernod", "=picon", "lillet", "amstel", "tuborg", "affligem", "goudale", "delirium tremens", "chouffe",
    "karmeliet", "westmalle", "feldschl*", "calanda", "quollfrisch", "absolut vodka", "grey goose", "jagerbomb*",
    # paris
    "jackpot", "betclic", "winamax", "=pmu", "unibet", "parions sport", "pokerstars", "=bwin", "zebet", "=fdj",
    "euromillion*", "bookmaker*", "bookie", "machine a sous", "machines a sous", "loterie", "=loto", "=lotos", "grattage",
    # haine
    "=kkk", "ku klux klan", "kuklux*", "daech", "daesh", "ben laden", "al qaida", "al qaeda", "=ratons?(?! laveur)",
    "tapette", "feuj", "mongol", "trisomique", "=gogol", "=ss", "staline", "terroriste", "terrorisme", "djihad*",
    "jihad*", "aryen", "supremaciste*", "mussolini", "goebbels", "himmler", "pol pot", "suicid*",
    # violence sexuelle
    "viol", "violer", "violeur*", "violez", "=pedo", "=pedos", "pedocriminel*", "inceste", "incestueu*",
    # sexuel
    "=(?<!pique )niqu(e|es|er|ez|ent|ee|ees)", "=suc(e|es|er|ent)", "penis", "vagin", "clito*", "orgie", "sexe",
    "sperme", "branl*", "=sodo",
    # Contrôle Apple, tour 6 (27.11) : la même chose en anglais, allemand, italien, espagnol (et néerlandais), et l'argot
    # français qui manquait, une fois par famille. Formes « = » (mot exact) pour les mots courts ou à double sens ; jamais
    # « die » (article allemand), « ale » (Ale, Alejandra), « butt » (nom de famille), « high » seul (« high school »),
    # « isis » (prénom), « jaja » / « lager » (allemand), « retard » (« en retard »), « rape » (« râpe » : store_app.RAPE).
    # boisson, ivresse
    "alcohol*", "drunk*", "drink*", "=wines?", "booze*", "=wasted", "hammered", "tipsy", "=liquors?", "=kegs?",
    "=chug", "chugging", "hangover*", "=beers", "=rum", "=cider", "purple drank", "=bier", "biertje",
    "saufen", "besoffen", "betrunken", "=wein", "birra", "ubriac*", "sbronz*", "=vino", "cerveza*", "cerveja*",
    "borrach*", "emborrach*", "chupito*", "dronken", "zuipen", "petit rose", "=martini", "jupiler", "paulaner", "=kwak",
    "=murger", "se pinter", "se cuiter", "=cuiter", "queue de pelle", "chouille",
    # drogue, tabac
    "stoned", "=stoners?", "pothead*", "crackhead*", "junkie*", "get high", "getting high", "got high", "so high",
    "get lit", "shrooms", "xanax", "=heroin", "=cocain", "cocaina", "kokain*", "=snort", "=cigs?", "=juul", "elfbar*",
    "=iqos", "marlboro*", "lucky strike", "smoke weed", "kiffen", "=ecsta", "de la md", "ballon de proto", "=du proto",
    "gaz hilarant", "amphet*", "=amphe", "=sniff", "sniffer", "sniffe", "sniffent", "sniffait", "=zamal", "=teuch",
    # jeux d'argent
    "=bets?", "betting", "gambl*", "wager*", "betway", "=ixbet", "swisslos", "=tribolo", "bandit manchot", "baccara",
    "texas hold*", "faites vos jeux", "faites vos paris", "paris sportif*", "le quinte", "jouer de l argent",
    # haine
    "auschwitz", "mein kampf", "=petain", "troisieme reich", "drittes reich", "bin laden", "=dutroux", "=fourniret",
    "=breivik", "=ritals?", "=boches?", "sale pedale", "=fiottes?", "=tafioles?", "=travelos?", "=trisos?",
    "sale blanc", "sale blanche", "sale gitan*", "sale chinois*", "sale rital", "sale boche", "rudolf hess", "=heydrich",
    "=eichmann", "terrorist*",
    # sexuel
    "levrette", "plan cul", "chaudasse", "=tchoin", "=cochonnes?", "=zob", "chibre", "braquemart", "foufoune",
    "nibard*", "=boobs", "=tits", "=nude", "=naked", "orgasm*", "gangbang*", "=bdsm", "onlyfans", "=milfs?", "hentai",
    "=sex", "=sexy", "gros cul", "=catins?", "prostitu*", "=nymphos?", "nymphoman*", "=ass",
    # violence
    "rapist*",  # « rape » : store_app.RAPE, sur le texte tel quel (« râpe » se normalise en « rape »)
    "kill yourself", "kill urself", "=kys", "va crever", "vais te tuer", "va te tuer", "vais te buter", "va te pendre",
    "ta gueule", "=ftg", "va te faire foutre", "fils de chien",
    # Contrôle Apple, tour 7 (27.11), par familles. Incitation au suicide : impératifs pronominaux (« Tue-toi », « Pends
    # toi »…), « va mourir » (jamais « va mourir de rire »).
    "re:(tue|tues|pends|suicide|flingue|bute|immole|noie|egorge|empoisonne)[^a-z]+toi",
    "re:(jette|balance|lance)[^a-z]+toi[^a-z]+(d|du|depuis|par|sous|dans)[^a-z]+(un|une|le|la|les|l)[^a-z]+"
    "(pont|fenetre|train|metro|falaise|balcon|toit|immeuble|vide|voiture|camion)",
    "ouvre toi les veines", "taille toi les veines", "coupe toi les veines",
    "re:va[^a-z]+mourir(?![^a-z]+de)", "allez mourir",  # « crève » : store_app.CREVE (texte tel quel, avec son « è »)
    # haine : vocabulaire nazi (« reich » en mot exact : Reichenbach passe)
    "gestapo", "swastika", "svastika", "croix gammee", "hakenkreuz", "wehrmacht", "=waffen", "=reich", "=kapos?",
    "mengele", "eva braun", "sieg heil", "hitlerjugend",
)
