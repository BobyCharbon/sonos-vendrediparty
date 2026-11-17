"""« Paiement ouvert » prévient les participants (17.11.2026, migration 20261117135000), sur la VRAIE base de test :
l'organisateur allume « Paiement ouvert » → chaque « Présent » qui n'a pas encore payé reçoit « 💳 Le paiement est ouvert »
(une seule fois : éteindre puis rallumer ne renvoie rien) ; l'organisateur peut choisir de ne prévenir personne ; « Sur place » ne prévient personne ; jamais l'organisateur.
Événement « sur invitation », sans annonce : seuls les comptes de test le voient.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_paiement_ouvert_notification_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, complete_profile, create_event
from tests.supabase_live.test_event_tickets_live import answer
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

TITLE = '💳 Le paiement est ouvert'


def patch(admin, eid, **row):
    r = httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, json=row, timeout=30)
    assert r.status_code in (200, 204), r.text


def sent(eid: str) -> list[dict]:
    return sql(f"select user_id::text, body from public.notifications where event_id = '{eid}' and title = '{TITLE}'")


@pytest.fixture
def event():
    admin, a = Session(ADMIN), Session(GUEST_A)
    complete_profile(a, 'Guest A')
    eid = create_event(admin, 'Test paiement ouvert', visibility='invited', notify_on_publish=False, price_chf=20, payment_open=False)
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': a.uid}, timeout=30)
        assert r.status_code == 201, r.text
        answer(a, eid, 'yes')
        yield admin, a, eid
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def test_opening_the_payment_tells_the_participants_once(event):
    admin, a, eid = event
    assert sent(eid) == []
    patch(admin, eid, payment_open=True)
    rows = sent(eid)
    assert [r['user_id'] for r in rows] == [a.uid], rows  # le participant, jamais l'organisateur
    assert 'Test paiement ouvert' in rows[0]['body'] and 'payer ta place' in rows[0]['body']
    patch(admin, eid, payment_open=False)
    patch(admin, eid, payment_open=True)
    assert len(sent(eid)) == 1  # une seule fois


def test_paying_on_site_tells_nobody(event):
    admin, _, eid = event
    patch(admin, eid, payment_mode='on_site')
    patch(admin, eid, payment_open=True)
    assert sent(eid) == []


def test_the_organizer_can_choose_not_to_notify(event):
    admin, _, eid = event
    patch(admin, eid, payment_open_notify=False)
    patch(admin, eid, payment_open=True)
    assert sent(eid) == []
