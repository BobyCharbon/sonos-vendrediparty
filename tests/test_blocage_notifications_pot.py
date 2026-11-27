"""Fichiers du lot 14 (migration 20261127150000) : le fichier prod reprend la migration à l'identique, le retour arrière la
retire sans recopier aucun texte de message ni de notification, la checklist l'ordonne ; le serveur et l'iPhone
connaissent les deux nouveaux types de signalement."""
import pathlib

from app.moderation_api import KINDS

ROOT = pathlib.Path(__file__).parents[1]
MIG = (ROOT / 'supabase/migrations/20261127150000_blocage_notifications_pot.sql').read_text()
APPLY = (ROOT / 'supabase/prod/2026-11-27-blocage-notifications-pot-apply.sql').read_text()
ROLLBACK = (ROOT / 'supabase/prod/2026-11-27-blocage-notifications-pot-rollback.sql').read_text()


def test_the_prod_file_is_the_migration_and_records_it():
    assert MIG in APPLY
    assert APPLY.lstrip().startswith('--') and 'begin;' in APPLY and APPLY.rstrip().endswith('commit;')
    assert "values ('20261127150000', 'blocage_notifications_pot')" in APPLY


def test_every_anchor_is_checked_before_any_change_and_cron_is_covered():
    assert MIG.index('defs := defs || def;') < MIG.index('execute defs[i];')
    assert MIG.index("ancre pet_word introuvable") < MIG.index('execute defs[i];')
    assert 'ev.created_by' in MIG and 'new.user_id' in MIG  # jamais auth.uid() pour l'événement


def test_the_rollback_removes_it_without_any_notification_text():
    assert "delete from supabase_migrations.schema_migrations where version = '20261127150000'" in ROLLBACK
    assert 'queue_notification' not in ROLLBACK and 'insert into public.notifications' not in ROLLBACK


def test_the_checklist_lists_it_fourteenth():
    text = (ROOT / 'docs/app-store/checklist-envoi.md').read_text()
    assert text.index('13. `2026-11-27-blocage-pot-commun`') < text.index('14. `2026-11-27-blocage-notifications-pot`')


def test_server_and_iphone_know_the_new_report_kinds():
    assert {'tc_group', 'tc_member'} <= set(KINDS)
    swift = (ROOT / 'ios/Party/Settings/Moderation/ModerationModels.swift').read_text()
    assert 'tcGroup = "tc_group"' in swift and 'tcMember = "tc_member"' in swift
    pot = (ROOT / 'ios/Party/Tricount/TricountGroupView.swift').read_text()
    assert 'Signaler le nom du pot' in pot and 'Signaler ce prénom' in pot
