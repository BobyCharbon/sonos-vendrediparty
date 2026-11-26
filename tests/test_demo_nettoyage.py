"""Nettoyage de la démo de la revue Apple (26.11, fichiers prod préparés, jamais appliqués sans « Ok prod ») : bar de la
Soirée démo retiré, Apple-test hors du vrai pot du Paintball SANS changer sa réponse, cloche sans « Événement annulé ».
Essai réel sur la base de TEST (identifiants de TEST) : retour arrière puis nettoyage, tout ou rien."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLY = (ROOT / "supabase/prod/2026-11-26-demo-nettoyage-apply.sql").read_text(encoding="utf-8")
ROLLBACK = (ROOT / "supabase/prod/2026-11-26-demo-nettoyage-rollback.sql").read_text(encoding="utf-8")


def test_apply_removes_the_bar_the_pot_membership_and_the_bell_only():
    assert APPLY.count("begin;") == 1 and APPLY.strip().endswith("commit;")
    assert "delete from public.event_bars where event_id = '82ea0ad6-ac8b-43c2-b4ee-548afd21b243';" in APPLY
    assert "update public.tc_members set left_at = now()" in APPLY
    assert "rsvps" in APPLY and "update public.rsvps" not in APPLY  # sa réponse (Absent) ne change pas
    assert "delete from public.notifications where user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd'" in APPLY
    assert "values ('20261126110000', 'demo_nettoyage')" in APPLY
    assert "cover" not in APPLY.lower()  # couverture de Verknipt : l'organisateur la change lui-même


def test_rollback_puts_back_every_row_read_in_prod():
    for table in ("event_bars", "event_bar_items", "event_bar_log", "notifications"):
        assert f"insert into public.{table}" in ROLLBACK, table
    assert "overriding system value" in ROLLBACK and "left_at = null" in ROLLBACK
    assert "where version = '20261126110000'" in ROLLBACK
