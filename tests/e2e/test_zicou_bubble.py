"""Bulle de Zicou (avis 3cd6d282745b de l'admin, 08.11) dans un vrai navigateur (iPhone), serveur Party réel, Supabase
simulé : dans l'app iOS BETA, la page décrit Zicou à la bulle native (PartyNative.zicou) et cache sa pastille ; la bulle
s'efface pendant une partie, dans l'onglet Zicou et sous une feuille ; son toucher ouvre Zicou ; dans le navigateur,
Réglages › « Bulle de Zicou » masque la pastille sur cet appareil."""
import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.helpers import sign_in
from tests.e2e.test_pet_game import grown
from tests.e2e.test_zicou_home import uid, world  # noqa: F401  (fixture)
from tests.test_pet_api import TOK_A

DONE = "localStorage.setItem('zc_onb', JSON.stringify({ step: 'done' }))"
# App iOS BETA simulée : barre native et bulle native (chaque description reçue est gardée).
NATIVE_ZICOU = """
window.__zicou = [];
window.PartyNative = { platform: "ios",
  tabs: { update: (s) => { window.__tabs = s; } },
  zicou: { update: (s) => { window.__zicou.push(s); } },
  push: { register: () => Promise.reject(new Error("non")), status: () => Promise.resolve({ status: "denied" }) } };
"""


def last(page) -> dict:
    return page.evaluate("window.__zicou[window.__zicou.length - 1] || null")


def wait_state(page, condition: str) -> dict:
    page.wait_for_function(f"(() => {{ const s = window.__zicou[window.__zicou.length - 1]; return !!s && ({condition}); }})()")
    return last(page)


def test_native_app_draws_the_bubble_and_the_page_hides_its_own(world):
    phone, supa = world
    page = phone.page
    phone.ctx.add_init_script(DONE)
    phone.ctx.add_init_script(NATIVE_ZICOU)
    life, owner = grown(food=10)                                      # il a faim : point rouge
    supa.seed(uid(supa), life, owner)
    page.goto("/")
    page.evaluate("PartyTabs.select('games')")
    sign_in(phone, TOK_A)

    state = wait_state(page, "s.visible")
    assert state["red"] is True and state["emotion"] == "hungry" and state["stage"] != "egg"
    assert state["label"] == "Zicou : a faim, il a besoin de toi"
    assert page.evaluate("document.documentElement.classList.contains('native-zicou')")
    expect(page.locator("#zicouChip")).to_be_hidden()                 # l'app la dessine : pas de double
    expect(page.locator("#zicouFloat")).to_be_hidden()

    # Partie en plein écran, feuille du module Événements : la bulle native s'efface puis revient.
    page.evaluate("document.body.classList.add('pyr-full')")
    wait_state(page, "!s.visible")
    page.evaluate("document.body.classList.remove('pyr-full')")
    wait_state(page, "s.visible")
    page.evaluate("document.documentElement.classList.add('events-sheet')")
    wait_state(page, "!s.visible")
    page.evaluate("document.documentElement.classList.remove('events-sheet')")
    wait_state(page, "s.visible")

    # Toucher de la bulle (l'app appelle ZicouHome.openFromApp) : l'onglet Zicou, où elle n'a plus lieu d'être.
    page.evaluate("ZicouHome.openFromApp()")
    page.wait_for_function("document.body.dataset.tab === 'pet'")
    wait_state(page, "!s.visible")
    page.evaluate("PartyTabs.select('events')")
    wait_state(page, "s.visible")
    assert len(page.evaluate("window.__zicou")) < 40                 # pas d'envoi en boucle : seulement les changements


def test_native_bubble_gives_the_daily_gift_hint_once(world):
    phone, supa = world
    page = phone.page
    phone.ctx.add_init_script(DONE)
    phone.ctx.add_init_script(NATIVE_ZICOU)
    life, owner = grown(food=90)
    supa.seed(uid(supa), life, owner)
    page.goto("/")
    page.evaluate("PartyTabs.select('games')")
    sign_in(phone, TOK_A)
    wait_state(page, "s.visible")
    # Coffre du jour prêt : le petit message passe par la bulle native, une fois par jour.
    page.evaluate("""ZicouHome.petChanged({ name: 'Zicou', stage: 'adult', variant: 'classic', emotion: 'happy',
                     daily: { chest: { state: 'ready' } } }, [])""")
    state = wait_state(page, "s.hint")
    assert state["hint"] == "Psst… ton cadeau du jour ! 🎁"
    expect(page.locator(".zc-bubble")).to_have_count(0)               # aucune bulle web par-dessus
    page.evaluate("ZicouHome.refresh(true)")
    page.wait_for_timeout(300)
    hints = [s.get("hint") for s in page.evaluate("window.__zicou")]
    # L'app ne l'affiche qu'à son apparition (onChange) : il n'apparaît qu'une fois, même relu ensuite.
    appears = sum(1 for before, now in zip([None, *hints], hints) if now and not before)
    assert appears == 1


def test_browser_settings_switch_hides_the_bubble_on_this_device(world):
    phone, supa = world
    page = phone.page
    phone.ctx.add_init_script(DONE)
    life, owner = grown(food=90)
    supa.seed(uid(supa), life, owner)
    page.goto("/")
    sign_in(phone, TOK_A)
    page.locator('#tabs [data-tab="games"]').click()
    chip = page.locator("#zicouChip")
    expect(chip).to_be_visible()
    assert not page.evaluate("document.documentElement.classList.contains('native-zicou')")
    # Réglages du module (même origine) : le choix est gardé et la page suit sans recharger.
    page.evaluate("localStorage.setItem('zc_bubble_off', '1'); postMessage({ type: 'party-events:zicou-bubble', on: false }, location.origin)")
    expect(chip).to_be_hidden()
    page.reload()
    page.locator('#tabs [data-tab="games"]').click()
    page.wait_for_timeout(1500)
    expect(chip).to_be_hidden()                                       # retenu sur cet appareil
    page.evaluate("ZicouHome.setBubble(true)")
    expect(chip).to_be_visible()
    assert page.evaluate("localStorage.getItem('zc_bubble_off')") is None
