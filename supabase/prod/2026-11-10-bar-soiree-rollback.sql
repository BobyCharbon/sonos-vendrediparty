-- PROD, retour arrière du bar de la soirée (20261110120000 à 20261110160000) : fonctions de notification et de Wallet
-- d'avant, puis suppression du bar (tables, fonctions, tâches planifiées, interrupteurs). EFFACE les données du bar.
-- Tout ou rien.
begin;
-- 20261110160000 bar_options : fonctions ajoutées (les colonnes partent avec les tables plus bas).
drop function if exists public.bar_item_action(uuid, uuid, text, numeric), public.bar_staff_items(uuid), public.bar_pledge(uuid, text, int),
  private.bar_options(public.event_bars), private.bar_counter_on(public.event_bars), private.bar_may(uuid, text), private.bar_rights(uuid),
  private.bar_item_json(public.event_bar_items), private.bar_pledged(public.event_bars, uuid),
  private.bar_check_limits(public.event_bars, public.event_bar_items, uuid, bigint, numeric), private.bar_lock_person(uuid, uuid);
-- 20261110140000 bar_corrections : déclencheur des réponses « Absent » (sur rsvps, table qui reste).
drop trigger if exists bar_cancel_absent on public.rsvps;
drop function if exists private.bar_cancel_absent();
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('pet_daily', 'pet_alert', 'pet_gift', 'pet_streak', 'pet_bar') and private.is_account_active(uid))
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message', 'moderation_notice', 'report_new',
                 'private_invite', 'announce_request', 'announce_accepted', 'announce_refused', 'group_event_request', 'group_event_accepted', 'group_event_refused', 'event_changed', 'date_fixed', 'reminder', 'waitlist',
                 'coorganizer_added')
        and private.is_account_active(uid));
$$;

create or replace function private.web_push_allowed(notification public.notifications) returns boolean
language plpgsql stable security definer set search_path = '' as $$
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
    when 'coorganizer_added' then coalesce(prefs.invites, true)
    when 'approved' then prefs.proposal_result
    when 'rejected' then prefs.proposal_result
    when 'link_join' then prefs.link_join
    when 'group_message' then prefs.group_messages
    when 'group_invite' then prefs.group_invites
    when 'group_join' then prefs.group_joins
    when 'report_new' then coalesce(prefs.moderation_reports, true)
    when 'moderation_notice' then coalesce(prefs.moderation_notices, true)
    when 'pet_daily' then coalesce(prefs.pet_daily, true)
    when 'pet_alert' then coalesce(prefs.pet_alerts, true)
    when 'pet_gift' then coalesce(prefs.pet_gifts, true)
    when 'pet_streak' then coalesce(prefs.pet_streaks, true)
    when 'pet_bar' then coalesce(prefs.pet_bar, true)
    when 'referral_join' then coalesce(prefs.referral_joins, true)
    when 'ticket_pay_declared' then coalesce(prefs.ticket_pay_declared, true)
    when 'ticket_pay_confirmed' then coalesce(prefs.ticket_pay_confirmed, true)
    when 'ticket_issued' then coalesce(prefs.ticket_issued, true)
    when 'direct_message' then coalesce(prefs.direct_messages, true)
    when 'announce_request' then coalesce(prefs.announce_requests, true)
    when 'announce_accepted' then coalesce(prefs.announce_results, true)
    when 'announce_refused' then coalesce(prefs.announce_results, true)
    when 'group_event_request' then coalesce(prefs.group_event_requests, true)
    when 'group_event_accepted' then coalesce(prefs.announce_results, true)
    when 'group_event_refused' then coalesce(prefs.announce_results, true)
    else true end;
end $$;

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

create or replace function public.wallet_push_targets(e uuid, member uuid default null) returns setof text
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if member is distinct from auth.uid() and not private.can_scan(e) then
    raise exception 'Seuls les organisateurs de l''événement préviennent les billets.' using errcode = '42501';
  end if;
  return query select distinct d.push_token from public.wallet_devices d
    where d.event_id = e and (member is null or d.user_id = member);
end $$;

drop trigger if exists wallet_touch on public.event_bar_units;
drop trigger if exists wallet_touch on public.event_bar_refunds;
drop trigger if exists wallet_touch on public.event_bars;
drop function if exists private.wallet_touch_bar();
do $$ begin
  perform cron.unschedule('bar-close-due') where exists (select 1 from cron.job where jobname = 'bar-close-due');
  perform cron.unschedule('bar-purge') where exists (select 1 from cron.job where jobname = 'bar-purge');
exception when undefined_function or invalid_schema_name or undefined_table then null; end $$;
drop function if exists public.bar_create(uuid), public.bar_save_settings(uuid, jsonb), public.bar_save_item(uuid, jsonb),
  public.bar_set_staff(uuid, uuid, boolean), public.my_bar(uuid), public.bar_order(uuid, jsonb, text, int), public.bar_cancel_mine(uuid, uuid, int),
  public.bar_declare_refund(uuid, numeric), public.bar_scan(uuid, text), public.bar_serve(uuid, uuid, jsonb, text), public.bar_undo_serve(uuid, uuid),
  public.bar_cancel_units(uuid, uuid, uuid, int), public.bar_correct_unit(uuid, uuid), public.bar_confirm_refund(uuid, uuid, boolean),
  public.bar_overview(uuid), public.bar_person(uuid, uuid);
drop table if exists public.event_bar_log, public.event_bar_staff, public.event_bar_refunds, public.event_bar_serves,
  public.event_bar_units, public.event_bar_pledges, public.event_bar_items, public.event_bars cascade;
drop function if exists private.guard_bar_unit(), private.guard_bar_append_only(), private.bar_can_manage(uuid), private.bar_is_present(uuid, uuid),
  private.bar_can_serve(uuid), private.bar_eligible(uuid, uuid), private.bar_phase(public.event_bars), private.bar_method_label(text),
  private.bar_date_fr(date), private.bar_pledge_text(public.event_bars), private.bar_counts(uuid), private.bar_balance(uuid, uuid),
  private.bar_log(uuid, text, uuid, uuid, bigint, numeric, jsonb), private.bar_chf(numeric), private.bar_require(uuid), private.bar_close(uuid),
  private.close_due_bars(), private.purge_old_bars();
alter table public.notification_prefs drop column if exists bar_served, drop column if exists bar_changed,
  drop column if exists bar_refund_declared, drop column if exists bar_refund_confirmed;

delete from supabase_migrations.schema_migrations where version = '20261110120000';
delete from supabase_migrations.schema_migrations where version = '20261110130000';
delete from supabase_migrations.schema_migrations where version = '20261110140000';
delete from supabase_migrations.schema_migrations where version = '20261110150000';
delete from supabase_migrations.schema_migrations where version = '20261110160000';
commit;

notify pgrst, 'reload schema';
