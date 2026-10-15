"""Culture générale : livres, tableaux, monuments, inventions, mythologie, chiffres romains, expressions, questions rédigées."""

import random

from . import make, pick
from .gen_histoire import roman

# (œuvre, auteur)
BOOKS = [
    ("Les Misérables", "Victor Hugo"), ("Notre-Dame de Paris", "Victor Hugo"), ("Germinal", "Émile Zola"), ("L'Assommoir", "Émile Zola"),
    ("Madame Bovary", "Gustave Flaubert"), ("Le Rouge et le Noir", "Stendhal"), ("La Chartreuse de Parme", "Stendhal"), ("Le Père Goriot", "Honoré de Balzac"),
    ("Eugénie Grandet", "Honoré de Balzac"), ("Les Trois Mousquetaires", "Alexandre Dumas"), ("Le Comte de Monte-Cristo", "Alexandre Dumas"),
    ("Vingt Mille Lieues sous les mers", "Jules Verne"), ("Le Tour du monde en quatre-vingts jours", "Jules Verne"), ("Voyage au centre de la Terre", "Jules Verne"),
    ("Le Petit Prince", "Antoine de Saint-Exupéry"), ("Vol de nuit", "Antoine de Saint-Exupéry"), ("L'Étranger", "Albert Camus"), ("La Peste", "Albert Camus"),
    ("Huis clos", "Jean-Paul Sartre"), ("La Nausée", "Jean-Paul Sartre"), ("Le Deuxième Sexe", "Simone de Beauvoir"), ("À la recherche du temps perdu", "Marcel Proust"),
    ("Candide", "Voltaire"), ("Les Fleurs du mal", "Charles Baudelaire"), ("Les Fables", "Jean de La Fontaine"), ("Le Misanthrope", "Molière"),
    ("Le Bourgeois gentilhomme", "Molière"), ("L'Avare", "Molière"), ("Tartuffe", "Molière"), ("Le Cid", "Pierre Corneille"), ("Phèdre", "Jean Racine"),
    ("Andromaque", "Jean Racine"), ("Cyrano de Bergerac", "Edmond Rostand"), ("Le Horla", "Guy de Maupassant"), ("Bel-Ami", "Guy de Maupassant"),
    ("Les Liaisons dangereuses", "Choderlos de Laclos"), ("Gargantua", "François Rabelais"), ("Les Essais", "Michel de Montaigne"),
    ("Le Contrat social", "Jean-Jacques Rousseau"), ("Les Confessions", "Jean-Jacques Rousseau"), ("Bonjour tristesse", "Françoise Sagan"),
    ("Le Grand Meaulnes", "Alain-Fournier"), ("Thérèse Raquin", "Émile Zola"), ("La Dame aux camélias", "Alexandre Dumas fils"),
    ("Le Lion", "Joseph Kessel"), ("La Gloire de mon père", "Marcel Pagnol"), ("Le Petit Nicolas", "René Goscinny"), ("Zazie dans le métro", "Raymond Queneau"),
    ("Voyage au bout de la nuit", "Louis-Ferdinand Céline"), ("La Condition humaine", "André Malraux"), ("L'Écume des jours", "Boris Vian"),
    ("Le Parfum", "Patrick Süskind"), ("Les Rois maudits", "Maurice Druon"), ("Les Fourmis", "Bernard Werber"), ("L'Alchimiste", "Paulo Coelho"),
    ("Hamlet", "William Shakespeare"), ("Roméo et Juliette", "William Shakespeare"), ("Macbeth", "William Shakespeare"), ("Othello", "William Shakespeare"),
    ("Don Quichotte", "Miguel de Cervantès"), ("La Divine Comédie", "Dante"), ("L'Odyssée", "Homère"), ("L'Iliade", "Homère"),
    ("Guerre et Paix", "Léon Tolstoï"), ("Anna Karénine", "Léon Tolstoï"), ("Crime et Châtiment", "Fiodor Dostoïevski"), ("Les Frères Karamazov", "Fiodor Dostoïevski"),
    ("1984", "George Orwell"), ("La Ferme des animaux", "George Orwell"), ("Le Meilleur des mondes", "Aldous Huxley"), ("Fahrenheit 451", "Ray Bradbury"),
    ("Orgueil et Préjugés", "Jane Austen"), ("Jane Eyre", "Charlotte Brontë"), ("Les Hauts de Hurlevent", "Emily Brontë"), ("Oliver Twist", "Charles Dickens"),
    ("Un chant de Noël", "Charles Dickens"), ("Frankenstein", "Mary Shelley"), ("Dracula", "Bram Stoker"), ("Le Portrait de Dorian Gray", "Oscar Wilde"),
    ("Alice au pays des merveilles", "Lewis Carroll"), ("L'Île au trésor", "Robert Louis Stevenson"), ("Robinson Crusoé", "Daniel Defoe"),
    ("Les Voyages de Gulliver", "Jonathan Swift"), ("Moby Dick", "Herman Melville"), ("Les Aventures de Tom Sawyer", "Mark Twain"),
    ("Gatsby le Magnifique", "F. Scott Fitzgerald"), ("Le Vieil Homme et la Mer", "Ernest Hemingway"), ("Des souris et des hommes", "John Steinbeck"),
    ("Les Raisins de la colère", "John Steinbeck"), ("L'Attrape-cœurs", "J. D. Salinger"), ("Sur la route", "Jack Kerouac"), ("Lolita", "Vladimir Nabokov"),
    ("Cent ans de solitude", "Gabriel García Márquez"), ("Le Nom de la rose", "Umberto Eco"), ("Le Seigneur des anneaux", "J. R. R. Tolkien"),
    ("Le Hobbit", "J. R. R. Tolkien"), ("Harry Potter", "J. K. Rowling"), ("Le Monde de Narnia", "C. S. Lewis"), ("Da Vinci Code", "Dan Brown"),
    ("Le Trône de fer", "George R. R. Martin"), ("Shining", "Stephen King"), ("Ça", "Stephen King"), ("Le Journal d'Anne Frank", "Anne Frank"),
    ("Le Petit Chaperon rouge (version écrite de 1697)", "Charles Perrault"), ("La Métamorphose", "Franz Kafka"), ("Le Procès", "Franz Kafka"),
    ("Le Loup des steppes", "Hermann Hesse"), ("Siddhartha", "Hermann Hesse"), ("Les Souffrances du jeune Werther", "Goethe"), ("Faust", "Goethe"),
    ("Heidi", "Johanna Spyri"), ("La Vérité sur l'affaire Harry Quebert", "Joël Dicker"), ("Le Docteur Jivago", "Boris Pasternak"),
    ("L'Archipel du Goulag", "Alexandre Soljenitsyne"), ("Le Petit Lord Fauntleroy", "Frances Hodgson Burnett"), ("Les Quatre Filles du docteur March", "Louisa May Alcott"),
    ("Le Livre de la jungle", "Rudyard Kipling"), ("Peter Pan", "J. M. Barrie"), ("Pinocchio", "Carlo Collodi"), ("Le Magicien d'Oz", "L. Frank Baum"),
    ("Charlie et la Chocolaterie", "Roald Dahl"), ("Matilda", "Roald Dahl"),
    ("Sherlock Holmes", "Arthur Conan Doyle"), ("Arsène Lupin", "Maurice Leblanc"), ("Le Crime de l'Orient-Express", "Agatha Christie"),
    ("Ils étaient dix", "Agatha Christie"), ("Maigret", "Georges Simenon"), ("Le Silence des agneaux", "Thomas Harris"),
]
FAMOUS_BOOKS = {"Les Misérables", "Le Petit Prince", "Harry Potter", "Roméo et Juliette", "Les Trois Mousquetaires", "1984", "Germinal",
                "Le Seigneur des anneaux", "Vingt Mille Lieues sous les mers", "Les Fables", "Hamlet", "Sherlock Holmes", "Heidi", "L'Odyssée",
                "Le Tour du monde en quatre-vingts jours", "Candide", "Don Quichotte", "L'Avare", "Notre-Dame de Paris", "Le Comte de Monte-Cristo"}

# (tableau / œuvre d'art, artiste)
PAINTINGS = [
    ("La Joconde", "Léonard de Vinci"), ("La Cène", "Léonard de Vinci"), ("La Naissance de Vénus", "Botticelli"), ("La Création d'Adam", "Michel-Ange"),
    ("Le David (sculpture de Florence)", "Michel-Ange"), ("L'École d'Athènes", "Raphaël"), ("La Ronde de nuit", "Rembrandt"), ("La Jeune Fille à la perle", "Vermeer"),
    ("Les Ménines", "Vélasquez"), ("Le Tres de Mayo", "Goya"), ("La Liberté guidant le peuple", "Eugène Delacroix"), ("Le Radeau de La Méduse", "Théodore Géricault"),
    ("Le Sacre de Napoléon", "Jacques-Louis David"), ("Impression, soleil levant", "Claude Monet"), ("Les Nymphéas", "Claude Monet"),
    ("Le Déjeuner sur l'herbe", "Édouard Manet"), ("Olympia", "Édouard Manet"), ("Bal du moulin de la Galette", "Auguste Renoir"),
    ("La Nuit étoilée", "Vincent van Gogh"), ("Les Tournesols", "Vincent van Gogh"), ("Les Joueurs de cartes", "Paul Cézanne"),
    ("Le Cri", "Edvard Munch"), ("Le Baiser (tableau doré)", "Gustav Klimt"), ("Le Penseur (sculpture)", "Auguste Rodin"), ("Guernica", "Pablo Picasso"),
    ("Les Demoiselles d'Avignon", "Pablo Picasso"), ("La Persistance de la mémoire (montres molles)", "Salvador Dalí"), ("Ceci n'est pas une pipe", "René Magritte"),
    ("Le Fils de l'homme (pomme devant le visage)", "René Magritte"), ("Campbell's Soup Cans", "Andy Warhol"), ("Marilyn Diptych", "Andy Warhol"),
    ("Nighthawks", "Edward Hopper"), ("American Gothic", "Grant Wood"), ("Composition en rouge, jaune et bleu", "Piet Mondrian"),
    ("La Danse", "Henri Matisse"), ("Les Glaneuses", "Jean-François Millet"), ("Un dimanche après-midi à l'île de la Grande Jatte", "Georges Seurat"),
    ("La Grande Vague de Kanagawa", "Hokusai"), ("Le Jardin des délices", "Jérôme Bosch"), ("Les Époux Arnolfini", "Jan van Eyck"),
    ("La Vénus d'Urbin", "Titien"), ("L'Homme qui marche (sculpture)", "Alberto Giacometti"), ("Le Bœuf écorché", "Rembrandt"),
    ("Au Moulin Rouge", "Henri de Toulouse-Lautrec"), ("Les Coquelicots", "Claude Monet"), ("L'Absinthe", "Edgar Degas"),
    ("La Classe de danse", "Edgar Degas"), ("Le Bain turc", "Jean-Auguste-Dominique Ingres"), ("La Grande Odalisque", "Jean-Auguste-Dominique Ingres"),
    ("Le Rêve (femme endormie sur un fauteuil rouge)", "Pablo Picasso"), ("Le Voyageur contemplant une mer de nuages", "Caspar David Friedrich"),
    ("Saturne dévorant un de ses fils", "Goya"), ("La Tour de Babel", "Pieter Bruegel l'Ancien"), ("Le Mont Sainte-Victoire (série)", "Paul Cézanne"),
]
ARTISTS_EXTRA = ["Paul Gauguin", "Paul Klee", "Wassily Kandinsky", "Joan Miró", "Marc Chagall", "Ferdinand Hodler", "Caravage", "Rubens"]

# (monument, ville)
MONUMENTS = [
    ("la tour Eiffel", "Paris"), ("l'Arc de triomphe de l'Étoile", "Paris"), ("le Sacré-Cœur", "Paris"), ("le Colisée", "Rome"), ("la fontaine de Trevi", "Rome"),
    ("le Panthéon antique", "Rome"), ("la tour penchée", "Pise"), ("le pont du Rialto", "Venise"), ("la place Saint-Marc", "Venise"), ("le Duomo de Brunelleschi", "Florence"),
    ("la Sagrada Família", "Barcelone"), ("le parc Güell", "Barcelone"), ("l'Alhambra", "Grenade"), ("le musée du Prado", "Madrid"), ("la tour de Belém", "Lisbonne"),
    ("Big Ben", "Londres"), ("le Tower Bridge", "Londres"), ("le palais de Buckingham", "Londres"), ("la porte de Brandebourg", "Berlin"),
    ("le château de Neuschwanstein (près de)", "Füssen"), ("la cathédrale de Cologne", "Cologne"), ("l'Atomium", "Bruxelles"), ("le Manneken-Pis", "Bruxelles"),
    ("le Rijksmuseum", "Amsterdam"), ("la Petite Sirène", "Copenhague"), ("le pont Charles", "Prague"), ("le Parlement hongrois au bord du Danube", "Budapest"),
    ("l'Acropole", "Athènes"), ("Sainte-Sophie", "Istanbul"), ("la Mosquée bleue", "Istanbul"), ("le Kremlin", "Moscou"), ("la cathédrale Saint-Basile", "Moscou"),
    ("le musée de l'Ermitage", "Saint-Pétersbourg"), ("la statue de la Liberté", "New York"), ("l'Empire State Building", "New York"), ("Central Park", "New York"),
    ("le Golden Gate Bridge", "San Francisco"), ("la Maison-Blanche", "Washington"), ("le Capitole des États-Unis", "Washington"),
    ("le Christ Rédempteur", "Rio de Janeiro"), ("le Pain de Sucre", "Rio de Janeiro"), ("l'Opéra de Sydney", "Sydney"), ("la Cité interdite", "Pékin"),
    ("la place Tian'anmen", "Pékin"), ("le Burj Khalifa", "Dubaï"), ("les tours Petronas", "Kuala Lumpur"), ("le Taj Mahal", "Agra"),
    ("le temple d'Or", "Amritsar"), ("le Pavillon d'or (Kinkaku-ji)", "Kyoto"), ("la tour CN", "Toronto"), ("le Space Needle", "Seattle"),
    ("la tour Montparnasse", "Paris"), ("le jet d'eau", "Genève"), ("le pont de la Chapelle (Kapellbrücke)", "Lucerne"),
    ("la Zytglogge (tour de l'horloge)", "Berne"), ("le château de Chillon (près de)", "Montreux"), ("la cathédrale Notre-Dame", "Lausanne"),
    ("le Grossmünster", "Zurich"), ("le Palais des Nations", "Genève"), ("le musée olympique", "Lausanne"), ("la Mole Antonelliana", "Turin"),
    ("le palais des Papes", "Avignon"), ("la cité médiévale fortifiée", "Carcassonne"), ("la basilique Notre-Dame de Fourvière", "Lyon"),
    ("Notre-Dame de la Garde", "Marseille"), ("la promenade des Anglais", "Nice"), ("la cathédrale Notre-Dame (plus haute flèche de France)", "Rouen"),
    ("le Mur des Lamentations", "Jérusalem"), ("les pyramides de Gizeh (près de)", "Le Caire"), ("la mosquée Hassan-II", "Casablanca"),
    ("la place Jemaa el-Fna", "Marrakech"), ("Times Square", "New York"), ("le Hollywood Sign", "Los Angeles"), ("le Strip", "Las Vegas"),
]

# (invention, inventeur)
INVENTIONS = [
    ("l'imprimerie à caractères mobiles (en Europe)", "Gutenberg"), ("le téléphone (brevet de 1876)", "Graham Bell"), ("l'ampoule à incandescence (commerciale)", "Thomas Edison"),
    ("le phonographe", "Thomas Edison"), ("la dynamite", "Alfred Nobel"), ("le cinématographe", "les frères Lumière"), ("la radio (TSF)", "Guglielmo Marconi"),
    ("le moteur diesel", "Rudolf Diesel"), ("le premier avion motorisé", "les frères Wright"), ("la montgolfière", "les frères Montgolfier"),
    ("le paratonnerre", "Benjamin Franklin"), ("la pile électrique", "Alessandro Volta"), ("le vaccin contre la rage", "Louis Pasteur"), ("la pasteurisation", "Louis Pasteur"),
    ("la machine à vapeur (améliorée)", "James Watt"), ("le braille", "Louis Braille"), ("le stéthoscope", "René Laennec"), ("la photographie (première image fixe)", "Nicéphore Niépce"),
    ("le télégraphe électrique et son code", "Samuel Morse"), ("le World Wide Web", "Tim Berners-Lee"), ("la pénicilline", "Alexander Fleming"),
    ("la machine à calculer (Pascaline)", "Blaise Pascal"), ("le Velcro", "George de Mestral"), ("le couteau suisse (couteau du soldat)", "Karl Elsener"),
    ("la cellophane", "Jacques Brandenberger"), ("le LSD (synthèse)", "Albert Hofmann"), ("le café soluble Nescafé", "Max Morgenthaler"),
    ("le chocolat au lait", "Daniel Peter"), ("le chocolat fondant (conchage)", "Rodolphe Lindt"), ("le tracteur à chenilles", "Benjamin Holt"),
    ("le stylo-bille (moderne)", "László Biró"), ("le gyroscope", "Léon Foucault"),
    ("le pendule démontrant la rotation de la Terre", "Léon Foucault"), ("le parachute (premier saut moderne)", "André-Jacques Garnerin"),
    ("la télévision mécanique", "John Logie Baird"), ("le moteur à combustion à quatre temps", "Nikolaus Otto"),
    ("l'automobile à essence (brevet 1886)", "Karl Benz"), ("la machine à coudre (brevet français)", "Barthélemy Thimonnier"), ("le jean (rivets)", "Levi Strauss et Jacob Davis"),
    ("le Rubik's Cube", "Ernő Rubik"), ("la carte à puce", "Roland Moreno"), ("le scaphandre autonome", "Cousteau et Gagnan"),
    ("le Bic Cristal (production de masse)", "Marcel Bich"), ("le Post-it", "Spencer Silver et Art Fry"), ("le micro-ondes", "Percy Spencer"),
]

# Mythologie grecque → équivalent romain
MYTHO = [("Zeus", "Jupiter"), ("Héra", "Junon"), ("Poséidon", "Neptune"), ("Hadès", "Pluton"), ("Athéna", "Minerve"), ("Arès", "Mars"),
         ("Aphrodite", "Vénus"), ("Hermès", "Mercure"), ("Héphaïstos", "Vulcain"), ("Artémis", "Diane"), ("Déméter", "Cérès"), ("Dionysos", "Bacchus"),
         ("Hestia", "Vesta"), ("Éros", "Cupidon"), ("Cronos", "Saturne"), ("Héraclès", "Hercule"), ("Perséphone", "Proserpine"), ("Gaïa", "Tellus")]
MYTHO_ROLES = [("Zeus", "le roi des dieux, maître de la foudre"), ("Poséidon", "le dieu des mers"), ("Hadès", "le dieu des Enfers"),
               ("Athéna", "la déesse de la sagesse"), ("Arès", "le dieu de la guerre"), ("Aphrodite", "la déesse de l'amour"),
               ("Hermès", "le messager des dieux"), ("Héphaïstos", "le dieu du feu et des forgerons"), ("Artémis", "la déesse de la chasse"),
               ("Déméter", "la déesse des moissons"), ("Dionysos", "le dieu du vin et de la fête"), ("Apollon", "le dieu de la lumière et des arts"),
               ("Héra", "la déesse du mariage, épouse de Zeus"), ("Hestia", "la déesse du foyer"), ("Nyx", "la déesse de la nuit"),
               ("Hypnos", "le dieu du sommeil"), ("Thanatos", "la personnification de la mort"), ("Éole", "le maître des vents"),
               ("Némésis", "la déesse de la vengeance"), ("Nikê", "la déesse de la victoire")]
NORSE = [("Odin", "le père des dieux nordiques"), ("Thor", "le dieu du tonnerre au marteau"), ("Loki", "le dieu de la ruse"),
         ("Freyja", "la déesse de l'amour et de la fertilité"), ("Baldr", "le dieu de la lumière, tué par le gui"), ("Heimdall", "le gardien du pont Bifröst")]
EGYPT = [("Râ", "le dieu du Soleil"), ("Anubis", "le dieu à tête de chacal, gardien des morts"), ("Osiris", "le dieu des morts et de la résurrection"),
         ("Isis", "la déesse de la magie, épouse d'Osiris"), ("Horus", "le dieu à tête de faucon"), ("Thot", "le dieu de l'écriture à tête d'ibis"),
         ("Bastet", "la déesse à tête de chat"), ("Seth", "le dieu du chaos et du désert")]

# Expressions : début → fin
SAYINGS = [
    ("Qui vole un œuf…", "vole un bœuf"), ("Petit à petit…", "l'oiseau fait son nid"), ("Pierre qui roule…", "n'amasse pas mousse"),
    ("L'habit ne fait pas…", "le moine"), ("Tel père…", "tel fils"), ("Après la pluie…", "le beau temps"), ("Qui sème le vent…", "récolte la tempête"),
    ("Il ne faut pas vendre la peau de l'ours…", "avant de l'avoir tué"), ("Quand le chat n'est pas là…", "les souris dansent"),
    ("Mieux vaut tard…", "que jamais"), ("La nuit, tous les chats…", "sont gris"), ("Rien ne sert de courir…", "il faut partir à point"),
    ("Chat échaudé…", "craint l'eau froide"), ("Qui va à la chasse…", "perd sa place"), ("Les absents…", "ont toujours tort"),
    ("Une hirondelle…", "ne fait pas le printemps"), ("Tant va la cruche à l'eau…", "qu'à la fin elle se casse"),
    ("Il n'y a pas de fumée…", "sans feu"), ("L'appétit vient…", "en mangeant"), ("Loin des yeux…", "loin du cœur"),
    ("Qui ne risque rien…", "n'a rien"), ("Les bons comptes font…", "les bons amis"), ("Il faut battre le fer…", "tant qu'il est chaud"),
    ("Qui se ressemble…", "s'assemble"), ("Un tiens vaut mieux…", "que deux tu l'auras"), ("Paris ne s'est pas fait…", "en un jour"),
    ("En avril, ne te découvre pas…", "d'un fil"), ("À cheval donné…", "on ne regarde pas les dents"), ("Mieux vaut prévenir…", "que guérir"),
    ("L'argent ne fait pas…", "le bonheur"), ("Il ne faut jamais dire : Fontaine…", "je ne boirai pas de ton eau"), ("Abondance de biens…", "ne nuit pas"),
    ("Qui aime bien…", "châtie bien"), ("La parole est d'argent…", "le silence est d'or"), ("C'est en forgeant…", "qu'on devient forgeron"),
    ("Tous les chemins mènent…", "à Rome"), ("Vouloir, c'est…", "pouvoir"), ("Œil pour œil…", "dent pour dent"), ("Aux grands maux…", "les grands remèdes"),
    ("L'union fait…", "la force"), ("Le temps, c'est…", "de l'argent"), ("Il ne faut pas mettre tous ses œufs…", "dans le même panier"),
    ("Charité bien ordonnée…", "commence par soi-même"), ("Plus on est de fous…", "plus on rit"), ("Les chiens aboient…", "la caravane passe"),
    ("Qui trop embrasse…", "mal étreint"), ("Bien mal acquis…", "ne profite jamais"), ("Il faut tourner sa langue sept fois…", "dans sa bouche avant de parler"),
]
IDIOMS = [  # expression → sens
    ("Poser un lapin", "Ne pas venir à un rendez-vous"), ("Avoir le cafard", "Être triste, déprimé"), ("Coûter les yeux de la tête", "Coûter très cher"),
    ("Tomber dans les pommes", "S'évanouir"), ("Avoir la tête dans les nuages", "Être distrait, rêveur"), ("Mettre la main à la pâte", "Participer au travail"),
    ("Casser les pieds", "Ennuyer, agacer"), ("Avoir un poil dans la main", "Être paresseux"), ("Donner sa langue au chat", "Renoncer à deviner"),
    ("Être dans la lune", "Être distrait"), ("Avoir le coup de foudre", "Tomber amoureux immédiatement"), ("Raconter des salades", "Mentir, raconter des histoires"),
    ("Mettre les pieds dans le plat", "Aborder maladroitement un sujet délicat"), ("Avoir du pain sur la planche", "Avoir beaucoup de travail"),
    ("Faire la grasse matinée", "Se lever tard"), ("Prendre ses jambes à son cou", "S'enfuir en courant"), ("Avoir la chair de poule", "Avoir froid ou peur"),
    ("Être sur son trente-et-un", "Être très bien habillé"), ("Mettre de l'eau dans son vin", "Modérer ses exigences"), ("Tirer les vers du nez", "Faire parler quelqu'un"),
    ("Avoir les dents longues", "Être très ambitieux"), ("Se mettre le doigt dans l'œil", "Se tromper complètement"), ("Faire chou blanc", "Échouer"),
    ("Avoir une dent contre quelqu'un", "Lui en vouloir"), ("Être un cordon-bleu", "Très bien cuisiner"), ("Passer l'arme à gauche", "Mourir"),
    ("Mettre la puce à l'oreille", "Éveiller les soupçons"), ("Payer en monnaie de singe", "Ne pas payer, payer en grimaces"), ("Avoir le bras long", "Avoir de l'influence"),
    ("Tourner autour du pot", "Ne pas aller droit au but"), ("Se serrer la ceinture", "Faire des économies"), ("Avoir la main verte", "Être doué pour le jardinage"),
    ("Jeter l'éponge", "Abandonner"), ("Être aux anges", "Être très heureux"), ("Prendre la mouche", "Se vexer"), ("Faire la sourde oreille", "Faire semblant de ne pas entendre"),
    ("Avoir un cœur d'artichaut", "Tomber facilement amoureux"), ("Ne pas avoir la langue dans sa poche", "Parler facilement, avoir la répartie"),
    ("Être soupe au lait", "S'emporter facilement"), ("Voir trente-six chandelles", "Être étourdi par un coup"),
]

# Orthographe : bonne graphie, puis 3 fautes fréquentes
SPELLING = [
    ("développement", ["dévelopement", "développemment", "dévellopement"]), ("connexion", ["connection", "conexion", "connexsion"]),
    ("événement", ["évenement", "évènnement", "éveinement"]), ("parallèle", ["parralèle", "paralèlle", "parallelle"]),
    ("rythme", ["rhytme", "rytme", "rhythme"]), ("accueil", ["acceuil", "acueil", "accueuil"]), ("chrysanthème", ["chrisanthème", "chrysantème", "crysanthème"]),
    ("néanmoins", ["néamoins", "néanmoin", "nénmoins"]), ("occurrence", ["occurence", "ocurrence", "occurance"]), ("abasourdi", ["abasourdit", "abbasourdi", "abassourdi"]),
    ("acquérir", ["aquérir", "acquérire", "accquérir"]), ("hémorragie", ["hémoragie", "hémoraggie", "émorragie"]), ("langage", ["language", "languaje", "langague"]),
    ("apparemment", ["apparament", "aparemment", "apparamment"]), ("vraisemblable", ["vraissemblable", "vraisemblabe", "vraisemblaple"]),
    ("dilemme", ["dilemne", "dillemme", "dilème"]), ("exercice", ["exercise", "excercice", "exercisse"]), ("succinct", ["succint", "succinc", "sucinct"]),
    ("fainéant", ["fénéant", "fainéan", "faignéant"]), ("quatre-vingts", ["quatre-vingt-s", "quatres-vingts", "quatre-vint"]),
    ("guetter", ["gueter", "guéter", "gettre"]), ("aéroport", ["aéreport", "aréoport", "aéropore"]), ("bizarre", ["bizare", "bisarre", "bizzare"]),
    ("hypothèse", ["hipothèse", "hypotèse", "hypothése"]), ("jusqu'ici", ["jusque ici", "jusqu'issi", "jusk'ici"]), ("ambiguïté", ["ambiguité", "ambigüité", "ambiguitée"]),
    ("pharmacie", ["farmacie", "pharmaçie", "pharmasie"]), ("athlète", ["athlette", "atlète", "athléte"]), ("mnémotechnique", ["mnémothechnique", "némotechnique", "mnémotecnique"]),
    ("chiffre", ["chifre", "chiffe", "chiffrre"]), ("caractère", ["charactère", "caractére", "carractère"]), ("tranquillité", ["tranquilité", "tranquillitée", "trankillité"]),
    ("aujourd'hui", ["aujourdhui", "aujourd'hui'", "aujour d'hui"]), ("excellent", ["exellent", "excelent", "excellant"]), ("intéressant", ["interressant", "intéréssant", "intéresant"]),
    ("professionnel", ["proffessionnel", "professionel", "profesionnel"]), ("appeler", ["apeler", "appelerr", "applerr"]), ("rationnel", ["rationel", "rassionnel", "rationnell"]),
    ("courrier", ["courier", "couriers", "courrié"]), ("bibliothèque", ["bibliotèque", "biblioteque", "bibliothéque"]), ("orthographe", ["ortographe", "orthografe", "orthographie"]),
]

# Pluriels : (singulier, bon pluriel, 3 faux)
PLURALS = [
    ("un cheval", "des chevaux", ["des chevals", "des chevaus", "des chevaulx"]), ("un œil", "des yeux", ["des œils", "des œuils", "des yeuxs"]),
    ("un bijou", "des bijoux", ["des bijous", "des bijoues", "des bijou"]), ("un caillou", "des cailloux", ["des caillous", "des caillouxs", "des caillou"]),
    ("un genou", "des genoux", ["des genous", "des genouxs", "des genou"]), ("un travail", "des travaux", ["des travails", "des travails (au sens d'ouvrages)", "des travailles"]),
    ("un vitrail", "des vitraux", ["des vitrails", "des vitraill", "des vitrailles"]), ("un bal", "des bals", ["des baux", "des bales", "des bal"]),
    ("un festival", "des festivals", ["des festivaux", "des festivales", "des festivaus"]), ("un carnaval", "des carnavals", ["des carnavaux", "des carnavales", "des carnavaus"]),
    ("un chacal", "des chacals", ["des chacaux", "des chacales", "des chacaus"]), ("un récital", "des récitals", ["des récitaux", "des récitales", "des récitaus"]),
    ("un landau", "des landaus", ["des landaux", "des landeaux", "des landau"]), ("un pneu", "des pneus", ["des pneux", "des pneues", "des pneu"]),
    ("un hibou", "des hiboux", ["des hibous", "des hibouxs", "des hibou"]), ("un pou", "des poux", ["des pous", "des poues", "des pou"]),
    ("un chou", "des choux", ["des chous", "des choues", "des chou"]), ("un idéal (au masculin, usage courant)", "des idéaux", ["des idéales", "des idéauxs", "des idéals (seule forme)"]),
    ("un monsieur", "des messieurs", ["des monsieurs", "des messieur", "des mes sieurs"]), ("un détail", "des détails", ["des détaux", "des détailles", "des détail"]),
    ("un éventail", "des éventails", ["des éventaux", "des éventailles", "des éventail"]), ("un journal", "des journaux", ["des journals", "des journales", "des journaus"]),
    ("un animal", "des animaux", ["des animals", "des animales", "des animaus"]), ("un bateau", "des bateaux", ["des bateaus", "des bateauxs", "des bateau"]),
    ("un feu", "des feux", ["des feus", "des feuxs", "des feues"]), ("un nez", "des nez", ["des nezs", "des nés", "des nezes"]),
]
PLURALS = [(a, b, [x for x in c if "(" not in x] + ["des " + a.split()[-1] + "es"]) for a, b, c in PLURALS]

WRITTEN = [
    (1, "Combien de jours compte une année bissextile ?", "366", ["365", "364", "367"]),
    (1, "Combien de mois ont 31 jours ?", "7", ["6", "5", "8"]),
    (1, "Quel mois compte 28 ou 29 jours ?", "Février", ["Avril", "Juin", "Novembre"]),
    (2, "Quel est le premier mois de l'année du calendrier romain primitif ?", "Mars", ["Janvier", "Avril", "Septembre"]),
    (2, "D'où vient le nom « juillet » ?", "De Jules César", ["De Junon", "De Jupiter", "De Julius Agricola"]),
    (2, "D'où vient le nom « août » ?", "De l'empereur Auguste", ["Du dieu Auguste", "Du latin « chaleur »", "De la moisson"]),
    (2, "Quel jour de la semaine doit son nom à la Lune ?", "Lundi", ["Mardi", "Dimanche", "Samedi"]),
    (2, "Quel jour de la semaine doit son nom à Mars ?", "Mardi", ["Mercredi", "Lundi", "Jeudi"]),
    (2, "Quel jour de la semaine doit son nom à Vénus ?", "Vendredi", ["Mercredi", "Samedi", "Jeudi"]),
    (2, "Quel jour de la semaine doit son nom à Jupiter ?", "Jeudi", ["Mardi", "Vendredi", "Samedi"]),
    (2, "Quel jour de la semaine doit son nom à Mercure ?", "Mercredi", ["Mardi", "Jeudi", "Vendredi"]),
    (2, "Comment appelle-t-on la peur des araignées ?", "L'arachnophobie", ["L'agoraphobie", "La claustrophobie", "L'acrophobie"]),
    (2, "Comment appelle-t-on la peur des espaces clos ?", "La claustrophobie", ["L'agoraphobie", "L'acrophobie", "L'arachnophobie"]),
    (2, "Comment appelle-t-on la peur du vide et des hauteurs ?", "L'acrophobie", ["La claustrophobie", "L'agoraphobie", "L'hydrophobie"]),
    (2, "Comment appelle-t-on la peur des foules et des espaces publics ?", "L'agoraphobie", ["La xénophobie", "La claustrophobie", "L'acrophobie"]),
    (2, "Comment appelle-t-on la collection de timbres ?", "La philatélie", ["La numismatique", "La cartophilie", "La glyptique"]),
    (2, "Comment appelle-t-on la collection de pièces de monnaie ?", "La numismatique", ["La philatélie", "La héraldique", "La sigillographie"]),
    (3, "Comment appelle-t-on la collection de capsules de champagne ?", "La placomusophilie", ["La tyrosémiophilie", "La copocléphilie", "La glycophilie"]),
    (3, "Comment appelle-t-on la collection d'étiquettes de fromage ?", "La tyrosémiophilie", ["La placomusophilie", "La fromagophilie", "La labellophilie"]),
    (2, "Quelle science étudie les blasons ?", "L'héraldique", ["La numismatique", "La généalogie", "La sigillographie"]),
    (2, "Quel est le féminin de « empereur » ?", "Impératrice", ["Empereuse", "Empereresse", "Emperesse"]),
    (2, "Quel est le féminin de « duc » ?", "Duchesse", ["Ducale", "Duquesse", "Ducesse"]),
    (2, "Combien font une douzaine ?", "12", ["10", "13", "20"]),
    (2, "Combien font une grosse (unité de compte) ?", "144", ["100", "120", "200"]),
    (3, "Combien vaut une « chiliade » ?", "1000", ["100", "10 000", "12"]),
    (1, "Combien de semaines y a-t-il dans une année ?", "52", ["48", "50", "54"]),
    (1, "Combien de joueurs compose une équipe de football sur le terrain ?", "11", ["10", "12", "9"]),
    (1, "Quelle est la couleur obtenue en mélangeant du bleu et du jaune ?", "Vert", ["Violet", "Orange", "Marron"]),
    (1, "Quelle couleur obtient-on en mélangeant du rouge et du blanc ?", "Rose", ["Violet", "Orange", "Saumon"]),
    (1, "Combien de cartes compte un jeu classique ?", "52", ["32", "54", "48"]),
    (2, "Combien de cartes compte un jeu de Jass suisse ?", "36", ["32", "40", "52"]),
    (1, "Combien de cases a un échiquier ?", "64", ["49", "81", "100"]),
    (2, "Quelle pièce des échecs ne peut se déplacer qu'en « L » ?", "Le cavalier", ["Le fou", "La tour", "Le pion"]),
    (2, "Quel est le seul mouvement où deux pièces bougent en même temps aux échecs ?", "Le roque", ["La prise en passant", "La promotion", "Le pat"]),
    (2, "Combien de points comptent les faces opposées d'un dé additionnées ?", "7", ["6", "8", "12"]),
    (2, "Combien de dominos compte un jeu classique ?", "28", ["24", "32", "36"]),
    (1, "Combien de couleurs a l'arc-en-ciel (traditionnellement) ?", "7", ["5", "6", "8"]),
    (1, "Quel est l'anniversaire de mariage pour 50 ans ?", "Les noces d'or", ["Les noces d'argent", "Les noces de diamant", "Les noces de platine"]),
    (2, "Quel est l'anniversaire de mariage pour 25 ans ?", "Les noces d'argent", ["Les noces d'or", "Les noces de perle", "Les noces de cristal"]),
    (2, "Quel est l'anniversaire de mariage pour 60 ans ?", "Les noces de diamant", ["Les noces d'or", "Les noces de platine", "Les noces de chêne"]),
    (3, "Quel est l'anniversaire de mariage pour 1 an ?", "Les noces de coton", ["Les noces de papier", "Les noces de cuir", "Les noces de bois"]),
    (1, "Quel est le symbole de la paix ?", "La colombe", ["L'aigle", "Le lion", "Le hibou"]),
    (1, "Combien de branches a l'étoile de David ?", "6", ["5", "7", "8"]),
    (2, "Quelle langue est la plus parlée au monde (locuteurs natifs) ?", "Le mandarin", ["L'anglais", "L'espagnol", "L'hindi"]),
    (2, "Combien de langues nationales compte la Suisse ?", "4", ["3", "2", "5"]),
    (2, "Quelle est la langue officielle du Brésil ?", "Le portugais", ["L'espagnol", "Le brésilien", "Le français"]),
    (2, "Dans quel alphabet écrit-on le russe ?", "Le cyrillique", ["Le grec", "Le latin", "L'arabe"]),
    (2, "Combien de lettres compte l'alphabet français ?", "26", ["24", "25", "28"]),
    (2, "Quelle est la lettre la plus utilisée en français ?", "E", ["A", "S", "I"]),
    (2, "Comment appelle-t-on un mot qui se lit dans les deux sens, comme « kayak » ?", "Un palindrome", ["Un anagramme", "Un homonyme", "Un acronyme"]),
    (2, "Comment appelle-t-on un mot formé avec les lettres d'un autre mot ?", "Une anagramme", ["Un palindrome", "Un synonyme", "Un pléonasme"]),
    (2, "Comment appelle-t-on des mots qui se prononcent pareil mais s'écrivent différemment ?", "Des homophones", ["Des synonymes", "Des antonymes", "Des paronymes"]),
    (2, "Comment appelle-t-on une répétition inutile, comme « monter en haut » ?", "Un pléonasme", ["Un oxymore", "Une litote", "Une hyperbole"]),
    (2, "Comment appelle-t-on l'association de deux mots contraires, comme « obscure clarté » ?", "Un oxymore", ["Un pléonasme", "Une métaphore", "Une antithèse"]),
    (2, "« Va, je ne te hais point » est un exemple célèbre de…", "Litote", ["Hyperbole", "Métaphore", "Oxymore"]),
    (1, "Quel animal est le symbole de la France ?", "Le coq", ["L'aigle", "Le lion", "L'ours"]),
    (1, "Quel animal est le symbole de la ville de Berne ?", "L'ours", ["Le lion", "L'aigle", "Le taureau"]),
    (2, "Quelle est la devise de la France ?", "Liberté, Égalité, Fraternité", ["Travail, Famille, Patrie", "Un pour tous, tous pour un", "Dieu et mon droit"]),
    (2, "Quelle est la devise traditionnelle de la Suisse ?", "Un pour tous, tous pour un", ["Liberté, Égalité, Fraternité", "L'union fait la force", "In God We Trust"]),
    (2, "Quelle est la devise de la Belgique ?", "L'union fait la force", ["Un pour tous, tous pour un", "Dieu et mon droit", "Unie dans la diversité"]),
    (2, "Qui est l'auteur de la phrase « Je pense, donc je suis » ?", "René Descartes", ["Blaise Pascal", "Voltaire", "Socrate"]),
    (2, "Qui a dit « Je sais que je ne sais rien » ?", "Socrate", ["Platon", "Aristote", "Diogène"]),
    (2, "Qui a écrit « L'homme est un roseau pensant » ?", "Blaise Pascal", ["Descartes", "Montaigne", "Rousseau"]),
    (2, "Quel philosophe vivait dans un tonneau selon la légende ?", "Diogène", ["Socrate", "Platon", "Épicure"]),
    (2, "Qui a dit « L'enfer, c'est les autres » ?", "Jean-Paul Sartre", ["Albert Camus", "Simone de Beauvoir", "Victor Hugo"]),
    (2, "Qui a écrit « On ne naît pas femme : on le devient » ?", "Simone de Beauvoir", ["Simone Veil", "George Sand", "Marguerite Duras"]),
    (2, "Quelle est la plus haute distinction honorifique française ?", "La Légion d'honneur", ["L'ordre du Mérite", "La croix de guerre", "La médaille militaire"]),
    (2, "Dans quelle ville sont remis les prix Nobel (sauf celui de la paix) ?", "Stockholm", ["Oslo", "Copenhague", "Genève"]),
    (2, "Dans quelle ville est remis le prix Nobel de la paix ?", "Oslo", ["Stockholm", "Genève", "La Haye"]),
    (2, "Quel prix littéraire français est le plus célèbre ?", "Le prix Goncourt", ["Le prix Renaudot", "Le prix Femina", "Le prix Médicis"]),
    (2, "Quel musée abrite la Joconde ?", "Le Louvre", ["Le musée d'Orsay", "Le Prado", "Les Offices"]),
    (2, "Dans quel musée se trouve « La Naissance de Vénus » ?", "La galerie des Offices (Florence)", ["Le Louvre", "Le Vatican", "Le Prado"]),
    (2, "Dans quelle ville se trouve le musée Van Gogh ?", "Amsterdam", ["Bruxelles", "Paris", "La Haye"]),
    (2, "Quel courant artistique Monet a-t-il fondé ?", "L'impressionnisme", ["Le cubisme", "Le fauvisme", "Le surréalisme"]),
    (2, "Quel courant Picasso et Braque ont-ils créé ?", "Le cubisme", ["Le pointillisme", "L'expressionnisme", "Le dadaïsme"]),
    (2, "Quel mouvement artistique est né à Zurich en 1916 au Cabaret Voltaire ?", "Le dadaïsme", ["Le surréalisme", "Le futurisme", "Le Bauhaus"]),
    (2, "Quel architecte suisse a conçu la Cité radieuse de Marseille ?", "Le Corbusier", ["Mario Botta", "Bernard Tschumi", "Peter Zumthor"]),
    (2, "Sous quel nom est connu l'architecte Charles-Édouard Jeanneret ?", "Le Corbusier", ["Hergé", "Blaise Cendrars", "Mario Botta"]),
    (2, "Quel est le plus long fleuve du monde (selon la plupart des mesures) ?", "Le Nil", ["L'Amazone", "Le Yangzi Jiang", "Le Mississippi"]),
    (1, "Quel est le plus grand animal du monde ?", "La baleine bleue", ["L'éléphant d'Afrique", "Le requin-baleine", "La girafe"]),
    (1, "Quelle est la capitale de l'Italie ?", "Rome", ["Milan", "Naples", "Turin"]),
    (2, "Que représentent les cinq anneaux olympiques ?", "Les cinq continents", ["Les cinq océans", "Les cinq valeurs", "Les cinq premiers pays hôtes"]),
    (1, "Quel jour fête-t-on la Saint-Valentin ?", "Le 14 février", ["Le 14 mars", "Le 1er février", "Le 21 février"]),
    (1, "Quel jour est la fête nationale suisse ?", "Le 1er août", ["Le 14 juillet", "Le 1er juillet", "Le 12 septembre"]),
    (1, "Quel jour est la fête nationale française ?", "Le 14 juillet", ["Le 1er août", "Le 8 mai", "Le 11 novembre"]),
    (2, "Quel jour célèbre-t-on la fête nationale des États-Unis ?", "Le 4 juillet", ["Le 14 juillet", "Le 1er juillet", "Le 4 août"]),
    (2, "À quelle date fête-t-on Halloween ?", "Le 31 octobre", ["Le 1er novembre", "Le 30 octobre", "Le 31 décembre"]),
    (2, "Quelle fête marque la fin du ramadan ?", "L'Aïd el-Fitr", ["L'Aïd el-Kébir", "Le Mawlid", "L'Achoura"]),
    (2, "Quelle fête juive commémore la sortie d'Égypte ?", "Pessah", ["Hanoukka", "Yom Kippour", "Pourim"]),
    (2, "Combien de branches a le chandelier de Hanoukka (hanoukia) ?", "9", ["7", "8", "12"]),
    (2, "Quel est le livre sacré de l'islam ?", "Le Coran", ["La Torah", "Les Védas", "Le Talmud"]),
    (2, "Dans quelle religion célèbre-t-on Diwali, la fête des lumières ?", "L'hindouisme", ["Le bouddhisme", "L'islam", "Le judaïsme"]),
    (2, "Combien de pièces de 20 centimes dans 5 francs ?", "25", ["20", "50", "10"]),
    (1, "Que signifie l'abréviation « SVP » ?", "S'il vous plaît", ["Sans vos papiers", "Service vite payé", "Soyez vraiment polis"]),
    (2, "Que signifie l'abréviation « RSVP » ?", "Répondez s'il vous plaît", ["Rendez-vous sans votre présence", "Réservé sans vrai programme", "Retour sous vingt jours"]),
    (2, "Que signifie « CFF » en Suisse ?", "Chemins de fer fédéraux", ["Compagnie ferroviaire de France", "Centrale fédérale des finances", "Conseil fédéral des finances"]),
    (2, "Que signifie l'acronyme « OVNI » ?", "Objet volant non identifié", ["Objet visible non inventorié", "Organisme volant non identifié", "Observation visuelle nocturne inexpliquée"]),
    (2, "Que signifie l'acronyme « Laser » (en anglais) ?", "Amplification de lumière par émission stimulée de rayonnement", ["Lumière à source électronique rapide", "Lampe à système électrique renforcé", "Lumière artificielle sans émission radioactive"]),
    (2, "Que signifie « ONG » ?", "Organisation non gouvernementale", ["Office national de gestion", "Organisation nationale générale", "Ordre des nations garantes"]),
    (2, "Quelle est la monnaie du Royaume-Uni ?", "La livre sterling", ["L'euro", "Le dollar", "La couronne"]),
    (1, "Quelle est la monnaie de la Suisse ?", "Le franc suisse", ["L'euro", "Le florin", "La couronne"]),
    (2, "Comment s'appelle la grosse cloche de la tour de l'horloge de Westminster ?", "Big Ben", ["Westminster Bell", "Tower Clock", "Old Tom"]),
    (2, "Combien de marches compte environ la tour Eiffel jusqu'au sommet ?", "1665", ["365", "999", "2400"]),
    (2, "Quelle est la hauteur approximative de la tour Eiffel ?", "330 m", ["150 m", "500 m", "220 m"]),
    (2, "Qui a conçu la tour Eiffel (entreprise) ?", "Gustave Eiffel", ["Le Corbusier", "Haussmann", "Viollet-le-Duc"]),
    (2, "Qui a sculpté la statue de la Liberté ?", "Auguste Bartholdi", ["Auguste Rodin", "Gustave Eiffel", "Camille Claudel"]),
    (2, "Quel pays a offert la statue de la Liberté aux États-Unis ?", "La France", ["Le Royaume-Uni", "L'Italie", "L'Espagne"]),
    (2, "Quelle merveille du monde antique est la seule encore debout ?", "La pyramide de Khéops", ["Le phare d'Alexandrie", "Les jardins de Babylone", "Le colosse de Rhodes"]),
    (2, "Combien y avait-il de merveilles du monde antique ?", "7", ["5", "9", "12"]),
    (2, "Quel instrument a 88 touches ?", "Le piano", ["L'orgue", "L'accordéon", "Le clavecin"]),
    (2, "Combien de cordes a une guitare classique ?", "6", ["4", "5", "7"]),
    (2, "Combien de cordes a un violon ?", "4", ["5", "6", "3"]),
    (2, "Combien de notes compte la gamme majeure (sans répéter l'octave) ?", "7", ["5", "8", "12"]),
    (1, "Quelle est la première note de la gamme en solfège français ?", "Do", ["La", "Ré", "Mi"]),
    (2, "Quelle lettre désigne la note « la » dans la notation anglaise ?", "A", ["L", "C", "E"]),
    (2, "Comment s'appelle la personne qui dirige un orchestre ?", "Le chef d'orchestre", ["Le soliste", "Le premier violon", "Le maestro di cappella"]),
    (2, "Comment s'appelle un groupe de quatre musiciens ?", "Un quatuor", ["Un trio", "Un quintette", "Un octuor"]),
    (2, "Quel compositeur est devenu sourd ?", "Beethoven", ["Mozart", "Bach", "Chopin"]),
    (2, "Quel compositeur a écrit « Les Quatre Saisons » ?", "Vivaldi", ["Bach", "Mozart", "Haendel"]),
    (2, "Quel compositeur a écrit « La Flûte enchantée » ?", "Mozart", ["Haydn", "Beethoven", "Verdi"]),
    (2, "Quel compositeur a écrit « Le Boléro » ?", "Maurice Ravel", ["Claude Debussy", "Erik Satie", "Georges Bizet"]),
    (2, "Quel compositeur a écrit l'opéra « Carmen » ?", "Georges Bizet", ["Giuseppe Verdi", "Jacques Offenbach", "Gounod"]),
    (2, "Quel compositeur a écrit « Le Lac des cygnes » ?", "Tchaïkovski", ["Stravinsky", "Prokofiev", "Rachmaninov"]),
    (2, "Quelle est la langue la plus parlée en Suisse ?", "L'allemand", ["Le français", "L'italien", "L'anglais"]),
    (2, "Quelle célèbre course de chiens de traîneau a lieu en Alaska ?", "L'Iditarod", ["La Yukon Quest", "La Finnmarksløpet", "La Grande Odyssée"]),
    (2, "Quel jeu de société consiste à acheter des rues et construire des hôtels ?", "Le Monopoly", ["Le Cluedo", "Le Risk", "La Bonne Paye"]),
    (2, "Dans quel jeu cherche-t-on le coupable, l'arme et la pièce ?", "Le Cluedo", ["Le Monopoly", "Le Trivial Pursuit", "Le Risk"]),
    (2, "Quel jeu de lettres se joue avec des jetons sur un plateau de 15 × 15 cases ?", "Le Scrabble", ["Le Boggle", "Le Mot le plus long", "Le Pictionary"]),
    (2, "De quel pays vient le jeu de go ?", "La Chine", ["Le Japon", "La Corée", "L'Inde"]),
    (2, "Combien de cases compte un plateau de dames international ?", "100", ["64", "81", "121"]),
    (1, "Quel est le cri du mouton ?", "Il bêle", ["Il meugle", "Il hennit", "Il brait"]),
    (2, "Combien de temps dure un siècle ?", "100 ans", ["1000 ans", "10 ans", "50 ans"]),
    (2, "Combien d'années dure un millénaire ?", "1000", ["100", "10 000", "500"]),
    (2, "Combien d'années dure une décennie ?", "10", ["100", "5", "12"]),
    (2, "Comment appelle-t-on une période de 5 ans ?", "Un lustre", ["Une décennie", "Un septennat", "Une olympiade"]),
]


def generate():
    out = []
    authors = list(dict.fromkeys(a for _, a in BOOKS))
    for book, author in BOOKS:
        d = 1 if book in FAMOUS_BOOKS else 2
        out.append(make("culture", f"Qui a écrit « {book} » ?", author, pick(f"bk-{book}", authors, author), d))
    by_author = {}
    for book, author in BOOKS:
        by_author.setdefault(author, []).append(book)
    titles = [b for b, _ in BOOKS]
    for author, books in by_author.items():
        for book in books[:4]:
            others = [t for t in titles if t not in books]
            out.append(make("culture", f"Laquelle de ces œuvres a été écrite par {author} ?", f"« {book} »",
                            [f"« {t} »" for t in pick(f"bkr-{book}", others, book)], 2 if book in FAMOUS_BOOKS else 3))
    artists = list(dict.fromkeys([a for _, a in PAINTINGS] + ARTISTS_EXTRA))
    for work, artist in PAINTINGS:
        d = 1 if work in ("La Joconde", "La Nuit étoilée", "Guernica", "Le Cri", "Les Tournesols") else 2
        out.append(make("culture", f"Qui est l'auteur de « {work} » ?", artist, pick(f"pt-{work}", artists, artist), d))
    by_artist = {}
    for work, artist in PAINTINGS:
        by_artist.setdefault(artist, []).append(work)
    works = [w for w, _ in PAINTINGS]
    for artist, ws in by_artist.items():
        others = [w for w in works if w not in ws]
        out.append(make("culture", f"Quelle œuvre est de {artist} ?", f"« {ws[0]} »", [f"« {w} »" for w in pick(f"ptr-{artist}", others, ws[0])], 2))
    cities = list(dict.fromkeys(c for _, c in MONUMENTS))
    for mon, city in MONUMENTS:
        d = 1 if city in ("Paris", "Rome", "Londres", "New York") else 2
        out.append(make("culture", f"Dans quelle ville se trouve {mon} ?", city, pick(f"mon-{mon}", cities, city), d))
    inventors = list(dict.fromkeys(i for _, i in INVENTIONS))
    for inv, who in INVENTIONS:
        out.append(make("culture", f"À qui doit-on {inv} ?", who[0].upper() + who[1:], [x[0].upper() + x[1:] for x in pick(f"inv-{inv}", inventors, who)], 2))
    greeks, romans = [g for g, _ in MYTHO], [r for _, r in MYTHO]
    for gr, ro in MYTHO:
        out.append(make("culture", f"Quel est le nom romain du dieu grec {gr} ?", ro, pick(f"my-{gr}", romans, ro), 2))
        out.append(make("culture", f"Quel est le nom grec du dieu romain {ro} ?", gr, pick(f"myr-{ro}", greeks, gr), 2))
    for group, theme_name in ((MYTHO_ROLES, "grecque"), (NORSE, "nordique"), (EGYPT, "égyptienne")):
        names = [n for n, _ in group]
        roles = [r for _, r in group]
        for name, role in group:
            out.append(make("culture", f"Dans la mythologie {theme_name}, qui est {role} ?", name, pick(f"mr-{name}", names, name), 2))
            out.append(make("culture", f"Dans la mythologie {theme_name}, qui est {name} ?", role[0].upper() + role[1:],
                            [r[0].upper() + r[1:] for r in pick(f"mrr-{name}", roles, role)], 2))
    ends = [e for _, e in SAYINGS]
    for start, end in SAYINGS:
        out.append(make("culture", f"Complète le proverbe : « {start} »", f"… {end}", [f"… {e}" for e in pick(f"say-{start}", ends, end)], 1))
    meanings = [m for _, m in IDIOMS]
    for idiom, meaning in IDIOMS:
        out.append(make("culture", f"Que signifie l'expression « {idiom} » ?", meaning, pick(f"id-{idiom}", meanings, meaning), 1))
    # Chiffres romains
    rng = random.Random("roman")
    for i in range(160):
        n = rng.choice([rng.randint(4, 50), rng.randint(40, 400), rng.randint(1000, 2030)])
        if rng.random() < 0.5:
            wrong = list(dict.fromkeys(str(x) for x in (n + 1, n - 1, n + 10, n - 10, n + 5, n + 100) if x > 0 and x != n))
            rng.shuffle(wrong)
            q = make("culture", f"Que vaut le nombre romain {roman(n)} ?", str(n), wrong, 1 if n < 40 else 2 if n < 400 else 3)
        else:
            wrong = list(dict.fromkeys(roman(x) for x in (n + 1, n - 1, n + 10, n - 10, n + 4, n + 50) if x > 0 and x != n))
            rng.shuffle(wrong)
            q = make("culture", f"Comment s'écrit {n} en chiffres romains ?", roman(n), wrong, 2 if n < 400 else 3)
        if q:
            out.append(q)
    for word, wrong in SPELLING:
        out.append(make("culture", "Quelle est la bonne orthographe ?", word, wrong[:3], 2))
    for sing, plur, wrong in PLURALS:
        out.append(make("culture", f"Quel est le pluriel de « {sing.split(' (')[0]} » ?", plur, wrong, 2))
    for d, q, a, w in WRITTEN:
        out.append(make("culture", q, a, w, d))
    return out
