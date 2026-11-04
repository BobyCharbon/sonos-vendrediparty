"""Billets et paiements (migration 20261105120000), sur la VRAIE base de test (jamais la prod) : « Pas reçu » ou
« payé » décoché retire le billet remis PAR CE PAIEMENT (pas un billet remis à la main), et un co-organisateur sans droit
de modifier un événement publié active ou coupe quand même l'option « Billets QR » (et rien d'autre).
Événements « sur invitation », sans annonce : seuls les comptes de test les voient, aucun vrai membre n'est prévenu.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_billets_paiement_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, create_event
from tests.supabase_live.test_event_tickets_live import answer, notes, sql_test, ticket
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope='module')
def party():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    complete_profile(a, 'Guest A')
    complete_profile(b, 'Guest B')
    eid = create_event(admin, 'Test billets et paiements', visibility='invited', notify_on_publish=False, price_chf=10)
    try:
        for who in (a, b):
            r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': who.uid}, timeout=30)
            assert r.status_code == 201, r.text
            answer(who, eid, 'yes')
        assert admin.rpc('set_event_tickets', e=eid, enabled=True).json() is True
        yield admin, a, b, eid
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def test_not_received_takes_back_the_ticket_given_by_the_payment(party):
    admin, a, b, eid = party
    paid = admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=True).json()
    assert paid['issued'] is True and paid['issued_by_payment'] is True
    assert ticket(a, eid)['state'] == 'ok'
    back = admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=False).json()
    assert back['paid'] is False and back['issued'] is False and back['issued_by_payment'] is False
    assert ticket(a, eid)['state'] == 'pending'
    told = notes(a, eid, 'ticket_pay_confirmed')
    assert 'ton billet est retiré' in told[-1]['body']


def test_unchecking_paid_takes_back_the_ticket_given_by_the_payment(party):
    admin, a, b, eid = party
    assert admin.rpc('set_ticket_paid', e=eid, member=a.uid, is_paid=True).json()['issued'] is True
    off = admin.rpc('set_ticket_paid', e=eid, member=a.uid, is_paid=False).json()
    assert off['issued'] is False and ticket(a, eid)['state'] == 'pending'


def test_a_ticket_given_by_hand_stays_when_the_payment_is_cancelled(party):
    admin, a, b, eid = party
    given = admin.rpc('issue_event_ticket', e=eid, member=b.uid, issued=True).json()
    assert given['issued'] is True and given['issued_by_payment'] is False
    admin.rpc('set_ticket_paid', e=eid, member=b.uid, is_paid=True)
    kept = admin.rpc('confirm_ticket_payment', e=eid, member=b.uid, received=False).json()
    assert kept['paid'] is False and kept['issued'] is True
    assert ticket(b, eid)['state'] == 'ok'
    assert 'billet est retiré' not in notes(b, eid, 'ticket_pay_confirmed')[-1]['body']


ROLE = 'test_billets'


@pytest.fixture()
def co_organizer(party):
    """Membre du groupe (events.view) SANS le droit de modifier un événement publié, co-organisateur de l'événement :
    rôle de test créé pour l'occasion, retiré à la fin (le compte VIP de test revient à Guest)."""
    admin, a, b, eid = party
    vip = Session(VIP)
    complete_profile(vip, 'VIP test')
    sql_test(f"insert into public.roles (key, label, rank) values ('{ROLE}', 'Test billets', 90) on conflict (key) do nothing; "
             f"insert into public.role_permissions (role, perm) values ('{ROLE}', 'events.view') on conflict do nothing; "
             f"update public.profiles set role = '{ROLE}' where id = '{vip.uid}'; "
             f"insert into public.event_organizers (event_id, user_id) values ('{eid}', '{vip.uid}') on conflict do nothing; select 1")
    try:
        yield vip
    finally:
        sql_test(f"delete from public.event_organizers where event_id = '{eid}' and user_id = '{vip.uid}'; "
                 f"update public.profiles set role = 'guest' where id = '{vip.uid}'; delete from public.roles where key = '{ROLE}'; select 1")


def test_a_co_organizer_switches_tickets_after_publication_but_nothing_else(party, co_organizer):
    admin, a, b, eid = party
    vip = co_organizer
    assert b.rpc('set_event_tickets', e=eid, enabled=False).status_code >= 400  # pas organisateur
    switched = vip.rpc('set_event_tickets', e=eid, enabled=False)
    assert switched.status_code == 200, switched.text
    assert switched.json() is False
    assert vip.rpc('set_event_tickets', e=eid, enabled=True).json() is True
    # La garde reste entière pour le reste : le titre d'un événement publié ne change pas.
    r = httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers={**vip.headers, 'Prefer': 'return=representation'},
                    json={'title': 'Titre changé par un co-organisateur', 'tickets_enabled': False}, timeout=30)
    row = admin.get(f'events?select=title,tickets_enabled&id=eq.{eid}').json()[0]
    assert row == {'title': 'Test billets et paiements', 'tickets_enabled': True}, r.text
