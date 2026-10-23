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


def test_next_mode_is_first_come_first_served_before_the_playlist():
    """« À la suite » : une demande passe après les demandes déjà en attente (celles de l'hôte comprises),
    jamais devant ; toujours avant la suite de la playlist."""
    assert simulate("next", [("A", "a1"), ("B", "b1")]) == ["a1", "b1", "p1", "p2", "p3"]
    assert simulate("next", [("Hôte", "h1"), ("B", "b1"), ("Hôte", "h2")]) == ["h1", "b1", "h2", "p1", "p2", "p3"]


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


def test_bans_by_guest_only_never_by_shared_ip(tmp_path, monkeypatch):
    store = PartyStore(tmp_path / "s.json")
    store.start("RINCON_X", "Salon", "next")
    store.add({"id": "a" * 22, "title": "T", "artist": "X"}, "guest-aaaa", "Tom", "192.168.50.40")

    store.ban("guest-aaaa", 10)
    assert store.ban_status("guest-aaaa")["until"] > 0
    # Même adresse IP (même box, même Wi-Fi de la soirée : l'iPhone de l'hôte, les autres invités) : jamais bloqué.
    assert store.ban_status("guest-new1", "192.168.50.40") is None
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


def test_fair_moves_reorders_existing_queue():
    from app.party import fair_moves

    # A a spammé 3 titres, puis B et C en ont ajouté un ; p1/p2 = playlist de l'hôte.
    reqs = [req("A", "a1"), req("A", "a2"), req("A", "a3"), req("B", "b1"), req("C", "c1")]
    for i, r in enumerate(reqs):
        r.added_at = i
    queue = ["a3", "a2", "a1", "c1", "b1", "p1", "p2"]  # ordre « juste après » (dernier ajouté en tête)
    current = 10
    moves = fair_moves(current, [(current + 1 + i, t) for i, t in enumerate(queue)], reqs)

    # Rejoue les déplacements comme le ferait Sonos.
    for src, dst in moves:
        queue.insert(dst - current - 1, queue.pop(src - current - 1))
    assert queue == ["a1", "b1", "c1", "a2", "a3", "p1", "p2"]


def test_fair_moves_nothing_to_do_when_already_fair():
    from app.party import fair_moves

    reqs = [req("A", "a1"), req("B", "b1")]
    reqs[1].added_at = 1
    assert fair_moves(3, [(4, "a1"), (5, "b1"), (6, "p1")], reqs) == []


def test_proxy_ip_never_bans_everyone(tmp_path):
    # Données enregistrées avant la prise en compte du proxy : tout le monde a l'IP de pfSense.
    store = PartyStore(tmp_path / "s.json", ignored_ips={"192.168.50.1"})
    store.start("RINCON_X", "Salon", "next")
    store.session.guests = {
        "guest-spam": {"name": "Spam", "ips": ["192.168.50.1", "86.220.23.199"], "joined_at": 0},
        "guest-ok11": {"name": "Ok", "ips": ["192.168.50.1"], "joined_at": 0},
    }
    store.register_guest("guest-new1", "Nouveau", "192.168.50.1")
    assert store.session.guests["guest-new1"]["ips"] == []

    store.ban("guest-spam", None)
    assert store.session.bans["guest-spam"]["ips"] == ["86.220.23.199"]
    assert store.ban_status("guest-ok11", "192.168.50.1") is None
    assert store.ban_status("guest-new1", "192.168.50.1") is None
    assert store.ban_status("guest-spam", "192.168.50.1") is not None
    assert store.ban_status("autre-onglet", "86.220.23.199") is None  # même box : pas touché


def test_end_of_requests_is_before_host_playlist():
    from app.party import end_of_requests

    pending = [req("A", "a1"), req("B", "b1")]
    upcoming = [(6, "a1"), (7, "b1"), (8, "p1"), (9, "p2")]
    assert end_of_requests(5, upcoming, pending) == 8   # après b1, avant p1
    assert end_of_requests(5, [(6, "p1")], []) == 6     # aucune demande : juste après le titre en cours
    assert end_of_requests(0, upcoming, pending) == 0   # rien ne joue : fin de file
