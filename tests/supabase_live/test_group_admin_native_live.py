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


def test_member_settings_routes_through_the_real_app():
    """Toutes les routes des Réglages natifs, par l'app FastAPI elle-même (rien de remplacé) : un membre
    lit son profil, ses notifications, ses groupes, ses abonnements ; l'administration lui répond sans planter."""
    from fastapi.testclient import TestClient

    from app import main
    patch = pytest.MonkeyPatch()
    patch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    patch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    patch.setattr(ga, 'SUPABASE_URL', TEST_URL)
    try:
        token = Session(GUESTS[0]).headers['Authorization'].removeprefix('Bearer ')
        client = TestClient(main.app)
        for path in ('/api/account/profile', '/api/account/notifications', '/api/account/groups',
                     '/api/account/subscriptions', '/api/account/group-admin'):
            r = client.post(path, json={'token': token})
            assert r.status_code == 200, (path, r.text)
        assert client.post('/api/account/profile', json={'token': token}).json()['display_name']
        assert client.post('/api/account/group-admin/journal', json={'token': token}).status_code == 400
    finally:
        patch.undo()


def test_native_sign_in_reads_and_sign_out_through_the_real_app():
    """Connexion native par code SMS (numéro de test), lectures des Réglages, puis déconnexion : la session
    rendue est celle que supabase-js lirait (même forme, clé du projet de test)."""
    from fastapi.testclient import TestClient

    from app import main
    patch = pytest.MonkeyPatch()
    patch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    patch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    patch.setattr(ga, 'SUPABASE_URL', TEST_URL)
    try:
        client = TestClient(main.app)
        for _ in range(3):
            sent = client.post('/api/account/otp', json={'phone': '+' + ADMIN_PHONE})
            if sent.status_code != 400 or 'Trop' not in sent.text:
                break
            import time
            time.sleep(31)
        assert sent.status_code == 200, sent.text
        out = client.post('/api/account/verify', json={'phone': '+' + ADMIN_PHONE, 'code': '123456'}).json()
        assert out['storage_key'] == 'sb-ewromqfsmcqsthftyhzm-auth-token'
        token = out['session']['access_token']
        assert out['session']['refresh_token'] and out['session']['user']['id']
        assert client.post('/api/account/verify', json={'phone': '+' + ADMIN_PHONE, 'code': '000000'}).status_code == 400
        assert 'announcements' in client.post('/api/account/announcements', json={'token': token}).json()
        tax = client.post('/api/account/group-admin/taxonomy', json={'token': token}).json()
        assert tax['categories'] and 'tags' in tax
        members = client.post('/api/account/group-admin/members', json={'token': token}).json()
        assert all('sign_in_count' in p for p in members['people'])
        assert client.post('/api/account/logout', json={'token': token}).json() == {'ok': True}
    finally:
        patch.undo()


def test_only_guest_plus_and_above_write_feedback(monkeypatch, tmp_path, request):
    """« Ton avis » sur la vraie base de test : Guest refusé, Guest+ et Admin acceptés. 41790000002 passe Guest+
    le temps du test (par l'admin, comme dans Membres), puis redevient Guest."""
    from fastapi.testclient import TestClient

    from app import main
    from app.feedback import FeedbackBox
    monkeypatch.setattr(accounts_mod, 'SUPABASE_URL', TEST_URL)
    monkeypatch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    monkeypatch.setattr(main, 'feedback', FeedbackBox(tmp_path / 'feedback.json'))
    client = TestClient(main.app)
    text = 'Un mode équipe au Quiz, avec deux camps'
    tokens = {phone: Session(phone).headers['Authorization'].removeprefix('Bearer ') for phone in (GUESTS[0], GUESTS[1], ADMIN_PHONE)}
    admin = ga.GroupAdmin(accounts_mod.Accounts(b'secret'))
    plus_id = next(p['id'] for p in admin.members(tokens[ADMIN_PHONE])['people'] if p['phone'] == GUESTS[1])
    admin.update_member(tokens[ADMIN_PHONE], plus_id, 'guestplus', None, None)
    request.addfinalizer(lambda: admin.update_member(tokens[ADMIN_PHONE], plus_id, 'guest', None, None))
    send = lambda phone: client.post('/api/feedback', json={'guest_id': f'live-{phone}-0001', 'name': 'Test', 'kind': 'idea',  # noqa: E731
                                                           'text': text, 'token': tokens[phone]})
    assert send(GUESTS[0]).status_code == 403          # Guest
    assert send(GUESTS[1]).status_code == 200          # Guest+
    assert send(ADMIN_PHONE).status_code == 200        # Admin
    assert client.post('/api/account/link', json={'token': tokens[GUESTS[1]], 'guest_id': 'live-plus-0001'}).json()['feedback'] is True
    assert client.post('/api/account/link', json={'token': tokens[GUESTS[0]], 'guest_id': 'live-guest-0001'}).json()['feedback'] is False
