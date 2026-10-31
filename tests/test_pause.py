"""Pause par l'animateur, dans tous les jeux : plus aucun coup (sauf reprendre, terminer, gérer les joueurs), le temps
s'arrête (question de quiz, bille du casino…) et reprend là où il en était ; tout le monde voit la pause."""
import random
import time

import pytest
from fastapi.testclient import TestClient

from app import games, main

HOST, LEA = "pause-host-00001", "pause-lea-000001"


@pytest.fixture
def make():
    before = set(main.store.session.games)
    made = []

    def create(kind, **opts):
        main._game_creations.clear()
        c = TestClient(main.app)
        code = c.post("/api/games", json={"type": kind, "guest_id": HOST, "name": "Boby", **opts}).json()["code"]
        act = lambda gid, **b: c.post(f"/api/games/{code}", json={"guest_id": gid, **b})  # noqa: E731
        act(LEA, action="join", name="Léa")
        made.append(code)
        return c, code, act
    yield create
    for k in set(main.store.session.games) - before:
        main.store.session.games.pop(k, None)
    main._game_creations.clear()


@pytest.mark.parametrize("kind", ["never", "whoof", "blackjack", "casino", "divan", "beerpong", "undercover", "pyramid", "biskit", "likely", "debate"])
def test_the_host_pauses_any_game_and_nobody_can_play_until_resume(make, kind):
    c, code, act = make(kind)
    act(HOST, action="join", name="Boby")
    act("pause-tom-000001", action="join", name="Tom")
    assert act(HOST, action="start").status_code == 200
    assert act(LEA, action="pause").status_code == 403  # seul l'animateur
    v = act(HOST, action="pause").json()
    assert v["paused"] and v["paused"]["by"] == "Boby"
    assert c.get(f"/api/games/{code}?guest_id={LEA}").json()["paused"]  # tout le monde le voit
    for a in ("vote", "bet", "cbet", "dnext", "spin", "next"):
        r = act(LEA if a not in ("spin", "next") else HOST, action=a, target="yes", amount=5)
        assert r.status_code in (400, 409), (a, r.status_code)
        if r.status_code == 409:
            assert "pause" in r.json()["detail"].lower()
    assert act(HOST, action="resume").json()["paused"] is None


def test_the_quiz_clock_stops_during_the_pause():
    g = games.new_game("quiz", "pause-host-00001", "Boby", code="7777")
    games.join(g, "pause-lea-000001", "Léa")
    games.start(g, random.Random(1))
    deadline = g["quiz"]["cur"]["end"]
    created = g["created_at"]
    games.pause_game(g, "pause-host-00001")
    g["paused"]["at"] -= 30  # la pause a duré 30 s
    games.resume_game(g)
    assert g["quiz"]["cur"]["end"] == pytest.approx(deadline + 30, abs=1)
    assert g["created_at"] == created  # les dates de création ne bougent pas


def test_no_pause_in_the_lobby_or_after_the_end(make):
    c, code, act = make("never")
    assert act(HOST, action="pause").status_code == 409
