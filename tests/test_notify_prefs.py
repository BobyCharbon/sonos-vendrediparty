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
    assert r == {"prefs": {"track": False, "feedback": True, "games": False}, "subscribed": False}

    assert guest.post("/api/notify", json={"guest_id": "guest-pref-1", "kind": "games", "on": True}).json()["prefs"]["games"]
    assert guest.post("/api/notify", json={"guest_id": "guest-pref-1", "kind": "nope", "on": True}).status_code == 400
    # Réglages natifs : l'abonnement de l'iPhone ne touche pas aux types choisis.
    guest.post("/api/push/subscribe", json={"guest_id": "guest-pref-1", "subscription": SUB, "keep_prefs": True})
    assert guest.get("/api/notify?guest_id=guest-pref-1").json() == {
        "prefs": {"track": False, "feedback": True, "games": True}, "subscribed": True}
    # Bouton « Préviens-moi quand mon titre passe » : il allume ce type.
    guest.post("/api/push/subscribe", json={"guest_id": "guest-pref-1", "subscription": SUB})
    assert guest.get("/api/notify?guest_id=guest-pref-1").json()["prefs"]["track"] is True
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
    guest_client("guest-pref-7", "Zoé").post("/api/feedback", json={"guest_id": "guest-pref-7", "name": "Zoé", "kind": "idea", "text": "Un mode karaoké avec les paroles à l'écran"})
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


def test_native_iphone_is_registered_for_event_notifications_with_the_member_session():
    import httpx
    from app import accounts as accounts_mod
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.url.path, request.content))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-9"})
        return httpx.Response(204)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    acc.register_push("tok", "ab" * 32, True)
    acc.register_push("tok", "ab" * 32, False)
    assert calls[-2] == ("/rest/v1/rpc/register_device_push_token", b'{"device_token":"apns:' + b"ab" * 32 + b'","device_platform":"ios"}')
    assert calls[-1] == ("/rest/v1/rpc/unregister_device_push_token", b'{"device_token":"apns:' + b"ab" * 32 + b'"}')


def test_push_register_api_checks_the_device_token(monkeypatch):
    seen = []

    class Fake:
        def register_push(self, token, device, on):
            seen.append((device, on))

    monkeypatch.setattr(main, "accounts", Fake())
    c = TestClient(main.app)
    assert c.post("/api/account/push", json={"token": "tok", "device": "ab" * 32, "on": True}).json() == {"ok": True}
    assert c.post("/api/account/push", json={"token": "tok", "device": "zz", "on": True}).status_code == 422
    assert seen == [("ab" * 32, True)]


NATIVE = {"endpoint": "apns:" + "ab" * 32,
          "apns": {"token": "ab" * 32, "environment": "production", "topic": "ch.bobycharbon.party.beta"}}


def test_iphone_app_subscribes_as_guest_and_as_host(admin):  # noqa: F811
    guest = guest_client("guest-native-1")
    assert guest.post("/api/push/subscribe", json={"guest_id": "guest-native-1", "subscription": NATIVE, "keep_prefs": True}).status_code == 200
    assert main.store.session.push["guest-native-1"] == [NATIVE]
    assert admin.post("/api/admin/push/subscribe", json={"subscription": NATIVE}).status_code == 200
    assert main.store.session.admin_push[-1] == NATIVE
    main.store.remove_push(NATIVE["endpoint"])


def test_host_in_the_app_hears_when_a_track_added_as_host_plays(admin, push):  # noqa: F811
    native = {"X-Party-Native": "ios"}
    assert admin.post("/api/push/subscribe", headers=native,
                      json={"guest_id": "guest-host-app", "subscription": NATIVE}).status_code == 200
    assert main.store.session.push[main.HOST_ID] == [NATIVE]
    assert main.store.session.guest_notify[main.HOST_ID]["track"] is True
    play(main.HOST_ID)
    assert any(p.get("tag") == "now-playing" and subs == [NATIVE] for subs, p in push.sent)
    # Coupé dans les Réglages de l'app : coupé aussi pour ses titres d'hôte.
    admin.post("/api/notify", headers=native, json={"guest_id": "guest-host-app", "kind": "track", "on": False})
    assert main.store.session.guest_notify[main.HOST_ID]["track"] is False
    main.store.remove_push(NATIVE["endpoint"])
    assert main.HOST_ID not in main.store.session.push


def pause_supabase(state: dict, seen: list):
    """Supabase de test : la pause est calculée par la base (set_notification_pause), relue ensuite."""
    import httpx

    def handler(request: httpx.Request):
        seen.append((request.method, request.url.path, request.content))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-9"})
        if request.url.path == "/rest/v1/rpc/set_notification_pause":
            state["muted_until"] = state.pop("next", None)
            return httpx.Response(200, json={"user_id": "u-9", **state})
        if request.url.path == "/rest/v1/notification_prefs":
            return httpx.Response(200, json=[{"user_id": "u-9", **state}])
        if request.url.path == "/rest/v1/rpc/my_permissions":
            return httpx.Response(200, json=[])
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_the_moon_is_set_by_the_base_and_remembered_by_party():
    from datetime import datetime, timedelta, timezone
    from app import accounts as accounts_mod
    soon = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    state, seen = {"muted_until": None, "chats_muted_until": None, "next": soon}, []
    acc = accounts_mod.Accounts(b"secret", pause_supabase(state, seen))
    gid = acc.gid("u-9")
    assert not acc.paused(gid)
    r = acc.set_notification_pause("tok", "all", "1h")
    assert r["prefs"]["muted_until"] == soon and acc.paused(gid)
    assert ("POST", "/rest/v1/rpc/set_notification_pause", b'{"what":"all","span":"1h"}') in seen
    acc.set_notification_pause("tok", "all", "off")  # « Réactiver »
    assert not acc.paused(gid)
    # Pause posée depuis le web : Party la lit à la liaison du compte. Une pause passée ne compte plus.
    state["muted_until"] = soon
    acc.link("tok")
    assert acc.paused(gid)
    state["muted_until"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    acc.link("tok")
    assert not acc.paused(gid)
    assert accounts_mod.pause_end("pas une date") == 0 and accounts_mod.pause_end(None) == 0


def test_party_notifications_arrive_silently_during_the_moon_admin_included(admin, push, monkeypatch):  # noqa: F811
    guest = guest_client("guest-moon-1")
    guest.post("/api/push/subscribe", json={"guest_id": "guest-moon-1", "subscription": SUB})
    monkeypatch.setattr(main.accounts, "pauses", {"guest-moon-1": 9e12})
    play("guest-moon-1")
    track = [p for _, p in push.sent if p.get("tag") == "now-playing"]
    assert track and track[-1]["silent"] is True  # lune : livrée, mais sans son ni vibration
    # Hôte : la lune d'un compte admin rend aussi ses notifications silencieuses (« le mode nuit coupe tout »).
    admin.post("/api/admin/push/subscribe", json={"subscription": NATIVE})
    monkeypatch.setattr(main.accounts, "by_gid", {"acct-admin": {"admin": True}})
    main.accounts.pauses["acct-admin"] = 9e12
    guest_client("guest-moon-2", "Zoé").post("/api/message", json={"guest_id": "guest-moon-2", "guest_name": "Zoé", "text": "Une lune ?"})
    assert [p for _, p in push.sent if p.get("tag") == "message"][-1]["silent"] is True
    monkeypatch.setattr(main.accounts, "pauses", {})
    push.sent.clear()
    play("guest-moon-1")
    assert [p for _, p in push.sent if p.get("tag") == "now-playing"][-1].get("silent") is None  # pause finie : avec son
    main.store.remove_push(SUB["endpoint"])
    main.store.remove_push(NATIVE["endpoint"])


def test_apns_payload_is_silent_during_a_pause():
    import httpx
    from app import apns as apns_mod
    sent = []

    def handler(request: httpx.Request):
        sent.append(request)
        return httpx.Response(200)

    a = apns_mod.Apns.__new__(apns_mod.Apns)
    a.client = httpx.Client(transport=httpx.MockTransport(handler))
    a._provider_token = lambda: "jwt"
    a.send(NATIVE, {"title": "T", "body": "B", "silent": True})
    a.send(NATIVE, {"title": "T", "body": "B"})
    import json as _json
    quiet, loud = (_json.loads(r.content)["aps"] for r in sent)
    assert quiet == {"alert": {"title": "T", "body": "B"}, "interruption-level": "passive"} and sent[0].headers["apns-priority"] == "5"
    assert loud["sound"] == "default" and sent[1].headers["apns-priority"] == "10"


def test_pause_api_accepts_only_known_choices(monkeypatch):
    seen = []

    class Fake:
        def set_notification_pause(self, token, what, span):
            if token != "ok":
                raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
            seen.append((what, span))
            return {"prefs": {"muted_until": None}, "approver": False}

    monkeypatch.setattr(main, "accounts", Fake())
    c = TestClient(main.app)
    for what, span in (("all", "1h"), ("all", "morning"), ("chats", "30m"), ("chats", "off")):
        assert c.post("/api/account/notifications/pause", json={"token": "ok", "what": what, "span": span}).status_code == 200
    assert c.post("/api/account/notifications/pause", json={"token": "ok", "what": "event_chats", "span": "2h"}).status_code == 200
    seen.pop()
    for what, span in (("all", "12h"), ("events", "1h")):
        assert c.post("/api/account/notifications/pause", json={"token": "ok", "what": what, "span": span}).status_code == 422
    assert c.post("/api/account/notifications/pause", json={"token": "bad", "what": "all", "span": "1h"}).status_code == 401
    assert seen == [("all", "1h"), ("all", "morning"), ("chats", "30m"), ("chats", "off")]


def test_every_notification_type_has_its_own_switch_through_party(monkeypatch):
    """Chaque type qu'on peut recevoir se coupe (Réglages natifs › Notifications) : les nouveaux réglages passent."""
    fake = FakeAccounts()
    monkeypatch.setattr(main, "accounts", fake)
    client = TestClient(main.app)
    for key in ("announcements", "rsvp_set", "invites", "proposal_result", "link_join", "group_messages", "group_invites", "group_joins"):
        r = client.post("/api/account/notifications/update", json={"token": "ok", "patch": {key: False}})
        assert r.status_code == 200 and r.json()["prefs"][key] is False, key
        assert client.post("/api/account/notifications/update", json={"token": "ok", "patch": {key: "non"}}).status_code == 422
