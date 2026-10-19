"""Deterministic physics, lifecycle and API contracts for Collapsing Island."""
import json
import math
import random

import pytest
from fastapi.testclient import TestClient
from app import games, island, main


def arena(n=1):
    g=games.new_game('island','island-player-0','J0',code='7852')
    for i in range(1,n):
        games.join(g,f'island-player-{i}',f'J{i}')
    games.start(g,random.Random(8))
    return g


def advance(g,seconds):
    target=g['island']['clock']+seconds
    while g['phase'] in ('play','countdown') and target-g['island']['clock']>=island.STEP:
        island.tick(g,min(target,g['island']['clock']+.1))


def test_solo_starts_and_view_keeps_guest_identifiers_private():
    g=arena();advance(g,3.1)
    assert g['phase']=='play'
    v=games.view(g,'island-player-0')['island']
    assert v['solo'] and len(v['tiles'])==37
    assert 'island-player' not in json.dumps(v)
    assert 'seen' not in json.dumps(v)
    assert v['me']==g['players'][0]['pid']


def test_normalized_motion_and_stale_input_stop():
    g=arena();advance(g,3.1);s=g['island'];b=next(iter(s['bodies'].values()))
    island.input_state(g,'island-player-0',100,100,now=s['clock'])
    assert math.hypot(b['ix'],b['iy'])==pytest.approx(1)
    x,y=b['x'],b['y'];advance(g,.2)
    assert math.hypot(b['x']-x,b['y']-y)<1.0
    advance(g,.8)
    assert b['ix']==b['iy']==0
    with pytest.raises(island.IslandError):
        island.input_state(g,'island-player-0',float('nan'),0)


def test_jump_crosses_missing_tile_but_landing_in_water_eliminates():
    g=arena();advance(g,3.1);s=g['island'];b=next(iter(s['bodies'].values()))
    island.input_state(g,'island-player-0',0,0,True,s['clock'])
    assert b['vz']>0
    for t in s['tiles']:t['fall']=0
    advance(g,.35)
    assert b['alive'] and b['z']>0
    island.input_state(g,'island-player-0',0,0,False,s['clock'])
    island.input_state(g,'island-player-0',0,0,True,s['clock'])
    assert b['vz']<7.5 # no double jump
    advance(g,.6)
    assert not b['alive'] and g['phase']=='results'
    assert s['best'][g['players'][0]['pid']]>0


def test_solo_can_survive_goal_on_last_island():
    g=arena();s=g['island'];b=next(iter(s['bodies'].values()))
    final=max(s['tiles'],key=lambda t:t['fall'])
    b.update(x=final['x'],y=final['y'])
    advance(g,93.2)
    assert g['phase']=='results' and s['winner']==g['players'][0]['pid']
    assert s['scores'][s['winner']]==1
    assert s['best'][s['winner']]>=90


def test_simultaneous_fall_is_draw_and_next_round_restores_players():
    g=arena(2);advance(g,3.1)
    for b in g['island']['bodies'].values():b.update(x=99,y=99)
    advance(g,.1)
    assert g['phase']=='results' and g['island']['winner'] is None
    games.next_step(g,random.Random(9))
    assert g['phase']=='countdown' and g['round']==2
    assert all(p['alive'] and not p['waiting'] for p in g['players'])


def test_last_survivor_scores_once_and_room_receives_win():
    g=arena(2);advance(g,3.1)
    list(g['island']['bodies'].values())[1].update(x=99,y=99)
    advance(g,.1);pid=g['players'][0]['pid']
    assert g['island']['scores']=={pid:1}
    island.tick(g,g['island']['clock']+1)
    assert g['island']['scores']=={pid:1}
    room=games.new_game('room','island-player-0','J0')
    games.room_merge(room,g)
    assert room['rpts']['island-player-0']==1
    assert room['rhistory'][0]['winner']=='J0'


def test_late_join_waits_and_departure_keeps_original_mode():
    g=arena();games.join(g,'late-island-player','Late')
    assert games.player(g,'late-island-player')['waiting']
    assert len(g['island']['bodies'])==1 and g['island']['solo']
    games.leave(g,'late-island-player')
    assert g['phase']=='countdown'
    games.leave(g,'island-player-0')
    assert g['phase']=='results'


def test_capacity_and_live_restart_guard():
    g=arena(8)
    with pytest.raises(games.GameError):games.join(g,'ninth-island-player','Nine')
    with pytest.raises(island.IslandError):games.restart(g)
    with pytest.raises(games.GameError):games.add_guest(g,'Manual')


def test_sleep_interrupts_without_awarding_record():
    g=arena(2);island.tick(g,g['island']['clock']+30)
    assert g['phase']=='results' and not g['island']['scores'] and not g['island']['best']
    assert 'interrompue' in g['island']['notice']


def test_cancel_and_spectator_cannot_move_player():
    g=arena();advance(g,3.1);s=g['island'];b=next(iter(s['bodies'].values()))
    island.input_state(g,'spectator-id',1,1,True,s['clock'])
    assert b['ix']==b['iy']==0 and b['z']==0
    island.input_state(g,'island-player-0',1,0,False,s['clock'])
    island.input_state(g,'island-player-0',0,0,False,s['clock'],cancel=True)
    assert b['ix']==b['iy']==0


def test_frame_endpoint_and_action_permissions(monkeypatch):
    g=arena(2);monkeypatch.setattr(main.store.session,'games',{g['code']:g})
    monkeypatch.setattr(main,'save_games',lambda *args:None)
    client=TestClient(main.app)
    assert client.post('/api/games/7852/island',json={'guest_id':'island-player-0'}).status_code==200
    response=client.post('/api/games/7852',json={'guest_id':'island-player-1','action':'restart'})
    assert response.status_code==403
    response=client.post('/api/games/7852',json={'guest_id':'island-player-0','action':'nset','settings':{'mode':'duo'}})
    assert response.status_code==400
    games.kick(g,'island-player-1')
    assert client.post('/api/games/7852/island',json={'guest_id':'island-player-1'}).status_code==403


def test_room_capacity_guard(monkeypatch):
    room=games.new_game('room','room-island-host','Host',code='8373')
    for i in range(8):games.join(room,f'room-island-{i}',str(i))
    monkeypatch.setattr(main.store.session,'games',{room['code']:room})
    with pytest.raises(main.HTTPException) as error:main.room_launch(room,'room-island-host',{'type':'island'})
    assert error.value.status_code==409 and room['current'] is None


def test_random_collapse_always_leaves_connected_escape_route():
    g=arena();tiles=sorted(g['island']['tiles'],key=lambda t:t['fall'])
    assert tiles[-1]['fall']>island.DURATION
    for i in range(1,len(tiles)):
        remaining=tiles[i:];seen={remaining[0]['id']}
        changed=True
        while changed:
            changed=False
            for t in remaining:
                if t['id'] not in seen and any(u['id'] in seen and math.hypot(t['x']-u['x'],t['y']-u['y'])<2.9 for u in remaining):
                    seen.add(t['id']);changed=True
        assert len(seen)==len(remaining)
