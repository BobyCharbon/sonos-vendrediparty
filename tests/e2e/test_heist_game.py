"""Browser checks using real controls and shared server state."""
import re
import time
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state


@pytest.fixture
def phones(browser):
    server=Server();made=[]
    def make(name,device='iphone'):
        p=Phone(browser,server,name,device);made.append(p);return p
    yield make
    errors=[e for p in made for e in p.errors]
    for p in made:p.close()
    server_errors=server.errors();server.stop()
    assert not server_errors,server_errors[-3000:]
    assert not errors,'\n'.join(errors)


def ready(p):expect(p.page.locator('.hs-primary[data-gact="start"]')).to_be_enabled(timeout=20000)
def mine(p):
    s=p.state()['heist'];return next(b for b in s['fighters'] if b['pid']==s['me'])


def walk_x(p,target):
    page=p.page;page.locator('.hs-canvas').click(position={'x':500,'y':250})
    before=mine(p)['x'];direction=1 if target>before else -1
    key='ArrowRight' if direction>0 else 'ArrowLeft';page.keyboard.down(key)
    try:
        wait_state(p,lambda g:direction*(target-next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['x'])<2,timeout=8)
    finally:page.keyboard.up(key)
    page.wait_for_timeout(600)
    # Analogue precision: software WebGL can render more slowly than the server.
    # Use the actual on-screen joystick for the final approach instead of a
    # one-pixel arrival boundary and a key-up racing an interaction request.
    stick=page.locator('.hs-stick').bounding_box();cx=stick['x']+stick['width']/2;cy=stick['y']+stick['height']/2
    deadline=time.monotonic()+25
    while abs(target-mine(p)['x'])>.3:
        delta=target-mine(p)['x'];assert time.monotonic()<deadline, mine(p)
        page.mouse.move(cx+(6 if delta>0 else -6),cy);page.mouse.down()
        try:page.wait_for_timeout(250)
        finally:page.mouse.up()
        page.wait_for_timeout(450)
    page.locator('.hs-canvas').click(position={'x':500,'y':250})


def test_heist_solo_three_maps_and_real_treasure_delivery(phones):
    host=phones('HeistSolo','desktop');host.create('heist');ready(host)
    for i in [1,2,0]:
        host.page.locator(f'[data-hs-map="{i}"]').click()
        wait_state(host,lambda g:g['heist']['map']['id']==i)
        expect(host.page.locator(f'[data-hs-map="{i}"]')).to_have_attribute('aria-pressed','true')
    host.page.locator('.hs-primary[data-gact="start"]').click();wait_state(host,lambda g:g['phase']=='play')
    from app import heist
    tx,ty=heist.MAPS[0]['treasures'][7]  # trésor près de la sortie (plan agrandi : il faut aussi monter un peu)
    walk_x(host,tx)
    host.page.keyboard.down('ArrowUp')
    try:wait_state(host,lambda g:next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['y']<ty+1,timeout=8)
    finally:host.page.keyboard.up('ArrowUp')
    expect(host.page.locator('.hs-action')).to_be_enabled()
    host.page.keyboard.press('Space')
    wait_state(host,lambda g:any(b['bag'] is not None for b in g['heist']['fighters']))
    walk_x(host,.5)
    host.page.keyboard.down('ArrowDown')  # redescendre jusqu'à la sortie (sinon on est près de l'interrupteur des lasers)
    try:wait_state(host,lambda g:next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['y']>heist.EXIT[1]-.6,timeout=8)
    finally:host.page.keyboard.up('ArrowDown')
    expect(host.page.locator('.hs-action')).to_have_text('Déposer')
    host.page.keyboard.press('e')
    wait_state(host,lambda g:g['heist']['banked']==1)
    assert mine(host)['bag'] is None
    expect(host.page.locator('.hs-count')).to_have_text('Butin 1 / 6')


def test_heist_coop_touch_late_join_and_network_recovery(phones):
    host=phones('HeistHost');code=host.create('heist');ready(host)
    friend=phones('HeistFriend');friend.join(code)
    wait_state(host,lambda g:len(g['players'])==2)
    host.page.locator('.hs-primary[data-gact="start"]').click();wait_state(host,lambda g:g['phase']=='play')
    wait_state(friend,lambda g:g['phase']=='play')
    assert host.state()['heist']['treasures']==friend.state()['heist']['treasures']
    stick=host.page.locator('.hs-stick').bounding_box();cdp=host.ctx.new_cdp_session(host.page)
    initial=mine(host)['x']
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':stick['x']+stick['width']*.8,'y':stick['y']+stick['height']/2,'id':1}]})
    wait_state(host,lambda g:next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['x']>initial+.3)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    late=phones('HeistLate');late.join(code);v=wait_state(late,lambda g:g.get('me') is not None)
    assert v['me']['waiting'] and len(v['heist']['fighters'])==2
    host.ctx.set_offline(True);expect(host.page.locator('.hs-network')).to_contain_text('reconnexion',timeout=6000)
    host.ctx.set_offline(False);expect(host.page.locator('.hs-network')).to_have_text(re.compile('^(En ligne|Réseau lent)$'),timeout=10000)
    for width,height in [(320,740),(844,390)]:
        host.page.set_viewport_size({'width':width,'height':height})
        expect(host.page.locator('.hs-action')).to_be_in_viewport()
        assert host.page.evaluate("document.querySelector('.hs-root').scrollWidth<=innerWidth")
    pid=host.state()['heist']['me'];host.page.reload();expect(host.page.locator('.hs-network')).to_have_text(re.compile('^(En ligne|Réseau lent)$'),timeout=15000)
    assert host.state()['heist']['me']==pid
    host.page.locator('[data-gdrawer="open"]').click();host.page.locator('#gDrawer [data-gdrawer="minimize"]').click()
    expect(host.page.locator('.hs-root')).to_have_count(0)
    host.page.locator('[data-pyr="enter"]').first.click();expect(host.page.locator('.hs-network')).to_have_text(re.compile('^(En ligne|Réseau lent)$'),timeout=15000)


def test_heist_floating_joystick_and_quit_by_touch(phones):
    """Toucher la moitié gauche de l'écran de jeu amène le joystick sous le doigt ; « Quitter », en haut à droite, ouvre le menu de sortie."""
    p=phones('HeistThumb');p.create('heist');ready(p)
    p.page.locator('.hs-primary[data-gact="start"]').tap();wait_state(p,lambda g:g['phase']=='play')
    expect(p.page.locator('.hs-root.hs-playing')).to_be_visible();p.page.wait_for_timeout(600)  # commandes actives
    x0=mine(p)['x'];cdp=p.ctx.new_cdp_session(p.page);vw=p.page.viewport_size;fx,fy=vw['width']*.3,vw['height']*.45
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':fx,'y':fy,'id':1}]})
    r=p.page.locator('.hs-stick').bounding_box()
    assert abs(r['x']+r['width']/2-fx)<2 and abs(r['y']+r['height']/2-fy)<2  # centré sous le doigt
    cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':fx+40,'y':fy,'id':1}]})
    wait_state(p,lambda g:next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['x']>x0+.5)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    expect(p.page.locator('.hs-stick')).to_have_attribute('style',re.compile(r'^(?!.*translate)'))  # revenu à sa place
    q=p.page.locator('.g-quit').bounding_box();assert q['x']+q['width']>vw['width']-30  # dans le coin, bien visible
    p.page.locator('.g-quit').tap()
    expect(p.page.locator('#gDrawerExit [data-exit]').first).to_be_visible()
