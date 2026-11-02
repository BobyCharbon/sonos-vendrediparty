"""« Le Masque » — tout le monde répond en secret à la même question profonde, puis devine qui a écrit quoi.

Un tour : une question s'affiche ; chacun écrit sa réponse sur son téléphone (une phrase). Quand tout le monde a écrit,
les réponses apparaissent mélangées, sans prénom. Chacun relie les réponses aux prénoms et, pour la sienne, choisit en
secret de lever le masque (se dévoiler, raconter) ou de rester masqué. À la révélation : l'auteur de chaque réponse
dévoilée, qui l'avait trouvé ; une réponse masquée garde son secret (personne ne sait qui l'a trouvée).

Points : 1 par auteur trouvé (sur les réponses dévoilées), 1 pour avoir levé son masque. Pas de point pour une réponse
drôle : on joue la sincérité. L'animateur peut retirer une réponse (elle sort du jeu, sans son auteur).

Module autonome et testable (mêmes conventions que debate.py) : il ne connaît que la partie `g` ; les droits
d'animateur restent dans main.py, et tout passe par le verrou unique des jeux.
"""
import random

from .masque_cards import MASQUE_CARDS

CATS = {
    "souvenirs": "📼 Souvenirs", "toi": "🪞 Toi en vrai", "liens": "🤝 Les liens",
    "valeurs": "🧭 Valeurs", "reves": "🌠 Rêves & peurs", "imaginaire": "🔮 Et si…",
}
LEVELS = {"leger": "🌤 Léger", "profond": "🌊 Profond", "intime": "🕯 Intime"}
DEFAULT_LEVELS = ["leger", "profond"]  # l'intime se choisit : jamais proposé d'office
COUNTS = (5, 8, 12)
MIN_PLAYERS = 3  # deviner parmi deux réponses n'est pas un jeu
MIN_ANSWER, MAX_ANSWER = 2, 140
POINT_FOUND, POINT_UNMASK = 1, 1


class MasqueError(ValueError):
    """Message affiché tel quel au joueur."""


def state(g: dict) -> dict:
    return g.setdefault("masque", {
        "cats": list(CATS), "levels": list(DEFAULT_LEVELS), "count": COUNTS[1], "used": [], "n": 0, "q": None,
        "answers": {}, "slots": [], "hidden": [], "guesses": {}, "unmask": {}, "sent": {}, "scores": {}, "history": [],
        "result": None,
    })


def init(g: dict):
    state(g)


def _player(g: dict, gid: str) -> dict | None:
    return next((p for p in g["players"] if p["id"] == gid), None)


def _name(g: dict, gid: str) -> str:
    p = _player(g, gid)
    return p["name"] if p else "?"


def deck(S: dict) -> list[int]:
    return [i for i, (cat, level, _) in enumerate(MASQUE_CARDS) if cat in S["cats"] and level in S["levels"]]


def configure(g: dict, settings: dict):
    """Catégories, niveaux et nombre de questions : avant la partie, ou entre deux parties."""
    S = state(g)
    if g["phase"] not in ("lobby", "end"):
        raise MasqueError("Les réglages se changent avant la partie")
    cats = settings.get("cats", S["cats"])
    levels = settings.get("levels", S["levels"])
    if not isinstance(cats, list) or not cats or any(not isinstance(c, str) or c not in CATS for c in cats):
        raise MasqueError("Garde au moins une catégorie")
    if not isinstance(levels, list) or not levels or any(not isinstance(lv, str) or lv not in LEVELS for lv in levels):
        raise MasqueError("Garde au moins un niveau")
    count = settings.get("count", S["count"])
    if isinstance(count, bool) or not isinstance(count, int) or count not in COUNTS:
        raise MasqueError("Nombre de questions inconnu")
    chosen = {"cats": list(dict.fromkeys(cats)), "levels": list(dict.fromkeys(levels))}
    if not deck(chosen):
        raise MasqueError("Aucune question pour ce choix")
    S.update(chosen, count=count)


def start(g: dict, rng=random):
    if len(g["players"]) < MIN_PLAYERS:
        raise MasqueError(f"Il faut au moins {MIN_PLAYERS} joueurs")
    S = state(g)
    S.update(n=0, scores={}, history=[], result=None)
    _deal(g, rng)


def _deal(g: dict, rng=random):
    """Nouvelle question, jamais deux fois la même dans la soirée (tant que le paquet n'est pas épuisé)."""
    S = state(g)
    cards = deck(S)
    if not cards:
        raise MasqueError("Aucune question pour ce choix")
    fresh = [i for i in cards if i not in S["used"]]
    if not fresh:  # paquet épuisé : on le remélange, sans retomber sur la question qu'on vient de voir
        last = S["used"][-1] if S["used"] else None
        S["used"] = [i for i in S["used"] if i not in cards]
        fresh = [i for i in cards if i != last] or cards
    pick = rng.choice(fresh)
    S["used"].append(pick)
    cat, level, text = MASQUE_CARDS[pick]
    S.update(q={"text": text, "cat": cat, "level": level}, answers={}, slots=[], hidden=[], guesses={}, unmask={},
             sent={}, result=None, n=S["n"] + 1)
    g["phase"] = "write"
    g["round"] = g.get("round", 0) + 1


INVISIBLE = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def _clean(text) -> str:
    """Une phrase lisible : sans caractères de contrôle ni invisibles (une réponse « vide » ne passe pas)."""
    text = "".join(c for c in str(text or "") if ord(c) >= 32 and ord(c) not in INVISIBLE)
    return " ".join(text.split())[:MAX_ANSWER]


def write(g: dict, gid: str, text, rng=random):
    """Sa réponse (modifiable tant que tout le monde n'a pas écrit). La dernière réponse lance la devinette."""
    S = state(g)
    if g["phase"] != "write" or not _player(g, gid):
        raise MasqueError("Pas maintenant")
    text = _clean(text)
    if len(text) < MIN_ANSWER:
        raise MasqueError("Écris au moins quelques mots")
    S["answers"][gid] = text
    if all(p["id"] in S["answers"] for p in g["players"]):
        show(g, rng)


def swap(g: dict, rng=random):
    """L'animateur change de question tant que personne n'a répondu (la question ne compte qu'une fois)."""
    S = state(g)
    if g["phase"] != "write":
        raise MasqueError("Pas maintenant")
    if S["answers"]:
        raise MasqueError("Quelqu'un a déjà répondu")
    S["n"] -= 1
    _deal(g, rng)


def show(g: dict, rng=random):
    """Fin de l'écriture (tous ont écrit, ou l'animateur n'attend plus) : réponses mélangées, sans prénom."""
    S = state(g)
    if g["phase"] != "write":
        raise MasqueError("Pas maintenant")
    authors = [p["id"] for p in g["players"] if p["id"] in S["answers"]]
    if len(authors) < MIN_PLAYERS:
        raise MasqueError(f"Il faut au moins {MIN_PLAYERS} réponses")
    rng.shuffle(authors)
    S["slots"] = [{"gid": a, "text": S["answers"][a]} for a in authors]
    # Prénoms proposés figés à cet instant : un départ ou un retrait ne doit rien trahir par élimination.
    S["authors"] = [{"gid": p["id"], "pid": p["pid"], "name": p["name"]} for p in g["players"] if p["id"] in S["answers"]]
    S["guessers"] = [p["id"] for p in g["players"]]  # un retardataire peut deviner, mais on ne l'attend pas
    g["phase"] = "guess"


def _mine(S: dict, gid: str) -> int | None:
    return next((i for i, s in enumerate(S["slots"]) if s["gid"] == gid), None)


def _everyone_sent(g: dict) -> bool:
    """Tous ceux qui étaient là quand les réponses sont apparues (et encore là) ont envoyé leurs choix."""
    S = state(g)
    here = {p["id"] for p in g["players"]}
    expected = [x for x in S.get("guessers") or here if x in here]
    return bool(expected) and all(S["sent"].get(x) for x in expected)


def guess(g: dict, gid: str, picks, unmask=None):
    """Ses devinettes (réponse → prénom) et, s'il a écrit, son choix de lever le masque. Envoi définitif."""
    S = state(g)
    if g["phase"] != "guess" or not _player(g, gid):
        raise MasqueError("Pas maintenant")
    if S["sent"].get(gid):
        raise MasqueError("Tes choix sont déjà envoyés")
    if not isinstance(picks, dict):
        raise MasqueError("Choix inconnus")
    mine = _mine(S, gid)
    pids = {a["pid"]: a["gid"] for a in S.get("authors") or []}
    clean: dict[str, str] = {}
    for slot, pid in picks.items():
        try:
            index = int(slot)
        except (TypeError, ValueError):
            raise MasqueError("Choix inconnus") from None
        if not isinstance(pid, str) or not 0 <= index < len(S["slots"]) or index == mine:
            raise MasqueError("Choix inconnus")
        who = pids.get(pid)
        if who == gid:
            raise MasqueError("Ce joueur n'a pas répondu")
        if who is None or index in S["hidden"]:
            continue  # réponse retirée ou prénom inconnu entre-temps : ce choix ne compte pas, l'envoi passe
        if who in clean.values():
            raise MasqueError("Un prénom ne va qu'avec une réponse")
        clean[str(index)] = who
    S["guesses"][gid] = clean
    if mine is not None:
        S["unmask"][gid] = unmask is True
    S["sent"][gid] = True
    if _everyone_sent(g):
        reveal(g)


def hide(g: dict, index):
    """L'animateur retire une réponse (déplacée, blessante) : elle sort du jeu et son auteur reste inconnu."""
    S = state(g)
    if g["phase"] != "guess":
        raise MasqueError("Pas maintenant")
    try:
        index = int(index)
    except (TypeError, ValueError):
        raise MasqueError("Réponse inconnue") from None
    if not 0 <= index < len(S["slots"]):
        raise MasqueError("Réponse inconnue")
    if index not in S["hidden"]:
        S["hidden"].append(index)
        for picks in S["guesses"].values():
            picks.pop(str(index), None)


def reveal(g: dict):
    S = state(g)
    if g["phase"] != "guess":
        raise MasqueError("Pas maintenant")
    if not any(S["sent"].values()):
        raise MasqueError("Personne n'a encore envoyé ses choix")
    rows = []
    for i, slot in enumerate(S["slots"]):
        if i in S["hidden"]:
            rows.append({"text": None, "hidden": True})
            continue
        author, open_ = slot["gid"], bool(S["unmask"].get(slot["gid"]))
        found = [x for x, picks in S["guesses"].items() if picks.get(str(i)) == author]
        if open_:
            S["scores"][author] = S["scores"].get(author, 0) + POINT_UNMASK
            for x in found:
                S["scores"][x] = S["scores"].get(x, 0) + POINT_FOUND
        rows.append({"text": slot["text"], "hidden": False, "open": open_,
                     "author": _name(g, author) if open_ else None,
                     "found": [_name(g, x) for x in found] if open_ else None,
                     "_author": author, "_found": found})
    S["result"] = rows
    S["history"].append({"q": S["q"]["text"], "rows": rows})
    g["phase"] = "reveal"


def next_step(g: dict, rng=random):
    S = state(g)
    if g["phase"] != "reveal":
        raise MasqueError("Pas maintenant")
    if S["n"] >= S["count"]:
        g["phase"] = "end"
        return
    _deal(g, rng)


def leave(g: dict, gid: str, rng=random):
    """Un joueur s'en va : ce qu'il a écrit ou deviné disparaît, et la partie n'attend plus après lui."""
    S = state(g)
    S["answers"].pop(gid, None)
    S["guesses"].pop(gid, None)
    S["sent"].pop(gid, None)
    if g["phase"] in ("write", "guess", "reveal") and len(g["players"]) < MIN_PLAYERS:
        g["phase"] = "end"  # deviner parmi deux réponses n'est plus un jeu
        return
    if g["phase"] == "write":
        if len(S["answers"]) >= MIN_PLAYERS and all(p["id"] in S["answers"] for p in g["players"]):
            show(g, rng)
    elif g["phase"] == "guess":
        # Sa réponse reste en jeu, masquée (la retirer à son départ dirait à tous qu'elle était la sienne).
        S["unmask"].pop(gid, None)
        if _everyone_sent(g):
            reveal(g)


def summary(g: dict) -> dict:
    S = state(g)
    found: dict[str, int] = {}
    opened: dict[str, int] = {}
    guessed_about: dict[str, list[int]] = {}
    for h in S["history"]:
        for r in h["rows"]:
            if r.get("hidden") or not r.get("open"):
                continue
            opened[r["_author"]] = opened.get(r["_author"], 0) + 1
            guessed_about.setdefault(r["_author"], []).append(len(r["_found"]))
            for x in r["_found"]:
                found[x] = found.get(x, 0) + 1

    def best(counts: dict) -> list[str]:
        here = {x: n for x, n in counts.items() if _player(g, x)}
        top = max(here.values(), default=0)
        return [_name(g, x) for x, n in here.items() if n == top and top > 0]

    mystery = {a: sum(v) / len(v) for a, v in guessed_about.items() if _player(g, a)}
    least = min(mystery.values(), default=None)
    if least is not None and len(mystery) > 1 and all(v == least for v in mystery.values()):
        least = None  # tout le monde à égalité : ce n'est un prix pour personne
    ranking = sorted(({"name": p["name"], "pid": p["pid"], "score": S["scores"].get(p["id"], 0)} for p in g["players"]),
                     key=lambda x: -x["score"])
    return {"ranking": ranking, "sharp": best(found), "open": best(opened),
            "mystery": [_name(g, a) for a, v in mystery.items() if v == least] if least is not None else [],
            "questions": len(S["history"])}


def _public(rows: list[dict] | None) -> list[dict] | None:
    """Sans les identifiants secrets des joueurs (gid) : seuls les prénoms des masques levés sortent."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows] if rows is not None else None


def view(g: dict, gid: str, lead: bool) -> dict:
    S = state(g)
    me = _player(g, gid)
    q = S["q"]
    out = {"cats": S["cats"], "levels": S["levels"], "count": S["count"], "n": S["n"], "playing": bool(me),
           "cat_list": [{"id": k, "label": v, "size": sum(1 for c in MASQUE_CARDS if c[0] == k)} for k, v in CATS.items()],
           "level_list": [{"id": k, "label": v} for k, v in LEVELS.items()], "counts": list(COUNTS),
           "min_players": MIN_PLAYERS, "max_answer": MAX_ANSWER,
           "q": q and {**q, "cat_label": CATS[q["cat"]], "level_label": LEVELS[q["level"]]},
           "scores": [{"pid": p["pid"], "name": p["name"], "score": S["scores"].get(p["id"], 0)} for p in g["players"]]}
    if g["phase"] == "write":
        out["wrote"] = [{"pid": p["pid"], "name": p["name"], "done": p["id"] in S["answers"]} for p in g["players"]]
        out["mine"] = S["answers"].get(gid)
        out["can_show"] = lead and len(S["answers"]) >= MIN_PLAYERS
    if g["phase"] == "guess":
        mine = _mine(S, gid)
        # Les réponses sans leur auteur : chacun ne connaît que la sienne (il l'a écrite).
        out["slots"] = [{"i": i, "text": None if i in S["hidden"] else s["text"], "hidden": i in S["hidden"], "mine": i == mine}
                        for i, s in enumerate(S["slots"])]
        out["authors"] = [{"pid": a["pid"], "name": a["name"]} for a in S.get("authors") or [] if a["gid"] != gid]
        out["sent"] = bool(S["sent"].get(gid))
        out["has_answer"] = mine is not None and mine not in S["hidden"]  # réponse retirée : plus de masque à choisir
        expected = set(S.get("guessers") or [])
        out["progress"] = [{"pid": p["pid"], "name": p["name"], "done": bool(S["sent"].get(p["id"]))} for p in g["players"]
                           if not expected or p["id"] in expected]
        out["late"] = bool(me) and bool(expected) and gid not in expected
        out["can_reveal"] = lead and any(S["sent"].values())
    if g["phase"] == "reveal":
        out["result"] = _public(S["result"])
        # Ses devinettes justes, sur les masques levés seulement : un masque gardé ne confirme rien, même à qui a vu juste.
        mine = S["guesses"].get(gid, {})
        out["my_hits"] = [i for i, s in enumerate(S["slots"]) if mine.get(str(i)) == s["gid"] and i not in S["hidden"]
                          and S["unmask"].get(s["gid"])]
    if g["phase"] == "end":
        out["summary"] = summary(g)
        out["history"] = [{"q": h["q"], "rows": _public(h["rows"])} for h in S["history"]]
    return out


def summary_facts(g: dict) -> list[str]:
    S = state(g)
    if not S["history"]:
        return []
    s = summary(g)
    facts = [f"{s['questions']} question(s) posée(s)"]
    if s["sharp"]:
        facts.append("Le plus perspicace : " + ", ".join(s["sharp"]))
    if s["open"]:
        facts.append("Livre ouvert : " + ", ".join(s["open"]))
    return facts
