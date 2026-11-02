-- PROD, retour arrière de ai_assistant_right (20261031170000) : retire le droit « Utiliser l'assistant IA ».
begin;
delete from public.role_permissions where perm = 'ai.use';
delete from public.permissions where key = 'ai.use';
delete from private.one_time_changes where name = 'ai_use_2026_10_31';
delete from supabase_migrations.schema_migrations where version = '20261031170000';
commit;
