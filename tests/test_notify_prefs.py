"""Réglages natifs › Notifications : chaque type de notification se choisit séparément (invité, hôte, compte)."""
from fastapi.testclient import TestClient

from app import main
from app.accounts import AccountError
from app.party import Request
from tests.test_extras import SUB, guest_client, push  # noqa: F401 (fixture)
from tests.test_features import admin, snap  # noqa: F401 (fixture)


def play(guest_id: str):
    """Le titre demandé par guest_id démarre."""
    main.store.session.requests.append(Request(f"r-{guest_id}", "z" * 22, "Mon titre", "Moi", "", guest_id, "Léa", 0))
    main._snap["current"] = None
    data = snap()
    data["current"] = {"pos": 5, "track_id": "z" * 22, "title": "Mon titre", "artist": "Moi", "art": ""}
    main.track_changed(data, main.store.reconcile({t["track_id"] for t in data["upcoming"] if t["track_id"]}))


def test_guest_prefs_default_and_are_saved_per_kind(admin):  # noqa: F811
    guest = guest_client("guest-pref-1")
    r = guest.get("/api/notify?guest_id=guest-pref-1").json()
    assert r == {"prefs": {"track": True, "feedback": True, "games": False}, "subscribed": False}

    assert guest.post("/api/notify", json={"guest_id": "guest-pref-1", "kind": "games", "on": True}).json()["prefs"]["games"]
    assert guest.post("/api/notify", json={"guest_id": "guest-pref-1", "kind": "nope", "on": True}).status_code == 400
    guest.post("/api/push/subscribe", json={"guest_id": "guest-pref-1", "subscription": SUB})
    assert guest.get("/api/notify?guest_id=guest-pref-1").json() == {
        "prefs": {"track": True, "feedback": True, "games": True}, "subscribed": True}
    main.store.remove_push(SUB["endpoint"])


def test_guest_prefs_require_the_party_code(admin):  # noqa: F811
    assert TestClient(main.app).get("/api/notify?guest_id=guest-pref-2").status_code == 401


def test_track_notification_respects_the_guest_choice(admin, push):  # noqa: F811
    guest = guest_client("guest-pref-3")
    guest.post("/api/push/subscribe", json={"guest_id": "guest-pref-3", "subscription": SUB})
    guest.post("/api/notify", json={"guest_id": "guest-pref-3", "kind": "track", "on": False})
    play("guest-pref-3")
    assert not any(p["tag"] == "now-playing" for _, p in push.sent)
    main.store.remove_push(SUB["endpoint"])


def test_guest_prefs_survive_a_new_party(admin):  # noqa: F811
    guest_client("guest-pref-4").post("/api/notify", json={"guest_id": "guest-pref-4", "kind": "feedback", "on": False})
    main.store.start("RINCON_X", "Salon", "next")
    assert main.store.session.guest_notify["guest-pref-4"]["feedback"] is False


def test_subscribed_guests_who_want_it_hear_about_new_games(admin, push):  # noqa: F811
    fan = guest_client("guest-pref-5")
    fan.post("/api/push/subscribe", json={"guest_id": "guest-pref-5", "subscription": SUB})
    fan.post("/api/notify", json={"guest_id": "guest-pref-5", "kind": "games", "on": True})
    main._game_creations.clear()
    # Celui qui lance la partie n'est pas prévenu de sa propre partie.
    TestClient(main.app).post("/api/games", json={"guest_id": "guest-pref-5", "name": "Léa", "type": "whoof"})
    assert not any(p["tag"].startswith("game-") for _, p in push.sent)
    g = TestClient(main.app).post("/api/games", json={"guest_id": "guest-pref-6", "name": "Tom", "type": "casino"}).json()
    assert ([SUB], {"title": "🎮 Casino", "body": f"Tom lance une partie · code {g['code']}",
                    "url": f"/?game={g['code']}", "tag": f"game-{g['code']}"}) in [
        (subs, p) for subs, p in push.sent]
    main.store.remove_push(SUB["endpoint"])


def test_host_reads_and_sets_feedback_notifications_separately(admin, push):  # noqa: F811
    assert admin.get("/api/admin/notify").json() == {"admin_notify": {"messages": True, "games": False, "feedback": True}}
    admin.post("/api/admin/push/subscribe", json={"subscription": SUB})
    admin.post("/api/admin/notify", json={"kind": "feedback", "on": False})
    guest_client("guest-pref-7", "Zoé").post("/api/feedback", json={"guest_id": "guest-pref-7", "name": "Zoé", "kind": "idea", "text": "Un mode karaoké"})
    assert not any(p.get("tag") == "feedback" for _, p in push.sent)
    admin.post("/api/admin/notify", json={"kind": "feedback", "on": True})
    main.store.remove_push(SUB["endpoint"])


def test_admin_notify_needs_the_host():
    assert TestClient(main.app).get("/api/admin/notify").status_code == 401


class FakeAccounts:
    def __init__(self):
        self.row = {"user_id": "u1", "push_enabled": True, "quiet_start": None, "quiet_end": None, "new_event": "all",
                    "event_changed": True, "poll_new": True, "date_fixed": True, "poll_nudge": True, "waitlist": True,
                    "reminders": ["1d"], "chat": "mentions", "rsvp_mine": True, "proposals": False}
        self.patches = []

    def notification_prefs(self, token):
        if token != "ok":
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        return {"prefs": self.row, "approver": True}

    def update_notification_prefs(self, token, patch):
        self.notification_prefs(token)
        self.patches.append(patch)
        self.row = {**self.row, **patch}
        return {"prefs": self.row, "approver": True}


def test_account_notification_prefs_go_through_the_member_session(monkeypatch):
    fake = FakeAccounts()
    monkeypatch.setattr(main, "accounts", fake)
    client = TestClient(main.app)
    assert client.post("/api/account/notifications", json={"token": "ok"}).json()["prefs"]["chat"] == "mentions"
    assert client.post("/api/account/notifications", json={"token": "bad"}).status_code == 401

    r = client.post("/api/account/notifications/update", json={"token": "ok", "patch": {"chat": "all", "reminders": ["7d", "2h"]}})
    assert r.json()["prefs"]["chat"] == "all" and fake.patches == [{"chat": "all", "reminders": ["7d", "2h"]}]
    # Seuls les champs connus, aux valeurs connues : jamais user_id ni une valeur inventée.
    for patch in ({"user_id": "u2"}, {"chat": "loud"}, {"reminders": ["3w"]}, {"quiet_start": "25:00"}, {}):
        assert client.post("/api/account/notifications/update", json={"token": "ok", "patch": patch}).status_code in (400, 422)
    assert client.post("/api/account/notifications/update", json={"token": "ok", "patch": {"quiet_start": "23:00", "quiet_end": "08:00"}}).status_code == 200
    assert len(fake.patches) == 2


def test_accounts_reads_and_patches_only_the_members_own_row():
    import httpx
    from app import accounts as accounts_mod
    seen = []

    def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, str(request.url.query, "ascii"), request.content))
        assert request.headers["authorization"] == "Bearer tok"
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-9"})
        if request.url.path == "/rest/v1/rpc/my_permissions":
            return httpx.Response(200, json=["events.approve"])
        if request.url.path == "/rest/v1/notification_prefs" and request.method == "GET":
            return httpx.Response(200, json=[{"user_id": "u-9", "chat": "all"}])
        if request.url.path == "/rest/v1/notification_prefs" and request.method == "PATCH":
            assert request.headers["prefer"] == "return=minimal"
            return httpx.Response(204)
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    assert acc.notification_prefs("tok") == {"prefs": {"user_id": "u-9", "chat": "all"}, "approver": True}
    acc.update_notification_prefs("tok", {"chat": "none"})
    patch = next(s for s in seen if s[0] == "PATCH")
    assert patch[2] == "user_id=eq.u-9" and patch[3] == b'{"chat":"none"}'
