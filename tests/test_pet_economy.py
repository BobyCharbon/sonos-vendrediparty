"""Nouvelle économie de Zicou (décision de l'admin du 4.11.2026, en bêta) — calcul pur, horloge et hasard imposés :
chiffres (coffres sur 100 000, coffre bonus, garantie au 45e sans Mythique, plafond commun de 20 pièces, mission de la
semaine, nuit douce, boutique, atelier, décor, séries), festins, niveau (XP), festin offert, chambre, teintures, saisons
(date de sortie), file de la vedette à l'Apple TV."""
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from app import (pet, pet_catalog as cat, pet_chest as pc, pet_collection as col, pet_feast as pf, pet_loop as pl,
                 pet_reactions, pet_xp as px, tv_star)

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)
LEFT = {m: 8 for m in cat.mythics("chest")}


def adult(now=T0):
    life, owner = pet.new_pet(now - timedelta(days=5))
    pet.advance(life, now - timedelta(days=5) + timedelta(minutes=4), owner)
    life.update(stage="adult", at=pet.iso(now), g={"food": 80.0, "joy": 60.0, "energy": 80.0, "care": 80.0},
                asleep=False, sick=False, starving_h=0.0)
    owner["loop"] = {"coins": 1000}
    return life, owner


# ── Chiffres de rapport.md §5 ──

def test_the_report_numbers_are_in_the_code():
    assert sum(r["weight"] for r in pc.CHEST_TABLE) == 100_000
    assert {r["cat"]: r["weight"] for r in pc.CHEST_TABLE} == {"coins": 58000, "object": 30650, "common": 7000,
                                                               "rare": 3000, "epic": 1100, "legendary": 249, "mythic": 1}
    assert {r["cat"]: r["weight"] for r in pc.BONUS_TABLE} == {"coins": 72000, "object": 24300, "common": 3000, "rare": 700}
    assert pc.CHEST_COINS == (8, 20) and pc.BONUS_COINS_FACTOR == 1 and pc.PITY == 45
    assert {k: v[2] for k, v in pet.REWARDS.items()} == {"brain": 4, "party": 5, "music": 3}
    assert pet.ACTIVITY_COINS_PER_DAY == 20 and pl.WEEK_COINS == 60 and pl.SOFT_NIGHT_COINS == 6
    assert {r["id"]: (r["shop"], r["craft"]) for r in cat.data()["rarities"]} == {
        "common": (300, 60), "rare": (1200, 150), "epic": (None, 600), "legendary": (None, 2400), "mythic": (None, None)}
    assert {s["id"]: (s["bonus"]["coins"], s["bonus"]["dust"]) for s in cat.data()["series"]} == {
        "disco": (150, 60), "montagne": (150, 60), "escalade": (150, 60), "halloween": (150, 60), "nouvelan": (150, 60),
        "soirees": (200, 120)}
    assert col.SHOP_COMMONS == 2 and col.SHOP_RARES == 1 and col.SHOP_RARE_EVERY == 2
    assert all(5 <= cat.item(m)["edition"] <= 10 for m in cat.mythics())
    # Inchangé : goûters, limites du jour, poussière des doublons, shiny 1 sur 64.
    assert col.SNACK_PRICES == {"cupcake": 40, "glace": 40, "crepe": 50} and col.SHINY_ONE_IN == 64
    assert [r["dust"] for r in cat.data()["rarities"][:4]] == [5, 20, 100, 400]


def test_small_odds_read_one_chance_in_n_never_zero_percent():
    texts = {o["kind"]: o["text"] for o in pc.odds(0, LEFT)}
    assert texts["mythic"] == "1 chance sur 100 000" and texts["legendary"] == "0,25 %" and texts["coins"] == "58 %"
    assert pc.odds_text(1, 1000) == "0,1 %" and pc.odds_text(1, 2000) == "1 chance sur 2 000"
    assert all("0,0 %" not in o["text"] for o in pc.odds(0, LEFT) + pc.odds(0, LEFT, bonus=True))


def test_the_bonus_chest_never_gives_an_epic_or_better_and_its_odds_are_shown():
    rng = random.Random(3)
    cats = Counter(pc.draw(rng, {}, set(), pity=pc.PITY - 1, mythic_left=LEFT, bonus=True)["cat"] for _ in range(5000))
    assert set(cats) <= {"coins", "object", "common", "rare"}   # même à 44 coffres sans Épique : pas de garantie ici
    shown = {o["kind"]: o for o in pc.odds(0, LEFT, bonus=True)}
    assert {k for k, o in shown.items() if o["pct"] > 0} == {"coins", "object", "common", "rare"}
    assert sum(o["pct"] for o in shown.values()) == pytest.approx(100.0)
    assert all(shown[k]["pct"] == 0 and "jamais" in shown[k]["text"] for k in ("epic", "legendary", "mythic"))


def test_the_45th_daily_chest_is_an_epic_or_a_legendary_never_the_mythic():
    picks = Counter(pc.draw(random.Random(i), {}, set(), pity=pc.PITY - 1, mythic_left=LEFT)["cat"] for i in range(3000))
    assert set(picks) == {"epic", "legendary"}
    assert pc.draw(random.Random(1), {}, set(), pity=pc.PITY - 2, mythic_left=LEFT)["guaranteed"] is False


def test_coins_from_brain_parties_and_titles_share_one_cap_of_20_a_day():
    life, owner = adult()
    owner["loop"]["coins"] = 0
    times = [pet.iso(T0 - timedelta(minutes=i)) for i in range(1, 4)]
    life, owner, got = pet.rewards(life, owner, T0, times, times, times)
    assert sum(g["coins"] for g in got) == 20 and owner["loop"]["coins"] == 20   # 12 + 15 + 9 = 36 → 20
    assert len(got) == 9 and all(g["source"] in pet.REWARDS for g in got)        # la joie reste, toutes les 9 fois
    later = [pet.iso(T0 + timedelta(minutes=5))]
    life, owner, got = pet.rewards(life, owner, T0 + timedelta(minutes=6), later, [], [])
    assert got == [] and owner["loop"]["coins"] == 20                             # 4e Méninges : plafond de source
    tomorrow = T0 + timedelta(days=1)
    life, owner, got = pet.rewards(life, owner, tomorrow, [pet.iso(tomorrow)], [], [])
    assert got[0]["coins"] == 4 and owner["loop"]["coins"] == 24                  # nouveau jour : remis à zéro


def test_reaction_banners_follow_the_common_cap(tmp_path):
    log = pet_reactions.ActivityLog(tmp_path / "a.json")
    gid, now = "acct-x", T0.timestamp()
    log.mark_pet(gid, "Zicou", True)
    for i in range(3):
        log.react(gid, "party", f"p{i}", now + i)          # 3 × 5 = 15
    for i in range(3):
        log.react(gid, "brain", f"b{i}", now + 10 + i)     # 4, puis 1, puis 0
    shown = log.take(gid, now + 20)
    assert [x["coins"] for x in shown] == [5, 5, 4, 1, 0]   # file de 5 bandeaux au plus (les plus récents)
    assert "🪙" not in shown[-1]["text"] and "fier" in shown[-1]["text"]
    log2 = pet_reactions.ActivityLog(None)
    log2.mark_pet(gid, "Zicou", True)
    for i, src in enumerate(["party", "party", "party", "brain", "brain"]):
        log2.react(gid, src, f"x{i}", now + i)
    coins = [x["coins"] for x in log2.take(gid, now + 9)]
    assert coins == [5, 5, 5, 4, 1] and sum(coins) == pet.ACTIVITY_COINS_PER_DAY
    log2.react(gid, "music", "m", now + 10)
    last = log2.take(gid, now + 11)
    assert last[0]["coins"] == 0 and "🪙" not in last[0]["text"]


def test_week_mission_and_soft_night_pay_the_new_amounts():
    owner = {"loop": {}}
    loop = pl.loop_of(owner)
    loop.update(day="2026-11-04", coins=0, week={"key": "w", "id": "brain3", "text": "x", "counter": "brain", "need": 1,
                                                  "have": 0, "done": False})
    assert pl._week_progress(loop, "brain", 1)[0]["coins"] == 60 and loop["coins"] == 60


# ── Boutique, décor, saisons ──

def test_the_shop_has_a_rare_only_every_other_day():
    days = [(T0 + timedelta(days=i)).date().isoformat() for i in range(6)]
    rares = [sum(cat.item(i)["rarity"] == "rare" for i in col.shop_today(random.Random(d), d)) for d in days]
    assert rares in ([1, 0, 1, 0, 1, 0], [0, 1, 0, 1, 0, 1])


def test_a_series_not_yet_released_stays_out_of_chests_shop_workshop_and_shows_as_soon(monkeypatch):
    data = cat.data()
    series = [dict(s) | ({"release": "2027-02-01"} if s["id"] == "montagne" else {}) for s in data["series"]]
    monkeypatch.setattr(cat, "data", lambda: {**data, "series": series})
    today = "2026-11-04"
    mont = set(cat.series_items("montagne"))
    assert not mont & set(cat.chest_pool("common", today) + cat.chest_pool("rare", today) + cat.chest_pool("epic", today))
    assert mont & set(cat.chest_pool("common"))   # sans date : pas de filtre
    assert all(cat.craft_cost(i, today) is None for i in mont) and "decor-chalet" not in cat.decor_items(today)
    assert not mont & set(col.shop_today(random.Random(1), today))
    dex = col.dex(set(), [], today)
    soon = [s for s in dex if s.get("soon")]
    assert len(soon) == 1 and soon[0]["items"] == [] and soon[0]["label"] == "Bientôt"
    assert "Montagne" not in repr(soon) and "chalet" not in repr(soon)
    assert cat.released("montagne", "2027-02-01") and cat.upcoming(today) == ["montagne"]
    found = {pc.draw(random.Random(i), {}, set(), mythic_left=LEFT, today=today).get("item") for i in range(4000)}
    assert not found & mont


def test_room_grows_without_end_at_400_times_1_3_power_n():
    life, owner = adult()
    owner["loop"]["coins"] = 2000
    assert [col.room_price(n) for n in range(4)] == [400, 520, 680, 880]
    assert col.grow_room(owner, life) == {"kind": "room", "level": 1, "price": 400}
    col.grow_room(owner, life)
    assert life["room"] == 2 and owner["coll"]["room"] == 2 and owner["loop"]["coins"] == 1080
    owner["loop"]["coins"] = 10
    with pytest.raises(col.CollectionError, match="manque 670"):
        col.grow_room(owner, life)


def test_dyes_recolor_an_owned_item_once_per_color_and_price_follows_rarity():
    life, owner = adult()
    have = {"bonnet", "piolet-or"}
    assert col.dye_price("bonnet") == 60 and col.dye_price("piolet-or") == 500 and col.dye_price("m-disco") is None
    assert col.dye_price("decor-chalet") is None
    col.buy_dye(owner, have, "bonnet", "rose")
    col.wear_dye(owner, life, "bonnet", "rose")
    assert owner["loop"]["coins"] == 940 and col.dyes_worn(life) == {"bonnet": "rose"}
    with pytest.raises(col.CollectionError, match="déjà cette couleur"):
        col.buy_dye(owner, have, "bonnet", "rose")
    with pytest.raises(col.CollectionError, match="propres objets"):
        col.buy_dye(owner, have, "cape", "or")
    with pytest.raises(col.CollectionError, match="n'existe pas"):
        col.buy_dye(owner, have, "bonnet", "vert-pomme")
    with pytest.raises(col.CollectionError, match="Achète d'abord"):
        col.wear_dye(owner, life, "bonnet", "or")
    col.wear_dye(owner, life, "bonnet", "")
    assert col.dyes_worn(life) == {}
    life["dye"] = {"bonnet": "<script>"}
    assert col.dyes_worn(life) == {}   # jamais une couleur hors liste vers un ami ou la télé


# ── Festins ──

def spend_from(owner):
    return lambda price: col._spend(owner, price)


def test_raclette_freezes_every_gauge_for_24_hours_then_life_goes_on():
    life, owner = adult()
    pf.buy(life, owner, "raclette", T0, "2026-11-04", spend_from(owner))
    assert owner["loop"]["coins"] == 900
    before = dict(life["g"])
    pet.advance(life, T0 + timedelta(hours=23), owner)
    assert life["g"]["food"] == before["food"] and life["g"]["joy"] == before["joy"] and life["g"]["care"] == before["care"]
    pet.advance(life, T0 + timedelta(hours=25), owner)
    assert life["g"]["food"] < before["food"]   # une heure après la fin, la faim reprend (exactement 1 h)
    assert before["food"] - life["g"]["food"] == pytest.approx(pet.FOOD_RATE * pet.STAGE_FACTOR["adult"], abs=0.01)


def test_fondue_puts_joy_at_max_for_6_hours_with_a_party_mood():
    life, owner = adult()
    pf.buy(life, owner, "fondue", T0, "2026-11-04", spend_from(owner))
    assert life["g"]["joy"] == 100.0 and pet.emotion(life, T0 + timedelta(hours=1)) == "party"
    pet.advance(life, T0 + timedelta(hours=5, minutes=59), owner)
    assert life["g"]["joy"] == 100.0
    pet.advance(life, T0 + timedelta(hours=8), owner)
    assert life["g"]["joy"] < 100.0


def test_pizza_doubles_xp_and_its_daily_caps_for_24_hours():
    life, owner = adult()
    for _ in range(6):
        px.gain(owner, "care", T0, pf.xp_factor(life, T0))
    assert owner["xp"]["total"] == 20   # plafond des soins : 20
    pf.buy(life, owner, "pizza", T0 + timedelta(hours=1), "2026-11-04", spend_from(owner))
    now = T0 + timedelta(hours=2)
    assert pf.xp_factor(life, now) == 2
    got = px.gain(owner, "game", now, pf.xp_factor(life, now))
    assert got["xp"] == 10 and px.gain(owner, "game", now, 2)["xp"] == 10 and px.gain(owner, "game", now, 2) is None
    assert px.gain(owner, "care", now, 2)["xp"] == 8   # plafond doublé (40) : encore 20
    assert pf.xp_factor(life, T0 + timedelta(hours=25, minutes=1)) == 1


def test_one_feast_at_a_time_one_purchase_a_day_never_asleep_or_short_of_coins():
    life, owner = adult()
    pf.buy(life, owner, "pizza", T0, "2026-11-04", spend_from(owner))
    with pytest.raises(pf.FeastError, match="Un festin à la fois"):
        pf.buy(life, owner, "fondue", T0 + timedelta(hours=1), "2026-11-04", spend_from(owner))
    with pytest.raises(pf.FeastError, match="Un festin par jour"):
        pf.buy(life, owner, "fondue", T0 + timedelta(hours=25), "2026-11-04", spend_from(owner))
    pf.buy(life, owner, "fondue", T0 + timedelta(hours=25), "2026-11-05", spend_from(owner))
    assert owner["loop"]["coins"] == 1000 - 120 - 60
    life2, owner2 = adult()
    life2["asleep"] = True
    with pytest.raises(pf.FeastError, match="dort"):
        pf.buy(life2, owner2, "pizza", T0, "2026-11-04", spend_from(owner2))
    life2["asleep"], owner2["loop"]["coins"] = False, 50
    with pytest.raises(col.CollectionError, match="manque 70"):
        pf.buy(life2, owner2, "pizza", T0, "2026-11-04", spend_from(owner2))
    assert "feast" not in life2 and owner2["loop"]["coins"] == 50
    with pytest.raises(pf.FeastError, match="n'existe pas"):
        pf.buy(life2, owner2, "caviar", T0, "2026-11-04", spend_from(owner2))


def test_a_gifted_feast_starts_now_or_waits_its_turn_and_raclette_is_never_giftable():
    assert set(pf.GIFT_KINDS) == {"feast_pizza", "feast_fondue"}
    life, owner = adult()
    life, owner, applied = pet.gifts(life, owner, T0, [{"id": "g1", "kind": "feast_pizza", "from_name": "Léa"}])
    assert applied[0]["feast"] == "now" and life["feast"]["kind"] == "pizza" and life["feast"]["by"] == "Léa"
    life, owner, applied = pet.gifts(life, owner, T0 + timedelta(hours=1),
                                     [{"id": "g2", "kind": "feast_fondue", "from_name": "Tom"}])
    assert applied[0]["feast"] == "later" and pf.current(life, T0 + timedelta(hours=1))["kind"] == "pizza"
    pet.advance(life, T0 + timedelta(hours=26), owner)
    cur = pf.current(life, T0 + timedelta(hours=26))
    assert cur["kind"] == "fondue" and cur["from"] == pet.iso(T0 + timedelta(hours=24)) and life["feast_next"] == []
    assert owner["loop"]["coins"] == 1000   # recevoir un festin ne donne JAMAIS de pièces


# ── Niveau ──

def test_levels_need_50_plus_25n_xp_then_stars_every_1000_after_level_50():
    assert px.need(1) == 75 and px.need(10) == 300
    assert px.level_of(0)["level"] == 1 and px.level_of(74)["level"] == 1 and px.level_of(75)["level"] == 2
    top = px.level_of(px.XP_TO_MAX)
    assert top["level"] == 50 and top["stars"] == 0
    assert px.level_of(px.XP_TO_MAX + 2500) | {} == {"level": 50, "stars": 2, "xp": 500, "need": 1000,
                                                     "total": px.XP_TO_MAX + 2500}


def test_xp_is_capped_per_day_and_per_kind_and_survives_a_new_egg():
    life, owner = adult()
    for kind, n in (("care", 9), ("game", 9), ("social", 9)):
        for _ in range(n):
            px.gain(owner, kind, T0)
    assert owner["xp"]["total"] == 40 and px.gain(owner, "drink", T0) is None
    view = px.view(owner, T0)
    assert view["today"] == {"care": 20, "game": 10, "social": 10} and view["caps"] == {"care": 20, "game": 10, "social": 10}
    assert px.gain(owner, "care", T0 + timedelta(days=1))["xp"] == 4
    life["stage"] = "dead"
    life2, owner2, _ = pet.act(life, owner, "new_egg", T0 + timedelta(days=1))
    assert owner2["xp"]["total"] == 44   # attaché au compte : ne redescend jamais


# ── Vedette à l'Apple TV ──

def test_tv_stars_queue_one_after_another_once_per_soiree():
    clock = [1000.0]
    stars = tv_star.TvStars(clock=lambda: clock[0])
    look = {"stage": "adult", "emotion": "party", "variant": "star", "acc": {}, "shiny": False, "dye": {}}
    assert stars.book("u1", "s1", "Léa", look) == {"starts_in": 0, "seconds": 30}
    assert stars.book("u2", "s1", None, look)["starts_in"] == 30
    with pytest.raises(tv_star.StarError, match="déjà dans la file"):
        stars.book("u1", "s1", "Léa", look)
    live, waiting = stars.on_air("s1")
    assert live["name"] == "Léa" and live["left"] == 30 and waiting == 1 and "u1" not in repr(live)
    clock[0] += 31
    live, waiting = stars.on_air("s1")
    assert live["name"] is None and waiting == 0
    clock[0] += 30
    assert stars.on_air("s1") == (None, 0)
    for i in range(tv_star.QUEUE_MAX):
        stars.book(f"x{i}", "s1", None, look)
    with pytest.raises(tv_star.StarError, match="pleine"):
        stars.book("y", "s1", None, look)
    stars.keep_only("s2")
    assert stars.on_air("s2") == (None, 0) and not stars.full()
