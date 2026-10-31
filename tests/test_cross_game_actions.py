"""Une action propre à un jeu (Pyramide, Biskit, Blackjack, Casino…) envoyée à une autre partie est refusée
proprement (400), jamais une erreur du serveur."""
import pytest
from fastapi.testclient import TestClient

from app import main

HOST = "cross-game-host-01"
OWN = {"pyramid": ["pans", "ptop", "pflip", "pmemory", "presults", "preveal", "pliar"],
       "biskit": ["bdraw", "bpick", "btap", "bclose"],
       "blackjack": ["bet", "hit", "stand", "deal"],
       "casino": ["cbet", "cspin", "cready"],
       "divan": ["dnext", "dheart"],
       "tmc": ["tanswer", "treveal", "finish"]}


@pytest.fixture(autouse=True)
def leave_no_game_behind():
    before = set(main.store.session.games)
    yield
    for code in set(main.store.session.games) - before:
        main.store.session.games.pop(code, None)
    main._game_creations.clear()


@pytest.mark.parametrize("kind", ["quiz", "never", "casino", "blackjack", "roulette", "tmc", "divan", "whoof"])
def test_actions_of_another_game_are_refused_cleanly(kind):
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    code = c.post("/api/games", json={"type": kind, "guest_id": HOST, "name": "Boby"}).json()["code"]
    c.post(f"/api/games/{code}", json={"guest_id": "cross-game-phone-1", "action": "join", "name": "Léa"})
    c.post(f"/api/games/{code}", json={"guest_id": HOST, "action": "start"})
    for owner, actions in OWN.items():
        if owner == kind:
            continue
        for a in actions:
            r = c.post(f"/api/games/{code}", json={"guest_id": HOST, "action": a, "target": "n:7", "amount": 5, "guess": "x"})
            assert r.status_code == 400, (kind, a, r.status_code, r.text[:200])


@pytest.mark.parametrize("kind, action", [("biskit", "bdraw"), ("biskit", "btap"), ("pyramid", "pans"), ("pyramid", "ptop")])
def test_card_moves_before_the_game_starts_are_refused_cleanly(kind, action):
    # Trouvé par les bots (tools/bot_soak.py) : le coup lisait l'état d'une partie pas encore lancée (erreur 500).
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    code = c.post("/api/games", json={"type": kind, "guest_id": HOST, "name": "Boby"}).json()["code"]
    r = c.post(f"/api/games/{code}", json={"guest_id": HOST, "action": action, "target": "red"})
    assert r.status_code == 409, r.text[:200]


@pytest.mark.parametrize("kind", ["room", "divan", "blackjack", "casino", "roulette"])
def test_restart_where_there_is_no_new_round_is_refused_cleanly(kind):
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    code = c.post("/api/games", json={"type": kind, "guest_id": HOST, "name": "Boby"}).json()["code"]
    assert c.post(f"/api/games/{code}", json={"guest_id": HOST, "action": "restart"}).status_code == 409
