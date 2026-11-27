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
