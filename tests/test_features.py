import pytest
from fastapi.testclient import TestClient

from app import main
from app.security import Limiter


class FakeSonos:
    def __init__(self):
        self.calls = []

    def move(self, uid, a, b):
        self.calls.append(("move", a, b))

    def remove_at(self, uid, pos):
        self.calls.append(("remove", pos))

    def play_at(self, uid, pos):
        self.calls.append(("play", pos))


def snap():
    track = lambda pos, tid, title: {"pos": pos, "track_id": tid, "title": title, "artist": "A", "art": ""}
    return {
        "coordinator_ip": "127.0.0.1", "room": "Salon", "state": "PLAYING", "from_queue": True, "current_pos": 4,
        "current": track(4, "c" * 22, "En cours"),
        "upcoming": [track(5, "a" * 22, "Un"), track(6, None, "Deux"), track(7, "b" * 22, "Trois")],
        "now": {"title": "En cours", "artist": "A", "art": "", "position": "", "duration": ""},
    }


@pytest.fixture
def admin(monkeypatch):
    fake = FakeSonos()
    monkeypatch.setattr(main, "sonos", fake)
    monkeypatch.setattr(main, "snapshot", lambda force=False: snap())
    monkeypatch.setattr(main, "guest_limiter", Limiter(per_ip=5, ip_lock=900, global_max=30, global_window=600, global_lock=600))
    main.store.start("RINCON_X", "Salon", "next")
    client = TestClient(main.app)
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    client.fake = fake
    return client


def test_admin_moves_any_track(admin):
    queue = admin.get("/api/admin/state").json()["queue"]
    assert [t["pos"] for t in queue] == [5, 6, 7]
    deux = queue[1]
    assert deux["key"] == "Deux|A"  # titre hors Spotify : identifié par titre + artiste

    admin.post("/api/admin/queue", json={"pos": 7, "key": queue[2]["key"], "action": "next"})
    admin.post("/api/admin/queue", json={"pos": 6, "key": deux["key"], "action": "down"})
    admin.post("/api/admin/queue", json={"pos": 6, "key": deux["key"], "action": "remove"})
    assert admin.fake.calls == [("move", 7, 5), ("move", 6, 7), ("remove", 6)]


def test_queue_action_refused_if_queue_changed(admin):
    r = admin.post("/api/admin/queue", json={"pos": 5, "key": "autre-titre", "action": "remove"})
    assert r.status_code == 409
    assert admin.fake.calls == []


def test_guest_appears_on_hello_and_sends_message(admin):
    guest = TestClient(main.app)
    guest.post("/api/join", json={"pin": main.store.session.guest_pin})
    assert guest.post("/api/hello", json={"guest_id": "guest-1234", "guest_name": "Léa"}).status_code == 200

    names = [g["name"] for g in admin.get("/api/admin/state").json()["guests"]]
    assert "Léa" in names

    r = guest.post("/api/message", json={"guest_id": "guest-1234", "guest_name": "Léa", "text": "Un peu de Daft Punk ?"})
    assert r.status_code == 200
    # Anti-spam : pas deux messages d'affilée.
    r = guest.post("/api/message", json={"guest_id": "guest-1234", "guest_name": "Léa", "text": "Encore !"})
    assert r.status_code == 429

    msgs = admin.get("/api/admin/state").json()["messages"]
    assert msgs[0]["text"] == "Un peu de Daft Punk ?" and not msgs[0]["read"]
    msgs = admin.post("/api/admin/messages", json={"ids": None, "action": "read"}).json()["messages"]
    assert all(m["read"] for m in msgs)
