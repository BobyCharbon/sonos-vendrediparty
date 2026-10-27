-- PROD, retour arrière de 2026-10-26-presences-apply.sql (20261026120000_rsvp_set_by_organizer).
-- Rend la base exactement comme avant : l'organisateur ne peut plus changer la réponse des autres.
-- Les réponses posées par l'organisateur restent (seule la trace « posée par » disparaît).
begin;
drop function if exists public.set_rsvp_for(uuid, uuid, public.rsvp_status);
drop function if exists private.sees_event_uninvited(public.events, uuid);
drop trigger if exists rsvps_set_by on public.rsvps;
drop function if exists private.rsvp_set_by();
alter table public.rsvps drop column if exists set_by;

-- guard_rsvp d'avant (20261020160100_member_roles_permissions) : seul un admin passe la date limite.
create or replace function public.guard_rsvp() returns trigger
language plpgsql security definer set search_path = 'public' as $$
declare ev events;
begin
  if tg_op = 'UPDATE' and new.status = old.status and new.plus_ones = old.plus_ones
     and new.note is not distinct from old.note then
    return new; -- seul `waitlisted` change (apply_waitlist)
  end if;
  select * into ev from events where id = new.event_id;
  if new.status = 'maybe' and not ev.allow_maybe then raise exception 'Réponse « Peut-être » désactivée'; end if;
  if not ev.allow_plus_ones or (auth.uid() is not null and not has_perm('events.plus_ones')) then new.plus_ones := 0;
  else new.plus_ones := least(new.plus_ones, ev.max_plus_ones); end if;
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline and auth.uid() is not null and not is_admin() then
    raise exception 'La date limite de réponse est passée';
  end if;
  new.updated_at := now();
  if tg_op = 'INSERT' or old.status <> 'yes' then new.waitlisted := true; end if;
  return new;
end $$;

delete from supabase_migrations.schema_migrations where version = '20261026120000';
commit;
