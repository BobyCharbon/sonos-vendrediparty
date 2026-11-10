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
