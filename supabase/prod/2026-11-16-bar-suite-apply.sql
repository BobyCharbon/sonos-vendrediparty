-- PROD, suite du bar : devise (20261116090000), récapitulatif (20261116100000), notification « verre servi » (20261116120000).
-- À appliquer APRÈS 2026-11-10-bar-soiree-apply.sql. Rejouable. Tout ou rien. Aucune donnée existante modifiée.
begin;

-- ===== 20261116090000_bar_devise =====
-- Bar de la soirée : devise choisie par l'organisateur, francs (CHF, défaut) ou euros (demande de l'admin du 16.11.2026).
-- Réglage « Options » du bar ; il se choisit avant les premières commandes payantes (jamais une dette de 8 CHF changée
-- en 8 € en douce), comme « Bar offert ». Les montants des messages du bar (servi, remboursement, limites) suivent la
-- devise : private.bar_chf(n, e). Le nom des colonnes (price_chf, limit_chf…) ne change pas.
-- Purement additif et rejouable. Le bar n'est pas en production : cette migration part avec lui.

alter table public.event_bars add column if not exists currency text not null default 'CHF';
alter table public.event_bars drop constraint if exists event_bars_currency_check;
alter table public.event_bars add constraint event_bars_currency_check check (currency in ('CHF', 'EUR'));

-- « 4.50 CHF » / « 4.50 € » selon le bar de l'événement.
create or replace function private.bar_chf(n numeric, e uuid) returns text
language sql stable set search_path = '' as $$
  select case when n = trunc(n) then trunc(n)::text else to_char(n, 'FM999990.00') end || ' '
    || case (select b.currency from public.event_bars b where b.event_id = e) when 'EUR' then '€' else 'CHF' end;
$$;
revoke all on function private.bar_chf(numeric, uuid) from public, anon, authenticated;

create or replace function private.bar_options(b public.event_bars) returns jsonb
language sql stable set search_path = '' as $$
  select jsonb_build_object('guest_orders', b.guest_orders, 'counter_serve', b.counter_serve, 'show_stock', b.show_stock,
    'free_bar', b.free_bar, 'limit_glasses', b.limit_glasses, 'limit_chf', b.limit_chf,
    'staff_adjust_stock', b.staff_adjust_stock, 'staff_unavailable', b.staff_unavailable, 'staff_correct', b.staff_correct,
    'staff_prices', b.staff_prices, 'staff_items', b.staff_items, 'currency', b.currency);
$$;

-- Choisir la devise : organisateurs seulement, avant tout verre payant commandé ou servi et tout remboursement.
create or replace function public.bar_set_currency(e uuid, currency text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.event_bars;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into b from public.event_bars where event_id = e for update;
  if b.event_id is null then raise exception 'not_found: pas de bar pour cet événement' using errcode = 'P0002'; end if;
  if currency is null or currency not in ('CHF', 'EUR') then raise exception 'Devise : francs (CHF) ou euros (EUR).' using errcode = '22023'; end if;
  if currency = b.currency then return public.bar_overview(e); end if;
  if exists (select 1 from public.event_bar_units u where u.event_id = e and u.status in ('pending', 'served') and u.price_chf > 0)
     or exists (select 1 from public.event_bar_refunds r where r.event_id = e) then
    raise exception 'Des verres payants sont déjà commandés ou servis : la devise se choisit avant les premières commandes.' using errcode = '22023';
  end if;
  update public.event_bars set currency = bar_set_currency.currency where event_id = e;
  perform private.bar_log(e, 'settings', null, null, null, null, jsonb_build_object('currency', currency));
  return public.bar_overview(e);
end $$;
revoke all on function public.bar_set_currency(uuid, text) from public, anon;
grant execute on function public.bar_set_currency(uuid, text) to authenticated;

-- Messages du bar dans la devise de l'événement (mêmes fonctions qu'aujourd'hui ; seul l'appel à bar_chf change).
CREATE OR REPLACE FUNCTION public.bar_serve(e uuid, member uuid, lines jsonb, client_key text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
         else 'Servi : ' || summary || ' (' || private.bar_chf(total, e) || '). À rembourser : ' || private.bar_chf(before + total, e) || '.' end,
    'bar_served:' || serve, jsonb_build_object('serve_id', serve, 'balance', before + total));
  return jsonb_build_object('serve_id', serve, 'total', total, 'balance_before', before, 'balance', before + total, 'lines', served_lines);
end $function$;

CREATE OR REPLACE FUNCTION public.bar_correct_unit(e uuid, unit uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
    'Correction : ' || label || ' servi par erreur, ' || private.bar_chf(u.price_chf, e) || ' retirés. À rembourser : ' || private.bar_chf(private.bar_balance(e, u.user_id), e) || '.',
    'bar_correct:' || u.id);
  return public.bar_person(e, u.user_id);
end $function$;

CREATE OR REPLACE FUNCTION public.bar_declare_refund(e uuid, amount numeric)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
    raise exception 'Montant à rembourser invalide (au plus %).', private.bar_chf(greatest(owed, 0), e) using errcode = '22023';
  end if;
  insert into public.event_bar_refunds (event_id, user_id, amount_chf) values (e, me, amount) returning id into refund_id;
  perform private.bar_log(e, 'refund_declared', me, null, null, amount);
  select * into ev from public.events where id = e;
  select display_name into who from public.profiles where id = me;
  for m in select x from (select b.payee_id x union select ev.created_by union select o.user_id from public.event_organizers o where o.event_id = e) s where x is not null loop
    perform public.queue_notification(m, 'bar_refund_declared', e, ev.title,
      coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' dit avoir remboursé ' || private.bar_chf(amount, e) || ' pour le bar : à confirmer.',
      'bar_refund:' || refund_id);  -- une notification par déclaration
  end loop;
  return public.my_bar(e);
end $function$;

CREATE OR REPLACE FUNCTION public.bar_confirm_refund(e uuid, refund uuid, received boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare r public.event_bar_refunds; ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into r from public.event_bar_refunds x where x.id = refund and x.event_id = e for update;
  if r.id is null or r.status <> 'declared' then raise exception 'Remboursement introuvable ou déjà traité' using errcode = '22023'; end if;
  -- Jamais plus que ce qui reste dû : un solde ne devient pas négatif (même verrou que la déclaration).
  perform pg_advisory_xact_lock(hashtextextended('bar_refund:' || e || ':' || r.user_id, 0));
  if received and r.amount_chf > private.bar_balance(e, r.user_id) then
    raise exception 'Ce remboursement (%) dépasse ce qui reste dû (%) : refuse-le, la personne en déclarera un juste.',
      private.bar_chf(r.amount_chf, e), private.bar_chf(greatest(private.bar_balance(e, r.user_id), 0), e) using errcode = '22023';
  end if;
  update public.event_bar_refunds set status = case when received then 'confirmed' else 'rejected' end, confirmed_at = now(), confirmed_by = auth.uid()
    where id = r.id;
  perform private.bar_log(e, case when received then 'refund_confirmed' else 'refund_rejected' end, r.user_id, null, null, r.amount_chf);
  select * into ev from public.events where id = e;
  perform public.queue_notification(r.user_id, 'bar_refund_confirmed', e, ev.title,
    case when received then 'Remboursement de ' || private.bar_chf(r.amount_chf, e) || ' reçu. Reste à rembourser : ' || private.bar_chf(private.bar_balance(e, r.user_id), e) || '.'
         else 'Remboursement de ' || private.bar_chf(r.amount_chf, e) || ' pas encore reçu : vois avec l''organisateur.' end,
    'bar_refund_done:' || r.id);
  return public.bar_overview(e);
end $function$;

CREATE OR REPLACE FUNCTION public.bar_undo_serve(e uuid, serve uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
    'Service annulé par le barman : ' || private.bar_chf(s.total_chf, e) || ' retirés. À rembourser : ' || private.bar_chf(private.bar_balance(e, s.user_id), e) || '.',
    'bar_undo:' || s.id);
  return jsonb_build_object('undone', n + extra, 'balance', private.bar_balance(e, s.user_id));
end $function$;

CREATE OR REPLACE FUNCTION private.bar_check_limits(b event_bars, it event_bar_items, member uuid, adding bigint, price numeric)
 RETURNS void
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
    raise exception 'limit_chf: % au plus par personne pour la soirée (déjà %).', private.bar_chf(b.limit_chf, b.event_id), private.bar_chf(spent, b.event_id)
      using errcode = '22023';
  end if;
end $function$;

-- Carte Wallet : le solde du bar dans sa devise.
CREATE OR REPLACE FUNCTION private.wallet_payload(e uuid, member uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
      'method', private.bar_method_label(b.pay_method), 'repay_by', b.repay_by, 'currency', b.currency) end)
  from public.wallet_passes w
  join public.events ev on ev.id = w.event_id
  left join public.rsvps r on r.event_id = w.event_id and r.user_id = w.user_id
  left join public.event_tickets t on t.event_id = w.event_id and t.user_id = w.user_id
  left join public.event_bars b on b.event_id = w.event_id
  left join public.profiles p on p.id = w.user_id
  where w.event_id = e and w.user_id = member;
$function$;



-- ===== 20261116100000_bar_recap =====
-- Bar de la soirée : récapitulatif pour l'organisateur (demande de l'admin du 16.11.2026) — qui a pris quoi (articles et
-- quantités), combien, remboursé, reste dû ; totaux par article et par barman. Lu dans l'app (écran « Récapitulatif »)
-- et exporté en PDF par la page. Organisateurs, co-organisateurs et admin seulement (comme bar_overview).
-- Seuls les verres SERVIS comptent (en attente : à part ; annulés et corrigés : jamais). Purement additif et rejouable.

create or replace function public.bar_recap(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare b public.event_bars; ev public.events;
begin
  if not private.bar_can_manage(e) then raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501'; end if;
  select * into b from public.event_bars where event_id = e;
  if b.event_id is null then raise exception 'not_found: pas de bar pour cet événement' using errcode = 'P0002'; end if;
  select * into ev from public.events where id = e;
  return jsonb_build_object(
    'title', ev.title, 'starts_at', ev.starts_at, 'closed_at', b.closed_at, 'generated_at', now(),
    'currency', b.currency, 'free_bar', b.free_bar,
    'totals', jsonb_build_object(
      'served', (select count(*) from public.event_bar_units where event_id = e and status = 'served'),
      'amount', coalesce((select sum(price_chf) from public.event_bar_units where event_id = e and status = 'served'), 0),
      'pending', (select count(*) from public.event_bar_units where event_id = e and status = 'pending'),
      'refunded', coalesce((select sum(amount_chf) from public.event_bar_refunds where event_id = e and status = 'confirmed'), 0),
      'due', coalesce((select sum(greatest(private.bar_balance(e, x.user_id), 0))
                       from (select distinct user_id from public.event_bar_units where event_id = e) x), 0),
      'people', (select count(distinct user_id) from public.event_bar_units where event_id = e and status = 'served')),
    'items', coalesce((select jsonb_agg(jsonb_build_object('name', i.name, 'emoji', i.emoji, 'detail', i.detail,
                                                           'qty', s.qty, 'amount', s.amount) order by s.qty desc, i.name)
      from (select item_id, count(*) qty, sum(price_chf) amount from public.event_bar_units
            where event_id = e and status = 'served' group by item_id) s
      join public.event_bar_items i on i.id = s.item_id), '[]'::jsonb),
    'people', coalesce((select jsonb_agg(x order by x->>'name') from (
        select jsonb_build_object('id', p.id, 'name', coalesce(p.display_name, 'Sans nom'),
          'served', (select count(*) from public.event_bar_units u where u.event_id = e and u.user_id = p.id and u.status = 'served'),
          'amount', coalesce((select sum(u.price_chf) from public.event_bar_units u where u.event_id = e and u.user_id = p.id and u.status = 'served'), 0),
          'pending', (select count(*) from public.event_bar_units u where u.event_id = e and u.user_id = p.id and u.status = 'pending'),
          'refunded', coalesce((select sum(r.amount_chf) from public.event_bar_refunds r where r.event_id = e and r.user_id = p.id and r.status = 'confirmed'), 0),
          'balance', private.bar_balance(e, p.id),
          'items', coalesce((select jsonb_agg(jsonb_build_object('name', i.name, 'emoji', i.emoji, 'qty', s.qty, 'amount', s.amount)
                                              order by s.qty desc, i.name)
            from (select u.item_id, count(*) qty, sum(u.price_chf) amount from public.event_bar_units u
                  where u.event_id = e and u.user_id = p.id and u.status = 'served' group by u.item_id) s
            join public.event_bar_items i on i.id = s.item_id), '[]'::jsonb)) x
        from public.profiles p where exists (select 1 from public.event_bar_units u where u.event_id = e and u.user_id = p.id
                                              and u.status in ('served', 'pending'))
           or exists (select 1 from public.event_bar_refunds r where r.event_id = e and r.user_id = p.id)) s), '[]'::jsonb),
    'staff', coalesce((select jsonb_agg(jsonb_build_object('name', coalesce(p.display_name, 'Sans nom'), 'served', s.n) order by s.n desc)
      from (select served_by, count(*) n from public.event_bar_units where event_id = e and status = 'served' and served_by is not null
            group by served_by) s join public.profiles p on p.id = s.served_by), '[]'::jsonb));
end $$;
revoke all on function public.bar_recap(uuid) from public, anon;
grant execute on function public.bar_recap(uuid) to authenticated;


-- ===== 20261116120000_bar_notification_servi =====
-- Bar : notification « verre servi » lisible d'un coup d'œil (demande de l'admin du 16.11.2026) :
--   titre « 🍹 Barman : −2 Vodka Red Bull, −1 Coca », texte « Servi par Valentin · 11 CHF · à rembourser : 20.50 CHF · Soirée ».
-- Toujours coupable dans les réglages (« Bar : verres servis », notification_prefs.bar_served, déjà en place web et iPhone).
-- Même fonction qu'en 20261116090000 (devise), seul le texte de la notification change. Rejouable. Bar pas en prod.

CREATE OR REPLACE FUNCTION public.bar_serve(e uuid, member uuid, lines jsonb, client_key text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
  -- Notification qui se comprend sans l'ouvrir (avis du 16.11) : « 🍹 Barman : −2 Vodka Red Bull » ; dessous qui a servi,
  -- combien, le nouveau total à rembourser et la soirée. Réglage « Bar : verres servis » (notification_prefs.bar_served).
  select string_agg('−' || (x->>'qty') || ' ' || (x->>'name'), ', ') into summary from jsonb_array_elements(served_lines) x;
  perform public.queue_notification(member, 'bar_served', e, left('🍹 Barman : ' || summary, 120),
    'Servi par ' || coalesce(private.member_name(me), 'le barman')
      || case when b.free_bar then ' · bar offert'
              else ' · ' || private.bar_chf(total, e) || ' · à rembourser : ' || private.bar_chf(before + total, e) end
      || ' · ' || ev.title,
    'bar_served:' || serve, jsonb_build_object('serve_id', serve, 'balance', before + total));
  return jsonb_build_object('serve_id', serve, 'total', total, 'balance_before', before, 'balance', before + total, 'lines', served_lines);
end $function$;


insert into supabase_migrations.schema_migrations (version, name) values ('20261116090000', 'bar_devise'), ('20261116100000', 'bar_recap'), ('20261116120000', 'bar_notification_servi')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
