"""Browser checks using real controls and shared server state."""
import re
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
    before=mine(p)['x'];key='ArrowRight' if target>before else 'ArrowLeft';page.keyboard.down(key)
    try:
        wait_state(p,lambda g:(next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['x']>=target if target>before else next(b for b in g['heist']['fighters'] if b['pid']==g['heist']['me'])['x']<=target),timeout=7)
    finally:page.keyboard.up(key)


def test_heist_solo_three_maps_and_real_treasure_delivery(phones):
    host=phones('HeistSolo','desktop');host.create('heist');ready(host)
    for i in [1,2,0]:
        host.page.locator(f'[data-hs-map="{i}"]').click()
        wait_state(host,lambda g:g['heist']['map']['id']==i)
        expect(host.page.locator(f'[data-hs-map="{i}"]')).to_have_attribute('aria-pressed','true')
    host.page.locator('.hs-primary[data-gact="start"]').click();wait_state(host,lambda g:g['phase']=='play')
    walk_x(host,7.5)
    expect(host.page.locator('.hs-action')).to_be_enabled()
    host.page.keyboard.press('Space')
    wait_state(host,lambda g:any(b['bag'] is not None for b in g['heist']['fighters']))
    walk_x(host,.8);expect(host.page.locator('.hs-action')).to_have_text('Déposer')
    host.page.keyboard.press('e')
    wait_state(host,lambda g:g['heist']['banked']==1)
    assert mine(host)['bag'] is None
    expect(host.page.locator('.hs-count')).to_have_text('Butin 1 / 4')


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
