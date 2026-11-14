-- PROD, retour arrière de nouveau_compte_suppression (20261114210000) : les « Nouveau compte » restent après une suppression.
begin;
drop trigger if exists profiles_forget_member_signup on public.profiles;
drop function if exists private.forget_member_signup();
delete from supabase_migrations.schema_migrations where version = '20261114210000';
commit;
