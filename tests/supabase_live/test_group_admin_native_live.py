"""Administration du groupe native (app/group_admin.py) contre la VRAIE base de test : lectures et refus réels.

Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import pytest

from app import accounts as accounts_mod, group_admin as ga
from tests.supabase_live.test_member_admin_live import ADMIN_PHONE, GUESTS, KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope='module')
def admin_and_token():
    patch = pytest.MonkeyPatch()
    patch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    patch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    patch.setattr(ga, 'SUPABASE_URL', TEST_URL)
    s = Session(ADMIN_PHONE)
    yield ga.GroupAdmin(accounts_mod.Accounts(b'secret')), s.headers['Authorization'].removeprefix('Bearer ')
    patch.undo()


def test_admin_reads_every_native_screen(admin_and_token):
    admin, token = admin_and_token
    overview = admin.overview(token)
    assert overview['rank'] == 4 and isinstance(overview['require_approval'], bool)
    members = admin.members(token)
    assert members['full'] and any(p['root'] for p in members['people'])
    assert all(p['photo'] is None or p['photo'].startswith(TEST_URL) for p in members['people'])
    roles = admin.roles(token)
    assert 'admin' not in roles['editable'] and 'basic' in roles['editable'] and roles['catalog']
    journal = admin.journal(token, None, None)
    assert journal['entries'] and all(e['text'] for e in journal['entries'])
    older = admin.journal(token, None, journal['entries'][-1]['id'])
    assert all(e['id'] < journal['entries'][-1]['id'] for e in older['entries'])


def test_guest_gets_refusals_not_data():
    patch = pytest.MonkeyPatch()
    patch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    patch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    try:
        s = Session(GUESTS[0])
        admin = ga.GroupAdmin(accounts_mod.Accounts(b'secret'))
        token = s.headers['Authorization'].removeprefix('Bearer ')
        assert admin.overview(token)['events'] == []
        with pytest.raises(accounts_mod.AccountError):
            admin.journal(token, None, None)
        with pytest.raises(accounts_mod.AccountError):
            admin.set_permission(token, 'member', 'events.approve', True)
        with pytest.raises(accounts_mod.AccountError):
            admin.update_member(token, ga.ROOT_ID, None, 'banned', None)
    finally:
        patch.undo()
