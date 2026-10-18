"""Party extérieur : ajout immédiat, file Spotify de référence et aucun renvoi automatique."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.party import PartyStore
from app.spotify import SpotifyError, SpotifyUser
from app.spotify_player import SpotifyPlayer


def item(letter):
    return {"id": letter * 22, "type": "track", "name": f"T-{letter}", "duration_ms": 200_000,
            "artists": [{"name": "DJ"}], "album": {"images": []}}


class FakeUser:
    connected, name, data = True, "Ludo", {"premium": True}

    def __init__(self):
        self.pb = {"is_playing": True, "progress_ms": 10_000,
                   "device": {"name": "iPhone", "volume_percent": 50}, "item": item("p")}
        self.calls, self.items = [], []

    def playback(self):
        return self.pb

    def get_queue(self):
        return {"currently_playing": (self.pb or {}).get("item"), "queue": list(self.items)}

    def queue(self, tid):
        self.calls.append(("queue", tid))
        self.items.append(item(tid[0]))

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
def ext(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "store", PartyStore(tmp_path / "session.json"))
    monkeypatch.setattr(main, "_snap", {"at": 0, "data": None, "fingerprint": None, "version": 0, "current": None})
    user, cat = FakeUser(), FakeCatalog()
    sp = SpotifyPlayer(user, cat, main.store)
    monkeypatch.setattr(main, "spotify_player", sp)
    monkeypatch.setattr(main, "spotify_user", user)
    monkeypatch.setattr(main, "spotify", cat)
    main.store.start("spotify", "Spotify", "next", source="spotify")
    client = TestClient(main.app)
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    client.user, client.sp = user, sp
    return client


def add(ext, letter, **kw):
    return ext.post("/api/admin/add", json={"track_id": letter * 22, "where": "end", **kw})


def test_requests_are_sent_immediately_in_arrival_order(ext):
    ext.user.items.append(item("x"))  # titre ajouté directement dans Spotify
    assert add(ext, "a").status_code == 200
    assert add(ext, "b", where="next").status_code == 200  # ancien client : même ajout immédiat
    assert ext.user.calls == [("queue", "a" * 22), ("queue", "b" * 22)]
    assert main.store.session.vqueue == []
    ext.user.pb["progress_ms"] = 190_000
    for _ in range(3):
        main.snapshot(force=True)
    assert len(ext.user.calls) == 2
    assert [t["key"] for t in ext.get("/api/admin/state").json()["queue"]] == [c * 22 for c in "xab"]


def test_guest_add_is_immediate_and_search_response_confirms_spotify(ext):
    assert ext.post("/api/join", json={"pin": main.store.session.guest_pin}).status_code == 200
    r = ext.post("/api/queue", json={"track_id": "a" * 22, "guest_id": "guest-1234", "guest_name": "Alice"})
    assert r.status_code == 200 and r.json()["source"] == "spotify"
    assert ext.user.calls == [("queue", "a" * 22)]
    state = ext.get("/api/state?guest_id=guest-1234").json()
    assert state["queue_editable"] is False and state["upcoming"][0]["by"] == "Alice"
    assert ext.post("/api/queue/remove", json={"request_id": main.store.pending()[0].id, "guest_id": "guest-1234"}).status_code == 409


@pytest.mark.parametrize("action", ["next", "up", "down", "play", "remove"])
def test_editing_queue_is_rejected_without_mutation(ext, action):
    add(ext, "a")
    r = ext.post("/api/admin/queue", json={"pos": 2, "key": "a" * 22, "action": action})
    assert r.status_code == 409 and "Spotify" in r.json()["detail"]
    assert ext.user.calls == [("queue", "a" * 22)]
    assert main.store.pending()[0].status == "queued"


def test_mode_remove_purge_undo_are_rejected_and_skip_only_skips(ext):
    add(ext, "a")
    for url, body in [
        ("/api/admin/mode", {"mode": "fair"}),
        ("/api/admin/remove", {"request_id": main.store.pending()[0].id}),
        ("/api/admin/purge", {"guest_id": "host"}),
        ("/api/admin/undo", {"token": "old-token"}),
    ]:
        assert ext.post(url, json=body).status_code == 409
    assert main.store.session.mode == "next"
    assert ext.post("/api/admin/skip", json={}).status_code == 200
    assert ext.user.calls == [("queue", "a" * 22), ("next",)]


def test_spotify_reordering_and_removal_are_reflected_in_preview(ext):
    add(ext, "a")
    add(ext, "b")
    ext.user.items = [item("b"), item("x")]
    snap = main.snapshot(force=True)
    assert [t["track_id"] for t in snap["upcoming"]] == [c * 22 for c in "bx"]
    # L'absence dans un aperçu ne prouve pas qu'un titre a été joué.
    assert all(r.status == "queued" for r in main.store.session.requests)


def test_failed_add_is_not_recorded_or_retried(ext, monkeypatch):
    def fail(tid):
        ext.user.calls.append(("queue", tid))
        raise SpotifyError("Aucun appareil Spotify actif")
    monkeypatch.setattr(ext.user, "queue", fail)
    r = add(ext, "a")
    assert r.status_code == 502 and "appareil Spotify" in r.json()["detail"]
    assert not main.store.session.requests
    for _ in range(3):
        main.snapshot(force=True)
    assert len(ext.user.calls) == 1


def test_ambiguous_send_does_not_retry_during_polling(ext, monkeypatch):
    def fail(tid):
        ext.user.calls.append(("queue", tid))
        raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(ext.user, "queue", fail)
    r = add(ext, "a")
    assert r.status_code == 502 and "vérifie la file Spotify" in r.json()["detail"]
    for _ in range(3):
        main.snapshot(force=True)
    assert len(ext.user.calls) == 1


def test_relinked_current_marks_one_request_played_and_notifies_once(ext, monkeypatch):
    notifications = []
    monkeypatch.setattr(main, "notify_guest", lambda *args: notifications.append(args))
    add(ext, "a")
    add(ext, "a", force=True)
    ext.user.pb.update(progress_ms=1000, item={**item("z"), "linked_from": {"id": "a" * 22}})
    main.snapshot(force=True)
    main.snapshot(force=True)
    assert [r.status for r in main.store.session.requests] == ["played", "queued"]
    assert len(notifications) == 1


def test_delayed_queue_visibility_does_not_mark_request_played(ext):
    add(ext, "a")
    ext.user.items = []
    main.snapshot(force=True)
    assert main.store.pending()[0].status == "queued"
    ext.user.pb["item"] = item("a")
    main.snapshot(force=True)
    assert main.store.session.requests[0].status == "played"


def test_legacy_queue_migration_does_not_resend_pushed_or_repeat_after_restart(ext):
    s = main.store.session
    s.vqueue = ["a" * 22, "b" * 22, "c" * 22]
    s.vpushed = "a" * 22
    main.snapshot(force=True)
    assert ext.user.calls == [("queue", "b" * 22), ("queue", "c" * 22)]
    reloaded = PartyStore(main.store.path)
    SpotifyPlayer(ext.user, FakeCatalog(), reloaded).snapshot()
    assert len(ext.user.calls) == 2
    assert not reloaded.session.vqueue and not reloaded.session.vpushed


def test_legacy_ambiguous_transfer_is_saved_and_visible(ext, monkeypatch):
    def fail(tid):
        ext.user.calls.append(("queue", tid))
        raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(ext.user, "queue", fail)
    main.store.session.vqueue = ["a" * 22]
    main.snapshot(force=True)
    reloaded = PartyStore(main.store.path)
    SpotifyPlayer(ext.user, FakeCatalog(), reloaded).snapshot()
    assert ext.user.calls == [("queue", "a" * 22)]
    assert ext.get("/api/admin/state").json()["spotify_transfer_issues"] == ["a" * 22]


def test_legacy_waits_for_device(ext):
    main.store.session.vqueue = ["a" * 22]
    ext.user.pb = None
    main.snapshot(force=True)
    assert not ext.user.calls and main.store.session.vqueue == ["a" * 22]


def test_start_requires_spotify_account(ext, monkeypatch):
    monkeypatch.setattr(ext.user.__class__, "connected", False)
    assert ext.post("/api/admin/start", json={"source": "spotify", "mode": "next"}).status_code == 409


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_empty_http_error_is_not_a_success(tmp_path, monkeypatch, status):
    user = SpotifyUser("id", "secret", tmp_path / "token.json", "https://example.com/callback")
    monkeypatch.setattr(user, "_access", lambda: "fake")
    monkeypatch.setattr(user, "_http", httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status))))
    with pytest.raises(SpotifyError):
        user.queue("a" * 22)


def test_recent_send_is_duplicate_until_spotify_catches_up(ext):
    assert add(ext, "a").status_code == 200
    ext.user.items = []
    assert add(ext, "a").status_code == 409
    assert add(ext, "a", force=True).status_code == 200
    assert len(ext.user.calls) == 2


def test_queue_read_failure_returns_actionable_error(ext, monkeypatch):
    def fail():
        raise SpotifyError("Aucun appareil Spotify actif : lance une musique sur ton téléphone")
    monkeypatch.setattr(ext.user, "get_queue", fail)
    r = add(ext, "a")
    assert r.status_code == 502 and "appareil Spotify actif" in r.json()["detail"]
    assert ext.user.calls == []
