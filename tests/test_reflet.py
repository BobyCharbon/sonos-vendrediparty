"""« Le Reflet » : qui est devant le miroir choisit et parie en secret, les autres votent anonymement, points selon
l'écart, tours qui s'enchaînent, départs en pleine partie, et actions vérifiées par le serveur."""
import json
import random

import pytest
from fastapi.testclient import TestClient

from app import games, main, reflet
from app.masque_cards import REFLET_CARDS


def table(n=4, seed=5):
    g = games.new_game("reflet", host="h", name="Léa")
    for i in range(1, n):
        games.join(g, f"p{i}", f"Ami{i}")
    games.start(g, random.Random(seed))
    return g


def mirror_id(g):
    return reflet.mirror(g)["id"]


def test_only_the_mirror_sees_and_picks_the_options_and_the_bet_stays_secret():
    g = table()
    assert g["phase"] == "pick" and mirror_id(g) == "h"
    assert len(games.view(g, "h")["reflet"]["options"]) == reflet.CHOICES
    assert "options" not in games.view(g, "p1")["reflet"]
    with pytest.raises(reflet.RefletError):
        reflet.pick(g, "p1", 0, 1)  # pas son tour
    with pytest.raises(reflet.RefletError, match="entre 0 et 3"):
        reflet.pick(g, "h", 0, 4)
    reflet.pick(g, "h", 1, 2)
    assert g["phase"] == "vote" and games.view(g, "p1")["reflet"]["card"]
    assert "bet" not in games.view(g, "p1")["reflet"] and games.view(g, "h")["reflet"]["bet"] == 2


def test_votes_are_secret_and_an_exact_bet_scores_three():
    g = table()
    reflet.pick(g, "h", 0, 2)
    reflet.vote(g, "p1", True)
    v = games.view(g, "p2")["reflet"]
    assert v["done"] == 1 and "p1" not in json.dumps(v)  # on sait combien ont voté, jamais quoi
    with pytest.raises(reflet.RefletError):
        reflet.vote(g, "p1", False)  # un seul vote
    with pytest.raises(reflet.RefletError):
        reflet.vote(g, "h", True)  # pas sur soi-même
    reflet.vote(g, "p2", True)
    reflet.vote(g, "p3", False)
    assert g["phase"] == "result"
    assert g["reflet"]["result"] == {"yes": 2, "no": 1, "voters": 3, "bet": 2, "gap": 0, "points": 3}
    assert g["reflet"]["scores"] == {"h": 3}


def test_one_off_scores_one_and_further_scores_nothing():
    g = table()
    reflet.pick(g, "h", 0, 3)
    for gid in ("p1", "p2"):
        reflet.vote(g, gid, True)
    reflet.vote(g, "p3", False)
    assert g["reflet"]["result"]["points"] == reflet.POINT_CLOSE
    games.next_step(g, random.Random(1))
    assert mirror_id(g) == "p1"
    reflet.pick(g, "p1", 0, 0)
    for gid in ("h", "p2", "p3"):
        reflet.vote(g, gid, True)
    assert g["reflet"]["result"]["points"] == 0


def test_the_host_can_skip_an_absent_voter_and_swap_once():
    g = table()
    first = games.view(g, "h")["reflet"]["options"]
    reflet.swap(g, "p2", True, random.Random(3))  # l'animateur (lead) peut changer les affirmations
    assert games.view(g, "h")["reflet"]["options"] != first
    with pytest.raises(reflet.RefletError, match="Une seule"):
        reflet.swap(g, "h", False)
    reflet.pick(g, "h", 0, 1)
    reflet.vote(g, "p1", True)
    reflet.vote(g, "p2", False)
    reflet.skip(g, "p3")
    assert g["phase"] == "result" and g["reflet"]["result"]["voters"] == 2


def test_everyone_passes_in_front_of_the_mirror_then_a_summary():
    g = games.new_game("reflet", host="h", name="Léa")
    for i in range(1, 3):
        games.join(g, f"p{i}", f"Ami{i}")
    reflet.configure(g, {"turns": 2})
    games.start(g, random.Random(2))
    mirrors = []
    for _ in range(6):
        m = mirror_id(g)
        mirrors.append(m)
        reflet.pick(g, m, 0, 2)
        for p in g["players"]:
            if p["id"] != m:
                reflet.vote(g, p["id"], True)
        games.next_step(g, random.Random(3))
    assert g["phase"] == "end" and mirrors == ["h", "p1", "p2"] * 2
    s = games.view(g, "h")["reflet"]["summary"]
    assert set(s["lucid"]) == {"Léa", "Ami1", "Ami2"} and len(s["unanimous"]) == 5
    assert any("lucide" in f for f in reflet.summary_facts(g))


def test_the_mirror_leaving_passes_the_turn_and_two_players_end_the_game():
    g = table()
    reflet.pick(g, "h", 0, 1)
    reflet.vote(g, "p1", True)
    games.leave(g, "h")  # devant le miroir, il part : le tour passe au suivant
    assert g["phase"] == "pick" and mirror_id(g) == "p1"
    games.leave(g, "p3")
    assert g["phase"] == "pick" and mirror_id(g) == "p1"
    games.leave(g, "p2")
    assert g["phase"] == "end"


def test_a_voter_leaving_settles_the_vote():
    g = table()
    reflet.pick(g, "h", 0, 1)
    reflet.vote(g, "p1", True)
    reflet.vote(g, "p2", False)
    games.leave(g, "p3")
    assert g["phase"] == "result" and g["reflet"]["result"]["voters"] == 2


def test_every_statement_is_well_formed():
    assert len(REFLET_CARDS) == len({c[1] for c in REFLET_CARDS})
    for level, text in REFLET_CARDS:
        assert level in ("leger", "profond") and 5 < len(text) <= 120


def test_actions_are_checked_by_the_server():
    before = set(main.store.session.games)
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    ids = ["rf-host-00000001", "rf-phone-0000001", "rf-phone-0000002"]
    try:
        code = c.post("/api/games", json={"type": "reflet", "guest_id": ids[0], "name": "Boby"}).json()["code"]
        for i, gid in enumerate(ids[1:]):
            c.post(f"/api/games/{code}", json={"guest_id": gid, "action": "join", "name": f"Ami{i}"})
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "rfset", "settings": {"turns": 2}}).status_code == 403
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "start"}).status_code == 200
        r = c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "rfpick", "settings": {"i": 0, "bet": 1}})
        assert r.status_code == 200 and r.json()["phase"] == "vote"
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "rfvote", "done": True}).status_code == 200
        r = c.post(f"/api/games/{code}", json={"guest_id": ids[2], "action": "rfvote", "done": False})
        assert r.json()["phase"] == "result" and r.json()["reflet"]["result"]["yes"] == 1
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "mswrite", "guess": "x"}).status_code == 400
    finally:
        for k in set(main.store.session.games) - before:
            main.store.session.games.pop(k, None)
        main._game_creations.clear()
