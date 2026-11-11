-- Bar de la soirée (maquettes v6 validées par l'admin le 10.11.2026) : un bar rattaché à UN événement.
-- - Organisateurs (créateur, co-organisateurs, admin) : articles (prix CHF, stock acheté, âge mini, maximum « en attente »
--   par personne), conditions de remboursement (bénéficiaire, moyen, date limite), barmans, précommande, fermeture.
-- - Invité « Présent » au profil complet : commande en cochant l'engagement à rembourser (texte exact gardé), voit son
--   solde, annule ce qui n'est pas servi. Rien n'est dû avant le service au bar ; le prix est figé à la commande.
-- - Barman (nommé pour CETTE soirée) : scanne le QR unique (le même jeton que le billet : event_tickets), choisit les
--   quantités, « Servir » → débité, stock décompté ; annulation par lui pendant 15 s, ensuite correction par un organisateur.
-- - STOCK VIRTUEL BLOQUANT : disponible = stock − servis − en attente ; verrous « for update » sur les articles (ordre des id).
-- - Précommande (si l'organisateur l'ouvre) : sans maximum par personne, mais dans le stock s'il est fixé.
-- - Notifications instantanées (bar_served, bar_changed, bar_refund_declared, bar_refund_confirmed), chacune avec son
--   interrupteur ; fermeture automatique (pg_cron) qui annule ce qui reste en attente ; purge 6 mois après la fermeture.
-- Aucun lien avec Zicou ni les jeux (préfixe bar_ / event_bar_, jamais pet_). Purement additif et rejouable.

-- 1. Tables (fermées : RLS sans politique, tout passe par les fonctions ci-dessous) ----------------------------------
create table if not exists public.event_bars (
  event_id uuid primary key references public.events (id) on delete cascade,
  created_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  orders_open boolean not null default false,
  preorder_enabled boolean not null default false,
  preorder_until timestamptz,
  closes_at timestamptz not null,
  closed_at timestamptz,
  payee_id uuid references public.profiles (id) on delete set null,
  pay_method text not null default 'revolut' check (pay_method in ('revolut', 'twint', 'iban')),
  repay_by date,
  terms_version int not null default 1 check (terms_version >= 1)
);

create table if not exists public.event_bar_items (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 40),
  emoji text check (emoji is null or char_length(emoji) <= 8),
  price_chf numeric(7, 2) not null check (price_chf >= 0 and price_chf <= 500),
  stock int check (stock is null or stock between 0 and 100000),
  age_min int not null default 0 check (age_min in (0, 16, 18)),
  max_pending int check (max_pending is null or max_pending between 1 and 50),
  sort int not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists event_bar_items_event on public.event_bar_items (event_id, sort);

-- Engagement à rembourser, coché à CHAQUE commande : le texte exact accepté est gardé (jamais modifié).
create table if not exists public.event_bar_pledges (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  accepted_at timestamptz not null default now(),
  text text not null,
  terms_version int not null
);
create index if not exists event_bar_pledges_user on public.event_bar_pledges (event_id, user_id, accepted_at desc);

-- Une ligne = un verre (prix figé à la commande).
create table if not exists public.event_bar_units (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  item_id uuid not null references public.event_bar_items (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  pledge_id uuid references public.event_bar_pledges (id) on delete set null,
  price_chf numeric(7, 2) not null check (price_chf >= 0),
  preorder boolean not null default false,
  status text not null default 'pending' check (status in ('pending', 'served', 'cancelled', 'corrected')),
  ordered_at timestamptz not null default now(),
  served_at timestamptz,
  served_by uuid references public.profiles (id) on delete set null,
  serve_id uuid,
  cancelled_at timestamptz,
  cancelled_by uuid references public.profiles (id) on delete set null,
  cancel_reason text check (cancel_reason is null or cancel_reason in ('mine', 'organizer', 'closed', 'removed')),
  corrected_at timestamptz,
  corrected_by uuid references public.profiles (id) on delete set null
);
create index if not exists event_bar_units_item on public.event_bar_units (item_id, status);
create index if not exists event_bar_units_person on public.event_bar_units (event_id, user_id, status);
create index if not exists event_bar_units_serve on public.event_bar_units (serve_id);

-- Un passage au bar (un « Servir ») : client_key unique → un double toucher ou une reprise réseau rend le même résultat.
create table if not exists public.event_bar_serves (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  served_by uuid references public.profiles (id) on delete set null,
  served_at timestamptz not null default now(),
  total_chf numeric(9, 2) not null,
  client_key text not null unique check (char_length(client_key) between 8 and 80),
  undone_at timestamptz,
  undone_by uuid references public.profiles (id) on delete set null
);

create table if not exists public.event_bar_refunds (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  amount_chf numeric(9, 2) not null check (amount_chf > 0),
  declared_at timestamptz not null default now(),
  status text not null default 'declared' check (status in ('declared', 'confirmed', 'rejected')),
  confirmed_at timestamptz,
  confirmed_by uuid references public.profiles (id) on delete set null
);
create index if not exists event_bar_refunds_person on public.event_bar_refunds (event_id, user_id, status);

create table if not exists public.event_bar_staff (
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  added_by uuid references public.profiles (id) on delete set null,
  added_at timestamptz not null default now(),
  primary key (event_id, user_id)
);

-- Journal (qui, quand, quoi) : ajouts seulement.
create table if not exists public.event_bar_log (
  id bigint generated always as identity primary key,
  event_id uuid not null references public.event_bars (event_id) on delete cascade,
  at timestamptz not null default now(),
  actor uuid references public.profiles (id) on delete set null,
  kind text not null,
  user_id uuid references public.profiles (id) on delete set null,
  item_id uuid references public.event_bar_items (id) on delete set null,
  qty int,
  amount numeric(9, 2),
  data jsonb not null default '{}'::jsonb
);
create index if not exists event_bar_log_event on public.event_bar_log (event_id, at desc);

do $$ declare t text; begin
  foreach t in array array['event_bars', 'event_bar_items', 'event_bar_pledges', 'event_bar_units', 'event_bar_serves',
                           'event_bar_refunds', 'event_bar_staff', 'event_bar_log'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
  end loop;
end $$;

-- Interrupteurs des notifications du bar (activés par défaut).
alter table public.notification_prefs add column if not exists bar_served boolean not null default true;
alter table public.notification_prefs add column if not exists bar_changed boolean not null default true;
alter table public.notification_prefs add column if not exists bar_refund_declared boolean not null default true;
alter table public.notification_prefs add column if not exists bar_refund_confirmed boolean not null default true;

-- 2. Gardes : prix, personne et article d'un verre immuables ; transitions permises seulement ---------------------
create or replace function private.guard_bar_unit() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.price_chf is distinct from old.price_chf or new.user_id is distinct from old.user_id
     or new.item_id is distinct from old.item_id or new.event_id is distinct from old.event_id
     or new.ordered_at is distinct from old.ordered_at or new.pledge_id is distinct from old.pledge_id then
    raise exception 'forbidden: un verre commandé ne change ni de prix, ni de personne, ni d''article' using errcode = '42501';
  end if;
  if new.status is distinct from old.status and not (
       (old.status = 'pending' and new.status in ('served', 'cancelled'))
    or (old.status = 'served' and new.status in ('pending', 'corrected'))) then
    raise exception 'forbidden: passage % → % refusé', old.status, new.status using errcode = '42501';
  end if;
  return new;
end $$;
drop trigger if exists guard_bar_unit on public.event_bar_units;
create trigger guard_bar_unit before update on public.event_bar_units for each row execute function private.guard_bar_unit();

create or replace function private.guard_bar_append_only() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Engagements et journal : jamais modifiés ; effacés seulement par la purge ou en cascade (bar, compte supprimés).
  if tg_op = 'UPDATE' or (tg_op = 'DELETE' and coalesce(current_setting('party.bar_purge', true), '') <> 'on'
                          and pg_trigger_depth() = 1) then
    raise exception 'forbidden: % est un registre en ajout seul', tg_table_name using errcode = '42501';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;
drop trigger if exists guard_bar_pledge on public.event_bar_pledges;
create trigger guard_bar_pledge before update or delete on public.event_bar_pledges for each row execute function private.guard_bar_append_only();
drop trigger if exists guard_bar_log on public.event_bar_log;
create trigger guard_bar_log before update or delete on public.event_bar_log for each row execute function private.guard_bar_append_only();

-- 3. Règles -------------------------------------------------------------------------------------------------------
create or replace function private.bar_can_manage(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (public.is_admin() or public.is_organizer(e));
$$;

create or replace function private.bar_is_present(e uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = uid and r.status = 'yes' and not r.waitlisted);
$$;

create or replace function private.bar_can_serve(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.bar_can_manage(e)
    or (exists (select 1 from public.event_bar_staff s where s.event_id = e and s.user_id = auth.uid())
        and private.bar_is_present(e, auth.uid()));
$$;

-- Peut commander : compte actif au profil complet, noté Présent (hors liste d'attente), événement publié.
create or replace function private.bar_eligible(e uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_account_active(uid) and private.identity_complete(uid) and private.bar_is_present(e, uid)
    and exists (select 1 from public.events ev where ev.id = e and ev.status = 'published');
$$;

create or replace function private.bar_phase(b public.event_bars) returns text
language sql stable set search_path = '' as $$
  select case
    when b.closed_at is not null or now() >= b.closes_at then 'closed'
    when b.orders_open then 'open'
    when b.preorder_enabled and (b.preorder_until is null or now() < b.preorder_until) then 'preorder'
    else 'waiting' end;
$$;

create or replace function private.bar_method_label(m text) returns text
language sql immutable set search_path = '' as $$
  select case m when 'twint' then 'Twint' when 'iban' then 'virement bancaire' else 'Revolut' end;
$$;

create or replace function private.bar_date_fr(d date) returns text
language sql immutable set search_path = '' as $$
  select extract(day from d)::int || ' ' || (array['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
    'septembre', 'octobre', 'novembre', 'décembre'])[extract(month from d)::int] || ' ' || extract(year from d)::int;
$$;

-- Texte d'engagement, construit par la base : l'écran l'affiche et le renvoie tel quel (comparé à la commande).
create or replace function private.bar_pledge_text(b public.event_bars) returns text
language sql stable security definer set search_path = '' as $$
  select 'Je m''engage à rembourser à ' || coalesce(nullif(btrim(p.display_name), ''), 'l''organisateur')
    || ', par ' || private.bar_method_label(b.pay_method)
    || case when b.repay_by is not null then ', avant le ' || private.bar_date_fr(b.repay_by) else ', après la soirée' end
    || ', chaque consommation servie à mon nom.'
  from (select 1) x left join public.profiles p on p.id = b.payee_id;
$$;

create or replace function private.bar_counts(item uuid) returns table (served bigint, pending bigint)
language sql stable security definer set search_path = '' as $$
  select count(*) filter (where u.status = 'served'), count(*) filter (where u.status = 'pending')
  from public.event_bar_units u where u.item_id = item;
$$;

create or replace function private.bar_balance(e uuid, uid uuid) returns numeric
language sql stable security definer set search_path = '' as $$
  select coalesce((select sum(u.price_chf) from public.event_bar_units u where u.event_id = e and u.user_id = uid and u.status = 'served'), 0)
       - coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = uid and r.status = 'confirmed'), 0);
$$;

drop function if exists private.bar_log(uuid, text, uuid, uuid, int, numeric, jsonb);  -- première écriture (int), jamais déployée
create or replace function private.bar_log(e uuid, kind text, member uuid, item uuid, qty bigint, amount numeric, data jsonb default '{}'::jsonb)
returns void language sql security definer set search_path = '' as $$
  insert into public.event_bar_log (event_id, actor, kind, user_id, item_id, qty, amount, data)
  values (e, auth.uid(), kind, member, item, qty, amount, coalesce(data, '{}'::jsonb));
$$;

create or replace function private.bar_chf(n numeric) returns text
language sql immutable set search_path = '' as $$
  select case when n = trunc(n) then trunc(n)::text else to_char(n, 'FM999990.00') end || ' CHF';
$$;

create or replace function private.bar_require(e uuid) returns public.event_bars
language plpgsql stable security definer set search_path = '' as $$
declare b public.event_bars;
begin
  select * into b from public.event_bars where event_id = e;
  if b.event_id is null then raise exception 'not_found: pas de bar pour cet événement' using errcode = 'P0002'; end if;
  return b;
end $$;

-- 4. Fermeture : tout ce qui reste en attente est annulé (rien à payer), chacun est prévenu -----------------------
create or replace function private.bar_close(e uuid) returns int
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; ev public.events; n int := 0; who record;
begin
  select * into b from public.event_bars where event_id = e for update skip locked;
  if b.event_id is null or b.closed_at is not null then return 0; end if;
  select * into ev from public.events where id = e;
  for who in select u.user_id, count(*) c from public.event_bar_units u where u.event_id = e and u.status = 'pending' group by u.user_id loop
    update public.event_bar_units set status = 'cancelled', cancelled_at = now(), cancel_reason = 'closed'
      where event_id = e and user_id = who.user_id and status = 'pending';
    n := n + who.c;
    perform public.queue_notification(who.user_id, 'bar_changed', e, ev.title,
      'Le bar est fermé : ' || who.c || case when who.c > 1 then ' verres en attente annulés' else ' verre en attente annulé' end || ', rien à payer pour eux.',
      'bar_closed:' || e || ':' || who.user_id);
  end loop;
  update public.event_bars set closed_at = now(), orders_open = false where event_id = e;
  insert into public.event_bar_log (event_id, actor, kind, qty) values (e, auth.uid(), 'closed', n);
  return n;
end $$;

create or replace function private.close_due_bars() returns int
language plpgsql security definer set search_path = '' as $$
declare e uuid; n int := 0;
begin
  for e in select b.event_id from public.event_bars b join public.events ev on ev.id = b.event_id
           where b.closed_at is null and (now() >= b.closes_at or ev.status = 'cancelled') loop
    n := n + private.bar_close(e);
  end loop;
  return n;
end $$;

create or replace function private.purge_old_bars() returns int
language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  -- Données personnelles (consommations) : effacées 6 mois après la fermeture du bar (politique de confidentialité).
  perform set_config('party.bar_purge', 'on', true);
  with gone as (delete from public.event_bars where closed_at < now() - interval '6 months' returning 1)
  select count(*) into n from gone;
  return n;
end $$;

do $$ begin
  perform cron.unschedule('bar-close-due') where exists (select 1 from cron.job where jobname = 'bar-close-due');
  perform cron.schedule('bar-close-due', '* * * * *', 'select private.close_due_bars();');
  perform cron.unschedule('bar-purge') where exists (select 1 from cron.job where jobname = 'bar-purge');
  perform cron.schedule('bar-purge', '17 3 * * *', 'select private.purge_old_bars();');
exception when undefined_function or invalid_schema_name or undefined_table then null; end $$;

-- 5. Organisateurs -------------------------------------------------------------------------------------------------
create or replace function public.bar_overview(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into b from public.event_bars where event_id = e;
  if b.event_id is null then return null; end if;
  if b.closed_at is null and now() >= b.closes_at then perform private.bar_close(e); select * into b from public.event_bars where event_id = e; end if;
  return jsonb_build_object(
    'phase', private.bar_phase(b), 'orders_open', b.orders_open, 'preorder_enabled', b.preorder_enabled, 'preorder_until', b.preorder_until,
    'closes_at', b.closes_at, 'closed_at', b.closed_at, 'payee_id', b.payee_id, 'pay_method', b.pay_method, 'repay_by', b.repay_by,
    'pledge_text', private.bar_pledge_text(b), 'terms_version', b.terms_version,
    'items', coalesce((select jsonb_agg(jsonb_build_object('id', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', i.price_chf,
        'stock', i.stock, 'age_min', i.age_min, 'max_pending', i.max_pending, 'sort', i.sort, 'active', i.active,
        'served', c.served, 'pending', c.pending,
        'available', case when i.stock is null then null else i.stock - c.served - c.pending end) order by i.sort, i.name)
      from public.event_bar_items i cross join lateral private.bar_counts(i.id) c where i.event_id = e), '[]'::jsonb),
    'staff', coalesce((select jsonb_agg(jsonb_build_object('id', s.user_id, 'name', p.display_name, 'avatar_url', p.avatar_url,
        'served', (select count(*) from public.event_bar_units u where u.event_id = e and u.served_by = s.user_id and u.status = 'served')) order by p.display_name)
      from public.event_bar_staff s join public.profiles p on p.id = s.user_id where s.event_id = e), '[]'::jsonb),
    'people', coalesce((select jsonb_agg(x order by x->>'name') from (
        select jsonb_build_object('id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url,
          'balance', private.bar_balance(e, p.id),
          'pending', (select count(*) from public.event_bar_units u where u.event_id = e and u.user_id = p.id and u.status = 'pending'),
          'served', (select count(*) from public.event_bar_units u where u.event_id = e and u.user_id = p.id and u.status = 'served'),
          'declared', (select jsonb_agg(jsonb_build_object('id', r.id, 'amount', r.amount_chf, 'at', r.declared_at))
                       from public.event_bar_refunds r where r.event_id = e and r.user_id = p.id and r.status = 'declared'),
          'refunded', coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = p.id and r.status = 'confirmed'), 0)) x
        from public.profiles p where exists (select 1 from public.event_bar_units u where u.event_id = e and u.user_id = p.id)) s), '[]'::jsonb),
    'totals', jsonb_build_object(
      'served', (select count(*) from public.event_bar_units where event_id = e and status = 'served'),
      'served_chf', coalesce((select sum(price_chf) from public.event_bar_units where event_id = e and status = 'served'), 0),
      'refunded_chf', coalesce((select sum(amount_chf) from public.event_bar_refunds where event_id = e and status = 'confirmed'), 0)),
    'cancellations', coalesce((select jsonb_agg(x) from (
        select jsonb_build_object('at', l.at, 'name', p.display_name, 'item', i.name, 'qty', l.qty, 'kind', l.kind) x
        from public.event_bar_log l left join public.profiles p on p.id = l.user_id left join public.event_bar_items i on i.id = l.item_id
        where l.event_id = e and l.kind in ('cancelled_mine', 'cancelled_by_organizer') order by l.at desc limit 10) s), '[]'::jsonb));
end $$;

create or replace function public.bar_person(e uuid, member uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  perform private.bar_require(e);
  return jsonb_build_object('id', member, 'name', (select display_name from public.profiles where id = member),
    'balance', private.bar_balance(e, member),
    'pledges', coalesce((select jsonb_agg(p.accepted_at order by p.accepted_at) from public.event_bar_pledges p where p.event_id = e and p.user_id = member), '[]'::jsonb),
    'units', coalesce((select jsonb_agg(jsonb_build_object('id', u.id, 'item', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', u.price_chf,
        'status', u.status, 'ordered_at', u.ordered_at, 'served_at', u.served_at,
        'served_by', (select display_name from public.profiles where id = u.served_by)) order by coalesce(u.served_at, u.ordered_at))
      from public.event_bar_units u join public.event_bar_items i on i.id = u.item_id where u.event_id = e and u.user_id = member), '[]'::jsonb));
end $$;

create or replace function public.bar_create(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into ev from public.events where id = e;
  if ev.id is null or ev.status = 'cancelled' then raise exception 'Cet événement n''est pas ouvert' using errcode = '22023'; end if;
  insert into public.event_bars (event_id, created_by, payee_id, closes_at)
  values (e, auth.uid(), coalesce(ev.created_by, auth.uid()),
          coalesce(ev.ends_at, ev.starts_at + interval '10 hours', now() + interval '30 days'))
  on conflict (event_id) do nothing;
  perform private.bar_log(e, 'created', null, null, null, null);
  return public.bar_overview(e);
end $$;

create or replace function public.bar_save_settings(e uuid, settings jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; nb public.event_bars; who uuid; ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into b from public.event_bars where event_id = e for update;
  if b.event_id is null then raise exception 'not_found: pas de bar pour cet événement' using errcode = 'P0002'; end if;
  nb := b;
  if settings ? 'orders_open' then nb.orders_open := (settings->>'orders_open')::boolean; end if;
  if settings ? 'preorder_enabled' then nb.preorder_enabled := (settings->>'preorder_enabled')::boolean; end if;
  if settings ? 'preorder_until' then nb.preorder_until := nullif(settings->>'preorder_until', '')::timestamptz; end if;
  if settings ? 'closes_at' then nb.closes_at := (settings->>'closes_at')::timestamptz; end if;
  if settings ? 'pay_method' then nb.pay_method := settings->>'pay_method'; end if;
  if settings ? 'repay_by' then nb.repay_by := nullif(settings->>'repay_by', '')::date; end if;
  if settings ? 'payee_id' then
    nb.payee_id := (settings->>'payee_id')::uuid;
    if not exists (select 1 from public.events where id = e and created_by = nb.payee_id)
       and not exists (select 1 from public.event_organizers where event_id = e and user_id = nb.payee_id) then
      raise exception 'Le remboursement va à l''organisateur ou à un co-organisateur.' using errcode = '22023';
    end if;
  end if;
  if nb.pay_method not in ('revolut', 'twint', 'iban') then raise exception 'Moyen de remboursement inconnu' using errcode = '22023'; end if;
  if nb.closes_at is null then raise exception 'Heure de fermeture du bar obligatoire' using errcode = '22023'; end if;
  if b.closed_at is not null and (nb.orders_open or nb.preorder_enabled) then
    raise exception 'Ce bar est fermé.' using errcode = '22023';
  end if;
  -- Conditions changées (bénéficiaire, moyen, date limite) : nouvelle version du texte d'engagement, chacun est prévenu.
  if (nb.payee_id, nb.pay_method, nb.repay_by) is distinct from (b.payee_id, b.pay_method, b.repay_by) then
    nb.terms_version := b.terms_version + 1;
  end if;
  update public.event_bars set orders_open = nb.orders_open, preorder_enabled = nb.preorder_enabled, preorder_until = nb.preorder_until,
    closes_at = nb.closes_at, pay_method = nb.pay_method, repay_by = nb.repay_by, payee_id = nb.payee_id, terms_version = nb.terms_version
    where event_id = e;
  perform private.bar_log(e, 'settings', null, null, null, null, settings);
  if nb.terms_version > b.terms_version then
    select * into ev from public.events where id = e;
    for who in select distinct u.user_id from public.event_bar_units u where u.event_id = e and u.status in ('pending', 'served') loop
      perform public.queue_notification(who, 'bar_changed', e, ev.title,
        'Conditions du bar changées : ' || private.bar_pledge_text(nb), 'bar_terms:' || e || ':' || nb.terms_version || ':' || who);
    end loop;
  end if;
  return public.bar_overview(e);
end $$;

create or replace function public.bar_save_item(e uuid, item jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare it public.event_bar_items; item_id uuid := nullif(item->>'id', '')::uuid; clean text; over bigint := 0; c record;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  perform private.bar_require(e);
  perform private.require_terms(auth.uid());  -- nom d'article : contenu vu des invités
  clean := private.item_text_verdict(btrim(coalesce(item->>'name', '')), 'Article');
  if item_id is null then
    insert into public.event_bar_items (event_id, name, emoji, price_chf, stock, age_min, max_pending, sort)
    values (e, clean, nullif(item->>'emoji', ''), (item->>'price_chf')::numeric, nullif(item->>'stock', '')::int,
            coalesce(nullif(item->>'age_min', '')::int, 0), nullif(item->>'max_pending', '')::int,
            coalesce(nullif(item->>'sort', '')::int, (select coalesce(max(i.sort), 0) + 1 from public.event_bar_items i where i.event_id = e)))
    returning * into it;
  else
    select * into it from public.event_bar_items i where i.id = item_id and i.event_id = e for update;
    if it.id is null then raise exception 'not_found: article introuvable' using errcode = 'P0002'; end if;
    update public.event_bar_items i set name = clean, emoji = nullif(item->>'emoji', ''),
      price_chf = coalesce((item->>'price_chf')::numeric, i.price_chf),
      stock = case when item ? 'stock' then nullif(item->>'stock', '')::int else i.stock end,
      age_min = coalesce(nullif(item->>'age_min', '')::int, i.age_min),
      max_pending = case when item ? 'max_pending' then nullif(item->>'max_pending', '')::int else i.max_pending end,
      sort = coalesce(nullif(item->>'sort', '')::int, i.sort),
      active = coalesce((item->>'active')::boolean, i.active)
      where i.id = it.id returning * into it;
  end if;
  -- Stock baissé sous ce qui est déjà réservé : on le dit (l'organisateur choisit quoi annuler).
  if it.stock is not null then
    select * into c from private.bar_counts(it.id);
    over := greatest(c.served + c.pending - it.stock, 0);
  end if;
  perform private.bar_log(e, 'item_saved', null, it.id, null, it.price_chf, jsonb_build_object('name', it.name, 'stock', it.stock));
  return jsonb_build_object('id', it.id, 'overbooked', over, 'name', it.name);
end $$;

create or replace function public.bar_set_staff(e uuid, member uuid, barman boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  perform private.bar_require(e);
  if barman then
    if not private.bar_is_present(e, member) then raise exception 'Un barman est choisi parmi les présents.' using errcode = '22023'; end if;
    insert into public.event_bar_staff (event_id, user_id, added_by) values (e, member, auth.uid()) on conflict do nothing;
    select * into ev from public.events where id = e;
    perform public.queue_notification(member, 'bar_changed', e, ev.title, 'Tu es barman de la soirée : « Scanner au bar » est sur la page de l''événement.',
      'bar_staff:' || e || ':' || member);
  else
    delete from public.event_bar_staff where event_id = e and user_id = member;
  end if;
  perform private.bar_log(e, case when barman then 'staff_added' else 'staff_removed' end, member, null, null, null);
  return public.bar_overview(e);
end $$;

-- 6. Invités -------------------------------------------------------------------------------------------------------
create or replace function public.my_bar(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); t public.event_tickets; pay public.tc_payment; eligible boolean; owes boolean;
begin
  if me is null or not public.can_see_event(e) then raise exception 'Événement introuvable' using errcode = '42501'; end if;
  select * into b from public.event_bars where event_id = e;
  if b.event_id is null then return null; end if;
  if b.closed_at is null and now() >= b.closes_at then perform private.bar_close(e); select * into b from public.event_bars where event_id = e; end if;
  eligible := private.bar_eligible(e, me);
  if eligible then t := private.ensure_ticket(e, me); end if;  -- un seul QR par soirée (entrée et bar)
  -- Coordonnées de paiement (IBAN, lien) : seulement à qui peut commander, doit de l'argent, ou gère le bar.
  owes := eligible or private.bar_balance(e, me) > 0 or private.bar_can_manage(e);
  if owes then select * into pay from public.tc_payment where user_id = b.payee_id; end if;
  return jsonb_build_object(
    'phase', private.bar_phase(b), 'eligible', eligible, 'manage', private.bar_can_manage(e), 'serve', private.bar_can_serve(e),
    'closes_at', b.closes_at, 'preorder_until', b.preorder_until,
    'pledge_text', private.bar_pledge_text(b), 'pledge_version', b.terms_version,
    'payee', jsonb_build_object('id', b.payee_id, 'name', (select display_name from public.profiles where id = b.payee_id),
      'method', b.pay_method, 'repay_by', b.repay_by,
      'iban', case when b.pay_method = 'iban' then pay.iban end, 'holder', case when b.pay_method = 'iban' then pay.holder end,
      'link', case b.pay_method when 'revolut' then pay.links->>'revolut' when 'twint' then pay.links->>'twint' end),
    'qr', case when eligible then jsonb_build_object('token', t.token, 'code', t.code) end,
    'balance', private.bar_balance(e, me),
    'pending_total', coalesce((select sum(u.price_chf) from public.event_bar_units u where u.event_id = e and u.user_id = me and u.status = 'pending'), 0),
    'refund_declared', coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = me and r.status = 'declared'), 0),
    'items', coalesce((select jsonb_agg(jsonb_build_object(
        'id', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', i.price_chf, 'age_min', i.age_min, 'max_pending', i.max_pending,
        'active', i.active, 'available', case when i.stock is null then null else greatest(i.stock - c.served - c.pending, 0) end,
        'mine_pending', (select count(*) from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status = 'pending'))
        order by i.sort, i.name)
      from public.event_bar_items i cross join lateral private.bar_counts(i.id) c where i.event_id = e
        and (i.active or exists (select 1 from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status = 'pending'))), '[]'::jsonb),
    'served', coalesce((select jsonb_agg(jsonb_build_object('at', u.served_at, 'item', i.name, 'emoji', i.emoji, 'price_chf', u.price_chf) order by u.served_at)
      from public.event_bar_units u join public.event_bar_items i on i.id = u.item_id
      where u.event_id = e and u.user_id = me and u.status = 'served'), '[]'::jsonb),
    'cancelled', coalesce((select jsonb_agg(jsonb_build_object('item', i.name, 'emoji', i.emoji, 'reason', u.cancel_reason, 'at', coalesce(u.cancelled_at, u.corrected_at)) order by coalesce(u.cancelled_at, u.corrected_at))
      from public.event_bar_units u join public.event_bar_items i on i.id = u.item_id
      where u.event_id = e and u.user_id = me and u.status in ('cancelled', 'corrected')), '[]'::jsonb),
    'pledges', coalesce((select jsonb_agg(p.accepted_at order by p.accepted_at) from public.event_bar_pledges p where p.event_id = e and p.user_id = me), '[]'::jsonb));
end $$;

-- Commande (tout ou rien) : engagement coché (texte exact), stock virtuel et maximum en attente vérifiés sous verrou.
create or replace function public.bar_order(e uuid, lines jsonb, pledge_text text, pledge_version int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); phase text; pledge uuid; line record; it public.event_bar_items; c record;
        mine bigint; preorder boolean;
begin
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  select * into b from public.event_bars where event_id = e;
  if b.event_id is null then raise exception 'not_found: pas de bar pour cet événement' using errcode = 'P0002'; end if;
  if not private.bar_eligible(e, me) then
    raise exception 'forbidden: seules les personnes notées « Présent », au profil complet, commandent au bar' using errcode = '42501';
  end if;
  phase := private.bar_phase(b);
  if phase not in ('open', 'preorder') then
    raise exception '%', case phase when 'closed' then 'Le bar est fermé.' else 'Les commandes ne sont pas encore ouvertes.' end using errcode = '22023';
  end if;
  preorder := phase = 'preorder';
  if pledge_version is distinct from b.terms_version or pledge_text is distinct from private.bar_pledge_text(b) then
    raise exception 'terms_changed: les conditions de remboursement ont changé, relis-les puis recoche l''engagement' using errcode = '22023';
  end if;
  if jsonb_typeof(lines) <> 'array' or jsonb_array_length(lines) = 0 then raise exception 'Commande vide' using errcode = '22023'; end if;
  insert into public.event_bar_pledges (event_id, user_id, text, terms_version) values (e, me, pledge_text, b.terms_version) returning id into pledge;
  -- Verrous dans l'ordre des articles : deux téléphones ou deux barmans passent l'un après l'autre, sans interblocage.
  for line in select (l->>'item')::uuid item, sum((l->>'qty')::int) qty from jsonb_array_elements(lines) l group by 1 order by 1 loop
    if line.qty is null or line.qty < 1 or line.qty > 50 then raise exception 'Quantité invalide' using errcode = '22023'; end if;
    select * into it from public.event_bar_items i where i.id = line.item and i.event_id = e and i.active for update;
    if it.id is null then raise exception 'Cet article n''est plus proposé.' using errcode = '22023'; end if;
    select * into c from private.bar_counts(it.id);
    if it.stock is not null and c.served + c.pending + line.qty > it.stock then
      raise exception 'stock: % — plus que % disponible%', it.name, greatest(it.stock - c.served - c.pending, 0),
        case when it.stock - c.served - c.pending > 1 then 's' else '' end using errcode = '22023';
    end if;
    if it.max_pending is not null and not preorder then
      select count(*) into mine from public.event_bar_units u where u.item_id = it.id and u.user_id = me and u.status = 'pending';
      if mine + line.qty > it.max_pending then
        raise exception 'max_pending: maximum % % en attente par personne (tu en as déjà % pas encore servi%)',
          it.max_pending, it.name, mine, case when mine > 1 then 's' else '' end using errcode = '22023';
      end if;
    end if;
    insert into public.event_bar_units (event_id, item_id, user_id, pledge_id, price_chf, preorder)
    select e, it.id, me, pledge, it.price_chf, preorder from generate_series(1, line.qty);
    perform private.bar_log(e, 'ordered', me, it.id, line.qty, it.price_chf * line.qty, jsonb_build_object('preorder', preorder));
  end loop;
  return public.my_bar(e);
end $$;

create or replace function public.bar_cancel_mine(e uuid, item uuid, qty int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); n int;
begin
  perform private.bar_require(e);
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if qty is null or qty < 1 then raise exception 'Quantité invalide' using errcode = '22023'; end if;
  perform 1 from public.event_bar_items i where i.id = item and i.event_id = e for update;
  with victims as (
    select u.id from public.event_bar_units u where u.event_id = e and u.item_id = item and u.user_id = me and u.status = 'pending'
    order by u.preorder, u.ordered_at desc limit qty for update)
  update public.event_bar_units u set status = 'cancelled', cancelled_at = now(), cancelled_by = me, cancel_reason = 'mine'
    from victims v where u.id = v.id;
  get diagnostics n = row_count;
  if n = 0 then raise exception 'Rien à annuler : ce verre a déjà été servi.' using errcode = '22023'; end if;
  perform private.bar_log(e, 'cancelled_mine', me, item, n, null);
  return public.my_bar(e);
end $$;

create or replace function public.bar_declare_refund(e uuid, amount numeric) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); ev public.events; owed numeric; who text; m uuid;
begin
  b := private.bar_require(e);
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  owed := private.bar_balance(e, me) - coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = me and r.status = 'declared'), 0);
  if amount is null or amount <= 0 or amount > owed then
    raise exception 'Montant à rembourser invalide (au plus %).', private.bar_chf(greatest(owed, 0)) using errcode = '22023';
  end if;
  insert into public.event_bar_refunds (event_id, user_id, amount_chf) values (e, me, amount);
  perform private.bar_log(e, 'refund_declared', me, null, null, amount);
  select * into ev from public.events where id = e;
  select display_name into who from public.profiles where id = me;
  for m in select x from (select b.payee_id x union select ev.created_by union select o.user_id from public.event_organizers o where o.event_id = e) s where x is not null loop
    perform public.queue_notification(m, 'bar_refund_declared', e, ev.title,
      coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' dit avoir remboursé ' || private.bar_chf(amount) || ' pour le bar : à confirmer.',
      'bar_refund:' || e || ':' || me || ':' || extract(epoch from clock_timestamp())::bigint);
  end loop;
  return public.my_bar(e);
end $$;

-- 7. Barman ---------------------------------------------------------------------------------------------------------
create or replace function public.bar_scan(e uuid, scanned text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; t public.event_tickets; raw text := btrim(coalesce(scanned, '')); tok text; member uuid; p public.profiles;
begin
  if not private.bar_can_serve(e) then raise exception 'forbidden: réservé aux barmans et organisateurs de la soirée' using errcode = '42501'; end if;
  b := private.bar_require(e);
  if b.closed_at is null and now() >= b.closes_at then perform private.bar_close(e); select * into b from public.event_bars where event_id = e; end if;
  tok := lower(substring(raw from '([0-9a-fA-F]{64})'));
  if tok is not null then
    select * into t from public.event_tickets x where x.token = tok;
  elsif upper(raw) ~ '^[A-Z2-9]{6}$' then
    select * into t from public.event_tickets x where x.event_id = e and x.code = upper(raw);
  end if;
  if t.user_id is null then return jsonb_build_object('result', 'unknown'); end if;
  if t.event_id <> e then return jsonb_build_object('result', 'other_event'); end if;
  member := t.user_id;
  select * into p from public.profiles where id = member;
  if private.bar_phase(b) = 'closed' then return jsonb_build_object('result', 'closed', 'name', p.display_name); end if;
  if not private.bar_eligible(e, member) then return jsonb_build_object('result', 'not_present', 'name', p.display_name); end if;
  return jsonb_build_object('result', 'ok', 'member', member, 'name', p.display_name, 'avatar_url', p.avatar_url,
    'pledged_at', (select max(x.accepted_at) from public.event_bar_pledges x where x.event_id = e and x.user_id = member),
    'balance', private.bar_balance(e, member),
    'pending', coalesce((select jsonb_agg(x order by x->>'name') from (
        select jsonb_build_object('item', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', i.price_chf, 'age_min', i.age_min,
          'qty', count(*), 'stock', case when i.stock is null then null else i.stock - (select c.served from private.bar_counts(i.id) c) end) x
        from public.event_bar_units u join public.event_bar_items i on i.id = u.item_id
        where u.event_id = e and u.user_id = member and u.status = 'pending' group by i.id) s), '[]'::jsonb));
end $$;

create or replace function public.bar_serve(e uuid, member uuid, lines jsonb, client_key text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); done public.event_bar_serves; serve uuid := gen_random_uuid(); line record;
        it public.event_bar_items; c record; total numeric := 0; served_lines jsonb := '[]'::jsonb; before numeric; ev public.events; n int;
        summary text;
begin
  if not private.bar_can_serve(e) then raise exception 'forbidden: réservé aux barmans et organisateurs de la soirée' using errcode = '42501'; end if;
  -- Même geste rejoué (double toucher, reprise réseau) : même résultat, rien de servi deux fois.
  select * into done from public.event_bar_serves s where s.client_key = bar_serve.client_key;
  if done.id is not null then
    if done.event_id <> e or done.user_id <> member then raise exception 'Clé de service déjà utilisée' using errcode = '22023'; end if;
    return jsonb_build_object('serve_id', done.id, 'total', done.total_chf, 'balance', private.bar_balance(e, member), 'replayed', true);
  end if;
  select * into b from public.event_bars where event_id = e;
  if b.event_id is null then raise exception 'not_found: pas de bar pour cet événement' using errcode = 'P0002'; end if;
  if private.bar_phase(b) = 'closed' then raise exception 'Le bar est fermé.' using errcode = '22023'; end if;
  if not private.bar_eligible(e, member) then raise exception 'Cette personne n''est pas notée présente.' using errcode = '22023'; end if;
  if jsonb_typeof(lines) <> 'array' or jsonb_array_length(lines) = 0 then raise exception 'Rien à servir' using errcode = '22023'; end if;
  before := private.bar_balance(e, member);
  for line in select (l->>'item')::uuid item, sum((l->>'qty')::int) qty from jsonb_array_elements(lines) l group by 1 order by 1 loop
    if line.qty is null or line.qty < 1 or line.qty > 50 then raise exception 'Quantité invalide' using errcode = '22023'; end if;
    select * into it from public.event_bar_items i where i.id = line.item and i.event_id = e for update;
    if it.id is null then raise exception 'Article introuvable' using errcode = '22023'; end if;
    select * into c from private.bar_counts(it.id);
    if it.stock is not null and c.served + line.qty > it.stock then
      raise exception 'stock: plus de % en stock', it.name using errcode = '22023';
    end if;
    with picked as (
      select u.id from public.event_bar_units u where u.item_id = it.id and u.user_id = member and u.status = 'pending'
      order by u.preorder desc, u.ordered_at limit line.qty for update)
    update public.event_bar_units u set status = 'served', served_at = now(), served_by = me, serve_id = serve
      from picked p where u.id = p.id;
    get diagnostics n = row_count;
    if n < line.qty then
      raise exception 'already_served: % — plus que % en attente (déjà servi par un autre barman ?)', it.name, n using errcode = '22023';
    end if;
    total := total + (select sum(u.price_chf) from public.event_bar_units u where u.serve_id = serve and u.item_id = it.id);
    served_lines := served_lines || jsonb_build_object('item', it.id, 'name', it.name, 'emoji', it.emoji, 'qty', n);
    perform private.bar_log(e, 'served', member, it.id, n, null, jsonb_build_object('serve_id', serve));
  end loop;
  insert into public.event_bar_serves (id, event_id, user_id, served_by, total_chf, client_key) values (serve, e, member, me, total, bar_serve.client_key);
  select * into ev from public.events where id = e;
  select string_agg((x->>'qty') || ' ' || (x->>'name'), ', ') into summary from jsonb_array_elements(served_lines) x;
  perform public.queue_notification(member, 'bar_served', e, ev.title,
    'Servi : ' || summary || ' (' || private.bar_chf(total) || '). À rembourser : ' || private.bar_chf(before + total) || '.',
    'bar_served:' || serve, jsonb_build_object('serve_id', serve, 'balance', before + total));
  return jsonb_build_object('serve_id', serve, 'total', total, 'balance_before', before, 'balance', before + total, 'lines', served_lines);
end $$;

-- Annuler un service : le même barman dans les 15 s (10 s à l'écran + réseau) ; ensuite seul un organisateur corrige.
create or replace function public.bar_undo_serve(e uuid, serve uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare s public.event_bar_serves; ev public.events; n int;
begin
  select * into s from public.event_bar_serves x where x.id = serve and x.event_id = e for update;
  if s.id is null or s.undone_at is not null then raise exception 'Service introuvable ou déjà annulé' using errcode = '22023'; end if;
  if not (s.served_by = auth.uid() and now() - s.served_at <= interval '15 seconds') then
    raise exception 'forbidden: trop tard pour annuler ici : un organisateur peut corriger depuis la fiche de la personne' using errcode = '42501';
  end if;
  update public.event_bar_units set status = 'pending', served_at = null, served_by = null, serve_id = null
    where serve_id = s.id and status = 'served';
  get diagnostics n = row_count;
  update public.event_bar_serves set undone_at = now(), undone_by = auth.uid() where id = s.id;
  perform private.bar_log(e, 'serve_undone', s.user_id, null, n, s.total_chf, jsonb_build_object('serve_id', s.id));
  select * into ev from public.events where id = e;
  perform public.queue_notification(s.user_id, 'bar_changed', e, ev.title,
    'Service annulé par le barman : ' || private.bar_chf(s.total_chf) || ' retirés. À rembourser : ' || private.bar_chf(private.bar_balance(e, s.user_id)) || '.',
    'bar_undo:' || s.id);
  return jsonb_build_object('undone', n, 'balance', private.bar_balance(e, s.user_id));
end $$;

-- 8. Corrections (organisateurs) ---------------------------------------------------------------------------------------
create or replace function public.bar_cancel_units(e uuid, member uuid, item uuid, qty int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; n int; label text;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  perform private.bar_require(e);
  if qty is null or qty < 1 then raise exception 'Quantité invalide' using errcode = '22023'; end if;
  select i.name into label from public.event_bar_items i where i.id = item and i.event_id = e for update;
  with victims as (
    select u.id from public.event_bar_units u where u.event_id = e and u.item_id = item and u.user_id = member and u.status = 'pending'
    order by u.ordered_at desc limit qty for update)
  update public.event_bar_units u set status = 'cancelled', cancelled_at = now(), cancelled_by = auth.uid(), cancel_reason = 'organizer'
    from victims v where u.id = v.id;
  get diagnostics n = row_count;
  if n = 0 then raise exception 'Rien à annuler pour cette personne.' using errcode = '22023'; end if;
  perform private.bar_log(e, 'cancelled_by_organizer', member, item, n, null);
  select * into ev from public.events where id = e;
  perform public.queue_notification(member, 'bar_changed', e, ev.title,
    'L''organisateur a annulé ' || n || ' ' || label || ' en attente : rien à payer pour ' || case when n > 1 then 'eux.' else 'lui.' end,
    'bar_cancel:' || e || ':' || member || ':' || extract(epoch from clock_timestamp())::bigint);
  return public.bar_person(e, member);
end $$;

create or replace function public.bar_correct_unit(e uuid, unit uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare u public.event_bar_units; ev public.events; label text;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into u from public.event_bar_units x where x.id = unit and x.event_id = e for update;
  if u.id is null or u.status <> 'served' then raise exception 'Ce verre n''est pas servi : rien à corriger.' using errcode = '22023'; end if;
  perform 1 from public.event_bar_items i where i.id = u.item_id for update;
  update public.event_bar_units set status = 'corrected', corrected_at = now(), corrected_by = auth.uid() where id = u.id;
  select i.name into label from public.event_bar_items i where i.id = u.item_id;
  perform private.bar_log(e, 'corrected', u.user_id, u.item_id, 1, u.price_chf);
  select * into ev from public.events where id = e;
  perform public.queue_notification(u.user_id, 'bar_changed', e, ev.title,
    'Correction : ' || label || ' servi par erreur, ' || private.bar_chf(u.price_chf) || ' retirés. À rembourser : ' || private.bar_chf(private.bar_balance(e, u.user_id)) || '.',
    'bar_correct:' || u.id);
  return public.bar_person(e, u.user_id);
end $$;

create or replace function public.bar_confirm_refund(e uuid, refund uuid, received boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.event_bar_refunds; ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into r from public.event_bar_refunds x where x.id = refund and x.event_id = e for update;
  if r.id is null or r.status <> 'declared' then raise exception 'Remboursement introuvable ou déjà traité' using errcode = '22023'; end if;
  update public.event_bar_refunds set status = case when received then 'confirmed' else 'rejected' end, confirmed_at = now(), confirmed_by = auth.uid()
    where id = r.id;
  perform private.bar_log(e, case when received then 'refund_confirmed' else 'refund_rejected' end, r.user_id, null, null, r.amount_chf);
  select * into ev from public.events where id = e;
  perform public.queue_notification(r.user_id, 'bar_refund_confirmed', e, ev.title,
    case when received then 'Remboursement de ' || private.bar_chf(r.amount_chf) || ' reçu. Reste à rembourser : ' || private.bar_chf(private.bar_balance(e, r.user_id)) || '.'
         else 'Remboursement de ' || private.bar_chf(r.amount_chf) || ' pas encore reçu : vois avec l''organisateur.' end,
    'bar_refund_done:' || r.id);
  return public.bar_overview(e);
end $$;

-- 9. Notifications : les Guests reçoivent aussi celles du bar ; chaque type a son interrupteur ---------------------
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('pet_daily', 'pet_alert', 'pet_gift', 'pet_streak', 'pet_bar') and private.is_account_active(uid))
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message', 'moderation_notice', 'report_new',
                 'private_invite', 'announce_request', 'announce_accepted', 'announce_refused', 'group_event_request', 'group_event_accepted', 'group_event_refused', 'event_changed', 'date_fixed', 'reminder', 'waitlist',
                 'coorganizer_added', 'bar_served', 'bar_changed', 'bar_refund_declared', 'bar_refund_confirmed')
        and private.is_account_active(uid));
$$;

do $$ declare def text; anchor text := $a$    when 'ticket_issued' then coalesce(prefs.ticket_issued, true)$a$;
begin
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''bar_served''' in def) = 0 then
    if position(anchor in def) = 0 then raise exception 'web_push_allowed : ancre ticket_issued introuvable'; end if;
    def := replace(def, anchor, anchor || $a$
    when 'bar_served' then coalesce(prefs.bar_served, true)
    when 'bar_changed' then coalesce(prefs.bar_changed, true)
    when 'bar_refund_declared' then coalesce(prefs.bar_refund_declared, true)
    when 'bar_refund_confirmed' then coalesce(prefs.bar_refund_confirmed, true)$a$);
    execute def;
  end if;
end $$;

-- 10. Droits -----------------------------------------------------------------------------------------------------
revoke all on function private.guard_bar_unit(), private.guard_bar_append_only(), private.bar_can_manage(uuid), private.bar_is_present(uuid, uuid),
  private.bar_can_serve(uuid), private.bar_eligible(uuid, uuid), private.bar_phase(public.event_bars), private.bar_method_label(text),
  private.bar_date_fr(date), private.bar_pledge_text(public.event_bars), private.bar_counts(uuid), private.bar_balance(uuid, uuid),
  private.bar_log(uuid, text, uuid, uuid, bigint, numeric, jsonb), private.bar_chf(numeric), private.bar_require(uuid), private.bar_close(uuid),
  private.close_due_bars(), private.purge_old_bars() from public, anon, authenticated;
revoke all on function public.bar_create(uuid), public.bar_save_settings(uuid, jsonb), public.bar_save_item(uuid, jsonb),
  public.bar_set_staff(uuid, uuid, boolean), public.my_bar(uuid), public.bar_order(uuid, jsonb, text, int), public.bar_cancel_mine(uuid, uuid, int),
  public.bar_declare_refund(uuid, numeric), public.bar_scan(uuid, text), public.bar_serve(uuid, uuid, jsonb, text), public.bar_undo_serve(uuid, uuid),
  public.bar_cancel_units(uuid, uuid, uuid, int), public.bar_correct_unit(uuid, uuid), public.bar_confirm_refund(uuid, uuid, boolean),
  public.bar_overview(uuid), public.bar_person(uuid, uuid) from public, anon;
grant execute on function public.bar_create(uuid), public.bar_save_settings(uuid, jsonb), public.bar_save_item(uuid, jsonb),
  public.bar_set_staff(uuid, uuid, boolean), public.my_bar(uuid), public.bar_order(uuid, jsonb, text, int), public.bar_cancel_mine(uuid, uuid, int),
  public.bar_declare_refund(uuid, numeric), public.bar_scan(uuid, text), public.bar_serve(uuid, uuid, jsonb, text), public.bar_undo_serve(uuid, uuid),
  public.bar_cancel_units(uuid, uuid, uuid, int), public.bar_correct_unit(uuid, uuid), public.bar_confirm_refund(uuid, uuid, boolean),
  public.bar_overview(uuid), public.bar_person(uuid, uuid) to authenticated;
