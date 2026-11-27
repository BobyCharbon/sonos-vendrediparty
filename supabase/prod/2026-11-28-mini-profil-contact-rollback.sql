-- Retour arrière de 2026-11-28-mini-profil-contact-apply.sql : retire la fonction (l'app revient au lien de member_mini).
begin;
drop function if exists public.member_mini_contact(uuid, text);
delete from supabase_migrations.schema_migrations where version = '20261128090000';
commit;
