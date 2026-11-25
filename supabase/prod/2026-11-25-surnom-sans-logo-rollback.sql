-- Retour arrière de 2026-11-25-surnom-sans-logo-apply.sql : remet l'ancien surnom (valeur lue en prod le 25.11.2026).
begin;
update public.profiles set display_name = convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8')
 where id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5' and display_name = 'Boby';
delete from supabase_migrations.schema_migrations where version = '20261125090100';
commit;
