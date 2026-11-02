"""Beer pong — la vraie table, l'app pour les sentences.

On joue avec de vrais gobelets : l'app ne gère pas les tours (chaque table a ses règles). L'animateur, ou le
marqueur qu'il désigne, touche le gobelet qui vient de tomber et la personne qui l'a perdu ; l'app propose trois
sentences tirées des familles cochées (gorgées, shot, gage, question WTF, question de quiz, sport, bonus, malus),
il en choisit une (ou en retire trois autres). L'équipe qui n'a plus de gobelets a perdu.

Module autonome et testable (mêmes conventions que likely.py) : il ne connaît que la partie `g` ; les droits
d'animateur restent dans main.py.
"""
import random

from . import quizbank as qb
from .debate_questions import WTF

TEAMS = ("red", "blue")
TEAM_NAMES = {"red": "Rouges", "blue": "Bleus"}
CUPS = (6, 10, 15)
PROPOSALS = 3
LOG_SIZE = 30
SHOT_SIPS = 3  # un shot compte comme 3 gorgées au tableau

KINDS: dict[str, str] = {
    "sips": "🍺 Gorgées", "shot": "🥃 Shot", "dare": "🎭 Gage", "wtf": "🤪 Question WTF", "quiz": "🧠 Quiz",
    "sport": "💪 Sport", "bonus": "🎁 Bonus", "malus": "💣 Malus",
}
DEFAULT_KINDS = list(KINDS)

DARES = [
    "Imite un animal choisi par l'équipe adverse pendant 15 secondes",
    "Parle avec un accent jusqu'au prochain gobelet",
    "Fais un compliment sincère à chaque joueur adverse",
    "Chante le refrain de la chanson en cours",
    "Danse 20 secondes sur la musique",
    "Joue le prochain tir avec ta main faible",
    "Garde les yeux fermés pendant le prochain tir de ton équipe",
    "Raconte ta pire honte en 30 secondes",
    "Fais ta meilleure imitation de quelqu'un de la soirée",
    "Échange un vêtement avec un joueur adverse jusqu'à la fin",
    "Fais un discours de victoire comme si ton équipe avait gagné",
    "Tire le prochain coup en sautant",
]
SPORT = [
    "10 pompes", "15 abdos", "20 squats", "30 secondes de gainage", "10 burpees", "20 jumping jacks",
    "Chaise contre le mur 30 secondes", "10 fentes par jambe", "15 pompes sur les genoux", "Planche latérale 20 secondes",
]
BONUS = [
    ("Le gobelet revient sur la table !", "cup_back"),
    ("Joker : la prochaine sentence de ton équipe est annulée", "joker"),
    ("Tu choisis qui boit 2 gorgées en face", "give2"),
]
MALUS = [
    ("Un gobelet de plus tombe !", "cup_off"),
    ("Toute ton équipe boit 1 gorgée", "team_sip"),
    ("Tu joues le prochain tir dos à la table", "back"),
]


class BeerPongError(Exception):
    pass


def init(g: dict):
    g["bp"] = {"cups": 10, "kinds": list(DEFAULT_KINDS), "teams": {}, "racks": {t: [] for t in TEAMS},
               "pending": None, "last": None, "log": [], "winner": None, "marker": None, "n": 0,
               "jokers": {t: 0 for t in TEAMS}}


def _pid_gid(g: dict, pid: str) -> str | None:
    return next((p["id"] for p in g["players"] if p["pid"] == pid), None)


def configure(g: dict, s: dict):
    """Réglages avant la partie : nombre de gobelets, équipe d'un joueur, mélange ; et ceux modifiables en jeu."""
    B = g["bp"]
    if ("cups" in s or "team" in s or s.get("shuffle")) and g["phase"] != "lobby":
        raise BeerPongError("La partie a commencé")
    if "cups" in s:
        if s["cups"] not in CUPS:
            raise BeerPongError("Nombre de gobelets : 6, 10 ou 15")
        B["cups"] = s["cups"]
    if "team" in s:
        team_set = s["team"] if isinstance(s["team"], dict) else {}
        gid = _pid_gid(g, team_set.get("pid") or "")
        if not gid or team_set.get("team") not in TEAMS:
            raise BeerPongError("Joueur ou équipe inconnu")
        B["teams"][gid] = team_set["team"]
    if s.get("shuffle"):
        B["teams"] = {}
        _balance(g, random.Random())
    configure_live(g, s)


def configure_live(g: dict, s: dict):
    """Réglages modifiables en jeu : familles de sentences, marqueur."""
    B = g["bp"]
    if "kinds" in s:
        kinds = [k for k in s["kinds"] if k in KINDS] if isinstance(s["kinds"], list) else []
        if not kinds:
            raise BeerPongError("Garde au moins une famille de sentences")
        B["kinds"] = kinds
    if "marker" in s:
        B["marker"] = _pid_gid(g, s["marker"]) if s["marker"] else None


def _balance(g: dict, rng):
    """Chaque joueur sans équipe va dans la plus petite (au hasard à égalité)."""
    B = g["bp"]
    present = {p["id"] for p in g["players"]}
    B["teams"] = {gid: t for gid, t in B["teams"].items() if gid in present}
    free = [p["id"] for p in g["players"] if p["id"] not in B["teams"]]
    rng.shuffle(free)
    for gid in free:
        sizes = {t: sum(1 for x in B["teams"].values() if x == t) for t in TEAMS}
        smallest = min(sizes.values())
        B["teams"][gid] = rng.choice([t for t in TEAMS if sizes[t] == smallest])


def start(g: dict, rng=random):
    B = g["bp"]
    if len(g["players"]) < 2:
        raise BeerPongError("Il faut au moins 2 joueurs")
    _balance(g, rng)
    if len(set(B["teams"].values())) < 2:
        raise BeerPongError("Il faut quelqu'un dans chaque équipe")
    B.update(racks={t: [True] * B["cups"] for t in TEAMS}, pending=None, last=None, log=[], winner=None, n=0,
             jokers={t: 0 for t in TEAMS})
    g["phase"] = "play"


def join_late(g: dict, rng=random):
    """Un joueur qui arrive (ou repart) : les équipes se rééquilibrent sans bouger ceux qui en ont une."""
    if "bp" in g:
        _balance(g, rng)


def _proposal(kind: str, rng) -> dict:
    if kind == "sips":
        n = rng.choice([1, 2, 2, 3, 3, 4])
        return {"kind": kind, "text": f"Bois {n} gorgée{'s' if n > 1 else ''}", "sips": n}
    if kind == "shot":
        return {"kind": kind, "text": "Cul sec : un shot !", "shot": True}
    if kind == "dare":
        return {"kind": kind, "text": rng.choice(DARES)}
    if kind == "wtf":
        return {"kind": kind, "text": rng.choice(WTF)}
    if kind == "quiz":
        q = rng.choice(rng.choice([b for b in qb.BANK.values() if b]))
        return {"kind": kind, "text": q["q"], "answer": q["a"], "hint": "Mauvaise réponse : 2 gorgées"}
    if kind == "sport":
        return {"kind": kind, "text": rng.choice(SPORT)}
    text, effect = rng.choice(BONUS if kind == "bonus" else MALUS)
    return {"kind": kind, "text": text, "effect": effect}


def _proposals(g: dict, rng) -> list[dict]:
    kinds = list(g["bp"]["kinds"])
    rng.shuffle(kinds)
    while len(kinds) < PROPOSALS:
        kinds.append(rng.choice(g["bp"]["kinds"]))
    return [_proposal(k, rng) for k in kinds[:PROPOSALS]]


def _alive(B: dict, team: str) -> int:
    return sum(1 for up in B["racks"][team] if up)


def hit(g: dict, team: str, cup: int, pid: str, rng=random):
    """Le gobelet `cup` de l'équipe `team` est tombé ; `pid` (de cette équipe) l'a perdu : trois sentences au choix."""
    B = g["bp"]
    if g["phase"] != "play":
        raise BeerPongError("La partie n'est pas en cours")
    if B["pending"]:
        raise BeerPongError("Choisis d'abord la sentence du gobelet précédent")
    if team not in TEAMS or not isinstance(cup, int) or not 0 <= cup < len(B["racks"][team]):
        raise BeerPongError("Gobelet inconnu")
    if not B["racks"][team][cup]:
        raise BeerPongError("Ce gobelet est déjà tombé")
    gid = _pid_gid(g, pid or "")
    if not gid or B["teams"].get(gid) != team:
        raise BeerPongError("Choisis un joueur de cette équipe")
    B["racks"][team][cup] = False
    B["pending"] = {"team": team, "cup": cup, "gid": gid, "options": _proposals(g, rng)}


def reroll(g: dict, rng=random):
    B = g["bp"]
    if not B["pending"]:
        raise BeerPongError("Aucun gobelet en attente")
    B["pending"]["options"] = _proposals(g, rng)


def undo(g: dict):
    """Le dernier gobelet marqué remonte (erreur de saisie)."""
    B = g["bp"]
    if not B["pending"]:
        raise BeerPongError("Rien à annuler")
    B["racks"][B["pending"]["team"]][B["pending"]["cup"]] = True
    B["pending"] = None


def _apply(g: dict, opt: dict, team: str, gid: str, cup: int, rng):
    from .games import add_sips, player  # import tardif : games importe ce module

    B = g["bp"]
    if opt["kind"] == "sips":
        add_sips(g, gid, drink=opt.get("sips", 1))
    elif opt["kind"] == "shot":
        add_sips(g, gid, drink=SHOT_SIPS)
    effect = opt.get("effect")
    if effect == "cup_back":
        B["racks"][team][cup] = True
    elif effect == "cup_off":
        standing = [i for i, up in enumerate(B["racks"][team]) if up]
        if standing:
            B["racks"][team][rng.choice(standing)] = False
    elif effect == "team_sip":
        for mate, t in B["teams"].items():
            if t == team and player(g, mate):
                add_sips(g, mate, drink=1)
    elif effect == "joker":
        B["jokers"][team] += 1


def sentence(g: dict, choice: int, rng=random):
    """La sentence choisie s'applique : gorgées et shots comptés, bonus et malus sur les gobelets."""
    from .games import player

    B = g["bp"]
    P = B["pending"]
    if not P:
        raise BeerPongError("Aucun gobelet en attente")
    if not isinstance(choice, int) or not 0 <= choice < len(P["options"]):
        raise BeerPongError("Sentence inconnue")
    opt = P["options"][choice]
    team, gid = P["team"], P["gid"]
    p = player(g, gid) or {}
    _apply(g, opt, team, gid, P["cup"], rng)
    B["n"] += 1
    B["last"] = {"n": B["n"], "team": team, "name": p.get("name", "?"), "pid": p.get("pid"), **opt}
    B["log"] = (B["log"] + [{"n": B["n"], "team": team, "name": p.get("name", "?"), "cup": P["cup"],
                             "kind": opt["kind"], "text": opt["text"]}])[-LOG_SIZE:]
    B["pending"] = None
    for t in TEAMS:
        if _alive(B, t) == 0:
            B["winner"] = "blue" if t == "red" else "red"
            g["phase"] = "end"


def view(g: dict, gid: str, lead: bool = False) -> dict:
    B = g["bp"]
    pending = B["pending"]
    pend_player = next((p for p in g["players"] if pending and p["id"] == pending["gid"]), {})
    return {
        "cups": B["cups"], "cup_choices": list(CUPS), "kinds": B["kinds"],
        "kind_list": [{"id": k, "label": v} for k, v in KINDS.items()],
        "racks": B["racks"], "alive": {t: _alive(B, t) for t in TEAMS}, "team_names": TEAM_NAMES,
        "players": [{"pid": p["pid"], "name": p["name"], "team": B["teams"].get(p["id"]), "me": p["id"] == gid}
                    for p in g["players"]],
        "my_team": B["teams"].get(gid),
        "marker": next((p["pid"] for p in g["players"] if p["id"] == B["marker"]), None),
        "can_mark": lead or (bool(gid) and gid == B["marker"]),
        "pending": None if not pending else {"team": pending["team"], "cup": pending["cup"], "name": pend_player.get("name", "?"),
                                             "pid": pend_player.get("pid"), "options": pending["options"]},
        "last": B["last"], "log": list(reversed(B["log"][-8:])), "winner": B["winner"], "jokers": B["jokers"],
    }
