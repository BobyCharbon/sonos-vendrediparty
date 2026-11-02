-- PROD, retour arrière de pot_commun_events (20261031150000) : le pot commun n'est plus relié aux événements.
begin;
drop trigger if exists tc_rsvp_pot on public.rsvps;
drop trigger if exists tc_event_pot on public.events;
drop function if exists private.tc_rsvp_changed(), private.tc_event_changed(), private.tc_event_sync(uuid);
drop index if exists public.tc_groups_one_per_event;
alter table public.tc_groups drop column if exists event_id;
alter table public.events drop column if exists pot_enabled;
delete from supabase_migrations.schema_migrations where version = '20261031150000';
commit;
-- Puis réappliquer la fonction private.tc_group_json de 20261031090000_tricount.sql (version sans « event »).
