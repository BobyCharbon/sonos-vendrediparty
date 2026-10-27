"""« Pour ou contre » : un dilemme, chacun se place en secret sur 5 crans (de « Totalement contre » à « Totalement
pour »), on découvre la répartition, on débat librement ; l'animateur décide de faire revoter ou de passer au suivant.
Les joueurs proposent leurs dilemmes, l'animateur les valide. Pas de gorgées, pas de points : un bilan à la fin."""
import random

import pytest
from fastapi.testclient import TestClient

from app import debate, games, main
from app.debate_questions import LIGHT, MORAL, RELATIONS, SOCIETY, WTF

HOST_GID = "host-aaaaaaaa"
ALL = MORAL + SOCIETY + RELATIONS + LIGHT + WTF


def new(names=("Alice", "Bob", "Chloé"), **settings):
    """Partie sur le téléphone d'Alice (animatrice, joue aussi) ; les autres sont ajoutés à la main (sans téléphone)."""
    g = games.new_game("debate", HOST_GID, names[0])
    for n in names[1:]:
        games.add_guest(g, n)
    if settings:
        debate.configure(g, settings)
    return g


def gid(g, name):
    return next(p["id"] for p in g["players"] if p["name"] == name)


def vote_all(g, ballots: dict[str, int]):
    """ballots : votant → cran (0 = totalement contre … 4 = totalement pour), dans l'ordre de passage du téléphone."""
    for voter, value in ballots.items():
        games.db_vote(g, gid(g, voter), value)


def view(g, who=HOST_GID):
    return games.view(g, who)["debate"]


def play(g, ballots, revote=None, rng=None):
    vote_all(g, ballots)
    if revote:
        games.db_revote(g)
        vote_all(g, revote)
    games.next_step(g, rng or random.Random(5))


# ── Dilemmes ──
def test_each_theme_has_enough_distinct_dilemmas():
    for pack in (MORAL, SOCIETY, RELATIONS, LIGHT, WTF):
        assert len(pack) >= 100
    assert len(set(ALL)) == len(ALL)


@pytest.mark.parametrize("q", ALL)
def test_dilemmas_are_clean_questions(q):
    assert q.endswith(" ?") and q == " ".join(q.split()) and len(q) <= debate.MAX_TEXT and q[0].isupper()


def test_dilemmas_never_say_sortie():
    assert not [q for q in ALL if "sortie" in q.lower()]


# ── Enregistrement ──
def test_registered_as_a_one_phone_game_without_drinks():
    assert games.GAMES["debate"] == "Pour ou contre"
    assert "debate" in games.MANUAL_GAMES
    g = new()
    assert g["debate"]["themes"] == list(debate.DEFAULT_THEMES) and g["debate"]["count"] == debate.DEFAULT_COUNT
    assert g["debate"]["public"] is False


def test_needs_two_players():
    with pytest.raises(games.GameError):
        games.start(new(names=("Alice",)))


# ── Vote ──
def test_dilemma_then_secret_votes_then_reveal_shows_the_spread():
    g = new()
    games.start(g, random.Random(1))
    v = view(g)
    assert g["phase"] == "ask" and v["q"]["text"] in ALL and v["n"] == 1 and v["round"] == 1
    assert v["can_vote"] and v["voter"]["name"] == "Bob" and v["scale"] == list(debate.SCALE)
    vote_all(g, {"Alice": 4, "Bob": 0})
    assert g["phase"] == "ask" and view(g)["voter"]["name"] == "Chloé"
    games.db_vote(g, gid(g, "Chloé"), 3)
    assert g["phase"] == "reveal"
    res = view(g)["result"]
    assert res["counts"] == [1, 0, 0, 1, 1] and res["votes"] == 3
    assert res["pour"] == 2 and res["contre"] == 1


def test_votes_are_anonymous_by_default():
    g = new()
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": 4, "Bob": 0, "Chloé": 2})
    res = view(g)["result"]
    assert res["names"] is None and "Bob" not in str(res)


def test_public_mode_places_each_name_on_the_scale():
    g = new(public=True)
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": 4, "Bob": 0, "Chloé": 4})
    assert view(g)["result"]["names"] == [["Bob"], [], [], [], ["Alice", "Chloé"]]


def test_public_setting_cannot_change_during_a_game():
    """Passer en public après des votes promis anonymes trahirait les votants."""
    g = new()
    games.start(g, random.Random(1))
    with pytest.raises(debate.DebateError):
        debate.configure(g, {"public": True})


def test_ballots_stay_secret_until_everyone_voted():
    g = new()
    games.start(g, random.Random(1))
    games.db_vote(g, HOST_GID, 4)
    v = view(g, gid(g, "Bob"))
    assert v["result"] is None and v["voted"] == 1 and v["mine"] is None


def test_my_own_vote_is_shown_only_to_me():
    g = new()
    games.join(g, "guest-dan-0001", "Dan")
    games.start(g, random.Random(1))
    games.db_vote(g, HOST_GID, 1)
    assert view(g)["mine"] == 1
    assert view(g, "guest-dan-0001")["mine"] is None


def test_vote_is_final_and_must_be_on_the_scale():
    g = new()
    games.start(g, random.Random(1))
    for bad in (-1, 5, "2", None, True, 2.5):
        with pytest.raises(games.GameError):
            games.db_vote(g, HOST_GID, bad)
    games.db_vote(g, HOST_GID, 2)
    with pytest.raises(games.GameError):
        games.db_vote(g, HOST_GID, 3)


def test_people_without_phone_vote_in_table_order_on_the_host_phone():
    g = new()
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.db_vote(g, gid(g, "Chloé"), 2)  # c'est le tour de Bob
    games.db_vote(g, gid(g, "Bob"), 2)


def test_a_phone_player_votes_only_on_their_own_phone():
    g = new()
    games.join(g, "guest-dan-0001", "Dan")
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.db_vote(g, "guest-dan-0001", 2, HOST_GID)
    games.db_vote(g, "guest-dan-0001", 2, "guest-dan-0001")


def test_skip_absent_and_leave_do_not_block_the_reveal():
    g = new()
    games.start(g, random.Random(1))
    games.db_vote(g, HOST_GID, 3)
    games.db_skip(g)  # Bob est absent
    games.leave(g, gid(g, "Chloé"))
    assert g["phase"] == "reveal" and view(g)["result"]["votes"] == 1


def test_swap_only_before_the_first_vote():
    g = new()
    games.start(g, random.Random(1))
    first = view(g)["q"]["text"]
    games.db_swap(g, random.Random(2))
    assert view(g)["q"]["text"] != first and view(g)["n"] == 1
    games.db_vote(g, HOST_GID, 3)
    with pytest.raises(games.GameError):
        games.db_swap(g, random.Random(3))


# ── Revote (décidé par l'animateur) ──
def test_host_can_revote_once_and_see_who_changed_their_mind():
    g = new()
    games.start(g, random.Random(1))
    text = view(g)["q"]["text"]
    vote_all(g, {"Alice": 4, "Bob": 0, "Chloé": 1})
    games.db_revote(g)
    v = view(g)
    assert g["phase"] == "ask" and v["round"] == 2 and v["q"]["text"] == text and v["n"] == 1 and v["mine"] is None
    vote_all(g, {"Alice": 4, "Bob": 3, "Chloé": 1})
    res = view(g)["result"]
    assert res["before"] == [1, 1, 0, 0, 1] and res["counts"] == [0, 1, 0, 1, 1] and res["moved"] == 1
    with pytest.raises(games.GameError):
        games.db_revote(g)  # un seul revote par dilemme


def test_revote_only_after_the_reveal():
    g = new()
    games.start(g, random.Random(1))
    with pytest.raises(games.GameError):
        games.db_revote(g)


def test_next_dilemma_without_revote():
    g = new(count=10)
    games.start(g, random.Random(1))
    play(g, {"Alice": 4, "Bob": 0, "Chloé": 1})
    assert g["phase"] == "ask" and view(g)["n"] == 2 and view(g)["round"] == 1


# ── Fin et bilan ──
def test_no_dilemma_comes_back_and_the_game_ends_on_a_summary():
    g = new(count=10)
    games.start(g, random.Random(1))
    seen = []
    for i in range(10):
        seen.append(view(g)["q"]["text"])
        if i == 0:  # deux personnes changent d'avis, et tout le monde finit « Totalement pour »
            play(g, {"Alice": 4, "Bob": 0, "Chloé": 0}, revote={"Alice": 4, "Bob": 4, "Chloé": 4})
        elif i == 1:  # très partagé
            play(g, {"Alice": 0, "Bob": 4, "Chloé": 4})
        else:
            play(g, {"Alice": 3, "Bob": 2, "Chloé": 3})
    assert len(set(seen)) == 10 and g["phase"] == "end"
    b = view(g)["summary"]
    assert b["divisive"]["text"] == seen[1]
    assert b["unanimous"]["text"] == seen[0]
    assert b["moved"]["text"] == seen[0] and b["moved"]["moved"] == 2
    assert len(view(g)["history"]) == 10


def test_summary_has_no_mind_changer_without_revote():
    g = new(count=10)
    games.start(g, random.Random(1))
    for _ in range(10):
        play(g, {"Alice": 0, "Bob": 4, "Chloé": 2})
    assert view(g)["summary"]["moved"] is None


def test_restart_keeps_players_and_clears_the_history():
    g = new(count=10)
    games.start(g, random.Random(1))
    for _ in range(10):
        play(g, {"Alice": 0, "Bob": 4, "Chloé": 2})
    games.restart(g, random.Random(9))
    assert g["phase"] == "ask" and view(g)["n"] == 1 and view(g)["history"] == [] and len(g["players"]) == 3


def test_settings_validate_themes_count_and_public():
    g = new()
    debate.configure(g, {"themes": ["light", "moral"], "count": 30, "public": True})
    assert g["debate"]["themes"] == ["moral", "light"] and g["debate"]["count"] == 30 and g["debate"]["public"] is True
    for bad in ({"themes": []}, {"themes": ["nope"]}, {"themes": "moral"}, {"themes": [{}]}, {"themes": [["moral"]]},
                {"count": 7}, {"count": 10.0}, {"count": True}, {"public": "yes"}):
        with pytest.raises(debate.DebateError):
            debate.configure(g, bad)


def test_only_chosen_themes_are_asked():
    g = new(themes=["light"], count=30)
    games.start(g, random.Random(1))
    for _ in range(30):
        assert view(g)["q"]["text"] in LIGHT
        play(g, {"Alice": 0, "Bob": 4, "Chloé": 2})


# ── Dilemmes proposés par les joueurs ──
def test_player_proposal_waits_for_the_host_then_comes_next():
    g = new()
    games.join(g, "guest-dan-0001", "Dan")
    games.start(g, random.Random(1))
    games.db_propose(g, "guest-dan-0001", "  Faut-il   interdire les trottinettes en ville ?  ")
    dan = view(g, "guest-dan-0001")
    assert dan["my_pending"] == 1 and dan["proposals"] == []  # seul l'animateur voit les propositions
    pending = view(g)["proposals"]
    assert [(p["text"], p["by"]) for p in pending] == [("Faut-il interdire les trottinettes en ville ?", "Dan")]
    games.db_accept(g, pending[0]["id"])
    assert view(g)["proposals"] == [] and view(g)["queued"] == 1
    vote_all(g, {"Alice": 1, "Bob": 1, "Chloé": 1})
    games.db_vote(g, "guest-dan-0001", 1, "guest-dan-0001")
    games.next_step(g, random.Random(1))
    q = view(g)["q"]
    assert q["text"] == "Faut-il interdire les trottinettes en ville ?" and q["by"] == "Dan"


def test_refused_proposal_disappears():
    g = new()
    games.db_propose(g, HOST_GID, "Les chaussettes dans les sandales, c'est acceptable ?")
    games.db_refuse(g, view(g)["proposals"][0]["id"])
    assert view(g)["proposals"] == [] and view(g)["queued"] == 0


def test_proposal_validation():
    g = new()
    for bad in ("", "   ", "Court ?", "x" * 200, 42, None):
        with pytest.raises(games.GameError):
            games.db_propose(g, HOST_GID, bad)
    with pytest.raises(games.GameError):
        games.db_propose(g, "stranger-0001", "Faut-il dire la vérité à un ami ?")  # pas dans la partie
    for bad_id in (999, "1", None):
        with pytest.raises(games.GameError):
            games.db_accept(g, bad_id)


def test_a_player_cannot_flood_proposals():
    g = new()
    for i in range(debate.MAX_PENDING_PER_PLAYER):
        games.db_propose(g, HOST_GID, f"Le dilemme numéro {i} est-il acceptable ?")
    with pytest.raises(games.GameError):
        games.db_propose(g, HOST_GID, "Un dilemme de trop est-il acceptable ?")


def test_summary_facts_for_the_admin_reveal_no_vote():
    g = new()
    games.start(g, random.Random(1))
    games.db_vote(g, HOST_GID, 4)
    facts = " · ".join(games.summary(g)["facts"])
    assert "Dilemme 1/10" in facts and "anonymes" in facts


# ── Serveur ──
HOST = "host-debate-0001"
BOB = "guest-bob-00001"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_game_creations", {})
    monkeypatch.setattr(main.store.session, "games", {})
    with TestClient(main.app) as c:
        yield c


def act(c, code, action, guest_id=HOST, name="Alice", **kw):
    return c.post(f"/api/games/{code}", json={"guest_id": guest_id, "name": name, "action": action, **kw})


def test_api_full_dilemma_with_revote(client):
    r = client.post("/api/games", json={"type": "debate", "guest_id": HOST, "name": "Alice", "cats": ["moral", "light"], "public": True})
    assert r.status_code == 200, r.text
    g = r.json()
    code = g["code"]
    assert g["debate"]["themes"] == ["moral", "light"] and g["debate"]["public"] is True
    act(client, code, "join", guest_id=BOB, name="Bob")
    assert act(client, code, "start").json()["phase"] == "ask"
    assert act(client, code, "dbvote", amount=4).status_code == 200
    g = act(client, code, "dbvote", guest_id=BOB, name="Bob", amount=0).json()
    assert g["phase"] == "reveal" and g["debate"]["result"]["names"][0] == ["Bob"]
    assert act(client, code, "dbrevote", guest_id=BOB, name="Bob").status_code == 403  # l'animateur décide
    assert act(client, code, "dbrevote").json()["debate"]["round"] == 2


def test_api_proposals_flow(client):
    code = client.post("/api/games", json={"type": "debate", "guest_id": HOST, "name": "Alice"}).json()["code"]
    act(client, code, "join", guest_id=BOB, name="Bob")
    r = act(client, code, "dbpropose", guest_id=BOB, name="Bob", guess="Faut-il rendre le vote obligatoire ?")
    assert r.status_code == 200, r.text
    assert r.json()["debate"]["proposals"] == [] and r.json()["debate"]["my_pending"] == 1
    pid = act(client, code, "join").json()["debate"]["proposals"][0]["id"]
    assert act(client, code, "dbaccept", guest_id=BOB, name="Bob", amount=pid).status_code == 403
    assert act(client, code, "dbaccept", amount=pid).json()["debate"]["queued"] == 1


def test_api_other_games_refuse_debate_actions(client):
    code = client.post("/api/games", json={"type": "likely", "guest_id": HOST, "name": "Alice"}).json()["code"]
    assert act(client, code, "dbvote", amount=2).status_code == 400
    code = client.post("/api/games", json={"type": "debate", "guest_id": HOST, "name": "Alice"}).json()["code"]
    assert act(client, code, "lkvote").status_code == 400


def test_api_launch_from_the_game_room(client):
    room = client.post("/api/games", json={"type": "room", "guest_id": HOST, "name": "Alice"}).json()["code"]
    act(client, room, "join", guest_id=BOB, name="Bob")
    act(client, room, "addguest", guess="Mamie")
    r = act(client, room, "launch", settings={"type": "debate", "cats": ["society"], "public": False})
    assert r.status_code == 200, r.text
    child = r.json()["room_info"]["current"]["code"]
    g = act(client, child, "start").json()
    assert sorted(p["name"] for p in g["players"]) == ["Alice", "Bob", "Mamie"] and g["phase"] == "ask"
    assert g["debate"]["q"]["text"] in SOCIETY


# ── Retours de relecture ──
def test_swapping_a_player_dilemma_keeps_it_for_later():
    g = new()
    games.db_propose(g, gid(g, "Alice"), "Faut-il interdire les trottinettes en ville ?")
    games.db_accept(g, view(g)["proposals"][0]["id"])
    games.start(g, random.Random(1))
    assert view(g)["q"]["by"] == "Alice"
    games.db_swap(g, random.Random(2))
    v = view(g)
    assert v["q"]["by"] is None and v["queued"] == 1  # reposé plus tard, pas perdu


def test_public_names_stay_after_a_voter_leaves():
    g = new(public=True)
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": 4, "Bob": 0, "Chloé": 4})
    games.leave(g, gid(g, "Bob"))
    assert view(g)["result"]["names"][0] == ["Bob"]


def test_revote_emptied_by_departures_keeps_the_first_round_in_the_summary():
    g = new(names=("Alice", "Bob", "Chloé"))
    games.start(g, random.Random(1))
    vote_all(g, {"Alice": 4, "Bob": 0, "Chloé": 1})
    games.db_revote(g)
    games.leave(g, gid(g, "Bob"))
    games.leave(g, gid(g, "Chloé"))
    games.db_skip(g, HOST_GID)
    assert g["phase"] == "reveal"
    assert g["debate"]["history"][-1]["counts"] == [1, 1, 0, 0, 1]


def test_api_vote_without_amount_is_refused(client):
    code = client.post("/api/games", json={"type": "debate", "guest_id": HOST, "name": "Alice"}).json()["code"]
    act(client, code, "join", guest_id=BOB, name="Bob")
    act(client, code, "start")
    assert act(client, code, "dbvote").status_code == 409
    assert act(client, code, "dbvote", amount=0).status_code == 200


# ── Thème WTF (absurde et osé) : seulement si l'animateur le coche ──
def test_wtf_theme_is_off_by_default_and_flagged_for_the_host():
    assert "wtf" in debate.THEMES and "wtf" not in debate.DEFAULT_THEMES
    themes = {t["id"]: t for t in view(new())["theme_list"]}
    assert themes["wtf"]["adult"] is True and themes["moral"]["adult"] is False


def test_host_can_play_only_wtf():
    g = new(themes=["wtf"], count=30)
    games.start(g, random.Random(1))
    for _ in range(30):
        assert view(g)["q"]["text"] in WTF
        play(g, {"Alice": 0, "Bob": 4, "Chloé": 2})


def test_wtf_never_comes_without_being_chosen():
    g = new(count=30)
    games.start(g, random.Random(3))
    for _ in range(30):
        assert view(g)["q"]["text"] not in WTF
        play(g, {"Alice": 0, "Bob": 4, "Chloé": 2})


def test_api_default_themes_exclude_wtf_and_room_launch_keeps_it_off(client):
    g = client.post("/api/games", json={"type": "debate", "guest_id": HOST, "name": "Alice"}).json()
    assert "wtf" not in g["debate"]["themes"]
    g = client.post("/api/games", json={"type": "debate", "guest_id": BOB, "name": "Bob", "cats": ["light", "wtf"]}).json()
    assert g["debate"]["themes"] == ["light", "wtf"]
