import pytest
from fastapi.testclient import TestClient

from app import main
from app.security import Limiter


class FakeSonos:
    def __init__(self):
        self.calls = []

    def move(self, uid, a, b):
        self.calls.append(("move", a, b))

    def remove_at(self, uid, pos):
        self.calls.append(("remove", pos))

    def play_at(self, uid, pos):
        self.calls.append(("play", pos))

    def play(self, uid):
        self.calls.append(("resume",))

    def pause(self, uid):
        self.calls.append(("pause",))

    def set_volume(self, uid, volume):
        self.calls.append(("volume", volume))

    def add_spotify_track(self, uid, track_id, title, pos):
        self.calls.append(("add", track_id, pos))


def snap():
    track = lambda pos, tid, title: {"pos": pos, "track_id": tid, "title": title, "artist": "A", "art": ""}
    return {
        "coordinator_ip": "127.0.0.1", "room": "Salon", "state": "PLAYING", "from_queue": True, "current_pos": 4,
        "current": track(4, "c" * 22, "En cours"),
        "upcoming": [track(5, "a" * 22, "Un"), track(6, None, "Deux"), track(7, "b" * 22, "Trois")],
        "now": {"title": "En cours", "artist": "A", "art": "", "position": "", "duration": ""},
    }


@pytest.fixture
def admin(monkeypatch):
    fake = FakeSonos()
    monkeypatch.setattr(main, "sonos", fake)
    monkeypatch.setattr(main, "snapshot", lambda force=False: snap())
    monkeypatch.setattr(main, "guest_limiter", Limiter(per_ip=5, ip_lock=900, global_max=30, global_window=600, global_lock=600))
    main.store.start("RINCON_X", "Salon", "next")
    client = TestClient(main.app)
    assert client.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    client.fake = fake
    return client


def test_admin_moves_any_track(admin):
    queue = admin.get("/api/admin/state").json()["queue"]
    assert [t["pos"] for t in queue] == [5, 6, 7]
    deux = queue[1]
    assert deux["key"] == "Deux|A"  # titre hors Spotify : identifié par titre + artiste

    admin.post("/api/admin/queue", json={"pos": 7, "key": queue[2]["key"], "action": "next"})
    admin.post("/api/admin/queue", json={"pos": 6, "key": deux["key"], "action": "down"})
    admin.post("/api/admin/queue", json={"pos": 6, "key": deux["key"], "action": "remove"})
    assert admin.fake.calls == [("move", 7, 5), ("move", 6, 7), ("remove", 6)]


def test_queue_action_refused_if_queue_changed(admin):
    r = admin.post("/api/admin/queue", json={"pos": 5, "key": "autre-titre", "action": "remove"})
    assert r.status_code == 409
    assert admin.fake.calls == []


def test_guest_appears_on_hello_and_sends_message(admin):
    guest = TestClient(main.app)
    guest.post("/api/join", json={"pin": main.store.session.guest_pin})
    assert guest.post("/api/hello", json={"guest_id": "guest-1234", "guest_name": "Léa"}).status_code == 200

    names = [g["name"] for g in admin.get("/api/admin/state").json()["guests"]]
    assert "Léa" in names

    r = guest.post("/api/message", json={"guest_id": "guest-1234", "guest_name": "Léa", "text": "Un peu de Daft Punk ?"})
    assert r.status_code == 200
    # Anti-spam : pas deux messages d'affilée.
    r = guest.post("/api/message", json={"guest_id": "guest-1234", "guest_name": "Léa", "text": "Encore !"})
    assert r.status_code == 429

    msgs = admin.get("/api/admin/state").json()["messages"]
    assert msgs[0]["text"] == "Un peu de Daft Punk ?" and not msgs[0]["read"]
    msgs = admin.post("/api/admin/messages", json={"ids": None, "action": "read"}).json()["messages"]
    assert all(m["read"] for m in msgs)


def test_admin_replies_and_guest_sees_it(admin):
    guest = TestClient(main.app)
    guest.post("/api/join", json={"pin": main.store.session.guest_pin})
    guest.post("/api/message", json={"guest_id": "guest-5678", "guest_name": "Tom", "text": "Tu passes du Queen ?"})
    msg = admin.get("/api/admin/state").json()["messages"][0]

    admin.post("/api/admin/messages/reply", json={"id": msg["id"], "text": "Juste après ce titre 😉"})
    mine = guest.get("/api/state?guest_id=guest-5678").json()["messages"]
    assert mine[0]["reply"] == "Juste après ce titre 😉"
    # Les autres invités ne voient pas cette conversation.
    assert guest.get("/api/state?guest_id=guest-9999").json()["messages"] == []


def test_pause_and_volume(admin):
    admin.post("/api/admin/playback", json={"action": "pause"})
    admin.post("/api/admin/playback", json={"action": "play"})
    admin.post("/api/admin/volume", json={"volume": 140})  # borné à 100
    assert admin.fake.calls == [("pause",), ("resume",), ("volume", 100)]


def test_new_pin_disconnects_guest_even_in_admin_browser(admin):
    admin.post("/api/join", json={"pin": main.store.session.guest_pin})
    assert admin.get("/api/state").status_code == 200
    admin.post("/api/admin/pin")
    assert admin.get("/api/state").status_code == 401
    # L'admin garde ses pochettes (et son flux en direct).
    assert admin.get("/art?p=/getaa%3Fx").status_code != 401


def test_admin_adds_track_next_or_end(admin, monkeypatch):
    class FakeSpotify:
        def track(self, tid):
            return {"id": tid, "title": "T", "artist": "A", "image": ""}

    monkeypatch.setattr(main, "spotify", FakeSpotify())
    # Un invité a demandé « Un » (position 5) ; « Deux » et « Trois » = suite de la playlist.
    main.store.add({"id": "a" * 22, "title": "Un", "artist": "A"}, "guest-1111", "Léa")
    admin.post("/api/admin/add", json={"track_id": "d" * 22, "where": "next"})
    admin.post("/api/admin/add", json={"track_id": "e" * 22, "where": "end"})
    # ⏫ juste après le titre en cours ; ＋ juste après la dernière demande, pas tout en bas.
    assert admin.fake.calls[:2] == [("add", "d" * 22, 5), ("add", "e" * 22, 6)]
    hosts = [r for r in main.store.pending() if r.guest_id == "host"]
    assert [r.guest_name for r in hosts] == ["Hôte", "Hôte"]
    assert "Hôte" not in [g["name"] for g in admin.get("/api/admin/state").json()["guests"]]
    # Déjà dans la file : on demande confirmation…
    r = admin.post("/api/admin/add", json={"track_id": "a" * 22, "where": "end"})
    assert r.status_code == 409 and r.json()["detail"]["duplicate"]
    # … et l'hôte peut forcer.
    assert admin.post("/api/admin/add", json={"track_id": "a" * 22, "where": "end", "force": True}).status_code == 200
    assert admin.fake.calls[-1][:2] == ("add", "a" * 22)


def test_kick_asks_code_again_without_banning(admin):
    guest, other = TestClient(main.app), TestClient(main.app)
    for c, gid in [(guest, "guest-kick"), (other, "guest-stay")]:
        c.post("/api/join", json={"pin": main.store.session.guest_pin})
        c.post("/api/hello", json={"guest_id": gid, "guest_name": gid})

    admin.post("/api/admin/kick", json={"guest_id": "guest-kick"})
    assert guest.get("/api/state?guest_id=guest-kick").status_code == 401
    names = [g["guest_id"] for g in admin.get("/api/admin/state").json()["guests"]]
    assert "guest-kick" not in names and "guest-stay" in names  # il disparaît de la liste
    assert other.get("/api/state?guest_id=guest-stay").status_code == 200  # les autres restent connectés

    # Il peut revenir avec le code : ce n'est pas un ban.
    guest.post("/api/join", json={"pin": main.store.session.guest_pin})
    guest.post("/api/hello", json={"guest_id": "guest-kick", "guest_name": "guest-kick"})
    assert guest.get("/api/state?guest_id=guest-kick").status_code == 200
    assert "guest-kick" in [g["guest_id"] for g in admin.get("/api/admin/state").json()["guests"]]


def test_speaker_group_and_volume(admin):
    calls = admin.fake.calls
    admin.fake.group_speaker = lambda uid, sp, join: calls.append(("group", sp, join))
    admin.fake.set_speaker_volume = lambda sp, v: calls.append(("spvol", sp, v))
    admin.fake.speakers = lambda uid: [{"uid": "RINCON_B", "name": "Cuisine", "volume": 20, "in_group": True, "coordinator": False}]

    assert admin.post("/api/admin/speakers/group", json={"uid": "RINCON_B", "join": True}).json()[0]["in_group"]
    admin.post("/api/admin/speakers/volume", json={"uid": "RINCON_B", "volume": -5})
    assert calls == [("group", "RINCON_B", True), ("spvol", "RINCON_B", 0)]


def test_rename_updates_queue_and_guest_page(admin):
    guest = TestClient(main.app)
    guest.post("/api/join", json={"pin": main.store.session.guest_pin})
    guest.post("/api/hello", json={"guest_id": "guest-name", "guest_name": "Tom"})
    main.store.add({"id": "a" * 22, "title": "Un", "artist": "A"}, "guest-name", "Tom")  # « Un » est en position 5

    # L'invité change lui-même son prénom : la file suit.
    guest.post("/api/hello", json={"guest_id": "guest-name", "guest_name": "Thomas"})
    assert admin.get("/api/admin/state").json()["queue"][0]["by"] == "Thomas"

    # L'hôte le renomme : la file et la page de l'invité suivent.
    admin.post("/api/admin/rename", json={"guest_id": "guest-name", "name": "DJ Tom"})
    assert admin.get("/api/admin/state").json()["queue"][0]["by"] == "DJ Tom"
    assert guest.get("/api/state?guest_id=guest-name").json()["name"] == "DJ Tom"


def test_tracks_added_from_sonos_app_are_tagged(admin, monkeypatch):
    from app.sonos import service_name
    assert service_name("x-sonosapi-hls-static:ALk?sid=284&flags=8232") == "YouTube Music"
    assert service_name("x-sonos-spotify:spotify%3atrack%3a1?sid=9") == "Spotify"
    s = snap()
    s["upcoming"][1]["service"] = "YouTube Music"
    monkeypatch.setattr(main, "snapshot", lambda force=False: s)
    q = admin.get("/api/admin/state").json()["queue"]
    assert q[1]["service"] == "YouTube Music" and q[0].get("service") is None
