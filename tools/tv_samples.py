#!/usr/bin/env python3
"""États de démonstration pour l'app Apple TV : joue chaque jeu au hasard (vraies actions du serveur) et garde la vue
spectateur de la télé à chaque nouvelle phase, résultats compris.

  .venv/bin/python tools/tv_samples.py <dossier> [jeu …]
Écrit <dossier>/<jeu>-<n>-<phase>.json au format démo de l'app ({game, music}) : SIMCTL_CHILD_PARTY_TV_DEMO=<fichier>.
"""
import json
import random
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import main

GAMES = ["quiz", "likely", "purity", "undercover", "whoof", "never", "debate", "roulette", "divan", "tmc",
         "blackjack", "casino", "pyramid", "biskit", "president"]
NAMES = ["Boby", "Léa", "Tom", "Nina", "Max", "Inès"]
STEPS, PER_PHASE = 900, 2
CRASHES: set = set()  # (jeu, action) qui font planter le serveur : à corriger
MUSIC = {"active": True, "state": "PLAYING", "pin": "4821",
         "now": {"title": "Blinding Lights", "artist": "The Weeknd", "art": "", "by": "Léa"},
         "upcoming": [{"title": "Levitating", "artist": "Dua Lipa", "by": "Tom"},
                      {"title": "Mr. Brightside", "artist": "The Killers", "by": None},
                      {"title": "Alors on danse", "artist": "Stromae", "by": "Nina"},
                      {"title": "Dancing Queen", "artist": "ABBA", "by": "Max"}]}
ACTIONS = ["vote", "next", "close_vote", "vote_start", "spin", "bet", "hit", "stand", "double", "deal", "cbet", "cready",
           "cspin", "dnext", "dheart", "tanswer", "tjudge", "treveal", "finish", "pans", "pflip", "pclaim", "pbu",
           "pliar", "preveal", "ptop", "pmemory", "pmem", "presults", "bdraw", "bpick", "btap", "bclose", "qans",
           "prplay", "prpass", "puans", "pusub", "pureveal", "lkvote", "dbvote", "eliminate", "guess", "skip_guess"]
BETS = ["color:red", "color:black", "n:7", "dozen:2", "parity:even"]


def explore(kind: str, out: Path, rng: random.Random) -> int:
    main._game_creations.clear()
    with TestClient(main.app, raise_server_exceptions=False) as c:
        assert c.post("/api/admin/login", json={"pin": main.ADMIN_PIN}).status_code == 200
        gids = [f"tv-sample-{kind[:6]}-{i:02d}" for i in range(len(NAMES))]
        made = c.post("/api/games", json={"type": kind, "guest_id": gids[0], "name": NAMES[0], "plays": True}).json()
        if "code" not in made:
            print(kind, "pas créé :", made.get("detail"))
            return 0
        code = made["code"]

        def act(gid, **b):
            r = c.post(f"/api/games/{code}", json={"guest_id": gid, **b})
            if r.status_code >= 500:
                CRASHES.add((kind, b.get("action")))
            return r

        for gid, name in zip(gids[1:5], NAMES[1:5]):
            act(gid, action="join", name=name)
        act(gids[0], action="addguest", guess=NAMES[5])  # un prénom ajouté à la main
        act(gids[0], action="names", names=NAMES)
        act(gids[0], action="start")
        seen: dict[str, int] = {}
        saved, last = 0, None
        for _ in range(STEPS):
            view = c.get(f"/api/tv/game/{code}").json()
            key = view.get("phase", "?")
            sig = json.dumps(view, sort_keys=True, default=str)[:4000]
            if sig != last and seen.get(key, 0) < PER_PHASE and key != "lobby":
                seen[key] = seen.get(key, 0) + 1
                saved += 1
                (out / f"{kind}-{saved:02d}-{key}.json").write_text(json.dumps({"game": view, "music": MUSIC}, ensure_ascii=False))
            last = sig
            if key == "end" and seen.get("end", 0) >= 1:
                break
            pids = [p["pid"] for p in view.get("players", [])]
            for gid in rng.sample(gids[:5], 5):
                a = rng.choice(ACTIONS)
                act(gid, action=a, target=rng.choice(pids + ["yes", "no"] + BETS) if pids else "",
                    amount=rng.choice([0, 1, 2, 5, 10]), guess=rng.choice(pids + ["yes", "no", "Paris", "1"]) if pids else "",
                    values=rng.sample(["A", "K", "Q", "J", "T", "9"], 2), slots=[0, 1], done=False)
            if rng.random() < 0.05:
                act(gids[0], action="next")
            time.sleep(0.005)
        return saved


def main_cli() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    for kind in sys.argv[2:] or GAMES:
        print(kind, explore(kind, out, rng))
    if CRASHES:
        print("ERREURS SERVEUR :", sorted(CRASHES))


if __name__ == "__main__":
    main_cli()
