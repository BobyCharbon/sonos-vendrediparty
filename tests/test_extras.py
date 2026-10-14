import pytest
from fastapi.testclient import TestClient

from app import main
from app.party import Request
from app.push import valid_subscription
from app.sonos import seconds
from tests.test_features import admin, snap  # noqa: F401 (fixture)

SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "k", "auth": "a"}}


class FakePush:
    public_key = "KEY"

    def __init__(self):
        self.sent = []

    def send(self, subs, payload, on_gone=None):
        self.sent.append((subs, payload))


@pytest.fixture
def push(monkeypatch):
    fake = FakePush()
    monkeypatch.setattr(main, "push", fake)
    return fake


def guest_client(guest_id="guest-push-1", name="Léa"):
    guest = TestClient(main.app)
    guest.post("/api/join", json={"pin": main.store.session.guest_pin})
    guest.post("/api/hello", json={"guest_id": guest_id, "guest_name": name})
    return guest


def test_seconds():
    assert seconds("0:03:45") == 225
    assert seconds("NOT_IMPLEMENTED") is None
    assert seconds("") is None


def test_subscription_only_to_known_push_services():
    assert valid_subscription(SUB)
    assert valid_subscription({**SUB, "endpoint": "https://web.push.apple.com/xyz"})
    assert not valid_subscription({**SUB, "endpoint": "http://fcm.googleapis.com/x"})
    assert not valid_subscription({**SUB, "endpoint": "https://192.168.50.1/x"})
    assert not valid_subscription({**SUB, "endpoint": "https://evil-fcm.googleapis.com.example/x"})
    assert not valid_subscription({"endpoint": SUB["endpoint"]})


def test_eta_counts_remaining_time_and_durations(admin, monkeypatch):  # noqa: F811
    s = snap()
    s["now"].update(position="0:01:00", duration="0:03:00")
    s["upcoming"][0]["duration"] = 200
    s["upcoming"][1]["duration"] = None  # inconnu : la suite n'est plus estimable
    assert main.etas(s) == [120, 320, None]
    s["state"] = "PAUSED_PLAYBACK"
    assert main.etas(s) == [None, None, None]


def test_eta_falls_back_on_spotify_duration(admin):  # noqa: F811
    s = snap()
    s["now"].update(position="0:00:00", duration="0:01:00")
    main.store.session.requests.append(Request("r1", "a" * 22, "Un", "A", "", "g", "G", 0, duration_ms=90_000))
    assert main.etas(s)[:2] == [60, 150]


def test_guest_subscribes_and_is_notified_when_track_starts(admin, push):  # noqa: F811
    guest = guest_client()
    assert guest.post("/api/push/subscribe", json={"guest_id": "guest-push-1", "subscription": {**SUB, "endpoint": "https://x.example/"}}).status_code == 400
    assert guest.post("/api/push/subscribe", json={"guest_id": "guest-push-1", "subscription": SUB}).status_code == 200

    main.store.session.requests.append(Request("r2", "z" * 22, "Mon titre", "Moi", "", "guest-push-1", "Léa", 0))
    main._snap["current"] = None
    data = snap()
    data["current"] = {"pos": 5, "track_id": "z" * 22, "title": "Mon titre", "artist": "Moi", "art": ""}
    done = main.store.reconcile({t["track_id"] for t in data["upcoming"] if t["track_id"]})
    main.track_changed(data, done)

    assert push.sent and push.sent[-1][0] == [SUB]
    assert push.sent[-1][1]["title"] == "🎶 Ton titre passe !"
    assert main.store.session.played[-1]["title"] == "Mon titre"
    # Même titre au tour suivant : ni nouvelle notification, ni doublon dans l'historique.
    count = len(push.sent)
    main.track_changed(data, main.store.reconcile(set()))
    assert len(push.sent) == count and main.store.session.played[-1]["title"] == "Mon titre"

    guest.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]})
    assert "guest-push-1" not in main.store.session.push


def test_admin_notified_of_new_message(admin, push):  # noqa: F811
    assert admin.post("/api/admin/push/subscribe", json={"subscription": SUB}).status_code == 200
    guest = guest_client("guest-push-2", "Tom")
    guest.post("/api/message", json={"guest_id": "guest-push-2", "guest_name": "Tom", "text": "Coucou"})
    assert push.sent[-1] == ([main.store.session.admin_push[0]], {"title": "💬 Tom", "body": "Coucou", "url": "/admin#settings", "tag": "message"})
    main.store.remove_push(SUB["endpoint"])


def test_admin_can_undo_a_removal(admin):  # noqa: F811
    res = admin.post("/api/admin/queue", json={"pos": 7, "key": "b" * 22, "action": "remove"}).json()
    assert res["undo"]
    admin.fake.calls.clear()
    assert admin.post("/api/admin/undo", json={"token": res["undo"]}).status_code == 200
    assert admin.fake.calls == [("add", "b" * 22, 7)]
    # Un jeton ne sert qu'une fois.
    assert admin.post("/api/admin/undo", json={"token": res["undo"]}).status_code == 404


def test_removal_of_non_spotify_track_is_not_undoable(admin):  # noqa: F811
    res = admin.post("/api/admin/queue", json={"pos": 6, "key": "Deux|A", "action": "remove"}).json()
    assert res["undo"] is None


def test_launch_playlist_keeps_pending_requests(admin, monkeypatch):  # noqa: F811
    launched = []
    admin.fake.launch_playlist = lambda uid, pid, keep: launched.append((pid, keep))
    main.store.session.requests = [
        Request("k1", "b" * 22, "Trois", "A", "", "g1", "G", 0),
        Request("k2", "q" * 22, "Plus dans la file", "A", "", "g1", "G", 0),
    ]
    assert admin.post("/api/admin/playlist", json={"id": "sq:SQ:2"}).status_code == 200
    assert launched == [("sq:SQ:2", [("b" * 22, "Trois")])]
    status = {r.id: r.status for r in main.store.session.requests}
    assert status == {"k1": "queued", "k2": "removed"}


def test_guest_state_has_eta_track_id_and_history(admin):  # noqa: F811
    main.store.session.played = [
        {"track_id": "p" * 22, "title": "Avant", "artist": "A", "art": "", "by": None, "at": 0},
        {"track_id": "c" * 22, "title": "En cours", "artist": "A", "art": "", "by": None, "at": 1},
    ]
    guest = guest_client("guest-hist-1", "Zoé")
    s = guest.get("/api/state?guest_id=guest-hist-1").json()
    assert s["now"]["track_id"] == "c" * 22
    assert "eta" in s["upcoming"][0] and s["upcoming"][0]["track_id"] == "a" * 22
    assert [p["title"] for p in s["played"]] == ["Avant"]  # sans le titre en cours
