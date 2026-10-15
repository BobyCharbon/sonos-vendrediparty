"""Histoire : événements datés, personnages par siècle, présidents, rois, questions rédigées."""

import random

from . import make, pick

# (année, événement) — négatif : avant J.-C.
EVENTS = [
    (-776, "les premiers Jeux olympiques de l'Antiquité"), (-753, "la fondation légendaire de Rome"), (-490, "la bataille de Marathon"),
    (-480, "la bataille des Thermopyles"), (-323, "la mort d'Alexandre le Grand"), (-218, "la traversée des Alpes par Hannibal"),
    (-52, "la bataille d'Alésia"), (-44, "l'assassinat de Jules César"), (-27, "le début du règne d'Auguste, premier empereur romain"),
    (79, "l'éruption du Vésuve qui détruit Pompéi"), (313, "l'édit de Milan (liberté de culte pour les chrétiens)"),
    (476, "la chute de l'Empire romain d'Occident"), (622, "l'Hégire (départ de Mahomet pour Médine)"), (732, "la bataille de Poitiers"),
    (800, "le couronnement de Charlemagne empereur"), (843, "le traité de Verdun (partage de l'empire carolingien)"),
    (987, "l'avènement d'Hugues Capet"), (1066, "la bataille d'Hastings"), (1095, "l'appel à la première croisade"),
    (1099, "la prise de Jérusalem par les croisés"), (1215, "la Magna Carta en Angleterre"), (1291, "le pacte fédéral des Waldstätten (Suisse)"),
    (1315, "la bataille de Morgarten"), (1337, "le début de la guerre de Cent Ans"), (1347, "l'arrivée de la peste noire en Europe"),
    (1386, "la bataille de Sempach"), (1415, "la bataille d'Azincourt"), (1429, "la libération d'Orléans par Jeanne d'Arc"),
    (1431, "la mort de Jeanne d'Arc sur le bûcher"), (1453, "la prise de Constantinople par les Ottomans"),
    (1476, "les batailles de Grandson et de Morat"), (1492, "l'arrivée de Christophe Colomb en Amérique"),
    (1498, "l'arrivée de Vasco de Gama en Inde"), (1515, "la bataille de Marignan"), (1517, "la publication des 95 thèses de Luther"),
    (1522, "le retour de l'expédition de Magellan (premier tour du monde)"), (1536, "l'adoption de la Réforme à Genève"),
    (1539, "l'ordonnance de Villers-Cotterêts (le français, langue officielle des actes)"), (1572, "le massacre de la Saint-Barthélemy"),
    (1598, "l'édit de Nantes"), (1610, "l'assassinat d'Henri IV"), (1618, "le début de la guerre de Trente Ans"),
    (1620, "l'arrivée du Mayflower en Amérique"), (1648, "les traités de Westphalie"), (1661, "le début du règne personnel de Louis XIV"),
    (1682, "l'installation de la cour à Versailles"), (1685, "la révocation de l'édit de Nantes"), (1715, "la mort de Louis XIV"),
    (1755, "le tremblement de terre de Lisbonne"), (1776, "la déclaration d'indépendance des États-Unis"),
    (1789, "la prise de la Bastille"), (1792, "la proclamation de la Ire République en France"), (1793, "l'exécution de Louis XVI"),
    (1798, "la proclamation de la République helvétique"), (1799, "le coup d'État du 18 Brumaire"), (1803, "l'Acte de médiation en Suisse"),
    (1804, "le sacre de Napoléon Ier"), (1805, "la bataille d'Austerlitz"), (1812, "la campagne de Russie de Napoléon"),
    (1815, "la bataille de Waterloo"), (1830, "la révolution de Juillet (les Trois Glorieuses)"), (1847, "la guerre du Sonderbund"),
    (1848, "la première Constitution fédérale suisse"), (1861, "le début de la guerre de Sécession"),
    (1863, "la fondation de la Croix-Rouge à Genève"), (1865, "l'assassinat d'Abraham Lincoln"), (1869, "l'inauguration du canal de Suez"),
    (1870, "le début de la guerre franco-prussienne"), (1871, "la Commune de Paris"), (1882, "l'ouverture du tunnel ferroviaire du Gothard"),
    (1889, "l'inauguration de la tour Eiffel"), (1894, "le début de l'affaire Dreyfus"), (1896, "les premiers Jeux olympiques modernes à Athènes"),
    (1903, "le premier vol motorisé des frères Wright"), (1905, "la loi de séparation des Églises et de l'État en France"),
    (1912, "le naufrage du Titanic"), (1914, "l'assassinat de l'archiduc François-Ferdinand à Sarajevo"), (1916, "la bataille de Verdun"),
    (1917, "la révolution d'Octobre en Russie"), (1918, "l'armistice de la Première Guerre mondiale"), (1919, "le traité de Versailles"),
    (1920, "la création de la Société des Nations"), (1929, "le krach de Wall Street"), (1933, "l'arrivée d'Hitler au pouvoir"),
    (1936, "le Front populaire et les premiers congés payés en France"), (1939, "l'invasion de la Pologne par l'Allemagne"),
    (1940, "l'appel du 18 Juin du général de Gaulle"), (1941, "l'attaque de Pearl Harbor"), (1943, "la fin de la bataille de Stalingrad"),
    (1944, "le débarquement en Normandie"), (1945, "les bombardements atomiques d'Hiroshima et Nagasaki"),
    (1947, "l'indépendance de l'Inde"), (1948, "la Déclaration universelle des droits de l'homme"), (1949, "la création de l'OTAN"),
    (1950, "le début de la guerre de Corée"), (1953, "la première ascension de l'Everest"), (1954, "la bataille de Diên Biên Phu"),
    (1955, "le refus de Rosa Parks de céder sa place dans le bus"), (1957, "le lancement de Spoutnik"), (1958, "la naissance de la Ve République"),
    (1961, "la construction du mur de Berlin"), (1962, "la crise des missiles de Cuba"), (1963, "l'assassinat de John F. Kennedy"),
    (1968, "les événements de Mai 68"), (1969, "les premiers pas de l'homme sur la Lune"),
    (1971, "le droit de vote des femmes au niveau fédéral en Suisse"), (1973, "le premier choc pétrolier"),
    (1974, "la démission de Richard Nixon (Watergate)"), (1975, "la chute de Saïgon"), (1979, "la révolution iranienne"),
    (1981, "l'abolition de la peine de mort en France"), (1986, "la catastrophe de Tchernobyl"), (1989, "la chute du mur de Berlin"),
    (1990, "la libération de Nelson Mandela"), (1991, "la dissolution de l'URSS"), (1992, "le traité de Maastricht"),
    (1994, "le génocide des Tutsi au Rwanda"), (1997, "la mort de Lady Diana"), (2001, "les attentats du 11 Septembre"),
    (2002, "la mise en circulation des pièces et billets en euros"), (2003, "le début de la guerre d'Irak"),
    (2004, "le tsunami dans l'océan Indien"), (2008, "la faillite de Lehman Brothers"), (2011, "la catastrophe nucléaire de Fukushima"),
    (2016, "le référendum du Brexit"), (2019, "l'incendie de Notre-Dame de Paris"), (2020, "la pandémie de Covid-19"),
    (2022, "l'invasion de l'Ukraine par la Russie"), (1944, "le droit de vote des femmes en France"),
    (1957, "la signature du traité de Rome"), (1960, "l'indépendance de nombreux pays d'Afrique francophone"), (1962, "l'indépendance de l'Algérie"),
    (1964, "l'adoption du Civil Rights Act aux États-Unis"), (1977, "la sortie du premier Star Wars au cinéma"), (1979, "la création du canton du Jura"),
    (1985, "l'arrivée de Gorbatchev au pouvoir en URSS"), (1993, "la naissance officielle de l'Union européenne"),
    (1999, "l'introduction de l'euro sur les marchés financiers"), (2002, "l'adhésion de la Suisse à l'ONU"), (2016, "l'inauguration du tunnel de base du Gothard"),
    (1871, "la proclamation de l'Empire allemand à Versailles"), (1848, "l'abolition définitive de l'esclavage en France"),
    (1789, "la Déclaration des droits de l'homme et du citoyen"), (1453, "la fin de la guerre de Cent Ans"), (1494, "le traité de Tordesillas"),
    (1519, "le début de la conquête de l'empire aztèque par Cortés"), (1532, "la capture de l'empereur inca Atahualpa par Pizarro"),
    (1588, "la défaite de l'Invincible Armada"), (1607, "la fondation de Jamestown, première colonie anglaise durable en Amérique"),
    (1608, "la fondation de Québec par Samuel de Champlain"), (1666, "le grand incendie de Londres"), (1688, "la Glorieuse Révolution en Angleterre"),
    (1756, "le début de la guerre de Sept Ans"), (1783, "le premier vol habité en montgolfière"), (1787, "la Constitution des États-Unis"),
    (1821, "la mort de Napoléon à Sainte-Hélène"), (1825, "la première ligne de chemin de fer publique en Angleterre"),
    (1859, "la bataille de Solférino"), (1867, "l'achat de l'Alaska par les États-Unis"), (1885, "la conférence de Berlin sur le partage de l'Afrique"),
    (1898, "la publication de « J'accuse… ! » de Zola"), (1911, "la conquête du pôle Sud par Amundsen"), (1922, "la découverte du tombeau de Toutânkhamon"),
    (1927, "la première traversée de l'Atlantique en solitaire par Lindbergh"), (1936, "le début de la guerre d'Espagne"),
    (1938, "les accords de Munich"), (1947, "le lancement du plan Marshall"),
]
EASY_YEARS = {1789, 1492, 1914, 1918, 1939, 1945, 1969, 1989, 2001, 1515, 1291, 1944, 1815, 800, 1066, 1804, 1912, 476, 1453, 1848, 1968, 2020}


def fmt_year(y: int) -> str:
    return f"{-y} av. J.-C." if y < 0 else str(y)


def roman(n: int) -> str:
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def century(c: int) -> str:
    """5 → « Ve siècle », 1 → « Ier siècle », -1 → « Ier siècle av. J.-C. »."""
    n = abs(c)
    s = f"{roman(n)}{'er' if n == 1 else 'e'} siècle"
    return s + (" av. J.-C." if c < 0 else "")


# Personnage → siècle de sa vie active
PEOPLE = [
    ("Ramsès II", -13), ("Périclès", -5), ("Socrate", -5), ("Platon", -4), ("Aristote", -4), ("Alexandre le Grand", -4), ("Archimède", -3),
    ("Hannibal", -3), ("Jules César", -1), ("Cléopâtre", -1), ("Vercingétorix", -1), ("Cicéron", -1), ("Auguste", -1), ("Néron", 1),
    ("Marc Aurèle", 2), ("Constantin Ier", 4), ("Attila", 5), ("Clovis", 5), ("Justinien", 6), ("Mahomet", 7), ("Charles Martel", 8),
    ("Charlemagne", 8), ("Hugues Capet", 10), ("Guillaume le Conquérant", 11), ("Saladin", 12), ("Aliénor d'Aquitaine", 12), ("Richard Cœur de Lion", 12),
    ("Gengis Khan", 13), ("Saint Louis (Louis IX)", 13), ("Marco Polo", 13), ("Jeanne d'Arc", 15), ("Gutenberg", 15),
    ("Christophe Colomb", 15), ("Charles le Téméraire", 15), ("Laurent de Médicis", 15), ("François Ier", 16), ("Martin Luther", 16),
    ("Jean Calvin", 16), ("Michel-Ange", 16), ("Henri VIII", 16), ("Élisabeth Ire d'Angleterre", 16), ("Soliman le Magnifique", 16), ("Copernic", 16),
    ("Hernán Cortés", 16), ("Catherine de Médicis", 16), ("Shakespeare", 16), ("Galilée", 17), ("Louis XIII", 17), ("Richelieu", 17),
    ("Louis XIV", 17), ("Molière", 17), ("Descartes", 17), ("Isaac Newton", 17), ("Rembrandt", 17), ("Voltaire", 18),
    ("Jean-Jacques Rousseau", 18), ("Louis XV", 18), ("Mozart", 18), ("George Washington", 18), ("Louis XVI", 18), ("Marie-Antoinette", 18),
    ("Catherine II de Russie", 18), ("Frédéric II de Prusse", 18), ("Robespierre", 18), ("Napoléon Ier", 19), ("Victor Hugo", 19),
    ("Abraham Lincoln", 19), ("La reine Victoria", 19), ("Bismarck", 19), ("Henri Dunant", 19), ("Guillaume-Henri Dufour", 19), ("Louis Pasteur", 19),
    ("Charles Darwin", 19), ("Napoléon III", 19), ("Garibaldi", 19), ("Karl Marx", 19), ("Jules Verne", 19), ("Vincent van Gogh", 19),
    ("Lénine", 20), ("Staline", 20), ("Winston Churchill", 20), ("Charles de Gaulle", 20), ("Gandhi", 20), ("Hitler", 20), ("Franklin D. Roosevelt", 20),
    ("Mao Zedong", 20), ("John F. Kennedy", 20), ("Martin Luther King", 20), ("Nelson Mandela", 20), ("Albert Einstein", 20), ("Marie Curie", 20),
    ("Picasso", 20), ("Fidel Castro", 20), ("Che Guevara", 20), ("Mikhaïl Gorbatchev", 20), ("Margaret Thatcher", 20), ("François Mitterrand", 20),
    ("Ho Chi Minh", 20), ("Simone Veil", 20), ("Le Corbusier", 20), ("Barack Obama", 21), ("Angela Merkel", 21), ("Emmanuel Macron", 21),
]

# Présidents de la Ve République, dans l'ordre
FR_PRESIDENTS = ["Charles de Gaulle", "Georges Pompidou", "Valéry Giscard d'Estaing", "François Mitterrand", "Jacques Chirac",
                 "Nicolas Sarkozy", "François Hollande", "Emmanuel Macron"]
US_PRESIDENTS = [  # (président, année du début du premier mandat)
    ("George Washington", 1789), ("Thomas Jefferson", 1801), ("Abraham Lincoln", 1861), ("Theodore Roosevelt", 1901), ("Woodrow Wilson", 1913),
    ("Franklin D. Roosevelt", 1933), ("Harry Truman", 1945), ("Dwight Eisenhower", 1953), ("John F. Kennedy", 1961), ("Lyndon Johnson", 1963),
    ("Richard Nixon", 1969), ("Gerald Ford", 1974), ("Jimmy Carter", 1977), ("Ronald Reagan", 1981), ("George H. W. Bush", 1989),
    ("Bill Clinton", 1993), ("George W. Bush", 2001), ("Barack Obama", 2009), ("Donald Trump", 2017), ("Joe Biden", 2021),
]

WRITTEN = [
    (1, "Qui était le premier empereur des Français ?", "Napoléon Ier", ["Louis XIV", "Charlemagne", "Napoléon III"]),
    (1, "Quel roi était surnommé le « Roi-Soleil » ?", "Louis XIV", ["Louis XVI", "François Ier", "Henri IV"]),
    (2, "Quel roi de France était surnommé « le Bon roi » et aimait la poule au pot ?", "Henri IV", ["Louis XII", "Saint Louis", "Charles VII"]),
    (2, "Quelle reine a été guillotinée en 1793 ?", "Marie-Antoinette", ["Catherine de Médicis", "Marie de Médicis", "Joséphine de Beauharnais"]),
    (1, "Dans quelle ville se trouve la Bastille prise en 1789 ?", "Paris", ["Versailles", "Lyon", "Marseille"]),
    (2, "Sur quelle île Napoléon est-il mort ?", "Sainte-Hélène", ["L'île d'Elbe", "La Corse", "Malte"]),
    (2, "Sur quelle île Napoléon a-t-il été exilé en 1814 ?", "L'île d'Elbe", ["Sainte-Hélène", "La Corse", "La Sardaigne"]),
    (1, "Où est né Napoléon Bonaparte ?", "En Corse (Ajaccio)", ["À Paris", "En Italie", "À Marseille"]),
    (2, "Qui a écrit « Le Prince » ?", "Machiavel", ["Erasme", "Thomas More", "Montaigne"]),
    (2, "Quelle civilisation a construit le Machu Picchu ?", "Les Incas", ["Les Mayas", "Les Aztèques", "Les Olmèques"]),
    (2, "Quelle était la capitale de l'empire aztèque ?", "Tenochtitlan", ["Cuzco", "Chichén Itzá", "Teotihuacan"]),
    (2, "Quelle était la capitale de l'empire inca ?", "Cuzco", ["Lima", "Quito", "Tenochtitlan"]),
    (2, "Quel pharaon est célèbre pour son tombeau intact découvert en 1922 ?", "Toutânkhamon", ["Ramsès II", "Khéops", "Akhenaton"]),
    (2, "Pour quel pharaon a été construite la plus grande pyramide de Gizeh ?", "Khéops", ["Khéphren", "Mykérinos", "Ramsès II"]),
    (2, "Quelle pierre a permis de déchiffrer les hiéroglyphes ?", "La pierre de Rosette", ["La pierre de Gizeh", "La stèle de Hammurabi", "La pierre noire"]),
    (2, "Qui a déchiffré les hiéroglyphes égyptiens ?", "Jean-François Champollion", ["Howard Carter", "Auguste Mariette", "Napoléon"]),
    (2, "Quel chef gaulois s'est rendu à Jules César à Alésia ?", "Vercingétorix", ["Ambiorix", "Brennus", "Astérix"]),
    (2, "Comment s'appelaient les soldats d'élite des empereurs romains ?", "Les prétoriens", ["Les légionnaires", "Les centurions", "Les hoplites"]),
    (2, "Comment s'appelaient les soldats grecs lourdement armés ?", "Les hoplites", ["Les légionnaires", "Les spartiates", "Les phalangistes"]),
    (2, "Quelle cité grecque était célèbre pour ses guerriers ?", "Sparte", ["Athènes", "Corinthe", "Thèbes"]),
    (2, "Quel empereur romain aurait fait incendier Rome en 64 ?", "Néron", ["Caligula", "Tibère", "Hadrien"]),
    (2, "Quel mur romain traversait le nord de l'Angleterre ?", "Le mur d'Hadrien", ["Le mur d'Antonin", "Le limes de Germanie", "Le mur d'Auguste"]),
    (2, "Comment appelle-t-on la période entre l'Antiquité et la Renaissance ?", "Le Moyen Âge", ["L'époque moderne", "La préhistoire", "L'âge du fer"]),
    (2, "Quel événement marque traditionnellement la fin du Moyen Âge ?", "La prise de Constantinople (1453)", ["La Révolution française", "La chute de Rome", "La mort de Charlemagne"]),
    (2, "Qui a fondé l'ordre des Templiers ?", "Hugues de Payns", ["Saint Louis", "Godefroy de Bouillon", "Bernard de Clairvaux"]),
    (2, "Quel roi de France a fait arrêter les Templiers en 1307 ?", "Philippe le Bel", ["Saint Louis", "Louis X", "Philippe Auguste"]),
    (2, "Comment appelait-on l'héritier du trône de France ?", "Le dauphin", ["Le prince", "Le duc", "Le régent"]),
    (2, "Quelle guerre a opposé la France et l'Angleterre de 1337 à 1453 ?", "La guerre de Cent Ans", ["La guerre de Trente Ans", "La guerre des Deux-Roses", "La guerre de Sept Ans"]),
    (2, "Quelle guerre civile anglaise opposait les York et les Lancastre ?", "La guerre des Deux-Roses", ["La guerre de Cent Ans", "La guerre civile de Cromwell", "La guerre de Sécession"]),
    (2, "Qui a peint la chapelle Sixtine ?", "Michel-Ange", ["Raphaël", "Léonard de Vinci", "Botticelli"]),
    (2, "Quel navigateur a donné son nom à l'Amérique ?", "Amerigo Vespucci", ["Christophe Colomb", "Jacques Cartier", "Fernand de Magellan"]),
    (2, "Quel explorateur a remonté le Saint-Laurent en 1534 ?", "Jacques Cartier", ["Samuel de Champlain", "Christophe Colomb", "Jean Cabot"]),
    (2, "Comment s'appelaient les trois navires de Christophe Colomb ?", "La Niña, la Pinta et la Santa María", ["Le Victoria, le Trinidad et le Santiago", "Le Mayflower, le Speedwell et le Fortune", "La Belle, l'Aimable et le Joly"]),
    (2, "Qui a mené la Réforme protestante en Allemagne ?", "Martin Luther", ["Jean Calvin", "Ulrich Zwingli", "John Knox"]),
    (2, "Quel réformateur s'est établi à Zurich ?", "Ulrich Zwingli", ["Jean Calvin", "Martin Luther", "Guillaume Farel"]),
    (2, "Quel réformateur a fait de Genève la « Rome protestante » ?", "Jean Calvin", ["Martin Luther", "Ulrich Zwingli", "Théodore de Bèze"]),
    (2, "Quel traité de 1648 a reconnu l'indépendance de la Suisse ?", "Les traités de Westphalie", ["Le traité de Vienne", "Le traité d'Utrecht", "Le traité de Paris"]),
    (2, "Qui était le ministre principal de Louis XIII ?", "Le cardinal de Richelieu", ["Mazarin", "Colbert", "Sully"]),
    (2, "Quel ministre de Louis XIV a développé les manufactures ?", "Colbert", ["Fouquet", "Richelieu", "Louvois"]),
    (2, "Quelle révolte des nobles a marqué l'enfance de Louis XIV ?", "La Fronde", ["La Jacquerie", "La Ligue", "La Commune"]),
    (2, "Comment appelait-on la société française avant 1789 ?", "L'Ancien Régime", ["Le Premier Empire", "La Restauration", "Le Consulat"]),
    (2, "Quels étaient les trois ordres de l'Ancien Régime ?", "Clergé, noblesse, tiers état", ["Roi, noblesse, peuple", "Clergé, bourgeoisie, paysans", "Noblesse, armée, clergé"]),
    (2, "Quel serment les députés ont-ils prêté le 20 juin 1789 ?", "Le serment du Jeu de paume", ["Le serment de Versailles", "Le serment du Grütli", "Le serment de la Bastille"]),
    (2, "Comment s'appelait la période la plus violente de la Révolution (1793-1794) ?", "La Terreur", ["La Fronde", "Le Directoire", "La Restauration"]),
    (2, "Quel instrument est devenu le symbole de la Terreur ?", "La guillotine", ["La potence", "Le bûcher", "La roue"]),
    (2, "Quel est l'hymne national français, composé en 1792 ?", "La Marseillaise", ["Le Chant du départ", "La Carmagnole", "Ça ira"]),
    (2, "Qui a composé la Marseillaise ?", "Rouget de Lisle", ["Hector Berlioz", "Méhul", "Gossec"]),
    (2, "Quel code de lois Napoléon a-t-il fait rédiger en 1804 ?", "Le Code civil", ["Le Code pénal", "La Charte", "Le Concordat"]),
    (2, "Après Waterloo, quelle dynastie revient sur le trône de France ?", "Les Bourbons", ["Les Orléans", "Les Bonaparte", "Les Valois"]),
    (2, "Quel était le dernier roi des Français (1830-1848) ?", "Louis-Philippe Ier", ["Charles X", "Louis XVIII", "Napoléon III"]),
    (2, "Quel régime Napoléon III a-t-il instauré ?", "Le Second Empire", ["La IIe République", "Le Consulat", "La IIIe République"]),
    (2, "Quelle guerre a opposé le Nord et le Sud des États-Unis ?", "La guerre de Sécession", ["La guerre d'indépendance", "La guerre de 1812", "La guerre hispano-américaine"]),
    (2, "Qui commandait les troupes sudistes pendant la guerre de Sécession ?", "Robert Lee", ["Ulysses Grant", "William Sherman", "Jefferson Davis"]),
    (2, "Quel général suisse a mené l'armée fédérale lors du Sonderbund ?", "Guillaume-Henri Dufour", ["Henri Guisan", "Ulrich Wille", "Hans Herzog"]),
    (2, "Quel général commandait l'armée suisse pendant la Seconde Guerre mondiale ?", "Henri Guisan", ["Guillaume-Henri Dufour", "Ulrich Wille", "Hans Herzog"]),
    (2, "Qui a fondé la Croix-Rouge ?", "Henri Dunant", ["Florence Nightingale", "Gustave Moynier", "Clara Barton"]),
    (2, "Quelle bataille a inspiré à Henri Dunant la création de la Croix-Rouge ?", "Solférino", ["Waterloo", "Sedan", "Magenta"]),
    (2, "Quel événement a déclenché la Première Guerre mondiale ?", "L'assassinat de François-Ferdinand à Sarajevo", ["L'invasion de la Pologne", "Le naufrage du Lusitania", "La révolution russe"]),
    (2, "Comment appelait-on les soldats français de la Première Guerre mondiale ?", "Les poilus", ["Les grognards", "Les sans-culottes", "Les chasseurs"]),
    (2, "Dans quel wagon fut signé l'armistice du 11 novembre 1918 ?", "Le wagon de Rethondes (forêt de Compiègne)", ["Le wagon de l'Orient-Express", "Le wagon de Versailles", "Le wagon de Sedan"]),
    (2, "Quelle organisation internationale siégeait à Genève entre les deux guerres ?", "La Société des Nations", ["L'ONU", "L'OTAN", "L'Union européenne"]),
    (2, "Quel régime a gouverné la France occupée depuis 1940 ?", "Le régime de Vichy", ["La IVe République", "Le Front populaire", "La Commune"]),
    (2, "Qui dirigeait le régime de Vichy ?", "Le maréchal Pétain", ["Édouard Daladier", "Charles de Gaulle", "Paul Reynaud"]),
    (2, "Sous quel nom de code le débarquement en Normandie était-il connu ?", "Opération Overlord", ["Opération Barbarossa", "Opération Torch", "Opération Market Garden"]),
    (2, "Comment s'appelait l'invasion allemande de l'URSS en 1941 ?", "Opération Barbarossa", ["Opération Overlord", "Opération Dynamo", "Opération Typhon"]),
    (2, "Sur quelle ville la première bombe atomique a-t-elle été larguée ?", "Hiroshima", ["Nagasaki", "Tokyo", "Kyoto"]),
    (2, "Quel était le nom de l'avion qui a largué la bombe sur Hiroshima ?", "Enola Gay", ["Bockscar", "Memphis Belle", "Spirit of St. Louis"]),
    (2, "Où siège l'ONU, à New York et aussi en Europe à… ?", "Genève", ["Vienne", "Bruxelles", "Strasbourg"]),
    (2, "Comment appelle-t-on l'opposition entre les États-Unis et l'URSS de 1947 à 1991 ?", "La guerre froide", ["La guerre des étoiles", "La détente", "Le rideau de fer"]),
    (2, "Qui a prononcé « Ich bin ein Berliner » ?", "John F. Kennedy", ["Ronald Reagan", "Willy Brandt", "Richard Nixon"]),
    (2, "Qui a dit « I have a dream » ?", "Martin Luther King", ["Malcolm X", "Barack Obama", "Rosa Parks"]),
    (2, "Qui a été le premier président noir d'Afrique du Sud ?", "Nelson Mandela", ["Desmond Tutu", "Thabo Mbeki", "Jacob Zuma"]),
    (2, "Quel était le nom de la politique de ségrégation en Afrique du Sud ?", "L'apartheid", ["Le Jim Crow", "La partition", "Le Bantoustan"]),
    (2, "Quel dirigeant soviétique a lancé la perestroïka ?", "Mikhaïl Gorbatchev", ["Leonid Brejnev", "Boris Eltsine", "Nikita Khrouchtchev"]),
    (2, "Qui a été la première femme Première ministre du Royaume-Uni ?", "Margaret Thatcher", ["Theresa May", "Élisabeth II", "Liz Truss"]),
    (2, "Qui a été la première femme élue au Conseil fédéral suisse (1984) ?", "Elisabeth Kopp", ["Ruth Dreifuss", "Micheline Calmy-Rey", "Doris Leuthard"]),
    (2, "Qui a fait voter la loi sur l'IVG en France en 1975 ?", "Simone Veil", ["Gisèle Halimi", "Simone de Beauvoir", "Françoise Giroud"]),
    (2, "Quel ministre a fait abolir la peine de mort en France en 1981 ?", "Robert Badinter", ["Jack Lang", "Pierre Mauroy", "Laurent Fabius"]),
    (2, "Quel pays a été le premier à accorder le droit de vote aux femmes (1893) ?", "La Nouvelle-Zélande", ["La Finlande", "Le Royaume-Uni", "Les États-Unis"]),
    (3, "Quel est le dernier canton suisse à avoir accordé le droit de vote aux femmes (1990, forcé par le Tribunal fédéral) ?", "Appenzell Rhodes-Intérieures", ["Appenzell Rhodes-Extérieures", "Uri", "Glaris"]),
    (2, "Quel mur est tombé le 9 novembre 1989 ?", "Le mur de Berlin", ["Le mur d'Hadrien", "La Grande Muraille", "Le mur des Lamentations"]),
    (2, "Quel paquebot a coulé lors de son voyage inaugural en 1912 ?", "Le Titanic", ["Le Lusitania", "L'Olympic", "Le Normandie"]),
    (2, "Quel dirigeant chinois a lancé la « Révolution culturelle » ?", "Mao Zedong", ["Deng Xiaoping", "Sun Yat-sen", "Tchang Kaï-chek"]),
    (2, "Comment s'appelait le mouvement de non-violence de Gandhi ?", "La satyagraha", ["Le panchsheel", "Le dharma", "Le bhakti"]),
    (2, "Quelle marche de Gandhi protestait contre l'impôt britannique en 1930 ?", "La marche du sel", ["La marche du thé", "La marche du coton", "La marche de Delhi"]),
    (2, "Quelle reine a régné le plus longtemps sur le Royaume-Uni ?", "Élisabeth II", ["Victoria", "Élisabeth Ire", "Anne"]),
    (2, "Quel tsar a fondé Saint-Pétersbourg ?", "Pierre le Grand", ["Ivan le Terrible", "Nicolas II", "Alexandre Ier"]),
    (2, "Qui était le dernier tsar de Russie ?", "Nicolas II", ["Alexandre III", "Pierre le Grand", "Alexandre II"]),
    (2, "Quelle dynastie a régné sur la Russie jusqu'en 1917 ?", "Les Romanov", ["Les Habsbourg", "Les Hohenzollern", "Les Rurikides"]),
    (2, "Quelle dynastie régnait sur l'Autriche-Hongrie ?", "Les Habsbourg", ["Les Romanov", "Les Hohenzollern", "Les Wittelsbach"]),
    (2, "Quelle impératrice d'Autriche était surnommée « Sissi » ?", "Élisabeth de Wittelsbach", ["Marie-Thérèse", "Marie-Louise", "Zita de Bourbon-Parme"]),
    (2, "Dans quelle ville suisse l'impératrice Sissi a-t-elle été assassinée en 1898 ?", "Genève", ["Lausanne", "Montreux", "Zurich"]),
    (2, "Qui a écrit le Manifeste du parti communiste avec Engels ?", "Karl Marx", ["Lénine", "Trotski", "Proudhon"]),
    (2, "Quel navigateur portugais a été le premier à contourner l'Afrique jusqu'en Inde ?", "Vasco de Gama", ["Bartolomeu Dias", "Magellan", "Henri le Navigateur"]),
    (2, "Quel navigateur a passé le cap de Bonne-Espérance en 1488 ?", "Bartolomeu Dias", ["Vasco de Gama", "Magellan", "Cabral"]),
    (3, "Qui a découvert le Brésil pour le Portugal en 1500 ?", "Pedro Álvares Cabral", ["Vasco de Gama", "Amerigo Vespucci", "Magellan"]),
    (2, "Quel peuple scandinave a pillé les côtes européennes vers l'an 800-1000 ?", "Les Vikings", ["Les Goths", "Les Huns", "Les Vandales"]),
    (2, "Quel Viking aurait atteint l'Amérique du Nord vers l'an 1000 ?", "Leif Erikson", ["Erik le Rouge", "Ragnar Lodbrok", "Harald à la Dent bleue"]),
    (2, "Quel chef hun était surnommé « le fléau de Dieu » ?", "Attila", ["Gengis Khan", "Alaric", "Genséric"]),
    (2, "Quel empire a fondé Gengis Khan ?", "L'Empire mongol", ["L'Empire ottoman", "L'Empire perse", "L'Empire moghol"]),
    (2, "Quelle route commerciale reliait la Chine à la Méditerranée ?", "La route de la soie", ["La route des épices", "La route de l'ambre", "La voie Appienne"]),
    (2, "Quel empereur moghol a fait construire le Taj Mahal ?", "Shah Jahan", ["Akbar", "Babur", "Aurangzeb"]),
    (2, "Dans quelle ville d'Italie la Renaissance est-elle née ?", "Florence", ["Rome", "Venise", "Milan"]),
    (2, "Quelle famille a dominé Florence pendant la Renaissance ?", "Les Médicis", ["Les Borgia", "Les Sforza", "Les Visconti"]),
    (2, "Qui a inventé l'imprimerie à caractères mobiles en Europe ?", "Gutenberg", ["Érasme", "Alde Manuce", "Léonard de Vinci"]),
    (2, "Quel était le premier livre imprimé par Gutenberg ?", "La Bible", ["Le Coran", "L'Iliade", "Un dictionnaire"]),
    (2, "Quel serment fondateur de la Suisse est associé à une prairie au bord du lac des Quatre-Cantons ?", "Le serment du Grütli", ["Le serment de Morgarten", "Le serment de Sempach", "Le pacte de Brunnen"]),
    (2, "Quel héros légendaire suisse a tiré sur une pomme posée sur la tête de son fils ?", "Guillaume Tell", ["Arnold de Winkelried", "Nicolas de Flüe", "Werner Stauffacher"]),
    (2, "Quel héros suisse se serait jeté sur les lances ennemies à Sempach ?", "Arnold de Winkelried", ["Guillaume Tell", "Nicolas de Flüe", "Hans Waldmann"]),
    (2, "Quel bailli Guillaume Tell aurait-il tué ?", "Gessler", ["Habsbourg", "Stauffacher", "Landenberg"]),
    (2, "Quel ermite suisse a réconcilié les Confédérés en 1481 (convenant de Stans) ?", "Nicolas de Flüe", ["Guillaume Tell", "Zwingli", "Arnold de Winkelried"]),
    (2, "Quel duc de Bourgogne a été vaincu par les Suisses à Grandson et Morat ?", "Charles le Téméraire", ["Philippe le Bon", "Jean sans Peur", "Philippe le Hardi"]),
    (2, "En 1515, contre qui les Suisses ont-ils perdu à Marignan ?", "François Ier", ["Charles Quint", "Louis XII", "Henri II"]),
    (2, "Quelle garde suisse protège le pape depuis 1506 ?", "La Garde suisse pontificale", ["La Garde royale", "La Légion étrangère", "Les Cent-Suisses"]),
    (2, "Lors de quelle journée de 1792 des gardes suisses ont-ils été massacrés aux Tuileries ?", "Le 10 août 1792", ["Le 14 juillet 1789", "Le 21 janvier 1793", "Le 9 thermidor"]),
    (2, "Quel monument de Lucerne honore les gardes suisses tués en 1792 ?", "Le Lion de Lucerne", ["Le pont de la Chapelle", "La tour Zytglogge", "Le monument Tell"]),
]


def _years_near(y: int, rng) -> list[str]:
    deltas = [d for d in (-30, -20, -15, -10, -7, -5, -3, 3, 5, 7, 10, 15, 20, 30) if (y < 0) == (y + d < 0) or y + d < 0]
    rng.shuffle(deltas)
    return [fmt_year(y + d) for d in deltas if y + d != 0]


def generate():
    out = []
    rng = random.Random("hist")
    for y, ev in EVENTS:
        d = 1 if y in EASY_YEARS else 2 if y >= 1500 else 3
        out.append(make("histoire", f"En quelle année a eu lieu : {ev} ?", fmt_year(y), _years_near(y, random.Random(f"y-{ev}")), d))
        others = [e for yy, e in EVENTS if abs(yy - y) >= 5]
        out.append(make("histoire", f"Quel événement a eu lieu en {fmt_year(y)} ?", ev[0].upper() + ev[1:],
                        [e[0].upper() + e[1:] for e in pick(f"ev-{ev}", others, ev)], d))
    # Chronologie : lequel en premier / en dernier (écart net)
    tries = 0
    n = 0
    while n < 380 and tries < 20000:
        tries += 1
        four = rng.sample(EVENTS, 4)
        first = rng.random() < 0.55
        srt = sorted(four, key=lambda e: e[0], reverse=not first)
        if abs(srt[1][0] - srt[0][0]) < 15:
            continue
        q = make("histoire", "Lequel de ces événements s'est produit en premier ?" if first else "Lequel de ces événements est le plus récent ?",
                 srt[0][1][0].upper() + srt[0][1][1:], [e[1][0].upper() + e[1][1:] for e in srt[1:]],
                 2 if abs(srt[1][0] - srt[0][0]) > 100 else 3)
        if q:
            out.append(q)
            n += 1
    # Personnages → siècle
    for name, c in PEOPLE:
        near = [century(x) for x in (c - 2, c - 1, c + 1, c + 2) if x != 0 and -15 < x < 22]
        d = 2 if c >= 15 else 3
        out.append(make("histoire", f"À quel siècle a vécu {name} ?", century(c), pick(f"pc-{name}", near, century(c)), d))
    # Personnages : qui vivait le plus tôt ?
    n = tries = 0
    while n < 150 and tries < 20000:
        tries += 1
        four = rng.sample(PEOPLE, 4)
        srt = sorted(four, key=lambda p: p[1])
        if srt[1][1] - srt[0][1] < 2:
            continue
        q = make("histoire", "Lequel de ces personnages a vécu le plus tôt ?", srt[0][0], [p[0] for p in srt[1:]], 2)
        if q:
            out.append(q)
            n += 1
    # Présidents
    for i, p in enumerate(FR_PRESIDENTS):
        if i:
            out.append(make("histoire", f"Qui a succédé à {FR_PRESIDENTS[i - 1]} à la présidence de la République française ?", p,
                            pick(f"frp-{p}", FR_PRESIDENTS, p), 2))
        out.append(make("histoire", f"Quel numéro d'ordre a {p} parmi les présidents de la Ve République ?", f"{i + 1}{'er' if i == 0 else 'e'}",
                        pick(f"frn-{p}", [f"{k}{'er' if k == 1 else 'e'}" for k in range(1, 10)], f"{i + 1}{'er' if i == 0 else 'e'}"), 3))
    for name, y in US_PRESIDENTS:
        others = [n for n, yy in US_PRESIDENTS if abs(yy - y) >= 8]
        out.append(make("histoire", f"Quel président des États-Unis a pris ses fonctions en {y} ?", name, pick(f"usp-{name}", others, name),
                        2 if y > 1950 or name in ("George Washington", "Abraham Lincoln") else 3))
    for d, q, a, w in WRITTEN:
        out.append(make("histoire", q, a, w, d))
    return out
