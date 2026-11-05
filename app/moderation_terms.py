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
