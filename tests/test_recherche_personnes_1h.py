"""Recherches de personnes d'un groupe (private.group_search_log) : empreinte seulement, gardée 1 h (contrôle Apple / RGPD
du 26.11, migration 20261126100000 ; essai réel sur la base de TEST : recherche, empreintes, purge, cron, retour arrière)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/20261126100000_recherche_personnes_1h.sql").read_text(encoding="utf-8")
APPLY = (ROOT / "supabase/prod/2026-11-26-recherche-personnes-1h-apply.sql").read_text(encoding="utf-8")
ROLLBACK = (ROOT / "supabase/prod/2026-11-26-recherche-personnes-1h-rollback.sql").read_text(encoding="utf-8")


def test_only_a_hash_is_kept_one_hour_and_purged_every_hour():
    assert "key := encode(sha256(convert_to(coalesce('tel:' || number, qq), 'UTF8')), 'hex');" in MIGRATION
    assert "delete from private.group_search_log l where l.at < now() - interval '1 hour';" in MIGRATION
    assert "interval '1 day'" not in MIGRATION
    assert "cron.schedule('group-search-log-purge'" in MIGRATION


def test_prod_files_apply_the_migration_and_roll_back():
    assert MIGRATION in APPLY and APPLY.count("begin;") == 1 and "commit;" in APPLY
    assert "values ('20261126100000'" in APPLY
    assert "cron.unschedule('group-search-log-purge')" in ROLLBACK and "interval '1 day'" in ROLLBACK
    assert "where version = '20261126100000'" in ROLLBACK
