-- Retour arrière de 20261121120000 : défaut 23:00 – 08:00 remis ; rallumé pour ceux qui l'ont encore éteint.
begin;
alter table public.notification_prefs alter column quiet_start set default '23:00';
alter table public.notification_prefs alter column quiet_end set default '08:00';
update public.notification_prefs set quiet_start = '23:00', quiet_end = '08:00' where quiet_start is null and quiet_end is null;
delete from supabase_migrations.schema_migrations where version = '20261121120000';
commit;
