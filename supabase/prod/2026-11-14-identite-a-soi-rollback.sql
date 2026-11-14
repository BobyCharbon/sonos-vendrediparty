-- PROD, retour arrière de identite_a_soi (20261114153000) : on revient à la garde d'avant (rôle et accès seulement).
begin;
drop trigger if exists profiles_auth_identity on public.profiles;
drop function if exists private.guard_profile_identity();
delete from supabase_migrations.schema_migrations where version = '20261114153000';
commit;
