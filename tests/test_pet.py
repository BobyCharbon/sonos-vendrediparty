"""Compagnon (app/pet.py) : la vie calculée à partir des dates, avec une horloge simulée — éclosion, jauges, sommeil,
maladie, évolution selon les soins, limites du jour, série 🔥, tenues, récompenses, cadeaux, mort après une longue
négligence, souvenirs et nouvel œuf."""
import copy
from datetime import datetime, timedelta, timezone

import pytest

from app import pet

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)   # 10 h à Zurich


def hatched(at=T0):
    life, owner = pet.new_pet(at)
    pet.advance(life, at + timedelta(seconds=pet.EGG_SECONDS), owner)
    return life, owner


def h(n):
    return T0 + timedelta(seconds=pet.EGG_SECONDS) + timedelta(hours=n)


def care_routine(life, owner, start_h, end_h, every_h=5):
    """Un propriétaire attentif : passe toutes les `every_h` heures, nourrit, joue, soigne, câline."""
    t = start_h
    while t < end_h:
        pet.advance(life, h(t), owner)
        if life["asleep"]:
            life, owner, _ = pet.act(life, owner, "wake", h(t))
        for action in ("feed", "play", "heal", "cuddle"):
            try:
                life, owner, _ = pet.act(life, owner, action, h(t), score=80)
            except pet.PetError:
                pass
        if life["stage"] != "dead" and life["g"]["energy"] < 30 and not life["asleep"]:
            life, owner, _ = pet.act(life, owner, "sleep", h(t))
        t += every_h
    return life, owner


# ── Œuf et éclosion ──

def test_a_new_pet_is_an_egg_that_hatches_after_three_minutes():
    life, owner = pet.new_pet(T0)
    assert life["stage"] == "egg" and life["gen"] == 1 and owner["unlocked"] == ["noeud"]
    assert pet.advance(life, T0 + timedelta(seconds=pet.EGG_SECONDS - 1), owner) == []
    assert life["stage"] == "egg" and pet.next_stage_in(life, T0) == pet.EGG_SECONDS
    assert pet.advance(life, T0 + timedelta(seconds=pet.EGG_SECONDS), owner) == [{"kind": "hatched"}]
    assert life["stage"] == "baby" and life["g"] == pet.START_GAUGES
    assert pet.emotion(life, T0 + timedelta(minutes=4)) == "happy"


def test_an_egg_cannot_be_fed_but_can_be_named():
    life, owner = pet.new_pet(T0)
    with pytest.raises(pet.PetError, match="œuf"):
        pet.act(life, owner, "feed", T0)
    life2, _, _ = pet.act(life, owner, "rename", T0, name="  Disco\u0000  Ball ")
    assert life2["name"] == "Disco Ball" and life["name"] == pet.DEFAULT_NAME


# ── Jauges, sommeil, maladie ──

def test_gauges_go_down_with_time_and_never_below_zero():
    life, owner = hatched()
    pet.advance(life, h(10), owner)
    g = life["g"]
    assert g["food"] == pytest.approx(80 - 10 * pet.FOOD_RATE * pet.STAGE_FACTOR["baby"], abs=0.01)
    assert g["care"] == pytest.approx(90 - 10 * pet.CARE_RATE, abs=0.01)
    pet.advance(life, h(60), owner)
    assert all(0 <= v <= 100 for v in life["g"].values())
    assert life["g"]["food"] == 0 and life["starving_h"] > 0


def test_advance_never_goes_back_in_time():
    life, owner = hatched()
    pet.advance(life, h(5), owner)
    before = copy.deepcopy(life)
    pet.advance(life, h(2), owner)
    assert life == before


def test_an_exhausted_pet_falls_asleep_then_wakes_up_rested():
    life, owner = hatched()
    life["g"].update(food=100, energy=3)
    pet.advance(life, h(1.5), owner)
    assert life["asleep"] and pet.emotion(life, h(1.5)) == "sleep"
    pet.advance(life, h(12), owner)
    assert not life["asleep"] and life["g"]["energy"] > 50


def test_turning_the_light_off_and_on():
    life, owner = hatched()
    with pytest.raises(pet.PetError, match="pas sommeil"):
        pet.act(life, owner, "sleep", h(0))
    life["g"]["energy"] = 40
    life, owner, _ = pet.act(life, owner, "sleep", h(0))
    assert life["asleep"]
    with pytest.raises(pet.PetError, match="dort"):
        pet.act(life, owner, "feed", h(0.1))
    life, owner, _ = pet.act(life, owner, "wake", h(1))
    assert not life["asleep"] and life["g"]["energy"] > 40


def test_a_dirty_pet_gets_sick_and_a_heal_cures_it():
    life, owner = hatched()
    life["g"]["care"] = 1
    pet.advance(life, h(1), owner)
    assert life["sick"] and pet.emotion(life, h(1)) == "sick"
    life, owner, _ = pet.act(life, owner, "heal", h(1))
    assert not life["sick"] and life["g"]["care"] == pytest.approx(pet.HEAL_CARE)


# ── Actions du jour ──

def test_actions_are_limited_per_day_and_reset_at_midnight_in_zurich():
    life, owner = hatched()
    for _ in range(pet.DAILY_LIMITS["cuddle"]):
        life, owner, _ = pet.act(life, owner, "cuddle", h(1))
    with pytest.raises(pet.PetError, match="câlins"):
        pet.act(life, owner, "cuddle", h(1))
    assert pet.view(life, owner, h(1))["left"]["cuddle"] == 0
    midnight_zurich = datetime(2026, 11, 4, 23, 0, 30, tzinfo=timezone.utc)   # 00:00:30 à Zurich
    life, owner, _ = pet.act(life, owner, "cuddle", midnight_zurich)
    assert owner["uses"]["cuddle"] == 1


def test_feeding_fills_the_belly_but_not_when_full():
    life, owner = hatched()
    life["g"]["food"] = 20
    life, owner, _ = pet.act(life, owner, "feed", h(0))
    assert life["g"]["food"] == pytest.approx(20 + pet.FEED_FOOD, abs=0.1)
    life["g"]["food"] = 99
    with pytest.raises(pet.PetError, match="plus faim"):
        pet.act(life, owner, "feed", h(0))


def test_play_uses_the_micro_game_score_and_needs_energy():
    life, owner = hatched()
    life["g"]["joy"] = 10
    low, _, _ = pet.act(life, owner, "play", h(0), score=0)
    high, _, _ = pet.act(life, owner, "play", h(0), score=999)   # borné à 100
    assert low["g"]["joy"] == pytest.approx(10 + pet.PLAY_JOY_MIN, abs=0.1)
    assert high["g"]["joy"] == pytest.approx(10 + pet.PLAY_JOY_MIN + 100 * pet.PLAY_JOY_SCORE, abs=0.1)
    life["g"]["energy"] = 5
    with pytest.raises(pet.PetError, match="fatigué"):
        pet.act(life, owner, "play", h(0))


def test_act_never_changes_its_inputs():
    life, owner = hatched()
    before = (copy.deepcopy(life), copy.deepcopy(owner))
    pet.act(life, owner, "feed", h(3))
    assert (life, owner) == before


def test_unknown_action_and_locked_outfit_are_refused():
    life, owner = hatched()
    with pytest.raises(pet.PetError):
        pet.act(life, owner, "dance", h(0))
    with pytest.raises(pet.PetError, match="débloquée"):
        pet.act(life, owner, "outfit", h(0), outfit="couronne")
    life, owner, _ = pet.act(life, owner, "outfit", h(0), outfit="noeud")
    assert life["outfit"] == "noeud"
    life, owner, _ = pet.act(life, owner, "outfit", h(0), outfit="")
    assert life["outfit"] is None


# ── Série 🔥 et tenues ──

def test_streak_grows_day_after_day_and_unlocks_outfits():
    life, owner = hatched()
    owner["streak"]["freezes"] = 0   # sans le gel offert au départ (testé dans test_pet_streak.py)
    unlocked = []
    for day in range(7):
        pet.advance(life, h(24 * day + 1), owner)
        if life["asleep"]:
            life, owner, _ = pet.act(life, owner, "wake", h(24 * day + 1))
        life, owner, effect = pet.act(life, owner, "cuddle", h(24 * day + 1))
        if life["g"]["food"] < 60:
            life, owner, _ = pet.act(life, owner, "feed", h(24 * day + 1))
        unlocked += effect["unlocked"]
    assert owner["streak"]["count"] == 7 and owner["streak"]["best"] == 7
    assert pet.streak_now(owner, h(24 * 6 + 3)) == 7
    assert unlocked == ["lunettes", "casquette"]
    assert owner["streak"]["freezes"] == 1                # 7 jours de série : un gel ❄️ gagné
    assert pet.streak_now(owner, h(24 * 8 + 3)) == 7      # un jour manqué (mercredi) : protégé par le gel
    life, owner, effect = pet.act(life, owner, "heal", h(24 * 9))   # deux jours manqués : la série repart (le record reste)
    assert owner["streak"]["count"] == 1 and owner["streak"]["best"] == 7
    assert owner["streak"]["freezes"] == 1                # le gel n'est pas dépensé pour rien
    assert owner["streak"]["lost"]["count"] == 7 and [e["kind"] for e in effect["streak"]] == ["broken"]


def test_two_care_actions_the_same_day_count_once():
    life, owner = hatched()
    life, owner, _ = pet.act(life, owner, "cuddle", h(1))
    life, owner, _ = pet.act(life, owner, "cuddle", h(2))
    assert owner["streak"]["count"] == 1


# ── Évolution selon la qualité des soins ──

def test_baby_teen_adult_with_good_care_gives_a_star_and_a_crown():
    life, owner = hatched()
    life, owner = care_routine(life, owner, 0, 100, every_h=4)
    assert life["stage"] == "adult" and life["variant"] == "star"
    assert owner["stats"]["stars"] == 1 and "couronne" in owner["unlocked"]
    assert pet.next_stage_in(life, h(100)) is None


def test_little_care_gives_a_wild_teen():
    life, owner = hatched()   # aucun soin pendant tout le stade bébé
    pet.advance(life, h(24.5), owner)
    assert life["stage"] == "teen" and life["variant"] == "wild"


def test_one_lonely_meal_a_day_is_not_a_cared_day():
    life, owner = hatched()
    life, owner, _ = pet.act(life, owner, "feed", h(20))
    assert life["cares"] == {pet.day_of(h(20)): 1}
    alone = pet.quality(life)
    life, owner, _ = pet.act(life, owner, "cuddle", h(20.1))   # 2e soin le même jour : un vrai passage
    assert pet.quality(life) >= alone + pet.REGULARITY_BONUS - 0.5


def test_evolution_times():
    life, owner = hatched()
    assert pet.next_stage_in(life, h(0)) == pet.BABY_HOURS * 3600
    life, owner = care_routine(life, owner, 0, 30, every_h=5)
    assert life["stage"] == "teen"
    assert pet.next_stage_in(life, h(30)) == (pet.BABY_HOURS + pet.TEEN_HOURS - 30) * 3600


# ── Mort, souvenirs, nouvel œuf ──

def test_death_only_after_three_days_with_an_empty_belly_and_projections_match():
    life, owner = hatched()
    proj = pet.projections(life, h(0))
    hungry, starving, dies = (pet.parse(proj[k]) for k in ("hungry_at", "starving_at", "dies_at"))
    assert h(0) < hungry < starving < dies
    assert (dies - starving).total_seconds() == pytest.approx(pet.DEATH_STARVING_HOURS * 3600, abs=60)
    assert (dies - h(0)).total_seconds() > 3.5 * 24 * 3600   # jamais en moins de 3 jours et demi sans soins
    just_before = copy.deepcopy(life)
    pet.advance(just_before, dies - timedelta(minutes=5), copy.deepcopy(owner))
    assert just_before["stage"] != "dead"
    assert pet.view(just_before, owner, dies - timedelta(minutes=5))["danger"] == {"hours_left": 0}
    events = pet.advance(life, dies + timedelta(hours=10), owner)
    assert events[-1] == {"kind": "died"} and life["stage"] == "dead"
    assert abs((pet.parse(life["died_at"]) - dies).total_seconds()) < 60
    assert pet.emotion(life, dies) == "ghost"


def test_a_meal_before_the_end_saves_it_and_resets_the_countdown():
    life, owner = hatched()
    dies = pet.parse(pet.projections(life, h(0))["dies_at"])
    life, owner, _ = pet.act(life, owner, "feed", dies - timedelta(hours=1))
    assert life["stage"] != "dead" and life["starving_h"] == 0
    later = pet.parse(pet.projections(life, dies - timedelta(hours=1))["dies_at"])
    assert later > dies + timedelta(days=3)


def test_memorial_record_and_a_new_egg():
    life, owner = hatched()
    life, owner, _ = pet.act(life, owner, "rename", h(0), name="Bijou")
    life, owner, _ = pet.act(life, owner, "cuddle", h(1))
    pet.advance(life, h(24 * 10), owner)
    assert life["stage"] == "dead"
    memo = owner["memorial"][0]
    assert memo["name"] == "Bijou" and memo["gen"] == 1 and memo["hours"] > 72
    assert owner["record_hours"] == memo["hours"]
    with pytest.raises(pet.PetError, match="envolé"):
        pet.act(life, owner, "feed", h(24 * 10))
    with pytest.raises(pet.PetError):
        pet.act(hatched()[0], owner, "new_egg", h(0))
    egg, owner2, effect = pet.act(life, owner, "new_egg", h(24 * 10))
    assert egg["stage"] == "egg" and egg["gen"] == 2 and egg["name"] == "Bijou"
    assert owner2["memorial"] == owner["memorial"] and owner2["unlocked"] == owner["unlocked"]
    assert owner2["stats"]["eggs"] == 2 and effect["events"][-1] == {"kind": "egg"}
    pet.advance(egg, h(24 * 10) + timedelta(minutes=5), owner2)
    assert egg["stage"] == "baby"


def test_memorial_keeps_the_last_twelve():
    owner = pet.new_owner()
    for gen in range(1, 16):
        life = pet.new_life(T0, gen)
        pet.advance(life, T0 + timedelta(days=20), owner)
    assert len(owner["memorial"]) == pet.MEMORIAL_MAX and owner["memorial"][0]["gen"] == 15


# ── Récompenses et cadeaux ──

def test_rewards_are_counted_once_and_capped_per_day():
    life, owner = hatched()
    life["g"]["joy"] = 10
    games = [pet.iso(h(1) - timedelta(minutes=m)) for m in (1, 2, 3, 4, 5)]
    life, owner, got = pet.rewards(life, owner, h(1), games, [], [])
    assert len(got) == pet.REWARDS["brain"][1] and owner["stats"]["brain"] == 5
    assert life["g"]["joy"] == pytest.approx(10 + 3 * pet.REWARDS["brain"][0]["joy"], abs=0.1)
    again = pet.rewards(life, owner, h(1.5), games, [], [])
    assert again[2] == [] and again[1]["stats"]["brain"] == 5


def test_an_old_game_does_not_count_and_an_egg_gets_nothing_but_the_cursor_moves():
    life, owner = pet.new_pet(T0)
    old = pet.iso(T0 - timedelta(hours=pet.REWARD_WINDOW_HOURS + 1))
    fresh = pet.iso(T0 - timedelta(minutes=1))
    life2, owner2, got = pet.rewards(life, owner, T0, [old, fresh], [fresh], [])
    assert got == [] and life2["g"] == life["g"]
    assert owner2["claimed"]["brain"] == fresh and owner2["stats"]["brain"] == 1 and owner2["stats"]["party"] == 1


def test_presence_and_answers_never_reward_anything_anymore():
    """Décision de l'admin (04.11.2026) : plus de source « soirée » ni « rsvp » ; rewards ne lit plus les événements."""
    assert set(pet.REWARDS) == {"brain", "party", "music"}
    assert "events" not in pet.rewards.__code__.co_varnames[:pet.rewards.__code__.co_argcount]


def test_event_coins_are_added_once_bounded_with_party_mood_and_the_light_necklace():
    life, owner = hatched()
    grants = [{"id": "g1", "event": "Vendredi chez Ludo", "coins": 20},
              {"id": "g2", "event": "Trop", "coins": 500}, {"id": "g3", "event": "Trop peu", "coins": 1},
              {"id": "", "coins": 20}, {"id": "g4", "coins": "illisible"}]
    life, owner, got, done = pet.event_coins(life, owner, h(0), grants)
    assert got == [{"kind": "event_coins", "coins": 20, "event": "Vendredi chez Ludo"}] and done == ["g1"]
    assert owner["loop"]["coins"] == 20 and owner["stats"]["soirees"] == 1
    assert pet.emotion(life, h(1)) == "party" and pet.unlock(owner) == ["boa"]
    life, owner, again, done = pet.event_coins(life, owner, h(1), grants)
    assert again == [] and done == ["g1"] and owner["loop"]["coins"] == 20   # déjà rangé : seulement à marquer


def test_an_egg_still_gets_its_event_coins():
    life, owner = pet.new_pet(T0)
    life, owner, got, _ = pet.event_coins(life, owner, T0, [{"id": "g1", "event": "E", "coins": 5}])
    assert owner["loop"]["coins"] == 5 and got[0]["coins"] == 5 and not life.get("party_until")


def test_gifts_from_friends():
    life, owner = hatched()
    life["g"]["joy"] = 50
    received = [{"id": "g1", "kind": "hug", "from_name": "<b>Léa</b>"}, {"id": "g2", "kind": "bomb", "from_name": "X"}]
    life, owner, applied = pet.gifts(life, owner, h(0), received)
    assert applied == [{"id": "g1", "kind": "hug", "from": "<b>Léa</b>"}]
    assert life["g"]["joy"] == 60 and owner["stats"]["gifts_received"] == 1


# ── Ce qu'on montre ──

def test_friends_only_see_the_creature_never_the_account():
    life, owner = hatched()
    pub = pet.public_life(life)
    assert "memorial" not in pub and "uses" not in pub and "streak" not in pub
    shown = pet.friend_view(pub, h(2))
    assert set(shown) == {"name", "stage", "variant", "emotion", "outfit", "age_hours", "gen", "line"}


def test_view_for_the_owner():
    life, owner = hatched()
    v = pet.view(life, owner, h(0))
    assert v["stage"] == "baby" and v["gauges"] == {"food": 80, "joy": 80, "energy": 90, "care": 90}
    assert v["left"] == pet.DAILY_LIMITS and len(v["outfits"]) == len(pet.OUTFITS)
    assert v["outfits"][0]["unlocked"] and not v["outfits"][-1]["unlocked"]
    assert v["hungry_at"] and v["dies_at"] and v["danger"] is None


def test_messages_are_never_guilt_tripping():
    words = ("faute", "oublié", "abandonn", "honte", "tué", "à cause de toi")
    texts = list(pet.MOOD_LINES.values()) + list(pet.LIMIT_MESSAGES.values())
    assert not [t for t in texts for w in words if w in t.lower()]


def test_a_long_absence_is_computed_quickly():
    life, owner = hatched()
    import time
    start = time.perf_counter()
    pet.advance(life, h(24 * 365), owner)
    pet.view(life, owner, h(24 * 365))
    assert time.perf_counter() - start < 0.5 and life["stage"] == "dead"
