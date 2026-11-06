"""Nouvelle économie de Zicou (vrai navigateur, iPhone, bêta) : boutique (2 Communs + 1 Rare un jour sur 2, nouveaux
prix), chances « 1 chance sur 100 000 » et coffre bonus affichés, festins (Pizza dorée → XP ×2, un à la fois), niveau,
festin offert au Zicou d'un ami, chambre et teintures, caisse commune sans classement. Serveur Party réel, Supabase
simulé (FakeBase + caisse commune de tests/test_pet_economy_api.py). Captures dans E2E_SHOTS."""
import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from app import pet_collection
from tests.e2e.helpers import sign_in
from tests.e2e.test_pet_game import grown, open_pet, quiet_week, world  # noqa: F401
from tests.test_pet_api import ALICE, BOB, TOK_A
from tests.test_pet_economy_api import Pot


def ready(phone, supa, coins=0, dust=0, inv=None):
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    owner["loop"] = {"coins": coins, "week": quiet_week()}   # pas de +60 « vendredi » au milieu des comptes
    owner["coll"] = pet_collection.new_coll() | {"dust": dust, "upgraded": True, "inv": inv or {"noeud": 1}}
    supa.seed(ALICE, life, owner)
    return open_pet(phone)


def test_shop_prices_and_the_odds_screen_show_the_new_economy(world):
    phone, supa = world
    root = ready(phone, supa, coins=400)
    root.locator('[data-pt="odds"]').click()
    expect(root.locator('.pt-odds')).to_contain_text('1 chance sur 100 000')
    expect(root.locator('.pt-odds')).to_contain_text('Chances du coffre bonus')
    expect(root.locator('.pt-odds')).to_contain_text('jamais dans le coffre bonus')
    expect(root.locator('.pt-odds')).not_to_contain_text('0,0 %')
    phone.shot('eco-1-chances')
    root.locator('[data-pt="home"]').first.click()
    root.locator('[data-pt="coll"][data-s="shop"]').click()
    shop = root.locator('.pc-list').first
    expect(shop.locator('li').nth(1)).to_be_visible()
    assert shop.locator('li').count() in (2, 3)
    expect(shop.locator('[data-pt="pc-buy"]').first).to_have_text('300 🪙')
    expect(root).to_contain_text('Communs chaque jour, et un Rare un jour sur 2')
    expect(root.locator('.pc-list').nth(1)).to_contain_text('1400 🪙')
    phone.shot('eco-2-boutique')


def test_a_feast_is_served_once_and_doubles_xp(world):
    phone, supa = world
    root = ready(phone, supa, coins=300)
    expect(root.locator('[data-pt="eco-level"]')).to_contain_text('Niv. 1')
    root.locator('.pt-more [data-pt="eco-feasts"]').click()
    expect(root.locator('.pc-list li')).to_have_count(3)
    phone.shot('eco-3-festins')
    root.locator('[data-pt="eco-feast"][data-i="pizza"]').click()
    expect(root.locator('.pt-feast-on')).to_contain_text('Pizza dorée')
    expect(root.locator('.pc-wallet')).to_contain_text('🪙 180')
    expect(root.locator('[data-pt="eco-feast"][data-i="fondue"]')).to_have_attribute('aria-disabled', 'true')
    assert supa.base.pets[ALICE]["life"]["feast"]["kind"] == "pizza"
    phone.shot('eco-4-pizza-servie')
    root.locator('[data-pt="home"]').first.click()
    expect(root.locator('.pt-feast-chip')).to_be_visible()
    root.locator('[data-pt="eco-level"]').click()
    expect(root.locator('.pt-level')).to_contain_text('XP ×2')
    expect(root.locator('.pt-level')).to_contain_text('0/40 XP')
    phone.shot('eco-5-niveau')


def test_a_pizza_is_offered_to_a_friends_zicou(world):
    phone, supa = world
    life, owner = grown()
    supa.seed(BOB, life, owner)
    root = ready(phone, supa, coins=200)
    root.locator('[data-pt="friends"]').click()
    root.locator('[data-pt="visit"]').first.click()
    gift = root.locator('[data-pt="gift"][data-k="feast_pizza"]')
    expect(gift).to_contain_text('120 🪙')
    phone.shot('eco-6-offrir-festin')
    gift.click()
    expect(root.locator('.pt-gifted')).to_be_visible()
    assert supa.base.gifts[-1]["kind"] == "feast_pizza" and supa.base.pets[ALICE]["owner"]["loop"]["coins"] == 80


def test_room_and_dyes(world):
    phone, supa = world
    root = ready(phone, supa, coins=1000, inv={"noeud": 1, "bonnet": 1})
    root.locator('[data-pt="eco-room"]').click()
    root.locator('[data-pt="eco-room-grow"]').click()
    expect(root.locator('.pt-room .pt-line')).to_have_text('Chambre niveau 1')
    root.locator('[data-pt="eco-dye"][data-i="bonnet"][data-c="rose"]').click()
    expect(root.locator('[data-pt="eco-dye-wear"][data-i="bonnet"][data-c="rose"]')).to_have_attribute('aria-pressed', 'true')
    assert supa.base.pets[ALICE]["owner"]["loop"]["coins"] == 1000 - 400 - 60
    phone.shot('eco-7-chambre-teintures')


def test_the_common_pot_has_no_ranking(world):
    phone, supa = world
    pot = Pot(supa.base)
    supa.base.pet_pot_get, supa.base.pet_pot_give = pot.get, pot.give
    pot.gifts.append({"ref": "x" * 10, "goal": "boule-disco", "user": BOB, "coins": 1200})
    root = ready(phone, supa, coins=300)
    root.locator('[data-pt="eco-pot"]').click()
    expect(root.locator('.pt-pot')).to_contain_text('1')
    root.locator('[data-pt="eco-pot-give"][data-n="100"]').click()
    expect(root.locator('.pt-tip')).to_contain_text('100 pièces dans la caisse commune')
    expect(root.locator('.pt-pot')).to_contain_text('1 300')
    expect(root).to_contain_text('Pas de classement'); expect(root.locator('.pt-pot')).not_to_contain_text('1er')
    assert supa.base.pets[ALICE]["owner"]["loop"]["coins"] == 200
    phone.shot('eco-8-caisse-commune')
