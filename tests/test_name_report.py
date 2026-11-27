"""« 🚩 Signaler ce prénom » (contrôle Apple 1.2, 27.11) : tout joueur signale le prénom d'un AUTRE joueur ; il devient
« Joueur N » aussitôt pour toute la table, le signalement va au journal `game.report` et à l'admin (« Retours »), une
fois par signaleur et par joueur."""
import pytest
from fastapi.testclient import TestClient

from app import main

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    monkeypatch.setattr(main.store.session, "games", {})
    monkeypatch.setattr(main, "save_games", lambda *a, **k: None)
    main._game_creations.clear()


@pytest.fixture
def sent(monkeypatch):
    out = {"journal": [], "admin": []}
    monkeypatch.setattr(main.journal, "record", lambda *a, **k: out["journal"].append(a))
    monkeypatch.setattr(main, "notify_admin", lambda payload, kind="messages": kind == "feedback" and out["admin"].append((payload, kind)))
    return out


def test_a_reported_name_shows_as_joueur_n_for_the_whole_table_once_per_reporter(sent):
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    code = c.post("/api/games", json={"guest_id": "namerep-host", "name": "Léa", "type": "likely", "terms": True}).json()["code"]
    for gid, name in (("namerep-bad", "Kevin le roi"), ("namerep-c", "Tom")):
        assert c.post(f"/api/games/{code}", json={"guest_id": gid, "name": name, "action": "join", "terms": True}).status_code == 200
    view = c.get(f"/api/games/{code}?guest_id=namerep-c").json()
    bad = next(p for p in view["players"] if p["name"] == "Kevin le roi")
    assert not bad.get("name_reported")
    # On ne se signale pas soi-même.
    me = next(p for p in view["players"] if p["name"] == "Tom")
    assert c.post(f"/api/games/{code}", json={"guest_id": "namerep-c", "action": "nreport", "target": me["pid"]}).status_code == 409

    r = c.post(f"/api/games/{code}", json={"guest_id": "namerep-c", "action": "nreport", "target": bad["pid"]})
    assert r.status_code == 200, r.text
    mine = next(p for p in r.json()["players"] if p["pid"] == bad["pid"])
    assert mine["name"].startswith("Joueur ") and mine["name_reported"]
    # Toute la table (l'animateur compris) le voit « Joueur N », et le prénom ne revient pas s'il le renvoie.
    for gid, q in (("namerep-host", ""), ("namerep-bad", "&name=Kevin%20le%20roi")):
        names = [p["name"] for p in c.get(f"/api/games/{code}?guest_id={gid}{q}").json()["players"]]
        assert "Kevin le roi" not in names and mine["name"] in names
    host_view = c.get(f"/api/games/{code}?guest_id=namerep-host").json()
    assert not next(p for p in host_view["players"] if p["pid"] == bad["pid"]).get("name_reported")  # l'hôte peut encore signaler
    # Journal et admin : le prénom d'origine, une seule fois pour ce signaleur.
    assert len(sent["journal"]) == 1 and sent["journal"][0][0] == "game.report"
    assert sent["journal"][0][3]["text"] == "Prénom signalé : Kevin le roi" and sent["journal"][0][3]["author"] == "Kevin le roi"
    assert len(sent["admin"]) == 1 and sent["admin"][0][1] == "feedback" and "Kevin le roi" in sent["admin"][0][0]["body"]
    assert c.post(f"/api/games/{code}", json={"guest_id": "namerep-c", "action": "nreport", "target": bad["pid"]}).status_code == 200
    assert len(sent["journal"]) == 1 and len(sent["admin"]) == 1
    # Un autre joueur peut signaler aussi (la modération voit les deux), le numéro ne change pas.
    c.post(f"/api/games/{code}", json={"guest_id": "namerep-host", "action": "nreport", "target": bad["pid"]})
    assert len(sent["journal"]) == 2
    assert next(p for p in c.get(f"/api/games/{code}?guest_id=namerep-c").json()["players"] if p["pid"] == bad["pid"])["name"] == mine["name"]


def test_a_reported_name_is_hidden_in_the_room_and_its_game(sent):
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    room = c.post("/api/games", json={"guest_id": "namerep-rh", "name": "Léa", "type": "room", "terms": True}).json()["code"]
    for gid, name in (("namerep-rb", "Maxou"), ("namerep-rc", "Tom")):
        assert c.post(f"/api/games/{room}", json={"guest_id": gid, "name": name, "action": "join", "terms": True}).status_code == 200
    r = c.post(f"/api/games/{room}", json={"guest_id": "namerep-rh", "action": "launch", "settings": {"type": "likely"}})
    assert r.status_code == 200, r.text
    child = main.room_child(main.store.session.games[room])
    bad = next(p for p in c.get(f"/api/games/{room}?guest_id=namerep-rc").json()["players"] if p["name"] == "Maxou")
    assert c.post(f"/api/games/{room}", json={"guest_id": "namerep-rc", "action": "nreport", "target": bad["pid"]}).status_code == 200
    for x in (main.store.session.games[room], child):
        assert "Maxou" not in [p["name"] for p in x["players"]]
    assert {p["name"] for p in main.store.session.games[room]["players"] if p["id"] == "namerep-rb"} == \
           {p["name"] for p in child["players"] if p["id"] == "namerep-rb"}


def test_a_name_reported_in_the_room_stays_joueur_n_in_every_game_launched_after(sent):
    c = TestClient(main.app, headers={"User-Agent": STORE_UA})
    room = c.post("/api/games", json={"guest_id": "namerep-sh", "name": "Léa", "type": "room", "terms": True}).json()["code"]
    for gid, name in (("namerep-sb", "Maxou"), ("namerep-sc", "Tom")):
        assert c.post(f"/api/games/{room}", json={"guest_id": gid, "name": name, "action": "join", "terms": True}).status_code == 200
    bad = next(p for p in c.get(f"/api/games/{room}?guest_id=namerep-sc").json()["players"] if p["name"] == "Maxou")
    assert c.post(f"/api/games/{room}", json={"guest_id": "namerep-sc", "action": "nreport", "target": bad["pid"]}).status_code == 200
    alias = next(p["name"] for p in main.store.session.games[room]["players"] if p["id"] == "namerep-sb")
    for _ in range(2):  # un jeu, sa fin, puis un autre jeu
        assert c.post(f"/api/games/{room}", json={"guest_id": "namerep-sh", "action": "launch", "settings": {"type": "likely"}}).status_code == 200
        child = main.room_child(main.store.session.games[room])
        view = c.get(f"/api/games/{child['code']}?guest_id=namerep-sb&name=Maxou").json()
        assert "Maxou" not in [p["name"] for p in view["players"]] and alias in [p["name"] for p in view["players"]]
        mine = c.get(f"/api/games/{child['code']}?guest_id=namerep-sc").json()
        pid = next(p["pid"] for p in mine["players"] if p["name"] == alias)
        assert next(p for p in mine["players"] if p["pid"] == pid)["name_reported"]
        assert c.post(f"/api/games/{child['code']}", json={"guest_id": "namerep-sc", "action": "nreport", "target": pid}).status_code == 200
        assert len(sent["journal"]) == 1
        assert c.post(f"/api/games/{child['code']}", json={"guest_id": "namerep-sh", "action": "end"}).status_code == 200
