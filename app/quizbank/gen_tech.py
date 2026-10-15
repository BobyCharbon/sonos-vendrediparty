"""Informatique, IA & technologies : entreprises, sigles, langages, produits, raccourcis, formats, IA, histoire."""

from . import make, pick
from .gen_divert import _chrono, _decades, _years, decade

# (entreprise, fondateur(s))
FOUNDERS = [
    ("Apple", "Steve Jobs et Steve Wozniak"), ("Microsoft", "Bill Gates et Paul Allen"), ("Google", "Larry Page et Sergey Brin"),
    ("Facebook", "Mark Zuckerberg"), ("Amazon", "Jeff Bezos"), ("SpaceX", "Elon Musk"), ("Netflix", "Reed Hastings et Marc Randolph"),
    ("Anthropic", "Dario et Daniela Amodei"), ("Nvidia", "Jensen Huang"), ("Oracle", "Larry Ellison"), ("Dell", "Michael Dell"), ("Spotify", "Daniel Ek"),
    ("Alibaba", "Jack Ma"), ("Linux (le noyau)", "Linus Torvalds"), ("Wikipédia", "Jimmy Wales"), ("LinkedIn", "Reid Hoffman"), ("Instagram", "Kevin Systrom"),
    ("WhatsApp", "Jan Koum"), ("Telegram", "Pavel Durov"), ("ByteDance (TikTok)", "Zhang Yiming"), ("Snapchat", "Evan Spiegel"),
    ("YouTube", "Chad Hurley, Steve Chen et Jawed Karim"), ("Reddit", "Steve Huffman et Alexis Ohanian"), ("Yahoo!", "Jerry Yang et David Filo"),
    ("eBay", "Pierre Omidyar"), ("Intel", "Robert Noyce et Gordon Moore"), ("HP", "Bill Hewlett et David Packard"), ("Adobe", "John Warnock et Charles Geschke"),
    ("Atari", "Nolan Bushnell"), ("Zoom", "Eric Yuan"), ("Shopify", "Tobias Lütke"), ("Proton (Proton Mail)", "Andy Yen et des chercheurs du CERN"),
    ("DeepMind", "Demis Hassabis, Shane Legg et Mustafa Suleyman"), ("Mistral AI", "Arthur Mensch, Guillaume Lample et Timothée Lacroix"),
    ("Logitech", "Daniel Borel, Pierluigi Zappacosta et Giacomo Marini"), ("Twitter", "Jack Dorsey, Biz Stone, Evan Williams et Noah Glass"),
    ("Airbnb", "Brian Chesky, Joe Gebbia et Nathan Blecharczyk"), ("Uber", "Travis Kalanick et Garrett Camp"), ("Sony", "Masaru Ibuka et Akio Morita"),
    ("Discord", "Jason Citron et Stan Vishnevskiy"), ("Tesla (direction et essor)", "Elon Musk"), ("OpenAI (co-fondation, PDG)", "Sam Altman"),
]
# (entreprise, pays du siège)
HQ = [
    ("Apple", "États-Unis"), ("Samsung", "Corée du Sud"), ("Sony", "Japon"), ("Huawei", "Chine"), ("Xiaomi", "Chine"), ("Lenovo", "Chine"),
    ("Nokia", "Finlande"), ("Ericsson", "Suède"), ("Spotify", "Suède"), ("SAP", "Allemagne"), ("Siemens", "Allemagne"), ("Philips", "Pays-Bas"),
    ("ASML", "Pays-Bas"), ("TSMC", "Taïwan"), ("Logitech", "Suisse"), ("Proton", "Suisse"), ("Swisscom", "Suisse"), ("Infomaniak", "Suisse"),
    ("Threema", "Suisse"), ("Ubisoft", "France"), ("Dassault Systèmes", "France"), ("Mistral AI", "France"), ("Nintendo", "Japon"), ("Tencent", "Chine"),
    ("Alibaba", "Chine"), ("ByteDance", "Chine"), ("Baidu", "Chine"), ("Yandex", "Russie"), ("Shopify", "Canada"), ("BlackBerry", "Canada"),
    ("Arm", "Royaume-Uni"), ("Raspberry Pi", "Royaume-Uni"), ("Infosys", "Inde"), ("LG", "Corée du Sud"), ("Nvidia", "États-Unis"), ("Intel", "États-Unis"),
    ("AMD", "États-Unis"), ("Anthropic", "États-Unis"), ("OpenAI", "États-Unis"), ("Booking.com", "Pays-Bas"), ("Zalando", "Allemagne"), ("Klarna", "Suède"),
    ("Revolut", "Royaume-Uni"), ("Deezer", "France"), ("Doctolib", "France"), ("BlaBlaCar", "France"), ("Skype (à sa création)", "Estonie"), ("Canon", "Japon"),
    ("Panasonic", "Japon"), ("Microsoft", "États-Unis"), ("Meta", "États-Unis"), ("Alphabet (Google)", "États-Unis"), ("Swatch Group", "Suisse"), ("u-blox", "Suisse"),
]
# Sigle → signification
ACRONYMS = [
    ("CPU", "Processeur central (Central Processing Unit)"), ("GPU", "Processeur graphique (Graphics Processing Unit)"), ("RAM", "Mémoire vive (Random Access Memory)"),
    ("ROM", "Mémoire morte (Read-Only Memory)"), ("USB", "Bus série universel (Universal Serial Bus)"), ("HTML", "Langage de balisage des pages web (HyperText Markup Language)"),
    ("HTTP", "Protocole de transfert hypertexte"), ("URL", "Adresse d'une ressource sur le web (Uniform Resource Locator)"), ("PDF", "Format de document portable"),
    ("SSD", "Disque à mémoire flash (Solid-State Drive)"), ("HDD", "Disque dur à plateaux (Hard Disk Drive)"), ("LAN", "Réseau local"), ("VPN", "Réseau privé virtuel"),
    ("IP (adresse)", "Protocole Internet"), ("DNS", "Système de noms de domaine"), ("SQL", "Langage de requête de bases de données"), ("API", "Interface de programmation"),
    ("IA", "Intelligence artificielle"), ("LLM", "Grand modèle de langage"), ("GPT", "Transformeur génératif pré-entraîné"), ("NFC", "Communication en champ proche"),
    ("GPS", "Système de positionnement par satellites"), ("OLED", "Diode électroluminescente organique"), ("LCD", "Écran à cristaux liquides"), ("BIOS", "Système d'entrée-sortie de base"),
    ("OS", "Système d'exploitation"), ("FAI", "Fournisseur d'accès à Internet"), ("SMS", "Message texte court"), ("SIM (carte)", "Module d'identité de l'abonné"),
    ("5G", "Cinquième génération de réseau mobile"), ("JPEG", "Format d'image compressée (groupe d'experts photo)"), ("MP3", "Format audio compressé"), ("CSS", "Feuilles de style des pages web"),
    ("JSON", "Format de données textuel issu de JavaScript"), ("SaaS", "Logiciel en tant que service"), ("IoT", "Internet des objets"), ("VR", "Réalité virtuelle"),
    ("AR", "Réalité augmentée"), ("OCR", "Reconnaissance optique de caractères"), ("CAPTCHA", "Test pour distinguer humains et robots"), ("PIN (code)", "Numéro d'identification personnel"),
    ("FTP", "Protocole de transfert de fichiers"), ("SSH", "Connexion à distance sécurisée"), ("DDoS", "Attaque par déni de service distribué"), ("Wi-Fi", "Réseau local sans fil"),
    ("PC", "Ordinateur personnel"), ("QR (code)", "Code à réponse rapide"), ("2FA", "Authentification à deux facteurs"), ("RGPD", "Règlement européen sur la protection des données"),
    ("ADSL", "Internet par la ligne téléphonique (ligne d'abonné numérique asymétrique)"), ("NAS", "Stockage en réseau"), ("CMS", "Système de gestion de contenu"),
]
# (langage, créateur, année)
LANGUAGES = [
    ("Python", "Guido van Rossum", 1991), ("Java", "James Gosling", 1995), ("C", "Dennis Ritchie", 1972), ("C++", "Bjarne Stroustrup", 1985),
    ("JavaScript", "Brendan Eich", 1995), ("PHP", "Rasmus Lerdorf", 1995), ("Ruby", "Yukihiro Matsumoto", 1995), ("Swift", "Chris Lattner (Apple)", 2014),
    ("Go", "Robert Griesemer, Rob Pike et Ken Thompson (Google)", 2009), ("Rust", "Graydon Hoare", 2010), ("Kotlin", "JetBrains", 2011),
    ("C#", "Anders Hejlsberg (Microsoft)", 2000), ("Pascal", "Niklaus Wirth", 1970), ("Lisp", "John McCarthy", 1958), ("Fortran", "John Backus (IBM)", 1957),
    ("COBOL", "Un comité inspiré par Grace Hopper", 1959), ("BASIC", "John Kemeny et Thomas Kurtz", 1964), ("Perl", "Larry Wall", 1987),
    ("TypeScript", "Microsoft (Anders Hejlsberg)", 2012), ("R", "Ross Ihaka et Robert Gentleman", 1993), ("MATLAB", "Cleve Moler", 1984),
    ("Scratch", "Le MIT Media Lab", 2007), ("Erlang", "Ericsson (Joe Armstrong)", 1986), ("Prolog", "Alain Colmerauer", 1972), ("Elixir", "José Valim", 2012),
    ("Julia", "Jeff Bezanson, Stefan Karpinski, Viral Shah et Alan Edelman", 2012), ("Dart", "Google (Lars Bak et Kasper Lund)", 2011),
]
# (produit ou événement, année)
PRODUCTS = [
    ("la sortie du premier iPhone", 2007), ("la sortie du premier iPad", 2010), ("la sortie du premier Macintosh", 1984), ("la sortie de l'Apple II", 1977),
    ("la sortie de l'IBM PC", 1981), ("la sortie de Windows 95", 1995), ("la sortie de Windows 1.0", 1985), ("le lancement du moteur de recherche Google", 1998),
    ("le lancement de Gmail", 2004), ("le lancement de Facebook", 2004), ("le lancement de YouTube", 2005), ("le lancement de Twitter", 2006),
    ("le lancement d'Instagram", 2010), ("le lancement de WhatsApp", 2009), ("le lancement de Snapchat", 2011), ("le lancement de Wikipédia", 2001),
    ("la création d'Amazon", 1994), ("le lancement du streaming de Netflix", 2007), ("le lancement de Spotify", 2008), ("la sortie du premier téléphone Android", 2008),
    ("la sortie de ChatGPT", 2022), ("la sortie de GPT-4", 2023), ("la première version de Claude", 2023), ("la création du Bitcoin", 2009),
    ("la première version de Linux", 1991), ("la sortie du premier iPod", 2001), ("la sortie de la liseuse Kindle", 2007), ("la sortie de l'Apple Watch", 2015),
    ("la victoire de Deep Blue sur Kasparov", 1997), ("la victoire d'AlphaGo sur Lee Sedol", 2016), ("la mise en service de l'ENIAC", 1946),
    ("l'invention du transistor", 1947), ("le premier e-mail (Ray Tomlinson)", 1971), ("la première liaison ARPANET", 1969), ("l'envoi du premier SMS", 1992),
    ("la mise en ligne du premier site web (CERN)", 1991), ("le bug de l'an 2000", 2000), ("la première norme USB", 1996), ("la première norme Wi-Fi (802.11)", 1997),
    ("l'invention du QR code", 1994), ("le lancement de Skype", 2003), ("le lancement de LinkedIn", 2003), ("le lancement de Reddit", 2005),
    ("le lancement de Discord", 2015), ("la conférence de Dartmouth qui nomme l'« intelligence artificielle »", 1956), ("la création du chatbot ELIZA", 1966),
    ("la publication de l'article « Attention Is All You Need » (transformers)", 2017), ("la victoire de l'IA Watson au jeu Jeopardy!", 2011),
    ("la sortie de Siri sur iPhone", 2011), ("le lancement d'Alexa d'Amazon", 2014), ("la sortie de DALL-E 2", 2022),
]
SHORTCUTS = [("Ctrl + C", "Copier"), ("Ctrl + V", "Coller"), ("Ctrl + X", "Couper"), ("Ctrl + Z", "Annuler"), ("Ctrl + Y", "Rétablir"), ("Ctrl + S", "Enregistrer"),
             ("Ctrl + P", "Imprimer"), ("Ctrl + F", "Rechercher dans la page"), ("Ctrl + A", "Tout sélectionner"), ("Alt + F4", "Fermer la fenêtre (Windows)"),
             ("Ctrl + T", "Ouvrir un nouvel onglet"), ("Ctrl + W", "Fermer l'onglet"), ("Ctrl + Maj + T", "Rouvrir le dernier onglet fermé"), ("F5", "Actualiser la page"),
             ("Cmd + Espace (Mac)", "Ouvrir la recherche Spotlight"), ("Windows + L", "Verrouiller la session"), ("Ctrl + Alt + Suppr", "Ouvrir l'écran de sécurité Windows")]
EXTENSIONS = [(".jpg", "Une image"), (".png", "Une image"), (".gif", "Une image animée ou non"), (".mp3", "Un fichier audio"), (".wav", "Un fichier audio"),
              (".mp4", "Une vidéo"), (".mov", "Une vidéo"), (".pdf", "Un document PDF"), (".docx", "Un document Word"), (".xlsx", "Un tableur Excel"),
              (".pptx", "Une présentation PowerPoint"), (".zip", "Une archive compressée"), (".exe", "Un programme Windows"), (".py", "Un script Python"),
              (".html", "Une page web"), (".csv", "Un tableau de données en texte"), (".txt", "Un texte brut"), (".apk", "Une application Android"),
              (".iso", "Une image de disque"), (".svg", "Une image vectorielle")]
EXT_KINDS = list(dict.fromkeys(k for _, k in EXTENSIONS))

WRITTEN = [
    (1, "Que signifie « IA » ?", "Intelligence artificielle", ["Informatique avancée", "Interface automatique", "Internet accéléré"]),
    (2, "Qui est considéré comme le père de l'informatique théorique et du test qui porte son nom ?", "Alan Turing", ["John von Neumann", "Charles Babbage", "Claude Shannon"]),
    (2, "En quoi consiste le test de Turing ?", "Savoir si une machine peut se faire passer pour un humain en conversation", ["Mesurer la vitesse d'un processeur", "Déchiffrer un code secret", "Tester la mémoire d'un ordinateur"]),
    (2, "Qui est considérée comme la première programmeuse de l'histoire ?", "Ada Lovelace", ["Grace Hopper", "Margaret Hamilton", "Hedy Lamarr"]),
    (2, "Sur quelle machine de Charles Babbage Ada Lovelace a-t-elle travaillé ?", "La machine analytique", ["L'ENIAC", "La Pascaline", "Le métier Jacquard"]),
    (2, "Qui a popularisé le terme « bug » après avoir trouvé un papillon de nuit dans un ordinateur ?", "Grace Hopper", ["Ada Lovelace", "Alan Turing", "Margaret Hamilton"]),
    (2, "Quelle informaticienne a dirigé le logiciel de vol d'Apollo 11 ?", "Margaret Hamilton", ["Grace Hopper", "Katherine Johnson", "Ada Lovelace"]),
    (2, "Quel ingénieur allemand a construit le Z3, l'un des premiers ordinateurs programmables (1941) ?", "Konrad Zuse", ["Alan Turing", "John von Neumann", "Howard Aiken"]),
    (2, "Que dit la loi de Moore ?", "Le nombre de transistors d'une puce double environ tous les deux ans", ["La vitesse d'Internet double chaque année", "Le prix des ordinateurs baisse de moitié", "La mémoire est toujours insuffisante"]),
    (2, "Combien de bits contient un octet ?", "8", ["4", "16", "10"]),
    (2, "Combien de valeurs différentes peut coder un octet ?", "256", ["128", "255", "1024"]),
    (2, "Quel système de numération utilise seulement 0 et 1 ?", "Le binaire", ["L'hexadécimal", "Le décimal", "L'octal"]),
    (2, "Quel système de numération utilise les chiffres 0-9 et les lettres A-F ?", "L'hexadécimal", ["Le binaire", "L'octal", "Le base 32"]),
    (2, "Quel est l'ordre croissant correct ?", "Ko, Mo, Go, To", ["Mo, Ko, Go, To", "Go, Mo, To, Ko", "Ko, Go, Mo, To"]),
    (2, "Combien de mégaoctets fait environ un gigaoctet ?", "1000 (ou 1024)", ["100", "10", "1 000 000"]),
    (2, "Comment s'appelle le symbole « @ » en français ?", "L'arobase", ["L'esperluette", "Le dièse", "La tilde"]),
    (2, "Comment s'appelle le symbole « & » ?", "L'esperluette", ["L'arobase", "Le croisillon", "La barre oblique"]),
    (2, "Quel clavier est utilisé en Suisse ?", "QWERTZ", ["AZERTY", "QWERTY", "BÉPO"]),
    (2, "Quel clavier est utilisé en France ?", "AZERTY", ["QWERTZ", "QWERTY", "DVORAK"]),
    (2, "Où a été inventé le World Wide Web ?", "Au CERN, près de Genève", ["Au MIT", "À la Silicon Valley", "À l'EPFL"]),
    (2, "Qui a inventé le World Wide Web ?", "Tim Berners-Lee", ["Vinton Cerf", "Bill Gates", "Steve Jobs"]),
    (2, "Quel Suisse a créé le langage Pascal ?", "Niklaus Wirth", ["Linus Torvalds", "Daniel Borel", "Guido van Rossum"]),
    (2, "Quelle entreprise suisse est célèbre pour ses souris d'ordinateur ?", "Logitech", ["Swisscom", "Proton", "Kudelski"]),
    (2, "Quelle région suisse est surnommée « Crypto Valley » ?", "Zoug", ["Genève", "Lugano", "Zurich"]),
    (2, "Dans quelle ville suisse se trouve la fondation Ethereum ?", "Zoug", ["Genève", "Bâle", "Berne"]),
    (2, "Sous quel pseudonyme se cache le créateur du Bitcoin ?", "Satoshi Nakamoto", ["Vitalik Buterin", "Hal Finney", "Nick Szabo"]),
    (2, "Qui a co-fondé Ethereum ?", "Vitalik Buterin", ["Satoshi Nakamoto", "Roger Ver", "Changpeng Zhao"]),
    (2, "Comment s'appelle la technologie de registre partagé derrière le Bitcoin ?", "La blockchain", ["Le cloud", "Le streaming", "Le big data"]),
    (2, "Quel est le système d'exploitation libre créé par Linus Torvalds ?", "Linux", ["Unix", "Windows", "macOS"]),
    (2, "Quel animal est la mascotte de Linux ?", "Un manchot (Tux)", ["Un renard", "Un éléphant", "Un serpent"]),
    (2, "Quel animal est le logo de Firefox ?", "Un renard (en réalité un panda roux)", ["Un loup", "Un chat", "Un dragon"]),
    (2, "Quel est le système d'exploitation mobile de Google ?", "Android", ["iOS", "HarmonyOS", "Windows Phone"]),
    (2, "Quel est le système d'exploitation de l'iPhone ?", "iOS", ["Android", "macOS", "watchOS"]),
    (2, "Quel navigateur web est développé par Google ?", "Chrome", ["Safari", "Firefox", "Edge"]),
    (2, "Quel navigateur web est développé par Apple ?", "Safari", ["Chrome", "Edge", "Opera"]),
    (2, "Quel navigateur a remplacé Internet Explorer chez Microsoft ?", "Edge", ["Chrome", "Firefox", "Brave"]),
    (2, "Quel assistant vocal est celui d'Apple ?", "Siri", ["Alexa", "Cortana", "Bixby"]),
    (2, "Quel assistant vocal est celui d'Amazon ?", "Alexa", ["Siri", "Google Assistant", "Cortana"]),
    (2, "Quelle entreprise a créé ChatGPT ?", "OpenAI", ["Google", "Anthropic", "Meta"]),
    (2, "Quelle entreprise a créé l'assistant Claude ?", "Anthropic", ["OpenAI", "Google", "Mistral AI"]),
    (2, "Quelle entreprise a créé Gemini ?", "Google", ["Microsoft", "OpenAI", "Meta"]),
    (2, "Quelle entreprise a publié les modèles Llama ?", "Meta", ["Google", "Amazon", "Apple"]),
    (2, "De quel pays vient l'entreprise d'IA Mistral AI ?", "La France", ["La Suisse", "L'Allemagne", "Le Canada"]),
    (2, "Quelle entreprise a développé AlphaGo et AlphaFold ?", "DeepMind (Google)", ["OpenAI", "IBM", "Microsoft"]),
    (2, "Pour quelle découverte AlphaFold a-t-il valu un prix Nobel de chimie en 2024 ?", "La prédiction de la structure des protéines", ["Le séquençage de l'ADN", "La fusion nucléaire", "Un nouveau vaccin"]),
    (2, "Quels pionniers des réseaux de neurones ont reçu le Nobel de physique 2024 ?", "John Hopfield et Geoffrey Hinton", ["Yann LeCun et Yoshua Bengio", "Demis Hassabis et John Jumper", "Sam Altman et Ilya Sutskever"]),
    (2, "Quel chercheur français est un pionnier des réseaux de neurones convolutifs ?", "Yann LeCun", ["Arthur Mensch", "Cédric Villani", "Luc Julia"]),
    (2, "Quelle architecture d'IA, présentée en 2017, est à la base des grands modèles de langage ?", "Le transformeur", ["Le perceptron", "Le réseau récurrent", "L'arbre de décision"]),
    (2, "Comment appelle-t-on une réponse inventée mais présentée avec assurance par une IA ?", "Une hallucination", ["Un bug", "Un biais", "Un prompt"]),
    (2, "Comment appelle-t-on l'instruction écrite qu'on donne à une IA générative ?", "Un prompt", ["Un token", "Un script", "Un modèle"]),
    (2, "Comment appelle-t-on les morceaux de texte que traite un modèle de langage ?", "Des tokens", ["Des pixels", "Des octets", "Des neurones"]),
    (2, "Comment appelle-t-on l'apprentissage où une IA apprend par essais, erreurs et récompenses ?", "L'apprentissage par renforcement", ["L'apprentissage supervisé", "L'apprentissage non supervisé", "L'apprentissage par transfert"]),
    (2, "Comment appelle-t-on l'apprentissage à partir d'exemples étiquetés ?", "L'apprentissage supervisé", ["L'apprentissage par renforcement", "L'apprentissage non supervisé", "Le transfert"]),
    (2, "Comment appelle-t-on l'apprentissage automatique avec de nombreuses couches de neurones ?", "L'apprentissage profond (deep learning)", ["Le big data", "Le cloud computing", "La logique floue"]),
    (2, "Quel composant, conçu pour les jeux vidéo, est devenu essentiel pour entraîner les IA ?", "La carte graphique (GPU)", ["Le disque dur", "La carte son", "Le modem"]),
    (2, "Quel nom désigne une IA hypothétique aussi capable qu'un humain dans tous les domaines ?", "L'IA générale (AGI)", ["L'IA faible", "Le chatbot", "Le système expert"]),
    (2, "Quel écrivain a imaginé les « trois lois de la robotique » ?", "Isaac Asimov", ["Philip K. Dick", "Arthur C. Clarke", "Jules Verne"]),
    (2, "Comment s'appelle l'ordinateur meurtrier de « 2001 : l'Odyssée de l'espace » ?", "HAL 9000", ["Skynet", "Ultron", "Mother"]),
    (2, "Comment s'appelle l'IA hostile de la saga Terminator ?", "Skynet", ["HAL 9000", "Matrix", "Jarvis"]),
    (2, "Comment s'appelle l'assistant IA de Tony Stark ?", "J.A.R.V.I.S.", ["HAL", "Vision", "Ultron"]),
    (2, "Quel générateur d'images par IA a été lancé par un laboratoire indépendant en 2022 et est utilisé via Discord ?", "Midjourney", ["DALL-E", "Stable Diffusion", "Firefly"]),
    (2, "Quel générateur d'images par IA est développé par OpenAI ?", "DALL-E", ["Midjourney", "Stable Diffusion", "Imagen"]),
    (2, "Quelle IA de programmation est proposée par GitHub et Microsoft ?", "GitHub Copilot", ["Cursor", "Claude Code", "Tabnine"]),
    (2, "Quelle entreprise fabrique la plupart des puces des iPhone et des GPU Nvidia ?", "TSMC", ["Intel", "Foxconn", "Qualcomm"]),
    (2, "Quelle entreprise néerlandaise fabrique les machines de lithographie EUV indispensables aux puces ?", "ASML", ["Philips", "TSMC", "Infineon"]),
    (2, "Quel matériau est à la base des puces électroniques ?", "Le silicium", ["Le cuivre", "Le graphite", "L'aluminium"]),
    (2, "Où se trouve la Silicon Valley ?", "En Californie", ["Au Texas", "À New York", "Dans l'État de Washington"]),
    (2, "Quel était le premier nom de Google ?", "BackRub", ["Googol", "PageRank", "Search Inc."]),
    (2, "Que signifie à l'origine le nom « Google » ?", "Un jeu de mots sur « gogol » (10 puissance 100)", ["Le nom d'un chien", "Les initiales des fondateurs", "Un mot de l'argot de Stanford"]),
    (2, "Dans quel garage aurait commencé Apple ?", "Celui des parents de Steve Jobs", ["Celui de Bill Gates", "Celui de Steve Wozniak à Seattle", "Celui de HP"]),
    (2, "Quel fruit est le logo d'Apple ?", "Une pomme croquée", ["Une poire", "Une pomme entière", "Une cerise"]),
    (2, "Combien de couleurs a le logo de Google ?", "4", ["3", "5", "6"]),
    (2, "Comment s'appelle aujourd'hui l'entreprise mère de Facebook ?", "Meta", ["Alphabet", "Oculus", "Instagram Inc."]),
    (2, "Comment s'appelle aujourd'hui Twitter ?", "X", ["Threads", "Bluesky", "Mastodon"]),
    (2, "Quelle est l'entreprise mère de Google ?", "Alphabet", ["Meta", "Gemini Inc.", "Waymo"]),
    (2, "Qui a racheté Twitter en 2022 ?", "Elon Musk", ["Mark Zuckerberg", "Jeff Bezos", "Bill Gates"]),
    (2, "Qui a racheté WhatsApp en 2014 ?", "Facebook (Meta)", ["Google", "Microsoft", "Apple"]),
    (2, "Qui a racheté LinkedIn en 2016 ?", "Microsoft", ["Google", "Meta", "Salesforce"]),
    (2, "Qui a racheté YouTube en 2006 ?", "Google", ["Microsoft", "Yahoo!", "Apple"]),
    (2, "Qui a racheté Minecraft (Mojang) en 2014 ?", "Microsoft", ["Sony", "Google", "Activision"]),
    (2, "Quelle plateforme de vidéos courtes est chinoise ?", "TikTok", ["YouTube Shorts", "Instagram Reels", "Snapchat Spotlight"]),
    (2, "Comment s'appelle le réseau social de Meta concurrent de X ?", "Threads", ["Bluesky", "Mastodon", "BeReal"]),
    (2, "Quelle messagerie chiffrée suisse est payante et anonyme ?", "Threema", ["Signal", "Telegram", "WhatsApp"]),
    (2, "Quel service d'e-mail chiffré a été créé à Genève par des chercheurs du CERN ?", "Proton Mail", ["Gmail", "Tutanota", "Infomaniak Mail"]),
    (2, "Quelle est la plus grande encyclopédie en ligne collaborative ?", "Wikipédia", ["Britannica", "Larousse", "Encarta"]),
    (2, "Quel moteur de recherche respecte la vie privée et a un canard pour logo ?", "DuckDuckGo", ["Qwant", "Ecosia", "Bing"]),
    (2, "Quel moteur de recherche plante des arbres avec ses revenus ?", "Ecosia", ["Qwant", "DuckDuckGo", "Lilo"]),
    (2, "Comment s'appelle un logiciel malveillant qui chiffre vos fichiers et demande une rançon ?", "Un rançongiciel (ransomware)", ["Un ver", "Un cheval de Troie", "Un logiciel espion"]),
    (2, "Comment appelle-t-on un faux e-mail qui imite une banque pour voler des identifiants ?", "L'hameçonnage (phishing)", ["Le spam", "Le ransomware", "Le DDoS"]),
    (2, "Comment appelle-t-on un logiciel malveillant caché dans un programme en apparence sain ?", "Un cheval de Troie", ["Un ver", "Un rançongiciel", "Un cookie"]),
    (2, "Comment appelle-t-on un petit fichier qu'un site enregistre dans votre navigateur ?", "Un cookie", ["Un cache", "Un pixel", "Un plugin"]),
    (2, "Qu'est-ce que le « cloud » ?", "Des serveurs distants accessibles par Internet", ["Un réseau sans fil", "Une mémoire vive", "Un antivirus"]),
    (2, "Qu'est-ce qu'un logiciel « open source » ?", "Un logiciel dont le code source est public", ["Un logiciel sans publicité", "Un logiciel sans licence", "Un logiciel en ligne"]),
    (2, "Quel est le langage le plus utilisé pour les pages web interactives côté navigateur ?", "JavaScript", ["Java", "Python", "C++"]),
    (2, "Quel langage, au logo de serpent, est très utilisé en IA ?", "Python", ["Java", "Ruby", "Go"]),
    (2, "D'où vient le nom du langage Python ?", "Des Monty Python", ["Du serpent", "D'un mathématicien grec", "D'une ville"]),
    (2, "Quelle plateforme héberge le code de millions de projets et appartient à Microsoft ?", "GitHub", ["GitLab", "Bitbucket", "SourceForge"]),
    (2, "Quel logiciel de gestion de versions a créé Linus Torvalds ?", "Git", ["SVN", "Mercurial", "CVS"]),
    (2, "Comment s'appelle le premier programme qu'on écrit traditionnellement dans un nouveau langage ?", "« Hello, World! »", ["« Lorem ipsum »", "« Test 123 »", "« Foo bar »"]),
    (2, "Quelle est la plus petite unité d'information ?", "Le bit", ["L'octet", "Le pixel", "Le hertz"]),
    (2, "Qu'est-ce qu'un pixel ?", "Le plus petit point d'une image numérique", ["Une unité de mémoire", "Un type de processeur", "Un format d'image"]),
    (2, "Que mesure la fréquence d'un processeur (en GHz) ?", "Le nombre de cycles par seconde", ["Sa taille", "Sa mémoire", "Sa température"]),
    (2, "Que signifie « 4K » pour un écran ?", "Environ 4000 pixels de large", ["4 000 couleurs", "4 fois plus rapide", "4 ports HDMI"]),
    (2, "Quel connecteur a remplacé le Lightning sur l'iPhone en 2023 ?", "L'USB-C", ["Le micro-USB", "Le mini-jack", "Le Thunderbolt 2"]),
    (2, "Quelle technologie sans fil relie écouteurs et téléphone à courte portée ?", "Le Bluetooth", ["Le Wi-Fi", "La 5G", "L'infrarouge"]),
    (2, "D'où vient le nom « Bluetooth » ?", "D'un roi viking, Harald à la Dent bleue", ["De la couleur des premières puces", "D'un dentiste", "D'une baleine"]),
    (2, "Quelle technologie permet de payer en approchant son téléphone d'un terminal ?", "Le NFC", ["Le Bluetooth", "Le GPS", "L'infrarouge"]),
    (2, "Quel était le premier ordinateur électronique à usage général (1946) ?", "L'ENIAC", ["Le Z3", "Le Colossus", "L'Apple I"]),
    (2, "Quel ordinateur a battu le champion du monde d'échecs Garry Kasparov ?", "Deep Blue (IBM)", ["Watson", "AlphaZero", "Stockfish"]),
    (2, "Contre qui AlphaGo a-t-il gagné au jeu de go en 2016 ?", "Lee Sedol", ["Fan Hui", "Garry Kasparov", "Magnus Carlsen"]),
    (2, "Comment s'appelait le premier « chatbot », créé au MIT en 1966 ?", "ELIZA", ["ALICE", "Siri", "Watson"]),
    (2, "Quel réseau, ancêtre d'Internet, a été créé en 1969 ?", "ARPANET", ["Minitel", "Usenet", "Ethernet"]),
    (2, "Quel service télématique français a précédé Internet dans les foyers ?", "Le Minitel", ["Le Vidéotex suisse", "Prestel", "ARPANET"]),
    (2, "Quelle loi européenne de 2018 protège les données personnelles ?", "Le RGPD", ["Le DSA", "La LPD", "Le Cloud Act"]),
    (2, "Quelle loi suisse protège les données personnelles (révisée en 2023) ?", "La LPD", ["Le RGPD", "La LIFD", "La LCD"]),
    (2, "Quelle loi européenne encadre l'intelligence artificielle (2024) ?", "L'AI Act (règlement européen sur l'IA)", ["Le RGPD", "Le DMA", "Le Chips Act"]),
]
WRITTEN += [
    (2, "Quelle machine de chiffrement allemande Turing a-t-il aidé à casser ?", "Enigma", ["Lorenz", "Purple", "Scytale"]),
]


def generate():
    out = []
    founders = [f for _, f in FOUNDERS]
    for co, f in FOUNDERS:
        out.append(make("tech", f"Qui a fondé (ou co-fondé) {co} ?", f, pick(f"fd-{co}", founders, f), 1 if co in ("Apple", "Microsoft", "Facebook", "Amazon", "Google") else 2))
        out.append(make("tech", f"Quelle entreprise a été fondée par {f} ?", co, pick(f"fdr-{co}", [c for c, _ in FOUNDERS], co), 2))
    countries = list(dict.fromkeys(c for _, c in HQ))
    for co, c in HQ:
        out.append(make("tech", f"Dans quel pays se trouve le siège de {co} ?", c, pick(f"hq-{co}", countries, c), 2))
    by_c = {}
    for co, c in HQ:
        by_c.setdefault(c, []).append(co)
    for c, cos in by_c.items():
        others = [x for x, cc in HQ if cc != c]
        for co in cos:
            out.append(make("tech", f"Laquelle de ces entreprises a son siège dans ce pays : {c} ?", co, pick(f"hqr-{co}", others, co), 2))
    meanings = [m for _, m in ACRONYMS]
    for ac, m in ACRONYMS:
        out.append(make("tech", f"Que signifie le sigle « {ac} » ?", m, pick(f"ac-{ac}", meanings, m), 2))
        out.append(make("tech", f"Quel sigle désigne : {m[0].lower() + m[1:]} ?", ac, pick(f"acr-{ac}", [a for a, _ in ACRONYMS], ac), 2))
    creators = [c for _, c, _ in LANGUAGES]
    for lang, creator, y in LANGUAGES:
        out.append(make("tech", f"Qui a créé le langage de programmation {lang} ?", creator, pick(f"lang-{lang}", creators, creator), 2 if lang in ("Python", "Java", "C", "JavaScript") else 3))
        out.append(make("tech", f"Quel langage de programmation a été créé par {creator} ?", lang, pick(f"langr-{lang}", [l for l, _, _ in LANGUAGES], lang), 3))
        out.append(make("tech", f"Dans quelle décennie est né le langage {lang} ?", decade(y), _decades(y, f"langd-{lang}"), 2))
    out += _chrono("tech", LANGUAGES, lambda l: l[0], lambda l: l[2], 120, "langchrono", 5,
                   "Lequel de ces langages est le plus ancien ?", "Lequel de ces langages est le plus récent ?")
    for ev, y in PRODUCTS:
        out.append(make("tech", f"En quelle année a eu lieu {ev} ?", str(y), _years(y, f"prod-{ev}"), 2 if y >= 2000 else 3))
        out.append(make("tech", f"Dans quelle décennie a eu lieu {ev} ?", decade(y), _decades(y, f"prodd-{ev}"), 2))
    out += _chrono("tech", PRODUCTS, lambda p: p[0][0].upper() + p[0][1:], lambda p: p[1], 360, "prodchrono", 3,
                   "Lequel de ces événements est le plus ancien ?", "Lequel de ces événements est le plus récent ?")
    actions = [a for _, a in SHORTCUTS]
    for keys, action in SHORTCUTS:
        out.append(make("tech", f"Que fait le raccourci clavier {keys} ?", action, pick(f"sc-{keys}", actions, action), 1 if keys in ("Ctrl + C", "Ctrl + V") else 2))
        out.append(make("tech", f"Quel raccourci clavier permet de : {action[0].lower() + action[1:]} ?", keys, pick(f"scr-{keys}", [k for k, _ in SHORTCUTS], keys), 2))
    for ext, kind in EXTENSIONS:
        out.append(make("tech", f"Quel type de fichier porte l'extension « {ext} » ?", kind, pick(f"ext-{ext}", EXT_KINDS, kind, key=lambda x: x.split()[1]), 1))
    for d, q, a, w in WRITTEN:
        out.append(make("tech", q, a, w, d))
    return out
