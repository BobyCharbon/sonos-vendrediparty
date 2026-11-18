-- PROD, CGU 2026-11-18 « Pronos et confettis » (20261118095000). À appliquer AVANT d'allumer PATATES_ENABLED en prod
-- (et avec la version de la web / de l'app qui montre le nouveau texte). Rejouable. Tout ou rien.
begin;
update private.moderation_settings set terms_version = '2026-11-18' where terms_version < '2026-11-18';
alter table private.moderation_settings alter column terms_version set default '2026-11-18';
insert into supabase_migrations.schema_migrations (version, name) values ('20261118095000', 'cgu_pronos_patates') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
