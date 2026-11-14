"""« Nouveau compte » et suppression du compte (recette des nouveaux comptes, 14.11.2026) : sur la base de TEST, les
notifications « Nouveau compte » (surnom, prénom et nom) restaient chez les valideurs après la suppression du compte
(18 comptes supprimés sur 20 encore nommés). La migration les efface avec le compte ; additive, rejouable, prête pour la prod
(jamais appliquée sans « Ok prod »). Recette réelle : tests/supabase_live/test_nouveaux_comptes_browser_live.py."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261114210000_nouveau_compte_suppression.sql"
STATEMENTS = MIGRATION.read_text(encoding="utf-8").split("\n\n", 1)[1].strip()


def test_deleting_an_account_deletes_the_nouveau_compte_notices_naming_it():
    sql = STATEMENTS.lower()
    assert "create or replace function private.forget_member_signup()" in sql and "security definer" in sql
    assert "delete from public.notifications where kind = 'member_signup' and data->>'member' = old.id::text" in sql
    assert "drop trigger if exists profiles_forget_member_signup on public.profiles" in sql
    assert "after delete on public.profiles" in sql  # la suppression du compte (auth.users) supprime le profil en cascade
    assert " table " not in sql.replace("on public.", "")  # aucune table créée, modifiée ni retirée


def test_prod_files_are_ready_and_identical():
    prod = ROOT / "supabase/prod"
    apply = (prod / "2026-11-14-nouveau-compte-suppression-apply.sql").read_text(encoding="utf-8")
    rollback = (prod / "2026-11-14-nouveau-compte-suppression-rollback.sql").read_text(encoding="utf-8")
    assert STATEMENTS in apply and apply.count("begin;") == 1 and "commit;" in apply
    assert "values ('20261114210000', 'nouveau_compte_suppression')" in apply and "« Ok prod »" in apply
    assert "drop trigger if exists profiles_forget_member_signup" in rollback and "where version = '20261114210000'" in rollback
