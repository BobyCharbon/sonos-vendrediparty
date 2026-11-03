-- PROD, retour arrière de event_attendance_tickets (20261103130000) : enlève la pastille des présents, les billets QR
-- et le paiement entre amis (arrivées et « payé » notés perdus) ; remet la règle des notifications de
-- 20261103120000_notification_pause. Le code web retombe seul sur le décompte local si event_attendance manque.
begin;
drop function if exists public.confirm_ticket_payment(uuid, uuid, boolean);
drop function if exists public.declare_ticket_payment(uuid, boolean);
drop function if exists public.event_pay_info(uuid);
drop function if exists private.event_managers(uuid);
drop function if exists public.event_checkins(uuid);
drop function if exists public.set_ticket_paid(uuid, uuid, boolean);
drop function if exists public.set_ticket_arrival(uuid, uuid, boolean);
drop function if exists public.check_in_ticket(uuid, text);
drop function if exists public.renew_event_ticket(uuid, uuid);
drop function if exists public.my_event_ticket(uuid);
drop function if exists private.ticket_view(uuid, uuid);
drop function if exists private.require_scanner(uuid);
drop function if exists private.can_scan(uuid);
drop function if exists private.ensure_ticket(uuid, uuid);
drop function if exists private.new_ticket_code(uuid);
drop function if exists private.new_ticket_token();
drop table if exists public.event_tickets;
drop function if exists public.event_attendance(uuid[]);
drop function if exists private.sees_participants(uuid);
alter table public.notification_prefs drop column if exists ticket_pay_declared;
alter table public.notification_prefs drop column if exists ticket_pay_confirmed;
delete from public.notifications where kind in ('ticket_pay_declared', 'ticket_pay_confirmed');
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
    else true end;
end $function$;

delete from supabase_migrations.schema_migrations where version = '20261103130000';
commit;
