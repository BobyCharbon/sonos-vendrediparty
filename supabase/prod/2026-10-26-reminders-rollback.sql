-- PROD, retour arrière de 20261026090000_reminders_personal : remet exactement les rappels sauvegardés
-- par 2026-10-26-reminders-apply.sql (comptes et événements), et les anciennes valeurs par défaut.
begin;
update public.events e set reminders = b.reminders from private.reminders_backup_20261026_events b where b.id = e.id;
update public.notification_prefs p set reminders = b.reminders from private.reminders_backup_20261026_prefs b where b.user_id = p.user_id;
alter table public.events alter column reminders set default '{1d,2h}';
alter table public.notification_prefs alter column reminders set default '{1d,2h}';
delete from supabase_migrations.schema_migrations where version = '20261026090000';
commit;
-- Les tables de sauvegarde restent (private.reminders_backup_20261026_*) ; les supprimer à la main ensuite.
