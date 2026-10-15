"""Sciences : éléments chimiques, unités, formules, savants, préfixes, calcul mental, nombres premiers, et questions rédigées."""

import random

from . import make, pick

# (numéro atomique, symbole, nom)
ELEMENTS = [
    (1, "H", "Hydrogène"), (2, "He", "Hélium"), (3, "Li", "Lithium"), (4, "Be", "Béryllium"), (5, "B", "Bore"), (6, "C", "Carbone"),
    (7, "N", "Azote"), (8, "O", "Oxygène"), (9, "F", "Fluor"), (10, "Ne", "Néon"), (11, "Na", "Sodium"), (12, "Mg", "Magnésium"),
    (13, "Al", "Aluminium"), (14, "Si", "Silicium"), (15, "P", "Phosphore"), (16, "S", "Soufre"), (17, "Cl", "Chlore"), (18, "Ar", "Argon"),
    (19, "K", "Potassium"), (20, "Ca", "Calcium"), (21, "Sc", "Scandium"), (22, "Ti", "Titane"), (23, "V", "Vanadium"), (24, "Cr", "Chrome"),
    (25, "Mn", "Manganèse"), (26, "Fe", "Fer"), (27, "Co", "Cobalt"), (28, "Ni", "Nickel"), (29, "Cu", "Cuivre"), (30, "Zn", "Zinc"),
    (31, "Ga", "Gallium"), (32, "Ge", "Germanium"), (33, "As", "Arsenic"), (34, "Se", "Sélénium"), (35, "Br", "Brome"), (36, "Kr", "Krypton"),
    (37, "Rb", "Rubidium"), (38, "Sr", "Strontium"), (39, "Y", "Yttrium"), (40, "Zr", "Zirconium"), (41, "Nb", "Niobium"), (42, "Mo", "Molybdène"),
    (43, "Tc", "Technétium"), (44, "Ru", "Ruthénium"), (45, "Rh", "Rhodium"), (46, "Pd", "Palladium"), (47, "Ag", "Argent"), (48, "Cd", "Cadmium"),
    (49, "In", "Indium"), (50, "Sn", "Étain"), (51, "Sb", "Antimoine"), (52, "Te", "Tellure"), (53, "I", "Iode"), (54, "Xe", "Xénon"),
    (55, "Cs", "Césium"), (56, "Ba", "Baryum"), (57, "La", "Lanthane"), (58, "Ce", "Cérium"), (59, "Pr", "Praséodyme"), (60, "Nd", "Néodyme"),
    (61, "Pm", "Prométhium"), (62, "Sm", "Samarium"), (63, "Eu", "Europium"), (64, "Gd", "Gadolinium"), (65, "Tb", "Terbium"), (66, "Dy", "Dysprosium"),
    (67, "Ho", "Holmium"), (68, "Er", "Erbium"), (69, "Tm", "Thulium"), (70, "Yb", "Ytterbium"), (71, "Lu", "Lutécium"), (72, "Hf", "Hafnium"),
    (73, "Ta", "Tantale"), (74, "W", "Tungstène"), (75, "Re", "Rhénium"), (76, "Os", "Osmium"), (77, "Ir", "Iridium"), (78, "Pt", "Platine"),
    (79, "Au", "Or"), (80, "Hg", "Mercure"), (81, "Tl", "Thallium"), (82, "Pb", "Plomb"), (83, "Bi", "Bismuth"), (84, "Po", "Polonium"),
    (85, "At", "Astate"), (86, "Rn", "Radon"), (87, "Fr", "Francium"), (88, "Ra", "Radium"), (89, "Ac", "Actinium"), (90, "Th", "Thorium"),
    (91, "Pa", "Protactinium"), (92, "U", "Uranium"), (93, "Np", "Neptunium"), (94, "Pu", "Plutonium"), (95, "Am", "Américium"), (96, "Cm", "Curium"),
    (97, "Bk", "Berkélium"), (98, "Cf", "Californium"), (99, "Es", "Einsteinium"), (100, "Fm", "Fermium"), (101, "Md", "Mendélévium"), (102, "No", "Nobélium"),
    (103, "Lr", "Lawrencium"), (104, "Rf", "Rutherfordium"), (105, "Db", "Dubnium"), (106, "Sg", "Seaborgium"), (107, "Bh", "Bohrium"), (108, "Hs", "Hassium"),
    (109, "Mt", "Meitnérium"), (110, "Ds", "Darmstadtium"), (111, "Rg", "Roentgenium"), (112, "Cn", "Copernicium"), (113, "Nh", "Nihonium"), (114, "Fl", "Flérovium"),
    (115, "Mc", "Moscovium"), (116, "Lv", "Livermorium"), (117, "Ts", "Tennesse"), (118, "Og", "Oganesson"),
]
FAMOUS_EL = {1, 2, 6, 7, 8, 11, 17, 20, 26, 29, 47, 79, 80, 82, 92, 13, 10, 19, 30, 78, 50, 53, 9, 12, 16, 15, 14, 18, 22, 28}

# Grandeur → unité SI (ou usuelle)
UNITS = [
    ("la force", "le newton"), ("l'énergie", "le joule"), ("la puissance", "le watt"), ("la pression", "le pascal"), ("la fréquence", "le hertz"),
    ("la tension électrique", "le volt"), ("l'intensité électrique", "l'ampère"), ("la résistance électrique", "l'ohm"), ("la charge électrique", "le coulomb"),
    ("la capacité électrique", "le farad"), ("la température (SI)", "le kelvin"), ("la quantité de matière", "la mole"), ("l'intensité lumineuse", "la candela"),
    ("la masse (SI)", "le kilogramme"), ("le temps (SI)", "la seconde"), ("la longueur (SI)", "le mètre"), ("le champ magnétique", "le tesla"),
    ("la radioactivité (activité)", "le becquerel"), ("la dose de rayonnement absorbée", "le gray"), ("le flux lumineux", "le lumen"),
    ("l'éclairement", "le lux"), ("l'inductance", "le henry"), ("le flux magnétique", "le weber"), ("l'intensité sonore (niveau)", "le décibel"),
]
SYMBOLS = [("le newton", "N"), ("le joule", "J"), ("le watt", "W"), ("le pascal", "Pa"), ("le hertz", "Hz"), ("le volt", "V"), ("l'ampère", "A"),
           ("l'ohm", "Ω"), ("le kelvin", "K"), ("la mole", "mol"), ("la candela", "cd"), ("le coulomb", "C"), ("le tesla", "T"), ("le becquerel", "Bq"),
           ("le lux", "lx"), ("le farad", "F"), ("le henry", "H"), ("le weber", "Wb"), ("le lumen", "lm"), ("le gray", "Gy")]

PREFIXES = [("kilo", "10³ (mille)"), ("méga", "10⁶ (un million)"), ("giga", "10⁹ (un milliard)"), ("téra", "10¹² (mille milliards)"),
            ("milli", "10⁻³ (un millième)"), ("micro", "10⁻⁶ (un millionième)"), ("nano", "10⁻⁹ (un milliardième)"), ("pico", "10⁻¹²"),
            ("centi", "10⁻² (un centième)"), ("déci", "10⁻¹ (un dixième)"), ("hecto", "10² (cent)"), ("déca", "10 (dix)"), ("péta", "10¹⁵")]

# Formule → nom
FORMULAS = [
    ("H₂O", "L'eau"), ("CO₂", "Le dioxyde de carbone"), ("NaCl", "Le chlorure de sodium (sel de table)"), ("O₂", "Le dioxygène"),
    ("O₃", "L'ozone"), ("CH₄", "Le méthane"), ("NH₃", "L'ammoniac"), ("H₂SO₄", "L'acide sulfurique"), ("HCl", "L'acide chlorhydrique"),
    ("CO", "Le monoxyde de carbone"), ("C₆H₁₂O₆", "Le glucose"), ("C₂H₅OH", "L'éthanol"), ("CaCO₃", "Le carbonate de calcium (calcaire)"),
    ("NaHCO₃", "Le bicarbonate de sodium"), ("H₂O₂", "Le peroxyde d'hydrogène (eau oxygénée)"), ("N₂", "Le diazote"), ("NaOH", "La soude (hydroxyde de sodium)"),
    ("HNO₃", "L'acide nitrique"), ("SO₂", "Le dioxyde de soufre"), ("C₁₂H₂₂O₁₁", "Le saccharose (sucre)"), ("Fe₂O₃", "L'oxyde de fer (rouille)"),
    ("SiO₂", "La silice (quartz)"), ("C₃H₈", "Le propane"), ("C₄H₁₀", "Le butane"), ("NO₂", "Le dioxyde d'azote"), ("H₂", "Le dihydrogène"),
    ("CH₃COOH", "L'acide acétique (vinaigre)"), ("KCl", "Le chlorure de potassium"), ("C₈H₁₀N₄O₂", "La caféine"), ("CaO", "La chaux vive (oxyde de calcium)"),
]

# Savant → découverte ou travaux
SCIENTISTS = [
    ("Isaac Newton", "La gravitation universelle"), ("Albert Einstein", "La relativité"), ("Charles Darwin", "La théorie de l'évolution"),
    ("Marie Curie", "Le radium et le polonium"), ("Louis Pasteur", "Le vaccin contre la rage"), ("Galilée", "Les lunes de Jupiter"),
    ("Nicolas Copernic", "L'héliocentrisme"), ("Johannes Kepler", "Les lois du mouvement des planètes"), ("Gregor Mendel", "Les lois de l'hérédité"),
    ("Alexander Fleming", "La pénicilline"), ("Dmitri Mendeleïev", "Le tableau périodique des éléments"), ("Antoine Lavoisier", "La conservation de la masse"),
    ("Archimède", "La poussée d'un fluide sur un corps immergé"), ("Michael Faraday", "L'induction électromagnétique"), ("James Clerk Maxwell", "Les équations de l'électromagnétisme"),
    ("Edwin Hubble", "L'expansion de l'Univers"), ("Max Planck", "Les quanta d'énergie"), ("Niels Bohr", "Le modèle de l'atome à couches"),
    ("Ernest Rutherford", "Le noyau atomique"), ("Wilhelm Röntgen", "Les rayons X"), ("Henri Becquerel", "La radioactivité"),
    ("Edward Jenner", "La vaccination contre la variole"), ("Robert Koch", "Le bacille de la tuberculose"), ("James Watson et Francis Crick", "La structure en double hélice de l'ADN"),
    ("Alfred Wegener", "La dérive des continents"), ("Blaise Pascal", "La pression atmosphérique et la machine à calculer"), ("Pythagore", "Le théorème sur le triangle rectangle"),
    ("Thalès", "Le théorème des droites parallèles coupant deux sécantes"), ("Euclide", "Les Éléments de géométrie"), ("Carl von Linné", "La classification des espèces"),
    ("Werner Heisenberg", "Le principe d'incertitude"), ("Erwin Schrödinger", "L'équation d'onde quantique"), ("Stephen Hawking", "Le rayonnement des trous noirs"),
    ("Nikola Tesla", "Le courant alternatif"), ("Thomas Edison", "L'ampoule à incandescence commerciale"), ("Alessandro Volta", "La pile électrique"),
    ("André-Marie Ampère", "L'électrodynamique"), ("Georg Ohm", "La loi reliant tension, courant et résistance"), ("Anders Celsius", "Une échelle de température à 100 degrés"),
    ("Daniel Gabriel Fahrenheit", "Le thermomètre à mercure"), ("Christian Huygens", "Les anneaux de Saturne (leur nature)"), ("William Harvey", "La circulation sanguine"),
    ("Claude Bernard", "La médecine expérimentale"), ("Rosalind Franklin", "Les clichés aux rayons X de l'ADN"), ("Lise Meitner", "La fission nucléaire (son explication)"),
    ("Jean-Baptiste de Lamarck", "Le transformisme (hérédité des caractères acquis)"), ("Georges Cuvier", "La paléontologie et l'anatomie comparée"),
    ("René Descartes", "Le repère cartésien"), ("Leonhard Euler", "La notation e et la formule e^(iπ) + 1 = 0"), ("Évariste Galois", "La théorie des groupes en algèbre"),
    ("Alan Turing", "La machine de Turing"), ("Ada Lovelace", "Le premier programme informatique"), ("Hippocrate", "Le serment des médecins"),
    ("Tim Berners-Lee", "Le World Wide Web"), ("Benjamin Franklin", "Le paratonnerre"), ("Joseph Fourier", "Les séries trigonométriques"),
    ("Pierre-Simon de Laplace", "La mécanique céleste"), ("Robert Hooke", "La cellule (le mot) et la loi de l'élasticité"), ("Antoni van Leeuwenhoek", "Les micro-organismes au microscope"),
]

# Questions rédigées (difficulté, question, bonne, 3 mauvaises)
WRITTEN = [
    (1, "Quelle est la formule de l'eau ?", "H₂O", ["CO₂", "O₂", "H₂O₂"]),
    (1, "À quelle température l'eau bout-elle au niveau de la mer ?", "100 °C", ["90 °C", "110 °C", "120 °C"]),
    (1, "À quelle température l'eau gèle-t-elle ?", "0 °C", ["-10 °C", "4 °C", "-4 °C"]),
    (1, "Quel gaz les plantes absorbent-elles pour la photosynthèse ?", "Le dioxyde de carbone", ["L'oxygène", "L'azote", "L'hélium"]),
    (1, "Quel gaz les plantes rejettent-elles grâce à la photosynthèse ?", "L'oxygène", ["Le dioxyde de carbone", "Le méthane", "L'azote"]),
    (1, "Quel est le gaz le plus abondant dans l'air ?", "L'azote", ["L'oxygène", "Le dioxyde de carbone", "L'argon"]),
    (2, "Quelle part de l'air environ est de l'oxygène ?", "21 %", ["10 %", "50 %", "78 %"]),
    (1, "Quelle est la vitesse de la lumière dans le vide, environ ?", "300 000 km/s", ["30 000 km/s", "3 000 km/s", "3 000 000 km/s"]),
    (2, "Quelle est la vitesse du son dans l'air, environ ?", "340 m/s", ["34 m/s", "3 400 m/s", "1 200 m/s"]),
    (2, "Que mesure l'échelle de Richter ?", "La magnitude des séismes", ["La force du vent", "La dureté des minéraux", "L'acidité"]),
    (2, "Que mesure l'échelle de Mohs ?", "La dureté des minéraux", ["Les séismes", "La force du vent", "La température"]),
    (2, "Que mesure l'échelle de Beaufort ?", "La force du vent", ["Les séismes", "La dureté des minéraux", "L'acidité"]),
    (1, "Quel est le minéral le plus dur ?", "Le diamant", ["Le quartz", "Le rubis", "Le fer"]),
    (2, "Que mesure le pH ?", "L'acidité ou la basicité", ["La pression", "La dureté de l'eau", "La salinité"]),
    (2, "Quel est le pH d'une solution neutre ?", "7", ["0", "14", "1"]),
    (2, "Un pH de 2 indique une solution…", "Acide", ["Basique", "Neutre", "Salée"]),
    (1, "Quelle est la formule du gaz carbonique ?", "CO₂", ["CO", "C₂O", "H₂O"]),
    (2, "Quelle particule a une charge électrique négative ?", "L'électron", ["Le proton", "Le neutron", "Le photon"]),
    (2, "Quelle particule du noyau n'a pas de charge électrique ?", "Le neutron", ["Le proton", "L'électron", "Le positron"]),
    (2, "Comment s'appelle le passage de l'état solide à l'état gazeux directement ?", "La sublimation", ["La fusion", "La condensation", "L'évaporation"]),
    (2, "Comment s'appelle le passage de l'état gazeux à l'état liquide ?", "La liquéfaction (condensation)", ["La sublimation", "La fusion", "La solidification"]),
    (1, "Comment s'appelle le passage de l'état solide à l'état liquide ?", "La fusion", ["La solidification", "La vaporisation", "La sublimation"]),
    (2, "Quel métal est liquide à température ambiante ?", "Le mercure", ["Le plomb", "L'étain", "Le sodium"]),
    (2, "Quel est le métal le plus conducteur d'électricité ?", "L'argent", ["Le cuivre", "L'or", "L'aluminium"]),
    (2, "Quel métal est le plus utilisé dans les fils électriques ?", "Le cuivre", ["L'argent", "Le fer", "Le zinc"]),
    (2, "Quel est l'alliage du cuivre et de l'étain ?", "Le bronze", ["Le laiton", "L'acier", "Le fer blanc"]),
    (2, "Quel est l'alliage du cuivre et du zinc ?", "Le laiton", ["Le bronze", "L'acier", "Le duralumin"]),
    (2, "L'acier est un alliage de fer et de…", "Carbone", ["Cuivre", "Étain", "Zinc"]),
    (1, "Combien de côtés a un hexagone ?", "6", ["5", "7", "8"]),
    (1, "Combien de côtés a un octogone ?", "8", ["6", "9", "10"]),
    (2, "Combien de côtés a un dodécagone ?", "12", ["10", "11", "20"]),
    (1, "Combien de degrés mesure la somme des angles d'un triangle ?", "180°", ["90°", "360°", "270°"]),
    (2, "Combien de degrés mesure la somme des angles d'un quadrilatère ?", "360°", ["180°", "270°", "540°"]),
    (1, "Quelle est la valeur approchée de π ?", "3,14", ["2,71", "1,61", "3,41"]),
    (2, "Quelle est la valeur approchée du nombre d'or ?", "1,618", ["3,14", "2,718", "1,414"]),
    (2, "Quelle est la valeur approchée de √2 ?", "1,414", ["1,732", "1,618", "2,236"]),
    (2, "Quelle est la valeur approchée du nombre e ?", "2,718", ["3,141", "1,618", "1,414"]),
    (1, "Comment s'appelle un angle de 90° ?", "Un angle droit", ["Un angle aigu", "Un angle obtus", "Un angle plat"]),
    (1, "Comment s'appelle un angle de 180° ?", "Un angle plat", ["Un angle droit", "Un angle obtus", "Un angle plein"]),
    (2, "Quelle est la formule de l'aire d'un disque ?", "π × r²", ["2 × π × r", "π × d", "4 × π × r²"]),
    (2, "Quelle est la formule du périmètre d'un cercle ?", "2 × π × r", ["π × r²", "4 × r", "π × r³"]),
    (2, "Dans un triangle rectangle, que dit le théorème de Pythagore ?", "a² + b² = c²", ["a + b = c", "a × b = c²", "a² − b² = c"]),
    (2, "Combien vaut 0! (factorielle de zéro) ?", "1", ["0", "Indéfini", "10"]),
    (2, "Combien de faces a un cube ?", "6", ["4", "8", "12"]),
    (2, "Combien d'arêtes a un cube ?", "12", ["6", "8", "10"]),
    (2, "Combien de sommets a un cube ?", "8", ["6", "10", "12"]),
    (3, "Combien de faces a un icosaèdre ?", "20", ["12", "16", "24"]),
    (2, "Comment appelle-t-on un nombre divisible seulement par 1 et par lui-même ?", "Un nombre premier", ["Un nombre parfait", "Un nombre pair", "Un carré parfait"]),
    (2, "Quel est le seul nombre premier pair ?", "2", ["4", "0", "1"]),
    (3, "Quel est le plus petit nombre parfait ?", "6", ["28", "1", "12"]),
    (2, "En binaire, comment s'écrit 5 ?", "101", ["110", "111", "100"]),
    (2, "En binaire, comment s'écrit 8 ?", "1000", ["111", "1001", "10000"]),
    (2, "Combien de bits dans un octet ?", "8", ["4", "16", "10"]),
    (2, "Que signifie l'abréviation ADN ?", "Acide désoxyribonucléique", ["Acide dinucléique", "Atome de nucléotide", "Acide diribonucléique"]),
    (2, "Combien de bases différentes composent l'ADN ?", "4", ["2", "3", "20"]),
    (2, "Quelle base n'existe pas dans l'ADN mais dans l'ARN ?", "L'uracile", ["La thymine", "La guanine", "L'adénine"]),
    (1, "Quel organite produit l'énergie de la cellule ?", "La mitochondrie", ["Le noyau", "Le ribosome", "La vacuole"]),
    (2, "Où se déroule la photosynthèse dans la cellule végétale ?", "Dans les chloroplastes", ["Dans les mitochondries", "Dans le noyau", "Dans les ribosomes"]),
    (2, "Quel pigment donne aux plantes leur couleur verte ?", "La chlorophylle", ["La mélanine", "Le carotène", "L'hémoglobine"]),
    (2, "Comment appelle-t-on un animal qui mange de tout ?", "Omnivore", ["Herbivore", "Carnivore", "Insectivore"]),
    (2, "Quelle force nous maintient au sol ?", "La gravité", ["Le magnétisme", "La friction", "La force centrifuge"]),
    (2, "Quelle est l'accélération de la pesanteur sur Terre, environ ?", "9,81 m/s²", ["1,62 m/s²", "98,1 m/s²", "3,71 m/s²"]),
    (2, "Quelle est la formule de l'énergie selon Einstein ?", "E = mc²", ["E = mv", "E = ½mv²", "E = hν²"]),
    (2, "Quelle est la formule de la loi d'Ohm ?", "U = R × I", ["P = U × I", "F = m × a", "E = m × c²"]),
    (2, "Quelle est la deuxième loi de Newton ?", "F = m × a", ["E = mc²", "U = R × I", "P = m × g × h"]),
    (2, "Quelle couleur a la plus grande longueur d'onde dans le spectre visible ?", "Le rouge", ["Le violet", "Le vert", "Le bleu"]),
    (2, "Quelles sont les trois couleurs primaires de la lumière ?", "Rouge, vert, bleu", ["Rouge, jaune, bleu", "Cyan, magenta, jaune", "Rouge, orange, jaune"]),
    (2, "Comment s'appelle la décomposition de la lumière blanche en couleurs ?", "La dispersion", ["La réfraction totale", "La diffraction", "La polarisation"]),
    (2, "Quel instrument mesure la pression atmosphérique ?", "Le baromètre", ["Le thermomètre", "L'hygromètre", "L'anémomètre"]),
    (2, "Quel instrument mesure l'humidité de l'air ?", "L'hygromètre", ["Le baromètre", "Le pluviomètre", "L'anémomètre"]),
    (2, "Quel instrument mesure la vitesse du vent ?", "L'anémomètre", ["Le baromètre", "L'hygromètre", "Le sismographe"]),
    (2, "Quel instrument enregistre les séismes ?", "Le sismographe", ["Le baromètre", "L'anémomètre", "Le gyroscope"]),
    (2, "Quel instrument mesure l'intensité électrique ?", "L'ampèremètre", ["Le voltmètre", "L'ohmmètre", "Le wattmètre"]),
    (2, "Quel instrument mesure la tension électrique ?", "Le voltmètre", ["L'ampèremètre", "Le galvanomètre", "Le baromètre"]),
    (2, "Que mesure un pluviomètre ?", "La quantité de pluie", ["La vitesse du vent", "La pression", "L'humidité"]),
    (2, "Quelle est la plus petite unité de la vie ?", "La cellule", ["L'atome", "La molécule", "Le gène"]),
    (2, "Comment s'appelle la science qui étudie les fossiles ?", "La paléontologie", ["L'archéologie", "La géologie", "L'entomologie"]),
    (2, "Comment s'appelle la science qui étudie les insectes ?", "L'entomologie", ["L'ornithologie", "L'ichtyologie", "L'herpétologie"]),
    (2, "Comment s'appelle la science qui étudie les oiseaux ?", "L'ornithologie", ["L'entomologie", "L'ichtyologie", "La mammalogie"]),
    (3, "Comment s'appelle la science qui étudie les poissons ?", "L'ichtyologie", ["L'ornithologie", "L'herpétologie", "La malacologie"]),
    (3, "Comment s'appelle la science qui étudie les reptiles et amphibiens ?", "L'herpétologie", ["L'ichtyologie", "L'entomologie", "L'ornithologie"]),
    (2, "Comment s'appelle la science qui étudie les champignons ?", "La mycologie", ["La botanique", "La virologie", "La bactériologie"]),
    (2, "Comment s'appelle la science qui étudie les volcans ?", "La volcanologie", ["La sismologie", "La géologie", "La météorologie"]),
    (2, "Quelle science étudie et prévoit le temps qu'il fait ?", "La météorologie", ["L'hydrologie", "La sismologie", "L'océanographie"]),
    (2, "Comment s'appelle la science qui étudie les plantes ?", "La botanique", ["La zoologie", "L'écologie", "La mycologie"]),
    (2, "Comment appelle-t-on un mélange homogène d'un solide dissous dans un liquide ?", "Une solution", ["Une suspension", "Une émulsion", "Un alliage"]),
    (2, "Comment appelle-t-on un mélange d'huile et d'eau finement dispersé ?", "Une émulsion", ["Une solution", "Un alliage", "Une dissolution"]),
    (2, "Quel est le nom du point de température le plus bas possible ?", "Le zéro absolu", ["Le point triple", "Le point critique", "Le point de rosée"]),
    (2, "À combien de degrés Celsius correspond le zéro absolu ?", "-273,15 °C", ["-100 °C", "-459,67 °C", "-180 °C"]),
    (2, "À quelle température Celsius correspondent 32 °F ?", "0 °C", ["32 °C", "-32 °C", "10 °C"]),
    (2, "À quelle température Fahrenheit bout l'eau ?", "212 °F", ["100 °F", "180 °F", "373 °F"]),
    (2, "Quel gaz donne leur couleur aux enseignes lumineuses rouge-orangé ?", "Le néon", ["L'argon", "L'hélium", "Le krypton"]),
    (2, "Quel gaz fait gonfler les ballons qui s'envolent ?", "L'hélium", ["L'hydrogène", "Le néon", "Le méthane"]),
    (2, "Quel gaz est responsable du « trou » dans la couche d'ozone (via les CFC) ?", "Le chlore", ["Le carbone", "L'azote", "Le soufre"]),
    (2, "Quel est le principal gaz à effet de serre émis par l'homme ?", "Le dioxyde de carbone", ["L'oxygène", "L'azote", "L'argon"]),
    (2, "Quelle est l'unité de mesure des séismes la plus connue ?", "La magnitude (échelle de Richter)", ["Le décibel", "Le pascal", "Le newton"]),
    (2, "Quelle énergie est produite par les éoliennes ?", "L'énergie électrique à partir du vent", ["L'énergie nucléaire", "L'énergie géothermique", "L'énergie marémotrice"]),
    (2, "Comment s'appelle l'énergie tirée de la chaleur de la Terre ?", "La géothermie", ["L'hydraulique", "La biomasse", "L'énergie marémotrice"]),
    (2, "Comment s'appelle l'énergie tirée des marées ?", "L'énergie marémotrice", ["La géothermie", "L'hydroélectricité", "L'énergie solaire"]),
    (2, "Quel est le principal combustible des centrales nucléaires ?", "L'uranium", ["Le charbon", "Le thorium", "Le radium"]),
    (2, "Comment s'appelle la réaction qui alimente le Soleil ?", "La fusion nucléaire", ["La fission nucléaire", "La combustion", "La radioactivité"]),
    (2, "Comment s'appelle la réaction utilisée dans les centrales nucléaires actuelles ?", "La fission nucléaire", ["La fusion nucléaire", "La combustion", "L'électrolyse"]),
    (2, "Quel scientifique a formulé les trois lois du mouvement ?", "Isaac Newton", ["Galilée", "Albert Einstein", "Johannes Kepler"]),
    (3, "Combien de chromosomes possède une cellule humaine (non sexuelle) ?", "46", ["23", "44", "48"]),
    (2, "Quelle est la molécule qui transporte l'information génétique ?", "L'ADN", ["L'ATP", "L'hémoglobine", "Le glucose"]),
    (3, "Quelle molécule est la « monnaie énergétique » de la cellule ?", "L'ATP", ["L'ADN", "Le glucose", "L'ARN"]),
    (2, "Quel type de rayonnement permet de voir les os à l'hôpital ?", "Les rayons X", ["Les ultraviolets", "Les infrarouges", "Les micro-ondes"]),
    (2, "Quels rayons provoquent les coups de soleil ?", "Les ultraviolets", ["Les infrarouges", "Les rayons X", "Les ondes radio"]),
    (2, "Quels rayons nos télécommandes de télé utilisent-elles ?", "Les infrarouges", ["Les ultraviolets", "Les rayons X", "Les rayons gamma"]),
    (2, "Quel appareil de cuisine utilise des ondes pour chauffer les aliments ?", "Le four à micro-ondes", ["Le four à induction", "Le grille-pain", "La plaque vitrocéramique"]),
    (2, "Quel est le symbole chimique de l'or ?", "Au", ["Or", "Ag", "Go"]),
    (2, "Quel est le symbole chimique du sodium ?", "Na", ["So", "Sd", "S"]),
    (2, "Quel est le symbole chimique du potassium ?", "K", ["P", "Po", "Pt"]),
    (2, "Quel est le symbole chimique du fer ?", "Fe", ["F", "Fr", "Ir"]),
    (2, "Quel est le symbole chimique de l'argent ?", "Ag", ["Ar", "Au", "Sv"]),
    (2, "Quel est le symbole chimique du plomb ?", "Pb", ["Pl", "Po", "P"]),
    (2, "Quel est le symbole chimique du mercure ?", "Hg", ["Me", "Mr", "Hy"]),
    (3, "Quel est l'élément le plus abondant dans l'Univers ?", "L'hydrogène", ["L'hélium", "L'oxygène", "Le carbone"]),
    (3, "Quel est l'élément le plus abondant dans la croûte terrestre ?", "L'oxygène", ["Le silicium", "Le fer", "L'aluminium"]),
    (2, "Quel élément est à la base de toute la chimie organique ?", "Le carbone", ["L'azote", "Le silicium", "L'hydrogène"]),
    (3, "Combien d'éléments compte le tableau périodique (2024) ?", "118", ["108", "112", "126"]),
    (2, "Comment s'appellent les éléments de la dernière colonne du tableau périodique ?", "Les gaz nobles", ["Les halogènes", "Les métaux alcalins", "Les lanthanides"]),
    (3, "Comment s'appellent les éléments de la première colonne (sauf l'hydrogène) ?", "Les métaux alcalins", ["Les gaz nobles", "Les halogènes", "Les alcalino-terreux"]),
    (3, "Le fluor, le chlore, le brome et l'iode sont des…", "Halogènes", ["Gaz nobles", "Métaux alcalins", "Métalloïdes"]),
    (2, "Quelle est la forme de la molécule d'ADN ?", "Une double hélice", ["Une simple chaîne", "Un anneau", "Une sphère"]),
    (2, "Qui a proposé la classification périodique des éléments en 1869 ?", "Dmitri Mendeleïev", ["Antoine Lavoisier", "Marie Curie", "John Dalton"]),
    (2, "Quelle scientifique a reçu deux prix Nobel dans deux sciences différentes ?", "Marie Curie", ["Rosalind Franklin", "Lise Meitner", "Irène Joliot-Curie"]),
    (2, "En quelle année Einstein a-t-il publié la relativité restreinte ?", "1905", ["1915", "1895", "1921"]),
    (3, "En quelle année Darwin a-t-il publié « De l'origine des espèces » ?", "1859", ["1809", "1871", "1899"]),
    (2, "Quel animal a été le premier mammifère cloné (1996) ?", "La brebis Dolly", ["La souris Mickey", "Le chien Laïka", "La vache Marguerite"]),
    (2, "Comment s'appelle le grand accélérateur de particules du CERN près de Genève ?", "Le LHC", ["L'ITER", "Le SLAC", "Le Tevatron"]),
    (3, "Quelle particule a été découverte au CERN en 2012 ?", "Le boson de Higgs", ["Le quark top", "Le neutrino", "Le graviton"]),
    (2, "Dans quelle ville est né le World Wide Web, au CERN ?", "Genève (Meyrin)", ["Zurich", "Lausanne", "Bâle"]),
    (2, "Quelle est la plus grande planète du Système solaire ?", "Jupiter", ["Saturne", "Neptune", "La Terre"]),
    (2, "Combien de temps met la lumière du Soleil pour arriver sur Terre ?", "Environ 8 minutes", ["Environ 8 secondes", "Environ 1 heure", "Environ 1 jour"]),
    (1, "Que produit un aimant ?", "Un champ magnétique", ["Un champ électrique", "De la lumière", "De la chaleur"]),
    (2, "Les pôles identiques de deux aimants…", "Se repoussent", ["S'attirent", "S'annulent", "N'interagissent pas"]),
    (2, "Quel métal est attiré par un aimant ?", "Le fer", ["Le cuivre", "L'aluminium", "L'or"]),
    (2, "Comment s'appelle un matériau qui ne conduit pas l'électricité ?", "Un isolant", ["Un conducteur", "Un semi-conducteur", "Un électrolyte"]),
    (2, "Quel matériau semi-conducteur est à la base des puces électroniques ?", "Le silicium", ["Le cuivre", "Le germanium seul", "Le carbone"]),
    (2, "Que signifie l'abréviation LED ?", "Diode électroluminescente", ["Lampe à économie d'énergie", "Laser électronique diffus", "Lumière électrique directe"]),
    (2, "Quel est le nom du changement d'une chenille en papillon ?", "La métamorphose", ["La mue", "La mitose", "La photosynthèse"]),
    (2, "Comment s'appelle la division d'une cellule en deux cellules identiques ?", "La mitose", ["La méiose", "La fécondation", "L'osmose"]),
    (3, "Comment s'appelle la division cellulaire qui produit les gamètes ?", "La méiose", ["La mitose", "La scissiparité", "La transcription"]),
    (2, "Quel est le passage de l'eau à travers une membrane, du moins concentré vers le plus concentré ?", "L'osmose", ["La diffusion", "La filtration", "La distillation"]),
    (2, "Comment sépare-t-on l'eau et le sel par chauffage puis condensation ?", "Par distillation", ["Par filtration", "Par décantation", "Par centrifugation"]),
    (2, "Quelle loi dit « Rien ne se perd, rien ne se crée, tout se transforme » ?", "La loi de Lavoisier", ["La loi de Newton", "La loi d'Ohm", "La loi de Boyle"]),
    (2, "Qui aurait crié « Eurêka ! » dans son bain ?", "Archimède", ["Pythagore", "Euclide", "Thalès"]),
    (2, "Qui a eu l'idée de la gravitation en voyant (selon la légende) tomber une pomme ?", "Isaac Newton", ["Galilée", "Albert Einstein", "René Descartes"]),
    (2, "Quel savant aurait lâché des objets du haut de la tour de Pise ?", "Galilée", ["Newton", "Copernic", "Kepler"]),
    (2, "Quel est l'os le plus long du corps humain ?", "Le fémur", ["Le tibia", "L'humérus", "Le radius"]),
    (2, "Combien de temps met la Terre pour tourner sur elle-même ?", "Environ 24 heures", ["Environ 365 jours", "Environ 12 heures", "Environ 28 jours"]),
    (2, "Comment s'appelle l'unité de l'information quantique ?", "Le qubit", ["Le quark", "Le quantum", "Le bit quantifié"]),
    (2, "Quel est le plus grand nombre premier inférieur à 100 ?", "97", ["99", "91", "89"]),
    (2, "Combien vaut la racine carrée de 144 ?", "12", ["14", "11", "13"]),
    (2, "Combien vaut 2 puissance 10 ?", "1024", ["1000", "512", "2048"]),
    (2, "Combien de zéros compte un milliard ?", "9", ["6", "12", "10"]),
    (2, "Combien de zéros compte un million ?", "6", ["5", "7", "9"]),
    (3, "Comment appelle-t-on un nombre suivi de 100 zéros ?", "Un gogol", ["Un milliard de milliards", "Un googolplex", "Un trillion"]),
    (2, "Quelle est la suite où chaque nombre est la somme des deux précédents ?", "La suite de Fibonacci", ["La suite de Syracuse", "La suite arithmétique", "La suite de Pascal"]),
    (2, "Comment appelle-t-on un triangle dont les trois côtés sont égaux ?", "Équilatéral", ["Isocèle", "Rectangle", "Scalène"]),
    (2, "Comment appelle-t-on un triangle qui a deux côtés égaux ?", "Isocèle", ["Équilatéral", "Scalène", "Rectangle"]),
    (2, "Comment s'appelle le côté opposé à l'angle droit d'un triangle rectangle ?", "L'hypoténuse", ["La médiane", "La bissectrice", "La hauteur"]),
    (2, "Comment appelle-t-on un quadrilatère avec 4 angles droits et 4 côtés égaux ?", "Un carré", ["Un losange", "Un rectangle", "Un trapèze"]),
    (2, "Combien de minutes y a-t-il dans une journée ?", "1440", ["1200", "3600", "720"]),
    (2, "Combien de secondes y a-t-il dans une heure ?", "3600", ["360", "6000", "1440"]),
    (3, "Combien de secondes y a-t-il dans une journée ?", "86 400", ["36 000", "60 000", "144 000"]),
    (2, "Combien de litres contient un mètre cube ?", "1000", ["100", "10", "10 000"]),
    (2, "Combien de centimètres cubes dans un litre ?", "1000", ["100", "10", "10 000"]),
    (2, "Combien de mètres carrés dans un hectare ?", "10 000", ["1000", "100", "100 000"]),
    (2, "Combien de grammes dans une livre (en Europe, usage courant) ?", "500", ["450", "1000", "250"]),
    (3, "Combien de centimètres mesure un pouce ?", "2,54 cm", ["2 cm", "3,14 cm", "1,6 cm"]),
    (3, "Combien de kilomètres mesure un mille terrestre (anglais) ?", "1,609 km", ["1,852 km", "1 km", "2 km"]),
    (3, "Combien de mètres mesure un mille marin ?", "1852 m", ["1609 m", "1000 m", "2000 m"]),
    (2, "Combien de nœuds représente une vitesse d'un mille marin par heure ?", "1", ["1,852", "10", "0,5"]),
]


def _calc(rng, i):
    """Calcul mental : tables, multiplications, carrés, pourcentages (toujours justes, mauvaises réponses proches)."""
    kind = i % 5
    if kind == 0:
        a, b = rng.randint(6, 19), rng.randint(6, 19)
        q, ans, d = f"Combien font {a} × {b} ?", a * b, 1 if max(a, b) < 13 else 2
        wrong = [ans + x for x in (-a, a, b, -b, 10, -10, 1, -1)]
    elif kind == 1:
        a = rng.randint(11, 30)
        q, ans, d = f"Combien vaut {a} au carré ?", a * a, 2 if a < 21 else 3
        wrong = [ans + x for x in (a, -a, 2 * a - 1, -(2 * a - 1), 10, -10)]
    elif kind == 2:
        p, n = rng.choice([10, 15, 20, 25, 30, 40, 50, 75]), rng.choice([40, 60, 80, 120, 160, 200, 240, 300, 360, 400, 480])
        ans = p * n // 100
        q, d = f"Combien font {p} % de {n} ?", 2
        wrong = [ans + x for x in (n // 10, -n // 10, n // 20, -n // 20, 5, -5)]
    elif kind == 3:
        a, b = rng.randint(120, 980), rng.randint(120, 980)
        q, ans, d = f"Combien font {a} + {b} ?", a + b, 1
        wrong = [ans + x for x in (10, -10, 100, -100, 1, -1)]
    else:
        b = rng.randint(3, 12)
        ans = rng.randint(6, 25)
        q, d = f"Combien font {b * ans} ÷ {b} ?", 2
        wrong = [ans + x for x in (1, -1, 2, -2, 3)]
    wrong = [w for w in dict.fromkeys(wrong) if w > 0 and w != ans]
    rng.shuffle(wrong)
    return make("sciences", q, str(ans), [str(w) for w in wrong[:3]], d)


def _primes(rng, i):
    def isp(n):
        return n > 1 and all(n % k for k in range(2, int(n ** .5) + 1))
    prime = rng.choice([p for p in range(11, 200) if isp(p)])
    comps = [n for n in range(prime - 30, prime + 30) if n > 9 and not isp(n) and n % 2 and n % 5]
    rng.shuffle(comps)
    return make("sciences", "Lequel de ces nombres est premier ?", str(prime), [str(c) for c in comps[:3]], 2 if prime < 60 else 3)


def generate():
    out = []
    names = [e[2] for e in ELEMENTS]
    syms = [e[1] for e in ELEMENTS]
    for n, sym, name in ELEMENTS:
        d = 1 if n in FAMOUS_EL and n <= 30 else 2 if n in FAMOUS_EL or n <= 36 else 3
        near_names = [e[2] for e in ELEMENTS if abs(e[0] - n) <= 12 and e[0] != n]
        near_syms = [e[1] for e in ELEMENTS if abs(e[0] - n) <= 12 and e[0] != n]
        # Mauvais symboles crédibles : ceux qui commencent par la même lettre en priorité.
        same_letter = [s for s in syms if s[0] == sym[0] and s != sym]
        out.append(make("sciences", f"Quel élément chimique a pour symbole « {sym} » ?", name, pick(f"sym-{n}", near_names, name), d))
        out.append(make("sciences", f"Quel est le symbole chimique de l'élément « {name} » ?", sym, pick(f"symr-{n}", same_letter + near_syms, sym)[:3]
                        if len(same_letter) >= 3 else pick(f"symr-{n}", same_letter + near_syms, sym), d))
        if n <= 56 or n in FAMOUS_EL:
            out.append(make("sciences", f"Quel élément porte le numéro atomique {n} ?", name, pick(f"num-{n}", near_names, name), min(3, d + 1)))
            nums = [str(x) for x in (n - 2, n - 1, n + 1, n + 2, n + 10) if 0 < x <= 118 and x != n]
            out.append(make("sciences", f"Quel est le numéro atomique de l'élément « {name} » ?", str(n), pick(f"numr-{n}", nums, str(n)), 3 if n > 20 else 2))
    unit_names = [u for _, u in UNITS]
    for qty, unit in UNITS:
        out.append(make("sciences", f"Quelle est l'unité de {qty} ?", unit[0].upper() + unit[1:], [u[0].upper() + u[1:] for u in pick(f"u-{qty}", unit_names, unit)], 2))
    for unit, sym in SYMBOLS:
        out.append(make("sciences", f"Quel est le symbole de l'unité « {unit} » ?", sym, pick(f"us-{unit}", [s for _, s in SYMBOLS], sym), 2))
    for pre, val in PREFIXES:
        out.append(make("sciences", f"Que signifie le préfixe « {pre}- » dans les unités ?", val, pick(f"pre-{pre}", [v for _, v in PREFIXES], val), 2))
    for f, name in FORMULAS:
        d = 1 if f in ("H₂O", "CO₂", "O₂", "NaCl") else 2 if len(f) <= 4 else 3
        out.append(make("sciences", f"Quelle molécule a pour formule {f} ?", name, pick(f"f-{f}", [n for _, n in FORMULAS], name), d))
        out.append(make("sciences", f"Quelle est la formule chimique de : {name[0].lower() + name[1:]} ?", f, pick(f"fr-{f}", [x for x, _ in FORMULAS], f), d + (d < 3)))
    sci = [s for s, _ in SCIENTISTS]
    works = [w for _, w in SCIENTISTS]
    for s, w in SCIENTISTS:
        out.append(make("sciences", f"À quel savant doit-on : {w[0].lower() + w[1:]} ?", s, pick(f"sc-{s}", sci, s), 2))
        out.append(make("sciences", f"Pour quoi {s} est-il ou elle célèbre ?", w, pick(f"scr-{s}", works, w), 2))
    for d, q, a, w in WRITTEN:
        out.append(make("sciences", q, a, w, d))
    rng = random.Random("calc")
    out += [_calc(rng, i) for i in range(260)]
    rng = random.Random("primes")
    out += [_primes(rng, i) for i in range(60)]
    return out
