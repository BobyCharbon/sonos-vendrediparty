-- Retour arrière de cgu_pronos_patates (20261118095000) : CGU 2026-11-16. Les acceptations des CGU 2026-11-18 restent
-- (sans effet).
begin;
update private.moderation_settings set terms_version = '2026-11-16';
alter table private.moderation_settings alter column terms_version set default '2026-11-16';
delete from supabase_migrations.schema_migrations where version = '20261118095000';
commit;
notify pgrst, 'reload schema';
