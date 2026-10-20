"""Jeux à joystick : la moitié gauche de l'écran amène le joystick sous le doigt, la moitié droite le bouton d'action."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect
from tests.e2e.helpers import Phone, Server, wait_state


@pytest.fixture
def phones(browser):
    server=Server();made=[]
    def make(name):
        p=Phone(browser,server,name);made.append(p);return p
    yield make
    errors=[e for p in made for e in p.errors]
    for p in made:p.close()
    server.stop()
    assert not errors,'\n'.join(errors)


def under_finger(p,sel,fx,fy):
    r=p.page.locator(sel).bounding_box()
    assert abs(r['x']+r['width']/2-fx)<2 and abs(r['y']+r['height']/2-fy)<2,(sel,r,fx,fy)


def press(p,cdp,fx,fy,sel):
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':fx,'y':fy,'id':1}]})
    under_finger(p,sel,fx,fy)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    p.page.wait_for_timeout(100)
    assert 'translate' not in (p.page.locator(sel).get_attribute('style') or '')  # revenu à sa place


@pytest.mark.parametrize('kind,prefix,button',[('island','is','.is-jump'),('neon','nk','.nk-dash')])
def test_stick_left_and_action_right_follow_the_finger(phones,kind,prefix,button):
    p=phones('Float'+kind);code=p.create(kind)
    if kind=='neon':phones('Mate'+kind).join(code);wait_state(p,lambda g:len(g['players'])==2)
    start=p.page.locator(f'.{prefix}-primary[data-gact="start"]');expect(start).to_be_enabled(timeout=20000);start.tap()
    wait_state(p,lambda g:g['phase']=='play',timeout=15)
    expect(p.page.locator(button)).to_be_enabled(timeout=10000)
    cdp=p.ctx.new_cdp_session(p.page);vw=p.page.viewport_size
    press(p,cdp,vw['width']*.25,vw['height']*.4,f'.{prefix}-stick')
    press(p,cdp,vw['width']*.75,vw['height']*.4,button)
