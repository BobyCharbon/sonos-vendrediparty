-- PROD, retour arrière de 20261029180000 (discussions de groupe, avis n°10). EFFACE les messages, réactions,
-- admins de groupe et réglages de discussion ; les photos deviennent inaccessibles. Les fonctions d'envoi des notifications
-- reprennent leur définition de prod d'avant la migration (copiées de la prod le 29.10.2026).
begin;
select cron.unschedule('chat-photos-expire') where exists (select 1 from cron.job where jobname = 'chat-photos-expire');
do $$ begin
  if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'group_message_reactions') then
    alter publication supabase_realtime drop table public.group_message_reactions; end if;
  if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'group_messages') then
    alter publication supabase_realtime drop table public.group_messages; end if;
end $$;
CREATE OR REPLACE FUNCTION public.claim_push_deliveries(batch_size integer DEFAULT 100)
 RETURNS TABLE(delivery_id uuid, notification_id uuid, user_id uuid, token text, attempts integer, title text, body text, data jsonb)
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
  with chosen as (
    select d.id from public.notification_deliveries d join public.notifications n on n.id=d.notification_id
    join public.notification_prefs p on p.user_id=n.user_id
    where d.status='queued' and d.next_attempt_at<=now() and (d.lease_until is null or d.lease_until<now())
      and not n.skipped and p.push_enabled and not private.push_is_quiet(p.quiet_start,p.quiet_end)
      and exists(select 1 from public.profiles p where p.id=n.user_id and private.is_member(p.id))
      and exists(select 1 from public.push_tokens t where t.token=d.token and t.user_id=n.user_id and t.session_id is not null)
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,100),100)) for update of d skip locked
  ), claimed as (
    update public.notification_deliveries d set lease_until=now()+interval '2 minutes', attempts=d.attempts+1
      from chosen c where d.id=c.id returning d.*
  )
  select d.id,d.notification_id,n.user_id,d.token,d.attempts,n.title,n.body,n.data
    from claimed d join public.notifications n on n.id=d.notification_id;
$function$;

CREATE OR REPLACE FUNCTION public.prepare_push_deliveries()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  update public.notifications n set skipped=true where n.sent_at is null and not n.skipped
    and (not exists(select 1 from public.profiles p where p.id=n.user_id and private.is_member(p.id))
      or not exists(select 1 from public.notification_prefs p where p.user_id=n.user_id and p.push_enabled)
      or not exists(select 1 from public.push_tokens t where t.user_id=n.user_id and t.session_id is not null));
  update public.notification_deliveries d set status='failed', error='DeviceUnavailable', lease_until=null
    from public.notifications n where n.id=d.notification_id and d.status='queued'
      and (n.skipped or not exists(select 1 from public.push_tokens t where t.user_id=n.user_id and t.token=d.token and t.session_id is not null));
  insert into public.notification_deliveries(notification_id,token)
    select n.id,t.token from public.notifications n join public.push_tokens t on t.user_id=n.user_id
    where n.sent_at is null and not n.skipped and t.session_id is not null
    on conflict(notification_id,token) do nothing;
end;
$function$;

CREATE OR REPLACE FUNCTION private.claim_web_push_deliveries(batch_size integer DEFAULT 20)
 RETURNS jsonb
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
  with chosen as (
    select d.id from private.web_push_deliveries d join public.notifications n on n.id=d.notification_id
    join private.web_push_subscriptions s on s.id=d.subscription_id
    join auth.sessions a on a.id=s.session_id and (a.not_after is null or a.not_after>now())
    left join public.notification_prefs p on p.user_id=n.user_id
    where d.status='queued' and d.next_attempt_at<=now() and (d.lease_until is null or d.lease_until<now())
      and n.user_id=s.user_id and n.read_at is null and n.created_at>=s.registered_at and private.web_push_allowed(n)
      and (n.kind='web_push_test' or not private.push_is_quiet(p.quiet_start,p.quiet_end))
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,20),50)) for update of d skip locked
  ), claimed as (
    update private.web_push_deliveries d set lease_until=now()+interval '2 minutes',attempts=attempts+1
      from chosen c where c.id=d.id returning d.*
  ) select coalesce(jsonb_agg(jsonb_build_object('id',d.id,'attempts',d.attempts,'subscription',s.subscription,
    'origin',s.origin,'title',n.title,'body',n.body,'event_id',n.event_id,'kind',n.kind,'notification_id',n.id)), '[]'::jsonb)
    from claimed d join public.notifications n on n.id=d.notification_id join private.web_push_subscriptions s on s.id=d.subscription_id;
$function$;

CREATE OR REPLACE FUNCTION private.web_push_allowed(notification notifications)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare prefs public.notification_prefs; ev public.events;
begin
  if not exists(select 1 from public.profiles where id=notification.user_id and private.is_member(id)) then return false; end if;
  if notification.kind='admin_announcement' then
    return exists(select 1 from public.admin_announcements where id::text=notification.data->>'announcement_id');
  end if;
  if notification.kind='web_push_test' then return true; end if;
  select * into prefs from public.notification_prefs where user_id=notification.user_id;
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
    else true end;
end $function$;

drop function if exists private.may_receive_push(uuid, text);
drop function if exists private.expire_chat_photos();
drop policy if exists "envoyer une photo dans son groupe" on storage.objects;
drop policy if exists "voir les photos de ses groupes" on storage.objects;
-- Le compartiment chat-photos reste (Supabase interdit d'effacer les fichiers en SQL) : sans ses règles, plus personne
-- n'y lit ni n'écrit. Pour le vider : Dashboard › Storage › chat-photos › Empty bucket.
drop function if exists public.my_chats();
drop function if exists public.mark_group_read(uuid);
drop function if exists public.set_group_chat_notify(uuid, text);
drop function if exists public.set_group_admin(uuid, uuid, boolean);
drop function if exists public.pin_group_message(uuid, boolean);
drop function if exists public.edit_group_message(uuid, text);
drop function if exists public.delete_group_message(uuid);
drop table if exists public.group_chat_settings;
drop table if exists public.group_admins;
drop table if exists public.group_message_reactions;
drop table if exists public.group_messages;
drop function if exists private.notify_group_message();
drop function if exists private.guard_group_message();
drop function if exists private.group_admin(uuid, uuid);
drop function if exists private.reads_group(uuid);
drop function if exists private.in_group_now(uuid, uuid);
delete from public.notifications where kind = 'group_message';
delete from supabase_migrations.schema_migrations where version = '20261029180000';
commit;
