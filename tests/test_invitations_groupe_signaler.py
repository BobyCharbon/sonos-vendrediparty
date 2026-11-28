"""Lot 21 (contrôle Apple 1.2) : invitations de groupe reçues — blocage filtré par la base, « Signaler » sur l'écran
(web et iPhone) avec repli par e-mail, fichiers prod (apply = corps de la migration, retour arrière = même texte retiré,
sans texte de message ni de notification) et 19e fichier de la checklist. Test réel : supabase_live/test_invitations_groupe_signaler_live.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = (ROOT / 'supabase/migrations/20261128110000_invitations_groupe_signaler.sql').read_text()
APPLY = (ROOT / 'supabase/prod/2026-11-28-invitations-groupe-signaler-apply.sql').read_text()
ROLLBACK = (ROOT / 'supabase/prod/2026-11-28-invitations-groupe-signaler-rollback.sql').read_text()


def test_the_migration_patches_by_anchor_and_is_replayable():
    assert 'blocked_either(auth.uid(), i.invited_by)' in MIG and 'blocked_either(auth.uid(), g.created_by)' in MIG
    assert "i.status = 'pending'" in MIG and 'group_report_snapshot' in MIG
    assert MIG.count("position('(20261128110000)' in def) = 0") == 2  # marqueur : rejoué sans effet
    assert MIG.count('ancre introuvable ou en double') == 2           # ancre manquante : refus, rien de modifié
    assert 'create or replace function' not in MIG.lower()           # jamais réécrite en entier


def test_prod_files_match_the_migration_and_carry_no_message_text():
    assert MIG[MIG.index('do $patch$'):] in APPLY
    assert APPLY.strip().startswith('--') and 'begin;' in APPLY and APPLY.rstrip().endswith('commit;')
    assert "values ('20261128110000', 'invitations_groupe_signaler')" in APPLY
    # Le retour arrière retire exactement ce que la migration ajoute.
    added = re.findall(r"added\d constant text := \$a\$(.*?)\$a\$;", ROLLBACK, re.S)
    assert len(added) == 2 and all(a.strip() in MIG for a in added)
    assert "delete from supabase_migrations.schema_migrations where version = '20261128110000'" in ROLLBACK
    for text in (APPLY, ROLLBACK):
        assert 'public.notifications' not in text and 'group_messages' not in text


def test_the_checklist_lists_the_19th_file_after_the_6th():
    checklist = (ROOT / 'docs/app-store/checklist-envoi.md').read_text()
    assert '19. `2026-11-28-invitations-groupe-signaler` (20261128110000)' in checklist


def test_received_invitations_offer_report_on_web_and_iphone_with_a_mail_fallback():
    web = (ROOT / 'web/events/src/app/groups.tsx').read_text()
    assert "testID=\"group-invitation-report\"" in web and "kind: 'group', id: i.group_id" in web
    assert '🚩 Signaler · Traité sous 24 h · {SUPPORT_EMAIL}' in web and 'fallback={' in web and 'InviteReportLine' in web
    assert '{error && fallback ? fallback : null}' in (ROOT / 'web/events/src/components/ReportSheet.tsx').read_text()
    ios = (ROOT / 'ios/Party/Chats/Groups/GroupsListView.swift').read_text()
    assert 'ReportTarget(kind: .group, id: inv.groupId' in ios and '"group-invitation-report"' in ios
    assert '🚩 Signaler · Traité sous 24 h · \\(TermsView.supportEmail)' in ios and 'fallbackMail: Self.reportMail' in ios
    sheet = (ROOT / 'ios/Party/Settings/Moderation/ModerationSheets.swift').read_text()
    assert 'var fallbackMail: URL? = nil' in sheet and 'report-mail-fallback' in sheet
