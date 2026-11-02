"""Méninges : statistiques d'un jeu (écran de fin enrichi, fiche du jeu) — calcul, route compte, route locale,
et la migration du percentile par jeu."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, brain, brain_game, main

TOK = 'a' * 40
NOW = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
MIGRATION = (Path(__file__).resolve().parents[1] / 'supabase' / 'migrations' / '20261102240000_brain_game.sql').read_text(encoding='utf-8')


def session(game='pareil', score=9000, days_ago=0, **kw):
    return {'game': game, 'score': score, 'accuracy': 0.8, 'avg_rt_ms': 600, 'level': 2, 'duration_ms': 45000,
            'played_at': (NOW - timedelta(days=days_ago)).isoformat(), **kw}


def test_game_detail_sums_up_one_game_only():
    rows = [session(score=4000, days_ago=3, level=1, accuracy=0.5, avg_rt_ms=800),
            session(score=9000, days_ago=2, level=4, accuracy=1.0, avg_rt_ms=400),
            session(score=6000, days_ago=1, level=3, accuracy=None, avg_rt_ms=0),
            session(game='motif', score=50000)]
    d = brain_game.game_detail(rows, 'pareil', percentile=40, now=NOW)
    assert (d['plays'], d['best'], d['avg'], d['level'], d['last_level']) == (3, 9000, 6333, 4, 3)
    assert d['accuracy'] == 0.75 and d['avg_rt_ms'] == 600 and d['percentile'] == 40
    assert d['index'] == brain.round_half_up(sum(brain.raw_index('pareil', s) for s in (4000, 9000, 6000)) / 3)
    assert [h['score'] for h in d['history']] == [4000, 9000, 6000]
    assert d['history'][1] == {'day': '2026-10-31', 'score': 9000, 'index': 1000, 'level': 4}
    assert d['name'] == 'Pareil ?' and d['domain'] == 'vitesse'


def test_game_detail_empty_history_and_limits():
    empty = brain_game.game_detail([], 'grille', now=NOW)
    assert (empty['plays'], empty['best'], empty['avg'], empty['index'], empty['accuracy'], empty['avg_rt_ms']) == (0, 0, 0, 0, None, None)
    assert empty['history'] == []
    many = [session(score=i * 100, days_ago=0) for i in range(brain_game.GAME_HISTORY + 10)]
    assert len(brain_game.game_detail(many, 'pareil', now=NOW)['history']) == brain_game.GAME_HISTORY
    with pytest.raises(brain.BrainError):
        brain_game.game_detail([], 'pinball')


def test_a_phone_clock_ahead_still_counts_the_last_game():
    ahead = [session(score=9000, played_at=(NOW + timedelta(minutes=5)).isoformat())]
    assert brain_game.game_detail(ahead, 'pareil', now=NOW)['index'] == 1000


class FakeBase:
    def __init__(self, with_percentile=True):
        self.with_percentile = with_percentile
        self.calls = []

    def handler(self, request: httpx.Request):
        if request.headers['Authorization'].removeprefix('Bearer ') != TOK:
            return httpx.Response(401, json={})
        path = request.url.path
        if path == '/auth/v1/user':
            return httpx.Response(200, json={'id': 'alice'})
        body = json.loads(request.content or b'{}')
        self.calls.append((path, body))
        if path == '/rest/v1/rpc/brain_my_stats':
            return httpx.Response(200, json={'sessions': [session(score=5000, days_ago=1), session(score=8000)], 'percentile': 60})
        if path == '/rest/v1/rpc/brain_game_percentile' and self.with_percentile:
            return httpx.Response(200, json={'percentile': 75, 'players': 5})
        return httpx.Response(404, json={'message': 'Could not find the function'})


def client(monkeypatch, base):
    acc = accounts_mod.Accounts(b'secret', httpx.Client(transport=httpx.MockTransport(base.handler)))
    monkeypatch.setattr(main, 'accounts', acc)
    monkeypatch.setattr(main, 'account_limiter', main.Limiter(per_ip=1000, ip_lock=1, global_max=10000, global_window=1, global_lock=1))
    return TestClient(main.app)


def test_route_for_a_signed_in_member(monkeypatch):
    base = FakeBase()
    with client(monkeypatch, base) as c:
        r = c.post('/api/brain/game', json={'token': TOK, 'game': 'pareil'})
        assert r.status_code == 200, r.text
        d = r.json()
        assert (d['plays'], d['best'], d['avg'], d['percentile']) == (2, 8000, 6500, 75)
        assert [h['score'] for h in d['history']] == [5000, 8000]
        assert ('/rest/v1/rpc/brain_game_percentile', {'p_game': 'pareil'}) in base.calls
        assert c.post('/api/brain/game', json={'token': TOK, 'game': 'pinball'}).status_code == 400
        assert c.post('/api/brain/game', json={'token': TOK, 'game': "x' or 1=1"}).status_code == 422
        assert c.post('/api/brain/game', json={'token': 'z' * 40, 'game': 'pareil'}).status_code == 401


def test_route_works_before_the_migration_is_applied(monkeypatch):
    with client(monkeypatch, FakeBase(with_percentile=False)) as c:
        d = c.post('/api/brain/game', json={'token': TOK, 'game': 'pareil'}).json()
        assert d['plays'] == 2 and d['percentile'] is None


def test_local_route_computes_from_the_phone_sessions():
    with TestClient(main.app) as c:
        rows = [session(score=3000, days_ago=2), session(score=7000), session(game='motif')]
        d = c.post('/api/brain/game/local', json={'game': 'pareil', 'sessions': rows}).json()
        assert (d['plays'], d['best'], d['avg'], d['percentile']) == (2, 7000, 5000, None)
        assert d['index'] > 0
        assert c.post('/api/brain/game/local', json={'game': 'pinball', 'sessions': []}).status_code == 400
        assert c.post('/api/brain/game/local', json={'game': 'pareil', 'sessions': rows * brain.LOCAL_MAX}).status_code == 422


def test_migration_is_additive_and_locked_down():
    assert 'create or replace function public.brain_game_percentile(p_game text)' in MIGRATION
    assert 'security definer set search_path = \'\'' in MIGRATION
    assert 'revoke all on function public.brain_game_percentile(text) from public, anon;' in MIGRATION
    assert 'grant execute on function public.brain_game_percentile(text) to authenticated;' in MIGRATION
    for word in ('drop table', 'drop column', 'delete from', 'truncate', 'alter table'):
        assert word not in MIGRATION.lower()
