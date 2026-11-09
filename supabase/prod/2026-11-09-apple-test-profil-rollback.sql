-- Retour arrière du profil Apple-test (20261109010000) : Guest sans prénom, nom ni photo, comme le 05.11.
begin;
update public.profiles set first_name = '', last_name = '', avatar_url = null, role = 'guest'
 where id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
delete from supabase_migrations.schema_migrations where version = '20261109010000';
commit;
