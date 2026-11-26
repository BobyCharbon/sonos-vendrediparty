-- Retour arrière de cgu_2026_11_25 (20261125100000) : CGU 2026-11-16 (valeur lue en prod le 25.11.2026). Les
-- acceptations des CGU 2026-11-25 restent (sans effet).
begin;
update private.moderation_settings set terms_version = '2026-11-16';
alter table private.moderation_settings alter column terms_version set default '2026-11-16';
delete from supabase_migrations.schema_migrations where version = '20261125100000';
commit;
notify pgrst, 'reload schema';
