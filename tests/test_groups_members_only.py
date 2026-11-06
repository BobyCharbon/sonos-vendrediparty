"""Groupes réservés à leurs membres (question de l'admin, 06.11.2026) : la migration est additive et rejouable, le fichier
de prod la reprend mot pour mot (jamais appliqué sans « Ok prod »), et les écrans ne proposent que ses groupes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261106090000_groupes_membres_seulement.sql"


def test_migration_is_additive_replayable_and_keeps_admins():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert " table " not in sql.replace("on public.", "")  # aucune table créée, modifiée ni retirée
    assert sql.count("create or replace function") == 3 and sql.count("drop trigger if exists") == 2
    assert "public.is_admin()" in sql  # events.manage_all : tous les groupes, comme avant
    assert "member_group_members m where m.group_id = g and m.user_id" in sql
    assert "old.visibility is distinct from new.visibility" in sql  # seulement un changement de visibilité est vérifié


def test_prod_files_are_ready_and_identical():
    prod = ROOT / "supabase/prod"
    apply = (prod / "2026-11-06-groupes-membres-seulement-apply.sql").read_text(encoding="utf-8")
    rollback = (prod / "2026-11-06-groupes-membres-seulement-rollback.sql").read_text(encoding="utf-8")
    assert MIGRATION.read_text(encoding="utf-8").strip() in apply and apply.count("begin;") == 1 and "commit;" in apply
    assert "values ('20261106090000'" in apply and "« Ok prod »" in apply
    assert "where version = '20261106090000'" in rollback


def test_screens_offer_only_the_groups_one_is_in():
    picker = (ROOT / "web/events/src/components/AudiencePicker.tsx").read_text(encoding="utf-8")
    assert "allGroups || g.member_group_members.some((m) => m.user_id === meId)" in picker
    assert "g.created_by === meId" not in picker  # créateur mais pas membre : plus proposé
    sheet = (ROOT / "web/events/src/components/InviteSheet.tsx").read_text(encoding="utf-8")
    assert "g.created_by === me.id" not in sheet
    step = (ROOT / "web/events/src/components/VisibilityChoice.tsx").read_text(encoding="utf-8")
    assert "(k !== 'vip' || vipOk)" in step
