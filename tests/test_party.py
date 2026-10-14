from app.party import PartyStore, Request, insert_position
from app.sonos import spotify_track_id


def req(guest, track):
    return Request(id=track, track_id=track, title="", artist="", image="", guest_id=guest, guest_name=guest, added_at=0)


def simulate(mode, adds, playlist=("p1", "p2", "p3")):
    """Joue une suite d'ajouts (invité, titre) et renvoie la file à venir."""
    current_pos = 5
    upcoming = list(playlist)
    pending = []
    for guest, track in adds:
        positions = [(current_pos + 1 + i, t) for i, t in enumerate(upcoming)]
        pos = insert_position(mode, current_pos, positions, pending, guest)
        upcoming.insert(pos - current_pos - 1, track)
        pending.append(req(guest, track))
    return upcoming


def test_next_mode_inserts_right_after_current():
    assert simulate("next", [("A", "a1"), ("B", "b1")]) == ["b1", "a1", "p1", "p2", "p3"]


def test_fair_mode_round_robin_before_playlist():
    adds = [("A", "a1"), ("A", "a2"), ("A", "a3"), ("B", "b1"), ("C", "c1"), ("B", "b2")]
    assert simulate("fair", adds) == ["a1", "b1", "c1", "a2", "b2", "a3", "p1", "p2", "p3"]


def test_fair_mode_ignores_played_requests():
    # a1 a déjà été joué : il n'est plus dans la file, A revient au tour 1.
    pending = [req("A", "a1"), req("B", "b1")]
    upcoming = [(6, "b1"), (7, "p1")]
    assert insert_position("fair", 5, upcoming, pending, "A") == 7


def test_nothing_playing_appends_to_end():
    assert insert_position("next", 0, [], [], "A") == 0
    assert insert_position("fair", 0, [], [], "A") == 0


def test_spotify_track_id_from_sonos_uri():
    uri = "x-sonos-spotify:spotify%3atrack%3a4xR85ArN9segGS9bqKE5gg?sid=12&flags=8224&sn=3"
    assert spotify_track_id(uri) == "4xR85ArN9segGS9bqKE5gg"
    assert spotify_track_id("x-file-cifs://nas/song.mp3") is None


def test_store_persists_and_reconciles(tmp_path):
    store = PartyStore(tmp_path / "s.json")
    store.start("RINCON_X", "Salon", "fair")
    store.add({"id": "a" * 22, "title": "T", "artist": "X"}, "guest-1234", "Léa")
    store.add({"id": "b" * 22, "title": "U", "artist": "Y"}, "guest-1234", "Léa")
    store.reconcile({"b" * 22})

    reloaded = PartyStore(tmp_path / "s.json")
    assert reloaded.session.active and reloaded.session.mode == "fair"
    assert [r.status for r in reloaded.session.requests] == ["played", "queued"]


def test_bans_by_guest_and_ip(tmp_path, monkeypatch):
    store = PartyStore(tmp_path / "s.json")
    store.start("RINCON_X", "Salon", "next")
    store.add({"id": "a" * 22, "title": "T", "artist": "X"}, "guest-aaaa", "Tom", "192.168.50.40")

    store.ban("guest-aaaa", 10)
    assert store.ban_status("guest-aaaa")["until"] > 0
    # Nouvel onglet privé (autre identifiant) depuis le même téléphone : toujours bloqué.
    assert store.ban_status("guest-new1", "192.168.50.40") is not None
    assert store.ban_status("guest-bbbb", "192.168.50.41") is None

    # Le blocage de 10 minutes expire tout seul.
    import app.party as party
    now = party.time.time()
    monkeypatch.setattr(party.time, "time", lambda: now + 601)
    assert store.ban_status("guest-aaaa", "192.168.50.40") is None


def test_permanent_ban_survives_new_party(tmp_path):
    store = PartyStore(tmp_path / "s.json")
    store.start("RINCON_X", "Salon", "next")
    store.add({"id": "a" * 22, "title": "T", "artist": "X"}, "guest-aaaa", "Tom", "192.168.50.40")
    store.ban("guest-aaaa", None)

    store.start("RINCON_X", "Salon", "next")
    assert store.ban_status("guest-aaaa") == {"until": 0}
    store.unban("guest-aaaa")
    assert store.ban_status("guest-aaaa", "192.168.50.40") is None
