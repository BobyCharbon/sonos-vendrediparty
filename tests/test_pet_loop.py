"""Boucle quotidienne du Compagnon (app/pet_loop.py), horloge et hasard simulés : coffre du jour (un par jour, non
cumulable, tirage du serveur et chances), missions et coffre bonus, mission de la semaine, rituels du matin et du soir,
paliers, heure apprise du rappel et son texte."""
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from app import pet, pet_texts
from app import pet_chest as pc
from app import pet_loop as pl

ZURICH = pet.TZ


def at(day, hour, minute=0):
    """Heure de Zurich, le `day`-ième jour de novembre 2026 (le 4 est un mercredi)."""
    return datetime(2026, 11, day, hour, minute, tzinfo=ZURICH).astimezone(timezone.utc)


def hatched(now):
    life, owner = pet.new_pet(now - timedelta(minutes=10))
    pet.advance(life, now, owner)
    return life, owner


def opened(life, owner, now, rng=None, src="tab"):
    return pl.visit(life, owner, now, rng or random.Random(1), src=src, seed="alice")


# ── Coffre du jour ──

def test_one_chest_a_day_until_midnight_and_never_cumulated():
    rng = random.Random(3)
    life, owner = hatched(at(4, 9))
    life, owner, events = opened(life, owner, at(4, 9))
    assert events[0] == {"kind": "new_day"} and pl.view(life, owner, at(4, 9))["chest"]["state"] == "ready"
    life, owner, effect = pl.act(life, owner, "chest", at(4, 9, 5), rng)
    assert effect["found"]["kind"] in ("coins", "snack", "sticker", "item") and effect["found"]["label"]
    with pytest.raises(pet.PetError, match="déjà ouvert"):
        pl.act(life, owner, "chest", at(4, 23, 59), rng)
    assert pl.view(life, owner, at(4, 23, 59))["chest"]["state"] == "opened"
    # Trois jours sans passer : un seul coffre le jour du retour (pas de rattrapage des coffres manqués).
    life, owner, _ = opened(life, owner, at(8, 12))
    life, owner, _ = pl.act(life, owner, "chest", at(8, 12), rng)
    with pytest.raises(pet.PetError):
        pl.act(life, owner, "chest", at(8, 13), rng)


def test_a_chest_not_opened_before_midnight_is_gone():
    life, owner = hatched(at(4, 20))
    life, owner, _ = opened(life, owner, at(4, 20))
    view = pl.view(life, owner, at(5, 0, 1))   # minuit passé, pas encore revenu
    assert view["chest"]["state"] == "ready" and view["missions"] == []   # le nouveau jour n'est pas encore ouvert
    life, owner, _ = opened(life, owner, at(5, 8))
    assert owner["loop"]["chest"] == {"day": "2026-11-05", "opened": False, "found": None}


def test_the_draw_follows_the_announced_odds():
    rng, count = random.Random(42), Counter()
    left = {m: 25 for m in pc.mythic_pool({"m-disco": 25, "m-montagne": 25, "m-escalade": 25, "m-halloween": 25, "m-nouvelan": 25})}
    for _ in range(40000):
        count[pc.draw(rng, {}, {"noeud"}, mythic_left=left)["cat"]] += 1
    shown = {o["kind"]: o["pct"] for o in pc.odds(0, left)}
    assert shown == {"coins": 58.0, "object": 30.65, "common": 7.0, "rare": 3.0, "epic": 1.1, "legendary": 0.249, "mythic": 0.001}
    for kind, pct in shown.items():
        assert abs(count[kind] / 400 - pct) < max(0.6, pct * 0.25), kind


def test_the_draw_is_deterministic_and_keeps_its_roll():
    a = pc.draw(random.Random("alice:2026-11-04:chest"), {}, set())
    b = pc.draw(random.Random("alice:2026-11-04:chest"), {}, set())
    assert a == b and a["table"] == pc.TABLE_VERSION and 0 <= a["roll"] < 1


def test_objects_are_half_snacks_half_stickers_and_coins_stay_between_8_and_20():
    rng, fam, coins, bonus = random.Random(5), Counter(), [], []
    for _ in range(20000):
        d = pc.draw(rng, {}, set())
        if d["cat"] == "object":
            fam[d["kind"]] += 1
        elif d["kind"] == "coins":
            coins.append(d["amount"])
    for _ in range(2000):
        d = pc.draw(rng, {}, set(), bonus=True)
        if d["cat"] == "coins":
            bonus.append(d["amount"])
    assert 0.4 < fam["snack"] / (fam["snack"] + fam["sticker"]) < 0.6
    assert min(coins) == 8 and max(coins) == 20 and min(bonus) == 8 and max(bonus) == 20   # coffre bonus : plus doublé


def test_rare_snacks_go_to_the_bag_and_are_eaten_outside_the_meal_limit():
    rng = random.Random(1)
    life, owner = hatched(at(4, 10))
    life, owner, _ = opened(life, owner, at(4, 10))
    pc.apply(owner["loop"], {"kind": "snack", "item": "snack:cupcake"})
    owner["uses"] = {"feed": pet.DAILY_LIMITS["feed"]}
    owner["day"] = "2026-11-04"
    life["g"]["food"] = 20.0
    assert pl.view(life, owner, at(4, 10))["bag"] == [{"id": "cupcake", "label": "Cupcake arc-en-ciel", "emoji": "🧁", "n": 1}]
    life2, owner2, _ = pl.act(life, owner, "treat", at(4, 10, 5), rng, item="cupcake")
    assert life2["g"]["food"] > 50 and owner2["loop"]["inv"]["snack:cupcake"] == 0
    with pytest.raises(pet.PetError, match="sac"):
        pl.act(life2, owner2, "treat", at(4, 10, 6), rng, item="cupcake")


def test_the_chest_alone_never_counts_for_the_streak_a_real_care_does():
    """Playtest « Marc » : le paresseux (un toucher par jour sur le coffre) gardait sa série. Il faut un vrai soin."""
    life, owner = hatched(at(4, 10))
    for d in (4, 5, 6):
        life, owner, _ = opened(life, owner, at(d, 10))
        life, owner, effect = pl.act(life, owner, "chest", at(d, 10), random.Random(d))
        assert owner["streak"]["count"] == 0 and effect["streak"] == []
    for d in (7, 8, 9):
        life, owner, _ = opened(life, owner, at(d, 10))
        pet.advance(life, at(d, 10, 1), owner)
        life["asleep"] = False
        life, owner, effect = pet.act(life, owner, "feed", at(d, 10, 1))
    assert owner["streak"]["count"] == 3
    assert [e["days"] for e in pl.streak_rewards(owner, effect["streak"])] == [3]   # palier de 3 jours : +30 pièces
    assert "lunettes" in pet.unlock(owner) + owner["unlocked"]


# ── Missions ──

def test_three_missions_a_day_one_of_each_family_then_a_bonus_chest():
    rng = random.Random(9)
    life, owner = hatched(at(4, 10))
    life, owner, _ = opened(life, owner, at(4, 10), rng)
    missions = owner["loop"]["missions"]["list"]
    assert [m["family"] for m in missions] == ["care", "game", "social"]
    with pytest.raises(pet.PetError, match="3 missions"):
        pl.act(life, owner, "bonus_chest", at(4, 10), rng)
    events = []
    for m in missions:
        events += pl.note(owner, m["counter"], at(4, 11), n=m["need"])
    assert [e["kind"] for e in events].count("mission") == 3 and events[-1]["kind"] in ("bonus_ready", "week_done")
    life, owner, effect = pl.act(life, owner, "bonus_chest", at(4, 12), rng)
    assert effect["found"] and pl.view(life, owner, at(4, 12))["bonus"] == "opened"
    with pytest.raises(pet.PetError, match="déjà ouvert"):
        pl.act(life, owner, "bonus_chest", at(4, 12), rng)


def test_missions_are_new_every_day_and_vary():
    rng = random.Random(11)
    life, owner = hatched(at(4, 10))
    seen = set()
    for d in range(4, 20):
        life, owner, _ = opened(life, owner, at(d, 10), rng)
        seen |= {m["id"] for m in owner["loop"]["missions"]["list"]}
        assert all(m["have"] == 0 for m in owner["loop"]["missions"]["list"])
    assert len(seen) >= 6


def test_a_play_score_above_40_and_care_count_through_after_care():
    life, owner = hatched(at(4, 10))
    life, owner, _ = opened(life, owner, at(4, 10))
    pl.after_care(owner, "play", 41, at(4, 10))
    pl.after_care(owner, "play", 40, at(4, 10))
    assert owner["loop"]["c"] == {"play": 2, "score40": 1}


def test_the_weekly_mission_counts_care_days_and_pays_once():
    life, owner = hatched(at(2, 10))   # lundi
    life, owner, _ = opened(life, owner, at(2, 10))
    owner["loop"]["week"] = {"key": "2026-W45", "id": "care5", "text": "x", "counter": "care_day", "need": 5,
                             "have": 0, "done": False}
    coins = owner["loop"]["coins"]
    for d in range(2, 8):
        life, owner, _ = opened(life, owner, at(d, 10))
        events = pl.note(owner, "feed", at(d, 10))
        assert pl.note(owner, "cuddle", at(d, 10)) == []   # deux soins le même jour : un seul jour compté
        if d == 6:
            assert events == [{"kind": "week_done", "id": "care5", "text": "x", "coins": pl.WEEK_COINS}]
    assert owner["loop"]["week"]["done"] and owner["loop"]["coins"] == coins + pl.WEEK_COINS
    life, owner, _ = opened(life, owner, at(9, 10))  # lundi suivant : nouvelle mission
    assert owner["loop"]["week"]["key"] == "2026-W46" and not owner["loop"]["week"]["done"]


def test_coming_on_friday_counts_for_the_friday_mission():
    life, owner = hatched(at(2, 10))
    life, owner, _ = opened(life, owner, at(2, 10))
    owner["loop"]["week"] = {"key": "2026-W45", "id": "friday", "text": "Passe le voir vendredi", "counter": "friday",
                             "need": 1, "have": 0, "done": False}
    life, owner, events = opened(life, owner, at(6, 18))
    assert {"kind": "week_done", "id": "friday", "text": "Passe le voir vendredi", "coins": pl.WEEK_COINS} in events


@pytest.mark.parametrize("day", [6, 7, 8])   # vendredi, samedi, dimanche
def test_the_friday_mission_is_never_drawn_on_or_after_friday(day):
    """Tirée un vendredi, « Passe le voir vendredi » se validait à la seconde où elle apparaissait (+60 pièces sans
    objectif) ; plus tard dans la semaine, elle était impossible. Une autre mission, même tirage (HMAC du jour)."""
    drawn = set()
    for seed in range(200):
        life, owner = hatched(at(day, 10))
        life, owner, events = opened(life, owner, at(day, 10), rng=random.Random(seed))
        drawn.add(owner["loop"]["week"]["id"])
        assert not any(e["kind"] == "week_done" for e in events)
    assert "friday" not in drawn and drawn == {w[0] for w in pl.WEEKLY} - {"friday"}


def test_the_friday_mission_can_still_be_drawn_before_friday():
    drawn = set()
    for seed in range(200):
        life, owner = hatched(at(5, 10))   # jeudi
        life, owner, _ = opened(life, owner, at(5, 10), rng=random.Random(seed))
        drawn.add(owner["loop"]["week"]["id"])
    assert drawn == {w[0] for w in pl.WEEKLY}


# ── Rituels ──

def test_the_morning_card_before_11_only_and_dreams_vary():
    life, owner = hatched(at(4, 8))
    life, owner, _ = opened(life, owner, at(4, 8))
    text = pl.view(life, owner, at(4, 8, 30))["morning"]
    assert text in pet_texts.DREAMS and pl.view(life, owner, at(4, 11, 1))["morning"] is None
    life2, owner2, _ = opened(*hatched(at(4, 12)), at(4, 12))
    assert pl.view(life2, owner2, at(4, 12))["morning"] is None   # 1re visite l'après-midi : pas de carte
    dreams = {pl.dream(datetime(2026, 11, 4).date() + timedelta(days=i), "alice") for i in range(len(pet_texts.DREAMS))}
    assert len(dreams) == len(pet_texts.DREAMS) >= 40          # tous différents avant de se répéter


def test_tucking_in_the_evening_gives_a_soft_night_without_any_penalty_otherwise():
    rng = random.Random(2)
    life, owner = hatched(at(4, 20))
    life, owner, _ = opened(life, owner, at(4, 20))
    with pytest.raises(pet.PetError, match="21 h"):
        pl.act(life, owner, "tuck", at(4, 20, 59), rng)
    life, owner, effect = pl.act(life, owner, "tuck", at(4, 22), rng)
    assert life["asleep"] and effect["text"] in pet_texts.LULLABIES and owner["streak"]["count"] == 0   # pas un soin
    with pytest.raises(pet.PetError, match="déjà bordé"):
        pl.act(life, owner, "tuck", at(4, 23), rng)
    with pytest.raises(pet.PetError):
        pl.act(life, owner, "tuck", at(4, 23, 31), rng)
    owner["loop"]["week"]["done"] = True   # (pas de récompense de la semaine dans ce compte)
    coins = owner["loop"]["coins"]
    life, owner, events = opened(life, owner, at(5, 9))
    assert {"kind": "soft_night", "coins": pl.SOFT_NIGHT_COINS} in events and owner["loop"]["coins"] == coins + 6
    # Pas couché hier soir : pas de bonus, et rien de retiré.
    life, owner, events = opened(life, owner, at(6, 9))
    assert not [e for e in events if e["kind"] == "soft_night"] and owner["loop"]["coins"] == coins + 6


# ── Rappel du jour ──

def test_learned_hour_is_the_usual_visit_minus_15_minutes():
    visits = [[f"2026-11-{d:02d}", 19 * 60 + 30] for d in range(1, 8)]
    assert pl.learned_minute(visits, "x") == 19 * 60 + 15
    assert pl.learned_minute([["d", 7 * 60]] * 5, "x") == 8 * 60                    # jamais avant 8 h
    assert pl.learned_minute([["d", 23 * 60 + 50]] * 5, "x") == 22 * 60 + 45       # jamais après 22 h 45
    fallback = {pl.learned_minute([], f"user{i}") for i in range(200)}
    assert min(fallback) >= 17 * 60 and max(fallback) < 20 * 60 and len(fallback) > 50   # 17 h – 20 h, étalé


def test_visits_from_a_notification_do_not_teach_the_hour():
    life, owner = hatched(at(4, 18))
    life, owner, _ = opened(life, owner, at(4, 18), src="notification")
    life, owner, _ = opened(life, owner, at(5, 12), src="tab")
    assert owner["loop"]["visits"] == [["2026-11-05", 12 * 60]]


def test_the_nudge_for_tomorrow_learned_hour_and_streak_milestone():
    rng = random.Random(4)
    life, owner = hatched(at(1, 19))
    for d in (1, 2, 3, 4, 5):
        life, owner, _ = opened(life, owner, at(d, 19), rng)
        life, owner, _ = pl.act(life, owner, "chest", at(d, 19), rng)
        life["asleep"] = False
        life, owner, _ = pet.act(life, owner, "feed", at(d, 19, 1))
    n = pl.nudge(life, owner, at(5, 19, 5), "alice")
    assert n["day"] == "2026-11-06" and n["minute"] == 18 * 60 + 45
    assert n["kind"] == "pet_daily" and n["title"] == life["name"] == "Zicou"
    life, owner, _ = opened(life, owner, at(6, 19), rng)
    life, owner, _ = pl.act(life, owner, "chest", at(6, 19), rng)
    life, owner, _ = pet.act(life, owner, "feed", at(6, 19, 1))       # 6 jours : demain, palier de 7
    n = pl.nudge(life, owner, at(6, 19, 5), "alice")
    assert n["kind"] == "pet_streak" and "7 jours" in n["body"] and "Casquette" in n["body"]
    assert n["alt_body"] != n["body"] and n["alt_title"] == "Zicou"   # repli si « Paliers de série » est coupé


def test_the_daily_text_says_what_really_happens():
    life, owner = hatched(at(4, 10))
    life, owner, _ = opened(life, owner, at(4, 10))
    hungry = pl.nudge(life, owner, at(4, 10), "a", hungry_at=pet.iso(at(5, 9)))
    assert hungry["body"] in pet_texts.NUDGE_HUNGRY
    plain = pl.nudge(life, owner, at(4, 10), "a", hungry_at=pet.iso(at(7, 9)))
    assert plain["body"] not in pet_texts.NUDGE_HUNGRY


def test_no_nudge_for_an_egg_or_a_pet_that_flew_away():
    life, owner = pet.new_pet(at(4, 10))
    assert pl.nudge(life, owner, at(4, 10), "a") is None
    life["stage"] = "dead"
    assert pl.nudge(life, owner, at(4, 10), "a") is None


def test_view_shows_everything_the_screen_needs():
    life, owner = hatched(at(6, 21, 30))   # vendredi soir
    life, owner, _ = opened(life, owner, at(6, 21, 30))
    v = pl.view(life, owner, at(6, 21, 30))
    assert v["evening"] == {"tucked": False} and v["morning"] is None and v["streak"]["respite"] == "friday"
    assert v["streak"]["next"] == {"days": 3, "reward": pl.MILESTONE_REWARDS[3][2]}
    assert [m["days"] for m in v["streak"]["milestones"]] == list(pl.MILESTONE_REWARDS)
    assert [o["kind"] for o in v["odds"]] == ["coins", "object", "common", "rare", "epic", "legendary", "mythic"]
    assert v["odds"][-1]["pct"] == 0.0 and v["pity_left"] == pc.PITY   # sans Mythique disponible : « tous partis »
    assert len(v["missions"]) == 3 and v["week"]["coins"] == pl.WEEK_COINS and v["stickers"]["total"] == 25


def test_texts_are_never_guilt_tripping():
    words = ("faute", "oublié", "abandonn", "honte", "tué", "à cause de toi", "déçu", "triste à cause")
    texts = (list(pet_texts.DREAMS) + list(pet_texts.LULLABIES) + list(pet_texts.NUDGE_CHEST)
             + list(pet_texts.NUDGE_HUNGRY) + [pet_texts.NUDGE_STREAK, pet_texts.NUDGE_WEEK, pet_texts.NUDGE_MILESTONE])
    from app import pet_store
    texts += list(pet_store.LOOP_TEXT.values()) + [pet_store.BROKEN_PLAIN, pet_store.BROKEN_REPAIR]
    assert not [t for t in texts for w in words if w in t.lower()]
