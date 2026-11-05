-- PROD, retour arrière de ai_pour_tous (20261105110000) : le droit « Utiliser l'assistant IA » revient au seul rôle
-- Admin (comme 20261031170000) et le texte d'aide reprend l'ancien libellé. Tout ou rien.
begin;
delete from public.role_permissions where perm = 'ai.use' and role <> 'admin';
insert into public.role_permissions (role, perm) values ('admin', 'ai.use') on conflict do nothing;
update public.permissions set hint = 'Scanner un ticket dans le pot commun (chaque usage est payant et compté)' where key = 'ai.use';
delete from private.one_time_changes where name = 'ai_use_all_roles_2026_11_05';
delete from supabase_migrations.schema_migrations where version = '20261105110000';
commit;
