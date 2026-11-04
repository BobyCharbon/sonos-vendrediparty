"""Compte progressivement obligatoire (décision de l'admin du 04.11) : parties et titres en invité, réglés par
l'admin ; compteur côté serveur, suivi par l'identifiant d'invité (jamais l'adresse IP) ; une partie commencée
n'est jamais interrompue ; à la création du compte, les stats du Quiz de l'invité passent au compte."""
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, games, main, quiz
from app.guest_gate import GuestGate
from app.party import PartyStore
from tests.test_purity_api import TOK_A, supabase_for
from tests.test_spotify_mode import FakeCatalog, FakeUser
from app.spotify_player import SpotifyPlayer

LULU = "5f0c2d3e-1a2b-4c3d-9e8f-0a1b2c3d4e5f"
LEA = "7a1d3e4f-2b3c-4d5e-8f9a-1b2c3d4e5f60"
MAX = "acct-" + "1" * 40  # animateur avec un compte : ses parties ne comptent pas


# ── Module seul ──
def test_the_counter_counts_each_game_once_and_blocks_from_the_limit(tmp_path):
    gate = GuestGate(tmp_path / "g.json")
    gate.set_settings(games=3)
    for code in ("1111", "2222", "2222", "3333"):
        gate.record(LULU, code)
    assert gate.played(LULU) == 3
    assert gate.blocked(LULU) and gate.blocked(LULU, "4444")
    assert not gate.blocked(LULU, "2222")  # partie déjà comptée : il y revient
    assert GuestGate(tmp_path / "g.json").played(LULU) == 3  # relu du disque : recharger la page n'y change rien


TEST_SITE = "https://partytest.bobycharbon.ch"


def test_soft_message_after_the_first_game_and_level_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("PARTY_PUBLIC_URL", TEST_SITE)  # 0 n'existe que sur le site de test
    gate = GuestGate(tmp_path / "g.json")
    gate.set_settings(games=3)
    assert gate.status(LULU)["nudge"] is False
    gate.record(LULU, "1111")
    st = gate.status(LULU)
    assert st["nudge"] and not st["blocked"] and "juste ton numéro" in st["text"]
    gate.set_settings(games=0)
    assert gate.status(LEA)["blocked"]  # 0 : compte obligatoire pour jouer dès l'arrivée


def test_settings_are_bounded_and_have_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("GUEST_GAMES_BEFORE_ACCOUNT", raising=False)
    monkeypatch.delenv("GUEST_TRACKS_PER_PARTY", raising=False)
    gate = GuestGate(tmp_path / "g.json")
    assert gate.settings() == {"games": 3, "tracks": 3}
    before, after = gate.set_settings(games=-4, tracks=5)
    assert before == {"games": 3, "tracks": 3} and after == {"games": 1, "tracks": 5}  # production : jamais 0


def test_production_never_asks_an_account_before_the_first_game(tmp_path, monkeypatch):
    """C1 (audit du 04.11, Apple 5.1.1(v)) : dans l'app App Store, on essaie toujours une partie sans compte."""
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://party.bobycharbon.ch")
    gate = GuestGate(tmp_path / "g.json")
    assert gate.set_settings(games=0)[1]["games"] == 1
    gate.data["settings"]["games"] = 0  # ancien réglage resté dans le fichier
    assert gate.settings()["games"] == 1 and not gate.status(LEA)["blocked"]
    monkeypatch.setenv("PARTY_PUBLIC_URL", TEST_SITE)
    assert gate.settings()["games"] == 0


# ── Parties (API) ──
@pytest.fixture
def setup(monkeypatch, tmp_path):
    acc = accounts_mod.Accounts(b"secret", supabase_for({TOK_A: "alice"}))
    monkeypatch.setattr(main, "accounts", acc)
    monkeypatch.setattr(main, "account_limiter", main.Limiter(per_ip=1000, ip_lock=1, global_max=10000, global_window=1, global_lock=1))
    monkeypatch.setattr(main, "_game_creations", {})
    monkeypatch.setattr(quiz, "STATS_PATH", tmp_path / "quiz_stats.json")
    gate = GuestGate(tmp_path / "gate.json")
    gate.set_settings(games=3, tracks=3)
    monkeypatch.setattr(main, "guest_gate", gate)
    s = main.store.session
    for field in ("games", "guests", "bans", "push", "guest_notify", "activity_start_tokens"):
        monkeypatch.setattr(s, field, {})
    monkeypatch.setattr(s, "requests", [])
    monkeypatch.setattr(s, "messages", [])
    with TestClient(main.app) as c:
        yield c, gate, acc.gid("alice")


def create(c, kind, gid, name="Lulu"):
    return c.post("/api/games", json={"type": kind, "guest_id": gid, "name": name})


def act(c, code, gid, action, **kw):
    return c.post(f"/api/games/{code}", json={"guest_id": gid, "action": action, **kw})


def test_after_three_games_a_new_game_needs_an_account(setup):
    c, gate, _ = setup
    codes = [create(c, "never", MAX, "Max").json()["code"] for _ in range(4)]
    for code in codes[:3]:
        r = act(c, code, LULU, "join", name="Lulu")
        assert r.status_code == 200
    assert r.json()["gate"]["played"] == 3 and r.json()["gate"]["blocked"] is False  # dans sa 3e partie : il y reste
    refused = act(c, codes[3], LULU, "join", name="Lulu")
    assert refused.status_code == 403 and refused.json()["detail"]["account_required"] == "games"
    assert not games.player(main.store.session.games[codes[3]], LULU)
    assert create(c, "never", LULU).status_code == 403  # créer une partie aussi
    assert create(c, "room", LULU).status_code == 200   # une salle n'est pas une partie
    # Une partie déjà commencée n'est jamais interrompue : il y joue, revient, la relance.
    assert act(c, codes[0], LULU, "leave").status_code == 200
    assert act(c, codes[0], LULU, "join", name="Lulu").status_code == 200
    view = c.get(f"/api/games/{codes[1]}", params={"guest_id": LULU}).json()
    assert view["me"] and view["gate"]["blocked"] is False
    assert c.get(f"/api/games/{codes[3]}", params={"guest_id": LULU}).json()["gate"]["blocked"] is True


def test_soft_message_after_the_first_game(setup):
    c, _, _ = setup
    code = create(c, "never", LEA, "Léa").json()["code"]
    gate = act(c, code, LULU, "join", name="Lulu").json()["gate"]
    assert gate["played"] == 1 and gate["nudge"] and not gate["blocked"]


def test_level_zero_needs_an_account_from_the_start_but_accounts_play_freely(setup, monkeypatch):
    monkeypatch.setenv("PARTY_PUBLIC_URL", TEST_SITE)  # site de test : 0 permis
    c, gate, alice = setup
    gate.set_settings(games=0)
    code = create(c, "never", alice, "alice").json()["code"]  # compte : jamais limité, pas de « gate »
    assert "gate" not in c.get(f"/api/games/{code}", params={"guest_id": alice}).json()
    assert act(c, code, LULU, "join", name="Lulu").status_code == 403
    assert create(c, "never", LULU).status_code == 403


def test_a_room_launch_does_not_enroll_a_guest_over_the_limit(setup):
    c, gate, _ = setup
    room = create(c, "room", LEA, "Léa").json()["code"]
    assert act(c, room, LULU, "join", name="Lulu").status_code == 200
    gate.set_settings(games=1)
    act(c, room, LEA, "launch", settings={"type": "never"})
    first = main.store.session.games[room]["current"]
    assert games.player(main.store.session.games[first], LULU)  # 1re partie : inscrit d'office, comptée
    act(c, first, LEA, "end")
    act(c, room, LEA, "launch", settings={"type": "never"})
    second = main.store.session.games[room]["current"]
    assert not games.player(main.store.session.games[second], LULU)  # au-delà : reste dans la salle
    assert games.player(main.store.session.games[room], LULU)
    view = c.get(f"/api/games/{second}", params={"guest_id": LULU}).json()
    assert view["gate"]["blocked"] is True


def test_creating_the_account_returns_to_the_game_and_keeps_quiz_stats(setup):
    c, gate, alice = setup
    gate.set_settings(games=1)
    quiz._save_stats({"players": {LULU: {"name": "Lulu", "pts": 7, "games": 1, "wins": 1, "ok": 3, "n": 4, "best_streak": 2,
                                          "records": {"classic": 7}, "themes": {"cine": [3, 4]}},
                                  alice: {"name": "alice", "pts": 5, "games": 2, "wins": 0, "ok": 2, "n": 6, "best_streak": 3,
                                          "records": {"classic": 4, "speed": 2}, "themes": {"cine": [1, 2]}}}})
    first = create(c, "never", MAX, "Max").json()["code"]
    act(c, first, LULU, "join", name="Lulu")
    second = create(c, "never", MAX, "Max").json()["code"]
    assert act(c, second, LULU, "join", name="Lulu").status_code == 403
    # Création du compte (parcours SMS) : le téléphone relie son compte, puis rejoint la partie.
    r = c.post("/api/account/link", json={"token": TOK_A, "guest_id": LULU})
    assert r.status_code == 200 and r.json()["guest_id"] == alice
    assert act(c, second, alice, "join", name="alice").status_code == 200
    assert games.player(main.store.session.games[first], alice)  # sa place de la 1re partie suit le compte
    row = quiz._load_stats()["players"]
    assert LULU not in row
    assert row[alice]["pts"] == 12 and row[alice]["games"] == 3 and row[alice]["best_streak"] == 3
    assert row[alice]["records"] == {"classic": 7, "speed": 2} and row[alice]["themes"] == {"cine": [4, 6]}
    assert gate.played(LULU) == 0  # plus de compteur d'invité


def test_admin_settings_are_logged_and_shown_in_the_admin_state(setup):
    c, gate, _ = setup
    assert c.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    r = c.post("/api/admin/guest-gate", json={"games": 5, "tracks": 0})
    assert r.status_code == 200 and r.json()["guest_gate"] == {"games": 5, "tracks": 0}
    assert c.get("/api/admin/state").json()["guest_gate"] == {"games": 5, "tracks": 0}
    entry = c.get("/api/admin/audit").json()["entries"][0]
    assert entry["action"] == "admin.guest_gate" and entry["details"] == {"games": "3 → 5", "tracks": "3 → 0"}
    assert c.post("/api/admin/guest-gate", json={"games": 99}).status_code == 422
    assert TestClient(main.app).post("/api/admin/guest-gate", json={"games": 1}).status_code == 401


# ── Musique ──
@pytest.fixture
def music(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "store", PartyStore(tmp_path / "session.json"))
    monkeypatch.setattr(main, "_snap", {"at": 0, "data": None, "fingerprint": None, "version": 0, "current": None})
    user, cat = FakeUser(), FakeCatalog()
    monkeypatch.setattr(main, "spotify_player", SpotifyPlayer(user, cat, main.store))
    monkeypatch.setattr(main, "spotify_user", user)
    monkeypatch.setattr(main, "spotify", cat)
    gate = GuestGate(tmp_path / "gate.json")
    gate.set_settings(tracks=3)
    monkeypatch.setattr(main, "guest_gate", gate)
    main.store.start("spotify", "Spotify", "next", source="spotify")
    guest = TestClient(main.app)  # invité : jamais connecté à l'admin
    assert guest.post("/api/join", json={"pin": main.store.session.guest_pin}).status_code == 200
    return guest, gate


def queue(c, letter, gid=LULU):
    return c.post("/api/queue", json={"track_id": letter * 22, "guest_id": gid, "guest_name": "Lulu"})


def test_a_guest_proposes_at_most_three_tracks_per_party(music):
    guest, _ = music
    assert guest.get("/api/state", params={"guest_id": LULU}).json()["guest_tracks"] == {"used": 0, "limit": 3, "left": 3}
    for letter in "abc":
        assert queue(guest, letter).status_code == 200
    r = queue(guest, "d")
    assert r.status_code == 403 and r.json()["detail"]["account_required"] == "music"
    assert "Crée ton compte" in r.json()["detail"]["message"]
    assert guest.get("/api/state", params={"guest_id": LULU}).json()["guest_tracks"]["left"] == 0
    assert queue(guest, "e", LEA).status_code == 200  # un autre invité garde ses titres
    main.store.start("spotify", "Spotify", "next", source="spotify")  # nouvelle soirée : nouveaux titres
    assert queue(guest, "f").status_code == 200


def test_tracks_level_zero_needs_an_account_but_music_stays_visible(music):
    guest, gate = music
    gate.set_settings(tracks=0)
    state = guest.get("/api/state", params={"guest_id": LULU}).json()
    assert state["active"] and state["guest_tracks"]["left"] == 0  # la musique reste accessible (Apple)
    assert queue(guest, "a").status_code == 403
    assert queue(guest, "a", "acct-" + "0" * 40).status_code == 200  # compte : sans cette limite
