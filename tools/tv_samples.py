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
STEPS, PER_PHASE = 700, 3
CRASHES: set = set()  # (jeu, action) qui font planter le serveur : à corriger
MUSIC = {"active": True, "state": "PLAYING", "pin": "4821",
         "now": {"title": "Blinding Lights", "artist": "The Weeknd", "art": "", "by": "Léa"},
         "upcoming": [{"title": "Levitating", "artist": "Dua Lipa", "by": "Tom"},
                      {"title": "Mr. Brightside", "artist": "The Killers", "by": None},
                      {"title": "Alors on danse", "artist": "Stromae", "by": "Nina"},
                      {"title": "Dancing Queen", "artist": "ABBA", "by": "Max"}]}
# Actions jouées par chaque joueur, propres à chaque jeu (les arguments sont tirés parmi des valeurs plausibles).
PLAYER_ACTIONS = {
    "quiz": ["qans"], "likely": ["lkvote"], "undercover": ["vote", "guess"], "whoof": ["vote"], "never": ["vote"],
    "debate": ["dbvote"], "roulette": [], "divan": ["dnext", "dheart"], "tmc": ["tanswer"],
    "blackjack": ["bet", "hit", "stand", "stand", "double"], "casino": ["cbet", "cbet", "cready"],
    "pyramid": ["pans", "pclaim", "preveal", "ptop", "pmem", "pbans"], "biskit": ["bdraw", "bpick", "btap"],
    "president": ["prplay", "prpass", "prexchange"],
}
# Actions de l'animateur, plus rares : on laisse le temps aux joueurs de voter ou miser.
HOST_ACTIONS = {
    "quiz": ["next"], "likely": ["next"], "undercover": ["vote_start", "close_vote", "next", "skip_guess"],
    "whoof": ["close_vote", "next"], "never": ["close_vote", "next"], "debate": ["next"], "roulette": ["spin", "next"],
    "divan": ["next"], "tmc": ["treveal", "tjudge", "next", "finish"], "blackjack": ["deal", "next"],
    "casino": ["cspin", "next"], "pyramid": ["pflip", "pbu", "pliar", "pmemory", "presults", "pboat", "pboatgo", "next"],
    "biskit": ["bclose", "next"], "president": ["next"],
}
BETS = ["color:red", "color:black", "n:7", "dozen:2", "parity:even"]


def explore(kind: str, out: Path, rng: random.Random) -> int:
    main._game_creations.clear()
    with TestClient(main.app, raise_server_exceptions=False) as c:
        assert c.post("/api/admin/login", json={"pin": main.ADMIN_PIN}).status_code == 200
        gids = [f"tv-sample-{kind[:6]}-{i:02d}" for i in range(len(NAMES))]
        made = c.post("/api/games", json={"type": kind, "guest_id": gids[0], "name": NAMES[0], "plays": True, "sips": 2}).json()
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
            targets = pids + (["yes", "no"] if kind == "never" else BETS if kind == "casino" else ["red", "black", "plus", "moins"])
            for gid in rng.sample(gids[:5], 5):
                for a in PLAYER_ACTIONS[kind][:1] + rng.sample(PLAYER_ACTIONS[kind], min(2, len(PLAYER_ACTIONS[kind]))):
                    act(gid, action=a, target=rng.choice(targets) if targets else "", amount=rng.choice([1, 2, 3, 5, 10]),
                        guess=rng.choice(pids + ["yes", "no", "1"]) if pids else "",
                        values=rng.sample(["A", "K", "Q", "J", "T", "9"], 2), slots=[0, 1], done=False)
            # Participant sans téléphone : l'animateur vote ou mise pour lui.
            manual = next((p["pid"] for p in view.get("players", []) if p.get("name") == NAMES[5]), "")
            if manual:
                act(gids[0], action=rng.choice(["mvote", "bet", "cbet", "stand"]), target=manual if kind in ("never", "whoof") else rng.choice(BETS),
                    guess=rng.choice(["yes", "no"] if kind == "never" else pids or ["x"]), amount=5, who=manual)
            if rng.random() < 0.25:
                act(gids[0], action=rng.choice(HOST_ACTIONS[kind]), amount=rng.choice([0, 1, 2]), target=rng.choice(pids) if pids else "")
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
