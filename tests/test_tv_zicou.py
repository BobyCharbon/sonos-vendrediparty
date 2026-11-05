"""Les Zicou de la soirée sur l'Apple TV (décision G, 04.11.2026) : /api/tv/zicou liste les Zicou des PRÉSENTS de la
soirée liée à un événement ET des joueurs avec compte de la partie regardée (même sans événement lié), chacun une
fois — aspect seulement (stade, humeur, tenue, shiny), surnom modéré ou rien, aucune donnée privée — et dit quelle
place (pid) chacun occupe dans la partie regardée (figure de victoire du gagnant)."""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod
from app import games, main, pet, tv_zicou

EVENT = '32f18a3b-827f-4123-8cf4-33de06c9a51c'
NOW = datetime.now(timezone.utc)


def token(who: str) -> str:
    return f'jeton-{who}-' + 'x' * 30


def life(stage_age_h: float = 30, **extra) -> dict:
    """Un Zicou né il y a `stage_age_h` heures (éclos 3 min après), avec un nom libre privé et des jauges."""
    born = datetime.now(timezone.utc) - timedelta(hours=stage_age_h)   # pas NOW : un œuf éclot en 3 min
    out = pet.new_life(born, name='NomPrivéDuZicou')
    return {**out, **extra}


@pytest.fixture
def party(monkeypatch):
    # Comptes : uid → surnom, présence, Zicou (None : pas de Zicou).
    people = {
        'lea': {'name': 'Léa', 'rsvp': 'yes', 'pet': life(30, shiny=True, acc={'head': 'couronne', 'facets': 'facettes-or'})},
        'tom': {'name': 'www.pub-casino.com', 'rsvp': 'yes', 'pet': life(0.01)},   # surnom refusé, Zicou encore œuf
        'max': {'name': 'Max', 'rsvp': 'yes', 'pet': None},                          # pas de Zicou
        'sam': {'name': 'Sam', 'rsvp': 'no', 'pet': life(100)},                       # pas présent
    }
    calls = []

    def who(request: httpx.Request) -> str:
        return request.headers['Authorization'].split('-')[1]

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path, request.content))
        uid = who(request)
        p = people[uid]
        if request.url.path == '/auth/v1/user':
            return httpx.Response(200, json={'id': uid})
        if request.url.path == '/rest/v1/rsvps':
            return httpx.Response(200, json=[{'status': p['rsvp'], 'waitlisted': False}])
        if request.url.path == '/rest/v1/rpc/get_member_directory':
            return httpx.Response(200, json=[{'status': 'active', 'display_name': p['name']}])
        if request.url.path == '/rest/v1/rpc/pet_load':
            saved = {'life': p['pet'], 'owner': pet.new_owner(), 'version': 3} if p['pet'] else None
            return httpx.Response(200, json={'pet': saved, 'gifts': [], 'brain': [], 'coins': []})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', client))
    monkeypatch.setattr(main, 'soiree_zicous', tv_zicou.SoireeZicous())
    monkeypatch.setattr(main.store, 'session', main.store.session)
    monkeypatch.setattr(main.store.session, 'active', True)
    monkeypatch.setattr(main.store.session, 'event_id', EVENT)
    monkeypatch.setattr(main.store.session, 'event_title', 'Vendredi chez Ludo')
    monkeypatch.setattr(main.store.session, 'event_passes', {})
    monkeypatch.setattr(main.store.session, 'games', {})
    monkeypatch.setattr(main, '_game_creations', {})   # limite de créations par adresse : propre à chaque test
    with TestClient(main.app) as host, TestClient(main.app) as phone:
        assert host.post('/api/admin/login', json={'pin': '9999'}).status_code == 200
        yield host, phone, people, calls


def join_all(phone, *names):
    for n in names:
        phone.cookies.clear()
        phone.post('/api/join/account', json={'token': token(n)})


def test_only_the_host_screen_reads_the_dancing_zicous(party):
    host, phone, _, _ = party
    assert phone.get('/api/tv/zicou').status_code == 401
    assert host.get('/api/tv/zicou').json() == {'zicous': [], 'count': 0, 'star': None, 'star_waiting': 0, 'salon': []}


def test_only_present_accounts_with_a_zicou_dance(party):
    host, phone, _, _ = party
    join_all(phone, 'lea', 'tom', 'max', 'sam')
    data = host.get('/api/tv/zicou').json()
    assert data['count'] == 2   # Léa et Tom ; Max n'a pas de Zicou ; Sam n'est pas présent
    by_stage = {z['stage']: z for z in data['zicous']}
    lea, tom = by_stage['teen'], by_stage['egg']
    assert lea['name'] == 'Léa' and lea['shiny'] is True
    assert lea['acc'] == {'head': 'couronne', 'facets': 'facettes-or'}
    assert lea['emotion'] in ('happy', 'party', 'sleep', 'tired', 'hungry', 'sad', 'sick') and lea['variant'] in pet.VARIANTS
    assert tom['name'] is None   # surnom refusé par la modération : rien plutôt qu'un texte libre


def test_nothing_private_reaches_the_tv(party):
    host, phone, _, _ = party
    join_all(phone, 'lea', 'tom')
    raw = host.get('/api/tv/zicou').text
    data = json.loads(raw)
    for z in data['zicous']:
        assert set(z) == {'key', 'name', 'stage', 'emotion', 'variant', 'acc', 'shiny', 'dye', 'pid'}
    for secret in ('NomPrivéDuZicou', 'lea', 'tom', 'acct-', 'food', 'joy', 'owner', 'www.pub-casino.com'):
        assert secret not in raw.replace('"name": "Léa"', '').replace('Léa', ''), secret


def test_the_pet_is_only_read_never_saved_and_no_opening_is_counted(party):
    host, phone, _, calls = party
    join_all(phone, 'lea')
    rpcs = [(path, body) for method, path, body in calls if path.startswith('/rest/v1/rpc/pet')]
    assert [p for p, _ in rpcs] == ['/rest/v1/rpc/pet_load']
    assert json.loads(rpcs[0][1])['p_src'] is None
    join_all(phone, 'lea')   # revérification 2 min plus tard (ici tout de suite) : pas relu avant 90 s
    assert sum(1 for _, p, _ in calls if p == '/rest/v1/rpc/pet_load') == 1


def test_a_guest_marked_absent_disappears_from_the_tv(party):
    host, phone, people, _ = party
    join_all(phone, 'lea', 'tom')
    assert host.get('/api/tv/zicou').json()['count'] == 2
    people['tom']['rsvp'] = 'no'
    join_all(phone, 'tom')
    assert host.get('/api/tv/zicou').json()['count'] == 1
    main.store.session.active = False   # la soirée est finie : plus personne ne danse
    assert host.get('/api/tv/zicou').json()['count'] == 0


def test_a_dead_zicou_does_not_dance(party):
    host, phone, people, _ = party
    people['lea']['pet'] = {**life(30), 'stage': 'dead', 'died_at': pet.iso(NOW)}
    join_all(phone, 'lea')
    assert host.get('/api/tv/zicou').json()['count'] == 0


def test_the_tv_knows_which_seat_each_zicou_holds_in_the_watched_game(party):
    host, phone, _, _ = party
    join_all(phone, 'lea', 'tom')
    code = host.post('/api/games', json={'type': 'never', 'guest_id': 'anon-host-0001', 'name': 'Hôte'}).json()['code']
    g = main.store.session.games[code]
    games.join(g, main.accounts.gid('lea'), 'Léa')
    pid = next(p['pid'] for p in g['players'] if p['name'] == 'Léa')
    data = host.get(f'/api/tv/zicou?game={code}').json()
    lea = next(z for z in data['zicous'] if z['name'] == 'Léa')
    assert lea['pid'] == pid
    assert all(z['pid'] is None for z in data['zicous'] if z is not lea)   # Tom ne joue pas
    assert host.get('/api/tv/zicou?game=abcd').status_code == 422


def link_all(phone, *names):
    """L'app relie le compte (ouverture, retour au premier plan) : /api/account/link, avec ou sans événement lié."""
    for n in names:
        phone.cookies.clear()
        assert phone.post('/api/account/link', json={'token': token(n), 'guest_id': ''}).status_code == 200


def new_game(host, *names) -> str:
    code = host.post('/api/games', json={'type': 'never', 'guest_id': 'anon-host-0001', 'name': 'Hôte'}).json()['code']
    g = main.store.session.games[code]
    for n in names:
        games.join(g, main.accounts.gid(n), n.capitalize())
    return code


def test_players_with_an_account_dance_even_without_a_linked_event(party):
    host, phone, _, _ = party
    main.store.session.event_id = None   # soirée sans événement lié : aucun présent
    link_all(phone, 'sam', 'max')        # Sam (pas présent) a un Zicou ; Max n'en a pas
    code = new_game(host, 'sam', 'max')
    games.join(main.store.session.games[code], 'guest-sans-compte', 'Invité')   # un invité sans compte : rien
    data = host.get(f'/api/tv/zicou?game={code}').json()
    assert data['count'] == 1 and data['zicous'][0]['name'] == 'Sam'
    sam_pid = next(p['pid'] for p in main.store.session.games[code]['players'] if p['name'] == 'Sam')
    assert data['zicous'][0]['pid'] == sam_pid
    assert host.get('/api/tv/zicou').json()['count'] == 0   # pas de partie regardée : Sam ne joue à rien


def test_a_present_player_is_shown_once(party):
    host, phone, _, _ = party
    join_all(phone, 'lea', 'tom')
    link_all(phone, 'lea', 'sam')
    code = new_game(host, 'lea', 'sam')
    data = host.get(f'/api/tv/zicou?game={code}').json()
    names = sorted(z['name'] or '' for z in data['zicous'])
    assert names == ['', 'Léa', 'Sam'] and data['count'] == 3   # Léa présente ET joueuse : une seule fois ; Tom, Sam
    assert len({z['key'] for z in data['zicous']}) == 3


def test_a_player_who_left_the_watched_game_stops_dancing(party):
    host, phone, _, _ = party
    main.store.session.event_id = None
    link_all(phone, 'sam')
    code = new_game(host, 'sam')
    assert host.get(f'/api/tv/zicou?game={code}').json()['count'] == 1
    other = new_game(host)
    assert host.get(f'/api/tv/zicou?game={other}').json()['count'] == 0


def test_linking_reads_the_zicou_only_while_a_soiree_is_open_and_at_most_every_90s(party):
    host, phone, _, calls = party
    link_all(phone, 'sam', 'sam')
    assert sum(1 for _, p, _ in calls if p == '/rest/v1/rpc/pet_load') == 1
    main.store.session.active = False
    link_all(phone, 'lea')
    assert sum(1 for _, p, _ in calls if p == '/rest/v1/rpc/pet_load') == 1


def test_tv_name_is_moderated_and_short():
    assert tv_zicou.tv_name('  Léa   la  Reine ') == 'Léa la Reine'
    assert tv_zicou.tv_name('https://exemple.ch') is None
    assert tv_zicou.tv_name('') is None and tv_zicou.tv_name(None) is None
    assert len(tv_zicou.tv_name('A' * 50)) == tv_zicou.NAME_MAX
