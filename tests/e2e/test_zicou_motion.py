"""Zicou en mouvement (pet/motion.js, retour de l'admin du 5.11 : « fade, pas d'animation ») — vrai navigateur, iPhone.
Chaque moment pose SA classe d'animation et la retire ; les particules apparaissent puis disparaissent ; les jauges se
remplissent depuis l'ancienne valeur ; une seule pièce glisse vers le compteur ; « Réduire les animations » = rien de
long ; aucun débordement à 360 px ; aucune règle de hauteur ou de défilement sur html/body (CLAUDE.md, iOS 26)."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from tests.e2e.helpers import Phone, Server, sign_in
from tests.e2e.test_pet_game import PetSupabase, grown, open_pet
from tests.test_pet_api import TOK_A

ANIM_GONE_MS = 2500   # la plus longue animation ponctuelle (évolution) dure 1,8 s


def make_world(browser, device="iphone", reduced=False):
    supa = PetSupabase()
    server = Server(supa)
    phone = Phone(browser, server, "Alice", device=device)
    phone.ctx.add_init_script("localStorage.setItem('zc_onb', JSON.stringify({ step: 'done' }))")
    if reduced:
        phone.page.emulate_media(reduced_motion='reduce')
    return phone, supa, server


@pytest.fixture
def world(browser):
    made = []

    def build(**kw):
        made.append(make_world(browser, **kw))
        return made[-1][:2]
    yield build
    for phone, supa, server in made:
        errors, server_errors = phone.errors, server.errors()
        phone.close()
        server.stop()
        supa.stop()
        assert not server_errors, server_errors[-3000:]
        assert not errors, "\n".join(errors)


def signed_in_with_pet(world, **kw):
    gauges = kw.pop("gauges", {})
    phone, supa = world(**kw)
    phone.page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown(**gauges)
    supa.seed(supa.base.users[TOK_A], life, owner)
    return phone, supa, open_pet(phone)


def back_to_zicou(page):
    """Jeux puis Zicou par la barre d'onglets (la page n'est pas rechargée : motion.js se souvient de l'état d'avant)."""
    page.locator('#tabs [data-tab="games"]').click()
    expect(page.locator('#petRoot')).to_be_hidden()
    page.locator('#tabs [data-tab="pet"]').click()
    expect(page.locator('#petRoot .pt-hero')).to_be_visible()


def fx_count(root):
    return root.locator('.pt-m-fx .pt-m-p').count()


def test_opening_the_tab_animates_the_screen_and_zicou_says_hello(world):
    phone, _, root = signed_in_with_pet(world)
    expect(root.locator('.pt-gauges')).to_be_visible()
    assert 'pt-m-enter-open' in root.get_attribute('class')
    assert 'pt-m-hello' in root.locator('.pt-stage .pt-art').get_attribute('class')
    # Cascade : jauges, boutons et raccourcis portent leur rang.
    assert root.locator('.pt-gauges > li').first.evaluate("el => el.style.getPropertyValue('--i')") == '0'
    phone.page.wait_for_timeout(ANIM_GONE_MS)
    assert 'pt-m-enter' not in root.get_attribute('class')
    assert 'pt-m-hello' not in root.locator('.pt-stage .pt-art').get_attribute('class')
    # Au repos : les yeux clignent, le regard est prêt à suivre le doigt (pt-face).
    assert root.locator('.pt-stage .pt-eyes').evaluate("el => getComputedStyle(el).animationName") == 'pt-blink'
    assert root.locator('.pt-stage .pt-face').count() == 1


def test_each_care_action_has_its_own_animation_and_particles_that_go_away(world):
    phone, _, root = signed_in_with_pet(world, gauges={"food": 40, "care": 40})
    page = phone.page
    for action, cls in (("feed", "pt-m-eat"), ("heal", "pt-m-wash"), ("cuddle", "pt-m-hug")):
        root.locator(f'[data-pt="act"][data-a="{action}"]').click()
        page.wait_for_function(f"document.querySelector('#petRoot .pt-stage .pt-art')?.classList.contains('{cls}')")
        assert fx_count(root) > 0
        page.wait_for_function(f"!document.querySelector('#petRoot .pt-stage .pt-art').classList.contains('{cls}')"
                               " && !document.querySelector('#petRoot .pt-m-fx')", timeout=ANIM_GONE_MS + 1500)
    # Le ventre est monté de 40 à 70 : la barre part de l'ancienne valeur, « +30 » s'envole.
    root.locator('[data-pt="act"][data-a="feed"]').click()
    page.wait_for_function("document.querySelector('#petRoot .pt-gauge .pt-bar i')?.classList.contains('pt-m-fill')")
    assert root.locator('.pt-gauge').first.locator('.pt-m-delta').inner_text() == '+30'
    # Dodo puis réveil : chacun son geste.
    root.locator('[data-pt="act"][data-a="sleep"]').click()
    page.wait_for_function("document.querySelector('#petRoot .pt-stage .pt-art')?.classList.contains('pt-m-sleep')")
    root.locator('[data-pt="act"][data-a="wake"]').click()
    page.wait_for_function("document.querySelector('#petRoot .pt-stage .pt-art')?.classList.contains('pt-m-wake')")
    page.wait_for_function("!document.querySelector('#petRoot .pt-stage .pt-art').classList.contains('pt-m-wake')",
                           timeout=ANIM_GONE_MS)


def test_tapping_zicou_reacts_and_buttons_bounce(world):
    phone, _, root = signed_in_with_pet(world)
    page = phone.page
    root.locator('[data-pt="pet"]').click()   # câlin
    page.wait_for_function("document.querySelector('#petRoot .pt-stage .pt-art')?.classList.contains('pt-m-hug')")
    assert root.locator('[data-a="cuddle"] .pt-act-i').get_attribute('class').split().count('pt-m-press') == 1


def test_screens_slide_deeper_and_back_and_lists_cascade(world):
    phone, _, root = signed_in_with_pet(world)
    page = phone.page
    page.wait_for_timeout(1200)
    root.locator('[data-pt="streak"]').click()
    expect(root.locator('.pt-streak')).to_be_visible()
    assert 'pt-m-enter-deeper' in root.get_attribute('class')
    assert root.locator('.pt-miles > li').first.evaluate("el => el.style.getPropertyValue('--i')") == '0'
    root.locator('[data-pt="home"]').click()
    expect(root.locator('.pt-gauges')).to_be_visible()
    assert 'pt-m-enter-back' in root.get_attribute('class')
    page.wait_for_function("!document.querySelector('#petRoot').className.includes('pt-m-enter')", timeout=ANIM_GONE_MS)


def test_coins_earned_count_up_and_a_single_coin_glides(world):
    phone, supa, root = signed_in_with_pet(world)
    page = phone.page
    chip = root.locator('.pt-chip[data-pt="treasures"]')
    expect(chip).to_be_visible()
    before = int(chip.get_attribute('aria-label').split()[0])
    supa.base.pets[supa.base.users[TOK_A]]["owner"].setdefault("loop", {})["coins"] = before + 25
    back_to_zicou(page)   # on quitte l'onglet, on y revient (sans recharger) : 25 pièces gagnées entre-temps
    page.wait_for_function("document.querySelectorAll('.pt-m-coin').length === 1")   # une seule pièce, jamais une pluie
    expect(root.locator('.pt-chip[data-pt="treasures"]')).to_have_text(f'🪙 {before + 25}', timeout=3000)
    page.wait_for_function("!document.querySelector('.pt-m-coin')", timeout=ANIM_GONE_MS)


def test_hatching_cracks_the_egg_and_zicou_is_born(world):
    phone, supa = world()
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    from app import pet
    from datetime import datetime, timezone
    life, owner = pet.new_pet(datetime.now(timezone.utc))
    supa.seed(supa.base.users[TOK_A], life, owner)
    root = open_pet(phone)
    expect(root.locator('.pt-count')).to_be_visible()
    page.evaluate("PetMotion.hatch(document.querySelector('#petRoot'))")
    assert 'pt-m-crack' in root.locator('.pt-stage').get_attribute('class')
    assert root.locator('.pt-m-cracks path').count() == 2
    # Il a éclos entre-temps : à la relecture, Zicou apparaît (pt-m-born) avec ses éclats de coquille.
    hatched, owner2 = grown()
    hatched["gen"] = life["gen"]
    supa.seed(supa.base.users[TOK_A], hatched, owner2)
    back_to_zicou(page)
    page.wait_for_function("document.querySelector('#petRoot .pt-stage .pt-art')?.classList.contains('pt-m-born')")
    assert root.locator('.pt-m-shell').count() > 0
    page.wait_for_function("!document.querySelector('#petRoot .pt-stage .pt-art').classList.contains('pt-m-born')", timeout=ANIM_GONE_MS)


def test_reduced_motion_means_no_particles_no_bounce_only_a_short_fade(world):
    phone, _, root = signed_in_with_pet(world, reduced=True, gauges={"food": 40})
    page = phone.page
    expect(root.locator('.pt-gauges')).to_be_visible()
    root.locator('[data-pt="act"][data-a="feed"]').click()
    expect(root.locator('.pt-gauges .pt-bar').first).to_have_attribute('aria-valuenow', '70')
    page.wait_for_timeout(150)
    assert fx_count(root) == 0 and page.locator('.pt-m-coin').count() == 0
    assert 'pt-m-eat' not in root.locator('.pt-stage .pt-art').get_attribute('class')
    assert root.locator('.pt-stage .pt-art').evaluate("el => getComputedStyle(el).animationName") == 'none'
    assert root.locator('.pt-gauge .pt-bar i').first.evaluate("el => getComputedStyle(el).animationName") == 'none'
    assert root.locator('.pt-stage .pt-eyes').evaluate("el => getComputedStyle(el).animationName") == 'none'
    # Le seul mouvement gardé : un fondu d'écran court (0,2 s).
    dur = root.evaluate("el => parseFloat(getComputedStyle(el).animationDuration)")
    assert dur <= 0.2


def test_no_horizontal_overflow_at_360px_while_particles_fly(world):
    phone, _, root = signed_in_with_pet(world, gauges={"food": 40})
    page = phone.page
    page.set_viewport_size({"width": 360, "height": 780})
    root.locator('[data-pt="act"][data-a="feed"]').click()
    page.wait_for_function("document.querySelector('#petRoot .pt-m-fx')")
    page.wait_for_timeout(500)   # particules au plus loin
    assert page.evaluate("document.scrollingElement.scrollWidth") <= 360
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'
    assert page.evaluate("getComputedStyle(document.documentElement).overflowY") != 'hidden'
