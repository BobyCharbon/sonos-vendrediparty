"""Réactions de Zicou (décision F, 4.11.2026) : petit bonus plafonné quand un membre ajoute un titre, termine une partie
de soirée ou de Méninges, répond à un événement ; jamais pour un jeu à boire ; une même chose comptée une fois ; sans
Zicou, aucun effet (une seule proposition d'adoption) ; bandeau éphémère coupable ; requêtes simultanées."""
import re
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, pet, pet_reactions, pet_store
from tests.test_pet_api import ALICE, T0, TOK_A, me, setup  # noqa: F401  (fixture du Compagnon câblé)
from tests.test_spotify_mode import ext  # noqa: F401  (fixture : soirée Spotify, file d'attente)

GID = "acct-" + "1" * 40
GAMES_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "games.js"


def h(hours: float) -> float:
    return (T0 + timedelta(hours=hours)).timestamp()


# ── Jeux à boire : jamais récompensés ──

def test_the_alcohol_category_of_games_js_is_never_rewarded():
    """La catégorie « 🍻 Alcool » de l'écran Jeux est entièrement exclue (un jeu ajouté là devra l'être aussi)."""
    src = GAMES_JS.read_text()
    drinks = re.search(r'\["drinks", "🍻 Alcool", \[([^\]]*)\]\]', src).group(1)
    listed = set(re.findall(r'"([a-z]+)"', drinks))
    assert listed and listed <= pet_reactions.DRINKING_GAMES
    for kind in listed | {"pyramid"}:
        assert not pet_reactions.rewardable_game({"type": kind, "options": {"sips": 0}})


@pytest.mark.parametrize("options", [{"sips": 2}, {"alcohol": True, "sips": 0}, {"sips": "x"}])
def test_a_game_played_with_sips_is_never_rewarded(options):
    for kind in ("blackjack", "quiz", "likely"):   # étiquette 🍻 de games.js : récompensés seulement sans alcool
        assert not pet_reactions.rewardable_game({"type": kind, "options": options})


def test_sober_games_are_rewarded_but_not_the_game_room():
    assert pet_reactions.rewardable_game({"type": "quiz", "options": {"sips": 0}})
    assert pet_reactions.rewardable_game({"type": "undercover", "options": {}})
    assert not pet_reactions.rewardable_game({"type": "room", "options": {}})
    assert not pet_reactions.rewardable_game({"options": {}})


# ── Journal : une fois par chose, plafond du jour, bandeaux ──

def test_each_thing_is_counted_once_and_banners_stop_at_the_daily_cap(tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "log.json")
    log.mark_pet(GID, "Paillette", True)
    assert log.react(GID, "music", "t1", h(0)) and not log.react(GID, "music", "t1", h(0.01))   # même titre : une fois
    for i in range(2, 6):
        assert log.react(GID, "music", f"t{i}", h(0.01 * i))
    items = log.take(GID, h(0.1))
    cap, coins = pet.REWARDS["music"][1], pet.REWARDS["music"][2]
    assert len(items) == cap and all(i["coins"] == coins for i in items)
    assert items[0]["text"] == f"🪩 Paillette danse sur ton son ! +{coins} 🪙"
    assert log.take(GID, h(0.1)) == []   # retirés de la file
    assert len(log.times(GID, "music")) == 5 and log.times(GID, "party") == []
    assert log.react(GID, "music", "t9", h(24)) and len(log.take(GID, h(24))) == 1   # nouveau jour : ça repart


def test_without_a_zicou_nothing_is_given_and_adoption_is_offered_once(tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "log.json")
    log.react(GID, "party", "p1", h(0))
    assert log.take(GID, h(0)) == []                  # état inconnu : le bandeau attend
    log.mark_pet(GID, None, False)
    assert log.take(GID, h(0)) == [{"kind": "adopt", "text": pet_reactions.ADOPT_TEXT}]
    log.react(GID, "party", "p2", h(1))
    assert log.take(GID, h(1)) == []                  # une seule proposition, jamais de relance
    assert pet_reactions.ActivityLog(log.path).offered.get(GID)   # gardé dans le fichier


def test_an_egg_or_a_departed_zicou_gets_no_banner_and_quiet_mode_hides_them(tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "log.json")
    log.mark_pet(GID, "Zicou", False)
    log.react(GID, "brain", "b1", h(0))
    assert log.take(GID, h(0)) == []
    log.mark_pet(GID, "Zicou", True)
    log.set_enabled(GID, False)
    log.react(GID, "brain", "b2", h(0))
    assert log.take(GID, h(0)) == [] and not log.enabled(GID)
    assert not pet_reactions.ActivityLog(log.path).enabled(GID)   # choix gardé
    log.set_enabled(GID, True)
    log.react(GID, "brain", "b3", h(0))
    assert [i["source"] for i in log.take(GID, h(0))] == ["brain"]


def test_guests_without_an_account_are_ignored_and_old_banners_expire(tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "log.json")
    assert not log.react("guest-1234", "music", "t1", h(0))
    log.mark_pet(GID, "Zicou", True)
    log.react(GID, "music", "t1", h(0))
    assert log.take(GID, h(1)) == []   # pas affiché dans les 10 min : oublié


def test_the_old_party_log_file_is_still_read(tmp_path):
    path = tmp_path / "pet_party.json"
    path.write_text('{"%s": [["partie-1", %f]]}' % (GID, h(0)))
    log = pet_store.PartyLog(path)
    assert log.times(GID) == [pet.iso(T0)] and log.times(GID, "music") == []
    assert not log.note(GID, "partie-1", h(1))


def test_simultaneous_requests_count_a_thing_only_once(tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "log.json")
    log.mark_pet(GID, "Zicou", True)
    results, start = [], threading.Barrier(12)

    def hit():
        start.wait()
        results.append(log.react(GID, "party", "same-game", h(0)))
    threads = [threading.Thread(target=hit) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1 and len(log.take(GID, h(0))) == 1


# ── Bonus appliqué au Zicou (pet.rewards) ──

def _alive():
    life, owner = pet.new_pet(T0)
    pet.advance(life, T0 + timedelta(minutes=5), owner)
    return life, owner


def test_music_gives_coins_capped_per_day_and_counted_once():
    life, owner = _alive()
    now = T0 + timedelta(hours=1)
    tracks = [pet.iso(now - timedelta(minutes=m)) for m in range(5, 0, -1)]
    life, owner, got = pet.rewards(life, owner, now, [], [], tracks)
    assert [g["source"] for g in got] == ["music"] * 3
    expected = 3 * pet.REWARDS["music"][2]
    assert owner["loop"]["coins"] == expected and owner["stats"]["music"] == 5
    life, owner, again = pet.rewards(life, owner, now + timedelta(minutes=1), [], [], tracks)
    assert again == [] and owner["loop"]["coins"] == expected   # rien n'est compté deux fois


def test_answering_an_event_is_no_longer_a_source():
    """Décision de l'admin (04.11.2026) : répondre à un événement ne rapporte plus rien."""
    assert "rsvp" not in pet.REWARDS and "rsvp" not in pet_reactions.SOURCES


def test_an_egg_gets_nothing_but_the_cursors_move_on():
    life, owner = pet.new_pet(T0)
    now = T0 + timedelta(minutes=1)
    life, owner, got = pet.rewards(life, owner, now, [], [], [pet.iso(now)])
    assert got == [] and not (owner.get("loop") or {}).get("coins")
    assert owner["claimed"]["music"] == pet.iso(now)


# ── Câblé au serveur ──

def test_a_finished_drinking_game_is_never_noted_and_a_sober_one_shows_a_banner(setup, monkeypatch):
    c, base, clock, acc, log = setup
    gid = acc.gid(ALICE)
    games = {"NEVR": {"id": "n1", "code": "NEVR", "type": "never", "phase": "end", "options": {}, "players": [{"id": gid}]},
             "QUIZ": {"id": "q1", "code": "QUIZ", "type": "quiz", "phase": "end", "options": {"sips": 0}, "players": [{"id": gid}]},
             "QBOI": {"id": "q2", "code": "QBOI", "type": "quiz", "phase": "end", "options": {"sips": 2}, "players": [{"id": gid}]}}
    monkeypatch.setattr(main, "get_game", lambda code: games[code])
    monkeypatch.setattr(main, "check_store_game", lambda *a: None)
    monkeypatch.setattr(main, "full_view", lambda game, guest: {"ok": True})
    for code in ("NEVR", "QBOI"):
        r = c.get(f"/api/games/{code}?guest_id={gid}")
        assert r.status_code == 200 and "x-zicou" not in r.headers
    assert log.times(gid) == []
    me(c)
    clock.go(minutes=5)
    me(c)                                             # œuf éclos : le serveur sait qu'il a un Zicou vivant
    c.get(f"/api/games/QUIZ?guest_id={gid}")
    assert len(log.times(gid)) == 1
    assert c.get(f"/api/games/QUIZ?guest_id={gid}").headers.get("x-zicou") == "1"
    r = c.post("/api/pet/reactions", json={"guest_id": gid})
    assert r.status_code == 200 and r.json()["enabled"] is True
    assert [i["coins"] for i in r.json()["items"]] == [pet.REWARDS["party"][2]]
    coins = me(c)["pet"]["daily"]["coins"]
    clock.go(minutes=1)
    news = me(c)
    assert news["pet"]["daily"]["coins"] == coins     # déjà compté à l'ouverture précédente : jamais deux fois


def test_the_reward_lands_in_the_zicou_at_the_next_opening(setup):
    c, base, clock, acc, log = setup
    me(c)
    clock.go(minutes=5)
    before = me(c)["pet"]["daily"]["coins"]
    log.note(acc.gid(ALICE), "titre-1", clock.now.timestamp() - 30, source="music")
    out = me(c)
    rewards = [n["text"] for n in out["news"] if n["kind"] == "reward"]
    assert any("musique" in t for t in rewards)
    assert out["pet"]["daily"]["coins"] == before + pet.REWARDS["music"][2]


def test_an_unknown_account_is_checked_once_with_its_token_and_offered_adoption(setup):
    c, base, clock, acc, log = setup
    gid = acc.gid(ALICE)
    log.react(gid, "music", "t1")
    assert c.post("/api/pet/reactions", json={"guest_id": gid}).json()["items"] == []   # sans jeton : attend
    r = c.post("/api/pet/reactions", json={"guest_id": gid, "token": TOK_A})
    assert r.json()["items"] == [{"kind": "adopt", "text": pet_reactions.ADOPT_TEXT}]
    assert ALICE not in base.pets   # simple lecture : aucun œuf pondu à sa place


def test_reactions_can_be_switched_off_and_ids_are_checked(setup):
    c, _, _, acc, log = setup
    gid = acc.gid(ALICE)
    assert c.post("/api/pet/reactions/prefs", json={"guest_id": gid, "on": False}).json()["enabled"] is False
    assert c.post("/api/pet/reactions", json={"guest_id": gid}).json() == {"enabled": False, "items": []}
    assert c.post("/api/pet/reactions", json={"guest_id": "guest-1234"}).status_code == 422
    assert c.post("/api/pet/reactions/prefs", json={"guest_id": "acct-x", "on": True}).status_code == 422


def test_an_accepted_track_is_noted_once_for_a_member(ext, monkeypatch, tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "log.json")
    log.mark_pet(GID, "Zicou", True)
    monkeypatch.setattr(main, "pet_party_log", log)
    assert ext.post("/api/join", json={"pin": main.store.session.guest_pin}).status_code == 200
    r = ext.post("/api/queue", json={"track_id": "a" * 22, "guest_id": GID, "guest_name": "Alice"})
    assert r.status_code == 200 and "x-zicou" not in r.headers   # bandeau dans la réponse même (aussi pour l'iPhone)
    assert [i["source"] for i in r.json()["zicou"]] == ["music"]
    assert ext.post("/api/queue", json={"track_id": "a" * 22, "guest_id": GID, "guest_name": "Alice"}).status_code == 409
    r = ext.post("/api/queue", json={"track_id": "b" * 22, "guest_id": "guest-1234", "guest_name": "Bob"})
    assert r.json()["zicou"] == [] and log.times("guest-1234", "music") == []
    assert len(log.times(GID, "music")) == 1
    unknown = pet_reactions.ActivityLog(tmp_path / "other.json")   # Zicou pas encore connu : en-tête, la page ira chercher
    monkeypatch.setattr(main, "pet_party_log", unknown)
    r = ext.post("/api/queue", json={"track_id": "c" * 22, "guest_id": GID, "guest_name": "Alice"})
    assert r.json()["zicou"] == [] and r.headers.get("x-zicou") == "1"
    assert ext.get(f"/api/state?guest_id={GID}").headers.get("x-zicou") == "1"
