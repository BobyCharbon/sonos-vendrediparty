"""Drapeaux (avis 544a8fd8b5bd) : « À quel pays appartient ce drapeau ? » et « Quel est le drapeau de… ? ».

Le drapeau est un emoji (paire d'indicateurs régionaux ISO 3166), affiché en grand par le Quiz (téléphone :
.qz-flag, Apple TV : QuizTV). Choix de l'emoji plutôt que d'images : net à toute taille sur iPhone, Android, Mac et
Apple TV, sans fichiers à servir ni à tenir à jour (Windows seul l'affiche en lettres « FR », voir le rapport).

Les mauvaises réponses viennent d'abord des drapeaux qui se ressemblent (LOOKALIKES : Irlande / Côte d'Ivoire,
Indonésie / Pologne, croix nordiques, Union Jack étoilés…), puis du même continent. Deux drapeaux identiques
une fois réduits en emoji (TWINS : Tchad / Roumanie, Indonésie / Monaco) ne sont jamais proposés ensemble :
la question serait un pile ou face.

Difficulté : 1 drapeaux très connus, 2 les autres, 3 les tout petits pays (moins d'un million d'habitants) et les
drapeaux rares (RARE) ; un cran de plus quand les trois autres propositions sont des sosies.
"""

import random

from . import make, pick
from .fr import bare, de, flag
from .gen_geo import AM, AS, COUNTRIES, EU, OC

THEME = "drapeaux"

# Pays absents de la table de géographie (sans capitale ni monnaie utiles ici), pour compléter les drapeaux.
# (code ISO, nom avec article, continent, population en millions)
EXTRA = [
    ("VA", "le Vatican", EU, 0.001),
    ("PW", "les Palaos", OC, 0.018),
    ("KI", "les Kiribati", OC, 0.13),
    ("MH", "les Îles Marshall", OC, 0.04),
    ("FM", "la Micronésie", OC, 0.11),
    ("NR", "Nauru", OC, 0.012),
    ("TV", "les Tuvalu", OC, 0.011),
    ("AG", "Antigua-et-Barbuda", AM, 0.09),
    ("DM", "la Dominique", AM, 0.07),
    ("GD", "la Grenade", AM, 0.12),
    ("KN", "Saint-Christophe-et-Niévès", AM, 0.05),
    ("LC", "Sainte-Lucie", AM, 0.18),
    ("VC", "Saint-Vincent-et-les-Grenadines", AM, 0.1),
]

# Drapeaux que presque tout le monde reconnaît.
EASY = set("FR DE IT ES PT GB BE CH AT GR US CA MX BR AR JP CN KR IN AU TR DK SE NO FI PL ZA IL JM SA NL IE RU UA NZ CU CL CO "
           "MA EG VN NP LB CY HR KE".split())
# Drapeaux rarement vus, même de pays peuplés.
RARE = set("TM TJ KG UZ BT LK LA KH MM BN TL ER DJ SO SS BI CF GQ GW BF TG BJ ST CV KM SC MU SZ LS MW ZM MZ AO NA BW "
           "GY SR BZ TT BB BS PG SB VU WS TO FJ MN AZ AM GE BY MD MK BA ME AL".split())

# Familles de drapeaux qui se ressemblent (mêmes couleurs, même disposition).
LOOKALIKES = [
    "IE CI IT MX",            # tricolores verticaux vert-blanc-orange/rouge
    "TD RO AD MD",            # bleu-jaune-rouge verticaux
    "ID MC PL SG",            # rouge et blanc
    "NL LU HR PY",            # rouge-blanc-bleu horizontal
    "RU SK SI RS",            # tricolores panslaves
    "AU NZ FJ TV",            # Union Jack et étoiles
    "NO IS DK FI SE",         # croix nordiques
    "SN ML GN CM",            # vert-jaune-rouge verticaux
    "GH BO LT ET",            # rouge-jaune-vert horizontaux
    "CO EC VE",               # jaune-bleu-rouge
    "HN NI SV GT",            # bleu-blanc-bleu d'Amérique centrale
    "AR UY GR",               # bleu ciel et blanc
    "US LR MY",               # bandes et canton étoilé
    "QA BH",                  # blanc et dents de scie
    "AE KW JO SD",            # couleurs panarabes avec triangle ou bande
    "EG SY IQ YE",            # rouge-blanc-noir
    "DE BE",                  # noir-jaune-rouge (ou noir-or-rouge)
    "AT LV",                  # rouge-blanc-rouge
    "PE CA",                  # rouge-blanc-rouge vertical
    "HU BG IR TJ",            # tricolores rouge-blanc-vert
    "JP BD PW",               # disque sur fond uni
    "TH CR",                  # bandes rouge-blanc-bleu-blanc-rouge
    "CN VN",                  # étoile jaune sur rouge
    "TR TN",                  # croissant et étoile sur rouge
    "NE IN",                  # orange-blanc-vert
    "PK DZ",                  # vert, blanc, croissant
    "SL GA",                  # bandes horizontales vert-…-bleu
    "HT LI",                  # bleu et rouge horizontaux à emblème
    "CZ PH",                  # triangle bleu, blanc et rouge
    "CL CU",                  # étoile blanche, rouge-blanc-bleu
    "KE MW SS",               # noir-rouge-vert
    "AL ME",                  # aigle bicéphale sur rouge
    "MK KG",                  # soleil sur rouge
    "LC KN VC GD DM AG",      # Petites Antilles
    "MH FM NR KI",            # Micronésie, étoiles sur bleu
]
# Identiques une fois réduits en emoji : jamais proposés dans la même question.
TWINS = [{"TD", "RO"}, {"ID", "MC"}]

Country = tuple[str, str, str | None, float]  # (iso, nom, continent, population)


def countries() -> list[Country]:
    base = [(c[0], c[1], c[3], c[5]) for c in COUNTRIES]
    return base + [c for c in EXTRA if c[0] not in {b[0] for b in base}]


# Pays à cheval sur deux continents (continent None dans la géographie) : rangés là où leurs voisins de drapeau sont.
REGION = {"KZ": AS}


def _region(c: Country) -> str:
    """Continent pour les choix proches ; la Russie, la Turquie, Chypre et le Caucase vont avec l'Europe."""
    return c[2] or REGION.get(c[0], EU)


def lookalikes(iso: str) -> list[str]:
    seen: list[str] = []
    for family in LOOKALIKES:
        codes = family.split()
        if iso in codes:
            seen += [x for x in codes if x != iso and x not in seen]
    return seen


def _twins(a: str, b: str) -> bool:
    return {a, b} in TWINS


def wrong_codes(c: Country, by_iso: dict[str, Country], seed: str) -> list[str]:
    """3 drapeaux à proposer à côté du bon : sosies d'abord (sans jumeau), puis même continent, toujours les mêmes."""
    iso = c[0]
    rng = random.Random(seed)
    similar = [x for x in lookalikes(iso) if x in by_iso and not _twins(iso, x)]
    rng.shuffle(similar)
    chosen: list[str] = []
    for x in similar:
        if len(chosen) < 3 and not any(_twins(x, y) for y in chosen):
            chosen.append(x)
    same = [x[0] for x in by_iso.values() if _region(x) == _region(c) and x[0] != iso]
    for x in pick(seed + "-fill", same, iso, n=len(same)):
        if len(chosen) == 3:
            break
        if x not in chosen and not _twins(iso, x) and not any(_twins(x, y) for y in chosen):
            chosen.append(x)
    return chosen


def level(c: Country, wrong: list[str]) -> int:
    iso, _, _, pop = c
    base = 1 if iso in EASY else 3 if iso in RARE or pop < 1 else 2
    close = sum(1 for x in wrong if x in lookalikes(iso))
    return min(3, base + 1) if close >= 3 else base


def generate() -> list[dict]:
    items = countries()
    by_iso = {c[0]: c for c in items}
    out = []
    for c in items:
        iso, name = c[0], c[1]
        wrong = wrong_codes(c, by_iso, f"drapeau-{iso}")
        d = level(c, wrong)
        out.append(make(THEME, f"À quel pays appartient ce drapeau ? {flag(iso)}", bare(name), [bare(by_iso[x][1]) for x in wrong], d))
        wrong_r = wrong_codes(c, by_iso, f"drapeau-r-{iso}")
        out.append(make(THEME, f"Quel est le drapeau {de(name)} ?", flag(iso), [flag(x) for x in wrong_r], level(c, wrong_r)))
    return out

