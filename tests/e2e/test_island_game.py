"""Real browser UI and shared-state checks for the 3D island."""
from io import BytesIO
import pytest

# Browser dependencies are optional for the existing server-only CI job.
pytest.importorskip('playwright.sync_api')
Image = pytest.importorskip('PIL.Image')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state


@pytest.fixture
def phones(browser):
    server = Server()
    made = []
    def make(name, device='iphone'):
        phone = Phone(browser, server, name, device)
        made.append(phone)
        return phone
    yield make
    errors = [error for phone in made for error in phone.errors]
    for phone in made:
        phone.close()
    server_errors = server.errors()
    server.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, '\n'.join(errors)



def ready(phone):
    expect(phone.page.locator('.is-primary[data-gact="start"]')).to_be_enabled(timeout=20000)


def test_island_solo_keyboard_jump_and_replay(phones):
    host=phones('IslandSolo','desktop');host.create('island');ready(host)
    host.page.locator('.is-primary[data-gact="start"]').click()
    state=wait_state(host,lambda g:g['phase']=='play')
    pid=state['island']['me'];before=next(p for p in state['island']['fighters'] if p['pid']==pid)
    host.page.locator('.is-canvas').click(position={'x':500,'y':200})
    host.page.keyboard.down('ArrowRight');host.page.keyboard.down('Space')
    airborne=wait_state(host,lambda g:any(p['pid']==pid and p['z']>.1 for p in g['island']['fighters']))
    host.page.keyboard.up('Space')
    assert next(p for p in airborne['island']['fighters'] if p['pid']==pid)['x']>before['x']
    # Keep walking outward until the server records the fall.
    wait_state(host,lambda g:g['phase']=='results',timeout=12)
    host.page.keyboard.up('ArrowRight')
    expect(host.page.locator('.is-primary[data-gact="next"]')).to_be_visible()
    host.page.locator('.is-primary[data-gact="next"]').click()
    state=wait_state(host,lambda g:g['round']==2 and g['phase']=='countdown')
    assert state['island']['best'][pid]>0


def test_island_shared_round_late_join_and_host_departure(phones):
    host=phones('IslandHost','desktop');code=host.create('island');ready(host)
    friend=phones('IslandFriend');friend.join(code)
    wait_state(host,lambda g:len(g['players'])==2)
    host.page.locator('.is-primary[data-gact="start"]').click()
    a=wait_state(host,lambda g:g['phase']=='play');b=wait_state(friend,lambda g:g['phase']=='play')
    assert a['island']['tiles']==b['island']['tiles']
    assert len(b['island']['fighters'])==2 and not b['island']['solo']
    late=phones('IslandLate');late.join(code)
    late_state=wait_state(late,lambda g:g.get('me') is not None)
    assert late_state['me']['waiting']
    assert late_state['island']['me'] not in [p['pid'] for p in late_state['island']['fighters']]
    host.act('leave')
    state=wait_state(friend,lambda g:g['phase']=='results')
    assert state['island']['winner']==state['island']['me']
    assert state['island']['scores'][state['island']['me']]==1


def test_island_touch_controls_resize_and_network_recovery(phones):
    host=phones('IslandTouch');host.create('island');ready(host)
    # A real pixel check catches the mobile lobby WebGL/opaque-panel compositing regression.
    image=Image.open(BytesIO(host.page.screenshot())).convert('RGB')
    w,h=image.size
    pixels=list(image.crop((0,int(h*.24),w,int(h*.53))).getdata())
    green=sum(g>r*1.05 and g>b*1.2 and r>40 and g>60 for r,g,b in pixels)
    assert green>len(pixels)*.03, 'The 3D island must be visible above the lobby panel'
    host.page.locator('.is-primary[data-gact="start"]').click()
    initial=wait_state(host,lambda g:g['phase']=='play')
    pid=initial['island']['me'];before=initial['island']['fighters'][0]
    stick=host.page.locator('.is-stick').bounding_box();jump=host.page.locator('.is-jump').bounding_box()
    cdp=host.ctx.new_cdp_session(host.page)
    points=[{'x':stick['x']+stick['width']*.7,'y':stick['y']+stick['height']/2,'id':1},
            {'x':jump['x']+jump['width']/2,'y':jump['y']+jump['height']/2,'id':2}]
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points})
    state=wait_state(host,lambda g:any(p['pid']==pid and p['z']>.1 for p in g['island']['fighters']))
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    assert state['island']['fighters'][0]['x']>before['x']
    host.ctx.set_offline(True)
    expect(host.page.locator('.is-network')).to_contain_text('reconnexion',timeout=5000)
    host.ctx.set_offline(False)
    expect(host.page.locator('.is-network')).to_have_text('En ligne',timeout=8000)
    for width,height in [(320,740),(844,390)]:
        host.page.set_viewport_size({'width':width,'height':height})
        expect(host.page.locator('.is-jump')).to_be_in_viewport()
        assert host.page.evaluate("document.querySelector('.is-root').scrollWidth<=innerWidth")
    host.page.reload()
    expect(host.page.locator('.is-root')).to_be_visible()
    expect(host.page.locator('.is-network')).to_have_text('En ligne',timeout=15000)
    assert host.state()['island']['me']==pid

    # Minimize and re-enter: disposing WebGL must not leave event handlers alive.
    host.page.locator('[data-gdrawer="open"]').click()
    host.page.locator('#gDrawer [data-gdrawer="minimize"]').click()
    expect(host.page.locator('.is-root')).to_have_count(0)
    host.page.locator('[data-pyr="enter"]').first.click()
    expect(host.page.locator('.is-network')).to_have_text('En ligne',timeout=15000)
