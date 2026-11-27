from fastapi.testclient import TestClient
from tests.test_controle_tour7 import admin  # noqa: F401
from app import main

def test_native_music_screen_hides_other_guests_names(admin):  # noqa: F811
    main.store.session.played = [
        {"track_id": "p" * 22, "title": "Avant", "artist": "A", "art": "", "by": "Noé", "at": 0},
        {"track_id": "c" * 22, "title": "En cours", "artist": "A", "art": "", "by": "Noé", "at": 1},
    ]
    g = TestClient(main.app, headers={"user-agent": "Party/1 CFNetwork Darwin", "x-party-native": "ios"})
    g.post("/api/join", json={"pin": main.store.session.guest_pin})
    g.post("/api/hello", json={"guest_id": "guest-native-1", "guest_name": "Zoé"})
    s = g.get("/api/state?guest_id=guest-native-1").json()
    assert [p["by"] for p in s["played"]] == [None]


def test_native_music_screen_hides_names_in_now_and_queue_but_keeps_mine(admin, monkeypatch):  # noqa: F811
    """Contrôle final (contenus, 1.2) : l'écran natif ne montre jamais le prénom d'un autre invité, ni pour le titre en
    cours ni dans la file ; ses propres demandes (rid) gardent le sien."""
    monkeypatch.setattr(main, "public_sonos", lambda *a, **k: {
        "now": {"title": "En cours", "artist": "A", "art": "", "by": "Noé", "track_id": "c" * 22},
        "upcoming": [{"title": "Le sien", "by": "Zoé", "rid": "r1"}, {"title": "D'un autre", "by": "Noé", "rid": None}],
    })
    g = TestClient(main.app, headers={"user-agent": "Party/1 CFNetwork Darwin", "x-party-native": "ios"})
    g.post("/api/join", json={"pin": main.store.session.guest_pin})
    g.post("/api/hello", json={"guest_id": "guest-native-2", "guest_name": "Zoé"})
    s = g.get("/api/state?guest_id=guest-native-2").json()
    assert s["now"]["by"] is None
    assert [(t["title"], t["by"]) for t in s["upcoming"]] == [("Le sien", "Zoé"), ("D'un autre", None)]
    web = TestClient(main.app, headers={"user-agent": "Mozilla/5.0 Safari"})
    web.post("/api/join", json={"pin": main.store.session.guest_pin})
    assert web.get("/api/state?guest_id=guest-native-2").json()["now"]["by"] == "Noé"  # le site garde tout
