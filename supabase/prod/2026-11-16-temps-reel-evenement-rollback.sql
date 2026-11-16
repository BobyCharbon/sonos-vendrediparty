-- Retour arrière de temps_reel_evenement (20261116110000) : retire les déclencheurs, la purge, les fonctions et la table
-- des signaux (aucune donnée utile : de simples « recharge »). Les pages reviennent à leur relecture régulière.
begin;
do $$
declare t text;
begin
  foreach t in array array['event_bar_units', 'event_bar_refunds', 'event_tickets', 'event_bars', 'event_bar_items',
                           'event_bar_staff', 'event_bar_pledges', 'event_carpool'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists live_ping on public.%I', t);
    end if;
  end loop;
  if exists (select 1 from cron.job where jobname = 'live-pings-purge') then perform cron.unschedule('live-pings-purge'); end if;
  if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'live_pings') then
    alter publication supabase_realtime drop table public.live_pings;
  end if;
end $$;
drop function if exists private.live_ping_member();
drop function if exists private.live_ping_bar();
drop function if exists private.live_ping_event();
drop function if exists private.live_managers(uuid);
drop function if exists private.live_ping(uuid, uuid[]);
drop table if exists public.live_pings;
delete from supabase_migrations.schema_migrations where version = '20261116110000';
commit;
notify pgrst, 'reload schema';
