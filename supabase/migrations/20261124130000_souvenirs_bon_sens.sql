-- Souvenirs : corrections du contrôle « bon sens » (24.11, après 20261124090000 et 20261124120000).
-- 1. Nouvelle ligne d'événement (récurrents : spawn_series recopie la date d'avant sous le rôle postgres) : verrou et
--    dévoilement remis à zéro quel que soit le rôle. Les photos ne sont jamais recopiées.
-- 2. souvenir_restore : jamais sa propre photo ; signalement « my_image » ouvert : seule la modération de Party tranche
--    (l'organisation peut toujours retirer).
-- 3. Événement annulé (ou plus publié) : ni dévoilement, ni notification, ni story ; « Mes souvenirs » restent.
-- 4. Date déplacée : un dévoilement posé avant la nouvelle fin est retiré (fin + 24 h à nouveau) ; si le dévoilement
--    redevient futur, la notification repartira à la nouvelle heure. L'appareil (fin + 2 h) suit la fin d'office.
-- 5. Signalements en rafale : une même personne masque au plus 5 photos Souvenirs par soirée ; au-delà, le signalement
--    va seulement à la modération de Party (pas de masquage, pas de notification à l'organisation).
-- 6. Notification de dévoilement : sans « garder », le texte dit que les photos disparaissent après 24 h.
-- 7. Story : une réponse Présent / Peut-être donnée par la personne elle-même APRÈS la fin (la base l'accepte jusqu'à
--    fin + 6 h, event_is_over) ne donne pas la story (private.souvenir_late) ; sauf si elle a pris une photo, ou si
--    l'organisation a noté sa présence. Organisation : toujours.
-- Purement additive et rejouable.

-- ───────────── 7. Réponses données après la fin ─────────────
create table if not exists private.souvenir_late (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  at timestamptz not null default now(),
  primary key (event_id, user_id)
);
revoke all on private.souvenir_late from public, anon, authenticated;

create or replace function private.souvenir_late_rsvp() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  if new.status in ('yes', 'maybe') and (tg_op = 'INSERT' or old.status not in ('yes', 'maybe'))
     and auth.uid() is not distinct from new.user_id then   -- la personne elle-même (pas l'organisation qui note)
    select * into ev from public.events where id = new.event_id;
    if ev.souvenirs_enabled and ev.starts_at is not null and now() >= private.souvenir_end(ev) then
      insert into private.souvenir_late (event_id, user_id, at) values (new.event_id, new.user_id, now())
      on conflict (event_id, user_id) do update set at = excluded.at;
    end if;
  end if;
  return null;
end $$;
revoke all on function private.souvenir_late_rsvp() from public, anon, authenticated;
drop trigger if exists souvenir_late_rsvp on public.rsvps;
create trigger souvenir_late_rsvp after insert or update of status on public.rsvps
  for each row execute function private.souvenir_late_rsvp();

-- Qui voit la story : l'organisation, qui a pris une photo, le cercle sauf réponse donnée après la fin (comparée à la
-- fin ACTUELLE : une date déplacée corrige d'elle-même).
create or replace function private.souvenir_viewer(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select u is not null and private.is_account_active(u) and (
    private.souvenir_staff(e, u)
    or exists (select 1 from public.souvenir_photos p where p.event_id = e and p.author_id = u)
    or (private.souvenir_circle(e, u) and not exists (
          select 1 from private.souvenir_late l join public.events ev on ev.id = l.event_id
          where l.event_id = e and l.user_id = u and l.at >= private.souvenir_end(ev))));
$$;
revoke all on function private.souvenir_viewer(uuid, uuid) from public, anon, authenticated;

create or replace function private.souvenir_visible(p public.souvenir_photos, u uuid) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events; ph text;
begin
  if p.id is null or u is null or p.hidden_at is not null or private.blocked_either(u, p.author_id) then return false; end if;
  select * into ev from public.events where id = p.event_id;
  ph := private.souvenir_phase(ev);
  if ph in ('soon', 'open', 'waiting') then
    return private.souvenir_staff(ev.id, u);                                    -- relecture de l'organisation
  elsif ph = 'story' then
    return private.souvenir_viewer(ev.id, u) or p.author_id = u;
  elsif ph = 'after' then
    return ev.souvenirs_keep and (p.author_id = u
      or exists (select 1 from public.souvenir_keeps k where k.photo_id = p.id and k.user_id = u));
  end if;
  return false;
end $$;
revoke all on function private.souvenir_visible(public.souvenir_photos, uuid) from public, anon, authenticated;

create or replace function public.souvenir_story(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not private.souvenir_viewer(e, me) then
    raise exception 'forbidden: la story est réservée aux participants (Présent ou Peut-être) et à l''organisation' using errcode = '42501';
  end if;
  if ev.status <> 'published' or private.souvenir_phase(ev) <> 'story' then
    raise exception 'closed: la story n''est pas visible maintenant' using errcode = '22023';
  end if;
  return jsonb_build_object('event_id', e, 'title', ev.title, 'keep', ev.souvenirs_keep,
    'until', private.souvenir_reveal_at(ev) + interval '24 hours',
    'photos', coalesce((select jsonb_agg(private.souvenir_json(p, me) || jsonb_build_object(
        'kept', exists (select 1 from public.souvenir_keeps k where k.photo_id = p.id and k.user_id = me),
        'can_keep', ev.souvenirs_keep and p.author_id <> me) order by p.taken_at, p.id)
      from public.souvenir_photos p where p.event_id = e and private.souvenir_visible(p, me)), '[]'::jsonb));
end $$;

-- Bulles (20261124120000) : mêmes règles que la story, jamais un événement annulé.
create or replace function public.souvenir_stories() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('event_id', ev.id, 'title', ev.title, 'phase', x.ph,
      'reveal_at', private.souvenir_reveal_at(ev),
      'until', private.souvenir_reveal_at(ev) + interval '24 hours', 'count', x.n,
      'seen', exists (select 1 from public.souvenir_seen s where s.event_id = ev.id and s.user_id = auth.uid()))
    order by (x.ph = 'story') desc, private.souvenir_reveal_at(ev) desc), '[]'::jsonb)
  from public.events ev
  cross join lateral (select private.souvenir_phase(ev) ph) p
  cross join lateral (select p.ph, case when p.ph = 'story'
        then (select count(*) from public.souvenir_photos f where f.event_id = ev.id and private.souvenir_visible(f, auth.uid()))
        else (select count(*) from public.souvenir_photos f where f.event_id = ev.id and f.hidden_at is null
              and not private.blocked_either(auth.uid(), f.author_id)) end n) x
  where ev.souvenirs_enabled and ev.status = 'published' and x.ph in ('story', 'waiting') and x.n > 0
    and private.souvenir_viewer(ev.id, auth.uid());
$$;

create or replace function public.souvenir_mark_seen(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.souvenir_viewer(e, me) then
    raise exception 'forbidden: story réservée aux participants' using errcode = '42501';
  end if;
  insert into public.souvenir_seen (event_id, user_id) values (e, me)
  on conflict (event_id, user_id) do update set seen_at = now();
  return jsonb_build_object('seen', true);
end $$;

create or replace function public.souvenir_keep(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos; ev public.events;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_keep.id;
  select * into ev from public.events where events.id = p.event_id;
  if p.id is null or not private.souvenir_visible(p, me) then
    raise exception 'not_found: photo introuvable' using errcode = 'PT404';
  end if;
  if not ev.souvenirs_keep then
    raise exception 'forbidden: l''organisation n''autorise pas à garder les photos de cette soirée' using errcode = '42501';
  end if;
  if private.souvenir_phase(ev) <> 'story' or ev.status <> 'published'
     or not private.souvenir_circle(ev.id, me) or not private.souvenir_viewer(ev.id, me) then
    raise exception 'closed: on garde une photo pendant la story seulement' using errcode = '22023';
  end if;
  if p.author_id = me then return jsonb_build_object('kept', true); end if;
  insert into public.souvenir_keeps (photo_id, user_id) values (p.id, me) on conflict do nothing;
  return jsonb_build_object('kept', true);
end $$;

-- ───────────── 1 et 4. Garde des colonnes ─────────────
-- Sans security definer : current_user dit qui écrit. Insertion : verrou et dévoilement à zéro pour TOUS les rôles.
create or replace function private.souvenirs_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    new.souvenirs_locked := false;
    new.souvenirs_reveal_at := null;
    return new;
  end if;
  if current_user in ('authenticated', 'anon') then
    if new.souvenirs_locked is distinct from old.souvenirs_locked or new.souvenirs_reveal_at is distinct from old.souvenirs_reveal_at then
      raise exception 'forbidden: le dévoilement des souvenirs passe par « Dévoiler maintenant »' using errcode = '42501';
    end if;
    if new.souvenirs_enabled is distinct from old.souvenirs_enabled or new.souvenirs_keep is distinct from old.souvenirs_keep then
      if not private.souvenir_staff(new.id, auth.uid()) then
        raise exception 'forbidden: seule l''organisation règle les Souvenirs' using errcode = '42501';
      end if;
      if old.souvenirs_locked then
        raise exception 'locked: les réglages des Souvenirs sont figés depuis la première photo' using errcode = '42501';
      end if;
    end if;
  end if;
  -- Date déplacée : un dévoilement posé avant la nouvelle fin est retiré (fin + 24 h à nouveau).
  if (new.starts_at is distinct from old.starts_at or new.ends_at is distinct from old.ends_at)
     and new.souvenirs_reveal_at is not null
     and new.souvenirs_reveal_at < coalesce(new.ends_at, new.starts_at + interval '12 hours') then
    new.souvenirs_reveal_at := null;
  end if;
  return new;
end $$;
revoke all on function private.souvenirs_guard() from public, anon, authenticated;

-- Date déplacée : si le dévoilement redevient futur, il repartira (et sa notification) à la nouvelle heure.
create or replace function private.souvenirs_dates_moved() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.souvenirs_enabled and private.souvenir_reveal_at(new) > now() then
    update private.souvenir_runs set revealed_at = null where event_id = new.id and revealed_at is not null;
  end if;
  return null;
end $$;
revoke all on function private.souvenirs_dates_moved() from public, anon, authenticated;
drop trigger if exists souvenirs_dates_moved on public.events;
create trigger souvenirs_dates_moved after update of starts_at, ends_at on public.events
  for each row when (old.starts_at is distinct from new.starts_at or old.ends_at is distinct from new.ends_at)
  execute function private.souvenirs_dates_moved();

-- ───────────── 2. Remettre une photo signalée ─────────────
create or replace function private.souvenir_my_image_open(p uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.content_reports r where r.target_kind = 'souvenir' and r.target_id = p::text
                 and r.status = 'open' and r.reason = 'my_image');
$$;
revoke all on function private.souvenir_my_image_open(uuid) from public, anon, authenticated;

create or replace function public.souvenir_restore(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_restore.id;
  if p.id is null or not private.souvenir_staff(p.event_id, me) then
    raise exception 'not_found: photo introuvable' using errcode = 'PT404';
  end if;
  if p.hidden_at is null then return jsonb_build_object('restored', false); end if;
  if p.author_id = me then
    raise exception 'forbidden: c''est ta photo : la modération de Party décide (tu peux la retirer)' using errcode = '42501';
  end if;
  if private.souvenir_my_image_open(p.id) then
    raise exception 'forbidden: la personne sur la photo ne veut pas qu''elle soit montrée : la modération de Party décide' using errcode = '42501';
  end if;
  update public.souvenir_photos x set hidden_at = null, restored_at = now(), restored_by = me where x.id = p.id;
  return jsonb_build_object('restored', true);
end $$;

-- Relecture : « can_restore » dit si « Remettre » est permis (jamais sa photo, jamais un « my_image » ouvert).
create or replace function public.souvenir_review(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not private.souvenir_staff(e, me) then
    raise exception 'forbidden: la relecture est réservée à l''organisation' using errcode = '42501';
  end if;
  return jsonb_build_object('phase', private.souvenir_phase(ev),
    'photos', coalesce((select jsonb_agg(private.souvenir_json(p, me) order by p.taken_at, p.id)
      from public.souvenir_photos p where p.event_id = e and p.hidden_at is null and not private.blocked_either(me, p.author_id)), '[]'::jsonb),
    'reported', coalesce((select jsonb_agg(private.souvenir_json(p, me) || jsonb_build_object('hidden_at', p.hidden_at,
        'reasons', (select coalesce(jsonb_agg(distinct r.reason), '[]'::jsonb) from public.content_reports r
                    where r.target_kind = 'souvenir' and r.target_id = p.id::text and r.status = 'open'),
        'can_restore', p.author_id <> me and not private.souvenir_my_image_open(p.id)) order by p.taken_at)
      from public.souvenir_photos p where p.event_id = e and p.hidden_at is not null), '[]'::jsonb));
end $$;

-- ───────────── 3 et 6. Dévoilement ─────────────
create or replace function private.souvenir_reveal_run(e uuid) returns int
language plpgsql security definer set search_path = '' as $$
declare ev public.events; u uuid; n int := 0;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or ev.status <> 'published' then return 0; end if;   -- annulé : rien (reste à faire s'il revient)
  insert into private.souvenir_runs (event_id) values (e) on conflict do nothing;
  update private.souvenir_runs set revealed_at = now() where event_id = e and revealed_at is null;
  if not found then return 0; end if;
  if not exists (select 1 from public.souvenir_photos p where p.event_id = e and p.hidden_at is null) then return 0; end if;
  for u in select x.u from (
      select ev.created_by u union select o.user_id from public.event_organizers o where o.event_id = e
      union select r.user_id from public.rsvps r where r.event_id = e and r.status in ('yes', 'maybe')) x
    left join public.notification_prefs np on np.user_id = x.u
    where x.u is not null and coalesce(np.souvenirs, true) and private.souvenir_circle(e, x.u)
      and private.souvenir_viewer(e, x.u) loop
    perform public.queue_notification(u, 'souvenirs_revealed', e, '📸 Les souvenirs sont dévoilés',
      case when ev.souvenirs_keep then 'Les photos de « ' || ev.title || ' » sont à voir pendant 24 h.'
           else 'Les photos de « ' || ev.title || ' » sont à voir pendant 24 h, puis elles disparaissent.' end,
      'souvenirs_revealed:' || e || ':' || u, jsonb_build_object('url', '/?tab=events&event=' || e || '&souvenirs=1'));
    n := n + 1;
  end loop;
  return n;
end $$;
revoke all on function private.souvenir_reveal_run(uuid) from public, anon, authenticated;

create or replace function public.souvenir_reveal_now(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not ev.souvenirs_enabled or not private.souvenir_staff(e, me) then
    raise exception 'forbidden: le dévoilement est réservé à l''organisation' using errcode = '42501';
  end if;
  if ev.status <> 'published' then
    raise exception 'closed: événement annulé, les souvenirs ne sont pas dévoilés' using errcode = '22023';
  end if;
  if ev.starts_at is null or now() < private.souvenir_end(ev) then
    raise exception 'too_early: on ne dévoile jamais avant la fin de l''événement' using errcode = '22023';
  end if;
  if private.souvenir_phase(ev) in ('open', 'waiting') then
    perform set_config('party.souvenirs', 'on', true);
    update public.events set souvenirs_reveal_at = now() where id = e;
    perform set_config('party.souvenirs', '', true);
    perform private.souvenir_reveal_run(e);
  end if;
  return public.souvenir_counter(e);
end $$;

create or replace function private.souvenir_tick() returns void
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  -- 1. Dévoilement (fin + 24 h, ou avancé) et notification, une fois ; jamais un événement annulé.
  for ev in select x.* from public.events x
      where x.souvenirs_enabled and x.status = 'published' and x.starts_at is not null and private.souvenir_reveal_at(x) <= now()
        and not exists (select 1 from private.souvenir_runs r where r.event_id = x.id and r.revealed_at is not null) loop
    perform private.souvenir_reveal_run(ev.id);
  end loop;
  -- 2. Fin de la story sans « garder » : rien ne reste (fichiers à la corbeille par le déclencheur).
  for ev in select x.* from public.events x
      where x.starts_at is not null and not x.souvenirs_keep and private.souvenir_reveal_at(x) + interval '24 hours' <= now()
        and exists (select 1 from public.souvenir_photos p where p.event_id = x.id) loop
    delete from public.souvenir_photos p where p.event_id = ev.id;
    insert into private.souvenir_runs (event_id, purged_at) values (ev.id, now())
    on conflict (event_id) do update set purged_at = now();
  end loop;
  -- 3. Conservation : 13 mois.
  delete from public.souvenir_photos p where p.taken_at < now() - interval '13 months';
  delete from public.souvenir_seen s where s.seen_at < now() - interval '13 months';
  -- 4. Fichiers.
  perform private.souvenir_files_gc_now();
end $$;
revoke all on function private.souvenir_tick() from public, anon, authenticated;

-- ───────────── 5. Signalements en rafale ─────────────
create or replace function private.souvenir_reported() returns trigger
language plpgsql security definer set search_path = '' as $$
declare p public.souvenir_photos; u uuid;
begin
  if new.target_kind <> 'souvenir' then return null; end if;
  begin
    select * into p from public.souvenir_photos where id = new.target_id::uuid;
  exception when others then return null;
  end;
  if p.id is null then return null; end if;
  if tg_op = 'INSERT' then
    -- 5 photos masquées au plus par personne et par soirée : au-delà, la modération de Party seule (notify_new_report).
    if (select count(distinct r.target_id) from public.content_reports r
        where r.target_kind = 'souvenir' and r.reporter_id = new.reporter_id and r.id <> new.id
          and r.target_id <> new.target_id and r.snapshot ->> 'event_id' = p.event_id::text) >= 5 then
      return null;
    end if;
    update public.souvenir_photos set hidden_at = coalesce(hidden_at, now()) where id = p.id;
    for u in select ev.created_by from public.events ev where ev.id = p.event_id
             union select o.user_id from public.event_organizers o where o.event_id = p.event_id loop
      perform public.queue_notification(u, 'souvenir_reported', p.event_id, '🚩 Une photo Souvenirs a été signalée',
        'Elle est masquée en attendant : retire-la ou remets-la (fiche › Souvenirs).',
        'souvenir_reported:' || p.id || ':' || u, jsonb_build_object('photo_id', p.id,
          'url', '/?tab=events&event=' || p.event_id || '&souvenirs=review'));
    end loop;
  elsif new.status = 'dismissed' and old.status = 'open'
        and not exists (select 1 from public.content_reports r where r.target_kind = 'souvenir' and r.target_id = new.target_id
                        and r.status = 'open') then
    update public.souvenir_photos set hidden_at = null where id = p.id;
  end if;
  return null;
end $$;
revoke all on function private.souvenir_reported() from public, anon, authenticated;

notify pgrst, 'reload schema';
