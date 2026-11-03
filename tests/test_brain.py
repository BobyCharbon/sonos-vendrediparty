"""Méninges (app/brain.py) : catalogue identique à la base, normalisation 0–2000, Température, série, forces."""
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import brain

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = (ROOT / "supabase" / "migrations" / "20261102210000_brain.sql").read_text(encoding="utf-8")
ENDLESS = (ROOT / "supabase" / "migrations" / "20261103090000_brain_sans_fin.sql").read_text(encoding="utf-8")
# Dernière définition de private.brain_index (niveaux jusqu'à 999, 03.11).
INDEX_SQL = (ROOT / "supabase" / "migrations" / "20261103150000_brain_niveaux.sql").read_text(encoding="utf-8")
PROD_APPLY = (ROOT / "supabase" / "prod" / "2026-11-02-meninges-apply.sql").read_text(encoding="utf-8")
PROD_ROLLBACK = (ROOT / "supabase" / "prod" / "2026-11-02-meninges-rollback.sql").read_text(encoding="utf-8")
TYPICAL = brain.CATALOG["pareil"].median   # score typique de Pareil ? (indice 1000 au niveau 10)
NOW = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
SHAPE = {"name", "temperature", "domains", "games", "streak", "history", "strengths", "weaknesses", "insight",
         "percentile", "speed_vs_accuracy", "month_progress"}
ANALYSIS_FIELDS = {"domain_analysis", "recent_trend", "advice", "speed_profile", "month_progress_text", "warmup"}


def session(game: str, score: int, days_ago: float = 0, **kw) -> dict:
    return {"game": game, "score": score, "accuracy": kw.get("accuracy", 0.9), "avg_rt_ms": kw.get("rt", 700),
            "level": kw.get("level", brain.LEVEL_REF), "duration_ms": 45000, "played_at": (NOW - timedelta(days=days_ago)).isoformat()}


def test_catalog_has_the_15_games_of_the_spec():
    assert set(brain.CATALOG) == {"pareil", "motif", "autoroute", "grille", "deux_avant", "tresor", "nuee", "aiguillage",
                                  "intrus", "encre", "bascule", "courant", "balance", "gouttes", "syllabes"}
    assert {g.domain for g in brain.CATALOG.values()} == set(brain.DOMAINS)
    assert brain.BRAIN_NAME == "Méninges"


def _catalog_in(sql: str) -> dict:
    rows = re.findall(r"\('(\w+)', '(\w+)', (\d+), (\d+), (\d+), (\d+)\)", sql)
    return {r[0]: (r[1], *map(int, r[2:])) for r in rows}


def test_migration_seeds_the_same_catalog_as_the_server():
    """La dernière migration du catalogue (sans fin, 03.11) porte les valeurs de CATALOG ; la première reste rejouable."""
    in_py = {g.id: (g.domain, g.median, g.spread, g.max_score, g.max_seconds) for g in brain.CATALOG.values()}
    assert _catalog_in(ENDLESS) == in_py
    assert set(_catalog_in(MIGRATION)) == set(in_py)


def test_sql_index_uses_the_same_constants_as_the_server():
    sql = " ".join(INDEX_SQL.split())
    assert f"{brain.SCORE_WEIGHT}::double precision * (ln((least(greatest(coalesce(p_score, 0), 0), g.max_score) + {brain.SCORE_OFFSET})" in sql
    assert f"/ (g.median + {brain.SCORE_OFFSET})::double precision) / (g.spread::double precision / 1000))" in sql
    assert (f"{brain.LEVEL_WEIGHT}::double precision * ((least(greatest(coalesce(p_level, 1), 1), {brain.MAX_LEVEL}) - "
            f"{brain.LEVEL_REF})::double precision / {brain.LEVEL_SPREAD})") in sql


def test_endless_migration_is_additive_and_ready_for_prod():
    low = ENDLESS.lower()
    for word in ("drop table", "drop column", "truncate", "delete from"):
        assert word not in low
    assert "on conflict (id) do update" in low and "create or replace function private.brain_index(p_game text, p_score integer, p_level integer)" in low
    assert "least(p_duration_ms, g.max_seconds * 1000)" in ENDLESS        # partie trop longue : bornée, pas refusée
    assert "p_duration_ms > g.max_seconds" not in ENDLESS
    assert ENDLESS.strip() in PROD_APPLY and "('20261103090000', 'brain_sans_fin')" in PROD_APPLY
    assert PROD_APPLY.rstrip().endswith("commit;")
    assert "version = '20261103090000'" in PROD_ROLLBACK and "private.brain_index(text, integer, integer)" in PROD_ROLLBACK


def test_index_is_1000_at_the_typical_score_and_stays_in_0_2000():
    for gid, g in brain.CATALOG.items():
        assert g.seconds is None and g.max_seconds == 30 * 60
        assert brain.game_index(gid, g.median) == 1000 == brain.game_index(gid, g.median, brain.LEVEL_REF)
        assert brain.game_index(gid, 0) >= 0
        assert brain.game_index(gid, 10 ** 9) <= 2000
        assert brain.game_index(gid, g.median * 2) > brain.game_index(gid, g.median) > brain.game_index(gid, g.median // 2)


def test_index_values_match_the_test_database():
    """Valeurs relevées sur la base de TEST (private.brain_index, migration 20261103090000) : même courbe, même arrondi."""
    assert brain.game_index("pareil", 22500, 10) == 1000
    assert brain.game_index("pareil", 0, 1) == 58
    assert brain.game_index("pareil", 60000, 20) == 1545
    assert brain.game_index("pareil", 250000, 38) == 1919
    assert brain.game_index("grille", 3000, 3) == 360
    assert brain.game_index("pareil", 1000, 36) == 507
    assert brain.game_index("pareil", 2702500, 99) == 1999
    assert brain.game_index("tresor", 12345, 7) == 930
    assert [brain.game_index(*x) for x in [("tresor", 8400, 10), ("syllabes", 1100, 2), ("aiguillage", 14000, 6),
                                          ("pareil", 18050, 9), ("encre", 5350, 5)]] == [847, 150, 732, 891, 418]


def test_index_rewards_the_level_reached_as_well_as_the_score():
    typical = brain.game_index("pareil", TYPICAL, brain.LEVEL_REF)
    assert brain.game_index("pareil", TYPICAL, 36) > typical > brain.game_index("pareil", TYPICAL, 2)
    # Palier 8 (niveaux 36-40) avec un gros score : bel indice, même sous le score des tout meilleurs.
    assert brain.game_index("pareil", 150_000, 36) >= 1850
    # Un joueur qui tape au hasard (petit score, niveau 1-2) reste bas.
    assert brain.game_index("pareil", 1500, 2) < 300
    # Le niveau seul ne suffit pas : partir du palier 8 et perdre tout de suite ne vaut pas une bonne partie.
    assert brain.game_index("pareil", 500, 36) < typical


def test_tiers_are_5_levels_wide():
    assert [brain.tier_of(n) for n in (0, 1, 5, 6, 10, 11, 36, 40, 41, 99)] == [0, 1, 1, 2, 2, 3, 8, 8, 9, 20]


def test_round_half_up_like_the_database():
    assert brain.round_half_up(997.5) == 998 and brain.round_half_up(2.5) == 3 and brain.round_half_up(2.49) == 2


def test_validate_bounds_the_score_and_rejects_impossible_results():
    r = brain.validate("pareil", 10 ** 8, 1, 400, 120, 45000)
    # 45 s de jeu : borné par la durée (anti-triche, QA 03.11), sous le plafond du jeu
    assert r["score"] == brain.score_cap(45000) < brain.CATALOG["pareil"].max_score
    assert r["level"] == 120 and r["domain"] == "vitesse"
    with pytest.raises(brain.BrainError):
        brain.validate("inconnu", 100, 1, 400, 1, 45000)
    with pytest.raises(brain.BrainError):
        brain.validate("pareil", 100, 1.5, 400, 1, 45000)
    with pytest.raises(brain.BrainError):
        brain.validate("pareil", 100, 1, 400, 1, 500)          # partie trop courte


def test_a_perfect_robot_is_never_refused():
    """Robot parfait : ne perd jamais, joue jusqu'à la coupure de 30 min (ou plus), score énorme, niveau 999+."""
    for gid in brain.CATALOG:
        r = brain.validate(gid, 50_000_000, 1, 150, 5000, 4 * 3600 * 1000)
        assert r["score"] == brain.MAX_SCORE and r["level"] == brain.MAX_LEVEL and r["duration_ms"] == 1_800_000
        assert brain.game_index(gid, r["score"], r["level"]) >= 1990


def test_temperature_matches_the_database_example():
    """Pareil 22 500 (1000) et 60 000 au niveau 20 (1545) → vitesse 1273 ; grille 3000 niveau 3 (360) → 816 °M."""
    p = brain.profile([session("pareil", 22500), session("pareil", 60000, level=20), session("grille", 3000, level=3)], now=NOW)
    assert p["domains"]["vitesse"]["index"] == 1273 and p["domains"]["memoire"]["index"] == 360
    assert p["temperature"] == 816


def test_game_index_uses_the_5_best_of_the_last_30_days_of_play():
    old = [session("pareil", 170000, days_ago=45)]              # trop vieux par rapport à la dernière partie
    recent = [session("pareil", s, days_ago=i) for i, s in enumerate([TYPICAL] * 5 + [100] * 3)]
    p = brain.profile(old + recent, now=NOW)
    assert p["games"]["pareil"]["index"] == 1000
    assert p["games"]["pareil"]["best"] == 170000 and p["games"]["pareil"]["plays"] == 9


def test_calcul_has_its_own_index_outside_the_temperature():
    p = brain.profile([session("pareil", TYPICAL), session("balance", 50000)], now=NOW)
    assert p["temperature"] == 1000
    assert p["domains"]["calcul"]["index"] > 1000 and p["domains"]["calcul"]["played"] == 1


def test_profile_has_exactly_the_shape_used_by_the_stats_screens():
    p = brain.profile([session("pareil", TYPICAL, level=12), session("pareil", 3000, level=4), session("encre", 3000)],
                      percentile=42, now=NOW)
    assert set(p) == SHAPE | ANALYSIS_FIELDS
    assert set(p["domains"]) == set(brain.DOMAINS)
    assert all(set(d) == {"index", "played"} for d in p["domains"].values())
    assert set(p["games"]) == set(brain.CATALOG)
    # max_level / max_tier : champs AJOUTÉS (palier le plus haut débloqué), les écrans plus anciens les ignorent.
    assert p["games"]["pareil"] == {"index": brain.round_half_up((brain.raw_index("pareil", TYPICAL, 12)
                                                                  + brain.raw_index("pareil", 3000, 4)) / 2),
                                    "best": TYPICAL, "plays": 2, "last_level": 4, "max_level": 12, "max_tier": 3}
    assert p["games"]["motif"] == {"index": 0, "best": 0, "plays": 0, "last_level": 0, "max_level": 0, "max_tier": 0}
    assert set(p["streak"]) == {"current", "best"} and set(p["speed_vs_accuracy"]) == {"speed", "accuracy"}
    assert p["history"][-1] == {"day": "2026-11-02", "temperature": p["temperature"]}
    assert p["percentile"] == 42 and p["name"] == "Méninges"


def test_empty_profile_invites_to_play():
    p = brain.profile([], now=NOW)
    assert p["temperature"] == 0 and p["history"] == [] and p["month_progress"] is None
    assert p["streak"] == {"current": 0, "best": 0} and "Échauffement" in p["insight"]


def test_strengths_and_weaknesses_compare_to_your_own_average():
    rows = [session(g, sc, days_ago=i) for g, sc in (("pareil", 105000), ("deux_avant", 2100), ("encre", 22500)) for i in range(3)]
    p = brain.profile(rows, now=NOW)
    assert p["strengths"] == ["vitesse"] and p["weaknesses"] == ["memoire"]
    assert "Vitesse" in p["insight"] and "Mémoire" in p["insight"]


def test_streak_counts_consecutive_days_and_survives_until_tomorrow():
    today = date(2026, 11, 2)
    days = {today - timedelta(days=i) for i in (1, 2, 3)} | {today - timedelta(days=i) for i in (10, 11, 12, 13, 14)}
    assert brain.streak(days, today) == {"current": 3, "best": 5}
    assert brain.streak(days, today + timedelta(days=2)) == {"current": 0, "best": 5}


def test_speed_vs_accuracy():
    p = brain.profile([session("pareil", 3000, days_ago=40), session("pareil", 9000, days_ago=1, rt=400, accuracy=1)], now=NOW)
    assert p["speed_vs_accuracy"] == {"speed": 100, "accuracy": 100}


def test_unknown_games_and_bad_dates_are_ignored():
    p = brain.profile([{"game": "pinball", "score": 1}, "x", {**session("pareil", 9000), "played_at": "pas une date"}], now=NOW)
    assert p["games"]["pareil"]["plays"] == 1 and "pinball" not in p["games"]


def test_catalog_route_payload():
    c = brain.catalog()
    assert c["name"] == "Méninges" and len(c["games"]) == 15
    assert [d["id"] for d in c["domains"] if d["in_temperature"]] == list(brain.TEMPERATURE_DOMAINS)
