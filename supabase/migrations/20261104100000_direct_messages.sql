-- Messages directs dans Discussions (décision de l'admin, 4 novembre 2026) : une discussion privée à deux, ouverte par
-- « Écrire » (Mes amis dans Party, fiche d'un membre) ; elle se mêle aux groupes dans la liste des Discussions.
--
-- Conception : des TABLES DÉDIÉES (direct_chats, direct_messages, direct_message_reactions, direct_chat_settings,
-- direct_blocks), PAS un « groupe caché » dans member_groups. Raison : plus de quinze fonctions et règles parcourent
-- member_groups / member_group_members (Root lit toutes les discussions, les Admins voient tous les groupes, liste des
-- membres de l'admin avec leurs groupes, journal « group.add », cartes « groupes en commun », Mes amis, liens et
-- invitations de groupe, audiences d'événements…) : un message direct y serait exposé à un tiers. Ici, aucune règle
-- existante ne touche ces tables : un message direct n'est lisible QUE par ses deux personnes (ni Root, ni les Admins).
--
-- • une seule conversation par paire (user_a < user_b, unique) : start_direct_chat est idempotente, même en parallèle ;
--   la conversation n'apparaît dans la liste qu'à partir du premier message ;
-- • qui peut écrire à qui (private.dm_knows) : deux comptes actifs qui ont un groupe en commun (Vendredi Party compris),
--   ou un événement en commun (invité, réponse, organisateur ou créateur), ou dont l'un a l'autre dans ses contacts
--   (empreinte du numéro, même clé que contacts_match) ; une conversation déjà ouverte reste toujours possible ;
-- • bloquer : direct_blocks ; dans les deux sens, plus de nouvelle conversation ni de message (l'historique reste lisible) ;
-- • pas d'@tout, d'@annonce ni d'organisateur dans un message direct ; épingler : les deux personnes ; supprimer ou
--   modifier : l'auteur seulement ;
-- • photos et vocaux : même compartiment chat-photos, dossier = id de la conversation, lus et écrits par ses deux
--   personnes seulement ; private.reads_group ne laisse plus Root lire un dossier qui n'est pas un groupe ;
-- • notification « Nouveau message de X » (kind direct_message) : interrupteur notification_prefs.direct_messages
--   (tous les canaux : web_push_allowed, donc prepare_push_deliveries et claim_*), sourdine par conversation, et la
--   pause des Discussions (chats_muted_until) s'applique aussi ; reçue par les comptes Guest (may_receive_push).
-- Purement additif et rejouable.

-- Interrupteur (activé par défaut). referral_joins : colonne de 20261104090000, lue par web_push_allowed ci-dessous.
alter table public.notification_prefs add column if not exists direct_messages boolean not null default true;
alter table public.notification_prefs add column if not exists referral_joins boolean not null default true;

-- Tables -------------------------------------------------------------------------------------------------------------

create table if not exists public.direct_chats (
  id uuid primary key default gen_random_uuid(),
  user_a uuid not null references public.profiles(id) on delete cascade,
  user_b uuid not null references public.profiles(id) on delete cascade,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  constraint direct_chats_ordered check (user_a < user_b),
  constraint direct_chats_pair unique (user_a, user_b)
);
create index if not exists direct_chats_by_b on public.direct_chats (user_b);

create table if not exists public.direct_messages (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.direct_chats(id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  body text not null default '' check (char_length(body) <= 2000),
  photo_path text,
  audio_path text,
  audio_seconds numeric(6, 1) check (audio_seconds between 0 and 600),
  reply_to uuid references public.direct_messages(id) on delete set null,
  pinned boolean not null default false,
  created_at timestamptz not null default now(),
  edited_at timestamptz,
  deleted_at timestamptz,
  constraint direct_messages_content
    check (btrim(body) <> '' or photo_path is not null or audio_path is not null or deleted_at is not null)
);
create index if not exists direct_messages_by_chat on public.direct_messages (chat_id, created_at desc);

create table if not exists public.direct_message_reactions (
  message_id uuid not null references public.direct_messages(id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  emoji text not null check (char_length(emoji) between 1 and 16),
  created_at timestamptz not null default now(),
  primary key (message_id, user_id, emoji)
);

create table if not exists public.direct_chat_settings (
  chat_id uuid not null references public.direct_chats(id) on delete cascade,
  user_id uuid not null default auth.uid() references public.profiles(id) on delete cascade,
  notify text not null default 'all' check (notify in ('all', 'none')),
  read_at timestamptz,
  primary key (chat_id, user_id)
);

create table if not exists public.direct_blocks (
  user_id uuid not null references public.profiles(id) on delete cascade,
  blocked_id uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, blocked_id),
  check (user_id <> blocked_id)
);

-- Qui fait quoi --------------------------------------------------------------------------------------------------------

create or replace function private.in_direct(chat uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and exists (select 1 from public.direct_chats c where c.id = chat and uid in (c.user_a, c.user_b));
$$;

create or replace function private.direct_other(chat uuid, uid uuid) returns uuid
language sql stable security definer set search_path = '' as $$
  select case when c.user_a = uid then c.user_b when c.user_b = uid then c.user_a end
  from public.direct_chats c where c.id = chat;
$$;

-- Blocage dans un sens ou dans l'autre.
create or replace function private.dm_blocked(a uuid, b uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.direct_blocks k
                 where (k.user_id = a and k.blocked_id = b) or (k.user_id = b and k.blocked_id = a));
$$;

-- Événements d'une personne : invitée, réponse donnée, organisatrice ou créatrice.
create or replace function private.dm_events_of(uid uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select event_id from public.rsvps where user_id = uid
  union select event_id from public.event_invites where user_id = uid
  union select event_id from public.event_organizers where user_id = uid
  union select id from public.events where created_by = uid;
$$;

-- « Se connaissent » : un groupe en commun, un événement en commun, ou le numéro de l'autre dans ses contacts
-- (contact_hash = empreinte HMAC « +<numéro> » calculée par l'iPhone avec contacts_key, comme contacts_match).
create or replace function private.dm_knows(me uuid, target uuid, contact_hash text default null) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_group_members a join public.member_group_members b on b.group_id = a.group_id
                 where a.user_id = me and b.user_id = target)
      or exists (select 1 from private.dm_events_of(me) e(id) where e.id in (select private.dm_events_of(target)))
      or (coalesce(contact_hash, '') ~ '^[0-9a-f]{64}$' and exists (
            select 1 from public.profiles p, private.contact_key k
            where p.id = target and k.id = 1 and p.phone ~ '^[1-9][0-9]{7,14}$'
              and encode(extensions.hmac('+' || p.phone, k.key, 'sha256'), 'hex') = contact_hash));
$$;

revoke all on function private.in_direct(uuid, uuid), private.direct_other(uuid, uuid), private.dm_blocked(uuid, uuid),
  private.dm_events_of(uuid), private.dm_knows(uuid, uuid, text) from public, anon;
grant execute on function private.in_direct(uuid, uuid) to authenticated;

-- Root ne lit plus que les vrais groupes (un dossier de photos qui n'est pas un groupe, comme une conversation
-- directe, ne lui est plus ouvert).
create or replace function private.reads_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (private.in_group_now(grp, auth.uid())
    or (private.is_root(auth.uid()) and exists (select 1 from public.member_groups g where g.id = grp)));
$$;

-- Règles d'accès : les deux personnes de la conversation, personne d'autre ---------------------------------------------

alter table public.direct_chats enable row level security;
alter table public.direct_messages enable row level security;
alter table public.direct_message_reactions enable row level security;
alter table public.direct_chat_settings enable row level security;
alter table public.direct_blocks enable row level security;

drop policy if exists "mes conversations directes" on public.direct_chats;
create policy "mes conversations directes" on public.direct_chats for select to authenticated
  using ((select auth.uid()) in (user_a, user_b));

drop policy if exists "lire mes messages directs" on public.direct_messages;
create policy "lire mes messages directs" on public.direct_messages for select to authenticated
  using (private.in_direct(chat_id, (select auth.uid())));
drop policy if exists "écrire un message direct" on public.direct_messages;
create policy "écrire un message direct" on public.direct_messages for insert to authenticated
  with check (user_id = (select auth.uid()) and private.in_direct(chat_id, (select auth.uid()))
              and private.is_account_active((select auth.uid())));

drop policy if exists "voir les réactions directes" on public.direct_message_reactions;
create policy "voir les réactions directes" on public.direct_message_reactions for select to authenticated
  using (exists (select 1 from public.direct_messages m where m.id = message_id and private.in_direct(m.chat_id, (select auth.uid()))));
drop policy if exists "réagir en direct" on public.direct_message_reactions;
create policy "réagir en direct" on public.direct_message_reactions for insert to authenticated
  with check (user_id = (select auth.uid()) and exists (select 1 from public.direct_messages m
              where m.id = message_id and m.deleted_at is null and private.in_direct(m.chat_id, (select auth.uid()))));
drop policy if exists "retirer sa réaction directe" on public.direct_message_reactions;
create policy "retirer sa réaction directe" on public.direct_message_reactions for delete to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists "mes réglages de conversation directe" on public.direct_chat_settings;
create policy "mes réglages de conversation directe" on public.direct_chat_settings for select to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists "mes blocages" on public.direct_blocks;
create policy "mes blocages" on public.direct_blocks for select to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.direct_chats, public.direct_messages, public.direct_message_reactions, public.direct_chat_settings,
  public.direct_blocks from anon;
grant select on public.direct_chats, public.direct_chat_settings, public.direct_blocks to authenticated;
grant select, insert on public.direct_messages to authenticated;
grant select, insert, delete on public.direct_message_reactions to authenticated;

-- Un message à l'arrivée : auteur = la personne connectée, rien d'épinglé ni de supprimé d'office, réponse dans la même
-- conversation, fichiers dans le dossier de la conversation ; personne de bloqué, deux comptes actifs.
create or replace function private.guard_direct_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare other uuid;
begin
  if auth.uid() is not null then new.user_id := auth.uid(); end if;
  other := private.direct_other(new.chat_id, new.user_id);
  if other is null then raise exception 'forbidden: conversation inaccessible' using errcode = '42501'; end if;
  if private.dm_blocked(new.user_id, other) or not private.is_account_active(other) then
    raise exception 'blocked: tu ne peux pas écrire à cette personne' using errcode = '42501';
  end if;
  new.body := btrim(new.body);
  new.pinned := false;
  new.deleted_at := null;
  new.edited_at := null;
  new.created_at := now();
  if new.reply_to is not null and not exists (select 1 from public.direct_messages r where r.id = new.reply_to and r.chat_id = new.chat_id) then
    new.reply_to := null;
  end if;
  if new.photo_path is not null and split_part(new.photo_path, '/', 1) <> new.chat_id::text then
    raise exception 'Photo invalide';
  end if;
  if new.audio_path is not null and split_part(new.audio_path, '/', 1) <> new.chat_id::text then
    raise exception 'Message vocal invalide';
  end if;
  return new;
end $$;
drop trigger if exists direct_messages_guard on public.direct_messages;
create trigger direct_messages_guard before insert on public.direct_messages
  for each row execute function private.guard_direct_message();

-- « Nouveau message de X » pour l'autre personne, sauf si elle a mis la conversation en sourdine. L'interrupteur
-- (direct_messages), la pause des Discussions et les heures calmes s'appliquent à l'envoi (web_push_allowed, push_paused).
create or replace function private.notify_direct_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare other uuid; who text; preview text;
begin
  other := private.direct_other(new.chat_id, new.user_id);
  if other is null or exists (select 1 from public.direct_chat_settings s
                              where s.chat_id = new.chat_id and s.user_id = other and s.notify = 'none') then
    return null;
  end if;
  select display_name into who from public.profiles where id = new.user_id;
  preview := case when new.body <> '' then left(new.body, 140) when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end;
  insert into public.notifications (user_id, kind, event_id, title, body, data)
  values (other, 'direct_message', null, 'Nouveau message de ' || coalesce(nullif(btrim(who), ''), 'quelqu''un'), preview,
          jsonb_build_object('chat_id', new.chat_id, 'group_id', new.chat_id, 'direct', true, 'message_id', new.id,
                             'kind', 'direct_message'));
  return null;
end $$;
drop trigger if exists direct_messages_notify on public.direct_messages;
create trigger direct_messages_notify after insert on public.direct_messages
  for each row execute function private.notify_direct_message();

-- Actions ----------------------------------------------------------------------------------------------------------------

-- Ouvre (ou crée) LA conversation avec target ; idempotente, même appelée deux fois en même temps des deux côtés.
create or replace function public.start_direct_chat(target uuid, contact_hash text default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); a uuid; b uuid; chat uuid;
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if target is null or target = me then raise exception 'Choisis une autre personne' using errcode = '22023'; end if;
  a := least(me, target); b := greatest(me, target);
  select id into chat from public.direct_chats where user_a = a and user_b = b;
  if chat is not null then return chat; end if;  -- déjà ouverte : toujours accessible (l'historique reste lisible)
  if not private.is_account_active(target) or private.dm_blocked(me, target) or not private.dm_knows(me, target, contact_hash) then
    raise exception 'forbidden: tu ne peux pas écrire à cette personne' using errcode = '42501';
  end if;
  insert into public.direct_chats (user_a, user_b, created_by) values (a, b, me)
  on conflict (user_a, user_b) do nothing returning id into chat;
  if chat is null then select id into chat from public.direct_chats where user_a = a and user_b = b; end if;
  return chat;
end $$;

create or replace function public.delete_direct_message(msg uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.direct_messages set body = '', photo_path = null, audio_path = null, pinned = false, deleted_at = now()
    where id = msg and user_id = auth.uid() and deleted_at is null;
  if not found then raise exception 'forbidden: tu ne peux supprimer que tes messages' using errcode = '42501'; end if;
  delete from public.direct_message_reactions where message_id = msg;
end $$;

create or replace function public.edit_direct_message(msg uuid, new_body text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if btrim(coalesce(new_body, '')) = '' or char_length(new_body) > 2000 then raise exception 'Message vide ou trop long'; end if;
  update public.direct_messages set body = btrim(new_body), edited_at = now()
    where id = msg and user_id = auth.uid() and deleted_at is null;
  if not found then raise exception 'forbidden: tu ne peux modifier que tes messages' using errcode = '42501'; end if;
end $$;

-- Épingler / désépingler : les deux personnes de la conversation.
create or replace function public.pin_direct_message(msg uuid, pin boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.direct_messages m set pinned = coalesce(pin, false)
    where m.id = msg and m.deleted_at is null and private.in_direct(m.chat_id, auth.uid());
  if not found then raise exception 'forbidden: conversation inaccessible' using errcode = '42501'; end if;
end $$;

create or replace function public.set_direct_chat_notify(chat uuid, level text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if level is null or level not in ('all', 'none') then raise exception 'Choix inconnu'; end if;
  if not private.in_direct(chat, auth.uid()) then raise exception 'forbidden: conversation inaccessible' using errcode = '42501'; end if;
  insert into public.direct_chat_settings (chat_id, user_id, notify) values (chat, auth.uid(), level)
  on conflict (chat_id, user_id) do update set notify = excluded.notify;
end $$;

create or replace function public.mark_direct_read(chat uuid) returns void
language sql security definer set search_path = '' as $$
  insert into public.direct_chat_settings (chat_id, user_id, read_at)
  select chat, auth.uid(), now() where private.in_direct(chat, auth.uid())
  on conflict (chat_id, user_id) do update set read_at = now();
$$;

-- Bloquer / débloquer quelqu'un (la personne bloquée n'en est pas prévenue).
create or replace function public.set_direct_block(target uuid, blocked boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if target is null or target = auth.uid() then raise exception 'Choisis une autre personne' using errcode = '22023'; end if;
  if blocked then
    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
  else
    delete from public.direct_blocks where user_id = auth.uid() and blocked_id = target;
  end if;
end $$;

-- Personnes d'une conversation directe : surnom et photo des deux personnes, pour elles seules.
create or replace function public.direct_chat_people(chat uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'display_name', p.display_name, 'avatar_url', p.avatar_url, 'member', true)
         order by p.display_name), '[]'::jsonb)
  from public.direct_chats c join public.profiles p on p.id in (c.user_a, c.user_b)
  where c.id = chat and auth.uid() in (c.user_a, c.user_b);
$$;

-- Liste des discussions : mes groupes (tous pour Root) ET mes conversations directes qui ont au moins un message,
-- triés par dernier message. Une conversation directe : nom et photo de l'autre personne, kind = 'direct'.
create or replace function public.my_chats() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(c order by (c->>'last_at') desc nulls last, c->>'name'), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', g.id, 'name', g.name, 'kind', 'group', 'system', g.system_key is not null,
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
    union all
    select jsonb_build_object(
      'id', d.id, 'name', coalesce(nullif(btrim(o.display_name), ''), 'Profil à compléter'), 'kind', 'direct', 'system', false,
      'user_id', o.id, 'avatar_url', o.avatar_url,
      'member', true, 'admin', false, 'creator', false, 'members', 2,
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = o.id),
      'notify', coalesce(s.notify, 'all'),
      'last_at', last.created_at,
      'last', case when last.deleted_at is not null then 'Message supprimé'
                   else case when last.user_id = auth.uid() then 'Toi : ' else '' end
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.direct_messages m where m.chat_id = d.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.direct_chats d
    join public.profiles o on o.id = case when d.user_a = auth.uid() then d.user_b else d.user_a end
    left join public.direct_chat_settings s on s.chat_id = d.id and s.user_id = auth.uid()
    join lateral (select * from public.direct_messages m where m.chat_id = d.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)
  ) x;
$$;

revoke all on function public.start_direct_chat(uuid, text), public.delete_direct_message(uuid), public.edit_direct_message(uuid, text),
  public.pin_direct_message(uuid, boolean), public.set_direct_chat_notify(uuid, text), public.mark_direct_read(uuid),
  public.set_direct_block(uuid, boolean), public.direct_chat_people(uuid), public.my_chats() from public, anon;
grant execute on function public.start_direct_chat(uuid, text), public.delete_direct_message(uuid), public.edit_direct_message(uuid, text),
  public.pin_direct_message(uuid, boolean), public.set_direct_chat_notify(uuid, text), public.mark_direct_read(uuid),
  public.set_direct_block(uuid, boolean), public.direct_chat_people(uuid), public.my_chats() to authenticated;

-- Photos et vocaux (compartiment chat-photos, dossier = conversation) : ses deux personnes seulement.
drop policy if exists "envoyer une photo en message direct" on storage.objects;
create policy "envoyer une photo en message direct" on storage.objects for insert to authenticated
  with check (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
              and private.in_direct(((storage.foldername(name))[1])::uuid, (select auth.uid())));
drop policy if exists "voir les photos de mes messages directs" on storage.objects;
create policy "voir les photos de mes messages directs" on storage.objects for select to authenticated
  using (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and private.in_direct(((storage.foldername(name))[1])::uuid, (select auth.uid())));

-- Au-delà de 90 jours, photos et vocaux ne sont plus montrés (groupes et messages directs).
create or replace function private.expire_chat_photos() returns integer
language sql security definer set search_path = '' as $$
  with gone as (update public.group_messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1),
       gone_direct as (update public.direct_messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1)
  select ((select count(*) from gone) + (select count(*) from gone_direct))::int;
$$;

-- Temps réel (les règles de lecture ci-dessus s'appliquent aussi au temps réel).
do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'direct_messages') then
    alter publication supabase_realtime add table public.direct_messages;
  end if;
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'direct_message_reactions') then
    alter publication supabase_realtime add table public.direct_message_reactions;
  end if;
end $$;

-- Notifications ----------------------------------------------------------------------------------------------------------

-- Reçues aussi par les comptes Guest actifs (comme les Discussions de groupe).
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message')
        and private.is_account_active(uid));
$$;
revoke all on function private.may_receive_push(uuid, text) from public, anon;

-- Pause des Discussions : aussi pour les messages directs.
create or replace function private.push_paused(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select not private.push_pause_exempt(kind) and exists (
    select 1 from public.notification_prefs p where p.user_id = uid
      and (p.muted_until > now()
        or (kind in ('group_message', 'direct_message') and p.chats_muted_until > now())
        or (kind = 'message' and p.event_chats_muted_until > now())));
$$;
revoke all on function private.push_paused(uuid, text) from public, anon, authenticated;

-- Une seule règle pour tous les canaux (iPhone APNs, Expo, Web Push) : + direct_message → notification_prefs.direct_messages.
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
    when 'direct_message' then coalesce(prefs.direct_messages, true)
    else true end;
end $function$;
