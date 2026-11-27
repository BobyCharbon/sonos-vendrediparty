"""Fichiers du blocage dans le Pot commun (migration 20261127140000) : le fichier prod reprend la migration à l'identique,
le retour arrière la retire sans recopier aucun texte de message ni de notification, la checklist l'ordonne."""
import pathlib

ROOT = pathlib.Path(__file__).parents[1]
MIG = (ROOT / 'supabase/migrations/20261127140000_blocage_pot_commun.sql').read_text()
APPLY = (ROOT / 'supabase/prod/2026-11-27-blocage-pot-commun-apply.sql').read_text()
ROLLBACK = (ROOT / 'supabase/prod/2026-11-27-blocage-pot-commun-rollback.sql').read_text()


def test_the_prod_file_is_the_migration_and_records_it():
    assert MIG in APPLY
    assert APPLY.lstrip().startswith('--') and 'begin;' in APPLY and APPLY.rstrip().endswith('commit;')
    assert "values ('20261127140000', 'blocage_pot_commun')" in APPLY


def test_every_anchor_is_checked_before_any_change():
    assert "ancre introuvable, rien n''est modifié" in MIG and "appliquer d''abord 20261126140000" in MIG
    for fn in ('tc_group_json', 'tc_join_info', 'tc_save_expense', 'tc_event_sync', 'flush_rsvp_digests'):
        assert fn in MIG
    assert MIG.index('defs := defs || def;') < MIG.index('execute defs[i];')


def test_the_rollback_removes_it_without_any_notification_text():
    assert "delete from supabase_migrations.schema_migrations where version = '20261127140000'" in ROLLBACK
    assert 'queue_notification' not in ROLLBACK and 'insert into public.notifications' not in ROLLBACK


def test_the_checklist_lists_it_after_the_pot_files():
    text = (ROOT / 'docs/app-store/checklist-envoi.md').read_text()
    assert text.index('2026-11-26-pot-filtre-paiement-purge') < text.index('13. `2026-11-27-blocage-pot-commun`')
