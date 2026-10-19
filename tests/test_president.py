"""Règles de la variante jouée à la soirée, confidentialité et transitions."""
import copy
import json
import random
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import games, main, president as pr


def new_table(n=4, seed=7):
    g = games.new_game("president", "player-0", "J0", code="8765")
    for i in range(1, n):
        games.join(g, f"player-{i}", f"J{i}")
    games.start(g, random.Random(seed))
    return g


def state_with(hands, turn="player-0"):
    g = new_table(len(hands))
    s = g["president"]
    s.update(hands=hands, turn=turn, pile=None, finished=[], departed=[], passed=[], discard=[])
    return g


def play(g, gid, cards):
    pr.play(g, gid, cards, pr.view(g, gid)["token"])


def pass_turn(g, gid):
    pr.pass_turn(g, gid, pr.view(g, gid)["token"])


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_deal_is_complete_balanced_and_private(n):
    g = new_table(n)
    hands = g["president"]["hands"]
    all_cards = [c for hand in hands.values() for c in hand]
    assert len(all_cards) == len(set(all_cards)) == 54
    assert set(all_cards) == set(pr.deck())
    assert max(map(len, hands.values())) - min(map(len, hands.values())) <= 1
    assert "3C" in hands[g["president"]["turn"]]
    for p in g["players"]:
        v = games.view(g, p["id"])
        assert {c["id"] for c in v["president"]["hand"]} == set(hands[p["id"]])
        assert all(other not in json.dumps(v) for other in hands)
        assert "hands" not in json.dumps(v)
    games.join(g, "watcher-1", "Spectateur") if n < 6 else None
    assert not games.view(g, "watcher-1")["president"]["hand"]
    g["leads"] = ["admin-0001"]
    assert not games.view(g, "admin-0001")["president"]["hand"]


@pytest.mark.parametrize("cards,value", [(["JK1"], 0), (["JK1", "JK2"], 0), (["AH", "JK1"], 11),
                                         (["7C", "7H", "JK1", "JK2"], 4), (["2C", "JK2"], 12)])
def test_jokers_are_threes_alone_and_duplicate_the_other_rank(cards, value):
    assert pr.combination(cards) == value


@pytest.mark.parametrize("cards", [[], ["JK1", "JK1"], ["4C", "5C", "JK1"], ["3C", "3D", "3H", "3S", "JK1"]])
def test_invalid_combinations(cards):
    with pytest.raises(pr.PresidentError):
        pr.combination(cards)


def test_same_count_strictly_higher_and_no_stolen_cards():
    g = state_with({"player-0": ["4C", "4D", "AC"], "player-1": ["4H", "4S", "5H", "5S", "6H"], "player-2": ["2C"]})
    play(g, "player-0", ["4C", "4D"])
    before = copy.deepcopy(g)
    for bad in (["5H"], ["4H", "4S"], ["AC", "5H"], ["5H", "5H"]):
        with pytest.raises(pr.PresidentError):
            play(g, "player-1", bad)
        assert g == before
    play(g, "player-1", ["5H", "5S"])
    assert g["president"]["pile"]["rank"] == 2


def test_passing_does_not_ban_reentry_and_everyone_passing_clears_pile():
    g = state_with({"player-0": ["3C", "7C"], "player-1": ["4C", "8C"], "player-2": ["5C", "6C"]})
    play(g, "player-0", ["3C"])
    pass_turn(g, "player-1")
    play(g, "player-2", ["5C"])
    pass_turn(g, "player-0")
    play(g, "player-1", ["8C"])
    pass_turn(g, "player-2")
    pass_turn(g, "player-0")
    assert g["president"]["pile"] is None
    assert g["president"]["turn"] == "player-1"
    with pytest.raises(pr.PresidentError):
        pass_turn(g, "player-1")


def test_finished_leader_hands_new_trick_to_next_active_player():
    g = state_with({"player-0": ["2C"], "player-1": ["4C", "8C"], "player-2": ["5C", "6C"]})
    play(g, "player-0", ["2C"])
    pass_turn(g, "player-1")
    pass_turn(g, "player-2")
    assert g["president"]["turn"] == "player-1"
    assert g["president"]["pile"] is None
    play(g, "player-1", ["4C"])
    play(g, "player-2", ["6C"])
    play(g, "player-1", ["8C"])
    assert g["phase"] == "end"
    assert g["president"]["finished"] == ["player-0", "player-1", "player-2"]
    assert [r["role"] for r in pr.view(g, "player-0")["ranking"]] == ["Président", "Neutre", "Trou du cul"]
    assert g["president"]["scores"] == {"player-0": 2, "player-1": 1, "player-2": 0}


def finish(g):
    for _ in range(1200):
        if g["phase"] == "end":
            return
        s = g["president"]
        gid = s["turn"]
        cards = sorted(s["hands"][gid], key=pr.rank)
        playable = [c for c in cards if not s["pile"] or pr.rank(c) > s["pile"]["rank"]]
        if playable:
            play(g, gid, playable[:1])
        else:
            pass_turn(g, gid)
        all_cards = [c for h in s["hands"].values() for c in h] + s["discard"] + (s["pile"] or {}).get("cards", [])
        assert len(all_cards) == len(set(all_cards)) == 54
    pytest.fail("La manche ne se termine pas")


@pytest.mark.parametrize("n", [3, 4, 5, 6])
@pytest.mark.parametrize("seed", [1, 8, 21])
def test_two_complete_rounds_with_exchange_and_card_conservation(n, seed):
    g = new_table(n, seed)
    finish(g)
    scores = dict(g["president"]["scores"])
    last = g["president"]["finished"][-1]
    games.next_step(g, random.Random(seed + 1))
    s = g["president"]
    assert g["phase"] == "exchange"
    assert len(s["exchange"]) == (2 if n == 3 else 4)
    before = copy.deepcopy(s["hands"])
    for gid, offer in s["offered"].items():
        assert sorted(map(pr.rank, offer), reverse=True) == sorted(map(pr.rank, before[gid]), reverse=True)[:len(offer)]
    for gid, job in list(s["exchange"].items()):
        if not job["best"]:
            v = pr.view(g, gid)
            pr.exchange_cards(g, gid, s["hands"][gid][:job["count"]], v["exchange"]["token"])
    assert g["phase"] == "play" and s["turn"] == last
    assert {i: len(h) for i, h in s["hands"].items()} == {i: len(h) for i, h in before.items()}
    finish(g)
    assert all(s["scores"][i] >= pts for i, pts in scores.items())
    assert sum(s["scores"].values()) == n * (n - 1)


def test_no_redistribution_mid_hand_or_duplicate_moves():
    g = new_table()
    s = g["president"]
    gid = s["turn"]
    token = pr.view(g, gid)["token"]
    cards = s["hands"][gid][:1]
    before = copy.deepcopy(g)
    with pytest.raises(pr.PresidentError):
        games.start(g)
    assert g == before
    def submit():
        try:
            pr.play(g, gid, cards, token)
            return True
        except pr.PresidentError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: submit(), range(2))) == [False, True]


def test_departure_turn_waiting_rejoin_and_roster_change():
    g = new_table(4)
    gid = g["president"]["turn"]
    games.leave(g, gid)
    assert g["president"]["turn"] != gid
    assert gid not in g["president"]["hands"]
    games.join(g, gid, "De retour")
    assert games.player(g, gid)["waiting"]
    assert not pr.view(g, gid)["hand"]
    finish(g)
    assert g["president"]["finished"][-1] == gid
    games.restart(g)
    assert g["phase"] == "play"  # abandon : pas d'échange issu d'un classement incomplet
    assert not games.player(g, gid)["waiting"]


def test_departure_cancels_exchange_without_awarding_points():
    g = new_table()
    finish(g)
    scores = dict(g["president"]["scores"])
    games.restart(g)
    games.leave(g, "player-2")
    assert g["phase"] == "lobby"
    assert g["president"]["scores"] == scores
    assert not pr.view(g, "player-0")["hand"]
    games.start(g)
    assert g["phase"] == "play"


def test_exchange_rejects_bad_selection_and_never_leaks_other_choices():
    g = new_table()
    finish(g)
    games.restart(g)
    s = g["president"]
    high = next(i for i, job in s["exchange"].items() if job["count"] == 2 and not job["best"])
    low = s["exchange"][high]["to"]
    v = pr.view(g, high)
    assert v["exchange"]["cards"] == []
    before = copy.deepcopy(g)
    for cards in ([], s["hands"][high][:1], [s["hands"][high][0]] * 2, s["hands"][low][:2]):
        with pytest.raises(pr.PresidentError):
            pr.exchange_cards(g, high, cards, v["exchange"]["token"])
        assert g == before


def test_api_authority_private_hands_persistence_and_room_points(monkeypatch, tmp_path):
    from app.party import PartyStore
    monkeypatch.setattr(main, "store", PartyStore(tmp_path / "session.json"))
    monkeypatch.setattr(main, "_game_creations", {})
    c = TestClient(main.app)
    host = "president-host-01"
    r = c.post("/api/games", json={"type": "room", "guest_id": host, "name": "Ludo"}).json()
    code = r["code"]
    for i in range(2):
        assert c.post(f"/api/games/{code}", json={"action": "join", "guest_id": f"president-other-{i}", "name": f"J{i}"}).status_code == 200
    r = c.post(f"/api/games/{code}", json={"action": "launch", "guest_id": host, "settings": {"type": "president"}})
    assert r.status_code == 200
    child = r.json()["room_info"]["current"]["code"]
    url = f"/api/games/{child}"
    assert c.post(url, json={"action": "start", "guest_id": "president-other-0"}).status_code == 403
    assert c.post(url, json={"action": "start", "guest_id": host}).status_code == 200
    g = main.store.session.games[child]
    turn = g["president"]["turn"]
    other = next(p for p in g["players"] if p["id"] != turn)
    view = c.get(url, params={"guest_id": turn}).json()["president"]
    # Même l'animateur ne peut pas jouer la main d'un autre via le champ "who".
    r = c.post(url, json={"action": "prplay", "guest_id": other["id"], "who": games.player(g, turn)["pid"],
                         "values": [view["hand"][0]["id"]], "guess": view["token"]})
    assert r.status_code == 409
    snapshot = json.loads(json.dumps(g))
    assert pr.view(snapshot, turn) == pr.view(g, turn)
    finish(g)
    total = sum(g["president"]["scores"].values())
    assert c.post(url, json={"action": "end", "guest_id": host}).status_code == 200
    board = c.get(f"/api/games/{code}", params={"guest_id": host}).json()["room_info"]["board"]
    assert sum(p["pts"] for p in board) == total == 3


def test_player_limits():
    g = games.new_game("president", "player-0", "J0")
    with pytest.raises(pr.PresidentError):
        games.start(g)
    for i in range(1, 6):
        games.join(g, f"player-{i}", f"J{i}")
    with pytest.raises(games.GameError):
        games.join(g, "player-6", "En trop")
