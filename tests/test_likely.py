"""« Qui est le plus… ? » : chacun vote en secret sur son téléphone (en même temps), le téléphone de l'animateur
fait voter les participants sans téléphone ; le plus désigné prend un point (ou boit ses gorgées)."""
import random
import re

import pytest
from fastapi.testclient import TestClient

from app import games, likely, main
from app.likely_questions import FAMILY, FRIENDS


def new(names=("Alice", "Bob", "Chloé"), **kw):
    """Partie sur le téléphone d'Alice (animatrice, joue aussi) ; les autres sont ajoutés à la main."""
    g = games.new_game("likely", "host-aaaaaaaa", names[0], **kw)
    for n in names[1:]:
        games.add_guest(g, n)
    return g


def gid(g, name):
    return next(p["id"] for p in g["players"] if p["name"] == name)


def vote_all(g, ballots: dict[str, str]):
    """ballots : votant → personne désignée, dans l'ordre de passage du téléphone."""
    for voter, target in ballots.items():
        games.lk_vote(g, gid(g, voter), gid(g, target))


# ── Questions ──
def test_at_least_300_family_questions_all_distinct():
    assert len(FAMILY) >= 300
    assert len(set(FAMILY)) == len(FAMILY)
    assert len(set(FRIENDS)) == len(FRIENDS)
    assert not set(FAMILY) & set(FRIENDS)


@pytest.mark.parametrize("q", FAMILY + FRIENDS)
def test_questions_are_complete_who_questions(q):
    assert q.startswith("Qui ") and q.endswith(" ?") and q == " ".join(q.split()) and len(q) <= 110


def test_family_pack_stays_family_friendly():
    banned = re.compile(r"\b(alcool|bières?|vins?|verres?|ivres?|gueule de bois|ex|drague\w*|sexe\w*|coucher|bar|boîte)\b")
    assert not [q for q in FAMILY if banned.search(q.lower())]


# ── Déroulé ──
def test_registered_as_a_one_phone_game():
    assert games.GAMES["likely"] == "Qui est le plus… ?"
    assert "likely" in games.MANUAL_GAMES  # participants sans téléphone ajoutés par l'animateur


def test_needs_two_players():
    g = new(names=("Alice",))
    with pytest.raises(games.GameError):
        games.start(g)


def test_question_then_votes_in_turn_then_reveal_gives_a_point():
    g = new()
    games.start(g, random.Random(1))
    v = games.view(g, "host-aaaaaaaa")["likely"]
    # Alice a son téléphone : elle vote directement ; le téléphone tourne seulement pour Bob et Chloé (sans téléphone).
    assert g["phase"] == "ask" and v["q"] in FAMILY and v["n"] == 1 and v["voter"]["name"] == "Bob" and v["can_vote"]
    vote_all(g, {"Alice": "Bob", "Bob": "Bob"})
    v = games.view(g, "host-aaaaaaaa")["likely"]
    assert g["phase"] == "ask" and v["voter"]["name"] == "Chloé" and v["voted"] == 2
    games.lk_vote(g, gid(g, "Chloé"), gid(g, "Alice"))
    assert g["phase"] == "reveal"
    v = games.view(g, "host-aaaaaaaa")["likely"]
    assert [w["name"] for w in v["result"]["winners"]] == ["Bob"]
    assert [(r["name"], r["count"]) for r in v["result"]["rows"]] == [("Bob", 2), ("Alice", 1)]
    assert {s["name"]: s["pts"] for s in v["scores"]} == {"Bob": 1, "Alice": 0, "Chloé": 0}


def test_ballots_stay_secret_before_and_after_reveal():
    g = new()
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": "Bob", "Bob": "Chloé"})
    before = games.view(g, "host-aaaaaaaa")["likely"]
    vote_all(g, {"Chloé": "Bob"})
    after = games.view(g, "host-aaaaaaaa")["likely"]
    for v in (before, after):
        text = str(v)
        assert gid(g, "Bob") not in text and gid(g, "Chloé") not in text  # jamais d'identifiant interne
        assert "ballots" not in v and "votes" not in v  # qui a voté pour qui : jamais montré
    assert before["result"] is None  # pas de décompte avant la fin du vote


def test_people_without_phone_vote_in_table_order_on_the_host_phone():
    g = new()
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.lk_vote(g, gid(g, "Chloé"), gid(g, "Alice"))  # le téléphone est d'abord à Bob
    with pytest.raises(games.GameError):
        games.lk_vote(g, gid(g, "Alice"), "inconnu")


def test_everyone_with_a_phone_votes_at_the_same_time_and_only_once():
    g = games.new_game("likely", "host-aaaaaaaa", "Alice")
    for i, n in enumerate(("Bob", "Chloé")):
        games.join(g, f"guest-{i}", n)
    games.start(g, random.Random(1))
    # N'importe quel ordre : Chloé vote avant Alice, sans passer de téléphone.
    games.lk_vote(g, gid(g, "Chloé"), gid(g, "Bob"))
    assert games.view(g, "guest-1")["likely"]["can_vote"] is False
    with pytest.raises(games.GameError):
        games.lk_vote(g, gid(g, "Chloé"), gid(g, "Alice"))  # vote définitif
    assert games.view(g, "host-aaaaaaaa")["likely"]["voter"] is None  # personne à qui passer le téléphone
    games.lk_vote(g, gid(g, "Bob"), gid(g, "Bob"))
    assert g["phase"] == "ask"
    games.lk_vote(g, gid(g, "Alice"), gid(g, "Chloé"))
    assert g["phase"] == "reveal" and g["likely"]["result"]["winners"] == [gid(g, "Bob")]


def test_the_host_cannot_vote_for_someone_who_has_a_phone():
    g = games.new_game("likely", "host-aaaaaaaa", "Alice")
    games.join(g, "guest-0", "Bob")
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.lk_vote(g, gid(g, "Bob"), gid(g, "Alice"), "host-aaaaaaaa")


def test_the_host_passes_someone_with_a_phone_who_is_away():
    g = games.new_game("likely", "host-aaaaaaaa", "Alice")
    games.join(g, "guest-0", "Bob")
    games.start(g, random.Random(1))
    games.lk_vote(g, gid(g, "Alice"), gid(g, "Bob"))
    v = games.view(g, "host-aaaaaaaa")["likely"]
    assert v["waiting"] == [{"pid": games.player(g, "guest-0")["pid"], "name": "Bob", "manual": False}]
    games.lk_skip(g, gid(g, "Bob"))
    assert g["phase"] == "reveal"


def test_tie_gives_everyone_on_top_a_point_and_sips_when_drinking():
    g = new(sips=2)
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": "Bob", "Bob": "Chloé", "Chloé": "Alice"})
    v = games.view(g, "host-aaaaaaaa")
    assert sorted(w["name"] for w in v["likely"]["result"]["winners"]) == ["Alice", "Bob", "Chloé"]
    assert {p["name"]: p["drink"] for p in v["players"]} == {"Alice": 2, "Bob": 2, "Chloé": 2}


def test_without_alcohol_nobody_drinks():
    g = new()
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": "Bob", "Bob": "Bob", "Chloé": "Bob"})
    assert all(p["drink"] == 0 for p in games.view(g, "host-aaaaaaaa")["players"])


def test_skipping_an_absent_voter_and_reveal_when_everyone_passed():
    g = new()
    games.start(g, random.Random(1))
    games.lk_vote(g, gid(g, "Alice"), gid(g, "Chloé"))
    games.lk_skip(g)  # Bob est parti chercher à boire
    assert games.view(g, "host-aaaaaaaa")["likely"]["voter"]["name"] == "Chloé"
    games.lk_skip(g)
    assert g["phase"] == "reveal"
    assert [w["name"] for w in games.view(g, "host-aaaaaaaa")["likely"]["result"]["winners"]] == ["Chloé"]


def test_nobody_voted_means_no_point():
    g = new()
    games.start(g, random.Random(1))
    games.lk_skip(g)
    games.lk_skip(g)
    games.lk_skip(g, gid(g, "Alice"))
    v = games.view(g, "host-aaaaaaaa")["likely"]
    assert g["phase"] == "reveal" and v["result"]["winners"] == [] and all(s["pts"] == 0 for s in v["scores"])


def test_a_player_who_leaves_mid_question_no_longer_blocks_the_vote():
    g = new()
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": "Bob", "Bob": "Alice"})
    games.kick(g, gid(g, "Chloé"))
    assert g["phase"] == "reveal"


def test_swap_question_only_before_the_first_vote():
    g = new()
    games.start(g, random.Random(1))
    first = g["likely"]["q"]
    games.lk_swap(g, random.Random(2))
    assert g["likely"]["q"] != first and g["likely"]["n"] == 1
    games.lk_vote(g, gid(g, "Alice"), gid(g, "Bob"))
    with pytest.raises(games.GameError):
        games.lk_swap(g, random.Random(3))


def test_no_question_comes_back_and_the_game_ends_on_a_podium():
    g = new()
    likely.configure(g, {"count": 10})
    games.start(g, random.Random(4))
    seen = []
    for i in range(10):
        seen.append(g["likely"]["q"])
        vote_all(g, {"Alice": "Bob", "Bob": "Bob", "Chloé": "Alice" if i % 2 else "Bob"})
        games.next_step(g, random.Random(i))
    assert len(set(seen)) == 10
    assert g["phase"] == "end"
    v = games.view(g, "host-aaaaaaaa")["likely"]
    assert (v["scores"][0]["name"], v["scores"][0]["pts"]) == ("Bob", 10)
    assert len(v["history"]) == 10 and v["history"][0]["winners"] == ["Bob"]


def test_restart_resets_scores_with_the_same_players():
    g = new()
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": "Bob", "Bob": "Bob", "Chloé": "Bob"})
    games.restart(g, random.Random(2))
    v = games.view(g, "host-aaaaaaaa")["likely"]
    assert g["phase"] == "ask" and v["n"] == 1 and all(s["pts"] == 0 for s in v["scores"])


def test_packs_count_and_sips_settings():
    g = new()
    likely.configure(g, {"packs": ["friends"], "count": 30, "sips": 1})
    games.start(g, random.Random(1))
    assert g["likely"]["q"] in FRIENDS and g["likely"]["count"] == 30 and g["options"]["sips"] == 1
    with pytest.raises(likely.LikelyError):
        likely.configure(g, {"count": 20})  # plus réglable une fois la partie lancée
    g2 = new()
    for bad in ({"packs": []}, {"packs": ["hot"]}, {"count": 7}, {"sips": 9}):
        with pytest.raises(likely.LikelyError):
            likely.configure(g2, bad)


def test_summary_for_the_admin_has_no_secret():
    g = new(sips=1)
    games.start(g, random.Random(1))
    s = games.summary(g)
    assert any("1 gorgée" in f for f in s["facts"]) and any("Question 1/20" in f for f in s["facts"])
    assert {p["name"]: p["extra"] for p in s["players_detail"]}["Bob"] == "⭐ 0"


def test_room_merge_adds_points_and_names_the_winner():
    room = games.new_game("room", "host-aaaaaaaa", "Alice")
    g = new()
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": "Bob", "Bob": "Bob", "Chloé": "Bob"})
    games.room_merge(room, g)
    assert room["rpts"][gid(g, "Bob")] == 1 and room["rhistory"][-1]["winner"] == "Bob"


# ── Serveur : un seul téléphone (celui de l'animateur) fait voter tout le monde ──
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_game_creations", {})
    monkeypatch.setattr(main.store.session, "games", {})
    with TestClient(main.app) as c:
        yield c


HOST = "host-likely-0001"
BOB = "guest-bob-00001"


def act(c, code, action, guest_id=HOST, name="Alice", **kw):
    return c.post(f"/api/games/{code}", json={"guest_id": guest_id, "name": name, "action": action, **kw})


def test_api_one_phone_full_question(client):
    r = client.post("/api/games", json={"type": "likely", "guest_id": HOST, "name": "Alice", "cats": ["family", "friends"], "sips": 1})
    assert r.status_code == 200, r.text
    g = r.json()
    code = g["code"]
    assert g["likely"]["packs"] == ["family", "friends"] and g["options"]["sips"] == 1
    act(client, code, "addguest", guess="Papa")
    act(client, code, "addguest", guess="Maman")
    assert act(client, code, "lkset", settings={"count": 10}).json()["likely"]["count"] == 10
    g = act(client, code, "start").json()
    assert g["phase"] == "ask"
    pids = {p["name"]: p["pid"] for p in g["players"]}
    for voter in ("Alice", "Papa", "Maman"):
        g = act(client, code, "lkvote", who=pids[voter], target=pids["Papa"]).json()
    assert g["phase"] == "reveal" and g["likely"]["result"]["winners"][0]["name"] == "Papa"
    assert {p["name"]: p["drink"] for p in g["players"]}["Papa"] == 1
    assert act(client, code, "next").json()["likely"]["n"] == 2


def test_api_a_guest_phone_can_only_vote_for_itself(client):
    code = client.post("/api/games", json={"type": "likely", "guest_id": HOST, "name": "Alice"}).json()["code"]
    act(client, code, "join", guest_id=BOB, name="Bob")
    g = act(client, code, "start").json()
    pids = {p["name"]: p["pid"] for p in g["players"]}
    # L'animatrice ne vote pas à la place de Bob, qui a son téléphone.
    assert act(client, code, "lkvote", who=pids["Bob"], target=pids["Alice"]).status_code == 409
    # Bob vote le premier, sur son téléphone ; son « who » ne lui donne pas la voix d'Alice.
    g = act(client, code, "lkvote", guest_id=BOB, name="Bob", who=pids["Alice"], target=pids["Bob"]).json()
    assert g["phase"] == "ask" and g["likely"]["can_vote"] is False
    assert act(client, code, "lkvote", guest_id=BOB, name="Bob", target=pids["Alice"]).status_code == 409
    g = act(client, code, "lkvote", target=pids["Bob"]).json()
    assert g["phase"] == "reveal"
    # Réglages, passage d'un votant et question suivante : l'animateur seulement.
    assert act(client, code, "next", guest_id=BOB, name="Bob").status_code == 403
    assert act(client, code, "lkskip", guest_id=BOB, name="Bob").status_code == 403


def test_api_other_games_refuse_likely_actions(client):
    code = client.post("/api/games", json={"type": "whoof", "guest_id": HOST, "name": "Alice"}).json()["code"]
    assert act(client, code, "lkvote").status_code == 400


def test_api_launch_from_the_game_room_brings_everyone_including_people_without_phone(client):
    room = client.post("/api/games", json={"type": "room", "guest_id": HOST, "name": "Alice"}).json()["code"]
    act(client, room, "join", guest_id=BOB, name="Bob")
    act(client, room, "addguest", guess="Mamie")
    r = act(client, room, "launch", settings={"type": "likely", "cats": ["family"], "sips": 0})
    assert r.status_code == 200, r.text
    child = r.json()["room_info"]["current"]["code"]
    g = act(client, child, "start").json()
    assert sorted(p["name"] for p in g["players"]) == ["Alice", "Bob", "Mamie"] and g["phase"] == "ask"
