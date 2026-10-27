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
    for bad in (["5H"], ["4H"], ["AC", "5H"], ["5H", "5H"], ["3C", "3D"]):
        with pytest.raises(pr.PresidentError):
            play(g, "player-1", bad)
        assert g == before
    play(g, "player-1", ["5H", "5S"])
    assert g["president"]["pile"]["rank"] == 2


def test_passing_is_final_for_the_trick_and_everyone_passing_clears_pile():
    g = state_with({"player-0": ["3C", "7C", "QC"], "player-1": ["4C", "8C", "AC"], "player-2": ["5C", "6C", "KC"]})
    play(g, "player-0", ["3C"])
    pass_turn(g, "player-1")
    play(g, "player-2", ["5C"])
    assert g["president"]["turn"] == "player-0"  # player-1 a passé : il est sauté jusqu'à la fin du pli
    with pytest.raises(pr.PresidentError):
        pr.play(g, "player-1", ["8C"], pr.view(g, "player-1")["token"])
    pass_turn(g, "player-0")  # tous les autres ont passé : le pli est ramassé
    s = g["president"]
    assert s["pile"] is None and s["turn"] == "player-2" and s["passed"] == []
    with pytest.raises(pr.PresidentError):
        pass_turn(g, "player-2")
    play(g, "player-2", ["6C"])  # nouveau pli : tout le monde peut rejouer
    play(g, "player-0", ["7C"])
    play(g, "player-1", ["8C"])


def test_turn_skips_players_who_passed():
    g = state_with({"player-0": ["JC", "JH", "3C"], "player-1": ["4C", "KC"], "player-2": ["JD", "JS", "5C"],
                    "player-3": ["QC", "QD", "9C"]})
    play(g, "player-0", ["3C"])
    pass_turn(g, "player-1")
    pass_turn(g, "player-2")
    play(g, "player-3", ["9C"])
    play(g, "player-0", ["JC"])  # player-1 et player-2 ont passé : le tour revient à player-3
    assert g["president"]["turn"] == "player-3"


def test_play_after_everyone_else_passed_closes_the_trick_for_its_author():
    g = state_with({"player-0": ["3C", "9C"], "player-1": ["4C", "KC"], "player-2": ["5C", "AC"]})
    play(g, "player-0", ["3C"])
    pass_turn(g, "player-1")
    pass_turn(g, "player-2")  # tout le monde a passé sur le 3 : player-0 rouvre
    s = g["president"]
    assert s["pile"] is None and s["turn"] == "player-0"


def test_finished_leader_hands_new_trick_to_next_active_player():
    g = state_with({"player-0": ["AC"], "player-1": ["4C", "8C"], "player-2": ["5C", "6C"]})
    play(g, "player-0", ["AC"])  # termine : on ne joue pas dessus, le pli est ramassé et le suivant ouvre
    assert g["president"]["turn"] == "player-1" and g["president"]["pile"] is None
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


# ── Compléter la famille ──
def family_table(turn="player-0"):
    return state_with({"player-0": ["7C", "JC", "JH", "QC", "QH", "AC"], "player-1": ["7H", "9C", "QD", "JK1", "KC"],
                       "player-2": ["7D", "7S", "JD", "JS", "9D", "KD"]}, turn=turn)


def test_same_value_is_allowed_then_it_is_that_value_or_nothing():
    g = family_table()
    play(g, "player-0", ["7C"])
    play(g, "player-1", ["7H"])  # même valeur : autorisé
    pile = pr.view(g, "player-2")["pile"]
    assert pile["locked"] and pile["family"] == 2
    with pytest.raises(pr.PresidentError, match="ou rien"):
        play(g, "player-2", ["9D"])  # plus fort, mais « 7 ou rien »
    play(g, "player-2", ["7D"])
    assert g["president"]["pile"]["family"] == 3


def test_completing_the_family_closes_the_trick_and_the_completer_opens():
    g = state_with({"player-0": ["7C", "7S", "QC"], "player-1": ["7H", "9C"], "player-2": ["7D", "KD"]})
    play(g, "player-0", ["7C"])
    play(g, "player-1", ["7H"])
    play(g, "player-2", ["7D"])
    play(g, "player-0", ["7S"])  # le 4e sept, à son tour
    s = g["president"]
    assert s["pile"] is None and s["turn"] == "player-0" and "famille" in s["notice"]


def test_a_pair_completes_the_family_out_of_turn():
    """Le cas de la soirée : un double valet posé, l'autre double valet complète la famille, même hors tour."""
    g = family_table()
    play(g, "player-0", ["JC", "JH"])
    assert g["president"]["turn"] == "player-1"
    play(g, "player-2", ["JD", "JS"])  # pas son tour, mais il complète les 4 valets
    s = g["president"]
    assert s["pile"] is None and s["turn"] == "player-2" and s["trick"] == 2


def test_out_of_turn_is_only_for_completing_the_family():
    g = family_table()
    play(g, "player-0", ["7C"])
    with pytest.raises(pr.PresidentError, match="pas ton tour"):
        play(g, "player-2", ["7D"])  # même valeur, mais il manque encore des 7 : il faut attendre son tour
    with pytest.raises(pr.PresidentError, match="pas ton tour"):
        play(g, "player-2", ["KD"])


def test_a_joker_counts_in_the_family():
    g = family_table()
    play(g, "player-0", ["QC", "QH"])
    play(g, "player-1", ["QD", "JK1"])  # deux dames de plus (dont un joker) : famille complète
    assert g["president"]["pile"] is None and g["president"]["turn"] == "player-1"


def test_completing_with_the_last_cards_finishes_and_the_next_player_opens():
    g = state_with({"player-0": ["JC", "JH", "3C"], "player-1": ["4C", "5C"], "player-2": ["JD", "JS"]})
    play(g, "player-0", ["JC", "JH"])
    play(g, "player-2", ["JD", "JS"])  # hors tour, et c'étaient ses dernières cartes
    s = g["president"]
    assert s["finished"] == ["player-2"] and s["pile"] is None and s["turn"] == "player-0"


# ── Le 2 ferme le pli ──
@pytest.mark.parametrize("twos", [["2C"], ["2C", "2D"], ["2C", "2D", "2H"], ["2C", "JK1"]])
def test_a_two_closes_the_trick_and_its_player_reopens(twos):
    g = state_with({"player-0": ["5C", "5D", "5H", "4C"], "player-1": ["2C", "2D", "2H", "JK1", "9C"], "player-2": ["KC", "KD", "KH"]})
    play(g, "player-0", ["5C", "5D", "5H"][: len(twos)])
    play(g, "player-1", twos)
    s = g["president"]
    assert s["pile"] is None and s["turn"] == "player-1" and s["trick"] == 2 and "2" in s["notice"]


def test_opening_with_a_two_also_closes_the_trick():
    g = state_with({"player-0": ["2C", "4C"], "player-1": ["9C"], "player-2": ["KC"]})
    play(g, "player-0", ["2C"])
    assert g["president"]["pile"] is None and g["president"]["turn"] == "player-0"


def test_finishing_on_a_two_hands_the_new_trick_to_the_next_player():
    g = state_with({"player-0": ["5C"], "player-1": ["2C"], "player-2": ["KC", "4C"], "player-3": ["QC", "6C"]})
    play(g, "player-0", ["5C"])  # player-0 termine
    play(g, "player-1", ["2C"])  # player-1 finit sur un 2 : le pli est fermé, et il sera Trou du cul
    s = g["president"]
    assert g["phase"] == "play" and s["finished"] == ["player-0"] and s["dunce"] == ["player-1"]
    assert s["pile"] is None and s["turn"] == "player-2"


# ── Derniers coups visibles ──
def test_the_last_five_plays_stay_visible_with_the_latest_last():
    g = state_with({"player-0": ["3C", "6C", "9C", "QC"], "player-1": ["4C", "7C", "10C", "KC"], "player-2": ["5C", "8C", "JC", "AC"]})
    for gid, card in [("player-0", "3C"), ("player-1", "4C"), ("player-2", "5C"), ("player-0", "6C"), ("player-1", "7C"), ("player-2", "8C")]:
        play(g, gid, [card])
    trail = pr.view(g, "player-0")["trail"]
    assert [(t["name"], [c["id"] for c in t["cards"]]) for t in trail] == [
        ("J1", ["4C"]), ("J2", ["5C"]), ("J0", ["6C"]), ("J1", ["7C"]), ("J2", ["8C"])]
    assert trail[-1]["rank"] == "8"


def test_a_new_trick_starts_from_zero():
    g = state_with({"player-0": ["5C", "9C"], "player-1": ["2C", "4C", "QC"], "player-2": ["KC", "KD"]})
    play(g, "player-0", ["5C"])
    play(g, "player-1", ["2C"])  # ferme le pli
    assert pr.view(g, "player-2")["trail"] == []
    play(g, "player-1", ["4C"])
    assert [t["name"] for t in pr.view(g, "player-2")["trail"]] == ["J1"]


def test_a_new_deal_clears_the_trail():
    g = state_with({"player-0": ["5C", "9C"], "player-1": ["6C", "4C"], "player-2": ["KC", "KD"]})
    play(g, "player-0", ["5C"])
    g["phase"] = "end"
    games.start(g, random.Random(3))
    assert pr.view(g, "player-0")["trail"] == []


def test_passed_player_is_out_even_for_completing_the_family():
    g = state_with({"player-0": ["9C", "9D", "4C"], "player-1": ["5C", "KC"], "player-2": ["JD", "JS", "6C"],
                    "player-3": ["JC", "JH", "8C"]})
    play(g, "player-0", ["9C", "9D"])
    pass_turn(g, "player-1")
    pass_turn(g, "player-2")  # il a pourtant deux valets
    play(g, "player-3", ["JC", "JH"])
    with pytest.raises(pr.PresidentError, match="passé"):
        pr.play(g, "player-2", ["JD", "JS"], pr.view(g, "player-2")["token"])  # compléterait, mais il a passé


# ── « … ou rien » : un tour sans complément lève la contrainte ──
def test_or_nothing_binds_only_the_next_player():
    """6, puis 6 : le joueur 3 doit mettre un 6 ; s'il n'en a pas, le joueur 4 met ce qu'il veut, 6 ou au-dessus."""
    g = state_with({"player-0": ["6C", "4C", "AC"], "player-1": ["6H", "QC", "5C"], "player-2": ["KC", "8C", "7C"],
                    "player-3": ["9C", "6D", "3D"]})
    play(g, "player-0", ["6C"])
    play(g, "player-1", ["6H"])  # « 6 ou rien » pour player-2
    with pytest.raises(pr.PresidentError, match="ou rien"):
        play(g, "player-2", ["KC"])
    pass_turn(g, "player-2")  # pas de 6 : la contrainte tombe, il reste dans le pli
    s = g["president"]
    assert s["pile"] and not s["pile"]["locked"] and s["turn"] == "player-3" and s["passed"] == []
    play(g, "player-3", ["9C"])  # au-dessus du 6
    play(g, "player-0", ["AC"])
    pass_turn(g, "player-1")
    assert g["president"]["turn"] == "player-2"  # il n'avait pas de 6, mais il est encore dans le pli


def test_after_an_or_nothing_the_next_player_may_also_put_the_same_value():
    g = state_with({"player-0": ["6C", "4C"], "player-1": ["6H", "QC"], "player-2": ["KC", "8C"], "player-3": ["6D", "3D"]})
    play(g, "player-0", ["6C"])
    play(g, "player-1", ["6H"])
    pass_turn(g, "player-2")
    play(g, "player-3", ["6D"])  # un 6 : de nouveau « 6 ou rien » pour le suivant
    assert g["president"]["pile"]["locked"] and g["president"]["pile"]["family"] == 3


def test_a_real_pass_outside_or_nothing_is_still_final():
    g = state_with({"player-0": ["JC", "4C", "AC"], "player-1": ["JH", "QC", "5C"], "player-2": ["KC", "6C", "7C"]})
    play(g, "player-0", ["4C"])
    pass_turn(g, "player-1")
    play(g, "player-2", ["6C"])
    assert g["president"]["turn"] == "player-0"
    play(g, "player-0", ["JC"])
    assert g["president"]["turn"] == "player-2"  # player-1 a vraiment passé


# ── Interdit de finir sur un 2 ──
def roles(g):
    return {r["name"]: r["role"] for r in pr.view(g, "player-0")["ranking"]}


def test_finishing_on_a_two_makes_you_the_dunce():
    g = state_with({"player-0": ["5C", "9C"], "player-1": ["2C"], "player-2": ["KC", "4C"], "player-3": ["QC", "6C"]})
    play(g, "player-0", ["5C"])
    play(g, "player-1", ["2C"])  # sa dernière carte est un 2
    assert "Trou du cul" in g["president"]["notice"]
    play(g, "player-2", ["4C"])
    play(g, "player-3", ["6C"])
    play(g, "player-0", ["9C"])  # player-0 termine premier : le pli est ramassé, player-2 ouvre
    play(g, "player-2", ["KC"])  # player-2 termine
    assert g["phase"] == "end"
    assert [r["name"] for r in pr.view(g, "player-0")["ranking"]] == ["J0", "J2", "J3", "J1"]
    assert roles(g)["J1"] == "Trou du cul"


def test_a_second_two_finisher_pushes_the_first_one_up():
    g = state_with({"player-0": ["2C"], "player-1": ["5C", "2D"], "player-2": ["KC", "4C"], "player-3": ["QC", "6C", "7C"]})
    play(g, "player-0", ["2C"])  # premier à finir sur un 2
    play(g, "player-1", ["5C"])
    play(g, "player-2", ["KC"])
    pass_turn(g, "player-3")
    play(g, "player-1", ["2D"])  # deuxième à finir sur un 2 : c'est lui le Trou du cul, l'ancien remonte
    play(g, "player-2", ["4C"])  # player-2 termine ; seul player-3 reste
    assert g["phase"] == "end"
    assert [r["name"] for r in pr.view(g, "player-0")["ranking"]] == ["J2", "J3", "J0", "J1"]
    assert roles(g) == {"J2": "Président", "J3": "Vice-président", "J0": "Vice-trou du cul", "J1": "Trou du cul"}


def test_a_joker_alone_is_not_a_two():
    g = state_with({"player-0": ["JK1"], "player-1": ["5C", "9C"], "player-2": ["KC", "4C"]})
    play(g, "player-0", ["JK1"])
    assert g["president"]["finished"] == ["player-0"] and g["president"].get("dunce", []) == []


# ── On ne joue pas sur celui qui termine ──
def test_nobody_plays_on_the_last_cards_of_a_finisher():
    g = state_with({"player-0": ["9C", "9D"], "player-1": ["KC", "KD", "4C"], "player-2": ["AC", "AD", "5C"]})
    play(g, "player-0", ["9C", "9D"])  # ses dernières cartes : il est Président
    s = g["president"]
    assert s["finished"] == ["player-0"] and s["pile"] is None and s["turn"] == "player-1"
    assert "ouvre" in s["notice"]
    play(g, "player-1", ["4C"])  # le suivant commence par ce qu'il veut


def test_after_the_president_others_can_be_played_on():
    g = state_with({"player-0": ["9C"], "player-1": ["KC", "4C"], "player-2": ["AC", "AD", "5C"], "player-3": ["QC", "QD", "6C"]})
    play(g, "player-0", ["9C"])  # Président : le pli est ramassé
    play(g, "player-1", ["4C"])
    play(g, "player-2", ["5C"])
    play(g, "player-3", ["6C"])
    play(g, "player-1", ["KC"])  # player-1 termine (2e) : on peut encore jouer dessus
    s = g["president"]
    assert s["finished"] == ["player-0", "player-1"] and s["pile"]["rank"] == pr.RANKS.index("K")
    assert s["turn"] == "player-2"
    play(g, "player-2", ["AC"])


# ── Animations : qui a joué, et les échanges de la donne ──
def test_trail_tells_which_seat_played():
    g = state_with({"player-0": ["3C", "6C"], "player-1": ["4C", "7C"], "player-2": ["5C", "8C"]})
    play(g, "player-0", ["3C"])
    v = pr.view(g, "player-1")
    assert v["trail"][-1]["pid"] == next(p["pid"] for p in g["players"] if p["id"] == "player-0")


def test_exchange_summary_is_public_but_cards_stay_private():
    g = new_table()
    finish(g)
    games.restart(g)
    s = g["president"]
    for gid, job in list(s["exchange"].items()):
        if not job["best"]:
            pr.exchange_cards(g, gid, s["hands"][gid][:job["count"]], pr.view(g, gid)["exchange"]["token"])
    assert g["phase"] == "play"
    pids = {p["id"]: p["pid"] for p in g["players"]}
    for p in g["players"]:
        swap = pr.view(g, p["id"])["swap"]
        assert swap["key"] and len(swap["moves"]) == 4 and sum(m["count"] for m in swap["moves"]) == 6
        mine_out = [m for m in swap["moves"] if m["from"] == pids[p["id"]]]
        mine_in = [m for m in swap["moves"] if m["to"] == pids[p["id"]]]
        assert len(swap["gave"]) == sum(m["count"] for m in mine_out)
        assert len(swap["got"]) == sum(m["count"] for m in mine_in)
        assert all(c["id"] in s["hands"][p["id"]] for c in swap["got"])  # ce qu'on a reçu est dans sa main
    watcher = "watcher-x"
    games.join(g, watcher, "Spectateur")
    assert pr.view(g, watcher)["swap"]["got"] == [] and pr.view(g, watcher)["swap"]["gave"] == []


def test_no_exchange_summary_after_the_first_trick():
    g = state_with({"player-0": ["3C", "6C"], "player-1": ["4C", "7C"], "player-2": ["5C", "8C"]})
    g["president"]["swap"] = {"moves": [], "cards": {}}
    g["president"]["trick"] = 2
    assert pr.view(g, "player-0")["swap"] is None


def test_out_of_turn_completion_only_with_a_pair():
    """En simple, on ne complète la famille qu'à son tour ; hors tour, seulement en double (paire sur paire)."""
    g = state_with({"player-0": ["7C", "7S", "QC"], "player-1": ["7H", "9C"], "player-2": ["7D", "KD"], "player-3": ["5C", "AC"]})
    play(g, "player-0", ["7C"])
    play(g, "player-1", ["7H"])
    play(g, "player-2", ["7D"])  # 3 sept posés ; c'est à player-3
    with pytest.raises(pr.PresidentError, match="pas ton tour"):
        play(g, "player-0", ["7S"])  # compléterait, mais en simple : interdit hors tour
