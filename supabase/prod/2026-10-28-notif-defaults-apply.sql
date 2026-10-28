-- PROD, notifications par défaut (20261028150000_notification_defaults).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod ») pour cette migration.
-- Tout-ou-rien ; rejouable sans risque (la mise à jour des comptes ne passe qu'une fois).
-- Retour arrière exact : 2026-10-28-notif-defaults-rollback.sql (lit la sauvegarde faite ici).
begin;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);

alter table public.notification_prefs alter column poll_nudge set default true;
alter table public.notification_prefs alter column reminders set default array['1d', '0h']::text[];

create table if not exists private.one_time_changes (
  name text primary key,
  applied_at timestamptz not null default now()
);
revoke all on private.one_time_changes from public, anon, authenticated;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'notification_defaults_2026_10_28') then
    return;
  end if;
  create table if not exists private.notification_prefs_backup_20261028 as select * from public.notification_prefs;
  update public.notification_prefs set
    push_enabled = true, new_event = 'all', event_changed = true, poll_new = true, poll_nudge = true,
    date_fixed = true, waitlist = true, proposals = true, rsvp_mine = true, chat = 'mentions',
    reminders = array['1d', '0h']::text[];
  insert into private.one_time_changes (name) values ('notification_defaults_2026_10_28');
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261028150000', 'notification_defaults')
  on conflict (version) do nothing;
commit;
