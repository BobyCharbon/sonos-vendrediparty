"""Soirée liée à un événement : les comptes notés « Présent » entrent dans Musique et Jeux sans le code ;
noté absent ensuite, l'accès sans code s'arrête (le code, lui, marche toujours)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod
from app import main

EVENT = '32f18a3b-827f-4123-8cf4-33de06c9a51c'
TOKEN = 'jeton-' + 'x' * 40


def fake_supabase(live: dict):
    calls = []

    def handler(request: httpx.Request):
        calls.append(str(request.url))
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': live.get('uid', 'u-1')})
        if request.url.path == '/rest/v1/rsvps':
            return httpx.Response(200, json=live.get('rsvps', []))
        if request.url.path == '/rest/v1/rpc/get_member_directory':
            return httpx.Response(200, json=[{'status': live.get('status', 'active')}])
        if request.url.path == '/rest/v1/events':
            return httpx.Response(200, json=[{'id': EVENT, 'title': 'Vendredi chez Boby', 'starts_at': '2026-10-30T19:00:00Z'}])
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler)), calls


@pytest.fixture
def party(monkeypatch):
    live = {'rsvps': [{'status': 'yes', 'waitlisted': False}]}
    client, calls = fake_supabase(live)
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', client))
    monkeypatch.setattr(main.store, 'session', main.store.session)  # rendue après le test, même si une soirée redémarre
    monkeypatch.setattr(main.store.session, 'active', True)
    monkeypatch.setattr(main.store.session, 'event_id', '')
    monkeypatch.setattr(main.store.session, 'event_title', '')
    monkeypatch.setattr(main.store.session, 'event_passes', {})
    with TestClient(main.app) as host, TestClient(main.app) as guest:
        assert host.post('/api/admin/login', json={'pin': '9999'}).status_code == 200
        yield host, guest, live, calls


def test_attending_means_present_and_not_on_the_waitlist():
    live = {'rsvps': [{'status': 'yes', 'waitlisted': False}]}
    client, calls = fake_supabase(live)
    a = accounts_mod.Accounts(b'secret', client)
    assert a.attending(TOKEN, EVENT) == ('u-1', True)
    assert any(f'event_id=eq.{EVENT}' in c and 'user_id=eq.u-1' in c for c in calls)
    for rows in ([{'status': 'maybe', 'waitlisted': False}], [{'status': 'yes', 'waitlisted': True}], []):
        live['rsvps'] = rows
        assert a.attending(TOKEN, EVENT) == ('u-1', False)
    live.update(rsvps=[{'status': 'yes', 'waitlisted': False}], status='banned')  # compte banni du groupe
    assert a.attending(TOKEN, EVENT) == ('u-1', False)


def test_without_a_linked_event_the_code_is_still_required(party):
    host, guest, live, _ = party
    r = guest.post('/api/join/account', json={'token': TOKEN})
    assert r.status_code == 409
    assert guest.get('/api/state').status_code == 401


def test_the_host_links_an_event_from_its_upcoming_events(party):
    host, guest, live, calls = party
    options = host.post('/api/admin/event/options', json={'token': TOKEN}).json()
    assert options == [{'id': EVENT, 'title': 'Vendredi chez Boby', 'starts_at': '2026-10-30T19:00:00Z'}]
    assert 'status=eq.published' in calls[-1]
    state = host.post('/api/admin/event', json={'event_id': EVENT, 'title': 'Vendredi chez Boby'}).json()
    assert state['event'] == {'id': EVENT, 'title': 'Vendredi chez Boby'}
    assert host.post('/api/admin/event', json={'event_id': 'pas-un-uuid', 'title': 'x'}).status_code == 422
    assert guest.post('/api/admin/event', json={'event_id': EVENT, 'title': 'x'}).status_code == 401
    assert host.post('/api/admin/event', json={'event_id': '', 'title': ''}).json()['event'] is None


def test_a_present_account_enters_without_code_and_loses_it_once_marked_absent(party):
    host, guest, live, _ = party
    host.post('/api/admin/event', json={'event_id': EVENT, 'title': 'Vendredi chez Boby'})
    r = guest.post('/api/join/account', json={'token': TOKEN})
    assert r.status_code == 200 and r.json()['event_title'] == 'Vendredi chez Boby'
    assert guest.get('/api/state').status_code == 200
    assert guest.post('/api/join/account', json={'token': TOKEN}).status_code == 200  # revérification : même accès
    live['rsvps'] = [{'status': 'no', 'waitlisted': False}]  # l'organisateur le note absent
    r = guest.post('/api/join/account', json={'token': TOKEN})
    assert r.status_code == 403 and '« Vendredi chez Boby »' in r.json()['detail']
    assert guest.get('/api/state').status_code == 401
    pin = main.store.session.guest_pin
    assert guest.post('/api/join', json={'pin': pin}).status_code == 200  # le code marche toujours
    live['rsvps'] = [{'status': 'yes', 'waitlisted': False}]  # de nouveau présent : accès rendu
    guest.cookies.clear()
    assert guest.post('/api/join/account', json={'token': TOKEN}).status_code == 200
    assert guest.get('/api/state').status_code == 200


def test_no_entry_without_a_running_party(party, monkeypatch):
    host, guest, live, _ = party
    host.post('/api/admin/event', json={'event_id': EVENT, 'title': 'Vendredi chez Boby'})
    monkeypatch.setattr(main.store.session, 'active', False)
    assert guest.post('/api/join/account', json={'token': TOKEN}).status_code == 409


def test_the_linked_event_survives_a_new_start(party):
    host, guest, live, _ = party
    host.post('/api/admin/event', json={'event_id': EVENT, 'title': 'Vendredi chez Boby'})
    main.store.start('room', 'Salon', 'next')
    assert (main.store.session.event_id, main.store.session.event_title) == (EVENT, 'Vendredi chez Boby')
