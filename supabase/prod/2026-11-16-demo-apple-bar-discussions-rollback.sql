-- Retour arrière des données de démonstration Apple du 16.11 (événement, bar, groupe, message direct).
begin;
delete from public.events where title = 'Soirée démo Vendredi Party' and created_by = '298ff6e0-07b2-4127-bb69-d254dd63a3d5'
  and starts_at = '2026-12-12 19:00:00+01';
delete from public.member_groups where name = 'Démo Apple' and created_by = '298ff6e0-07b2-4127-bb69-d254dd63a3d5';
delete from public.direct_messages where chat_id in (select id from public.direct_chats where user_a = '298ff6e0-07b2-4127-bb69-d254dd63a3d5'
  and user_b = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd') and body like 'Bienvenue sur Vendredi Party ! Ceci est un message privé de démonstration.';
delete from supabase_migrations.schema_migrations where version = '20261116160000';
commit;
