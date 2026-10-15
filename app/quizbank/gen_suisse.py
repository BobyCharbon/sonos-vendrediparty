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
    for d, q, a, w in WRITTEN:
        out.append(make("suisse", q, a, w, d))
    return out


WRITTEN = [
    (1, "Quelle est la ville fédérale de la Suisse ?", "Berne", ["Zurich", "Genève", "Lausanne"]),
    (1, "Combien de cantons compte la Suisse ?", "26", ["23", "24", "20"]),
    (1, "Combien de langues nationales compte la Suisse ?", "4", ["3", "2", "5"]),
    (2, "Quelle est la quatrième langue nationale suisse, parlée dans les Grisons ?", "Le romanche", ["Le ladin", "Le frioulan", "Le walser"]),
    (1, "Quel est le plus haut sommet de Suisse ?", "La pointe Dufour", ["Le Cervin", "La Jungfrau", "Le Dom"]),
    (2, "Quel est le plus grand lac entièrement suisse ?", "Le lac de Neuchâtel", ["Le lac Léman", "Le lac de Constance", "Le lac des Quatre-Cantons"]),
    (1, "Quel est le plus grand lac de Suisse (partagé avec la France) ?", "Le Léman", ["Le lac de Neuchâtel", "Le lac Majeur", "Le lac de Constance"]),
    (1, "Quelle est la plus grande ville de Suisse ?", "Zurich", ["Genève", "Bâle", "Berne"]),
    (2, "Combien de membres compte le Conseil fédéral ?", "7", ["5", "9", "12"]),
    (2, "Combien de temps dure le mandat du président de la Confédération ?", "1 an", ["4 ans", "2 ans", "5 ans"]),
    (2, "Combien de sièges compte le Conseil national ?", "200", ["246", "150", "100"]),
    (2, "Combien de sièges compte le Conseil des États ?", "46", ["26", "50", "200"]),
    (2, "Comment s'appellent les deux chambres réunies du Parlement suisse ?", "L'Assemblée fédérale", ["Le Conseil fédéral", "La Diète", "Le Grand Conseil"]),
    (2, "Comment s'appelle le parlement d'un canton romand ?", "Le Grand Conseil", ["Le Conseil d'État", "L'Assemblée fédérale", "La Landsgemeinde"]),
    (2, "Comment s'appelle le gouvernement d'un canton romand ?", "Le Conseil d'État", ["Le Grand Conseil", "Le Conseil fédéral", "La Municipalité"]),
    (2, "Quelle assemblée en plein air vote à main levée à Appenzell Rhodes-Intérieures et Glaris ?", "La Landsgemeinde", ["La Diète", "Le Grand Conseil", "La Tagsatzung"]),
    (2, "Combien de signatures faut-il pour une initiative populaire fédérale ?", "100 000", ["50 000", "10 000", "200 000"]),
    (2, "Combien de signatures faut-il pour un référendum facultatif fédéral ?", "50 000", ["100 000", "10 000", "25 000"]),
    (2, "Que signifie l'abréviation « CH » ?", "Confoederatio Helvetica", ["Confédération Helvétique", "Cantons Helvètes", "Communauté Helvétique"]),
    (2, "Quel est le titre de l'hymne national suisse ?", "Le Cantique suisse", ["La Marche suisse", "Ô monts indépendants", "L'Hymne helvétique"]),
    (2, "Par quels mots commence le Cantique suisse en français ?", "Sur nos monts, quand le soleil…", ["Allons enfants de la patrie…", "Ô monts indépendants…", "Rufst du, mein Vaterland…"]),
    (2, "Quels sont les trois cantons du pacte de 1291 ?", "Uri, Schwytz et Unterwald", ["Uri, Zoug et Lucerne", "Berne, Zurich et Lucerne", "Schwytz, Glaris et Zoug"]),
    (2, "Depuis quel congrès la neutralité de la Suisse est-elle reconnue (1815) ?", "Le congrès de Vienne", ["Le traité de Westphalie", "Le traité de Versailles", "Le congrès de Berlin"]),
    (2, "En quelle année la Suisse a-t-elle rejoint l'ONU ?", "2002", ["1945", "1992", "2008"]),
    (2, "En quelle année le peuple suisse a-t-il refusé l'Espace économique européen ?", "1992", ["1986", "2002", "1999"]),
    (2, "En quelle année les femmes ont-elles obtenu le droit de vote fédéral en Suisse ?", "1971", ["1945", "1959", "1981"]),
    (2, "Quel est le plus long tunnel ferroviaire du monde, ouvert en 2016 ?", "Le tunnel de base du Gothard", ["Le tunnel du Lötschberg", "Le tunnel du Simplon", "Le tunnel sous la Manche"]),
    (2, "Quelle est la longueur du tunnel de base du Gothard, environ ?", "57 km", ["35 km", "50 km", "80 km"]),
    (2, "Quel est le plus grand glacier des Alpes ?", "Le glacier d'Aletsch", ["La Mer de Glace", "Le glacier du Rhône", "Le glacier de Morteratsch"]),
    (2, "Où se trouvent les plus grandes chutes d'Europe (débit) ?", "À Neuhausen (chutes du Rhin)", ["À Lauterbrunnen", "À Giessbach", "À Reichenbach"]),
    (2, "Où le Rhône prend-il sa source ?", "Au glacier du Rhône (Valais)", ["Au lac Léman", "Au Gothard", "Dans les Grisons"]),
    (2, "Dans quel canton le Rhin prend-il sa source ?", "Les Grisons", ["Uri", "Le Valais", "Saint-Gall"]),
    (3, "Vers quelle mer coule l'Inn, qui naît en Engadine ?", "La mer Noire (via le Danube)", ["La mer du Nord", "La Méditerranée", "La mer Adriatique"]),
    (3, "Quel est le point le plus bas de Suisse ?", "Le lac Majeur (193 m)", ["Le lac Léman", "Bâle", "Le lac de Lugano"]),
    (2, "Quelles sont les trois grandes régions naturelles de la Suisse ?", "Le Jura, le Plateau et les Alpes", ["Le Jura, les Préalpes et le Tessin", "Le Plateau, les lacs et les Alpes", "La Romandie, la Suisse alémanique et le Tessin"]),
    (2, "Quelle gare, la plus haute d'Europe, est surnommée « Top of Europe » ?", "Le Jungfraujoch", ["Le Gornergrat", "Le Petit Cervin", "Le Titlis"]),
    (2, "Quel train relie Zermatt à Saint-Moritz ?", "Le Glacier Express", ["Le Bernina Express", "Le GoldenPass Express", "Le Gotthard Panorama Express"]),
    (2, "Quel train relie les Grisons à Tirano en Italie ?", "Le Bernina Express", ["Le Glacier Express", "Le Centovalli", "Le GoldenPass"]),
    (2, "Quel funiculaire suisse est le plus raide du monde ?", "Le funiculaire du Stoos", ["Le funiculaire de Gelmer", "Le Gütsch", "Le funiculaire du Niesen"]),
    (2, "Quel chemin de fer à crémaillère est le plus raide du monde ?", "Celui du Pilate", ["Celui de la Jungfrau", "Celui du Rigi", "Celui du Gornergrat"]),
    (2, "Quelle station du Valais est interdite aux voitures à essence ?", "Zermatt", ["Verbier", "Crans-Montana", "Nendaz"]),
    (2, "Dans quel pays se trouve l'aéroport de Bâle-Mulhouse ?", "En France", ["En Suisse", "En Allemagne", "Il est binational sur sol suisse"]),
    (2, "Quelle ville accueille chaque année le Forum économique mondial ?", "Davos", ["Saint-Moritz", "Genève", "Zurich"]),
    (2, "Quelle ville suisse a accueilli deux fois les Jeux olympiques d'hiver ?", "Saint-Moritz", ["Davos", "Sion", "Crans-Montana"]),
    (2, "Quelle haute école polytechnique se trouve à Lausanne ?", "L'EPFL", ["L'ETH", "L'HEIG", "La HES-SO"]),
    (2, "Quelle haute école polytechnique se trouve à Zurich ?", "L'ETH", ["L'EPFL", "La ZHAW", "L'Université de Saint-Gall"]),
    (2, "Quelle est la hauteur du jet d'eau de Genève, environ ?", "140 m", ["50 m", "90 m", "200 m"]),
    (2, "Quelle fête genevoise célèbre la défaite des Savoyards en 1602 ?", "L'Escalade", ["La Fête de Genève", "Le Bol d'or", "La Restauration"]),
    (2, "Quelle fête zurichoise brûle un bonhomme de neige appelé Böögg ?", "Le Sechseläuten", ["Le Knabenschiessen", "La Street Parade", "Le Züri Fäscht"]),
    (2, "Quel carnaval suisse commence par le Morgestraich à 4 heures du matin ?", "Le carnaval de Bâle", ["Le carnaval de Lucerne", "Le carnaval de Bellinzone", "Le carnaval de Sion"]),
    (2, "Quel marché aux oignons a lieu à Berne en novembre ?", "Le Zibelemärit", ["Le Sechseläuten", "La Bénichon", "Le Chalandamarz"]),
    (2, "Quelle fête des Grisons célèbre le 1er mars avec des cloches ?", "Le Chalandamarz", ["L'Escalade", "Le Vogel Gryff", "La Désalpe"]),
    (2, "Comment s'appellent les combats entre vaches d'Hérens en Valais ?", "Les combats de reines", ["Les joutes alpines", "La désalpe", "La lutte des vaches"]),
    (2, "Comment appelle-t-on la descente des troupeaux des alpages en automne ?", "La désalpe", ["L'inalpe", "La transhumance d'hiver", "La remuage"]),
    (2, "Quel monstre poilu masqué parcourt le Lötschental en février ?", "Les Tschäggättä", ["Les Silvesterchläuse", "Les Krampus", "Les Perchten"]),
    (2, "Quel animal figure sur les armoiries du canton de Berne ?", "L'ours", ["Le lion", "L'aigle", "Le taureau"]),
    (2, "Quel animal figure sur les armoiries du canton d'Uri ?", "Une tête de taureau", ["Un ours", "Un bouquetin", "Un lion"]),
    (2, "Quel animal est l'emblème du canton des Grisons ?", "Le bouquetin", ["L'ours", "Le chamois", "L'aigle"]),
    (2, "Quel chien de montagne porte le nom d'un col suisse ?", "Le saint-bernard", ["Le bouvier bernois", "L'appenzeller", "Le berger blanc suisse"]),
    (2, "Quelle multinationale de l'alimentation a son siège à Vevey ?", "Nestlé", ["Lindt", "Emmi", "Migros"]),
    (2, "Quelles grandes entreprises pharmaceutiques ont leur siège à Bâle ?", "Novartis et Roche", ["Lonza et Sandoz", "Nestlé et Roche", "Novartis et Givaudan"]),
    (2, "Dans quelle ville est basée Swatch ?", "Bienne", ["Genève", "La Chaux-de-Fonds", "Le Locle"]),
    (2, "Dans quelle ville est basé Rolex ?", "Genève", ["Bienne", "Le Locle", "Zurich"]),
    (2, "Qui a fondé la Migros ?", "Gottlieb Duttweiler", ["Bernhard Jäggi", "Henri Nestlé", "Nicolas Hayek"]),
    (2, "Quelle entreprise fabrique le couteau suisse à Ibach (Schwytz) ?", "Victorinox", ["Wenger", "Swiza", "Caran d'Ache"]),
    (2, "Quelle entreprise genevoise fabrique crayons et stylos de luxe ?", "Caran d'Ache", ["Victorinox", "Montblanc", "Pelikan"]),
    (2, "Quelle boisson gazeuse suisse est à base de petit-lait ?", "Le Rivella", ["L'Ovomaltine", "Le Sinalco", "L'Elmer Citro"]),
    (2, "Quelle police de caractères célèbre a été créée en Suisse en 1957 ?", "L'Helvetica", ["L'Arial", "Le Times", "Le Futura"]),
    (2, "Dans quelle ville est né Le Corbusier ?", "La Chaux-de-Fonds", ["Genève", "Lausanne", "Neuchâtel"]),
    (2, "Dans quelle ville est né Jean-Jacques Rousseau ?", "Genève", ["Lausanne", "Neuchâtel", "Paris"]),
    (2, "Dans quelle ville Einstein travaillait-il à l'Office des brevets en 1905 ?", "Berne", ["Zurich", "Bâle", "Genève"]),
    (2, "Quel sculpteur grison est célèbre pour ses figures filiformes ?", "Alberto Giacometti", ["Jean Tinguely", "Paul Klee", "Hans Erni"]),
    (2, "Quel artiste fribourgeois a créé des machines sculptures animées ?", "Jean Tinguely", ["Alberto Giacometti", "Bernhard Luginbühl", "Hans Erni"]),
    (2, "Quel peintre suisse a peint « Le Bûcheron », reproduit sur un ancien billet de 50 francs ?", "Ferdinand Hodler", ["Albert Anker", "Félix Vallotton", "Cuno Amiet"]),
    (2, "Quelle romancière suisse a écrit « Heidi » ?", "Johanna Spyri", ["Corinna Bille", "Alice Rivaz", "Ella Maillart"]),
    (2, "Quel écrivain vaudois a écrit « Derborence » ?", "Charles-Ferdinand Ramuz", ["Jacques Chessex", "Maurice Chappaz", "Philippe Jaccottet"]),
    (2, "Quel écrivain suisse a écrit « La Visite de la vieille dame » ?", "Friedrich Dürrenmatt", ["Max Frisch", "Robert Walser", "Gottfried Keller"]),
    (2, "Quel psychiatre suisse a fondé la psychologie analytique ?", "Carl Gustav Jung", ["Jean Piaget", "Sigmund Freud", "Auguste Forel"]),
    (2, "Quel psychologue neuchâtelois a étudié le développement de l'enfant ?", "Jean Piaget", ["Carl Jung", "Édouard Claparède", "Pestalozzi"]),
    (2, "Quel aventurier suisse a fait le tour du monde en avion solaire (Solar Impulse) ?", "Bertrand Piccard", ["Auguste Piccard", "Mike Horn", "Ueli Steck"]),
    (2, "Quel Neuchâtelois a co-fondé la marque automobile Chevrolet ?", "Louis Chevrolet", ["Louis Renault", "Ferdinand Porsche", "Ettore Bugatti"]),
    (2, "Quel humoriste suisse s'appelle Emil Steinberger ?", "Emil", ["Marco Rima", "Massimo Rocchi", "Zouc"]),
    (2, "Quel parti suisse est le plus grand au Conseil national (depuis 1999) ?", "L'UDC", ["Le PS", "Le PLR", "Le Centre"]),
    (2, "Combien de partis sont représentés au Conseil fédéral par la « formule magique » historique ?", "4", ["2", "3", "7"]),
    (2, "Quelle banque centrale émet le franc suisse ?", "La Banque nationale suisse", ["UBS", "PostFinance", "La Banque cantonale de Berne"]),
    (2, "Où se trouve la Bourse suisse (SIX) ?", "Zurich", ["Genève", "Bâle", "Berne"]),
    (2, "Quel est le plus vieux pont couvert en bois d'Europe, à Lucerne ?", "Le pont de la Chapelle", ["Le pont de Spreuer", "Le pont de Berne", "Le pont de Rapperswil"]),
    (2, "Dans quelle ville se trouve la Zytglogge, tour de l'horloge astronomique ?", "Berne", ["Zurich", "Soleure", "Lucerne"]),
    (2, "Quelle ville suisse compte deux châteaux, Valère et Tourbillon ?", "Sion", ["Bellinzone", "Gruyères", "Grandson"]),
    (2, "Quelle ville tessinoise a trois châteaux classés à l'UNESCO ?", "Bellinzone", ["Lugano", "Locarno", "Mendrisio"]),
    (2, "Où se trouve le château de Chillon ?", "À Veytaux, près de Montreux", ["À Morges", "À Grandson", "À Gruyères"]),
    (2, "Quel poète anglais a rendu célèbre le château de Chillon ?", "Lord Byron", ["Percy Shelley", "John Keats", "William Wordsworth"]),
    (2, "Dans quelle ville se trouve la fondation Beyeler ?", "Riehen (près de Bâle)", ["Zurich", "Genève", "Lucerne"]),
    (2, "Quelle foire d'art contemporain a lieu chaque juin à Bâle ?", "Art Basel", ["Artgenève", "Kunst Zürich", "La Biennale de Bâle"]),
    (2, "Quel artiste a donné son musée au château de Gruyères ?", "H. R. Giger", ["Jean Tinguely", "Hans Erni", "Alberto Giacometti"]),
    (2, "Quelle ville fribourgeoise est célèbre pour son château et son fromage ?", "Gruyères", ["Bulle", "Romont", "Morat"]),
    (2, "Quelle région vaudoise est réputée pour l'horlogerie de luxe ?", "La vallée de Joux", ["La Broye", "Le Chablais", "Le Gros-de-Vaud"]),
    (2, "Quelles villes neuchâteloises sont classées à l'UNESCO pour leur urbanisme horloger ?", "La Chaux-de-Fonds et Le Locle", ["Neuchâtel et Boudry", "Fleurier et Môtiers", "Saint-Imier et Tramelan"]),
    (2, "Quel site suisse a été le premier classé au patrimoine mondial naturel de l'UNESCO dans les Alpes ?", "Jungfrau-Aletsch", ["Le Haut lieu tectonique Sardona", "Le Monte San Giorgio", "Lavaux"]),
    (2, "Quelle vieille ville suisse est classée à l'UNESCO ?", "Berne", ["Zurich", "Lucerne", "Bâle"]),
    (2, "Quel couvent suisse classé à l'UNESCO possède une célèbre bibliothèque ?", "L'abbaye de Saint-Gall", ["L'abbaye d'Einsiedeln", "Le couvent de Müstair", "L'abbaye de Saint-Maurice"]),
    (2, "Quelle est la plus ancienne abbaye d'Occident en activité continue (515) ?", "L'abbaye de Saint-Maurice", ["L'abbaye de Saint-Gall", "L'abbaye d'Einsiedeln", "L'abbaye de Romainmôtier"]),
    (2, "Quel est le lieu de pèlerinage marial le plus visité de Suisse ?", "Einsiedeln", ["Saint-Maurice", "Sachseln", "Le Ranft"]),
    (2, "Combien d'habitants compte la Suisse, environ (2024) ?", "9 millions", ["6 millions", "12 millions", "7 millions"]),
    (2, "Quelle part environ du territoire suisse est couverte par les Alpes ?", "Environ 60 %", ["Environ 30 %", "Environ 80 %", "Environ 45 %"]),
    (2, "Quel pays n'a pas de frontière avec la Suisse ?", "La Belgique", ["Le Liechtenstein", "L'Autriche", "L'Italie"]),
    (2, "Avec combien de pays la Suisse a-t-elle une frontière ?", "5", ["4", "6", "3"]),
    (2, "Quel canton est le seul officiellement trilingue ?", "Les Grisons", ["Berne", "Le Valais", "Fribourg"]),
    (2, "Quel est le seul canton où l'italien est la seule langue officielle ?", "Le Tessin", ["Les Grisons", "Le Valais", "Uri"]),
    (2, "Quel canton est le plus récent ?", "Le Jura", ["Genève", "Le Valais", "Neuchâtel"]),
    (2, "Quelle commune bernoise a rejoint le canton du Jura le 1er janvier 2026 ?", "Moutier", ["Saint-Imier", "Tramelan", "La Neuveville"]),
    (2, "Quel col relie Uri au Tessin ?", "Le Gothard", ["Le Simplon", "Le Grimsel", "La Furka"]),
    (2, "Quel col relie le Valais à l'Italie par Brigue et Domodossola ?", "Le Simplon", ["Le Grand-Saint-Bernard", "Le Nufenen", "Le Gothard"]),
    (2, "Quel lac traverse la frontière entre la Suisse, l'Allemagne et l'Autriche ?", "Le lac de Constance", ["Le lac Majeur", "Le lac de Lugano", "Le lac de Zurich"]),
    (2, "Sur quel lac se trouve Lucerne ?", "Le lac des Quatre-Cantons", ["Le lac de Zoug", "Le lac de Zurich", "Le lac de Sempach"]),
    (2, "Sur quel lac se trouvent Lugano et Morcote ?", "Le lac de Lugano (Ceresio)", ["Le lac Majeur", "Le lac de Côme", "Le lac de Garde"]),
    (2, "Sur quel lac se trouvent Locarno et Ascona ?", "Le lac Majeur", ["Le lac de Lugano", "Le lac de Côme", "Le lac d'Orta"]),
    (2, "Quels lacs encadrent Interlaken ?", "Les lacs de Thoune et de Brienz", ["Les lacs de Neuchâtel et de Bienne", "Les lacs de Zoug et de Lucerne", "Les lacs de Sils et de Silvaplana"]),
    (2, "Quel lac relie Neuchâtel, Bienne et Morat par des canaux ?", "Les trois lacs jurassiens", ["Les lacs de l'Engadine", "Les lacs de la Suisse centrale", "Les lacs de la Broye"]),
    (2, "Quelle course de voiliers a lieu chaque année sur le Léman ?", "Le Bol d'Or Mirabaud", ["La Route du Rhum", "La Coupe de l'America", "Le Tour du Léman à l'aviron"]),
    (2, "Quelle est l'altitude du Cervin, environ ?", "4 478 m", ["4 810 m", "4 158 m", "4 634 m"]),
    (2, "Quel sommet suisse a une forme pyramidale célèbre sur les emballages Toblerone ?", "Le Cervin", ["L'Eiger", "La Jungfrau", "Le Pilate"]),
    (2, "Quelle face nord est la plus célèbre des Alpes bernoises ?", "Celle de l'Eiger", ["Celle du Mönch", "Celle du Cervin", "Celle du Titlis"]),
    (2, "Quel téléphérique de Zermatt mène au plus haut point accessible des Alpes en Europe ?", "Le Petit Cervin (Matterhorn Glacier Paradise)", ["Le Gornergrat", "Le Rothorn", "Le Klein Titlis"]),
    (2, "Comment s'appelle la principale compagnie aérienne suisse ?", "Swiss", ["Swissair", "Helvetic Airways", "EasyJet Switzerland"]),
    (2, "Quelle ancienne compagnie aérienne nationale a fait faillite en 2001-2002 ?", "Swissair", ["Crossair", "Balair", "Swiss"]),
    (2, "Comment s'appelle la télévision publique suisse alémanique ?", "La SRF", ["La RTS", "La RSI", "La RTR"]),
    (2, "Comment s'appelle la télévision publique suisse italophone ?", "La RSI", ["La RTS", "La SRF", "La RAI"]),
]
WRITTEN += [
    (2, "Comment s'appelle la télévision publique suisse romande ?", "La RTS", ["La SRF", "La RSI", "La RTR"]),
    (2, "Quel col relie le Valais à l'Italie par le val d'Aoste ?", "Le col du Grand-Saint-Bernard", ["Le Simplon", "Le Gothard", "Le Lukmanier"]),
]
