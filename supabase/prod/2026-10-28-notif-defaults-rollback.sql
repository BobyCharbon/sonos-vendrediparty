-- PROD, retour arrière de 20261028150000_notification_defaults : remet exactement les choix sauvegardés
-- par 2026-10-28-notif-defaults-apply.sql et les anciennes valeurs par défaut.
begin;
update public.notification_prefs p set
  push_enabled = b.push_enabled, new_event = b.new_event, event_changed = b.event_changed, poll_new = b.poll_new,
  poll_nudge = b.poll_nudge, date_fixed = b.date_fixed, waitlist = b.waitlist, proposals = b.proposals,
  rsvp_mine = b.rsvp_mine, chat = b.chat, reminders = b.reminders
  from private.notification_prefs_backup_20261028 b where b.user_id = p.user_id;
alter table public.notification_prefs alter column poll_nudge set default false;
alter table public.notification_prefs alter column reminders set default array['2h', '0h']::text[];
delete from private.one_time_changes where name = 'notification_defaults_2026_10_28';
delete from supabase_migrations.schema_migrations where version = '20261028150000';
commit;
-- La sauvegarde reste (private.notification_prefs_backup_20261028) ; la supprimer à la main ensuite.
