"""Méninges : niveaux jusqu'à 999 (les jeux sans fin montent à 250+). Même plafond dans le moteur (core.js), le serveur
(app/brain.py) et la base (migration 20261103150000_brain_niveaux.sql, fichier prod et retour arrière)."""
import re
from pathlib import Path

from app import brain

ROOT = Path(__file__).resolve().parent.parent
CORE = (ROOT / "app" / "static" / "brain" / "core.js").read_text(encoding="utf-8")
NIVEAUX = (ROOT / "supabase" / "migrations" / "20261103150000_brain_niveaux.sql").read_text(encoding="utf-8")
PROD_APPLY = (ROOT / "supabase" / "prod" / "2026-11-02-meninges-apply.sql").read_text(encoding="utf-8")
PROD_ROLLBACK = (ROOT / "supabase" / "prod" / "2026-11-02-meninges-rollback.sql").read_text(encoding="utf-8")


def flat(sql: str) -> str:
    return " ".join(sql.split())


def test_server_keeps_levels_up_to_999():
    assert brain.MAX_LEVEL == 999
    assert brain.validate("encre", 50_000, 0.9, 600, 296, 20 * 60_000)["level"] == 296
    assert brain.validate("encre", 50_000, 0.9, 600, 5000, 20 * 60_000)["level"] == 999
    assert brain.tier_of(999) == 200


def test_engine_uses_the_same_level_cap():
    assert re.search(r"\bMAX_LEVEL = (\d+)", CORE).group(1) == str(brain.MAX_LEVEL)


def test_database_accepts_and_bounds_levels_like_the_server():
    sql = flat(NIVEAUX)
    # Colonne : 1 à 999 (l'ancienne contrainte bornait à 99).
    assert f"check (level between 1 and {brain.MAX_LEVEL})" in sql
    # brain_record : même plafond que validate.
    assert f"lvl := least(greatest(coalesce(p_level, 1), 1), {brain.MAX_LEVEL}," in sql
    # Indice : même formule que raw_index, niveau borné au même plafond.
    assert (f"{brain.LEVEL_WEIGHT}::double precision * ((least(greatest(coalesce(p_level, 1), 1), {brain.MAX_LEVEL}) - "
            f"{brain.LEVEL_REF})::double precision / {brain.LEVEL_SPREAD})") in sql
    assert f"g.max_score, dur * {brain.SCORE_PER_SECOND_CAP // 1000} + {brain.SCORE_BONUS_CAP})" in sql


def test_levels_migration_is_additive_replayable_and_in_the_prod_files():
    low = NIVEAUX.lower()
    for word in ("drop table", "drop column", "truncate", "delete from"):
        assert word not in low
    assert "drop constraint if exists" in low and "create or replace function public.brain_record(" in low
    assert NIVEAUX.strip() in PROD_APPLY
    assert "('20261103150000', 'brain_niveaux')" in PROD_APPLY and PROD_APPLY.rstrip().endswith("commit;")
    assert "version = '20261103150000'" in PROD_ROLLBACK
