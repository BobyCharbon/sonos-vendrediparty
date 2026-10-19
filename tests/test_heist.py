import json
import math
import random
from collections import deque

import pytest
from fastapi.testclient import TestClient
from app import games, heist, main


def game(n=1, map_id=0):
    g=games.new_game('heist','heist-owner','Camille',code='8732')
    for i in range(1,n):games.join(g,f'heist-player-{i}',f'J{i}')
    heist.configure(g,{'map':map_id});games.start(g,random.Random(4));advance(g,3.1)
    return g


def advance(g,seconds):
    s=heist.state(g);target=s['clock']+seconds
    while g['phase'] in ('countdown','play') and target-s['clock']>=heist.STEP:
        heist.tick(g,min(target,s['clock']+.1))


def body(g,index=0):return g['heist']['bodies'][g['players'][index]['pid']]


def test_three_maps_have_accessible_treasures_exit_jail_switch_and_distinct_layouts():
    assert len({str(m['walls']) for m in heist.MAPS})==3
    for m in heist.MAPS:
        # Half-unit navigation grid, player radius included.
        start=(0,16);seen={start};queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                q=(x+dx,y+dy)
                if q not in seen and not heist.blocked(q[0]/2,q[1]/2,m):seen.add(q);queue.append(q)
        for x,y in m['treasures']+[m['switch'],heist.JAIL,heist.EXIT]:
            assert (x*2,y*2) in seen,(m['name'],x,y)
        for path in m['patrols']:
            for a,b in zip(path,path[1:]+path[:1]):assert heist.clear_line(*a,*b,m)


def test_solo_collect_deliver_complete_without_duplicate_score():
    g=game();s=g['heist'];b=body(g);pid=g['players'][0]['pid']
    for t in s['treasures'][:s['target']]:
        b.update(x=t['x'],y=t['y']);heist.act(g,pid)
        assert b['bag']==t['id']
        heist.act(g,pid);assert b['bag']==t['id']
        b.update(x=0,y=8);heist.act(g,pid)
    assert g['phase']=='results' and s['success'] and s['banked']==4
    assert s['scores'][pid]==1
    heist.finish(g,True);assert s['scores'][pid]==1
    games.next_step(g,random.Random(2));assert g['phase']=='countdown' and g['round']==2
    assert s['banked']==0 and s['scores'][pid]==1


def test_coop_rescue_all_prisoners_drop_and_team_loss():
    g=game(3);s=g['heist'];pids=[p['pid'] for p in g['players']]
    b=body(g);t=s['treasures'][0];b.update(x=t['x'],y=t['y']);heist.act(g,pids[0])
    heist.capture(g,pids[0]);heist.capture(g,pids[1]);assert g['phase']=='play'
    assert t['status']=='floor' and b['bag'] is None
    body(g,2).update(x=-9,y=7);heist.act(g,pids[2])
    assert all(not b['jailed'] for b in s['bodies'].values())
    assert body(g,2)['rescued']==2
    for b in s['bodies'].values():b['immune']=0
    for pid in pids:heist.capture(g,pid)
    assert g['phase']=='results' and not s['success']


def test_solo_capture_costs_time_and_returns_to_exit():
    g=game();s=g['heist'];before=s['time'];heist.capture(g,g['players'][0]['pid'])
    assert s['time']==before+12 and not body(g)['jailed']
    assert (body(g)['x'],body(g)['y'])==tuple(heist.EXIT)
    heist.capture(g,g['players'][0]['pid']);assert s['captures']==1


def test_wall_collision_stale_controls_normalization_and_invalid_input():
    g=game();b=body(g);s=g['heist'];b.update(x=-6,y=-3)
    heist.input_state(g,'heist-owner',100,0,now=s['clock']);advance(g,.3)
    assert b['x']<=-5.8
    b.update(x=0,y=8);heist.input_state(g,'heist-owner',1,0,now=s['clock']);advance(g,1)
    assert b['x']<1.8
    with pytest.raises(heist.HeistError):heist.input_state(g,'heist-owner',math.nan,0)
    heist.input_state(g,'heist-owner',1,0,cancel=True);assert b['ix']==0


def test_laser_switch_and_guard_detection_wall_occlusion():
    g=game();s=g['heist'];b=body(g);pid=g['players'][0]['pid'];b.update(x=0,y=7)
    heist.act(g,pid);assert s['disabled_until']>s['time']
    assert not any(heist.laser_active(s,i) for i in range(2))
    assert not heist.clear_line(-6,-3,-4,-3,heist.MAPS[0])
    guard=s['guards'][0];b.update(x=guard['x']+math.sin(guard['angle'])*2,y=guard['y']+math.cos(guard['angle'])*2);advance(g,1.1)
    assert s['captures']==1


def test_late_arrival_cannot_move_or_take_and_departure_drops_bag():
    g=game(2);s=g['heist'];games.join(g,'late-guest','Late')
    assert games.player(g,'late-guest')['waiting']
    heist.input_state(g,'late-guest',1,1,True);assert len(s['bodies'])==2
    b=body(g);t=s['treasures'][0];b.update(x=t['x'],y=t['y']);heist.act(g,g['players'][0]['pid'])
    games.leave(g,'heist-owner');assert t['status']=='floor' and not b['active']
    heist.capture(g,g['players'][0]['pid']);assert g['phase']=='results'


def test_timeout_interrupt_and_settings():
    g=game();s=g['heist']
    with pytest.raises(heist.HeistError):heist.configure(g,{'map':1})
    with pytest.raises(heist.HeistError):games.restart(g)
    s['time']=239.95;advance(g,.2);assert g['phase']=='results' and not s['success']
    with pytest.raises(heist.HeistError):heist.configure(g,{'map':True})
    heist.configure(g,{'map':2});games.next_step(g);assert s['map_id']==2
    heist.tick(g,s['clock']+10);assert g['phase']=='results' and s['wins']==0


def test_view_has_no_private_ids_and_team_points_merge():
    g=game(2);s=g['heist'];assert 'heist-owner' not in json.dumps(heist.view(g,'heist-owner'))
    s['banked']=s['target'];heist.conclude(g)
    room=games.new_game('room','heist-owner','Camille',code='9811');games.join(room,'heist-player-1','J1')
    games.room_merge(room,g)
    assert room['rpts']['heist-owner']==1 and room['rpts']['heist-player-1']==1


def test_api_host_settings_permissions_removed_guest_and_room_cap():
    with TestClient(main.app) as c:
        r=c.post('/api/games',json={'type':'heist','guest_id':'api-heist-host','name':'Host'});assert r.status_code==200
        code=r.json()['code'];url=f'/api/games/{code}'
        c.post(url,json={'action':'join','guest_id':'api-heist-friend','name':'Friend'})
        assert c.post(url,json={'action':'hset','guest_id':'api-heist-friend','settings':{'map':2}}).status_code==403
        assert c.post(url,json={'action':'hset','guest_id':'api-heist-host','settings':{'map':2}}).status_code==200
        v=c.post(url,json={'action':'start','guest_id':'api-heist-host'}).json();pid=next(p['pid'] for p in v['players'] if p['name']=='Friend')
        assert v['heist']['map']['id']==2
        c.post(url,json={'action':'remove','guest_id':'api-heist-host','target':pid})
        assert c.post(url+'/heist',json={'guest_id':'api-heist-friend','x':1}).status_code==403
        assert c.post(url,json={'action':'hset','guest_id':'api-heist-host','settings':{'map':0}}).status_code==409
        assert c.post(url,json={'action':'vote','guest_id':'api-heist-host'}).status_code==400


def test_eight_players_capacity_shared_pickup_and_configuration_reset():
    g=game(8);s=g['heist'];t=s['treasures'][0]
    with pytest.raises(games.GameError):games.join(g,'ninth-player','Nine')
    for i in (0,1):body(g,i).update(x=t['x'],y=t['y'])
    for p in g['players'][:2]:heist.input_state(g,p['id'],0,0,True)
    assert sum(b['bag'] is not None for b in s['bodies'].values())==1
    assert s['target']==8
    heist.finish(g);heist.configure(g,{'map':1})
    assert g['phase']=='lobby' and not s['treasures'] and not s['bodies']


def test_laser_capture_and_release_button_required():
    g=game();s=g['heist'];b=body(g);s['guards']=[]
    b.update(x=0,y=-2);advance(g,1.1)
    assert s['captures']==1 and b['bag'] is None
    t=s['treasures'][6];b.update(x=t['x'],y=t['y'])
    heist.input_state(g,'heist-owner',0,0,True);assert b['bag']==6
    b.update(x=0,y=8);heist.input_state(g,'heist-owner',0,0,True);assert s['banked']==0
    heist.input_state(g,'heist-owner',0,0,False);heist.input_state(g,'heist-owner',0,0,True);assert s['banked']==1


def test_room_rejects_manual_players_for_heist():
    room=games.new_game('room','host-room','Host',code='7682')
    games.add_guest(room,'Manual')
    with pytest.raises(main.HTTPException) as error:main.room_launch(room,'host-room',{'type':'heist'})
    assert error.value.status_code==409
