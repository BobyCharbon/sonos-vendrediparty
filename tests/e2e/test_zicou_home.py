"""Zicou dans l'app (décision de l'admin du 4.11, maquettes « Où vit Zicou »), dans un vrai navigateur (iPhone) :
onglet « Zicou » (A), pastille dans l'en-tête (C), accueil en 5 écrans + rappel doux + invité sans compte, « Ton avis »
devenu une page des Réglages (liens profonds compris). Serveur Party réel ; Supabase simulé (PetSupabase)."""
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from app import pet
from tests.e2e.helpers import FakeSupabase, Phone, Server, sign_in
from tests.e2e.test_pet_game import PetSupabase, grown
from tests.test_pet_api import TOK_A

DAY_MS = 86400000
# App iOS native simulée : barre native + notifications natives (la demande système répond « oui »).
NATIVE = """
window.__pushAsked = 0;
window.PartyNative = { platform: "ios",
  tabs: { update: (s) => { window.__tabs = s; } },
  push: { register: () => { window.__pushAsked += 1; return Promise.resolve({ token: "ab".repeat(32), environment: "sandbox", bundleId: "ch.test" }); },
          status: () => Promise.resolve({ status: "granted" }) } };
"""


@pytest.fixture
def world(browser):
    supa = PetSupabase()
    server = Server(supa)
    phone = Phone(browser, server, "Alice")
    yield phone, supa
    errors, server_errors = phone.errors, server.errors()
    phone.close()
    server.stop()
    supa.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, "\n".join(errors)


def uid(supa):
    return supa.base.users[TOK_A]


def onb(page) -> dict:
    return page.evaluate("JSON.parse(localStorage.getItem('zc_onb') || '{}')")


def hatch_now(supa):
    """L'œuf a été pondu il y a 4 min : il éclot à la prochaine lecture."""
    supa.base.pets[uid(supa)]["life"]["born_at"] = pet.iso(datetime.now(timezone.utc) - timedelta(minutes=4))


def test_zicou_tab_between_games_and_events_and_guest_is_invited_to_adopt(world):
    phone, _ = world
    page = phone.page
    page.goto("/")
    ids = page.locator("#tabs button[data-tab]:visible").evaluate_all("els => els.map((b) => b.dataset.tab)")
    assert ids == ["music", "games", "pet", "events", "account"]   # « Ton avis » n'est plus dans la barre
    assert page.locator('#tabs [data-tab="pet"] span').inner_text() == "Zicou"
    expect(page.locator("#zicouChip")).to_be_hidden()               # sans compte : pas de pastille
    page.locator('#tabs [data-tab="pet"]').click()
    root = page.locator("#petRoot")
    expect(root.locator(".pt-login h2")).to_have_text("Adopte ton Zicou")
    expect(root.locator('[data-pt="login"]')).to_have_text("Créer mon compte")
    expect(page.locator("#appTitle")).to_have_text("Zicou")
    expect(page.locator("#tabs")).to_be_visible()                    # le panneau vit dans l'onglet, la barre reste
    phone.shot("zicou-0-invite")
    root.locator('[data-pt="login"]').click()
    assert page.evaluate("document.body.dataset.tab") == "account"   # parcours de connexion existant (SMS)


def test_welcome_flow_name_hatch_gift_then_notifications(world):
    phone, supa = world
    page = phone.page
    phone.ctx.add_init_script(NATIVE)
    patches, pushes = [], []
    page.route("**/api/account/notifications/update", lambda r: (patches.append(json.loads(r.request.post_data)), r.fulfill(json={"prefs": {}}))[1])
    page.route("**/api/account/push", lambda r: (pushes.append(json.loads(r.request.post_data)), r.fulfill(json={"ok": True}))[1])
    page.goto("/")
    page.evaluate("PartyTabs.select('games')")   # un onglet affiché par la page (Musique est native dans l'app)
    sign_in(phone, TOK_A)

    # 1. « Quelqu'un t'attend… » : une feuille, pas un mur ; rien n'est encore créé.
    sheet = page.locator("#zicouSheet")
    expect(sheet.locator("h2")).to_have_text("Quelqu'un t'attend…")
    expect(sheet.locator("[data-zc-close]")).to_have_text("Plus tard")
    assert uid(supa) not in supa.base.pets
    phone.shot("zicou-1-accueil")
    sheet.locator('[data-zc="discover"]').click()

    # 2. Le nom : prérempli, suggestions, modération du serveur.
    expect(sheet.locator("h2")).to_have_text("Comment va-t-il s'appeler ?")
    assert sheet.locator("#zcName").input_value() in ("Paillette", "Disco", "Bobby")
    sheet.locator('[data-zc="pick"][data-n="Bobby"]').click()
    expect(sheet.locator(".zc-count")).to_have_text("5/16")
    phone.shot("zicou-2-nom")
    sheet.locator(".zc-name [type=submit]").click()

    # 3. Éclosion : 3 min, sans attendre ici.
    expect(sheet.locator("h2")).to_have_text("Bobby éclot bientôt")
    expect(sheet.locator("[data-zc-clock]")).to_contain_text("2:5")
    assert supa.base.pets[uid(supa)]["life"]["name"] == "Bobby"
    phone.shot("zicou-3-eclosion")
    sheet.locator("[data-zc-close]").click()                         # « Explorer l'app »
    expect(sheet).to_be_hidden()
    chip = page.locator("#zicouChip")
    expect(chip).to_be_visible()
    expect(chip).to_have_class("zc-chip zc-egg zc-hello")              # l'œuf dans l'en-tête, un petit salut la 1re fois

    # 4. Éclosion (le serveur fait foi) : premier cadeau garanti, déjà porté.
    hatch_now(supa)
    page.evaluate("ZicouHome.refresh(true)")
    expect(sheet.locator("h2")).to_have_text("Coucou, je suis Bobby !")
    expect(sheet.locator(".zc-gift")).to_contain_text("Nœud papillon · 50 pièces · garanti")
    saved = supa.base.pets[uid(supa)]
    assert saved["owner"]["welcome"]["item"] == "noeud" and saved["owner"]["loop"]["coins"] == 50
    assert saved["life"]["acc"]["neck"] == "noeud"
    assert pushes == [] and page.evaluate("__pushAsked") == 0        # pas de demande de notifications avant le cadeau
    phone.shot("zicou-4-cadeau")
    sheet.locator('[data-zc="open-gift"]').click()

    # 5. Notifications, au bon moment : explication, choix par catégorie, PUIS la demande du système.
    expect(sheet.locator("h2")).to_have_text("Je te préviens quand j'ai besoin de toi ?")
    phone.shot("zicou-5-notifications")
    sheet.locator('[data-pref="pet_gifts"]').uncheck(force=True)
    sheet.locator('[data-zc="notif-yes"]').click()
    expect(sheet).to_be_hidden()
    assert patches[-1]["patch"] == {"pet_daily": True, "pet_gifts": False, "pet_alerts": True}
    assert page.evaluate("__pushAsked") == 1 and pushes[-1]["device"] == "ab" * 32 and pushes[-1]["on"] is True
    assert onb(page)["step"] == "done"
    # Coffre du jour prêt : un point sur l'onglet Zicou de la barre native, jamais un chiffre.
    page.wait_for_function("window.__tabs && window.__tabs.tabs.find((t) => t.id === 'pet').badge === ''")
    expect(chip.locator(".zc-dot")).to_be_hidden()                          # … et pas de point rouge pour un coffre


def test_header_badge_mood_rare_red_dot_and_hidden_during_a_game(world):
    phone, supa = world
    page = phone.page
    phone.ctx.add_init_script("localStorage.setItem('zc_onb', JSON.stringify({ step: 'done' }))")
    page.emulate_media(reduced_motion="reduce")
    life, owner = grown(food=10)                                       # il a faim : point rouge
    supa.seed(uid(supa), life, owner)
    page.goto("/")
    sign_in(phone, TOK_A)
    page.locator('#tabs [data-tab="games"]').click()
    chip = page.locator("#zicouChip")
    expect(chip).to_be_visible()
    expect(chip.locator(".zc-dot")).to_be_visible()
    expect(chip).to_have_attribute("aria-label", "Zicou : a faim, il a besoin de toi")
    assert "255, 181, 71" in chip.evaluate("el => getComputedStyle(el).boxShadow") or chip.evaluate("el => el.style.getPropertyValue('--zc-mood')")
    assert chip.locator(".pt-body").first.evaluate("el => getComputedStyle(el).animationName") == "none"   # animations réduites
    assert not chip.inner_text().strip()                                # jamais de chiffre
    phone.shot("zicou-6-pastille")
    # Partie en plein écran : la pastille s'efface.
    page.evaluate("document.body.classList.add('pyr-full')")
    expect(chip).to_be_hidden()
    page.evaluate("document.body.classList.remove('pyr-full')")
    expect(chip).to_be_visible()
    # Repas : plus de point rouge ; toucher la pastille ouvre l'onglet Zicou.
    supa.base.pets[uid(supa)]["life"]["g"]["food"] = 90
    page.evaluate("ZicouHome.refresh(true)")
    expect(chip.locator(".zc-dot")).to_be_hidden()
    chip.click()
    page.wait_for_function("document.body.dataset.tab === 'pet'")
    expect(page.locator("#petRoot .pt-gauges")).to_be_visible()
    expect(chip).to_be_hidden()                                         # on y est déjà


def test_later_then_gentle_reminder_three_times_at_most(world):
    phone, _ = world
    page = phone.page
    page.goto("/")
    page.locator('#tabs [data-tab="games"]').click()
    sign_in(phone, TOK_A)
    sheet = page.locator("#zicouSheet")
    expect(sheet.locator("h2")).to_have_text("Quelqu'un t'attend…")
    sheet.locator("[data-zc-close]").click()                           # « Plus tard » : rien n'est pénalisé
    expect(sheet).to_be_hidden()
    assert onb(page)["step"] == "later"
    page.reload()
    page.locator('#tabs [data-tab="games"]').click()
    page.wait_for_timeout(1500)
    expect(page.locator(".zc-remind")).to_have_count(0)                # jamais le jour même
    for shown in range(1, 4):
        page.evaluate(f"""() => {{ const s = JSON.parse(localStorage.getItem('zc_onb'));
            s.laterAt = Date.now() - 2 * {DAY_MS}; s.remindedAt = Date.now() - {DAY_MS}; localStorage.setItem('zc_onb', JSON.stringify(s)); }}""")
        page.reload()
        page.locator('#tabs [data-tab="games"]').click()
        card = page.locator(".zc-remind")
        expect(card).to_contain_text("Ton œuf a bougé…")
        assert onb(page)["reminders"] == shown
        if shown == 1:
            phone.shot("zicou-7-rappel")
        card.locator('[data-zc-remind="close"]').click()
        expect(card).to_have_count(0)
    page.evaluate(f"""() => {{ const s = JSON.parse(localStorage.getItem('zc_onb'));
        s.remindedAt = Date.now() - {DAY_MS}; localStorage.setItem('zc_onb', JSON.stringify(s)); }}""")
    page.reload()
    page.locator('#tabs [data-tab="games"]').click()
    page.wait_for_timeout(1500)
    expect(page.locator(".zc-remind")).to_have_count(0)                # 3 fois au plus
    # Ensuite l'œuf ne reste que dans l'onglet Zicou : « Le découvrir » y reprend au nom.
    page.locator("#zicouChip").click()
    expect(sheet.locator("h2")).to_have_text("Comment va-t-il s'appeler ?")


def pull_down(page, surface):
    box = surface.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + 30
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x, y + 400, steps=8)
    page.mouse.up()


@pytest.mark.parametrize("how", ["swipe", "later", "backdrop"])
def test_closing_the_welcome_sheet_lays_no_egg_and_the_tab_offers_adoption(world, how):
    """Bug de l'admin du 5.11 : feuille d'accueil baissée d'un geste… et pourtant l'œuf pondu puis éclos. Fermer
    (geste vers le bas, « Plus tard », toucher à côté) ne pond rien ; seul « Continuer » après le nom pond l'œuf."""
    phone, supa = world
    page = phone.page
    page.goto("/")
    page.locator('#tabs [data-tab="games"]').click()
    sign_in(phone, TOK_A)
    sheet = page.locator("#zicouSheet")
    expect(sheet.locator("h2")).to_have_text("Quelqu'un t'attend…")
    page.wait_for_timeout(400)
    if how == "swipe":
        pull_down(page, sheet.locator(".zc-sheet"))
    elif how == "later":
        sheet.locator("[data-zc-close]").click()
    else:
        page.mouse.click(10, 10)                                       # le fond, au-dessus de la feuille
    expect(sheet).to_be_hidden()
    assert onb(page)["step"] == "later"
    # Rechargé, puis l'onglet Zicou (et la pastille, l'en-tête) : toujours aucun œuf, l'écran d'adoption.
    page.reload()
    page.locator('#tabs [data-tab="pet"]').click()
    root = page.locator("#petRoot")
    expect(root.locator(".pt-adopt h2")).to_have_text("Quelqu'un t'attend…")
    page.evaluate("ZicouHome.refresh(true)")
    page.wait_for_timeout(1500)
    assert uid(supa) not in supa.base.pets
    assert page.evaluate("ZicouHome.state().status.adopted") is False
    expect(page.locator("#zicouSheet [data-zc-clock]")).to_have_count(0)  # aucun compte à rebours
    # Adoption explicite depuis l'onglet : le nom, puis l'œuf (et lui seul) est pondu.
    root.locator('[data-pt="adopt"]').click()
    expect(sheet.locator("h2")).to_have_text("Comment va-t-il s'appeler ?")
    sheet.locator('[data-zc="pick"][data-n="Bobby"]').click()
    sheet.locator(".zc-name [type=submit]").click()
    expect(sheet.locator("h2")).to_have_text("Bobby éclot bientôt")
    assert supa.base.pets[uid(supa)]["life"]["name"] == "Bobby"
    sheet.locator("[data-zc-close]").click()
    expect(root.locator(".pt-hero.pt-egg")).to_be_visible()                   # l'onglet suit : l'œuf, plus l'adoption


def test_guest_is_invited_once_after_his_first_game_never_after_a_drinking_game(world):
    phone, _ = world
    page = phone.page
    page.goto("/")
    seen = lambda g: page.evaluate("(g) => ZicouHome.gameSeen(g)", g)  # noqa: E731
    # Jeu d'alcool : jamais.
    seen({"id": "b1", "type": "beerpong", "name": "Beer pong", "phase": "play", "me": {"pid": "p"}})
    seen({"id": "b1", "type": "beerpong", "name": "Beer pong", "phase": "end", "me": {"pid": "p"}})
    page.wait_for_timeout(2000)
    expect(page.locator("#zicouSheet")).to_have_count(0)
    # Pendant la partie : rien. À la fin : une feuille, une seule fois.
    seen({"id": "q1", "type": "quiz", "name": "Quiz", "phase": "play", "me": {"pid": "p"}})
    page.wait_for_timeout(1800)
    expect(page.locator("#zicouSheet")).to_have_count(0)
    seen({"id": "q1", "type": "quiz", "name": "Quiz", "phase": "end", "me": {"pid": "p"}})
    sheet = page.locator("#zicouSheet")
    expect(sheet.locator("h2")).to_have_text("Adopte ton Zicou")
    expect(sheet).to_contain_text("Il a vu ta partie de Quiz ce soir.")
    expect(sheet.locator(".zc-cta")).to_have_text("Créer mon compte")   # pas de connexion Apple : le parcours SMS
    phone.shot("zicou-8-invite-soiree")
    sheet.locator("[data-zc-close]").click()
    expect(sheet).to_be_hidden()
    seen({"id": "q2", "type": "quiz", "name": "Quiz", "phase": "play", "me": {"pid": "p"}})
    seen({"id": "q2", "type": "quiz", "name": "Quiz", "phase": "end", "me": {"pid": "p"}})
    page.wait_for_timeout(2000)
    expect(sheet).to_be_hidden()


def test_pet_deep_links_open_the_zicou_tab(world):
    phone, supa = world
    page = phone.page
    phone.ctx.add_init_script("localStorage.setItem('zc_onb', JSON.stringify({ step: 'done' }))")
    page.goto("/")
    sign_in(phone, TOK_A)
    life, owner = grown()
    supa.seed(uid(supa), life, owner)
    for url in ("/?tab=pet", "/?tab=games&pet=1&src=widget"):
        page.goto(url)
        page.wait_for_function("document.body.dataset.tab === 'pet'")
        expect(page.locator("#petRoot .pt-gauges")).to_be_visible()
    # La carte de Jeux mène au même panneau, dans l'onglet.
    page.locator('#tabs [data-tab="games"]').click()
    page.locator("#gHome [data-pet-open]").click()
    page.wait_for_function("document.body.dataset.tab === 'pet'")


@pytest.fixture
def feedback_world(browser):
    supa = FakeSupabase()
    server = Server(supa)
    phone = Phone(browser, server, "Lea")
    yield phone
    errors = phone.errors
    phone.close()
    server.stop()
    supa.stop()
    assert not errors, "\n".join(errors)


def test_ton_avis_is_a_settings_page_with_its_badge_and_deep_link(feedback_world):
    phone = feedback_world
    page = phone.page
    page.goto("/")
    sign_in(phone, "jeton-de-test-guest-plus-0001")
    page.wait_for_function("fbInfo().allowed")
    # La ligne des Réglages (module Événements) demande la page « Ton avis » à Party.
    page.evaluate("window.postMessage({ type: 'party-events:open-tab', tab: 'feedback' }, location.origin)")
    page.wait_for_function("document.body.dataset.tab === 'feedback'")
    screen = page.locator('[data-view="feedback"]')
    expect(screen.locator("#fbScreenTitle")).to_have_text("Ton avis")
    expect(page.locator('#tabs [data-tab="account"]')).to_have_class("on")   # sous Réglages
    phone.shot("zicou-9-ton-avis")
    screen.locator(".nav-back").click()                                       # ‹ Réglages
    page.wait_for_function("document.body.dataset.tab === 'account'")
    # Réponse reçue : la pastille passe sur Réglages (et sur la ligne, via fbInfo).
    page.evaluate("fbUnseen = 2; fbBadge()")
    expect(page.locator("#hostBadge")).to_have_text("2")
    assert page.evaluate("fbInfo().badge") == "2"
    # Lien profond (notification « réponse à ton avis ») toujours valide.
    page.goto("/?tab=feedback")
    page.wait_for_function("document.body.dataset.tab === 'feedback'")
    assert page.evaluate("location.search") == ""
    time.sleep(0.2)
