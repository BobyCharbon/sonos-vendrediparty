"""Plusieurs téléphones interrogent ou jouent en même temps : chaque étape de jeu ne doit s'appliquer qu'une fois.

Régression (audit des jeux) : à la fin d'une question de quiz, les rafraîchissements simultanés de tous les
téléphones déclenchaient chacun la révélation ; en mode Survie, une seule question ratée retirait toutes les vies."""
import sys
import threading
import time

import pytest
from starlette.requests import Request

from app import games, main, quiz


@pytest.fixture(autouse=True)
def fast_thread_switching(monkeypatch):
    """Changements de fil très fréquents : rend la course visible à coup sûr si le verrou manque."""
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main.store, "save", lambda notify=True: None)  # pas d'écriture disque pendant le test
    yield
    sys.setswitchinterval(old)


def request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b"",
                    "client": ("10.0.0.9", 5000)})


def all_at_once(fn, n=8):
    gate = threading.Barrier(n)
    errors = []

    def run():
        gate.wait()
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - remonté par l'assertion du test
            errors.append(e)
    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def survival_quiz() -> dict:
    g = games.new_game("quiz", "host-aaaaaaaa", "Hôte", code="1234")
    games.join(g, "guest-bbbbbbbb", "Bob")
    quiz.configure(g, {"mode": "survival", "lives": 3})
    games.start(g)
    main.store.session.games["1234"] = g
    return g


def test_simultaneous_polls_at_the_end_of_a_question_take_one_life_only():
    for _ in range(40):
        g = survival_quiz()
        g["quiz"]["cur"]["end"] = time.time() - 1  # le chrono vient d'arriver à zéro, personne n'a répondu
        assert not all_at_once(lambda: main.game_state("1234", request(), guest_id="host-aaaaaaaa"))
        lives = [s["lives"] for s in g["quiz"]["scores"].values()]
        assert lives == [2, 2], f"une question ratée a retiré {3 - min(lives)} vies"


def test_simultaneous_last_bets_deal_the_blackjack_hand_once(monkeypatch):
    deals = []
    real_deal = games.bj_deal
    monkeypatch.setattr(games, "bj_deal", lambda g, *a: (deals.append(1), real_deal(g, *a)))
    for _ in range(40):
        deals.clear()
        g = games.new_game("blackjack", "host-aaaaaaaa", "Hôte", code="4321")
        games.join(g, "guest-bbbbbbbb", "Bob")
        main.store.session.games["4321"] = g
        games.start(g)
        bet = lambda gid: main.game_action("4321", main.GameAction(guest_id=gid, name="x", action="bet", amount=10), request())  # noqa: E731
        errors = all_at_once(lambda: [bet(gid) for gid in ("host-aaaaaaaa", "guest-bbbbbbbb")], n=4)
        assert all(getattr(e, "status_code", None) == 409 for e in errors), errors  # mise refusée après la donne : normal
        assert len(deals) == 1, f"la main a été distribuée {len(deals)} fois"
