import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, games, main


def fake_supabase(user_id='u-1', status='active', valid=True, beta=False, live=None, perms=()):
    calls = []
    def handler(request: httpx.Request):
        calls.append(request.url.path)
        assert request.headers['apikey'] == accounts_mod.SUPABASE_ANON_KEY
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': user_id}) if valid else httpx.Response(401, json={})
        if request.url.path == '/rest/v1/rpc/get_member_directory':
            return httpx.Response(200, json=[{'display_name': '  Lulu ', 'avatar_url': f'{user_id}/a.jpg', 'status': status}])
        if request.url.path == '/rest/v1/rpc/my_permissions':
            return httpx.Response(200, json=list(perms))
        if request.url.path == '/rest/v1/rpc/is_beta_tester':
            return httpx.Response(200, json=live['beta'] if live is not None else beta)
        if request.url.path.startswith('/storage/v1/object/sign/profile-photos/'):
            return httpx.Response(200, json={'signedURL': '/object/sign/profile-photos/x.jpg?token=t'})
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_link_is_stable_secret_cached_and_rejects_bad_or_banned_tokens():
    client, calls = fake_supabase()
    a = accounts_mod.Accounts(b'secret', client)
    first = a.link('token-' + 'x' * 30)
    assert first['name'] == 'Lulu' and first['guest_id'].startswith('acct-') and 'u-1' not in first['guest_id']
    assert first['photo'].endswith('/storage/v1/object/sign/profile-photos/x.jpg?token=t')
    assert first['beta'] is False and accounts_mod.Accounts(b'secret', fake_supabase(beta=True)[0]).link('b' * 40)['beta'] is True
    assert a.link('token-' + 'x' * 30) == first and calls.count('/auth/v1/user') == 1  # jeton vérifié une fois
    assert calls.count('/rest/v1/rpc/get_member_directory') == 2  # surnom relu : un changement de profil arrive tout de suite
    assert accounts_mod.Accounts(b'secret', fake_supabase()[0]).link('autre-jeton' + 'y' * 30)['guest_id'] == first['guest_id']
    assert a.photo(first['guest_id']) == first['photo']
    with pytest.raises(accounts_mod.AccountError):
        accounts_mod.Accounts(b'secret', fake_supabase(valid=False)[0]).link('t' * 40)
    with pytest.raises(accounts_mod.AccountError):
        accounts_mod.Accounts(b'secret', fake_supabase(status='banned')[0]).link('t' * 40)


def test_beta_checked_by_an_admin_is_seen_at_the_next_link_without_cache_delay():
    live = {'beta': False}
    client, calls = fake_supabase(live=live)
    a = accounts_mod.Accounts(b'secret', client)
    assert a.link('jeton-' + 'z' * 30)['beta'] is False
    live['beta'] = True  # case « 🧪 Bêta-testeur » cochée
    assert a.link('jeton-' + 'z' * 30)['beta'] is True
    assert calls.count('/auth/v1/user') == 1  # le jeton, lui, reste vérifié une seule fois


def test_api_link_moves_the_phone_seat_to_the_account_and_shows_the_photo(monkeypatch):
    client, _ = fake_supabase('u-2')
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', client))
    with TestClient(main.app) as c:
        code = c.post('/api/games', json={'type': 'undercover', 'guest_id': 'anon-phone-1', 'name': 'Lulu'}).json()['code']
        r = c.post('/api/account/link', json={'token': 'z' * 40, 'guest_id': 'anon-phone-1'})
        assert r.status_code == 200
        gid = r.json()['guest_id']
        v = c.get(f'/api/games/{code}', params={'guest_id': gid, 'name': 'Lulu'}).json()
        me = v['me']
        assert me and len(v['players']) == 1  # même place, pas de doublon
        assert v['players'][0]['photo'] == r.json()['photo']
        assert c.post('/api/account/link', json={'token': 'court'}).status_code == 400


ROOT_PERMS = ('party.admin', 'party.settings', 'games.lead_all', 'music.control')


def test_party_admin_needs_page_and_settings_rights():
    assert accounts_mod.Accounts(b'secret', fake_supabase(perms=ROOT_PERMS)[0]).is_party_admin('r' * 40) is True
    assert accounts_mod.Accounts(b'secret', fake_supabase(perms=('party.admin',))[0]).is_party_admin('r' * 40) is False  # co-admin par défaut
    assert accounts_mod.Accounts(b'secret', fake_supabase(perms=ROOT_PERMS)[0]).link('r' * 40)['admin'] is True
    assert accounts_mod.Accounts(b'secret', fake_supabase()[0]).link('r' * 40)['admin'] is False


def test_root_account_opens_the_admin_session_without_pin_and_leads_every_game(monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_PIN', '8462')
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', fake_supabase('root', perms=ROOT_PERMS)[0]))
    with TestClient(main.app) as c:
        assert c.get('/qr.svg').status_code == 401
        code = c.post('/api/games', json={'type': 'undercover', 'guest_id': 'anon-host', 'name': 'Alex'}).json()['code']
        assert c.post('/api/account/admin', json={'token': 'r' * 40}).status_code == 200
        assert c.get('/qr.svg').status_code == 200  # page admin ouverte, comme avec le code PIN
        root = c.post('/api/account/link', json={'token': 'r' * 40}).json()
        assert root['admin'] is True
        c.get(f'/api/games/{code}', params={'guest_id': root['guest_id'], 'name': root['name']})
        assert root['guest_id'] in main.store.session.games[code]['leads']  # animateur par défaut


def test_account_without_admin_rights_or_expired_gets_no_admin_session(monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_PIN', '8462')
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', fake_supabase('membre', perms=('events.view',))[0]))
    with TestClient(main.app) as c:
        r = c.post('/api/account/admin', json={'token': 'm' * 40})
        assert r.status_code == 403 and 'vp_admin' not in r.cookies
        assert c.get('/qr.svg').status_code == 401
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', fake_supabase(valid=False)[0]))
    with TestClient(main.app) as c:
        assert c.post('/api/account/admin', json={'token': 'x' * 40}).status_code == 401
        assert c.post('/api/account/admin', json={'token': 'court'}).status_code == 400
