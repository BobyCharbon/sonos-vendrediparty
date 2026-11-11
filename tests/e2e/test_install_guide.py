"""Guide « Installe Party ! » sur iPhone (retour de l'admin du 11.11.2026) : avec Safari 27 et la barre d'adresse en bas,
le bouton est à GAUCHE de l'adresse sur un grand iPhone (Pro Max, Plus, Air) mais à DROITE sur un iPhone ou un iPhone
Pro. Le guide le détecte par la largeur de l'écran : la flèche et le texte montrent le bon côté."""
import pytest

pytest.importorskip('playwright.sync_api')
from tests.e2e.helpers import Server

SAFARI_27 = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
             'Version/27.0 Mobile/15E148 Safari/604.1')


@pytest.fixture(scope='module')
def server():
    s = Server()
    yield s
    s.stop()


def guide(browser, server, width: int, height: int, bar: str):
    context = browser.new_context(viewport={'width': width, 'height': height}, screen={'width': width, 'height': height},
                                  user_agent=SAFARI_27, is_mobile=True, has_touch=True)
    context.add_init_script(f"localStorage.setItem('vp_bar', {bar!r})")
    page = context.new_page()
    page.goto(server.url + '/', wait_until='domcontentloaded')
    page.evaluate('openInstallSheet()')
    page.wait_for_selector('#iArrows .i-arrow')
    arrows = page.eval_on_selector_all('#iArrows .i-arrow', 'els => els.map((e) => e.className)')
    steps = page.inner_text('#iSteps')
    context.close()
    return arrows, steps


@pytest.mark.parametrize('name, width, height', [('iPhone 17', 402, 874), ('iPhone 17 Pro', 402, 874), ('iPhone 16e', 390, 844)])
def test_on_a_regular_or_pro_iphone_the_arrow_points_right(browser, server, name, width, height):
    arrows, steps = guide(browser, server, width, height, 'bottom')
    assert arrows == ['i-arrow at-br'], name
    assert 'à droite de l\'adresse' in steps and 'à gauche' not in steps


@pytest.mark.parametrize('name, width, height', [('iPhone 17 Pro Max', 440, 956), ('iPhone Air', 420, 912), ('iPhone 15 Plus', 430, 932)])
def test_on_a_large_iphone_the_arrow_points_left(browser, server, name, width, height):
    arrows, steps = guide(browser, server, width, height, 'bottom')
    assert arrows == ['i-arrow at-bl'], name
    assert 'à gauche de l\'adresse' in steps


def test_address_bar_on_top_stays_on_the_left(browser, server):
    arrows, steps = guide(browser, server, 402, 874, 'top')
    assert arrows == ['i-arrow at-tl'] and 'à gauche de l\'adresse' in steps
