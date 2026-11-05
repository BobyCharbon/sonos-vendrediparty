"""Widgets Zicou de l'app iOS (ios/Party/Pet) : leur chronologie refait vivre Zicou sur l'iPhone avec une copie des
rythmes de app/pet.py, et lit des champs précis de la réponse /api/pet/me. Ces tests cassent si le serveur change
l'un ou l'autre sans l'app."""
import re
from datetime import datetime, timezone
from pathlib import Path

from app import pet, pet_loop

ROOT = Path(__file__).resolve().parents[1]
FORECAST = (ROOT / "ios/Party/Pet/PetForecast.swift").read_text(encoding="utf-8")
STATE = (ROOT / "ios/Party/Pet/PetWidgetState.swift").read_text(encoding="utf-8")
BRIDGE = (ROOT / "ios/Party/Pet/PetWidgetBridge.swift").read_text(encoding="utf-8")
HATCH = (ROOT / "ios/Party/Pet/HatchActivities.swift").read_text(encoding="utf-8")


def swift_number(name: str, text: str = FORECAST) -> float:
    m = re.search(rf"static let {name}(?:: \w+)? = ([0-9.]+)", text)
    assert m, f"{name} introuvable dans PetForecast.swift"
    return float(m.group(1))


def test_rates_match_the_server():
    assert swift_number("food") == pet.FOOD_RATE
    assert swift_number("foodSleepFactor") == pet.FOOD_SLEEP_FACTOR
    assert swift_number("joy") == pet.JOY_RATE
    assert swift_number("joySickFactor") == pet.JOY_SICK_FACTOR
    assert swift_number("joyStarvingFactor") == pet.JOY_STARVING_FACTOR
    assert swift_number("energy") == pet.ENERGY_RATE
    assert swift_number("energyRegen") == pet.ENERGY_REGEN
    assert swift_number("care") == pet.CARE_RATE
    assert swift_number("low") == pet.LOW
    assert swift_number("partyLevel") == pet.PARTY_LEVEL
    assert swift_number("stepHours") == pet.STEP_HOURS
    assert swift_number("full") == pet.FULL
    factors = dict(re.findall(r'"(\w+)": ([0-9.]+)', re.search(r"stageFactor.*", FORECAST).group(0)))
    assert {k: float(v) for k, v in factors.items()} == pet.STAGE_FACTOR


def test_egg_duration_and_name_rules_match_the_server():
    assert swift_number("eggDuration", HATCH) == pet.EGG_SECONDS
    assert swift_number("nameMax", STATE) == pet.NAME_MAX
    assert f'"{pet.DEFAULT_NAME}"' in STATE
    for emotion in pet.MOOD_LINES:
        assert f'"{emotion}"' in STATE, f"humeur {emotion} inconnue des widgets"


def test_the_fields_read_by_the_widgets_are_in_the_answer():
    now = datetime(2026, 11, 4, 15, tzinfo=timezone.utc)
    life, owner = pet.new_pet(now)
    shown = pet.view(life, owner, now) | {"daily": pet_loop.view(life, owner, now)}
    for field in ("name", "stage", "variant", "emotion", "asleep", "sick", "gauges", "streak", "next_stage_in", "dies_at"):
        assert field in shown and f"p.{field}" in BRIDGE, field
    assert set(shown["gauges"]) == {"food", "joy", "energy", "care"}
    assert shown["daily"]["chest"]["state"] in ("ready", "opened")
    assert "count" in shown["daily"]["streak"]
