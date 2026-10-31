#!/usr/bin/env python3
"""Bots d'endurance : jouent toutes les parties au hasard (vraies actions du serveur) jusqu'à une heure donnée et notent
chaque erreur du serveur (avec sa trace) et chaque incohérence d'une partie.

  PYTHONPATH=. DATA_DIR=$(mktemp -d) ADMIN_PIN=9999 .venv/bin/python tools/bot_soak.py <rapport.txt> <HH:MM fin>
"""
import datetime as dt
import json
import random
import sys
import time
import traceback
from collections import Counter

from fastapi.testclient import TestClient

from app import main

GAMES = ["beerpong", "room", "quiz", "likely", "undercover", "whoof", "never", "debate", "roulette", "divan", "tmc",
         "blackjack", "casino", "pyramid", "biskit", "president"]
NAMES = ["Boby", "Léa", "Tom", "Nina", "Max", "Inès", "Zoé"]
ACTIONS = ["vote", "next", "close_vote", "vote_start", "spin", "bet", "hit", "stand", "double", "deal", "cbet", "cready",
           "cspin", "dnext", "dheart", "tanswer", "tjudge", "treveal", "finish", "pans", "pflip", "pclaim", "pbu", "pliar",
           "preveal", "ptop", "pmemory", "pmem", "presults", "bdraw", "bpick", "btap", "bclose", "qans", "prplay", "prpass",
           "lkvote", "dbvote", "eliminate", "guess", "skip_guess", "rvote", "launch", "bpset", "bphit", "bpsent", "bpreroll",
           "bpundo", "pause", "resume", "leave", "join", "addguest", "restart", "end", "handover", "remove"]
TYPES = [t for t in GAMES if t != "room"] + ["heist", "island", "neon"]


class Soak:
    def __init__(self, report: str, until: dt.datetime):
        self.report, self.until = report, until
        self.crashes: dict[str, dict] = {}
        self.problems: Counter = Counter()
        self.actions = 0
        self.games = 0
        self.started = time.time()

    def write(self):
        with open(self.report, "w") as f:
            f.write(f"Bots : {self.games} parties, {self.actions} actions, {int(time.time() - self.started) // 60} min\n")
            f.write(f"Erreurs du serveur (500) : {len(self.crashes)} sortes\n")
            for key, c in self.crashes.items():
                f.write(f"\n== {key} ×{c['n']}\n{c['trace']}\n")
            f.write(f"\nIncohérences : {sum(self.problems.values())}\n")
            for k, n in self.problems.most_common():
                f.write(f"  {k} ×{n}\n")

    def call(self, c, method, url, **kw):
        self.actions += 1
        try:
            return getattr(c, method)(url, **kw)
        except Exception as e:  # erreur du serveur : on la garde, avec la trace
            body = kw.get("json", {})
            key = f"{body.get('action', url)} → {type(e).__name__}: {str(e)[:120]}"
            c_ = self.crashes.setdefault(key, {"n": 0, "trace": "".join(traceback.format_exc()[-2500:])})
            c_["n"] += 1
            return None

    def check(self, kind: str, v: dict):
        """Invariants vus par tous : rien d'incohérent ni de secret."""
        if not isinstance(v, dict) or "phase" not in v:
            return
        try:
            json.dumps(v)
        except Exception:
            self.problems[f"{kind}: vue non sérialisable"] += 1
        if kind == "beerpong" and v.get("bp"):
            B = v["bp"]
            for t in ("red", "blue"):
                if B["alive"][t] != sum(1 for x in B["racks"][t] if x):
                    self.problems["beerpong: compte de gobelets faux"] += 1
            if v["phase"] == "end" and not B.get("winner"):
                self.problems["beerpong: fin sans gagnant"] += 1
            if v["phase"] == "play" and min(B["alive"].values()) == 0 and not B.get("pending"):
                self.problems["beerpong: une équipe à 0 gobelet sans fin"] += 1
        if kind == "room" and v.get("room_info"):
            R = v["room_info"]
            if sum(R.get("votes", {}).values()) > len(v["players"]):
                self.problems["salle: plus de votes que de joueurs"] += 1
            if R.get("current") and R.get("votes"):
                self.problems["salle: votes pendant un jeu"] += 1
        if v.get("paused") and v["phase"] in ("lobby",):
            self.problems[f"{kind}: pause en salle d'attente"] += 1

    def play(self, kind: str, rng: random.Random):
        main._game_creations.clear()
        if len(main.store.session.games) > 20:
            main.store.session.games.clear()
        c = TestClient(main.app)
        gids = [f"soak-{kind[:6]}-{rng.randrange(10**6):06d}-{i}" for i in range(rng.randint(2, 6))]
        made = self.call(c, "post", "/api/games", json={"type": kind, "guest_id": gids[0], "name": NAMES[0], "plays": rng.random() < .8,
                                                        "sips": rng.choice([0, 1, 2])})
        if made is None or made.status_code != 200:
            return
        self.games += 1
        code = made.json()["code"]
        for gid, name in zip(gids[1:], NAMES[1:]):
            self.call(c, "post", f"/api/games/{code}", json={"guest_id": gid, "name": name, "action": "join"})
        if rng.random() < .5:
            self.call(c, "post", f"/api/games/{code}", json={"guest_id": gids[0], "action": "addguest", "guess": "Mamie"})
        for _ in range(rng.randint(30, 200)):
            if dt.datetime.now() >= self.until:
                return
            view = self.call(c, "get", f"/api/games/{code}?guest_id={rng.choice(gids)}")
            if view is None or view.status_code != 200:
                return
            v = view.json()
            self.check(kind, v)
            target_code = code
            if kind == "room" and (v.get("room_info") or {}).get("current"):
                target_code = v["room_info"]["current"]["code"] if rng.random() < .7 else code
            pids = [p["pid"] for p in v.get("players", [])] or [""]
            a = rng.choice(ACTIONS)
            body = {"guest_id": rng.choice(gids), "action": a, "target": rng.choice(pids + ["yes", "no", "color:red", "n:7", rng.choice(TYPES)]),
                    "amount": rng.choice([0, 1, 2, 5, 10]), "guess": rng.choice(pids + ["yes", "no", "1", "Paris"]),
                    "values": rng.sample(["A", "K", "Q", "J", "T", "9"], 2), "slots": [0, 1], "done": rng.random() < .5}
            bp = v.get("bp") or {}
            if a == "bphit" and bp:
                team = rng.choice(["red", "blue"])
                mates = [p["pid"] for p in bp.get("players", []) if p.get("team") == team] or pids
                body["settings"] = {"team": team, "cup": rng.randrange(max(1, len(bp["racks"].get(team) or [1]))), "pid": rng.choice(mates)}
                body["guest_id"] = gids[0] if rng.random() < .8 else body["guest_id"]
            elif a == "bpset":
                body["settings"] = rng.choice([{"cups": rng.choice([6, 10, 15, 7])}, {"shuffle": True}, {"kinds": rng.sample(["sips", "shot", "dare", "wtf", "quiz", "sport", "bonus", "malus", "x"], 3)},
                                               {"marker": rng.choice(pids + [""])}, {"team": {"pid": rng.choice(pids), "team": rng.choice(["red", "blue", "green"])}}])
                body["guest_id"] = gids[0]
            elif a == "launch":
                body["settings"] = {"type": rng.choice(TYPES), "sips": 1}
                body["guest_id"] = gids[0]
            elif a in ("bpsent", "bpreroll", "bpundo", "pause", "resume", "next", "close_vote", "deal", "cspin", "start") and rng.random() < .8:
                body["guest_id"] = gids[0]
            r = self.call(c, "post", f"/api/games/{target_code}", json=body)
            if r is not None and r.status_code >= 500:
                self.crashes.setdefault(f"{kind}/{a} → HTTP {r.status_code}", {"n": 0, "trace": r.text[:500]})["n"] += 1
            if rng.random() < .03:
                self.call(c, "post", f"/api/games/{code}", json={"guest_id": gids[0], "action": "start"})

    def run(self):
        rng = random.Random(int(time.time()))
        last = 0
        while dt.datetime.now() < self.until:
            self.play(rng.choice(GAMES), rng)
            if time.time() - last > 60:
                self.write()
                last = time.time()
        self.write()


if __name__ == "__main__":
    report, hhmm = sys.argv[1], sys.argv[2]
    h, m = map(int, hhmm.split(":"))
    until = dt.datetime.now().replace(hour=h, minute=m, second=0)
    if until <= dt.datetime.now():
        until += dt.timedelta(days=1)
    Soak(report, until).run()
