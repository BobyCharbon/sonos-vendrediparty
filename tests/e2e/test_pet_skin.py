"""Couche graphique du Compagnon, « Zicou Nuit » (app/static/pet/skin.js), dans un vrai navigateur : contrat de
PetSkin.render (stades, 9 émotions, branches, toutes les tenues de app/pet.py), couleur d'humeur sur les anneaux ET les
LED d'antenne, tenue « casque » qui remplace le casque, fantôme sans tenue, identifiants uniques, libellé échappé,
architecture des accessoires (emplacements, points d'ancrage, ordre des calques, palette, shiny) et animations coupées
quand l'utilisateur les réduit."""
from pathlib import Path

import pytest
pytest.importorskip('playwright.sync_api')

from app.pet import OUTFITS

SKIN = (Path(__file__).resolve().parents[2] / "app" / "static" / "pet" / "skin.js").read_text()
STAGES = ("baby", "teen", "adult")
EMOTIONS = ("happy", "party", "hungry", "tired", "sad", "sick", "sleep")
VARIANTS = ("star", "classic", "wild")


@pytest.fixture
def page(browser):
    page = browser.new_page(viewport={"width": 420, "height": 420})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_content("<html><body><div id=a style='width:200px'></div></body></html>")
    page.add_script_tag(content=SKIN)
    yield page
    page.close()
    assert not errors, errors


def render(page, **opts):
    return page.evaluate("o => PetSkin.render(o)", opts)


def mount(page, **opts):
    page.evaluate("o => { document.getElementById('a').innerHTML = PetSkin.render(o); }", opts)
    return page.locator('#a svg')


def test_every_stage_emotion_branch_and_outfit_draws_a_clean_200_svg(page):
    outfits = [None] + [o[0] for o in OUTFITS]
    bad = page.evaluate("""([stages, emotions, variants, outfits]) => {
        const bad = [];
        const cases = [{stage: "egg", emotion: "egg"}, {stage: "dead", emotion: "ghost"}];
        for (const stage of stages) for (const emotion of emotions) for (const variant of variants) for (const outfit of outfits)
            cases.push({stage, emotion, variant, outfit});
        for (const c of cases) {
            const svg = PetSkin.render(c);
            const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
            if (doc.querySelector("parsererror") || /NaN|undefined|Infinity/.test(svg)
                || doc.documentElement.getAttribute("viewBox") !== "0 0 200 200" || !doc.querySelector(".pt-body")) bad.push(c);
        }
        return {bad, count: cases.length};
    }""", [STAGES, EMOTIONS, VARIANTS, outfits])
    assert bad["count"] > 400
    assert bad["bad"] == []


def test_the_mood_colour_lights_both_rings_and_both_antenna_leds(page):
    for emotion in EMOTIONS:
        svg = mount(page, stage="adult", emotion=emotion, variant="classic")
        mood = page.evaluate("e => PetSkin.moodColor(e)", emotion)
        leds = svg.locator(f'.pt-led[fill="{mood}"]')      # deux LED d'antenne
        rings = svg.locator(f'.pt-led[stroke="{mood}"]')   # deux anneaux d'oreillette
        assert (leds.count(), rings.count()) == (2, 2), emotion
    assert page.evaluate("PetSkin.moodColor('happy')") == "#5ee7ff"
    assert page.evaluate("PetSkin.creatureName") == "Zicou"


def test_the_dj_headset_outfit_replaces_zicou_headset_with_a_golden_one(page):
    plain = mount(page, stage="adult", emotion="happy")
    plain_cups, plain_fx = plain.locator('rect[rx]').count(), plain.locator('.pt-fx').count()
    gold = mount(page, stage="adult", emotion="happy", outfit="casque")
    assert gold.locator('path[stroke="#ffd24d"]').count() == 1           # un seul arceau, doré
    assert gold.locator('rect[fill="#ffd24d"]').count() == 2             # deux oreillettes dorées, pas quatre
    assert gold.locator('rect[rx]').count() == plain_cups
    assert gold.locator('.pt-led').count() == 4                          # l'humeur reste lisible
    assert gold.locator('.pt-fx').count() > plain_fx                     # paillettes


def test_animations_classes_sleep_tear_and_twinkle(page):
    assert mount(page, stage="adult", emotion="sleep").locator('.pt-z').count() == 1
    assert mount(page, stage="baby", emotion="tired").locator('.pt-z').count() == 1
    assert mount(page, stage="teen", emotion="sad").locator('.pt-tear').count() == 1
    assert mount(page, stage="adult", emotion="hungry").locator('.pt-tear').count() == 1
    assert mount(page, stage="adult", emotion="party").locator('.pt-fx').count() > 10
    assert mount(page, stage="adult", variant="star", emotion="happy").locator('.pt-l-aura .pt-fx').count() == 3


def test_a_ghost_wears_nothing_and_ids_never_collide(page):
    ghost = render(page, stage="dead", emotion="ghost", outfit="couronne")
    assert "#ffd24d" in ghost                      # auréole du fantôme
    page.evaluate("""() => { document.getElementById('a').innerHTML = PetSkin.render({stage:'adult'}) + PetSkin.render({stage:'adult'}); }""")
    ids = page.evaluate("[...document.querySelectorAll('#a [id]')].map(e => e.id)")
    assert len(ids) == len(set(ids))
    crowned = mount(page, stage="dead", emotion="ghost", outfit="couronne")
    assert crowned.locator('path[fill="#ffd24d"]').count() == 0     # pas de couronne sur un fantôme


def test_the_label_is_escaped(page):
    svg = mount(page, stage="adult", emotion="happy", label='<img src=x onerror=alert(1)>"')
    assert svg.get_attribute("aria-label") == '<img src=x onerror=alert(1)>"'
    assert page.locator('#a img').count() == 0


def test_accessories_slots_anchors_layers_palette_and_shiny(page):
    res = page.evaluate("""() => {
        const seen = {};
        for (const slot of PetSkin.SLOTS) {
            if (slot === "facets") continue;
            PetSkin.defineAccessory({id: "t-" + slot, slot, draw: (ctx) => { seen[slot] = ctx.a;
                const tag = `<g data-acc="${slot}"/>`; return slot === "effect" ? {back: `<g data-acc="effect-back"/>`, front: tag} : tag; }});
        }
        PetSkin.defineAccessory({id: "t-or", slot: "facets", palette: {base: ["#aaaaaa", "#888888", "#444444"], tiles: ["#123456"], accents: []}});
        let invalid = false;
        try { PetSkin.defineAccessory({id: "x", slot: "nez", draw: () => ""}); } catch (e) { invalid = true; }
        const accessories = Object.fromEntries(PetSkin.SLOTS.map((s) => [s, s === "facets" ? "t-or" : "t-" + s]));
        document.getElementById("a").innerHTML = PetSkin.render({stage: "adult", emotion: "happy", accessories});
        const order = [...document.querySelectorAll("#a [data-acc]")].map((e) => e.dataset.acc);
        const inBody = [...document.querySelectorAll("#a .pt-body [data-acc]")].map((e) => e.dataset.acc);
        const a = seen.head;
        const pts = [a.ground, a.head, a.crown, a.eyes.l, a.eyes.r, a.mouth, a.neck, a.back, a.hands.l, a.hands.r, a.feet.l, a.feet.r, a.antennas.l, a.antennas.r, a.pet];
        const inside = pts.every((p) => p.x >= 0 && p.x <= 200 && p.y >= 0 && p.y <= 200);
        const palette = document.querySelectorAll('#a path[fill="#123456"]').length;
        const shiny = PetSkin.render({stage: "adult", emotion: "happy", shiny: true});
        return {order, inBody, inside, palette, invalid, shiny: shiny.includes("pt-shiny") && shiny.includes("#f4f6ff"),
                eyesBelowCrown: a.eyes.y > a.crown.y, s: a.s,
                slots: PetSkin.SLOTS.length, listed: PetSkin.accessories("neck").map((x) => x.id)};
    }""")
    assert res["slots"] == 10 and res["invalid"] and res["inside"] and res["eyesBelowCrown"]
    assert res["order"] == ["decor", "effect-back", "back", "feet", "eyes", "neck", "head", "hand", "pet", "effect"]
    assert res["inBody"] == ["back", "feet", "eyes", "neck", "head", "hand"]
    assert res["palette"] > 20 and res["shiny"] and res["s"] == 1
    assert {"noeud", "boa", "echarpe", "paillettes", "t-neck"} <= set(res["listed"])


def test_reduced_motion_stops_every_skin_animation_even_outside_the_panel(browser):
    page = browser.new_page()
    page.emulate_media(reduced_motion="reduce")
    page.set_content("<html><body><div id=a></div></body></html>")
    page.add_script_tag(content=SKIN)
    page.evaluate("document.getElementById('a').innerHTML = PetSkin.render({stage:'adult', emotion:'party'})")
    names = page.evaluate("[...document.querySelectorAll('.pt-led, .pt-fx')].map(e => getComputedStyle(e).animationName)")
    assert names and set(names) == {"none"}
    page.emulate_media(reduced_motion="no-preference")
    assert page.evaluate("getComputedStyle(document.querySelector('.pt-led')).animationName") == "pt-led"
    page.close()
