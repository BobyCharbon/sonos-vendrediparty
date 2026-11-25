-- Retour arrière de 2026-11-25-pot-commun-filtre-apply.sql : le Pot commun n'est plus filtré (aucune donnée touchée).
begin;
drop trigger if exists tc_groups_moderation on public.tc_groups;
drop trigger if exists tc_members_moderation on public.tc_members;
drop trigger if exists tc_expenses_moderation on public.tc_expenses;
drop function if exists private.moderate_tc_text();
delete from supabase_migrations.schema_migrations where version = '20261125110000';
commit;
