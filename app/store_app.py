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
from functools import lru_cache

from .features import is_test_site
from .moderation import check as moderation_check, clean as moderation_clean, merged, normalize, store_hit

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
    r"|happy hour|after-?work|\bpintes?\b|oktoberfest|ti-?punch|binouze|pub crawl|margarita|\bshooters?\b|ricard"
    r"|heineken|chicha|narguil[ée]|\bvapot|\bvape\b|\bpuffs?\b|\bj[äa]ger\b|\bpils\b|\bipa\b|verknipt|asbak"
    r"|🍻|🍺|🥃|🍸|🍹|🍷|🍾|🥂",
    re.IGNORECASE)
# Phrases qui supposent l'ivresse sans aucun mot de la liste (relues le 25.11) : jamais tirées dans l'app.
STORE_EXCLUDE = re.compile(
    r"sans savoir comment j['’]y étais arrivé|dormi dans ma voiture après une soirée|oublié avec qui j['’]étais venu"
    r"|oublier comment il est rentré|se réveiller chez quelqu['’]un d['’]autre|organiser l['’]after|la veille d['’]un examen"
    r"|plus jamais.{0,20}recommencer|dont tu ne te souviens plus du prénom|soirée légendaire|lendemain de soirée|lendemain d['’]une f[êe]te"
    r"|sans se souvenir|trou noir|black-?out|si (?:tu étais|c['’]était) une boisson",
    re.IGNORECASE)


def is_store(request) -> bool:
    """L'app App Store : « PartyStore » dans l'User-Agent (vue web). En production, tout client iOS natif aussi : les
    écrans natifs n'envoient que « X-Party-Native: ios » (PartyAPI.swift), et la BETA parle au site de test, jamais à
    la prod (ios/project.yml, workflow TestFlight) ; le site de test garde la BETA telle quelle."""
    if request is None:
        return False
    ua = request.headers.get("user-agent", "")
    if MARK in ua:
        return True
    return request.headers.get("x-party-native") == "ios" and not is_test_site()


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
    r"|cul[ ]sec|rouler un pet\w*|de la c)( |$)"
    # « mise » / « mises » (enjeu) : refusé, sauf « mise à jour », « mise en place », « mise au point »…
    r"|(^| )mises?( |$)(?!(a|au|aux|en|bas|hors|jour|sur pied)( |$))")


NUMBER = re.compile(r"(?<![^\W\d_])\d{2,}(?![^\W\d_])")  # « 30 ans », « 5 à 7 » : un nombre reste un nombre
# Mots qu'on retrouve en recollant deux morceaux (« vod ka », « hit ler ») ; jamais toute la liste des boissons : deux
# mots ordinaires recollés en formeraient (« mal t'aime » → « malt »).
PAIR_WORDS = {"vodka", "whisky", "whiskey", "biere", "bieres", "alcool", "tequila", "cocaine", "cannabis", "hitler",
              "nazi", "nazis", "shots", "rhum", "picole", "picoler", "pompette", "saoul", "parier", "miser"}


def _player_forms(text: str) -> tuple[str, list[str]]:
    """Le texte normalisé (chiffres dans un mot ramenés aux lettres, lettres séparées recollées), et chaque paire de
    mots voisins recollée (« hit ler » → « hitler »)."""
    norm = merged(normalize(moderation_clean(NUMBER.sub(" ", text))))
    words = norm.split()
    return norm, ["".join(p) for p in zip(words, words[1:])]


@lru_cache(maxsize=8192)
def player_offensive(text) -> bool:
    """Texte d'un joueur refusé dans une partie de l'app : liste commune de l'app (offensive) et argot, contournements
    compris (chiffres, lettres séparées, mot coupé en deux)."""
    text = str(text or "")
    if offensive(text) or PLAYER_RAW.search(text) or PARIS.search(text):
        return True
    norm, pairs = _player_forms(text)
    if DRINK_RE.search(norm) or STORE_EXCLUDE.search(norm) or PLAYER_NORM.search(norm):
        return True
    return any(w in PAIR_WORDS or store_hit(w) for w in pairs)


def check_text(text, store: bool):
    """Texte libre d'un joueur montré à la table d'une partie de l'app : jamais de boisson, de drogue ni de mot de
    STORE_ONLY, argot compris (ValueError)."""
    if store and player_offensive(text):
        raise ValueError(TEXT_REFUSED)


@lru_cache(maxsize=8192)
def name_refused(name) -> bool:
    """Prénom jamais montré dans une partie de l'app : refusé par l'app (player_offensive) ou par le filtre commun."""
    return isinstance(name, str) and bool(name) and (player_offensive(name) or not moderation_check(name, "name").ok)


ALIAS = "Joueur"


ID_KEYS = ("id", "gid", "pid", "host", "code", "room", "current", "store_alias", "aliases", "leads", "kicked", "removed")


def _replace(o, old, new: str):
    """Toutes les copies d'un prénom dans la partie (historiques, auteurs, classements, trames, journaux) : la valeur
    exacte, ou le mot entier dans une phrase (« Hitler a gagné » ; « Paris » reste si « Pari » est renommé) ; jamais un
    identifiant. `old` : le prénom, et le motif du mot entier."""
    name, word = old
    if isinstance(o, str):
        return new if o == name else word.sub(new, o) if " " in o and name in o else o
    if isinstance(o, dict):
        for k, x in o.items():
            if k not in ID_KEYS:
                o[k] = _replace(x, old, new)
        return o
    if isinstance(o, list):
        for i, x in enumerate(o):
            o[i] = _replace(x, old, new)
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
OTHER_PLATFORM_RE = re.compile(r"android|\.apk\b|google play|play store|windows phone|harmonyos", re.IGNORECASE)


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
