"""Collapsing Island: authoritative fixed-step movement and shared collapse schedule.

Only inputs cross the network. Round roster and solo/multi mode are frozen at
start; late arrivals spectate. The transport shares LOCK with all lobby actions.
"""
import math
import random
import threading
import time

LOCK = threading.RLock()
STEP = 1 / 60
TILE_RADIUS = 1.65
DURATION = 90.0
WARNING = 2.8
COLORS = ['#20c9d0', '#f66b60', '#f4bd40', '#a185e8', '#78ba60', '#ef91ba', '#539cef', '#ef984b']


class IslandError(ValueError):
    pass


def terrain():
    return [dict(id=f'{q}:{r}', x=round(math.sqrt(3)*TILE_RADIUS*(q+r/2), 5),
                 y=round(1.5*TILE_RADIUS*r, 5), ring=max(abs(q), abs(r), abs(q+r)), fall=999.)
            for q in range(-3, 4) for r in range(-3, 4) if abs(q+r) <= 3]


def state(g):
    if g['type'] != 'island':
        raise IslandError('Cette action appartient à L’île qui s’effondre')
    return g.setdefault('island', dict(tiles=terrain(), bodies={}, time=0., clock=0.,
        solo=True, winner=None, notice='', best={}, scores={}))


def on_tile(x, y, tile):
    # Pointy-top hexagon, matching Three's six-sided cylinder orientation.
    dx, dy = abs(x-tile['x']), abs(y-tile['y'])
    return dx <= math.sqrt(3)*TILE_RADIUS/2 and dy <= TILE_RADIUS and math.sqrt(3)*dy+dx <= math.sqrt(3)*TILE_RADIUS


def supported(s, x, y):
    return any(t['fall'] > s['time'] and on_tile(x, y, t) for t in s['tiles'])


def start(g, rng=None):
    s = state(g)
    if g['phase'] not in ('lobby', 'results', 'end'):
        raise IslandError('Une manche est déjà en cours')
    if not 1 <= len(g['players']) <= 8 or any(p.get('manual') for p in g['players']):
        raise IslandError('Il faut 1 à 8 joueurs, chacun avec son téléphone')
    rng = rng or random
    tiles = terrain()
    # Random erosion, retaining a connected route until the last tile. The
    # centre is not a permanent safe spot; jumping can shortcut emerging holes.
    remaining = {t['id']: t for t in tiles}
    neighbors = {t['id']: {u['id'] for u in tiles if u != t and
                 math.hypot(t['x']-u['x'], t['y']-u['y']) < 2.9} for t in tiles}
    order = []
    while len(remaining) > 1:
        candidates = list(remaining)
        rng.shuffle(candidates)
        for candidate in candidates:
            rest = set(remaining) - {candidate}
            visited, pending = set(), [next(iter(rest))]
            while pending:
                node = pending.pop()
                if node in visited:
                    continue
                visited.add(node)
                pending.extend((neighbors[node] & rest) - visited)
            if visited == rest:
                order.append(remaining.pop(candidate))
                break
    order.extend(remaining.values())
    for i, tile in enumerate(order):
        tile['fall'] = DURATION + 1 if i == len(order)-1 else 10. + i * 2.15  # final island survives the solo objective
    spawn = [t for t in tiles if t['ring'] == 2]
    bodies = {}
    for i, p in enumerate(g['players']):
        tile = spawn[int(i*len(spawn)/len(g['players']))]
        bodies[p['pid']] = dict(x=tile['x'], y=tile['y'], z=0., vz=0., ix=0., iy=0.,
            seen=0., jump=False, cooldown=0., alive=True, out_at=None,
            color=COLORS[i], name=p['name'])
        p.update(alive=True, waiting=False)
    s.update(tiles=tiles, bodies=bodies, solo=len(bodies)==1, time=-3., clock=time.time(), winner=None, notice='')
    g.update(phase='countdown', round=g['round']+1)


def finish(g, winner=None, notice='', interrupted=False):
    s = state(g)
    if g['phase'] not in ('countdown', 'play'):
        return
    s.update(winner=winner, notice=notice)
    if not interrupted:
        for pid, b in s['bodies'].items():
            survived = b['out_at'] if b['out_at'] is not None else max(0., s['time'])
            s['best'][pid] = round(max(s['best'].get(pid, 0.), survived), 2)
        if winner:
            s['scores'][winner] = s['scores'].get(winner, 0)+1
    g['phase'] = 'results'
    for b in s['bodies'].values():
        b.update(ix=0., iy=0., jump=False)


def conclude(g):
    s = state(g)
    alive = [pid for pid, b in s['bodies'].items() if b['alive']]
    if not alive:
        finish(g, notice='À l’eau ! Essaie encore.' if s['solo'] else 'Chute simultanée : égalité !')
    elif not s['solo'] and len(alive) == 1:
        finish(g, alive[0])
    elif s['time'] >= DURATION:
        finish(g, alive[0] if s['solo'] else None,
               '90 secondes : île maîtrisée !' if s['solo'] else 'Temps écoulé : égalité entre les survivants.')


def leave(g, gid, pid):
    s = state(g)
    b = s['bodies'].get(pid)
    if b:
        b.update(alive=False, out_at=max(0., s['time']), ix=0., iy=0., jump=False)
    if g['phase'] in ('countdown', 'play'):
        conclude(g)


def input_state(g, gid, x, y, jump=False, now=None, cancel=False):
    s = state(g)
    if not math.isfinite(x) or not math.isfinite(y):
        raise IslandError('Commande invalide')
    p = next((p for p in g['players'] if p['id'] == gid), None)
    b = s['bodies'].get(p['pid']) if p else None
    if not b or not b['alive'] or g['phase'] != 'play':
        return
    if cancel:
        b.update(ix=0., iy=0., jump=False)
        return
    length = max(1., math.hypot(x, y))
    b.update(ix=x/length, iy=y/length, seen=time.time() if now is None else now)
    # Rising edge: holding the button never gives automatic or double jumps.
    if jump and not b['jump'] and b['z'] == 0 and s['time'] >= b['cooldown'] and supported(s, b['x'], b['y']):
        b['vz'] = 7.5
        b['z'] = .001
        b['cooldown'] = s['time'] + 1.
    b['jump'] = jump


def tick(g, now=None):
    if g['type'] != 'island' or g['phase'] not in ('countdown', 'play'):
        return False
    s = state(g)
    now = time.time() if now is None else now
    gap = now-s['clock']
    previous = g['phase']
    if gap > 5 or gap < -1:
        finish(g, notice='Connexion interrompue. Relance la manche ; aucun score attribué.', interrupted=True)
        s['clock'] = now
        return True
    for _ in range(max(0, int(gap/STEP))):
        s['clock'] += STEP
        s['time'] += STEP
        if s['time'] < 0:
            continue
        g['phase'] = 'play'
        for pid, b in s['bodies'].items():
            if not b['alive']:
                continue
            if s['clock']-b['seen'] > .4:
                b.update(ix=0., iy=0., jump=False)
            speed = 6.0 if b['z'] > 0 else 4.6
            b['x'] += b['ix']*speed*STEP
            b['y'] += b['iy']*speed*STEP
            if b['z'] > 0:
                b['vz'] -= 18.*STEP
                b['z'] = max(0., b['z']+b['vz']*STEP)
            if b['z'] == 0 and not supported(s, b['x'], b['y']):
                b.update(alive=False, out_at=max(0., s['time']), ix=0., iy=0., jump=False)
                for p in g['players']:
                    if p['pid'] == pid:
                        p['alive'] = False
        conclude(g)
        if g['phase'] == 'results':
            break
    return previous != g['phase']


def view(g, gid):
    s = state(g)
    p = next((p for p in g['players'] if p['id'] == gid), None)
    return dict(phase=g['phase'], round=g['round'], clock=s['clock'], time=round(s['time'], 3),
        duration=DURATION, warning=WARNING, tile_radius=TILE_RADIUS, solo=s['solo'],
        winner=s['winner'], notice=s['notice'], best=dict(s['best']), scores=dict(s['scores']),
        me=p['pid'] if p else None, tiles=[dict(t) for t in s['tiles']],
        fighters=[dict(pid=pid, **{k: b[k] for k in ('x','y','z','alive','color','name','out_at')})
                  for pid, b in s['bodies'].items()])
