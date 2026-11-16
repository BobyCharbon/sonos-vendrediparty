"""Mode de paiement d'un événement (migration 20261115120000, maquette du 15.11), sur la VRAIE base de test :
« On me paie » et « Paiement en ligne » : la personne note « J'ai payé », l'organisateur confirme « Reçu ✓ » (jamais payé
sur la seule parole de la personne) ; le lien de l'événement part avec les infos de paiement ; « Sur place » refuse
« J'ai payé » ; en ligne exige un lien https.
Événement « sur invitation », sans annonce : seuls les comptes de test le voient.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_paiement_mode_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, complete_profile, create_event
from tests.supabase_live.test_event_tickets_live import answer, notes, ticket
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

LINK = 'https://revolut.me/test-party'


@pytest.fixture(scope='module')
def party():
    admin, a = Session(ADMIN), Session(GUEST_A)
    complete_profile(a, 'Guest A')
    eid = create_event(admin, 'Test mode de paiement', visibility='invited', notify_on_publish=False, price_chf=25)
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': a.uid}, timeout=30)
        assert r.status_code == 201, r.text
        answer(a, eid, 'yes')
        yield admin, a, eid
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def patch(admin, eid, **row):
    return httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, json=row, timeout=30)


def test_by_default_the_organizer_is_paid_and_confirms(party):
    admin, a, eid = party
    assert patch(admin, eid, payment_url=LINK).status_code in (200, 204)
    info = a.rpc('event_pay_info', e=eid).json()
    assert info['mode'] == 'organizer' and info['payment_url'] == LINK
    declared = a.rpc('declare_ticket_payment', e=eid, declared=True).json()
    assert declared['pay_pending'] is True and declared['paid'] is False
    assert any('confirme' in n['body'] for n in notes(admin, eid, 'ticket_pay_declared'))
    assert admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=True).json()['paid'] is True
    admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=False)


def test_online_needs_a_link_and_still_waits_for_the_organizer(party):
    admin, a, eid = party
    refused = patch(admin, eid, payment_mode='online', payment_url=None)
    assert refused.status_code == 400 and 'events_payment_online_url_check' in refused.text
    assert patch(admin, eid, payment_url='http://pas-sur.ch').status_code == 400
    assert patch(admin, eid, payment_mode='online', payment_url='https://billetterie.example.ch/paintball').status_code in (200, 204)
    assert a.rpc('event_pay_info', e=eid).json()['mode'] == 'online'
    a.rpc('declare_ticket_payment', e=eid, declared=False)
    declared = a.rpc('declare_ticket_payment', e=eid, declared=True).json()
    assert declared['pay_pending'] is True and declared['paid'] is False   # jamais payé sur sa seule parole
    assert any('en ligne' in n['body'] for n in notes(admin, eid, 'ticket_pay_declared'))
    assert admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=True).json()['paid'] is True
    admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=False)


def test_switching_to_on_site_lets_a_pending_payment_be_cancelled(party):
    """« J'ai payé » noté, puis l'organisateur passe en « Sur place » : la personne peut encore l'annuler (sinon elle
    reste « en attente de confirmation » pour toujours, l'organisateur n'ayant plus la liste des paiements à confirmer)."""
    admin, a, eid = party
    assert patch(admin, eid, payment_mode='organizer', payment_url=None).status_code in (200, 204)
    assert a.rpc('declare_ticket_payment', e=eid, declared=True).json()['pay_pending'] is True
    assert patch(admin, eid, payment_mode='on_site').status_code in (200, 204)
    r = a.rpc('declare_ticket_payment', e=eid, declared=False)
    assert r.status_code == 200, r.text
    assert r.json().get('pay_pending') is not True


def test_on_site_has_nothing_to_note(party):
    admin, a, eid = party
    assert patch(admin, eid, payment_mode='on_site', payment_url=None).status_code in (200, 204)
    a.rpc('declare_ticket_payment', e=eid, declared=False)
    r = a.rpc('declare_ticket_payment', e=eid, declared=True)
    assert r.status_code == 400 and 'sur place' in r.text
    assert ticket(a, eid).get('pay_pending') is not True


def test_a_guest_cannot_change_how_the_event_is_paid(party):
    """Revue du 15.11 : un invité ne détourne jamais le paiement (son propre lien, « sur place »…) ; jamais de javascript:."""
    admin, a, eid = party
    before = admin.get(f'events?id=eq.{eid}&select=payment_mode,payment_url').json()[0]
    r = httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers={**a.headers, 'Prefer': 'return=representation'},
                    json={'payment_mode': 'organizer', 'payment_url': 'https://revolut.me/pas-l-organisateur'}, timeout=30)
    assert r.status_code == 200 and r.json() == [], r.text  # aucune ligne modifiable (RLS)
    assert admin.get(f'events?id=eq.{eid}&select=payment_mode,payment_url').json()[0] == before
    assert patch(admin, eid, payment_mode='organizer', payment_url='javascript:alert(1)').status_code == 400
