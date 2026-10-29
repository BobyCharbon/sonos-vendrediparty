-- Notifications des événements (retour de l'admin du 29 octobre 2026) :
-- 1) Envoi immédiat : une notification créée réveille tout de suite l'envoi (APNs et web push) au lieu d'attendre
--    la tâche de chaque minute, qui reste en secours. Un seul réveil par seconde au plus.
-- 2) Réponses aux événements (Présent / Peut-être / Absent) regroupées : le premier changement ouvre une fenêtre
--    de 5 minutes ; à la fin, une seule notification par organisateur avec l'état final de chacun.
--    Quelqu'un qui change d'avis toutes les 2 secondes ne déclenche donc qu'une notification.
-- Rejouable.

-- 1) Envoi immédiat -----------------------------------------------------------------------------------------------

create table if not exists private.push_kick (
  id boolean primary key default true check (id),
  at timestamptz not null default '-infinity'
);
insert into private.push_kick (id) values (true) on conflict do nothing;
revoke all on private.push_kick from public, anon, authenticated;

create or replace function private.kick_push() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Au plus un réveil par seconde (une rafale de notifications dans la même transaction part d'un seul envoi :
  -- la requête HTTP ne part qu'une fois la transaction validée).
  update private.push_kick set at = clock_timestamp() where id and at < clock_timestamp() - interval '1 second';
  if found then
    perform private.dispatch_push_job();
    perform private.dispatch_web_push_job();
  end if;
  return null;
exception when others then
  return null;  -- un réveil raté n'empêche jamais la notification d'être enregistrée : la tâche de chaque minute l'enverra
end $$;
revoke all on function private.kick_push() from public, anon, authenticated;

drop trigger if exists notifications_kick_push on public.notifications;
create trigger notifications_kick_push after insert on public.notifications
  for each statement execute function private.kick_push();

-- 2) Réponses regroupées sur 5 minutes ---------------------------------------------------------------------------

create table if not exists private.rsvp_digest (
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  status public.rsvp_status not null,
  first_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (event_id, user_id)
);
revoke all on private.rsvp_digest from public, anon, authenticated;

create or replace function public.notify_rsvp() returns trigger
language plpgsql security definer set search_path = 'public' as $$
begin
  if tg_op = 'UPDATE' and new.status = old.status then return null; end if;
  -- Réponses créées automatiquement (clôture d'un sondage) : pas de notif
  if auth.uid() is distinct from new.user_id then return null; end if;
  -- Retenue 5 minutes : seul l'état final de chaque personne partira (private.flush_rsvp_digests).
  insert into private.rsvp_digest (event_id, user_id, status) values (new.event_id, new.user_id, new.status)
  on conflict (event_id, user_id) do update set status = excluded.status, updated_at = now();
  return null;
end $$;

create or replace function private.rsvp_phrase(who text, s public.rsvp_status) returns text
language sql immutable set search_path = '' as $$
  select coalesce(nullif(btrim(who), ''), 'Quelqu''un')
    || case s when 'yes' then ' vient' when 'maybe' then ' viendra peut-être' else ' ne vient pas' end;
$$;

create or replace function private.flush_rsvp_digests() returns integer
language plpgsql security definer set search_path = '' as $$
declare
  started timestamptz := now();
  ev public.events;
  recipient uuid;
  phrases text[];
  n integer;
  sent integer := 0;
begin
  for ev in
    select e.* from public.events e
    where e.id in (select event_id from private.rsvp_digest group by event_id having min(first_at) <= started - interval '5 minutes')
  loop
    for recipient in
      select o.x from (select ev.created_by x union select user_id from public.event_organizers where event_id = ev.id) o
      join public.notification_prefs np on np.user_id = o.x where np.rsvp_mine
    loop
      -- Tout le monde sauf l'organisateur lui-même, dans l'ordre des réponses.
      select array_agg(private.rsvp_phrase(p.display_name, d.status) order by d.updated_at)
        into phrases
        from private.rsvp_digest d join public.profiles p on p.id = d.user_id
        where d.event_id = ev.id and d.user_id <> recipient and d.updated_at <= started;
      n := coalesce(array_length(phrases, 1), 0);
      if n = 0 then continue; end if;
      perform public.queue_notification(recipient, 'rsvp', ev.id, ev.title,
        case when n <= 3 then array_to_string(phrases, ' · ')
             else array_to_string(phrases[1:3], ' · ') || ' · et ' || (n - 3)
                  || case when n - 3 > 1 then ' autres réponses' else ' autre réponse' end end);
      sent := sent + 1;
    end loop;
    -- Réponses arrivées pendant l'envoi : elles ouvrent la prochaine fenêtre de 5 minutes.
    delete from private.rsvp_digest where event_id = ev.id and updated_at <= started;
    update private.rsvp_digest set first_at = now() where event_id = ev.id;
  end loop;
  return sent;
end $$;
revoke all on function private.flush_rsvp_digests() from public, anon, authenticated;

select cron.schedule('rsvp-digest', '* * * * *', $$ select private.flush_rsvp_digests(); $$);
