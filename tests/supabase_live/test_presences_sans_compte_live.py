"""Présences à la main, personnes SANS compte (demande de l'admin du 26.11, migration 20261126150000), sur la VRAIE base
de TEST (jamais la prod) : l'organisation ajoute « Pote Théo du bar » Présent → compté chez un invité, qui ne voit jamais
le nom ; un invité ne lit ni n'écrit la table ; nom injurieux refusé ; Peut-être refusé si l'événement ne le propose pas ;
places comptées. Événements « sur invitation », sans notification.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_presences_sans_compte_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, create_event
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

QUIET = {'visibility': 'invited', 'notify_on_publish': False}
TABLE = 'event_manual_guests'


@pytest.fixture(scope='module')
def people():
    admin, ga, vip = Session(ADMIN), Session(GUEST_A), Session(VIP)
    made: list[str] = []
    yield admin, ga, vip, made
    for eid in made:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def event(admin: Session, made: list[str], title: str, **fields) -> str:
    eid = create_event(admin, title, **{**QUIET, **fields})
    made.append(eid)
    return eid


def post(who: Session, body) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/{TABLE}', headers={**who.headers, 'Prefer': 'return=representation'},
                      json=body, timeout=30)


def patch(who: Session, gid: str, body: dict) -> httpx.Response:
    return httpx.patch(f'{TEST_URL}/rest/v1/{TABLE}?id=eq.{gid}', headers={**who.headers, 'Prefer': 'return=representation'},
                       json=body, timeout=30)


def attendance(who: Session, eid: str) -> dict:
    rows = who.rpc('event_attendance', ids=[eid]).json()
    return rows[0] if rows else {}


def test_a_person_without_account_counts_for_a_guest_who_never_sees_the_name(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test présences sans compte')
    assert httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, timeout=30,
                      json={'event_id': eid, 'user_id': ga.uid}).status_code == 201
    before = attendance(ga, eid)
    card_before = ga.rpc('chat_event_cards', ids=[eid]).json()[0]['going']
    r = post(admin, {'event_id': eid, 'name': '  Pote Théo du bar ', 'status': 'yes'})
    assert r.status_code == 201, r.text
    theo = r.json()[0]
    assert theo['name'] == 'Pote Théo du bar' and theo['added_by'] == admin.uid

    after = attendance(ga, eid)
    assert after['going'] == before['going'] + 1
    assert 'Théo' not in str(after)  # aucun visage ni nom pour une personne sans compte
    assert ga.rpc('chat_event_cards', ids=[eid]).json()[0]['going'] == card_before + 1
    guest_view = ga.rpc('event_guest_list', e=eid).json()
    assert guest_view['counts']['yes'] >= 1 and 'Théo' not in str(guest_view)
    assert admin.rpc('event_guest_list', e=eid).json()['manual'] == {'yes': 1, 'maybe': 0, 'no': 0}

    # Peut-être puis Absent : les nombres suivent.
    assert patch(admin, theo['id'], {'status': 'maybe'}).json()[0]['status'] == 'maybe'
    assert attendance(ga, eid)['going'] == before['going']
    assert attendance(ga, eid)['maybe'] == before['maybe'] + 1
    assert patch(admin, theo['id'], {'status': 'no'}).json()[0]['status'] == 'no'
    assert ga.rpc('event_guest_list', e=eid).json()['counts']['no'] >= 1

    # Retiré : plus rien.
    assert httpx.delete(f'{TEST_URL}/rest/v1/{TABLE}?id=eq.{theo["id"]}', headers=admin.headers, timeout=30).status_code in (200, 204)
    assert admin.get(f'{TABLE}?event_id=eq.{eid}').json() == []
    assert attendance(ga, eid) == before


def test_a_guest_can_neither_read_nor_write_the_list(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test présences invité')
    assert httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, timeout=30,
                      json={'event_id': eid, 'user_id': ga.uid}).status_code == 201
    gid = post(admin, {'event_id': eid, 'name': 'Cousin Max', 'status': 'yes'}).json()[0]['id']
    assert ga.get(f'{TABLE}?event_id=eq.{eid}').json() == []
    assert post(ga, {'event_id': eid, 'name': 'Intrus', 'status': 'yes'}).status_code in (401, 403)
    assert patch(ga, gid, {'status': 'no'}).json() == []
    assert httpx.delete(f'{TEST_URL}/rest/v1/{TABLE}?id=eq.{gid}', headers={**ga.headers, 'Prefer': 'return=representation'},
                        timeout=30).json() == []
    assert admin.get(f'{TABLE}?id=eq.{gid}&select=status').json() == [{'status': 'yes'}]
    # Un co-organisateur, lui, gère la liste.
    assert httpx.post(f'{TEST_URL}/rest/v1/event_organizers', headers=admin.headers, timeout=30,
                      json={'event_id': eid, 'user_id': vip.uid}).status_code == 201
    assert patch(vip, gid, {'status': 'no'}).json()[0]['status'] == 'no'


def test_an_insulting_name_is_refused_and_maybe_follows_the_event(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test présences filtre', allow_maybe=False)
    bad = post(admin, {'event_id': eid, 'name': 'Gros connard', 'status': 'yes'})
    assert bad.status_code >= 400 and 'connard' not in str(admin.get(f'{TABLE}?event_id=eq.{eid}').json())
    maybe = post(admin, {'event_id': eid, 'name': 'Julie', 'status': 'maybe'})
    assert maybe.status_code >= 400 and 'Peut-être' in maybe.text
    assert post(admin, {'event_id': eid, 'name': ' ', 'status': 'yes'}).status_code >= 400


def test_a_person_without_account_takes_a_place(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test présences places', max_participants=1)
    assert post(admin, {'event_id': eid, 'name': 'Pote Théo', 'status': 'yes'}).status_code == 201
    full = post(admin, {'event_id': eid, 'name': 'Une de trop', 'status': 'yes'})
    assert full.status_code >= 400 and 'complet' in full.text
    assert attendance(admin, eid)['going'] == 1
