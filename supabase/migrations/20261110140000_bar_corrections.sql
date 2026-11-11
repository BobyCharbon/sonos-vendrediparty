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
