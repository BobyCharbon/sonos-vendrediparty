-- Discussion d'un événement façon WhatsApp (demande de l'admin du 16.11.2026) : écran natif dans l'app iPhone, page web
-- revue. Purement additive et rejouable.
--  1. Photos et messages vocaux (comme les Discussions de groupe) : photo_path / audio_path dans le dossier de l'événement
--     du stockage chat-photos (« <événement>/… ») ; un message peut n'être qu'une photo ou un vocal.
--  2. @toutlemonde (invités et participants) et @present (Présent ou Peut-être) : réservés à l'organisation de
--     l'événement (organisateur, co-organisateurs) et aux admins et co-admins (events.manage_all). D'un autre, le mot
--     reste dans le texte mais ne prévient personne. La base décide d'après le texte : l'app ne peut pas tricher.
--  3. Annonces : « @annonce » ou l'interrupteur 📣 de l'organisation ; épinglée d'office, en tête de la discussion,
--     notifiée à tous (invités et participants). Épingler / désépingler : l'organisation, comme avant.
--  4. Notifications : citée (@surnom, @toutlemonde, @present, annonce, réponse) même en mode « Mentions » ; titre
--     « 📣 … » pour une annonce ; « 📷 Photo » / « 🎤 Message vocal » à la place d'un texte vide. Muet (event_mutes) : rien.
--  5. event_chat_people(e) : les personnes que l'on peut citer, avec leur réponse ; les invités sans réponse seulement
--     pour l'organisation (un invité ne voit jamais les noms de la liste des invités, règle du 11.11).
--  6. event_chat_state(e) : titre, droits (lire, écrire, organisation), discussion coupée pour moi.

-- 1. -----------------------------------------------------------------------------------------------------------------
alter table public.messages add column if not exists photo_path text;
alter table public.messages add column if not exists audio_path text;
alter table public.messages add column if not exists audio_seconds numeric;
alter table public.messages add column if not exists mention_all boolean not null default false;
alter table public.messages add column if not exists mention_present boolean not null default false;
alter table public.messages add column if not exists announcement boolean not null default false;
alter table public.messages drop constraint if exists messages_body_check;
alter table public.messages drop constraint if exists messages_content;
alter table public.messages add constraint messages_content check (
  length(body) <= 4000
  and (length(body) >= 1 or photo_path is not null or audio_path is not null)
  and (audio_seconds is null or audio_seconds between 0 and 600));
create index if not exists messages_pinned on public.messages (event_id, created_at desc) where pinned and deleted_at is null;

create or replace function private.event_chat_staff(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_admin() or public.is_organizer(e);
$$;
revoke all on function private.event_chat_staff(uuid) from public, anon;
grant execute on function private.event_chat_staff(uuid) to authenticated;

-- Écrire dans la discussion (photo, vocal) : mêmes conditions que la règle « écrire message ».
create or replace function private.event_chat_writes(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.can_participate(e) and public.has_perm('chat.write')
         and coalesce((select ev.forum_enabled from public.events ev where ev.id = e), false);
$$;
revoke all on function private.event_chat_writes(uuid) from public, anon;
grant execute on function private.event_chat_writes(uuid) to authenticated;

drop policy if exists "envoyer une photo dans un événement" on storage.objects;
create policy "envoyer une photo dans un événement" on storage.objects for insert to authenticated
  with check (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
              and private.event_chat_writes(((storage.foldername(name))[1])::uuid));
drop policy if exists "voir les photos d'un événement" on storage.objects;
create policy "voir les photos d'un événement" on storage.objects for select to authenticated
  using (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and public.can_see_event(((storage.foldername(name))[1])::uuid));

-- 2. et 3. ------------------------------------------------------------------------------------------------------------
create or replace function private.guard_message_change()
 returns trigger
 language plpgsql
 security definer
 set search_path to ''
as $function$
declare staff boolean;
begin
  if auth.uid() is null then return new; end if;
  staff := private.event_chat_staff(coalesce(old.event_id, new.event_id));
  if tg_op = 'INSERT' then
    if new.photo_path is not null and split_part(new.photo_path, '/', 1) <> new.event_id::text then
      raise exception 'Photo invalide.' using errcode = '22023';
    end if;
    if new.audio_path is not null and split_part(new.audio_path, '/', 1) <> new.event_id::text then
      raise exception 'Message vocal invalide.' using errcode = '22023';
    end if;
    if staff then
      -- Mot entier, sans casse ; l'interrupteur 📣 de l'app vaut « @annonce ».
      new.announcement := coalesce(new.announcement, false) or new.body ~* '(^|[^[:alnum:]_])@annonce([^[:alnum:]_]|$)';
      new.mention_all := new.body ~* '(^|[^[:alnum:]_])@toutlemonde([^[:alnum:]_]|$)';
      new.mention_present := new.body ~* '(^|[^[:alnum:]_])@pr[eé]sents?([^[:alnum:]_]|$)';
      if new.announcement then new.pinned := true; end if;
    else
      new.pinned := false; new.announcement := false; new.mention_all := false; new.mention_present := false;
    end if;
    return new;
  end if;
  new.event_id := old.event_id; new.user_id := old.user_id; new.created_at := old.created_at;
  new.photo_path := old.photo_path; new.audio_path := old.audio_path; new.audio_seconds := old.audio_seconds;
  new.mention_all := old.mention_all; new.mention_present := old.mention_present; new.announcement := old.announcement;
  if old.deleted_at is not null then
    -- Supprimé : le reste, sans texte.
    new.deleted_at := old.deleted_at; new.body := old.body; new.mentions := old.mentions; new.reply_to := old.reply_to;
    new.edited_at := old.edited_at; new.pinned := false;
    return new;
  end if;
  if new.deleted_at is not null then
    -- Supprimer efface le texte, la photo et le vocal pour de bon (plus lisibles par l'API).
    new.body := '•'; new.mentions := '{}'; new.pinned := false; new.photo_path := null; new.audio_path := null; new.audio_seconds := null;
    return new;
  end if;
  if auth.uid() is distinct from old.user_id
     and (new.body is distinct from old.body or new.mentions is distinct from old.mentions
          or new.reply_to is distinct from old.reply_to or new.edited_at is distinct from old.edited_at) then
    raise exception 'Seul l''auteur peut modifier son message.' using errcode = '42501';
  end if;
  if new.pinned is distinct from old.pinned and not staff then
    raise exception 'Épingler un message est réservé à l''organisation de l''événement.' using errcode = '42501';
  end if;
  return new;
end $function$;

-- 4. -----------------------------------------------------------------------------------------------------------------
create or replace function public.notify_message()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare ev events; who text; reply_author uuid; u uuid; np notification_prefs; cited boolean; title text; said text;
begin
  select * into ev from events where id = new.event_id;
  select display_name into who from profiles where id = new.user_id;
  select user_id into reply_author from messages where id = new.reply_to;
  said := btrim(regexp_replace(coalesce(new.body, ''), '(^|\s)@annonce\M', '\1', 'gi'));
  if said = '' then said := case when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end; end if;
  title := case when new.announcement then '📣 Annonce · ' || ev.title else ev.title end;
  for u in select distinct x from (
      select a x from event_audience(ev.id) a
      union select user_id from messages where event_id = ev.id
      union select unnest(new.mentions)
      -- @toutlemonde et annonce : aussi les invités qui n'ont pas encore répondu.
      union select user_id from event_invites where event_id = ev.id and (new.mention_all or new.announcement)
    ) s
    where x not in (select user_id from event_mutes where event_id = ev.id)
      and exists(select 1 from profiles p where p.id=x and private.is_member(p.id) and (
        private.user_has(p.id, 'events.manage_all') or ev.created_by=x
        or exists(select 1 from event_organizers where event_id=ev.id and user_id=x)
        or (ev.status in ('published','cancelled') and (ev.visibility='all'
          or exists(select 1 from event_invites where event_id=ev.id and user_id=x))))) loop
    cited := u = any (new.mentions) or u = reply_author or new.mention_all or new.announcement
      or (new.mention_present and exists (select 1 from rsvps r where r.event_id = ev.id and r.user_id = u and r.status in ('yes', 'maybe')));
    select * into np from notification_prefs where user_id = u;
    if np.chat = 'all' or (np.chat = 'mentions' and cited) then
      perform queue_notification(u, 'message', ev.id, title, who || ' : ' || left(said, 140), null,
        jsonb_build_object('mentioned', cited, 'message_id', new.id, 'chat', true));
    end if;
  end loop;
  return null;
end $function$;

-- 5. -----------------------------------------------------------------------------------------------------------------
create or replace function public.event_chat_people(e uuid)
returns table (id uuid, display_name text, avatar_url text, rsvp text, organizer boolean, invited boolean)
language plpgsql stable security definer set search_path = '' as $$
declare staff boolean;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'Cette discussion n''est pas accessible.' using errcode = '42501';
  end if;
  staff := private.event_chat_staff(e);
  return query
    with people as (
      select ev.created_by u from public.events ev where ev.id = e
      union select o.user_id from public.event_organizers o where o.event_id = e
      union select r.user_id from public.rsvps r where r.event_id = e
      union select m.user_id from public.messages m where m.event_id = e
      union select dv.user_id from public.date_votes dv join public.date_options d on d.id = dv.option_id where d.event_id = e
      union select i.user_id from public.event_invites i where i.event_id = e and staff
    )
    select p.id, p.display_name, p.avatar_url,
           (select r.status::text from public.rsvps r where r.event_id = e and r.user_id = p.id),
           p.id = (select ev.created_by from public.events ev where ev.id = e)
             or exists (select 1 from public.event_organizers o where o.event_id = e and o.user_id = p.id),
           exists (select 1 from public.event_invites i where i.event_id = e and i.user_id = p.id) and staff
    from people x join public.profiles p on p.id = x.u
    where p.status = 'active' and coalesce(p.display_name, '') <> '';
end $$;
revoke all on function public.event_chat_people(uuid) from public, anon;
grant execute on function public.event_chat_people(uuid) to authenticated;

-- 6. -----------------------------------------------------------------------------------------------------------------
create or replace function public.event_chat_state(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'Cette discussion n''est pas accessible.' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  return jsonb_build_object(
    'title', ev.title, 'forum', ev.forum_enabled, 'status', ev.status,
    'write', private.event_chat_writes(e), 'staff', private.event_chat_staff(e),
    'moderate', public.has_perm('chat.moderate'),
    'muted', exists (select 1 from public.event_mutes m where m.event_id = e and m.user_id = auth.uid()));
end $$;
revoke all on function public.event_chat_state(uuid) from public, anon;
grant execute on function public.event_chat_state(uuid) to authenticated;

notify pgrst, 'reload schema';
