"""« Le Reflet » — te vois-tu comme les autres te voient ?

À tour de rôle, un joueur est « devant le miroir » : il choisit une affirmation sur lui-même parmi trois (« On me
confie facilement ses secrets ») et parie en secret combien d'amis seront d'accord. Les autres votent oui ou non,
anonymement, chacun sur son téléphone. La révélation : le compteur des « oui » monte, puis l'écart avec le pari.
Ensuite, qui veut dit pourquoi. Points : pari exact 3, à un près 1. Fin après un ou deux passages devant le miroir.

Votes toujours anonymes : seul le nombre de « oui » sort, jamais qui a voté quoi.

Module autonome et testable (mêmes conventions que debate.py) : il ne connaît que la partie `g` ; les droits
d'animateur restent dans main.py, et tout passe par le verrou unique des jeux.
"""
import random

from .masque_cards import REFLET_CARDS

CHOICES = 3  # affirmations proposées à qui est devant le miroir
TURNS = (1, 2)  # passages devant le miroir par joueur
MIN_PLAYERS = 4  # au moins trois votants : à deux, chacun déduirait le vote de l'autre
MIN_VOTES = 2  # en dessous, le décompte dévoilerait le vote du seul votant : il n'est pas publié
POINT_EXACT, POINT_CLOSE = 3, 1


class RefletError(ValueError):
    """Message affiché tel quel au joueur."""


def state(g: dict) -> dict:
    return g.setdefault("reflet", {
        "turns": TURNS[0], "used": [], "seat": -1, "passes": {}, "options": [], "card": None, "bet": None,
        "votes": {}, "skipped": [], "result": None, "scores": {}, "history": [], "swapped": False,
    })


def init(g: dict):
    state(g)


def _player(g: dict, gid: str) -> dict | None:
    return next((p for p in g["players"] if p["id"] == gid), None)


def configure(g: dict, settings: dict):
    S = state(g)
    if g["phase"] not in ("lobby", "end"):
        raise RefletError("Les réglages se changent avant la partie")
    turns = settings.get("turns", S["turns"])
    if isinstance(turns, bool) or not isinstance(turns, int) or turns not in TURNS:
        raise RefletError("Nombre de passages inconnu")
    S["turns"] = turns


def _total_turns(g: dict) -> int:
    return state(g)["turns"] * len(g["players"])


def _done_turns(g: dict) -> int:
    """Passages faits par les joueurs encore là (un joueur parti ne compte plus, un nouveau venu a les siens à faire)."""
    S = state(g)
    return sum(min(S["passes"].get(p["id"], 0), S["turns"]) for p in g["players"])


def start(g: dict, rng=random):
    if len(g["players"]) < MIN_PLAYERS:
        raise RefletError(f"Il faut au moins {MIN_PLAYERS} joueurs")
    S = state(g)
    S.update(seat=-1, passes={}, scores={}, history=[], result=None)
    _next_seat(g, rng)


def _draw(S: dict, rng, k: int) -> list[int]:
    fresh = [i for i in range(len(REFLET_CARDS)) if i not in S["used"]]
    if len(fresh) < k:  # paquet épuisé : on le remélange
        S["used"] = []
        fresh = list(range(len(REFLET_CARDS)))
    picks = rng.sample(fresh, k)
    light = [i for i in fresh if REFLET_CARDS[i][0] == "leger" and i not in picks]
    if light and not any(REFLET_CARDS[i][0] == "leger" for i in picks):
        picks[-1] = rng.choice(light)  # toujours une porte de sortie légère parmi les trois
    S["used"].extend(picks)
    return picks


def _next_seat(g: dict, rng=random):
    """Le prochain joueur, dans l'ordre de la table, qui n'a pas fait tous ses passages ; sinon, le bilan. Ainsi
    personne ne passe deux fois de trop ni jamais, même si des joueurs arrivent ou partent en cours de partie."""
    S = state(g)
    n = len(g["players"])
    order = [(S["seat"] + k) % n for k in range(1, n + 1)] if n else []
    seat = next((i for i in order if S["passes"].get(g["players"][i]["id"], 0) < S["turns"]), None)
    if seat is None:
        g["phase"] = "end"
        return
    S["seat"] = seat
    S.update(options=_draw(S, rng, CHOICES), card=None, bet=None, votes={}, skipped=[], result=None, swapped=False,
             electors=None)
    g["phase"] = "pick"
    g["round"] = g.get("round", 0) + 1


def mirror(g: dict) -> dict | None:
    S = state(g)
    return g["players"][S["seat"]] if 0 <= S["seat"] < len(g["players"]) else None


def _voters(g: dict) -> list[dict]:
    """Ceux qui votent : tous sauf le joueur devant le miroir ; une fois le pari fait, seulement ceux d'alors."""
    S = state(g)
    m = mirror(g)
    out = [p for p in g["players"] if not m or p["id"] != m["id"]]
    if g["phase"] in ("vote", "result") and S.get("electors") is not None:
        out = [p for p in out if p["id"] in S["electors"]]
    return out


def pick(g: dict, gid: str, index, bet):
    """Qui est devant le miroir choisit son affirmation et parie (en secret) le nombre de « oui »."""
    S = state(g)
    m = mirror(g)
    if g["phase"] != "pick" or not m or m["id"] != gid:
        raise RefletError("Ce n'est pas ton tour")
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (index, bet)):
        raise RefletError("Choix inconnu")
    if not 0 <= index < len(S["options"]):
        raise RefletError("Choix inconnu")
    if not 0 <= bet <= len(_voters(g)):
        raise RefletError(f"Parie entre 0 et {len(_voters(g))}")
    # Les votants sont ceux pour qui le pari a été fait : un retardataire votera au tour suivant.
    S.update(card=S["options"][index], bet=bet, electors=[p["id"] for p in _voters(g)])
    g["phase"] = "vote"


def swap(g: dict, gid: str, lead: bool, rng=random):
    """Trois autres affirmations, une fois par tour (qui est devant le miroir, ou l'animateur)."""
    S = state(g)
    m = mirror(g)
    if g["phase"] != "pick" or not m or (m["id"] != gid and not lead):
        raise RefletError("Pas maintenant")
    if S["swapped"]:
        raise RefletError("Une seule fois par tour")
    S.update(options=_draw(S, rng, CHOICES), swapped=True)


def vote(g: dict, gid: str, yes):
    S = state(g)
    m = mirror(g)
    if g["phase"] != "vote" or not _player(g, gid) or (m and m["id"] == gid):
        raise RefletError("Pas maintenant")
    if not any(p["id"] == gid for p in _voters(g)):
        raise RefletError("Tu voteras au prochain tour")
    if gid in S["votes"]:
        raise RefletError("Tu as déjà voté")
    S["votes"][gid] = bool(yes)
    _maybe_settle(g)


def skip(g: dict, target: str):
    """L'animateur n'attend plus un votant absent."""
    S = state(g)
    if g["phase"] != "vote" or not any(p["id"] == target for p in _voters(g)):
        raise RefletError("Pas maintenant")
    if target not in S["votes"] and target not in S["skipped"]:
        S["skipped"].append(target)
    _maybe_settle(g)


def _maybe_settle(g: dict):
    S = state(g)
    if all(p["id"] in S["votes"] or p["id"] in S["skipped"] for p in _voters(g)):
        settle(g)


def settle(g: dict):
    S = state(g)
    if g["phase"] != "vote":
        raise RefletError("Pas maintenant")
    m = mirror(g)
    voters = len(S["votes"])
    yes = sum(1 for v in S["votes"].values() if v) if voters >= MIN_VOTES else 0
    # Le pari se compare aux vrais votants : un absent passé compte comme « non » s'il avait été parié.
    gap = abs(S["bet"] - yes)
    # Trop peu de votes (votants passés ou partis) : rien n'est publié ni compté, l'anonymat passe avant le jeu.
    hidden = voters < MIN_VOTES
    points = 0 if hidden else POINT_EXACT if gap == 0 else POINT_CLOSE if gap == 1 else 0
    if m and points:
        S["scores"][m["id"]] = S["scores"].get(m["id"], 0) + points
    # Le nom et le pid du joueur devant le miroir restent dans le résultat : s'il part, rien ne glisse vers un autre.
    S["result"] = {"yes": yes, "no": 0 if hidden else voters - yes, "voters": 0 if hidden else voters, "bet": S["bet"],
                   "gap": 0 if hidden else gap, "points": points, "hidden": hidden,
                   "name": m["name"] if m else "?", "pid": m["pid"] if m else ""}
    S["history"].append({"gid": m["id"] if m else "", "text": REFLET_CARDS[S["card"]][1], **S["result"]})
    if m:
        S["passes"][m["id"]] = S["passes"].get(m["id"], 0) + 1
    g["phase"] = "result"


def next_step(g: dict, rng=random):
    S = state(g)
    if g["phase"] != "result":
        raise RefletError("Pas maintenant")
    _next_seat(g, rng)


def leave(g: dict, gid: str, index: int, rng=random):
    """Un joueur s'en va (il était à la place `index`, déjà retiré de la liste) : son vote disparaît, la place du
    miroir suit ; s'il était devant le miroir, le tour passe au suivant. À moins de deux joueurs, la partie s'arrête."""
    S = state(g)
    S["votes"].pop(gid, None)
    if gid in S["skipped"]:
        S["skipped"].remove(gid)
    if g["phase"] in ("lobby", "end"):
        return
    if len(g["players"]) < MIN_PLAYERS:
        g["phase"] = "end"  # à deux, un seul votant : son vote ne serait plus anonyme
        return
    was_mirror = index == S["seat"]
    if index <= S["seat"]:
        S["seat"] -= 1
    if was_mirror and g["phase"] in ("pick", "vote"):
        _next_seat(g, rng)
    elif g["phase"] == "vote":
        _maybe_settle(g)


def summary(g: dict) -> dict:
    S = state(g)
    here = {p["id"] for p in g["players"]}
    ranking = sorted(({"name": p["name"], "pid": p["pid"], "score": S["scores"].get(p["id"], 0)} for p in g["players"]),
                     key=lambda x: -x["score"])
    top = ranking[0]["score"] if ranking else 0
    hist = [h for h in S["history"] if h["gid"] in here]
    surprise = max(hist, key=lambda h: h["gap"], default=None)
    unanimous = [h for h in hist if h["voters"] and h["yes"] == h["voters"]]
    return {"ranking": ranking, "lucid": [r["name"] for r in ranking if r["score"] == top and top > 0],
            "surprise": surprise and {k: surprise[k] for k in ("name", "text", "yes", "voters", "bet", "gap")},
            "unanimous": [{"name": h["name"], "text": h["text"]} for h in unanimous][:5]}


def view(g: dict, gid: str, lead: bool) -> dict:
    S = state(g)
    m = mirror(g)
    mine = bool(m and m["id"] == gid)
    if g["phase"] == "result" and S["result"]:  # le joueur du résultat, même s'il est parti depuis
        shown = {"pid": S["result"]["pid"], "name": S["result"]["name"]}
    else:
        shown = m and {"pid": m["pid"], "name": m["name"]}
    out = {"turns": S["turns"], "turn_list": list(TURNS), "done_turns": _done_turns(g), "total": _total_turns(g),
           "playing": bool(_player(g, gid)), "min_players": MIN_PLAYERS,
           "mirror": shown, "is_mirror": mine and g["phase"] in ("pick", "vote"),
           "voters": len(_voters(g)),
           "scores": [{"pid": p["pid"], "name": p["name"], "score": S["scores"].get(p["id"], 0)} for p in g["players"]]}
    if g["phase"] == "pick":
        if mine:
            out["options"] = [REFLET_CARDS[i][1] for i in S["options"]]
            out["can_swap"] = not S["swapped"]
        out["can_swap_lead"] = lead and not S["swapped"]
    if g["phase"] in ("vote", "result") and S["card"] is not None:
        out["card"] = REFLET_CARDS[S["card"]][1]
    if g["phase"] == "vote":
        out["my_vote"] = gid in S["votes"]  # voté ou pas, jamais quoi : le vote est secret
        out["can_vote"] = any(p["id"] == gid for p in _voters(g)) and gid not in S["votes"]
        out["late"] = bool(_player(g, gid)) and not mine and not out["can_vote"] and gid not in S["votes"]
        out["waiting"] = [{"pid": p["pid"], "name": p["name"]} for p in _voters(g)
                          if p["id"] not in S["votes"] and p["id"] not in S["skipped"]]
        out["done"] = len(S["votes"])
        if mine:
            out["bet"] = S["bet"]
    if g["phase"] == "result":
        out["result"] = S["result"]
    if g["phase"] == "end":
        out["summary"] = summary(g)
    return out


def summary_facts(g: dict) -> list[str]:
    S = state(g)
    if not S["history"]:
        return []
    s = summary(g)
    facts = [f"{len(S['history'])} passage(s) devant le miroir"]
    if s["lucid"]:
        facts.append("Le plus lucide : " + ", ".join(s["lucid"]))
    return facts
