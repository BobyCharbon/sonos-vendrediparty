"""Zicou qui dort (retour de l'admin, 6.11.2026 : « Je ne comprends pas comment allumer la lumière »), dans un vrai
navigateur (iPhone) : trois états bien distincts — fatigué (il propose « Dodo », pas de Zzz), endormi (bouton
« Réveiller » visible, Zzz, nuit), réveillé ; toucher un soin pendant son sommeil propose « Le réveiller ? ». Un état
affiché périmé (le serveur l'a endormi entre-temps) est relu au premier refus. Mise en page de l'onglet : un seul titre
« Zicou », jamais dessiné sur la barre d'état (zone sûre simulée : 47 px), dans la PWA et dans l'app native.
Serveur Party réel ; Supabase simulé (PetSupabase)."""
import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.helpers import Phone, Server, sign_in
from tests.e2e.test_pet_game import PetSupabase, grown
from tests.e2e.test_zicou_home import NATIVE
from tests.test_pet_api import TOK_A

import re

SAFE_TOP = 47
ANIM = {"sleep": re.compile(r"\bpt-m-sleep\b"), "wake": re.compile(r"\bpt-m-wake\b")}
# Chromium n'a pas d'encoche : on donne à la page la zone sûre d'un iPhone (mêmes règles que env(safe-area-inset-top)).
SAFE_AREA = f"""
document.addEventListener("DOMContentLoaded", () => {{
  const s = document.createElement("style");
  s.textContent = `body {{ padding-top: {SAFE_TOP}px !important; }}
    .nav-bar {{ padding-top: {SAFE_TOP}px !important; height: {44 + SAFE_TOP}px !important; }}`;
  document.head.append(s);
}});
"""


@pytest.fixture
def world(browser):
    supa = PetSupabase()
    server = Server(supa)
    phone = Phone(browser, server, "Alice")
    phone.ctx.add_init_script("localStorage.setItem('zc_onb', JSON.stringify({ step: 'done' }))")
    yield phone, supa
    errors, server_errors = phone.errors, server.errors()
    phone.close()
    server.stop()
    supa.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, "\n".join(errors)


def open_tab(phone, supa, life, owner):
    supa.seed(supa.base.users[TOK_A], life, owner)
    page = phone.page
    page.goto("/")
    sign_in(phone, TOK_A)
    page.evaluate("showTab('pet')")
    root = page.locator("#petRoot")
    expect(root.locator(".pt-gauges")).to_be_visible()
    return page, root


def server_life(supa):
    return supa.base.pets[supa.base.users[TOK_A]]["life"]


def test_tired_but_awake_offers_dodo_without_zzz(world):
    phone, supa = world
    life, owner = grown(energy=12)
    page, root = open_tab(phone, supa, life, owner)
    expect(root.locator(".pt-line")).to_contain_text("bâille… une petite sieste ?")
    expect(root.locator(".pt-hero.pt-night")).to_have_count(0)
    expect(root.locator(".pt-stage .pt-z")).to_have_count(0)   # les Zzz, c'est seulement quand il dort
    dodo = root.locator('[data-pt="act"][data-a="sleep"]')
    expect(dodo).to_contain_text("Dodo")
    expect(dodo).to_have_class("pt-act pt-light pt-suggest")   # fatigué : le bouton Dodo est mis en avant
    expect(root.locator('[data-a="wake"]')).to_have_count(0)
    phone.shot("zicou-fatigue-dodo")
    dodo.click()
    expect(root.locator(".pt-hero.pt-night")).to_be_visible()
    expect(root.locator(".pt-stage .pt-art")).to_have_class(ANIM["sleep"])   # motion.js : le geste du dodo
    expect(root.locator(".pt-m-zz").first).to_be_attached()                   # … et ses « z » qui flottent
    expect(root.locator('[data-pt="act"][data-a="wake"]')).to_contain_text("Réveiller")
    assert server_life(supa)["asleep"]


def test_asleep_shows_a_clear_wake_button_and_a_care_asks_to_wake_him(world):
    phone, supa = world
    life, owner = grown(energy=30)
    life["asleep"] = True
    page, root = open_tab(phone, supa, life, owner)
    expect(root.locator(".pt-line")).to_contain_text("fait de beaux rêves")
    expect(root.locator(".pt-hero.pt-night")).to_be_visible()
    expect(root.locator(".pt-stage .pt-z")).to_have_count(1)
    wake = root.locator('[data-pt="act"][data-a="wake"]')
    expect(wake).to_be_visible()
    expect(wake.locator(".pt-act-i")).to_have_text("☀️")
    expect(wake).to_contain_text("Réveiller")
    expect(wake).to_contain_text("Allumer la lumière")
    expect(root.locator('[data-a="sleep"]')).to_have_count(0)

    feed = root.locator('[data-a="feed"]')
    feed.evaluate("el => el.scrollIntoView({ block: 'center' })")
    feed.click(force=True)   # aria-disabled : il dort
    ask = root.locator(".pt-wake-ask")
    expect(ask).to_be_visible()
    expect(ask).to_contain_text("Le réveiller ?")
    ask.locator('[data-pt="wake-no"]').click()   # « Laisser dormir »
    expect(ask).to_have_count(0)
    assert server_life(supa)["asleep"]

    feed.click(force=True)
    phone.shot("zicou-dort-reveiller")
    root.locator('.pt-wake-ask [data-pt="act"][data-a="wake"]').click()
    expect(root.locator(".pt-hero.pt-night")).to_have_count(0)
    expect(root.locator(".pt-stage .pt-art")).to_have_class(ANIM["wake"])    # motion.js : le réveil
    expect(root.locator(".pt-m-ray").first).to_be_attached()                  # … et ses rayons
    expect(root.locator(".pt-wake-ask")).to_have_count(0)
    expect(root.locator('[data-pt="act"][data-a="sleep"]')).to_contain_text("Dodo")
    assert not server_life(supa)["asleep"]


def test_a_stale_awake_screen_is_resynced_when_the_server_put_him_to_sleep(world):
    """Énergie affichée 0 mais encore éveillé ; le serveur l'endort tout seul. Le soin refusé relit l'état :
    plus de « Dodo » trompeur, le bouton Réveiller apparaît et la question « Le réveiller ? » aussi."""
    phone, supa = world
    life, owner = grown(energy=0.3)
    page, root = open_tab(phone, supa, life, owner)
    expect(root.locator('[data-pt="act"][data-a="sleep"]')).to_be_visible()
    server_life(supa)["asleep"] = True   # pendant ce temps, côté serveur : épuisé, il s'est endormi
    root.locator('[data-pt="act"][data-a="cuddle"]').click()
    expect(root.locator(".pt-hero.pt-night")).to_be_visible()
    expect(root.locator('[data-pt="act"][data-a="wake"]').first).to_be_visible()
    expect(root.locator(".pt-wake-ask")).to_contain_text("Le réveiller ?")
    expect(root.locator(".pt-live")).not_to_contain_text("Rallume la lumière")


@pytest.mark.parametrize("native", [False, True], ids=["pwa", "app-native"])
def test_zicou_tab_has_one_title_never_under_the_status_bar(world, native):
    phone, supa = world
    phone.ctx.add_init_script(SAFE_AREA)
    if native:
        phone.ctx.add_init_script(NATIVE)
    life, owner = grown()
    page, root = open_tab(phone, supa, life, owner)
    if native:
        assert page.evaluate("document.documentElement.classList.contains('native-tabs')")
    # Un seul titre « Zicou » : le grand titre de l'onglet (pas de second titre centré dans le panneau).
    expect(page.locator("#appTitle")).to_have_text("Zicou")
    expect(root.locator("h1.pt-title")).to_have_count(0)
    top = page.evaluate("document.getElementById('appTitle').getBoundingClientRect().top")
    assert top >= SAFE_TOP, top
    phone.shot(f"zicou-haut-{'native' if native else 'pwa'}")
    # Un petit défilement : le grand titre reste sous la barre d'état, rien ne bouge.
    page.evaluate("scrollTo(0, 8)")
    page.wait_for_timeout(150)
    assert page.evaluate("document.getElementById('appTitle').getBoundingClientRect().top") >= SAFE_TOP
    assert not page.evaluate("document.body.classList.contains('nav-compact')")
    # Plus loin : avant que le grand titre n'atteigne l'heure, la barre translucide et le petit titre le couvrent.
    page.evaluate("scrollTo(0, 30)")
    page.wait_for_function("document.body.classList.contains('nav-compact')")
    box = page.evaluate("(() => { const r = document.getElementById('appTitle').getBoundingClientRect(); return [r.top, r.bottom]; })()")
    assert box[1] <= SAFE_TOP + 44, box   # entièrement sous la barre (barre d'état + 44 px)
    expect(page.locator("#navBar")).to_have_css("opacity", "1")
    expect(page.locator("#navBarTitle")).to_have_text("Zicou")
    phone.shot(f"zicou-titre-defile-{'native' if native else 'pwa'}")
    page.evaluate("scrollTo(0, 0)")
    page.wait_for_function("!document.body.classList.contains('nav-compact')")
    expect(page.locator("#navBar")).to_have_css("opacity", "0")


def test_a_renamed_zicou_keeps_his_name_on_screen(world):
    phone, supa = world
    life, owner = grown()
    life["name"] = "Bijou"
    page, root = open_tab(phone, supa, life, owner)
    expect(root.locator("h1.pt-title")).to_have_text("Bijou")   # son nom, sous le grand titre « Zicou »
