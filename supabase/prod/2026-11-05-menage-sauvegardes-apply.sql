-- Ménage (accord de l'admin du 05.11.2026) : les 3 copies de sauvegarde faites avant les migrations des rappels (26.10)
-- et des préférences de notifications (28.10) ne servent plus et gardent des identifiants de comptes supprimés (nLPD).
begin;
drop table if exists private.reminders_backup_20261026_events;
drop table if exists private.reminders_backup_20261026_prefs;
drop table if exists private.notification_prefs_backup_20261028;
insert into supabase_migrations.schema_migrations (version, name) values ('20261105191000', 'menage_sauvegardes')
 on conflict do nothing;
commit;
