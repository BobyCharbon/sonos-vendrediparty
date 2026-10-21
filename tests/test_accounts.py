import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, games, main


def fake_supabase(user_id='u-1', status='active', valid=True, beta=False):
    calls = []
    def handler(request: httpx.Request):
        calls.append(request.url.path)
        assert request.headers['apikey'] == accounts_mod.SUPABASE_ANON_KEY
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': user_id}) if valid else httpx.Response(401, json={})
        if request.url.path == '/rest/v1/rpc/get_member_directory':
            return httpx.Response(200, json=[{'display_name': '  Lulu ', 'avatar_url': f'{user_id}/a.jpg', 'status': status}])
        if request.url.path == '/rest/v1/rpc/is_beta_tester':
            return httpx.Response(200, json=beta)
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
