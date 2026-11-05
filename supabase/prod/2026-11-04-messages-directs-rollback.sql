-- PROD, retour arrière de direct_messages (20261104100000) : les messages directs disparaissent (tables supprimées,
-- AVEC leurs messages : à n'utiliser qu'en cas de problème grave) ; les fonctions modifiées reprennent leur version d'avant
-- (referral_join gardé : il appartient à 20261104090000 et reste sans effet tant que celle-ci n'est pas en prod).
-- Photos et vocaux déjà envoyés restent dans chat-photos, illisibles (plus aucune règle ne les ouvre). Tout ou rien.
begin;

drop policy if exists "envoyer une photo en message direct" on storage.objects;
drop policy if exists "voir les photos de mes messages directs" on storage.objects;

do $$
begin
  if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'direct_message_reactions') then
    alter publication supabase_realtime drop table public.direct_message_reactions;
  end if;
  if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'direct_messages') then
    alter publication supabase_realtime drop table public.direct_messages;
  end if;
end $$;

drop function if exists public.start_direct_chat(uuid, text);
drop function if exists public.delete_direct_message(uuid);
drop function if exists public.edit_direct_message(uuid, text);
drop function if exists public.pin_direct_message(uuid, boolean);
drop function if exists public.set_direct_chat_notify(uuid, text);
drop function if exists public.mark_direct_read(uuid);
drop function if exists public.set_direct_block(uuid, boolean);
drop function if exists public.direct_chat_people(uuid);

-- Fonctions modifiées : version d'avant (elles ne lisent plus les tables supprimées ensuite).
create or replace function public.my_chats() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(c order by (c->>'last_at') desc nulls last, c->>'name'), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', g.id, 'name', g.name, 'system', g.system_key is not null,
      'member', private.in_group_now(g.id, auth.uid()),
      'admin', private.group_admin(g.id, auth.uid()),
      'creator', g.created_by = auth.uid(),
      'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
      'notify', coalesce(s.notify, 'mentions'),
      'last_at', last.created_at,
      'last', case when last.id is null then null
                   when last.deleted_at is not null then case when last.deleted_by_admin then 'Message supprimé par un admin' else 'Message supprimé' end
                   else coalesce((select display_name from public.profiles where id = last.user_id), '?') || ' : '
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or private.is_root(auth.uid()))
  ) x;
$$;

create or replace function private.expire_chat_photos() returns integer
language sql security definer set search_path = '' as $$
  with gone as (update public.group_messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1)
  select count(*)::int from gone;
$$;

create or replace function private.reads_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (private.in_group_now(grp, auth.uid()) or private.is_root(auth.uid()));
$$;

create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join') and private.is_account_active(uid));
$$;

create or replace function private.push_paused(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select not private.push_pause_exempt(kind) and exists (
    select 1 from public.notification_prefs p where p.user_id = uid
      and (p.muted_until > now()
        or (kind = 'group_message' and p.chats_muted_until > now())
        or (kind = 'message' and p.event_chats_muted_until > now())));
$$;

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
    when 'referral_join' then coalesce(prefs.referral_joins, true)
    when 'ticket_pay_declared' then coalesce(prefs.ticket_pay_declared, true)
    when 'ticket_pay_confirmed' then coalesce(prefs.ticket_pay_confirmed, true)
    else true end;
end $function$;

drop trigger if exists direct_messages_notify on public.direct_messages;
drop trigger if exists direct_messages_guard on public.direct_messages;
drop function if exists private.notify_direct_message();
drop function if exists private.guard_direct_message();
drop table if exists public.direct_message_reactions;
drop table if exists public.direct_chat_settings;
drop table if exists public.direct_blocks;
drop table if exists public.direct_messages;
drop table if exists public.direct_chats;
drop function if exists private.dm_knows(uuid, uuid, text);
drop function if exists private.dm_events_of(uuid);
drop function if exists private.dm_blocked(uuid, uuid);
drop function if exists private.direct_other(uuid, uuid);
drop function if exists private.in_direct(uuid, uuid);
alter table public.notification_prefs drop column if exists direct_messages;
update public.notifications set skipped = true where kind = 'direct_message' and sent_at is null;

delete from supabase_migrations.schema_migrations where version = '20261104100000';
commit;

notify pgrst, 'reload schema';
