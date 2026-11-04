-- Zicou, pièces d'un événement (décision de l'admin du 4 novembre 2026). Purement additif et rejouable.
-- Prérequis : 20261104210000 (collection : cadeaux d'événement, présents) et 20261103140000 (rôles et droits).
--
-- Être présent à une soirée ou à un événement ne rapporte PLUS rien automatiquement, répondre à un événement non plus
-- (la migration 20261104230000 est devenue neutre ; app/pet.py n'a plus les sources « soiree » ni « rsvp »).
-- À la place, un droit « zicou.event_coins » (« Donner des pièces Zicou pour un événement »), donné au départ aux rôles
-- Admin et Co-admin : sur la page « Cadeaux Zicou » de l'événement, on active « Pièces pour les présents » avec un
-- montant borné (5 à 100). La base les verse UNE fois à chaque PRÉSENT (même définition que les cadeaux d'événement :
-- private.pet_drop_eligible, jamais selon un paiement) à la fin de l'événement (private.pet_drop_draw_at), avec un
-- journal (public.pet_event_coin_grants, une ligne par personne, unique). Le serveur Party les range dans le Zicou à
-- la prochaine ouverture (pet_load « coins »), puis les marque (pet_event_coins_claim) : jamais versées deux fois.
-- Sans le droit : rien n'est visible (pet_event_coins_get ne renvoie que ses propres pièces reçues).
--
-- 1. Droit ; 2. réglage et journal ; 3. réglage (lire, fixer) ; 4. versement ; 5. pet_load (sans « events » ni
-- « answers », plus « coins ») et marque.

-- 1. Droit ----------------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('zicou.event_coins', 'Zicou', 'Donner des pièces Zicou pour un événement',
   'Sur la page des cadeaux Zicou d''un événement : des pièces (5 à 100) pour chaque présent, versées une fois à la fin', 80)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'zicou_event_coins_2026_11_05') then
    return;
  end if;
  insert into public.role_permissions (role, perm)
    select r.key, 'zicou.event_coins' from public.roles r where r.key in ('admin', 'coadmin')
  on conflict do nothing;
  insert into private.one_time_changes (name) values ('zicou_event_coins_2026_11_05');
end $$;

-- 2. Réglage et journal ---------------------------------------------------------------------------------------------
create table if not exists public.pet_event_coins (
  event_id uuid primary key references public.events(id) on delete cascade,
  coins integer not null check (coins between 5 and 100),
  set_by uuid references public.profiles(id) on delete set null,
  set_at timestamptz not null default now()
);
alter table public.pet_event_coins enable row level security;
revoke all on public.pet_event_coins from anon, authenticated;

create table if not exists public.pet_event_coin_grants (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  coins integer not null check (coins between 5 and 100),
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  unique (event_id, user_id)
);
create index if not exists pet_event_coin_grants_user on public.pet_event_coin_grants (user_id) where claimed_at is null;
alter table public.pet_event_coin_grants enable row level security;
revoke all on public.pet_event_coin_grants from anon, authenticated;

-- Après la fin de l'événement, les présents notés plus tard reçoivent encore leurs pièces pendant 7 jours.
create or replace function private.pet_event_coins_open_until(e uuid) returns timestamptz
language sql stable security definer set search_path = '' as $$
  select private.pet_drop_draw_at(e) + interval '7 days';
$$;
revoke all on function private.pet_event_coins_open_until(uuid) from public, anon, authenticated;

-- 3. Réglage ---------------------------------------------------------------------------------------------------------
create or replace function public.pet_event_coins_get(p_event uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare allowed boolean := public.has_perm('zicou.event_coins'); c public.pet_event_coins;
begin
  if auth.uid() is null or not public.can_see_event(p_event) then
    raise exception 'forbidden: Événement introuvable.' using errcode = '42501';
  end if;
  select * into c from public.pet_event_coins where event_id = p_event;
  return jsonb_build_object(
    'allowed', allowed,
    'mine', (select g.coins from public.pet_event_coin_grants g where g.event_id = p_event and g.user_id = auth.uid()),
    'setting', case when allowed then jsonb_build_object(
        'coins', c.coins, 'set_at', c.set_at, 'min', 5, 'max', 100,
        'pay_at', private.pet_drop_draw_at(p_event),
        'open_until', private.pet_event_coins_open_until(p_event),
        'late', now() > private.pet_event_coins_open_until(p_event),
        'given', (select count(*) from public.pet_event_coin_grants g where g.event_id = p_event),
        'eligible_now', (select count(*) from private.pet_drop_eligible(p_event))) end);
end $$;

-- 4. Versement (interne) : chaque présent pas encore servi, une fois ; journal = pet_event_coin_grants.
create or replace function private.pet_event_coins_grant(p_event uuid) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare c public.pet_event_coins; n integer;
begin
  perform pg_advisory_xact_lock(hashtextextended('pet_coins:' || p_event::text, 0));
  select * into c from public.pet_event_coins where event_id = p_event;
  if c.event_id is null or private.pet_drop_draw_at(p_event) > now()
     or now() > private.pet_event_coins_open_until(p_event)
     or not exists (select 1 from public.events where id = p_event and status = 'published') then
    return 0;
  end if;
  insert into public.pet_event_coin_grants (event_id, user_id, coins)
    select p_event, u, c.coins from private.pet_drop_eligible(p_event) u
  on conflict (event_id, user_id) do nothing;
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function private.pet_event_coins_grant(uuid) from public, anon, authenticated;

-- Fixer le montant (p_coins entre 5 et 100) ou l'enlever (null). Refusé dès qu'une pièce a été versée (plus rien ne
-- change : chacun reçoit le même montant) et après la fenêtre de 7 jours. Versé tout de suite si l'événement est fini.
create or replace function public.pet_event_coins_set(p_event uuid, p_coins integer) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.has_perm('zicou.event_coins') then
    raise exception 'forbidden: Réservé aux personnes qui ont le droit « Donner des pièces Zicou pour un événement ».'
      using errcode = '42501';
  end if;
  if not exists (select 1 from public.events where id = p_event) or not public.can_see_event(p_event) then
    raise exception 'forbidden: Événement introuvable.' using errcode = '42501';
  end if;
  if p_coins is not null and (p_coins < 5 or p_coins > 100) then
    raise exception 'invalid: De 5 à 100 pièces par présent.';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('pet_coins:' || p_event::text, 0));
  if exists (select 1 from public.pet_event_coin_grants where event_id = p_event) then
    raise exception 'frozen: Les pièces sont déjà versées : le montant ne change plus.';
  end if;
  if now() > private.pet_event_coins_open_until(p_event) then
    raise exception 'invalid: Trop tard : l''événement est fini depuis plus de 7 jours.';
  end if;
  if p_coins is null then
    delete from public.pet_event_coins where event_id = p_event;
  else
    insert into public.pet_event_coins (event_id, coins, set_by) values (p_event, p_coins, auth.uid())
    on conflict (event_id) do update set coins = excluded.coins, set_by = excluded.set_by, set_at = now();
  end if;
  perform private.audit('pet.event_coins', null, jsonb_build_object('event', p_event, 'coins', p_coins));
  perform private.pet_event_coins_grant(p_event);
  return public.pet_event_coins_get(p_event);
end $$;

revoke all on function public.pet_event_coins_get(uuid), public.pet_event_coins_set(uuid, integer) from public, anon;
grant execute on function public.pet_event_coins_get(uuid), public.pet_event_coins_set(uuid, integer) to authenticated;

-- Événements à servir (cron toutes les 10 min, et à l'ouverture de Zicou pour ses propres événements).
create or replace function private.pet_event_coins_due(only_for uuid default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare e uuid; n integer := 0;
begin
  for e in select c.event_id from public.pet_event_coins c
            where private.pet_drop_draw_at(c.event_id) <= now() and now() <= private.pet_event_coins_open_until(c.event_id)
              and (only_for is null or only_for in (select private.pet_drop_eligible(c.event_id)))
              and (only_for is null or not exists (select 1 from public.pet_event_coin_grants g
                                                    where g.event_id = c.event_id and g.user_id = only_for)) loop
    n := n + private.pet_event_coins_grant(e);
  end loop;
  return n;
end $$;
revoke all on function private.pet_event_coins_due(uuid) from public, anon, authenticated;

-- Comme 20261104210000, plus le versement des pièces d'événement (même cron « pet-event-draw », même pet_load).
create or replace function private.pet_event_draw_due(only_for uuid default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare e uuid; n integer := 0;
begin
  for e in select d.event_id from public.pet_event_drops d
            where d.status = 'published' and private.pet_drop_draw_at(d.event_id) <= now()
              and (only_for is null or only_for in (select private.pet_drop_eligible(d.event_id))) loop
    n := n + private.pet_event_draw(e);
  end loop;
  return n + private.pet_event_coins_due(only_for);
end $$;
revoke all on function private.pet_event_draw_due(uuid) from public, anon, authenticated;

-- 5. Pièces rangées par le serveur dans le Zicou (après l'enregistrement du personnage).
create or replace function public.pet_event_coins_claim(p_ids uuid[], p_key text default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := private.pet_server_guard(p_key); n integer;
begin
  update public.pet_event_coin_grants set claimed_at = now()
   where user_id = me and claimed_at is null and id = any(coalesce(p_ids, '{}'));
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.pet_event_coins_claim(uuid[], text) from public, anon;
grant execute on function public.pet_event_coins_claim(uuid[], text) to authenticated;

-- Chargement : comme 20261104210000, sans « events » (présence) ni « answers » (réponses) qui ne rapportent plus rien,
-- plus « coins » : mes pièces d'événement pas encore rangées.
create or replace function public.pet_load(p_src text default null, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  today date := (now() at time zone 'Europe/Zurich')::date;
begin
  if p_src in ('tab', 'notification', 'widget', 'link') then
    insert into public.pet_opens as o (user_id, day, src) values (me, today, jsonb_build_object(p_src, 1))
    on conflict (user_id, day) do update
      set n = o.n + 1, last_at = now(),
          src = o.src || jsonb_build_object(p_src, coalesce((o.src ->> p_src)::integer, 0) + 1);
    perform private.pet_event_draw_due(me);
  end if;
  update public.pets set last_seen_at = now() where user_id = me;
  return jsonb_build_object(
    'pet', (select jsonb_build_object('life', p.life, 'owner', p.owner, 'version', p.version)
              from public.pets p where p.user_id = me),
    'gifts', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'kind', g.kind, 'created_at', g.created_at,
                                                            'from_name', coalesce(pr.display_name, 'Un ami')) order by g.created_at)
                         from public.pet_gifts g left join public.profiles pr on pr.id = g.from_user
                        where g.to_user = me and g.applied_at is null), '[]'::jsonb),
    'brain', coalesce((select jsonb_agg(b.played_at order by b.played_at)
                         from (select played_at from public.brain_sessions
                                where user_id = me and played_at > now() - interval '48 hours'
                                order by played_at desc limit 20) b), '[]'::jsonb),
    'items', coalesce((select jsonb_agg(private.pet_item_json(i) order by i.minted_at)
                         from public.pet_items i where i.owner_id = me), '[]'::jsonb),
    'mythic_left', coalesce((select jsonb_object_agg(c.id, c.edition - (select count(*) from public.pet_items i where i.item = c.id))
                               from public.pet_catalog c where c.rarity = 'mythic'), '{}'::jsonb),
    'awards', coalesce((select jsonb_agg(jsonb_build_object('id', a.id, 'event_id', a.event_id, 'event', e.title,
                                'item', a.item, 'prize', a.prize, 'roll', a.roll, 'instance', a.instance_id) order by a.created_at)
                          from public.pet_event_awards a join public.events e on e.id = a.event_id
                         where a.user_id = me and a.claimed_at is null), '[]'::jsonb),
    'coins', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'event_id', g.event_id, 'event', e.title,
                                'coins', g.coins) order by g.created_at)
                         from public.pet_event_coin_grants g join public.events e on e.id = g.event_id
                        where g.user_id = me and g.claimed_at is null), '[]'::jsonb));
end;
$$;
revoke all on function public.pet_load(text, text) from public, anon;
grant execute on function public.pet_load(text, text) to authenticated;

notify pgrst, 'reload schema';
