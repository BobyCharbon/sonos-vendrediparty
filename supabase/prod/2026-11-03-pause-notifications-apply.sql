-- PROD, notification_pause (20261103120000). À appliquer SEULEMENT après « Ok prod ». Rejouable.
-- Fonctions Edge à redéployer en prod avec : send-push, send-web-push (champ « silent »), sinon les pauses sonnent encore.
begin;
-- Pause des notifications et choix complets par type (avis de l'admin du 3 novembre 2026).
-- 1) Lune des Réglages (muted_until) : pendant 1 h, 2 h ou jusqu'au prochain 8 h (Zurich), TOUTES les notifications
--    (admin comprises) arrivent SANS son ni vibration : livrées en silence dans le centre de notifications.
-- 2) Deux pauses distinctes, mêmes règles : Discussions des groupes (chats_muted_until, kind group_message) et
--    discussions des événements (event_chats_muted_until, kind message) : 30 min, 1 h, 2 h ou 8 h.
-- 3) « S'il peut recevoir une forme de notification, il doit pouvoir la désactiver » : chaque kind a son réglage
--    (nouvelles colonnes ci-dessous), et l'app iOS (APNs) applique désormais les mêmes choix que le web push
--    (avant : seul push_enabled comptait pour l'iPhone).
-- Seuls les essais demandés depuis les Réglages (push_test, web_push_test) sonnent toujours. Une pause passée ne
-- compte plus. Les Live Activities ne passent pas par ici.
-- Purement additif et rejouable : colonnes « if not exists », fonctions « create or replace ».

alter table public.notification_prefs add column if not exists muted_until timestamptz;
alter table public.notification_prefs add column if not exists chats_muted_until timestamptz;
alter table public.notification_prefs add column if not exists event_chats_muted_until timestamptz;
-- Un réglage par type qui n'en avait pas (activés par défaut : rien ne change tant qu'on n'y touche pas).
alter table public.notification_prefs add column if not exists announcements boolean not null default true;   -- admin_announcement
alter table public.notification_prefs add column if not exists rsvp_set boolean not null default true;        -- un organisateur t'a noté présent…
alter table public.notification_prefs add column if not exists invites boolean not null default true;         -- private_invite
alter table public.notification_prefs add column if not exists proposal_result boolean not null default true; -- approved / rejected
alter table public.notification_prefs add column if not exists link_join boolean not null default true;       -- quelqu'un rejoint par le lien
alter table public.notification_prefs add column if not exists group_messages boolean not null default true;  -- group_message
alter table public.notification_prefs add column if not exists group_invites boolean not null default true;   -- group_invite
alter table public.notification_prefs add column if not exists group_joins boolean not null default true;     -- group_join

-- Essais demandés par le membre lui-même : jamais réduits au silence.
create or replace function private.push_pause_exempt(kind text) returns boolean
language sql immutable set search_path = '' as $$
  select kind in ('push_test', 'web_push_test');
$$;
revoke all on function private.push_pause_exempt(text) from public, anon, authenticated;

-- Vrai si cette notification doit arriver sans son ni vibration (lune, ou pause de sa discussion).
create or replace function private.push_paused(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select not private.push_pause_exempt(kind) and exists (
    select 1 from public.notification_prefs p where p.user_id = uid
      and (p.muted_until > now()
        or (kind = 'group_message' and p.chats_muted_until > now())
        or (kind = 'message' and p.event_chats_muted_until > now())));
$$;
revoke all on function private.push_paused(uuid, text) from public, anon, authenticated;

-- Fin d'une pause : maintenant + 30 min / 1 h / 2 h, ou le prochain 8 h du matin à Zurich ; « off » la retire.
create or replace function private.pause_end(span text) returns timestamptz
language sql stable set search_path = '' as $$
  select case span
    when '30m' then now() + interval '30 minutes'
    when '1h' then now() + interval '1 hour'
    when '2h' then now() + interval '2 hours'
    when 'morning' then (
      select (case when z < date_trunc('day', z) + interval '8 hours' then date_trunc('day', z) + interval '8 hours'
                   else date_trunc('day', z) + interval '1 day 8 hours' end) at time zone 'Europe/Zurich'
      from (select now() at time zone 'Europe/Zurich' as z) t)
    else null end;
$$;
revoke all on function private.pause_end(text) from public, anon, authenticated;

-- Réglages (web et iOS) : what = 'all' (lune), 'chats' (Discussions des groupes) ou 'event_chats' (discussions des
-- événements) ; span = '30m', '1h', '2h', 'morning', 'off'.
create or replace function public.set_notification_pause(what text, span text) returns public.notification_prefs
language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); until timestamptz; result public.notification_prefs;
begin
  if uid is null then raise exception 'Connexion requise' using errcode = '28000'; end if;
  if what is null or span is null or what not in ('all', 'chats', 'event_chats')
     or span not in ('30m', '1h', '2h', 'morning', 'off') then
    raise exception 'Durée de pause inconnue' using errcode = '22023';
  end if;
  until := private.pause_end(span);
  insert into public.notification_prefs (user_id) values (uid) on conflict (user_id) do nothing;
  if what = 'all' then
    update public.notification_prefs set muted_until = until where user_id = uid returning * into result;
  elsif what = 'chats' then
    update public.notification_prefs set chats_muted_until = until where user_id = uid returning * into result;
  else
    update public.notification_prefs set event_chats_muted_until = until where user_id = uid returning * into result;
  end if;
  return result;
end $$;
revoke all on function public.set_notification_pause(text, text) from public, anon;
grant execute on function public.set_notification_pause(text, text) to authenticated;

-- Le membre veut-il recevoir cette notification ? Une seule règle pour TOUS les canaux (iPhone APNs, Expo, Web Push).
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

-- App iOS (APNs) et Expo : mêmes choix que le web push (avant : seul « Recevoir mes alertes » comptait).
CREATE OR REPLACE FUNCTION public.prepare_push_deliveries()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  update public.notifications n set skipped=true where n.sent_at is null and not n.skipped
    and (not private.web_push_allowed(n)
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

-- Envoi APNs / Expo : choix revérifiés au moment d'envoyer ; data.silent = true pendant une pause (pas de son).
CREATE OR REPLACE FUNCTION public.claim_push_deliveries(batch_size integer DEFAULT 100)
 RETURNS TABLE(delivery_id uuid, notification_id uuid, user_id uuid, token text, attempts integer, title text, body text, data jsonb)
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
  with chosen as (
    select d.id from public.notification_deliveries d join public.notifications n on n.id=d.notification_id
    left join public.notification_prefs p on p.user_id=n.user_id
    where d.status='queued' and d.next_attempt_at<=now() and (d.lease_until is null or d.lease_until<now())
      and not n.skipped and private.web_push_allowed(n)
      and (n.kind='push_test' or not private.push_is_quiet(p.quiet_start,p.quiet_end))
      and exists(select 1 from public.push_tokens t where t.token=d.token and t.user_id=n.user_id and t.session_id is not null)
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,100),100)) for update of d skip locked
  ), claimed as (
    update public.notification_deliveries d set lease_until=now()+interval '2 minutes', attempts=d.attempts+1
      from chosen c where d.id=c.id returning d.*
  )
  select d.id,d.notification_id,n.user_id,d.token,d.attempts,n.title,n.body,
         n.data || jsonb_build_object('silent', private.push_paused(n.user_id, n.kind))
    from claimed d join public.notifications n on n.id=d.notification_id;
$function$;

-- Web Push : même corps qu'avant (20261019094527), plus « silent » pendant une pause.
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
    'origin',s.origin,'title',n.title,'body',n.body,'event_id',n.event_id,'kind',n.kind,'group_id',n.data->>'group_id','notification_id',n.id,
    'silent',private.push_paused(n.user_id, n.kind))), '[]'::jsonb)
    from claimed d join public.notifications n on n.id=d.notification_id join private.web_push_subscriptions s on s.id=d.subscription_id;
$function$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103120000', 'notification_pause')
  on conflict (version) do nothing;
commit;
