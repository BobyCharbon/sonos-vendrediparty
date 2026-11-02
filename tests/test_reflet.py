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
    r = g["reflet"]["result"]
    assert {k: r[k] for k in ("yes", "no", "voters", "bet", "gap", "points")} == {"yes": 2, "no": 1, "voters": 3, "bet": 2, "gap": 0, "points": 3}
    assert r["name"] == "Léa"
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
    for i in range(1, 4):
        games.join(g, f"p{i}", f"Ami{i}")
    reflet.configure(g, {"turns": 2})
    games.start(g, random.Random(2))
    mirrors = []
    for _ in range(8):
        m = mirror_id(g)
        mirrors.append(m)
        reflet.pick(g, m, 0, 2)
        for p in g["players"]:
            if p["id"] != m:
                reflet.vote(g, p["id"], True)
        games.next_step(g, random.Random(3))
    assert g["phase"] == "end" and mirrors == ["h", "p1", "p2", "p3"] * 2
    s = games.view(g, "h")["reflet"]["summary"]
    assert set(s["lucid"]) == {"Léa", "Ami1", "Ami2", "Ami3"} and len(s["unanimous"]) == 5
    assert any("lucide" in f for f in reflet.summary_facts(g))


def test_the_mirror_leaving_passes_the_turn_and_two_players_end_the_game():
    g = table(5)
    reflet.pick(g, "h", 0, 1)
    reflet.vote(g, "p1", True)
    games.leave(g, "h")  # devant le miroir, il part : le tour passe au suivant
    assert g["phase"] == "pick" and mirror_id(g) == "p1"
    games.leave(g, "p4")
    assert g["phase"] == "end"  # à trois, chacun des deux votants devinerait le vote de l'autre


def test_a_voter_leaving_settles_the_vote():
    g = table(5)
    reflet.pick(g, "h", 0, 1)
    for gid in ("p1", "p2", "p3"):
        reflet.vote(g, gid, gid == "p1")
    games.leave(g, "p4")
    assert g["phase"] == "result" and g["reflet"]["result"]["voters"] == 3


def test_every_statement_is_well_formed():
    assert len(REFLET_CARDS) == len({c[1] for c in REFLET_CARDS})
    for level, text in REFLET_CARDS:
        assert level in ("leger", "profond") and 5 < len(text) <= 120


def test_actions_are_checked_by_the_server():
    before = set(main.store.session.games)
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    ids = ["rf-host-00000001", "rf-phone-0000001", "rf-phone-0000002", "rf-phone-0000003"]
    try:
        code = c.post("/api/games", json={"type": "reflet", "guest_id": ids[0], "name": "Boby"}).json()["code"]
        for i, gid in enumerate(ids[1:]):
            c.post(f"/api/games/{code}", json={"guest_id": gid, "action": "join", "name": f"Ami{i}"})
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "rfset", "settings": {"turns": 2}}).status_code == 403
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "start"}).status_code == 200
        r = c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "rfpick", "settings": {"i": 0, "bet": 1}})
        assert r.status_code == 200 and r.json()["phase"] == "vote"
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[1], "action": "rfvote", "done": True}).status_code == 200
        c.post(f"/api/games/{code}", json={"guest_id": ids[2], "action": "rfvote", "done": False})
        r = c.post(f"/api/games/{code}", json={"guest_id": ids[3], "action": "rfvote", "done": False})
        assert r.json()["phase"] == "result" and r.json()["reflet"]["result"]["yes"] == 1
        assert c.post(f"/api/games/{code}", json={"guest_id": ids[0], "action": "mswrite", "guess": "x"}).status_code == 400
    finally:
        for k in set(main.store.session.games) - before:
            main.store.session.games.pop(k, None)
        main._game_creations.clear()


def test_every_trio_offers_at_least_one_light_statement():
    for seed in range(30):
        g = table(seed=seed)
        assert any(REFLET_CARDS[i][0] == "leger" for i in g["reflet"]["options"])


def play_turn(g, bet=1, yes=True):
    m = mirror_id(g)
    reflet.pick(g, m, 0, bet)
    for p in list(g["players"]):
        if p["id"] != m and g["phase"] == "vote":
            reflet.vote(g, p["id"], yes)
    return m


def test_someone_leaving_after_their_turn_never_skips_a_player():
    # Retour des tests : H et P1 passent, P1 part, P2 passe… et P3 ne passait jamais avant le bilan.
    g = table(5)
    seen = [play_turn(g)]
    games.next_step(g, random.Random(1))
    seen.append(play_turn(g))
    games.leave(g, "p1")
    while g["phase"] != "end":
        games.next_step(g, random.Random(1))
        if g["phase"] == "pick":
            seen.append(play_turn(g))
    assert sorted(seen) == ["h", "p1", "p2", "p3", "p4"]


def test_a_late_joiner_gets_a_turn_and_nobody_passes_twice_too_many():
    g = games.new_game("reflet", host="h", name="Léa")
    for i in range(1, 4):
        games.join(g, f"p{i}", f"Ami{i}")
    reflet.configure(g, {"turns": 2})
    games.start(g, random.Random(2))
    seen = []
    while g["phase"] != "end":
        if g["phase"] == "pick":
            seen.append(play_turn(g))
            if len(seen) == 5:
                games.join(g, "late", "Tardif")
        games.next_step(g, random.Random(3))
    assert {x: seen.count(x) for x in set(seen)} == {"h": 2, "p1": 2, "p2": 2, "p3": 2, "late": 2}


def test_the_result_keeps_its_mirror_even_if_they_leave():
    g = table(5)
    reflet.pick(g, "h", 0, 3)
    for gid in ("p1", "p2", "p3", "p4"):
        reflet.vote(g, gid, True)
    games.leave(g, "h")
    v = games.view(g, "p1")["reflet"]
    assert g["phase"] == "result" and v["mirror"]["name"] == "Léa" and v["result"]["name"] == "Léa"


def test_no_voter_means_no_points_and_bad_types_are_refused():
    g = table()
    with pytest.raises(reflet.RefletError):
        reflet.pick(g, "h", 0, 1.7)
    with pytest.raises(reflet.RefletError):
        reflet.pick(g, "h", True, 1)
    reflet.pick(g, "h", 0, 0)
    for gid in ("p1", "p2", "p3"):
        reflet.skip(g, gid)
    assert g["reflet"]["result"]["points"] == 0
    with pytest.raises(reflet.RefletError):
        reflet.configure(games.new_game("reflet", host="x", name="X"), {"turns": True})


def test_too_few_votes_keep_the_result_secret_and_score_nothing():
    g = table()
    reflet.pick(g, "h", 0, 0)
    reflet.vote(g, "p1", False)
    reflet.skip(g, "p2")
    reflet.skip(g, "p3")
    r = g["reflet"]["result"]
    assert r["hidden"] and r["yes"] == 0 and r["voters"] == 0 and r["points"] == 0
