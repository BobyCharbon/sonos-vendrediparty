-- Retour arrière des événements récurrents (20261116170000) : plus de nouvelle date créée ; les occurrences déjà créées
-- restent des événements ordinaires (leur lien à la série est retiré avec la colonne).
begin;
do $$ begin
  if exists (select 1 from cron.job where jobname = 'event-series-spawn') then perform cron.unschedule('event-series-spawn'); end if;
end $$;
drop function if exists private.spawn_series();
drop function if exists public.set_event_recurrence(uuid, text, int, date);
drop function if exists private.occurrence_end(public.events);
drop function if exists private.series_start(public.event_series, int);
drop policy if exists "série d'un événement visible" on public.event_series;
drop index if exists public.events_by_series;
alter table public.events drop column if exists series_id;
drop table if exists public.event_series;
delete from public.role_permissions where perm = 'events.recurring';
delete from public.permissions where key = 'events.recurring';
delete from private.one_time_changes where name = 'events_recurring_2026_11_16';
delete from supabase_migrations.schema_migrations where version = '20261116170000';
commit;
notify pgrst, 'reload schema';
