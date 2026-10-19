"""Arcade rules and transport boundaries, with a deterministic simulation clock."""
import json
import math

import pytest
from fastapi.testclient import TestClient
from app import games, main, neon


def arena(n=2, duo=False):
    g = games.new_game('neon', 'neon-player-0', 'J0', code='7842')
    for i in range(1, n):
        games.join(g, f'neon-player-{i}', f'J{i}')
    if duo:
        neon.configure(g, {'mode': 'duo'})
    games.start(g)
    return g


def advance(g, seconds):
    target = g['neon']['clock'] + seconds
    while g['phase'] in ('play', 'countdown') and target - g['neon']['clock'] >= neon.STEP:
        neon.tick(g, min(target, g['neon']['clock'] + .1))


def test_two_players_countdown_and_private_identifiers():
    g = arena()
    assert g['phase'] == 'countdown'
    advance(g, 3.1)
    assert g['phase'] == 'play'
    v = games.view(g, 'neon-player-0')
    assert v['neon']['me'] == g['players'][0]['pid']
    assert 'neon-player-' not in json.dumps(v)
    assert 'seen' not in json.dumps(v['neon'])


@pytest.mark.parametrize('n', [2, 3, 5, 7])
def test_duos_require_complete_teams(n):
    with pytest.raises(neon.NeonError):
        arena(n, duo=True)


@pytest.mark.parametrize('n', [4, 6, 8])
def test_valid_duos_and_shared_colors(n):
    g = arena(n, duo=True)
    fighters = neon.view(g, '')['fighters']
    assert len({b['group'] for b in fighters}) == n//2
    assert fighters[0]['group'] == fighters[1]['group']
    assert fighters[0]['color'] == fighters[1]['color']


def test_full_arena_and_no_mid_match_team_change():
    g = arena(8)
    with pytest.raises(games.GameError):
        games.join(g, 'ninth-player', 'Nine')
    with pytest.raises(neon.NeonError):
        neon.team(g, 'neon-player-0', 2)
    with pytest.raises(neon.NeonError):
        games.start(g)


def test_cannot_overfill_duo_and_spectator_cannot_choose_team():
    g = games.new_game('neon', 'neon-player-0', 'J0')
    for i in range(1, 4):
        games.join(g, f'neon-player-{i}', f'J{i}')
    neon.configure(g, {'mode': 'duo'})
    with pytest.raises(neon.NeonError):
        neon.team(g, 'neon-player-2', 0)
    with pytest.raises(neon.NeonError):
        neon.team(g, 'spectator-id', 3)


def test_movement_is_normalized_and_stale_input_stops():
    g = arena(); advance(g, 3.1)
    b = next(iter(g['neon']['bodies'].values()))
    neon.input_state(g, 'neon-player-0', 100, 100, False, g['neon']['clock'])
    assert math.hypot(b['ix'], b['iy']) == pytest.approx(1)
    advance(g, .2)
    assert 0 < math.hypot(b['vx'], b['vy']) <= 5.3
    advance(g, 1)
    assert b['ix'] == b['iy'] == 0
    assert math.hypot(b['vx'], b['vy']) < .1


def test_server_times_charge_and_cooldown():
    g = arena(); advance(g, 3.1)
    s = g['neon']; b = next(iter(s['bodies'].values()))
    for _ in range(14):
        neon.input_state(g, 'neon-player-0', 1, 0, True, s['clock'])
        advance(g, .1)
    neon.input_state(g, 'neon-player-0', 1, 0, False, s['clock'])
    assert b['pulse'] == 1 and b['vx'] == pytest.approx(26)
    neon.input_state(g, 'neon-player-0', 1, 0, True, s['clock'])
    neon.input_state(g, 'neon-player-0', 1, 0, False, s['clock'])
    assert b['pulse'] == 1


def test_charged_collision_pushes_opponent_off_edge():
    g = arena(); advance(g, 3.1)
    s = g['neon']; a, b = s['bodies'].values()
    a.update(x=8., y=0., vx=26., vy=0., dash=s['time']+.23)
    b.update(x=9., y=0.)
    advance(g, .4)
    assert not b['alive']
    assert s['scores'][a['group']] == 1


def test_teammates_do_not_push_each_other_and_share_win():
    g = arena(4, True); advance(g, 3.1)
    s = g['neon']; a, b, c, d = s['bodies'].values()
    a.update(x=-.5, y=0., vx=26., vy=0., dash=s['time']+.23)
    b.update(x=.5, y=0.)
    advance(g, .04)
    assert b['vx'] == 0
    a['alive'] = False; c['alive'] = d['alive'] = False
    advance(g, .1)
    assert s['winner'] == b['group'] and s['scores'][b['group']] == 1


def test_draw_shrinking_ring_and_match_to_five():
    g = arena(); advance(g, 16)
    assert g['neon']['radius'] < 10
    # At the same edge both fall on the same physics step: no arbitrary winner.
    for b in g['neon']['bodies'].values():
        b.update(x=20., y=0.)
    advance(g, .1)
    assert g['phase'] == 'results' and g['neon']['scores'] == {}
    for win in range(5):
        games.next_step(g); advance(g, 3.1)
        a, b = g['neon']['bodies'].values(); b.update(x=20., y=0.)
        advance(g, .1)
        assert g['neon']['scores'][a['group']] == win+1
    assert g['phase'] == 'end'
    games.restart(g)
    assert g['round'] == 1 and not g['neon']['scores']


def test_idle_round_ends_within_45_seconds():
    g = arena(8); advance(g, 48.1)
    assert g['phase'] == 'results'


def test_sleep_or_server_restart_does_not_award_points():
    g = arena(); neon.tick(g, g['neon']['clock']+60)
    assert g['phase'] == 'results' and not g['neon']['scores']
    assert 'interrompue' in g['neon']['notice']


def test_late_join_waits_and_host_departure_finishes_round():
    g = arena(); games.join(g, 'late-player', 'Late')
    assert g['players'][-1]['waiting']
    games.leave(g, 'neon-player-0')
    assert g['phase'] == 'results' and g['host'] == 'neon-player-1'
    games.next_step(g)
    assert len(g['neon']['bodies']) == 2 and not g['players'][-1]['waiting']


def test_transport_guards_permissions_types_and_nonfinite_input(monkeypatch):
    g = arena(); advance(g, 3.1)
    monkeypatch.setitem(main.store.session.games, g['code'], g)
    client = TestClient(main.app)
    base = '/api/games/' + g['code']
    response = client.post(base+'/neon', json={'guest_id':'neon-player-0','x':1,'y':0})
    assert response.status_code == 200
    assert 'neon-player-' not in response.text
    assert client.post(base, json={'guest_id':'neon-player-1','action':'nset','settings':{'mode':'duo'}}).status_code == 403
    assert client.post(base, json={'guest_id':'neon-player-0','action':'spin'}).status_code == 400
    with pytest.raises(neon.NeonError):
        neon.input_state(g, 'neon-player-0', math.inf, 0, False)
    g['kicked'].append('banned-player')
    assert client.post(base+'/neon', json={'guest_id':'banned-player'}).status_code == 403


def test_duplicate_ticks_do_not_accelerate_physics():
    g = arena(); now=g['neon']['clock']+.2
    neon.tick(g, now); t=g['neon']['time']
    for _ in range(8):
        neon.tick(g, now)
    assert g['neon']['time'] == t


def test_cancel_touch_drops_charge_without_firing():
    g = arena(); advance(g, 3.1)
    s = g['neon']; b = next(iter(s['bodies'].values()))
    neon.input_state(g, 'neon-player-0', 0, 0, True, s['clock'])
    advance(g, .2)
    neon.input_state(g, 'neon-player-0', 0, 0, False, s['clock'], cancel=True)
    assert b['pulse'] == 0 and b['charge'] is None


def test_room_score_includes_both_duo_members():
    g = arena(4, True)
    room = games.new_game('room', 'neon-player-0', 'J0')
    neon.finish(g, '0'); games.room_merge(room, g)
    assert room['rpts']['neon-player-0'] == room['rpts']['neon-player-1'] == 1
    assert room['rpts']['neon-player-2'] == 0


def test_late_arrival_cannot_block_existing_duo_match():
    g = arena(4, True)
    with pytest.raises(games.GameError, match='prochain match'):
        games.join(g, 'late-player', 'Late')
    assert len(g['players']) == 4
    neon.finish(g, '0'); games.next_step(g)
    assert g['phase'] == 'countdown' and len(g['neon']['bodies']) == 4


def test_host_can_reform_teams_after_departure_at_results():
    g = arena(4, True)
    games.leave(g, 'neon-player-0'); neon.finish(g, '1')
    neon.configure(g, {'mode':'duo'})
    assert g['phase'] == 'lobby' and not g['neon']['scores']
    games.join(g, 'replacement-player', 'Remplaçant')
    games.start(g)
    assert g['phase'] == 'countdown'
