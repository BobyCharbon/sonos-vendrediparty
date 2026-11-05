"""Barre « petit cadeau » de Zicou (app/pet_bar.py), horloge et hasard simulés : remplissage en 2 h 30, pause la nuit,
pas d'accumulation, plafond de 4 par jour, chances affichées, tirage HMAC rejouable, puis par l'API (/api/pet/act
« bar ») : idempotence (jamais deux fois la même barre), conflit entre deux appareils, pastille."""
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from app import pet, pet_bar as pb, pet_collection, pet_loop as pl, pet_store
from tests.test_pet_api import ALICE, PET_KEY, TOK_A, act, me, setup  # noqa: F401 (fixture)

ZURICH = pet.TZ


def at(day, hour, minute=0):
    """Heure de Zurich, le `day`-ième jour de novembre 2026."""
    return datetime(2026, 11, day, hour, minute, tzinfo=ZURICH).astimezone(timezone.utc)


def hatched(now):
    life, owner = pet.new_pet(now - timedelta(minutes=10))
    pet.advance(life, now, owner)
    return life, owner


def started(now):
    life, owner = hatched(now)
    pb.ensure(owner, now)
    return life, owner


# ── Remplissage ──

def test_it_fills_in_two_and_a_half_hours_and_shows_a_calm_time():
    life, owner = started(at(5, 13, 40))
    v = pb.view(life, owner, at(5, 13, 40))
    assert v["state"] == "filling" and v["progress"] == 0 and v["when"] == "vers 16 h 10"
    half = pb.view(life, owner, at(5, 14, 55))
    assert half["state"] == "filling" and half["progress"] == pytest.approx(0.5)
    assert pb.view(life, owner, at(5, 16, 10))["state"] == "full"
    assert [o["text"] for o in v["odds"]] == ["60 %", "20 %", "17 %", "3 %"]   # chances affichées


def test_night_pauses_the_bar_and_it_never_pushes_to_wake_up():
    life, owner = started(at(5, 22, 0))   # 1 h avant la nuit, il reste 1 h 30 → demain 9 h 30
    assert owner["bar"]["full_at"] == pet.iso(at(6, 9, 30))
    assert pb.view(life, owner, at(6, 3, 0))["state"] == "filling" and pb.view(life, owner, at(6, 3, 0))["night"]
    assert pb.view(life, owner, at(6, 3, 0))["when"] == "vers 9 h 30"
    assert pb.view(life, owner, at(5, 22, 0))["when"] == "demain vers 9 h 30"
    life2, owner2 = started(at(6, 2, 0))   # en pleine nuit : elle commence à 8 h
    assert owner2["bar"]["full_at"] == pet.iso(at(6, 10, 30))
    assert pb.active_between(at(5, 22, 0), at(6, 9, 30)) == timedelta(minutes=150)


def test_full_stays_full_without_piling_up_and_nothing_is_lost():
    life, owner = started(at(5, 9, 0))
    for later in (at(5, 12, 0), at(6, 20, 0), at(9, 3, 0)):   # pleine depuis longtemps, même la nuit
        v = pb.view(life, owner, later)
        assert v["state"] == "full" and v["progress"] == 1
    owner, found, _ = pb.claim(life, owner, at(9, 3, 0), random.Random(1))   # récupérée même la nuit
    assert found["label"]
    with pytest.raises(pet.PetError, match="se remplit encore"):
        pb.claim(life, owner, at(9, 3, 1), random.Random(1))   # une seule récompense, pas trois jours d'arriéré


def test_at_most_four_a_day_then_it_restarts_tomorrow_at_eight():
    life, owner = started(at(5, 8, 0))
    now = at(5, 10, 30)
    for i in range(pb.PER_DAY):
        owner, _, _ = pb.claim(life, owner, now, random.Random(i))
        now = pet.parse(owner["bar"]["full_at"])
    assert owner["bar"]["n"] == 4 and owner["bar"]["full_at"] == pet.iso(at(6, 10, 30))
    v = pb.view(life, owner, at(5, 20, 30))
    assert v["state"] == "rest" and v["today"] == 4 and v["when"] == "demain vers 10 h 30"
    with pytest.raises(pet.PetError, match="demain à 8 h"):
        pb.claim(life, owner, at(5, 22, 0), random.Random(9))
    assert pb.view(life, owner, at(6, 10, 30))["state"] == "full"
    assert pb.claimed_today(owner, at(6, 10, 30)) == 0


def test_rewards_land_where_they_belong():
    life, owner = started(at(5, 8, 0))
    pl.loop_of(owner)
    pet_collection.coll_of(owner)
    seen = Counter()
    for seed in range(400):
        o, found, _ = pb.claim(life, owner, at(5, 12, 0), random.Random(seed))
        seen[found["kind"]] += 1
        if found["kind"] == "coins":
            assert pb.BAR_COINS[0] <= found["amount"] <= pb.BAR_COINS[1]
            assert o["loop"]["coins"] == owner["loop"]["coins"] + found["amount"]
        elif found["kind"] == "snack":
            assert o["loop"]["inv"][found["item"]] == owner["loop"]["inv"].get(found["item"], 0) + 1
        elif found["kind"] == "dust":
            assert o["coll"]["dust"] == owner.get("coll", {}).get("dust", 0) + pb.BAR_DUST
        else:
            assert o["xp"]["total"] == (owner.get("xp") or {}).get("total", 0) + pb.BAR_XP
    assert set(seen) == {"coins", "snack", "xp", "dust"} and 0.5 < seen["coins"] / 400 < 0.7
    assert "bar" in owner and owner["bar"]["n"] == 0   # l'original n'a pas bougé (copies neuves)


def test_a_dead_companion_has_no_bar():
    life, owner = started(at(5, 8, 0))
    life["stage"] = "dead"
    assert pb.view(life, owner, at(5, 12, 0))["state"] == "off"
    with pytest.raises(pet.PetError, match="envolé"):
        pb.claim(life, owner, at(5, 12, 0), random.Random(1))


def test_the_draw_is_hmac_seeded_per_account_day_and_claim_number():
    store = pet_store.PetStore(None, None, secret=PET_KEY)
    s1 = store.seed("alice", "2026-11-05", "bar0")
    assert s1 == store.seed("alice", "2026-11-05", "bar0")
    assert len({s1, store.seed("alice", "2026-11-05", "bar1"), store.seed("bob", "2026-11-05", "bar0"),
                store.seed("alice", "2026-11-06", "bar0")}) == 4
    other = pet_store.PetStore(None, None, secret="une-autre-cle-de-serveur-0123456789abcdef")
    assert other.seed("alice", "2026-11-05", "bar0") != s1   # imprévisible sans la clé du serveur


# ── Par l'API ──

def test_claim_through_the_api_once_per_fill(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    bar = me(c)["pet"]["bar"]
    assert bar["state"] == "filling" and bar["odds"] and base.pets[ALICE]["owner"]["bar"]["full_at"]
    r = act(c, "bar")
    assert r.status_code == 400 and "se remplit encore" in r.json()["detail"]
    clock.go(hours=2, minutes=30)
    status = c.post("/api/pet/status", json={"token": TOK_A}).json()["bar"]
    assert status["state"] == "full" and "odds" not in status   # pastille : l'anneau
    r = act(c, "bar")
    assert r.status_code == 200, r.text
    found = r.json()["effect"]["found"]
    assert found["kind"] in ("coins", "snack", "xp", "dust") and "roll" in found
    assert r.json()["pet"]["bar"]["state"] == "filling" and r.json()["pet"]["bar"]["today"] == 1
    assert (ALICE, {"kind": "bar", "detail": {"kind": found["kind"], "roll": found["roll"]}}) in base.journal
    again = act(c, "bar")   # deuxième toucher, autre appareil : jamais deux fois
    assert again.status_code == 400 and "se remplit encore" in again.json()["detail"]


def test_a_claim_racing_another_device_is_replayed_with_the_same_draw(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(hours=3)
    me(c)
    base.race = 1   # un autre appareil enregistre juste avant : relu, rejoué une fois, même jet (HMAC)
    r = act(c, "bar")
    assert r.status_code == 200, r.text
    assert base.pets[ALICE]["owner"]["bar"]["n"] == 1
