"""Party extérieur : la file des demandes reste sur le serveur, une demande part chez Spotify avant la fin du titre."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.spotify_player import SpotifyPlayer


class FakeUser:
    connected, name, data = True, "Ludo", {"premium": True}

    def __init__(self):
        self.pb = {"is_playing": True, "progress_ms": 10_000, "device": {"name": "iPhone", "volume_percent": 50},
                   "item": {"id": "p" * 22, "name": "Playlist", "duration_ms": 200_000, "artists": [{"name": "DJ"}], "album": {"images": []}}}
        self.calls = []

    def playback(self):
        return self.pb

    def queue(self, tid):
        self.calls.append(("queue", tid))

    def next(self):
        self.calls.append(("next",))

    def play(self, uri=None):
        self.calls.append(("play", uri))

    def pause(self):
        self.calls.append(("pause",))

    def shuffle(self, on):
        self.calls.append(("shuffle", on))

    def volume(self, v):
        self.calls.append(("volume", v))


class FakeCatalog:
    def track(self, tid):
        return {"id": tid, "title": f"T-{tid[0]}", "artist": "A", "image": "", "duration_ms": 180_000, "explicit": False}

    search = lambda self, q: []


@pytest.fixture
def ext(monkeypatch):
    user, cat = FakeUser(), FakeCatalog()
    sp = SpotifyPlayer(user, cat, main.store)
    monkeypatch.setattr(main, "spotify_player", sp)
    monkeypatch.setattr(main, "spotify_user", user)
    monkeypatch.setattr(main, "spotify", cat)
    main.store.start("spotify", "Spotify", "next", source="spotify")
    main._snap.update(data=None, current=None)
    client = TestClient(main.app)
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    client.user, client.sp = user, sp
    return client


def test_requests_stay_on_server_until_near_end(ext):
    ext.post("/api/admin/add", json={"track_id": "a" * 22, "where": "next"})
    ext.post("/api/admin/add", json={"track_id": "b" * 22, "where": "next"})  # « juste après » : passe devant a
    assert main.store.session.vqueue == ["b" * 22, "a" * 22]
    assert ext.user.calls == []  # rien n'est encore parti chez Spotify
    ext.user.pb["progress_ms"] = 190_000  # 10 s avant la fin
    main.snapshot(force=True)
    assert ext.user.calls == [("queue", "b" * 22)] and main.store.session.vpushed == "b" * 22
    main.snapshot(force=True)
    assert ext.user.calls == [("queue", "b" * 22)]  # une seule à la fois
    # La demande démarre : elle quitte la file, la suivante attendra la fin de ce titre.
    ext.user.pb.update(progress_ms=1000, item={**ext.user.pb["item"], "id": "b" * 22})
    snap = main.snapshot(force=True)
    assert main.store.session.vqueue == ["a" * 22] and main.store.session.vpushed == ""
    assert snap["current"]["track_id"] == "b" * 22 and [t["track_id"] for t in snap["upcoming"]] == ["a" * 22]


def test_queue_actions_and_skip(ext):
    for t in ("a", "b", "c"):
        ext.post("/api/admin/add", json={"track_id": t * 22, "where": "end"})
    assert main.store.session.vqueue == ["a" * 22, "b" * 22, "c" * 22]
    state = ext.get("/api/admin/state").json()
    c = next(t for t in state["queue"] if t["key"] == "c" * 22)
    ext.post("/api/admin/queue", json={"pos": c["pos"], "key": c["key"], "action": "next"})
    assert main.store.session.vqueue[0] == "c" * 22
    ext.post("/api/admin/skip", json={})
    assert ext.user.calls[-2:] == [("queue", "c" * 22), ("next",)]  # la demande en tête passe tout de suite


def test_start_requires_spotify_account(ext, monkeypatch):
    monkeypatch.setattr(ext.user.__class__, "connected", False)
    r = ext.post("/api/admin/start", json={"source": "spotify", "mode": "next"})
    assert r.status_code == 409
