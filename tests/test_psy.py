"""« Qui es-tu vraiment ? » : questions sans leur clé, réponses secrètes, profil et logique à la révélation, âmes sœurs."""
import random

import pytest
from fastapi.testclient import TestClient

from app import games, main, psy


def table(n=3, seed=4):
    g = games.new_game("psy", host="h", name="Léa")
    for i in range(1, n):
        games.join(g, f"p{i}", f"Ami{i}")
    games.start(g, random.Random(seed))
    return g


def answer_all(g, gid, pick):
    S = g["psy"]
    for i, q in enumerate(S["questions"]):
        games.psy_answer(g, gid, i, pick(i, q))
    games.psy_submit(g, gid)


def tag_index(q, tag):
    return next(j for j, o in enumerate(q["options"]) if o["tag"] == tag)


def test_questions_are_shown_without_their_key_and_answers_stay_secret():
    g = table()
    v = games.view(g, "p1")["psy"]
    assert v["count"] == 12 and len(v["questions"]) == 12
    assert all(isinstance(o, str) for q in v["questions"] for o in q["options"])  # ni profil ni bonne réponse
    assert sum(q["kind"] == "logic" for q in v["questions"]) == psy.LOGIC_COUNT
    games.psy_answer(g, "p1", 0, 1)
    assert games.view(g, "p1")["psy"]["mine"] == {"0": 1} and games.view(g, "p2")["psy"]["mine"] == {}
    with pytest.raises(games.GameError):
        games.psy_submit(g, "p1")  # il manque des réponses
    with pytest.raises(games.GameError):
        games.psy_answer(g, "p1", 99, 0)


def test_reveal_gives_each_profile_logic_score_and_soulmates():
    g = table()
    S = g["psy"]
    leader = lambda i, q: tag_index(q, "leader") if q["kind"] == "self" else tag_index(q, "ok")
    dreamer = lambda i, q: tag_index(q, "dreamer") if q["kind"] == "self" else tag_index(q, "no")
    answer_all(g, "h", leader)
    answer_all(g, "p1", leader)
    answer_all(g, "p2", dreamer)
    assert psy.everyone_done(g)
    games.psy_reveal(g)
    r = games.view(g, "p2")["psy"]
    people = {x["name"]: x for x in r["results"]["people"]}
    assert people["Léa"]["profile"] == "leader" and people["Léa"]["pct"]["leader"] == 100 and people["Léa"]["logic"] == 3
    assert people["Ami2"]["profile"] == "dreamer" and people["Ami2"]["logic"] == 0
    assert r["results"]["most_logic"] == ["Léa", "Ami1"] and r["results"]["pair"]["pct"] == 100
    assert r["me"]["profile"] == "dreamer" and r["results"]["distribution"]["leader"] == 2
    assert "questions" not in r  # plus rien à répondre
    with pytest.raises(games.GameError):
        games.psy_answer(g, "p1", 0, 0)
    games.next_step(g, random.Random(9))  # nouveau test
    assert g["phase"] == "answering" and not S["done"]


def test_reveal_needs_someone_done_and_actions_are_checked_by_the_server():
    g = table(2)
    with pytest.raises(games.GameError):
        games.psy_reveal(g)
    before = set(main.store.session.games)
    main._game_creations.clear()
    c = TestClient(main.app, raise_server_exceptions=False)
    try:
        code = c.post("/api/games", json={"type": "psy", "guest_id": "psy-host-0000001", "name": "Boby"}).json()["code"]
        c.post(f"/api/games/{code}", json={"guest_id": "psy-phone-0000001", "action": "join", "name": "Léa"})
        assert c.post(f"/api/games/{code}", json={"guest_id": "psy-host-0000001", "action": "start"}).status_code == 200
        r = c.post(f"/api/games/{code}", json={"guest_id": "psy-phone-0000001", "action": "psyreveal"})
        assert r.status_code in (400, 403)  # réservé à l'animateur
        r = c.post(f"/api/games/{code}", json={"guest_id": "psy-phone-0000001", "action": "psyans", "settings": {"q": 0, "a": 2}})
        assert r.status_code == 200 and r.json()["psy"]["mine"] == {"0": 2}
        r = c.post(f"/api/games/{code}", json={"guest_id": "psy-phone-0000001", "action": "dbvote", "amount": 1})
        assert r.status_code == 400  # action d'un autre jeu refusée proprement
    finally:
        for k in set(main.store.session.games) - before:
            main.store.session.games.pop(k, None)
        main._game_creations.clear()
