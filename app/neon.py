"""Server-authoritative Neon Knockout. Positions never come from the client.

Fixed 60 Hz physics, sampled by the lightweight phone transport. The shared lock
also covers lobby actions, so two phones cannot advance the same time twice.
"""
import math
import threading
import time

LOCK = threading.RLock()
STEP = 1 / 60
RADIUS = 10.0
BODY = 0.48
COLORS = ["#55e8ff", "#ff668f", "#ffce66", "#ad96ff", "#73f5ad", "#ff985c", "#86a9ff", "#f893eb"]
TEAM_NAMES = ["Équipe Cyan", "Équipe Rose", "Équipe Or", "Équipe Iris"]


class NeonError(ValueError):
    pass


def state(g):
    if g["type"] != "neon":
        raise NeonError("Cette action appartient à Néon Knockout")
    return g.setdefault("neon", {"mode": "solo", "teams": {}, "scores": {}, "bodies": {}, "winner": None,
                                  "notice": "", "time": 0, "radius": RADIUS, "clock": 0})


def roster(g):
    s = state(g)
    for p in g["players"]:
        if p["pid"] not in s["teams"]:
            counts = [sum(s["teams"].get(x["pid"]) == i for x in g["players"]) for i in range(4)]
            s["teams"][p["pid"]] = next((i for i, n in enumerate(counts) if n < 2), 0)
    return s


def configure(g, settings):
    s = roster(g)
    if g["phase"] not in ("lobby", "results", "end"):
        raise NeonError("Attends la fin de la manche pour préparer un nouveau match")
    mode = settings.get("mode")
    if mode not in ("solo", "duo"):
        raise NeonError("Choisis chacun pour soi ou équipes de deux")
    s.update(mode=mode, scores={}, winner=None)
    g.update(phase="lobby", round=0)


def team(g, gid, number):
    s = roster(g)
    if g["phase"] not in ("lobby", "end"):
        raise NeonError("Les équipes sont fixées pour tout le match")
    p = next((p for p in g["players"] if p["id"] == gid), None)
    if not p or number not in range(4):
        raise NeonError("Rejoins la partie pour choisir ton équipe")
    if sum(s["teams"].get(x["pid"]) == number and x != p for x in g["players"]) >= 2:
        raise NeonError("Ce duo est déjà complet")
    s["teams"][p["pid"]] = number


def start(g, rng=None):
    s = roster(g)
    if g["phase"] not in ("lobby", "results", "end"):
        raise NeonError("Une manche est déjà en cours")
    n = len(g["players"])
    if not 2 <= n <= 8 or any(p.get("manual") for p in g["players"]):
        raise NeonError("Il faut 2 à 8 joueurs, chacun avec son téléphone")
    if s["mode"] == "duo":
        counts = [sum(s["teams"][p["pid"]] == i for p in g["players"]) for i in range(4)]
        if n < 4 or any(c not in (0, 2) for c in counts):
            raise NeonError("Formez 2 à 4 équipes complètes de deux joueurs")
    if g["phase"] in ("lobby", "end"):
        s["scores"] = {}
        g["round"] = 0
    now = time.time()
    s.update(bodies={}, time=-3.0, clock=now, radius=RADIUS, winner=None, notice="")
    for i, p in enumerate(g["players"]):
        angle = -math.pi / 2 + i * math.tau / n
        group = str(s["teams"][p["pid"]]) if s["mode"] == "duo" else p["pid"]
        s["bodies"][p["pid"]] = dict(x=math.cos(angle)*6.3, y=math.sin(angle)*6.3, vx=0., vy=0.,
            ax=-math.cos(angle), ay=-math.sin(angle), ix=0., iy=0., seen=0., charge=None,
            cooldown=0., dash=0., alive=True, group=group, color=COLORS[s["teams"][p["pid"]] if s["mode"] == "duo" else i],
            name=p["name"], hit=[], pulse=0)
        p.update(alive=True, waiting=False)
    g.update(phase="countdown", round=g["round"] + 1)


def finish(g, winner, notice=""):
    s = state(g)
    s["winner"], s["notice"] = winner, notice
    if winner is not None:
        s["scores"][winner] = s["scores"].get(winner, 0) + 1
    g["phase"] = "end" if winner is not None and s["scores"][winner] >= 5 else "results"
    for b in s["bodies"].values():
        b.update(ix=0., iy=0., charge=None)


def leave(g, gid, pid):
    s = state(g)
    if pid in s["bodies"]:
        s["bodies"][pid]["alive"] = False
    s["teams"].pop(pid, None)
    if g["phase"] in ("countdown", "play"):
        groups = {b["group"] for b in s["bodies"].values() if b["alive"]}
        if len(groups) <= 1:
            finish(g, next(iter(groups), None))


def input_state(g, gid, x, y, charging, now=None, cancel=False):
    s = state(g)
    now = time.time() if now is None else now
    p = next((p for p in g["players"] if p["id"] == gid), None)
    b = s["bodies"].get(p["pid"]) if p else None
    if not math.isfinite(x) or not math.isfinite(y):
        raise NeonError("Commande invalide")
    if not b or not b["alive"] or g["phase"] != "play":
        return
    if cancel:
        b.update(ix=0., iy=0., charge=None)
        return
    length = max(1., math.hypot(x, y))
    b.update(ix=x/length, iy=y/length, seen=now)
    if math.hypot(x, y) > .1:
        aim = math.hypot(x, y)
        b.update(ax=x/aim, ay=y/aim)
    if charging and b["charge"] is None and b["cooldown"] <= s["time"]:
        b["charge"] = s["time"]
    elif not charging and b["charge"] is not None:
        power = min(1., max(0., s["time"] - b["charge"]) / 1.1)
        b.update(vx=b["ax"]*(13+13*power), vy=b["ay"]*(13+13*power), dash=s["time"]+.23,
                 charge=None, cooldown=s["time"]+1.15, hit=[], pulse=b["pulse"]+1)


def tick(g, now=None):
    if g["type"] != "neon" or g["phase"] not in ("countdown", "play"):
        return False
    s = state(g)
    now = time.time() if now is None else now
    phase = g["phase"]
    gap = now - s["clock"]
    # After sleep/restart do not replay minutes of stale controls or award a win.
    if gap > 5 or gap < -1:
        finish(g, None, "Connexion interrompue. Relancez cette manche ; aucun point attribué.")
        s["clock"] = now
        return True
    steps = max(0, int(gap / STEP))
    for _ in range(steps):
        s["clock"] += STEP
        s["time"] += STEP
        if s["time"] < 0:
            continue
        g["phase"] = "play"
        t = s["time"]
        s["radius"] = RADIUS * max(0., 1 - max(0., t - 12) / 33)
        bodies = [(pid, b) for pid, b in s["bodies"].items() if b["alive"]]
        for pid, b in bodies:
            if s["clock"] - b["seen"] > .4:
                b.update(ix=0., iy=0., charge=None)
            if b["dash"] <= t:
                speed = 2.7 if b["charge"] is not None else 5.3
                drag = math.exp(-7*STEP)
                b["vx"] = b["vx"]*drag + b["ix"]*speed*(1-drag)
                b["vy"] = b["vy"]*drag + b["iy"]*speed*(1-drag)
            b["x"] += b["vx"]*STEP
            b["y"] += b["vy"]*STEP
        for i, (aid, a) in enumerate(bodies):
            for bid, b in bodies[i+1:]:
                dx, dy = b["x"]-a["x"], b["y"]-a["y"]
                d = math.hypot(dx, dy)
                if d >= BODY*2 or a["group"] == b["group"]:
                    continue
                nx, ny = (dx/d, dy/d) if d > .0001 else (1., 0.)
                overlap = (BODY*2-d)/2
                a["x"] -= nx*overlap
                a["y"] -= ny*overlap
                b["x"] += nx*overlap
                b["y"] += ny*overlap
                # Snapshot both attacks before applying impulses: simultaneous dashes are symmetric.
                attack_a = a["dash"] > t and bid not in a["hit"]
                attack_b = b["dash"] > t and aid not in b["hit"]
                av, bv = math.hypot(a["vx"], a["vy"]), math.hypot(b["vx"], b["vy"])
                if attack_a:
                    a["hit"].append(bid)
                    b.update(vx=nx*(av*.9+5), vy=ny*(av*.9+5), dash=max(b["dash"], t+.18), charge=None)
                if attack_b:
                    b["hit"].append(aid)
                    a.update(vx=-nx*(bv*.9+5), vy=-ny*(bv*.9+5), dash=max(a["dash"], t+.18), charge=None)
        for pid, b in bodies:
            if math.hypot(b["x"], b["y"]) > s["radius"] + BODY*.55:
                b["alive"] = False
                for p in g["players"]:
                    if p["pid"] == pid:
                        p["alive"] = False
        groups = {b["group"] for _, b in bodies if b["alive"]}
        if len(groups) <= 1 or t >= 45:
            finish(g, next(iter(groups)) if len(groups) == 1 else None)
            break
    return phase != g["phase"]


def view(g, gid):
    s = roster(g)
    me = next((p["pid"] for p in g["players"] if p["id"] == gid), None)
    return {"mode": s["mode"], "teams": dict(s["teams"]), "scores": dict(s["scores"]), "winner": s["winner"],
            "notice": s["notice"], "time": round(s["time"], 3), "radius": s["radius"], "me": me,
            "phase": g["phase"], "round": g["round"], "clock": s["clock"],
            "fighters": [{"pid": pid, **{k: b[k] for k in ("x", "y", "vx", "vy", "ax", "ay", "alive", "group", "color", "name", "pulse")},
                          "charge": min(1., max(0., s["time"]-b["charge"])/1.1) if b["charge"] is not None else 0,
                          "cooldown": max(0., b["cooldown"]-s["time"]), "dashing": b["dash"] > s["time"]}
                         for pid, b in s["bodies"].items()]}
