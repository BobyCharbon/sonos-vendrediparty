"""Avis 6bad207324a3 : « Quand une personne est dans un jeu mais s'inscrit en même temps, elle a deux profils. »
Se connecter à son compte Party en pleine soirée ne crée plus de deuxième profil : places de jeu, salle de jeux,
Purify Test, liste des invités de l'hôte, bannissement, titres demandés et notifications suivent le compte."""
import threading

import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, games, main, purity
from tests.test_features import FakeSonos, snap
from tests.test_purity_api import TOK_A, TOK_B, supabase_for

LULU = "5f0c2d3e-1a2b-4c3d-9e8f-0a1b2c3d4e5f"   # téléphone de Lulu, avant de se connecter (compte « alice »)
LEA = "7a1d3e4f-2b3c-4d5e-8f9a-1b2c3d4e5f60"
TOM = "9c2e4f5a-3c4d-4e6f-a0b1-2c3d4e5f6071"
ZOE = "b3d5f6a7-4d5e-4f70-b1c2-3d4e5f607182"


@pytest.fixture
def setup(monkeypatch, tmp_path):
    acc = accounts_mod.Accounts(b'secret', supabase_for({TOK_A: 'alice', TOK_B: 'bob'}))
    monkeypatch.setattr(main, 'accounts', acc)
    monkeypatch.setattr(main, 'account_limiter', main.Limiter(per_ip=1000, ip_lock=1, global_max=10000, global_window=1, global_lock=1))
    monkeypatch.setattr(purity, 'STATS_PATH', tmp_path / 'purity_stats.json')
    monkeypatch.setattr(main, '_game_creations', {})
    s = main.store.session
    for field in ('games', 'guests', 'bans', 'push', 'guest_notify', 'activity_start_tokens'):
        monkeypatch.setattr(s, field, {})
    monkeypatch.setattr(s, 'requests', [])
    monkeypatch.setattr(s, 'messages', [])
    with TestClient(main.app) as c:
        yield c, acc.gid('alice'), acc.gid('bob')


def create(c, kind, gid, name):
    return c.post('/api/games', json={'type': kind, 'guest_id': gid, 'name': name}).json()['code']


def act(c, code, gid, action, **kw):
    return c.post(f'/api/games/{code}', json={'guest_id': gid, 'action': action, **kw})


def link(c, token, guest_id):
    r = c.post('/api/account/link', json={'token': token, 'guest_id': guest_id})
    assert r.status_code == 200
    return r.json()['guest_id']


def view(c, code, gid, name=''):
    return c.get(f'/api/games/{code}', params={'guest_id': gid, 'name': name}).json()


def test_one_seat_after_signing_in_then_a_game_launched_from_the_room(setup):
    c, alice, _ = setup
    room = create(c, 'room', LULU, 'Lulu')
    act(c, room, LEA, 'join', name='Léa')
    assert link(c, TOK_A, LULU) == alice  # surnom du compte (« alice ») différent du prénom tapé (« Lulu »)
    r = main.store.session.games[room]
    assert [p['id'] for p in r['players']] == [alice, LEA] and r['host'] == alice
    assert act(c, room, alice, 'launch', settings={'type': 'quiz'}).status_code == 200
    child = r['current']
    ids = [p['id'] for p in main.store.session.games[child]['players']]
    assert sorted(ids) == sorted([alice, LEA])  # une seule place, au nom du compte
    me = view(c, child, alice, 'alice')['me']
    assert me and view(c, child, LULU, 'Lulu')['me']['pid'] == me['pid']  # onglet resté sur l'ancienne identité
    assert len(view(c, child, LULU, 'Lulu')['players']) == 2


def test_room_launch_takes_the_aliases_of_the_room(setup):
    c, alice, _ = setup
    room = create(c, 'room', LULU, 'Lulu')
    act(c, room, LEA, 'join', name='Léa')
    main.store.session.games[room]['aliases'] = {TOM: LEA}  # Léa a repris sa place depuis un autre appareil
    act(c, room, LULU, 'launch', settings={'type': 'undercover'})
    child = main.store.session.games[room]['current']
    assert act(c, child, TOM, 'join', name='Léa').status_code == 200
    assert len(main.store.session.games[child]['players']) == 2  # pas de deuxième place pour Léa


def test_purify_enrolls_the_signed_in_phone_and_keeps_its_stats_under_the_account(setup):
    c, alice, bob = setup
    link(c, TOK_A, 'anon-alice-0001')
    room = create(c, 'room', alice, 'Alice')
    act(c, room, LEA, 'join', name='Bob')
    assert link(c, TOK_B, LEA) == bob
    act(c, room, alice, 'launch', settings={'type': 'purity'})
    child = main.store.session.games[room]['current']
    assert {p['id'] for p in main.store.session.games[child]['players']} == {alice, bob}  # inscrit d'office
    act(c, child, alice, 'start')
    act(c, child, bob, 'puans', amount=0, done=True)
    act(c, child, LEA, 'pusub')  # onglet resté sur l'ancienne identité : il répond pour le compte
    act(c, child, alice, 'pusub')
    act(c, child, alice, 'pureveal')
    stats = purity._load_stats()
    assert bob in stats and LEA not in stats and stats[bob]['plays'] == 1


def test_purify_stats_of_a_seat_linked_by_alias_go_to_the_account(setup):
    _, alice, _ = setup
    g = games.new_game('purity', 'anon-old-id', 'Lulu', code='4300')  # identifiant atypique : alias seulement
    g['aliases'] = {alice: 'anon-old-id'}
    games.start(g)
    purity.answer(g, 'anon-old-id', 0, True)
    purity.submit(g, 'anon-old-id')
    games.purity_reveal(g)
    assert set(purity._load_stats()) == {alice}


def test_host_keeps_his_rights_after_signing_in(setup):
    c, alice, _ = setup
    code = create(c, 'undercover', LULU, 'Lulu')
    for gid, name in ((LEA, 'Léa'), (TOM, 'Tom')):
        act(c, code, gid, 'join', name=name)
    main.store.session.games[code]['leads'] = [LULU]
    link(c, TOK_A, LULU)
    g = main.store.session.games[code]
    assert g['host'] == alice and g['leads'] == [alice]
    assert act(c, code, alice, 'start').status_code == 200  # action d'animateur
    assert act(c, code, LULU, 'vote_start').status_code == 200  # ancien onglet : même place, mêmes droits
    assert act(c, code, LEA, 'vote_start').status_code == 403


def test_masque_secret_answer_and_guesses_survive_a_sign_in_mid_round(setup):
    c, alice, _ = setup
    code = create(c, 'masque', LULU, 'Lulu')
    for gid, name in ((LEA, 'Léa'), (TOM, 'Tom'), (ZOE, 'Zoé')):
        act(c, code, gid, 'join', name=name)
    act(c, code, LULU, 'start')
    texts = {LULU: "J'ai déjà mangé un insecte", LEA: "J'ai peur des pigeons", TOM: 'Je chante sous la douche',
             ZOE: 'Je dors avec une peluche'}
    for gid, text in texts.items():
        act(c, code, gid, 'mswrite', guess=text)
    g = main.store.session.games[code]
    lulu_pid = games.player(g, LULU)['pid']
    lulu_slot = next(i for i, s in enumerate(g['masque']['slots']) if s['gid'] == LULU)
    act(c, code, LEA, 'msguess', settings={'picks': {str(lulu_slot): lulu_pid}})  # Léa a deviné Lulu
    link(c, TOK_A, LULU)
    mine = view(c, code, alice, 'alice')['masque']
    # Sa réponse reste la sienne : absente de sa liste (rien ne la désigne à un voisin), les trois autres y sont.
    assert sorted(s['text'] for s in mine['slots']) == sorted(t for gid, t in texts.items() if gid != LULU)
    assert all(a['pid'] != lulu_pid for a in mine['authors'])
    for other in (LEA, TOM, ZOE):
        raw = c.get(f'/api/games/{code}', params={'guest_id': other}).text
        assert alice not in raw and LULU not in raw  # aucune identité secrète chez les autres
    act(c, code, alice, 'msguess', settings={'picks': {}, 'unmask': True})
    act(c, code, TOM, 'msguess', settings={'picks': {}})
    act(c, code, ZOE, 'msguess', settings={'picks': {}})
    row = next(r for r in view(c, code, LEA)['masque']['result'] if r.get('text') == texts[LULU])
    assert row['open'] and row['found'] == ['Léa']  # la devinette de Léa compte toujours


def test_guest_list_shows_one_entry_and_keeps_the_ban(setup):
    c, alice, _ = setup
    c.post('/api/presence', json={'guest_id': LULU, 'name': 'Lulu'})
    main.store.ban(LULU, None)
    code = create(c, 'undercover', LEA, 'Léa')
    main.store.session.games[code]['kicked'] = [LULU]  # banni aussi de cette partie
    link(c, TOK_A, LULU)
    guests = [g for g in main.store.guests() if g['guest_id'] != LEA]
    assert [g['guest_id'] for g in guests] == [alice] and guests[0]['ban'] == {'until': 0}
    assert main.ban_message(alice, '') is not None  # se connecter ne lève pas le bannissement
    assert alice in main.store.session.games[code]['kicked']
    assert act(c, code, alice, 'join', name='alice').status_code in (403, 409)


def test_push_subscription_and_notification_choices_follow_the_account(setup):
    c, alice, _ = setup
    sub = {'endpoint': 'https://push.example/1', 'keys': {'p256dh': 'k', 'auth': 'a'}}
    main.store.session.push[LULU] = [sub]
    main.store.session.guest_notify[LULU] = {'track': True}
    link(c, TOK_A, LULU)
    assert main.store.session.push == {alice: [sub]}
    assert main.store.session.guest_notify[alice] == {'track': True}


def test_two_simultaneous_sign_ins_leave_a_single_seat(setup):
    c, alice, _ = setup
    code = create(c, 'undercover', LULU, 'Lulu')
    act(c, code, LEA, 'join', name='Léa')
    errors = []

    def go():
        try:
            link(TestClient(main.app), TOK_A, LULU)
        except AssertionError as e:  # pragma: no cover - remonté plus bas
            errors.append(e)
    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    g = main.store.session.games[code]
    assert not errors and [p['id'] for p in g['players']] == [alice, LEA]
    assert g['aliases'] == {LULU: alice}


@pytest.fixture
def party(setup, monkeypatch):
    c, alice, _ = setup
    monkeypatch.setattr(main, 'sonos', FakeSonos())
    monkeypatch.setattr(main, 'snapshot', lambda force=False: snap())
    main.store.start('RINCON_X', 'Salon', 'next')
    guest = TestClient(main.app)
    assert guest.post('/api/join', json={'pin': main.store.session.guest_pin}).status_code == 200
    return c, guest, alice


def test_a_requested_track_can_still_be_removed_after_signing_in(party):
    c, guest, alice = party
    req = main.store.add({'id': 'a' * 22, 'title': 'Un', 'artist': 'A'}, LULU, 'Lulu')
    link(c, TOK_A, LULU)
    assert guest.post('/api/queue/remove', json={'request_id': req.id, 'guest_id': LULU}).status_code == 404
    assert guest.post('/api/queue/remove', json={'request_id': req.id, 'guest_id': alice}).status_code == 200
