-- Covoiturage dans un événement (avis 34d5c07f2e56 de l'admin, 11.11.2026).
-- Option de l'événement (events.carpool_enabled, éteinte par défaut, l'organisateur l'allume). Les participants (Présent
-- ou Peut-être) et les organisateurs : « Je conduis » (places, ville de départ facultative) ou « Je cherche une place »
-- (ville facultative) ; un passager monte dans une voiture, un conducteur prend quelqu'un qui cherche. Chacun voit qui
-- conduit, qui cherche, qui monte avec qui. Aucun argent, aucun texte libre sauf la ville (filtrée, CGU exigées).
-- Purement additive et rejouable.

alter table public.events add column if not exists carpool_enabled boolean not null default false;
comment on column public.events.carpool_enabled is 'Covoiturage proposé aux participants (option de l''organisateur, 13.11).';

create table if not exists public.event_carpool (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  role text not null check (role in ('driver', 'passenger')),
  seats int check (seats between 1 and 8),
  from_city text check (char_length(from_city) <= 60),
  driver_id uuid,
  created_at timestamptz not null default now(),
  primary key (event_id, user_id),
  constraint event_carpool_driver_fk foreign key (event_id, driver_id)
    references public.event_carpool (event_id, user_id) on delete set null (driver_id),
  constraint event_carpool_shape check (
    (role = 'driver' and seats is not null and driver_id is null) or (role = 'passenger' and seats is null)),
  constraint event_carpool_not_self check (driver_id is distinct from user_id)
);
comment on table public.event_carpool is
  'Covoiturage : un conducteur (places, ville) ou un passager (driver_id = sa voiture, vide = cherche une place).';
create index if not exists event_carpool_driver on public.event_carpool (event_id, driver_id);

-- Aucun accès direct : tout passe par les fonctions ci-dessous (places comptées sous verrou).
alter table public.event_carpool enable row level security;
revoke all on public.event_carpool from anon, authenticated;

-- Qui prend part au covoiturage : un organisateur, ou un participant (Présent / Peut-être) qui voit l'événement.
create or replace function private.carpool_member(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.events ev where ev.id = e and ev.carpool_enabled and ev.status = 'published')
    and (exists (select 1 from public.events ev where ev.id = e and ev.created_by = u)
         or exists (select 1 from public.event_organizers o where o.event_id = e and o.user_id = u)
         or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = u and r.status in ('yes', 'maybe')));
$$;
revoke all on function private.carpool_member(uuid, uuid) from public, anon, authenticated;

create or replace function private.carpool_guard(e uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null then raise exception 'forbidden: connecte-toi' using errcode = '42501'; end if;
  if not public.can_see_event(e) or not private.carpool_member(e, me) then
    raise exception 'forbidden: le covoiturage est réservé aux participants (Présent ou Peut-être)' using errcode = '42501';
  end if;
  if exists (select 1 from public.events ev where ev.id = e and coalesce(ev.ends_at, ev.starts_at, 'infinity') < now() - interval '12 hours') then
    raise exception 'L''événement est passé : le covoiturage est fermé';
  end if;
  return me;
end $$;
revoke all on function private.carpool_guard(uuid) from public, anon, authenticated;

create or replace function private.carpool_city(c text) returns text
language plpgsql security definer set search_path = '' as $$
declare t text := nullif(btrim(coalesce(c, '')), '');
begin
  if t is null then return null; end if;
  perform private.require_terms(auth.uid());
  return left(private.moderate_text(t, 'name'), 60);  -- comme un nom : une insulte est refusée, jamais masquée
end $$;
revoke all on function private.carpool_city(text) from public, anon, authenticated;

-- Le tableau du covoiturage, vu par la personne (sans les comptes bloqués avec elle).
create or replace function public.carpool(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); mine public.event_carpool;
begin
  if not exists (select 1 from public.events ev where ev.id = e and ev.carpool_enabled) or not public.can_see_event(e) then
    return jsonb_build_object('enabled', false);
  end if;
  if me is null or not private.carpool_member(e, me) then
    return jsonb_build_object('enabled', true, 'member', false);
  end if;
  select * into mine from public.event_carpool c where c.event_id = e and c.user_id = me;
  return jsonb_build_object('enabled', true, 'member', true,
    'me', case when mine.user_id is null then null
              else jsonb_build_object('id', me, 'role', mine.role, 'seats', mine.seats, 'from_city', mine.from_city, 'driver_id', mine.driver_id) end,
    'drivers', coalesce((select jsonb_agg(jsonb_build_object(
        'id', d.user_id, 'name', p.display_name, 'avatar_url', p.avatar_url, 'from_city', d.from_city, 'seats', d.seats,
        'passengers', coalesce((select jsonb_agg(jsonb_build_object('id', x.user_id, 'name', xp.display_name) order by x.created_at)
                                from public.event_carpool x join public.profiles xp on xp.id = x.user_id
                                where x.event_id = e and x.driver_id = d.user_id), '[]'::jsonb)) order by d.created_at)
      from public.event_carpool d join public.profiles p on p.id = d.user_id
      where d.event_id = e and d.role = 'driver' and not private.blocked_either(me, d.user_id)), '[]'::jsonb),
    'seekers', coalesce((select jsonb_agg(jsonb_build_object('id', s.user_id, 'name', p.display_name, 'avatar_url', p.avatar_url,
        'from_city', s.from_city) order by s.created_at)
      from public.event_carpool s join public.profiles p on p.id = s.user_id
      where s.event_id = e and s.role = 'passenger' and s.driver_id is null and not private.blocked_either(me, s.user_id)), '[]'::jsonb));
end $$;

-- « Je conduis » : places offertes (1 à 8) et ville de départ facultative ; jamais moins de places que de passagers.
create or replace function public.carpool_drive(e uuid, seats int, from_city text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := private.carpool_guard(e); taken int; city text := private.carpool_city(from_city);
begin
  if seats is null or seats < 1 or seats > 8 then raise exception 'De 1 à 8 places'; end if;
  perform 1 from public.event_carpool c where c.event_id = e and c.user_id = me for update;
  select count(*) into taken from public.event_carpool c where c.event_id = e and c.driver_id = me;
  if taken > seats then
    raise exception 'Tu as déjà % passagers : retire quelqu''un avant de réduire tes places', taken;
  end if;
  insert into public.event_carpool (event_id, user_id, role, seats, from_city, driver_id)
    values (e, me, 'driver', carpool_drive.seats, city, null)
  on conflict (event_id, user_id) do update set role = 'driver', seats = excluded.seats, from_city = excluded.from_city, driver_id = null;
  return public.carpool(e);
end $$;

-- « Je cherche une place » : un conducteur qui devient passager libère ses passagers (ils cherchent à nouveau).
create or replace function public.carpool_seek(e uuid, from_city text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := private.carpool_guard(e); city text := private.carpool_city(from_city);
begin
  update public.event_carpool c set driver_id = null where c.event_id = e and c.driver_id = me;
  insert into public.event_carpool (event_id, user_id, role, seats, from_city, driver_id) values (e, me, 'passenger', null, city, null)
  on conflict (event_id, user_id) do update set role = 'passenger', seats = null, from_city = excluded.from_city, driver_id = null;
  return public.carpool(e);
end $$;

-- Place libre dans une voiture, comptée sous verrou (deux personnes ne prennent jamais la même place).
create or replace function private.carpool_board(e uuid, driver uuid, passenger uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare d public.event_carpool; taken int;
begin
  if driver = passenger then raise exception 'C''est ta propre voiture'; end if;
  if private.blocked_either(driver, passenger) then raise exception 'forbidden: impossible' using errcode = '42501'; end if;
  if not private.carpool_member(e, passenger) then
    raise exception 'Cette personne ne participe plus à l''événement';
  end if;
  select * into d from public.event_carpool c where c.event_id = e and c.user_id = driver and c.role = 'driver' for update;
  if d.user_id is null then raise exception 'Cette voiture n''existe plus'; end if;
  select count(*) into taken from public.event_carpool c where c.event_id = e and c.driver_id = driver and c.user_id <> passenger;
  if taken >= d.seats then raise exception 'Plus de place dans cette voiture'; end if;
  update public.event_carpool c set driver_id = null where c.event_id = e and c.driver_id = passenger;  -- conducteur qui monte ailleurs
  insert into public.event_carpool (event_id, user_id, role, seats, from_city, driver_id) values (e, passenger, 'passenger', null, null, driver)
  on conflict (event_id, user_id) do update set role = 'passenger', seats = null, driver_id = driver;
end $$;
revoke all on function private.carpool_board(uuid, uuid, uuid) from public, anon, authenticated;

-- Un passager monte dans une voiture.
create or replace function public.carpool_take(e uuid, driver uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := private.carpool_guard(e);
begin
  perform private.carpool_board(e, driver, me);
  return public.carpool(e);
end $$;

-- Un conducteur prend quelqu'un qui cherche une place (seulement qui cherche : jamais quelqu'un d'autre).
create or replace function public.carpool_pick(e uuid, person uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := private.carpool_guard(e);
begin
  if not exists (select 1 from public.event_carpool c where c.event_id = e and c.user_id = person and c.role = 'passenger' and c.driver_id is null) then
    raise exception 'Cette personne ne cherche plus de place';
  end if;
  perform private.carpool_board(e, me, person);
  return public.carpool(e);
end $$;

-- Le conducteur fait descendre un passager (il cherche à nouveau une place).
create or replace function public.carpool_drop(e uuid, person uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := private.carpool_guard(e);
begin
  update public.event_carpool c set driver_id = null where c.event_id = e and c.user_id = person and c.driver_id = me;
  return public.carpool(e);
end $$;

-- Je ne fais plus partie du covoiturage (mes passagers cherchent à nouveau).
create or replace function public.carpool_leave(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null then raise exception 'forbidden: connecte-toi' using errcode = '42501'; end if;
  delete from public.event_carpool c where c.event_id = e and c.user_id = me;
  return public.carpool(e);
end $$;

revoke all on function public.carpool(uuid), public.carpool_drive(uuid, int, text), public.carpool_seek(uuid, text),
  public.carpool_take(uuid, uuid), public.carpool_pick(uuid, uuid), public.carpool_drop(uuid, uuid), public.carpool_leave(uuid)
  from public, anon;
grant execute on function public.carpool(uuid), public.carpool_drive(uuid, int, text), public.carpool_seek(uuid, text),
  public.carpool_take(uuid, uuid), public.carpool_pick(uuid, uuid), public.carpool_drop(uuid, uuid), public.carpool_leave(uuid)
  to authenticated;

-- Réponse « Pas présent » (ou retirée) : la personne quitte le covoiturage, ses passagers cherchent à nouveau.
create or replace function private.carpool_on_rsvp() returns trigger
language plpgsql security definer set search_path = '' as $$
declare r public.rsvps := case when tg_op = 'DELETE' then old else new end;
begin
  if (tg_op = 'DELETE' or new.status = 'no') and not exists (
      select 1 from public.events ev where ev.id = r.event_id and ev.created_by = r.user_id)
    and not exists (select 1 from public.event_organizers o where o.event_id = r.event_id and o.user_id = r.user_id) then
    delete from public.event_carpool c where c.event_id = r.event_id and c.user_id = r.user_id;
  end if;
  return null;
end $$;
revoke all on function private.carpool_on_rsvp() from public, anon, authenticated;
drop trigger if exists rsvps_carpool on public.rsvps;
create trigger rsvps_carpool after update of status or delete on public.rsvps
  for each row execute function private.carpool_on_rsvp();
