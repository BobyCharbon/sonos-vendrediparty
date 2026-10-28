"""App VendrediParty de l'App Store : sans jeux d'argent simulés (Casino, Blackjack), exigence d'Apple pour un
compte développeur individuel. Le site, l'app BETA et Android les gardent."""
import pytest
from fastapi.testclient import TestClient

from app import main

STORE_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0 PartyStore"
BETA_UA = "Mozilla/5.0 (iPhone) AppleWebKit/605.1.15 PartyApp-iOS/1.0.0"


@pytest.fixture(autouse=True)
def no_games(monkeypatch):
    """Parties des autres tests : le plafond de 30 parties ou de 5 créations par adresse serait atteint."""
    monkeypatch.setattr(main.store.session, "games", {})
    main._game_creations.clear()


def client(ua):
    return TestClient(main.app, headers={"User-Agent": ua})


def test_store_app_cannot_open_casino_or_blackjack():
    main._game_creations.clear()
    for kind in main.STORE_HIDDEN_GAMES:
        r = client(STORE_UA).post("/api/games", json={"guest_id": f"store-{kind}", "name": "Léa", "type": kind})
        assert r.status_code == 403 and "App Store" in r.json()["detail"]
    assert client(STORE_UA).post("/api/games", json={"guest_id": "store-ok", "name": "Léa", "type": "whoof"}).status_code == 200


def test_other_apps_keep_every_game():
    main._game_creations.clear()
    for i, ua in enumerate((BETA_UA, "Mozilla/5.0 Safari")):
        r = client(ua).post("/api/games", json={"guest_id": f"guest-bj-{i}", "name": "Tom", "type": "blackjack"})
        assert r.status_code == 200, r.text


def test_store_app_cannot_view_or_join_a_casino_opened_elsewhere():
    main._game_creations.clear()
    g = client(BETA_UA).post("/api/games", json={"guest_id": "web-host-1", "name": "Tom", "type": "casino"}).json()
    assert client(STORE_UA).get(f"/api/games/{g['code']}?guest_id=store-p1").status_code == 403
    r = client(STORE_UA).post(f"/api/games/{g['code']}", json={"guest_id": "store-p1", "action": "join", "name": "Léa"})
    assert r.status_code == 403


def test_store_app_cannot_launch_them_from_a_game_room():
    main._game_creations.clear()
    room = client(STORE_UA).post("/api/games", json={"guest_id": "store-room-1", "name": "Léa", "type": "room"}).json()
    r = client(STORE_UA).post(f"/api/games/{room['code']}", json={"guest_id": "store-room-1", "action": "launch",
                                                                  "settings": {"type": "blackjack"}})
    assert r.status_code == 403
