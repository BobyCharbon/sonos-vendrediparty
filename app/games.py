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

from . import beerpong, debate, heist, island, likely, neon, president, purity, quiz
from .divan_cards import DIVAN_CARDS
from .tmc_questions import TMC_QUESTIONS
from .party_questions import NEVER_AWKWARD, NEVER_HOT, NEVER_SOFT, WHOOF_AWKWARD, WHOOF_HOT, WHOOF_SOFT

GAMES = {
    "undercover": "Undercover",
    "whoof": "Qui de nous ?",
    "likely": "Qui est le plus… ?",
    "debate": "Pour ou contre",
    "beerpong": "Beer pong",
    "never": "Je n'ai jamais",
    "roulette": "Roulette",
    "blackjack": "Blackjack",
    "casino": "Casino",
    "divan": "Le Divan",
    "tmc": "Tu me connais ?",
    "pyramid": "Pyramide",
    "biskit": "Biskit Royal",
    "quiz": "Quiz",
    "president": "Président",
    "neon": "Néon Knockout",
    "island": "L’île qui s’effondre",
    "heist": "Braquage en miniature",
    "purity": "Purify Test",
    "room": "Salle de jeux",
}
BLACKJACKS = ("blackjack",)

# Undercover : les civils reçoivent un mot, les undercovers un mot proche ; Mr. White n'a pas de mot.
# (mot, mot proche, indice : ce que les deux ont en commun, donné aux imposteurs qui le demandent)
WORD_PAIRS = [
    ("Chat", "Chien", "un animal de compagnie"), ("Café", "Thé", "une boisson chaude"), ("Plage", "Piscine", "un endroit pour se baigner"),
    ("Pizza", "Burger", "un plat de fast-food"), ("Guitare", "Violon", "un instrument à cordes"), ("Soleil", "Lune", "un astre"),
    ("Avion", "Hélicoptère", "un engin volant"), ("Vin", "Bière", "une boisson alcoolisée"), ("Train", "Métro", "un transport sur rails"),
    ("Pomme", "Poire", "un fruit"), ("Football", "Rugby", "un sport de ballon"), ("Ski", "Snowboard", "un sport d'hiver"),
    ("Netflix", "YouTube", "une plateforme de vidéos"), ("Instagram", "TikTok", "un réseau social"), ("Chocolat", "Caramel", "une douceur sucrée"),
    ("Fromage", "Beurre", "un produit laitier"), ("Médecin", "Infirmier", "un métier de la santé"), ("Policier", "Pompier", "un métier de secours"),
    ("Lit", "Canapé", "un meuble pour s'allonger"), ("Douche", "Bain", "un moment dans la salle de bain"), ("Stylo", "Crayon", "un objet pour écrire"),
    ("Livre", "Magazine", "de la lecture"), ("Cinéma", "Théâtre", "un spectacle"), ("Mariage", "Anniversaire", "une fête"),
    ("Noël", "Pâques", "une fête de l'année"), ("Lion", "Tigre", "un grand félin"), ("Requin", "Dauphin", "un animal marin"),
    ("Abeille", "Guêpe", "un insecte qui pique"), ("Rose", "Tulipe", "une fleur"), ("Vampire", "Zombie", "un monstre"),
    ("Sorcière", "Fée", "un personnage magique"), ("Paris", "Londres", "une capitale européenne"), ("Genève", "Lausanne", "une ville de Suisse romande"),
    ("Raclette", "Fondue", "un plat au fromage"), ("Croissant", "Pain au chocolat", "une viennoiserie"), ("Sushi", "Ramen", "un plat japonais"),
    ("Kebab", "Tacos", "un plat à emporter"), ("Vélo", "Trottinette", "un engin à roues sans moteur"), ("Moto", "Scooter", "un deux-roues à moteur"),
    ("Voiture", "Camion", "un véhicule à moteur"), ("Bateau", "Sous-marin", "un véhicule sur l'eau"), ("Pirate", "Viking", "un navigateur d'autrefois"),
    ("Château", "Palais", "une demeure royale"), ("Roi", "Prince", "un membre de la royauté"), ("iPhone", "Android", "un smartphone"),
    ("Mojito", "Caïpirinha", "un cocktail"), ("Champagne", "Prosecco", "un vin pétillant"), ("Whisky", "Rhum", "un alcool fort"),
    ("Tequila", "Vodka", "un alcool qui se boit en shot"), ("DJ", "Chanteur", "un métier de la musique"), ("Concert", "Festival", "un événement musical"),
    ("Boîte de nuit", "Bar", "un lieu de sortie"), ("Karaoké", "Blind test", "une animation musicale"), ("Neige", "Grêle", "une précipitation glacée"),
    ("Pluie", "Orage", "une météo humide"), ("Été", "Printemps", "une saison"), ("Lunettes", "Lentilles", "pour mieux voir"),
    ("Montre", "Bracelet", "un objet au poignet"), ("Bague", "Collier", "un bijou"), ("Chaussette", "Chaussure", "quelque chose qu'on porte aux pieds"),
    ("Short", "Jupe", "un vêtement d'été"), ("Casquette", "Bonnet", "un couvre-chef"), ("Parapluie", "Parasol", "un objet qui protège du ciel"),
    ("Tente", "Caravane", "un abri de vacances"), ("Hôtel", "Camping", "un hébergement de vacances"), ("Avocat", "Juge", "un métier de la justice"),
    ("Professeur", "Directeur", "un métier de l'école"), ("École", "Université", "un lieu d'études"), ("Harry Potter", "Le Seigneur des anneaux", "une saga fantastique"),
    ("Batman", "Superman", "un super-héros"), ("Mario", "Sonic", "un héros de jeu vidéo"), ("Star Wars", "Star Trek", "une saga de science-fiction"),
    ("Titanic", "Avatar", "un film à grand succès"), ("Ketchup", "Mayonnaise", "une sauce"), ("Sel", "Poivre", "un assaisonnement"),
    ("Miel", "Confiture", "quelque chose à tartiner"), ("Crêpe", "Gaufre", "une douceur à la pâte"), ("Glace", "Sorbet", "un dessert glacé"),
    ("Gâteau", "Tarte", "une pâtisserie"), ("Banane", "Mangue", "un fruit exotique"), ("Fraise", "Framboise", "un fruit rouge"),
    ("Citron", "Orange", "un agrume"), ("Tomate", "Poivron", "un légume"), ("Frites", "Chips", "un snack de pomme de terre"),
    ("Poulet", "Dinde", "une volaille"), ("Saumon", "Thon", "un poisson"), ("Lac", "Mer", "une étendue d'eau"),
    ("Forêt", "Jungle", "un paysage plein d'arbres"), ("Désert", "Savane", "un paysage aride"), ("Volcan", "Geyser", "un phénomène naturel"),
    ("Fusée", "Satellite", "un engin spatial"), ("Astronaute", "Pilote", "un métier du ciel"), ("Robot", "Cyborg", "une machine humanoïde"),
    ("Fantôme", "Squelette", "une créature d'Halloween"), ("Clown", "Mime", "un artiste de cirque"), ("Ange", "Démon", "un être surnaturel"),
    ("Licorne", "Pégase", "un cheval légendaire"), ("Dragon", "Dinosaure", "une créature géante"), ("Cheval", "Âne", "un animal qu'on monte"),
    ("Vache", "Chèvre", "un animal de la ferme"), ("Mouton", "Lama", "un animal à laine"), ("Souris", "Hamster", "un rongeur"),
    ("Perroquet", "Pigeon", "un oiseau"), ("Musculation", "Yoga", "une activité en salle de sport"), ("Tennis", "Badminton", "un sport de raquette"),
    ("Basket", "Volley", "un sport de ballon en salle"), ("Golf", "Mini-golf", "un jeu avec une balle et un trou"), ("Bowling", "Billard", "un jeu de bar"),
    ("Échecs", "Dames", "un jeu de plateau"), ("Poker", "Blackjack", "un jeu de cartes de casino"), ("Uno", "Monopoly", "un jeu de société"),
    ("Selfie", "Photo de groupe", "une photo"), ("Tatouage", "Piercing", "une marque sur le corps"), ("Barbe", "Moustache", "des poils du visage"),
    ("Coiffeur", "Barbier", "un métier des cheveux"), ("Parfum", "Déodorant", "une odeur qu'on porte"), ("Dentifrice", "Shampoing", "un produit de toilette"),
    ("Réveil", "Horloge", "un objet qui donne l'heure"), ("Ascenseur", "Escalator", "pour changer d'étage"), ("Cascade", "Rivière", "de l'eau qui coule"),
    ("Igloo", "Cabane", "un petit abri"), ("Pyjama", "Peignoir", "une tenue de maison"), ("Barbecue", "Pique-nique", "un repas en plein air"),
    ("Popcorn", "Barbe à papa", "une friandise de fête foraine"), ("Taxi", "Uber", "un trajet avec chauffeur"),
]




# Modes de « Qui de nous ? » : (libellé, questions).
WHOOF_MODES = {
    "soft": ("😇 Soft", WHOOF_SOFT),
    "awkward": ("😬 Malaisant", WHOOF_AWKWARD),
    "hot": ("🔥 Hot", WHOOF_HOT),
    "mix": ("🎲 Mix", WHOOF_SOFT + WHOOF_AWKWARD + WHOOF_HOT),
}

# « Je n'ai jamais… » : chacun répond « déjà fait » ou « jamais » ; ceux qui l'ont fait boivent.

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


# Le Divan : questions pour parler vrai, dans quatre catégories (textes originaux).
DIVAN_LABELS = {"experiences": "Expériences", "emotions": "Émotions", "relations": "Relations", "childhood": "Enfance",
                "dreams": "Rêves & avenir", "whatif": "Et si…", "couple": "Couple"}
# Catégories proposées par défaut ; le mode couple se choisit à part (il remplace les autres).
DIVAN_DEFAULT = [c for c in DIVAN_CARDS if c != "couple"]

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
        "options": {"white": white, "mode": mode, "sips": max(0, min(10, int(sips))), "floors": 5}, "players": [], "round": 0, "order": [], "votes": {},
        "candidates": None, "last": None, "winner": None, "words": None, "used": [],
        "question": None, "results": None, "kicked": [],
        # Roulette : noms notés par l'animateur, dernier tirage et perdants précédents.
        "names": [], "spin": None, "history": [],
        # Blackjack : sabot, croupier, mains et jetons (voir plus bas).
        "bj": {"shoe": [], "dealer": [], "seats": [], "turn": None, "hands": {}, "chips": {}, "rebuys": {}},
        # Casino (roulette européenne) : mises du tour, jetons, dernier lancer et numéros sortis.
        "casino": {"bets": {}, "chips": {}, "rebuys": {}, "spin": None, "history": [], "results": {}},
        # Le Divan : catégories choisies, joueur sur le divan, carte en cours, soutiens reçus.
        "divan": {"cats": list(DIVAN_DEFAULT), "turn": 0, "card": None, "used": [], "hearts": [], "joker": False, "n": 0},
        # Tu me connais ? : duo en cours, points par joueur et par duo (« a>b » : a devine b), noms des joueurs partis.
        "tmc": {"duo": None, "scores": {}, "pairs": {}, "names": {}, "used": [], "last": []},
    }
    if kind == "quiz":
        quiz.init(g)
    if kind == "purity":
        purity.init(g)
    if kind == "likely":
        likely.init(g)
    if kind == "debate":
        debate.init(g)
    if kind == "beerpong":
        beerpong.init(g)
    if kind == "room":
        # Salle de jeux : un seul code pour la soirée ; l'animateur y lance les jeux les uns après les autres.
        g.update(current=None, rhistory=[], rtally={}, rpts={}, rnames={})
    if host and plays:
        join(g, host, name)
    return g


SIPS_LOG_SIZE = 20  # dernières gorgées gardées pour la télé (« Léa boit 2 »)


def add_sips(g: dict, gid: str, drink: int = 0, give: int = 0):
    """Compteur de gorgées de la partie : bues et distribuées, par joueur ; chaque gorgée est aussi notée dans le
    journal (numéroté), d'où la télé annonce en grand qui boit et qui distribue, quel que soit le jeu."""
    t = g.setdefault("tally", {}).setdefault(gid, {"drink": 0, "give": 0})
    t["drink"] += drink
    t["give"] += give
    if not drink and not give:
        return
    p = player(g, gid) or {}
    log = g.setdefault("sips_log", [])
    n = (log[-1]["n"] + 1) if log else 1
    g["sips_log"] = (log + [{"n": n, "gid": gid, "pid": p.get("pid"), "name": p.get("name", "?"),
                             "drink": drink, "give": give, "at": time.time()}])[-SIPS_LOG_SIZE:]


def is_lead(g: dict, gid: str | None) -> bool:
    """Droits d'animateur : le créateur de la partie, ou l'admin de la soirée (toujours au moins les mêmes droits)."""
    return bool(gid) and (gid == g.get("host") or gid in g.get("leads", []))


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
    if g["type"] == "neon" and neon.state(g)["mode"] == "duo" and g["phase"] not in ("lobby", "end"):
        raise GameError("Ce match en duo a commencé. Tu peux regarder et rejoindre au prochain match.")
    if gid in g.get("kicked", []):
        raise GameError("Tu as été banni de cette partie : tu ne peux plus la rejoindre")
    if len(g["players"]) >= ({"president": 6, "neon": 8, "island": 8, "heist": 8}.get(g["type"], 30)):
        raise GameError("La partie est complète")
    if gid in g.get("removed", []):  # revenir après une exclusion efface la marque
        g["removed"].remove(gid)
    taken = {p["pid"] for p in g["players"]}
    while (pid := secrets.token_hex(4)) in taken:
        pass
    # Undercover déjà lancé : le retardataire attend la prochaine partie (il reçoit un mot à « Rejouer »).
    waiting = g["type"] in ("undercover", "president", "neon", "island", "heist") and g["phase"] not in ("lobby", "end")
    # Pyramide déjà lancée : l'animateur doit accepter l'arrivée (puis le nouveau fait sa distribution).
    pending = g["type"] == "pyramid" and g["phase"] not in ("lobby",) and bool(g.get("pyr"))
    g["players"].append({"id": gid, "pid": pid, "name": name or "?", "alive": True, "role": None, "word": None,
                         "waiting": waiting, "pending": pending})
    if g["type"] == "beerpong" and g["phase"] != "lobby":
        beerpong.join_late(g)  # le retardataire rejoint la plus petite équipe


# Jeux où l'animateur peut ajouter des participants sans téléphone (il vote, mise ou joue pour eux). Pas Undercover,
# Quiz, Purify ni Président : ils reposent sur un secret (mot, main) ou des réponses personnelles.
MANUAL_GAMES = ("divan", "tmc", "never", "pyramid", "biskit", "likely", "debate", "room", "whoof", "blackjack", "casino", "beerpong")


def add_guest(g: dict, name: str, guest_id: str | None = None):
    """L'animateur ajoute un participant sans téléphone (tapé à la main) : c'est lui qui agit pour lui."""
    if g["type"] not in MANUAL_GAMES:
        raise GameError("Pas possible dans ce jeu")
    name = " ".join((name or "").split())[:30]
    if not name:
        raise GameError("Écris un prénom")
    if guest_id:
        if not guest_id.startswith("manual-"):
            raise GameError("Identité manuelle non valide")
        if existing := player(g, guest_id):
            return existing
    if len(g["players"]) >= 30:
        raise GameError("La partie est complète")
    taken = {p["pid"] for p in g["players"]}
    while (pid := secrets.token_hex(4)) in taken:
        pass
    new = {"id": guest_id or "manual-" + secrets.token_hex(6), "pid": pid, "name": name, "alive": True, "role": None,
           "word": None, "waiting": False, "manual": True}
    g["players"].append(new)
    if g["type"] == "pyramid" and g.get("pyr"):
        pyr_accept(g, new["id"])  # ajouté par l'animateur : déjà accepté
    return new


def is_manual(g: dict, gid: str) -> bool:
    return bool((player(g, gid) or {}).get("manual"))


def vote_for(g: dict, target: str, answer: str, rng: random.Random = random):
    """L'animateur enregistre le vote d'un participant sans téléphone : sa réponse (Je n'ai jamais) ou la personne
    qu'il désigne (Qui de nous ?, identifiant public)."""
    if not is_manual(g, target):
        raise GameError("Ce joueur répond sur son téléphone")
    if g["type"] == "whoof":
        answer = gid_of(g, answer)
        if not answer:
            raise GameError("Choisis qui il ou elle désigne")
    vote(g, target, answer, rng)


def leave(g: dict, gid: str):
    """Un joueur part (ou est exclu), même en pleine partie : la partie continue sans lui."""
    p = player(g, gid)
    if p is None:
        raise GameError("Joueur introuvable")
    in_play = p in alive(g)
    g["players"].remove(p)
    if g["type"] == "heist":
        heist.leave(g, gid, p["pid"])
    if g["type"] == "island":
        island.leave(g, gid, p["pid"])
    if g["type"] == "neon":
        neon.leave(g, gid, p["pid"])
    if g["type"] == "president":
        president.leave(g, gid)
    if g["type"] == "pyramid":
        pyr_leave(g, gid)
    if g["type"] == "biskit":
        bk_leave(g, gid)
    if g["type"] == "purity":
        purity.leave(g, gid)
    if g["type"] == "likely":
        _lk_award(g, likely.settle(g))  # il ne manquait que son vote
    if g["type"] == "debate":
        debate.settle(g)  # il ne manquait que son vote
    if g["type"] == "quiz":
        g["quiz"]["personal"].pop(gid, None)
        if g["phase"] == "run" and g["quiz"]["personal"] and all(x["done"] for x in g["quiz"]["personal"].values()):
            quiz._finish(g)
    g["votes"] = {v: t for v, t in g["votes"].items() if v != gid and t != gid}
    g["order"] = [i for i in g["order"] if i != gid]
    if g["candidates"]:
        g["candidates"] = [c for c in g["candidates"] if c != gid] or None
    # L'animateur s'en va : le joueur suivant reprend la main.
    if g["host"] == gid:
        nxt = next((p for p in g["players"] if not p.get("manual")), None)
        g["host"], g["host_name"] = (nxt["id"], nxt["name"]) if nxt else ("", "")
    if g["type"] in BLACKJACKS:
        bj = g["bj"]
        turn = bj["turn"]
        current = bj["seats"][turn] if turn is not None and turn < len(bj["seats"]) else None
        if gid in bj["seats"]:
            bj["seats"].remove(gid)
        bj["hands"].pop(gid, None)
        if g["phase"] == "play":
            if current == gid:
                _bj_advance(g, turn)  # le suivant a pris sa place dans la liste
            elif current:
                bj["turn"] = bj["seats"].index(current)
        elif g["phase"] == "bet" and bj["hands"] and all(p["id"] in bj["hands"] for p in g["players"]):
            bj_deal(g)  # il ne manquait que sa mise
    if g["type"] == "tmc":
        tmc_left(g, gid)
    if g["type"] == "undercover":
        if g["phase"] == "white_guess" and g["last"] and g["last"]["eliminated"] == gid:
            skip_white_guess(g)  # Mr. White parti avant de deviner
        elif in_play and g["phase"] in ("words", "vote", "reveal"):
            _check_end(g)


def handover(g: dict, actor: str, target: str):
    """L'animateur passe la main à un autre joueur (qui a son téléphone) et reste joueur s'il jouait.
    Valable pour tous les jeux : la partie continue avec le nouvel animateur. Pour partir : « Quitter la partie »."""
    p = player(g, target)
    if not p or target == actor:
        raise GameError("Choisis un autre joueur")
    if p.get("manual") or p.get("pending"):
        raise GameError("Choisis un joueur présent avec son téléphone")
    g["host"], g["host_name"] = target, p["name"]
    if actor in g.get("leads", []):
        g["leads"].remove(actor)


def kick(g: dict, gid: str):
    """L'animateur exclut un joueur (absent, parti…) : il pourra revenir quand il veut avec le code."""
    leave(g, gid)
    if gid not in g.setdefault("removed", []):
        g["removed"].append(gid)


def ban(g: dict, gid: str):
    """L'animateur bannit un joueur : il ne peut plus revenir dans cette partie avec ce code."""
    if player(g, gid):
        leave(g, gid)
    if gid not in g.setdefault("kicked", []):
        g["kicked"].append(gid)
    if gid in g.get("removed", []):
        g["removed"].remove(gid)


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


def set_names(g: dict, names: list[str]):
    """Roulette : l'animateur note les participants (pas forcément inscrits à la partie)."""
    if g["type"] != "roulette":
        raise GameError("Pas une roulette")
    clean = []
    for n in names:
        n = " ".join(str(n).split())[:20]
        if n and n.lower() not in [c.lower() for c in clean]:
            clean.append(n)
    if len(clean) > 30:
        raise GameError("30 noms au maximum")
    g["names"] = clean
    # Roue modifiée après un tirage : on revient à la préparation (le résultat affiché ne correspond plus).
    if g["spin"] and clean != g["spin"]["names"]:
        g["phase"] = "lobby"


def spin(g: dict, rng: random.Random = random):
    """Lance la roue : tout le monde voit la même animation et le même perdant."""
    if g["type"] != "roulette":
        raise GameError("Pas une roulette")
    if len(g["names"]) < 2:
        raise GameError("Il faut au moins 2 noms sur la roue")
    i = rng.randrange(len(g["names"]))
    g["spin"] = {"id": secrets.token_hex(4), "index": i, "names": list(g["names"]), "at": time.time(),
                 "jitter": round(rng.uniform(-0.35, 0.35), 3)}
    g["history"] = (g["history"] + [g["names"][i]])[-20:]
    g["phase"] = "spun"
    g["round"] += 1


# --- Blackjack (croupier = l'app ; pas de split ni d'assurance) ---

BJ_START_CHIPS = 100
BJ_BETS = {"blackjack": (5, 1000)}  # mise min / max (jetons)


def bj_drinks(g: dict) -> int:
    """Mode gorgées : on mise des gorgées (1 à options.sips) au lieu de jetons ; 0 = mode jetons."""
    return g["options"].get("sips", 0)


def _bj_shoe(rng) -> list[str]:
    shoe = [r + s for _ in range(6) for s in "SHDC" for r in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K")]
    rng.shuffle(shoe)
    return shoe


def bj_value(cards: list[str]) -> tuple[int, bool]:
    """(total, souple) : un as compte 11 tant que ça ne dépasse pas 21."""
    total = sum(11 if c[0] == "A" else 10 if c[0] in "TJQK" else int(c[0]) for c in cards)
    aces = sum(c[0] == "A" for c in cards)
    while total > 21 and aces:
        total, aces = total - 10, aces - 1
    return total, aces > 0


def _bj_is_blackjack(cards: list[str]) -> bool:
    return len(cards) == 2 and bj_value(cards)[0] == 21


SUIT_SIGNS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def card_label(c: str) -> str:
    return ("10" if c[0] == "T" else c[0]) + SUIT_SIGNS[c[1]]


def _bj_log(g: dict, gid: str | None, text: str):
    """Dernières actions de la table, affichées sur tous les écrans."""
    bj = g["bj"]
    p = player(g, gid) if gid else None
    entry = {"n": bj.get("log_n", 0) + 1, "pid": p["pid"] if p else None, "name": p["name"] if p else "Croupier", "text": text}
    bj["log_n"] = entry["n"]
    bj["log"] = (bj.get("log", []) + [entry])[-8:]


def _bj_draw(g: dict, rng) -> str:
    bj = g["bj"]
    if len(bj["shoe"]) < 52:
        bj["shoe"] = _bj_shoe(rng)  # sabot presque vide : on rebat 6 jeux
    return bj["shoe"].pop()


def bj_open_bets(g: dict):
    if not g["players"]:
        raise GameError("Il faut au moins 1 joueur")
    bj = g["bj"]
    for p in g["players"]:
        bj["chips"].setdefault(p["id"], BJ_START_CHIPS)
    bj.update(dealer=[], seats=[], turn=None, hands={})
    g["phase"] = "bet"
    g["round"] += 1


def bj_bet(g: dict, gid: str, amount: int, rng: random.Random = random):
    if g["phase"] != "bet" or not player(g, gid):
        raise GameError("Les mises sont fermées")
    lo, hi = BJ_BETS[g["type"]]
    bj = g["bj"]
    bj["chips"].setdefault(gid, BJ_START_CHIPS)
    if bj_drinks(g):
        lo, hi = 1, bj_drinks(g)
    else:
        hi = min(hi, bj["chips"][gid])
    if not lo <= amount <= hi:
        raise GameError(f"Mise entre {lo} et {hi}" if hi >= lo else "Plus assez de jetons : recharge-toi")
    bj["hands"][gid] = {"cards": [], "bet": amount, "status": "bet", "doubled": False, "result": None, "delta": 0}
    # Tout le monde a misé : on distribue.
    if all(p["id"] in bj["hands"] for p in g["players"]):
        bj_deal(g, rng)


def bj_rebuy(g: dict, gid: str):
    bj = g["bj"]
    if bj_drinks(g) or bj["chips"].get(gid, 0) >= BJ_BETS["blackjack"][0]:
        raise GameError("Tu as encore des jetons")
    bj["chips"][gid] = BJ_START_CHIPS
    bj["rebuys"][gid] = bj["rebuys"].get(gid, 0) + 1


def bj_deal(g: dict, rng: random.Random = random):
    bj = g["bj"]
    if g["phase"] != "bet":
        raise GameError("Pas le moment de distribuer")
    seats = [p["id"] for p in g["players"] if p["id"] in bj["hands"]]
    if not seats:
        raise GameError("Personne n'a misé")
    for gid in list(bj["hands"]):
        if gid not in seats:
            del bj["hands"][gid]
    bj["seats"] = seats
    for gid in seats:
        h = bj["hands"][gid]
        if not bj_drinks(g):
            bj["chips"][gid] -= h["bet"]
        h.update(cards=[_bj_draw(g, rng), _bj_draw(g, rng)], status="playing")
        if _bj_is_blackjack(h["cards"]):
            h["status"] = "blackjack"
    bj["dealer"] = [_bj_draw(g, rng), _bj_draw(g, rng)]
    g["phase"] = "play"
    _bj_log(g, None, f"distribue et montre {card_label(bj['dealer'][0])}")
    for gid in seats:
        if bj["hands"][gid]["status"] == "blackjack":
            _bj_log(g, gid, "Blackjack ! 🃏")
    if _bj_is_blackjack(bj["dealer"]):
        return _bj_finish(g, rng)  # blackjack du croupier : la manche s'arrête là
    _bj_advance(g, from_current=0, rng=rng)


def _bj_advance(g: dict, from_current: int = 0, rng: random.Random = random):
    """Donne la main au prochain joueur qui joue encore ; sinon le croupier joue."""
    bj = g["bj"]
    for i in range(from_current, len(bj["seats"])):
        if bj["hands"][bj["seats"][i]]["status"] == "playing":
            bj["turn"] = i
            return
    _bj_finish(g, rng)


def _bj_current(g: dict, gid: str) -> dict:
    bj = g["bj"]
    if g["phase"] != "play" or bj["turn"] is None or bj["seats"][bj["turn"]] != gid:
        raise GameError("Ce n'est pas ton tour")
    return bj["hands"][gid]


def bj_hit(g: dict, gid: str, rng: random.Random = random):
    h = _bj_current(g, gid)
    card = _bj_draw(g, rng)
    h["cards"].append(card)
    total = bj_value(h["cards"])[0]
    _bj_log(g, gid, f"tire {card_label(card)} → {total}" + (" : sauté !" if total > 21 else ""))
    if total > 21:
        h["status"] = "bust"
    elif total == 21:
        h["status"] = "stand"
    if h["status"] != "playing":
        _bj_advance(g, g["bj"]["turn"] + 1, rng)


def bj_stand(g: dict, gid: str, rng: random.Random = random):
    h = _bj_current(g, gid)
    h["status"] = "stand"
    _bj_log(g, gid, f"reste sur {bj_value(h['cards'])[0]}")
    _bj_advance(g, g["bj"]["turn"] + 1, rng)


def bj_double(g: dict, gid: str, rng: random.Random = random):
    h = _bj_current(g, gid)
    bj = g["bj"]
    if len(h["cards"]) != 2:
        raise GameError("On ne double qu'avec ses 2 premières cartes")
    if not bj_drinks(g):
        if bj["chips"][gid] < h["bet"]:
            raise GameError("Pas assez de jetons pour doubler")
        bj["chips"][gid] -= h["bet"]
    h["bet"] *= 2
    h["doubled"] = True
    card = _bj_draw(g, rng)
    h["cards"].append(card)
    total = bj_value(h["cards"])[0]
    h["status"] = "bust" if total > 21 else "stand"
    _bj_log(g, gid, f"double la mise, tire {card_label(card)} → {total}" + (" : sauté !" if total > 21 else ""))
    _bj_advance(g, bj["turn"] + 1, rng)


def bj_force_stand(g: dict, rng: random.Random = random):
    """L'animateur passe le tour d'un joueur qui traîne (il reste sur sa main)."""
    bj = g["bj"]
    if g["phase"] != "play" or bj["turn"] is None:
        raise GameError("Personne ne joue")
    bj_stand(g, bj["seats"][bj["turn"]], rng)


def _bj_finish(g: dict, rng):
    """Le croupier tire jusqu'à 17 (il reste sur 17 souple), puis on règle les mises."""
    bj = g["bj"]
    bj["turn"] = None
    bj["finished_at"] = time.time()
    hands = [bj["hands"][gid] for gid in bj["seats"]]
    dealer_bj = _bj_is_blackjack(bj["dealer"])
    _bj_log(g, None, f"retourne {card_label(bj['dealer'][1])} → {bj_value(bj['dealer'])[0]}" + (" : Blackjack !" if dealer_bj else ""))
    if not dealer_bj and any(h["status"] in ("stand", "playing") for h in hands):
        while bj_value(bj["dealer"])[0] < 17:
            card = _bj_draw(g, rng)
            bj["dealer"].append(card)
            _bj_log(g, None, f"tire {card_label(card)} → {bj_value(bj['dealer'])[0]}")
    dealer = bj_value(bj["dealer"])[0]
    if dealer > 21:
        _bj_log(g, None, "saute ! Tout le monde encore en jeu gagne")
    for gid in bj["seats"]:
        h = bj["hands"][gid]
        mine = bj_value(h["cards"])[0]
        if h["status"] == "bust":
            result = "lose"
        elif h["status"] == "blackjack":
            result = "push" if dealer_bj else "blackjack"
        elif dealer_bj or (dealer <= 21 and dealer > mine):
            result = "lose"
        elif dealer > 21 or mine > dealer:
            result = "win"
        else:
            result = "push"
        h["result"] = result
        bet = h["bet"]
        if bj_drinks(g):
            # Gorgées : perdu = tu bois ta mise ; gagné = tu distribues le double ; blackjack = le triple.
            h["delta"] = 0
            h["sips"] = {"lose": -bet, "win": 2 * bet, "blackjack": 3 * bet, "push": 0}[result]
            add_sips(g, gid, drink=max(0, -h["sips"]), give=max(0, h["sips"]))
        else:
            # Jetons : la mise a déjà été retirée ; gain 1:1, blackjack 3:2, égalité = mise rendue.
            back = {"win": 2 * bet, "blackjack": bet + (3 * bet + 1) // 2, "push": bet, "lose": 0}[result]
            bj["chips"][gid] += back
            h["delta"] = back - bet
            h["sips"] = 0
    g["phase"] = "results"


def _bj_card_view(cards: list[str]) -> list[str]:
    return list(cards)


def bj_view(g: dict, gid: str) -> dict:
    bj = g["bj"]
    hidden = g["phase"] == "play"  # la 2e carte du croupier reste cachée pendant que les joueurs jouent
    dealer = bj["dealer"][:1] + (["??"] if hidden and len(bj["dealer"]) > 1 else bj["dealer"][1:])
    seats = []
    for p in g["players"]:
        h = bj["hands"].get(p["id"])
        seats.append({
            "pid": p["pid"], "name": p["name"], "chips": bj["chips"].get(p["id"], BJ_START_CHIPS),
            "rebuys": bj["rebuys"].get(p["id"], 0),
            "hand": None if not h else {**{k: h.get(k) for k in ("cards", "bet", "status", "doubled", "result", "delta", "sips")},
                                        "total": bj_value(h["cards"])[0] if h["cards"] else 0},
        })
    turn = bj["seats"][bj["turn"]] if bj["turn"] is not None and bj["turn"] < len(bj["seats"]) else None
    lo, hi = (1, bj_drinks(g)) if bj_drinks(g) else BJ_BETS[g["type"]]
    return {
        "drinks": bj_drinks(g),
        # Secondes depuis la fin de la main : l'animation de résultat ne se joue que si elle est toute fraîche.
        "finished_age": time.time() - bj["finished_at"] if bj.get("finished_at") else None,
        "dealer": dealer, "dealer_total": None if hidden else (bj_value(bj["dealer"])[0] if bj["dealer"] else None),
        "dealer_up": bj_value(bj["dealer"][:1])[0] if bj["dealer"] else None,
        "seats": seats, "turn": _pid(g, turn), "my_turn": bool(gid) and turn == gid, "log": bj.get("log", []),
        "min_bet": lo, "max_bet": hi, "start_chips": BJ_START_CHIPS,
    }


# --- Casino : roulette européenne (un seul zéro) ---

WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14,
               31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
CASINO_START_CHIPS = 100
# Paris : (gain en jetons pour 1 misé, multiplicateur de gorgées à distribuer en mode alcool).
CASINO_PAYOUTS = {"n": (35, 10), "dozen": (2, 3), "color": (1, 2), "parity": (1, 2), "half": (1, 2)}
CASINO_TARGETS = {"color": ("red", "black"), "parity": ("even", "odd"), "half": ("low", "high"), "dozen": ("1", "2", "3")}


def casino_sips(g: dict) -> int:
    """Mode alcool : mise totale maximale par tour, en gorgées ; 0 = mode jetons."""
    return g["options"].get("sips", 0)


def casino_wins(kind: str, target: str, n: int) -> bool:
    if kind == "n":
        return int(target) == n
    if n == 0:
        return False  # le zéro fait perdre toutes les mises extérieures
    return {
        "color": lambda: (n in RED) == (target == "red"),
        "parity": lambda: (n % 2 == 0) == (target == "even"),
        "half": lambda: (n <= 18) == (target == "low"),
        "dozen": lambda: (n - 1) // 12 + 1 == int(target),
    }[kind]()


def casino_open(g: dict):
    if not g["players"]:
        raise GameError("Il faut au moins 1 joueur")
    c = g["casino"]
    for p in g["players"]:
        c["chips"].setdefault(p["id"], CASINO_START_CHIPS)
    c.update(bets={}, results={}, stack={}, ready=[])
    g["phase"] = "bet"
    g["round"] += 1


def casino_bet(g: dict, gid: str, target: str, amount: int):
    """Ajoute une mise sur une case du tapis (« n:17 », « color:red », « dozen:2 »…)."""
    if g["phase"] != "bet" or not player(g, gid):
        raise GameError("Rien ne va plus : les mises sont fermées")
    kind, _, value = target.partition(":")
    if kind == "n":
        if not value.isdigit() or not 0 <= int(value) <= 36:
            raise GameError("Case inconnue")
        value = str(int(value))
    elif value not in CASINO_TARGETS.get(kind, ()):
        raise GameError("Case inconnue")
    c = g["casino"]
    c["chips"].setdefault(gid, CASINO_START_CHIPS)
    bets = c["bets"].setdefault(gid, [])
    total = sum(b["amount"] for b in bets) + amount
    limit = casino_sips(g) or c["chips"][gid]
    if amount < 1 or total > limit:
        raise GameError(f"Tu peux miser {limit} {'gorgée' if casino_sips(g) else 'jeton'}{'s' if limit > 1 else ''} au total par tour"
                        if limit else "Plus de jetons : recharge-toi")
    for b in bets:
        if b["kind"] == kind and b["target"] == value:
            b["amount"] += amount
            break
    else:
        bets.append({"kind": kind, "target": value, "amount": amount})
    # Historique des mises posées (pour « Annuler »), et on n'est plus « prêt » après un changement.
    c.setdefault("stack", {}).setdefault(gid, []).append([kind, value, amount])
    _casino_unready(c, gid)


def _casino_unready(c: dict, gid: str):
    if gid in c.setdefault("ready", []):
        c["ready"].remove(gid)


def casino_undo(g: dict, gid: str):
    """Annule la dernière mise posée."""
    c = g["casino"]
    if g["phase"] != "bet":
        raise GameError("Rien ne va plus : les mises sont fermées")
    stack = c.setdefault("stack", {}).get(gid) or []
    if not stack:
        raise GameError("Aucune mise à annuler")
    kind, value, amount = stack.pop()
    bets = c["bets"].get(gid, [])
    for b in bets:
        if b["kind"] == kind and b["target"] == value:
            b["amount"] -= amount
            if b["amount"] <= 0:
                bets.remove(b)
            break
    _casino_unready(c, gid)


def casino_clear(g: dict, gid: str):
    if g["phase"] != "bet":
        raise GameError("Rien ne va plus : les mises sont fermées")
    c = g["casino"]
    c["bets"].pop(gid, None)
    c.setdefault("stack", {}).pop(gid, None)
    _casino_unready(c, gid)


def casino_ready(g: dict, gid: str, rng: random.Random = random):
    """« Je suis prêt » (ou plus prêt) ; quand toute la table est prête, la bille part toute seule."""
    c = g["casino"]
    if g["phase"] != "bet" or not player(g, gid):
        raise GameError("Rien ne va plus : les mises sont fermées")
    ready = c.setdefault("ready", [])
    if gid in ready:
        ready.remove(gid)
        return
    ready.append(gid)
    seated = [p["id"] for p in g["players"] if not p.get("pending")]
    if all(x in ready for x in seated) and any(c["bets"].values()):
        casino_spin(g, rng)


def casino_rebuy(g: dict, gid: str):
    c = g["casino"]
    if casino_sips(g) or c["chips"].get(gid, 0) >= 1 or c["bets"].get(gid):
        raise GameError("Tu as encore des jetons")
    c["chips"][gid] = CASINO_START_CHIPS
    c["rebuys"][gid] = c["rebuys"].get(gid, 0) + 1


def casino_spin(g: dict, rng: random.Random = random):
    """« Rien ne va plus » : la bille tombe sur un numéro, on paie les mises."""
    c = g["casino"]
    if g["phase"] != "bet":
        raise GameError("Ouvre d'abord les mises")
    if not any(c["bets"].values()):
        raise GameError("Personne n'a misé")
    n = rng.randrange(37)
    c["spin"] = {"id": secrets.token_hex(4), "number": n, "at": time.time(), "wheel": round(rng.uniform(0, 360), 1)}
    c["history"] = (c["history"] + [n])[-30:]
    drinks = casino_sips(g)
    c["results"] = {}
    for gid, bets in c["bets"].items():
        if not bets or not player(g, gid):
            continue
        staked = sum(b["amount"] for b in bets)
        won_back = drink = give = 0
        jackpot = False
        for b in bets:
            chips_mult, sips_mult = CASINO_PAYOUTS[b["kind"]]
            if casino_wins(b["kind"], b["target"], n):
                won_back += b["amount"] * (chips_mult + 1)
                give += b["amount"] * sips_mult
                jackpot = jackpot or b["kind"] == "n"
            else:
                drink += b["amount"]
        if drinks:
            # Le zéro : la maison gagne, chaque joueur boit 1 gorgée de plus (sauf ceux qui avaient misé sur le 0).
            if n == 0 and not any(b["kind"] == "n" and b["target"] == "0" for b in bets):
                drink += 1
            add_sips(g, gid, drink=drink, give=give)
            c["results"][gid] = {"staked": staked, "drink": drink, "give": give, "net": 0, "jackpot": jackpot}
        else:
            c["chips"][gid] += won_back - staked
            c["results"][gid] = {"staked": staked, "drink": 0, "give": 0, "net": won_back - staked, "jackpot": jackpot}
    g["phase"] = "results"


def casino_view(g: dict, gid: str) -> dict:
    c = g["casino"]
    board: dict[str, int] = {}
    table = []
    for p in g["players"]:
        bets = c["bets"].get(p["id"], [])
        for b in bets:
            key = f"{b['kind']}:{b['target']}"
            board[key] = board.get(key, 0) + b["amount"]
        table.append({"pid": p["pid"], "name": p["name"], "chips": c["chips"].get(p["id"], CASINO_START_CHIPS),
                      "rebuys": c["rebuys"].get(p["id"], 0), "staked": sum(b["amount"] for b in bets),
                      "bets": bets, "result": c["results"].get(p["id"]), "ready": p["id"] in c.get("ready", []),
                      "can_undo": bool(c.get("stack", {}).get(p["id"]))})
    spin = c["spin"]
    me = next((t for t in table if player(g, gid) and t["pid"] == player(g, gid)["pid"]), None)
    return {
        "drinks": casino_sips(g), "board": board, "table": table, "me": me, "history": list(reversed(c["history"])),
        "spin": {**spin, "age": time.time() - spin["at"]} if spin else None, "start_chips": CASINO_START_CHIPS,
    }


# --- Le Divan ---

def divan_set_cats(g: dict, cats: list[str]):
    cats = ["couple"] if "couple" in cats else [c for c in DIVAN_CARDS if c in cats]
    if not cats:
        raise GameError("Choisis au moins une catégorie")
    g["divan"]["cats"] = cats


def _divan_current(g: dict) -> dict | None:
    return g["players"][g["divan"]["turn"] % len(g["players"])] if g["players"] else None


def _divan_draw(g: dict, rng):
    d = g["divan"]
    pool = [(c, q) for c in d["cats"] for q in DIVAN_CARDS[c]]
    used = set(d["used"])
    left = [x for x in pool if x[1] not in used] or pool
    cat, text = rng.choice(left)
    d["used"] = (d["used"] + [text])[-(len(pool) - 1):]
    d["n"] += 1
    d.update(card={"cat": cat, "text": text, "id": d["n"]}, hearts=[])
    g["round"] = d["n"]


def _divan_can_lead(g: dict, gid: str):
    cur = _divan_current(g)
    if g["phase"] != "card" or not (is_lead(g, gid) or (cur and cur["id"] == gid)):
        raise GameError("C'est à la personne sur le divan (ou à l'animateur) de décider")


DIVAN_BACK = 20  # retours en arrière possibles


def _divan_save(g: dict, gid: str):
    """Mémorise l'état avant « Au suivant » ou le joker, pour pouvoir revenir en arrière."""
    d = g["divan"]
    back = d.setdefault("back", [])
    back.append({"turn": d["turn"], "card": d["card"], "joker": d["joker"], "hearts": list(d["hearts"]),
                 "n": d["n"], "used": len(d["used"]), "by": gid})
    del back[:-DIVAN_BACK]


def divan_back(g: dict, gid: str):
    """Retour en arrière : annule le dernier « Au suivant » ou joker (la carte écartée retourne dans le paquet)."""
    d = g["divan"]
    back = d.get("back") or []
    if g["phase"] != "card" or not back:
        raise GameError("Rien à annuler")
    if back[-1]["by"] != gid:
        _divan_can_lead(g, gid)
    s = back.pop()
    if len(d["used"]) > s["used"]:
        del d["used"][s["used"]:]
    d.update(turn=s["turn"] % len(g["players"]), card=s["card"], joker=s["joker"], hearts=s["hearts"], n=s["n"])
    g["round"] = s["n"]


def divan_next(g: dict, gid: str, rng: random.Random = random):
    """Au suivant : le divan passe au joueur suivant, nouvelle carte."""
    _divan_can_lead(g, gid)
    _divan_save(g, gid)
    g["divan"]["turn"] = (g["divan"]["turn"] + 1) % len(g["players"])
    g["divan"]["joker"] = False
    _divan_draw(g, rng)


def divan_joker(g: dict, gid: str, rng: random.Random = random):
    """Joker : une autre carte pour la même personne (une fois par tour)."""
    _divan_can_lead(g, gid)
    if g["divan"]["joker"]:
        raise GameError("Le joker de ce tour a déjà été utilisé")
    _divan_save(g, gid)
    g["divan"]["joker"] = True
    _divan_draw(g, rng)


def divan_heart(g: dict, gid: str):
    """Un soutien ❤️ pour la personne sur le divan (une fois par carte)."""
    d = g["divan"]
    cur = _divan_current(g)
    if g["phase"] != "card" or not player(g, gid) or (cur and cur["id"] == gid):
        raise GameError("Pas de soutien possible")
    if gid not in d["hearts"]:
        d["hearts"].append(gid)


def divan_view(g: dict, gid: str) -> dict:
    d = g["divan"]
    cur = _divan_current(g)
    return {"cats": d["cats"], "labels": DIVAN_LABELS, "card": d["card"], "hearts": len(d["hearts"]),
            "hearted": gid in d["hearts"], "joker": d["joker"],
            "current": {"pid": cur["pid"], "name": cur["name"]} if cur else None,
            "my_turn": bool(cur) and cur["id"] == gid, "can_lead": bool(gid) and (is_lead(g, gid) or (bool(cur) and cur["id"] == gid)),
            "can_back": bool(gid) and bool(d.get("back")) and (is_lead(g, gid) or (bool(cur) and cur["id"] == gid) or d["back"][-1]["by"] == gid)}


# --- Tu me connais ? ---
# Deux joueurs sont tirés : l'un (le sujet) écrit en secret sa réponse à une question sur lui-même
# (impossible de mentir ensuite), l'autre (le devin) devine à voix haute. L'animateur révèle la réponse écrite
# puis attribue les points : juste (1), presque (½) ou faux (0).

TMC_VERDICTS = {0: 0.0, 1: 0.5, 2: 1.0}  # body.amount → points


def _tmc_pick(g: dict, rng):
    """Duo suivant : d'abord les duos (dans ce sens) les moins joués, en évitant le duo précédent."""
    t, ids = g["tmc"], [p["id"] for p in g["players"]]
    pairs = [(a, b) for a in ids for b in ids if a != b]
    last = set(t["last"])

    def cost(ab):
        return t["pairs"].get(f"{ab[0]}>{ab[1]}", {}).get("asked", 0) * 10 + len(last & set(ab))
    best = min(cost(ab) for ab in pairs)
    return rng.choice([ab for ab in pairs if cost(ab) == best])


def _tmc_question(g: dict, rng) -> str:
    t = g["tmc"]
    left = [q for q in TMC_QUESTIONS if q not in t["used"]] or TMC_QUESTIONS
    q = rng.choice(left)
    t["used"] = (t["used"] + [q])[-(len(TMC_QUESTIONS) - 1):]
    return q


def tmc_next(g: dict, rng: random.Random = random):
    """Nouveau duo et nouvelle question."""
    if g["phase"] == "end" or len(g["players"]) < 2:
        raise GameError("Il faut au moins 2 joueurs")
    t = g["tmc"]
    guesser, subject = _tmc_pick(g, rng)
    for i in (guesser, subject):
        t["names"][i] = player(g, i)["name"]
    t["duo"] = {"guesser": guesser, "subject": subject, "q": _tmc_question(g, rng), "answers": {}, "verdict": None}
    t["last"] = [guesser, subject]
    g["phase"] = "answer"
    g["round"] += 1


def tmc_change_question(g: dict, rng: random.Random = random):
    """Même duo, autre question (tant que personne n'a répondu… ou si la question ne plaît pas)."""
    d = g["tmc"]["duo"]
    if g["phase"] != "answer" or not d:
        raise GameError("Pas maintenant")
    d.update(q=_tmc_question(g, rng), answers={})


def tmc_answer(g: dict, gid: str, text: str):
    """Seule la personne interrogée écrit sa réponse (en secret) ; le devin, lui, parle à voix haute."""
    d = g["tmc"]["duo"]
    text = " ".join((text or "").split())[:80]
    proxy = is_lead(g, gid) and is_manual(g, d["subject"]) if d else False  # téléphone de l'animateur prêté
    if g["phase"] != "answer" or not d or (gid != d["subject"] and not proxy):
        raise GameError("C'est à la personne interrogée d'écrire sa réponse")
    if not text:
        raise GameError("Écris une réponse")
    d["answers"][d["subject"]] = text  # au nom du sujet, même saisi sur le téléphone de l'animateur
    g["phase"] = "guess"


def tmc_reveal(g: dict):
    """L'animateur révèle la réponse écrite, une fois que le devin a parlé."""
    if g["phase"] != "guess":
        raise GameError("Pas maintenant")
    g["phase"] = "judge"


def tmc_judge(g: dict, gid: str, amount: int):
    """L'animateur attribue les points au devin."""
    t = g["tmc"]
    d = t["duo"]
    if g["phase"] != "judge" or not d or not is_lead(g, gid):
        raise GameError("C'est à l'animateur d'attribuer les points")
    if amount not in TMC_VERDICTS:
        raise GameError("Verdict inconnu")
    pts = TMC_VERDICTS[amount]
    d["verdict"] = pts
    pair = t["pairs"].setdefault(f"{d['guesser']}>{d['subject']}", {"asked": 0, "pts": 0.0})
    pair["asked"] += 1
    pair["pts"] += pts
    t["scores"][d["guesser"]] = t["scores"].get(d["guesser"], 0.0) + pts
    g["phase"] = "scored"


def tmc_finish(g: dict):
    if g["phase"] in ("lobby", "end"):
        raise GameError("Pas maintenant")
    g["phase"] = "end"


def tmc_left(g: dict, gid: str, rng=random):
    """Un joueur du duo s'en va en pleine question : on passe au duo suivant."""
    d = g["tmc"]["duo"]
    if d and gid in (d["guesser"], d["subject"]) and g["phase"] in ("answer", "guess", "judge"):
        if len(g["players"]) >= 2:
            tmc_next(g, rng)
        else:
            g["phase"], g["tmc"]["duo"] = "end", None


def _tmc_pct(pair: dict) -> int:
    return round(100 * pair["pts"] / pair["asked"]) if pair.get("asked") else 0


def tmc_view(g: dict, gid: str) -> dict:
    t = g["tmc"]
    d = t["duo"]
    pid = lambda i: _pid(g, i)
    name = lambda i: (player(g, i) or {}).get("name") or t["names"].get(i, "?")
    who = lambda i: {"pid": pid(i), "name": name(i)}
    duo = None
    if d:
        reveal = g["phase"] in ("judge", "scored", "end")
        duo = {"guesser": who(d["guesser"]), "subject": who(d["subject"]), "question": d["q"],
               "role": "guesser" if gid == d["guesser"] else "subject" if gid == d["subject"] else None,
               "mine": d["answers"].get(gid),  # la personne interrogée revoit sa propre réponse
               # Sujet sans téléphone : l'animateur lui prête le sien pour écrire en secret.
               "proxy": g["phase"] == "answer" and is_lead(g, gid) and is_manual(g, d["subject"]),
               "answer": d["answers"].get(d["subject"]) if reveal else None,
               "verdict": d["verdict"], "can_judge": g["phase"] == "judge" and is_lead(g, gid)}
    # Classement : points, et nombre de questions où chacun a deviné.
    asked = {}
    for k, p in t["pairs"].items():
        a = k.split(">")[0]
        asked[a] = asked.get(a, 0) + p["asked"]
    everyone = list(dict.fromkeys([p["id"] for p in g["players"]] + list(t["scores"])))
    ranking = sorted(({**who(i), "pts": t["scores"].get(i, 0.0), "asked": asked.get(i, 0)} for i in everyone),
                     key=lambda r: (-r["pts"], r["asked"], r["name"].lower()))
    pairs = [{"guesser": who(k.split(">")[0]), "subject": who(k.split(">")[1]), "asked": p["asked"], "pts": p["pts"],
              "pct": _tmc_pct(p)} for k, p in t["pairs"].items() if p["asked"]]
    # Duos d'amis : points des deux sens réunis.
    duos = {}
    for k, p in t["pairs"].items():
        a, b = k.split(">")
        key = tuple(sorted((a, b)))
        x = duos.setdefault(key, {"asked": 0, "pts": 0.0})
        x["asked"] += p["asked"]
        x["pts"] += p["pts"]
    best_duos = sorted(({"a": who(a), "b": who(b), "asked": x["asked"], "pts": x["pts"], "pct": _tmc_pct(x)}
                        for (a, b), x in duos.items() if x["asked"]), key=lambda r: (-r["pct"], -r["pts"]))
    return {"duo": duo, "ranking": ranking, "pairs": pairs, "duos": best_duos}


# --- Pyramide (jeu de cartes à boire, joueurs autour de la même table) ---
# 1. Distribution : 4 questions par joueur (rouge/noir, plus/moins, dedans/dehors, symbole), une carte chacune.
# 2. Pyramide : l'animateur retourne les cartes ; on peut donner les gorgées de l'étage, bluff compris ;
#    accusé de mentir, on retourne une de ses cartes 3 s. Sommet : cul sec, sans bluff.
# 3. Mémoire : chacun retrouve ses 4 valeurs dans l'ordre. 4. Bateau pour celui qui en rate le plus.

PYR_RANKS = "A23456789TJQK"
PYR_SUITS = "SHDC"
PYR_STEPS = {1: ("red", "black"), 2: ("plus", "moins"), 3: ("dedans", "dehors"), 4: tuple(PYR_SUITS)}


def pyr_size(floors: int) -> int:
    return floors * (floors + 1) // 2


def pyr_max_players(floors: int) -> int:
    return (52 - pyr_size(floors)) // 4  # un seul paquet de 52 cartes


def pyr_value(card: str) -> int:
    return "23456789TJQKA".index(card[0]) + 2  # l'As est la carte la plus forte (au-dessus du Roi)


def pyr_floor(floors: int, index: int) -> int:
    """Étage (1 = la base) de la carte n° index, dans l'ordre où on les retourne (de bas en haut, de gauche à droite)."""
    for floor in range(1, floors + 1):
        width = floors - floor + 1
        if index < width:
            return floor
        index -= width
    raise ValueError(index)


def _pyr_check(step: int, value: str, previous: list[str], card: str) -> bool:
    if value not in PYR_STEPS[step]:
        raise GameError("Réponse invalide")
    v = pyr_value(card)
    if step == 1:
        return (value == "red") == (card[1] in "HD")
    if step == 2:
        first = pyr_value(previous[0])
        return v > first if value == "plus" else v < first  # même valeur : raté
    if step == 3:
        lo, hi = sorted(pyr_value(c) for c in previous[:2])
        return lo < v < hi if value == "dedans" else (v < lo or v > hi)  # sur le poteau : raté
    return card[1] == value


def pyr_floor_sips(g: dict, floor: int) -> int:
    """Gorgées d'un étage : 1, 2, 3… ou, en mode double, 2, 4, 6…"""
    return floor * (2 if g["options"].get("double") else 1)


def pyr_step_sips(g: dict, step: int) -> int:
    """Distribution : mode hard = 1, 2, 3 puis 4 gorgées ; mode soft = 1 gorgée à chaque carte."""
    return step if g["options"].get("pmode", "hard") == "hard" else 1


def _pyr_event(P: dict) -> int:
    P["n"] += 1
    return P["n"]


def pyr_start(g: dict, rng):
    floors = g["options"].get("floors", 5)
    order = [p["id"] for p in g["players"]]
    if len(order) < 2:
        raise GameError("Il faut au moins 2 joueurs")
    if len(order) > pyr_max_players(floors):
        raise GameError(f"Trop de joueurs pour {floors} étages : {pyr_max_players(floors)} au plus avec un seul paquet")
    deck = [r + s for r in PYR_RANKS for s in PYR_SUITS]
    rng.shuffle(deck)
    g["pyr"] = {"floors": floors, "deck": deck, "order": order, "turn": 0, "step": 1, "hands": {gid: [] for gid in order},
                "pyramid": [deck.pop() for _ in range(pyr_size(floors))], "flipped": 0, "claims": [], "reveal": None,
                "peeks": [], "top": {}, "liars": [], "memory": {}, "errors": {}, "candidates": [], "boat": None,
                "spin": None, "bstate": None, "last": None, "n": 0}
    g["phase"] = "deal"
    g["round"] = 1


def _pyr_poteau(g: dict, previous: list[str], card: str) -> bool:
    """Poteau : le joueur a deux fois la même valeur. Soft : tout le monde boit 1 gorgée ; hard : lui, cul sec."""
    if not any(pyr_value(c) == pyr_value(card) for c in previous):
        return False
    if g["options"].get("poteau", "soft") == "soft":
        for x in g["pyr"]["order"]:
            add_sips(g, x, drink=1)
    return True


def pyr_answer(g: dict, actor: str, value: str):
    """Distribution : le joueur dont c'est le tour répond ; il reçoit sa carte (bonne réponse : il distribue, sinon il boit).
    Sert aussi à un joueur arrivé en cours de partie (sa distribution perso, pendant la pyramide)."""
    P = g["pyr"]
    late = P.get("late")
    if g["phase"] == "pyramid" and late:
        cur, step = late["gid"], late["step"]
    elif g["phase"] == "deal":
        if not P["order"]:  # tout le monde est parti pendant la distribution (trouvé par les bots)
            raise GameError("Plus personne à la table")
        cur, step = P["order"][P["turn"] % len(P["order"])], P["step"]
    else:
        raise GameError("La distribution est terminée")
    if actor != cur:
        raise GameError("Ce n'est pas ton tour")
    hand = P["hands"][cur]
    if value not in PYR_STEPS[step]:
        raise GameError("Réponse invalide")
    card = P["deck"].pop()
    ok = _pyr_check(step, value, hand, card)
    poteau = _pyr_poteau(g, hand, card)
    hand.append(card)
    sips = pyr_step_sips(g, step)
    add_sips(g, cur, drink=0 if ok else sips, give=sips if ok else 0)
    P["last"] = {"n": _pyr_event(P), "gid": cur, "step": step, "value": value, "card": card, "ok": ok, "sips": sips,
                 "poteau": poteau, "late": bool(late)}
    if late:
        late["step"] += 1
        if late["step"] > 4:
            P["late"] = None  # ses cartes se retournent : la pyramide reprend
            _pyr_next_late(g)
        return
    P["turn"] += 1
    if P["turn"] >= len(P["order"]):
        P["turn"] = 0
        P["step"] += 1
        g["round"] = P["step"]
        if P["step"] > 4:
            g["phase"] = "pyramid"  # les mains se retournent : plus personne ne voit ses cartes
            _pyr_next_late(g)


def _pyr_next_late(g: dict):
    """Lance la distribution perso du prochain joueur accepté en cours de partie."""
    P = g["pyr"]
    while not P.get("late") and P.get("queue"):
        gid = P["queue"].pop(0)
        if not player(g, gid):
            continue
        if len(P["deck"]) < 4:
            raise GameError("Plus assez de cartes dans le paquet")
        P["order"].append(gid)
        P["hands"][gid] = []
        P["late"] = {"gid": gid, "step": 1}
        _pyr_event(P)


def pyr_accept(g: dict, target: str):
    """L'animateur accepte un joueur arrivé en cours de partie."""
    P = g["pyr"]
    p = player(g, target)
    if not p:
        raise GameError("Joueur introuvable")
    p["pending"] = False
    if g["phase"] in ("deal", "pyramid") and target not in P["order"] and target not in P.setdefault("queue", []):
        if len(P["deck"]) - 4 * len(P["queue"]) < 4:
            raise GameError("Plus assez de cartes dans le paquet pour un joueur de plus")
        P["queue"].append(target)
        if g["phase"] == "pyramid":
            _pyr_next_late(g)
    _pyr_event(P)  # après la pyramide : il regarde, sans cartes


def pyr_refuse(g: dict, target: str):
    p = player(g, target)
    if not p or not p.get("pending"):
        raise GameError("Demande introuvable")
    g["players"].remove(p)
    _pyr_event(g["pyr"])


def pyr_flip(g: dict):
    P = g["pyr"]
    if g["phase"] != "pyramid":
        raise GameError("Pas le moment")
    if P["flipped"] >= len(P["pyramid"]):
        raise GameError("La pyramide est entièrement retournée")
    if P.get("late"):
        raise GameError("Attends la fin de la distribution du nouveau joueur")
    P["flipped"] += 1
    P.update(claims=[], reveal=None, top={})
    _pyr_event(P)


def _pyr_current(P: dict) -> tuple[str, int, bool]:
    i = P["flipped"] - 1
    return P["pyramid"][i], pyr_floor(P["floors"], i), P["flipped"] == len(P["pyramid"])


def pyr_claim(g: dict, actor: str):
    """« Je donne N gorgées » : possible pour tout le monde, qu'on ait la carte ou non (bluff permis)."""
    P = g["pyr"]
    if g["phase"] != "pyramid" or not P["flipped"]:
        raise GameError("Aucune carte retournée")
    _, floor, top = _pyr_current(P)
    if top:
        raise GameError("Au sommet, pas de bluff : annonce si tu as la carte")
    if actor not in P["order"] or any(c["gid"] == actor for c in P["claims"]):
        raise GameError("Déjà annoncé")
    P["claims"].append({"id": _pyr_event(P), "gid": actor, "sips": pyr_floor_sips(g, floor), "status": "pending"})


def pyr_judge(g: dict, claim_id: str, liar: bool):
    """L'animateur : gorgées bues, ou « menteur ! » (l'accusé doit alors retourner une carte)."""
    P = g["pyr"]
    c = next((c for c in P["claims"] if str(c["id"]) == str(claim_id)), None)
    if not c or c["status"] != "pending":
        raise GameError("Annonce introuvable")
    c["status"] = "accused" if liar else "drunk"
    _pyr_event(P)


def pyr_reveal(g: dict, actor: str, slot: int):
    """L'accusé retourne une de ses cartes : visible 3 s par tous, puis cachée à nouveau."""
    P = g["pyr"]
    c = next((c for c in P["claims"] if c["gid"] == actor and c["status"] == "accused"), None)
    if not c:
        raise GameError("Personne ne t'accuse")
    if not 0 <= slot < len(P["hands"][actor]):
        raise GameError("Choisis une de tes cartes")
    card = P["hands"][actor][slot]
    truth = pyr_value(card) == pyr_value(_pyr_current(P)[0])
    c["status"] = "truth" if truth else "lie"
    P["reveal"] = {"n": _pyr_event(P), "gid": actor, "slot": slot, "card": card, "truth": truth, "at": time.time()}


def pyr_peek(g: dict, actor: str, slots: list[int]):
    """Demande à l'animateur de revoir 1 à 4 de ses cartes (2 gorgées de pénalité par carte)."""
    P = g["pyr"]
    if g["phase"] != "pyramid" or actor not in P["order"]:
        raise GameError("Pas le moment")
    slots = sorted({int(x) for x in slots if 0 <= int(x) < 4})
    if not slots:
        raise GameError("Choisis au moins une carte")
    if any(r["gid"] == actor and r["status"] == "pending" for r in P["peeks"]):
        raise GameError("Une demande est déjà en attente")
    P["peeks"].append({"id": _pyr_event(P), "gid": actor, "slots": slots, "status": "pending", "at": 0})


def pyr_peek_decide(g: dict, req_id: str, ok: bool):
    P = g["pyr"]
    r = next((r for r in P["peeks"] if str(r["id"]) == str(req_id) and r["status"] == "pending"), None)
    if not r:
        raise GameError("Demande introuvable")
    r.update(status="ok" if ok else "no", at=time.time())
    if ok:
        add_sips(g, r["gid"], drink=2 * len(r["slots"]))
    _pyr_event(P)


def pyr_top(g: dict, actor: str):
    """Sommet (cul sec) : on annonce avoir la carte, sans bluff ; l'app vérifie."""
    P = g["pyr"]
    if g["phase"] != "pyramid" or not P["flipped"] or not _pyr_current(P)[2]:
        raise GameError("Ce n'est pas encore le sommet")
    if actor not in P["order"] or actor in P["top"]:
        raise GameError("Déjà annoncé")
    has = any(pyr_value(c) == pyr_value(_pyr_current(P)[0]) for c in P["hands"][actor])
    P["top"][actor] = has
    if not has and actor not in P["liars"]:
        P["liars"].append(actor)  # il tentera sa chance à la roulette du bateau
    _pyr_event(P)


def pyr_to_memory(g: dict):
    P = g["pyr"]
    if g["phase"] != "pyramid" or P["flipped"] < len(P["pyramid"]):
        raise GameError("Retourne d'abord toute la pyramide")
    g["phase"] = "memory"
    _pyr_event(P)


def pyr_memory(g: dict, actor: str, values: list[str]):
    """Test de mémoire : les 4 valeurs, dans l'ordre (gauche à droite)."""
    P = g["pyr"]
    if g["phase"] != "memory" or actor not in P["order"]:
        raise GameError("Pas le moment")
    vals = [("T" if str(v).upper() == "10" else str(v).upper()[:1]) for v in values]
    if len(vals) != 4 or any(v not in PYR_RANKS for v in vals):
        raise GameError("Donne tes 4 valeurs")
    P["memory"][actor] = vals
    _pyr_event(P)
    if all(gid in P["memory"] for gid in P["order"]):
        pyr_results(g)


def pyr_results(g: dict):
    P = g["pyr"]
    if g["phase"] != "memory":
        raise GameError("Pas le moment")
    for gid in P["order"]:
        guess = P["memory"].get(gid, [])
        P["errors"][gid] = sum(1 for i, c in enumerate(P["hands"][gid]) if i >= len(guess) or guess[i] != c[0])
    worst = max(P["errors"].values(), default=0)
    cands = [gid for gid in P["order"] if P["errors"][gid] == worst]
    P["candidates"] = cands + [gid for gid in P["liars"] if gid not in cands and gid in P["order"]]
    # Sans bateau, la partie s'arrête sur les résultats du test de mémoire.
    g["phase"] = "memres" if g["options"].get("boat", True) else "end"
    _pyr_event(P)


def pyr_pick_boat(g: dict, rng):
    """Qui fait le bateau ? Le seul candidat, sinon la roulette tranche."""
    P = g["pyr"]
    if g["phase"] != "memres" or not P["candidates"]:
        raise GameError("Pas le moment")
    cands = P["candidates"]
    i = rng.randrange(len(cands))
    P["boat"] = cands[i]
    P["spin"] = None if len(cands) == 1 else {"id": secrets.token_hex(4), "names": [player(g, x)["name"] for x in cands],
                                               "index": i, "at": time.time(), "jitter": round(rng.uniform(-0.35, 0.35), 3)}
    g["phase"] = "boatpick"
    _pyr_event(P)


def pyr_boat_start(g: dict, rng: random.Random = random):
    P = g["pyr"]
    if g["phase"] != "boatpick":
        raise GameError("Pas le moment")
    # Le bateau repart avec un paquet complet, bien mélangé.
    P["deck"] = [r + s for r in PYR_RANKS for s in PYR_SUITS]
    rng.shuffle(P["deck"])
    P["bstate"] = {"step": 1, "cards": [], "sips": 0, "last": None, "result": None, "tries": 1}
    g["phase"] = "boat"
    _pyr_event(P)


def pyr_boat_answer(g: dict, actor: str, value: str):
    """Le bateau : les 4 questions d'affilée ; une erreur = 1 gorgée et retour au début."""
    P = g["pyr"]
    b = P["bstate"]
    if g["phase"] != "boat" or actor != P["boat"]:
        raise GameError("Ce n'est pas à toi")
    if value not in PYR_STEPS[b["step"]]:
        raise GameError("Réponse invalide")
    card = P["deck"].pop()
    ok = _pyr_check(b["step"], value, b["cards"], card)
    poteau = _pyr_poteau(g, b["cards"], card)
    b["last"] = {"n": _pyr_event(P), "step": b["step"], "value": value, "card": card, "ok": ok, "poteau": poteau}
    if ok:
        b["cards"].append(card)
        b["step"] += 1
        if b["step"] > 4:
            b["result"] = "won"
            g["phase"] = "end"
            return
    else:
        b["sips"] += 1
        add_sips(g, actor, drink=1)
        b["cards"], b["step"] = [], 1
        b["tries"] += 1
    if not P["deck"]:
        b["result"] = "deck"  # paquet terminé : le bateau s'arrête là
        g["phase"] = "end"


def pyr_leave(g: dict, gid: str):
    P = g.get("pyr")
    if not P:
        return
    if gid in P.get("queue", []):
        P["queue"].remove(gid)
    if P.get("late") and P["late"]["gid"] == gid:
        P["late"] = None
    if gid == P.get("boat") and g["phase"] in ("boatpick", "boat"):
        g["phase"] = "end"  # le joueur du bateau est parti : fin de partie
        if P.get("bstate"):
            P["bstate"]["result"] = "left"
    if gid not in P["order"]:
        _pyr_next_late(g) if g["phase"] == "pyramid" else None
        return
    i = P["order"].index(gid)
    P["order"].remove(gid)
    if g["phase"] == "deal":
        if i < P["turn"]:
            P["turn"] -= 1
        if P["turn"] >= len(P["order"]):
            P["turn"], P["step"] = 0, P["step"] + 1
            if P["step"] > 4:
                g["phase"] = "pyramid"
    P["candidates"] = [c for c in P["candidates"] if c != gid]
    P["claims"] = [c for c in P["claims"] if c["gid"] != gid]
    if g["phase"] == "pyramid":
        _pyr_next_late(g)
    if g["phase"] in ("memory",) and P["order"] and all(x in P["memory"] for x in P["order"]):
        pyr_results(g)


def pyr_view(g: dict, gid: str) -> dict:
    P = g.get("pyr") or {}
    if not P:
        floors = g["options"].get("floors", 5)
        return {"floors": floors, "size": pyr_size(floors), "max_players": pyr_max_players(floors),
                "hard": g["options"].get("pmode", "hard") == "hard", "boat_on": g["options"].get("boat", True),
                "double": bool(g["options"].get("double")), "poteau_hard": g["options"].get("poteau", "soft") == "hard"}
    now = time.time()
    name = lambda x: (player(g, x) or {}).get("name", "?")
    pid = lambda x: (player(g, x) or {}).get("pid")
    hidden = g["phase"] not in ("deal", "memres", "boatpick", "boat", "end")
    reveal = P["reveal"]
    late = P.get("late")
    seats = []
    for x in P["order"]:
        hand = P["hands"][x]
        # Distribution perso d'un nouveau venu : ses cartes restent visibles de tous jusqu'à la 4e.
        cards = list(hand) if not hidden or (late and late["gid"] == x) else ["??"] * len(hand)
        if hidden and reveal and reveal["gid"] == x and now - reveal["at"] < 3:
            cards[reveal["slot"]] = hand[reveal["slot"]]  # carte retournée devant tout le monde, 3 secondes
        if hidden and x == gid:
            for r in P["peeks"]:
                if r["gid"] == x and r["status"] == "ok" and now - r["at"] < 5:
                    for sl in r["slots"]:
                        cards[sl] = hand[sl]  # coup d'œil privé, 5 secondes
        seats.append({"pid": pid(x), "name": name(x), "cards": cards, "manual": is_manual(g, x),
                      "memory": P["memory"].get(x) if not hidden and g["phase"] != "deal" else None,
                      "answered": x in P["memory"], "errors": P["errors"].get(x)})
    cur_card = top = None
    floor = 0
    if P["flipped"]:
        cur_card, floor, top = _pyr_current(P)
    last = P["last"]
    out = {
        "floors": P["floors"], "size": len(P["pyramid"]), "flipped": P["flipped"],
        "pyramid": [c if i < P["flipped"] else "??" for i, c in enumerate(P["pyramid"])],
        "current": cur_card, "floor": floor, "is_top": bool(top), "deck_left": len(P["deck"]),
        "seats": seats, "turn": pid(P["order"][P["turn"]]) if g["phase"] == "deal" and P["order"] else None,
        "step": P["step"], "event": P["n"], "step_sips": pyr_step_sips(g, min(P["step"], 4)),
        "floor_sips": pyr_floor_sips(g, floor) if floor else 0, "double": bool(g["options"].get("double")),
        "poteau_hard": g["options"].get("poteau", "soft") == "hard",
        "hard": g["options"].get("pmode", "hard") == "hard", "boat_on": g["options"].get("boat", True),
        "last": {**last, "pid": pid(last["gid"]), "name": name(last["gid"]), "gid": None} if last else None,
        "claims": [{"id": c["id"], "pid": pid(c["gid"]), "name": name(c["gid"]), "sips": c["sips"], "status": c["status"],
                    "mine": c["gid"] == gid} for c in P["claims"]],
        "reveal": {"n": reveal["n"], "pid": pid(reveal["gid"]), "name": name(reveal["gid"]), "slot": reveal["slot"],
                   "card": reveal["card"] if now - reveal["at"] < 3 else None, "truth": reveal["truth"],
                   "age": now - reveal["at"]} if reveal else None,
        "peeks": [{"id": r["id"], "pid": pid(r["gid"]), "name": name(r["gid"]), "count": len(r["slots"]),
                   "status": r["status"], "mine": r["gid"] == gid, "age": now - r["at"] if r["at"] else None}
                  for r in P["peeks"] if r["status"] == "pending" or now - (r["at"] or now) < 8],
        "top_me": P["top"].get(gid), "top_done": [name(x) for x in P["top"]],
        "liars": [name(x) for x in P["liars"]],
        "memory_done": sum(1 for x in P["order"] if x in P["memory"]),
        "candidates": [{"pid": pid(x), "name": name(x), "errors": P["errors"].get(x), "liar": x in P["liars"]} for x in P["candidates"]],
        "boat": {"pid": pid(P["boat"]), "name": name(P["boat"])} if P["boat"] else None,
        "spin": {**P["spin"], "age": now - P["spin"]["at"]} if P["spin"] else None,
        "bstate": P["bstate"],
        "me": {"seat": next((i for i, x in enumerate(P["order"]) if x == gid), None), "boat": gid == P["boat"],
               "pending": bool((player(g, gid) or {}).get("pending"))},
        "pending": [{"pid": p["pid"], "name": p["name"]} for p in g["players"] if p.get("pending")],
        "late": {"pid": pid(late["gid"]), "name": name(late["gid"]), "step": late["step"],
                 "step_sips": pyr_step_sips(g, late["step"])} if late else None,
        "queue": [name(x) for x in P.get("queue", [])],
    }
    return out


# --- Biskit Royal : le Roi des cartes (chaque carte, rouge ou noire, a son effet) + les dés du Biskit ---
# La table tourne vers la gauche : le voisin de gauche est le joueur suivant, celui de droite le précédent.

def _bk_mult(g: dict) -> int:
    return max(1, g["options"].get("sips", 1) or 1)


def bk_start(g: dict, rng):
    order = [p["id"] for p in g["players"] if not p.get("pending")]
    if len(order) < 2:
        raise GameError("Il faut au moins 2 joueurs")
    deck = [r + s for r in PYR_RANKS for s in PYR_SUITS]
    rng.shuffle(deck)
    g["bk"] = {"deck": deck, "order": order, "turn": 0, "card": None, "key": None, "drawer": None, "drawn": 0,
               "kings": 0, "biskit": rng.choice(order), "mates": [], "qmaster": None, "thumb": None, "rules": [],
               "dice": None, "reflex": None, "duel": None, "await": None, "outcomes": [], "final": None, "n": 0}
    g["phase"] = "play"
    g["round"] = 0


def _bk_side(B: dict, gid: str, step: int) -> str:
    o = B["order"]
    return o[(o.index(gid) + step) % len(o)]


def _bk_out(g: dict, text: str, drink: dict | None = None, give: dict | None = None, tone: str = "", head: str = ""):
    """Un effet de la carte, affiché sur tous les écrans (et compté dans les gorgées).
    tone : drink (boit) | give (distribue) | all (tout le monde) | info ; head : le titre court en très gros."""
    B = g["bk"]
    drink = dict(drink or {})
    # Potes de boisson : quand l'un boit, l'autre boit autant.
    extra = []
    for x, n in list(drink.items()):
        for pair in B.get("mates", []):
            if x in pair:
                other = pair[1] if pair[0] == x else pair[0]
                if other not in drink:
                    drink[other] = n
                    extra.append(f"🤝 {_bk_name(g, other)} boit aussi (pote de boisson)")
    for x, n in drink.items():
        add_sips(g, x, drink=n)
    for x, n in (give or {}).items():
        add_sips(g, x, give=n)
    if not head and drink:
        first = next(iter(drink))
        head = f"{_bk_name(g, first)} boit {drink[first]}"
    if not head and give:
        first = next(iter(give))
        head = f"{_bk_name(g, first)} distribue {give[first]}"
    B["outcomes"].append({"text": text, "head": head or text, "tone": tone or ("drink" if drink else "give" if give else "info"),
                          "extra": extra})


def _bk_name(g: dict, gid: str) -> str:
    return (player(g, gid) or {}).get("name", "?")


def _bk_dice(g: dict, actor: str, red: bool, rng):
    """Les dés du Biskit. Rouge : tu lances pour toi. Noir : ton voisin lance, et c'est toi la cible."""
    B, m = g["bk"], _bk_mult(g)
    roller = actor if red else _bk_side(B, actor, 1)
    d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
    B["dice"] = {"id": secrets.token_hex(4), "d": [d1, d2], "roller": roller, "at": time.time()}
    total, threes, n = d1 + d2, [d1, d2].count(3), _bk_name
    if d1 == d2 == 3:
        B["biskit"] = actor
        _bk_out(g, f"Double 3 : {n(g, actor)} devient le Biskit 🍪")
    elif threes:
        _bk_out(g, f"Un 3 : le Biskit ({n(g, B['biskit'])}) boit {threes * m}", drink={B["biskit"]: threes * m})
    if red:
        if total == 7:
            left = _bk_side(B, actor, 1)
            _bk_out(g, f"Total 7 : {n(g, left)} (à gauche) boit {2 * m}", drink={left: 2 * m})
        elif total == 11:
            right = _bk_side(B, actor, -1)
            _bk_out(g, f"Total 11 : {n(g, right)} (à droite) boit {2 * m}", drink={right: 2 * m})
        elif total == 9:
            _bk_out(g, f"Total 9 : {n(g, actor)} invente une mini-règle ou choisit qui boit {2 * m}")
        if d1 == d2 != 3:
            _bk_out(g, f"Double {d1} : {n(g, actor)} distribue {d1 * m}", give={actor: d1 * m})
    else:
        if total in (7, 11):
            _bk_out(g, f"Total {total} : {n(g, actor)} boit {2 * m}", drink={actor: 2 * m})
        elif total == 9:
            _bk_out(g, f"Total 9 : {n(g, actor)} boit {m}", drink={actor: m})
        if d1 == d2 != 3:
            _bk_out(g, f"Double {d1} : {n(g, actor)} boit {d1 * m}", drink={actor: d1 * m})
    if not B["outcomes"]:
        _bk_out(g, "Rien ne se passe… cette fois 😏", head="Rien ne se passe 😏")


BK_PAUSE = 5  # secondes pour que tout le monde lise le gage avant la carte suivante


def bk_draw(g: dict, actor: str, rng: random.Random = random):
    """Le joueur dont c'est le tour tire une carte ; son effet dépend de sa valeur et de sa couleur."""
    B = g["bk"]
    if g["phase"] != "play":
        raise GameError("La partie est terminée")
    cur = B["order"][B["turn"] % len(B["order"])]
    if actor != cur:
        raise GameError("Ce n'est pas ton tour")
    if B["await"]:
        raise GameError(f"{_bk_name(g, B['await']['gid'])} doit d'abord terminer son action")
    if B["reflex"] and not B["reflex"]["done"]:
        raise GameError("Attendez la fin du réflexe !")
    if (wait := B.get("ready_at", 0) - time.time()) > 0:
        raise GameError(f"Laisse tout le monde lire le gage ({int(wait) + 1} s)")
    if not B["deck"]:
        g["phase"] = "end"
        raise GameError("Le paquet est vide : fin de la partie")
    card = B["deck"].pop()
    B["ready_at"] = time.time() + BK_PAUSE
    rank, red = card[0], card[1] in "HD"
    m = _bk_mult(g)
    B.update(card=card, key=f"{rank}-{'red' if red else 'black'}", drawer=cur, dice=None, reflex=None, duel=None, outcomes=[])
    B["await"] = None
    B["drawn"] += 1
    g["round"] = B["drawn"]
    name = _bk_name(g, cur)
    if rank == "A":
        starter = cur if red else _bk_side(B, cur, 1)
        _bk_out(g, f"Tout le monde boit en cascade : {_bk_name(g, starter)} commence" + ("" if red else f", {name} s'arrête en dernier"),
                tone="all", head="Cascade : tout le monde boit")
    elif rank == "5":
        _bk_out(g, f"{name} dit « Je n'ai jamais… » : ceux qui l'ont fait boivent" if red
                else f"Les autres posent un « Je n'ai jamais… » à {name} : s'il l'a fait, il boit", tone="info",
                head=f"{name} : Je n'ai jamais" if red else f"Je n'ai jamais… contre {name}")
    elif rank == "6":
        _bk_out(g, "Toutes les filles de la table boivent" if red else "Tous les garçons de la table boivent", tone="all",
                head="Les filles boivent 👭" if red else "Les gars boivent 👬")
    elif rank == "9":
        _bk_out(g, f"{name} choisit un thème, chacun cite un mot : le premier qui sèche boit" if red
                else f"{name} dit un mot, chacun trouve une rime : le premier qui sèche boit", tone="info",
                head="Catégories" if red else "Rimes")
    if rank in "23":
        k = int(rank) * m
        _bk_out(g, f"{_bk_name(g, cur)} {'distribue' if red else 'boit'} {k}", **({"give": {cur: k}} if red else {"drink": {cur: k}}))
    elif rank == "4":
        # Les dés attendent leur lanceur : il secoue son téléphone (ou touche « Lancer »). Rouge : le tireur ; noir : son voisin.
        B["await"] = {"kind": "dice", "gid": cur if red else _bk_side(B, cur, 1), "for": cur, "red": red}
    elif rank == "7":
        B["reflex"] = {"id": secrets.token_hex(4), "kind": "paradis" if red else "nez", "at": time.time(), "taps": {}, "done": False, "losers": []}
    elif rank == "8":
        if red:
            B["await"] = {"kind": "mate", "gid": cur}
        else:
            mate = _bk_side(B, cur, -1)
            B["mates"] = [[cur, mate]]
            _bk_out(g, f"{_bk_name(g, cur)} et {_bk_name(g, mate)} sont potes de boisson 🤝")
    elif rank == "T":
        if red:
            B["qmaster"] = cur
            _bk_out(g, f"{_bk_name(g, cur)} est le maître des questions 🤐")
        else:
            B["thumb"] = cur
            _bk_out(g, f"{_bk_name(g, cur)} est le maître du pouce 👍")
    elif rank == "J":
        if red:
            B["await"] = {"kind": "rule", "gid": cur}
        elif B["rules"]:
            B["await"] = {"kind": "unrule", "gid": cur}
        else:
            _bk_out(g, "Aucune règle à supprimer")
    elif rank == "Q":
        B["await"] = {"kind": "queen" if red else "duel", "gid": cur}
    elif rank == "K":
        B["kings"] += 1
        if B["kings"] >= 4:
            B["final"] = cur
            _bk_out(g, f"4e Roi ! {_bk_name(g, cur)} boit la coupe du Roi 👑")
            g["phase"] = "end"
        else:
            _bk_out(g, f"{_bk_name(g, cur)} verse dans la coupe du Roi ({B['kings']}/4)")
    B["turn"] = (B["order"].index(cur) + 1) % len(B["order"])
    B["n"] += 1
    if not B["deck"] and g["phase"] == "play":
        g["phase"] = "end"


def bk_roll(g: dict, actor: str, lead: bool = False, rng: random.Random = random):
    """Le lanceur jette les dés de la carte 4 (l'animateur peut lancer pour lui : participant sans téléphone)."""
    B = g["bk"]
    a = B.get("await")
    if not a or a["kind"] != "dice":
        raise GameError("Pas de dés à lancer")
    if actor != a["gid"] and not lead:
        raise GameError(f"C'est à {_bk_name(g, a['gid'])} de lancer les dés")
    B["await"] = None
    _bk_dice(g, a["for"], a["red"], rng)


def bk_complete(g: dict, actor: str, target: str = "", text: str = "", rng: random.Random = random):
    """Le tireur termine son action : choisir un joueur, écrire ou supprimer une règle."""
    B = g["bk"]
    a = B.get("await")
    if not a or a["gid"] != actor:
        raise GameError("Rien à faire pour toi")
    m, n = _bk_mult(g), _bk_name
    kind = a["kind"]
    if kind in ("mate", "queen", "duel"):
        if target not in B["order"] or target == actor:
            raise GameError("Choisis un autre joueur")
        if kind == "mate":
            B["mates"] = [[actor, target]]
            _bk_out(g, f"{n(g, actor)} et {n(g, target)} sont potes de boisson 🤝")
        elif kind == "queen":
            _bk_out(g, f"{n(g, target)} boit {2 * m} 💃", drink={target: 2 * m})
        else:
            x, y = rng.randint(1, 6), rng.randint(1, 6)
            B["duel"] = {"id": secrets.token_hex(4), "a": actor, "b": target, "da": x, "db": y, "at": time.time()}
            if x == y:
                _bk_out(g, f"Duel : égalité {x}-{y}, les deux boivent {m}", drink={actor: m, target: m})
            else:
                loser = actor if x < y else target
                _bk_out(g, f"Duel : {x} contre {y}, {n(g, loser)} boit {2 * m} 🎯", drink={loser: 2 * m})
    elif kind == "rule":
        t = " ".join(text.split())[:120]
        if not t:
            raise GameError("Écris ta règle")
        B["rules"].append({"id": secrets.token_hex(3), "text": t, "by": n(g, actor)})
        _bk_out(g, f"Nouvelle règle : « {t} »")
    elif kind == "unrule":
        r = next((r for r in B["rules"] if r["id"] == target), None)
        if not r:
            raise GameError("Choisis une règle")
        B["rules"].remove(r)
        _bk_out(g, f"Règle supprimée : « {r['text']} »")
    B["await"] = None
    B["ready_at"] = time.time() + BK_PAUSE  # le résultat du choix aussi doit être lu
    B["n"] += 1


def bk_tap(g: dict, actor: str):
    """Paradis / doigt sur le nez : chacun touche ; le dernier boit."""
    B = g["bk"]
    r = B.get("reflex")
    if not r or r["done"] or actor not in B["order"] or actor in r["taps"]:
        return
    r["taps"][actor] = time.time()
    if all(x in r["taps"] for x in B["order"]):
        _bk_close_reflex(g, [max(r["taps"], key=r["taps"].get)])


def bk_close_reflex(g: dict):
    """L'animateur clôt le réflexe : ceux qui n'ont pas touché boivent."""
    B = g["bk"]
    r = B.get("reflex")
    if not r or r["done"]:
        raise GameError("Pas de réflexe en cours")
    late = [x for x in B["order"] if x not in r["taps"]] or ([max(r["taps"], key=r["taps"].get)] if r["taps"] else [])
    _bk_close_reflex(g, late)


def _bk_close_reflex(g: dict, losers: list[str]):
    B, m = g["bk"], _bk_mult(g)
    r = B["reflex"]
    r.update(done=True, losers=losers)
    B["ready_at"] = time.time() + BK_PAUSE
    if losers:
        who = ", ".join(_bk_name(g, x) for x in losers)
        _bk_out(g, f"Trop lent : {who} boi{'vent' if len(losers) > 1 else 't'} {m}", drink={x: m for x in losers},
                head=f"{who} boi{'vent' if len(losers) > 1 else 't'} {m}")
    B["n"] += 1


def bk_leave(g: dict, gid: str):
    B = g.get("bk")
    if not B or gid not in B["order"]:
        return
    i = B["order"].index(gid)
    B["order"].remove(gid)
    if not B["order"]:
        g["phase"] = "end"
        return
    if i < B["turn"]:
        B["turn"] -= 1
    B["turn"] %= len(B["order"])
    B["mates"] = [m for m in B["mates"] if gid not in m]
    if B.get("await") and B["await"]["gid"] == gid:
        B["await"] = None
    if B["biskit"] == gid:
        B["biskit"] = B["order"][0]
    for k in ("qmaster", "thumb"):
        if B[k] == gid:
            B[k] = None
    if B.get("reflex") and not B["reflex"]["done"] and all(x in B["reflex"]["taps"] for x in B["order"]):
        _bk_close_reflex(g, [max(B["reflex"]["taps"], key=B["reflex"]["taps"].get)])


def bk_view(g: dict, gid: str) -> dict:
    B = g.get("bk") or {}
    pid = lambda x: (player(g, x) or {}).get("pid") if x else None
    if not B:
        return {"mult": _bk_mult(g), "alcohol": bool(g["options"].get("sips", 1))}
    tally = g.get("tally", {})
    r, d, du = B.get("reflex"), B.get("dice"), B.get("duel")
    cur = B["order"][B["turn"] % len(B["order"])] if B["order"] else None
    now = time.time()
    return {
        "mult": _bk_mult(g), "alcohol": bool(g["options"].get("sips", 1)), "event": B["n"],
        "seats": [{"pid": pid(x), "name": _bk_name(g, x), "drink": tally.get(x, {}).get("drink", 0), "give": tally.get(x, {}).get("give", 0),
                   "biskit": x == B["biskit"], "qmaster": x == B["qmaster"], "thumb": x == B["thumb"],
                   "mate": any(x in m for m in B["mates"]), "manual": bool((player(g, x) or {}).get("manual"))} for x in B["order"]],
        "turn": pid(cur), "my_turn": cur == gid, "card": B["card"], "key": B["key"], "drawer": pid(B["drawer"]),
        "drawer_name": _bk_name(g, B["drawer"]) if B["drawer"] else None, "drawn": B["drawn"], "deck_left": len(B["deck"]),
        "wait": max(0.0, B.get("ready_at", 0) - now),
        "kings": B["kings"], "outcomes": B["outcomes"], "rules": B["rules"],
        "mates": [[_bk_name(g, a), _bk_name(g, b)] for a, b in B["mates"]],
        "biskit": _bk_name(g, B["biskit"]), "qmaster": _bk_name(g, B["qmaster"]) if B["qmaster"] else None,
        "thumb": _bk_name(g, B["thumb"]) if B["thumb"] else None, "final": _bk_name(g, B["final"]) if B["final"] else None,
        "dice": {**d, "roller": pid(d["roller"]), "roller_name": _bk_name(g, d["roller"]), "age": now - d["at"]} if d else None,
        "duel": {**du, "a": pid(du["a"]), "b": pid(du["b"]), "a_name": _bk_name(g, du["a"]), "b_name": _bk_name(g, du["b"]), "age": now - du["at"]} if du else None,
        "reflex": {"id": r["id"], "kind": r["kind"], "done": r["done"], "tapped": [pid(x) for x in r["taps"]], "me_tapped": gid in r["taps"],
                   "losers": [_bk_name(g, x) for x in r["losers"]], "age": now - r["at"]} if r else None,
        "await": {"kind": B["await"]["kind"], "pid": pid(B["await"]["gid"]), "name": _bk_name(g, B["await"]["gid"]),
                  "mine": B["await"]["gid"] == gid} if B.get("await") else None,
    }


def purity_reveal(g: dict):
    """Purify Test : l'animateur révèle les scores ; avec l'alcool, le plus sulfureux boit (compté au tableau)."""
    try:
        purity.reveal(g)
    except purity.PurityError as e:
        raise GameError(str(e))
    for r in purity.gorgees(g):
        add_sips(g, gid_of(g, r["pid"]), drink=r["sips"])


def _lk_award(g: dict, winners: list[str]):
    """« Qui est le plus… ? » : avec l'option alcool, chaque personne désignée boit ses gorgées (compté au tableau)."""
    for w in winners:
        add_sips(g, w, drink=g["options"].get("sips", 0))


def _lk(fn, g: dict, *args):
    try:
        return fn(g, *args)
    except likely.LikelyError as e:
        raise GameError(str(e))


def lk_vote(g: dict, voter: str, target: str, by: str = ""):
    _lk_award(g, _lk(likely.vote, g, voter, target, by))


def lk_skip(g: dict, target: str = ""):
    _lk_award(g, _lk(likely.skip, g, target))


def lk_swap(g: dict, rng: random.Random = random):
    _lk(likely.swap, g, rng)


def _db(fn, g: dict, *args):
    """« Pour ou contre » : les erreurs du module deviennent des erreurs de jeu (message affiché tel quel)."""
    try:
        return fn(g, *args)
    except debate.DebateError as e:
        raise GameError(str(e))


# ── Pause de l'animateur, dans tous les jeux ──
PAUSE_KEEP = {"created_at", "updated_at"}  # dates qui ne bougent pas à la reprise
PAUSE_WINDOW = 6 * 3600  # une date de la partie : entre 6 h avant la pause et 1 h après (échéances à venir)


def pause_game(g: dict, gid: str):
    """L'animateur met la partie en pause : plus aucun coup, le temps s'arrête (voir resume_game)."""
    if g["phase"] in ("lobby", "end") or g["type"] == "room":
        raise GameError("Rien à mettre en pause : la partie n'est pas en cours")
    if g.get("paused"):
        raise GameError("La partie est déjà en pause")
    g["paused"] = {"at": time.time(), "by": (player(g, gid) or {}).get("name") or g.get("host_name") or "L'animateur"}


def _shift_times(node, since: float, delta: float):
    """Décale chaque date de la partie (échéance d'une question, lancer de la bille…) de la durée de la pause."""
    items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
    for k, v in items:
        if isinstance(v, (dict, list)):
            _shift_times(v, since, delta)
        elif isinstance(v, float) and k not in PAUSE_KEEP and since - PAUSE_WINDOW <= v <= since + 3600:
            node[k] = v + delta


def resume_game(g: dict):
    """Reprise : chaque minuteur repart là où il s'était arrêté."""
    paused = g.get("paused")
    if not paused:
        raise GameError("La partie n'est pas en pause")
    g["paused"] = None
    _shift_times(g, paused["at"], time.time() - paused["at"])


def bp_call(g: dict, fn, *args):
    """Beer pong : ses erreurs deviennent des erreurs de jeu (message pour le téléphone)."""
    try:
        return fn(g, *args)
    except beerpong.BeerPongError as e:
        raise GameError(str(e))


def bp_can_mark(g: dict, gid: str) -> bool:
    """Marquer un gobelet et choisir la sentence : l'animateur, ou le marqueur qu'il a désigné."""
    return is_lead(g, gid) or (bool(gid) and g.get("bp", {}).get("marker") == gid)


def bp_mark(g: dict, gid: str, fn, *args):
    if not bp_can_mark(g, gid):
        raise GameError("Seul l'animateur ou le marqueur note les gobelets")
    return bp_call(g, fn, *args)


def db_vote(g: dict, voter: str, value, by: str = ""):
    _db(debate.vote, g, voter, value, by)


def db_skip(g: dict, target: str = ""):
    _db(debate.skip, g, target)


def db_swap(g: dict, rng: random.Random = random):
    _db(debate.swap, g, rng)


def db_revote(g: dict):
    _db(debate.revote, g)


def db_propose(g: dict, gid: str, text):
    _db(debate.propose, g, gid, text)


def db_accept(g: dict, proposal_id):
    _db(debate.accept, g, proposal_id)


def db_refuse(g: dict, proposal_id):
    _db(debate.refuse, g, proposal_id)


def start(g: dict, rng: random.Random = random):
    """Distribue les rôles (Undercover) ou pose la première question (Qui de nous ?)."""
    if g["type"] == "heist":
        heist.start(g, rng)
        return
    if g["type"] == "island":
        island.start(g, rng)
        return
    if g["type"] == "neon":
        neon.start(g, rng)
        return
    if g["type"] == "president":
        president.start(g, rng)
        return
    if g["type"] == "room":
        raise GameError("Choisis d'abord un jeu à lancer")
    if g["type"] == "purity":
        try:
            purity.start(g)
        except purity.PurityError as e:
            raise GameError(str(e))
        return
    if g["type"] == "likely":
        try:
            likely.start(g, rng)
        except likely.LikelyError as e:
            raise GameError(str(e))
        return
    if g["type"] == "debate":
        _db(debate.start, g, rng)
        return
    if g["type"] == "beerpong":
        bp_call(g, beerpong.start, rng)
        return
    if g["type"] == "quiz":
        try:
            quiz.start(g, rng)
        except quiz.QuizError as e:
            raise GameError(str(e))
        return
    if g["type"] == "biskit":
        bk_start(g, rng)
        return
    if g["type"] == "pyramid":
        pyr_start(g, rng)
        return
    if g["type"] == "tmc":
        if len(g["players"]) < 2:
            raise GameError("Il faut au moins 2 joueurs")
        tmc_next(g, rng)
    elif g["type"] == "divan":
        if not g["players"]:
            raise GameError("Il faut au moins 1 joueur")
        g["phase"] = "card"
        g["divan"]["turn"] = 0
        _divan_draw(g, rng)
    elif g["type"] == "casino":
        casino_open(g)
    elif g["type"] in BLACKJACKS:
        bj_open_bets(g)
    elif g["type"] == "undercover":
        _deal(g, rng)
    elif g["type"] not in QUESTION_GAMES:
        raise GameError("Ce jeu ne se lance pas ainsi")
    else:
        if len(g["players"]) < 2:
            raise GameError("Il faut au moins 2 joueurs")
        _next_question(g, rng)


def _deal(g: dict, rng):
    players = g["players"]
    n = len(players)
    if n < 3:
        raise GameError("Il faut au moins 3 joueurs")
    whites = 1 if g["options"]["white"] and n >= 5 else 0
    # Nombre d'imposteurs choisi (sinon selon la tablée) ; les civils restent toujours majoritaires.
    undercovers = g["options"].get("impostors") or (1 if n <= 6 else 2 if n <= 9 else 3)
    undercovers = max(1, min(undercovers, (n - 1) // 2 - whites))
    pairs = [i for i in range(len(WORD_PAIRS)) if i not in g["used"]] or list(range(len(WORD_PAIRS)))
    pair_index = rng.choice(pairs)
    g["used"] = (g["used"] + [pair_index])[-60:]
    civil, under, hint = WORD_PAIRS[pair_index]
    if rng.random() < 0.5:
        civil, under = under, civil
    g["words"] = {"civil": civil, "undercover": under, "hint": hint}
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
    elif voter in g["votes"]:
        raise GameError("Ton vote est déjà enregistré")  # Qui de nous ? : vote définitif
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
        sips = g["options"].get("sips", 0)
        if g["type"] == "never":
            g["results"] = [[gid, answer] for gid, answer in g["votes"].items()]
            drinkers = [gid for gid, answer in g["votes"].items() if answer == "yes"]
        else:
            g["results"] = sorted(([gid, c] for gid, c in counts.items()), key=lambda x: -x[1])
            best = g["results"][0][1] if g["results"] else 0
            drinkers = [gid for gid, c in g["results"] if c == best and best]
        for gid in drinkers:
            if sips and player(g, gid):
                add_sips(g, gid, drink=sips)
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
    if g["type"] == "heist":
        heist.start(g, rng)
        return
    if g["type"] == "island":
        island.start(g, rng)
        return
    if g["type"] == "neon":
        neon.start(g, rng)
        return
    if g["type"] == "president":
        president.start(g, rng)
        return
    if g["type"] == "tmc":
        tmc_next(g, rng)
        return
    if g["type"] == "purity":
        start(g, rng)  # nouveau test, mêmes joueurs
        return
    if g["type"] == "likely":
        try:
            likely.next_step(g, rng)
        except likely.LikelyError as e:
            raise GameError(str(e))
        return
    if g["type"] == "debate":
        _db(debate.next_step, g, rng)
        return
    if g["type"] == "casino":
        if g["phase"] != "results":
            raise GameError("Pas encore")
        casino_open(g)
        return
    if g["type"] in BLACKJACKS:
        if g["phase"] != "results":
            raise GameError("Pas encore")
        bj_open_bets(g)
        return
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
    if g["type"] == "heist":
        heist.start(g, rng)
    elif g["type"] == "island":
        island.start(g, rng)
    elif g["type"] == "neon":
        neon.start(g, rng)
    elif g["type"] == "president":
        president.start(g, rng)
    elif g["type"] in ("quiz", "purity", "likely", "debate"):
        start(g, rng)
    elif g["type"] == "beerpong":
        start(g, rng)  # remet les gobelets ; refusé sans rien toucher s'il manque une équipe
    elif g["type"] == "biskit":
        start(g, rng)
    elif g["type"] == "pyramid":
        g["pyr"] = {}
        start(g, rng)
    elif g["type"] == "tmc":
        g["tmc"].update(scores={}, pairs={}, last=[])
        g["round"] = 0
        start(g, rng)
    elif g["type"] == "undercover":
        _deal(g, rng)
    elif g["type"] in QUESTION_GAMES:
        _next_question(g, rng)
    else:
        # Salle de jeux, Divan, Blackjack, Casino, Roulette : pas de « nouvelle manche » (ils continuent d'eux-mêmes).
        raise GameError("Pas de nouvelle manche pour ce jeu")
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
    master = is_lead(g, gid) and me is None
    players = []
    for p in g["players"]:
        waiting = bool(p.get("waiting")) and g["phase"] != "end"
        t = g.get("tally", {}).get(p["id"], {})
        out = {"pid": p["pid"], "name": p["name"], "alive": p["alive"] and not waiting, "waiting": waiting,
               "voted": p["id"] in g["votes"], "host": p["id"] == g["host"],
               "drink": t.get("drink", 0), "give": t.get("give", 0), "manual": bool(p.get("manual"))}
        if p.get("manual") and is_lead(g, gid) and g["type"] == "never":
            out["answer"] = g["votes"].get(p["id"])  # l'animateur voit ce qu'il a saisi pour lui
        # Un éliminé dévoile son rôle, pas son mot (celui d'un civil aiderait les undercovers restants).
        if (ended or master or not p["alive"]) and p["role"]:
            out["role"] = ROLE_LABELS[p["role"]]
        if ended or master:
            out["word"] = p["word"]
        players.append(out)
    out = {
        "id": g["id"], "code": g["code"], "type": g["type"], "name": GAMES[g["type"]], "phase": g["phase"], "room": g.get("room"),
        "mode": mode_label(g),
        "round": g["round"], "players": players, "is_host": is_lead(g, gid), "is_owner": bool(gid) and gid == g["host"], "master": master,
        "host_name": g.get("host_name", ""),
        "order": [player(g, i)["name"] for i in g["order"] if player(g, i)] if g["type"] == "undercover" else [],
        "order_pids": [_pid(g, i) for i in g["order"] if player(g, i)] if g["type"] == "undercover" else [],
        "candidates": [_pid(g, i) for i in g["candidates"]] if g["candidates"] else None,
        "winner": g["winner"], "question": g["question"], "votes_count": len(g["votes"]), "options": g["options"],
        "kicked": bool(gid) and gid in g.get("kicked", []),  # banni : ne peut plus revenir
        "excluded": bool(gid) and gid in g.get("removed", []) and not player(g, gid),  # exclu : peut revenir
        # Durée de la partie en secondes (calculée ici : l'horloge des téléphones peut être décalée).
        "elapsed": time.time() - g.get("created_at", g["updated_at"]),
    }
    if g["type"] in BLACKJACKS:
        out["bj"] = bj_view(g, gid)
    if g["type"] == "casino":
        out["casino"] = casino_view(g, gid)
    if g["type"] == "divan":
        out["divan"] = divan_view(g, gid)
    if g["type"] == "pyramid":
        out["pyr"] = pyr_view(g, gid)
    if g["type"] == "biskit":
        out["bk"] = bk_view(g, gid)
    if g["type"] == "quiz":
        out["quiz"] = quiz.view(g, gid)
    if g["type"] == "likely":
        out["likely"] = likely.view(g, gid)
    if g["type"] == "debate":
        out["debate"] = debate.view(g, gid, is_lead(g, gid))
    if g["type"] == "beerpong":
        out["bp"] = beerpong.view(g, gid, is_lead(g, gid))
    if g["type"] == "purity":
        out["purity"] = purity.view(g, gid)
        if g["phase"] == "results":
            out["purity"]["leaderboard"] = purity.leaderboard()
    if g["type"] == "heist":
        out["heist"] = heist.view(g, gid)
    if g["type"] == "island":
        out["island"] = island.view(g, gid)
    if g["type"] == "neon":
        out["neon"] = neon.view(g, gid)
    if g["type"] == "president":
        out["president"] = president.view(g, gid)
    if g["type"] == "tmc":
        out["tmc"] = tmc_view(g, gid)
    if g["type"] == "roulette":
        out["names"] = g.get("names", [])
        out["history"] = list(reversed(g.get("history", [])))
        if g.get("spin"):
            out["spin"] = {**g["spin"], "age": time.time() - g["spin"]["at"]}
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
    out["paused"] = {"by": g["paused"]["by"], "for": round(time.time() - g["paused"]["at"])} if g.get("paused") else None
    # Gorgées des derniers coups, sans l'identifiant privé (la télé et les téléphones les annoncent).
    now = time.time()
    out["sips_log"] = [{**{k: e[k] for k in ("n", "pid", "name", "drink", "give")}, "age": round(now - e.get("at", now), 1)}
                       for e in g.get("sips_log", [])]
    if ended or master:
        out["words"] = g["words"]
    if me:
        out["me"] = {"pid": me["pid"], "alive": me["alive"], "waiting": bool(me.get("waiting")) and not ended, "vote": g["votes"].get(gid) if g["type"] == "never" else _pid(g, g["votes"].get(gid)),
                     "role": "Mr. White" if me["role"] == "white" else "Undercover" if me["role"] == "undercover" and g["options"].get("reveal") else None,
                     "word": me["word"],
                     # Indice (option) : ce que les mots ont en commun, pour Mr. White et les imposteurs qui se savent imposteurs.
                     "hint": (g.get("words") or {}).get("hint") if (me["role"] == "white" and g["options"].get("white_hint"))
                     or (me["role"] == "undercover" and g["options"].get("reveal") and g["options"].get("hint")) else None,
                     "dealt": me["role"] is not None,
                     "drink": g.get("tally", {}).get(gid, {}).get("drink", 0),
                     "give": g.get("tally", {}).get(gid, {}).get("give", 0)}
    return out


def _summary_facts(g: dict) -> list[str]:
    """Infos utiles pour l'hôte de la soirée (réglages, avancement), sans aucun secret (mots, cartes…)."""
    o, t, facts = g["options"], g["type"], []
    sips = o.get("sips", 0)
    if mode_label(g):
        facts.append(f"Questions : {mode_label(g)}")
    if t == "undercover":
        facts.append("Avec Mr. White" if o.get("white") else "Sans Mr. White")
    if t in ("whoof", "never", "blackjack", "casino"):
        facts.append(f"Alcool : {sips} gorgée{'s' if sips > 1 else ''}" if sips else "Sans alcool")
    if t in ("whoof", "never") and g["round"]:
        facts.append(f"{g['round']} question{'s' if g['round'] > 1 else ''} posée{'s' if g['round'] > 1 else ''}")
    if t == "pyramid":
        P = g.get("pyr") or {}
        facts.append(f"{o.get('floors', 5)} étages · distribution {'hard' if o.get('pmode', 'hard') == 'hard' else 'soft'}"
                     f" · poteau {o.get('poteau', 'soft')} · {'avec' if o.get('boat', True) else 'sans'} bateau")
        if P:
            facts.append(f"Pyramide : {P.get('flipped', 0)}/{len(P.get('pyramid', []))} cartes retournées")
            if P.get("boat"):
                b = P.get("bstate") or {}
                facts.append(f"Bateau : {(player(g, P['boat']) or {}).get('name', '?')} · {b.get('sips', 0)} gorgée(s), essai {b.get('tries', 1)}")
    if t == "casino":
        c = g.get("casino", {})
        if c.get("history"):
            facts.append("Derniers numéros : " + ", ".join(str(n) for n in reversed(c["history"][-8:])))
    if t == "roulette":
        facts.append(f"{len(g.get('names', []))} noms sur la roue")
        if g.get("history"):
            facts.append("Derniers perdants : " + ", ".join(reversed(g["history"][-5:])))
    if t == "divan":
        facts.append(f"{g.get('divan', {}).get('n', 0)} carte(s) tirée(s)")
    if t == "tmc":
        facts.append(f"{g['round']} question(s) posée(s)")
    if t == "quiz":
        facts += quiz.summary_facts(g)
    if t == "debate":
        facts += debate.summary_facts(g)
    if t == "likely":
        facts += likely.summary_facts(g)
        facts.append(f"Alcool : {sips} gorgée{'s' if sips > 1 else ''} pour la personne désignée" if sips else "Sans alcool : un point")
    if t == "purity":
        facts.append(f"Alcool : {sips} gorgée{'s' if sips > 1 else ''} pour le plus sulfureux" if o.get("alcohol") and sips else "Sans alcool")
        if g["phase"] == "answering":
            done = sum(1 for p in g["players"] if g["purity"]["submitted"].get(p["id"]))
            facts.append(f"{done}/{len(g['players'])} test(s) validé(s)")
        facts += purity.summary_facts(g)
    if t == "heist":
        facts.append("3D · solo ou coopération · trois musées · 1 à 8 joueurs")
    if t == "island":
        facts.append("3D · survie solo ou dernier survivant · 1 à 8 joueurs")
    if t == "neon":
        s = neon.state(g)
        facts.append(("Équipes de deux" if s["mode"] == "duo" else "Chacun pour soi") + " · premier à 5 victoires")
    if t == "president":
        facts.append("54 cartes · 2 jokers · 3 à 6 joueurs")
        if g["round"]:
            facts.append(f"Manche {g['round']}")
    if t == "biskit":
        B = g.get("bk") or {}
        facts.append(f"Gorgées ×{_bk_mult(g)}" if o.get("sips", 1) else "Sans alcool")
        if B:
            facts.append(f"{B.get('drawn', 0)} carte(s) tirée(s) · coupe du Roi {B.get('kings', 0)}/4 · Biskit : {_bk_name(g, B.get('biskit'))}")
            if B.get("rules"):
                facts.append("Règles : " + " · ".join(r["text"] for r in B["rules"]))
    return facts


def _summary_extra(g: dict, p: dict) -> str:
    """Score ou jetons d'un joueur, selon le jeu."""
    if g["type"] == "quiz":
        return quiz.summary_extra(g, p["id"])
    if g["type"] == "purity":
        score = g["purity"]["scores"].get(p["id"])
        return f"{score} % impur" if score is not None else ""
    if g["type"] == "heist":
        return f"{heist.state(g)['scores'].get(p['pid'], 0)} braquage(s) réussi(s)"
    if g["type"] == "island":
        s = island.state(g)
        return f"{s['scores'].get(p['pid'], 0)} victoire(s) · record {s['best'].get(p['pid'], 0):.1f} s"
    if g["type"] == "neon":
        s = neon.state(g)
        key = str(s["teams"].get(p["pid"])) if s["mode"] == "duo" else p["pid"]
        return f"{s['scores'].get(key, 0)} victoire(s)"
    if g["type"] == "president":
        s = g.get("president", {})
        return f"{s.get('scores', {}).get(p['id'], 0)} pts · {len(s.get('hands', {}).get(p['id'], []))} cartes"
    if g["type"] == "blackjack":
        return f"💰 {g['bj']['chips'].get(p['id'], BJ_START_CHIPS)}" if not bj_drinks(g) else ""
    if g["type"] == "casino" and not casino_sips(g):
        return f"💰 {g['casino']['chips'].get(p['id'], CASINO_START_CHIPS)}"
    if g["type"] == "likely":
        return f"⭐ {likely.state(g)['scores'].get(p['id'], 0)}"
    if g["type"] == "tmc":
        sc = g.get("tmc", {}).get("scores", {}).get(p["id"])
        return f"⭐ {sc}" if sc is not None else ""
    if g["type"] == "pyramid":
        err = (g.get("pyr") or {}).get("errors", {}).get(p["id"])
        return f"🧠 {err} erreur(s)" if err is not None else ""
    return ""


def room_merge(room: dict, g: dict):
    """Fin d'un jeu lancé depuis la salle : ses gorgées et ses points s'ajoutent au tableau de la soirée."""
    for gid, t in (g.get("tally") or {}).items():
        r = room["rtally"].setdefault(gid, {"drink": 0, "give": 0})
        r["drink"] += t.get("drink", 0)
        r["give"] += t.get("give", 0)
    for gid, sc in ((g.get("quiz") or {}).get("scores") or {}).items():
        room["rpts"][gid] = room["rpts"].get(gid, 0) + sc.get("pts", 0)
    for gid, pts in (g.get("president") or {}).get("scores", {}).items():
        room["rpts"][gid] = room["rpts"].get(gid, 0) + pts
    room["rnames"].update((g.get("president") or {}).get("names", {}))
    for p in g["players"]:
        room["rnames"][p["id"]] = p["name"]
    winner = None
    if g["type"] == "quiz" and g["players"]:
        rows = quiz.board(g)
        winner = rows[0][0]["name"] if rows and rows[0][1]["n"] else None
    if g["type"] == "likely":
        for gid, pts in likely.state(g)["scores"].items():
            room["rpts"][gid] = room["rpts"].get(gid, 0) + pts
        winner = likely.winner_name(g)  # le plus désigné de la partie
    if g["type"] == "purity" and (rows := purity.ranking(g)):
        winner = rows[0]["name"]  # le plus impur ; les scores (en %) ne s'ajoutent pas aux points de la soirée
    if g["type"] == "president" and g.get("president", {}).get("finished"):
        s = g["president"]
        winner = room["rnames"].get(s["finished"][0])
    if g["type"] == "neon":
        s = neon.state(g)
        for p in g["players"]:
            key = str(s["teams"].get(p["pid"])) if s["mode"] == "duo" else p["pid"]
            room["rpts"][p["id"]] = room["rpts"].get(p["id"], 0) + s["scores"].get(key, 0)
        if s["winner"] is not None and g["phase"] == "end":
            winner = neon.TEAM_NAMES[int(s["winner"])] if s["mode"] == "duo" else next((p["name"] for p in g["players"] if p["pid"] == s["winner"]), None)
    if g["type"] == "heist":
        s = heist.state(g)
        for p in g["players"]:
            room["rpts"][p["id"]] = room["rpts"].get(p["id"], 0) + s["scores"].get(p["pid"], 0)
        winner = "Toute l’équipe" if s["success"] else None
    if g["type"] == "island":
        s = island.state(g)
        for p in g["players"]:
            room["rpts"][p["id"]] = room["rpts"].get(p["id"], 0) + s["scores"].get(p["pid"], 0)
        winner = next((p["name"] for p in g["players"] if p["pid"] == s["winner"]), None)
    room["rhistory"].append({"type": g["type"], "name": GAMES.get(g["type"], ""), "at": time.time(), "players": len(g["players"]),
                             "winner": winner})
    room["current"] = None


def room_vote(room: dict, gid: str, kind: str):
    """Un participant de la salle vote pour le prochain jeu : un seul choix, qu'il déplace quand il veut (retoucher
    son choix le retire). L'animateur ne vote pas : il voit les votes et décide."""
    if room["type"] != "room":
        raise GameError("Action inconnue")
    if room.get("current"):
        raise GameError("Un jeu est en cours : on vote pour le suivant à la fin")
    if is_lead(room, gid):
        raise GameError("L'animateur choisit le jeu : il ne vote pas")
    if player(room, gid) is None:
        raise GameError("Rejoins la salle pour voter")
    if kind not in GAMES or kind == "room":
        raise GameError("Jeu inconnu")
    votes = room.setdefault("rvotes", {})
    if votes.get(gid) == kind:
        votes.pop(gid)
    else:
        votes[gid] = kind


def room_votes(room: dict) -> dict[str, int]:
    """Votes pour le prochain jeu, des seuls participants encore dans la salle."""
    present = {p["id"] for p in room["players"]}
    counts: dict[str, int] = {}
    for gid, kind in room.get("rvotes", {}).items():
        if gid in present:
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def room_view(room: dict, gid: str, child: dict | None) -> dict:
    """Ce qu'affiche la salle : le jeu en cours, l'historique et le tableau de la soirée."""
    names = {**room.get("rnames", {}), **{p["id"]: p["name"] for p in room["players"]}}
    ids = set(room["rtally"]) | set(room["rpts"]) | {p["id"] for p in room["players"]}
    board = [{"name": names.get(i, "?"), "me": i == gid, "drink": room["rtally"].get(i, {}).get("drink", 0),
              "give": room["rtally"].get(i, {}).get("give", 0), "pts": room["rpts"].get(i, 0)} for i in ids if i in names]
    board.sort(key=lambda r: (-r["pts"], -r["drink"], r["name"]))
    return {"current": {"code": child["code"], "type": child["type"], "name": GAMES[child["type"]], "phase": child["phase"],
                        "players": len(child["players"])} if child else None,
            "history": list(reversed(room["rhistory"][-12:])), "board": board,
            "votes": (votes := room_votes(room)), "my_vote": room.get("rvotes", {}).get(gid) if player(room, gid) else None,
            # Le ou les jeux les plus votés (égalité : tous), proposés à l'animateur.
            "top": sorted(k for k, n in votes.items() if n == max(votes.values())) if votes else [],
            "catalog": [{"type": t, "name": n} for t, n in GAMES.items() if t != "room"]}


def summary(g: dict) -> dict:
    """Vue d'ensemble pour l'admin (sans les secrets)."""
    name = GAMES[g["type"]] + (" · " + mode_label(g) if mode_label(g) else "")
    tally = g.get("tally", {})
    return {"code": g["code"], "type": g["type"], "name": name, "phase": g["phase"], "round": g["round"],
            "players": [p["name"] for p in g["players"]], "host": g.get("host_name", ""),
            "created_at": g.get("created_at", g["updated_at"]), "updated_at": g["updated_at"],
            "elapsed": time.time() - g.get("created_at", g["updated_at"]), "facts": _summary_facts(g),
            "players_detail": [{"name": p["name"], "host": p["id"] == g["host"], "manual": bool(p.get("manual")),
                                "pending": bool(p.get("pending")), "drink": tally.get(p["id"], {}).get("drink", 0),
                                "give": tally.get(p["id"], {}).get("give", 0), "extra": _summary_extra(g, p)}
                               for p in g["players"]]}
