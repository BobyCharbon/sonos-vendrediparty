"""Président : paquet privé de 54 cartes, plis, classement et échanges.

Les identifiants des cartes sont stables dans une donne. Seule view() sort vers
le navigateur ; ni l'animateur ni un spectateur ne reçoit les mains adverses.
"""
import random
import secrets
from functools import wraps

RANKS = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
SUITS = {"C": ("♣", "trèfle"), "D": ("♦", "carreau"), "H": ("♥", "cœur"), "S": ("♠", "pique")}
FACES = {"J": "Valet", "Q": "Dame", "K": "Roi", "A": "As"}
from .game_lock import LOCK  # verrou commun à toutes les parties (voir game_lock.py)


class PresidentError(Exception):
    pass


def serialized(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        with LOCK:
            return fn(*args, **kwargs)
    return call


def deck():
    return [rank + suit for rank in RANKS for suit in SUITS] + ["JK1", "JK2"]


def rank(card):
    return 0 if card.startswith("JK") else RANKS.index(card[:-1])


def card_view(card):
    if card.startswith("JK"):
        return {"id": card, "rank": "Joker", "value": 0, "suit": "", "red": card == "JK2", "joker": True,
                "label": "Joker " + ("rouge" if card == "JK2" else "noir")}
    face, suit = card[:-1], card[-1]
    return {"id": card, "rank": face, "value": rank(card), "suit": SUITS[suit][0], "red": suit in "DH", "joker": False,
            "label": FACES.get(face, face) + " de " + SUITS[suit][1]}


def role(pos, total):
    if pos == 0:
        return "Président"
    if pos == total - 1:
        return "Trou du cul"
    if total >= 4 and pos == 1:
        return "Vice-président"
    if total >= 4 and pos == total - 2:
        return "Vice-trou du cul"
    return "Neutre"


def _state(g):
    if g["type"] != "president" or not g.get("president", {}).get("hands"):
        raise PresidentError("Distribue d'abord les cartes")
    return g["president"]


def _name(g, gid):
    return next((p["name"] for p in g["players"] if p["id"] == gid), g.get("president", {}).get("names", {}).get(gid, "Joueur parti"))


def _active(s):
    return [i for i in s["seats"] if s["hands"].get(i) and i not in s["departed"]]


def _next(s, after):
    seats, active = s["seats"], _active(s)
    if not active:
        return None
    pos = seats.index(after) if after in seats else -1
    return next(seats[(pos + n) % len(seats)] for n in range(1, len(seats) + 1) if seats[(pos + n) % len(seats)] in active)


def _next_in_trick(s, after):
    """Joueur suivant pour ce pli : ceux qui ont passé en sont sortis jusqu'au prochain pli."""
    seats, live = s["seats"], [i for i in _active(s) if i not in s["passed"]]
    pos = seats.index(after) if after in seats else -1
    return next((seats[(pos + n) % len(seats)] for n in range(1, len(seats) + 1) if seats[(pos + n) % len(seats)] in live), None)


def _everyone_else_passed(s, author):
    return all(i == author or i in s["passed"] for i in _active(s))


def _touch(s):
    s["revision"] += 1


def _token(s):
    return f"{s['deal']}:{s['revision']}"


def _clear(g):
    s = g["president"]
    leader = s["pile"]["by"]
    s["discard"].extend(s["pile"]["cards"])
    s["pile"], s["passed"], s["trail"] = None, [], []
    s["turn"] = leader if leader in _active(s) else _next(s, leader)
    s["trick"] += 1
    s["notice"] = f"Pli remporté par {_name(g, leader)}. {_name(g, s['turn'])} ouvre le suivant."


def _finish_if_needed(g):
    s = g["president"]
    active = _active(s)
    if len(active) > 1:
        return False
    # Classement : ceux qui ont fini normalement, le dernier en jeu, ceux qui ont fini sur un 2 (le plus récent
    # tout en bas : il pousse l'ancien Trou du cul d'un rang vers le haut), puis les abandons.
    bottom = s.get("dunce", []) + list(reversed(s["departed"]))
    s["finished"] += [i for i in active + bottom if i not in s["finished"]]
    for pos, gid in enumerate(s["finished"]):
        # Un abandon ne rapporte pas de points.
        pts = 0 if gid in s["departed"] else len(s["seats"]) - pos - 1
        s["scores"][gid] = s["scores"].get(gid, 0) + pts
    s["turn"] = None
    g["phase"] = "end"
    s["notice"] = "Manche terminée. Les places déterminent les échanges de la prochaine donne."
    return True


@serialized
def start(g, rng=random):
    if g["type"] != "president":
        raise PresidentError("Ce n'est pas une partie de Président")
    if g["phase"] not in ("lobby", "end"):
        raise PresidentError("Termine cette manche avant de redistribuer")
    players = g["players"]
    if not 3 <= len(players) <= 6:
        raise PresidentError("Il faut de 3 à 6 joueurs, chacun sur son téléphone")
    if any(p.get("manual") for p in players):
        raise PresidentError("Chaque joueur a besoin de son téléphone pour garder ses cartes secrètes")
    seats = [p["id"] for p in players]
    previous = g.get("president", {})
    order = previous.get("finished", [])
    exchange = len(order) == len(seats) and set(order) == set(seats) and not previous.get("departed")
    cards = deck()
    rng.shuffle(cards)
    hands = {gid: sorted(cards[n::len(seats)], key=lambda c: (rank(c), c)) for n, gid in enumerate(seats)}
    s = {"hands": hands, "seats": seats, "names": {**previous.get("names", {}), **{p["id"]: p["name"] for p in players}},
         "pids": {p["id"]: p["pid"] for p in players}, "turn": None, "pile": None, "passed": [],
         "finished": [], "dunce": [], "departed": [], "discard": [], "scores": dict(previous.get("scores", {})),
         "roles": {gid: role(pos, len(order)) for pos, gid in enumerate(order)} if exchange else {},
         "exchange": {}, "offered": {}, "deal": secrets.token_hex(8), "revision": 0, "trick": 1, "trail": [],
         "notice": "Le 3 de trèfle donne la première main. Les jokers seuls valent des 3."}
    g["president"] = s
    g["round"] += 1
    g["results"] = None
    for p in players:
        p["waiting"] = False
    if exchange:
        pairs = [(order[0], order[-1], 2)]
        if len(order) >= 4:
            pairs.append((order[1], order[-2], 1))
        for high, low, count in pairs:
            s["exchange"][high] = {"to": low, "count": count, "best": False}
            s["exchange"][low] = {"to": high, "count": count, "best": True}
            # Variante de la soirée : un joker vaut aussi un 3 lors des échanges.
            s["offered"][low] = sorted(hands[low], key=lambda c: (rank(c), c), reverse=True)[:count]
        s["starter"] = order[-1]
        s["notice"] = "Les mieux classés choisissent leurs cartes à donner ; les meilleures cartes des derniers sont réservées automatiquement."
        g["phase"] = "exchange"
    else:
        s["turn"] = next(gid for gid, hand in hands.items() if "3C" in hand)
        g["phase"] = "play"


def combination(cards):
    if not 1 <= len(cards) <= 4 or len(set(cards)) != len(cards):
        raise PresidentError("Choisis de 1 à 4 cartes différentes")
    real = {rank(c) for c in cards if not c.startswith("JK")}
    if len(real) > 1:
        raise PresidentError("Les cartes doivent avoir la même valeur ; un joker peut les compléter")
    return next(iter(real)) if real else 0


def _turn(g, gid, token):
    s = _state(g)
    if g["phase"] != "play" or gid != s["turn"] or gid not in _active(s):
        raise PresidentError("Ce n'est pas ton tour")
    if token != _token(s):
        raise PresidentError("La table a changé. Vérifie les cartes avant de rejouer")
    return s


FAMILY = 4  # les quatre cartes d'une valeur (jokers joués comme elle compris)
TRAIL = 5  # derniers coups du pli en cours montrés à la table (un nouveau pli repart de zéro)
TWO = RANKS.index("2")  # un 2 (seul, double, triple, carré) ferme le pli : son auteur rouvre


@serialized
def play(g, gid, cards, token):
    """Poser une combinaison. Même valeur et même nombre de cartes que le pli : autorisé, puis « … ou rien »
    pour les suivants. Le coup qui complète la famille (4 cartes de la valeur) ramasse le pli, et son auteur
    rouvre ; ce coup-là peut être joué par n'importe qui, même hors tour. Un 2 ferme aussi le pli."""
    s = _state(g)
    if g["phase"] != "play" or gid not in _active(s):
        raise PresidentError("Ce n'est pas ton tour")
    if gid in s["passed"]:
        raise PresidentError("Tu as passé : tu rejoueras au prochain pli")
    if token != _token(s):
        raise PresidentError("La table a changé. Vérifie les cartes avant de rejouer")
    hand = s["hands"][gid]
    if any(c not in hand for c in cards):
        raise PresidentError("Tu ne possèdes pas ces cartes")
    value = combination(cards)
    pile = s["pile"]
    same = bool(pile) and len(cards) == len(pile["cards"]) and value == pile["rank"]
    family = pile.get("family", len(pile["cards"])) + len(cards) if same else len(cards)
    completes = same and family >= FAMILY
    if gid != s["turn"] and not completes:
        raise PresidentError("Ce n'est pas ton tour (hors tour, on peut seulement compléter la famille)")
    if pile and not same:
        if pile.get("locked"):
            raise PresidentError(f"{RANKS[pile['rank']]} ou rien : pose la même valeur, ou passe")
        if len(cards) != len(pile["cards"]) or value <= pile["rank"]:
            raise PresidentError("Pose le même nombre de cartes, d'une valeur égale ou supérieure, ou passe")
    if pile:
        s["discard"].extend(pile["cards"])
    for c in cards:
        hand.remove(c)
    s["pile"] = {"cards": list(cards), "rank": value, "by": gid, "family": family, "locked": same}
    s["trail"] = (s.get("trail", []) + [{"cards": list(cards), "rank": value, "by": gid}])[-TRAIL:]
    label = RANKS[value]
    s["notice"] = f"{_name(g, gid)} pose {len(cards)} carte(s) de valeur {label}" + (f" : {label} ou rien." if same else ".")
    if not hand and value == TWO:  # interdit de finir sur un 2 : Trou du cul
        s["dunce"] = s.get("dunce", []) + [gid]
        s["notice"] = f"{_name(g, gid)} finit sur un 2 : interdit, il sera Trou du cul !"
    elif not hand:
        s["finished"].append(gid)
        s["notice"] = f"{_name(g, gid)} termine à la place {len(s['finished'])}."
    if not _finish_if_needed(g):
        # On ne joue pas sur celui qui termine : ses dernières cartes ferment le pli, le suivant ouvre.
        if completes or value == TWO or not hand or _everyone_else_passed(s, gid):
            notice = s["notice"]
            _clear(g)
            opener = _name(g, s["turn"])
            if not hand:
                s["notice"] = f"{notice} On ne joue pas dessus : {opener} ouvre le pli suivant."
            elif completes or value == TWO:
                done = f"complète la famille de {label}" if completes else f"ferme le pli avec {len(cards)} × 2"
                s["notice"] = f"{_name(g, gid)} {done} ! {opener} ouvre le pli suivant."
        else:
            s["turn"] = _next_in_trick(s, gid)
    _touch(s)


@serialized
def pass_turn(g, gid, token):
    s = _turn(g, gid, token)
    if not s["pile"]:
        raise PresidentError("Tu ouvres le pli : choisis au moins une carte")
    if s["pile"].get("locked"):
        _lack(g, s, gid)
        _touch(s)
        return
    s["passed"].append(gid)
    s["notice"] = f"{_name(g, gid)} passe et attend le prochain pli."
    if _everyone_else_passed(s, s["pile"]["by"]):
        _clear(g)
    else:
        s["turn"] = _next_in_trick(s, gid)
    _touch(s)


def _lack(g, s, gid):
    """« … ou rien » ne vise que le joueur suivant. S'il n'a pas la valeur, il le dit (ce n'est pas un vrai passe,
    il reste dans le pli) et la contrainte tombe : le suivant pose ce qu'il veut, la même valeur ou au-dessus."""
    pile = s["pile"]
    pile["locked"] = False
    s["turn"] = _next_in_trick(s, gid)
    label = RANKS[pile["rank"]]
    s["notice"] = f"{_name(g, gid)} n'a pas de {label} : {_name(g, s['turn'])} pose {label} ou plus."


@serialized
def exchange_cards(g, gid, cards, token):
    s = _state(g)
    if g["phase"] != "exchange" or gid not in s["exchange"] or gid in s["offered"]:
        raise PresidentError("Tu n'as pas de cartes à choisir pour cet échange")
    if token != s["deal"]:
        raise PresidentError("Cette distribution a changé. Recharge la partie")
    job = s["exchange"][gid]
    if len(cards) != job["count"] or len(set(cards)) != len(cards) or any(c not in s["hands"][gid] for c in cards):
        raise PresidentError(f"Choisis exactement {job['count']} carte(s) de ta main")
    s["offered"][gid] = list(cards)
    if len(s["offered"]) == len(s["exchange"]):
        for sender, selected in s["offered"].items():
            for c in selected:
                s["hands"][sender].remove(c)
        for sender, selected in s["offered"].items():
            s["hands"][s["exchange"][sender]["to"]].extend(selected)
        for hand in s["hands"].values():
            hand.sort(key=lambda c: (rank(c), c))
        s["turn"] = s["starter"]
        s["exchange"], s["offered"] = {}, {}
        s["notice"] = f"Échanges terminés. {_name(g, s['turn'])} ouvre le premier pli."
        g["phase"] = "play"
    _touch(s)


@serialized
def leave(g, gid):
    s = g.get("president", {})
    if gid not in s.get("seats", []) or g["phase"] not in ("play", "exchange"):
        return
    if g["phase"] == "exchange":
        # Aucun échange partiel : une nouvelle distribution est nécessaire.
        g["president"] = {"scores": s["scores"], "notice": f"{_name(g, gid)} est parti pendant les échanges. Redistribuez les cartes."}
        g["phase"] = "lobby"
        g["round"] -= 1
        return
    s["discard"].extend(s["hands"].pop(gid, []))
    if gid not in s["finished"] and gid not in s.get("dunce", []):
        s["departed"].append(gid)
    s["notice"] = f"{_name(g, gid)} quitte la manche. Ses cartes sont écartées."
    if not _finish_if_needed(g):
        if s["pile"] and _everyone_else_passed(s, s["pile"]["by"]):
            _clear(g)
        elif s["turn"] == gid:
            s["turn"] = _next_in_trick(s, gid) or _next(s, gid)
    _touch(s)


@serialized
def view(g, gid):
    s = g.get("president", {})
    live = {p["id"]: p for p in g["players"]}
    pid = lambda i: (live.get(i) or {}).get("pid") or s.get("pids", {}).get(i)
    order = s.get("finished", [])
    seats = []
    for i in s.get("seats", []):
        place = order.index(i) + 1 if i in order else None
        seats.append({"pid": pid(i), "name": _name(g, i), "count": len(s.get("hands", {}).get(i, [])),
                      "dunce": i in s.get("dunce", []),
                      "me": i == gid, "turn": s.get("turn") == i, "passed": i in s.get("passed", []),
                      "place": place, "departed": i in s.get("departed", []), "role": s.get("roles", {}).get(i),
                      "points": s.get("scores", {}).get(i, 0)})
    pile = s.get("pile")
    out = {"seats": seats, "hand": [card_view(c) for c in s.get("hands", {}).get(gid, [])] if gid in live else [],
           "turn": pid(s.get("turn")), "my_turn": g["phase"] == "play" and s.get("turn") == gid,
           "pile": {"cards": [card_view(c) for c in pile["cards"]], "rank": RANKS[pile["rank"]], "value": pile["rank"],
                    "name": _name(g, pile["by"]), "family": pile.get("family", len(pile["cards"])),
                    "locked": bool(pile.get("locked"))} if pile else None,
           "token": _token(s) if s.get("deal") else "", "trick": s.get("trick", 0),
           "trail": [{"name": _name(g, t["by"]), "cards": [card_view(c) for c in t["cards"]], "rank": RANKS[t["rank"]]}
                     for t in s.get("trail", [])],
           "notice": s.get("notice", ""), "exchange": None,
           "ranking": [{"pid": pid(i), "name": _name(g, i), "me": i == gid, "place": pos + 1,
                        "role": role(pos, len(order)), "points": s.get("scores", {}).get(i, 0),
                        "departed": i in s.get("departed", [])} for pos, i in enumerate(order)] if g["phase"] == "end" else []}
    if g["phase"] == "exchange":
        job = s["exchange"].get(gid)
        out["exchange"] = {"count": job["count"] if job else 0, "to": _name(g, job["to"]) if job else "",
                           "automatic": bool(job and job["best"]), "sent": gid in s["offered"], "token": s["deal"],
                           "cards": [card_view(c) for c in s["offered"].get(gid, [])] if gid in live else [],
                           "pending": [_name(g, i) for i in s["exchange"] if i not in s["offered"]]}
    return out
