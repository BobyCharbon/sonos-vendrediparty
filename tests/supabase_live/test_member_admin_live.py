"""Tests de bout en bout sur la VRAIE base de test Supabase (jamais la prod) : connexions par code fixe
(numéros de test, aucun SMS), vrais jetons, vraies règles d'accès.

Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q
Clé publique de la base de test lue dans ~/.config/supabase-claude/test-publishable-key (hors dépôt)."""
import os
import time
from pathlib import Path

import httpx
import pytest

TEST_URL = 'https://ewromqfsmcqsthftyhzm.supabase.co'  # Vendrediparty-test, jamais la prod
KEY_FILE = Path.home() / '.config/supabase-claude/test-publishable-key'
ROOT_PHONE = '41765576900'
GUESTS = ['41790000001', '41790000002', '41790000003']
OTP = '123456'

pytestmark = pytest.mark.skipif(not (os.environ.get('SUPABASE_LIVE_TESTS') and KEY_FILE.exists()),
                                reason='SUPABASE_LIVE_TESTS=1 et la clé de la base de test sont nécessaires')


class Session:
    def __init__(self, phone: str):
        self.key = KEY_FILE.read_text().strip()
        base = {'apikey': self.key, 'Content-Type': 'application/json'}
        for _ in range(3):  # un code par minute et par numéro (limite anti-abus d'Auth)
            sent = httpx.post(f'{TEST_URL}/auth/v1/otp', headers=base, json={'phone': phone}, timeout=30)
            if sent.status_code != 429:
                break
            time.sleep(31)
        assert sent.status_code == 200, sent.text
        r = httpx.post(f'{TEST_URL}/auth/v1/verify', headers=base, json={'type': 'sms', 'phone': phone, 'token': OTP}, timeout=30)
        assert r.status_code == 200, r.text
        self.uid = r.json()['user']['id']
        self.headers = {**base, 'Authorization': f"Bearer {r.json()['access_token']}"}

    def rpc(self, name: str, **args) -> httpx.Response:
        return httpx.post(f'{TEST_URL}/rest/v1/rpc/{name}', headers=self.headers, json=args, timeout=30)

    def get(self, path: str) -> httpx.Response:
        return httpx.get(f'{TEST_URL}/rest/v1/{path}', headers=self.headers, timeout=30)

    def set_nickname(self, name: str):
        r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{self.uid}', headers=self.headers, json={'display_name': name}, timeout=30)
        assert r.status_code in (200, 204), r.text


@pytest.fixture(scope='module')
def root():
    s = Session(ROOT_PHONE)
    assert s.uid == '298ff6e0-07b2-4127-bb69-d254dd63a3d5'  # même identifiant que le root de la prod
    assert s.rpc('my_rank').json() == 99
    return s


@pytest.fixture(scope='module')
def guests():
    sessions = [Session(p) for p in GUESTS]
    for i, s in enumerate(sessions):
        s.set_nickname(f'Testeur {i + 1}')
    return sessions


def test_a_new_sms_account_is_a_guest_and_cannot_read_the_members_or_the_journal(guests):
    g = guests[0]
    assert g.rpc('my_rank').json() == 0  # Guest
    assert g.rpc('admin_member_list').status_code in (400, 401, 403)
    assert g.rpc('admin_member_audit').status_code in (400, 401, 403)
    assert g.get('member_audit?select=id').status_code in (401, 403, 404)  # table invisible depuis l'app


def test_root_sees_every_signup_with_connections_and_the_view_is_logged(root, guests):
    r = root.rpc('admin_member_list')
    assert r.status_code == 200, r.text
    rows = {p['id']: p for p in r.json()}
    for g in guests:
        u = rows[g.uid]
        assert u['role'] == 'guest' and u['phone'] == GUESTS[guests.index(g)]
        assert u['first_sign_in_at'] and u['last_sign_in_at'] and u['sign_in_count'] >= 1
    journal = root.rpc('admin_member_audit', lim=200).json()
    assert any(e['action'] == 'members.viewed' and e['actor'] == root.uid for e in journal)
    assert any(e['action'] == 'account.login' and e['target'] == guests[0].uid for e in journal)


def test_root_deletes_a_guest_only_with_the_right_nickname_and_it_is_logged(root, guests):
    victim = guests[2]
    bad = root.rpc('admin_delete_member', member=victim.uid, confirm_name='Pas lui')
    assert bad.status_code >= 400 and 'confirm' in bad.text
    assert guests[0].rpc('admin_delete_member', member=victim.uid, confirm_name='Testeur 3').status_code >= 400  # un Guest ne peut pas
    ok = root.rpc('admin_delete_member', member=victim.uid, confirm_name='  testeur 3 ')
    assert ok.status_code in (200, 204), ok.text
    assert victim.uid not in {p['id'] for p in root.rpc('admin_member_list').json()}
    gone = [e for e in root.rpc('admin_member_audit', member=victim.uid).json() if e['action'] == 'account.deleted']
    assert gone and gone[0]['actor'] == root.uid and gone[0]['target_name'] == 'Testeur 3'
    assert gone[0]['details']['by'] == 'admin' and gone[0]['details']['phone_end'] == GUESTS[2][-2:]


def test_root_cannot_be_deleted_and_root_cannot_delete_itself(root, guests):
    assert root.rpc('admin_delete_member', member=root.uid, confirm_name='Boby').status_code >= 400
    assert guests[0].rpc('admin_delete_member', member=root.uid, confirm_name='Boby').status_code >= 400


def test_role_and_beta_changes_by_root_are_logged(root, guests):
    g = guests[1]
    assert root.rpc('set_beta_tester', member=g.uid, enabled=True).status_code in (200, 204)
    assert root.rpc('set_beta_tester', member=g.uid, enabled=False).status_code in (200, 204)
    actions = [e['action'] for e in root.rpc('admin_member_audit', member=g.uid).json()]
    assert actions[:2] == ['member.beta', 'member.beta']
