"""Sport : sportifs (sport, pays), Coupe du monde, Euro, Jeux olympiques, F1, clubs, règles et chiffres."""

from . import make, pick

FOOT, TEN, ATH, NAT, SKI, VEL, F1, BAS = "Football", "Tennis", "Athlétisme", "Natation", "Ski alpin", "Cyclisme", "Formule 1", "Basketball"
RU = "Royaume-Uni"
ATHLETES = [
    ("Lionel Messi", FOOT, "Argentine"), ("Cristiano Ronaldo", FOOT, "Portugal"), ("Kylian Mbappé", FOOT, "France"), ("Zinédine Zidane", FOOT, "France"),
    ("Pelé", FOOT, "Brésil"), ("Diego Maradona", FOOT, "Argentine"), ("Neymar", FOOT, "Brésil"), ("Erling Haaland", FOOT, "Norvège"), ("Karim Benzema", FOOT, "France"),
    ("Antoine Griezmann", FOOT, "France"), ("Thierry Henry", FOOT, "France"), ("Michel Platini", FOOT, "France"), ("Johan Cruyff", FOOT, "Pays-Bas"),
    ("Franz Beckenbauer", FOOT, "Allemagne"), ("Ronaldinho", FOOT, "Brésil"), ("Zlatan Ibrahimović", FOOT, "Suède"), ("Mohamed Salah", FOOT, "Égypte"),
    ("Luka Modrić", FOOT, "Croatie"), ("Robert Lewandowski", FOOT, "Pologne"), ("Kevin De Bruyne", FOOT, "Belgique"), ("Xherdan Shaqiri", FOOT, "Suisse"),
    ("Granit Xhaka", FOOT, "Suisse"), ("Yann Sommer", FOOT, "Suisse"), ("Didier Drogba", FOOT, "Côte d'Ivoire"), ("Samuel Eto'o", FOOT, "Cameroun"),
    ("George Weah", FOOT, "Liberia"), ("Sadio Mané", FOOT, "Sénégal"), ("Andrés Iniesta", FOOT, "Espagne"), ("Iker Casillas", FOOT, "Espagne"),
    ("Gianluigi Buffon", FOOT, "Italie"), ("Paolo Maldini", FOOT, "Italie"), ("David Beckham", FOOT, RU), ("Wayne Rooney", FOOT, RU), ("Harry Kane", FOOT, RU),
    ("Jude Bellingham", FOOT, RU), ("Lamine Yamal", FOOT, "Espagne"), ("Vinícius Júnior", FOOT, "Brésil"), ("Alexia Putellas", FOOT, "Espagne"),
    ("Megan Rapinoe", FOOT, "États-Unis"), ("Marta", FOOT, "Brésil"), ("Ada Hegerberg", FOOT, "Norvège"), ("Lia Wälti", FOOT, "Suisse"), ("Stéphane Chapuisat", FOOT, "Suisse"),
    ("Roger Federer", TEN, "Suisse"), ("Stan Wawrinka", TEN, "Suisse"), ("Martina Hingis", TEN, "Suisse"), ("Belinda Bencic", TEN, "Suisse"), ("Rafael Nadal", TEN, "Espagne"),
    ("Novak Djokovic", TEN, "Serbie"), ("Carlos Alcaraz", TEN, "Espagne"), ("Jannik Sinner", TEN, "Italie"), ("Andy Murray", TEN, RU), ("Serena Williams", TEN, "États-Unis"),
    ("Steffi Graf", TEN, "Allemagne"), ("Björn Borg", TEN, "Suède"), ("John McEnroe", TEN, "États-Unis"), ("Pete Sampras", TEN, "États-Unis"), ("Andre Agassi", TEN, "États-Unis"),
    ("Yannick Noah", TEN, "France"), ("Amélie Mauresmo", TEN, "France"), ("Iga Świątek", TEN, "Pologne"), ("Naomi Osaka", TEN, "Japon"), ("Aryna Sabalenka", TEN, "Biélorussie"),
    ("Boris Becker", TEN, "Allemagne"), ("Justine Henin", TEN, "Belgique"), ("Kim Clijsters", TEN, "Belgique"), ("Maria Sharapova", TEN, "Russie"),
    ("Usain Bolt", ATH, "Jamaïque"), ("Carl Lewis", ATH, "États-Unis"), ("Jesse Owens", ATH, "États-Unis"), ("Armand Duplantis", ATH, "Suède"), ("Eliud Kipchoge", ATH, "Kenya"),
    ("Haile Gebreselassie", ATH, "Éthiopie"), ("Florence Griffith-Joyner", ATH, "États-Unis"), ("Marie-José Pérec", ATH, "France"), ("Renaud Lavillenie", ATH, "France"),
    ("Kevin Mayer", ATH, "France"), ("Mujinga Kambundji", ATH, "Suisse"), ("Ditaji Kambundji", ATH, "Suisse"), ("Shelly-Ann Fraser-Pryce", ATH, "Jamaïque"),
    ("Sergueï Bubka", ATH, "Ukraine"), ("Paavo Nurmi", ATH, "Finlande"), ("Faith Kipyegon", ATH, "Kenya"), ("Michael Johnson", ATH, "États-Unis"), ("Mo Farah", ATH, RU),
    ("Jakob Ingebrigtsen", ATH, "Norvège"), ("Karsten Warholm", ATH, "Norvège"),
    ("Michael Phelps", NAT, "États-Unis"), ("Léon Marchand", NAT, "France"), ("Katie Ledecky", NAT, "États-Unis"), ("Laure Manaudou", NAT, "France"),
    ("Florent Manaudou", NAT, "France"), ("Ian Thorpe", NAT, "Australie"), ("Mark Spitz", NAT, "États-Unis"), ("Federica Pellegrini", NAT, "Italie"), ("Noè Ponti", NAT, "Suisse"),
    ("Marco Odermatt", SKI, "Suisse"), ("Lara Gut-Behrami", SKI, "Suisse"), ("Didier Cuche", SKI, "Suisse"), ("Bernhard Russi", SKI, "Suisse"), ("Pirmin Zurbriggen", SKI, "Suisse"),
    ("Vreni Schneider", SKI, "Suisse"), ("Mikaela Shiffrin", SKI, "États-Unis"), ("Lindsey Vonn", SKI, "États-Unis"), ("Marcel Hirscher", SKI, "Autriche"),
    ("Hermann Maier", SKI, "Autriche"), ("Ingemar Stenmark", SKI, "Suède"), ("Alberto Tomba", SKI, "Italie"), ("Jean-Claude Killy", SKI, "France"),
    ("Aksel Lund Svindal", SKI, "Norvège"), ("Alexis Pinturault", SKI, "France"), ("Wendy Holdener", SKI, "Suisse"), ("Corinne Suter", SKI, "Suisse"),
    ("Loïc Meillard", SKI, "Suisse"), ("Beat Feuz", SKI, "Suisse"),
    ("Dario Cologna", "Ski de fond", "Suisse"), ("Marit Bjørgen", "Ski de fond", "Norvège"), ("Simon Ammann", "Saut à ski", "Suisse"),
    ("Martin Fourcade", "Biathlon", "France"), ("Ole Einar Bjørndalen", "Biathlon", "Norvège"), ("Johannes Thingnes Bø", "Biathlon", "Norvège"),
    ("Eddy Merckx", VEL, "Belgique"), ("Bernard Hinault", VEL, "France"), ("Jacques Anquetil", VEL, "France"), ("Miguel Indurain", VEL, "Espagne"),
    ("Tadej Pogačar", VEL, "Slovénie"), ("Jonas Vingegaard", VEL, "Danemark"), ("Chris Froome", VEL, RU), ("Fabian Cancellara", VEL, "Suisse"),
    ("Ferdi Kübler", VEL, "Suisse"), ("Hugo Koblet", VEL, "Suisse"), ("Julian Alaphilippe", VEL, "France"), ("Wout van Aert", VEL, "Belgique"),
    ("Mathieu van der Poel", VEL, "Pays-Bas"), ("Peter Sagan", VEL, "Slovaquie"), ("Remco Evenepoel", VEL, "Belgique"), ("Nino Schurter", "VTT", "Suisse"),
    ("Michael Schumacher", F1, "Allemagne"), ("Ayrton Senna", F1, "Brésil"), ("Alain Prost", F1, "France"), ("Lewis Hamilton", F1, RU), ("Max Verstappen", F1, "Pays-Bas"),
    ("Sebastian Vettel", F1, "Allemagne"), ("Fernando Alonso", F1, "Espagne"), ("Niki Lauda", F1, "Autriche"), ("Juan Manuel Fangio", F1, "Argentine"),
    ("Kimi Räikkönen", F1, "Finlande"), ("Charles Leclerc", F1, "Monaco"), ("Lando Norris", F1, RU), ("Clay Regazzoni", F1, "Suisse"), ("Jo Siffert", F1, "Suisse"),
    ("Sébastien Loeb", "Rallye", "France"), ("Sébastien Ogier", "Rallye", "France"),
    ("Michael Jordan", BAS, "États-Unis"), ("LeBron James", BAS, "États-Unis"), ("Kobe Bryant", BAS, "États-Unis"), ("Stephen Curry", BAS, "États-Unis"),
    ("Victor Wembanyama", BAS, "France"), ("Tony Parker", BAS, "France"), ("Dirk Nowitzki", BAS, "Allemagne"), ("Giannis Antetokounmpo", BAS, "Grèce"),
    ("Nikola Jokić", BAS, "Serbie"), ("Clint Capela", BAS, "Suisse"), ("Thabo Sefolosha", BAS, "Suisse"), ("Yao Ming", BAS, "Chine"),
    ("Tiger Woods", "Golf", "États-Unis"), ("Jack Nicklaus", "Golf", "États-Unis"), ("Rory McIlroy", "Golf", RU), ("Seve Ballesteros", "Golf", "Espagne"),
    ("Mohamed Ali", "Boxe", "États-Unis"), ("Mike Tyson", "Boxe", "États-Unis"), ("Manny Pacquiao", "Boxe", "Philippines"),
    ("Wayne Gretzky", "Hockey sur glace", "Canada"), ("Sidney Crosby", "Hockey sur glace", "Canada"), ("Roman Josi", "Hockey sur glace", "Suisse"),
    ("Nico Hischier", "Hockey sur glace", "Suisse"), ("Connor McDavid", "Hockey sur glace", "Canada"), ("Alexandre Ovetchkine", "Hockey sur glace", "Russie"),
    ("Jonah Lomu", "Rugby", "Nouvelle-Zélande"), ("Antoine Dupont", "Rugby", "France"), ("Jonny Wilkinson", "Rugby", RU), ("Richie McCaw", "Rugby", "Nouvelle-Zélande"),
    ("Teddy Riner", "Judo", "France"), ("Tony Estanguet", "Canoë-kayak", "France"), ("Nadia Comăneci", "Gymnastique", "Roumanie"), ("Simone Biles", "Gymnastique", "États-Unis"),
    ("Giulia Steingruber", "Gymnastique", "Suisse"), ("Shaun White", "Snowboard", "États-Unis"), ("Ueli Steck", "Alpinisme", "Suisse"), ("Kilian Jornet", "Trail", "Espagne"),
    ("Christian Stucki", "Lutte suisse", "Suisse"), ("Joel Wicki", "Lutte suisse", "Suisse"), ("Tony Hawk", "Skateboard", "États-Unis"), ("Kelly Slater", "Surf", "États-Unis"),
    ("Magnus Carlsen", "Échecs", "Norvège"), ("Garry Kasparov", "Échecs", "Russie"), ("Ronnie O'Sullivan", "Snooker", RU), ("Tom Brady", "Football américain", "États-Unis"),
    ("Shohei Ohtani", "Baseball", "Japon"), ("Babe Ruth", "Baseball", "États-Unis"), ("Sachin Tendulkar", "Cricket", "Inde"), ("Valentino Rossi", "Moto", "Italie"),
    ("Marc Márquez", "Moto", "Espagne"), ("Thomas Lüthi", "Moto", "Suisse"),
]
FAMOUS = {"Lionel Messi", "Cristiano Ronaldo", "Kylian Mbappé", "Zinédine Zidane", "Pelé", "Roger Federer", "Rafael Nadal", "Usain Bolt", "Michael Phelps",
          "Michael Jordan", "Tiger Woods", "Mohamed Ali", "Lewis Hamilton", "Michael Schumacher", "Serena Williams", "Novak Djokovic", "Marco Odermatt", "LeBron James"}

WORLD_CUP = [(1930, "Uruguay", "Uruguay"), (1934, "Italie", "Italie"), (1938, "Italie", "France"), (1950, "Uruguay", "Brésil"), (1954, "RFA", "Suisse"),
             (1958, "Brésil", "Suède"), (1962, "Brésil", "Chili"), (1966, "Angleterre", "Angleterre"), (1970, "Brésil", "Mexique"), (1974, "RFA", "RFA"),
             (1978, "Argentine", "Argentine"), (1982, "Italie", "Espagne"), (1986, "Argentine", "Mexique"), (1990, "RFA", "Italie"), (1994, "Brésil", "États-Unis"),
             (1998, "France", "France"), (2002, "Brésil", "Corée du Sud et Japon"), (2006, "Italie", "Allemagne"), (2010, "Espagne", "Afrique du Sud"),
             (2014, "Allemagne", "Brésil"), (2018, "France", "Russie"), (2022, "Argentine", "Qatar")]
EURO = [(1960, "URSS"), (1964, "Espagne"), (1968, "Italie"), (1972, "RFA"), (1976, "Tchécoslovaquie"), (1980, "RFA"), (1984, "France"), (1988, "Pays-Bas"),
        (1992, "Danemark"), (1996, "Allemagne"), (2000, "France"), (2004, "Grèce"), (2008, "Espagne"), (2012, "Espagne"), (2016, "Portugal"), (2021, "Italie"), (2024, "Espagne")]
SUMMER = [(1896, "Athènes"), (1900, "Paris"), (1904, "Saint-Louis"), (1908, "Londres"), (1912, "Stockholm"), (1920, "Anvers"), (1924, "Paris"), (1928, "Amsterdam"),
          (1932, "Los Angeles"), (1936, "Berlin"), (1948, "Londres"), (1952, "Helsinki"), (1956, "Melbourne"), (1960, "Rome"), (1964, "Tokyo"), (1968, "Mexico"),
          (1972, "Munich"), (1976, "Montréal"), (1980, "Moscou"), (1984, "Los Angeles"), (1988, "Séoul"), (1992, "Barcelone"), (1996, "Atlanta"), (2000, "Sydney"),
          (2004, "Athènes"), (2008, "Pékin"), (2012, "Londres"), (2016, "Rio de Janeiro"), (2021, "Tokyo"), (2024, "Paris"), (2028, "Los Angeles"), (2032, "Brisbane")]
WINTER = [(1924, "Chamonix"), (1928, "Saint-Moritz"), (1932, "Lake Placid"), (1936, "Garmisch-Partenkirchen"), (1948, "Saint-Moritz"), (1952, "Oslo"),
          (1956, "Cortina d'Ampezzo"), (1960, "Squaw Valley"), (1964, "Innsbruck"), (1968, "Grenoble"), (1972, "Sapporo"), (1976, "Innsbruck"), (1980, "Lake Placid"),
          (1984, "Sarajevo"), (1988, "Calgary"), (1992, "Albertville"), (1994, "Lillehammer"), (1998, "Nagano"), (2002, "Salt Lake City"), (2006, "Turin"),
          (2010, "Vancouver"), (2014, "Sotchi"), (2018, "Pyeongchang"), (2022, "Pékin"), (2026, "Milan et Cortina d'Ampezzo")]
F1_CHAMPIONS = [(1994, "Michael Schumacher"), (1995, "Michael Schumacher"), (1996, "Damon Hill"), (1997, "Jacques Villeneuve"), (1998, "Mika Häkkinen"),
                (1999, "Mika Häkkinen"), (2000, "Michael Schumacher"), (2001, "Michael Schumacher"), (2002, "Michael Schumacher"), (2003, "Michael Schumacher"),
                (2004, "Michael Schumacher"), (2005, "Fernando Alonso"), (2006, "Fernando Alonso"), (2007, "Kimi Räikkönen"), (2008, "Lewis Hamilton"),
                (2009, "Jenson Button"), (2010, "Sebastian Vettel"), (2011, "Sebastian Vettel"), (2012, "Sebastian Vettel"), (2013, "Sebastian Vettel"),
                (2014, "Lewis Hamilton"), (2015, "Lewis Hamilton"), (2016, "Nico Rosberg"), (2017, "Lewis Hamilton"), (2018, "Lewis Hamilton"),
                (2019, "Lewis Hamilton"), (2020, "Lewis Hamilton"), (2021, "Max Verstappen"), (2022, "Max Verstappen"), (2023, "Max Verstappen"), (2024, "Max Verstappen")]

# (club, ville)
CLUBS = [
    ("le Real Madrid", "Madrid"), ("le FC Barcelone", "Barcelone"), ("l'Atlético de Madrid", "Madrid"), ("Manchester United", "Manchester"),
    ("Manchester City", "Manchester"), ("le Liverpool FC", "Liverpool"), ("Chelsea", "Londres"), ("Arsenal", "Londres"), ("Tottenham", "Londres"),
    ("le Bayern Munich", "Munich"), ("le Borussia Dortmund", "Dortmund"), ("la Juventus", "Turin"), ("l'AC Milan", "Milan"), ("l'Inter", "Milan"),
    ("l'AS Roma", "Rome"), ("la Lazio", "Rome"), ("le SSC Naples", "Naples"), ("le Paris Saint-Germain", "Paris"), ("l'Olympique de Marseille", "Marseille"),
    ("l'Olympique lyonnais", "Lyon"), ("le LOSC", "Lille"), ("l'Ajax", "Amsterdam"), ("le PSV", "Eindhoven"), ("le Feyenoord", "Rotterdam"),
    ("le Benfica", "Lisbonne"), ("le Sporting CP", "Lisbonne"), ("le FC Porto", "Porto"), ("le Celtic", "Glasgow"), ("les Rangers", "Glasgow"),
    ("Galatasaray", "Istanbul"), ("Fenerbahçe", "Istanbul"), ("le RSC Anderlecht", "Bruxelles"), ("le Club Bruges", "Bruges"), ("le FC Bâle", "Bâle"),
    ("les Young Boys", "Berne"), ("le FC Zurich", "Zurich"), ("Grasshopper", "Zurich"), ("le Servette FC", "Genève"), ("le FC Lausanne-Sport", "Lausanne"),
    ("le FC Sion", "Sion"), ("le FC Lugano", "Lugano"), ("le FC Saint-Gall", "Saint-Gall"), ("le FC Lucerne", "Lucerne"), ("Neuchâtel Xamax", "Neuchâtel"),
    ("Boca Juniors", "Buenos Aires"), ("River Plate", "Buenos Aires"), ("Flamengo", "Rio de Janeiro"), ("le Santos FC", "Santos"), ("le LA Galaxy", "Los Angeles"),
    ("l'Inter Miami", "Miami"), ("Al-Nassr", "Riyad"), ("le HC Davos", "Davos"), ("le CP Berne", "Berne"), ("le Lausanne HC", "Lausanne"),
    ("Genève-Servette HC", "Genève"), ("le HC Fribourg-Gottéron", "Fribourg"), ("l'EV Zoug", "Zoug"), ("les ZSC Lions", "Zurich"), ("le HC Lugano", "Lugano"),
    ("l'EHC Bienne", "Bienne"), ("le HC Ajoie", "Porrentruy"), ("les Rapperswil-Jona Lakers", "Rapperswil-Jona"), ("les Los Angeles Lakers", "Los Angeles"),
    ("les Boston Celtics", "Boston"), ("les Chicago Bulls", "Chicago"), ("les Golden State Warriors", "San Francisco"), ("les New York Knicks", "New York"),
    ("le Miami Heat", "Miami"), ("les San Antonio Spurs", "San Antonio"), ("le Stade toulousain", "Toulouse"), ("le RC Toulon", "Toulon"),
]

WRITTEN = [
    (1, "Combien de joueurs compte une équipe de basketball sur le terrain ?", "5", ["6", "7", "4"]),
    (1, "Avec quoi frappe-t-on la balle au tennis ?", "Une raquette", ["Une batte", "Une crosse", "Un maillet"]),
    (1, "Quel sport se joue avec une crosse et un palet sur la glace ?", "Le hockey sur glace", ["Le curling", "Le patinage", "La ringuette"]),
    (2, "Quelle est la distance du sprint le plus court aux JO d'été en athlétisme ?", "100 m", ["60 m", "50 m", "200 m"]),
    (2, "Quelle épreuve d'athlétisme utilise une perche ?", "Le saut à la perche", ["Le saut en hauteur", "Le triple saut", "Le lancer du javelot"]),
    (2, "Quel lancer se fait avec un engin attaché à un câble ?", "Le lancer du marteau", ["Le lancer du disque", "Le lancer du poids", "Le lancer du javelot"]),
    (2, "Combien de sauts enchaîne-t-on au triple saut ?", "3", ["2", "4", "5"]),
    (2, "Quelle nage se pratique sur le ventre en « grenouille » ?", "La brasse", ["Le crawl", "Le dos", "Le papillon"]),
    (2, "Combien de couloirs compte une piscine olympique en compétition ?", "8 (ou 10)", ["6", "12", "4"]),
    (2, "Quel sport combine équitation, escrime, natation, tir et course (pentathlon moderne) ?", "Le pentathlon moderne", ["Le triathlon", "Le décathlon", "Le biathlon"]),
    (2, "Comment s'appelle le ski de compétition entre des portes rapprochées ?", "Le slalom", ["La descente", "Le super-G", "Le combiné"]),
    (2, "Quelle est la discipline de ski alpin la plus rapide ?", "La descente", ["Le slalom", "Le géant", "Le super-G"]),
    (2, "Comment s'appelle le globe remis au vainqueur de la Coupe du monde de ski ?", "Le gros globe de cristal", ["Le globe d'or", "La coupe des neiges", "Le trophée Killy"]),
    (2, "Quel skieur suisse a remporté plusieurs gros globes de cristal à partir de 2022 ?", "Marco Odermatt", ["Didier Cuche", "Beat Feuz", "Loïc Meillard"]),
    (2, "Quelle skieuse suisse a remporté le gros globe de cristal en 2016 et 2024 ?", "Lara Gut-Behrami", ["Wendy Holdener", "Corinne Suter", "Michelle Gisin"]),
    (2, "Quel sauteur à ski suisse a gagné 4 médailles d'or olympiques ?", "Simon Ammann", ["Andreas Küttel", "Gregor Deschwanden", "Killian Peier"]),
    (2, "Quel sport est le plus populaire en Inde ?", "Le cricket", ["Le football", "Le hockey sur gazon", "Le badminton"]),
    (2, "Quel sport est le plus populaire aux États-Unis (audiences) ?", "Le football américain", ["Le baseball", "Le basketball", "Le soccer"]),
    (2, "Dans quel sport parle-t-on de « home run » ?", "Le baseball", ["Le cricket", "Le golf", "Le football américain"]),
    (2, "Dans quel sport fait-on un « smash » au filet ?", "Le volleyball (et le tennis)", ["Le golf", "La natation", "Le rugby"]),
    (2, "Quel sport pratique-t-on sur une piste en bois inclinée appelée vélodrome ?", "Le cyclisme sur piste", ["Le BMX", "Le roller", "Le patinage de vitesse"]),
    (2, "Quel sport de glisse se pratique sur une planche, avec une voile ?", "La planche à voile", ["Le surf", "Le wakeboard", "Le skimboard"]),
    (2, "Quel sport consiste à descendre une piste de glace sur une luge, tête la première ?", "Le skeleton", ["La luge", "Le bobsleigh", "Le curling"]),
    (2, "Combien de personnes compte un bob à quatre ?", "4", ["2", "3", "5"]),
    (2, "Combien de joueurs compte une équipe de curling ?", "4", ["5", "3", "6"]),
    (2, "Quel pays domine historiquement le ski de fond ?", "La Norvège", ["La Suisse", "L'Autriche", "Le Canada"]),
    (2, "Quel pays a remporté le plus de médailles aux Jeux olympiques d'hiver ?", "La Norvège", ["Les États-Unis", "L'Allemagne", "La Suisse"]),
    (2, "Quelle course cycliste est surnommée « l'Enfer du Nord » ?", "Paris-Roubaix", ["Milan-San Remo", "Le Tour des Flandres", "Liège-Bastogne-Liège"]),
    (2, "Quelle course cycliste par étapes parcourt la Suisse chaque mois de juin ?", "Le Tour de Suisse", ["Le Critérium du Dauphiné", "Le Giro", "La Vuelta"]),
    (1, "Combien de joueurs compte une équipe de volleyball sur le terrain ?", "6", ["5", "7", "4"]),
    (1, "Combien de joueurs compte une équipe de rugby à XV sur le terrain ?", "15", ["13", "11", "12"]),
    (2, "Combien de joueurs compte une équipe de handball sur le terrain ?", "7", ["6", "5", "8"]),
    (2, "Combien de joueurs compte une équipe de hockey sur glace sur la glace ?", "6", ["5", "7", "11"]),
    (2, "Combien de joueurs compte une équipe de water-polo dans l'eau ?", "7", ["6", "5", "8"]),
    (2, "Combien de joueurs compte une équipe de baseball sur le terrain ?", "9", ["11", "10", "8"]),
    (1, "Combien de temps dure un match de football (hors prolongations) ?", "90 minutes", ["80 minutes", "60 minutes", "100 minutes"]),
    (2, "Combien de temps dure un match de rugby ?", "80 minutes", ["90 minutes", "70 minutes", "60 minutes"]),
    (2, "Combien de tiers-temps compte un match de hockey sur glace ?", "3", ["2", "4", "5"]),
    (2, "Combien de quart-temps compte un match de basketball ?", "4", ["2", "3", "6"]),
    (2, "Combien de points vaut un panier marqué derrière la ligne à 3 points ?", "3", ["2", "4", "1"]),
    (2, "Combien de points vaut un essai au rugby à XV ?", "5", ["3", "4", "7"]),
    (2, "Combien de points vaut une transformation au rugby ?", "2", ["1", "3", "5"]),
    (2, "Combien de points vaut un touchdown au football américain ?", "6", ["7", "3", "5"]),
    (1, "Au tennis, comment dit-on 0 point ?", "Zéro (« love » en anglais)", ["Nul", "Rien", "Blanc"]),
    (2, "Au tennis, quel score suit 30 ?", "40", ["45", "35", "50"]),
    (2, "Au tennis, comment appelle-t-on 40-40 ?", "Égalité", ["Avantage", "Jeu blanc", "Tie-break"]),
    (2, "Quel tournoi du Grand Chelem se joue sur gazon ?", "Wimbledon", ["Roland-Garros", "L'US Open", "L'Open d'Australie"]),
    (2, "Quel tournoi du Grand Chelem se joue sur terre battue ?", "Roland-Garros", ["Wimbledon", "L'US Open", "L'Open d'Australie"]),
    (2, "Combien de tournois composent le Grand Chelem de tennis ?", "4", ["3", "5", "6"]),
    (2, "Dans quelle ville se joue l'US Open de tennis ?", "New York", ["Los Angeles", "Miami", "Washington"]),
    (2, "Dans quelle ville se joue l'Open d'Australie ?", "Melbourne", ["Sydney", "Brisbane", "Perth"]),
    (2, "Combien de titres du Grand Chelem a remportés Roger Federer ?", "20", ["18", "22", "24"]),
    (2, "Combien de fois Rafael Nadal a-t-il gagné Roland-Garros ?", "14", ["12", "10", "16"]),
    (2, "Quelle est la distance d'un marathon ?", "42,195 km", ["40 km", "42 km pile", "45,5 km"]),
    (2, "Combien de haies compte un 110 m haies ?", "10", ["8", "12", "11"]),
    (2, "Combien d'épreuves compte un décathlon ?", "10", ["7", "8", "12"]),
    (2, "Combien d'épreuves compte un heptathlon ?", "7", ["5", "8", "10"]),
    (2, "Quelles sont les trois disciplines du triathlon ?", "Natation, vélo, course à pied", ["Natation, aviron, course", "Vélo, ski, course", "Tir, ski, course"]),
    (2, "Quelles disciplines combine le biathlon ?", "Ski de fond et tir", ["Ski alpin et tir", "Ski de fond et saut", "Course et tir à l'arc"]),
    (2, "Quel record du monde du 100 m détient Usain Bolt ?", "9,58 s", ["9,69 s", "9,48 s", "9,74 s"]),
    (2, "Combien de médailles d'or olympiques a remportées Michael Phelps ?", "23", ["18", "28", "21"]),
    (2, "Quelle est la couleur du maillot du leader du Tour de France ?", "Jaune", ["Vert", "Rose", "À pois rouges"]),
    (2, "Quelle est la couleur du maillot du meilleur grimpeur du Tour de France ?", "Blanc à pois rouges", ["Vert", "Jaune", "Blanc"]),
    (2, "Quelle est la couleur du maillot du leader du Tour d'Italie ?", "Rose", ["Jaune", "Rouge", "Bleu"]),
    (2, "Où arrive traditionnellement le Tour de France ?", "Sur les Champs-Élysées à Paris", ["À Nice", "À Lyon", "À l'Alpe d'Huez"]),
    (2, "Combien de victoires dans le Tour de France compte Eddy Merckx ?", "5", ["4", "6", "7"]),
    (2, "Quelle course de 24 heures automobile a lieu en France ?", "Les 24 Heures du Mans", ["Les 24 Heures de Spa", "Le Bol d'or", "Le Rallye Monte-Carlo"]),
    (2, "Sur quel circuit urbain se court le Grand Prix de F1 le plus prestigieux ?", "Monaco", ["Monza", "Silverstone", "Spa-Francorchamps"]),
    (2, "Quelle écurie de F1 est italienne, au cheval cabré ?", "Ferrari", ["Maserati", "Alfa Romeo", "Lamborghini"]),
    (2, "Quelle écurie de F1 a son siège à Hinwil, dans le canton de Zurich ?", "Sauber", ["Alpine", "Williams", "Haas"]),
    (2, "Combien de titres de champion du monde de F1 a Lewis Hamilton ?", "7", ["6", "8", "5"]),
    (2, "Quel pays a remporté le plus de Coupes du monde de football ?", "Le Brésil", ["L'Allemagne", "L'Italie", "L'Argentine"]),
    (2, "Combien de Coupes du monde a gagnées le Brésil ?", "5", ["4", "3", "6"]),
    (2, "Quel joueur a remporté le plus de Ballons d'or ?", "Lionel Messi", ["Cristiano Ronaldo", "Michel Platini", "Johan Cruyff"]),
    (2, "Quel trophée récompense le meilleur footballeur de l'année ?", "Le Ballon d'or", ["Le Soulier d'or", "Le Trophée Yachine", "Le Golden Boy"]),
    (2, "Comment s'appelle la principale compétition européenne des clubs de football ?", "La Ligue des champions", ["La Ligue Europa", "La Coupe des coupes", "La Supercoupe"]),
    (2, "Quel club a gagné le plus de Ligues des champions ?", "Le Real Madrid", ["L'AC Milan", "Le Bayern Munich", "Liverpool"]),
    (2, "Quelle sanction donne un carton rouge au football ?", "L'expulsion", ["Un avertissement", "Un penalty", "Un coup franc"]),
    (2, "De combien de mètres se tire un penalty au football ?", "11 mètres", ["9 mètres", "12 mètres", "16,5 mètres"]),
    (2, "Où siège la FIFA ?", "Zurich", ["Genève", "Paris", "Nyon"]),
    (2, "Où siège l'UEFA ?", "Nyon", ["Zurich", "Genève", "Lausanne"]),
    (2, "Où siège le Comité international olympique ?", "Lausanne", ["Genève", "Paris", "Athènes"]),
    (2, "Quelle ville suisse est surnommée « capitale olympique » ?", "Lausanne", ["Genève", "Zurich", "Saint-Moritz"]),
    (2, "Qui a rénové les Jeux olympiques modernes ?", "Pierre de Coubertin", ["Juan Antonio Samaranch", "Jacques Rogge", "Avery Brundage"]),
    (2, "Combien d'anneaux figurent sur le drapeau olympique ?", "5", ["4", "6", "7"]),
    (2, "Quelle est la devise olympique ?", "Plus vite, plus haut, plus fort", ["L'important c'est de participer", "Le sport pour tous", "Unis par le sport"]),
    (2, "Quel sport national suisse se pratique dans un rond de sciure ?", "La lutte suisse (Schwingen)", ["Le Hornuss", "Le lancer de la pierre d'Unspunnen", "La pétanque"]),
    (2, "Quel sport traditionnel suisse frappe un palet avec un long fouet flexible ?", "Le hornuss", ["Le curling", "Le hockey", "Le golf"]),
    (2, "Quelle célèbre course de ski de fond relie Maloja à S-chanf ?", "Le marathon de l'Engadine", ["La Vasaloppet", "La Transjurassienne", "La Patrouille des Glaciers"]),
    (2, "Quelle course militaire et civile relie Zermatt à Verbier ?", "La Patrouille des Glaciers", ["Le marathon de l'Engadine", "Sierre-Zinal", "Le Tour des Stations"]),
    (2, "Quelle course de montagne relie Sierre à Zinal ?", "Sierre-Zinal", ["Morat-Fribourg", "Le Grand Raid", "Le Trail Verbier Saint-Bernard"]),
    (2, "Quelle course à pied relie Morat à Fribourg ?", "Morat-Fribourg", ["Sierre-Zinal", "Le Grand Prix de Berne", "Les 20 km de Lausanne"]),
    (2, "Quelle célèbre descente de ski a lieu à Wengen ?", "Le Lauberhorn", ["La Streif", "Le Chuenisbärgli", "La Saslong"]),
    (2, "Dans quelle station a lieu la descente de la Streif ?", "Kitzbühel", ["Wengen", "Val Gardena", "Chamonix"]),
    (2, "Qui a gagné la Coupe de l'America en 2003 pour la Suisse ?", "Alinghi", ["Luna Rossa", "Team New Zealand", "Oracle"]),
    (2, "Quelle compétition de tennis par équipes la Suisse a-t-elle gagnée en 2014 avec Federer et Wawrinka ?", "La Coupe Davis", ["La Fed Cup", "La Hopman Cup", "L'ATP Cup"]),
    (2, "Quel tournoi de tennis se joue chaque automne à Bâle ?", "Les Swiss Indoors", ["Le Swiss Open Gstaad", "Le Geneva Open", "Le tournoi de Montreux"]),
    (2, "Quel sport se joue avec des pierres de granit qu'on fait glisser sur la glace ?", "Le curling", ["Le hornuss", "Le bobsleigh", "Le palet"]),
    (2, "Dans quel sport utilise-t-on un « birdie » et un « eagle » ?", "Le golf", ["Le badminton", "Le tir à l'arc", "Le cricket"]),
    (2, "Dans quel sport utilise-t-on un volant ?", "Le badminton", ["Le tennis", "Le squash", "Le padel"]),
    (2, "Dans quel sport fait-on un « strike » en renversant toutes les quilles ?", "Le bowling", ["Le baseball", "Le curling", "La pétanque"]),
    (2, "Quel sport se pratique sur un tatami ?", "Le judo", ["L'escrime", "La lutte suisse", "La boxe"]),
    (2, "De quel pays le judo est-il originaire ?", "Le Japon", ["La Chine", "La Corée", "La Thaïlande"]),
    (2, "De quel pays le taekwondo est-il originaire ?", "La Corée du Sud", ["Le Japon", "La Chine", "Le Viêt Nam"]),
    (2, "Dans quel pays est né le rugby ?", "L'Angleterre", ["La France", "La Nouvelle-Zélande", "L'Irlande"]),
    (2, "Dans quel pays est né le basketball (inventé par James Naismith) ?", "Les États-Unis", ["Le Canada", "Le Royaume-Uni", "La France"]),
    (2, "Comment s'appelle la danse maorie des All Blacks ?", "Le haka", ["Le hula", "Le siva tau", "Le cibi"]),
    (2, "Quelle est la couleur du maillot de l'équipe de Nouvelle-Zélande de rugby ?", "Noir", ["Blanc", "Vert", "Bleu"]),
    (2, "Combien de nations jouent le Tournoi des Six Nations ?", "6", ["5", "8", "4"]),
    (2, "Quelle équipe a remporté la Coupe du monde de rugby 2023 ?", "L'Afrique du Sud", ["La Nouvelle-Zélande", "La France", "L'Irlande"]),
    (2, "Quelle compétition de hockey sur glace nord-américaine est la plus prestigieuse ?", "La LNH (NHL)", ["La NBA", "La KHL", "La MLB"]),
    (2, "Quel trophée remporte le champion de la LNH ?", "La coupe Stanley", ["Le trophée Larry O'Brien", "La coupe Spengler", "Le Vince Lombardi"]),
    (2, "Quel tournoi de hockey sur glace a lieu chaque fin d'année à Davos ?", "La Coupe Spengler", ["La coupe Stanley", "La Champions Hockey League", "Le tournoi des Quatre Nations"]),
    (2, "Comment s'appelle la finale du football américain ?", "Le Super Bowl", ["La World Series", "Les finales NBA", "Le Pro Bowl"]),
    (2, "Quel trophée de golf oppose l'Europe aux États-Unis ?", "La Ryder Cup", ["La Solheim Cup", "Le Masters", "La Presidents Cup"]),
    (2, "Combien de trous compte un parcours de golf standard ?", "18", ["9", "12", "24"]),
    (2, "Combien de rounds dure un combat de boxe pour un titre mondial ?", "12", ["10", "15", "8"]),
    (2, "Quelle est la longueur d'une piscine olympique ?", "50 m", ["25 m", "100 m", "33 m"]),
    (2, "Quel style de nage est le plus rapide ?", "Le crawl (nage libre)", ["La brasse", "Le dos", "Le papillon"]),
    (2, "Quelle est la hauteur d'un panier de basketball ?", "3,05 m", ["2,80 m", "3,50 m", "3,30 m"]),
    (2, "Quelle est la hauteur d'un filet de volleyball masculin ?", "2,43 m", ["2,24 m", "2,60 m", "2,10 m"]),
    (2, "Combien de sets gagnants faut-il au volleyball ?", "3", ["2", "4", "5"]),
]
WRITTEN += [
    (2, "Combien de pièces chaque joueur a-t-il au début d'une partie d'échecs ?", "16", ["12", "14", "18"]),
    (2, "Dans quel sport utilise-t-on un fleuret, une épée ou un sabre ?", "L'escrime", ["Le kendo", "Le judo", "Le hornuss"]),
]


def generate():
    out = []
    sports = list(dict.fromkeys(a[1] for a in ATHLETES))
    countries = list(dict.fromkeys(a[2] for a in ATHLETES))
    for name, sport, country in ATHLETES:
        d = 1 if name in FAMOUS else 2 if country == "Suisse" or sport in (FOOT, TEN) else 3
        out.append(make("sport", f"Quel sport pratique (ou pratiquait) {name} ?", sport, pick(f"sp-{name}", sports, sport), max(1, d - 1)))
        out.append(make("sport", f"De quel pays est {name} ?", country, pick(f"spc-{name}", countries, country), d))
    by_sport = {}
    for a in ATHLETES:
        by_sport.setdefault(a[1], []).append(a[0])
    for sport, names in by_sport.items():
        others = [a[0] for a in ATHLETES if a[1] != sport]
        for n in names[:10]:
            out.append(make("sport", f"Lequel de ces sportifs pratique (ou pratiquait) : {sport.lower()} ?", n, pick(f"spr-{n}", others, n), 2))
    # Par pays
    art = {"Suisse": "la Suisse", "France": "la France", "États-Unis": "les États-Unis", "Royaume-Uni": "le Royaume-Uni", "Espagne": "l'Espagne",
           "Brésil": "le Brésil", "Argentine": "l'Argentine", "Allemagne": "l'Allemagne", "Italie": "l'Italie", "Norvège": "la Norvège",
           "Belgique": "la Belgique", "Suède": "la Suède", "Canada": "le Canada", "Pays-Bas": "les Pays-Bas", "Autriche": "l'Autriche",
           "Jamaïque": "la Jamaïque", "Kenya": "le Kenya", "Serbie": "la Serbie", "Russie": "la Russie", "Nouvelle-Zélande": "la Nouvelle-Zélande"}
    by_country = {}
    for a in ATHLETES:
        by_country.setdefault(a[2], []).append(a[0])
    for country, names in by_country.items():
        if len(names) < 3 or country not in art:
            continue
        others = [a[0] for a in ATHLETES if a[2] != country]
        for n in names[:12]:
            out.append(make("sport", f"Lequel de ces sportifs représente {art[country]} ?", n, pick(f"spcr-{n}", others, n), 2))
    teams = list(dict.fromkeys([w for _, w, _ in WORLD_CUP] + ["Pays-Bas", "Croatie", "Hongrie", "Suède", "Tchécoslovaquie", "Portugal"]))
    hosts = list(dict.fromkeys(h for _, _, h in WORLD_CUP))
    for y, w, h in WORLD_CUP:
        out.append(make("sport", f"Quelle équipe a gagné la Coupe du monde de football {y} ?", w, pick(f"wc-{y}", teams, w), 1 if y >= 1998 else 2 if y >= 1970 else 3))
        out.append(make("sport", f"Quel pays a organisé la Coupe du monde de football {y} ?", h, pick(f"wch-{y}", hosts + ["Suisse", "Allemagne"], h), 2 if y >= 1990 else 3))
    eteams = list(dict.fromkeys([w for _, w in EURO] + ["Belgique", "Angleterre", "Croatie", "Suisse"]))
    for y, w in EURO:
        out.append(make("sport", f"Quelle équipe a gagné l'Euro de football {y} ?", w, pick(f"eu-{y}", eteams, w), 2 if y >= 1984 else 3))
    cities = list(dict.fromkeys(c for _, c in SUMMER))
    for y, c in SUMMER:
        out.append(make("sport", f"Quelle ville a accueilli (ou accueillera) les Jeux olympiques d'été de {y} ?", c, pick(f"ol-{y}", cities, c), 1 if y >= 2000 else 2 if y >= 1960 else 3))
    once = [c for c in cities if sum(1 for _, x in SUMMER if x == c) == 1]
    for y, c in SUMMER:
        if c in once:
            years = [str(yy) for yy, _ in SUMMER if abs(yy - y) <= 24 and yy != y]
            out.append(make("sport", f"En quelle année {c} a-t-elle accueilli les Jeux olympiques d'été ?", str(y), pick(f"oly-{c}", years, str(y)), 2 if y >= 1980 else 3))
    wcities = list(dict.fromkeys(c for _, c in WINTER))
    for y, c in WINTER:
        out.append(make("sport", f"Quelle station ou ville a accueilli les Jeux olympiques d'hiver de {y} ?", c, pick(f"olw-{y}", wcities, c), 2 if y >= 1988 else 3))
    drivers = list(dict.fromkeys(d for _, d in F1_CHAMPIONS))
    for y, d in F1_CHAMPIONS:
        near = [x for yy, x in F1_CHAMPIONS if abs(yy - y) <= 8 and x != d] + drivers
        out.append(make("sport", f"Qui a été champion du monde de Formule 1 en {y} ?", d, pick(f"f1-{y}", near, d), 2 if y >= 2008 else 3))
    ccities = list(dict.fromkeys(c for _, c in CLUBS))
    for club, city in CLUBS:
        out.append(make("sport", f"Dans quelle ville joue {club} ?", city, pick(f"club-{club}", ccities, city), 2))
    for d, q, a, w in WRITTEN:
        out.append(make("sport", q, a, w, d))
    return out
