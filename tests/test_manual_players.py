"""Prénoms ajoutés à la main (joueurs sans téléphone) dans Qui de nous ?, Blackjack et Casino : l'animateur vote,
mise et joue pour eux — jamais à la place d'un joueur qui a son téléphone."""
import pytest
from fastapi.testclient import TestClient

from app import games, main

HOST, PHONE = "manual-test-host-01", "manual-test-phone-1"


@pytest.fixture(autouse=True)
def leave_no_game_behind():
    before = set(main.store.session.games)
    yield
    # Sinon les tests suivants butent sur les limites (créations par adresse, 30 parties en cours).
    for code in set(main.store.session.games) - before:
        main.store.session.games.pop(code, None)
    main._game_creations.clear()


def setup(kind):
    main._game_creations.clear()
    c = TestClient(main.app)
    code = c.post("/api/games", json={"type": kind, "guest_id": HOST, "name": "Boby"}).json()["code"]
    act = lambda gid=HOST, **b: c.post(f"/api/games/{code}", json={"guest_id": gid, **b})  # noqa: E731
    assert act(PHONE, action="join", name="Léa").status_code == 200
    assert act(action="addguest", guess="Mamie").status_code == 200
    g = main.store.session.games[code]
    mamie = next(p for p in g["players"] if p["name"] == "Mamie")
    assert mamie["manual"]
    return c, code, act, g, mamie


def test_whoof_host_votes_for_a_player_without_phone():
    c, code, act, g, mamie = setup("whoof")
    lea = next(p for p in g["players"] if p["name"] == "Léa")
    assert act(action="start").status_code == 200
    assert act(action="mvote", target=mamie["pid"], guess=lea["pid"]).status_code == 200
    assert g["votes"][mamie["id"]] == lea["id"]  # Mamie désigne Léa
    assert act(action="mvote", target=lea["pid"], guess=mamie["pid"]).status_code == 409  # Léa vote sur son téléphone
    act(action="vote", target=lea["pid"])
    act(PHONE, action="vote", target=mamie["pid"])
    assert g["phase"] == "results"  # tout le monde a voté, Mamie comprise


def test_blackjack_host_bets_and_plays_for_a_player_without_phone():
    c, code, act, g, mamie = setup("blackjack")
    lea = next(p for p in g["players"] if p["name"] == "Léa")
    assert act(action="start").status_code == 200
    assert act(action="bet", amount=10, who=mamie["pid"]).status_code == 200
    assert g["bj"]["hands"][mamie["id"]]["bet"] == 10 and HOST not in g["bj"]["hands"]
    assert act(action="bet", amount=25, who=lea["pid"]).status_code == 200  # pas pour Léa : la mise reste à l'animateur
    assert lea["id"] not in g["bj"]["hands"] and g["bj"]["hands"][HOST]["bet"] == 25
    act(PHONE, action="bet", amount=5)  # tout le monde a misé : la donne part toute seule
    for _ in range(6):  # chacun reste, Mamie par l'animateur
        if g["phase"] != "play" or g["bj"]["turn"] is None:
            break
        turn = g["bj"]["seats"][g["bj"]["turn"]]
        who = next(p for p in g["players"] if p["id"] == turn)
        if who.get("manual"):
            assert act(action="stand", who=who["pid"]).status_code == 200
        else:
            assert act(turn, action="stand").status_code == 200
    assert g["phase"] == "results"


def test_casino_host_bets_for_a_player_without_phone():
    c, code, act, g, mamie = setup("casino")
    assert act(action="start").status_code == 200
    assert act(action="cbet", target="color:red", amount=10, who=mamie["pid"]).status_code == 200
    assert act(action="cready", who=mamie["pid"]).status_code == 200
    assert g["casino"]["bets"].get(mamie["id"]) and not g["casino"]["bets"].get(HOST)


def test_secret_games_still_refuse_players_without_phone():
    for kind in ("undercover", "quiz", "president"):
        main._game_creations.clear()
        c = TestClient(main.app)
        code = c.post("/api/games", json={"type": kind, "guest_id": HOST, "name": "Boby"}).json()["code"]
        r = c.post(f"/api/games/{code}", json={"guest_id": HOST, "action": "addguest", "guess": "Mamie"})
        assert r.status_code >= 400 and kind not in games.MANUAL_GAMES
