-- Notifications par défaut choisies par l'admin le 28 octobre 2026 (Réglages natifs › Notifications) :
-- tout activé sauf les rappels « 7 jours » et « 2 heures avant » ; discussions « si on me cite » ; nouvel événement
-- « toujours ». Les heures de silence ne changent pas.
-- 1) valeurs par défaut des nouveaux comptes ; 2) une seule fois, les comptes existants reprennent ces choix
--    (demande explicite de l'admin : « modifier ça aussi sur tous les comptes déjà présents »).
-- Rejouable : la mise à jour des comptes est notée dans private.one_time_changes et ne repasse jamais.

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
  -- Sauvegarde des choix d'avant (retour arrière exact : supabase/prod/2026-10-28-notif-defaults-rollback.sql).
  create table if not exists private.notification_prefs_backup_20261028 as select * from public.notification_prefs;
  update public.notification_prefs set
    push_enabled = true, new_event = 'all', event_changed = true, poll_new = true, poll_nudge = true,
    date_fixed = true, waitlist = true, proposals = true, rsvp_mine = true, chat = 'mentions',
    reminders = array['1d', '0h']::text[];
  insert into private.one_time_changes (name) values ('notification_defaults_2026_10_28');
end $$;
