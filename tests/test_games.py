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
    civil = by_role(g, "civil")[0]
    v = games.view(g, civil)
    assert v["me"]["word"] == g["words"]["civil"] and v["me"]["role"] is None
    assert "words" not in v and all("role" not in p and "word" not in p for p in v["players"])
    # Les guest_id (secrets) des joueurs n'apparaissent jamais : seulement des identifiants publics.
    assert not any(p["id"] in str(v) for p in g["players"])
    white = by_role(g, "white")[0]
    assert games.view(g, white)["me"]["role"] == "Mr. White" and games.view(g, white)["me"]["word"] is None
    assert "me" not in games.view(g, "inconnu") and "words" not in games.view(g, "inconnu")


def test_host_who_does_not_play_is_game_master():
    g = games.new_game("undercover", host="boss", name="Boss", plays=False)
    for i in range(4):
        games.join(g, f"p{i}", f"P{i}")
    assert games.player(g, "boss") is None
    games.start(g, random.Random(2))
    v = games.view(g, "boss")
    assert v["is_host"] and v["master"] and v["words"] == g["words"]
    assert all(p["role"] and "word" in p for p in v["players"])
    # Un animateur qui joue ne voit que son propre mot.
    g2 = games.new_game("undercover", host="boss", name="Boss")
    for i in range(3):
        games.join(g2, f"p{i}", f"P{i}")
    games.start(g2, random.Random(3))
    v2 = games.view(g2, "boss")
    assert v2["is_host"] and not v2["master"] and "words" not in v2


def test_host_leaving_hands_over():
    g = games.new_game("whoof", host="h", name="Hôte")
    games.join(g, "a", "Ana")
    games.leave(g, "h")
    assert g["host"] == "a" and g["host_name"] == "Ana"


def test_vote_eliminates_and_civils_win():
    g = undercover(4, white=False)
    under = by_role(g, "undercover")[0]
    games.start_vote(g)
    voters = [p["id"] for p in g["players"]]
    for v in voters:
        games.vote(g, v, under if v != under else next(x for x in voters if x != under))
    assert g["phase"] == "end" and g["winner"] == "civils"
    assert games.view(g, voters[0])["words"] == g["words"]  # tout est dévoilé à la fin


def test_eliminated_reveals_role_not_word():
    g = undercover(5, white=False)
    civil = by_role(g, "civil")
    games.eliminate(g, civil[0])
    out = next(p for p in games.view(g, civil[1])["players"] if not p["alive"])
    assert out["role"] == "Civil" and "word" not in out


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


def test_late_joiner_waits_for_next_game():
    g = undercover(4, white=False)
    games.join(g, "late", "Retard")
    v = games.view(g, "late")
    assert v["me"]["waiting"] and v["me"]["word"] is None
    assert next(p for p in v["players"] if p["name"] == "Retard")["waiting"]
    games.start_vote(g)
    with pytest.raises(games.GameError):
        games.vote(g, "late", "p0")  # ne vote pas
    with pytest.raises(games.GameError):
        games.vote(g, "p0", next(p["pid"] for p in g["players"] if p["id"] == "late") and "late")  # ni ne peut être visé
    # Les votes des 4 joueurs en lice suffisent à clore le vote.
    under = by_role(g, "undercover")[0]
    for v in ["p0", "p1", "p2", "p3"]:
        games.vote(g, v, under if v != under else next(x for x in ["p0", "p1"] if x != under))
    assert g["phase"] == "end"
    games.restart(g, random.Random(5))
    assert games.player(g, "late")["role"] and not games.player(g, "late")["waiting"]


def test_host_kicks_mid_game():
    g = undercover(5, white=False)
    under = by_role(g, "undercover")[0]
    games.start_vote(g)
    games.vote(g, "p0" if under != "p0" else "p1", under)
    games.kick(g, under)
    # Le seul undercover est parti : les civils gagnent ; il ne peut pas revenir.
    assert g["winner"] == "civils" and games.player(g, under) is None
    with pytest.raises(games.GameError):
        games.join(g, under, "Revenant")
    assert games.view(g, under)["kicked"]


def test_player_can_leave_mid_game():
    g = undercover(4, white=False)
    civil = by_role(g, "civil")[0]
    games.leave(g, civil)
    assert games.player(g, civil) is None and civil not in g["order"]
    games.join(g, civil, "De retour")  # partir de soi-même n'empêche pas de revenir
    assert games.player(g, civil)["waiting"]


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


def test_game_api_flow_without_music_code():
    clients = [TestClient(main.app) for _ in range(4)]  # aucun n'a saisi le code de la musique
    host, *others = clients
    g = host.post("/api/games", json={"guest_id": "host-abcdef12", "name": "Ludo", "type": "undercover", "plays": False}).json()
    code = g["code"]
    assert len(code) == 4 and g["is_host"] and g["master"]
    for i, c in enumerate(others):
        r = c.post(f"/api/games/{code}", json={"guest_id": f"gamer-{i}-xyz", "name": f"Joueur {i}", "action": "join"})
        assert r.status_code == 200 and r.json()["me"]
    # Seul l'animateur fait avancer la partie.
    assert others[0].post(f"/api/games/{code}", json={"guest_id": "gamer-0-xyz", "action": "start"}).status_code == 403
    assert host.post(f"/api/games/{code}", json={"guest_id": "host-abcdef12", "action": "start"}).json()["phase"] == "words"
    me = others[0].get(f"/api/games/{code}?guest_id=gamer-0-xyz").json()["me"]
    assert me["word"] or me["role"]
    # Vote par identifiant public.
    host.post(f"/api/games/{code}", json={"guest_id": "host-abcdef12", "action": "vote_start"})
    view = others[0].get(f"/api/games/{code}?guest_id=gamer-0-xyz").json()
    target = next(p["pid"] for p in view["players"] if p["pid"] != view["me"]["pid"])
    r = others[0].post(f"/api/games/{code}", json={"guest_id": "gamer-0-xyz", "action": "vote", "target": target})
    assert r.json()["me"]["vote"] == target
    assert TestClient(main.app).get(f"/qr/game/{code}.svg").status_code == 200
    host.post(f"/api/games/{code}", json={"guest_id": "host-abcdef12", "action": "end"})
    assert others[0].get(f"/api/games/{code}").status_code == 404


def test_admin_sees_and_closes_games(admin):  # noqa: F811
    g = TestClient(main.app).post("/api/games", json={"guest_id": "host-zzzz1234", "name": "Zoé", "type": "whoof"}).json()
    listed = admin.get("/api/admin/state").json()["games"]
    assert any(x["code"] == g["code"] and x["host"] == "Zoé" for x in listed)
    admin.post("/api/admin/games/close", json={"guest_id": "admin-console", "action": "end", "target": g["code"]})
    assert g["code"] not in main.store.session.games


def test_game_creation_rate_limited():
    main._game_creations.clear()  # les autres tests ont créé des parties depuis la même adresse
    c = TestClient(main.app)
    codes = [c.post("/api/games", json={"guest_id": f"spam-{i}-abcd", "name": "X", "type": "whoof"}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_host_reorders_speaking_order_and_lobby():
    g = games.new_game("undercover", host="h", name="H")
    for i in range(3):
        games.join(g, f"p{i}", f"P{i}")
    games.move(g, "p2", -1)
    assert [p["id"] for p in g["players"]] == ["h", "p0", "p2", "p1"]
    games.start(g, random.Random(4))
    first, second = g["order"][:2]
    games.move(g, second, -1)
    assert g["order"][:2] == [second, first]
    games.move(g, second, -1)  # déjà en tête : ne bouge plus
    assert g["order"][0] == second


def test_game_codes_are_digits_and_never_the_music_pin():
    assert all(games.new_code(set()).isdigit() for _ in range(50))
    taken = {f"{i:04d}" for i in range(10000)} - {"0042"}
    assert games.new_code(taken) == "0042"


@pytest.mark.parametrize("mode, pool", [("soft", games.WHOOF_QUESTIONS), ("awkward", games.WHOOF_AWKWARD), ("hot", games.WHOOF_HOT)])
def test_whoof_modes_pick_from_their_pool_without_repeats(mode, pool):
    g = games.new_game("whoof", host="h", name="H", mode=mode, sips=3)
    games.join(g, "a", "A")
    games.start(g)
    seen = set()
    for _ in range(len(pool)):
        seen.add(g["question"])
        assert g["question"][len("Qui de nous "):-2] in pool
        games.next_step(g)
    assert len(seen) == len(pool)  # toutes les questions avant de repasser par une déjà posée
    assert games.view(g, "h")["options"]["sips"] == 3 and games.view(g, "h")["mode"]


def test_whoof_rejects_unknown_mode_and_clamps_sips():
    with pytest.raises(games.GameError):
        games.new_game("whoof", mode="nope")
    assert games.new_game("whoof", sips=99)["options"]["sips"] == 10
