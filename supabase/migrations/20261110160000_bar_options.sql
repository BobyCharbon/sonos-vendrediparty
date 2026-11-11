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
