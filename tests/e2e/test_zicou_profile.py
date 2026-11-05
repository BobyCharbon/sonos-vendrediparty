"""Zicou sur la fiche profil (avis de l'admin, 4.11), dans un vrai navigateur (iPhone) : fiche d'un joueur (jeux) avec
son Zicou en vedette (toucher = sa visite), un œuf terne « Pas encore de Zicou » + « Adopter le mien » sans Zicou, et
rien du tout quand le Zicou est éteint (production). Serveur Party réel (route /api/pet/profile) ; Supabase simulé.
Captures : test-results/shots/zicou_profile_*.png."""
import json
import os

import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402

from tests.e2e.helpers import Phone, Server, sign_in  # noqa: E402
from tests.e2e.test_pet_game import PetSupabase, grown  # noqa: E402
from tests.test_pet_api import BOB, TOK_A  # noqa: E402
from tests.test_zicou_profile import with_profiles  # noqa: E402


def card_for(member: str) -> dict:
    """Ce que /api/account/card renverrait pour ce joueur (la fiche elle-même est testée par test_profile_card.py)."""
    return {"id": member, "display_name": "Bob", "photo": None, "role": "member", "role_label": "Membre", "root": False,
            "me": False, "first_name": None, "last_name": None, "phone": None, "groups": ["Les Vendredis"]}


def open_card(phone, member=BOB):
    page = phone.page
    page.route("**/api/account/card", lambda route: route.fulfill(status=200, content_type="application/json",
                                                                   body=json.dumps(card_for(member))))
    page.evaluate("ProfileCard.open('ABCD', 'p-bob')")
    expect(page.locator(".pc-card")).to_contain_text("Bob")
    return page.locator(".pc-card")


def world_for(browser, compagnon=True):
    supa = PetSupabase()
    with_profiles(supa.base)
    server = Server(supa, compagnon=compagnon)
    phone = Phone(browser, server, "Alice")
    phone.page.goto("/")
    sign_in(phone, TOK_A)
    phone.page.wait_for_function("typeof account !== 'undefined' && account")
    return phone, supa, server


@pytest.fixture
def world(browser):
    phone, supa, server = world_for(browser)
    yield phone, supa
    errors, server_errors = phone.errors, server.errors()
    phone.close(); server.stop(); supa.stop()
    assert not server_errors, server_errors[-3000:]
    assert not errors, "\n".join(errors)


def test_a_friend_with_a_zicou_is_shown_in_the_spotlight_and_tapping_visits_him(world):
    phone, supa = world
    life, owner = grown(minutes_ago=60 * 24 * 3, food=90, joy=95, energy=90, care=95)
    life |= {"name": "Paillette", "shiny": True, "acc": {"head": "couronne", "neck": "noeud"}}
    supa.seed(BOB, life, owner)
    card = open_card(phone)
    spot = card.locator(".zp-on")
    expect(spot).to_be_visible()
    expect(spot).to_contain_text("Paillette")
    expect(spot).to_contain_text("Génération 1 · 3 jours")
    expect(spot.locator(".zp-shiny-tag")).to_be_visible()
    expect(spot.locator(".zp-chip")).to_have_count(2)
    assert spot.locator("svg.pt-svg").count() == 1
    phone.page.wait_for_timeout(600)
    phone.shot("zicou_profile_with")
    spot.locator(".zp-visit").click()
    expect(card).to_be_hidden()
    expect(phone.page.locator("#petRoot")).to_contain_text("chez")


def test_without_a_zicou_a_dull_egg_invites_me_to_adopt_mine(world):
    phone, _ = world
    card = open_card(phone)
    none = card.locator(".zp-none")
    expect(none).to_contain_text("Pas encore de Zicou")
    assert none.locator(".zp-halo, .zp-glint, .zp-chrome").count() == 0   # rien ne brille
    phone.shot("zicou_profile_without")
    none.locator(".zp-adopt").click()
    expect(card).to_be_hidden()
    phone.page.wait_for_function("document.body.dataset.tab === 'pet'")


def test_names_are_escaped(world):
    phone, supa = world
    life, owner = grown()
    life["name"] = "<img src=x onerror=alert(1)>"
    supa.seed(BOB, life, owner)
    card = open_card(phone)
    expect(card.locator(".zp-on")).to_be_visible()
    assert card.locator(".zp img").count() == 0


def test_nothing_when_zicou_is_off(browser):
    phone, supa, server = world_for(browser, compagnon=False)
    try:
        card = open_card(phone)
        phone.page.wait_for_timeout(500)
        assert card.locator(".pc-zicou, .zp").count() == 0
        assert phone.page.evaluate("typeof window.ZicouProfile") == "undefined"
        if os.environ.get("E2E_SHOTS"):
            phone.shot("zicou_profile_off")
        assert not phone.errors, phone.errors
    finally:
        phone.close(); server.stop(); supa.stop()
