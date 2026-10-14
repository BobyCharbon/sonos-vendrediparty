"""Jeux de soirée : Undercover et « Qui de nous ? ».

N'importe quel invité crée une partie (avec son propre code / QR) et la fait avancer depuis son
téléphone ; les autres la rejoignent avec ce code, sans le code de la musique.
L'état d'une partie est un dict sérialisable (persisté avec la session).

Chaque joueur est identifié en secret par son guest_id (gardé sur son téléphone) et publiquement
par un « pid » aléatoire : les vues ne contiennent jamais le guest_id des autres, sinon on pourrait
se faire passer pour eux et lire leur mot.
"""

import random
import secrets
import time
import unicodedata

GAMES = {
    "undercover": "Undercover",
    "whoof": "Qui de nous ?",
    "never": "Je n'ai jamais",
}

# Undercover : les civils reçoivent un mot, les undercovers un mot proche ; Mr. White n'a pas de mot.
WORD_PAIRS = [
    ("Chat", "Chien"), ("Café", "Thé"), ("Plage", "Piscine"), ("Pizza", "Burger"), ("Guitare", "Violon"),
    ("Soleil", "Lune"), ("Avion", "Hélicoptère"), ("Vin", "Bière"), ("Train", "Métro"), ("Pomme", "Poire"),
    ("Football", "Rugby"), ("Ski", "Snowboard"), ("Netflix", "YouTube"), ("Instagram", "TikTok"),
    ("Chocolat", "Caramel"), ("Fromage", "Beurre"), ("Médecin", "Infirmier"), ("Policier", "Pompier"),
    ("Lit", "Canapé"), ("Douche", "Bain"), ("Stylo", "Crayon"), ("Livre", "Magazine"), ("Cinéma", "Théâtre"),
    ("Mariage", "Anniversaire"), ("Noël", "Pâques"), ("Lion", "Tigre"), ("Requin", "Dauphin"),
    ("Abeille", "Guêpe"), ("Rose", "Tulipe"), ("Vampire", "Zombie"), ("Sorcière", "Fée"), ("Paris", "Londres"),
    ("Genève", "Lausanne"), ("Raclette", "Fondue"), ("Croissant", "Pain au chocolat"), ("Sushi", "Ramen"),
    ("Kebab", "Tacos"), ("Vélo", "Trottinette"), ("Moto", "Scooter"), ("Voiture", "Camion"),
    ("Bateau", "Sous-marin"), ("Pirate", "Viking"), ("Château", "Palais"), ("Roi", "Prince"),
    ("iPhone", "Android"), ("Mojito", "Caïpirinha"), ("Champagne", "Prosecco"), ("Whisky", "Rhum"),
    ("Tequila", "Vodka"), ("DJ", "Chanteur"), ("Concert", "Festival"), ("Boîte de nuit", "Bar"),
    ("Karaoké", "Blind test"), ("Neige", "Grêle"), ("Pluie", "Orage"), ("Été", "Printemps"),
    ("Lunettes", "Lentilles"), ("Montre", "Bracelet"), ("Bague", "Collier"), ("Chaussette", "Chaussure"),
    ("Short", "Jupe"), ("Casquette", "Bonnet"), ("Parapluie", "Parasol"), ("Tente", "Caravane"),
    ("Hôtel", "Camping"), ("Avocat", "Juge"), ("Professeur", "Directeur"), ("École", "Université"),
    ("Harry Potter", "Le Seigneur des anneaux"), ("Batman", "Superman"), ("Mario", "Sonic"),
    ("Star Wars", "Star Trek"), ("Titanic", "Avatar"), ("Ketchup", "Mayonnaise"), ("Sel", "Poivre"),
    ("Miel", "Confiture"), ("Crêpe", "Gaufre"), ("Glace", "Sorbet"), ("Gâteau", "Tarte"), ("Banane", "Mangue"),
    ("Fraise", "Framboise"), ("Citron", "Orange"), ("Tomate", "Poivron"), ("Frites", "Chips"),
    ("Poulet", "Dinde"), ("Saumon", "Thon"), ("Lac", "Mer"), ("Forêt", "Jungle"), ("Désert", "Savane"),
    ("Volcan", "Geyser"), ("Fusée", "Satellite"), ("Astronaute", "Pilote"), ("Robot", "Cyborg"),
    ("Fantôme", "Squelette"), ("Clown", "Mime"), ("Ange", "Démon"), ("Licorne", "Pégase"),
    ("Dragon", "Dinosaure"), ("Cheval", "Âne"), ("Vache", "Chèvre"), ("Mouton", "Lama"),
    ("Souris", "Hamster"), ("Perroquet", "Pigeon"), ("Musculation", "Yoga"), ("Tennis", "Badminton"),
    ("Basket", "Volley"), ("Golf", "Mini-golf"), ("Bowling", "Billard"), ("Échecs", "Dames"),
    ("Poker", "Blackjack"), ("Uno", "Monopoly"), ("Selfie", "Photo de groupe"), ("Tatouage", "Piercing"),
    ("Barbe", "Moustache"), ("Coiffeur", "Barbier"), ("Parfum", "Déodorant"), ("Dentifrice", "Shampoing"),
    ("Réveil", "Horloge"), ("Ascenseur", "Escalator"), ("Cascade", "Rivière"), ("Igloo", "Cabane"),
    ("Pyjama", "Peignoir"), ("Barbecue", "Pique-nique"), ("Popcorn", "Barbe à papa"), ("Taxi", "Uber"),
]

WHOOF_QUESTIONS = [
    "finira par devenir célèbre", "oubliera son téléphone ici ce soir", "partira le dernier de la soirée",
    "survivrait le plus longtemps sur une île déserte", "tiendrait un mois sans internet",
    "se perdrait même avec un GPS", "deviendra millionnaire", "ferait le meilleur président",
    "chante le plus faux", "est le plus mauvais perdant", "pourrait dormir n'importe où", "mange le plus",
    "rit à ses propres blagues", "pleure devant un dessin animé", "arrive toujours en retard",
    "adopterait cinq chats", "sauterait en parachute sans hésiter", "participerait à une téléréalité",
    "partirait vivre à l'autre bout du monde", "oublierait l'anniversaire de son meilleur ami",
    "gagnerait un concours de danse", "mourrait en premier dans un film d'horreur",
    "dépenserait tout son salaire en un week-end", "a le plus de photos dans son téléphone",
    "cuisine le mieux", "ferait le meilleur espion", "tomberait amoureux en vacances",
    "lancerait une start-up", "se lèverait à 5 h pour aller courir", "met le plus l'ambiance sur la piste",
    "choisirait la pire musique", "ferait le meilleur DJ ce soir", "raconte les pires blagues",
    "garde le mieux un secret", "garde le moins bien un secret", "se marierait sur un coup de tête à Las Vegas",
    "se ferait un tatouage regrettable", "perdra ses clés ce soir", "finira la soirée en pyjama",
    "envoie les vocaux les plus longs", "passerait une nuit dans une maison hantée",
    "répond aux messages trois jours plus tard", "ferait le tour du monde en stop",
    "regarde une série entière en une nuit", "parle à ses plantes", "connaît toutes les paroles par cœur",
    "deviendrait le chef d'une bande de pirates", "se ferait passer pour malade pour éviter une soirée",
    "gagnerait à Qui veut gagner des millions", "ferait le meilleur prof",
]

WHOOF_AWKWARD = [
    "a déjà stalké son ex sur Instagram cette semaine", "a déjà fait semblant de ne pas voir quelqu'un dans la rue",
    "a déjà menti sur son âge", "a déjà lu les messages de quelqu'un en cachette",
    "a déjà envoyé un message à la mauvaise personne", "a déjà ghosté quelqu'un",
    "a le pire historique de recherche", "a déjà dragué quelqu'un dans cette pièce",
    "a déjà oublié le prénom de quelqu'un avec qui il est sorti", "a déjà fouillé dans la salle de bain de quelqu'un",
    "a déjà parlé dans le dos de quelqu'un ici", "a déjà vomi en soirée",
    "s'est déjà réveillé chez quelqu'un sans savoir comment il y était arrivé", "a déjà fait une déclaration bourré",
    "a déjà écrit à un ex à 3 h du matin", "a déjà fait semblant de rire à une blague qu'il ne comprenait pas",
    "a déjà inventé une excuse bidon pour partir d'un date", "a déjà eu un faux compte sur les réseaux",
    "a déjà liké une vieille photo par erreur en stalkant", "a déjà menti sur son CV",
    "a déjà offert un cadeau qu'on lui avait offert", "a déjà été jaloux de quelqu'un ici",
    "cache le plus de secrets", "a les conversations qu'il voudrait le moins qu'on lise",
    "a déjà eu un crush sur le ou la partenaire d'un ami", "a déjà été surpris en train de se parler tout seul",
    "a déjà fait pipi dans une piscine", "a déjà fait tomber son téléphone dans les toilettes",
    "est déjà parti d'un restaurant sans payer", "a déjà fait semblant d'être malade pour sécher le travail",
    "a déjà pleuré pour obtenir quelque chose", "a déjà raté un rendez-vous parce qu'il dormait",
    "a déjà mangé un truc tombé par terre devant tout le monde", "a déjà été recalé en public",
    "a déjà menti dans ce jeu", "a déjà pleuré devant une téléréalité",
    "a déjà fait un selfie aux toilettes", "a déjà été pris en train de chanter seul dans la rue",
    "regarde encore les stories de son ex", "a déjà dit « je t'aime » trop tôt",
]

WHOOF_HOT = [
    "a le plus d'expérience au lit", "a déjà couché le premier soir", "a déjà fait l'amour dans un lieu public",
    "a déjà envoyé une photo coquine", "a déjà fait un plan à trois", "a déjà simulé",
    "a le plus de fantasmes inavoués", "serait le meilleur coup de la soirée",
    "a déjà couché avec quelqu'un sans connaître son prénom", "a déjà été surpris en pleine action",
    "possède le plus de sextoys", "a déjà fait un strip-tease", "a déjà eu un sex friend",
    "a déjà fait l'amour au travail", "a déjà regardé un porno à deux", "a déjà fait du sexe en visio",
    "a déjà eu une aventure en vacances", "a déjà embrassé quelqu'un du même sexe",
    "a déjà couché avec un ex après la rupture", "a déjà fait l'amour dans une voiture",
    "a déjà utilisé des menottes", "a eu le plus de coups d'un soir cette année", "est le plus bruyant au lit",
    "a déjà couché avec deux personnes la même semaine", "a déjà conclu sur Tinder le soir même",
    "a déjà fait l'amour à la plage", "a déjà fait des bêtises dans un avion ou un train",
    "a déjà fantasmé sur quelqu'un dans cette pièce", "a déjà été pris en train de regarder un porno",
    "a déjà eu un suçon visible au travail", "a déjà envoyé un message coquin à la mauvaise personne",
    "a déjà testé le bondage", "reste le plus longtemps sous la couette", "ferait le meilleur acteur de film X",
    "a déjà fait l'amour sous la douche", "a eu le plus de partenaires",
    "a déjà embrassé plus de trois personnes dans la même soirée", "a déjà fini un jeu à boire déshabillé",
    "a déjà couché dans le lit de ses parents", "a déjà dormi nu chez quelqu'un",
]

# Modes de « Qui de nous ? » : (libellé, questions).
WHOOF_MODES = {
    "soft": ("😇 Soft", WHOOF_QUESTIONS),
    "awkward": ("😬 Malaisant", WHOOF_AWKWARD),
    "hot": ("🔥 Hot", WHOOF_HOT),
    "mix": ("🎲 Mix", WHOOF_QUESTIONS + WHOOF_AWKWARD + WHOOF_HOT),
}

# « Je n'ai jamais… » : chacun répond « déjà fait » ou « jamais » ; ceux qui l'ont fait boivent.
NEVER_SOFT = [
    "pris l'avion", "chanté au karaoké", "fait une nuit blanche", "raté un train ou un avion",
    "dormi à la belle étoile", "mangé des escargots", "regardé une série entière en un week-end",
    "oublié l'anniversaire d'un proche", "fait un tatouage", "teint mes cheveux d'une couleur flashy",
    "gagné à un jeu à gratter", "fait du stop", "parlé à une célébrité", "été dans le journal ou à la télé",
    "cassé l'écran de mon téléphone", "pleuré devant un Disney", "dansé sur une table", "sauté en parachute",
    "nagé dans une eau à moins de 15 degrés", "cuisiné pour plus de 10 personnes",
    "inventé une excuse pour annuler une soirée", "joué à un jeu vidéo toute une nuit",
    "été en retard à un rendez-vous important", "fait un road trip", "dormi dans un festival",
    "fait un selfie avec un inconnu", "parlé à mes plantes", "raté un gâteau", "fait une sieste de plus de 3 heures",
    "visité plus de 10 pays", "monté sur scène", "perdu mes clés plus de trois fois cette année",
    "fait une fausse note en chantant devant du monde", "adopté un animal sur un coup de tête",
    "mangé un repas entier avec les doigts au restaurant", "fini un marathon de films en une journée",
    "eu peur dans une maison hantée", "appelé un prof « maman » ou « papa »", "fait du camping sauvage",
    "été pris en photo par la presse",
]
NEVER_AWKWARD = [
    "stalké un ex sur les réseaux", "lu les messages de quelqu'un en cachette", "menti sur mon âge",
    "ghosté quelqu'un", "envoyé un message à la mauvaise personne", "fait semblant d'être malade pour sécher le travail",
    "vomi en soirée", "écrit à un ex en étant bourré", "oublié le prénom de quelqu'un en pleine conversation",
    "fait pipi dans une piscine", "volé quelque chose dans un magasin", "menti sur mon CV",
    "regretté un message vocal", "été viré", "dit « je t'aime » sans le penser",
    "fait semblant de ne pas voir quelqu'un dans la rue", "pleuré au travail", "fouillé dans la salle de bain de quelqu'un",
    "mangé un truc tombé par terre", "offert un cadeau qu'on m'avait offert", "eu un crush sur quelqu'un dans cette pièce",
    "eu un faux compte sur les réseaux", "liké une vieille photo par erreur en stalkant", "dormi au travail",
    "été mis à la porte d'un bar ou d'une boîte", "pris quelqu'un en photo en cachette",
    "répété un secret qu'on m'avait confié", "fait semblant d'aimer un cadeau", "triché à un examen",
    "fait semblant d'avoir oublié mon porte-monnaie", "été jaloux d'un ami", "googlé mon propre nom",
    "parlé dans le dos de quelqu'un ici", "été recalé devant tout le monde", "eu un fou rire à un enterrement",
    "envoyé à 4 h du matin un message que j'ai regretté", "fait semblant de connaître une chanson",
    "raccroché au nez de quelqu'un", "lu le journal intime de quelqu'un", "menti dans ce genre de jeu",
]
NEVER_HOT = [
    "couché le premier soir", "fait l'amour dans un lieu public", "envoyé une photo coquine", "fait un plan à trois",
    "simulé", "eu un sex friend", "couché avec un ex après la rupture", "fait l'amour dans une voiture",
    "utilisé des menottes", "eu un coup d'un soir", "fait l'amour au travail", "regardé un porno à deux",
    "fait du sexe en visio", "embrassé quelqu'un du même sexe", "fait un strip-tease", "eu une aventure en vacances",
    "couché avec quelqu'un sans connaître son prénom", "été surpris en pleine action", "fait l'amour à la plage",
    "fait l'amour sous la douche", "utilisé un sextoy", "conclu sur Tinder le soir même",
    "embrassé plus de trois personnes dans la même soirée", "fantasmé sur quelqu'un dans cette pièce",
    "dormi nu chez quelqu'un", "eu un suçon visible au travail", "fait des bêtises dans un avion ou un train",
    "testé le bondage", "fini un jeu à boire déshabillé", "couché avec deux personnes la même semaine",
    "fait l'amour dans le lit de mes parents", "envoyé un message coquin à la mauvaise personne",
    "été attiré par le ou la partenaire d'un ami", "eu une histoire avec un collègue",
    "fait l'amour plus de trois fois dans la même nuit", "acheté de la lingerie pour séduire",
    "joué à un jeu de rôle coquin", "embrassé quelqu'un dans cette pièce", "fait l'amour en pleine nature",
    "été réveillé par les voisins… à cause de moi",
]

NEVER_MODES = {
    "soft": ("😇 Soft", NEVER_SOFT),
    "awkward": ("😬 Malaisant", NEVER_AWKWARD),
    "hot": ("🔥 Hot", NEVER_HOT),
    "mix": ("🎲 Mix", NEVER_SOFT + NEVER_AWKWARD + NEVER_HOT),
}
# Jeux à questions : modes et formulation de la question.
QUESTION_GAMES = {
    "whoof": (WHOOF_MODES, "Qui de nous {} ?"),
    "never": (NEVER_MODES, "Je n'ai jamais {}."),
}
NEVER_ANSWERS = ("yes", "no")  # « je l'ai déjà fait » / « jamais »


def mode_label(g: dict) -> str | None:
    if g["type"] not in QUESTION_GAMES:
        return None
    return QUESTION_GAMES[g["type"]][0][g["options"].get("mode", "soft")][0]


ROLE_LABELS = {"civil": "Civil", "undercover": "Undercover", "white": "Mr. White"}


class GameError(Exception):
    pass


def normalize(text: str) -> str:
    """Comparaison tolérante (accents, majuscules, espaces) pour la réponse de Mr. White."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().replace("-", " ").split())


def new_code(taken) -> str:
    """Code à 4 chiffres, comme celui de la musique (plus simple à taper)."""
    while (code := f"{secrets.randbelow(10000):04d}") in taken:
        pass
    return code


def new_game(kind: str, host: str = "", name: str = "", white: bool = True, code: str = "", plays: bool = True,
             mode: str = "soft", sips: int = 0) -> dict:
    """Nouvelle partie ; son créateur (host) l'anime, et la rejoint comme joueur s'il joue aussi.
    S'il ne joue pas, il est maître du jeu : il peut voir les rôles et les mots."""
    if kind not in GAMES:
        raise GameError("Jeu inconnu")
    if mode not in WHOOF_MODES:
        raise GameError("Mode inconnu")
    g = {
        "id": secrets.token_hex(4), "code": code, "type": kind, "phase": "lobby", "host": host, "host_name": name,
        "created_at": time.time(), "updated_at": time.time(),
        # sips : gorgées que boit la personne désignée (« Qui de nous ? »), 0 = sans alcool.
        "options": {"white": white, "mode": mode, "sips": max(0, min(10, int(sips)))}, "players": [], "round": 0, "order": [], "votes": {},
        "candidates": None, "last": None, "winner": None, "words": None, "used": [],
        "question": None, "results": None, "kicked": [],
    }
    if host and plays:
        join(g, host, name)
    return g


def gid_of(g: dict, pid: str) -> str:
    """guest_id du joueur dont l'identifiant public est pid ("" si inconnu)."""
    return next((p["id"] for p in g["players"] if p["pid"] == pid), "")


def player(g: dict, gid: str) -> dict | None:
    return next((p for p in g["players"] if p["id"] == gid), None)


def alive(g: dict) -> list[dict]:
    """Joueurs encore en lice (pas les éliminés, ni ceux qui attendent la prochaine partie)."""
    return [p for p in g["players"] if p["alive"] and not p.get("waiting")]


def join(g: dict, gid: str, name: str = ""):
    if p := player(g, gid):
        p["name"] = name or p["name"]
        return
    if gid in g.get("kicked", []):
        raise GameError("L'animateur t'a retiré de cette partie")
    if len(g["players"]) >= 30:
        raise GameError("La partie est complète")
    taken = {p["pid"] for p in g["players"]}
    while (pid := secrets.token_hex(4)) in taken:
        pass
    # Undercover déjà lancé : le retardataire attend la prochaine partie (il reçoit un mot à « Rejouer »).
    waiting = g["type"] == "undercover" and g["phase"] not in ("lobby", "end")
    g["players"].append({"id": gid, "pid": pid, "name": name or "?", "alive": True, "role": None, "word": None,
                         "waiting": waiting})


def leave(g: dict, gid: str):
    """Un joueur part (ou est exclu), même en pleine partie : la partie continue sans lui."""
    p = player(g, gid)
    if p is None:
        raise GameError("Joueur introuvable")
    in_play = p in alive(g)
    g["players"].remove(p)
    g["votes"] = {v: t for v, t in g["votes"].items() if v != gid and t != gid}
    g["order"] = [i for i in g["order"] if i != gid]
    if g["candidates"]:
        g["candidates"] = [c for c in g["candidates"] if c != gid] or None
    # L'animateur s'en va : le joueur suivant reprend la main.
    if g["host"] == gid:
        nxt = g["players"][0] if g["players"] else None
        g["host"], g["host_name"] = (nxt["id"], nxt["name"]) if nxt else ("", "")
    if g["type"] == "undercover":
        if g["phase"] == "white_guess" and g["last"] and g["last"]["eliminated"] == gid:
            skip_white_guess(g)  # Mr. White parti avant de deviner
        elif in_play and g["phase"] in ("words", "vote", "reveal"):
            _check_end(g)


def kick(g: dict, gid: str):
    """L'animateur exclut un joueur : il ne peut plus revenir dans cette partie."""
    leave(g, gid)
    g.setdefault("kicked", []).append(gid)


def move(g: dict, gid: str, delta: int):
    """L'animateur change l'ordre : ordre de parole pendant les indices, sinon ordre de la liste."""
    if g["type"] == "undercover" and g["phase"] == "words":
        items, key = g["order"], gid
    else:
        items, key = g["players"], player(g, gid)
    if key not in items:
        raise GameError("Joueur introuvable")
    i = items.index(key)
    j = max(0, min(len(items) - 1, i + delta))
    items.insert(j, items.pop(i))


def start(g: dict, rng: random.Random = random):
    """Distribue les rôles (Undercover) ou pose la première question (Qui de nous ?)."""
    if g["type"] == "undercover":
        _deal(g, rng)
    else:
        if len(g["players"]) < 2:
            raise GameError("Il faut au moins 2 joueurs")
        _next_question(g, rng)


def _deal(g: dict, rng):
    players = g["players"]
    n = len(players)
    if n < 3:
        raise GameError("Il faut au moins 3 joueurs")
    undercovers = 1 if n <= 6 else 2 if n <= 9 else 3
    whites = 1 if g["options"]["white"] and n >= 5 else 0
    pairs = [i for i in range(len(WORD_PAIRS)) if i not in g["used"]] or list(range(len(WORD_PAIRS)))
    pair_index = rng.choice(pairs)
    g["used"] = (g["used"] + [pair_index])[-60:]
    civil, under = WORD_PAIRS[pair_index]
    if rng.random() < 0.5:
        civil, under = under, civil
    g["words"] = {"civil": civil, "undercover": under}
    roles = ["undercover"] * undercovers + ["white"] * whites
    roles += ["civil"] * (n - len(roles))
    rng.shuffle(roles)
    for p, role in zip(players, roles):
        p.update(alive=True, waiting=False, role=role, word={"civil": civil, "undercover": under}.get(role))
    g.update(round=1, winner=None, last=None, votes={}, candidates=None)
    _speaking_order(g, rng)


def _speaking_order(g: dict, rng):
    order = [p["id"] for p in alive(g)]
    rng.shuffle(order)
    # Mr. White ne commence jamais : il n'a rien pour donner un indice.
    if len(order) > 1 and player(g, order[0])["role"] == "white":
        order.append(order.pop(0))
    g["order"] = order
    g["phase"] = "words"


def start_vote(g: dict):
    if g["type"] != "undercover" or g["phase"] != "words":
        raise GameError("Pas le moment de voter")
    g.update(phase="vote", votes={}, candidates=None)


def vote(g: dict, voter: str, target: str, rng: random.Random = random):
    me, other = player(g, voter), player(g, target)
    if g["phase"] not in ("vote", "question") or not me:
        raise GameError("Pas de vote en cours")
    if g["type"] == "undercover":
        if me not in alive(g):
            raise GameError("Tu ne votes pas pendant cette manche")
        if not other or other not in alive(g) or target == voter:
            raise GameError("Vote invalide")
        if g["candidates"] and target not in g["candidates"]:
            raise GameError("Vote seulement pour les ex æquo")
    elif g["type"] == "never":
        if target not in NEVER_ANSWERS:
            raise GameError("Réponse invalide")
    elif not other:
        raise GameError("Vote invalide")
    g["votes"][voter] = target
    voters = alive(g) if g["type"] == "undercover" else g["players"]
    if all(p["id"] in g["votes"] for p in voters):
        close_vote(g, rng)


def tally(g: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for target in g["votes"].values():
        counts[target] = counts.get(target, 0) + 1
    return counts


def close_vote(g: dict, rng: random.Random = random):
    counts = tally(g)
    if g["type"] in QUESTION_GAMES:
        if g["phase"] != "question":
            raise GameError("Pas de question en cours")
        if g["type"] == "never":
            g["results"] = [[gid, answer] for gid, answer in g["votes"].items()]
        else:
            g["results"] = sorted(([gid, c] for gid, c in counts.items()), key=lambda x: -x[1])
        g["phase"] = "results"
        return
    if g["phase"] != "vote":
        raise GameError("Pas de vote en cours")
    if not counts:
        raise GameError("Personne n'a encore voté")
    best = max(counts.values())
    tied = [gid for gid, c in counts.items() if c == best]
    if len(tied) > 1 and not g["candidates"]:
        # Égalité : on revote entre les ex æquo ; à la deuxième égalité, le hasard tranche.
        g.update(candidates=tied, votes={}, last={"tie": True})
        return
    eliminate(g, rng.choice(tied) if len(tied) > 1 else tied[0])


def eliminate(g: dict, target: str):
    p = player(g, target)
    if g["type"] != "undercover" or g["phase"] not in ("words", "vote") or not p or p not in alive(g):
        raise GameError("Élimination impossible")
    p["alive"] = False
    g.update(votes={}, candidates=None, last={"eliminated": target, "role": p["role"], "round": g["round"]})
    if p["role"] == "white":
        g["phase"] = "white_guess"
    else:
        _check_end(g) or g.update(phase="reveal")


def white_guess(g: dict, gid: str, guess: str):
    if g["phase"] != "white_guess" or not g["last"] or g["last"]["eliminated"] != gid:
        raise GameError("Ce n'est pas à toi de deviner")
    guess = guess.strip()[:40]
    g["last"]["guess"] = guess
    if normalize(guess) == normalize(g["words"]["civil"]):
        g.update(winner="white", phase="end")
    else:
        _check_end(g) or g.update(phase="reveal")


def skip_white_guess(g: dict):
    """L'hôte passe la devinette (Mr. White parti ou trop long)."""
    if g["phase"] != "white_guess":
        raise GameError("Pas de devinette en cours")
    _check_end(g) or g.update(phase="reveal")


def _check_end(g: dict) -> bool:
    living = alive(g)
    impostors = [p for p in living if p["role"] != "civil"]
    civils = [p for p in living if p["role"] == "civil"]
    if not impostors:
        g.update(winner="civils", phase="end")
    elif len(civils) <= 1:
        g.update(winner="impostors", phase="end")
    return g["phase"] == "end"


def next_step(g: dict, rng: random.Random = random):
    if g["type"] == "undercover":
        if g["phase"] != "reveal":
            raise GameError("Pas encore")
        g["round"] += 1
        g["last"] = None
        _speaking_order(g, rng)
    else:
        if g["phase"] not in ("results", "question"):
            raise GameError("Pas encore")
        _next_question(g, rng)


def _next_question(g: dict, rng):
    modes, phrasing = QUESTION_GAMES[g["type"]]
    pool = modes[g["options"].get("mode", "soft")][1]
    left = [q for q in pool if q not in g["used"]] or pool
    q = rng.choice(left)
    g["used"] = (g["used"] + [q])[-(len(pool) - 1):]
    g.update(phase="question", question=phrasing.format(q), votes={}, results=None, round=g["round"] + 1)


def restart(g: dict, rng: random.Random = random) -> dict:
    """Nouvelle manche avec les mêmes joueurs."""
    if g["type"] == "undercover":
        _deal(g, rng)
    else:
        _next_question(g, rng)
    return g


# --- Vues : chaque invité ne voit que ce qu'il a le droit de voir ---

def _pid(g: dict, gid: str | None) -> str | None:
    p = player(g, gid) if gid else None
    return p["pid"] if p else None


def view(g: dict, gid: str) -> dict:
    """Vue d'un joueur (ou d'un visiteur qui n'a pas encore rejoint) : son mot, jamais celui des autres.
    Le maître du jeu (animateur qui ne joue pas) voit tout."""
    ended = g["phase"] == "end"
    me = player(g, gid)
    master = bool(gid) and g["host"] == gid and me is None
    players = []
    for p in g["players"]:
        waiting = bool(p.get("waiting")) and g["phase"] != "end"
        out = {"pid": p["pid"], "name": p["name"], "alive": p["alive"] and not waiting, "waiting": waiting,
               "voted": p["id"] in g["votes"], "host": p["id"] == g["host"]}
        # Un éliminé dévoile son rôle, pas son mot (celui d'un civil aiderait les undercovers restants).
        if (ended or master or not p["alive"]) and p["role"]:
            out["role"] = ROLE_LABELS[p["role"]]
        if ended or master:
            out["word"] = p["word"]
        players.append(out)
    out = {
        "id": g["id"], "code": g["code"], "type": g["type"], "name": GAMES[g["type"]], "phase": g["phase"],
        "mode": mode_label(g),
        "round": g["round"], "players": players, "is_host": bool(gid) and g["host"] == gid, "master": master,
        "host_name": g.get("host_name", ""),
        "order": [player(g, i)["name"] for i in g["order"] if player(g, i)] if g["type"] == "undercover" else [],
        "order_pids": [_pid(g, i) for i in g["order"] if player(g, i)] if g["type"] == "undercover" else [],
        "candidates": [_pid(g, i) for i in g["candidates"]] if g["candidates"] else None,
        "winner": g["winner"], "question": g["question"], "votes_count": len(g["votes"]), "options": g["options"],
        "kicked": bool(gid) and gid in g.get("kicked", []),
    }
    last = g["last"] or {}
    if last.get("eliminated"):
        p = player(g, last["eliminated"])
        out["last"] = {"pid": p["pid"] if p else None, "name": p["name"] if p else "?",
                       "role": ROLE_LABELS.get(last["role"]), "guess": last.get("guess"), "me": last["eliminated"] == gid}
    elif last.get("tie"):
        out["last"] = {"tie": True}
    if g["results"] and g["type"] == "never":
        # Pas anonyme, comme le vrai jeu : on voit qui l'a déjà fait (et qui boit).
        out["results"] = [{"pid": _pid(g, i), "name": (player(g, i) or {}).get("name", "?"), "answer": a}
                          for i, a in g["results"]]
    elif g["results"]:
        out["results"] = [{"pid": _pid(g, i), "name": (player(g, i) or {}).get("name", "?"), "count": c}
                          for i, c in g["results"]]
    if ended or master:
        out["words"] = g["words"]
    if me:
        out["me"] = {"pid": me["pid"], "alive": me["alive"], "waiting": bool(me.get("waiting")) and not ended, "vote": g["votes"].get(gid) if g["type"] == "never" else _pid(g, g["votes"].get(gid)),
                     "role": "Mr. White" if me["role"] == "white" else None, "word": me["word"],
                     "dealt": me["role"] is not None}
    return out


def summary(g: dict) -> dict:
    """Vue d'ensemble pour l'admin (sans les secrets)."""
    name = GAMES[g["type"]] + (" · " + mode_label(g) if mode_label(g) else "")
    return {"code": g["code"], "name": name, "phase": g["phase"], "round": g["round"],
            "players": [p["name"] for p in g["players"]], "host": g.get("host_name", ""),
            "updated_at": g["updated_at"]}
