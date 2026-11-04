"""Collection du Compagnon (lot A), calcul pur : catalogue (fichier unique, recopié tel quel dans la migration), tirages
et chances affichées (« Objet mystère » compris), garantie d'un Épique au plus tard au 30e coffre, doublons en
poussière, atelier (barème Hearthstone), boutique du jour en pièces gagnées, décor, séries, Zicoudex (Mythiques
masqués), porter, vitrine, shiny, certificats signés (Ed25519) et jets des cadeaux d'événement vérifiables."""
import random
import re
from collections import Counter
from pathlib import Path

import pytest

from app import pet, pet_catalog as cat, pet_cert, pet_chest as pc, pet_collection as col, pet_events

ROOT = Path(__file__).resolve().parents[1]
SKIN_OUTFITS = ("noeud", "lunettes", "casquette", "casque", "boa", "chapeau", "couronne", "echarpe", "bonnet",
                "paillettes", "ailes", "cape", "aureole", "comete")
ALL_LEFT = {m: cat.item(m)["edition"] for m in cat.mythics()}


# ── Catalogue ──

def test_the_catalog_has_60_items_on_10_slots_in_6_series_with_5_rarities():
    items = cat.items()
    assert len(items) >= 60
    assert {it["slot"] for it in items.values()} == set(cat.SLOT_IDS)
    assert len(cat.series()) == 6 and {"disco", "montagne", "escalade", "halloween", "nouvelan", "soirees"} == set(cat.series())
    assert Counter(it["rarity"] for it in items.values()).keys() == set(cat.RARITY_ORDER)
    for s in cat.series():
        rar = Counter(cat.item(i)["rarity"] for i in cat.series_items(s, with_mythic=True))
        assert rar["mythic"] == 1 and rar["legendary"] == 1 and rar["common"] == 4, s


def test_the_14_old_outfits_are_catalog_items_and_mythics_are_numbered_with_neutral_ids():
    assert all(cat.item(o) for o in SKIN_OUTFITS)
    assert {o[0] for o in pet.OUTFITS} <= set(SKIN_OUTFITS)
    for m in cat.mythics():
        assert m.startswith("m-") and 5 <= cat.item(m)["edition"] <= 10   # économie du 4.11 : 5 à 10 exemplaires
    assert cat.mythics("event") == ["m-soirees"] and "m-soirees" not in cat.mythics("chest")


def test_the_migration_holds_exactly_the_same_catalog():
    """La DERNIÈRE migration qui recopie le catalogue le tient à l'identique (économie : 20261105120000)."""
    copies = sorted(f for f in (ROOT / "supabase/migrations").glob("*.sql") if "insert into public.pet_catalog" in f.read_text())
    assert copies[-1].name == "20261105120000_zicou_economie.sql"
    assert cat.sql_values() in copies[-1].read_text()


def test_every_catalog_item_has_a_drawing():
    js = "".join((ROOT / f"app/static/pet/{f}").read_text() for f in ("skin.js", "acc-a.js", "acc-b.js"))
    drawn = set(re.findall(r'(?:def\(|id: )"([a-z0-9-]+)"', js))
    assert not set(cat.items()) - drawn


def test_validation_refuses_a_broken_catalog():
    good = cat.data()
    bad = {**good, "items": good["items"] + [{"id": "m-faux", "slot": "head", "series": "disco", "rarity": "mythic", "label": "x", "emoji": "x"}]}
    with pytest.raises(cat.CatalogError, match="tirage limité"):
        cat.validate(bad)
    bad = {**good, "items": good["items"] + [good["items"][0]]}
    with pytest.raises(cat.CatalogError, match="double"):
        cat.validate(bad)


# ── Coffres : chances, garantie, doublons ──

def test_odds_are_shown_for_every_draw_with_the_mystery_object_and_sum_to_100():
    odds = pc.odds(0, ALL_LEFT)
    assert sum(o["pct"] for o in odds) == pytest.approx(100.0)
    # Table sur 100 000 : jamais « 0,0 % », mais « 1 chance sur 100 000 » (économie du 4.11.2026).
    assert {"kind": "mythic", "label": "Objet mystère", "pct": 0.001, "text": "1 chance sur 100\u202f000"} in odds
    assert [o["text"] for o in odds] == ["58 %", "30,7 %", "7 %", "3 %", "1,1 %", "0,25 %", "1 chance sur 100\u202f000"]
    gone = pc.odds(0, {})
    assert gone[-1]["kind"] == "mythic" and gone[-1]["pct"] == 0.0 and "partis" in gone[-1]["label"]
    assert next(o for o in gone if o["kind"] == "legendary")["pct"] == 0.25   # la part du Mythique va au Légendaire
    guaranteed = pc.odds(pc.PITY - 1, ALL_LEFT)   # la garantie ne tire JAMAIS le Mythique
    assert [o["kind"] for o in guaranteed] == ["epic", "legendary"] and sum(o["pct"] for o in guaranteed) == pytest.approx(100)


def test_at_least_one_epic_every_45_chests_whatever_the_luck():
    for seed in range(40):
        rng, coll, owner, gap, worst = random.Random(seed), col.new_coll(), {"loop": {}}, 0, 0
        for _ in range(300):
            found = pc.draw(rng, {}, set(), pity=coll["pity"], mythic_left=ALL_LEFT)
            pc.note_chest(coll, found)
            if found["kind"] == "item":
                pc.apply(owner["loop"], found, coll)
            gap = 0 if found.get("rarity") in pc.EPIC_PLUS else gap + 1
            worst = max(worst, gap)
        assert worst < pc.PITY, seed
    assert pc.pity_left(0) == 45 and pc.pity_left(44) == 1


def test_a_duplicate_becomes_dust_and_a_legendary_prefers_the_missing_ones():
    coll = col.new_coll()
    shown = pc.apply({}, {"kind": "item", "item": "bonnet", "rarity": "common", "dup": True, "mint": False}, coll)
    assert coll["dust"] == 5 and "Doublon" in shown["label"] and shown["dust"] == 5
    pc.apply({}, {"kind": "item", "item": "cloche-vache", "rarity": "rare", "dup": True, "mint": False}, coll)
    assert coll["dust"] == 25
    legendaries = set(cat.chest_pool("legendary"))
    owned = legendaries - {"marmotte"}
    picks = {pc._accessory(random.Random(i), "legendary", owned, {})["item"] for i in range(30)}
    assert picks == {"marmotte"}
    every = pc._accessory(random.Random(1), "legendary", legendaries, {})
    assert every["dup"] and not every["mint"]
    fresh = pc._accessory(random.Random(1), "legendary", set(), {})
    assert fresh["mint"] and not fresh["dup"]


def test_a_mystery_object_is_a_chest_mythic_with_copies_left_never_a_party_souvenir():
    seen = {pc._accessory(random.Random(i), "mythic", set(), ALL_LEFT)["item"] for i in range(200)}
    assert seen == set(cat.mythics("chest"))
    only = pc._accessory(random.Random(3), "mythic", set(), {"m-disco": 1, "m-halloween": 0})
    assert only["item"] == "m-disco" and only["mint"]


# ── Atelier, boutique, décor ──

def test_the_workshop_uses_hearthstone_rates_and_never_makes_a_mythic_or_a_souvenir():
    assert [(r["dust"], r["craft"]) for r in cat.data()["rarities"][:4]] == [(5, 60), (20, 150), (100, 600), (400, 2400)]
    owner = {"loop": {}, "coll": col.new_coll() | {"dust": 2500, "upgraded": True}}
    assert col.craft(owner, set(), "bonnet") == {"kind": "crafted", "item": "bonnet", "cost": 60, "mint": False}
    assert owner["coll"]["dust"] == 2440 and owner["coll"]["inv"]["bonnet"] == 1
    assert col.craft(owner, set(), "piolet-or")["mint"] and owner["coll"]["dust"] == 40
    for refused, why in (("m-disco", "ne se fabrique"), ("lumi", "ne se fabrique"), ("decor-chalet", "ne se fabrique"),
                         ("cor-alpes", "manque 560"), ("bonnet", "déjà")):
        with pytest.raises(col.CollectionError, match=why):
            col.craft(owner, {"bonnet"}, refused)


def test_the_daily_shop_is_2_commons_and_a_rare_every_other_day_paid_with_earned_coins():
    rare_day, plain_day = ("2026-11-04", "2026-11-05") if col.rare_day("2026-11-04") else ("2026-11-05", "2026-11-04")
    shop = col.shop_today(random.Random(rare_day), rare_day)
    assert len(shop) == 3 and [cat.item(i)["rarity"] for i in shop] == ["common", "common", "rare"]
    assert [cat.item(i)["rarity"] for i in col.shop_today(random.Random(plain_day), plain_day)] == ["common", "common"]
    assert shop == col.shop_today(random.Random(rare_day), rare_day) and not any(cat.is_event_only(cat.item(i)) for i in shop)
    owner = {"loop": {"coins": 500}, "coll": col.new_coll() | {"upgraded": True}}
    col.buy(owner, set(), shop[0], rare_day, shop)
    assert owner["loop"]["coins"] == 200 and owner["coll"]["inv"][shop[0]] == 1   # Commun : 300 (avant 60)
    with pytest.raises(col.CollectionError, match="manque 1000"):                 # Rare : 1 200 (avant 200)
        col.buy(owner, set(), shop[2], rare_day, shop)
    with pytest.raises(col.CollectionError, match="déjà à toi"):
        col.buy(owner, {shop[0]}, shop[0], "2026-11-04", shop)
    with pytest.raises(col.CollectionError, match="pas en boutique"):
        col.buy(owner, set(), "lumi", "2026-11-04", shop)


def test_room_decor_is_the_big_coin_sink_and_snacks_are_limited_to_3_a_day():
    owner = {"loop": {"coins": 4000}, "coll": col.new_coll() | {"upgraded": True}}
    assert sorted({cat.shop_price(i) for i in cat.decor_items()}) == [1400, 3200]   # Rare 1 400, Épique 3 200
    col.buy(owner, set(), "decor-chalet", "2026-11-04", [])
    assert owner["loop"]["coins"] == 800
    for _ in range(3):
        col.buy(owner, set(), "snack:cupcake", "2026-11-04", [])
    assert owner["loop"]["inv"]["snack:cupcake"] == 3
    with pytest.raises(col.CollectionError, match="3 goûters"):
        col.buy(owner, set(), "snack:glace", "2026-11-04", [])
    col.buy(owner, set(), "snack:glace", "2026-11-05", [])


# ── Séries, Zicoudex, porter, vitrine, shiny ──

def test_a_complete_series_pays_its_bonus_once():
    owner = {"loop": {"coins": 0}, "coll": col.new_coll() | {"upgraded": True}}
    have = set(cat.series_items("disco"))
    got = col.series_bonus(owner, have)
    assert [g["series"] for g in got] == ["disco"] and owner["loop"]["coins"] == 150 and owner["coll"]["dust"] == 60
    assert col.series_bonus(owner, have) == []


def test_the_zicoudex_shows_everything_but_unowned_mythics_stay_masked():
    dex = col.dex({"bonnet"})
    rows = [x for s in dex for x in s["items"]]
    masked = [x for x in rows if x.get("masked")]
    assert len(masked) == len(cat.mythics()) and all(set(x) == {"masked", "rarity", "rarity_label", "label", "where"} for x in masked)
    assert all(x["label"] == "???" for x in masked)
    text = repr(masked)
    assert not any(cat.item(m)["label"] in text or m in text for m in cat.mythics())
    bonnet = next(x for x in rows if x.get("id") == "bonnet")
    assert bonnet["owned"] and next(x for x in rows if x.get("id") == "cape")["owned"] is False
    assert all(x["where"] for x in rows)
    mine = col.dex({"m-disco"}, [{"id": "u1", "item": "m-disco", "serial": 3, "code": "ZC-AAAA-BBBB-CCCC"}])
    disco = next(x for s in mine for x in s["items"] if x.get("id") == "m-disco")
    assert disco["label"] == "Couronne Aurore" and disco["serial"] == 3 and not disco.get("masked")


def test_wearing_one_accessory_per_slot_and_old_outfits_are_converted_once():
    owner = pet.new_owner()
    owner["loop"] = {"inv": {"outfit:casque": 1, "piece:boa": 2, "snack:glace": 1}}
    coll = col.coll_of(owner)
    assert coll["inv"] == {"casque": 1, "noeud": 1} and coll["dust"] == 10 and owner["loop"]["inv"] == {"snack:glace": 1}
    life = {"outfit": "noeud"}
    have = col.owned(owner)
    col.equip(life, have, "head", "casque")
    assert life["acc"] == {"neck": "noeud", "head": "casque"} and life["outfit"] is None
    with pytest.raises(col.CollectionError, match="ne va pas"):
        col.equip(life, have, "eyes", "casque")
    with pytest.raises(col.CollectionError, match="débloquée"):
        col.equip(life, have, "back", "cape")
    col.strip_lost(life, {"noeud"})
    assert life["acc"] == {"neck": "noeud"}


def test_the_showcase_holds_3_owned_items_and_a_short_title():
    life = {}
    col.set_showcase(life, {"bonnet", "piolet-or"}, ["bonnet", "piolet-or"], "Mes trésors", [{"item": "piolet-or", "serial": 2}])
    view = col.showcase_view(life)
    assert view["title"] == "Mes trésors" and [x["id"] for x in view["items"]] == ["bonnet", "piolet-or"]
    assert view["items"][1]["serial"] == 2
    with pytest.raises(col.CollectionError, match="3 objets"):
        col.set_showcase(life, {"a", "b", "c", "d"}, ["a", "b", "c", "d"], "", [])
    with pytest.raises(col.CollectionError, match="tes objets"):
        col.set_showcase(life, set(), ["bonnet"], "", [])


def test_a_shiny_zicou_is_one_in_64():
    rng = random.Random(4)
    n = sum(col.roll_shiny(rng) for _ in range(64000))
    assert 800 < n < 1200


# ── Certificats et cadeaux d'événement ──

INST = {"id": "4f1c2b8e-0000-4000-8000-000000000001", "item": "m-disco", "serial": 3, "edition": 25,
        "minted_at": "2026-11-04T20:15:00Z", "source": "chest"}


def test_a_certificate_is_signed_by_the_server_and_any_change_breaks_it():
    cert = pet_cert.sign("cle-du-serveur-de-test-0123456789abcdef", INST)
    key = pet_cert.public_key_b64("cle-du-serveur-de-test-0123456789abcdef")
    assert cert["payload"] == "ZC1|4f1c2b8e-0000-4000-8000-000000000001|m-disco|3|25|2026-11-04T20:15:00Z|chest"
    assert pet_cert.verify(key, cert["payload"], cert["sig"])
    assert not pet_cert.verify(key, cert["payload"].replace("|3|", "|1|"), cert["sig"])   # numéro retouché
    other = pet_cert.public_key_b64("une-autre-cle-qui-nest-pas-celle-de-party-000")
    assert not pet_cert.verify(other, cert["payload"], cert["sig"])
    assert re.fullmatch(r"ZC-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", cert["code"])
    assert pet_cert.normalize_code(cert["code"].lower().replace("-", " ")) == cert["code"]
    assert pet_cert.normalize_code("ZC-0000-1111-OOOO") == "" and pet_cert.normalize_code("bonjour") == ""


def test_event_rolls_are_reproducible_from_the_revealed_seed():
    seed = "a" * 64
    import hashlib
    assert pet_events.seed_matches(seed, hashlib.sha256(seed.encode()).hexdigest())
    rolls = [pet_events.roll(seed, "ev", f"user{i}", 0) for i in range(5000)]
    assert all(0 <= r < 100 for r in rolls) and 18 < sum(r < 20 for r in rolls) / 50 < 22   # ≈ 20 %
    assert pet_events.won(seed, "ev", "user1", 0, 100.0)
    assert any("Apple et Google ne sont ni organisateurs ni sponsors" in r for r in pet_events.RULES)
    assert any("Jamais selon un paiement" in r for r in pet_events.RULES)
