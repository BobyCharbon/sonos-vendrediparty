"""Joueur qui revient avec un autre identifiant (app installée ↔ Safari, navigation privée…) : pas de doublon."""
import pytest
from fastapi.testclient import TestClient

from app import main

HOST, OLD, NEW = "rejoin-host-0001", "rejoin-lea-old-01", "rejoin-lea-new-01"


@pytest.fixture
def api(monkeypatch):
    ips = {}
    monkeypatch.setattr(main, "client_ip", lambda request: ips.get("now", "10.0.0.1"))
    c = TestClient(main.app)

    def call(gid, action=None, ip="10.0.0.1", code=None, **extra):
        ips["now"] = ip
        if action is None:
            return c.get(f"/api/games/{code}", params={"guest_id": gid}).json()
        return c.post(f"/api/games/{code}", json={"guest_id": gid, "name": extra.pop("name", "Léa"), "action": action, **extra}).json()

    def create(kind="whoof"):
        ips["now"] = "10.0.0.9"
        return c.post("/api/games", json={"guest_id": HOST, "name": "Ludo", "type": kind, "plays": True}).json()["code"]
    call.create = create
    return call


def names(view):
    return [p["name"] for p in view["players"]]


def test_same_phone_reclaims_seat(api):
    code = api.create()
    first = api(OLD, "join", code=code)
    back = api(NEW, "join", code=code, name="léa ")  # autre navigateur, même téléphone, casse et espace différents
    assert len(back["players"]) == 2 and back["me"]["pid"] == first["me"]["pid"]
    assert api(NEW, code=code)["me"]["pid"] == first["me"]["pid"]  # l'état aussi parle au nom de l'ancienne place


def test_offline_seat_is_reclaimed_from_another_network(api, monkeypatch):
    code = api.create()
    first = api(OLD, "join", code=code)
    monkeypatch.setitem(main.store.last_seen, OLD, 0)  # téléphone parti depuis longtemps
    back = api(NEW, "join", code=code, ip="10.0.0.2")
    assert back["me"]["pid"] == first["me"]["pid"] and len(back["players"]) == 2


def test_two_real_namesakes_get_two_numbered_seats(api):
    code = api.create()
    api(OLD, "join", code=code)  # Léa est là, sur son téléphone
    other = api(NEW, "join", code=code, ip="10.0.0.2")  # une autre Léa, autre appareil
    assert names(other) == ["Ludo", "Léa", "Léa"]
    host = api(HOST, code=code)
    leas = [p for p in host["players"] if p["name"] == "Léa"]
    assert [p["twin"] for p in leas] == [1, 2] and all(p["online"] for p in leas)


def test_banned_player_cannot_come_back_through_a_new_id(api):
    code = api.create()
    lea = api(OLD, "join", code=code)["me"]["pid"]
    api(HOST, "ban", code=code, target=lea, name="Ludo")
    again = api(OLD, "join", code=code)
    assert "banni" in again["detail"]
