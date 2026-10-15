"""Suisse : cantons (chef-lieu, abréviation, langues, entrée dans la Confédération, population, superficie),
localités → canton, sommets."""

import random

from . import make, pick
from .fr import de
from .gen_geo import _comparisons

# Avec l'article : canton du Tessin, des Grisons, d'Argovie…
ARTICLE = {'Tessin': 'le Tessin', 'Valais': 'le Valais', 'Grisons': 'les Grisons', 'Jura': 'le Jura'}

# (abréviation, nom, chef-lieu, langues officielles, année d'entrée, habitants en milliers, superficie en km²)
CANTONS = [
    ("ZH", "Zurich", "Zurich", "allemand", 1351, 1580, 1729),
    ("BE", "Berne", "Berne", "allemand et français", 1353, 1060, 5959),
    ("LU", "Lucerne", "Lucerne", "allemand", 1332, 425, 1493),
    ("UR", "Uri", "Altdorf", "allemand", 1291, 37, 1077),
    ("SZ", "Schwytz", "Schwytz", "allemand", 1291, 166, 908),
    ("OW", "Obwald", "Sarnen", "allemand", 1291, 38.6, 491),
    ("NW", "Nidwald", "Stans", "allemand", 1291, 44, 276),
    ("GL", "Glaris", "Glaris", "allemand", 1352, 41.5, 685),
    ("ZG", "Zoug", "Zoug", "allemand", 1352, 131, 239),
    ("FR", "Fribourg", "Fribourg", "français et allemand", 1481, 335, 1671),
    ("SO", "Soleure", "Soleure", "allemand", 1481, 282, 790),
    ("BS", "Bâle-Ville", "Bâle", "allemand", 1501, 196, 37),
    ("BL", "Bâle-Campagne", "Liestal", "allemand", 1501, 295, 518),
    ("SH", "Schaffhouse", "Schaffhouse", "allemand", 1501, 85, 298),
    ("AR", "Appenzell Rhodes-Extérieures", "Herisau", "allemand", 1513, 56, 243),
    ("AI", "Appenzell Rhodes-Intérieures", "Appenzell", "allemand", 1513, 16.5, 173),
    ("SG", "Saint-Gall", "Saint-Gall", "allemand", 1803, 525, 2031),
    ("GR", "Grisons", "Coire", "allemand, romanche et italien", 1803, 203, 7105),
    ("AG", "Argovie", "Aarau", "allemand", 1803, 709, 1404),
    ("TG", "Thurgovie", "Frauenfeld", "allemand", 1803, 290, 992),
    ("TI", "Tessin", "Bellinzone", "italien", 1803, 355, 2812),
    ("VD", "Vaud", "Lausanne", "français", 1803, 830, 3212),
    ("VS", "Valais", "Sion", "français et allemand", 1815, 357, 5224),
    ("NE", "Neuchâtel", "Neuchâtel", "français", 1815, 177, 802),
    ("GE", "Genève", "Genève", "français", 1815, 515, 282),
    ("JU", "Jura", "Delémont", "français", 1979, 74, 839),
]
EASY = {"ZH", "BE", "VD", "GE", "VS", "TI", "FR", "NE", "JU", "BS", "LU", "GR"}

# Localité → canton (abréviation)
TOWNS = [
    # Vaud
    ("Montreux", "VD"), ("Vevey", "VD"), ("Nyon", "VD"), ("Morges", "VD"), ("Yverdon-les-Bains", "VD"), ("Renens", "VD"), ("Pully", "VD"),
    ("Aigle", "VD"), ("Payerne", "VD"), ("Gland", "VD"), ("Rolle", "VD"), ("Prilly", "VD"), ("Bex", "VD"), ("Château-d'Œx", "VD"),
    ("Le Sentier", "VD"), ("Sainte-Croix", "VD"), ("Orbe", "VD"), ("Moudon", "VD"), ("Lutry", "VD"), ("Leysin", "VD"), ("Villars-sur-Ollon", "VD"),
    ("Coppet", "VD"), ("Avenches", "VD"), ("Échallens", "VD"), ("Grandson", "VD"),
    # Genève
    ("Carouge", "GE"), ("Vernier", "GE"), ("Lancy", "GE"), ("Meyrin", "GE"), ("Onex", "GE"), ("Thônex", "GE"), ("Versoix", "GE"),
    ("Plan-les-Ouates", "GE"), ("Chêne-Bougeries", "GE"), ("Collonge-Bellerive", "GE"),
    # Fribourg
    ("Bulle", "FR"), ("Morat", "FR"), ("Estavayer-le-Lac", "FR"), ("Romont", "FR"), ("Châtel-Saint-Denis", "FR"), ("Gruyères", "FR"),
    ("Guin", "FR"), ("Villars-sur-Glâne", "FR"), ("Marly", "FR"), ("Charmey", "FR"),
    # Neuchâtel
    ("La Chaux-de-Fonds", "NE"), ("Le Locle", "NE"), ("Boudry", "NE"), ("Val-de-Travers", "NE"), ("Cortaillod", "NE"),
    # Valais
    ("Sierre", "VS"), ("Martigny", "VS"), ("Monthey", "VS"), ("Brigue", "VS"), ("Viège", "VS"), ("Zermatt", "VS"), ("Verbier", "VS"),
    ("Crans-Montana", "VS"), ("Saas-Fee", "VS"), ("Loèche-les-Bains", "VS"), ("Champéry", "VS"), ("Saint-Maurice", "VS"), ("Conthey", "VS"),
    ("Nendaz", "VS"), ("Évolène", "VS"), ("Grimentz", "VS"), ("Fully", "VS"),
    # Jura
    ("Porrentruy", "JU"), ("Saignelégier", "JU"), ("Bassecourt", "JU"),
    # Berne
    ("Bienne", "BE"), ("Thoune", "BE"), ("Berthoud", "BE"), ("Langenthal", "BE"), ("Interlaken", "BE"), ("Grindelwald", "BE"),
    ("Gstaad", "BE"), ("Saint-Imier", "BE"), ("Tramelan", "BE"), ("La Neuveville", "BE"), ("Köniz", "BE"), ("Spiez", "BE"),
    ("Adelboden", "BE"), ("Wengen", "BE"), ("Mürren", "BE"), ("Lauterbrunnen", "BE"), ("Meiringen", "BE"),
    # Zurich
    ("Winterthour", "ZH"), ("Uster", "ZH"), ("Dübendorf", "ZH"), ("Dietikon", "ZH"), ("Wädenswil", "ZH"), ("Kloten", "ZH"), ("Horgen", "ZH"), ("Bülach", "ZH"),
    # Bâle
    ("Riehen", "BS"), ("Liestal", "BL"), ("Allschwil", "BL"), ("Muttenz", "BL"), ("Pratteln", "BL"), ("Binningen", "BL"),
    # Argovie
    ("Aarau", "AG"), ("Baden", "AG"), ("Wettingen", "AG"), ("Brugg", "AG"), ("Zofingue", "AG"), ("Rheinfelden", "AG"),
    # Soleure
    ("Olten", "SO"), ("Granges", "SO"),
    # Suisse centrale
    ("Emmen", "LU"), ("Kriens", "LU"), ("Sursee", "LU"), ("Horw", "LU"), ("Weggis", "LU"),
    ("Baar", "ZG"), ("Cham", "ZG"), ("Einsiedeln", "SZ"), ("Küssnacht", "SZ"), ("Brunnen", "SZ"),
    ("Altdorf", "UR"), ("Andermatt", "UR"), ("Flüelen", "UR"), ("Sarnen", "OW"), ("Engelberg", "OW"), ("Stans", "NW"), ("Beckenried", "NW"),
    ("Glaris", "GL"), ("Braunwald", "GL"),
    # Suisse orientale
    ("Rapperswil-Jona", "SG"), ("Bad Ragaz", "SG"),
    ("Appenzell", "AI"), ("Herisau", "AR"), ("Trogen", "AR"),
    ("Frauenfeld", "TG"), ("Kreuzlingen", "TG"), ("Arbon", "TG"), ("Amriswil", "TG"), ("Weinfelden", "TG"),
    ("Neuhausen am Rheinfall", "SH"), ("Stein am Rhein", "SH"),
    # Grisons
    ("Coire", "GR"), ("Davos", "GR"), ("Saint-Moritz", "GR"), ("Arosa", "GR"), ("Pontresina", "GR"), ("Klosters", "GR"),
    ("Lenzerheide", "GR"), ("Flims", "GR"), ("Laax", "GR"), ("Scuol", "GR"), ("Poschiavo", "GR"), ("Sils", "GR"),
    # Tessin
    ("Lugano", "TI"), ("Bellinzone", "TI"), ("Locarno", "TI"), ("Mendrisio", "TI"), ("Chiasso", "TI"), ("Ascona", "TI"), ("Airolo", "TI"),
    ("Biasca", "TI"), ("Brissago", "TI"),
]

# Sommets suisses (nom, altitude en m, canton si un seul, sinon None)
PEAKS = [
    ("la pointe Dufour", 4634, "VS"), ("le Dom", 4545, "VS"), ("le Weisshorn", 4506, "VS"), ("le Cervin", 4478, "VS"),
    ("la Dent Blanche", 4357, "VS"), ("le Grand Combin", 4314, "VS"), ("le Finsteraarhorn", 4274, None), ("la Jungfrau", 4158, None),
    ("le Mönch", 4107, None), ("le Piz Bernina", 4049, "GR"), ("l'Eiger", 3967, "BE"), ("le Piz Palü", 3901, "GR"),
    ("le Tödi", 3614, None), ("les Dents du Midi", 3257, "VS"), ("le Wildstrubel", 3244, None), ("le Titlis", 3238, None),
    ("les Diablerets", 3210, None), ("le Grand Muveran", 3051, None), ("le Säntis", 2502, None), ("le Niesen", 2362, "BE"),
    ("le Stockhorn", 2190, "BE"), ("le Pilate", 2128, None), ("les Rochers de Naye", 2042, "VD"), ("le Moléson", 2002, "FR"),
    ("le Rigi", 1798, None), ("le Mont Tendre", 1679, "VD"), ("la Dôle", 1677, "VD"), ("le Chasseral", 1607, "BE"),
]


def cde(name: str) -> str:
    """« du Tessin », « des Grisons », « d'Argovie », « de Vaud », « d'Uri »."""
    return de(ARTICLE.get(name, name))


def generate():
    out = []
    by = {c[0]: c for c in CANTONS}
    names = [c[1] for c in CANTONS]
    for ab, name, cap, langs, year, pop, area in CANTONS:
        d = 1 if ab in EASY else 2
        if cap != name:
            out.append(make("suisse", f"Quel est le chef-lieu du canton {cde(name)} ?", cap, pick(f"chl-{ab}", [c[2] for c in CANTONS], cap), d))
            out.append(make("suisse", f"{cap} est le chef-lieu de quel canton ?", name, pick(f"chlr-{ab}", names, name), d))
        out.append(make("suisse", f"Quelle est l'abréviation du canton {cde(name)} (plaques d'immatriculation) ?", ab,
                        pick(f"ab-{ab}", [c[0] for c in CANTONS], ab), d + 1))
        out.append(make("suisse", f"Quel canton a pour abréviation « {ab} » ?", name, pick(f"abr-{ab}", names, name), d))
        out.append(make("suisse", f"Quelle(s) langue(s) officielle(s) parle-t-on dans le canton {cde(name)} ?", langs,
                        pick(f"lang-{ab}", ["allemand", "français", "italien", "français et allemand", "allemand, romanche et italien", "romanche"], langs,
                             key=lambda x: frozenset(x.replace(",", " et").split(" et "))), d))
        out.append(make("suisse", f"En quelle année le canton {cde(name)} est-il entré dans la Confédération ?", str(year),
                        pick(f"yr-{ab}", ["1291", "1332", "1351", "1353", "1481", "1501", "1513", "1803", "1815", "1848", "1979", "1874"], str(year)),
                        2 if year in (1291, 1979, 1815) else 3))
    for town, ab in TOWNS:
        c = by[ab]
        # Mauvaises réponses : de préférence des cantons de la même région linguistique (plus crédibles).
        same = [x[1] for x in CANTONS if (x[3] == c[3] or x[0] in ("VD", "GE", "FR", "NE", "VS", "JU", "BE")) and x[0] != ab]
        d = 1 if ab in ("VD", "GE", "VS", "TI") and town in ("Montreux", "Zermatt", "Lugano", "Locarno", "Verbier", "Carouge", "Vevey", "Nyon") else 2
        out.append(make("suisse", f"Dans quel canton se trouve {town} ?", c[1], pick(f"town-{town}", same, c[1]), d if ab in EASY else 3))
    out += _comparisons("suisse", CANTONS, lambda c: c[1], lambda c: c[5], "Lequel de ces cantons compte le plus d'habitants ?",
                        "Lequel de ces cantons compte le moins d'habitants ?", 220, "ch-pop", 1.35, lambda c: 2 if c[0] in EASY else 3)
    out += _comparisons("suisse", CANTONS, lambda c: c[1], lambda c: c[6], "Lequel de ces cantons est le plus grand (superficie) ?",
                        "Lequel de ces cantons est le plus petit (superficie) ?", 220, "ch-area", 1.35, lambda c: 2 if c[0] in EASY else 3)
    out += _comparisons("suisse", PEAKS, lambda p: p[0][0].upper() + p[0][1:], lambda p: p[1], "Lequel de ces sommets suisses est le plus haut ?",
                        "Lequel de ces sommets suisses est le moins haut ?", 120, "ch-peak", 1.04)
    for name, alt, ab in PEAKS:
        if ab:
            out.append(make("suisse", f"Dans quel canton se trouve {name} ?", by[ab][1],
                            pick(f"peak-{name}", ["Valais", "Berne", "Grisons", "Vaud", "Fribourg", "Uri", "Tessin", "Glaris"], by[ab][1]),
                            2 if alt > 4000 or name in ("le Moléson", "le Cervin") else 3))
    return out
