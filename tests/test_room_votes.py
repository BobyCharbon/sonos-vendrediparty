"""Salle de jeux : chaque participant vote pour le jeu qu'il veut jouer (un seul choix, modifiable à tout moment) ;
tout le monde voit le compteur de chaque jeu ; l'animateur ne vote pas mais voit le ou les jeux les plus votés.
Les votes repartent à zéro à chaque jeu lancé."""
import pytest
from fastapi.testclient import TestClient

from app import main

HOST, LEA, TOM, ZOE = "room-vote-host-01", "room-vote-lea-001", "room-vote-tom-001", "room-vote-zoe-001"


@pytest.fixture
def room():
    before = set(main.store.session.games)
    main._game_creations.clear()
    c = TestClient(main.app)
    code = c.post("/api/games", json={"guest_id": HOST, "name": "Ludo", "type": "room", "plays": True}).json()["code"]
    act = lambda gid, **b: c.post(f"/api/games/{code}", json={"guest_id": gid, **b})  # noqa: E731
    for gid, name in [(LEA, "Léa"), (TOM, "Tom"), (ZOE, "Zoé")]:
        assert act(gid, action="join", name=name).status_code == 200
    yield c, code, act
    for k in set(main.store.session.games) - before:
        main.store.session.games.pop(k, None)
    main._game_creations.clear()


def info(c, code, gid=HOST):
    return c.get(f"/api/games/{code}?guest_id={gid}").json()["room_info"]


def test_each_player_has_one_vote_and_can_change_it(room):
    c, code, act = room
    act(LEA, action="rvote", target="quiz")
    act(TOM, action="rvote", target="quiz")
    act(ZOE, action="rvote", target="never")
    r = info(c, code, LEA)
    assert r["votes"] == {"quiz": 2, "never": 1} and r["my_vote"] == "quiz"
    act(LEA, action="rvote", target="never")  # Léa change d'avis : son vote se déplace
    assert info(c, code)["votes"] == {"quiz": 1, "never": 2}
    act(LEA, action="rvote", target="never")  # toucher son propre choix le retire
    assert info(c, code)["votes"] == {"quiz": 1, "never": 1} and info(c, code, LEA)["my_vote"] is None


def test_the_most_voted_games_are_suggested_ties_included(room):
    c, code, act = room
    assert info(c, code)["top"] == []
    act(LEA, action="rvote", target="quiz")
    act(TOM, action="rvote", target="never")
    assert sorted(info(c, code)["top"]) == ["never", "quiz"]  # égalité : les deux
    act(ZOE, action="rvote", target="quiz")
    assert info(c, code)["top"] == ["quiz"]


def test_the_host_does_not_vote_and_unknown_games_are_refused(room):
    c, code, act = room
    assert act(HOST, action="rvote", target="quiz").status_code == 409
    assert act(LEA, action="rvote", target="room").status_code == 409
    assert act(LEA, action="rvote", target="nope").status_code == 409
    assert info(c, code)["votes"] == {}


def test_votes_start_again_after_each_launched_game(room):
    c, code, act = room
    act(LEA, action="rvote", target="biskit")
    act(TOM, action="rvote", target="biskit")
    cur = act(HOST, action="launch", settings={"type": "biskit"}).json()["room_info"]["current"]
    assert info(c, code)["votes"] == {}
    assert act(LEA, action="rvote", target="quiz").status_code == 409  # un jeu est en cours
    act(HOST, action="end") if False else c.post(f"/api/games/{cur['code']}", json={"guest_id": HOST, "action": "end"})
    assert info(c, code)["current"] is None and info(c, code)["votes"] == {}
    act(LEA, action="rvote", target="quiz")
    assert info(c, code)["votes"] == {"quiz": 1}


def test_the_tv_sees_the_votes(room):
    c, code, act = room
    act(LEA, action="rvote", target="quiz")
    assert c.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    assert c.get(f"/api/tv/game/{code}").json()["room_info"]["votes"] == {"quiz": 1}


def test_a_player_who_leaves_takes_his_vote_back(room):
    c, code, act = room
    act(LEA, action="rvote", target="quiz")
    act(LEA, action="leave")
    assert info(c, code)["votes"] == {}
