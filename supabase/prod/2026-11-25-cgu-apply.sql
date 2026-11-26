-- PROD, CGU 2026-11-25 (20261125100000) : à appliquer AVEC le déploiement de fix-143 (la web et le nouveau build iPhone
-- montrent la version du 25 novembre 2026). Remplace 2026-11-18-cgu-pronos-patates (même effet, version plus récente).
-- Rejouable. Tout ou rien. Retour arrière : 2026-11-25-cgu-rollback.sql.
begin;
update private.moderation_settings set terms_version = '2026-11-25' where terms_version < '2026-11-25';
alter table private.moderation_settings alter column terms_version set default '2026-11-25';
insert into supabase_migrations.schema_migrations (version, name) values ('20261125100000', 'cgu_2026_11_25') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
