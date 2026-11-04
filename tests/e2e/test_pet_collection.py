"""Collection du Compagnon (vrai navigateur, iPhone) : Zicoudex (Mythiques masqués « ??? », où le trouver), boutique du
jour et décor en pièces gagnées, atelier en poussière, garde-robe, cadeau d'événement Mythique révélé en plusieurs temps
(numéro tamponné), vitrine d'un ami avec Signaler et Bloquer, page d'authenticité d'un objet (signature vérifiée).
Serveur Party réel, Supabase simulé (FakeBase). Captures dans E2E_SHOTS."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from app import pet_catalog, pet_collection
from tests.e2e.helpers import sign_in
from tests.e2e.test_pet_game import grown, open_pet, world  # noqa: F401
from tests.test_pet_api import ALICE, BOB, TOK_A


def ready(phone, supa, coins=0, dust=0, **owner_extra):
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    owner["loop"] = {"coins": coins}
    owner["coll"] = pet_collection.new_coll() | {"dust": dust, "upgraded": True, "inv": {"noeud": 1}}
    owner.update(owner_extra)
    supa.seed(ALICE, life, owner)
    return open_pet(phone)


def test_the_zicoudex_masks_mythics_and_says_where_to_find_each_item(world):
    phone, supa = world
    root = ready(phone, supa)
    root.locator('[data-pt="coll"][data-s="dex"]').click()
    expect(root.locator('.pc-series')).to_have_count(6)
    expect(root.locator('.pc-masked')).to_have_count(len(pet_catalog.mythics()))
    html = root.inner_html()
    assert not any(pet_catalog.item(m)["label"] in html for m in pet_catalog.mythics())   # ni nom…
    assert not any(f'"{m}"' in html for m in pet_catalog.mythics())                      # … ni identifiant
    expect(root.locator('.pc-off').first).to_be_visible()
    phone.shot('coll-1-zicoudex')
    root.locator('.pc-tile.pc-off', has_text='Cor des Alpes').click()
    expect(root.locator('.pc-detail')).to_contain_text('Où le trouver')
    expect(root.locator('.pc-detail')).to_contain_text('Atelier (400 ✨)')
    root.locator('.pc-masked').first.click()
    expect(root.locator('.pc-detail')).to_contain_text('Objet mystère')
    expect(root.locator('.pc-detail')).to_contain_text('0,1 %')


def test_shop_and_workshop_spend_earned_coins_and_dust(world):
    phone, supa = world
    root = ready(phone, supa, coins=500, dust=450)
    root.locator('[data-pt="coll"][data-s="shop"]').click()
    first = root.locator('.pc-list').first.locator('[data-pt="pc-buy"]').first
    expect(root.locator('.pc-list').first.locator('li')).to_have_count(4)
    expect(root).to_contain_text('ne s\'achètent jamais avec de l\'argent')
    phone.shot('coll-2-boutique')
    first.click()
    expect(root.locator('.pc-wallet')).not_to_contain_text('🪙 500')
    expect(root.locator('.pc-own').first).to_be_visible()
    root.locator('[data-pt="pc-tab"][data-t="craft"]').click()
    expect(root.locator('.pc-rates tbody tr')).to_have_count(4)
    phone.shot('coll-3-atelier')
    root.locator('[data-pt="pc-craft"][data-i="cor-alpes"]').click()
    expect(root.locator('.pc-wallet')).to_contain_text('✨ 50')
    root.locator('[data-pt="pc-tab"][data-t="wear"]').click()
    root.locator('[data-pt="pc-slot"][data-s="hand"]').click()
    root.locator('[data-pt="pc-wear"][data-i="cor-alpes"]').click()
    expect(root.locator('[data-pt="pc-wear"][data-i="cor-alpes"]')).to_have_attribute('aria-pressed', 'true')
    assert supa.base.pets[ALICE]["life"]["acc"]["hand"] == "cor-alpes"
    phone.shot('coll-6-garde-robe')


def test_a_mythic_event_gift_is_revealed_in_several_steps_with_its_number(world):
    phone, supa = world
    inst = supa.base.mint_for(ALICE, "m-soirees", "event", "event:ev1:0", "ev1")
    supa.base.awards.append({"id": "aw1", "user": ALICE, "event_id": "ev1", "event": "Soirée disco du 14", "item": "m-soirees",
                             "prize": 0, "roll": 0.4, "instance": inst["id"]})
    root = ready(phone, supa)
    myth = root.locator('.pc-myth')
    expect(myth).to_be_visible(timeout=5000)
    expect(root.locator('.pc-from')).to_contain_text('Soirée disco du 14')
    phone.shot('coll-4-mythique-1-antennes')
    expect(myth).to_have_attribute('data-step', '3', timeout=5000)
    phone.shot('coll-4-mythique-2-eclats')
    expect(myth).to_have_attribute('data-step', '4', timeout=5000)
    expect(root.locator('.pc-stamp')).to_have_text('n° 1/10')
    expect(root.locator('.pc-myth-name')).to_have_text('Boule de Party')
    phone.page.wait_for_timeout(500)
    phone.shot('coll-4-mythique-3-numero')
    assert supa.base.awards[0]["claimed"] and inst["sig"]
    root.locator('.pc-myth [data-pt="pc-wear-new"]').click()
    expect(root.locator('.pt-gauges')).to_be_visible()
    assert supa.base.pets[ALICE]["life"]["acc"]["head"] == "m-soirees"


def test_a_friends_showcase_can_be_reported_and_its_owner_blocked(world):
    phone, supa = world
    life, owner = grown()
    life["name"] = "Pikou"
    life["acc"] = {"head": "couronne"}
    life["showcase"] = {"title": "Mes trésors <b>", "items": [{"id": "couronne"}]}
    supa.seed(BOB, life, owner)
    root = ready(phone, supa)
    root.locator('.pt-more [data-pt="friends"]').click()
    root.locator('[data-pt="visit"]').click()
    expect(root.locator('.pc-their h3')).to_have_text('🏆 Mes trésors <b>')   # échappé, jamais interprété
    phone.shot('coll-7-visite-vitrine')
    root.locator('[data-pt="pc-report"]').click()
    root.locator('[data-pt="pc-report"][data-k="pet_showcase"]').click()
    root.locator('[data-pt="pc-reason"][data-r="harassment"]').click()
    expect(root.locator('.pt-news')).to_contain_text('signalé')
    assert supa.base.reports[-1] == (ALICE, "pet_showcase", BOB, "harassment")
    root.locator('.pt-more [data-pt="friends"]').click()
    root.locator('[data-pt="visit"]').click()
    block = root.locator('[data-pt="pc-block"]')
    block.click()
    expect(block).to_contain_text('Confirmer')
    block.click()
    expect(root.locator('.pt-news')).to_contain_text('bloquée')
    assert BOB not in supa.base.friends[ALICE]


def test_the_authenticity_page_verifies_a_signed_certificate(world):
    phone, supa = world
    supa.base.mint_for(ALICE, "piolet-or", "atelier", "atelier:piolet-or")
    root = ready(phone, supa)
    root.locator('[data-pt="coll"][data-s="dex"]').click()
    root.locator('[data-pt="pc-tab"][data-t="certs"]').click()
    code = supa.base.items[0]["code"]
    assert code and code.startswith("ZC-")
    expect(root.locator('.pc-cert')).to_contain_text(code)
    expect(root.locator('.pc-cert .pc-serial')).to_have_text('n° 1')
    page = phone.page
    page.goto(f'/zicou/certificat?code={code}')
    expect(page.locator('.vf-ok')).to_contain_text('Authentique')
    expect(page.locator('#vfOut h2')).to_have_text('Piolet d\'or')
    phone.shot('coll-5-certificat')
    page.locator('#vfCode').fill('ZC-2222-3333-4444')
    page.locator('#vfForm button').click()
    expect(page.locator('.vf-bad')).to_contain_text('Aucun objet')
