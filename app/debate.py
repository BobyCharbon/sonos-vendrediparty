"""« Pour ou contre » — un dilemme, chacun se place en secret sur une échelle de 5 crans.

Tous ceux qui ont leur téléphone votent en même temps ; les participants sans téléphone votent sur celui de
l'animateur, dans l'ordre de la table. Quand tout le monde a voté (ou a été passé), on révèle la répartition :
anonyme, ou avec les prénoms si l'animateur l'a choisi avant la partie. Le groupe débat librement, puis
l'animateur décide : faire revoter (une fois, pour voir qui a changé d'avis) ou passer au dilemme suivant.
Les joueurs proposent leurs propres dilemmes ; ceux que l'animateur valide passent avant ceux de la banque.
Pas de points ni de gorgées : après 10, 20 ou 30 dilemmes, un bilan (le plus divisant, le plus unanime, celui
qui a fait changer le plus d'avis).

Module autonome et testable (mêmes conventions que likely.py) : il ne connaît que la partie `g` ; les droits
d'animateur restent dans main.py.
"""
import random
from statistics import pstdev

from .debate_questions import LIGHT, MORAL, RELATIONS, SOCIETY

THEMES: dict[str, tuple[str, list[str]]] = {
    "moral": ("⚖️ Morale & dilemmes", MORAL),
    "society": ("🏛️ Société & débats", SOCIETY),
    "relations": ("💞 Relations & couple", RELATIONS),
    "light": ("🍍 Léger & absurde", LIGHT),
}
SCALE = ("Totalement contre", "Plutôt contre", "Partagé", "Plutôt pour", "Totalement pour")
CONTRE, PARTAGE, POUR = (0, 1), (2,), (3, 4)
COUNTS = (10, 20, 30)
DEFAULT_COUNT = 10
MIN_TEXT, MAX_TEXT = 10, 160  # longueur d'un dilemme proposé
MAX_PENDING = 20  # propositions en attente de validation, pour toute la partie
MAX_PENDING_PER_PLAYER = 3
MAX_QUEUE = 30  # dilemmes validés pas encore posés


class DebateError(Exception):
    pass


def state(g: dict) -> dict:
    return g["debate"]


def init(g: dict):
    g["debate"] = {"themes": list(THEMES), "count": DEFAULT_COUNT, "public": False, "used": [], "queue": [],
                   "proposals": [], "next_id": 1, "q": None, "n": 0, "round": 1, "voters": [], "votes": {},
                   "skipped": [], "first": None, "result": None, "history": []}


def configure(g: dict, settings: dict):
    """Réglages de l'animateur, avant la partie ou une fois finie (jamais en cours : passer en public trahirait
    des votes promis anonymes)."""
    if g["phase"] not in ("lobby", "end"):
        raise DebateError("Les réglages se changent avant de commencer")
    S = state(g)
    if "themes" in settings:
        themes = settings["themes"]
        if not isinstance(themes, list) or not themes or any(not isinstance(t, str) or t not in THEMES for t in themes):
            raise DebateError("Choisis au moins un thème")
        S["themes"] = [t for t in THEMES if t in themes]
    if "count" in settings:
        if type(settings["count"]) is not int or settings["count"] not in COUNTS:
            raise DebateError("Nombre de dilemmes inconnu")
        S["count"] = settings["count"]
    if "public" in settings:
        if not isinstance(settings["public"], bool):
            raise DebateError("Votes anonymes ou publics ?")
        S["public"] = settings["public"]


def start(g: dict, rng=random):
    """Nouvelle partie avec les mêmes joueurs : bilan remis à zéro, premier dilemme."""
    if len(g["players"]) < 2:
        raise DebateError("Il faut au moins 2 joueurs")
    S = state(g)
    S.update(n=0, history=[])
    _ask(g, rng)


def _draw(S: dict, rng, bank_only: bool = False) -> dict:
    """Un dilemme validé d'un joueur en priorité ; sinon un de la banque, jamais deux fois tant qu'il en reste."""
    if S["queue"] and not bank_only:
        return S["queue"].pop(0)
    pool = [(t, q) for t in S["themes"] for q in THEMES[t][1]]
    left = [x for x in pool if x[1] not in S["used"]]
    if not left:
        S["used"], left = [], pool
    theme, text = rng.choice(left)
    S["used"].append(text)
    return {"text": text, "theme": theme, "by": None}


def _ask(g: dict, rng, bank_only: bool = False):
    S = state(g)
    S.update(q=_draw(S, rng, bank_only), n=S["n"] + 1)
    _open_vote(g, 1)


def _open_vote(g: dict, round_no: int):
    S = state(g)
    S.update(round=round_no, voters=[p["id"] for p in g["players"]], votes={}, skipped=[], result=None)
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


def vote(g: dict, voter_id: str, value: int, by: str = ""):
    """Le votant se place sur l'échelle (0 = totalement contre … 4 = totalement pour). Vote secret et définitif.
    by : qui envoie le vote (un participant sans téléphone vote sur celui de l'animateur, à son tour)."""
    if g["phase"] != "ask":
        raise DebateError("Pas de vote en cours")
    if type(value) is not int or not 0 <= value < len(SCALE):
        raise DebateError("Choisis un cran sur l'échelle")
    if voter_id not in waiting(g):
        raise DebateError("Ton vote est déjà enregistré" if voter_id in state(g)["votes"] else "Tu ne votes pas pour ce dilemme")
    if voter_id in _manual(g):
        if voter_id != voter(g):
            raise DebateError("Ce n'est pas son tour : passe le téléphone dans l'ordre de la table")
    elif by and by != voter_id:
        raise DebateError("Cette personne vote sur son propre téléphone")
    state(g)["votes"][voter_id] = value
    settle(g)


def skip(g: dict, target: str = ""):
    """Un votant est absent : on le passe (par défaut, celui à qui revient le téléphone de l'animateur)."""
    current = target or voter(g)
    if not current or current not in waiting(g):
        raise DebateError("Personne à passer")
    state(g)["skipped"].append(current)
    settle(g)


def swap(g: dict, rng=random):
    """Autre dilemme (avant le premier vote du premier tour) : la même manche continue. Un dilemme proposé par un
    joueur n'est pas perdu : il repasse en fin de file et on tire celui-ci dans la banque."""
    S = state(g)
    if g["phase"] != "ask" or S["round"] != 1 or S["votes"]:
        raise DebateError("On ne change de dilemme qu'avant le premier vote")
    proposed = S["q"]["by"] is not None
    if proposed:
        S["queue"].append(S["q"])
    S["n"] -= 1
    _ask(g, rng, bank_only=proposed)


def _counts(values) -> list[int]:
    counts = [0] * len(SCALE)
    for v in values:
        counts[v] += 1
    return counts


def _spread(counts: list[int]) -> float:
    values = [i for i, c in enumerate(counts) for _ in range(c)]
    return pstdev(values) if len(values) > 1 else 0.0


def settle(g: dict):
    """Révèle la répartition dès qu'il ne reste plus personne à faire voter (vote, passage ou départ d'un joueur)."""
    if g["phase"] != "ask" or waiting(g):
        return
    S = state(g)
    here = _present(g)
    votes = {v: x for v, x in S["votes"].items() if v in here}
    counts = _counts(votes.values())
    # Prénoms figés à la révélation : un joueur qui part ensuite reste à sa place sur l'échelle (mode public).
    result = {"counts": counts, "votes": len(votes), "ballots": votes, "before": None, "moved": None,
              "names": [[p["name"] for p in g["players"] if votes.get(p["id"]) == i] for i in range(len(SCALE))]}
    if S["round"] == 2 and S["first"] is not None:
        first = {v: x for v, x in S["first"].items() if v in here}
        result["before"] = _counts(first.values())
        result["moved"] = sum(1 for v, x in votes.items() if v in first and first[v] != x)
    S["result"] = result
    entry = {"text": S["q"]["text"], "counts": counts, "spread": _spread(counts), "moved": result["moved"]}
    if S["round"] == 2 and S["history"]:
        if votes:  # le revote remplace le premier tour dans le bilan (sauf s'il s'est vidé, tout le monde parti)
            S["history"][-1] = entry
    else:
        S["history"].append(entry)
    g["phase"] = "reveal"


def revote(g: dict):
    """L'animateur fait revoter après le débat (une seule fois par dilemme)."""
    S = state(g)
    if g["phase"] != "reveal":
        raise DebateError("Termine d'abord le vote")
    if S["round"] != 1:
        raise DebateError("On ne revote qu'une fois par dilemme")
    S["first"] = dict(S["result"]["ballots"])
    _open_vote(g, 2)


def next_step(g: dict, rng=random):
    if g["phase"] != "reveal":
        raise DebateError("Termine d'abord le vote")
    S = state(g)
    S["first"] = None
    if S["n"] >= S["count"]:
        g["phase"] = "end"
    else:
        _ask(g, rng)


# ── Dilemmes proposés par les joueurs ──
def propose(g: dict, gid: str, text) -> int:
    """Un joueur propose un dilemme ; il attend la validation de l'animateur. Renvoie son numéro."""
    S = state(g)
    if gid not in _present(g):
        raise DebateError("Rejoins la partie pour proposer un dilemme")
    if not isinstance(text, str):
        raise DebateError("Écris ton dilemme")
    text = " ".join(text.split())
    if not MIN_TEXT <= len(text) <= MAX_TEXT:
        raise DebateError(f"Ton dilemme doit faire entre {MIN_TEXT} et {MAX_TEXT} caractères")
    if len(S["proposals"]) >= MAX_PENDING:
        raise DebateError("Trop de propositions en attente : l'animateur doit d'abord les trier")
    if sum(1 for p in S["proposals"] if p["gid"] == gid) >= MAX_PENDING_PER_PLAYER:
        raise DebateError(f"Tu as déjà {MAX_PENDING_PER_PLAYER} propositions en attente")
    pid = S["next_id"]
    S["next_id"] += 1
    S["proposals"].append({"id": pid, "gid": gid, "by": _name(g, gid), "text": text})
    return pid


def _take_proposal(g: dict, proposal_id) -> dict:
    S = state(g)
    found = next((p for p in S["proposals"] if type(proposal_id) is int and p["id"] == proposal_id), None)
    if not found:
        raise DebateError("Cette proposition n'existe plus")
    S["proposals"] = [p for p in S["proposals"] if p is not found]
    return found


def accept(g: dict, proposal_id):
    """L'animateur valide : le dilemme passera avant ceux de la banque."""
    S = state(g)
    if len(S["queue"]) >= MAX_QUEUE:
        raise DebateError("Assez de dilemmes validés pour l'instant")
    p = _take_proposal(g, proposal_id)
    S["queue"].append({"text": p["text"], "theme": None, "by": p["by"]})


def refuse(g: dict, proposal_id):
    _take_proposal(g, proposal_id)


# ── Vues ──
def _name(g: dict, gid: str) -> str:
    return next((p["name"] for p in g["players"] if p["id"] == gid), "?")


def _pid(g: dict, gid: str) -> str:
    return next((p["pid"] for p in g["players"] if p["id"] == gid), "")


def _result_view(g: dict) -> dict | None:
    S = state(g)
    res = S["result"]
    if not res or g["phase"] not in ("reveal", "end"):
        return None
    counts = res["counts"]
    return {"counts": counts, "votes": res["votes"], "names": res["names"] if S["public"] else None, "before": res["before"], "moved": res["moved"],
            "pour": sum(counts[i] for i in POUR), "contre": sum(counts[i] for i in CONTRE),
            "partage": sum(counts[i] for i in PARTAGE)}


def summary(g: dict) -> dict:
    """Bilan de fin : le dilemme le plus divisant, le plus unanime, celui qui a fait changer le plus d'avis."""
    rows = [h for h in state(g)["history"] if sum(h["counts"]) >= 2]
    divisive = max(rows, key=lambda h: h["spread"], default=None)
    calm = [h for h in rows if h is not divisive] or rows
    unanimous = min(calm, key=lambda h: h["spread"], default=None)
    moved = max((h for h in state(g)["history"] if h["moved"]), key=lambda h: h["moved"], default=None)
    return {"divisive": _public_entry(divisive), "unanimous": _public_entry(unanimous), "moved": _public_entry(moved)}


def _public_entry(h: dict | None) -> dict | None:
    return {"text": h["text"], "counts": h["counts"], "moved": h["moved"]} if h else None


def view(g: dict, gid: str, lead: bool = False) -> dict:
    """Ce qu'affiche le téléphone : le dilemme, s'il peut voter, à qui passer celui de l'animateur, puis la
    répartition (avec les prénoms seulement en mode public)."""
    S = state(g)
    current = voter(g)
    left = waiting(g)
    manual = _manual(g)
    here = _present(g)
    voters = [v for v in S["voters"] if v in here]
    q = S["q"]
    end = g["phase"] == "end"
    return {"themes": S["themes"], "count": S["count"], "counts": list(COUNTS), "public": S["public"],
            "theme_list": [{"id": k, "label": label, "size": len(qs)} for k, (label, qs) in THEMES.items()],
            "scale": list(SCALE), "n": S["n"], "round": S["round"],
            "q": {"text": q["text"], "theme": THEMES[q["theme"]][0] if q["theme"] else None, "by": q["by"]} if q else None,
            "voter": {"pid": _pid(g, current), "name": _name(g, current)} if current else None,
            "can_vote": gid in left and gid not in manual,
            "mine": S["votes"].get(gid) if g["phase"] in ("ask", "reveal") and gid not in manual else None,
            "waiting": [{"pid": _pid(g, v), "name": _name(g, v), "manual": v in manual} for v in left],
            "voted": len([v for v in S["votes"] if v in here]), "total": len(voters),
            "done": [_pid(g, v) for v in voters if v in S["votes"] or v in S["skipped"]],
            "result": _result_view(g),
            "proposals": [{"id": p["id"], "by": p["by"], "text": p["text"]} for p in S["proposals"]] if lead else [],
            "my_pending": sum(1 for p in S["proposals"] if p["gid"] == gid), "queued": len(S["queue"]),
            "max_text": MAX_TEXT, "min_text": MIN_TEXT,
            "history": [_public_entry(h) for h in S["history"]] if end else [],
            "summary": summary(g) if end else None}


def summary_facts(g: dict) -> list[str]:
    S = state(g)
    facts = [" + ".join(THEMES[t][0] for t in S["themes"])]
    facts.append(f"Dilemme {S['n']}/{S['count']}" if g["phase"] in ("ask", "reveal") else f"{S['count']} dilemmes")
    facts.append("Votes publics (prénoms affichés)" if S["public"] else "Votes anonymes")
    if S["proposals"]:
        facts.append(f"{len(S['proposals'])} proposition(s) à valider")
    return facts
