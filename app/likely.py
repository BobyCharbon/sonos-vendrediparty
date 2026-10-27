"""« Qui est le plus… ? » — chacun désigne quelqu'un en secret (soi-même compris).

Une question s'affiche ; tous ceux qui ont leur téléphone votent en même temps, chacun sur le sien, une seule fois.
Les participants sans téléphone (ajoutés à la main) votent sur le téléphone de l'animateur, qu'on leur passe dans
l'ordre de la table. Quand tout le monde a voté (ou a été passé), on révèle la personne la plus désignée : elle prend
un point, ou boit ses gorgées si l'option alcool est active. En cas d'égalité, tous les ex æquo sont désignés.
Après le nombre de questions choisi, podium de la partie. Qui a voté pour qui n'est jamais montré.

Module autonome et testable (mêmes conventions que quiz.py et purity.py) : il ne connaît que la partie `g` ;
les gorgées, l'ordre des joueurs et les droits d'animateur restent dans games.py et main.py.
"""
import random

from .likely_questions import FAMILY, FRIENDS

PACKS: dict[str, tuple[str, list[str]]] = {
    "family": ("👨‍👩‍👧 Tous publics", FAMILY),
    "friends": ("😏 Entre amis", FRIENDS),
}
COUNTS = (10, 20, 30)
DEFAULT_COUNT = 20
MAX_SIPS = 3  # gorgées pour la personne désignée (0 = un point, sans alcool)


class LikelyError(Exception):
    pass


def state(g: dict) -> dict:
    return g["likely"]


def init(g: dict):
    g["likely"] = {"packs": ["family"], "count": DEFAULT_COUNT, "used": [], "q": None, "n": 0,
                   "voters": [], "votes": {}, "skipped": [], "result": None, "scores": {}, "history": []}


def configure(g: dict, settings: dict):
    """Réglages de l'animateur (avant la première question ou une fois la partie finie)."""
    if g["phase"] not in ("lobby", "end"):
        raise LikelyError("Les réglages se changent avant de commencer")
    S = state(g)
    if "packs" in settings:
        packs = settings["packs"]
        if not isinstance(packs, list) or not packs or any(p not in PACKS for p in packs):
            raise LikelyError("Choisis au moins un paquet de questions")
        S["packs"] = [p for p in PACKS if p in packs]
    if "count" in settings:
        if settings["count"] not in COUNTS:
            raise LikelyError("Nombre de questions inconnu")
        S["count"] = settings["count"]
    if "sips" in settings:
        sips = settings["sips"]
        if not isinstance(sips, int) or not 0 <= sips <= MAX_SIPS:
            raise LikelyError(f"Entre 0 et {MAX_SIPS} gorgées")
        g["options"]["sips"] = sips


def start(g: dict, rng=random):
    """Nouvelle partie avec les mêmes joueurs : scores remis à zéro, première question."""
    if len(g["players"]) < 2:
        raise LikelyError("Il faut au moins 2 joueurs")
    S = state(g)
    S.update(n=0, scores={}, history=[])
    _ask(g, rng)


def _pool(S: dict) -> list[str]:
    return [q for p in S["packs"] for q in PACKS[p][1]]


def _ask(g: dict, rng):
    """Question suivante : jamais une déjà posée tant que le paquet n'est pas épuisé."""
    S = state(g)
    pool = _pool(S)
    left = [q for q in pool if q not in S["used"]] or pool
    q = rng.choice(left)
    S["used"] = (S["used"] + [q])[-(len(pool) - 1):]
    S.update(q=q, n=S["n"] + 1, voters=[p["id"] for p in g["players"]], votes={}, skipped=[], result=None)
    g["phase"], g["round"] = "ask", S["n"]


def _present(g: dict) -> set[str]:
    return {p["id"] for p in g["players"]}


def _manual(g: dict) -> set[str]:
    return {p["id"] for p in g["players"] if p.get("manual")}


def waiting(g: dict) -> list[str]:
    """Ceux qui n'ont encore ni voté ni été passés, dans l'ordre de la table."""
    S = state(g)
    if g["phase"] != "ask":
        return []
    here = _present(g)
    return [v for v in S["voters"] if v in here and v not in S["votes"] and v not in S["skipped"]]


def voter(g: dict) -> str | None:
    """À qui passer le téléphone de l'animateur : le premier participant sans téléphone qui n'a pas encore voté."""
    manual = _manual(g)
    return next((v for v in waiting(g) if v in manual), None)


def vote(g: dict, voter_id: str, target: str, by: str = "") -> list[str]:
    """Le votant désigne quelqu'un ; renvoie les personnes désignées si c'était le dernier vote (sinon []).
    by : qui envoie le vote. Un participant sans téléphone vote sur le téléphone de l'animateur, à son tour ;
    un joueur qui a son téléphone ne vote que sur le sien."""
    if g["phase"] != "ask":
        raise LikelyError("Pas de vote en cours")
    if voter_id not in waiting(g):
        raise LikelyError("Ton vote est déjà enregistré" if voter_id in state(g)["votes"] else "Tu ne votes pas pour cette question")
    if voter_id in _manual(g):
        if voter_id != voter(g):
            raise LikelyError("Ce n'est pas son tour : passe le téléphone dans l'ordre de la table")
    elif by and by != voter_id:
        raise LikelyError("Cette personne vote sur son propre téléphone")
    if target not in _present(g):
        raise LikelyError("Choisis quelqu'un autour de la table")
    state(g)["votes"][voter_id] = target
    return settle(g)


def skip(g: dict, target: str = "") -> list[str]:
    """Un votant est absent : on le passe (par défaut, celui à qui revient le téléphone de l'animateur)."""
    current = target or voter(g)
    if not current or current not in waiting(g):
        raise LikelyError("Personne à passer")
    state(g)["skipped"].append(current)
    return settle(g)


def swap(g: dict, rng=random):
    """Autre question (avant le premier vote) : la même manche continue."""
    S = state(g)
    if g["phase"] != "ask" or S["votes"]:
        raise LikelyError("On ne change de question qu'avant le premier vote")
    S["n"] -= 1
    _ask(g, rng)


def settle(g: dict) -> list[str]:
    """Révèle le résultat dès qu'il ne reste plus personne à faire voter (vote, passage ou départ d'un joueur)."""
    if g["phase"] != "ask" or waiting(g):
        return []
    S = state(g)
    here = _present(g)
    counts: dict[str, int] = {}
    for v, t in S["votes"].items():
        if v in here and t in here:
            counts[t] = counts.get(t, 0) + 1
    top = max(counts.values(), default=0)
    winners = [p["id"] for p in g["players"] if top and counts.get(p["id"]) == top]
    for w in winners:
        S["scores"][w] = S["scores"].get(w, 0) + 1
    S["result"] = {"counts": counts, "winners": winners, "votes": sum(counts.values())}
    S["history"].append({"q": S["q"], "winners": [_name(g, w) for w in winners]})
    g["phase"] = "reveal"
    return winners


def next_step(g: dict, rng=random):
    if g["phase"] != "reveal":
        raise LikelyError("Termine d'abord le vote")
    S = state(g)
    if S["n"] >= S["count"]:
        g["phase"] = "end"
    else:
        _ask(g, rng)


def _name(g: dict, gid: str) -> str:
    return next((p["name"] for p in g["players"] if p["id"] == gid), "?")


def _pid(g: dict, gid: str) -> str:
    return next((p["pid"] for p in g["players"] if p["id"] == gid), "")


def board(g: dict) -> list[dict]:
    """Classement : du plus désigné au moins désigné (identifiants publics seulement)."""
    S = state(g)
    rows = [{"pid": p["pid"], "name": p["name"], "pts": S["scores"].get(p["id"], 0)} for p in g["players"]]
    return sorted(rows, key=lambda r: -r["pts"])


def view(g: dict, gid: str) -> dict:
    """Ce qu'affiche le téléphone : la question, s'il peut voter, à qui passer celui de l'animateur, puis le décompte
    (jamais les bulletins)."""
    S = state(g)
    current = voter(g)
    left = waiting(g)
    manual = _manual(g)
    res = S["result"]
    result = None
    if res and g["phase"] in ("reveal", "end"):
        rows = sorted(({"pid": _pid(g, t), "name": _name(g, t), "count": c} for t, c in res["counts"].items() if _pid(g, t)),
                      key=lambda r: -r["count"])
        result = {"rows": rows, "votes": res["votes"],
                  "winners": [{"pid": _pid(g, w), "name": _name(g, w)} for w in res["winners"] if _pid(g, w)]}
    here = _present(g)
    voters = [v for v in S["voters"] if v in here]
    return {"packs": S["packs"], "pack_list": [{"id": k, "label": label, "size": len(qs)} for k, (label, qs) in PACKS.items()],
            "count": S["count"], "counts": list(COUNTS), "max_sips": MAX_SIPS, "q": S["q"], "n": S["n"],
            "voter": {"pid": _pid(g, current), "name": _name(g, current)} if current else None,
            "can_vote": gid in left and gid not in manual,
            "waiting": [{"pid": _pid(g, v), "name": _name(g, v), "manual": v in manual} for v in left],
            "voted": len([v for v in S["votes"] if v in here]), "total": len(voters),
            "done": [_pid(g, v) for v in voters if v in S["votes"] or v in S["skipped"]],
            "result": result, "scores": board(g), "history": S["history"] if g["phase"] == "end" else []}


def summary_facts(g: dict) -> list[str]:
    S = state(g)
    facts = [" + ".join(PACKS[p][0] for p in S["packs"])]
    if g["phase"] in ("ask", "reveal"):
        facts.append(f"Question {S['n']}/{S['count']}")
    else:
        facts.append(f"{S['count']} questions")
    return facts


def winner_name(g: dict) -> str | None:
    rows = board(g)
    return rows[0]["name"] if rows and rows[0]["pts"] else None
