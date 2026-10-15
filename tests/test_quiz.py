import random

import pytest
from fastapi.testclient import TestClient

from app import games, main, quiz
from app import quizbank as qb


@pytest.fixture(autouse=True)
def stats(tmp_path):
    quiz.STATS_PATH = tmp_path / "quiz_stats.json"
    yield


def qgame(n=2, **settings):
    g = games.new_game("quiz", host="p0", name="P0")
    for i in range(1, n):
        games.join(g, f"p{i}", f"P{i}")
    quiz.configure(g, settings)
    return g


def test_bank_is_well_formed():
    for t, qs in qb.BANK.items():
        for q in qs:
            assert q["t"] == t and len(q["w"]) == 3 and q["a"] not in q["w"] and len(set(q["w"])) == 3, q
            assert 1 <= q["d"] <= 3 and q["q"].strip() and q["id"] in qb.BY_ID
    assert len(qb.BANK["geo"]) >= 1000 and len(qb.BANK["suisse"]) >= 800


def test_classic_points_and_reveal():
    g = qgame(2, themes=["geo"], time=20)
    g["quiz"]["settings"]["count"] = 2  # (minimum réglable : 5)
    games.start(g, random.Random(1))
    c = g["quiz"]["cur"]
    v = games.view(g, "p0")["quiz"]["q"]
    assert "correct" not in v and len(v["choices"]) == 4  # la bonne réponse n'est jamais envoyée avant la révélation
    quiz.answer(g, "p0", c["ans"])
    with pytest.raises(quiz.QuizError):
        quiz.answer(g, "p0", c["ans"])  # une seule réponse
    quiz.answer(g, "p1", (c["ans"] + 1) % 4)
    assert g["phase"] == "rev"  # tout le monde a répondu : révélation
    sc = g["quiz"]["scores"]
    assert sc["p0"]["pts"] >= 500 and sc["p1"]["pts"] == 0 and sc["p0"]["ok"] == 1
    assert games.view(g, "p1")["quiz"]["q"]["correct"] == c["ans"]
    g["quiz"]["cur"]["next_at"] = 0
    quiz.tick(g, random.Random(2))
    assert g["phase"] == "q" and g["quiz"]["n"] == 2
    g["quiz"]["cur"]["end"] = 0  # temps écoulé
    quiz.tick(g)
    g["quiz"]["cur"]["next_at"] = 0
    quiz.tick(g)
    assert g["phase"] == "end" and quiz.leaderboard()["top"][0]["name"] == "P0"


def test_speed_first_right_answer_wins_and_wrong_locks():
    g = qgame(3, mode="speed")
    games.start(g, random.Random(3))
    a = g["quiz"]["cur"]["ans"]
    quiz.answer(g, "p1", (a + 1) % 4)
    assert "p1" in g["quiz"]["cur"]["locked"] and g["phase"] == "q"
    quiz.answer(g, "p2", a)
    assert g["phase"] == "rev" and g["quiz"]["cur"]["winner"] == "p2" and g["quiz"]["scores"]["p2"]["pts"] == 1000


def test_survival_lives_and_last_standing():
    g = qgame(2, mode="survival", lives=1)
    games.start(g, random.Random(4))
    a = g["quiz"]["cur"]["ans"]
    quiz.answer(g, "p0", a)
    quiz.answer(g, "p1", (a + 1) % 4)
    assert g["quiz"]["scores"]["p1"]["out"]
    g["quiz"]["cur"]["next_at"] = 0
    quiz.tick(g)
    assert g["phase"] == "end" and quiz.board(g)[0][0]["id"] == "p0"


def test_ladder_safe_level_jokers_and_stop():
    g = qgame(1, mode="ladder")
    games.start(g, random.Random(5))
    P = g["quiz"]["personal"]["p0"]
    for _ in range(6):
        quiz.answer(g, "p0", P["q"]["ans"])
        assert P["between"]  # la bonne réponse reste affichée un moment
        P["between"] = 1  # (temps écoulé)
        quiz.tick(g)
    assert P["level"] == 6 and not P.get("between")
    quiz.joker(g, "p0", "5050", random.Random(1))
    assert len(P["cut"]) == 2 and P["q"]["ans"] not in P["cut"]
    with pytest.raises(quiz.QuizError):
        quiz.joker(g, "p0", "5050")
    quiz.answer(g, "p0", P["cut"][0])  # raté : retour au palier assuré (5)
    assert g["phase"] == "end" and P["level"] == 5


def test_chrono_runs_until_deadline():
    g = qgame(2, mode="chrono", chrono=30)
    games.start(g, random.Random(6))
    for _ in range(3):
        quiz.answer(g, "p0", g["quiz"]["personal"]["p0"]["q"]["ans"])
    assert g["quiz"]["scores"]["p0"]["ok"] == 3 and g["phase"] == "run"
    g["quiz"]["deadline"] = 0
    quiz.tick(g)
    assert g["phase"] == "end"


def test_solo_and_api():
    main._game_creations.clear()
    c = TestClient(main.app)
    g = c.post("/api/games", json={"guest_id": "quiz-solo-0001", "name": "Ludo", "type": "quiz", "plays": True}).json()
    code = g["code"]
    r = c.post(f"/api/games/{code}", json={"guest_id": "quiz-solo-0001", "action": "qset", "settings": {"mode": "classic", "themes": ["suisse"], "count": 5}})
    assert r.json()["quiz"]["settings"]["themes"] == ["suisse"]
    v = c.post(f"/api/games/{code}", json={"guest_id": "quiz-solo-0001", "action": "start"}).json()
    assert v["phase"] == "q" and v["quiz"]["q"]["theme"] == "Suisse"
    v = c.post(f"/api/games/{code}", json={"guest_id": "quiz-solo-0001", "action": "qans", "amount": 0}).json()
    assert v["phase"] == "rev"  # seul joueur : révélation tout de suite
    # Un autre invité ne peut pas changer les réglages.
    other = TestClient(main.app)
    other.post(f"/api/games/{code}", json={"guest_id": "quiz-other-001", "name": "Léa", "action": "join"})
    assert other.post(f"/api/games/{code}", json={"guest_id": "quiz-other-001", "action": "qset", "settings": {"mode": "speed"}}).status_code == 403


def test_bank_has_no_draft_leftovers():
    """Toutes les mauvaises réponses sont de vraies réponses (pas de brouillons « … seul », « — »…) et tous les thèmes ont 1000+ questions."""
    import re
    for t, qs in qb.BANK.items():
        assert len(qs) >= 1000, t
        for q in qs:
            txt = " | ".join([q["q"], q["a"], *q["w"]])
            assert not re.search(r"\bseule?s?\b", " ".join(q["w"])), txt
            assert "—" not in txt and "non :" not in txt, txt
            assert len({c.lower() for c in [q["a"], *q["w"]]}) == 4, txt


def test_pause_after_answer():
    g = qgame(1)
    games.start(g, random.Random(7))
    quiz.answer(g, "p0", g["quiz"]["cur"]["ans"])
    assert g["phase"] == "rev"
    quiz.pause(g, "p0", True)
    g["quiz"]["cur"]["next_at"] = 0
    quiz.tick(g)
    assert g["phase"] == "rev"  # en pause : on reste sur la réponse
    quiz.pause(g, "p0", True)
    assert g["phase"] == "q" and g["quiz"]["n"] == 2 and not g["quiz"]["paused"]
    with pytest.raises(quiz.QuizError):
        quiz.pause(g, "p1", False)  # un simple joueur ne peut pas


def test_ladder_pause_between_questions():
    g = qgame(1, mode="ladder")
    games.start(g, random.Random(8))
    P = g["quiz"]["personal"]["p0"]
    quiz.answer(g, "p0", P["q"]["ans"])
    quiz.pause(g, "p0", False)
    P["between"] = 1
    quiz.tick(g)
    assert P["paused"] and P["between"]  # pas de nouvelle question pendant la pause
    quiz.pause(g, "p0", False)
    assert not P.get("between") and P["i"] == 1


def test_speed_needs_two_players():
    g = qgame(1)
    with pytest.raises(quiz.QuizError):
        quiz.configure(g, {"mode": "speed"})
    g2 = qgame(2, mode="speed")
    g2["players"].pop()  # le deuxième joueur est parti
    with pytest.raises(games.GameError):
        games.start(g2)


def test_late_answer_and_double_next_are_ignored():
    g = qgame(1)
    games.start(g, random.Random(9))
    tok = quiz.token(g, "p0")
    quiz.answer(g, "p0", g["quiz"]["cur"]["ans"], tok=tok)
    assert g["phase"] == "rev"
    rev_tok = quiz.token(g, "")
    quiz.next_step(g, tok=rev_tok)
    assert g["quiz"]["n"] == 2
    quiz.next_step(g, tok=rev_tok)  # deuxième clic sur « Suivante » : ignoré
    assert g["quiz"]["n"] == 2 and g["phase"] == "q"
    with pytest.raises(quiz.QuizError):
        quiz.answer(g, "p0", 0, tok=tok)  # réponse destinée à la question 1 : refusée


def test_chrono_double_tap_does_not_answer_next_question():
    g = qgame(1, mode="chrono")
    games.start(g, random.Random(10))
    tok = quiz.token(g, "p0")
    quiz.answer(g, "p0", 0, tok=tok)
    with pytest.raises(quiz.QuizError):
        quiz.answer(g, "p0", 0, tok=tok)
    assert g["quiz"]["scores"]["p0"]["n"] == 1


@pytest.mark.parametrize("kind", ["quiz", "biskit", "never", "undercover", "casino"])
def test_handover_in_every_game(kind):
    g = games.new_game(kind, host="h", name="Ludo")
    games.join(g, "a", "Léa")
    games.join(g, "b", "Tom")
    games.handover(g, "h", "a")
    assert g["host"] == "a" and g["host_name"] == "Léa" and not games.player(g, "h")
    assert games.view(g, "a")["is_owner"] and not games.view(g, "b")["is_owner"]
    with pytest.raises(games.GameError):
        games.handover(g, "a", "a")


def test_handover_api_only_for_lead():
    main._game_creations.clear()
    h, o = TestClient(main.app), TestClient(main.app)
    g = h.post("/api/games", json={"guest_id": "hand-host-0001", "name": "Ludo", "type": "quiz", "plays": True}).json()
    v = o.post(f"/api/games/{g['code']}", json={"guest_id": "hand-other-001", "name": "Léa", "action": "join"}).json()
    lea = next(p["pid"] for p in v["players"] if p["name"] == "Léa")
    assert o.post(f"/api/games/{g['code']}", json={"guest_id": "hand-other-001", "action": "handover", "target": lea}).status_code == 403
    r = h.post(f"/api/games/{g['code']}", json={"guest_id": "hand-host-0001", "action": "handover", "target": lea})
    assert r.status_code == 200
    v = o.get(f"/api/games/{g['code']}?guest_id=hand-other-001").json()
    assert v["is_owner"] and v["is_host"] and [p["name"] for p in v["players"]] == ["Léa"]
