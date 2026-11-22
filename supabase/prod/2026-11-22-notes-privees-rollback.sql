-- Retour arrière de 20261122132000 : les notes privées disparaissent (avec leur contenu).
begin;
drop function if exists public.member_note_set(uuid, text);
drop function if exists public.member_note_get(uuid);
drop table if exists public.member_notes;
delete from supabase_migrations.schema_migrations where version = '20261122132000';
commit;
