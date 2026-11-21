-- Prod : 20261121120000_silence_nuit_eteint (demande de l'admin du 21.11) : heures de silence éteintes pour tous, plus de défaut.
begin;
alter table public.notification_prefs alter column quiet_start drop default;
alter table public.notification_prefs alter column quiet_end drop default;
update public.notification_prefs set quiet_start = null, quiet_end = null
 where quiet_start = '23:00' and quiet_end = '08:00';
insert into supabase_migrations.schema_migrations (version, name) values ('20261121120000', 'silence_nuit_eteint') on conflict do nothing;
commit;
