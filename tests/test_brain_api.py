"""Méninges câblé au serveur : enregistrement d'une partie (compte connecté), profil, classement, mode local."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, brain, main

TOK_A, TOK_B, TOK_BANNED = 'a' * 40, 'b' * 40, 'c' * 40
TARGET = '407eb502-c0b8-45f3-8d3a-be471b72c4b5'
NEVER_PLAYED = '5d1f7f0e-3a1b-4c6e-9d2a-0b8e1c2d3f40'
UNKNOWN = '00000000-0000-4000-8000-000000000000'
ALICE = '9a8b7c6d-1111-4222-8333-444455556666'
PROFILES = {
    TARGET: {'temperature': 1100, 'domains': {'vitesse': 900, 'memoire': 1300, 'calcul': 700}, 'games': {'pareil': 900}},
    NEVER_PLAYED: {'temperature': 0, 'domains': {}, 'games': {}},
    ALICE: {'temperature': 1000, 'domains': {'vitesse': 1000}, 'games': {'pareil': 1000}},
}


class FakeBase:
    """Faux Supabase : jetons → comptes, et les fonctions brain_* tenues en mémoire."""

    def __init__(self):
        self.users = {TOK_A: ALICE, TOK_B: 'bob', TOK_BANNED: 'banni'}
        self.sessions: dict[str, list] = {}
        self.calls: list[tuple[str, dict]] = []
        self.party = None   # moyenne des autres joueurs par domaine (migration 20261102220000)

    def handler(self, request: httpx.Request):
        uid = self.users.get(request.headers['Authorization'].removeprefix('Bearer '))
        path = request.url.path
        if path == '/auth/v1/user':
            return httpx.Response(200, json={'id': uid}) if uid else httpx.Response(401, json={})
        body = json.loads(request.content or b'{}')
        self.calls.append((path, body))
        if uid == 'banni':
            return httpx.Response(400, json={'message': "forbidden: Ton compte n'a pas accès à Méninges."})
        if path == '/rest/v1/rpc/brain_record':
            rows = self.sessions.setdefault(uid, [])
            prev = max((r['score'] for r in rows if r['game'] == body['p_game']), default=None)
            rows.append({'game': body['p_game'], 'score': body['p_score'], 'accuracy': body['p_accuracy'],
                         'avg_rt_ms': body['p_avg_rt_ms'], 'level': body['p_level'], 'duration_ms': body['p_duration_ms'],
                         'played_at': '2026-11-02T18:00:00+00:00'})
            return httpx.Response(200, json={'index': brain.game_index(body['p_game'], body['p_score']),
                                             'best': max(prev or 0, body['p_score']), 'record': prev is None or body['p_score'] > prev,
                                             'plays': sum(r['game'] == body['p_game'] for r in rows)})
        if path == '/rest/v1/rpc/brain_my_stats':
            return httpx.Response(200, json={'sessions': self.sessions.get(uid, []), 'percentile': 75, 'players': 5,
                                             'party': self.party})
        if path == '/rest/v1/rpc/brain_compare':
            return httpx.Response(200, json={'board': [{'id': 'x', 'name': '<b>Bob</b>', 'temperature': 1200, 'me': False},
                                                       {'id': 'y', 'name': uid, 'temperature': 900, 'me': True}],
                                             'rank': 2, 'players': 2, 'percentile': 0,
                                             'target': {**PROFILES[body['p_target']], 'id': body['p_target'], 'name': ' <b>Bob</b> '}
                                             if body.get('p_target') in PROFILES else None})
        return httpx.Response(404)


@pytest.fixture
def setup(monkeypatch):
    base = FakeBase()
    acc = accounts_mod.Accounts(b'secret', httpx.Client(transport=httpx.MockTransport(base.handler)))
    monkeypatch.setattr(main, 'accounts', acc)
    monkeypatch.setattr(main, 'account_limiter', main.Limiter(per_ip=1000, ip_lock=1, global_max=10000, global_window=1, global_lock=1))
    with TestClient(main.app) as c:
        yield c, base


def result(**kw):
    return {'token': TOK_A, 'game': 'pareil', 'score': 9000, 'accuracy': 0.9, 'avg_rt_ms': 650, 'level': 3,
            'duration_ms': 45000, **kw}


def test_a_connected_player_saves_a_game(setup):
    c, base = setup
    r = c.post('/api/brain/result', json=result())
    assert r.status_code == 200
    assert r.json() == {'saved': True, 'index': 1000, 'best': 9000, 'record': True, 'plays': 1}
    assert base.calls[-1] == ('/rest/v1/rpc/brain_record', {'p_game': 'pareil', 'p_score': 9000, 'p_accuracy': 0.9,
                                                            'p_avg_rt_ms': 650, 'p_level': 3, 'p_duration_ms': 45000})
    second = c.post('/api/brain/result', json=result(score=5000)).json()
    assert second['record'] is False and second['best'] == 9000 and second['plays'] == 2


def test_the_server_bounds_the_score_before_the_database(setup):
    c, base = setup
    c.post('/api/brain/result', json=result(score=999_999))
    assert base.calls[-1][1]['p_score'] == brain.CATALOG['pareil'].max_score


def test_bad_results_are_refused(setup):
    c, base = setup
    assert c.post('/api/brain/result', json=result(game='pinball')).status_code == 400
    assert c.post('/api/brain/result', json=result(game='<script>')).status_code == 422
    assert c.post('/api/brain/result', json=result(accuracy=2)).status_code == 422
    assert c.post('/api/brain/result', json=result(duration_ms=200)).status_code == 400
    assert not base.calls


def test_a_session_needs_a_valid_account(setup):
    c, _ = setup
    assert c.post('/api/brain/result', json=result(token='x' * 40)).status_code == 401
    assert c.post('/api/brain/result', json=result(token='')).status_code == 422
    assert c.post('/api/brain/me', json={'token': 'x' * 40}).status_code == 401
    assert c.post('/api/brain/me', json={'token': 'court'}).status_code == 400
    refused = c.post('/api/brain/result', json=result(token=TOK_BANNED))
    assert refused.status_code == 400 and 'Méninges' in refused.json()['detail']


def test_me_returns_the_profile_of_this_account_only(setup):
    c, _ = setup
    c.post('/api/brain/result', json=result())
    c.post('/api/brain/result', json=result(token=TOK_B, game='grille', score=3000, duration_ms=60000))
    me = c.post('/api/brain/me', json={'token': TOK_A}).json()
    assert me['name'] == 'Méninges' and me['temperature'] == 1000 and me['percentile'] == 75
    assert me['games']['pareil']['plays'] == 1 and me['games']['grille']['plays'] == 0
    assert {"name", "temperature", "domains", "games", "streak", "history", "strengths", "weaknesses",
            "insight", "percentile", "speed_vs_accuracy", "month_progress"} <= set(me)
    assert {"domain_analysis", "recent_trend", "advice", "speed_profile", "month_progress_text", "warmup"} <= set(me)


def test_compare_lists_friends_and_a_target(setup):
    c, base = setup
    r = c.post('/api/brain/compare', json={'token': TOK_A, 'target': TARGET}).json()
    assert [p['temperature'] for p in r['board']] == [1200, 900] and r['board'][1]['me'] is True
    assert r['rank'] == 2 and r['target']['id'] == TARGET
    assert base.calls[-1] == ('/rest/v1/rpc/brain_compare', {'p_target': TARGET})
    assert ('/rest/v1/rpc/brain_my_stats', {}) in base.calls
    assert c.post('/api/brain/compare', json={'token': TOK_A, 'target': "x' or 1=1"}).status_code == 422
    assert c.post('/api/brain/compare', json={'token': TOK_A}).json()['target'] is None


def test_compare_with_a_member_domain_by_domain(setup):
    c, _ = setup
    c.post('/api/brain/result', json=result(score=12000))   # Vitesse (pareil) au-dessus du typique
    t = c.post('/api/brain/compare', json={'token': TOK_A, 'target': TARGET}).json()['target']
    assert t['name'] == '<b>Bob</b>' and t['self'] is False and t['played'] and t['me_played']
    assert t['temperature'] == 1100 and t['me_temperature'] > 1000
    rows = {r['domain']: r for r in t['rows']}
    assert list(rows) == ['vitesse', 'memoire', 'calcul']
    assert rows['vitesse']['them'] == 900 and rows['vitesse']['me'] > 1000 and rows['memoire']['me'] is None
    assert rows['vitesse']['label'] == 'Vitesse' and rows['vitesse']['icon'] == '⚡'
    assert t['verdict'].startswith('Tu devances <b>Bob</b> partout, surtout en Vitesse')
    assert set(t) == {'id', 'name', 'self', 'played', 'temperature', 'me_played', 'me_temperature', 'rows', 'verdict'}
    assert 'games' not in t and 'sessions' not in t   # agrégats seulement


def test_compare_with_a_member_who_never_played(setup):
    c, _ = setup
    c.post('/api/brain/result', json=result())
    t = c.post('/api/brain/compare', json={'token': TOK_A, 'target': NEVER_PLAYED}).json()['target']
    assert t['played'] is False and t['temperature'] == 0 and all(r['them'] is None for r in t['rows'])
    assert t['verdict'] == "<b>Bob</b> n'a pas encore joué à Méninges."


def test_compare_when_i_never_played(setup):
    c, _ = setup
    t = c.post('/api/brain/compare', json={'token': TOK_A, 'target': TARGET}).json()['target']
    assert t['me_played'] is False and t['me_temperature'] == 0 and t['played']
    assert t['verdict'] == 'Joue à Méninges pour te comparer à <b>Bob</b>.'


def test_compare_with_an_unknown_member_or_myself(setup):
    c, _ = setup
    assert c.post('/api/brain/compare', json={'token': TOK_A, 'target': UNKNOWN}).json()['target'] is None
    c.post('/api/brain/result', json=result())
    t = c.post('/api/brain/compare', json={'token': TOK_A, 'target': ALICE}).json()['target']
    assert t['self'] is True and t['verdict'].startswith("C'est toi")


def test_compare_verdict_names_where_each_one_is_strongest():
    v = brain.compare_verdict('Bob', {'vitesse': 1200, 'memoire': 800}, {'vitesse': 1000, 'memoire': 1100}, False)
    assert v == 'Ton point fort : Vitesse (+200 °M) ; celui de Bob : Mémoire (+300 °M).'
    assert brain.compare_verdict('Bob', {'vitesse': 900}, {'vitesse': 1400}, False).startswith('Bob te devance partout, surtout en Vitesse (+500')
    assert brain.compare_verdict('Bob', {'vitesse': 900}, {'vitesse': 900}, False).startswith('Égalité')
    assert brain.compare_verdict('Bob', {'vitesse': 900}, {'logique': 900}, False).startswith("Vous n'avez pas encore")


def test_local_profile_for_a_player_without_account(setup):
    c, base = setup
    sessions = [{'game': 'pareil', 'score': 9000, 'accuracy': 0.8, 'avg_rt_ms': 700, 'level': 2, 'duration_ms': 45000,
                 'played_at': '2026-11-02T10:00:00Z'}]
    r = c.post('/api/brain/local', json={'sessions': sessions})
    assert r.status_code == 200 and r.json()['games']['pareil']['index'] == 1000 and r.json()['percentile'] is None
    assert c.post('/api/brain/local', json={'sessions': sessions * (brain.LOCAL_MAX + 1)}).status_code == 422
    assert not base.calls


def test_catalog_route(setup):
    c, _ = setup
    cat = c.get('/api/brain/catalog').json()
    assert cat['name'] == 'Méninges' and {g['id'] for g in cat['games']} == set(brain.CATALOG)


def test_me_compares_each_domain_to_the_other_party_players(setup):
    c, base = setup
    for _ in range(3):
        c.post('/api/brain/result', json=result(score=14000))
        c.post('/api/brain/result', json=result(game='encre', score=9000))
    base.party = {'domains': {'vitesse': {'avg': 1000, 'players': 4}, 'flexibilite': {'avg': 900, 'players': 2}}}
    me = c.post('/api/brain/me', json={'token': TOK_A}).json()
    vitesse, flex = me['domain_analysis']['vitesse'], me['domain_analysis']['flexibilite']
    assert vitesse['party_avg'] == 1000 and vitesse['vs_party'] == vitesse['index'] - 1000 > 0
    assert flex['party_avg'] is None and flex['vs_party'] is None          # 2 joueurs seulement : pas de comparaison
    assert me['strengths'] == ['vitesse'] and 'moyenne Party' in me['insight']
    assert len(me['warmup']) == 5 and 1 <= len(me['advice']) <= 3


def test_me_ignores_a_malformed_party_payload(setup):
    c, base = setup
    for _ in range(3):
        c.post('/api/brain/result', json=result())
    base.party = {'domains': {'vitesse': {'avg': 'x', 'players': 9}, 'memoire': 'nope'}}
    me = c.post('/api/brain/me', json={'token': TOK_A})
    assert me.status_code == 200
    assert all(a['party_avg'] is None for a in me.json()['domain_analysis'].values())
