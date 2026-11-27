"""App VendrediParty de l'App Store (« PartyStore » dans l'User-Agent, ios/Party/AppConfig.swift).

Refus Apple 1.4.3 du 25.11.2026 (build 216) : dans l'app App Store, AUCUN jeu à boire, aucune gorgée, aucune
boisson alcoolisée ni drogue, aucun vote sexuel sur les présents (modes Hot / Mix). C'est le SERVEUR qui le garantit :
- jeux cachés : refusés à la création, au lancement depuis une salle, à la lecture et aux actions (code, QR) ;
- partie créée par l'app (ou lancée dans une salle où l'app est entrée) : marquée `store`, SANS gorgées ni « mode points »
  qui les remplacerait (`options.sips` toujours 0, tout réglage > 0 refusé : décision de l'admin du 25.11, les modes gorgées
  reviendront dans une mise à jour décrite à Apple) ; questions et mots tirés sans boisson ni drogue (`drinky`) ;
- partie créée ailleurs : refusée à l'app si elle a des gorgées (le web garde ses gorgées), un mode Hot / Mix, ou des
  questions déjà tirées sans ce filtre. Le site, l'app BETA et Android gardent tout. Voir CLAUDE.md « Refus Apple 1.4.3 (25.11) ».
"""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .moderation import check as moderation_check, clean as moderation_clean, merged, nfkc, normalize, store_hit

MARK = "PartyStore"
# Casino et Blackjack (jeux d'argent simulés) depuis le 05.11 ; les autres sont des jeux à boire par leur origine ou leur
# mécanique (Beer pong, Biskit, Pyramide, Je n'ai jamais, Qui de nous ?, Roulette « qui boit ») ou parlent de drogue et de
# sexe explicite (Purify Test). Décision de l'admin du 25.11 : BLOQUÉS pour la version 1.0.0, ils ne reviendront que dans une
# mise à jour décrite à Apple (le code « en points » de la Pyramide reste en place, éteint ici).
HIDDEN_GAMES = ("casino", "blackjack", "beerpong", "biskit", "purity", "pyramid", "never", "whoof", "roulette")
# Modes de questions refusés (votes sexuels sur les personnes présentes, Apple 1.1.4 / 1.2).
HIDDEN_MODES = ("hot", "mix")
# Jeux dont le texte vient d'une banque (questions, mots, cartes) filtrée dans une partie `store` : une partie de l'un
# d'eux lancée ailleurs n'est ouverte à l'app qu'avant le début (puis `store`).
BANK_GAMES = ("likely", "undercover", "quiz", "tmc", "divan", "debate", "masque")
# Thème de Pour ou contre caché dans l'app (nudité, strip-tease, « moment intime » : Apple 1.1.4, 1.4.5).
HIDDEN_THEMES = ("wtf",)
# Paquets de Qui est le plus… cachés dans l'app (soirées, lendemains : ivresse sans le mot, Apple 1.4.3).
HIDDEN_PACKS = ("friends",)
MESSAGE = "Ce jeu n'est pas disponible dans l'app."

# Mots et emojis de boisson, d'ivresse ou de drogue (larges exprès : une question de trop retirée ne coûte rien).
DRINK_RE = re.compile(
    r"gorg[ée]es?|\bboire\b|\bboi[st]\b|\bboivent\b|\bbuvez\b|\bbu\b|\bshots?\b|alcool|bi[èe]res?\b|\bvins?\b|vodka|tequila"
    r"|whisky|\brhums?\b|\bgin\b|\btourn[ée]es?\b|\bcuites?\b|\bivres?\b|ivresse|bourr[ée]e?s?\b|gueule de bois|ap[ée]ro"
    r"|cocktail|champagne|mojito|ca[iï]pirinha|sangria|spritz|pastis|j[äa]germeister|liqueur|\bbars?\b|\bverres?\b"
    r"|drogue|cannabis|coca[iï]ne|\bjoint\b|ecstasy|mdma|\blsd\b|cigarette|nicotine|\bvomi|tchin|\bbeer\b|bouteilles?\b"
    r"|ap[ée]ritif|arros[ée]|pot de d[ée]part|buvette|\bboirai|cuv[ée]e|vigneron|vendange|viticole|vignoble|c[ée]page"
    r"|absinthe|tabac|casino|poker|blackjack|cidre|\bkir\b|kirsch|cognac|calvados|armagnac|grappa|\bsak[ée]\b|prosecco"
    r"|\bcava\b|guinness|eau-de-vie|eaux-de-vie|damassine|fendant|chasselas|merlot|pinot|chouchen|soju|baijiu|limoncello"
    r"|ouzo|campari|aperol|cacha[çc]a|bourbon|cervoise|[ée]thanol|porto\b|bordeaux|bourgogne|beaujolais|chardonnay"
    r"|sauvignon|riesling|lambrusco|chianti|rioja|brasserie|brasseur|houblon|malt\b|distill|spiritueux|digestif"
    r"|\braki\b|mezcal|chartreuse|fernet|pimm|\bkvas\b|barolo|gamay|syrah|cornalin|humagne|d[ée]zaley|\bperlan\b"
    r"|johannisberg|arvine|perdrix|amaretto|poire williams|ros[ée] de provence|gin-tonic"
    r"|trafiquant|narcos|escobar|\bweeds\b|breaking bad|trainspotting|\bcoke\b|h[ée]ro[iï]ne\b|\bcrack\b|opium|dealer"
    r"|happy hour|after-?work|\bpintes?\b|oktoberfest|ti-?punch|binouze|pub crawl|margarita|\bshooters?\b|\bricard\b"
    r"|heineken|chicha|narguil[ée]|\bvapot|\bvape\b|\bpuffs?\b|\bj[äa]ger\b|\bpils\b|\bipa\b|verknipt|asbak"
    r"|🍻|🍺|🥃|🍸|🍹|🍷|🍾|🥂",
    re.IGNORECASE)
# Phrases qui supposent l'ivresse sans aucun mot de la liste (relues le 25.11) : jamais tirées dans l'app.
STORE_EXCLUDE = re.compile(
    r"sans savoir comment j['’]y étais arrivé|dormi dans ma voiture après une soirée|oublié avec qui j['’]étais venu"
    r"|oublier comment il est rentré|se réveiller chez quelqu['’]un d['’]autre|organiser l['’]after|la veille d['’]un examen"
    r"|plus jamais.{0,20}recommencer|dont tu ne te souviens plus du prénom|soirée légendaire|lendemain de soirée|lendemain d['’]une f[êe]te"
    r"|sans se souvenir|trou noir|black-?out|si (?:tu étais|c['’]était) une boisson"
    r"|(?:[ée]tait|serait) une boisson|soir[ée]e.{0,40}l[ée]gendaire",  # tour 8 : cartes du Divan
    re.IGNORECASE)


def is_store(request) -> bool:
    """L'app App Store : « PartyStore » dans l'User-Agent (vue web), et tout client iOS natif : les écrans natifs
    n'envoient que « X-Party-Native: ios » (PartyAPI.swift). Sur le site de test aussi : la BETA est la copie exacte
    de l'app App Store (décision de l'admin du 27.11)."""
    if request is None:
        return False
    ua = request.headers.get("user-agent", "")
    if MARK in ua:
        return True
    return request.headers.get("x-party-native") == "ios"


def drinky(text) -> bool:
    return _drinky(str(text or ""))


@lru_cache(maxsize=None)  # banques fixes : chaque texte n'est examiné qu'une fois
def _drinky(text: str) -> bool:
    return bool(DRINK_RE.search(text) or STORE_EXCLUDE.search(text))


TEXT_REFUSED = "Ce texte n'est pas accepté ici : choisis d'autres mots."


def offensive(text) -> bool:
    """Boisson, drogue, ou mot refusé dans l'app seulement (haine, drogue, sexuel, juron : moderation_terms.STORE_ONLY)."""
    return drinky(text) or store_hit(str(text or ""))


# Textes de JOUEURS seulement (prénoms, réponses, mots : jamais le filtre des événements ni des banques) : argot de
# l'ivresse et du pari que la liste commune ne connaît pas, écrit en clair, en chiffres (v0dka), lettres séparées
# (v.o.d.k.a) ou coupé en deux (hit ler). Contrôle Apple, tour 4 (27.11).
# « Paris » (la ville, le prénom) passe : seul « paris » sans majuscule (« faire des paris ») est refusé.
PLAYER_RAW = re.compile(r"so[ûü]l|torché", re.IGNORECASE)
PARIS = re.compile(r"(?<![^\W\d_])(?!Paris\b)[pP][aA][rR][iI][sS](?![^\W\d_])")
# Après normalisation (minuscules, sans accents, chiffres ramenés aux lettres, mots séparés par une espace).
PLAYER_NORM = re.compile(
    r"(^| )(picol\w*|trinqu\w*|saoul\w*|pompettes?|emeche\w*|bitures?|pinards?|tise[sr]?|tisent|tisez|torcher\w*"
    r"|torchent|defonc\w*|clopes?|clopers?|clopent|pari|parie[rsz]?|parient|parions|pariai[st]?|parieurs?|paries"
    r"|mise[rz]|misons|misent|misai[st]?|miseurs?|whiskey|vodka|hitler\w*"
    r"|(mettre|mets|met|mis|mise|mettent|mettait|mettais|mettons) (une|la|sa|ta|ma) (mine|race)"
    r"|cul[ ]sec|rouler un pet\w*|de la c|demis? pression|petites? mousses?|mousses? (bien )?fraiches?"
    r"|(boire|bu|prendre|prend|prends|pris|prenons|prennent|tenir|tient|tiens) (une|la|sa|ta|ma) caisse)( |$)"
    # « mise » / « mises » (enjeu) : refusé, sauf « mise à jour », « mise en place », « mise au point »…
    r"|(^| )mises?( |$)(?!(a|au|aux|en|bas|hors|jour|sur pied)( |$))")


NUMBER = re.compile(r"(?<![^\W\d_])\d{2,}(?![^\W\d_])")  # « 30 ans », « 5 à 7 » : un nombre reste un nombre
# Mots qu'on retrouve en recollant deux morceaux (« vod ka », « hit ler ») ; jamais toute la liste des boissons : deux
# mots ordinaires recollés en formeraient (« mal t'aime » → « malt »).
PAIR_WORDS = {"vodka", "whisky", "whiskey", "biere", "bieres", "alcool", "tequila", "cocaine", "cannabis", "hitler",
              "nazi", "nazis", "shots", "rhum", "picole", "picoler", "pompette", "saoul", "parier", "miser"}


def _player_forms(text: str) -> tuple[str, list[tuple[str, tuple]]]:
    """Le texte normalisé (chiffres dans un mot ramenés aux lettres, lettres séparées recollées), et chaque paire de
    mots voisins recollée (« hit ler » → « hitler »)."""
    norm = merged(normalize(moderation_clean(NUMBER.sub(" ", text))))
    words = merged(normalize(moderation_clean(NUMBER.sub(" ", INITIAL.sub(" ", ELISION.sub(" ", text)))))).split()
    return norm, [("".join(p), p) for p in zip(words, words[1:])]  # « Martin I » ≠ « martini »


# Mots en chiffres ou de deux lettres, lus sur le texte BRUT (NFKC, minuscules) en mot entier : la normalisation ferait
# de « 88 » « bb » et de « 55 ans » « ss ». Contrôle Apple, tour 5.
RAW_TOKENS = re.compile(r"(?<![^\W_])(88|14 ?[-/]? ?88|ss|s\.s\.?|get ?27|get ?31|1664|label ?5|bet ?365)(?![^\W_])", re.IGNORECASE)
# Texte entier seulement (tour 6) : « S S », « H H ».
WHOLE_RAW = re.compile(r"\s*(s\W*s|h\W*h)\s*", re.IGNORECASE)
# « rape » (viol, anglais) lu sur le texte TEL QUEL, sans pli : « râpe », « fromage râpé », « une rape » passent.
RAPE = re.compile(r"(?<![^\W\d_])(?<!une )(?<!la )(?<!ma )(?<!ta )(?<!sa )(?<!les )(?<!des )(?<!fromage )"
                  r"rap(e|es|ed|ing|ist|ists)(?![^\W\d_])", re.IGNORECASE)
# « Crève » (tour 7, incitation au suicide) : lu sur le texte tel quel, avec son « è » (« crevé », « un pneu crevé »,
# « crevée » passent : sans accents, les deux se confondent) ; « crève de faim / de chaud… », « crève-cœur » passent.
CREVE = re.compile(r"(?<![^\W\d_])(cr[eè]vez|cr[eè]vent|crèves?)(?![^\W\d_])(?![\s-]+(de|d['’]|du|des|c(œ|oe)ur)\b)",
                   re.IGNORECASE)

# « champ' » (champagne, lot 16) : forme exacte avec son apostrophe, lue sur le texte tel quel ; « champ », « champs »,
# « champion » passent.
CHAMP = re.compile(r"(?<![^\W\d_])champ['’ʼ](?![^\W\d_])", re.IGNORECASE)


def _plain_hit(text: str) -> bool:
    """Une forme du texte (NFKC) : liste commune de l'app, argot, chiffres, lettres séparées, deux morceaux recollés."""
    # Nombres retirés avant la liste de l'app (« 55 ans » ≠ « ss ») : « 88 » et consorts sont lus par RAW_TOKENS.
    if drinky(text) or store_hit(NUMBER.sub(" ", text)) or PLAYER_RAW.search(text) or PARIS.search(text) \
            or RAW_TOKENS.search(text) or WHOLE_RAW.fullmatch(text):
        return True
    norm, pairs = _player_forms(text)
    if DRINK_RE.search(norm) or STORE_EXCLUDE.search(norm) or PLAYER_NORM.search(norm):
        return True
    # Paires recollées : les mots de PAIR_WORDS, ou un mot de STORE_ONLY d'au moins 6 lettres (« su ce » ≠ « suce ») dont
    # un morceau est un bout de mot (tour 6 : « le chat te regarde » ≠ « chatte »).
    return any(w in PAIR_WORDS or (len(w) >= 6 and any(len(x) <= 3 and x not in COMMON for x in p) and store_hit(w))
               for w, p in pairs)


# ── Contrôle Apple, tour 6 (27.11) : familles fermées PAR CONSTRUCTION, plus mot par mot ──
# 1. Pli : décomposition NFKD, accents (Mn) retirés, puis les lettres latines sans décomposition ; l'alphabet admis
#    (prénoms, réponses) n'a QUE des lettres que ce pli ramène à a-z (test : chaque caractère admis).
FOLD = {"ı": "i", "ĸ": "k", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "ħ": "h", "Ħ": "H", "ŀ": "l", "Ŀ": "L", "ŋ": "n",
        "Ŋ": "N", "þ": "th", "Þ": "Th", "ŧ": "t", "Ŧ": "T", "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae",
        "œ": "oe", "Œ": "Oe", "ß": "ss", "ẞ": "Ss", "ŉ": "n"}
_FOLD = str.maketrans(FOLD)


def fold(text: str) -> str:
    """« Vŏdka », « Hıtler », « Vođka », « Thị » → « Vodka », « Hitler », « Vodka », « Thi » (casse gardée)."""
    text = unicodedata.normalize("NFKD", str(text or "").translate(_FOLD))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


# 2. Formes DÉRIVÉES, examinées EN PLUS de la forme normale (jamais à sa place) : lettres répétées (3 fois ou plus
#    ramenées à une, puis à deux : « Vooodka », « Pompettte » ; « Shoot » reste « Shoot »), « ! » et « + » lus comme
#    lettres ENTRE deux lettres (« H!tler », « Pu+ain » ; « par ! » ne devient pas « pari »).
TRIPLE = re.compile(r"([^\W\d_])\1{2,}", re.IGNORECASE)
SIGNS = ((re.compile(r"(?<=[^\W\d_])!(?=[^\W\d_])"), "i"), (re.compile(r"(?<=[^\W\d_])\+(?=[^\W\d_])"), "t"),
         (re.compile(r"\(\)"), "o"))  # tour 8 : « V()dka », « C()ke »


def _signs(text: str) -> str:
    for rx, letter in SIGNS:
        text = rx.sub(letter, text)
    return text


def _derived(text: str) -> set[str]:
    f = fold(text)
    out = {f, _signs(f)}
    for x in list(out):
        out |= {TRIPLE.sub(r"\1", x), TRIPLE.sub(r"\1\1", x)}
    out.discard(text)
    return out


# 3. Morceaux voisins recollés (2 ou 3 : « Vo dk a », « Hi tl er », « Pas-tis ») et mot collé à un article (« Lamerde »,
#    « Unshot », « VivaHitler ») : le mot recollé doit ÊTRE un mot de la liste (égalité, jamais une sous-chaîne). Tout le
#    texte recollé (« Mer de », « Vi n ») ; au milieu d'une phrase, seulement si un morceau est un BOUT de mot (3 lettres
#    au plus, pas un petit mot courant) : « la mer de glace », « le chat te regarde », « il a pu te voir » passent.
COMMON = set("""a ai as au aux de des du d l le la les un une et en est es ou on il ils elle je j tu te t me m se s ce c
sa ta ma mon ton son ses tes mes ne n y pas pu mer ni si qui que qu sur par pour mais an go vu lu eu dit ca fin vie art
mot jeu feu eau air or mal peu va vas ont mis nez roi loi toi moi lui eux nos vos car ici lit fil mur sol bal bas dos pot
top tir rue riz sel sec net nul dur bel tel mi do re fa oh ah eh ok yo hey lol and for you my we us he she his her at up so
if be by am are was the of to in is it no oui non der die das ein und ist lo gli di da che el los las o con por jus bon
ans toi via ras bus bis duo zen ces gaz vin bar gin su nu ne ri dis fis cru tot ete fut sut put mit vit lit dut ose une"""
             .split())
ARTICLES = ("une", "un", "les", "le", "la", "du", "des", "de", "mon", "ma", "ton", "ta", "son", "sa", "cette", "cet", "ce",
            "grosse", "gros", "sale", "viva", "vive", "adolf")


def is_bad_word(w: str) -> bool:
    """Un mot seul (normalisé, a-z) de la liste de l'app : boisson, drogue, argot, STORE_ONLY ou filtre commun."""
    return bool(w in PAIR_WORDS or DRINK_RE.fullmatch(w) or store_hit(w) or PLAYER_NORM.search(w)
                or not moderation_check(w, "name").ok)


DIGITS = re.compile(r"(?<![^\W_])\d+(?![^\W_])")  # nombre seul (« par 1 et ») : jamais une lettre à recoller
MOTS = Path(__file__).resolve().parent / "static" / "brain" / "mots"  # dictionnaire de Méninges (755 000 formes, a-z)


@lru_cache(maxsize=4096)
def _mots(abc: str) -> frozenset:
    try:
        return frozenset((MOTS / f"{abc}.txt").read_text(encoding="utf-8").split())
    except (OSError, ValueError):
        return frozenset()


def french_word(w: str) -> bool:
    """Un mot du dictionnaire français (« députés », « Tamise », « décider », « épinard » : jamais un mot collé)."""
    return len(w) >= 4 and w.isalpha() and w.isascii() and w in _mots(w[:3])


# Avant de recoller : une élision (« Ana l'a dit », « Vi n'a ») et une initiale en majuscule après un prénom (« Ana L »,
# « Vi N. ») ne sont jamais un bout de mot ; « Vi n » (minuscule) se recolle toujours.
ELISION = re.compile(r"(?<![^\W\d_])([^\W\d_]|qu)['’]", re.IGNORECASE)
INITIAL = re.compile(r"(?<=[^\W\d_]{2}) +[A-Z]\.?(?= |$)")


def _words(text: str) -> list[str]:
    return merged(normalize(nfkc(DIGITS.sub(" ", INITIAL.sub(" ", ELISION.sub(" ", text)))))).split()


def _joined_hit(text: str) -> bool:
    words = _words(text)
    if 2 <= len(words) <= 4 and len("".join(words)) >= 3 and is_bad_word("".join(words)):
        return True  # tout le texte recollé (« Mer de », « Co ke », « Hit-l-er »)
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            part = words[i:i + n]
            w = "".join(part)
            if len(w) >= 4 and any(len(x) <= 3 and x not in COMMON for x in part) and is_bad_word(w):
                return True
    return False


# Mots de DRINK_RE qui sont aussi des mots ordinaires : jamais lus collés à un article (« Desbois », « Leverre »).
HOMONYMS = {"bois", "boit", "verre", "verres", "tournee", "tournees", "cuite", "cuites", "bars", "vins", "arrose", "cuvee",
            "porto", "malt"}


def _article_hit(text: str) -> bool:
    for word in re.split("[^a-z]+", normalize(nfkc(text))):
        for a in ARTICLES:
            rest = word[len(a):]
            if word.startswith(a) and len(rest) >= 4 and rest not in HOMONYMS and not french_word(word) and is_bad_word(rest):
                return True
    return False


# Phrases ordinaires qui contiennent un mot de DRINK_RE (textes des joueurs seulement : DRINK_RE reste celui des banques
# et des événements) : « un verre d'eau », « un crack en maths », « j'habite à Bordeaux ».
# Tour 7 : verre / bouteille de lait, de jus, d'eau… ; « en Bourgogne » ; « le Casino de Montreux » (salle de concert).
PLAYER_SAFE = re.compile(r"\b(verres?|bouteilles?) (d['’ ]?eau(?![\s-]*de[\s-]*vie)|de (lait|jus|sirop|soda|limonade|grenadine"
                         r"|th[ée]|caf[ée]|coca(?![iï]ne)|chocolat)\b)|\b(un|le|ce|quel|vrai|petit) crack (en|de|du|au|aux)\b"
                         r"|\b(à|a|en|vers|depuis|pr[èe]s de|(viens|vient|venu|venue|originaire|n[ée]e?) de) (bordeaux|bourgogne)\b"
                         r"|\bcasino de montreux\b"
                         # Tour 8 (27.11) : boire de l'eau, du café… ; « sans alcool », « non à la drogue », « je déteste la
                         # cigarette » ; le trou noir de l'espace ; Porto-Novo (capitale du Bénin). Seule la phrase sûre est
                         # retirée : « une bière sans alcool », « je bois de l'eau et de la vodka » restent refusées.
                         r"|\b(bu|bois|boit|boivent|boire|buvons|buvez)(\s+trop)?\s+(de\s+l['’]\s*|de\s+la\s+|de\s+|du\s+"
                         r"|d['’]\s*|un\s+|une\s+|des\s+|le\s+|la\s+|l['’]\s*)?(eau(?![\s-]*de[\s-]*vie)|caf[ée]|th[ée]|jus"
                         r"|lait|soda|sirop|limonade|chocolat|tisane)\b"
                         r"|(?<!pas de )(?<!jamais de )(?<!aucune )\b(?:(?:une|la|ma|ta|notre|cette)\s+)?(?:soir[ée]e|f[êe]te|journ[ée]e"
                         r"|semaine|vie|boisson)\s+sans\s+alcool\b|(?<!pas )(?<!jamais )\bz[ée]ro\s+alcool\b|\bnon\s+[àa]\s+la\s+drogue\b|\ble\s+tabac\s+tue\b"
                         r"|\bd[ée]teste\s+(la\s+cigarette|les\s+cigarettes|le\s+tabac)\b"
                         r"|\btrou\s+noir\s+(dans\s+l['’]\s*espace|de\s+l['’]\s*univers|supermassif|galactique)"
                         r"|\bporto[\s-]+novo\b",
                         re.IGNORECASE)
# Noms de famille qui contiennent un mot de DRINK_RE (prénoms et noms des joueurs seulement, tour 7) : Brasseur, Escobar
# (jamais « Pablo Escobar »), Kirschner, Perdrix, Tchindjang.
NAME_SAFE = re.compile(r"\b(brasseurs?|escobar|kirschner|perdrix|tchindjang|porto[\s-]+novo)\b", re.IGNORECASE)
# Tour 8 : « Bordeaux », « Cointreau » (noms de famille) seulement comme nom entier ou « Prénom Nom » ; jamais « Le
# Bordeaux », « Team Cointreau », « Bordeaux rouge » (le prénom devant passe le filtre lui-même).
FAMILY_NAME = re.compile(r"\s*(?:([^\W\d_][\w'’-]*)\s+)?(bordeaux|cointreau)\s*", re.IGNORECASE)
NOT_FIRST_NAMES = {"team", "vin", "rouge", "blanc", "verre", "shot", "fan", "club", "grand", "cru", "petit", "gros", "mister",
                   "monsieur", "madame", "miss", "king", "queen", "roi", "reine", "chateau", "château"}


PABLO_ESCOBAR = re.compile(r"pablo[^a-z]*escobar|escobar[^a-z]*pablo")


def name_safe(name) -> str:
    """Le prénom sans ses noms de famille sûrs (NAME_SAFE, FAMILY_NAME) : le reste passe le filtre."""
    text = str(name or "")
    # « Pablo Escobar » (le trafiquant), quelle que soit l'espace ou l'ordre : jamais un nom sûr.
    if not PABLO_ESCOBAR.search(normalize(nfkc(text))):
        text = NAME_SAFE.sub(" ", text)
    m = FAMILY_NAME.fullmatch(text)
    if m and (not m.group(1) or m.group(1).lower() not in COMMON | NOT_FIRST_NAMES):
        return m.group(1) or " "
    return text


@lru_cache(maxsize=8192)
def player_offensive(text) -> bool:
    """Texte d'un joueur refusé dans une partie de l'app : liste commune de l'app (offensive) et argot, contournements
    compris (formes NFKC, sosies cyrillique / grec, accents hors table, chiffres, signes, lettres séparées ou répétées,
    morceaux recollés, mot collé à un article)."""
    text = PLAYER_SAFE.sub(" ", nfkc(moderation_clean(str(text or ""))))
    if RAPE.search(text) or CREVE.search(text) or CHAMP.search(text) or _plain_hit(text):
        return True
    base_ok = moderation_check(text, "name").ok  # insulte d'une réponse masquée ailleurs : seulement si une forme la révèle
    for form in _derived(text):
        if _plain_hit(form) or (base_ok and not moderation_check(form, "name").ok):
            return True
    # Lettre doublée en fin de mot (« Shotss », « Cannabiss ») : le mot sans elle, s'il fait 4 lettres ou plus (« Barr »,
    # « Ginn » passent) ; jamais au milieu (« Shoot », « Cooke » restent).
    forms = {fold(text), _signs(fold(text))}
    if any(len(w) >= 5 and w[-1] == w[-2] and not french_word(w) and is_bad_word(w[:-1]) for x in forms for w in _words(x)):
        return True
    return any(_joined_hit(x) or _article_hit(x) for x in forms)


# Alphabet des textes de joueurs de l'app (contrôle Apple, tour 5 : CHANGER DE MÉTHODE, liste blanche plutôt que liste
# noire) : après NFKC, lettres latines (accents français et européens compris), chiffres, espace, trait d'union,
# apostrophe (' et ’). Tout le reste (cyrillique, grec, symboles, emoji) est refusé. Réponses : plus la ponctuation courante.
# Tour 6 : seulement les lettres que le pli (fold, puis normalize) ramène au latin simple a-z, prises dans le latin de
# base, Latin-1, Latin étendu A, Ș-ț et le Latin étendu additionnel (U+1E00–1EFF : Thị, Đức, Ngọc) ; une lettre que le pli
# ne ramène pas à a-z (ẜ, ỻ…) n'est pas admise. Test : chaque caractère admis.
LETTERS = "".join(c for c in map(chr, [*range(0x41, 0x7B), *range(0xC0, 0x180), *range(0x218, 0x21C), *range(0x1E00, 0x1F00)])
                  if c.isalpha() and re.fullmatch("[a-z]+", normalize(fold(c).lower())))
LATIN = "A-Za-z" + "".join(c for c in LETTERS if not c.isascii())
NAME_MAX = 30
NAME_CHARS = re.compile(rf"[{LATIN}0-9 '’-]{{1,{NAME_MAX}}}")
ANSWER_CHARS = re.compile(rf"[{LATIN}0-9 '’\-.,;:!?\"«»()…–—%/&+°\n]*")
HAS_LETTER = re.compile(rf"[{LATIN}0-9]")
NAME_REFUSED = "Ce prénom n'est pas accepté dans les jeux : choisis-en un autre."
NAME_CHARS_REFUSED = "Ce prénom n'est pas accepté ici : lettres, chiffres, espace, trait d'union et apostrophe seulement."
ANSWER_CHARS_REFUSED = "Ce texte n'est pas accepté ici : lettres, chiffres et ponctuation courante seulement (ni emoji ni symbole)."


def name_chars_ok(name) -> bool:
    """Prénom d'un joueur de l'app : seulement l'alphabet des prénoms (après NFKC), 30 signes au plus."""
    name = nfkc(moderation_clean(str(name or ""))).strip()
    return bool(NAME_CHARS.fullmatch(name) and HAS_LETTER.search(name))


# Prénoms de l'app : un mot de la liste COLLÉ à un autre (« Zoépicoler », recette iPhone du 28.11) est aussi refusé. Lu
# dans chaque mot du prénom normalisé ; seulement des mots assez longs et sans double sens dans un prénom
# (jamais « nazi », « shit », « chatte » : Nazim, Shitaké, Matchatte restent acceptés).
GLUED = ("picol", "trinqu", "pompette", "biture", "pinard", "defonc", "saoul", "vodka", "whisk", "tequila", "hitler",
         "cocaine", "cannabis", "ganja", "ketamin", "pochtron", "ivrogne", "poivrot", "smirnof", "schnaps", "kronenbourg",
         "desperados", "baileys", "jackdaniel", "jackpot", "winamax", "betclic", "tierce", "violeur", "inceste", "trisomique",
         "pedophil", "salope", "connard", "encule", "putain", "merdeux", "marijuana", "heroine", "codeine", "poppers",
         "alcool", "biere", "gorgee", "cocktail", "champagne", "mojito", "pastis", "casino", "poker", "blackjack",
         "pompett", "beuverie", "suicid", "terroris", "daech", "daesh", "staline", "bougnoul", "pedo", "porno")


# Réponses (tour 6 : « VivaHitler ») : les mêmes, sauf ceux qu'un mot ordinaire contient (« la tierce personne »,
# « torpédo », « pédologue »).
GLUED_ANSWER = tuple(w for w in GLUED if w not in ("tierce", "pedo"))


def glued_hit(name, glued=GLUED) -> bool:
    """Prénom (GLUED) ou réponse (GLUED_ANSWER : un mot du dictionnaire n'est jamais un mot collé, « épinard »,
    « terrorisait » passent ; le mot lui-même est lu par player_offensive)."""
    text = nfkc(moderation_clean(str(name or "")))
    return any(w in word and (glued is GLUED or not french_word(word)) for t in {text, fold(text), _signs(fold(text))}
               for word in re.split("[^a-z]+", normalize(t)) for w in glued)  # mot par mot (« mal à la gorge » passe)


def answer_chars_ok(text) -> bool:
    return bool(ANSWER_CHARS.fullmatch(nfkc(moderation_clean(str(text or "")))))


def check_text(text, store: bool, kind: str = "answer"):
    """Texte libre d'un joueur montré à la table d'une partie de l'app : alphabet des prénoms (« name ») ou des réponses,
    jamais de boisson, de drogue ni de mot de STORE_ONLY, argot compris (ValueError)."""
    if not store:
        return
    if kind == "name" and not name_chars_ok(text):
        raise ValueError(NAME_CHARS_REFUSED)
    if kind == "name" and (glued_hit(name_safe(text)) or player_offensive(name_safe(text))):
        raise ValueError(NAME_REFUSED)
    if kind != "name" and not answer_chars_ok(text):
        raise ValueError(ANSWER_CHARS_REFUSED)
    if kind != "name" and (player_offensive(text) or glued_hit(text, GLUED_ANSWER)):
        raise ValueError(TEXT_REFUSED)


@lru_cache(maxsize=8192)
def name_refused(name) -> bool:
    """Prénom jamais montré dans une partie de l'app : hors de l'alphabet des prénoms, refusé par l'app
    (player_offensive) ou par le filtre commun (un prénom du web hors de l'alphabet devient « Joueur N »)."""
    return isinstance(name, str) and bool(name) and (
        not name_chars_ok(name) or glued_hit(name_safe(name)) or player_offensive(name_safe(name))
        or not moderation_check(name, "name").ok)


ALIAS = "Joueur"


ID_KEYS = ("id", "gid", "pid", "host", "code", "room", "current", "store_alias", "aliases", "leads", "kicked", "removed")


# Champs qui portent un prénom (copies comprises : historiques, auteurs, journaux, annonces) : seuls réécrits, jamais
# type, phase, mots, options, questions (un joueur « room », « likely » ou « lobby » signalé cassait la partie).
NAME_KEYS = ("name", "host_name", "by", "author", "winners", "names", "rnames", "history", "log", "notice")


def _replace(o, old, new: str, named: bool = False):
    """Toutes les copies d'un prénom dans les champs qui en portent (NAME_KEYS) : la valeur exacte, ou le mot entier
    dans une phrase (« Hitler a gagné » ; « Paris » reste si « Pari » est renommé) ; jamais un identifiant. `old` :
    le prénom, et le motif du mot entier."""
    name, word = old
    if isinstance(o, str):
        return o if not named else new if o == name else word.sub(new, o) if " " in o and name in o else o
    if isinstance(o, dict):
        game = "type" in o  # partie, jeu de l'historique de la salle, catalogue : « name » = titre du jeu
        for k, x in o.items():
            if k not in ID_KEYS:
                hit = (named and isinstance(x, str)) or (k in NAME_KEYS and not (k == "name" and game)) \
                    or (k == "winner" and game and "phase" not in o)  # gagnant de l'historique, jamais le rôle gagnant
                o[k] = _replace(x, old, new, hit)
        return o
    if isinstance(o, list):
        for i, x in enumerate(o):
            o[i] = _replace(x, old, new, named and not isinstance(x, dict))  # entrée d'historique : ses propres clés
    return o


def scrub_names(g: dict, peers=()) -> bool:
    """Partie touchée par l'app App Store : tout prénom refusé (insulte, haine, drogue, boisson, argot) devient
    « Joueur 1 », « Joueur 2 »… DANS la partie (stable par joueur, même numéro dans la salle et son jeu), copies
    comprises : rien ne reste à masquer à l'affichage. True si un prénom a changé."""
    if not isinstance(g, dict):
        return False
    peers = [x for x in peers if isinstance(x, dict)]
    seats = [(p, p.get("id")) for p in g.get("players", []) if isinstance(p, dict)]
    if g.get("host_name") and not any(i == g.get("host") for _, i in seats):
        seats.append((None, g.get("host")))  # animateur qui ne joue pas : seul son host_name porte le prénom
    bad = [(p, i) for p, i in seats if name_refused(p["name"] if p else g.get("host_name"))]
    if not bad:
        return False
    aliases = g.setdefault("store_alias", {})
    taken = {p.get("name") for x in [g, *peers] for p in x.get("players", []) if isinstance(p, dict)}
    taken |= {a for x in [g, *peers] for a in (x.get("store_alias") or {}).values()}
    copies = {}  # prénom refusé → alias de sa première place (homonymes : chacun son numéro, copies au premier)
    for p, gid in bad:
        old = p["name"] if p else g["host_name"]
        alias = aliases.get(gid) or next((x["store_alias"][gid] for x in peers if gid in (x.get("store_alias") or {})), None)
        if not alias:
            n = 1
            while f"{ALIAS} {n}" in taken:
                n += 1
            alias = f"{ALIAS} {n}"
        aliases[gid] = alias
        taken.add(alias)
        copies.setdefault(old, alias)
        if p:
            p["name"] = alias
        if g.get("host") == gid:
            g["host_name"] = alias
    for old, alias in copies.items():
        _replace(g, (old, re.compile(r"(?<![^\W\d_])" + re.escape(old) + r"(?![^\W\d_])")), alias)
    return True


def bank_only(g: dict) -> bool:
    """Pour ou contre d'une partie de l'app : seulement les dilemmes de la banque, aucun dilemme proposé."""
    return bool(g.get("store"))


def clean(pool: list, text=lambda x: x) -> list:
    """La banque sans boisson ni drogue (jamais vide : les banques en ont des centaines)."""
    return [x for x in pool if not drinky(text(x))] or pool


# Autres plateformes mobiles (Apple 2.3.10) : jamais dans une question tirée dans l'app (Quiz › Informatique & IA).
OTHER_PLATFORM_RE = re.compile(r"android|\.apk\b|google play|play store|windows phone|harmonyos|blackberry|samsung|huawei|xiaomi|nokia", re.IGNORECASE)


def clean_platforms(pool: list, text=lambda x: x) -> list:
    return [x for x in pool if not OTHER_PLATFORM_RE.search(text(x))] or pool


def flag(g: dict):
    """Partie de l'app App Store : aucune gorgée (ni « mode points » qui les remplacerait), aucun mode Hot / Mix, aucun
    thème ou paquet caché ; questions filtrées (les modules qui ne voient que leur état le lisent)."""
    g["store"] = True
    g["options"]["sips"] = 0
    g["options"]["alcohol"] = False
    if g["options"].get("mode") in HIDDEN_MODES:
        g["options"]["mode"] = "soft"
    for key in ("likely", "debate", "quiz"):
        if isinstance(g.get(key), dict):
            g[key]["store"] = True
    d = g.get("debate")
    if isinstance(d, dict):  # dilemmes proposés sur le web avant l'arrivée de l'app : la banque seule (bank_only)
        for k in ("queue", "proposals"):
            if isinstance(d.get(k), list):
                d[k] = [x for x in d[k] if isinstance(x, dict) and x.get("by") is None and not player_offensive(x.get("text"))]
        if isinstance(d.get("history"), list):
            d["history"] = [x for x in d["history"] if not (isinstance(x, dict) and player_offensive(x.get("text")))]
    if isinstance(g.get("debate"), dict) and isinstance(g["debate"].get("themes"), list):
        g["debate"]["themes"] = [t for t in g["debate"]["themes"] if t not in HIDDEN_THEMES] or ["light"]
    if isinstance(g.get("likely"), dict) and isinstance(g["likely"].get("packs"), list):
        g["likely"]["packs"] = [p for p in g["likely"]["packs"] if p not in HIDDEN_PACKS] or ["family"]
    scrub_names(g)


def refused_settings(g: dict, settings) -> bool:
    """Réglage refusé dans une partie de l'app : des gorgées, un thème ou un paquet caché."""
    if not g.get("store") or not isinstance(settings, dict):
        return False
    if settings.get("sips") or settings.get("alcohol"):
        return True
    themes, packs = settings.get("themes"), settings.get("packs")
    return (isinstance(themes, list) and any(t in HIDDEN_THEMES for t in themes)) or \
        (isinstance(packs, list) and any(p in HIDDEN_PACKS for p in packs))


def refused(g: dict) -> bool:
    """L'app App Store ne voit pas cette partie (jeu caché, gorgées du web, mode Hot, texte tiré sans filtre)."""
    if g["type"] in HIDDEN_GAMES or (g.get("options") or {}).get("sips"):
        return True  # une partie « store » n'a jamais de gorgées (flag) : des gorgées = une partie du web
    if g["options"].get("mode") in HIDDEN_MODES:
        return True
    if g["type"] == "debate" and any(t in HIDDEN_THEMES for t in (g.get("debate") or {}).get("themes", [])) \
            and g.get("phase") != "lobby":
        return True
    if g["type"] == "likely" and any(p in HIDDEN_PACKS for p in (g.get("likely") or {}).get("packs", [])) \
            and g.get("phase") != "lobby":
        return True
    return g["type"] in BANK_GAMES and not g.get("store") and g.get("phase") != "lobby"


DRINK_EMOJIS = ("🍻", "🍷")  # emojis de groupe de la liste fermée (member_groups.emoji) : 🎉 dans l'app App Store


def neutral_emojis(data):
    """Réponse des discussions pour l'app App Store : l'emoji 🍻 / 🍷 d'un groupe (clé « emoji ») devient 🎉."""
    if isinstance(data, dict):
        return {k: ("🎉" if k == "emoji" and v in DRINK_EMOJIS else neutral_emojis(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [neutral_emojis(x) for x in data]
    return data
