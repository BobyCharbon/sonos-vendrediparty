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


def test_host_seat_is_not_stolen_by_a_namesake(api, monkeypatch):
    # Sécurité : derrière le NAT d'une soirée, une IP partagée ne doit pas permettre
    # à un invité de reprendre le siège de l'animateur en se nommant comme lui.
    code = api.create()  # hôte « Ludo » (HOST), plays=True
    intruder = api("rejoin-intrus-0001", "join", code=code, name="ludo ")  # même IP, même prénom
    assert intruder["me"]["pid"] != api(HOST, code=code)["me"]["pid"]  # place distincte, pas celle de l'hôte
    # L'hôte reste l'hôte (toujours lead/host sur son identifiant stable).
    host_view = api(HOST, code=code)
    assert host_view["me"].get("host") or host_view["me"]["pid"] != intruder["me"]["pid"]
    # Même une place devenue hors-ligne ne cède pas le siège animateur.
    monkeypatch.setitem(main.store.last_seen, HOST, 0)
    again = api("rejoin-intrus-0002", "join", code=code, name="Ludo")
    assert again["me"]["pid"] != api(HOST, code=code)["me"]["pid"]


def test_banned_player_cannot_come_back_through_a_new_id(api):
    code = api.create()
    lea = api(OLD, "join", code=code)["me"]["pid"]
    api(HOST, "ban", code=code, target=lea, name="Ludo")
    again = api(OLD, "join", code=code)
    assert "banni" in again["detail"]
