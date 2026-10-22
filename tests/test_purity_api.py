"""Purify Test câblé au serveur : création et participation réservées aux comptes Party,
actions de jeu, salle de jeux, classement général."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, games, main, purity


def supabase_for(users: dict[str, str]):
    """Faux Supabase : chaque jeton connu correspond à un utilisateur (jeton → identifiant Supabase)."""
    def handler(request: httpx.Request):
        token = request.headers['Authorization'].removeprefix('Bearer ')
        uid = users.get(token)
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': uid}) if uid else httpx.Response(401, json={})
        if request.url.path == '/rest/v1/rpc/get_member_directory':
            return httpx.Response(200, json=[{'display_name': uid, 'avatar_url': None, 'status': 'active'}])
        if request.url.path == '/rest/v1/rpc/my_permissions':
            return httpx.Response(200, json=[])
        if request.url.path == '/rest/v1/rpc/is_beta_tester':
            return httpx.Response(200, json=False)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


TOK_A, TOK_B = 'a' * 40, 'b' * 40
ONE_DONE = round(100 * (purity.TOTAL - 1) / purity.TOTAL)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    acc = accounts_mod.Accounts(b'secret', supabase_for({TOK_A: 'alice', TOK_B: 'bob'}))
    monkeypatch.setattr(main, 'accounts', acc)
    monkeypatch.setattr(main, 'account_limiter', main.Limiter(per_ip=1000, ip_lock=1, global_max=10000, global_window=1, global_lock=1))
    monkeypatch.setattr(purity, 'STATS_PATH', tmp_path / 'purity_stats.json')
    monkeypatch.setattr(main, '_game_creations', {})  # limite de créations par adresse : chaque test repart de zéro
    monkeypatch.setattr(main.store.session, 'games', {})  # ne pas laisser de parties aux tests suivants (30 au plus)
    with TestClient(main.app) as c:
        yield c, acc.gid('alice'), acc.gid('bob')


def create(c, gid, token=TOK_A, **kw):
    return c.post('/api/games', json={'type': 'purity', 'guest_id': gid, 'name': 'Alice', 'token': token, **kw})


def act(c, code, gid, action, **kw):
    return c.post(f'/api/games/{code}', json={'guest_id': gid, 'action': action, **kw})


def solo_round(c, code, gid):
    act(c, code, gid, 'start')
    act(c, code, gid, 'puans', amount=0, done=True)
    act(c, code, gid, 'pusub')
    return act(c, code, gid, 'pureveal')


def test_purity_is_a_registered_game():
    assert games.GAMES['purity'] == 'Purify Test'
    g = games.new_game('purity', 'acct-host-0001', 'Alice')
    assert g['purity'] == {'answers': {}, 'submitted': {}, 'scores': {}}


def test_creation_requires_a_verified_account(setup):
    c, alice, _ = setup
    assert create(c, 'anon-phone-0001', token='').status_code == 401
    assert create(c, alice, token='x' * 40).status_code == 401           # jeton refusé par Supabase
    assert create(c, 'anon-phone-0001', token=TOK_A).status_code == 403  # jeton d'un autre compte que la place
    r = create(c, alice)
    assert r.status_code == 200 and r.json()['type'] == 'purity' and r.json()['purity']['playing'] is True


def test_join_requires_the_token_of_that_account(setup):
    c, alice, bob = setup
    code = create(c, alice).json()['code']
    assert act(c, code, 'anon-phone-0002', 'join', name='Anon').status_code == 401
    assert act(c, code, bob, 'join', name='Bob').status_code == 401                # pas de jeton
    assert act(c, code, bob, 'join', name='Bob', token=TOK_A).status_code == 403   # jeton d'Alice
    assert act(c, code, 'acct-forged-000001', 'join', name='X', token=TOK_B).status_code == 403
    r = act(c, code, bob, 'join', name='Bob', token=TOK_B)
    assert r.status_code == 200 and len(r.json()['players']) == 2


def test_namesake_cannot_take_an_account_seat(setup):
    c, alice, bob = setup
    code = create(c, alice).json()['code']
    act(c, code, bob, 'join', name='Bob', token=TOK_B)
    # Un autre téléphone (sans compte) se nomme « Bob » : il ne reprend pas la place du compte de Bob.
    assert act(c, code, 'anon-phone-0003', 'join', name='Bob').status_code == 401
    assert 'anon-phone-0003' not in (main.store.session.games[code].get('aliases') or {})


def test_account_seats_are_never_reclaimed_by_name_in_any_game():
    g = games.new_game('whoof', 'anon-host-0001', 'Hôte')
    games.join(g, 'acct-' + 'f' * 40, 'Bob')
    assert main.reclaim_seat(g, 'anon-phone-0009', 'Bob', '') == 'anon-phone-0009'


def test_full_round_answers_stay_private_and_ranking_is_revealed(setup):
    c, alice, bob = setup
    code = create(c, alice).json()['code']
    act(c, code, bob, 'join', name='Bob', token=TOK_B)
    assert act(c, code, bob, 'start').status_code == 403  # réservé à l'animateur
    assert act(c, code, alice, 'start').json()['purity']['phase'] == 'answering'
    for i in range(10):
        assert act(c, code, bob, 'puans', amount=i, done=True).status_code == 200
    v = act(c, code, bob, 'puans', amount=3, done=False).json()['purity']
    assert v['answered'] == 9 and '3' not in v['mine'] and '0' in v['mine']
    assert act(c, code, bob, 'puans', amount=purity.TOTAL, done=True).status_code == 409
    # Alice ne voit jamais les cases de Bob.
    va = c.get(f'/api/games/{code}', params={'guest_id': alice}).json()
    assert va['purity']['mine'] == {} and va['purity']['count_submitted'] == 0
    act(c, code, bob, 'pusub')
    assert act(c, code, bob, 'puans', amount=20, done=True).status_code == 409  # réponses figées
    act(c, code, bob, 'puunsub')
    act(c, code, bob, 'pusub')
    act(c, code, alice, 'pusub')
    assert act(c, code, bob, 'pureveal').status_code == 403
    v = act(c, code, alice, 'pureveal').json()['purity']
    assert v['phase'] == 'results'
    assert [r['name'] for r in v['ranking']] == ['Alice', 'Bob']
    assert v['ranking'][0]['score'] == 100 and v['me_score'] == 100
    assert 'mine' not in v and 'questions' not in v
    assert [r['name'] for r in v['leaderboard']['rows']] == ['Alice', 'Bob']


def test_unrelated_actions_are_refused(setup):
    c, alice, _ = setup
    code = create(c, alice).json()['code']
    assert act(c, code, alice, 'spin').status_code == 400


def test_settings_and_sips_are_counted(setup):
    c, alice, bob = setup
    code = create(c, alice, sips=3).json()['code']
    g = main.store.session.games[code]
    assert g['options']['alcohol'] is True and g['options']['sips'] == 3
    assert act(c, code, bob, 'puset', settings={'sips': 5}).status_code == 403
    act(c, code, alice, 'puset', settings={'alcohol': True, 'sips': 4})
    act(c, code, bob, 'join', name='Bob', token=TOK_B)
    act(c, code, alice, 'start')
    act(c, code, bob, 'puans', amount=0, done=True)
    act(c, code, alice, 'pusub')
    act(c, code, bob, 'pusub')
    v = act(c, code, alice, 'pureveal').json()
    assert v['purity']['gorgees'] == [{'pid': v['purity']['ranking'][1]['pid'], 'name': 'Bob', 'sips': 4}]
    assert g['tally'][bob]['drink'] == 4
    assert act(c, code, alice, 'restart').json()['purity']['phase'] == 'answering'


def test_leaving_drops_private_answers(setup):
    c, alice, bob = setup
    code = create(c, alice).json()['code']
    act(c, code, bob, 'join', name='Bob', token=TOK_B)
    act(c, code, alice, 'start')
    act(c, code, bob, 'puans', amount=1, done=True)
    act(c, code, bob, 'pusub')
    act(c, code, bob, 'leave')
    p = main.store.session.games[code]['purity']
    assert bob not in p['answers'] and bob not in p['submitted']


def test_general_leaderboard_endpoint(setup):
    c, alice, _ = setup
    solo_round(c, create(c, alice).json()['code'], alice)
    lb = c.get('/api/purity/leaderboard').json()
    assert lb['total'] == 1 and lb['rows'][0]['best'] == ONE_DONE
    assert alice not in str(lb)  # l'identifiant secret du compte ne fuit pas


def test_admin_summary_shows_scores_not_answers(setup):
    c, alice, _ = setup
    code = create(c, alice).json()['code']
    solo_round(c, code, alice)
    s = games.summary(main.store.session.games[code])
    assert any('Le plus pur' in f for f in s['facts'])
    assert s['players_detail'][0]['extra'] == f"{ONE_DONE} % pur"


def room_with(c, alice, bob):
    room = c.post('/api/games', json={'type': 'room', 'guest_id': alice, 'name': 'Alice'}).json()['code']
    c.post('/api/account/link', json={'token': TOK_A})
    c.post('/api/account/link', json={'token': TOK_B})
    act(c, room, bob, 'join', name='Bob')
    act(c, room, 'anon-phone-0004', 'join', name='Anon')
    return room


def test_room_launch_enrolls_only_linked_accounts_and_merges_the_winner(setup):
    c, alice, bob = setup
    room = room_with(c, alice, bob)
    assert act(c, room, alice, 'launch', settings={'type': 'purity'}).status_code == 200
    child_code = main.store.session.games[room]['current']
    child = main.store.session.games[child_code]
    assert {p['id'] for p in child['players']} == {alice, bob}
    # Un nouveau venu sans compte dans la salle n'est pas inscrit au test en cours.
    act(c, room, 'anon-phone-0005', 'join', name='Zoé')
    assert games.player(child, 'anon-phone-0005') is None
    act(c, child_code, alice, 'start')
    act(c, child_code, bob, 'puans', amount=0, done=True)
    act(c, child_code, alice, 'pusub')
    act(c, child_code, bob, 'pusub')
    act(c, child_code, alice, 'pureveal')
    act(c, child_code, alice, 'end')
    r = main.store.session.games[room]
    assert r['current'] is None and r['rhistory'][-1]['winner'] == 'Alice'


def test_room_launch_of_purity_requires_a_linked_animator(setup):
    c, _, _ = setup
    room = c.post('/api/games', json={'type': 'room', 'guest_id': 'anon-host-0001', 'name': 'Hôte'}).json()['code']
    assert act(c, room, 'anon-host-0001', 'launch', settings={'type': 'purity'}).status_code == 403
