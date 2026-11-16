-- Événements récurrents (demande de l'admin du 16.11.2026) : chaque jour, chaque semaine, toutes les 2 semaines, chaque
-- mois, chaque année ; « jusqu'au » facultatif.
-- Une seule occurrence existe à la fois : la suivante n'est créée (donc visible) qu'une fois la précédente TERMINÉE (sa fin,
-- ou sans heure de fin : le lendemain à 0 h ; le sbire du lundi 19 h apparaît mardi). Elle recopie la DERNIÈRE occurrence
-- (une modification vaut pour les suivantes) : titre, texte, lieu, options, visibilité, groupes, invités ajoutés un à un ou
-- par numéro, co-organisateurs, étiquettes, « qui amène quoi » demandé par l'organisateur ; jamais les réponses, votes,
-- messages, billets, bar, covoiturage, sondages ni liens d'invitation. Elle est publiée comme un événement neuf : un
-- public ne prévient personne ; les invités un à un reçoivent leur invitation ; jamais de nouvelle annonce au groupe.
-- Dates en heure de Suisse (Europe/Zurich, changement d'heure compris), comptées depuis la première occurrence de la
-- règle : le 31 de chaque mois tombe le 30 ou le 28 sans dériver ensuite.
-- Purement additive et rejouable.

create table if not exists public.event_series (
  id uuid primary key default gen_random_uuid(),
  frequency text not null check (frequency in ('daily', 'weekly', 'monthly', 'yearly')),
  every int not null default 1 check (every between 1 and 12),
  until date,
  anchor timestamp not null,              -- début de l'occurrence 0 de la règle, heure de Suisse
  last_n int not null default 0,          -- rang de la dernière occurrence créée
  stopped_at timestamptz,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
alter table public.event_series enable row level security;
alter table public.events add column if not exists series_id uuid references public.event_series(id) on delete set null;
create index if not exists events_by_series on public.events (series_id, starts_at desc) where series_id is not null;
drop policy if exists "série d'un événement visible" on public.event_series;
create policy "série d'un événement visible" on public.event_series for select to authenticated
  using (exists (select 1 from public.events e where e.series_id = event_series.id));
revoke insert, update, delete on public.event_series from anon, authenticated;
grant select on public.event_series to authenticated;

-- Droit « Créer des événements récurrents » (précision de l'admin du 16.11) : Admin, Co-admin et Organisateur seulement
-- au départ ; réglable ensuite dans Rôles et droits.
insert into public.permissions (key, grp, label, hint, sort) values
  ('events.recurring', 'Événements', 'Créer des événements récurrents',
   'Répéter un événement chaque jour, semaine, mois ou année (une seule date visible à la fois)', 16)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'events_recurring_2026_11_16') then return; end if;
  insert into public.role_permissions (role, perm)
    select r, 'events.recurring' from unnest(array['admin', 'coadmin', 'organizer']) r
    where exists (select 1 from public.roles where key = r)
  on conflict do nothing;
  insert into private.one_time_changes (name) values ('events_recurring_2026_11_16');
end $$;

-- Début (heure de Suisse → instant) de l'occurrence n de la règle.
create or replace function private.series_start(s public.event_series, n int) returns timestamptz
language sql stable set search_path = '' as $$
  select (s.anchor + (n * s.every) * case s.frequency when 'daily' then interval '1 day' when 'weekly' then interval '1 week'
                                                       when 'monthly' then interval '1 month' else interval '1 year' end)
         at time zone 'Europe/Zurich';
$$;

-- Fin d'une occurrence : son heure de fin ; sans fin (ou journée entière), le lendemain de son jour à 0 h.
create or replace function private.occurrence_end(ev public.events) returns timestamptz
language sql stable set search_path = '' as $$
  select case when ev.ends_at is not null and not ev.all_day then ev.ends_at
              else (((coalesce(ev.ends_at, ev.starts_at) at time zone 'Europe/Zurich')::date + 1)::timestamp) at time zone 'Europe/Zurich' end;
$$;

-- Répétition d'un événement, par ceux qui peuvent le modifier ET ont le droit events.recurring (l'arrêter : tout organisateur). frequency 'none' (ou null) : la répétition s'arrête
-- (l'occurrence en cours reste). Sinon la règle part de CET événement (sa date et son heure) : modifier la date de la
-- dernière occurrence dans le formulaire déplace aussi les suivantes.
create or replace function public.set_event_recurrence(e uuid, frequency text, every int default 1, until date default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare ev public.events; s public.event_series; latest uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  select * into ev from public.events where id = e;
  if not found then raise exception 'Événement introuvable' using errcode = 'PT404'; end if;
  if not (public.is_organizer(e) or private.user_has(auth.uid(), 'events.manage_all')) then
    raise exception 'forbidden: seuls les organisateurs choisissent la répétition' using errcode = '42501';
  end if;
  if ev.series_id is not null then
    select * into s from public.event_series where id = ev.series_id;
    select x.id into latest from public.events x where x.series_id = ev.series_id order by x.starts_at desc nulls last limit 1;
  end if;
  if coalesce(frequency, 'none') <> 'none' and not private.user_has(auth.uid(), 'events.recurring') then
    raise exception 'forbidden: les événements récurrents sont réservés aux admins, co-admins et organisateurs' using errcode = '42501';
  end if;
  if coalesce(frequency, 'none') = 'none' then
    if s.id is not null and s.stopped_at is null then update public.event_series set stopped_at = now() where id = s.id; end if;
    return jsonb_build_object('frequency', 'none');
  end if;
  if frequency not in ('daily', 'weekly', 'monthly', 'yearly') then
    raise exception 'Répétition inconnue : chaque jour, semaine, mois ou année.' using errcode = '22023';
  end if;
  if every is null or every not between 1 and 12 then raise exception 'Répétition : tous les 1 à 12.' using errcode = '22023'; end if;
  if ev.date_mode <> 'fixed' or ev.starts_at is null then
    raise exception 'Un événement qui se répète a une date fixée (pas un sondage de dates).' using errcode = '22023';
  end if;
  if until is not null and until < (ev.starts_at at time zone 'Europe/Zurich')::date then
    raise exception 'La répétition doit finir après la première date.' using errcode = '22023';
  end if;
  if s.id is not null and latest is distinct from e then
    raise exception 'Change la répétition depuis la prochaine date de la série.' using errcode = '22023';
  end if;
  if s.id is null then
    insert into public.event_series (frequency, every, until, anchor, created_by)
      values (frequency, every, until, ev.starts_at at time zone 'Europe/Zurich', auth.uid()) returning * into s;
    update public.events set series_id = s.id where id = e;
  else
    update public.event_series set frequency = set_event_recurrence.frequency, every = set_event_recurrence.every,
      until = set_event_recurrence.until, anchor = ev.starts_at at time zone 'Europe/Zurich', last_n = 0, stopped_at = null
      where id = s.id returning * into s;
  end if;
  return jsonb_build_object('id', s.id, 'frequency', s.frequency, 'every', s.every, 'until', s.until);
end $$;
revoke all on function public.set_event_recurrence(uuid, text, int, date) from public, anon;
grant execute on function public.set_event_recurrence(uuid, text, int, date) to authenticated;

-- Crée l'occurrence suivante des séries dont la dernière occurrence est terminée (pg_cron, toutes les 5 minutes).
create or replace function private.spawn_series() returns int
language plpgsql security definer set search_path = '' as $$
declare s public.event_series; last public.events; n int; nxt timestamptz; dur interval; nid uuid; made int := 0;
begin
  for s in select * from public.event_series where stopped_at is null for update skip locked loop
    select * into last from public.events where series_id = s.id order by starts_at desc nulls last limit 1;
    if not found then update public.event_series set stopped_at = now() where id = s.id; continue; end if;
    if last.status not in ('published', 'cancelled') or last.starts_at is null then continue; end if;
    if private.occurrence_end(last) > now() then continue; end if;
    dur := last.ends_at - last.starts_at;
    -- Prochaine date pas encore terminée (le serveur arrêté longtemps ne recrée pas les dates passées).
    n := s.last_n + 1;
    loop
      nxt := private.series_start(s, n);
      exit when coalesce(nxt + dur, nxt) > now() and nxt > last.starts_at;
      n := n + 1;
    end loop;
    if s.until is not null and (nxt at time zone 'Europe/Zurich')::date > s.until then
      update public.event_series set stopped_at = now() where id = s.id;
      continue;
    end if;
    insert into public.events
      select (jsonb_populate_record(null::public.events, to_jsonb(last) || jsonb_build_object(
        'id', gen_random_uuid(), 'status', 'draft', 'starts_at', nxt, 'ends_at', nxt + dur,
        'rsvp_deadline', case when last.rsvp_deadline is null then null else nxt - (last.starts_at - last.rsvp_deadline) end,
        'poll_deadline', null, 'announce_group', false, 'invite_token', gen_random_uuid(),
        'created_at', now(), 'updated_at', now(), 'rejection_reason', null))).*
      returning id into nid;
    insert into public.event_organizers (event_id, user_id) select nid, user_id from public.event_organizers where event_id = last.id;
    insert into public.event_tags (event_id, tag_id) select nid, tag_id from public.event_tags where event_id = last.id;
    insert into public.event_groups (event_id, group_id, status, requested_by, answered_by, answered_at)
      select nid, group_id, status, requested_by, answered_by, answered_at from public.event_groups where event_id = last.id;
    insert into public.event_invites (event_id, user_id, invited_by)
      select nid, user_id, invited_by from public.event_invites where event_id = last.id and not via_group and not via_link
      on conflict do nothing;
    insert into public.event_phone_invites (event_id, phone, invited_by)
      select nid, phone, invited_by from public.event_phone_invites where event_id = last.id on conflict do nothing;
    insert into public.bring_items (event_id, label, sort, quantity)
      select nid, label, sort, quantity from public.bring_items where event_id = last.id and added_by is null;
    -- Publiée seulement maintenant, enfants en place : invitations envoyées comme pour un événement neuf.
    update public.events set status = 'published', approved_at = now() where id = nid;
    update public.event_series set last_n = n where id = s.id;
    made := made + 1;
  end loop;
  return made;
end $$;
revoke all on function private.spawn_series() from public, anon, authenticated;

do $$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    if exists (select 1 from cron.job where jobname = 'event-series-spawn') then perform cron.unschedule('event-series-spawn'); end if;
    perform cron.schedule('event-series-spawn', '*/5 * * * *', 'select private.spawn_series()');
  end if;
end $$;

notify pgrst, 'reload schema';
