"""Recette simulateur du 28.11 (décision Q1 choix b) : ce que la recette réelle a trouvé côté serveur.
- Musique : un prénom de l'app (écrans natifs « X-Party-Native: ios » ou vue web « PartyStore ») hors de la liste devient
  « Joueur » pour l'hôte et les invités (/api/hello, /api/message, /api/presence) ; le web garde son prénom.
- « + Ajouter » (participant sans téléphone) : un prénom de la liste déjà pris devient « Joueur N », dans la salle ET son jeu.
- L'Intrus : les 6 mots proposés au Fantôme ne sont envoyés qu'à lui."""
import pytest
from fastapi.testclient import TestClient

from app import games, main, store_app
from tests.test_features import admin  # noqa: F401 (fixture)
from tests.test_store_sans_texte import STORE_UA, WEB_UA, Reader, body, isolated  # noqa: F401 (fixture)

NATIVE = {"X-Party-Native": "ios", "User-Agent": "Party/216 CFNetwork"}


def music_guest(headers):
    c = TestClient(main.app, headers=headers)
    assert c.post("/api/join", json={"pin": main.store.session.guest_pin}).status_code == 200
    return c


@pytest.mark.parametrize("headers", [NATIVE, {"User-Agent": STORE_UA}])
def test_a_music_name_from_the_app_is_one_of_the_list_or_joueur(admin, headers):  # noqa: F811
    app = music_guest(headers)
    main._last_message.clear()
    for gid, sent, kept in (("mq-app-0001", "Zorblax", "Joueur"), ("mq-app-0002", "lea", "Léa"),
                            ("mq-app-0003", "Joueur 4", "Joueur 4")):
        assert app.post("/api/hello", json={"guest_id": gid, "guest_name": sent}).status_code == 200
        assert main.store.session.guests[gid]["name"] == kept
        assert app.get(f"/api/state?guest_id={gid}").json()["name"] == kept  # l'app le reprend (MusicStore.reload)
    r = app.post("/api/message", json={"guest_id": "mq-app-0004", "guest_name": "Zorblax", "text": "Merci pour la soirée"})
    assert r.status_code == 200 and main.store.session.guests["mq-app-0004"]["name"] == "Joueur"
    assert main.store.session.messages[-1]["name"] == "Joueur"
    assert app.post("/api/presence", json={"guest_id": "mq-app-0005", "name": "Zorblax"}).status_code == 200
    assert main.store.session.guests["mq-app-0005"]["name"] == "Joueur"
    assert "Zorblax" not in str(main.store.session.guests) + str(main.store.session.messages)


def test_the_web_keeps_its_typed_music_name(admin):  # noqa: F811
    web = music_guest({"User-Agent": WEB_UA})
    web.post("/api/hello", json={"guest_id": "mq-web-0001", "guest_name": "Zorblax"})
    assert main.store.session.guests["mq-web-0001"]["name"] == "Zorblax"


def test_a_name_added_twice_by_the_host_becomes_joueur_n_in_the_room_and_its_game():
    app = Reader(STORE_UA)
    code = app.post("/api/games", {"guest_id": "ma-host-0001", "name": "Léa", "type": "room", "terms": True}).json()["code"]
    assert app.post(f"/api/games/{code}", {**body("ma-host-0001", "launch", "room"), "settings": {"type": "likely"}}).status_code == 200
    for _ in range(3):
        r = app.post(f"/api/games/{code}", {**body("ma-host-0001", "addguest", "room"), "guess": "Alice"})
        assert r.status_code == 200, r.text
    room = main.store.session.games[code]
    child = main.room_child(room)
    names = [p["name"] for p in room["players"] if p.get("manual")]
    assert names.count("Alice") == 1 and len(set(names)) == 3, names
    assert all(n == "Alice" or store_app.ALIAS_RE.fullmatch(n) for n in names), names
    assert sorted(names) == sorted(p["name"] for p in child["players"] if p.get("manual"))  # même prénom des deux côtés


def test_a_name_added_twice_in_a_game_of_the_app_becomes_joueur_n():
    app = Reader(STORE_UA)
    code = app.post("/api/games", {"guest_id": "mb-host-0001", "name": "Léa", "type": "likely", "terms": True}).json()["code"]
    for n in ("Alice", "Alice", "Léa"):
        assert app.post(f"/api/games/{code}", {**body("mb-host-0001", "addguest", "likely"), "guess": n}).status_code == 200
    names = [p["name"] for p in main.store.session.games[code]["players"]]
    assert len(set(names)) == len(names) and names.count("Alice") == 1, names


def test_only_the_ghost_receives_the_six_words():
    app = Reader(STORE_UA)
    code = app.post("/api/games", {"guest_id": "mc-host-0001", "name": "Léa", "type": "undercover", "terms": True,
                                   "white": True}).json()["code"]
    for i, n in enumerate(("Tom", "Zoé", "Hugo", "Lina")):
        assert app.post(f"/api/games/{code}", {**body(f"mc-p{i}-00001", "join", "undercover"), "name": n}).status_code == 200
    g = main.store.session.games[code]
    games.start(g)
    white = next(p for p in g["players"] if p["role"] == "white")
    g["phase"] = "vote"
    games.eliminate(g, white["id"])
    assert app.get(f"/api/games/{code}", guest_id=white["id"]).json()["last"]["choices"] == g["last"]["choices"]
    for p in g["players"]:
        if p["id"] != white["id"]:
            assert "choices" not in app.get(f"/api/games/{code}", guest_id=p["id"]).json()["last"], p["name"]
    assert "choices" not in games.view(g, "")["last"]  # télé, animateur qui ne joue pas
