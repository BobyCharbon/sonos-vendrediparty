"""Cooperative museum heist. Authoritative movement, patrols and interactions."""
import copy
import math
import random
import time

from .game_lock import LOCK  # verrou commun à toutes les parties (voir game_lock.py)
STEP = 1 / 30
DURATION = 300
COLORS = ['#56ded7', '#fc846c', '#f4cc63', '#b69cff', '#91d077', '#f397cc', '#80b6ff', '#ffac67']
# Rectangles are centre x/y and width/depth. All coordinates also drive rendering.
MAPS = [
    dict(id=0, name='Galerie royale', subtitle='Marbre bleu · grands salons · joyaux de la couronne', color='#426998',
         walls=[[-5,-3,1,8],[5,-3,1,8],[-5,5,6,1],[5,5,6,1]],
         treasures=[[-8,-7],[0,-7],[8,-7],[-8,0],[0,0],[8,0],[-8,7],[8,7],[0,4],[-2,-4]],
         patrols=[[[-8,-8],[-8,3],[-2,3],[-2,-8]],[[2,-8],[8,-8],[8,2],[2,2]],[[-1,-6],[1,-6],[1,2],[-1,2]]],
         lasers=[[-3,-2,3,-2],[6,4,10,4],[-10,1,-6,1],[-1.5,3,1.5,3]], switch=[0,7]),
    dict(id=1, name='Cabinet des curiosités', subtitle='Jade et cuivre · vitrines en îlots · chemins croisés', color='#3d807c',
         walls=[[-5,-5,5,1],[5,-5,5,1],[-5,1,1,5],[5,1,1,5],[0,3,4,1]],
         treasures=[[-8,-7],[0,-7],[8,-7],[-8,-1],[0,-1],[8,-1],[-8,6],[8,6],[-2,6],[2,-4]],
         patrols=[[[-8,-3],[-3,-3],[-3,4],[-8,4]],[[3,-3],[8,-3],[8,4],[3,4]],[[-8,-8],[8,-8],[8,-6],[-8,-6]]],
         lasers=[[-10,4,-6,4],[-3,-5,3,-5],[-10,-6,-6,-6],[2,5,10,5]], switch=[8,7]),
    dict(id=2, name='Aile des antiquités', subtitle='Grès et améthyste · sarcophages · galerie centrale', color='#876248',
         walls=[[-6,-3,1,8],[6,-3,1,8],[-2,-1,1,5],[2,-1,1,5],[-6,5,5,1],[6,5,5,1]],
         treasures=[[-9,-7],[-4,-6],[0,-6],[4,-6],[9,-7],[-9,2],[9,2],[-4,3],[4,3],[0,6]],
         patrols=[[[-9,-5],[-9,3],[-7,3],[-7,-5]],[[3,-5],[5,-5],[5,3],[3,3]],[[-.7,-7],[.7,-7],[.7,2],[-.7,2]]],
         lasers=[[-1.4,-3,1.4,-3],[-5,4,-2,4],[7,3,10,3],[-5,-5,-3,-5],[-1.4,3,1.4,3]], switch=[-8,7]),
]
# Plans dessinés sur une grille de 21 × 19, agrandis à l'échelle (les murs gardent leur épaisseur).
SCALE = 1.6
HALF = [10.5 * SCALE, 9.5 * SCALE]  # demi-largeur et demi-profondeur du musée


def _scaled(m):
    k = SCALE
    wall = lambda x, y, w, h: [x * k, y * k, w * k if w > h else w, h * k if h >= w else h]
    return dict(m, walls=[wall(*w) for w in m['walls']], treasures=[[x * k, y * k] for x, y in m['treasures']],
                patrols=[[[x * k, y * k] for x, y in path] for path in m['patrols']],
                lasers=[[v * k for v in line] for line in m['lasers']], switch=[v * k for v in m['switch']])


MAPS = [_scaled(m) for m in MAPS]
EXIT = [0, 8 * SCALE]
JAIL = [-9 * SCALE, 8 * SCALE]
# Gardes : ronde, puis poursuite de qui ils voient (un peu moins vite qu'un voleur sans butin), fouille, retour.
GUARD_WALK, GUARD_RUN, GUARD_SIGHT, GUARD_CONE, GUARD_SEARCH = 2.2, 3.7, 6.5, .75, 2.5


class HeistError(ValueError):
    pass


def state(g):
    if g['type'] != 'heist':
        raise HeistError('Cette action appartient au Braquage')
    return g.setdefault('heist', dict(map_id=0, bodies={}, treasures=[], guards=[], time=0., clock=0.,
        solo=True, target=6, banked=0, captures=0, wins=0, scores={}, success=False, notice='', disabled_until=0.))


def configure(g, settings):
    s = state(g)
    if g['phase'] not in ('lobby', 'results', 'end'):
        raise HeistError('Choisis la carte entre deux manches')
    choice = settings.get('map', s['map_id'])
    if type(choice) is not int or not 0 <= choice < len(MAPS):
        raise HeistError('Carte inconnue')
    if s['map_id'] != choice:
        s.update(map_id=choice,bodies={},treasures=[],guards=[],time=0.,clock=time.time())
        g['phase']='lobby'


def start(g, rng=None):
    s = state(g)
    if g['phase'] not in ('lobby', 'results', 'end'):
        raise HeistError('Un braquage est déjà en cours')
    if not 1 <= len(g['players']) <= 8 or any(p.get('manual') for p in g['players']):
        raise HeistError('Il faut 1 à 8 joueurs, chacun avec son téléphone')
    rng = rng or random
    layout = MAPS[s['map_id']]
    treasures = [dict(id=i, x=x, y=y, status='floor', carrier=None) for i, (x,y) in enumerate(layout['treasures'])]
    bodies = {}
    for i,p in enumerate(g['players']):
        bodies[p['pid']] = dict(x=(i%4-1.5)*1.5, y=EXIT[1]+(i//4)*.6, name=p['name'], color=COLORS[i],
            ix=0., iy=0., seen=0., action=False, jailed=False, active=True, exposure=0., bag=None, immune=0., delivered=0, rescued=0)
        p.update(alive=True, waiting=False)
    guards = []
    for i,path in enumerate(layout['patrols']):
        node = rng.randrange(len(path))
        x,y = path[node]
        dest = path[(node+1)%len(path)]
        guards.append(dict(x=x,y=y,node=(node+1)%len(path),angle=math.atan2(dest[0]-x,dest[1]-y),path=i,
                           mode='patrol',target=None,until=0.,trail=[]))
    s.update(bodies=bodies, treasures=treasures, guards=guards, time=-3., clock=time.time(), solo=len(bodies)==1,
        target=max(6,min(8,3+len(bodies))),banked=0,captures=0,success=False,notice='',disabled_until=0.)
    g.update(phase='countdown',round=g['round']+1)


def finish(g, success=False, notice=''):
    s = state(g)
    if g['phase'] not in ('countdown','play'):
        return
    s.update(success=success,notice=notice)
    if success:
        s['wins'] += 1
        for pid,b in s['bodies'].items():
            if b['active']:
                s['scores'][pid] = s['scores'].get(pid,0)+1
    g['phase']='results'
    for b in s['bodies'].values():
        b.update(ix=0.,iy=0.,action=False)


def conclude(g):
    s=state(g)
    active=[b for b in s['bodies'].values() if b['active']]
    if s['banked'] >= s['target']:
        finish(g,True,'Butin à l’abri. Toute l’équipe gagne !')
    elif not active or all(b['jailed'] for b in active):
        finish(g,notice='Toute l’équipe est en prison. Préparez une nouvelle tentative !')
    elif s['time'] >= DURATION:
        finish(g,notice='Le musée ferme : le butin requis n’a pas été livré à temps.')


def blocked(x,y,layout,radius=.30):
    return abs(x)>HALF[0]-radius or abs(y)>HALF[1]-radius or any(abs(x-wx)<w/2+radius and abs(y-wy)<h/2+radius for wx,wy,w,h in layout['walls'])


def clear_line(x,y,tx,ty,layout):
    steps=max(1,math.ceil(math.hypot(tx-x,ty-y)/.15))
    return all(not blocked(x+(tx-x)*i/steps,y+(ty-y)*i/steps,layout,0) for i in range(1,steps))


def distance_to_segment(x,y,line):
    ax,ay,bx,by=line
    dx,dy=bx-ax,by-ay
    u=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-ax-u*dx,y-ay-u*dy)


def drop(s,b):
    if b['bag'] is not None:
        t=s['treasures'][b['bag']]
        t.update(status='floor',carrier=None,x=b['x'],y=b['y'])
        b['bag']=None


def capture(g,pid):
    s=state(g);b=s['bodies'][pid]
    if b['jailed'] or not b['active'] or s['time']<b['immune']:
        return
    drop(s,b);s['captures']+=1
    b.update(ix=0.,iy=0.,action=False,exposure=0.)
    if s['solo']:
        s['time']+=12
        b.update(x=EXIT[0],y=EXIT[1],immune=s['time']+4)
    else:
        b.update(x=JAIL[0],y=JAIL[1],jailed=True)
    conclude(g)


def leave(g,gid,pid):
    s=state(g);b=s['bodies'].get(pid)
    if b:
        drop(s,b);b.update(active=False,ix=0.,iy=0.)
    if g['phase'] in ('countdown','play'):
        conclude(g)


def interaction(s,pid):
    b=s['bodies'].get(pid)
    if not b or not b['active'] or b['jailed']:
        return None
    layout=MAPS[s['map_id']]
    near=lambda x,y,r: math.hypot(x-b['x'],y-b['y'])<=r and clear_line(b['x'],b['y'],x,y,layout)
    if near(*JAIL,2.) and any(p['active'] and p['jailed'] for p in s['bodies'].values()):
        return ('rescue',None,'Libérer')
    if b['bag'] is not None and near(*EXIT,1.8):
        return ('deposit',None,'Déposer')
    if near(*layout['switch'],1.6) and s['time']>=s['disabled_until']:
        return ('switch',None,'Couper lasers')
    if b['bag'] is None:
        available=[t for t in s['treasures'] if t['status']=='floor' and near(t['x'],t['y'],1.35)]
        if available:
            t=min(available,key=lambda t:math.hypot(t['x']-b['x'],t['y']-b['y']))
            return ('take',t['id'],'Prendre')
    return None


def act(g,pid):
    s=state(g);b=s['bodies'][pid];choice=interaction(s,pid)
    if not choice:return
    kind,tid,_=choice
    if kind=='take':
        s['treasures'][tid].update(status='carried',carrier=pid);b['bag']=tid
    elif kind=='deposit':
        s['treasures'][b['bag']].update(status='banked',carrier=None)
        b['bag']=None;b['delivered']+=1;s['banked']+=1
    elif kind=='switch':
        s['disabled_until']=s['time']+15
    elif kind=='rescue':
        for other in s['bodies'].values():
            if other['active'] and other['jailed']:
                other.update(jailed=False,immune=s['time']+4,exposure=0.)
                b['rescued']+=1
    conclude(g)


def input_state(g,gid,x,y,action=False,now=None,cancel=False):
    s=state(g)
    if not math.isfinite(x) or not math.isfinite(y):raise HeistError('Commande invalide')
    p=next((p for p in g['players'] if p['id']==gid),None)
    b=s['bodies'].get(p['pid']) if p else None
    if not b or not b['active'] or b['jailed'] or g['phase']!='play':return
    if cancel:
        b.update(ix=0.,iy=0.,action=False);return
    norm=max(1,math.hypot(x,y))
    b.update(ix=x/norm,iy=y/norm,seen=time.time() if now is None else now)
    if action and not b['action']:act(g,p['pid'])
    b['action']=action


def sees(guard,b,layout):
    dx,dy=b['x']-guard['x'],b['y']-guard['y'];d=math.hypot(dx,dy)
    angle=(math.atan2(dx,dy)-guard['angle']+math.pi)%(2*math.pi)-math.pi
    return (d<1. or (d<GUARD_SIGHT and abs(angle)<GUARD_CONE)) and clear_line(guard['x'],guard['y'],b['x'],b['y'],layout)


def step_towards(guard,tx,ty,speed):
    """Avance vers (tx, ty) ; vrai une fois arrivé."""
    dx,dy=tx-guard['x'],ty-guard['y'];d=math.hypot(dx,dy);step=speed*STEP
    if d<=step:
        guard.update(x=tx,y=ty);return True
    guard['x']+=dx/d*step;guard['y']+=dy/d*step;guard['angle']=math.atan2(dx,dy);return False


def move_guard(s,guard,layout):
    """Ronde → poursuite (cible vue) → fouille du dernier endroit vu → retour à la ronde par le chemin pris.
    La poursuite ne va qu'en ligne de vue et le retour suit les pas du garde : il ne traverse jamais un mur."""
    mode=guard.setdefault('mode','patrol');trail=guard.setdefault('trail',[])
    if mode in ('chase','search','return') and (not trail or math.hypot(guard['x']-trail[-1][0],guard['y']-trail[-1][1])>.4):
        if mode!='return':trail.append([guard['x'],guard['y']])
    if mode=='chase':
        if step_towards(guard,*guard['target'],GUARD_RUN):
            guard.update(mode='search',until=s['time']+GUARD_SEARCH)
    elif mode=='search':
        guard['angle']+=STEP*2.4  # il regarde autour de lui
        if s['time']>=guard['until']:guard['mode']='return'
    elif mode=='return':
        if not trail:guard['mode']='patrol'
        elif step_towards(guard,*trail[-1],GUARD_WALK):trail.pop()
    else:
        path=layout['patrols'][guard['path']]
        if step_towards(guard,*path[guard['node']],GUARD_WALK):guard['node']=(guard['node']+1)%len(path)


def laser_active(s,i):
    return s['time']>=s['disabled_until'] and (s['time']+i*1.5)%7<4


def tick(g,now=None):
    if g['type']!='heist' or g['phase'] not in ('countdown','play'):return False
    s=state(g);now=time.time() if now is None else now;gap=now-s['clock'];old=g['phase']
    if gap>5 or gap < -1:
        finish(g,notice='Connexion interrompue : relancez le braquage.');s['clock']=now;return True
    layout=MAPS[s['map_id']]
    for _ in range(max(0,int(gap/STEP))):
        s['clock']+=STEP;s['time']+=STEP
        if s['time']<0:continue
        g['phase']='play'
        for guard in s['guards']:
            move_guard(s,guard,layout)
        for pid,b in s['bodies'].items():
            if not b['active'] or b['jailed']:continue
            if s['clock']-b['seen']>.4:b.update(ix=0.,iy=0.,action=False)
            speed=3.5 if b['bag'] is not None else 4.2
            nx=b['x']+b['ix']*speed*STEP;ny=b['y']+b['iy']*speed*STEP
            if not blocked(nx,b['y'],layout):b['x']=nx
            if not blocked(b['x'],ny,layout):b['y']=ny
            danger=tripped=False
            if s['time']>=b['immune']:
                for guard in s['guards']:
                    if sees(guard,b,layout):
                        danger=True;guard.update(mode='chase',target=[b['x'],b['y']])
                # Laser allumé : l'alarme se déclenche au contact, sans délai.
                tripped=any(laser_active(s,i) and distance_to_segment(b['x'],b['y'],line)<.3 for i,line in enumerate(layout['lasers']))
            b['exposure']=1. if tripped else max(0,min(1,b['exposure']+(STEP/.45 if danger else -STEP*1.4)))
            if b['exposure']>=1:capture(g,pid)
            if g['phase']=='results':break
        if g['phase']=='results':break
        conclude(g)
        if g['phase']=='results':break
    return old!=g['phase']


def view(g,gid):
    s=state(g);p=next((p for p in g['players'] if p['id']==gid),None);pid=p['pid'] if p else None
    layout=copy.deepcopy(MAPS[s['map_id']]);layout.update(exit=EXIT,jail=JAIL,half=HALF,sight=[GUARD_SIGHT,GUARD_CONE])
    choice=interaction(s,pid) if g['phase']=='play' else None
    return dict(phase=g['phase'],round=g['round'],clock=s['clock'],time=round(s['time'],3),duration=DURATION,
        solo=s['solo'],map=layout,maps=[dict(id=m['id'],name=m['name'],subtitle=m['subtitle']) for m in MAPS],
        target=s['target'],banked=s['banked'],captures=s['captures'],success=s['success'],notice=s['notice'],wins=s['wins'],
        me=pid,action=choice[2] if choice else '',disabled_for=max(0,s['disabled_until']-s['time']),
        lasers=[laser_active(s,i) for i in range(len(layout['lasers']))],guards=[{k:v for k,v in guard.items() if k!='trail'} for guard in s['guards']],
        treasures=copy.deepcopy(s['treasures']),scores=dict(s['scores']),
        fighters=[dict(pid=key,**{k:b[k] for k in ('x','y','name','color','jailed','active','exposure','bag','delivered','rescued')}) for key,b in s['bodies'].items()])
