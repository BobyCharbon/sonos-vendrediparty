"""Méninges (app/brain.py) : catalogue identique à la base, normalisation 0–2000, Température, série, forces."""
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import brain

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = (ROOT / "supabase" / "migrations" / "20261102210000_brain.sql").read_text(encoding="utf-8")
NOW = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)


def session(game: str, score: int, days_ago: float = 0, **kw) -> dict:
    return {"game": game, "score": score, "accuracy": kw.get("accuracy", 0.9), "avg_rt_ms": kw.get("rt", 700),
            "level": kw.get("level", 3), "duration_ms": 45000, "played_at": (NOW - timedelta(days=days_ago)).isoformat()}


def test_catalog_has_the_15_games_of_the_spec():
    assert set(brain.CATALOG) == {"pareil", "motif", "autoroute", "grille", "deux_avant", "tresor", "nuee", "aiguillage",
                                  "intrus", "encre", "bascule", "courant", "balance", "gouttes", "syllabes"}
    assert {g.domain for g in brain.CATALOG.values()} == set(brain.DOMAINS)
    assert brain.BRAIN_NAME == "Méninges"


def test_migration_seeds_the_same_catalog_as_the_server():
    rows = re.findall(r"\('(\w+)', '(\w+)', (\d+), (\d+), (\d+), (\d+)\)", MIGRATION)
    in_sql = {r[0]: (r[1], *map(int, r[2:])) for r in rows}
    in_py = {g.id: (g.domain, g.median, g.spread, g.max_score, g.max_seconds) for g in brain.CATALOG.values()}
    assert in_sql == in_py


def test_index_is_1000_at_the_typical_score_and_stays_in_0_2000():
    for gid, g in brain.CATALOG.items():
        assert brain.game_index(gid, g.median) == 1000
        assert brain.game_index(gid, 0) >= 0
        assert brain.game_index(gid, 10 ** 9) <= 2000
        assert brain.game_index(gid, g.median * 2) > brain.game_index(gid, g.median) > brain.game_index(gid, g.median // 2)


def test_index_values_match_the_test_database():
    """Valeurs relevées sur la base de TEST (brain_record) : même courbe, même arrondi."""
    assert brain.game_index("pareil", 9000) == 1000
    assert brain.game_index("pareil", 999999) == 2000
    assert brain.game_index("grille", 3000) == 495


def test_round_half_up_like_the_database():
    assert brain.round_half_up(997.5) == 998 and brain.round_half_up(2.5) == 3 and brain.round_half_up(2.49) == 2


def test_validate_bounds_the_score_and_rejects_impossible_results():
    r = brain.validate("pareil", 10 ** 6, 1, 400, 120, 45000)
    assert r["score"] == brain.CATALOG["pareil"].max_score and r["level"] == 99 and r["domain"] == "vitesse"
    with pytest.raises(brain.BrainError):
        brain.validate("inconnu", 100, 1, 400, 1, 45000)
    with pytest.raises(brain.BrainError):
        brain.validate("pareil", 100, 1.5, 400, 1, 45000)
    with pytest.raises(brain.BrainError):
        brain.validate("pareil", 100, 1, 400, 1, 500)          # partie trop courte
    with pytest.raises(brain.BrainError):
        brain.validate("pareil", 100, 1, 400, 1, 3_000_000)    # bien plus long que le chrono


def test_temperature_matches_the_database_example():
    """Base de TEST : pareil 9000 puis 70000 (vitesse 1500), grille 3000 (mémoire 495) → 998 °M."""
    p = brain.profile([session("pareil", 9000), session("pareil", 999999), session("grille", 3000)], now=NOW)
    assert p["temperature"] == 998
    assert p["domains"]["vitesse"]["index"] == 1500 and p["domains"]["memoire"]["index"] == 495


def test_game_index_uses_the_5_best_of_the_last_30_days_of_play():
    old = [session("pareil", 70000, days_ago=45)]               # trop vieux par rapport à la dernière partie
    recent = [session("pareil", s, days_ago=i) for i, s in enumerate([9000] * 5 + [100] * 3)]
    p = brain.profile(old + recent, now=NOW)
    assert p["games"]["pareil"]["index"] == 1000
    assert p["games"]["pareil"]["best"] == 70000 and p["games"]["pareil"]["plays"] == 9


def test_calcul_has_its_own_index_outside_the_temperature():
    p = brain.profile([session("pareil", 9000), session("balance", 20000)], now=NOW)
    assert p["temperature"] == 1000
    assert p["domains"]["calcul"]["index"] > 1000 and p["domains"]["calcul"]["played"] == 1


def test_profile_has_exactly_the_shape_used_by_the_stats_screens():
    p = brain.profile([session("pareil", 9000, level=4), session("encre", 3000)], percentile=42, now=NOW)
    assert set(p) == {"name", "temperature", "domains", "games", "streak", "history", "strengths", "weaknesses",
                      "insight", "percentile", "speed_vs_accuracy", "month_progress"}
    assert set(p["domains"]) == set(brain.DOMAINS)
    assert all(set(d) == {"index", "played"} for d in p["domains"].values())
    assert set(p["games"]) == set(brain.CATALOG)
    assert p["games"]["pareil"] == {"index": 1000, "best": 9000, "plays": 1, "last_level": 4}
    assert p["games"]["motif"] == {"index": 0, "best": 0, "plays": 0, "last_level": 0}
    assert set(p["streak"]) == {"current", "best"} and set(p["speed_vs_accuracy"]) == {"speed", "accuracy"}
    assert p["history"][-1] == {"day": "2026-11-02", "temperature": p["temperature"]}
    assert p["percentile"] == 42 and p["name"] == "Méninges"


def test_empty_profile_invites_to_play():
    p = brain.profile([], now=NOW)
    assert p["temperature"] == 0 and p["history"] == [] and p["month_progress"] is None
    assert p["streak"] == {"current": 0, "best": 0} and "Échauffement" in p["insight"]


def test_strengths_and_weaknesses_compare_to_your_own_average():
    p = brain.profile([session("pareil", 14000), session("deux_avant", 2000), session("encre", 9000)], now=NOW)
    assert p["strengths"] == ["vitesse"] and p["weaknesses"] == ["memoire"]
    assert "Vitesse" in p["insight"] and "Mémoire" in p["insight"]


def test_streak_counts_consecutive_days_and_survives_until_tomorrow():
    today = date(2026, 11, 2)
    days = {today - timedelta(days=i) for i in (1, 2, 3)} | {today - timedelta(days=i) for i in (10, 11, 12, 13, 14)}
    assert brain.streak(days, today) == {"current": 3, "best": 5}
    assert brain.streak(days, today + timedelta(days=2)) == {"current": 0, "best": 5}


def test_month_progress_and_speed_vs_accuracy():
    p = brain.profile([session("pareil", 3000, days_ago=40), session("pareil", 9000, days_ago=1, rt=400, accuracy=1)], now=NOW)
    assert p["month_progress"] == p["temperature"] - brain.game_index("pareil", 3000) > 0
    assert p["speed_vs_accuracy"] == {"speed": 100, "accuracy": 100}


def test_unknown_games_and_bad_dates_are_ignored():
    p = brain.profile([{"game": "pinball", "score": 1}, "x", {**session("pareil", 9000), "played_at": "pas une date"}], now=NOW)
    assert p["games"]["pareil"]["plays"] == 1 and "pinball" not in p["games"]


def test_catalog_route_payload():
    c = brain.catalog()
    assert c["name"] == "Méninges" and len(c["games"]) == 15
    assert [d["id"] for d in c["domains"] if d["in_temperature"]] == list(brain.TEMPERATURE_DOMAINS)
