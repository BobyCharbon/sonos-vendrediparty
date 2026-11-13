-- PROD, retour arrière de covoiturage (20261113090000) : l'option, la table et les fonctions disparaissent
-- (le covoiturage en cours est effacé avec la table).
begin;
drop trigger if exists rsvps_carpool on public.rsvps;
drop function if exists private.carpool_on_rsvp();
drop function if exists public.carpool(uuid), public.carpool_drive(uuid, int, text), public.carpool_seek(uuid, text),
  public.carpool_take(uuid, uuid), public.carpool_pick(uuid, uuid), public.carpool_drop(uuid, uuid), public.carpool_leave(uuid);
drop function if exists private.carpool_board(uuid, uuid, uuid), private.carpool_city(text), private.carpool_guard(uuid),
  private.carpool_member(uuid, uuid);
drop table if exists public.event_carpool;
alter table public.events drop column if exists carpool_enabled;
delete from supabase_migrations.schema_migrations where version = '20261113090000';
commit;
