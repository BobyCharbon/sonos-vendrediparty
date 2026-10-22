"""Party maison = file Sonos native (API locale Sonos, compte Spotify lié au système Sonos), comme avant :
pas besoin de connecter un compte Spotify dans Party ; mode d'insertion choisi au démarrage."""
from fastapi.testclient import TestClient

from app import main
from tests.test_features import FakeSonos


class RoomsSonos(FakeSonos):
    def rooms(self):
        return [{"uid": "RINCON_ARC", "name": "Arc Bureau", "spotify_name": "Arc Bureau"}]


def admin_client(monkeypatch):
    monkeypatch.setattr(main, "sonos", RoomsSonos())
    monkeypatch.setattr(main, "spotify_user", None)  # aucun compte Spotify connecté dans Party
    main.store.stop()
    c = TestClient(main.app)
    assert c.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    return c


def test_home_party_starts_on_the_native_sonos_queue_without_spotify_account(monkeypatch):
    c = admin_client(monkeypatch)
    r = c.post("/api/admin/start", json={"source": "sonos", "room_uid": "RINCON_ARC", "mode": "fair"})
    assert r.status_code == 200, r.text
    assert main.store.session.source == "sonos" and main.store.session.room_uid == "RINCON_ARC"
    assert main.store.session.mode == "fair"  # le mode d'insertion choisi est gardé (Équitable)
    main.store.stop()


def test_home_party_rejects_an_unknown_room(monkeypatch):
    c = admin_client(monkeypatch)
    assert c.post("/api/admin/start", json={"source": "sonos", "room_uid": "RINCON_AUTRE"}).status_code == 404
    assert not main.store.session.active


def test_default_source_is_the_native_sonos_queue():
    assert main.Start().source == "sonos"
