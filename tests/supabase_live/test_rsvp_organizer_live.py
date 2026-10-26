"""Présences gérées par l'organisateur, sur la VRAIE base de test (jamais la prod) : l'organisateur (ou un admin) note
quelqu'un Présent / Absent, même après la date limite ; la personne est prévenue et peut répondre elle-même ensuite.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, create_event, make_vip
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


def rsvp(s: Session, event: str, member: str) -> dict | None:
    rows = s.get(f'rsvps?select=status,set_by,plus_ones&event_id=eq.{event}&user_id=eq.{member}').json()
    return rows[0] if rows else None


def notified(s: Session, event: str) -> list[str]:
    return [n['body'] for n in s.get(f'notifications?select=body&kind=eq.rsvp_set&event_id=eq.{event}&order=created_at').json()]


@pytest.fixture(scope='module')
def world():
    admin, ga, gb, vip = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    make_vip(admin, vip)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ids = {'publique': create_event(admin, 'Test présences', public_link=True),
           'close': create_event(admin, 'Test présences après la date limite', public_link=True, rsvp_deadline=past),
           'invités': create_event(admin, 'Test présences sur invitation', visibility='invited')}
    r = httpx.post(f'{TEST_URL}/rest/v1/event_organizers', headers=admin.headers, timeout=30,
                   json={'event_id': ids['publique'], 'user_id': vip.uid})
    assert r.status_code == 201, r.text
    yield admin, ga, gb, vip, ids
    for eid in ids.values():
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'guest'}, timeout=30)


def test_an_organizer_marks_someone_present_then_absent_and_the_person_is_told(world):
    admin, ga, gb, vip, ids = world
    assert vip.rpc('set_rsvp_for', event=ids['publique'], member=ga.uid, answer='yes').status_code == 204
    assert rsvp(ga, ids['publique'], ga.uid) == {'status': 'yes', 'set_by': vip.uid, 'plus_ones': 0}
    assert vip.rpc('set_rsvp_for', event=ids['publique'], member=ga.uid, answer='no').status_code == 204
    assert rsvp(ga, ids['publique'], ga.uid)['status'] == 'no'
    assert notified(ga, ids['publique']) == ['VIP test t\'a noté présent', 'VIP test t\'a noté absent']


def test_the_person_answering_again_takes_the_answer_back(world):
    admin, ga, gb, vip, ids = world
    assert vip.rpc('set_rsvp_for', event=ids['publique'], member=gb.uid, answer='no').status_code == 204
    r = httpx.patch(f"{TEST_URL}/rest/v1/rsvps?event_id=eq.{ids['publique']}&user_id=eq.{gb.uid}", headers=gb.headers,
                    json={'status': 'yes'}, timeout=30)
    assert r.status_code in (200, 204), r.text
    assert rsvp(gb, ids['publique'], gb.uid)['set_by'] is None


def test_nobody_can_pretend_the_organizer_set_their_answer(world):
    admin, ga, gb, vip, ids = world
    r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=ga.headers, timeout=30,
                   json={'event_id': ids['close'], 'user_id': ga.uid, 'status': 'yes', 'set_by': admin.uid})
    assert r.status_code >= 400  # date limite passée pour la personne elle-même
    assert ga.rpc('set_rsvp_for', event=ids['publique'], member=ga.uid, answer='yes').status_code >= 400  # pas organisateur


def test_the_organizer_still_fixes_attendance_after_the_deadline(world):
    admin, ga, gb, vip, ids = world
    assert admin.rpc('set_rsvp_for', event=ids['close'], member=ga.uid, answer='yes').status_code == 204
    assert rsvp(ga, ids['close'], ga.uid)['status'] == 'yes'
    assert admin.rpc('set_rsvp_for', event=ids['close'], member=ga.uid, answer=None).status_code == 204
    assert rsvp(admin, ids['close'], ga.uid) is None
    assert notified(ga, ids['close'])[-1] == 'Admin test a retiré ta réponse'


def test_marking_someone_present_on_an_invitation_only_event_invites_them(world):
    admin, ga, gb, vip, ids = world
    assert gb.get(f"events?select=id&id=eq.{ids['invités']}").json() == []
    assert admin.rpc('set_rsvp_for', event=ids['invités'], member=gb.uid, answer='yes').status_code == 204
    assert gb.get(f"events?select=id&id=eq.{ids['invités']}").json() != []


def test_party_reads_with_the_guest_own_token_whether_it_is_marked_present(world, monkeypatch):
    """Ce que fait le serveur Party pour entrer sans code (app/accounts.py), contre la vraie base de test."""
    from app import accounts as accounts_mod
    admin, ga, gb, vip, ids = world
    monkeypatch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    monkeypatch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', ga.key)
    party = accounts_mod.Accounts(b'secret')
    token = ga.headers['Authorization'].removeprefix('Bearer ')
    assert vip.rpc('set_rsvp_for', event=ids['publique'], member=ga.uid, answer='yes').status_code == 204
    assert party.attending(token, ids['publique']) == (ga.uid, True)
    assert vip.rpc('set_rsvp_for', event=ids['publique'], member=ga.uid, answer='no').status_code == 204
    assert party.attending(token, ids['publique']) == (ga.uid, False)
    assert any(e['id'] == ids['publique'] for e in party.upcoming_events(token))
