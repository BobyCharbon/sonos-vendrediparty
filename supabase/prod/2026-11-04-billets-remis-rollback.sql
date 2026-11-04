-- PROD, retour arrière de event_tickets_issued (20261104233000) : retour au billet automatique de tout présent
-- (20261103130000) et au pass Wallet d'avant. L'option « Billets QR » (events.tickets_enabled), la remise des billets
-- (event_tickets.issued_at / issued_by) et l'interrupteur « Billet prêt » (notification_prefs.ticket_issued) sont
-- supprimés ; les notifications « ticket_issued » déjà envoyées restent dans l'historique. Tout ou rien.
begin;

drop trigger if exists ticket_paid_issues on public.event_tickets;
drop trigger if exists ticket_issued on public.event_tickets;
drop trigger if exists tickets_option on public.events;
drop function if exists public.set_event_tickets(uuid, boolean);
drop function if exists public.issue_event_ticket(uuid, uuid, boolean);
drop function if exists public.issue_all_event_tickets(uuid);
drop function if exists private.can_manage_tickets_option(uuid);
drop function if exists private.require_tickets_enabled(uuid);
drop function if exists private.ticket_paid_issues();
drop function if exists private.ticket_issued_changed();
drop function if exists private.tickets_option_changed();
drop function if exists private.notify_ticket_ready(uuid, uuid, timestamptz);

-- Fonctions reprises telles qu'avant (20261103130000, 20261103160000).
create or replace function private.ticket_view(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'user_id', p.id, 'display_name', p.display_name, 'avatar_url', p.avatar_url,
    'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
    'checked_in_at', t.checked_in_at, 'paid', coalesce(t.paid, false),
    'pay_pending', coalesce(not t.paid and t.pay_declared_at is not null, false), 'pay_declared_at', t.pay_declared_at,
    'price_chf', (select price_chf from public.events where id = e))
  from public.profiles p
  left join public.rsvps r on r.event_id = e and r.user_id = p.id
  left join public.event_tickets t on t.event_id = e and t.user_id = p.id
  where p.id = member;
$$;

create or replace function public.my_event_ticket(e uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  r public.rsvps;
  t public.event_tickets;
begin
  if me is null or not public.can_see_event(e) then
    raise exception 'Événement introuvable' using errcode = '42501';
  end if;
  select * into r from public.rsvps where event_id = e and user_id = me;
  if r.user_id is null or r.status <> 'yes' then return jsonb_build_object('state', 'none'); end if;
  if r.waitlisted then return jsonb_build_object('state', 'waitlist'); end if;
  if not exists (select 1 from public.events where id = e and status = 'published') then
    return jsonb_build_object('state', 'none');
  end if;
  t := private.ensure_ticket(e, me);
  return jsonb_build_object('state', 'ok', 'token', t.token, 'code', t.code, 'plus_ones', r.plus_ones,
    'checked_in_at', t.checked_in_at, 'paid', t.paid, 'pay_pending', not t.paid and t.pay_declared_at is not null,
    'price_chf', (select price_chf from public.events where id = e));
end $$;

create or replace function public.check_in_ticket(e uuid, scanned text) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  s text := btrim(coalesce(scanned, ''));
  t public.event_tickets;
  r public.rsvps;
  other text;
begin
  perform private.require_scanner(e);
  if s ~* '^[0-9a-f]{64}$' then
    select * into t from public.event_tickets where token = lower(s) for update;
    if t.event_id is not null and t.event_id <> e then
      select title into other from public.events where id = t.event_id;
      return jsonb_build_object('result', 'other_event', 'event_title', other);
    end if;
  elsif upper(s) ~ '^[A-Z2-9]{6}$' then
    select * into t from public.event_tickets where event_id = e and code = upper(s) for update;
  end if;
  if t.user_id is null then return jsonb_build_object('result', 'unknown'); end if;

  select * into r from public.rsvps where event_id = e and user_id = t.user_id;
  if r.user_id is null or r.status <> 'yes' then
    return jsonb_build_object('result', 'not_registered', 'person', private.ticket_view(e, t.user_id));
  end if;
  if r.waitlisted then
    return jsonb_build_object('result', 'waitlist', 'person', private.ticket_view(e, t.user_id));
  end if;
  if t.checked_in_at is not null then
    return jsonb_build_object('result', 'already', 'person', private.ticket_view(e, t.user_id));
  end if;
  update public.event_tickets set checked_in_at = now(), checked_in_by = auth.uid()
    where event_id = e and user_id = t.user_id;
  return jsonb_build_object('result', 'ok', 'person', private.ticket_view(e, t.user_id));
end $$;

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

revoke all on function private.ticket_view(uuid, uuid) from public, anon, authenticated;
revoke all on function public.my_event_ticket(uuid), public.check_in_ticket(uuid, text) from public, anon;
grant execute on function public.my_event_ticket(uuid), public.check_in_ticket(uuid, text) to authenticated;
revoke all on function private.wallet_payload(uuid, uuid) from public, anon, authenticated;
revoke all on function public.wallet_pass_issue(uuid) from public, anon, authenticated;
grant execute on function public.wallet_pass_issue(uuid) to authenticated;

-- Déclencheurs Wallet d'avant (sans issued_at ni tickets_enabled).
drop trigger if exists wallet_touch on public.event_tickets;
create trigger wallet_touch after update on public.event_tickets for each row
  when (old.token is distinct from new.token or old.code is distinct from new.code
     or old.checked_in_at is distinct from new.checked_in_at or old.paid is distinct from new.paid)
  execute function private.wallet_touch_member();

drop trigger if exists wallet_touch on public.events;
create trigger wallet_touch after update on public.events for each row
  when (old.title is distinct from new.title or old.starts_at is distinct from new.starts_at
     or old.ends_at is distinct from new.ends_at or old.all_day is distinct from new.all_day
     or old.location_name is distinct from new.location_name or old.location_address is distinct from new.location_address
     or old.location_url is distinct from new.location_url or old.status is distinct from new.status
     or old.price_chf is distinct from new.price_chf)
  execute function private.wallet_touch_event();


-- web_push_allowed : la branche ticket_issued retirée en place (le reste, complété par d'autres migrations, gardé).
do $$
declare def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
begin
  if position('''ticket_issued''' in def) = 0 then return; end if;
  execute replace(def, E'\n    when ''ticket_issued'' then coalesce(prefs.ticket_issued, true)', '');
end $$;

alter table public.notification_prefs drop column if exists ticket_issued;
alter table public.event_tickets drop column if exists issued_by;
alter table public.event_tickets drop column if exists issued_at;
alter table public.events drop column if exists tickets_enabled;

delete from supabase_migrations.schema_migrations where version = '20261104233000';
commit;

notify pgrst, 'reload schema';
