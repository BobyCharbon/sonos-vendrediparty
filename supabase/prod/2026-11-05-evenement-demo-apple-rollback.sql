-- Retour arrière : supprime l'événement de démonstration Apple (et son invitation, en cascade).
begin;
delete from public.events where title = 'Soirée démo Vendredi Party' and created_by = '298ff6e0-07b2-4127-bb69-d254dd63a3d5';
delete from supabase_migrations.schema_migrations where version = '20261105190000';
commit;
