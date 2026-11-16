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

notify pgrst, 'reload schema';
