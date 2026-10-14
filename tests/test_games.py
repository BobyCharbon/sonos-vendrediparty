import random

import pytest
from fastapi.testclient import TestClient

from app import games, main
from tests.test_features import admin, snap  # noqa: F401 (fixture)


def undercover(n, white=True, seed=1):
    g = games.new_game("undercover", white=white)
    for i in range(n):
        games.join(g, f"p{i}")
    games.start(g, random.Random(seed))
    return g


def by_role(g, role):
    return [p["id"] for p in g["players"] if p["role"] == role]


def test_roles_and_words_dealt():
    g = undercover(6)
    assert len(by_role(g, "undercover")) == 1 and len(by_role(g, "white")) == 1 and len(by_role(g, "civil")) == 4
    civil, under = g["words"]["civil"], g["words"]["undercover"]
    assert civil != under
    assert all(p["word"] == {"civil": civil, "undercover": under, "white": None}[p["role"]] for p in g["players"])
    assert games.player(g, g["order"][0])["role"] != "white"  # Mr. White ne parle jamais en premier
    assert len(by_role(undercover(4), "white")) == 0  # pas de Mr. White à moins de 5
    assert len(by_role(undercover(10, white=False), "undercover")) == 3


def test_views_hide_secrets():
    g = undercover(5)
    names = {p["id"]: p["id"].upper() for p in g["players"]}
    civil = by_role(g, "civil")[0]
    v = games.view(g, civil, names)
    assert v["me"]["word"] == g["words"]["civil"] and v["me"]["role"] is None
    assert "words" not in v and all("role" not in p for p in v["players"])
    white = by_role(g, "white")[0]
    assert games.view(g, white, names)["me"] == {"alive": True, "vote": None, "role": "Mr. White", "word": None}
    assert games.view(g, None, names)["words"] == g["words"]  # l'hôte voit tout


def test_vote_eliminates_and_civils_win():
    g = undercover(4, white=False)
    under = by_role(g, "undercover")[0]
    games.start_vote(g)
    voters = [p["id"] for p in g["players"]]
    for v in voters:
        games.vote(g, v, under if v != under else next(x for x in voters if x != under))
    assert g["phase"] == "end" and g["winner"] == "civils"
    # Un éliminé dévoile son rôle aux autres, pas son mot (sauf en fin de partie).
    assert games.view(g, voters[0], {})["players"]


def test_tie_revote_then_random():
    g = undercover(4, white=False)
    a, b, c, d = [p["id"] for p in g["players"]]
    games.start_vote(g)
    for voter, target in [(a, b), (b, a), (c, a), (d, b)]:
        games.vote(g, voter, target)
    assert g["phase"] == "vote" and sorted(g["candidates"]) == sorted([a, b])
    with pytest.raises(games.GameError):
        games.vote(g, c, d)  # seulement les ex æquo
    for voter, target in [(a, b), (b, a), (c, a), (d, b)]:
        games.vote(g, voter, target, random.Random(0))
    assert sum(not p["alive"] for p in g["players"]) == 1


def test_mr_white_guess_wins_with_accents_ignored():
    g = undercover(5)
    white = by_role(g, "white")[0]
    games.start_vote(g)
    games.eliminate(g, white)
    assert g["phase"] == "white_guess"
    with pytest.raises(games.GameError):
        games.white_guess(g, by_role(g, "civil")[0], "x")
    games.white_guess(g, white, games.normalize(g["words"]["civil"]).upper())
    assert g["winner"] == "white"


def test_impostors_win_when_one_civil_left():
    g = undercover(4, white=False)
    civils = by_role(g, "civil")
    games.eliminate(g, civils[0])
    assert g["phase"] == "reveal"
    games.next_step(g)
    games.start_vote(g)
    games.eliminate(g, civils[1])
    assert g["winner"] == "impostors"


def test_late_join_refused_for_undercover():
    g = undercover(3)
    with pytest.raises(games.GameError):
        games.join(g, "late")


def test_whoof_round():
    g = games.new_game("whoof")
    for gid in ("a", "b", "c"):
        games.join(g, gid)
    games.start(g)
    assert g["question"].startswith("Qui de nous")
    games.vote(g, "a", "b")
    games.vote(g, "b", "b")
    games.join(g, "d")  # retardataire accepté
    games.vote(g, "c", "a")
    games.vote(g, "d", "b")
    assert g["phase"] == "results" and g["results"][0] == ["b", 3]
    games.next_step(g)
    assert g["phase"] == "question" and g["votes"] == {}


def test_game_api_flow(admin):  # noqa: F811
    players = []
    for i in range(3):
        c = TestClient(main.app)
        c.post("/api/join", json={"pin": main.store.session.guest_pin})
        c.post("/api/hello", json={"guest_id": f"gamer-{i}-xyz", "guest_name": f"Joueur {i}"})
        players.append(c)
    assert admin.post("/api/admin/game", json={"action": "open", "type": "undercover"}).status_code == 200
    for i, c in enumerate(players):
        assert c.post("/api/game", json={"guest_id": f"gamer-{i}-xyz", "action": "join"}).status_code == 200
    state = admin.post("/api/admin/game", json={"action": "start"}).json()
    assert state["game"]["phase"] == "words" and state["game"]["words"]
    view = players[0].get("/api/state?guest_id=gamer-0-xyz").json()["game"]
    assert view["me"]["word"] or view["me"]["role"] and "words" not in view
    # Un invité non inscrit ne voit pas les mots.
    assert "me" not in players[0].get("/api/state?guest_id=").json()["game"]
    assert admin.post("/api/admin/game", json={"action": "end"}).json()["game"] is None
