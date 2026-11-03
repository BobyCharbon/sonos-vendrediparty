-- Billets dans Apple Wallet (Cartes Apple) qui se mettent à jour tout seuls (demande de l'admin, 3 novembre 2026) :
-- « Ajouter à Apple Wallet » sous le billet, puis le pass suit les changements : arrivée scannée, paiement confirmé,
-- nouveau QR, événement modifié (titre, date, lieu), annulé ou plus noté Présent (pass « annulé » dans Cartes).
--
-- PassKit Web Service (developer.apple.com/documentation/walletpasses) : l'iPhone parle au serveur Party, sans
-- session Supabase. Chaque pass a donc son propre jeton (authenticationToken, aléatoire) ; le serveur relit le billet
-- par ce jeton (fonctions ci-dessous), jamais autrement. Les appareils qui ont ajouté le pass s'inscrivent
-- (identifiant de l'appareil + jeton de push) ; à chaque changement, le serveur leur envoie un push vide et ils
-- redemandent la liste des pass modifiés, puis le pass.
-- Les déclencheurs datent chaque modification (wallet_passes.updated_at) ; l'envoi des push est demandé au serveur par
-- l'écran qui fait le changement (wallet_push_targets : seulement ce que la personne connectée a le droit de toucher).
-- Tables fermées : aucun accès direct, tout passe par les fonctions. Purement additif et rejouable.

-- --------------------------------------------------------------------------------------------------------------
-- 1. Tables
-- --------------------------------------------------------------------------------------------------------------
create table if not exists public.wallet_passes (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  auth_token text not null unique check (auth_token ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (event_id, user_id)
);
alter table public.wallet_passes enable row level security;
revoke all on public.wallet_passes from public, anon, authenticated;

create table if not exists public.wallet_devices (
  device_id text not null check (device_id ~ '^[A-Za-z0-9._-]{1,128}$'),
  event_id uuid not null,
  user_id uuid not null,
  push_token text not null check (push_token ~ '^[0-9A-Fa-f]{16,200}$'),
  created_at timestamptz not null default now(),
  primary key (device_id, event_id, user_id),
  foreign key (event_id, user_id) references public.wallet_passes (event_id, user_id) on delete cascade
);
create index if not exists wallet_devices_pass on public.wallet_devices (event_id, user_id);
alter table public.wallet_devices enable row level security;
revoke all on public.wallet_devices from public, anon, authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 2. Ce que le pass montre (jamais d'autre billet que celui du jeton)
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.wallet_payload(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'serial', w.event_id::text || '.' || w.user_id::text,
    'user_id', w.user_id,
    'auth_token', w.auth_token,
    'updated_at', w.updated_at,
    -- Pass valable : noté Présent (hors liste d'attente) à un événement publié, billet en place.
    'valid', coalesce(r.status = 'yes' and not coalesce(r.waitlisted, false) and ev.status = 'published' and t.token is not null, false),
    'holder', p.display_name,
    'event', jsonb_build_object('id', ev.id, 'title', ev.title, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at,
      'all_day', ev.all_day, 'location_name', ev.location_name, 'location_address', ev.location_address,
      'location_url', ev.location_url, 'status', ev.status),
    'ticket', jsonb_build_object('token', t.token, 'code', t.code, 'plus_ones', coalesce(r.plus_ones, 0),
      'checked_in_at', t.checked_in_at, 'paid', coalesce(t.paid, false), 'price_chf', ev.price_chf))
  from public.wallet_passes w
  join public.events ev on ev.id = w.event_id
  left join public.rsvps r on r.event_id = w.event_id and r.user_id = w.user_id
  left join public.event_tickets t on t.event_id = w.event_id and t.user_id = w.user_id
  left join public.profiles p on p.id = w.user_id
  where w.event_id = e and w.user_id = member;
$$;

create or replace function private.wallet_pass_of(tok text, serial text) returns public.wallet_passes
language sql stable security definer set search_path = '' as $$
  select w.* from public.wallet_passes w
  where tok ~ '^[0-9a-f]{64}$' and w.auth_token = tok and w.event_id::text || '.' || w.user_id::text = serial;
$$;

revoke all on function private.wallet_payload(uuid, uuid), private.wallet_pass_of(text, text) from public, anon, authenticated;

-- Mon pass (personne connectée, notée Présente) : crée son jeton à la première demande, toujours le même ensuite.
create or replace function public.wallet_pass_issue(e uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if public.my_event_ticket(e) ->> 'state' is distinct from 'ok' then  -- même règle que pour afficher son billet
    raise exception 'Pas de billet pour cet événement : il faut être noté Présent.' using errcode = '22023';
  end if;
  insert into public.wallet_passes (event_id, user_id, auth_token) values (e, me, private.new_ticket_token())
    on conflict (event_id, user_id) do nothing;
  return private.wallet_payload(e, me);
end $$;

-- Le pass par son jeton (appel du serveur pour l'iPhone, sans session) ; null si le jeton ne correspond pas.
create or replace function public.wallet_pass_by_token(tok text, serial text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select private.wallet_payload(w.event_id, w.user_id) from private.wallet_pass_of(tok, serial) w where w.event_id is not null;
$$;

-- --------------------------------------------------------------------------------------------------------------
-- 3. Appareils (PassKit Web Service)
-- --------------------------------------------------------------------------------------------------------------
-- Résultat : 'created', 'exists' ou 'unauthorized'. Au plus 10 appareils par pass.
create or replace function public.wallet_register(tok text, serial text, device text, push text) returns text
language plpgsql volatile security definer set search_path = '' as $$
declare w public.wallet_passes;
begin
  w := private.wallet_pass_of(tok, serial);
  if w.event_id is null then return 'unauthorized'; end if;
  if device is null or device !~ '^[A-Za-z0-9._-]{1,128}$' or push is null or push !~ '^[0-9A-Fa-f]{16,200}$' then
    raise exception 'Appareil ou jeton de push invalide' using errcode = '22023';
  end if;
  update public.wallet_devices d set push_token = push
    where d.device_id = device and d.event_id = w.event_id and d.user_id = w.user_id;
  if found then return 'exists'; end if;
  if (select count(*) from public.wallet_devices d where d.event_id = w.event_id and d.user_id = w.user_id) >= 10 then
    raise exception 'Trop d''appareils pour ce billet' using errcode = '22023';
  end if;
  insert into public.wallet_devices (device_id, event_id, user_id, push_token) values (device, w.event_id, w.user_id, push)
    on conflict do nothing;
  return 'created';
end $$;

create or replace function public.wallet_unregister(tok text, serial text, device text) returns boolean
language plpgsql volatile security definer set search_path = '' as $$
declare w public.wallet_passes;
begin
  w := private.wallet_pass_of(tok, serial);
  if w.event_id is null then return false; end if;
  delete from public.wallet_devices d where d.device_id = device and d.event_id = w.event_id and d.user_id = w.user_id;
  return true;
end $$;

-- Pass de cet appareil modifiés depuis « since » (null : tous) : { serials, last_updated }.
create or replace function public.wallet_updated_serials(device text, since timestamptz default null) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'serials', coalesce(jsonb_agg(w.event_id::text || '.' || w.user_id::text) filter (where since is null or w.updated_at > since), '[]'::jsonb),
    'last_updated', max(w.updated_at))
  from public.wallet_devices d
  join public.wallet_passes w on w.event_id = d.event_id and w.user_id = d.user_id
  where d.device_id = device;
$$;

-- Jetons de push à prévenir après un changement : son propre pass ; celui d'un participant ou de tout l'événement
-- pour qui gère l'entrée (organisateur, co-organisateur, admin, droit « Scanner les billets » : private.can_scan).
create or replace function public.wallet_push_targets(e uuid, member uuid default null) returns setof text
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if member is distinct from auth.uid() and not private.can_scan(e) then
    raise exception 'Seuls les organisateurs de l''événement préviennent les billets.' using errcode = '42501';
  end if;
  return query select distinct d.push_token from public.wallet_devices d
    where d.event_id = e and (member is null or d.user_id = member);
end $$;

revoke all on function public.wallet_pass_issue(uuid), public.wallet_pass_by_token(text, text),
  public.wallet_register(text, text, text, text), public.wallet_unregister(text, text, text),
  public.wallet_updated_serials(text, timestamptz), public.wallet_push_targets(uuid, uuid) from public, anon, authenticated;
grant execute on function public.wallet_pass_issue(uuid), public.wallet_push_targets(uuid, uuid) to authenticated;
-- Appels de l'iPhone (via le serveur, sans session) : seulement avec le jeton du pass ou l'identifiant de l'appareil.
grant execute on function public.wallet_pass_by_token(text, text), public.wallet_register(text, text, text, text),
  public.wallet_unregister(text, text, text), public.wallet_updated_serials(text, timestamptz) to anon, authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 4. Date de modification des pass (ce que le pass montre a changé)
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.wallet_touch_member() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    update public.wallet_passes set updated_at = now() where event_id = old.event_id and user_id = old.user_id;
  else
    update public.wallet_passes set updated_at = now() where event_id = new.event_id and user_id = new.user_id;
  end if;
  return null;
end $$;

create or replace function private.wallet_touch_event() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.wallet_passes set updated_at = now() where event_id = new.id;
  return null;
end $$;

create or replace function private.wallet_touch_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.wallet_passes set updated_at = now() where user_id = new.id;
  return null;
end $$;

revoke all on function private.wallet_touch_member(), private.wallet_touch_event(), private.wallet_touch_profile()
  from public, anon, authenticated;

drop trigger if exists wallet_touch on public.event_tickets;
create trigger wallet_touch after update on public.event_tickets for each row
  when (old.token is distinct from new.token or old.code is distinct from new.code
     or old.checked_in_at is distinct from new.checked_in_at or old.paid is distinct from new.paid)
  execute function private.wallet_touch_member();

drop trigger if exists wallet_touch on public.rsvps;
create trigger wallet_touch after update on public.rsvps for each row
  when (old.status is distinct from new.status or old.waitlisted is distinct from new.waitlisted
     or old.plus_ones is distinct from new.plus_ones)
  execute function private.wallet_touch_member();

drop trigger if exists wallet_touch_delete on public.rsvps;
create trigger wallet_touch_delete after delete on public.rsvps for each row
  execute function private.wallet_touch_member();

drop trigger if exists wallet_touch on public.events;
create trigger wallet_touch after update on public.events for each row
  when (old.title is distinct from new.title or old.starts_at is distinct from new.starts_at
     or old.ends_at is distinct from new.ends_at or old.all_day is distinct from new.all_day
     or old.location_name is distinct from new.location_name or old.location_address is distinct from new.location_address
     or old.location_url is distinct from new.location_url or old.status is distinct from new.status
     or old.price_chf is distinct from new.price_chf)
  execute function private.wallet_touch_event();

drop trigger if exists wallet_touch on public.profiles;
create trigger wallet_touch after update on public.profiles for each row
  when (old.display_name is distinct from new.display_name)
  execute function private.wallet_touch_profile();

notify pgrst, 'reload schema';
