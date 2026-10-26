"""Écran TV (/tv, Apple TV via AirPlay depuis le Mac) : titre en cours, prochaines demandes avec les prénoms,
code et QR pour entrer, parties de jeu en cours. Réservé à l'hôte (il affiche le code de la soirée)."""
import pytest
from fastapi.testclient import TestClient

from app import main

NOW = {"title": "Titre en cours", "artist": "Artiste", "art": "", "by": "Léa", "track_id": "t0"}
UPCOMING = [{"title": f"Titre {i}", "artist": "A", "art": "", "by": "Tom" if i % 2 else None, "track_id": f"t{i}",
             "rid": None, "eta": 60 * i, "service": None} for i in range(1, 10)]


@pytest.fixture
def tv(monkeypatch):
    monkeypatch.setattr(main.store, 'session', main.store.session)
    monkeypatch.setattr(main.store.session, 'active', False)
    monkeypatch.setattr(main.store.session, 'event_title', '')
    monkeypatch.setattr(main.store.session, 'games', {})
    monkeypatch.setattr(main, 'snapshot', lambda *a, **k: {})
    monkeypatch.setattr(main, 'public_sonos', lambda snap, guest_id='': {"state": "PLAYING", "now": NOW, "upcoming": UPCOMING})
    with TestClient(main.app) as host, TestClient(main.app) as guest:
        assert host.post('/api/admin/login', json={'pin': '9999'}).status_code == 200
        yield host, guest


def test_the_tv_page_is_served(tv):
    host, guest = tv
    r = guest.get('/tv')
    assert r.status_code == 200 and '<title>Party TV</title>' in r.text


def test_only_the_host_reads_the_tv_screen_since_it_shows_the_code(tv):
    host, guest = tv
    assert guest.get('/api/tv').status_code == 401


def test_before_the_party_the_tv_shows_how_to_join(tv):
    host, guest = tv
    data = host.get('/api/tv').json()
    assert data['active'] is False and data['pin'] == main.store.session.guest_pin and data['url']


def test_during_the_party_the_tv_shows_the_track_the_next_requests_the_event_and_the_games(tv, monkeypatch):
    host, guest = tv
    monkeypatch.setattr(main.store.session, 'active', True)
    monkeypatch.setattr(main.store.session, 'event_title', 'Vendredi chez Boby')
    code = host.post('/api/games', json={'type': 'undercover', 'guest_id': 'anon-phone-1', 'name': 'Lulu'}).json()['code']
    data = host.get('/api/tv').json()
    assert data['now']['title'] == 'Titre en cours' and data['now']['by'] == 'Léa'
    assert [t['title'] for t in data['upcoming']] == [f'Titre {i}' for i in range(1, 7)]  # les 6 prochains
    assert data['upcoming'][0] == {'title': 'Titre 1', 'artist': 'A', 'art': '', 'by': 'Tom'}
    assert data['event'] == 'Vendredi chez Boby'
    assert data['games'] == [{'code': code, 'name': 'Undercover', 'players': 1}]


def test_the_tv_says_when_the_music_cannot_be_reached(tv, monkeypatch):
    host, guest = tv
    monkeypatch.setattr(main.store.session, 'active', True)

    def broken(*a, **k):
        raise OSError('Sonos injoignable')
    monkeypatch.setattr(main, 'snapshot', broken)
    data = host.get('/api/tv').json()
    assert data['active'] is True and data['error'] and 'now' not in data
