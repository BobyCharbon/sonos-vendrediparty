-- PROD, event_attendance_tickets (20261103130000). À appliquer SEULEMENT après « Ok prod ». Rejouable.
-- À appliquer APRÈS 2026-11-03-pause-notifications-apply.sql (20261103120000) : reprend sa règle des notifications.
begin;
-- Événements, deux avis de l'admin (3 novembre 2026) :
-- 1. Pastille « présents » en haut à droite d'un événement : nombre de présents (accompagnants compris), de peut-être
--    et de la liste d'attente, avec les visages des premiers présents seulement si la personne a le droit de voir qui
--    vient (show_participants, organisateur, admin, droit events.see_participants). Les totaux, eux, sont anonymes
--    (déjà montrés sur la page publique d'un événement) : la pastille compte juste même quand la liste est cachée.
-- 2. Billet QR : chaque présent a un billet personnel (jeton aléatoire non devinable + code court de secours), lié à
--    l'événement et à la personne, renouvelable (l'ancien QR ne vaut plus rien). L'organisateur, les co-organisateurs
--    et les admins le scannent : arrivée notée une seule fois (« déjà scanné » ensuite), « payé » coché à la main.
-- 3. Paiement « entre amis » (réponse de l'admin) : sur un événement payant, le participant voit comment payer
--    l'organisateur (son profil de paiement du Pot commun / Tricount : Twint, Revolut, PayPal, IBAN), touche « J'ai
--    payé » (en attente de confirmation) ; l'organisateur confirme « Reçu » ou « Pas reçu ». Deux notifications, chacune
--    avec son interrupteur dans Réglages › Notifications (ticket_pay_declared, ticket_pay_confirmed), respecté par
--    tous les canaux (private.web_push_allowed, repris de 20261103120000_notification_pause avec ces deux types).
-- Table fermée : aucun accès direct, tout passe par les fonctions ci-dessous (un participant ne voit que son billet).
-- Purement additif et rejouable.

-- --------------------------------------------------------------------------------------------------------------
-- 1. Pastille des présents
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.sees_participants(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_admin() or public.is_organizer(e) or public.has_perm('events.see_participants')
      or coalesce((select show_participants from public.events where id = e), false);
$$;
revoke all on function private.sees_participants(uuid) from public, anon;
grant execute on function private.sees_participants(uuid) to authenticated;

create or replace function public.event_attendance(ids uuid[])
returns table (event_id uuid, going int, maybe int, waitlist int, faces jsonb)
language sql stable security definer set search_path = '' as $$
  select e.id,
    coalesce((select sum(1 + r.plus_ones)::int from public.rsvps r
              where r.event_id = e.id and r.status = 'yes' and not r.waitlisted), 0),
    (select count(*)::int from public.rsvps r where r.event_id = e.id and r.status = 'maybe'),
    (select count(*)::int from public.rsvps r where r.event_id = e.id and r.status = 'yes' and r.waitlisted),
    case when private.sees_participants(e.id) then coalesce((
      select jsonb_agg(jsonb_build_object('id', f.id, 'name', f.display_name, 'avatar_url', f.avatar_url) order by f.at)
      from (select p.id, p.display_name, p.avatar_url, r.updated_at as at
            from public.rsvps r join public.profiles p on p.id = r.user_id
            where r.event_id = e.id and r.status = 'yes' and not r.waitlisted and p.status = 'active'
            order by r.updated_at limit 3) f), '[]'::jsonb)
    else '[]'::jsonb end
  from public.events e
  where e.id = any(ids[1:200]) and public.can_see_event(e.id);
$$;
revoke all on function public.event_attendance(uuid[]) from public, anon;
grant execute on function public.event_attendance(uuid[]) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 2. Billets QR
-- --------------------------------------------------------------------------------------------------------------
create table if not exists public.event_tickets (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  token text not null unique check (token ~ '^[0-9a-f]{64}$'),
  code text not null check (code ~ '^[A-Z2-9]{6}$'),
  created_at timestamptz not null default now(),
  checked_in_at timestamptz,
  checked_in_by uuid references public.profiles (id) on delete set null,
  paid boolean not null default false,
  paid_at timestamptz,
  paid_by uuid references public.profiles (id) on delete set null,
  primary key (event_id, user_id),
  unique (event_id, code)
);
alter table public.event_tickets add column if not exists pay_declared_at timestamptz;  -- « J'ai payé », pas encore confirmé
alter table public.event_tickets enable row level security;
revoke all on public.event_tickets from public, anon, authenticated;

-- Jeton : 2 UUID aléatoires (244 bits) en hexadécimal. Code court (saisie à la main) : 6 signes sans 0/O/1/I/L.
create or replace function private.new_ticket_token() returns text
language sql volatile set search_path = '' as $$
  select replace(pg_catalog.gen_random_uuid()::text || pg_catalog.gen_random_uuid()::text, '-', '');
$$;

create or replace function private.new_ticket_code(e uuid) returns text
language plpgsql volatile security definer set search_path = '' as $$
declare
  alphabet constant text := 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  raw bytea;
  picked text;
begin
  loop
    raw := pg_catalog.uuid_send(pg_catalog.gen_random_uuid());
    picked := '';
    for i in 0..5 loop
      picked := picked || substr(alphabet, 1 + get_byte(raw, i) % length(alphabet), 1);
    end loop;
    exit when not exists (select 1 from public.event_tickets where event_id = e and code = picked);
  end loop;
  return picked;
end $$;

-- Billet de la personne (créé à la première demande).
create or replace function private.ensure_ticket(e uuid, member uuid) returns public.event_tickets
language plpgsql volatile security definer set search_path = '' as $$
declare t public.event_tickets;
begin
  insert into public.event_tickets (event_id, user_id, token, code)
  values (e, member, private.new_ticket_token(), private.new_ticket_code(e))
  on conflict (event_id, user_id) do nothing;
  select * into t from public.event_tickets where event_id = e and user_id = member;
  return t;
end $$;

create or replace function private.can_scan(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_admin() or public.is_organizer(e);
$$;

create or replace function private.require_scanner(e uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.can_scan(e) then
    raise exception 'Seuls les organisateurs de l''événement valident les billets.' using errcode = '42501';
  end if;
end $$;

-- Ce que l'organisateur voit d'un billet (jamais le jeton).
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

-- Fonctions internes : appelées seulement par les fonctions publiques ci-dessous (security definer).
revoke all on function private.new_ticket_token(), private.new_ticket_code(uuid), private.ensure_ticket(uuid, uuid),
  private.can_scan(uuid), private.require_scanner(uuid), private.ticket_view(uuid, uuid) from public, anon, authenticated;

-- Mon billet : seulement si je suis noté Présent (hors liste d'attente) à un événement publié que je vois.
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

-- Nouveau QR (l'ancien ne vaut plus rien) : pour soi, ou pour quelqu'un par l'organisateur (billet perdu, partagé…).
create or replace function public.renew_event_ticket(e uuid, member uuid default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare who uuid := coalesce(member, auth.uid());
begin
  if auth.uid() is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if who <> auth.uid() then perform private.require_scanner(e); end if;
  update public.event_tickets set token = private.new_ticket_token(), code = private.new_ticket_code(e)
    where event_id = e and user_id = who;
  if who = auth.uid() then return public.my_event_ticket(e); end if;
  return private.ticket_view(e, who);
end $$;

-- Scan (QR ou code court) : enregistre l'arrivée une seule fois. Le résultat dit quoi montrer à l'organisateur.
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

-- Arrivée notée (ou retirée) à la main, sans scan : téléphone à plat, erreur de scan…
create or replace function public.set_ticket_arrival(e uuid, member uuid, arrived boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.require_scanner(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  if arrived and not exists (select 1 from public.rsvps where event_id = e and user_id = member and status = 'yes' and not waitlisted) then
    raise exception 'Cette personne n''est pas notée présente.' using errcode = '22023';
  end if;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set checked_in_at = case when arrived then coalesce(checked_in_at, now()) end,
        checked_in_by = case when arrived then coalesce(checked_in_by, auth.uid()) end
    where event_id = e and user_id = member;
  return private.ticket_view(e, member);
end $$;

-- « Payé » coché à la main par l'organisateur (paiement en espèces, TWINT…).
create or replace function public.set_ticket_paid(e uuid, member uuid, is_paid boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.require_scanner(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set paid = is_paid, paid_at = case when is_paid then now() end, paid_by = case when is_paid then auth.uid() end,
        pay_declared_at = case when is_paid then pay_declared_at end
    where event_id = e and user_id = member;
  return private.ticket_view(e, member);
end $$;

-- Liste de l'entrée : tous les présents (et la liste d'attente), arrivés ou attendus, avec « payé ».
create or replace function public.event_checkins(e uuid) returns setof jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.require_scanner(e);
  return query
    select private.ticket_view(e, r.user_id)
    from public.rsvps r
    join public.profiles p on p.id = r.user_id
    left join public.event_tickets t on t.event_id = e and t.user_id = r.user_id
    where r.event_id = e and r.status = 'yes'
    order by r.waitlisted, t.checked_in_at desc nulls last, lower(p.display_name);
end $$;

revoke all on function public.my_event_ticket(uuid), public.renew_event_ticket(uuid, uuid), public.check_in_ticket(uuid, text),
  public.set_ticket_arrival(uuid, uuid, boolean), public.set_ticket_paid(uuid, uuid, boolean), public.event_checkins(uuid)
  from public, anon;
grant execute on function public.my_event_ticket(uuid), public.renew_event_ticket(uuid, uuid), public.check_in_ticket(uuid, text),
  public.set_ticket_arrival(uuid, uuid, boolean), public.set_ticket_paid(uuid, uuid, boolean), public.event_checkins(uuid)
  to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 3. Paiement entre amis : « J'ai payé » par le participant, « Reçu » / « Pas reçu » par l'organisateur
-- --------------------------------------------------------------------------------------------------------------
-- Interrupteurs des deux nouvelles notifications (activées par défaut).
alter table public.notification_prefs add column if not exists ticket_pay_declared boolean not null default true;   -- organisateur
alter table public.notification_prefs add column if not exists ticket_pay_confirmed boolean not null default true;  -- participant

-- Comment payer l'organisateur : son profil de paiement (Pot commun / Tricount), seulement à ses présents et organisateurs,
-- et seulement pour un événement payant.
create or replace function public.event_pay_info(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  ev public.events;
  pay public.tc_payment;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'Événement introuvable' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  if coalesce(ev.price_chf, 0) <= 0 then return null; end if;
  if not (private.can_scan(e) or exists (select 1 from public.rsvps where event_id = e and user_id = auth.uid() and status = 'yes')) then
    return null;
  end if;
  select * into pay from public.tc_payment where user_id = ev.created_by;
  return jsonb_build_object(
    'organizer_id', ev.created_by,
    'organizer_name', (select display_name from public.profiles where id = ev.created_by),
    'amount', ev.price_chf, 'payment_info', ev.payment_info,
    'iban', pay.iban, 'holder', pay.holder, 'links', coalesce(pay.links, '{}'::jsonb), 'note', pay.note,
    'reference', left('Party · ' || ev.title, 140));
end $$;

-- Organisateurs à prévenir : le créateur et les co-organisateurs.
create or replace function private.event_managers(e uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select created_by from public.events where id = e
  union select user_id from public.event_organizers where event_id = e;
$$;
revoke all on function private.event_managers(uuid) from public, anon, authenticated;

-- « J'ai payé » (declared = true) ou « Je n'ai pas encore payé » (false) : seulement un présent, sur un événement payant.
create or replace function public.declare_ticket_payment(e uuid, declared boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  ev public.events;
  t public.event_tickets;
  who text;
  manager uuid;
begin
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if not exists (select 1 from public.rsvps where event_id = e and user_id = me and status = 'yes' and not waitlisted) then
    raise exception 'Seuls les présents paient leur place.' using errcode = '22023';
  end if;
  select * into ev from public.events where id = e;
  if coalesce(ev.price_chf, 0) <= 0 then raise exception 'Cet événement est gratuit.' using errcode = '22023'; end if;
  t := private.ensure_ticket(e, me);
  if t.paid then return public.my_event_ticket(e); end if;
  update public.event_tickets set pay_declared_at = case when declared then coalesce(pay_declared_at, now()) end
    where event_id = e and user_id = me;
  if declared and t.pay_declared_at is null then
    who := coalesce(private.member_name(me), 'Quelqu''un');
    for manager in select private.event_managers(e) loop
      perform public.queue_notification(manager, 'ticket_pay_declared', e, ev.title,
        who || ' dit avoir payé sa place (' || trim_scale(ev.price_chf)::text || ' CHF) : confirme quand tu l''as reçu.',
        null, jsonb_build_object('member', me));
    end loop;
  end if;
  return public.my_event_ticket(e);
end $$;

-- L'organisateur confirme : « Reçu » (payé ✓) ou « Pas reçu » (retour à payer). Le participant est prévenu.
create or replace function public.confirm_ticket_payment(e uuid, member uuid, received boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  ev public.events;
  who text;
begin
  perform private.require_scanner(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  select * into ev from public.events where id = e;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set paid = received, paid_at = case when received then now() end, paid_by = case when received then auth.uid() end,
        pay_declared_at = case when received then pay_declared_at end
    where event_id = e and user_id = member;
  who := coalesce(private.member_name(auth.uid()), 'L''organisateur');
  perform public.queue_notification(member, 'ticket_pay_confirmed', e, ev.title,
    case when received then who || ' a bien reçu ton paiement : ta place est payée ✓'
         else who || ' n''a pas reçu ton paiement : vérifie-le, puis touche à nouveau « J''ai payé ».' end,
    null, jsonb_build_object('received', received));
  return private.ticket_view(e, member);
end $$;

revoke all on function public.event_pay_info(uuid), public.declare_ticket_payment(uuid, boolean),
  public.confirm_ticket_payment(uuid, uuid, boolean) from public, anon;
grant execute on function public.event_pay_info(uuid), public.declare_ticket_payment(uuid, boolean),
  public.confirm_ticket_payment(uuid, uuid, boolean) to authenticated;

-- Chaque notification a son interrupteur, pour tous les canaux (iPhone, Expo, Web Push) : même fonction que
-- 20261103120000_notification_pause, plus les deux types des billets (ticket_pay_declared, ticket_pay_confirmed).
CREATE OR REPLACE FUNCTION private.web_push_allowed(notification notifications)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare prefs public.notification_prefs; ev public.events;
begin
  if not exists(select 1 from public.profiles where id=notification.user_id and private.may_receive_push(id, notification.kind)) then return false; end if;
  if notification.kind in ('web_push_test', 'push_test') then return true; end if;
  select * into prefs from public.notification_prefs where user_id=notification.user_id;
  if notification.kind='admin_announcement' then
    return exists(select 1 from public.admin_announcements where id::text=notification.data->>'announcement_id')
      and coalesce(prefs.announcements, true);
  end if;
  if prefs.user_id is null or not prefs.push_enabled then return false; end if;
  if notification.event_id is not null then
    select * into ev from public.events where id=notification.event_id;
    if ev.id is null or exists(select 1 from public.event_mutes where event_id=ev.id and user_id=notification.user_id) then return false; end if;
    if not (exists(select 1 from public.profiles where id=notification.user_id and private.user_has(id, 'events.manage_all'))
      or ev.created_by=notification.user_id
      or exists(select 1 from public.event_organizers where event_id=ev.id and user_id=notification.user_id)
      or (ev.status in ('published','cancelled') and (ev.visibility='all'
        or exists(select 1 from public.event_invites where event_id=ev.id and user_id=notification.user_id)))) then return false; end if;
  end if;
  return case notification.kind
    when 'new_event' then prefs.new_event='all' or (prefs.new_event='subscribed' and (
      exists(select 1 from public.category_subscriptions where user_id=notification.user_id and category_id=ev.category_id)
      or exists(select 1 from public.tag_subscriptions t join public.event_tags e on e.tag_id=t.tag_id where e.event_id=ev.id and t.user_id=notification.user_id)))
    when 'event_changed' then prefs.event_changed
    when 'poll_new' then prefs.poll_new
    when 'date_fixed' then prefs.date_fixed
    when 'poll_nudge' then prefs.poll_nudge
    when 'waitlist' then prefs.waitlist
    when 'proposal' then prefs.proposals
    when 'rsvp' then prefs.rsvp_mine
    when 'message' then prefs.chat='all' or (prefs.chat='mentions' and coalesce((notification.data->>'mentioned')::boolean,false))
    when 'reminder' then split_part(notification.dedupe_key,':',3)=any(prefs.reminders)
    when 'rsvp_set' then prefs.rsvp_set
    when 'private_invite' then prefs.invites
    when 'approved' then prefs.proposal_result
    when 'rejected' then prefs.proposal_result
    when 'link_join' then prefs.link_join
    when 'group_message' then prefs.group_messages
    when 'group_invite' then prefs.group_invites
    when 'group_join' then prefs.group_joins
    when 'ticket_pay_declared' then coalesce(prefs.ticket_pay_declared, true)
    when 'ticket_pay_confirmed' then coalesce(prefs.ticket_pay_confirmed, true)
    else true end;
end $function$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103130000', 'event_attendance_tickets')
  on conflict (version) do nothing;
commit;
