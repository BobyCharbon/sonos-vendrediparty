"""Billets dans Cartes Apple (Wallet) qui se mettent à jour, sur la VRAIE base de test (jamais la prod) :
jeton propre au pass, appareils inscrits avec ce jeton seulement, date de modification à chaque changement
(arrivée, paiement, nouveau QR, événement modifié, plus présent → pass annulé), push réservés aux bons comptes.
Le serveur Party (app/wallet_tickets.py) est branché sur la base de test, avec de faux certificats ; le push APNs
est simulé. Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_wallet_live.py -q"""
import time
from unittest import mock

import httpx
import pytest

from app import accounts as accounts_mod, wallet_tickets
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, complete_profile, create_event
from tests.supabase_live.test_event_tickets_live import answer, ticket
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.test_wallet import FakeApns, fake_signer_dir, open_pass
from app.wallet_push import WalletPush

DEVICE = 'livetestdevice01'
PUSH = 'ab' * 32


def anon(name: str, key: str, **args):
    """Appel sans session, comme le serveur pour l'iPhone."""
    r = httpx.post(f'{TEST_URL}/rest/v1/rpc/{name}', headers={'apikey': key, 'Content-Type': 'application/json'}, json=args, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope='module')
def party():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    complete_profile(a, 'Guest A')
    complete_profile(b, 'Guest B')
    # Sur invitation, sans notification : seuls les comptes de test le voient, personne n'est prévenu (conftest).
    eid = create_event(admin, 'Test billets Wallet', visibility='invited', notify_on_publish=False, price_chf=15,
                       location_name='Chez Boby')
    try:
        for who in (a, b):
            r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': who.uid}, timeout=30)
            assert r.status_code == 201, r.text
        answer(a, eid, 'yes')
        answer(b, eid, 'maybe')
        yield admin, a, b, eid
    finally:  # même si la mise en place échoue : la base de test ne garde rien (pass, appareils : en cascade)
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def issue(who: Session, eid: str) -> dict:
    r = who.rpc('wallet_pass_issue', e=eid)
    assert r.status_code == 200, r.text
    return r.json()


def updated_at(key: str, p: dict) -> str:
    return anon('wallet_pass_by_token', key, tok=p['auth_token'], serial=p['serial'])['updated_at']


def test_only_a_present_guest_gets_a_pass_with_a_stable_token(party):
    admin, a, b, eid = party
    mine = issue(a, eid)
    assert mine['valid'] is True and mine['serial'] == f'{eid}.{a.uid}' and len(mine['auth_token']) == 64
    assert mine['ticket']['token'] == ticket(a, eid)['token'] and mine['holder'] == 'Guest A'
    assert issue(a, eid)['auth_token'] == mine['auth_token']  # même pass à chaque ajout
    refused = b.rpc('wallet_pass_issue', e=eid)  # peut-être : pas de billet
    assert refused.status_code >= 400 and 'Présent' in refused.text
    # Tables fermées, même pour un admin.
    assert admin.get(f'wallet_passes?event_id=eq.{eid}').status_code in (401, 403)
    assert admin.get('wallet_devices').status_code in (401, 403)


def test_the_iphone_reads_and_registers_only_with_the_pass_token(party):
    admin, a, b, eid = party
    p = issue(a, eid)
    key = a.key
    assert anon('wallet_pass_by_token', key, tok='0' * 64, serial=p['serial']) is None
    assert anon('wallet_pass_by_token', key, tok=p['auth_token'], serial=f'{eid}.{b.uid}') is None  # pas le pass d'un autre
    assert anon('wallet_pass_by_token', key, tok=p['auth_token'], serial=p['serial'])['ticket']['code'] == ticket(a, eid)['code']
    assert anon('wallet_register', key, tok='0' * 64, serial=p['serial'], device=DEVICE, push=PUSH) == 'unauthorized'
    assert anon('wallet_register', key, tok=p['auth_token'], serial=p['serial'], device=DEVICE, push=PUSH) == 'created'
    assert anon('wallet_register', key, tok=p['auth_token'], serial=p['serial'], device=DEVICE, push=PUSH) == 'exists'
    listing = anon('wallet_updated_serials', key, device=DEVICE)
    assert listing['serials'] == [p['serial']]
    assert anon('wallet_updated_serials', key, device=DEVICE, since=listing['last_updated'])['serials'] == []
    assert anon('wallet_updated_serials', key, device='autreappareil')['serials'] == []


def test_every_change_dates_the_pass(party):
    admin, a, b, eid = party
    p = issue(a, eid)
    key = a.key
    steps = [
        lambda: admin.rpc('check_in_ticket', e=eid, scanned=ticket(a, eid)['token']),       # arrivée scannée
        lambda: admin.rpc('confirm_ticket_payment', e=eid, member=a.uid, received=True),     # paiement confirmé
        lambda: a.rpc('renew_event_ticket', e=eid),                                          # nouveau QR
        lambda: httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, json={'location_name': 'Ailleurs'}, timeout=30),
    ]
    for step in steps:
        before = updated_at(key, p)
        time.sleep(0.05)
        r = step()
        assert r.status_code < 300, r.text
        assert updated_at(key, p) > before
        assert anon('wallet_updated_serials', key, device=DEVICE, since=before)['serials'] == [p['serial']]
    now = anon('wallet_pass_by_token', key, tok=p['auth_token'], serial=p['serial'])
    assert now['ticket']['checked_in_at'] and now['ticket']['paid'] is True
    assert now['ticket']['token'] == ticket(a, eid)['token'] and now['event']['location_name'] == 'Ailleurs'


def test_push_targets_follow_the_rights(party):
    admin, a, b, eid = party
    assert a.rpc('wallet_push_targets', e=eid, member=a.uid).json() == [PUSH]  # son propre pass
    assert admin.rpc('wallet_push_targets', e=eid).json() == [PUSH]           # l'organisateur : tout l'événement
    assert b.rpc('wallet_push_targets', e=eid, member=a.uid).status_code >= 400  # pas les pass des autres
    assert b.rpc('wallet_push_targets', e=eid).status_code >= 400


def test_server_builds_the_real_updated_pass_and_pushes(party, tmp_path):
    admin, a, b, eid = party
    p = issue(a, eid)
    base = accounts_mod.Accounts(b's' * 32, httpx.Client(timeout=30))
    apns = FakeApns()
    with mock.patch.object(wallet_tickets, 'SUPABASE_URL', TEST_URL), mock.patch.object(wallet_tickets, 'SUPABASE_ANON_KEY', a.key), \
            mock.patch.object(accounts_mod, 'SUPABASE_URL', TEST_URL), mock.patch.object(accounts_mod, 'SUPABASE_ANON_KEY', a.key):
        tickets = wallet_tickets.WalletTickets(base, fake_signer_dir(tmp_path / 'w'), push=WalletPush(apns.client()))
        data, modified = tickets.latest(p['auth_token'], p['serial'], 'https://partytest.bobycharbon.ch')
        pass_json, _, _ = open_pass(data)
        assert pass_json['serialNumber'] == p['serial'] and 'voided' not in pass_json
        assert pass_json['barcodes'][0]['message'].endswith(f"&ticket={ticket(a, eid)['token']}")
        assert tickets.notify(tickets.push_targets(admin.headers['Authorization'][7:], eid, a.uid)) == 1
    assert apns.requests[0].headers['apns-topic'] == 'pass.ch.bobycharbon.party.ticket'


def test_no_longer_present_voids_the_pass_and_unregister_works(party):
    admin, a, b, eid = party
    p = issue(a, eid)
    key = a.key
    answer(a, eid, 'no')
    assert anon('wallet_pass_by_token', key, tok=p['auth_token'], serial=p['serial'])['valid'] is False
    assert anon('wallet_unregister', key, tok='0' * 64, serial=p['serial'], device=DEVICE) is False
    assert anon('wallet_unregister', key, tok=p['auth_token'], serial=p['serial'], device=DEVICE) is True
    assert anon('wallet_updated_serials', key, device=DEVICE)['serials'] == []
