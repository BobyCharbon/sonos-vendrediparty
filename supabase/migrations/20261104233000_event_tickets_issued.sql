-- Billets QR remis par l'organisateur (demande de l'admin, 4 novembre 2026). Jusqu'ici, tout présent d'un événement
-- publié recevait automatiquement son billet QR. Désormais :
-- 1. Option par événement « Billets QR » : events.tickets_enabled, NON par défaut (y compris pour les événements
--    existants). L'organisateur, les co-organisateurs, les admins (et le droit events.manage_all) l'activent ou la
--    désactivent à tout moment, même après publication : formulaire de l'événement, ou public.set_event_tickets
--    (écran des présents). L'IA de création ne la touche jamais (la colonne n'est pas dans ce qu'elle écrit).
-- 2. Billet REMIS : event_tickets.issued_at / issued_by. Seuls les gestionnaires de l'entrée (organisateurs, admins,
--    droits « Scanner les billets » / « Confirmer les paiements » : private.require_entry_staff) remettent ou
--    retirent un billet (public.issue_event_ticket), ou le remettent à tous les présents (issue_all_event_tickets).
--    Sur un événement payant, la place payée (« Reçu » ou « payé » coché) remet aussi le billet (garde
--    private.ticket_paid_issues, quel que soit le chemin).
-- 3. Le participant ne reçoit son QR (my_event_ticket) que si l'option est active ET son billet remis ; sinon
--    state 'off' (option éteinte) ou 'pending' (en attente de l'organisateur), avec ce qu'il faut pour payer, mais
--    jamais le jeton. Le pass Wallet est refusé (wallet_pass_issue) et un pass déjà ajouté devient « annulé »
--    (wallet_payload.valid) quand l'option s'éteint ou que le billet est retiré.
-- 4. Notification « Ton billet est prêt » (kind ticket_issued) à la remise (ou à l'activation de l'option pour un
--    billet déjà remis), avec son propre interrupteur notification_prefs.ticket_issued, respecté par tous les canaux
--    (private.web_push_allowed, complétée en place une seule fois).
-- 5. Le scanner refuse un billet non remis (« not_issued ») et tout billet quand l'option est éteinte (« tickets_off »).
-- Purement additif et rejouable. Les fonctions reprises de 20261103130000 / 20261103140000 / 20261103160000 gardent
-- leur comportement, seules la remise et l'option s'ajoutent.

-- --------------------------------------------------------------------------------------------------------------
-- 1. Colonnes
-- --------------------------------------------------------------------------------------------------------------
alter table public.events add column if not exists tickets_enabled boolean not null default false;
alter table public.event_tickets add column if not exists issued_at timestamptz;
alter table public.event_tickets add column if not exists issued_by uuid references public.profiles (id) on delete set null;
alter table public.notification_prefs add column if not exists ticket_issued boolean not null default true;

-- --------------------------------------------------------------------------------------------------------------
-- 2. Option de l'événement
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.can_manage_tickets_option(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_admin() or public.is_organizer(e) or public.has_perm('events.manage_all');
$$;
revoke all on function private.can_manage_tickets_option(uuid) from public, anon, authenticated;

create or replace function public.set_event_tickets(e uuid, enabled boolean) returns boolean
language plpgsql volatile security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.can_manage_tickets_option(e) then
    raise exception 'Seuls les organisateurs de l''événement activent les billets QR.' using errcode = '42501';
  end if;
  update public.events set tickets_enabled = coalesce(enabled, false) where id = e;
  if not found then raise exception 'Événement introuvable' using errcode = '42501'; end if;
  return coalesce(enabled, false);
end $$;
revoke all on function public.set_event_tickets(uuid, boolean) from public, anon;
grant execute on function public.set_event_tickets(uuid, boolean) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 3. Ce que voit l'organisateur (repris de 20261103130000, plus la remise et l'option)
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.ticket_view(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'user_id', p.id, 'display_name', p.display_name, 'avatar_url', p.avatar_url,
    'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
    'checked_in_at', t.checked_in_at, 'paid', coalesce(t.paid, false),
    'pay_pending', coalesce(not t.paid and t.pay_declared_at is not null, false), 'pay_declared_at', t.pay_declared_at,
    'price_chf', (select price_chf from public.events where id = e),
    'issued', t.issued_at is not null, 'issued_at', t.issued_at,
    'tickets_enabled', coalesce((select tickets_enabled from public.events where id = e), false))
  from public.profiles p
  left join public.rsvps r on r.event_id = e and r.user_id = p.id
  left join public.event_tickets t on t.event_id = e and t.user_id = p.id
  where p.id = member;
$$;
revoke all on function private.ticket_view(uuid, uuid) from public, anon, authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 4. Mon billet : le QR seulement si l'option est active et le billet remis
-- --------------------------------------------------------------------------------------------------------------
create or replace function public.my_event_ticket(e uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  r public.rsvps;
  t public.event_tickets;
  ev public.events;
  pay jsonb;
begin
  if me is null or not public.can_see_event(e) then
    raise exception 'Événement introuvable' using errcode = '42501';
  end if;
  select * into r from public.rsvps where event_id = e and user_id = me;
  if r.user_id is null or r.status <> 'yes' then return jsonb_build_object('state', 'none'); end if;
  if r.waitlisted then return jsonb_build_object('state', 'waitlist'); end if;
  select * into ev from public.events where id = e;
  if ev.status is distinct from 'published' then return jsonb_build_object('state', 'none'); end if;
  select * into t from public.event_tickets where event_id = e and user_id = me;
  -- Paiement (sans jeton) : utile même sans QR, pour payer l'organisateur.
  pay := jsonb_build_object('plus_ones', r.plus_ones, 'paid', coalesce(t.paid, false),
    'pay_pending', coalesce(not t.paid and t.pay_declared_at is not null, false), 'price_chf', ev.price_chf);
  if not ev.tickets_enabled then return pay || jsonb_build_object('state', 'off'); end if;
  if t.issued_at is null then return pay || jsonb_build_object('state', 'pending'); end if;
  return pay || jsonb_build_object('state', 'ok', 'token', t.token, 'code', t.code,
    'checked_in_at', t.checked_in_at, 'issued_at', t.issued_at);
end $$;
revoke all on function public.my_event_ticket(uuid) from public, anon;
grant execute on function public.my_event_ticket(uuid) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 5. Remettre / retirer un billet (gestionnaires de l'entrée seulement)
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.require_tickets_enabled(e uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if not coalesce((select tickets_enabled from public.events where id = e), false) then
    raise exception 'Active d''abord les billets QR de l''événement.' using errcode = '22023';
  end if;
end $$;
revoke all on function private.require_tickets_enabled(uuid) from public, anon, authenticated;

create or replace function public.issue_event_ticket(e uuid, member uuid, issued boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.require_entry_staff(e);
  perform private.require_tickets_enabled(e);
  if issued and not exists (select 1 from public.rsvps where event_id = e and user_id = member and status = 'yes' and not waitlisted) then
    raise exception 'Cette personne n''est pas notée présente.' using errcode = '22023';
  end if;
  if not issued and not exists (select 1 from public.event_tickets where event_id = e and user_id = member) then
    return private.ticket_view(e, member);
  end if;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set issued_at = case when issued then coalesce(issued_at, now()) end,
        issued_by = case when issued then coalesce(issued_by, auth.uid()) end
    where event_id = e and user_id = member;
  return private.ticket_view(e, member);
end $$;

-- « Remettre à tous les présents » : rend le nombre de billets remis par cet appel.
create or replace function public.issue_all_event_tickets(e uuid) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare
  member uuid;
  n integer := 0;
begin
  perform private.require_entry_staff(e);
  perform private.require_tickets_enabled(e);
  for member in
    select r.user_id from public.rsvps r
    left join public.event_tickets t on t.event_id = e and t.user_id = r.user_id
    where r.event_id = e and r.status = 'yes' and not r.waitlisted and t.issued_at is null
  loop
    perform private.ensure_ticket(e, member);
    update public.event_tickets set issued_at = now(), issued_by = auth.uid()
      where event_id = e and user_id = member and issued_at is null;
    n := n + 1;
  end loop;
  return n;
end $$;

revoke all on function public.issue_event_ticket(uuid, uuid, boolean), public.issue_all_event_tickets(uuid) from public, anon;
grant execute on function public.issue_event_ticket(uuid, uuid, boolean), public.issue_all_event_tickets(uuid) to authenticated;

-- Place payée (« Reçu », « payé » coché, quel que soit le chemin) : le billet est remis aussi.
create or replace function private.ticket_paid_issues() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.paid and not coalesce(old.paid, false) and new.issued_at is null then
    new.issued_at := now();
    new.issued_by := coalesce(new.paid_by, auth.uid());
  end if;
  return new;
end $$;
revoke all on function private.ticket_paid_issues() from public, anon, authenticated;
drop trigger if exists ticket_paid_issues on public.event_tickets;
create trigger ticket_paid_issues before update on public.event_tickets for each row
  when (new.paid and not old.paid) execute function private.ticket_paid_issues();

-- --------------------------------------------------------------------------------------------------------------
-- 6. « Ton billet est prêt »
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.notify_ticket_ready(e uuid, member uuid, issued timestamptz) returns void
language plpgsql volatile security definer set search_path = '' as $$
declare ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not ev.tickets_enabled or ev.status <> 'published' then return; end if;
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member and status = 'yes' and not waitlisted) then
    return;
  end if;
  perform public.queue_notification(member, 'ticket_issued', e, ev.title,
    '🎟️ Ton billet est prêt : ouvre l''événement pour afficher ton QR à l''entrée.',
    'ticket_issued:' || e::text || ':' || floor(extract(epoch from issued))::bigint::text, '{}'::jsonb);
end $$;

create or replace function private.ticket_issued_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.issued_at is not null and (tg_op = 'INSERT' or old.issued_at is null) then
    perform private.notify_ticket_ready(new.event_id, new.user_id, new.issued_at);
  end if;
  return null;
end $$;

-- Option activée : les billets déjà remis (places payées avant l'activation, par exemple) sont annoncés.
create or replace function private.tickets_option_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
declare t public.event_tickets;
begin
  for t in select * from public.event_tickets where event_id = new.id and issued_at is not null loop
    perform private.notify_ticket_ready(t.event_id, t.user_id, t.issued_at);
  end loop;
  return null;
end $$;

revoke all on function private.notify_ticket_ready(uuid, uuid, timestamptz), private.ticket_issued_changed(),
  private.tickets_option_changed() from public, anon, authenticated;

drop trigger if exists ticket_issued on public.event_tickets;
-- Sans liste de colonnes : la remise par la place payée vient de la garde BEFORE (issued_at absent du SET).
create trigger ticket_issued after insert or update on public.event_tickets for each row
  execute function private.ticket_issued_changed();

drop trigger if exists tickets_option on public.events;
create trigger tickets_option after update of tickets_enabled on public.events for each row
  when (new.tickets_enabled and not old.tickets_enabled) execute function private.tickets_option_changed();

-- Interrupteur pour tous les canaux : private.web_push_allowed complétée en place, une seule fois.
do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''ticket_pay_confirmed'' then coalesce(prefs.ticket_pay_confirmed, true)';
begin
  if position('''ticket_issued''' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then
    raise exception 'web_push_allowed : branche ticket_pay_confirmed introuvable, ticket_issued non ajouté';
  end if;
  execute replace(def, anchor, anchor || E'\n    when ''ticket_issued'' then coalesce(prefs.ticket_issued, true)');
end $$;

-- --------------------------------------------------------------------------------------------------------------
-- 7. Scanner : refuse un billet non remis, ou tout billet quand l'option est éteinte
-- --------------------------------------------------------------------------------------------------------------
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
  if not coalesce((select tickets_enabled from public.events where id = e), false) then
    return jsonb_build_object('result', 'tickets_off', 'person', private.ticket_view(e, t.user_id));
  end if;

  select * into r from public.rsvps where event_id = e and user_id = t.user_id;
  if r.user_id is null or r.status <> 'yes' then
    return jsonb_build_object('result', 'not_registered', 'person', private.ticket_view(e, t.user_id));
  end if;
  if r.waitlisted then
    return jsonb_build_object('result', 'waitlist', 'person', private.ticket_view(e, t.user_id));
  end if;
  if t.issued_at is null then
    return jsonb_build_object('result', 'not_issued', 'person', private.ticket_view(e, t.user_id));
  end if;
  if t.checked_in_at is not null then
    return jsonb_build_object('result', 'already', 'person', private.ticket_view(e, t.user_id));
  end if;
  update public.event_tickets set checked_in_at = now(), checked_in_by = auth.uid()
    where event_id = e and user_id = t.user_id;
  return jsonb_build_object('result', 'ok', 'person', private.ticket_view(e, t.user_id));
end $$;
revoke all on function public.check_in_ticket(uuid, text) from public, anon;
grant execute on function public.check_in_ticket(uuid, text) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 8. Apple Wallet : pas de pass sans billet remis ; un pass déjà ajouté devient « annulé »
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.wallet_payload(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'serial', w.event_id::text || '.' || w.user_id::text,
    'user_id', w.user_id,
    'auth_token', w.auth_token,
    'updated_at', w.updated_at,
    -- Pass valable : noté Présent (hors liste d'attente) à un événement publié, billets QR actifs, billet remis.
    'valid', coalesce(r.status = 'yes' and not coalesce(r.waitlisted, false) and ev.status = 'published'
                      and ev.tickets_enabled and t.token is not null and t.issued_at is not null, false),
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
revoke all on function private.wallet_payload(uuid, uuid) from public, anon, authenticated;

create or replace function public.wallet_pass_issue(e uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if public.my_event_ticket(e) ->> 'state' is distinct from 'ok' then  -- même règle que pour afficher son QR
    raise exception 'Pas encore de billet pour cet événement : l''organisateur doit te le remettre.' using errcode = '22023';
  end if;
  insert into public.wallet_passes (event_id, user_id, auth_token) values (e, me, private.new_ticket_token())
    on conflict (event_id, user_id) do nothing;
  return private.wallet_payload(e, me);
end $$;
revoke all on function public.wallet_pass_issue(uuid) from public, anon, authenticated;
grant execute on function public.wallet_pass_issue(uuid) to authenticated;

-- Les pass se redatent aussi quand le billet est remis / retiré et quand l'option change.
drop trigger if exists wallet_touch on public.event_tickets;
create trigger wallet_touch after update on public.event_tickets for each row
  when (old.token is distinct from new.token or old.code is distinct from new.code
     or old.checked_in_at is distinct from new.checked_in_at or old.paid is distinct from new.paid
     or old.issued_at is distinct from new.issued_at)
  execute function private.wallet_touch_member();

drop trigger if exists wallet_touch on public.events;
create trigger wallet_touch after update on public.events for each row
  when (old.title is distinct from new.title or old.starts_at is distinct from new.starts_at
     or old.ends_at is distinct from new.ends_at or old.all_day is distinct from new.all_day
     or old.location_name is distinct from new.location_name or old.location_address is distinct from new.location_address
     or old.location_url is distinct from new.location_url or old.status is distinct from new.status
     or old.price_chf is distinct from new.price_chf or old.tickets_enabled is distinct from new.tickets_enabled)
  execute function private.wallet_touch_event();

notify pgrst, 'reload schema';
