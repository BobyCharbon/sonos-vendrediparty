-- PROD, group_chats (20261029180000). À appliquer SEULEMENT après « Ok prod ». Rejouable.
begin;
-- Discussions de groupe (avis n°10 de l'admin, 29 octobre 2026), façon messagerie instantanée :
-- une discussion par groupe (Vendredi Party compris) ; messages, réponses, @surnom, @tout (admins du groupe),
-- photos (gardées 90 jours), réactions emoji, messages épinglés ; un message supprimé par un admin devient
-- « Message supprimé par un admin ». Admins du groupe : son créateur, ceux qu'il nomme, et les admins / co-admins
-- du site qui en font partie. Root lit toutes les discussions (tests de l'admin), sans mention.
-- Notifications : par défaut seulement quand on est cité (@surnom, @tout ou réponse) ; chacun choisit par groupe
-- (tous les messages, citations, rien). Les comptes Guest reçoivent aussi les notifications de leurs groupes.
-- Rejouable.

create table if not exists public.group_messages (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  body text not null default '' check (char_length(body) <= 2000),
  photo_path text,
  reply_to uuid references public.group_messages(id) on delete set null,
  mentions uuid[] not null default '{}',
  mention_all boolean not null default false,
  pinned boolean not null default false,
  created_at timestamptz not null default now(),
  edited_at timestamptz,
  deleted_at timestamptz,
  deleted_by_admin boolean not null default false,
  check (btrim(body) <> '' or photo_path is not null or deleted_at is not null)
);
create index if not exists group_messages_by_group on public.group_messages (group_id, created_at desc);
-- Messages vocaux (30.10) : fichier audio dans le même compartiment privé que les photos, durée en secondes.
alter table public.group_messages add column if not exists audio_path text;
alter table public.group_messages add column if not exists audio_seconds numeric(6, 1) check (audio_seconds between 0 and 600);
alter table public.group_messages drop constraint if exists group_messages_check;
alter table public.group_messages drop constraint if exists group_messages_content;
alter table public.group_messages add constraint group_messages_content
  check (btrim(body) <> '' or photo_path is not null or audio_path is not null or deleted_at is not null);

create table if not exists public.group_message_reactions (
  message_id uuid not null references public.group_messages(id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  emoji text not null check (char_length(emoji) between 1 and 16),
  created_at timestamptz not null default now(),
  primary key (message_id, user_id, emoji)
);

create table if not exists public.group_admins (
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  primary key (group_id, user_id)
);

create table if not exists public.group_chat_settings (
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  notify text not null default 'mentions' check (notify in ('all', 'mentions', 'none')),
  read_at timestamptz,
  primary key (group_id, user_id)
);

-- Qui fait quoi --------------------------------------------------------------------------------------------------

create or replace function private.in_group_now(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_group_members where group_id = grp and user_id = uid);
$$;

create or replace function private.reads_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (private.in_group_now(grp, auth.uid()) or private.is_root(auth.uid()));
$$;

create or replace function private.group_admin(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and (
    private.is_root(uid)
    or exists (select 1 from public.member_groups g where g.id = grp and g.created_by = uid)
    or (private.in_group_now(grp, uid) and (
          exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid)
          or private.rank_of(uid) >= 3)));  -- admins et co-admins du site : admins d'office de leurs groupes
$$;

revoke all on function private.in_group_now(uuid, uuid), private.reads_group(uuid), private.group_admin(uuid, uuid) from public, anon;
grant execute on function private.in_group_now(uuid, uuid), private.reads_group(uuid), private.group_admin(uuid, uuid) to authenticated;

-- Règles d'accès ---------------------------------------------------------------------------------------------------

alter table public.group_messages enable row level security;
alter table public.group_message_reactions enable row level security;
alter table public.group_admins enable row level security;
alter table public.group_chat_settings enable row level security;

drop policy if exists "lire les messages de ses groupes" on public.group_messages;
create policy "lire les messages de ses groupes" on public.group_messages for select to authenticated
  using (private.reads_group(group_id));
drop policy if exists "écrire dans ses groupes" on public.group_messages;
create policy "écrire dans ses groupes" on public.group_messages for insert to authenticated
  with check (user_id = (select auth.uid()) and private.in_group_now(group_id, (select auth.uid()))
              and private.is_account_active((select auth.uid())));

drop policy if exists "voir les réactions" on public.group_message_reactions;
create policy "voir les réactions" on public.group_message_reactions for select to authenticated
  using (exists (select 1 from public.group_messages m where m.id = message_id and private.reads_group(m.group_id)));
drop policy if exists "réagir" on public.group_message_reactions;
create policy "réagir" on public.group_message_reactions for insert to authenticated
  with check (user_id = (select auth.uid()) and exists (select 1 from public.group_messages m
              where m.id = message_id and m.deleted_at is null and private.in_group_now(m.group_id, (select auth.uid()))));
drop policy if exists "retirer sa réaction" on public.group_message_reactions;
create policy "retirer sa réaction" on public.group_message_reactions for delete to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists "voir les admins du groupe" on public.group_admins;
create policy "voir les admins du groupe" on public.group_admins for select to authenticated
  using (private.reads_group(group_id));

drop policy if exists "mes réglages de discussion" on public.group_chat_settings;
create policy "mes réglages de discussion" on public.group_chat_settings for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

grant select, insert on public.group_messages to authenticated;
grant select, insert, delete on public.group_message_reactions to authenticated;
grant select on public.group_admins to authenticated;
grant select, insert, update on public.group_chat_settings to authenticated;

-- Un message à l'arrivée : auteur = la personne connectée ; @tout réservé aux admins du groupe ; citations limitées
-- aux membres du groupe ; rien de supprimé ni d'épinglé d'office.
create or replace function private.guard_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null then new.user_id := auth.uid(); end if;
  new.body := btrim(new.body);
  new.pinned := false;
  new.deleted_at := null;
  new.deleted_by_admin := false;
  new.edited_at := null;
  new.created_at := now();
  if new.mention_all and not private.group_admin(new.group_id, new.user_id) then new.mention_all := false; end if;
  new.mentions := coalesce((select array_agg(distinct m) from unnest(new.mentions) m
                            where private.in_group_now(new.group_id, m) and m <> new.user_id), '{}');
  if new.reply_to is not null and not exists (select 1 from public.group_messages r where r.id = new.reply_to and r.group_id = new.group_id) then
    new.reply_to := null;
  end if;
  if new.photo_path is not null and split_part(new.photo_path, '/', 1) <> new.group_id::text then
    raise exception 'Photo invalide';
  end if;
  if new.audio_path is not null and split_part(new.audio_path, '/', 1) <> new.group_id::text then
    raise exception 'Message vocal invalide';
  end if;
  return new;
end $$;
drop trigger if exists group_messages_guard on public.group_messages;
create trigger group_messages_guard before insert on public.group_messages
  for each row execute function private.guard_group_message();

-- Notifications : citations (@surnom, @tout, réponse) par défaut ; « tous les messages » ou « rien » au choix.
create or replace function private.notify_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text; replied uuid; u uuid; level text; cited boolean; preview text;
begin
  select * into g from public.member_groups where id = new.group_id;
  select display_name into who from public.profiles where id = new.user_id;
  select user_id into replied from public.group_messages where id = new.reply_to;
  preview := case when new.body <> '' then left(new.body, 140) when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end;
  for u in select user_id from public.member_group_members where group_id = new.group_id and user_id <> new.user_id loop
    select notify into level from public.group_chat_settings where group_id = new.group_id and user_id = u;
    cited := new.mention_all or u = any(new.mentions) or u = replied;
    if coalesce(level, 'mentions') = 'all' or (coalesce(level, 'mentions') = 'mentions' and cited) then
      insert into public.notifications (user_id, kind, event_id, title, body, data)
      values (u, 'group_message', null, g.name, coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' : ' || preview,
              jsonb_build_object('group_id', g.id, 'message_id', new.id, 'mentioned', cited, 'kind', 'group_message'));
    end if;
  end loop;
  return null;
end $$;
drop trigger if exists group_messages_notify on public.group_messages;
create trigger group_messages_notify after insert on public.group_messages
  for each row execute function private.notify_group_message();

-- Actions -----------------------------------------------------------------------------------------------------------

create or replace function public.delete_group_message(msg uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.group_messages;
begin
  select * into m from public.group_messages where id = msg and deleted_at is null;
  if m.id is null then raise exception 'Message introuvable'; end if;
  if m.user_id = auth.uid() then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false, pinned = false,
      deleted_at = now(), deleted_by_admin = false where id = msg;
  elsif private.group_admin(m.group_id, auth.uid()) then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false, pinned = false,
      deleted_at = now(), deleted_by_admin = true where id = msg;
  else
    raise exception 'forbidden: seuls l''auteur et les admins du groupe suppriment un message' using errcode = '42501';
  end if;
  delete from public.group_message_reactions where message_id = msg;
end $$;

create or replace function public.edit_group_message(msg uuid, new_body text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if btrim(coalesce(new_body, '')) = '' or char_length(new_body) > 2000 then raise exception 'Message vide ou trop long'; end if;
  update public.group_messages set body = btrim(new_body), edited_at = now()
    where id = msg and user_id = auth.uid() and deleted_at is null;
  if not found then raise exception 'forbidden: tu ne peux modifier que tes messages' using errcode = '42501'; end if;
end $$;

create or replace function public.pin_group_message(msg uuid, pin boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  select group_id into grp from public.group_messages where id = msg and deleted_at is null;
  if grp is null or not private.group_admin(grp, auth.uid()) then
    raise exception 'forbidden: réservé aux admins du groupe' using errcode = '42501';
  end if;
  update public.group_messages set pinned = pin where id = msg;
end $$;

-- Le créateur (ou un admin du site) nomme ou retire les admins du groupe.
create or replace function public.set_group_admin(grp uuid, member uuid, admin boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select 1 from public.member_groups g where g.id = grp
                 and (g.created_by = auth.uid() or private.is_root(auth.uid()) or private.rank_of(auth.uid()) >= 3)) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  if not private.in_group_now(grp, member) then raise exception 'Cette personne n''est pas dans le groupe'; end if;
  if admin then
    insert into public.group_admins (group_id, user_id) values (grp, member) on conflict do nothing;
  else
    delete from public.group_admins where group_id = grp and user_id = member;
  end if;
end $$;

create or replace function public.set_group_chat_notify(grp uuid, level text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if level not in ('all', 'mentions', 'none') then raise exception 'Choix inconnu'; end if;
  if not private.in_group_now(grp, auth.uid()) then raise exception 'forbidden: tu ne fais pas partie de ce groupe' using errcode = '42501'; end if;
  insert into public.group_chat_settings (group_id, user_id, notify) values (grp, auth.uid(), level)
  on conflict (group_id, user_id) do update set notify = excluded.notify;
end $$;

create or replace function public.mark_group_read(grp uuid) returns void
language sql security definer set search_path = '' as $$
  insert into public.group_chat_settings (group_id, user_id, read_at)
  select grp, auth.uid(), now() where private.in_group_now(grp, auth.uid())
  on conflict (group_id, user_id) do update set read_at = now();
$$;

-- Liste des discussions : mes groupes (tous pour root), dernier message, non lus, mon réglage, admin ou pas.
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

revoke all on function public.delete_group_message(uuid), public.edit_group_message(uuid, text), public.pin_group_message(uuid, boolean),
  public.set_group_admin(uuid, uuid, boolean), public.set_group_chat_notify(uuid, text), public.mark_group_read(uuid),
  public.my_chats() from public, anon;
grant execute on function public.delete_group_message(uuid), public.edit_group_message(uuid, text), public.pin_group_message(uuid, boolean),
  public.set_group_admin(uuid, uuid, boolean), public.set_group_chat_notify(uuid, text), public.mark_group_read(uuid),
  public.my_chats() to authenticated;

-- Photos (bucket privé, dossier = groupe) : envoyées et vues par les membres du groupe ; gardées 90 jours.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('chat-photos', 'chat-photos', false, 8 * 1024 * 1024, array['image/jpeg', 'image/png', 'image/heic', 'image/webp',
        'audio/mp4', 'audio/x-m4a', 'audio/aac', 'audio/webm', 'audio/ogg', 'audio/mpeg'])
on conflict (id) do update set file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "envoyer une photo dans son groupe" on storage.objects;
create policy "envoyer une photo dans son groupe" on storage.objects for insert to authenticated
  with check (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
              and private.in_group_now(((storage.foldername(name))[1])::uuid, (select auth.uid())));
drop policy if exists "voir les photos de ses groupes" on storage.objects;
create policy "voir les photos de ses groupes" on storage.objects for select to authenticated
  using (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and private.reads_group(((storage.foldername(name))[1])::uuid));

-- Au-delà de 90 jours, la photo n'est plus montrée (le message reste, avec « 📷 Photo expirée »).
create or replace function private.expire_chat_photos() returns integer
language sql security definer set search_path = '' as $$
  with gone as (update public.group_messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1)
  select count(*)::int from gone;
$$;
select cron.schedule('chat-photos-expire', '17 4 * * *', $cron$ select private.expire_chat_photos(); $cron$);

-- Temps réel (messagerie instantanée).
do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'group_messages') then
    alter publication supabase_realtime add table public.group_messages;
  end if;
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'group_message_reactions') then
    alter publication supabase_realtime add table public.group_message_reactions;
  end if;
end $$;

-- Notifications des groupes aussi pour les comptes Guest (qui ne voient pas les événements).
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join') and private.is_account_active(uid));
$$;
revoke all on function private.may_receive_push(uuid, text) from public, anon;

CREATE OR REPLACE FUNCTION private.web_push_allowed(notification notifications)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare prefs public.notification_prefs; ev public.events;
begin
  if not exists(select 1 from public.profiles where id=notification.user_id and private.may_receive_push(id, notification.kind)) then return false; end if;
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

CREATE OR REPLACE FUNCTION public.prepare_push_deliveries()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  update public.notifications n set skipped=true where n.sent_at is null and not n.skipped
    and (not exists(select 1 from public.profiles p where p.id=n.user_id and private.may_receive_push(p.id, n.kind))
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
      and exists(select 1 from public.profiles p where p.id=n.user_id and private.may_receive_push(p.id, n.kind))
      and exists(select 1 from public.push_tokens t where t.token=d.token and t.user_id=n.user_id and t.session_id is not null)
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,100),100)) for update of d skip locked
  ), claimed as (
    update public.notification_deliveries d set lease_until=now()+interval '2 minutes', attempts=d.attempts+1
      from chosen c where d.id=c.id returning d.*
  )
  select d.id,d.notification_id,n.user_id,d.token,d.attempts,n.title,n.body,n.data
    from claimed d join public.notifications n on n.id=d.notification_id;
$function$;

-- Web Push : le toucher d'une notification de discussion ouvre la conversation (send-web-push lit group_id).
create or replace function private.claim_web_push_deliveries(batch_size integer default 20) returns jsonb
language sql security definer set search_path='' as $$
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
    'origin',s.origin,'title',n.title,'body',n.body,'event_id',n.event_id,'kind',n.kind,'group_id',n.data->>'group_id','notification_id',n.id)), '[]'::jsonb)
    from claimed d join public.notifications n on n.id=d.notification_id join private.web_push_subscriptions s on s.id=d.subscription_id;
$$;

-- Infos du groupe (avis n°10, 30.10) : numéros que les membres montrent dans CE groupe (Réglages › Groupes),
-- pour les appeler d'un toucher. Seuls les membres du groupe les lisent.
create or replace function public.group_chat_phones(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'phone', p.phone) order by p.display_name), '[]'::jsonb)
  from private.group_phone_shares s
  join public.profiles p on p.id = s.user_id and p.status = 'active' and coalesce(p.phone, '') <> ''
  where s.group_id = grp and private.in_group_now(grp, s.user_id) and private.in_group_now(grp, auth.uid());
$$;
revoke all on function public.group_chat_phones(uuid) from public, anon;
grant execute on function public.group_chat_phones(uuid) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261029180000', 'group_chats')
  on conflict (version) do nothing;
commit;
