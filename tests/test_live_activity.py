"""Live Activity poussée par le serveur : ce qui part vers l'iPhone selon la file (app fermée)."""
from app.live_activity import PLAYING_STAY, START_GRACE, SWIFT_EPOCH, Slot, plan, starts

NOW = 1_800_000_000.0


def slot(rid="r1", ahead=2, eta=300.0, owner="guest-1", added=NOW - 60):
    return Slot(rid, owner, "t" + rid, "Titre " + rid, "Artiste", added, ahead, eta)


def test_first_update_carries_place_countdown_and_stale_date():
    [step] = plan([slot()], "now-playing", {"r1": {"track_id": "tr1"}}, False, NOW)
    state = step.payload["content-state"]
    assert step.event == "update" and step.priority == 10
    assert state == {"arrival": NOW + 300 - SWIFT_EPOCH, "playing": False, "paused": False, "remaining": 300.0, "ahead": 2}
    assert step.payload["stale-date"] == int(NOW + 300)


def test_same_view_is_not_sent_twice_but_a_new_place_is():
    tracked = {"r1": {"track_id": "tr1"}}
    [first] = plan([slot()], None, tracked, False, NOW)
    tracked["r1"]["key"] = first.key
    assert plan([slot(eta=290.0)], None, tracked, False, NOW + 10) == []  # même heure à 20 s près
    [moved] = plan([slot(ahead=1, eta=200.0)], None, tracked, False, NOW + 10)
    assert moved.payload["content-state"]["ahead"] == 1 and moved.priority == 10


def test_clock_drift_only_is_sent_with_low_priority():
    tracked = {"r1": {"track_id": "tr1"}}
    tracked["r1"]["key"] = plan([slot()], None, tracked, False, NOW)[0].key
    [drift] = plan([slot(eta=360.0)], None, tracked, False, NOW)
    assert drift.priority == 5


def test_pause_freezes_the_remaining_time_and_has_no_stale_date():
    tracked = {"r1": {"track_id": "tr1", "remaining": 120.0}}
    [step] = plan([slot(eta=None)], None, tracked, True, NOW)
    assert step.payload["content-state"]["paused"] is True and step.payload["content-state"]["remaining"] == 120.0
    assert "stale-date" not in step.payload


def test_my_track_playing_ends_the_activity_in_green_after_a_while():
    tracked = {"r1": {"track_id": "tr1", "key": ("wait", 0, False, 1)}}
    [step] = plan([], "tr1", tracked, False, NOW)
    assert step.event == "end" and step.payload["content-state"]["playing"] is True
    assert step.payload["dismissal-date"] == int(NOW + PLAYING_STAY)
    tracked["r1"]["key"] = step.key
    assert plan([], "tr1", tracked, False, NOW + 5) == []


def test_removed_track_dismisses_the_activity_right_away():
    tracked = {"r1": {"track_id": "tr1", "key": ("wait", 3, False, 1)}}
    [step] = plan([], "other", tracked, False, NOW)
    assert step.event == "end" and step.payload["dismissal-date"] == int(NOW)
    tracked["r1"]["key"] = step.key
    assert plan([], "other", tracked, False, NOW) == []


def test_push_start_only_for_the_next_track_of_a_guest_with_a_start_token():
    slots = [slot("a", ahead=0, eta=100.0), slot("b", ahead=1, eta=300.0), slot("c", owner="guest-2", ahead=2)]
    [step] = starts(slots, {"guest-1"}, {}, set(), False, NOW)
    assert step.rid == "a" and step.event == "start"
    assert step.payload["attributes-type"] == "TrackActivityAttributes"
    assert step.payload["attributes"]["requestID"] == "a" and step.payload["alert"]["title"]


def test_no_push_start_when_the_app_already_follows_it_or_just_added_it():
    s = slot("a", ahead=0)
    assert starts([s], {"guest-1"}, {"a": {}}, set(), False, NOW) == []
    assert starts([s], {"guest-1"}, {}, {"a"}, False, NOW) == []
    assert starts([slot("a", added=NOW - 1)], {"guest-1"}, {}, set(), False, NOW) == []
    assert START_GRACE > 1


# --- Intégration : enregistrement par l'app, envoi par la boucle de suivi de la file ---
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.party import Request  # noqa: E402
from tests.test_extras import guest_client  # noqa: E402
from tests.test_features import admin, snap  # noqa: E402,F401

TOKEN = "cd" * 32
BETA = "ch.bobycharbon.party.beta"


class FakeLivePush:
    apns = object()

    def __init__(self):
        self.sent = []

    def send_live_activity(self, target, event, aps, priority, on_gone=lambda: None):
        self.sent.append((target["token"], event, aps, priority))

    def send(self, subs, payload, on_gone=None):
        pass


@pytest.fixture
def live(admin, monkeypatch):  # noqa: F811
    fake = FakeLivePush()
    monkeypatch.setattr(main, "push", fake)
    main._live.clear()
    main.store.session.activities.clear()
    main.store.session.activity_start_tokens.clear()
    main.store.session.activities_started.clear()
    # La file de snap() : « Un » (a…), « Deux », « Trois » (b…) ; « Trois » est demandé par l'invité.
    main.store.session.requests.append(Request("rq-trois", "b" * 22, "Trois", "A", "", "guest-live-1", "Léa", 0))
    return fake


def test_app_registers_its_activity_and_the_server_keeps_it_up_to_date(live):
    guest = guest_client("guest-live-1")
    body = {"guest_id": "guest-live-1", "request_id": "rq-trois", "token": TOKEN, "topic": BETA}
    assert guest.post("/api/activity", json=body).status_code == 200
    data = snap()
    main.refresh_live_activities(data, now=NOW)
    [(token, event, aps, _)] = live.sent
    assert token == TOKEN and event == "update" and aps["content-state"]["ahead"] == 2
    main.refresh_live_activities(data, now=NOW + 1)
    assert len(live.sent) == 1  # rien de nouveau : rien d'envoyé


def test_someone_elses_track_or_an_unknown_app_is_refused(live):
    other = guest_client("guest-live-2")
    body = {"guest_id": "guest-live-2", "request_id": "rq-trois", "token": TOKEN, "topic": BETA}
    assert other.post("/api/activity", json=body).status_code == 404
    mine = guest_client("guest-live-1")
    assert mine.post("/api/activity", json={**body, "guest_id": "guest-live-1", "topic": "com.evil"}).status_code == 400
    assert mine.post("/api/activity", json={**body, "guest_id": "guest-live-1", "token": "xyz"}).status_code == 422


def test_my_track_starting_turns_the_activity_green_and_stops_following_it(live):
    guest_client("guest-live-1").post("/api/activity", json={"guest_id": "guest-live-1", "request_id": "rq-trois", "token": TOKEN, "topic": BETA})
    data = snap()
    data["current"] = {"pos": 7, "track_id": "b" * 22, "title": "Trois", "artist": "A", "art": ""}
    data["upcoming"] = data["upcoming"][:2]
    main.refresh_live_activities(data, now=NOW)
    [(_, event, aps, _)] = live.sent
    assert event == "end" and aps["content-state"]["playing"] is True
    assert "rq-trois" not in main.store.session.activities


def test_a_track_added_app_closed_starts_its_activity_by_push_once(live):
    guest = guest_client("guest-live-1")
    assert guest.post("/api/activity/start", json={"guest_id": "guest-live-1", "token": TOKEN, "topic": BETA}).status_code == 200
    main.refresh_live_activities(snap(), now=NOW)
    [(token, event, aps, _)] = live.sent
    assert event == "start" and aps["attributes"]["requestID"] == "rq-trois"
    main.refresh_live_activities(snap(), now=NOW + 5)
    assert len(live.sent) == 1
    # Réglage « Décompte dans la Dynamic Island » coupé : plus de démarrage par push.
    guest.post("/api/activity/start", json={"guest_id": "guest-live-1", "token": ""})
    assert main.store.session.activity_start_tokens == {}
