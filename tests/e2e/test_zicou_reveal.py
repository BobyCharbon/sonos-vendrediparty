"""Zicou — scène d'ouverture d'une récompense (app/static/pet/reveal.js, avis du 5.11 « comme un booster ») dans un vrai
navigateur : le coffre du jour se DÉCHIRE au doigt puis montre ce que le serveur a tiré (bonne rareté), le coffre garanti
le dit sur le paquet, le cadeau d'événement se GRATTE, chances visibles dans le paquet et sous « i », « Passer » et double
toucher, mouvement réduit en fondu, rien ne déborde à 360 px, vrai toucher Android. Captures et une vidéo par rareté
dans E2E_REVEAL_DIR (par défaut test-results/zicou-reveal)."""
import os
import shutil
from pathlib import Path

import pytest
pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from app import pet_catalog, pet_chest, pet_collection
from tests.e2e.helpers import DEVICES, ROOT, sign_in
from tests.e2e.test_pet_game import grown, open_pet, world  # noqa: F401
from tests.test_pet_api import ALICE, TOK_A

OUT = Path(os.environ.get("E2E_REVEAL_DIR", ROOT / "test-results" / "zicou-reveal"))
RARITIES = ("common", "rare", "epic", "legendary", "mythic")


def ready(phone, supa, **coll_extra):
    phone.page.goto('/')
    sign_in(phone, TOK_A)
    life, owner = grown()
    owner["coll"] = pet_collection.new_coll() | {"upgraded": True} | coll_extra
    supa.seed(ALICE, life, owner)
    return open_pet(phone)


def tear(page, steps=14):
    """Glisser le doigt (souris) en travers du paquet."""
    box = page.locator('.zr-pack').bounding_box()
    y = box["y"] + box["height"] * 0.3
    page.mouse.move(box["x"] + 12, y)
    page.mouse.down()
    for i in range(1, steps + 1):
        page.mouse.move(box["x"] + 12 + (box["width"] - 24) * i / steps, y + (i % 2) * 3)
        page.wait_for_timeout(16)
    page.mouse.up()


def scratch(page):
    """Gratter la carte en zigzag jusqu'à la révélation."""
    box = page.locator('.zr-scratch-c').bounding_box()
    page.mouse.move(box["x"] + 8, box["y"] + 8)
    page.mouse.down()
    rows = 9
    for r in range(rows + 1):
        y = box["y"] + 8 + (box["height"] - 16) * r / rows
        for x in (box["x"] + 8, box["x"] + box["width"] - 8) if r % 2 == 0 else (box["x"] + box["width"] - 8, box["x"] + 8):
            page.mouse.move(x, y, steps=6)
        if page.locator('.zr').get_attribute('data-phase') in ("show", "done"):
            break
    page.mouse.up()


def expected_rarity(found):
    return found["rarity"] if found["kind"] == "item" else ("none" if found["kind"] == "coins" else "common")


def test_the_daily_chest_is_torn_open_and_shows_what_the_server_drew(world):
    phone, supa = world
    page = phone.page
    root = ready(phone, supa)
    root.locator('[data-pt="chest"]').click()
    scene = page.locator('.zr')
    expect(scene).to_be_visible()
    # Avant d'ouvrir : chances dans le paquet (Objet mystère compris), « i » pour le détail, « Passer » visible.
    expect(scene.locator('.zr-odds')).to_contain_text('Objet mystère')
    expect(scene.locator('.zr-odds')).to_contain_text('%')
    expect(scene.locator('.zr-skip')).to_be_visible()
    scene.locator('.zr-info').click()
    expect(scene.locator('.zr-full')).to_contain_text('Le tirage est fait par Party avant')
    scene.locator('.zr-full-x').click()
    expect(scene).to_have_attribute('data-phase', 'ready')
    found = supa.base.pets[ALICE]["owner"]["loop"]["chest"]["found"]   # déjà tiré par le serveur, avant l'animation
    assert supa.base.pets[ALICE]["owner"]["loop"]["chest"]["opened"]
    tear(page)
    # La rareté montrée est celle du tirage, dès le début de la révélation, et ne change plus.
    expect(scene).to_have_attribute('data-phase', 'show', timeout=3000)
    assert scene.get_attribute('data-r') == expected_rarity(found)
    if found.get("rarity") != "mythic":
        expect(scene).to_have_attribute('data-phase', 'done', timeout=5000)
        assert scene.get_attribute('data-r') == expected_rarity(found)
        scene.locator('.zr-done').click()
        expect(scene).to_have_count(0)
        expect(root.locator('.pt-reveal h2')).not_to_be_empty()


def test_a_guaranteed_chest_says_so_and_reveals_an_epic_or_better(world):
    phone, supa = world
    page = phone.page
    root = ready(phone, supa, pity=pet_chest.PITY - 1)
    root.locator('[data-pt="chest"]').click()
    scene = page.locator('.zr')
    expect(scene.locator('.zr-pack')).to_contain_text('Épique ou Légendaire garanti')
    page.locator('.zr-pack').hover()
    page.mouse.down()                      # maintenir ouvre aussi le paquet
    expect(scene).to_have_attribute('data-phase', 'show', timeout=3000)
    page.mouse.up()
    assert scene.get_attribute('data-r') in ("epic", "legendary")
    found = supa.base.pets[ALICE]["owner"]["loop"]["chest"]["found"]
    assert scene.get_attribute('data-r') == found["rarity"]


def test_an_event_gift_is_scratched_then_revealed(world):
    phone, supa = world
    page = phone.page
    supa.base.awards.append({"id": "aw2", "user": ALICE, "event_id": "ev2", "event": "Soirée disco", "item": "cor-alpes",
                             "prize": 0, "roll": 1.2, "instance": None})
    root = ready(phone, supa)
    scene = page.locator('.zr')
    expect(scene).to_have_attribute('data-mode', 'scratch', timeout=8000)
    expect(scene.locator('.zr-from')).to_contain_text('Soirée disco')
    expect(scene).to_have_attribute('data-phase', 'ready')
    scene.locator('.zr-info').click()
    expect(scene.locator('.zr-full')).to_contain_text('jamais d’un billet'.replace('’', "'"))
    scene.locator('.zr-full-x').click()
    scratch(page)
    expect(scene).to_have_attribute('data-phase', 'done', timeout=5000)
    assert scene.get_attribute('data-r') == pet_catalog.item("cor-alpes")["rarity"]
    expect(scene.locator('.zr-name')).to_have_text(pet_catalog.item("cor-alpes")["label"])
    scene.locator('.zr-done').click()
    expect(root.locator('.pc-from')).to_contain_text('Soirée disco')


# ── La scène seule, pour chaque rareté (sur la page de l'app, sans serveur de tirage) ──

def item_for(rarity):
    if rarity == "mythic":
        return None
    return pet_catalog.chest_pool(rarity)[0]


def play(page, rarity, mode="tear", kind="item", **extra):
    iid = item_for(rarity)
    spec = {"rarity": rarity, "kind": kind, "mode": mode, "title": "Coffre du jour", "pack": "chest",
            "label": pet_catalog.item(iid)["label"] if iid else "Objet mystère",
            "odds": [{"kind": "coins", "label": "Pièces", "text": "58 %"}, {"kind": "mythic", "label": "Objet mystère", "text": "1 chance sur 100 000"}],
            **extra}
    page.evaluate("""([spec, iid]) => {
      const slot = iid && window.__slots ? window.__slots[iid] : null;
      spec.icon = iid && spec.kind !== 'coins' && window.PetSkin ? window.PetSkin.render({ stage: 'adult', variant: 'classic', emotion: 'happy',
        accessories: slot ? { [slot]: iid } : {} }) : '';
      window.__played = window.PetReveal.play(spec);
    }""", [spec, iid])
    expect(page.locator('.zr')).to_be_visible()


def slots(page):
    page.evaluate("slots => { window.__slots = slots; }", {pet_catalog.chest_pool(r)[0]: pet_catalog.item(pet_catalog.chest_pool(r)[0])["slot"]
                                                           for r in ("common", "rare", "epic", "legendary")})


def test_double_tap_skips_and_the_last_rarity_stays(world):
    phone, _ = world
    page = phone.page
    page.goto('/')
    slots(page)
    play(page, "legendary")
    scene = page.locator('.zr')
    expect(scene).to_have_attribute('data-phase', 'ready')
    scene.locator('.zr-stage').dblclick()
    expect(scene).to_have_attribute('data-phase', 'done')
    assert scene.get_attribute('data-r') == 'legendary'
    page.wait_for_timeout(500)
    expect(scene).to_be_visible()          # le double toucher passe, il ne referme pas d'un coup
    scene.locator('.zr-done').click()
    expect(scene).to_have_count(0)
    assert page.evaluate("window.__played.then(r => r.skipped)") is False


def test_reduced_motion_is_a_short_fade(world):
    phone, _ = world
    page = phone.page
    page.emulate_media(reduced_motion="reduce")
    page.goto('/')
    slots(page)
    play(page, "epic", mode="auto")
    scene = page.locator('.zr')
    expect(scene).to_have_class('zr zr-calm')
    expect(scene).to_have_attribute('data-phase', 'done', timeout=1500)
    assert scene.locator('.zr-card').evaluate('el => getComputedStyle(el).animationName') == 'none'
    assert not scene.locator('.zr-confetti').count()
    scene.locator('.zr-done').click()


@pytest.mark.parametrize("rarity", RARITIES)
def test_nothing_overflows_at_360px(world, rarity):
    phone, _ = world
    page = phone.page
    page.set_viewport_size({"width": 360, "height": 640})
    page.goto('/')
    slots(page)
    play(page, rarity, kind="coins" if rarity == "common" else "item", amount=25)
    scene = page.locator('.zr')
    expect(scene).to_have_attribute('data-phase', 'ready')
    for sel in ('.zr-top', '.zr-pack', '.zr-foot', '.zr-odds', '.zr-skip'):
        b = scene.locator(sel).bounding_box()
        assert b and b["x"] >= 0 and b["x"] + b["width"] <= 360.5 and b["y"] + b["height"] <= 640.5, (sel, b)
    scene.locator('.zr-open').click()
    if rarity != "mythic":
        expect(scene).to_have_attribute('data-phase', 'done', timeout=5000)
        assert page.evaluate("document.documentElement.scrollWidth") <= 360
        for sel in ('.zr-card', '.zr-done'):
            b = scene.locator(sel).bounding_box()
            assert b and b["x"] >= 0 and b["x"] + b["width"] <= 360.5 and b["y"] + b["height"] <= 640.5, (sel, b)
        if rarity == "common":
            expect(scene.locator('.zr-coins b')).to_have_text('+25')
    # Règle iOS : rien sur html/body.
    assert page.evaluate("getComputedStyle(document.body).overflowY") != 'hidden'
    assert scene.evaluate('el => getComputedStyle(el).position') == 'fixed'


def test_a_real_android_finger_tears_the_pack(browser, world):
    phone, _ = world
    ctx = browser.new_context(base_url=phone.server.url, locale="fr-CH", **DEVICES["android"])
    try:
        page = ctx.new_page()
        page.goto('/')
        slots(page)
        play(page, "rare")
        expect(page.locator('.zr')).to_have_attribute('data-phase', 'ready')
        box = page.locator('.zr-pack').bounding_box()
        y = box["y"] + box["height"] * 0.3
        cdp = ctx.new_cdp_session(page)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box["x"] + 10, 'y': y}]})
        for i in range(1, 13):
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': box["x"] + 10 + (box["width"] - 20) * i / 12, 'y': y}]})
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        expect(page.locator('.zr')).to_have_attribute('data-phase', 'done', timeout=4000)
    finally:
        ctx.close()


@pytest.mark.parametrize("rarity", RARITIES)
def test_video_of_each_rarity(browser, world, rarity):
    """Une courte vidéo et trois captures par rareté (paquet, déchirure, révélation), pour l'admin."""
    phone, _ = world
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"_video-{rarity}"
    shutil.rmtree(tmp, ignore_errors=True)
    ctx = browser.new_context(base_url=phone.server.url, locale="fr-CH", viewport={"width": 390, "height": 844},
                              device_scale_factor=2, record_video_dir=str(tmp), record_video_size={"width": 390, "height": 844})
    page = ctx.new_page()
    try:
        page.goto('/')
        slots(page)
        mode = "scratch" if rarity == "rare" else "tear"
        if rarity == "common":
            play(page, rarity, mode=mode, kind="coins", amount=25, label="25 pièces", emoji="🪙")
        else:
            play(page, rarity, mode=mode)
        scene = page.locator('.zr')
        expect(scene).to_have_attribute('data-phase', 'ready')
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT / f"{rarity}-1-paquet.png"))
        if mode == "scratch":
            scratch(page)
        else:
            tear(page, steps=22)
        page.wait_for_timeout(250 if rarity in ("common", "rare") else 600)
        page.screenshot(path=str(OUT / f"{rarity}-2-revelation.png"))
        if rarity == "mythic":
            expect(scene).to_have_count(0, timeout=5000)
        else:
            expect(scene).to_have_attribute('data-phase', 'done', timeout=5000)
            page.wait_for_timeout(900)
            page.screenshot(path=str(OUT / f"{rarity}-3-carte.png"))
    finally:
        video = page.video
        ctx.close()
    src = Path(video.path())
    shutil.move(str(src), str(OUT / f"{rarity}.webm"))
    shutil.rmtree(tmp, ignore_errors=True)
