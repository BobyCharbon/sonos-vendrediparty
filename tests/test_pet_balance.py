"""Compagnon : équilibre (playtest « Marc », 4 novembre 2026), moteur + boucle du jour, horloge simulée sur 30 jours.

  · le paresseux (un toucher par jour sur le coffre) ne garde pas de série et ne gagne presque rien ;
  · l'honnête (un passage le soir : 2 repas, 1 partie, 2 câlins, 1 toilette) obtient un adulte classique ou étoile,
    jamais rebelle, et son compagnon n'est pas à zéro quand il passe ;
  · jouer plus ne fait jamais baisser le résultat ; le talent au jeu des notes compte un peu (bonus plafonné).
Tableau complet avant/après : rapport de l'agent (simulation des 3 profils)."""
import random
from datetime import datetime, timedelta, timezone

import pytest

from app import pet, pet_loop

T0 = datetime(2026, 11, 4, 7, 30, tzinfo=timezone.utc)   # mercredi 8 h 30 à Zurich


def _try(life, owner, action, now, **kw):
    try:
        return pet.act(life, owner, action, now, **kw)[:2]
    except pet.PetError:
        return life, owner


def _visit(life, owner, now, day):
    pet.advance(life, now, owner)
    return pet_loop.visit(life, owner, now, random.Random(day), src="tab", seed="x")[:2]


def honest(days=30, score=57, hour=11.7):
    """Un passage par jour à 19 h 10 : coffre, 2 repas, 1 partie, 2 câlins, 1 toilette."""
    life, owner = pet.new_pet(T0)
    lows, variants = [], []
    for day in range(days):
        now = T0 + timedelta(days=day, hours=hour)
        life, owner = _visit(life, owner, now, day)
        if life["stage"] not in ("egg", "dead") and day >= 2:
            lows.append(min(life["g"].values()))
        try:
            life, owner, _ = pet_loop.act(life, owner, "chest", now, random.Random(day))
        except pet.PetError:
            pass
        for action, kw in (("feed", {}), ("feed", {}), ("play", {"score": score}), ("cuddle", {}), ("cuddle", {}),
                           ("heal", {})):
            life, owner = _try(life, owner, action, now, **kw)
        if life["stage"] == "adult":
            variants.append(life["variant"])
    return life, owner, lows, variants


def test_the_honest_player_gets_a_classic_or_star_adult_in_good_shape():
    life, owner, lows, variants = honest()
    assert life["stage"] == "adult" and set(variants) <= {"classic", "star"}
    assert min(lows) > 0 and sum(lows) / len(lows) > 25   # jamais à zéro quand il passe
    assert pet.streak_now(owner, T0 + timedelta(days=29, hours=12)) >= 28


def test_the_honest_player_with_no_talent_is_still_not_wild():
    life, *_ = honest(score=0)
    assert life["stage"] == "adult" and life["variant"] in ("classic", "star")


def test_the_lazy_player_keeps_no_streak_and_almost_no_coins():
    life, owner = pet.new_pet(T0)
    coins = []
    for day in range(30):
        now = T0 + timedelta(days=day, hours=3.5)
        life, owner = _visit(life, owner, now, day)
        try:
            life, owner, _ = pet_loop.act(life, owner, "chest", now, random.Random(day))
        except pet.PetError:
            pass
        coins.append(owner["loop"]["coins"])
    assert life["stage"] == "dead" and owner["streak"]["count"] == 0 and owner["streak"]["best"] == 0
    assert coins[-1] == coins[7] and coins[-1] < 200   # plus rien une fois envolé ; avant : 1034 pièces


def _adult_quality(plays: int, score: int, visits=(11.0,)) -> float:
    life, owner = pet.new_pet(T0)
    last = 0.0
    for day in range(5):
        for h in visits:
            now = T0 + timedelta(days=day, hours=h)
            pet.advance(life, now, owner)
            if life["stage"] in ("adult", "dead"):
                return last
            life["asleep"] = False
            for action in ["feed", "feed"] + ["play"] * plays + ["cuddle", "cuddle", "heal"]:
                life, owner = _try(life, owner, action, now, score=score)
            if life["stage"] == "teen":
                last = pet.quality(life)
    return last


@pytest.mark.parametrize("visits", [(11.0,), (1.0, 11.0), (1.0, 6.0, 11.0)])
def test_playing_more_never_lowers_the_result(visits):
    results = [_adult_quality(plays, 80, visits) for plays in range(pet.DAILY_LIMITS["play"] + 1)]
    assert all(b >= a - 1e-9 for a, b in zip(results, results[1:])), results


def test_talent_counts_a_little_and_is_capped():
    life, _ = pet.new_pet(T0)
    life.update(care_sum=60.0 * 48, care_h=48.0, cares={})
    base = pet.quality(life)
    assert pet.quality(dict(life, best_score=100)) - base == pytest.approx(pet.TALENT_BONUS)
    assert pet.quality(dict(life, best_score=999)) - base == pytest.approx(pet.TALENT_BONUS)   # plafonné
    assert _adult_quality(1, 100) > _adult_quality(1, 0)   # mieux jouer : un peu mieux


def test_a_tired_companion_wakes_up_when_you_open_the_app_but_not_after_being_tucked_in():
    life, owner = pet.new_pet(T0)
    now = T0 + timedelta(hours=2)
    pet.advance(life, now, owner)
    life.update(asleep=True)
    life["g"]["energy"] = 70.0
    woke, owner2, events = pet_loop.visit(life, owner, now, random.Random(1), src="tab")
    assert not woke["asleep"] and {"kind": "woke_up"} in events
    owner["loop"] = dict(pet_loop.new_loop(), tucked_at=pet.iso(now))   # bordé pour la nuit : on le laisse dormir
    still, *_ = pet_loop.visit(life, owner, now, random.Random(1), src="tab")
    assert still["asleep"]
    low = dict(life, g=dict(life["g"], energy=20.0))
    assert pet_loop.visit(low, pet.new_owner(), now, random.Random(1), src="tab")[0]["asleep"]   # trop fatigué
