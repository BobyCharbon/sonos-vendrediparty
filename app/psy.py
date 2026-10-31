"""« Qui es-tu vraiment ? » — test psychologique entre amis (avis 49275b68240b : relations, pensées, réflexion, logique).

Chacun répond en secret, sur son téléphone, à 12 questions : 9 sur sa façon d'être (relations, réactions, valeurs),
chaque réponse comptant pour un des quatre profils, et 3 petites énigmes de logique. Quand tout le monde a validé,
l'animateur révèle : le profil de chacun (dominant, second, pourcentages), son score de logique, la répartition du
groupe, le plus logique et les deux personnes qui se ressemblent le plus. Un jeu pour se découvrir, pas un vrai test.

Module autonome et testable (mêmes conventions que debate.py) : il ne connaît que la partie `g` ; les droits
d'animateur restent dans main.py.
"""
import random

PERSONALITY_COUNT = 9
LOGIC_COUNT = 3
SOULMATES_MIN = 30  # en dessous, deux personnes ne se ressemblent pas assez pour être « âmes sœurs »

PROFILES: dict[str, dict[str, str]] = {
    "leader": {"emoji": "🦁", "name": "Le Meneur", "color": "#ff6b5e",
               "text": "Direct, décidé, tu aimes les défis et faire avancer les choses. Le groupe compte sur toi pour trancher."},
    "social": {"emoji": "🎉", "name": "L'Âme de la fête", "color": "#ffc23d",
               "text": "Enthousiaste et rayonnant·e, tu crées du lien partout. Avec toi, rien n'est jamais ennuyeux."},
    "thinker": {"emoji": "🧠", "name": "Le Stratège", "color": "#5aa9ff",
                "text": "Réfléchi·e et précis·e, tu veux comprendre avant d'agir. Ton calme et ta logique rassurent."},
    "dreamer": {"emoji": "🌙", "name": "Le Cœur tendre", "color": "#7bd88f",
                "text": "Sensible et à l'écoute, tu ressens ce que vivent les autres. Ta douceur apaise tout le monde."},
}
ORDER = ("leader", "social", "thinker", "dreamer")

# Chaque question : (texte, réponses dans l'ordre leader, social, thinker, dreamer).
PERSONALITY: list[tuple[str, tuple[str, str, str, str]]] = [
    ("Un vendredi soir idéal, c'est…", ("Organiser la soirée et embarquer tout le monde", "Une grosse fête où je connais à peine la moitié des gens",
                                       "Un bon jeu de société ou une discussion passionnante", "Un plaid, un film et deux ou trois proches")),
    ("Un ami te raconte un gros problème. Tu…", ("Proposes tout de suite un plan d'action", "Lui changes les idées : on sort !",
                                                 "Poses des questions pour bien comprendre", "L'écoutes longtemps, sans juger")),
    ("Dans un travail de groupe, tu es plutôt…", ("Celui ou celle qui répartit les tâches", "L'ambianceur·euse qui motive l'équipe",
                                                  "Celui ou celle qui vérifie que tout est juste", "Celui ou celle qui veille à ce que chacun se sente bien")),
    ("Face à une décision importante…", ("Je tranche vite, quitte à corriger après", "J'en parle à plein de monde",
                                         "Je fais la liste des pour et des contre", "J'écoute mon intuition")),
    ("Ce qui t'énerve le plus chez les autres…", ("L'indécision", "Les rabat-joie", "Le manque de logique", "La méchanceté gratuite")),
    ("En vacances, tu préfères…", ("Un programme chargé que j'ai organisé", "Une ville où on sort tous les soirs",
                                   "Visiter des musées et tout apprendre sur le pays", "Un coin de nature calme")),
    ("Une dispute éclate entre deux amis. Tu…", ("Prends les choses en main et calmes le jeu", "Détends l'atmosphère avec une blague",
                                                 "Cherches qui a raison, faits à l'appui", "Restes à l'écart et consoles ensuite")),
    ("Ce qu'on dit le plus souvent de toi…", ("« Tu as du caractère »", "« Tu es trop drôle »", "« Tu réfléchis trop »", "« Tu es adorable »")),
    ("Ton rapport aux règles…", ("Je préfère les fixer moi-même", "Elles sont faites pour être un peu contournées",
                                 "Elles sont là pour une bonne raison", "Tant que personne n'est blessé, ça me va")),
    ("Tu arrives dans une soirée où tu ne connais personne…", ("Je repère qui organise et je me présente", "Je parle à tout le monde en dix minutes",
                                                               "J'observe d'abord qui est qui", "Je trouve une personne avec qui parler vraiment")),
    ("Ton plus grand moteur dans la vie…", ("Réussir", "Partager de bons moments", "Comprendre", "Être en paix")),
    ("Un imprévu ruine ton week-end. Tu…", ("Trouves un plan B dans la minute", "Improvises : c'est souvent mieux",
                                            "Analyses ce qui a coincé", "Acceptes et profites autrement")),
    ("En amitié comme en amour, tu as surtout besoin de…", ("Respect et franchise", "Rire et complicité", "Discussions profondes", "Tendresse et sécurité")),
    ("Ton super-pouvoir rêvé…", ("Convaincre n'importe qui", "Être partout à la fois", "Tout savoir", "Lire dans les cœurs")),
    ("Quand tu es stressé·e…", ("Je m'active encore plus", "J'appelle quelqu'un", "Je fais des listes", "Je m'isole un moment")),
    ("Un film parfait pour toi…", ("Un film d'action où le héros gagne", "Une comédie entre amis", "Un thriller à énigmes", "Un film qui fait pleurer")),
]

# Énigmes de logique : (texte, réponses, index de la bonne).
LOGIC: list[tuple[str, tuple[str, str, str, str], int]] = [
    ("2, 4, 8, 16… Quel nombre vient ensuite ?", ("18", "24", "32", "30"), 2),
    ("Tous les Blips sont des Blops, et certains Blops sont verts. Donc…",
     ("Tous les Blips sont verts", "Certains Blips sont peut-être verts", "Aucun Blip n'est vert", "Tous les Blops sont des Blips"), 1),
    ("Une batte et une balle coûtent 1.10 CHF. La batte coûte 1 franc de plus que la balle. Combien coûte la balle ?",
     ("10 centimes", "5 centimes", "1 franc", "55 centimes"), 1),
    ("Le père de Marie a cinq filles : Lala, Lélé, Lili, Lolo… Comment s'appelle la cinquième ?", ("Lulu", "Marie", "Lyly", "Impossible à savoir"), 1),
    ("Combien de mois ont 28 jours ?", ("Un seul", "Deux", "Tous les douze", "Ça dépend de l'année"), 2),
    ("5 machines font 5 gadgets en 5 minutes. Combien de minutes pour que 100 machines fassent 100 gadgets ?", ("100", "20", "5", "1"), 2),
    ("Pendant une course, tu dépasses le deuxième. Tu es maintenant…", ("Premier·ère", "Deuxième", "Troisième", "Dernier·ère"), 1),
    ("Des nénuphars doublent chaque jour et couvrent tout le lac en 48 jours. En combien de jours en couvrent-ils la moitié ?",
     ("24", "47", "46", "36"), 1),
    ("Quel mot ne va pas avec les autres ?", ("Chaise", "Table", "Pomme", "Armoire"), 2),
]


class PsyError(ValueError):
    """Message affiché tel quel au joueur."""


def state(g: dict) -> dict:
    return g.setdefault("psy", {"questions": [], "answers": {}, "done": {}})


def init(g: dict):
    state(g)


def start(g: dict, rng=random):
    """Nouveau test : 9 questions de personnalité et 3 énigmes, réponses dans un ordre mélangé, mêmes pour tous."""
    if len(g["players"]) < 1:
        raise PsyError("Il faut au moins un joueur")
    S = state(g)
    questions = []
    for text, answers in rng.sample(PERSONALITY, PERSONALITY_COUNT):
        options = [{"text": a, "tag": tag} for a, tag in zip(answers, ORDER)]
        rng.shuffle(options)
        questions.append({"kind": "self", "text": text, "options": options})
    for text, answers, good in rng.sample(LOGIC, LOGIC_COUNT):
        options = [{"text": a, "tag": "ok" if i == good else "no"} for i, a in enumerate(answers)]
        rng.shuffle(options)
        questions.append({"kind": "logic", "text": text, "options": options})
    S.update(questions=questions, answers={}, done={})
    g["phase"] = "answering"
    g["round"] = g.get("round", 0) + 1  # chaque téléphone repart de la première question


def _player(g: dict, gid: str) -> bool:
    return any(p["id"] == gid for p in g["players"])


def answer(g: dict, gid: str, index, choice):
    S = state(g)
    if g["phase"] != "answering" or not _player(g, gid):
        raise PsyError("Pas maintenant")
    if S["done"].get(gid):
        raise PsyError("Tes réponses sont déjà validées")
    try:
        index, choice = int(index), int(choice)
    except (TypeError, ValueError):
        raise PsyError("Réponse inconnue") from None
    if not 0 <= index < len(S["questions"]) or not 0 <= choice < len(S["questions"][index]["options"]):
        raise PsyError("Réponse inconnue")
    S["answers"].setdefault(gid, {})[str(index)] = choice


def submit(g: dict, gid: str):
    S = state(g)
    if g["phase"] != "answering" or not _player(g, gid):
        raise PsyError("Pas maintenant")
    if len(S["answers"].get(gid, {})) < len(S["questions"]):
        raise PsyError("Réponds à toutes les questions")
    S["done"][gid] = True


def leave(g: dict, gid: str):
    S = state(g)
    S["answers"].pop(gid, None)
    S["done"].pop(gid, None)


def everyone_done(g: dict) -> bool:
    S = state(g)
    return bool(g["players"]) and all(S["done"].get(p["id"]) for p in g["players"])


def reveal(g: dict):
    S = state(g)
    if g["phase"] != "answering":
        raise PsyError("Pas maintenant")
    if not any(S["done"].values()):
        raise PsyError("Personne n'a encore validé")
    g["phase"] = "results"


def _tags(S: dict, gid: str) -> list[str]:
    mine = S["answers"].get(gid, {})
    return [q["options"][mine[str(i)]]["tag"] if str(i) in mine else "" for i, q in enumerate(S["questions"])]


def profile_of(S: dict, gid: str) -> dict:
    tags = _tags(S, gid)
    selfs = [t for t, q in zip(tags, S["questions"]) if q["kind"] == "self" and t]
    counts = {p: selfs.count(p) for p in ORDER}
    total = max(1, len(selfs))
    ranked = sorted(ORDER, key=lambda p: (-counts[p], ORDER.index(p)))
    logic = sum(1 for t, q in zip(tags, S["questions"]) if q["kind"] == "logic" and t == "ok")
    return {"profile": ranked[0], "second": ranked[1] if counts[ranked[1]] else None,
            "pct": {p: round(100 * counts[p] / total) for p in ORDER}, "logic": logic}


def _similarity(S: dict, a: str, b: str) -> int:
    ta, tb = _tags(S, a), _tags(S, b)
    selfs = [i for i, q in enumerate(S["questions"]) if q["kind"] == "self"]
    same = sum(1 for i in selfs if ta[i] and ta[i] == tb[i])
    return round(100 * same / max(1, len(selfs)))


def results(g: dict) -> dict:
    S = state(g)
    done = [p for p in g["players"] if S["done"].get(p["id"])]
    people = [{"pid": p["pid"], "name": p["name"], **profile_of(S, p["id"])} for p in done]
    distribution = {k: sum(1 for x in people if x["profile"] == k) for k in ORDER}
    best_logic = max((x["logic"] for x in people), default=0)
    pair = None
    for i, a in enumerate(done):
        for b in done[i + 1:]:
            pct = _similarity(S, a["id"], b["id"])
            if pct >= SOULMATES_MIN and (not pair or pct > pair["pct"]):
                pair = {"a": a["name"], "b": b["name"], "pct": pct}
    return {"people": people, "distribution": distribution, "logic_count": LOGIC_COUNT,
            "most_logic": [x["name"] for x in people if x["logic"] == best_logic] if people and best_logic else [],
            "pair": pair}


def view(g: dict, gid: str) -> dict:
    S = state(g)
    playing = _player(g, gid)
    out = {"profiles": PROFILES, "count": len(S["questions"]), "playing": playing, "done": bool(S["done"].get(gid)),
           "progress": [{"pid": p["pid"], "name": p["name"], "done": bool(S["done"].get(p["id"]))} for p in g["players"]]}
    if g["phase"] == "answering" and playing:
        # Questions sans leur clé : personne ne voit quel profil ni quelle bonne réponse se cache derrière un choix.
        out["questions"] = [{"kind": q["kind"], "text": q["text"], "options": [o["text"] for o in q["options"]]} for q in S["questions"]]
        out["mine"] = S["answers"].get(gid, {})
    if g["phase"] == "results":
        out["results"] = results(g)
        if playing and S["done"].get(gid):
            out["me"] = profile_of(S, gid)
    return out


def summary_facts(g: dict) -> list[str]:
    if g["phase"] != "results":
        return []
    r = results(g)
    facts = [f"{x['name']} : {PROFILES[x['profile']]['emoji']} {PROFILES[x['profile']]['name']}" for x in r["people"]]
    if r["pair"]:
        facts.append(f"Âmes sœurs : {r['pair']['a']} & {r['pair']['b']} ({r['pair']['pct']} %)")
    return facts
