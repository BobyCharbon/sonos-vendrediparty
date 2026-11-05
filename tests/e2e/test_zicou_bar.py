"""Barre « petit cadeau » de Zicou (vrai navigateur, iPhone ; app/static/pet/bar.js, serveur app/pet_bar.py) : la barre en
haut de l'écran de Zicou avec une heure calme (« pleine vers … », jamais un compte à rebours), ses chances sous « i »,
« Récupérer » une fois pleine (révélation, récompense rangée par le serveur, barre qui repart), et le petit anneau de la
pastille de l'en-tête. Supabase simulé (FakeBase de tests/test_pet_api.py), serveur Party réel."""
import re
from datetime import datetime, timedelta, timezone

import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from app import pet
from tests.e2e.helpers import pass_reveal, sign_in
from tests.e2e.test_pet_game import grown, open_pet, world  # noqa: F401 (fixture)
from tests.test_pet_api import TOK_A


def seeded(supa, full_in: timedelta):
    """Zicou d'Alice avec une barre qui sera (ou est) pleine dans `full_in`."""
    now = datetime.now(timezone.utc)
    life, owner = grown()
    owner["bar"] = {"from": pet.iso(now - timedelta(hours=3)), "full_at": pet.iso(now + full_in), "day": "", "n": 0,
                    "last": None}
    uid = supa.base.users[TOK_A]
    supa.seed(uid, life, owner)
    return uid


def test_the_bar_fills_shows_a_calm_time_and_its_odds(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    seeded(supa, timedelta(hours=1))
    root = open_pet(phone)
    bar = root.locator('.zb')
    expect(bar).to_be_visible()
    expect(bar).to_have_class(re.compile(r'\bzb-filling\b'))
    expect(bar.locator('.zb-when')).to_contain_text('vers')
    text = bar.inner_text()
    assert 'min' not in text and ':' not in text   # une heure calme, jamais « 0:59 » ni « plus que 5 min »
    expect(bar.locator('[data-zb="claim"]')).to_have_count(0)
    # Au-dessus de Zicou (avant la scène), visible sans défiler.
    assert bar.evaluate("el => el.compareDocumentPosition(document.querySelector('.pt-hero')) & Node.DOCUMENT_POSITION_FOLLOWING")
    phone.shot('zicou-barre-1-se-remplit')
    bar.locator('[data-zb="odds"]').click()
    expect(root.locator('.pt-odds li')).to_have_count(4)
    expect(root.locator('.zb-today')).to_contain_text('0/4 aujourd')
    for odd in ('60 %', '20 %', '17 %', '3 %'):
        expect(root.locator('.pt-odds')).to_contain_text(odd)
    expect(root.locator('.pt-odds')).to_contain_text('rien ne se perd')
    expect(root.locator('.pt-odds')).to_contain_text('Rien ne la remplit plus vite')
    page.go_back()
    expect(root.locator('.zb')).to_be_visible()


def test_a_full_bar_is_claimed_once_and_restarts(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    uid = seeded(supa, timedelta(minutes=-30))
    coins_before = supa.base.pets[uid]["owner"].get("loop", {}).get("coins", 0)
    root = open_pet(phone)
    bar = root.locator('.zb')
    expect(bar).to_have_class(re.compile(r'\bzb-full\b'))
    expect(bar.locator('[data-zb="claim"]')).to_be_visible()
    assert 'Pleine' in bar.locator('.zb-track').get_attribute('aria-valuetext')
    phone.shot('zicou-barre-2-pleine')
    # Pastille de l'en-tête : l'anneau suit la barre (pleine : il brille).
    ring = page.locator('#zicouChip .zb-ring, #zicouFloat .zb-ring')
    expect(ring.first).to_have_class(re.compile(r'\bzb-ring-full\b'), timeout=10000)
    bar.locator('[data-zb="claim"]').click()
    pass_reveal(page)
    saved = supa.base.pets[uid]["owner"]
    assert saved["bar"]["n"] == 1 and saved["bar"]["last"]["kind"] in ("coins", "snack", "xp", "dust")
    if saved["bar"]["last"]["kind"] == "coins":
        assert saved["loop"]["coins"] == coins_before + saved["bar"]["last"]["amount"]
    expect(root.locator('.zb')).to_have_class(re.compile(r'\bzb-filling\b'))
    expect(root.locator('.zb [data-zb="claim"]')).to_have_count(0)
    expect(root.locator('.zb .zb-when')).to_contain_text('vers')
    phone.shot('zicou-barre-3-recuperee')
    root.locator('.zb [data-zb="odds"]').click()
    expect(root.locator('.zb-today')).to_contain_text('1/4 aujourd')


def test_the_thin_bar_keeps_the_care_buttons_on_screen(world):
    phone, supa = world
    page = phone.page
    page.goto('/')
    sign_in(phone, TOK_A)
    seeded(supa, timedelta(minutes=-5))
    root = open_pet(phone)
    bar = root.locator('.zb')
    expect(bar).to_be_visible()
    assert bar.bounding_box()["height"] <= 44   # une ligne fine, pas une carte
    box = root.locator('.pt-acts [data-a="feed"]').bounding_box()
    assert box["y"] + box["height"] <= 844, box   # boutons de soin visibles sans défiler (390 × 844)
