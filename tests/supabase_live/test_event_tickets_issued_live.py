"""Billets QR remis par l'organisateur (migration 20261104233000), sur la VRAIE base de test (jamais la prod) :
option « Billets QR » éteinte par défaut, QR seulement quand l'option est active ET le billet remis, remise par les
gestionnaires seulement (un à un, à tous, ou par la place payée), scanner qui refuse un billet non remis, pass Wallet
refusé, notification « Ton billet est prêt » avec son propre interrupteur.
Événement « sur invitation », sans annonce : seuls les comptes de test le voient, aucun vrai membre n'est prévenu.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_event_tickets_issued_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile, create_event, make_vip
from tests.supabase_live.test_event_tickets_live import answer, notes, sql_test, ticket
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope='module')
def party():
    admin, a, b, vip = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    complete_profile(a, 'Guest A')
    complete_profile(b, 'Guest B')
    make_vip(admin, vip)
    eid = create_event(admin, 'Test billets remis', visibility='invited', notify_on_publish=False, price_chf=12)
    try:
        for who in (a, b, vip):
            r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': who.uid}, timeout=30)
            assert r.status_code == 201, r.text
        for who in (a, b, vip):
            answer(who, eid, 'yes')
        yield admin, a, b, vip, eid
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def option(who: Session, eid: str, enabled: bool) -> httpx.Response:
    return who.rpc('set_event_tickets', e=eid, enabled=enabled)


def token_of(eid: str, uid: str) -> str:
    return sql_test(f"select token from public.event_tickets where event_id = '{eid}' and user_id = '{uid}'")[0]['token']


def test_option_is_off_by_default_and_nobody_gets_a_qr(party):
    admin, a, b, vip, eid = party
    row = admin.get(f'events?select=tickets_enabled&id=eq.{eid}').json()[0]
    assert row['tickets_enabled'] is False
    mine = ticket(a, eid)
    assert mine['state'] == 'off' and 'token' not in mine and 'code' not in mine
    assert mine['price_chf'] == 12 and mine['paid'] is False  # payer reste possible, sans QR
    assert a.rpc('wallet_pass_issue', e=eid).status_code >= 400
    refused = admin.rpc('issue_event_ticket', e=eid, member=a.uid, issued=True)
    assert refused.status_code >= 400 and 'Active d' in refused.text


def test_only_managers_switch_the_option_and_hand_out_tickets(party):
    admin, a, b, vip, eid = party
    assert option(a, eid, True).status_code >= 400
    assert option(admin, eid, True).json() is True
    pending = ticket(a, eid)
    assert pending['state'] == 'pending' and 'token' not in pending
    assert a.rpc('wallet_pass_issue', e=eid).status_code >= 400
    assert a.rpc('issue_event_ticket', e=eid, member=a.uid, issued=True).status_code >= 400  # pas soi-même
    assert a.rpc('issue_all_event_tickets', e=eid).status_code >= 400
    given = admin.rpc('issue_event_ticket', e=eid, member=a.uid, issued=True).json()
    assert given['issued'] is True and given['issued_at'] and given['tickets_enabled'] is True
    ok = ticket(a, eid)
    assert ok['state'] == 'ok' and len(ok['token']) == 64 and ok['issued_at']
    told = notes(a, eid, 'ticket_issued')
    assert len(told) == 1 and 'Ton billet est prêt' in told[0]['body']
    assert a.rpc('wallet_pass_issue', e=eid).json()['valid'] is True


def test_scanner_refuses_a_ticket_taken_back_and_when_the_option_is_off(party):
    admin, a, b, vip, eid = party
    token = ticket(a, eid)['token']
    taken = admin.rpc('issue_event_ticket', e=eid, member=a.uid, issued=False).json()
    assert taken['issued'] is False
    assert ticket(a, eid)['state'] == 'pending'
    assert admin.rpc('check_in_ticket', e=eid, scanned=token).json()['result'] == 'not_issued'
    # Pass déjà dans Cartes : il devient « annulé ».
    pass_row = sql_test(f"select private.wallet_payload('{eid}', '{a.uid}') as p")[0]['p']
    assert pass_row['valid'] is False
    admin.rpc('issue_event_ticket', e=eid, member=a.uid, issued=True)
    assert option(admin, eid, False).json() is False
    assert admin.rpc('check_in_ticket', e=eid, scanned=token).json()['result'] == 'tickets_off'
    assert ticket(a, eid)['state'] == 'off'
    assert sql_test(f"select private.wallet_payload('{eid}', '{a.uid}') as p")[0]['p']['valid'] is False
    option(admin, eid, True)
    assert admin.rpc('check_in_ticket', e=eid, scanned=token).json()['result'] == 'ok'


def test_received_payment_hands_out_the_ticket(party):
    admin, a, b, vip, eid = party
    assert ticket(b, eid)['state'] == 'pending'
    assert b.rpc('declare_ticket_payment', e=eid, declared=True).json()['state'] == 'pending'  # payé, en attente
    done = admin.rpc('confirm_ticket_payment', e=eid, member=b.uid, received=True).json()
    assert done['paid'] is True and done['issued'] is True
    assert ticket(b, eid)['state'] == 'ok'
    assert any('Ton billet est prêt' in n['body'] for n in notes(b, eid, 'ticket_issued'))


def test_hand_out_to_all_and_the_switch_of_the_notification(party):
    admin, a, b, vip, eid = party
    assert admin.rpc('issue_all_event_tickets', e=eid).json() == 1  # seul le VIP attendait encore
    assert ticket(vip, eid)['state'] == 'ok'
    note_id = notes(vip, eid, 'ticket_issued')[-1]['id']

    def allowed() -> bool:
        return sql_test(f"select private.web_push_allowed(n) as ok from public.notifications n where id = '{note_id}'")[0]['ok']

    def prefs(**values):
        r = httpx.patch(f'{TEST_URL}/rest/v1/notification_prefs?user_id=eq.{vip.uid}', headers=vip.headers, timeout=30, json=values)
        assert r.status_code in (200, 204), r.text
    was = vip.get(f'notification_prefs?select=push_enabled&user_id=eq.{vip.uid}').json()[0]['push_enabled']
    try:
        prefs(push_enabled=True, ticket_issued=True)
        assert allowed() is True
        prefs(ticket_issued=False)
        assert allowed() is False
    finally:
        prefs(push_enabled=was, ticket_issued=True)


def test_paid_before_the_option_is_announced_when_switched_on(party):
    admin, a, b, vip, eid = party
    other = create_event(admin, 'Test billets payés avant', visibility='invited', notify_on_publish=False, price_chf=5)
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': other, 'user_id': a.uid}, timeout=30)
        assert r.status_code == 201, r.text
        answer(a, other, 'yes')
        assert admin.rpc('set_ticket_paid', e=other, member=a.uid, is_paid=True).json()['issued'] is True
        assert ticket(a, other)['state'] == 'off' and notes(a, other, 'ticket_issued') == []
        option(admin, other, True)
        assert ticket(a, other)['state'] == 'ok' and len(notes(a, other, 'ticket_issued')) == 1
        option(admin, other, False)
        option(admin, other, True)
        assert len(notes(a, other, 'ticket_issued')) == 1  # même remise : annoncée une seule fois
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{other}', headers=admin.headers, timeout=30)
