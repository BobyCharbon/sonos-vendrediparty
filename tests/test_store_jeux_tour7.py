"""Contrôle Apple, tour 7 (27.11), angle jeux de l'app App Store (« PartyStore ») :
- 🔴1 le titre d'un JEU n'est jamais lu comme un prénom (« Qui est le plus… ? » devenait « Joueur ») ;
- 🔴2 incitation au suicide en français, 🔴3 vocabulaire nazi : refusés en prénom et en réponse ;
- 🟠1 gagnants de l'historique de la salle passés par le même filtre que les prénoms ;
- 🟠3 refus à tort (Ricardo, Brasseur, « Un verre de lait »…) ;
- 🟠4 le prénom de l'animateur qui ne joue pas se signale, et l'animateur signale ;
- 🟠5 fabricants d'autres plateformes hors du Quiz de l'app ; 🟠7 Paliers en points, sans « comme à la télé » ;
- « Signaler » une réponse ou un dilemme dit « Traité sous 24 h · support@vendrediparty.ch »."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import games, main, store_app

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
STATIC = Path(main.__file__).resolve().parent / "static"


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


def name_blocked(text) -> bool:
    try:
        return main.name_refusal(main.clean_name(text), True) != ""
    except Exception:
        return True


def answer_blocked(text) -> bool:
    try:
        return games.shown_text(text, "answer", store=True) != text
    except games.GameError:
        return True


@pytest.mark.parametrize("kind", [k for k in games.GAMES if k not in store_app.HIDDEN_GAMES])
def test_the_app_sees_the_real_title_of_every_game(kind):
    title = games.GAMES[kind]
    # Partie, jeu en cours de la salle, historique de la salle : le titre reste, un vrai prénom refusé non.
    seen = games.store_view({"type": kind, "name": title, "host_name": "Vodka", "players": [{"name": "Vodka", "pid": "p1"}],
                             "room_info": {"current": {"type": kind, "name": title},
                                           "history": [{"type": kind, "name": title, "winner": "Vodka"}]}})
    assert seen["name"] == title
    assert seen["room_info"]["current"]["name"] == title and seen["room_info"]["history"][0]["name"] == title
    assert seen["host_name"] == "Joueur" and seen["players"][0]["name"] == "Joueur"
    assert seen["room_info"]["history"][0]["winner"] == "Joueur"


@pytest.mark.parametrize("kind", ["likely", "tmc", "psy", "debate", "quiz"])
def test_the_app_receives_the_title_of_a_game_it_creates(kind):
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    r = c.post("/api/games", json={"guest_id": f"tour7-host-{kind}", "name": "Léa", "type": kind, "terms": True})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == games.GAMES[kind]


def test_winners_of_the_room_history_go_through_the_name_filter():
    seen = games.store_view({"type": "room", "rhistory": [{"type": "likely", "name": "Qui est le plus… ?", "winner": "Pompette"}],
                             "history": [{"q": "…", "winners": ["Pompette", "Léa"]}]})
    assert seen["rhistory"][0] == {"type": "likely", "name": "Qui est le plus… ?", "winner": "Joueur"}
    assert seen["history"][0]["winners"] == ["Joueur", "Léa"]
    assert games.store_view({"winner": "Toute l’équipe"})["winner"] == "Toute l’équipe"


SUICIDE = ["Tue toi", "Tue-toi", "Pends toi", "Pends-toi", "Jette toi d'un pont", "Jette-toi par la fenêtre",
           "Ouvre toi les veines", "Va mourir", "Crève", "Suicide-toi", "Flingue toi"]
NAZI = ["Gestapo", "Swastika", "Croix gammée", "Wehrmacht", "Waffen SS", "Waffen", "Reich", "Kapo", "Mengele", "Eva Braun",
        "Sieg Heil"]


@pytest.mark.parametrize("text", SUICIDE + NAZI)
def test_suicide_incitement_and_nazi_words_are_refused(text):
    assert name_blocked(text), text
    assert answer_blocked(text), text


@pytest.mark.parametrize("text", ["Je suis crevé", "Trop crevé", "Il va mourir de rire", "Jette-toi à l'eau",
                                  "Ouvre-toi sésame", "Tire-toi", "Reichenbach", "Kapoor"])
def test_ordinary_french_still_passes(text):
    assert not answer_blocked(text), text


@pytest.mark.parametrize("name", ["Ricardo", "Brasseur", "Marie Brasseur", "Escobar", "Kirschner", "Perdrix", "Tchindjang"])
def test_real_names_are_no_longer_refused(name):
    assert not name_blocked(name), name
    assert not store_app.name_refused(name), name


@pytest.mark.parametrize("text", ["Un verre de lait", "Une bouteille d'eau", "Un verre de jus", "Le Casino de Montreux",
                                  "En Bourgogne"])
def test_ordinary_answers_are_no_longer_refused(text):
    assert not answer_blocked(text), text


@pytest.mark.parametrize("text", ["Ricard", "Pablo Escobar", "Une bouteille de vodka", "Un vin de Bourgogne", "Le casino",
                                  "Un verre de vin"])
def test_the_drinks_behind_those_exceptions_stay_refused(text):
    assert answer_blocked(text), text


def test_the_name_of_a_host_who_does_not_play_can_be_reported(monkeypatch):
    sent = []
    monkeypatch.setattr(main.journal, "record", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(main, "notify_admin", lambda *a, **k: None)
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    code = c.post("/api/games", json={"guest_id": "tour7-host-x", "name": "Kevin le roi", "type": "likely", "terms": True}).json()["code"]
    g = main.store.session.games[code]
    g["players"] = [p for p in g["players"] if p["id"] != "tour7-host-x"]  # l'animateur ne joue pas
    assert c.post(f"/api/games/{code}", json={"guest_id": "tour7-ana-x", "name": "Ana", "action": "join", "terms": True}).status_code == 200
    # L'animateur, qui ne joue pas, signale lui aussi ; et on ne signale pas son propre prénom.
    assert c.post(f"/api/games/{code}", json={"guest_id": "tour7-host-x", "action": "nreport", "target": "host"}).status_code == 409
    ana = next(p for p in c.get(f"/api/games/{code}?guest_id=tour7-ana-x").json()["players"] if p["name"] == "Ana")
    assert c.post(f"/api/games/{code}", json={"guest_id": "tour7-host-x", "action": "nreport", "target": ana["pid"]}).status_code == 200
    r = c.post(f"/api/games/{code}", json={"guest_id": "tour7-ana-x", "action": "nreport", "target": "host"})
    assert r.status_code == 200, r.text
    assert r.json()["host_name"].startswith("Joueur ") and r.json()["host_name_reported"]
    assert g["host_name"].startswith("Joueur ")
    assert [a[3]["text"] for a in sent] == ["Prénom signalé : Ana", "Prénom signalé : Kevin le roi"]
    js = (STATIC / "games.js").read_text()
    assert "function hostRow(g)" in js and 'data-target="host"' in js and "(g.me || g.is_owner) && p.pid !== g.me?.pid" in js


@pytest.mark.parametrize("text", ["Où se trouve le siège de BlackBerry ?", "Samsung est coréen", "Huawei", "Xiaomi", "Nokia"])
def test_other_phone_makers_never_reach_the_quiz_of_the_app(text):
    assert store_app.OTHER_PLATFORM_RE.search(text)
    assert store_app.clean_platforms([text, "Quelle est la capitale de la Suisse ?"]) == ["Quelle est la capitale de la Suisse ?"]


def test_the_ladder_counts_points_never_a_tv_prize():
    js = (STATIC / "quiz.js").read_text()
    assert "comme à la télé" not in js and "Tu as tout gagné" not in js
    assert "<b>${fmtPts(val)} pts</b>" in js and "Garder ${fmtPts(won)} pts" in js and "assuré : ${fmtPts(safe)} pts" in js


def test_reporting_an_answer_or_a_dilemma_says_who_handles_it_and_when():
    for name, marker in (("games.js", 'a === "treport" && !confirm('), ("debate.js", "Signaler ce dilemme ?"),
                         ("masque.js", "Signaler cette réponse ?")):
        js = (STATIC / name).read_text()
        line = next(x for x in js.splitlines() if marker in x)
        assert "Traité sous 24 h · support@vendrediparty.ch" in line, name


WEB_UA = "Mozilla/5.0 Safari"


def test_a_real_room_shows_game_titles_and_filters_the_winner_of_a_player_who_left():
    """Vrai parcours : salle du web, jeu lancé puis terminé, « Pompette » gagne puis s'en va ; l'app entre."""
    web, app = TestClient(main.app, headers={"User-Agent": WEB_UA}), TestClient(main.app, headers={"User-Agent": STORE_UA})
    code = web.post("/api/games", json={"guest_id": "tour7-room-host", "name": "Léa", "type": "room"}).json()["code"]
    room = main.store.session.games[code]
    games.join(room, "tour7-room-pomp", "Pompette")
    assert web.post(f"/api/games/{code}", json={"guest_id": "tour7-room-host", "action": "launch",
                                                "settings": {"type": "likely"}}).status_code == 200
    seen = app.get(f"/api/games/{code}?guest_id=tour7-room-app").json()
    assert seen["room_info"]["current"]["name"] == "Qui est le plus… ?"
    child = app.get(f"/api/games/{room['current']}?guest_id=tour7-room-app").json()
    assert child["name"] == "Qui est le plus… ?"
    main.end_game(room["current"], "host")
    room["rhistory"][-1]["winner"] = "Pompette"  # le plus désigné de la partie
    room["players"] = [p for p in room["players"] if p["id"] != "tour7-room-pomp"]  # parti de la salle
    history = app.get(f"/api/games/{code}?guest_id=tour7-room-app").json()["room_info"]["history"]
    assert history[0]["name"] == "Qui est le plus… ?" and history[0]["winner"] == "Joueur"
    assert web.get(f"/api/games/{code}?guest_id=tour7-room-host").json()["room_info"]["history"][0]["winner"] == "Pompette"


def test_neon_and_island_winner_ids_are_never_rewritten():
    assert games.store_view({"type": "neon", "neon": {"winner": "p1", "scores": {}}})["neon"]["winner"] == "p1"
    assert games.store_view({"type": "island", "island": {"winner": "p2"}})["island"]["winner"] == "p2"
    seen = games.store_view({"result": {"winners": [{"pid": "p1", "name": "Pompette"}, {"pid": "p2", "name": "Léa"}]}})
    assert seen["result"]["winners"] == [{"pid": "p1", "name": "Joueur"}, {"pid": "p2", "name": "Léa"}]


def test_the_reported_host_name_is_hidden_in_the_room_and_its_game(monkeypatch):
    monkeypatch.setattr(main.journal, "record", lambda *a, **k: None)
    monkeypatch.setattr(main, "notify_admin", lambda *a, **k: None)
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    code = c.post("/api/games", json={"guest_id": "tour7-rh-host", "name": "Kevin le roi", "type": "room", "terms": True}).json()["code"]
    for gid, name in (("tour7-rh-ana", "Ana"), ("tour7-rh-tom", "Tom")):
        assert c.post(f"/api/games/{code}", json={"guest_id": gid, "name": name, "action": "join", "terms": True}).status_code == 200
    assert c.post(f"/api/games/{code}", json={"guest_id": "tour7-rh-host", "action": "launch",
                                              "settings": {"type": "likely"}}).status_code == 200
    room = main.store.session.games[code]
    child = main.store.session.games[room["current"]]
    for x in (room, child):
        x["players"] = [p for p in x["players"] if p["id"] != "tour7-rh-host"]  # l'animateur ne joue pas
    r = c.post(f"/api/games/{child['code']}", json={"guest_id": "tour7-rh-ana", "action": "nreport", "target": "host"})
    assert r.status_code == 200, r.text
    assert room["host_name"] == child["host_name"] and room["host_name"].startswith("Joueur ")


@pytest.mark.parametrize("text", ["Crevé", "Un pneu crevé", "J'étais crevée", "Il crève de faim", "Crève-cœur"])
def test_crevé_passes_crève_does_not(text):
    assert not answer_blocked(text), text
