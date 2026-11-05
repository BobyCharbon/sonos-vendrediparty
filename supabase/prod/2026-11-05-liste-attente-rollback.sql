-- PROD, retour arrière de liste_attente_rang (20261105143000) : public.guard_rsvp redevient celle de 20261026120000,
-- apply_waitlist / after_rsvp / rsvps_after celles du schéma initial (le rang en liste d’attente rebouge à chaque mot /
-- accompagnant ; un accompagnant de plus sur un événement complet fait de nouveau passer toute la réponse en attente ;
-- une réponse Peut-être / Absent peut de nouveau rester « en attente »). Les accompagnants en attente sont rendus à leur
-- réponse (plus_ones = total) : l'ancienne règle la remet en attente entière s'il n'y a pas de place. Les colonnes
-- plus_ones_waitlisted / plus_ones_waitlisted_since sont retirées. Les lignes remises à waitlisted = false restent ainsi
-- (sans effet : seul un Présent est compté en attente). Tout ou rien.
begin;
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
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline and auth.uid() is not null
     and not is_admin() and not is_organizer(new.event_id) then
    raise exception 'La date limite de réponse est passée';
  end if;
  new.updated_at := now();
  if tg_op = 'INSERT' or old.status <> 'yes' then new.waitlisted := true; end if;
  return new;
end $$;

create or replace function public.apply_waitlist(e uuid) returns void
language plpgsql security definer set search_path = public as $$
declare ev events; taken int; r record;
begin
  select * into ev from events where id = e;
  if ev.max_participants is null then
    update rsvps set waitlisted = false where event_id = e and waitlisted;
    return;
  end if;
  taken := 0;
  for r in select * from rsvps where event_id = e and status = 'yes' order by waitlisted, updated_at loop
    if taken + 1 + r.plus_ones <= ev.max_participants then
      taken := taken + 1 + r.plus_ones;
      if r.waitlisted then
        update rsvps set waitlisted = false where event_id = e and user_id = r.user_id;
        -- updated_at = now() : réponse donnée dans cette transaction, pas une vraie attente
        if r.updated_at < now() and (select waitlist from notification_prefs where user_id = r.user_id) then
          perform queue_notification(r.user_id, 'waitlist', e, 'Une place s''est libérée',
            'Tu es inscrit à « ' || ev.title || ' ».');
        end if;
      end if;
    elsif not r.waitlisted then
      update rsvps set waitlisted = true where event_id = e and user_id = r.user_id;
    end if;
  end loop;
end $$;

create or replace function public.after_rsvp() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  perform apply_waitlist(coalesce(new.event_id, old.event_id));
  return null;
end $$;
drop trigger if exists rsvps_after on public.rsvps;
create trigger rsvps_after after insert or update of status, plus_ones or delete on public.rsvps
for each row execute function public.after_rsvp();

update public.rsvps set plus_ones = plus_ones + plus_ones_waitlisted where plus_ones_waitlisted > 0;
alter table public.rsvps drop column if exists plus_ones_waitlisted_since;
alter table public.rsvps drop column if exists plus_ones_waitlisted;
delete from supabase_migrations.schema_migrations where version = '20261105143000';
commit;

notify pgrst, 'reload schema';
