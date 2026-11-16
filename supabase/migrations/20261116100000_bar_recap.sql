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

notify pgrst, 'reload schema';
