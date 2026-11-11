-- PROD, bar de la soirée (20261110120000 bar_soiree + 20261110130000 bar_wallet + 20261110140000 bar_corrections + 20261110150000 bar_compte_supprime + 20261110160000 bar_options). À appliquer SEULEMENT après un
-- « Ok prod » de l'admin pour CETTE migration, après la recette réelle ; le bar reste caché tant que BAR_ENABLED n'est
-- pas à 1 sur la production. Rejouable. Tout ou rien. Aucune donnée existante modifiée.
begin;
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

-- Bar de la soirée dans l'app Cartes Apple (maquette v6, écran 9 ; demande de l'admin du 10.11 : « un seul QR, aussi dans
-- Apple Wallet ») : le pass du billet porte aussi le bar (solde à rembourser, verres à servir) et existe dès qu'on peut
-- commander au bar, même billets QR éteints. Il se redate à chaque service, annulation, correction, remboursement ou
-- changement de conditions ; le barman qui sert peut prévenir l'iPhone de la personne (« Nouveau solde : … »).
-- Purement additif et rejouable (create or replace, drop trigger if exists).

create or replace function private.wallet_payload(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'serial', w.event_id::text || '.' || w.user_id::text,
    'user_id', w.user_id,
    'auth_token', w.auth_token,
    'updated_at', w.updated_at,
    -- Pass valable : billet QR remis (comme avant) OU personne qui peut commander au bar de cette soirée.
    'valid', coalesce(r.status = 'yes' and not coalesce(r.waitlisted, false) and ev.status = 'published'
                      and ev.tickets_enabled and t.token is not null and t.issued_at is not null, false)
             or (b.event_id is not null and t.token is not null and private.bar_eligible(w.event_id, w.user_id)),
    'holder', p.display_name,
    'event', jsonb_build_object('id', ev.id, 'title', ev.title, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at,
      'all_day', ev.all_day, 'location_name', ev.location_name, 'location_address', ev.location_address,
      'location_url', ev.location_url, 'status', ev.status),
    'ticket', jsonb_build_object('token', t.token, 'code', t.code, 'plus_ones', coalesce(r.plus_ones, 0),
      'checked_in_at', t.checked_in_at, 'paid', coalesce(t.paid, false), 'price_chf', ev.price_chf),
    'bar', case when b.event_id is not null and private.bar_eligible(w.event_id, w.user_id) then jsonb_build_object(
      'balance', private.bar_balance(w.event_id, w.user_id),
      'pending', (select count(*) from public.event_bar_units u where u.event_id = w.event_id and u.user_id = w.user_id and u.status = 'pending'),
      'payee', (select display_name from public.profiles where id = b.payee_id),
      'method', private.bar_method_label(b.pay_method), 'repay_by', b.repay_by) end)
  from public.wallet_passes w
  join public.events ev on ev.id = w.event_id
  left join public.rsvps r on r.event_id = w.event_id and r.user_id = w.user_id
  left join public.event_tickets t on t.event_id = w.event_id and t.user_id = w.user_id
  left join public.event_bars b on b.event_id = w.event_id
  left join public.profiles p on p.id = w.user_id
  where w.event_id = e and w.user_id = member;
$$;
revoke all on function private.wallet_payload(uuid, uuid) from public, anon, authenticated;

create or replace function public.wallet_pass_issue(e uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if public.my_event_ticket(e) ->> 'state' is distinct from 'ok' then  -- même règle que pour afficher son QR…
    -- … sauf au bar : toute personne qui peut y commander a son QR (le même jeton que le billet).
    if not (exists (select 1 from public.event_bars where event_id = e) and private.bar_eligible(e, me)) then
      raise exception 'Pas encore de billet pour cet événement : l''organisateur doit te le remettre.' using errcode = '22023';
    end if;
    perform private.ensure_ticket(e, me);
  end if;
  insert into public.wallet_passes (event_id, user_id, auth_token) values (e, me, private.new_ticket_token())
    on conflict (event_id, user_id) do nothing;
  return private.wallet_payload(e, me);
end $$;
revoke all on function public.wallet_pass_issue(uuid) from public, anon, authenticated;
grant execute on function public.wallet_pass_issue(uuid) to authenticated;

-- Prévenir les iPhone : soi-même, un organisateur (tous), ou le barman pour la personne qu'il sert.
create or replace function public.wallet_push_targets(e uuid, member uuid default null) returns setof text
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if member is distinct from auth.uid() and not private.can_scan(e)
     and not (member is not null and private.bar_can_serve(e)) then
    raise exception 'Seuls les organisateurs de l''événement préviennent les billets.' using errcode = '42501';
  end if;
  return query select distinct d.push_token from public.wallet_devices d
    where d.event_id = e and (member is null or d.user_id = member);
end $$;
revoke all on function public.wallet_push_targets(uuid, uuid) from public, anon;
grant execute on function public.wallet_push_targets(uuid, uuid) to authenticated;

-- Le pass se redate quand le bar de la personne change.
drop trigger if exists wallet_touch on public.event_bar_units;
create trigger wallet_touch after insert or update of status on public.event_bar_units for each row
  execute function private.wallet_touch_member();
drop trigger if exists wallet_touch on public.event_bar_refunds;
create trigger wallet_touch after insert or update of status on public.event_bar_refunds for each row
  execute function private.wallet_touch_member();

create or replace function private.wallet_touch_bar() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.wallet_passes set updated_at = now() where event_id = new.event_id;
  return null;
end $$;
revoke all on function private.wallet_touch_bar() from public, anon, authenticated;
drop trigger if exists wallet_touch on public.event_bars;
create trigger wallet_touch after insert or update on public.event_bars for each row execute function private.wallet_touch_bar();

notify pgrst, 'reload schema';

-- ===== 20261110140000 bar_corrections (test réel du 10.11) =====
-- Bar de la soirée : corrections du test réel du 10.11.2026 (agents organisateur, barman, clients, client chaotique).
-- Rejouable et additive (create or replace, drop … if exists). Base de TEST d'abord ; prod seulement après « Ok prod ».

-- Verres en attente d'une personne qui n'est plus « Présent » : annulés (motif « absent »), le stock est rendu.
alter table public.event_bar_units drop constraint if exists event_bar_units_cancel_reason_check;
alter table public.event_bar_units add constraint event_bar_units_cancel_reason_check
  check (cancel_reason is null or cancel_reason in ('mine', 'organizer', 'closed', 'removed', 'absent'));

create or replace function private.bar_cancel_absent() returns trigger
language plpgsql security definer set search_path = '' as $$
declare n int; target uuid := coalesce(new.event_id, old.event_id); member uuid := coalesce(new.user_id, old.user_id);
begin
  if tg_op = 'UPDATE' and new.status = 'yes' and not new.waitlisted then return new; end if;
  -- Événement (ou bar) en cours d'effacement : tout part en cascade, rien à annuler ni à noter au journal.
  if not exists (select 1 from public.event_bars where event_id = target) then return coalesce(new, old); end if;
  update public.event_bar_units set status = 'cancelled', cancelled_at = now(), cancel_reason = 'absent'
    where event_id = target and user_id = member and status = 'pending';
  get diagnostics n = row_count;
  if n > 0 then perform private.bar_log(target, 'cancelled_absent', member, null, n, null); end if;
  return coalesce(new, old);
end $$;
revoke all on function private.bar_cancel_absent() from public, anon, authenticated;
drop trigger if exists bar_cancel_absent on public.rsvps;
create trigger bar_cancel_absent after update of status, waitlisted or delete on public.rsvps
  for each row when (old.status = 'yes') execute function private.bar_cancel_absent();

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
  -- Test réel du 10.11 : un tableau de 100 001 lignes occupait la base 17 s.
  if jsonb_array_length(lines) > 50 then raise exception 'Commande trop longue : 50 lignes au plus.' using errcode = '22023'; end if;
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
    -- Sans maximum fixé par l'organisateur : 10 en attente par personne et par article (test réel du 10.11 : une seule
    -- personne réservait tout le stock d'un article, gratuitement, jusqu'à la fermeture).
    if not preorder then
      select count(*) into mine from public.event_bar_units u where u.item_id = it.id and u.user_id = me and u.status = 'pending';
      if mine + line.qty > coalesce(it.max_pending, 10) then
        raise exception 'max_pending: maximum % % en attente par personne (tu en as déjà % pas encore servi%)',
          coalesce(it.max_pending, 10), it.name, mine, case when mine > 1 then 's' else '' end using errcode = '22023';
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
  if n = 0 then raise exception 'Rien à annuler : aucun verre de cet article en attente (peut-être déjà servi).' using errcode = '22023'; end if;
  perform private.bar_log(e, 'cancelled_mine', me, item, n, null);
  return public.my_bar(e);
end $$;

create or replace function public.bar_declare_refund(e uuid, amount numeric) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); ev public.events; owed numeric; who text; m uuid; refund_id uuid;
begin
  b := private.bar_require(e);
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  -- Une déclaration à la fois par personne (test réel du 10.11 : 10 déclarations simultanées de 26 CHF pour 26 CHF dus
  -- passaient toutes ; confirmées, le solde devenait négatif, donc du crédit gratuit).
  perform pg_advisory_xact_lock(hashtextextended('bar_refund:' || e || ':' || me, 0));
  amount := round(amount, 2);
  owed := private.bar_balance(e, me) - coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = me and r.status = 'declared'), 0);
  if amount is null or amount <= 0 or amount > owed then
    raise exception 'Montant à rembourser invalide (au plus %).', private.bar_chf(greatest(owed, 0)) using errcode = '22023';
  end if;
  insert into public.event_bar_refunds (event_id, user_id, amount_chf) values (e, me, amount) returning id into refund_id;
  perform private.bar_log(e, 'refund_declared', me, null, null, amount);
  select * into ev from public.events where id = e;
  select display_name into who from public.profiles where id = me;
  for m in select x from (select b.payee_id x union select ev.created_by union select o.user_id from public.event_organizers o where o.event_id = e) s where x is not null loop
    perform public.queue_notification(m, 'bar_refund_declared', e, ev.title,
      coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' dit avoir remboursé ' || private.bar_chf(amount) || ' pour le bar : à confirmer.',
      'bar_refund:' || refund_id);  -- une notification par déclaration
  end loop;
  return public.my_bar(e);
end $$;

create or replace function public.bar_confirm_refund(e uuid, refund uuid, received boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.event_bar_refunds; ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into r from public.event_bar_refunds x where x.id = refund and x.event_id = e for update;
  if r.id is null or r.status <> 'declared' then raise exception 'Remboursement introuvable ou déjà traité' using errcode = '22023'; end if;
  -- Jamais plus que ce qui reste dû : un solde ne devient pas négatif (même verrou que la déclaration).
  perform pg_advisory_xact_lock(hashtextextended('bar_refund:' || e || ':' || r.user_id, 0));
  if received and r.amount_chf > private.bar_balance(e, r.user_id) then
    raise exception 'Ce remboursement (%) dépasse ce qui reste dû (%) : refuse-le, la personne en déclarera un juste.',
      private.bar_chf(r.amount_chf), private.bar_chf(greatest(private.bar_balance(e, r.user_id), 0)) using errcode = '22023';
  end if;
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

create or replace function public.bar_serve(e uuid, member uuid, lines jsonb, client_key text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); done public.event_bar_serves; serve uuid := gen_random_uuid(); line record;
        it public.event_bar_items; c record; total numeric := 0; served_lines jsonb := '[]'::jsonb; before numeric; ev public.events; n int;
        summary text;
begin
  if not private.bar_can_serve(e) then raise exception 'forbidden: réservé aux barmans et organisateurs de la soirée' using errcode = '42501'; end if;
  if jsonb_typeof(lines) <> 'array' or jsonb_array_length(lines) > 50 then raise exception 'Service trop long : 50 lignes au plus.' using errcode = '22023'; end if;
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
      raise exception 'already_served: % — plus que % en attente (déjà servi, ou commande annulée entre-temps)', it.name, n using errcode = '22023';
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
        'mine_pending', (select count(*) from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status = 'pending'),
        -- Prix figés à la commande (la carte a pu changer depuis) : test réel du 10.11.
        'mine_pending_chf', (select coalesce(sum(u.price_chf), 0) from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status = 'pending'))
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
          'qty', count(*),
          -- Prix figé de chaque verre, dans l'ordre où bar_serve les sert (le panneau annonçait le prix actuel de la carte).
          'prices', jsonb_agg(u.price_chf order by u.preorder desc, u.ordered_at),
          'stock', case when i.stock is null then null else i.stock - (select c.served from private.bar_counts(i.id) c) end) x
        from public.event_bar_units u join public.event_bar_items i on i.id = u.item_id
        where u.event_id = e and u.user_id = member and u.status = 'pending' group by i.id) s), '[]'::jsonb));
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
      'bar_staff:' || e || ':' || member || ':' || extract(epoch from clock_timestamp())::bigint);  -- renommé plus tard : prévenu à nouveau
  else
    delete from public.event_bar_staff where event_id = e and user_id = member;
  end if;
  perform private.bar_log(e, case when barman then 'staff_added' else 'staff_removed' end, member, null, null, null);
  return public.bar_overview(e);
end $$;

-- Un verre « servi par erreur » (corrigé) est physiquement parti : il reste compté comme servi pour le stock.
create or replace function private.bar_counts(item uuid) returns table (served bigint, pending bigint)
language sql stable security definer set search_path = '' as $$
  select count(*) filter (where u.status in ('served', 'corrected')), count(*) filter (where u.status = 'pending')
  from public.event_bar_units u where u.item_id = item;
$$;

create or replace function public.bar_undo_serve(e uuid, serve uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare s public.event_bar_serves; ev public.events; n int;
begin
  select * into s from public.event_bar_serves x where x.id = serve and x.event_id = e for update;
  if s.id is null or s.undone_at is not null then raise exception 'Service introuvable ou déjà annulé' using errcode = '22023'; end if;
  -- Bar fermé : plus d'annulation ici (les verres remis « en attente » ne seraient plus jamais servis ni annulés).
  if exists (select 1 from public.event_bars b where b.event_id = e and b.closed_at is not null) then
    raise exception 'Le bar est fermé : un organisateur peut corriger depuis la fiche de la personne.' using errcode = '22023';
  end if;
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

-- 20261110150000 bar_compte_supprime -------------------------------------------------------------------------
-- Bar de la soirée : un compte qui a commandé ou servi au bar peut toujours être supprimé (Apple 5.1.1(v), RGPD).
-- Trouvé par le test réel du 10.11.2026 (suppression d'un Guest par l'admin) : le registre « en ajout seul » refusait la
-- mise à vide automatique de ses colonnes de personne (actor, user_id, item_id : « on delete set null »), donc la
-- suppression du compte échouait (« event_bar_log est un registre en ajout seul »).
-- Désormais permis : seulement en cascade (pg_trigger_depth() > 1) et seulement une colonne qui devient vide ; toute
-- autre modification reste refusée. Purement additif et rejouable.
create or replace function private.guard_bar_append_only() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Compte ou article supprimé : la ligne perd la personne (ou l'article), le reste ne bouge pas.
  if tg_op = 'UPDATE' and pg_trigger_depth() > 1 and not exists (
       select 1 from jsonb_each(to_jsonb(new)) n join jsonb_each(to_jsonb(old)) o using (key)
       where n.value is distinct from o.value and n.value <> 'null'::jsonb) then
    return new;
  end if;
  -- Engagements et journal : jamais modifiés ; effacés seulement par la purge ou en cascade (bar, compte supprimés).
  if tg_op = 'UPDATE' or (tg_op = 'DELETE' and coalesce(current_setting('party.bar_purge', true), '') <> 'on'
                          and pg_trigger_depth() = 1) then
    raise exception 'forbidden: % est un registre en ajout seul', tg_table_name using errcode = '42501';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;
revoke all on function private.guard_bar_append_only() from public, anon, authenticated;

-- 20261110160000 bar_options -------------------------------------------------------------------------------
-- Bar de la soirée : options de l'organisateur (demande de l'admin du 10.11.2026 : « Il doit y avoir pleins d'option pour
-- l'organisateur aussi. Ça doit être vraiment modulable l'option bar. Par exemple permettre au barman de marquer les
-- quantités ou les indisponibilités etc »).
-- A. Options du bar (event_bars) : commandes dans l'app (sinon carte en consultation, commande au comptoir), service au
--    comptoir sans commande (le barman sert en scannant), stock montré aux invités, bar offert (ni prix, ni engagement,
--    ni solde : verres à 0 CHF, comptés), limites par personne pour la soirée (verres et/ou CHF), droits des barmans
--    (ajuster les quantités, marquer indisponible, annuler/corriger, changer les prix, ajouter/modifier des articles).
-- B. Articles : catégorie (choix fixes), précision courte (« 33 cl »), maximum par personne pour la soirée, état
--    « Indisponible pour l'instant » (visible grisé, nouvelles commandes refusées, ce qui attend reste au barman).
-- C. Gestes du barman (et de l'organisateur) : « Il en reste… », « + Réassort », « Indisponible » / « De nouveau dispo »,
--    « Prix » ; chacun noté au journal (qui, quoi, combien) ; droits vérifiés ICI (organisateur, ou barman autorisé).
-- Service au comptoir en bar payant : la personne a accepté l'engagement à rembourser (version en cours) dans « Mon bar ».
-- Aucune nouvelle notification (types existants seulement). Purement additif et rejouable.

-- 1. Colonnes -------------------------------------------------------------------------------------------------------
alter table public.event_bars add column if not exists guest_orders boolean not null default true;
alter table public.event_bars add column if not exists counter_serve boolean not null default false;
alter table public.event_bars add column if not exists show_stock boolean not null default true;
alter table public.event_bars add column if not exists free_bar boolean not null default false;
alter table public.event_bars add column if not exists limit_glasses int check (limit_glasses is null or limit_glasses between 1 and 200);
alter table public.event_bars add column if not exists limit_chf numeric(7, 2) check (limit_chf is null or limit_chf between 1 and 5000);
alter table public.event_bars add column if not exists staff_adjust_stock boolean not null default true;
alter table public.event_bars add column if not exists staff_unavailable boolean not null default true;
alter table public.event_bars add column if not exists staff_correct boolean not null default true;
alter table public.event_bars add column if not exists staff_prices boolean not null default false;
alter table public.event_bars add column if not exists staff_items boolean not null default false;

alter table public.event_bar_items add column if not exists category text not null default 'autre'
  check (category in ('softs', 'bieres', 'vins', 'cocktails', 'shots', 'autre'));
alter table public.event_bar_items add column if not exists detail text check (detail is null or char_length(detail) <= 30);
alter table public.event_bar_items add column if not exists max_per_person int check (max_per_person is null or max_per_person between 1 and 100);
alter table public.event_bar_items add column if not exists unavailable boolean not null default false;

-- Verre servi au comptoir sans commande : annulé (pas remis « en attente ») si le barman annule son service.
alter table public.event_bar_units add column if not exists counter boolean not null default false;
alter table public.event_bar_units drop constraint if exists event_bar_units_cancel_reason_check;
alter table public.event_bar_units add constraint event_bar_units_cancel_reason_check
  check (cancel_reason is null or cancel_reason in ('mine', 'organizer', 'closed', 'removed', 'absent', 'undone'));

-- 2. Règles -----------------------------------------------------------------------------------------------------------
create or replace function private.bar_options(b public.event_bars) returns jsonb
language sql stable set search_path = '' as $$
  select jsonb_build_object('guest_orders', b.guest_orders, 'counter_serve', b.counter_serve, 'show_stock', b.show_stock,
    'free_bar', b.free_bar, 'limit_glasses', b.limit_glasses, 'limit_chf', b.limit_chf,
    'staff_adjust_stock', b.staff_adjust_stock, 'staff_unavailable', b.staff_unavailable, 'staff_correct', b.staff_correct,
    'staff_prices', b.staff_prices, 'staff_items', b.staff_items);
$$;

-- Service sans commande permis : interrupteur de l'organisateur, ou commandes dans l'app éteintes (sinon rien ne se sert).
create or replace function private.bar_counter_on(b public.event_bars) returns boolean
language sql stable set search_path = '' as $$
  select b.counter_serve or not b.guest_orders;
$$;

-- Ce que je peux faire au bar (organisateur : tout ; barman : ce que l'organisateur a permis ; sinon rien).
create or replace function private.bar_may(e uuid, what text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.bar_can_manage(e) or (private.bar_can_serve(e) and coalesce((
    select case what when 'adjust_stock' then b.staff_adjust_stock when 'unavailable' then b.staff_unavailable
                     when 'correct' then b.staff_correct when 'prices' then b.staff_prices or b.staff_items
                     when 'items' then b.staff_items else false end
    from public.event_bars b where b.event_id = e), false));
$$;

create or replace function private.bar_rights(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select case when private.bar_can_serve(e) then jsonb_build_object('adjust_stock', private.bar_may(e, 'adjust_stock'),
    'unavailable', private.bar_may(e, 'unavailable'), 'correct', private.bar_may(e, 'correct'),
    'prices', private.bar_may(e, 'prices'), 'items', private.bar_may(e, 'items')) end;
$$;

-- Un article vu par l'organisateur ou le barman : stock acheté, servis, réservés, disponible (virtuel), reste (physique).
create or replace function private.bar_item_json(i public.event_bar_items) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', i.price_chf, 'stock', i.stock,
    'age_min', i.age_min, 'max_pending', i.max_pending, 'sort', i.sort, 'active', i.active, 'category', i.category,
    'detail', i.detail, 'max_per_person', i.max_per_person, 'unavailable', i.unavailable, 'served', c.served, 'pending', c.pending,
    'available', case when i.stock is null then null else i.stock - c.served - c.pending end,
    'left', case when i.stock is null then null else i.stock - c.served end)
  from private.bar_counts(i.id) c;
$$;

-- Engagement de la version en cours accepté par cette personne (le plus récent), sinon null.
create or replace function private.bar_pledged(b public.event_bars, member uuid) returns uuid
language sql stable security definer set search_path = '' as $$
  select p.id from public.event_bar_pledges p where p.event_id = b.event_id and p.user_id = member and p.terms_version = b.terms_version
  order by p.accepted_at desc limit 1;
$$;

-- Limites de la soirée pour une personne, avant d'ajouter `adding` verres de cet article (au prix `price`).
-- Servis + en attente comptent ; annulés et corrigés (servis par erreur, pas dus) non. Appelé sous le verrou de la personne.
drop function if exists private.bar_check_limits(public.event_bars, public.event_bar_items, uuid, int, numeric);  -- première écriture, jamais déployée
create or replace function private.bar_check_limits(b public.event_bars, it public.event_bar_items, member uuid, adding bigint, price numeric)
returns void language plpgsql stable security definer set search_path = '' as $$
declare mine bigint; glasses bigint; spent numeric;
begin
  if it.max_per_person is not null then
    select count(*) into mine from public.event_bar_units u where u.item_id = it.id and u.user_id = member and u.status in ('pending', 'served');
    if mine + adding > it.max_per_person then
      raise exception 'max_person: % : % au plus par personne pour la soirée (déjà % servi% ou en attente).',
        it.name, it.max_per_person, mine, case when mine > 1 then 's' else '' end using errcode = '22023';
    end if;
  end if;
  select count(*), coalesce(sum(u.price_chf), 0) into glasses, spent from public.event_bar_units u
    where u.event_id = b.event_id and u.user_id = member and u.status in ('pending', 'served');
  if b.limit_glasses is not null and glasses + adding > b.limit_glasses then
    raise exception 'limit_glasses: % verres au plus par personne pour la soirée (déjà % servi% ou en attente).',
      b.limit_glasses, glasses, case when glasses > 1 then 's' else '' end using errcode = '22023';
  end if;
  if b.limit_chf is not null and spent + adding * price > b.limit_chf then
    raise exception 'limit_chf: % au plus par personne pour la soirée (déjà %).', private.bar_chf(b.limit_chf), private.bar_chf(spent)
      using errcode = '22023';
  end if;
end $$;

-- Deux commandes (ou une commande et un service au comptoir) d'une même personne passent l'une après l'autre : les
-- limites de la soirée se comptent juste. Toujours AVANT les verrous des articles (même ordre partout, sans interblocage).
create or replace function private.bar_lock_person(e uuid, member uuid) returns void
language sql security definer set search_path = '' as $$
  select pg_advisory_xact_lock(hashtextextended('bar_person:' || e || ':' || member, 0));
$$;

-- 3. Organisateurs : options ---------------------------------------------------------------------------------------------
create or replace function public.bar_save_settings(e uuid, settings jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; nb public.event_bars; who uuid; ev public.events; flag text;
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
  -- Options (A) : interrupteurs (vrai / faux), limites (vide = sans limite).
  foreach flag in array array['guest_orders', 'counter_serve', 'show_stock', 'free_bar', 'staff_adjust_stock', 'staff_unavailable',
                              'staff_correct', 'staff_prices', 'staff_items'] loop
    if settings ? flag and jsonb_typeof(settings->flag) <> 'boolean' then
      raise exception 'Option % : vrai ou faux.', flag using errcode = '22023';
    end if;
  end loop;
  if settings ? 'guest_orders' then nb.guest_orders := (settings->>'guest_orders')::boolean; end if;
  if settings ? 'counter_serve' then nb.counter_serve := (settings->>'counter_serve')::boolean; end if;
  if settings ? 'show_stock' then nb.show_stock := (settings->>'show_stock')::boolean; end if;
  if settings ? 'free_bar' then nb.free_bar := (settings->>'free_bar')::boolean; end if;
  if settings ? 'staff_adjust_stock' then nb.staff_adjust_stock := (settings->>'staff_adjust_stock')::boolean; end if;
  if settings ? 'staff_unavailable' then nb.staff_unavailable := (settings->>'staff_unavailable')::boolean; end if;
  if settings ? 'staff_correct' then nb.staff_correct := (settings->>'staff_correct')::boolean; end if;
  if settings ? 'staff_prices' then nb.staff_prices := (settings->>'staff_prices')::boolean; end if;
  if settings ? 'staff_items' then nb.staff_items := (settings->>'staff_items')::boolean; end if;
  if settings ? 'limit_glasses' then
    if coalesce(nullif(settings->>'limit_glasses', ''), '1') !~ '^\d{1,4}$'
       or coalesce(nullif(settings->>'limit_glasses', '')::int, 1) not between 1 and 200 then
      raise exception 'Limite de verres : de 1 à 200 par personne, ou vide pour sans limite.' using errcode = '22023';
    end if;
    nb.limit_glasses := nullif(settings->>'limit_glasses', '')::int;
  end if;
  if settings ? 'limit_chf' then
    if coalesce(nullif(settings->>'limit_chf', ''), '1') !~ '^\d{1,4}(\.\d{1,2})?$'
       or coalesce(nullif(settings->>'limit_chf', '')::numeric, 1) not between 1 and 5000 then
      raise exception 'Limite en CHF : de 1 à 5000 par personne, ou vide pour sans limite.' using errcode = '22023';
    end if;
    nb.limit_chf := nullif(settings->>'limit_chf', '')::numeric;
  end if;
  if not nb.guest_orders and not nb.counter_serve then
    raise exception 'Sans commande dans l''app, le service au comptoir doit rester allumé (sinon personne ne peut être servi).' using errcode = '22023';
  end if;
  -- Bar offert : seulement tant qu'aucun verre payant n'attend ni n'est servi (jamais de dette effacée ou changée en douce).
  if nb.free_bar and not b.free_bar and exists (select 1 from public.event_bar_units u where u.event_id = e and u.status in ('pending', 'served') and u.price_chf > 0) then
    raise exception 'Des verres payants sont déjà commandés ou servis : le bar offert se choisit avant les premières commandes.' using errcode = '22023';
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
    closes_at = nb.closes_at, pay_method = nb.pay_method, repay_by = nb.repay_by, payee_id = nb.payee_id, terms_version = nb.terms_version,
    guest_orders = nb.guest_orders, counter_serve = nb.counter_serve, show_stock = nb.show_stock, free_bar = nb.free_bar,
    limit_glasses = nb.limit_glasses, limit_chf = nb.limit_chf, staff_adjust_stock = nb.staff_adjust_stock,
    staff_unavailable = nb.staff_unavailable, staff_correct = nb.staff_correct, staff_prices = nb.staff_prices, staff_items = nb.staff_items
    where event_id = e;
  perform private.bar_log(e, 'settings', null, null, null, null, settings);
  if nb.terms_version > b.terms_version and not nb.free_bar then
    select * into ev from public.events where id = e;
    for who in select distinct u.user_id from public.event_bar_units u where u.event_id = e and u.status in ('pending', 'served') loop
      perform public.queue_notification(who, 'bar_changed', e, ev.title,
        'Conditions du bar changées : ' || private.bar_pledge_text(nb), 'bar_terms:' || e || ':' || nb.terms_version || ':' || who);
    end loop;
  end if;
  return public.bar_overview(e);
end $$;

-- 4. Articles (organisateur ; barman si l'organisateur le permet) ------------------------------------------------------
create or replace function public.bar_save_item(e uuid, item jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare it public.event_bar_items; item_id uuid := nullif(item->>'id', '')::uuid; clean text; clean_detail text; over bigint := 0; c record;
        cat text := nullif(item->>'category', ''); per int;
begin
  if not private.bar_may(e, 'items') then raise exception 'forbidden: réservé aux organisateurs (et aux barmans s''ils y sont autorisés)' using errcode = '42501'; end if;
  perform private.bar_require(e);
  perform private.require_terms(auth.uid());  -- nom et précision d'article : contenu vu des invités
  clean := private.item_text_verdict(btrim(coalesce(item->>'name', '')), 'Article');
  if cat is not null and cat not in ('softs', 'bieres', 'vins', 'cocktails', 'shots', 'autre') then
    raise exception 'Catégorie inconnue : Softs, Bières, Vins, Cocktails, Shots ou Autre.' using errcode = '22023';
  end if;
  if item ? 'detail' then
    clean_detail := nullif(btrim(coalesce(item->>'detail', '')), '');
    if char_length(clean_detail) > 30 then raise exception 'Précision : 30 signes au plus (par exemple « 33 cl »).' using errcode = '22023'; end if;
    if clean_detail is not null then clean_detail := private.item_text_verdict(clean_detail, 'Précision'); end if;
  end if;
  if item ? 'max_per_person' then
    per := nullif(item->>'max_per_person', '')::int;
    if per is not null and per not between 1 and 100 then
      raise exception 'Maximum par personne pour la soirée : de 1 à 100, ou vide pour sans limite.' using errcode = '22023';
    end if;
  end if;
  if item_id is null then
    insert into public.event_bar_items (event_id, name, emoji, price_chf, stock, age_min, max_pending, sort, category, detail, max_per_person, unavailable)
    values (e, clean, nullif(item->>'emoji', ''), (item->>'price_chf')::numeric, nullif(item->>'stock', '')::int,
            coalesce(nullif(item->>'age_min', '')::int, 0), nullif(item->>'max_pending', '')::int,
            coalesce(nullif(item->>'sort', '')::int, (select coalesce(max(i.sort), 0) + 1 from public.event_bar_items i where i.event_id = e)),
            coalesce(cat, 'autre'), clean_detail, per, coalesce((item->>'unavailable')::boolean, false))
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
      active = coalesce((item->>'active')::boolean, i.active),
      category = coalesce(cat, i.category),
      detail = case when item ? 'detail' then clean_detail else i.detail end,
      max_per_person = case when item ? 'max_per_person' then per else i.max_per_person end,
      unavailable = coalesce((item->>'unavailable')::boolean, i.unavailable)
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

-- Gestes de la soirée sur un article (C) : « Il en reste… » (stock physique restant), « + Réassort », « Indisponible »,
-- « De nouveau dispo », « Prix ». Chacun noté au journal.
create or replace function public.bar_item_action(e uuid, item uuid, action text, amount numeric default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare it public.event_bar_items; c record; next_stock int; right_needed text;
begin
  right_needed := case action when 'remaining' then 'adjust_stock' when 'restock' then 'adjust_stock'
                              when 'unavailable' then 'unavailable' when 'available' then 'unavailable' when 'price' then 'prices' end;
  if right_needed is null then raise exception 'Geste inconnu' using errcode = '22023'; end if;
  if not private.bar_may(e, right_needed) then
    raise exception 'forbidden: réservé aux organisateurs (et aux barmans s''ils y sont autorisés)' using errcode = '42501';
  end if;
  perform private.bar_require(e);
  select * into it from public.event_bar_items i where i.id = item and i.event_id = e for update;
  if it.id is null then raise exception 'not_found: article introuvable' using errcode = 'P0002'; end if;
  select * into c from private.bar_counts(it.id);
  if action = 'remaining' then
    if amount is null or amount <> trunc(amount) or amount < 0 or amount > 100000 then
      raise exception 'Il en reste : un nombre entier, de 0 à 100000.' using errcode = '22023';
    end if;
    next_stock := c.served + amount::int;  -- reste physique = stock − servis
    if next_stock > 100000 then raise exception 'Stock trop grand' using errcode = '22023'; end if;
    update public.event_bar_items set stock = next_stock where id = it.id;
    perform private.bar_log(e, 'stock_set', null, it.id, amount::int, null, jsonb_build_object('before', it.stock, 'after', next_stock));
  elsif action = 'restock' then
    if it.stock is null then raise exception 'Stock illimité : rien à réassortir.' using errcode = '22023'; end if;
    if amount is null or amount <> trunc(amount) or amount < 1 or amount > 10000 then
      raise exception 'Réassort : un nombre entier, de 1 à 10000.' using errcode = '22023';
    end if;
    next_stock := it.stock + amount::int;
    if next_stock > 100000 then raise exception 'Stock trop grand' using errcode = '22023'; end if;
    update public.event_bar_items set stock = next_stock where id = it.id;
    perform private.bar_log(e, 'restock', null, it.id, amount::int, null, jsonb_build_object('before', it.stock, 'after', next_stock));
  elsif action in ('unavailable', 'available') then
    update public.event_bar_items set unavailable = (action = 'unavailable') where id = it.id;
    perform private.bar_log(e, action, null, it.id, null, null, jsonb_build_object('name', it.name));
  else
    if amount is null or amount < 0 or amount > 500 or round(amount, 2) <> amount then
      raise exception 'Prix : de 0 à 500 CHF, au centime près.' using errcode = '22023';
    end if;
    update public.event_bar_items set price_chf = amount where id = it.id;
    perform private.bar_log(e, 'price_set', null, it.id, null, amount, jsonb_build_object('before', it.price_chf));
  end if;
  select * into it from public.event_bar_items where id = item;
  return private.bar_item_json(it);
end $$;

-- Carte complète pour l'écran de service (barman, organisateur) : articles et droits.
create or replace function public.bar_staff_items(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not private.bar_can_serve(e) then raise exception 'forbidden: réservé aux barmans et organisateurs de la soirée' using errcode = '42501'; end if;
  perform private.bar_require(e);
  return jsonb_build_object('rights', private.bar_rights(e),
    'items', coalesce((select jsonb_agg(private.bar_item_json(i) order by i.sort, i.name) from public.event_bar_items i where i.event_id = e), '[]'::jsonb));
end $$;

-- 5. Vue d'ensemble de l'organisateur --------------------------------------------------------------------------------
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
    'pledge_text', private.bar_pledge_text(b), 'terms_version', b.terms_version, 'options', private.bar_options(b),
    'items', coalesce((select jsonb_agg(private.bar_item_json(i) order by i.sort, i.name) from public.event_bar_items i where i.event_id = e), '[]'::jsonb),
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
        where l.event_id = e and l.kind in ('cancelled_mine', 'cancelled_by_organizer') order by l.at desc limit 10) s), '[]'::jsonb),
    -- Gestes de la soirée sur la carte (qui, quoi, combien) : les 15 derniers.
    'stock_log', coalesce((select jsonb_agg(x) from (
        select jsonb_build_object('at', l.at, 'actor', p.display_name, 'item', i.name, 'kind', l.kind, 'qty', l.qty, 'amount', l.amount) x
        from public.event_bar_log l left join public.profiles p on p.id = l.actor left join public.event_bar_items i on i.id = l.item_id
        where l.event_id = e and l.kind in ('stock_set', 'restock', 'unavailable', 'available', 'price_set') order by l.id desc limit 15) s), '[]'::jsonb));
end $$;

-- 6. Invités -----------------------------------------------------------------------------------------------------------
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
  -- Coordonnées de paiement (IBAN, lien) : seulement à qui peut commander (bar payant), doit de l'argent, ou gère le bar.
  owes := (eligible and not b.free_bar) or private.bar_balance(e, me) > 0 or private.bar_can_manage(e);
  if owes then select * into pay from public.tc_payment where user_id = b.payee_id; end if;
  return jsonb_build_object(
    'phase', private.bar_phase(b), 'eligible', eligible, 'manage', private.bar_can_manage(e), 'serve', private.bar_can_serve(e),
    'closes_at', b.closes_at, 'preorder_until', b.preorder_until,
    'options', private.bar_options(b), 'rights', private.bar_rights(e),
    'pledge_text', private.bar_pledge_text(b), 'pledge_version', b.terms_version,
    'pledged_current', private.bar_pledged(b, me) is not null,
    'payee', jsonb_build_object('id', b.payee_id, 'name', (select display_name from public.profiles where id = b.payee_id),
      'method', b.pay_method, 'repay_by', b.repay_by,
      'iban', case when b.pay_method = 'iban' then pay.iban end, 'holder', case when b.pay_method = 'iban' then pay.holder end,
      'link', case b.pay_method when 'revolut' then pay.links->>'revolut' when 'twint' then pay.links->>'twint' end),
    'qr', case when eligible then jsonb_build_object('token', t.token, 'code', t.code) end,
    'balance', private.bar_balance(e, me),
    'pending_total', coalesce((select sum(u.price_chf) from public.event_bar_units u where u.event_id = e and u.user_id = me and u.status = 'pending'), 0),
    'refund_declared', coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = me and r.status = 'declared'), 0),
    -- Ma soirée, pour les limites par personne (servis + en attente).
    'mine', (select jsonb_build_object('glasses', count(*), 'chf', coalesce(sum(u.price_chf), 0)) from public.event_bar_units u
             where u.event_id = e and u.user_id = me and u.status in ('pending', 'served')),
    'items', coalesce((select jsonb_agg(jsonb_build_object(
        'id', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', case when b.free_bar then 0 else i.price_chf end,
        'age_min', i.age_min, 'max_pending', i.max_pending, 'category', i.category, 'detail', i.detail,
        'max_per_person', i.max_per_person, 'unavailable', i.unavailable, 'active', i.active,
        -- Stock montré seulement si l'organisateur le veut ; « épuisé » se dit toujours.
        'available', case when i.stock is null or not b.show_stock then null else greatest(i.stock - c.served - c.pending, 0) end,
        'sold_out', i.stock is not null and i.stock - c.served - c.pending <= 0,
        'mine_pending', (select count(*) from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status = 'pending'),
        'mine_total', (select count(*) from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status in ('pending', 'served')),
        'mine_pending_chf', (select coalesce(sum(u.price_chf), 0) from public.event_bar_units u where u.item_id = i.id and u.user_id = me and u.status = 'pending'))
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

-- Accepter l'engagement sans commander (service au comptoir, bar payant) : le texte exact est gardé.
create or replace function public.bar_pledge(e uuid, pledge_text text, pledge_version int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid();
begin
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  b := private.bar_require(e);
  if not private.bar_eligible(e, me) then
    raise exception 'forbidden: seules les personnes notées « Présent », au profil complet, sont servies au bar' using errcode = '42501';
  end if;
  if b.free_bar then raise exception 'Bar offert : rien à rembourser, pas d''engagement.' using errcode = '22023'; end if;
  if private.bar_phase(b) = 'closed' then raise exception 'Le bar est fermé.' using errcode = '22023'; end if;
  if pledge_version is distinct from b.terms_version or pledge_text is distinct from private.bar_pledge_text(b) then
    raise exception 'terms_changed: les conditions de remboursement ont changé, relis-les puis recoche l''engagement' using errcode = '22023';
  end if;
  if private.bar_pledged(b, me) is null then
    insert into public.event_bar_pledges (event_id, user_id, text, terms_version) values (e, me, pledge_text, b.terms_version);
    perform private.bar_log(e, 'pledged', me, null, null, null);
  end if;
  return public.my_bar(e);
end $$;

-- Commande (tout ou rien) : options de l'organisateur, engagement (bar payant), stock virtuel, indisponibilités, maximum
-- en attente, limites de la soirée, sous verrous (la personne, puis les articles dans l'ordre des id).
create or replace function public.bar_order(e uuid, lines jsonb, pledge_text text, pledge_version int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); phase text; pledge uuid; line record; it public.event_bar_items; c record;
        mine bigint; preorder boolean; price numeric;
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
  if not b.guest_orders then
    raise exception 'counter_only: les commandes se font au comptoir : montre ton QR au barman.' using errcode = '22023';
  end if;
  preorder := phase = 'preorder';
  if not b.free_bar and (pledge_version is distinct from b.terms_version or pledge_text is distinct from private.bar_pledge_text(b)) then
    raise exception 'terms_changed: les conditions de remboursement ont changé, relis-les puis recoche l''engagement' using errcode = '22023';
  end if;
  if jsonb_typeof(lines) <> 'array' or jsonb_array_length(lines) = 0 then raise exception 'Commande vide' using errcode = '22023'; end if;
  if jsonb_array_length(lines) > 50 then raise exception 'Commande trop longue : 50 lignes au plus.' using errcode = '22023'; end if;
  perform private.bar_lock_person(e, me);
  if not b.free_bar then
    insert into public.event_bar_pledges (event_id, user_id, text, terms_version) values (e, me, pledge_text, b.terms_version) returning id into pledge;
  end if;
  for line in select (l->>'item')::uuid item, sum((l->>'qty')::int) qty from jsonb_array_elements(lines) l group by 1 order by 1 loop
    if line.qty is null or line.qty < 1 or line.qty > 50 then raise exception 'Quantité invalide' using errcode = '22023'; end if;
    select * into it from public.event_bar_items i where i.id = line.item and i.event_id = e and i.active for update;
    if it.id is null then raise exception 'Cet article n''est plus proposé.' using errcode = '22023'; end if;
    if it.unavailable then raise exception 'unavailable: % est indisponible pour l''instant.', it.name using errcode = '22023'; end if;
    select * into c from private.bar_counts(it.id);
    if it.stock is not null and c.served + c.pending + line.qty > it.stock then
      raise exception 'stock: % — plus que % disponible%', it.name, greatest(it.stock - c.served - c.pending, 0),
        case when it.stock - c.served - c.pending > 1 then 's' else '' end using errcode = '22023';
    end if;
    if not preorder then
      select count(*) into mine from public.event_bar_units u where u.item_id = it.id and u.user_id = me and u.status = 'pending';
      if mine + line.qty > coalesce(it.max_pending, 10) then
        raise exception 'max_pending: maximum % % en attente par personne (tu en as déjà % pas encore servi%)',
          coalesce(it.max_pending, 10), it.name, mine, case when mine > 1 then 's' else '' end using errcode = '22023';
      end if;
    end if;
    price := case when b.free_bar then 0 else it.price_chf end;
    perform private.bar_check_limits(b, it, me, line.qty, price);
    insert into public.event_bar_units (event_id, item_id, user_id, pledge_id, price_chf, preorder)
    select e, it.id, me, pledge, price, preorder from generate_series(1, line.qty);
    perform private.bar_log(e, 'ordered', me, it.id, line.qty, price * line.qty, jsonb_build_object('preorder', preorder));
  end loop;
  return public.my_bar(e);
end $$;

-- 7. Barman ------------------------------------------------------------------------------------------------------------
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
    'pledged_current', private.bar_pledged(b, member) is not null,
    'balance', private.bar_balance(e, member),
    'free', b.free_bar, 'counter', private.bar_counter_on(b), 'rights', private.bar_rights(e),
    'pending', coalesce((select jsonb_agg(x order by x->>'name') from (
        select jsonb_build_object('item', i.id, 'name', i.name, 'emoji', i.emoji, 'price_chf', i.price_chf, 'age_min', i.age_min,
          'qty', count(*),
          'prices', jsonb_agg(u.price_chf order by u.preorder desc, u.ordered_at),
          'stock', case when i.stock is null then null else i.stock - (select c.served from private.bar_counts(i.id) c) end) x
        from public.event_bar_units u join public.event_bar_items i on i.id = u.item_id
        where u.event_id = e and u.user_id = member and u.status = 'pending' group by i.id) s), '[]'::jsonb),
    -- Carte du comptoir (service sans commande) : articles proposés, avec ce qui est encore libre (stock virtuel).
    'menu', case when private.bar_counter_on(b) then coalesce((select jsonb_agg(jsonb_build_object('item', i.id, 'name', i.name,
        'emoji', i.emoji, 'detail', i.detail, 'category', i.category, 'price_chf', case when b.free_bar then 0 else i.price_chf end,
        'age_min', i.age_min, 'unavailable', i.unavailable,
        'available', case when i.stock is null then null else greatest(i.stock - c.served - c.pending, 0) end) order by i.sort, i.name)
      from public.event_bar_items i cross join lateral private.bar_counts(i.id) c where i.event_id = e and i.active), '[]'::jsonb)
      else '[]'::jsonb end);
end $$;

-- Servir : `qty` verres pris dans ce que la personne a commandé (comme avant), plus `extra` verres servis au comptoir sans
-- commande (si l'organisateur le permet : mêmes règles qu'une commande, engagement compris en bar payant).
create or replace function public.bar_serve(e uuid, member uuid, lines jsonb, client_key text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars; me uuid := auth.uid(); done public.event_bar_serves; serve uuid := gen_random_uuid(); line record;
        it public.event_bar_items; c record; total numeric := 0; served_lines jsonb := '[]'::jsonb; before numeric; ev public.events; n int;
        summary text; pledge uuid; price numeric; who text;
begin
  if not private.bar_can_serve(e) then raise exception 'forbidden: réservé aux barmans et organisateurs de la soirée' using errcode = '42501'; end if;
  if jsonb_typeof(lines) <> 'array' or jsonb_array_length(lines) > 50 then raise exception 'Service trop long : 50 lignes au plus.' using errcode = '22023'; end if;
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
  perform private.bar_lock_person(e, member);
  before := private.bar_balance(e, member);
  select display_name into who from public.profiles where id = member;
  for line in select (l->>'item')::uuid item, sum(coalesce((l->>'qty')::int, 0)) qty, sum(coalesce((l->>'extra')::int, 0)) extra
              from jsonb_array_elements(lines) l group by 1 order by 1 loop
    if line.qty < 0 or line.extra < 0 or line.qty + line.extra < 1 or line.qty + line.extra > 50 then
      raise exception 'Quantité invalide' using errcode = '22023';
    end if;
    select * into it from public.event_bar_items i where i.id = line.item and i.event_id = e for update;
    if it.id is null then raise exception 'Article introuvable' using errcode = '22023'; end if;
    select * into c from private.bar_counts(it.id);
    n := 0;
    if line.qty > 0 then
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
        raise exception 'already_served: % — plus que % en attente (déjà servi, ou commande annulée entre-temps)', it.name, n using errcode = '22023';
      end if;
    end if;
    if line.extra > 0 then
      if not private.bar_counter_on(b) then
        raise exception 'counter_off: le service sans commande est éteint : la personne commande d''abord dans « Mon bar ».' using errcode = '22023';
      end if;
      if not it.active then raise exception 'Cet article n''est plus proposé.' using errcode = '22023'; end if;
      if it.unavailable then raise exception 'unavailable: % est indisponible pour l''instant.', it.name using errcode = '22023'; end if;
      pledge := null;
      if not b.free_bar then
        pledge := private.bar_pledged(b, member);
        if pledge is null then
          raise exception 'pledge_required: % n''a pas encore accepté l''engagement à rembourser : il ou elle le coche dans « Mon bar ».',
            coalesce(nullif(btrim(who), ''), 'Cette personne') using errcode = '22023';
        end if;
      end if;
      if it.stock is not null and c.served + c.pending + line.extra > it.stock then
        raise exception 'stock: % — plus que % disponible%', it.name, greatest(it.stock - c.served - c.pending, 0),
          case when it.stock - c.served - c.pending > 1 then 's' else '' end using errcode = '22023';
      end if;
      price := case when b.free_bar then 0 else it.price_chf end;
      perform private.bar_check_limits(b, it, member, line.extra, price);
      insert into public.event_bar_units (event_id, item_id, user_id, pledge_id, price_chf, status, served_at, served_by, serve_id, counter)
      select e, it.id, member, pledge, price, 'served', now(), me, serve, true from generate_series(1, line.extra);
    end if;
    total := total + coalesce((select sum(u.price_chf) from public.event_bar_units u where u.serve_id = serve and u.item_id = it.id), 0);
    served_lines := served_lines || jsonb_build_object('item', it.id, 'name', it.name, 'emoji', it.emoji, 'qty', n + line.extra);
    perform private.bar_log(e, 'served', member, it.id, n + line.extra, null, jsonb_build_object('serve_id', serve, 'counter', line.extra));
  end loop;
  insert into public.event_bar_serves (id, event_id, user_id, served_by, total_chf, client_key) values (serve, e, member, me, total, bar_serve.client_key);
  select * into ev from public.events where id = e;
  select string_agg((x->>'qty') || ' ' || (x->>'name'), ', ') into summary from jsonb_array_elements(served_lines) x;
  perform public.queue_notification(member, 'bar_served', e, ev.title,
    case when b.free_bar then 'Servi : ' || summary || '. Bar offert.'
         else 'Servi : ' || summary || ' (' || private.bar_chf(total) || '). À rembourser : ' || private.bar_chf(before + total) || '.' end,
    'bar_served:' || serve, jsonb_build_object('serve_id', serve, 'balance', before + total));
  return jsonb_build_object('serve_id', serve, 'total', total, 'balance_before', before, 'balance', before + total, 'lines', served_lines);
end $$;

-- Annuler un service : le même barman dans les 15 s, si l'organisateur le permet. Verres servis au comptoir sans commande :
-- annulés (rien à payer) ; verres commandés : de nouveau en attente.
create or replace function public.bar_undo_serve(e uuid, serve uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare s public.event_bar_serves; ev public.events; n int; extra int;
begin
  select * into s from public.event_bar_serves x where x.id = serve and x.event_id = e for update;
  if s.id is null or s.undone_at is not null then raise exception 'Service introuvable ou déjà annulé' using errcode = '22023'; end if;
  if exists (select 1 from public.event_bars b where b.event_id = e and b.closed_at is not null) then
    raise exception 'Le bar est fermé : un organisateur peut corriger depuis la fiche de la personne.' using errcode = '22023';
  end if;
  if not (s.served_by = auth.uid() and now() - s.served_at <= interval '15 seconds') then
    raise exception 'forbidden: trop tard pour annuler ici : un organisateur peut corriger depuis la fiche de la personne' using errcode = '42501';
  end if;
  if not private.bar_may(e, 'correct') then
    raise exception 'forbidden: l''organisateur garde pour lui l''annulation des services : demande-lui de corriger' using errcode = '42501';
  end if;
  -- Servis au comptoir : rien n'avait été commandé, ils sont annulés (servi → en attente → annulé : passages permis).
  update public.event_bar_units set status = 'pending' where serve_id = s.id and status = 'served' and counter;
  update public.event_bar_units set status = 'cancelled', cancelled_at = now(), cancelled_by = auth.uid(), cancel_reason = 'undone'
    where serve_id = s.id and status = 'pending' and counter;
  get diagnostics extra = row_count;
  update public.event_bar_units set status = 'pending', served_at = null, served_by = null, serve_id = null
    where serve_id = s.id and status = 'served';
  get diagnostics n = row_count;
  update public.event_bar_serves set undone_at = now(), undone_by = auth.uid() where id = s.id;
  perform private.bar_log(e, 'serve_undone', s.user_id, null, n + extra, s.total_chf, jsonb_build_object('serve_id', s.id, 'counter', extra));
  select * into ev from public.events where id = e;
  perform public.queue_notification(s.user_id, 'bar_changed', e, ev.title,
    'Service annulé par le barman : ' || private.bar_chf(s.total_chf) || ' retirés. À rembourser : ' || private.bar_chf(private.bar_balance(e, s.user_id)) || '.',
    'bar_undo:' || s.id);
  return jsonb_build_object('undone', n + extra, 'balance', private.bar_balance(e, s.user_id));
end $$;

-- Annuler des verres en attente d'une personne : organisateur, ou barman si l'organisateur le permet.
create or replace function public.bar_cancel_units(e uuid, member uuid, item uuid, qty int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; n int; label text; manager boolean := private.bar_can_manage(e);
begin
  if not private.bar_may(e, 'correct') then raise exception 'forbidden: réservé aux organisateurs (et aux barmans s''ils y sont autorisés)' using errcode = '42501'; end if;
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
  perform private.bar_log(e, 'cancelled_by_organizer', member, item, n, null, jsonb_build_object('by_barman', not manager));
  select * into ev from public.events where id = e;
  perform public.queue_notification(member, 'bar_changed', e, ev.title,
    case when manager then 'L''organisateur' else 'Le barman' end || ' a annulé ' || n || ' ' || label
      || ' en attente : rien à payer pour ' || case when n > 1 then 'eux.' else 'lui.' end,
    'bar_cancel:' || e || ':' || member || ':' || extract(epoch from clock_timestamp())::bigint);
  if manager then return public.bar_person(e, member); end if;
  return jsonb_build_object('cancelled', n);
end $$;

-- 8. Droits ------------------------------------------------------------------------------------------------------------
revoke all on function private.bar_options(public.event_bars), private.bar_counter_on(public.event_bars), private.bar_may(uuid, text),
  private.bar_rights(uuid), private.bar_item_json(public.event_bar_items), private.bar_pledged(public.event_bars, uuid),
  private.bar_check_limits(public.event_bars, public.event_bar_items, uuid, bigint, numeric), private.bar_lock_person(uuid, uuid)
  from public, anon, authenticated;
revoke all on function public.bar_item_action(uuid, uuid, text, numeric), public.bar_staff_items(uuid), public.bar_pledge(uuid, text, int),
  public.bar_save_settings(uuid, jsonb), public.bar_save_item(uuid, jsonb), public.bar_overview(uuid), public.my_bar(uuid),
  public.bar_order(uuid, jsonb, text, int), public.bar_scan(uuid, text), public.bar_serve(uuid, uuid, jsonb, text),
  public.bar_undo_serve(uuid, uuid), public.bar_cancel_units(uuid, uuid, uuid, int) from public, anon;
grant execute on function public.bar_item_action(uuid, uuid, text, numeric), public.bar_staff_items(uuid), public.bar_pledge(uuid, text, int),
  public.bar_save_settings(uuid, jsonb), public.bar_save_item(uuid, jsonb), public.bar_overview(uuid), public.my_bar(uuid),
  public.bar_order(uuid, jsonb, text, int), public.bar_scan(uuid, text), public.bar_serve(uuid, uuid, jsonb, text),
  public.bar_undo_serve(uuid, uuid), public.bar_cancel_units(uuid, uuid, uuid, int) to authenticated;

notify pgrst, 'reload schema';

insert into supabase_migrations.schema_migrations (version, name) values ('20261110120000', 'bar_soiree'), ('20261110130000', 'bar_wallet'), ('20261110140000', 'bar_corrections'), ('20261110150000', 'bar_compte_supprime'), ('20261110160000', 'bar_options')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
