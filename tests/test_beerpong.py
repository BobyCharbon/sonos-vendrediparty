"""Beer pong : on joue avec une vraie table ; l'app ne gère pas les tours. L'animateur (ou le marqueur qu'il
désigne) touche le gobelet perdu, qui l'a perdu, puis choisit la sentence (gage, question WTF, quiz, sport,
gorgées, shot, bonus ou malus). L'équipe qui n'a plus de gobelets a perdu."""
import random

import pytest

from app import beerpong as bp
from app import games


def table(n=4, cups=6, rng=None):
    g = games.new_game("beerpong", "bp-host-0001", "Boby", code="4242")
    for i in range(1, n):
        games.join(g, f"bp-player-{i:03d}", f"P{i}")
    bp.configure(g, {"cups": cups})
    games.start(g, rng or random.Random(4))
    return g


def test_teams_are_balanced_red_and_blue():
    g = table(n=5)
    teams = g["bp"]["teams"]
    reds = [gid for gid, t in teams.items() if t == "red"]
    blues = [gid for gid, t in teams.items() if t == "blue"]
    assert abs(len(reds) - len(blues)) <= 1 and len(reds) + len(blues) == 5
    assert g["phase"] == "play" and g["bp"]["racks"]["red"] == [True] * 6


def test_the_host_moves_a_player_to_the_other_team_before_starting():
    g = games.new_game("beerpong", "bp-host-0001", "Boby", code="4243")
    games.join(g, "bp-player-001", "Léa")
    bp.configure(g, {"team": {"pid": games.player(g, "bp-player-001")["pid"], "team": "blue"}})
    assert g["bp"]["teams"]["bp-player-001"] == "blue"


def test_a_lost_cup_then_a_sentence_chosen_among_proposals():
    g = table()
    red = next(gid for gid, t in g["bp"]["teams"].items() if t == "red")
    bp.hit(g, "red", 2, games.player(g, red)["pid"], random.Random(1))
    assert g["bp"]["racks"]["red"][2] is False
    pending = g["bp"]["pending"]
    assert pending["team"] == "red" and len(pending["options"]) == 3
    bp.sentence(g, 0, random.Random(1))
    assert g["bp"]["pending"] is None and g["bp"]["last"]["name"] == games.player(g, red)["name"]
    assert g["bp"]["log"][-1]["cup"] == 2


def test_sips_and_shots_are_counted_for_the_tv():
    g = table()
    red = next(gid for gid, t in g["bp"]["teams"].items() if t == "red")
    bp.hit(g, "red", 0, games.player(g, red)["pid"], random.Random(1))
    g["bp"]["pending"]["options"][0] = {"kind": "sips", "text": "Bois 3 gorgées", "sips": 3}
    bp.sentence(g, 0, random.Random(1))
    assert g["tally"][red]["drink"] == 3 and g["sips_log"][-1]["drink"] == 3


def test_a_cup_cannot_be_lost_twice_and_a_sentence_is_needed_before_the_next_cup():
    g = table()
    pid = next(p["pid"] for p in g["players"] if g["bp"]["teams"][p["id"]] == "blue")
    bp.hit(g, "blue", 1, pid, random.Random(1))
    with pytest.raises(bp.BeerPongError):
        bp.hit(g, "blue", 3, pid, random.Random(1))  # d'abord la sentence
    bp.sentence(g, 1, random.Random(1))
    with pytest.raises(bp.BeerPongError):
        bp.hit(g, "blue", 1, pid, random.Random(1))  # déjà tombé


def test_the_team_without_cups_loses_and_the_game_ends():
    g = table(cups=6)
    pid = next(p["pid"] for p in g["players"] if g["bp"]["teams"][p["id"]] == "blue")
    for cup in range(6):
        bp.hit(g, "blue", cup, pid, random.Random(cup))
        bp.sentence(g, 0, random.Random(cup))
    assert g["phase"] == "end" and g["bp"]["winner"] == "red"


def test_undo_puts_the_last_cup_back():
    g = table()
    pid = next(p["pid"] for p in g["players"] if g["bp"]["teams"][p["id"]] == "red")
    bp.hit(g, "red", 4, pid, random.Random(1))
    bp.undo(g)
    assert g["bp"]["racks"]["red"][4] is True and g["bp"]["pending"] is None


def test_bonus_brings_a_cup_back_and_malus_takes_one_more():
    g = table()
    pid = next(p["pid"] for p in g["players"] if g["bp"]["teams"][p["id"]] == "red")
    bp.hit(g, "red", 0, pid, random.Random(1))
    g["bp"]["pending"]["options"][0] = {"kind": "bonus", "text": "Le gobelet revient", "effect": "cup_back"}
    bp.sentence(g, 0, random.Random(1))
    assert g["bp"]["racks"]["red"][0] is True
    bp.hit(g, "red", 1, pid, random.Random(1))
    g["bp"]["pending"]["options"][0] = {"kind": "malus", "text": "Un gobelet de plus", "effect": "cup_off"}
    bp.sentence(g, 0, random.Random(1))
    assert g["bp"]["racks"]["red"].count(False) == 2


def test_only_enabled_sentence_kinds_are_proposed():
    g = table()
    bp.configure_live(g, {"kinds": ["sport"]})
    pid = g["players"][0]["pid"]
    team = g["bp"]["teams"][g["players"][0]["id"]]
    bp.hit(g, team, 0, pid, random.Random(2))
    assert {o["kind"] for o in g["bp"]["pending"]["options"]} == {"sport"}


def test_the_view_hides_nothing_secret_and_shows_the_racks():
    g = table()
    v = bp.view(g, "")
    assert set(v["racks"]) == {"red", "blue"} and v["cups"] == 6 and {"red", "blue"} == {t["team"] for t in v["players"]}


def test_api_flow_host_marker_and_tv():
    from fastapi.testclient import TestClient

    from app import main
    main._game_creations.clear()
    before = set(main.store.session.games)
    c, tv = TestClient(main.app), TestClient(main.app)
    try:
        code = c.post("/api/games", json={"type": "beerpong", "guest_id": "bp-api-host-01", "name": "Boby"}).json()["code"]
        act = lambda gid, **b: c.post(f"/api/games/{code}", json={"guest_id": gid, **b})  # noqa: E731
        for i, n in enumerate(["Léa", "Tom", "Nina"]):
            act(f"bp-api-p-{i:04d}", action="join", name=n)
        assert act("bp-api-p-0000", action="bpset", settings={"cups": 6}).status_code == 403  # réglages : l'animateur
        assert act("bp-api-host-01", action="bpset", settings={"cups": 6, "kinds": ["sips", "sport"]}).status_code == 200
        v = act("bp-api-host-01", action="start").json()
        lea = next(p for p in v["bp"]["players"] if p["name"] == "Léa")
        hit = {"team": lea["team"], "cup": 0, "pid": lea["pid"]}
        assert act("bp-api-p-0001", action="bphit", settings=hit).status_code == 409  # Tom n'est pas marqueur
        act("bp-api-host-01", action="bpset", settings={"marker": next(p["pid"] for p in v["bp"]["players"] if p["name"] == "Tom")})
        assert act("bp-api-p-0001", action="bphit", settings=hit).status_code == 200  # Tom, marqueur désigné
        assert act("bp-api-p-0001", action="bpsent", amount=1).status_code == 200
        tv.post("/api/admin/login", json={"pin": "9999"})
        view = tv.get(f"/api/tv/game/{code}").json()
        assert view["bp"]["last"]["name"] == "Léa" and view["bp"]["alive"][lea["team"]] == 5
        assert act("bp-api-host-01", action="pans").status_code == 400  # action d'un autre jeu
    finally:
        for k in set(main.store.session.games) - before:
            main.store.session.games.pop(k, None)
        main._game_creations.clear()


def test_a_failed_rematch_leaves_the_table_as_it_was():
    # Trouvé par les bots : « Revanche » sans équipe complète vidait la table d'une partie en cours.
    g = table(n=2, cups=6)
    blue = next(gid for gid, t in g["bp"]["teams"].items() if t == "blue")
    games.leave(g, blue)
    with pytest.raises(games.GameError):
        games.restart(g, random.Random(1))
    assert g["phase"] == "play" and g["bp"]["racks"]["red"] == [True] * 6
