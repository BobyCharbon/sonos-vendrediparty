-- PROD, discussions_v2 (20261118120000) : migration supabase/migrations/20261118120000_discussions_v2.sql telle quelle (mise en prod du 19.11).
-- Additive et rejouable. Tout ou rien.
begin;
-- Discussions v2 (contrat du 18.11.2026, revue de conformité du même jour, partie C) : la base de « Nouveau message »,
-- des demandes de message, de la liste unifiée et des groupes privés. Purement additive et rejouable ; les anciennes
-- fonctions (my_chats, start_direct_chat…) gardent leur signature pour les vieilles apps (Discussions allumées en prod).
--
--  1. Qui peut écrire à qui : private.dm_link(me, target) → 'direct' | 'request' | 'none' ; public.chat_link(target).
--     Direct : conversation déjà acceptée, groupe en commun HORS Membres Vendredi Party, événement NON public en commun
--     (« Sur invitation » non réservé au groupe Vendredi Party), organisateur ↔ personne qui a répondu à SON événement.
--     Demande : seulement Vendredi Party en commun, même événement public (ou réservé à Vendredi Party), contact du
--     répertoire, ou deux membres (rôle avec events.view) trouvés par la recherche. Un Guest sans aucun lien : impossible.
--     Impossible : blocage (un sens ou l'autre), compte inactif, mon profil incomplet ou CGU manquantes, la cible a réglé
--     « Demandes de message : personne », soi-même.
--  2. Demandes de message : direct_chats.status ('active' | 'request'), open_direct_chat, accept / decline, garde des
--     messages (un seul texte, sans photo, vocal, lien, numéro, carte ni citation), plafonds (10 / 24 h, 30 en attente),
--     purge pg_cron « chat-requests-tick », réglages chat_prefs, notification message_request (une seule, sans contenu).
--  3. Liste unifiée chat_list (groupes, messages directs, discussions d'événement), état par personne chat_list_state
--     (épinglée, archivée, non lu manuel, sourdine datée, lu des discussions d'événement), chat_badge.
--  4. Personnes : chat_people_suggestions, chat_people_search (jamais par numéro), member_mini (« Déjà vu », soirées).
--  5. Groupes privés (member_groups.private_chat) : Root ne les lit pas ; create_chat_group, chat_group_with.
--  6. Conversation : direct_seen, modification limitée à 15 minutes (edit_window), carte d'événement (event_id +
--     chat_event_cards), citation d'un message de groupe / d'événement (direct_messages.quote).
--  7. Devinette de numéro (🔴 3) : 20 empreintes ratées / 24 h au plus (private.contact_hash_fails), puis plus rien.

-- ───────────── Colonnes et tables ─────────────

alter table public.direct_chats add column if not exists status text not null default 'active';
alter table public.direct_chats add column if not exists requested_by uuid references public.profiles(id) on delete set null;
alter table public.direct_chats add column if not exists requested_at timestamptz;
alter table public.direct_chats add column if not exists declined_at timestamptz;
alter table public.direct_chats drop constraint if exists direct_chats_status_check;
alter table public.direct_chats add constraint direct_chats_status_check check (status in ('active', 'request'));
create index if not exists direct_chats_requests on public.direct_chats (requested_by, requested_at) where requested_by is not null;

-- Carte d'événement : event_id (nul si l'événement est supprimé) + event_card (le message en avait une, pour que la
-- règle « un message a un contenu » tienne encore après la suppression de l'événement).
alter table public.direct_messages add column if not exists event_id uuid references public.events(id) on delete set null;
alter table public.direct_messages add column if not exists event_card boolean not null default false;
alter table public.direct_messages add column if not exists quote jsonb;
alter table public.group_messages add column if not exists event_id uuid references public.events(id) on delete set null;
alter table public.group_messages add column if not exists event_card boolean not null default false;
alter table public.direct_messages drop constraint if exists direct_messages_content;
alter table public.direct_messages add constraint direct_messages_content
  check (btrim(body) <> '' or photo_path is not null or audio_path is not null or event_card or deleted_at is not null);
alter table public.group_messages drop constraint if exists group_messages_content;
alter table public.group_messages add constraint group_messages_content
  check (btrim(body) <> '' or photo_path is not null or audio_path is not null or event_card or deleted_at is not null);

alter table public.member_groups add column if not exists private_chat boolean not null default false;

alter table public.notification_prefs add column if not exists message_requests boolean not null default true;

create table if not exists public.chat_prefs (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  message_requests text not null default 'all' check (message_requests in ('all', 'none')),
  read_receipts boolean not null default true,
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_list_state (
  user_id uuid not null references public.profiles(id) on delete cascade,
  kind text not null check (kind in ('direct', 'group', 'event')),
  chat_id uuid not null,
  pinned_at timestamptz,
  archived_at timestamptz,
  marked_unread boolean not null default false,
  muted_until timestamptz,
  read_at timestamptz,  -- discussions d'événement seulement (groupes et directs : *_chat_settings.read_at)
  primary key (user_id, kind, chat_id)
);

create table if not exists private.contact_hash_fails (
  user_id uuid not null references public.profiles(id) on delete cascade,
  at timestamptz not null default now()
);
create index if not exists contact_hash_fails_by_user on private.contact_hash_fails (user_id, at);

alter table public.chat_prefs enable row level security;
alter table public.chat_list_state enable row level security;
drop policy if exists "mes réglages de discussions" on public.chat_prefs;
create policy "mes réglages de discussions" on public.chat_prefs for select to authenticated
  using (user_id = (select auth.uid()));
drop policy if exists "mon état de la liste" on public.chat_list_state;
create policy "mon état de la liste" on public.chat_list_state for select to authenticated
  using (user_id = (select auth.uid()));
revoke all on public.chat_prefs, public.chat_list_state from anon;
grant select on public.chat_prefs, public.chat_list_state to authenticated;

-- ───────────── Petits outils ─────────────

-- Minuscules sans accents (recherche de personnes ; pas d'extension unaccent sur la base).
create or replace function private.fold(t text) returns text
language sql immutable set search_path = '' as $$
  select translate(lower(coalesce(t, '')), 'àáâãäåçèéêëìíîïñòóôõöùúûüýÿœæ', 'aaaaaaceeeeiiiinooooouuuuyyoa');
$$;

-- Nom montré d'une personne : prénom et nom si elle les montre (ou si je peux voir les identités), sinon son surnom.
create or replace function private.chat_name(uid uuid) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce(case when private.shows_name(p.id) or public.has_perm('members.view_identity')
                       then nullif(btrim(concat_ws(' ', nullif(btrim(p.first_name), ''), nullif(btrim(p.last_name), ''))), '') end,
                  nullif(btrim(p.display_name), ''), 'Profil à compléter')
  from public.profiles p where p.id = uid;
$$;

create or replace function private.chat_msg_type(deleted boolean, photo text, audio text, card boolean) returns text
language sql immutable set search_path = '' as $$
  select case when deleted then 'deleted' when photo is not null then 'photo' when audio is not null then 'audio'
              when coalesce(card, false) then 'event' else 'text' end;
$$;

-- Texte interdit dans une demande : lien (http, www) ou numéro de téléphone (7 chiffres ou plus, séparateurs compris).
create or replace function private.request_text_refused(body text) returns boolean
language sql immutable set search_path = '' as $$
  select coalesce(body, '') ~* '(https?://|www\.)'
      or regexp_replace(coalesce(body, ''), '[[:space:].()/+-]', '', 'g') ~ '[0-9]{7}';
$$;

-- L'organisation d'un événement (ou un admin des événements) voit tout de ses invités.
create or replace function private.chat_manages(ev public.events, viewer uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select viewer is not null and (viewer = ev.created_by
    or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = viewer)
    or private.user_has(viewer, 'events.manage_all'));
$$;

-- Place de uid dans l'événement, telle que viewer peut la voir : 'organizer' | 'yes' | 'maybe' | 'no' | 'invited' | null.
-- Réponse d'un autre : seulement si la liste des participants est montrée ou si viewer organise ; « invité » : viewer
-- organise (un invité ne voit jamais la liste des invités, règle du 11.11).
create or replace function private.chat_role(ev public.events, uid uuid, viewer uuid) returns text
language sql stable security definer set search_path = '' as $$
  select case
    when uid = ev.created_by or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = uid)
      then 'organizer'
    when uid = viewer or ev.show_participants or private.chat_manages(ev, viewer) then
      coalesce((select r.status::text from public.rsvps r where r.event_id = ev.id and r.user_id = uid),
               case when (uid = viewer or private.chat_manages(ev, viewer))
                         and exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = uid)
                    then 'invited' end)
  end;
$$;

-- « Déjà vu » : soirées PASSÉES (fin, sinon début + 4 h) où nous étions tous les deux présents (« Présent », organisation,
-- ou billet scanné), que je peux voir ; les plus récentes d'abord. me = la personne connectée (can_see_event).
create or replace function private.met_events(me uuid, other uuid)
returns table (id uuid, title text, starts_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select ev.id, ev.title, ev.starts_at from public.events ev
  where ev.id in (select private.dm_events_of(me)) and ev.id in (select private.dm_events_of(other))
    and ev.status = 'published' and ev.starts_at is not null
    and coalesce(ev.ends_at, ev.starts_at + interval '4 hours') < now()
    and public.can_see_event(ev.id)
    and (private.chat_role(ev, me, me) in ('organizer', 'yes')
         or exists (select 1 from public.event_tickets t where t.event_id = ev.id and t.user_id = me and t.checked_in_at is not null))
    and (private.chat_role(ev, other, me) in ('organizer', 'yes')
         or (private.chat_manages(ev, me)
             and exists (select 1 from public.event_tickets t where t.event_id = ev.id and t.user_id = other and t.checked_in_at is not null)))
  order by ev.starts_at desc;
$$;

-- ───────────── 1. Qui peut écrire à qui ─────────────

-- {"link": "direct"|"request"|"none", "reason": null|"blocked"|"inactive"|"profile_required"|"terms_required"|"closed"}.
-- contact : le numéro de target est dans MES contacts (empreinte vérifiée par open_direct_chat).
create or replace function private.dm_check(me uuid, target uuid, contact boolean default false) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare vp uuid := private.vip_group_id();
begin
  if me is null or target is null or me = target then return jsonb_build_object('link', 'none', 'reason', null); end if;
  if not private.is_account_active(me) or not private.is_account_active(target) then
    return jsonb_build_object('link', 'none', 'reason', 'inactive');
  end if;
  if private.blocked_either(me, target) then return jsonb_build_object('link', 'none', 'reason', 'blocked'); end if;
  if not private.identity_complete(me) then return jsonb_build_object('link', 'none', 'reason', 'profile_required'); end if;
  if coalesce((select s.terms_enforced from private.moderation_settings s where s.id = 1), false) and not private.terms_accepted(me) then
    return jsonb_build_object('link', 'none', 'reason', 'terms_required');
  end if;
  if exists (select 1 from public.direct_chats c where c.user_a = least(me, target) and c.user_b = greatest(me, target)
             and c.status = 'active')
     or exists (select 1 from public.member_group_members a join public.member_group_members b on b.group_id = a.group_id
                where a.user_id = me and b.user_id = target and a.group_id is distinct from vp)
     or exists (select 1 from public.events ev
                where ev.visibility = 'invited' and ev.status in ('published', 'cancelled')
                  and not exists (select 1 from public.event_groups eg where eg.event_id = ev.id and eg.group_id = vp)
                  and ev.id in (select private.dm_events_of(me)) and ev.id in (select private.dm_events_of(target)))
     or exists (select 1 from public.rsvps r join public.events ev on ev.id = r.event_id
                where (r.user_id = target and (ev.created_by = me
                         or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = me)))
                   or (r.user_id = me and (ev.created_by = target
                         or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = target)))) then
    return jsonb_build_object('link', 'direct', 'reason', null);
  end if;
  if coalesce((select p.message_requests from public.chat_prefs p where p.user_id = target), 'all') = 'none'
     or not private.identity_complete(target) then
    return jsonb_build_object('link', 'none', 'reason', 'closed');
  end if;
  if coalesce(contact, false)
     or (vp is not null and private.in_group_now(vp, me) and private.in_group_now(vp, target))
     or exists (select 1 from public.events ev
                where (ev.visibility = 'all' or exists (select 1 from public.event_groups eg where eg.event_id = ev.id and eg.group_id = vp))
                  and ev.status in ('published', 'cancelled')
                  and ev.id in (select private.dm_events_of(me)) and ev.id in (select private.dm_events_of(target)))
     or (private.is_member(me) and private.is_member(target)) then
    return jsonb_build_object('link', 'request', 'reason', null);
  end if;
  return jsonb_build_object('link', 'none', 'reason', null);
end $$;

create or replace function private.dm_link(me uuid, target uuid) returns text
language sql stable security definer set search_path = '' as $$
  select private.dm_check(me, target, false) ->> 'link';
$$;

create or replace function public.chat_link(target uuid) returns text
language sql stable security definer set search_path = '' as $$
  select private.dm_link(auth.uid(), target);
$$;

-- ───────────── 2. Demandes de message ─────────────

create or replace function public.open_direct_chat(target uuid, contact_hash text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); a uuid; b uuid; c public.direct_chats; chk jsonb; contact_ok boolean := false; reason text;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if target is null or target = me then raise exception 'invalid: Choisis une autre personne' using errcode = '22023'; end if;
  a := least(me, target); b := greatest(me, target);
  select * into c from public.direct_chats d where d.user_a = a and d.user_b = b;
  if c.id is not null then
    -- Demande encore vide (rien d'envoyé, pas refusée) et un vrai lien est apparu : elle devient une conversation.
    if c.status = 'request' and c.declined_at is null and private.dm_link(me, target) = 'direct'
       and not exists (select 1 from public.direct_messages m where m.chat_id = c.id) then
      update public.direct_chats set status = 'active' where id = c.id returning * into c;
    end if;
    reason := case when private.blocked_either(me, target) then 'blocked'
                   when not private.is_account_active(target) then 'inactive' end;
    return jsonb_build_object('chat', c.id, 'status', c.status, 'reason', reason);
  end if;
  -- Empreinte d'un numéro de mes contacts : 20 ratées par 24 h au plus, puis plus aucune n'est essayée (même réponse).
  if nullif(btrim(coalesce(contact_hash, '')), '') is not null
     and (select count(*) from private.contact_hash_fails f where f.user_id = me and f.at > now() - interval '24 hours') < 20 then
    contact_ok := contact_hash ~ '^[0-9a-f]{64}$' and exists (
      select 1 from public.profiles p, private.contact_key k
      where p.id = target and k.id = 1 and p.phone ~ '^[1-9][0-9]{7,14}$'
        and encode(extensions.hmac('+' || p.phone, k.key, 'sha256'), 'hex') = contact_hash);
    if not contact_ok then insert into private.contact_hash_fails (user_id) values (me); end if;
  end if;
  chk := private.dm_check(me, target, contact_ok);
  if chk ->> 'link' = 'none' then
    return jsonb_build_object('chat', null, 'status', 'none', 'reason', chk ->> 'reason');
  end if;
  if chk ->> 'link' = 'request' then
    if (select count(*) from public.direct_chats d where d.requested_by = me and d.requested_at > now() - interval '24 hours') >= 10
       or (select count(*) from public.direct_chats d where d.requested_by = me and d.status = 'request') >= 30 then
      return jsonb_build_object('chat', null, 'status', 'none', 'reason', 'limit');
    end if;
    insert into public.direct_chats (user_a, user_b, created_by, status, requested_by, requested_at)
    values (a, b, me, 'request', me, now())
    on conflict (user_a, user_b) do nothing returning * into c;
  else
    insert into public.direct_chats (user_a, user_b, created_by) values (a, b, me)
    on conflict (user_a, user_b) do nothing returning * into c;
  end if;
  if c.id is null then select * into c from public.direct_chats d where d.user_a = a and d.user_b = b; end if;
  return jsonb_build_object('chat', c.id, 'status', c.status, 'reason', null);
end $$;

-- Vieilles apps : même signature. Une conversation existante s'ouvre toujours ; sinon les règles de open_direct_chat
-- (demande comprise). Refus : la même erreur qu'avant, SAUF avec une empreinte de contact : null (l'essai raté doit rester
-- compté, une erreur l'annulerait ; le serveur traite null comme un refus).
create or replace function public.start_direct_chat(target uuid, contact_hash text default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare r jsonb;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if target is null or target = auth.uid() then raise exception 'Choisis une autre personne' using errcode = '22023'; end if;
  r := public.open_direct_chat(target, contact_hash);
  if r ->> 'chat' is not null then return (r ->> 'chat')::uuid; end if;
  if nullif(btrim(coalesce(contact_hash, '')), '') is not null then return null; end if;
  if r ->> 'reason' = 'limit' then
    raise exception 'limit: Tu as envoyé beaucoup de demandes de message, réessaie plus tard.' using errcode = '54000';
  end if;
  raise exception 'forbidden: tu ne peux pas écrire à cette personne' using errcode = '42501';
end $$;

create or replace function public.accept_message_request(chat uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.direct_chats d set status = 'active', declined_at = null
   where d.id = chat and d.status = 'request' and auth.uid() in (d.user_a, d.user_b) and d.requested_by is distinct from auth.uid();
  if not found then raise exception 'forbidden: demande introuvable' using errcode = '42501'; end if;
end $$;

-- Refuser : la demande disparaît chez moi, son message est effacé aussitôt ; l'expéditeur n'en sait rien.
create or replace function public.decline_message_request(chat uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.direct_chats d set declined_at = coalesce(d.declined_at, now())
   where d.id = chat and d.status = 'request' and auth.uid() in (d.user_a, d.user_b) and d.requested_by is distinct from auth.uid();
  if not found then raise exception 'forbidden: demande introuvable' using errcode = '42501'; end if;
  delete from public.direct_messages where chat_id = chat;
  delete from public.notifications where user_id = auth.uid() and kind = 'message_request' and data ->> 'chat_id' = chat::text;
end $$;

-- Messages d'une demande et contenu d'un message (après guard_direct_message, qui fixe l'auteur) : un seul message,
-- de l'expéditeur, texte seul ; carte d'événement seulement si l'auteur le voit ; citation nettoyée et filtrée.
create or replace function private.clean_quote(q jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare src text; ex text;
begin
  if q is null or jsonb_typeof(q) <> 'object' then return null; end if;
  src := q ->> 'from';
  if src is null or src not in ('group', 'event') then return null; end if;
  ex := left(btrim(coalesce(q ->> 'excerpt', '')), 140);
  if ex = '' then return null; end if;
  return jsonb_build_object('from', src,
    'title', nullif(private.moderate_text(left(btrim(coalesce(q ->> 'title', '')), 80), 'message'), ''),
    'author', nullif(private.moderate_text(left(btrim(coalesce(q ->> 'author', '')), 60), 'message'), ''),
    'excerpt', private.moderate_text(ex, 'message'));
end $$;

create or replace function private.guard_direct_message_v2() returns trigger
language plpgsql security definer set search_path = '' as $$
declare c public.direct_chats;
begin
  if tg_op = 'UPDATE' then
    -- Ni carte ni citation changées après l'envoi ; supprimer le message les retire (l'événement supprimé : event_id nul).
    if new.deleted_at is not null or new.event_id is null then new.event_id := null; else new.event_id := old.event_id; end if;
    new.event_card := old.event_card;
    new.quote := case when new.deleted_at is null then old.quote end;
    return new;
  end if;
  if new.event_id is not null and auth.uid() is not null and not public.can_see_event(new.event_id) then
    new.event_id := null;
  end if;
  new.event_card := new.event_id is not null;
  new.quote := private.clean_quote(new.quote);
  select * into c from public.direct_chats d where d.id = new.chat_id;
  if c.status = 'request' then
    select * into c from public.direct_chats d where d.id = new.chat_id for update;  -- deux envois en même temps : un seul passe
    if new.user_id is distinct from c.requested_by or c.declined_at is not null
       or exists (select 1 from public.direct_messages m where m.chat_id = c.id) then
      raise exception 'request_pending: En attente de sa réponse : tu pourras écrire quand ta demande sera acceptée.' using errcode = '42501';
    end if;
    if new.photo_path is not null or new.audio_path is not null or new.event_card or new.quote is not null
       or new.reply_to is not null or btrim(coalesce(new.body, '')) = '' or private.request_text_refused(new.body) then
      raise exception 'request_pending: Une demande de message est un seul texte, sans photo, vocal, lien ni numéro.' using errcode = '42501';
    end if;
  end if;
  return new;
end $$;
drop trigger if exists direct_messages_request on public.direct_messages;
create trigger direct_messages_request before insert or update on public.direct_messages
  for each row execute function private.guard_direct_message_v2();

create or replace function private.guard_group_message_v2() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' then
    if new.deleted_at is not null or new.event_id is null then new.event_id := null; else new.event_id := old.event_id; end if;
    new.event_card := old.event_card;
    return new;
  end if;
  if new.event_id is not null and auth.uid() is not null and not public.can_see_event(new.event_id) then
    new.event_id := null;
  end if;
  new.event_card := new.event_id is not null;
  return new;
end $$;
drop trigger if exists group_messages_card on public.group_messages;
create trigger group_messages_card before insert or update on public.group_messages
  for each row execute function private.guard_group_message_v2();

-- « Nouveau message de X » : jamais pour un message de demande (celui-là prévient par message_request).
create or replace function private.notify_direct_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare other uuid; who text; preview text;
begin
  other := private.direct_other(new.chat_id, new.user_id);
  if other is null or exists (select 1 from public.direct_chat_settings s
                              where s.chat_id = new.chat_id and s.user_id = other and s.notify = 'none') then
    return null;
  end if;
  if exists (select 1 from public.direct_chats c where c.id = new.chat_id and c.status = 'request') then return null; end if;
  select display_name into who from public.profiles where id = new.user_id;
  preview := case when new.body <> '' then left(new.body, 140) when new.audio_path is not null then '🎤 Message vocal'
                  when new.photo_path is null and new.event_card then '🎉 Soirée partagée' else '📷 Photo' end;
  insert into public.notifications (user_id, kind, event_id, title, body, data)
  values (other, 'direct_message', null, 'Nouveau message de ' || coalesce(nullif(btrim(who), ''), 'quelqu''un'), preview,
          jsonb_build_object('chat_id', new.chat_id, 'group_id', new.chat_id, 'direct', true, 'message_id', new.id,
                             'kind', 'direct_message'));
  return null;
end $$;

-- « 💬 X veut t'écrire », sans le contenu ; une seule par conversation (dedupe_key).
create or replace function private.notify_message_request() returns trigger
language plpgsql security definer set search_path = '' as $$
declare c public.direct_chats; other uuid; who text;
begin
  select * into c from public.direct_chats d where d.id = new.chat_id;
  if c.status is distinct from 'request' or new.user_id is distinct from c.requested_by then return null; end if;
  other := private.direct_other(new.chat_id, new.user_id);
  if other is null then return null; end if;
  select display_name into who from public.profiles where id = new.user_id;
  insert into public.notifications (user_id, kind, event_id, title, body, data, dedupe_key)
  values (other, 'message_request', null, '💬 ' || coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' veut t''écrire',
          'Demande de message : ouvre Discussions pour répondre.',
          jsonb_build_object('chat_id', c.id, 'kind', 'message_request', 'requests', true, 'url', '/?tab=chats&requests=1'),
          'message_request:' || c.id)
  on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing;
  return null;
end $$;
drop trigger if exists direct_messages_request_notify on public.direct_messages;
create trigger direct_messages_request_notify after insert on public.direct_messages
  for each row execute function private.notify_message_request();

-- Demande acceptée : les deux écrans relisent (signal sans contenu « user:<id> ») ; refusée : seulement celui qui refuse.
create or replace function private.direct_chat_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.status is distinct from old.status then
    perform private.party_signal('user:' || new.user_a);
    perform private.party_signal('user:' || new.user_b);
  elsif new.declined_at is distinct from old.declined_at and auth.uid() is not null then
    perform private.party_signal('user:' || auth.uid());
  end if;
  return null;
end $$;
drop trigger if exists direct_chats_changed on public.direct_chats;
create trigger direct_chats_changed after update of status, declined_at on public.direct_chats
  for each row execute function private.direct_chat_changed();

-- Purge (toutes les heures) : demande refusée → messages effacés ; demande de plus de 30 jours (refusée ou ignorée)
-- → conversation effacée ; essais d'empreinte de plus de 24 h ; état de liste d'une discussion disparue.
create or replace function private.chat_requests_tick() returns void
language plpgsql security definer set search_path = '' as $$
begin
  delete from public.direct_messages m using public.direct_chats c
   where m.chat_id = c.id and c.status = 'request' and c.declined_at is not null;
  delete from public.direct_chats c where c.status = 'request' and coalesce(c.requested_at, c.created_at) < now() - interval '30 days';
  delete from public.notifications n where n.kind = 'message_request'
     and not exists (select 1 from public.direct_chats c where c.id::text = n.data ->> 'chat_id' and c.status = 'request'
                     and c.declined_at is null);
  delete from private.contact_hash_fails where at < now() - interval '24 hours';
  delete from public.chat_list_state s
   where (s.kind = 'direct' and not exists (select 1 from public.direct_chats c where c.id = s.chat_id))
      or (s.kind = 'group' and not exists (select 1 from public.member_groups g where g.id = s.chat_id))
      or (s.kind = 'event' and not exists (select 1 from public.events e where e.id = s.chat_id));
end $$;
select cron.unschedule('chat-requests-tick') where exists (select 1 from cron.job where jobname = 'chat-requests-tick');
select cron.schedule('chat-requests-tick', '7 * * * *', 'select private.chat_requests_tick();');

-- Réglages des Discussions (Réglages › Confidentialité).
create or replace function public.chat_prefs_get() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('message_requests', coalesce(p.message_requests, 'all'), 'read_receipts', coalesce(p.read_receipts, true))
  from (select auth.uid() as uid) me left join public.chat_prefs p on p.user_id = me.uid
  where me.uid is not null;
$$;

create or replace function public.chat_prefs_set(message_requests text default null, read_receipts boolean default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
#variable_conflict use_variable
begin
  if auth.uid() is null then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if message_requests is not null and message_requests not in ('all', 'none') then
    raise exception 'invalid: Choix inconnu' using errcode = '22023';
  end if;
  insert into public.chat_prefs (user_id) values (auth.uid()) on conflict on constraint chat_prefs_pkey do nothing;
  update public.chat_prefs p set message_requests = coalesce(message_requests, p.message_requests),
                                 read_receipts = coalesce(read_receipts, p.read_receipts), updated_at = now()
   where p.user_id = auth.uid();
  return public.chat_prefs_get();
end $$;

-- Notifications : interrupteur, Guests, blocage, pause des Discussions, sourdine datée par conversation.
do $$ declare def text;
begin
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''message_request''' in def) = 0 then
    if position($a$    when 'direct_message' then coalesce(prefs.direct_messages, true)$a$ in def) = 0 then
      raise exception 'web_push_allowed : ancre direct_message introuvable';
    end if;
    def := replace(def, $a$    when 'direct_message' then coalesce(prefs.direct_messages, true)$a$,
      $a$    when 'direct_message' then coalesce(prefs.direct_messages, true)
    when 'message_request' then coalesce(prefs.message_requests, true)$a$);
  end if;
  if position('chat_list_state' in def) = 0 then
    if position($a$  return case notification.kind$a$ in def) = 0 then raise exception 'web_push_allowed : ancre return case introuvable'; end if;
    def := replace(def, $a$  return case notification.kind$a$,
      $a$  -- Sourdine datée d'une conversation (liste des Discussions : 1 h, 8 h, 1 semaine, toujours).
  if notification.kind in ('group_message', 'direct_message', 'message') and exists (
       select 1 from public.chat_list_state s where s.user_id = notification.user_id and s.muted_until > now()
         and s.chat_id::text in (notification.data ->> 'chat_id', notification.data ->> 'group_id', notification.event_id::text)) then
    return false;
  end if;
  return case notification.kind$a$);
  end if;
  execute def;

  def := pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure);
  if position('''message_request''' in def) = 0 then
    if position('''direct_message'',' in def) = 0 then raise exception 'may_receive_push : ancre direct_message introuvable'; end if;
    execute replace(def, '''direct_message'',', '''direct_message'', ''message_request'',');
  end if;

  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position('''message_request''' in def) = 0 then
    if position('''direct_message'',' in def) = 0 then raise exception 'drop_blocked_notification : ancre direct_message introuvable'; end if;
    execute replace(def, '''direct_message'',', '''direct_message'', ''message_request'',');
  end if;

  def := pg_get_functiondef('private.push_paused(uuid,text)'::regprocedure);
  if position('''message_request''' in def) = 0 then
    if position($a$kind in ('group_message', 'direct_message')$a$ in def) = 0 then raise exception 'push_paused : ancre introuvable'; end if;
    execute replace(def, $a$kind in ('group_message', 'direct_message')$a$, $a$kind in ('group_message', 'direct_message', 'message_request')$a$);
  end if;

  -- Groupes : aperçu « 🎉 Soirée partagée » pour une carte sans texte.
  def := pg_get_functiondef('private.notify_group_message()'::regprocedure);
  if position('Soirée partagée' in def) = 0 then
    if position($a$when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end$a$ in def) = 0 then
      raise exception 'notify_group_message : ancre aperçu introuvable';
    end if;
    execute replace(def, $a$when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end$a$,
      $a$when new.audio_path is not null then '🎤 Message vocal' when new.photo_path is null and new.event_card then '🎉 Soirée partagée' else '📷 Photo' end$a$);
  end if;

  -- Ancienne liste (vieilles apps) : Root ne voit plus les groupes privés ; une demande reçue n'y entre pas (ni refusée).
  def := pg_get_functiondef('public.my_chats()'::regprocedure);
  if position('private_chat' in def) = 0 then
    if position('or private.is_root(auth.uid()))' in def) = 0
       or position('where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)' in def) = 0 then
      raise exception 'my_chats : ancres introuvables';
    end if;
    def := replace(def, 'or private.is_root(auth.uid()))', 'or (private.is_root(auth.uid()) and not g.private_chat))');
    execute replace(def, 'where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)',
      'where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b) and (d.status = ''active'' or d.requested_by = auth.uid())');
  end if;
end $$;

-- ───────────── 5. Groupes privés ─────────────

-- private_chat ne se pose qu'à la création par create_chat_group (party.private_chat = 1) et ne change plus ensuite.
create or replace function private.group_private_chat_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'UPDATE' then
    new.private_chat := old.private_chat;
  else
    new.private_chat := new.system_key is null and coalesce(current_setting('party.private_chat', true), '') = '1';
  end if;
  return new;
end $$;
drop trigger if exists member_groups_private_chat on public.member_groups;
create trigger member_groups_private_chat before insert or update of private_chat on public.member_groups
  for each row execute function private.group_private_chat_guard();

create or replace function private.group_is_private(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select g.private_chat from public.member_groups g where g.id = grp), false);
$$;

-- Root ne lit que les vrais groupes NON privés (dont il ne fait pas partie).
create or replace function private.reads_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (private.in_group_now(grp, auth.uid())
    or (private.is_root(auth.uid()) and exists (select 1 from public.member_groups g where g.id = grp and not g.private_chat)));
$$;

create or replace function private.group_admin(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and (
    (private.is_root(uid) and not private.group_is_private(grp))
    or exists (select 1 from public.member_groups g where g.id = grp and g.created_by = uid)
    or (private.in_group_now(grp, uid) and (
          exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid)
          or private.rank_of(uid) >= private.role_rank('coadmin'))));  -- co-admins du site et au-dessus : admins d'office de leurs groupes
$$;

-- Photos et vocaux d'un ÉVÉNEMENT seulement : can_see_event() vaut vrai pour un admin quel que soit l'id, si bien que la
-- règle du 16.11 ouvrait aussi aux admins les dossiers des messages directs et des groupes (trouvé par
-- test_direct_messages_live, 18.11). Le dossier doit être celui d'un événement existant.
drop policy if exists "voir les photos d'un événement" on storage.objects;
create policy "voir les photos d'un événement" on storage.objects for select to authenticated
  using (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and exists (select 1 from public.events ev where ev.id = ((storage.foldername(name))[1])::uuid)
         and public.can_see_event(((storage.foldername(name))[1])::uuid));

-- Les admins qui voient tous les groupes ne voient pas les groupes privés (ni leurs membres).
drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using ((created_by = (select auth.uid())) or private.in_group(id, (select auth.uid()))
         or ((select private.sees_all_groups()) and not private_chat));
drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using ((user_id = (select auth.uid())) or private.in_group(group_id, (select auth.uid()))
         or private.created_group(group_id, (select auth.uid()))
         or ((select private.sees_all_groups()) and not private.group_is_private(group_id)));

create or replace function public.create_chat_group(name text, emoji text, color text, members uuid[]) returns jsonb
language plpgsql security definer set search_path = '' as $$
#variable_conflict use_variable
declare me uuid := auth.uid(); g public.member_groups; who text; m uuid; people uuid[]; invited int := 0; refused uuid[] := '{}';
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.identity_complete(me) then
    raise exception 'profile_required: Complète ton profil (prénom, nom, surnom) pour créer un groupe.' using errcode = '42501';
  end if;
  perform private.require_terms(me);
  select coalesce(array_agg(distinct u), '{}') into people from unnest(coalesce(members, '{}')) u where u is not null and u <> me;
  if cardinality(people) < 2 or cardinality(people) > 50 then
    raise exception 'invalid: Choisis entre 2 et 50 personnes.' using errcode = '22023';
  end if;
  if btrim(coalesce(name, '')) = '' then raise exception 'invalid: Donne un nom au groupe.' using errcode = '22023'; end if;
  perform set_config('party.private_chat', '1', true);
  begin
    insert into public.member_groups (name, emoji, color, created_by)
    values (left(btrim(name), 60), coalesce(emoji, '👯'),
            coalesce(color, (array['pink', 'coral', 'mint', 'sky', 'lavender', 'lemon'])[1 + floor(random() * 6)::int]), me)
    returning * into g;
  exception when check_violation then
    perform set_config('party.private_chat', '', true);
    if sqlerrm like 'content_refused%' then raise; end if;
    raise exception 'invalid: Emoji ou couleur inconnus.' using errcode = '22023';
  end;
  perform set_config('party.private_chat', '', true);
  select display_name into who from public.profiles where id = me;
  foreach m in array people loop
    if private.dm_link(me, m) = 'direct' then
      insert into private.group_invitations (group_id, user_id, invited_by) values (g.id, m, me) on conflict do nothing;
      perform public.queue_notification(m, 'group_invite', null, g.name,
        coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
        'group_invite:' || g.id || ':' || m);
      invited := invited + 1;
    else
      refused := refused || m;
    end if;
  end loop;
  return jsonb_build_object('group', g.id, 'invited', invited, 'refused', to_jsonb(refused));
end $$;

-- Un groupe (pas Vendredi Party) dont je fais partie avec EXACTEMENT ces personnes (membres + invitations en attente).
create or replace function public.chat_group_with(members uuid[]) returns uuid
language sql stable security definer set search_path = '' as $$
  with want as (select array_agg(distinct u order by u) a from unnest(coalesce(members, '{}') || auth.uid()) u where u is not null)
  select g.id from public.member_groups g, want
  where auth.uid() is not null and g.system_key is null and private.in_group_now(g.id, auth.uid())
    and (select array_agg(distinct x order by x) from (
           select mm.user_id x from public.member_group_members mm where mm.group_id = g.id
           union select i.user_id from private.group_invitations i
                 where i.group_id = g.id and i.status = 'pending' and i.user_id is not null) s) = want.a
  order by g.private_chat desc, g.created_at desc
  limit 1;
$$;

-- ───────────── 3. Liste unifiée ─────────────

create or replace function public.chat_list(include_archived boolean default false) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); my_rr boolean; out jsonb;
  -- Discussions d'événement jamais ouvertes depuis la liste : non lues seulement après la mise en service.
  since constant timestamptz := '2026-11-18 00:00:00+00';
begin
  if me is null then return '[]'::jsonb; end if;
  my_rr := coalesce((select p.read_receipts from public.chat_prefs p where p.user_id = me), true);
  with lst as (
    -- Groupes (Root : aussi les groupes non privés dont il ne fait pas partie, sans non lus).
    select g.id, st.pinned_at, st.archived_at, last.created_at as last_at, jsonb_build_object(
      'kind', 'group', 'id', g.id, 'title', g.name,
      'photo', case when g.system_key is null then g.photo_path end, 'emoji', g.emoji, 'color', g.color,
      'user_id', null, 'event_start', null, 'event_past', false,
      'last', case when last.id is null then null else jsonb_build_object(
        'id', last.id, 'at', last.created_at, 'from_me', last.user_id = me,
        'author', coalesce(nullif(btrim(a.display_name), ''), '?'),
        'type', private.chat_msg_type(last.deleted_at is not null, last.photo_path, last.audio_path, last.event_card),
        'text', case when last.deleted_at is not null then '' else left(last.body, 140) end) end,
      'unread', coalesce(un.n, 0), 'mention', coalesce(un.mention, false),
      'marked_unread', coalesce(st.marked_unread, false), 'pinned_at', st.pinned_at, 'archived', st.archived_at is not null,
      'notify', coalesce(s.notify, 'mentions'), 'muted_until', case when st.muted_until > now() then st.muted_until end,
      'request', null, 'seen_by_other', null,
      'members', (select count(*) from public.member_group_members mm where mm.group_id = g.id),
      'is_vp', g.system_key is not distinct from 'vip', 'blocked', false) as c
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = me
    left join public.chat_list_state st on st.user_id = me and st.kind = 'group' and st.chat_id = g.id
    left join lateral (select m.* from public.group_messages m where m.group_id = g.id and not private.blocked_either(me, m.user_id)
                       order by m.created_at desc limit 1) last on true
    left join public.profiles a on a.id = last.user_id
    left join lateral (select count(*) as n,
                              bool_or(me = any (m.mentions) or m.mention_all
                                      or exists (select 1 from public.group_messages r where r.id = m.reply_to and r.user_id = me)) as mention
                       from public.group_messages m
                       where m.group_id = g.id and m.user_id <> me and m.deleted_at is null and private.in_group_now(g.id, me)
                         and m.created_at > coalesce(s.read_at, '-infinity') and not private.blocked_either(me, m.user_id)) un on true
    where private.in_group_now(g.id, me) or (private.is_root(me) and not g.private_chat)

    union all
    -- Messages directs : avec au moins un message ; demande reçue (pas refusée, pas bloquée) ; demande envoyée (même
    -- refusée : l'expéditeur n'en sait rien, elle disparaît avec la purge des 30 jours).
    select d.id, st.pinned_at, st.archived_at, coalesce(last.created_at, d.requested_at), jsonb_build_object(
      'kind', 'direct', 'id', d.id, 'title', coalesce(nullif(btrim(o.display_name), ''), 'Profil à compléter'),
      'photo', o.avatar_url, 'emoji', null, 'color', null, 'user_id', o.id, 'event_start', null, 'event_past', false,
      'last', case when last.id is null then null else jsonb_build_object(
        'id', last.id, 'at', last.created_at, 'from_me', last.user_id = me,
        'author', coalesce(nullif(btrim(a.display_name), ''), '?'),
        'type', private.chat_msg_type(last.deleted_at is not null, last.photo_path, last.audio_path, last.event_card),
        'text', case when last.deleted_at is not null then '' else left(last.body, 140) end) end,
      'unread', (select count(*) from public.direct_messages m where m.chat_id = d.id and m.user_id <> me
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity')),
      'mention', false,
      'marked_unread', coalesce(st.marked_unread, false), 'pinned_at', st.pinned_at, 'archived', st.archived_at is not null,
      'notify', coalesce(s.notify, 'all'), 'muted_until', case when st.muted_until > now() then st.muted_until end,
      'request', case when d.status = 'request' then case when d.requested_by = me then 'outgoing' else 'incoming' end end,
      'seen_by_other', case when d.status = 'active' and last.id is not null and last.user_id = me and last.deleted_at is null
                              and my_rr and coalesce(op.read_receipts, true) and not private.blocked_either(me, o.id)
                            then coalesce(os.read_at >= last.created_at, false) end,
      'members', 2, 'is_vp', false,
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = me and k.blocked_id = o.id))
    from public.direct_chats d
    join public.profiles o on o.id = case when d.user_a = me then d.user_b else d.user_a end
    left join public.direct_chat_settings s on s.chat_id = d.id and s.user_id = me
    left join public.direct_chat_settings os on os.chat_id = d.id and os.user_id = o.id
    left join public.chat_prefs op on op.user_id = o.id
    left join public.chat_list_state st on st.user_id = me and st.kind = 'direct' and st.chat_id = d.id
    left join lateral (select m.* from public.direct_messages m where m.chat_id = d.id order by m.created_at desc limit 1) last on true
    left join public.profiles a on a.id = last.user_id
    where me in (d.user_a, d.user_b)
      and case when d.status = 'active' then last.id is not null
               when d.requested_by = me then last.id is not null or d.declined_at is not null
               else d.declined_at is null and last.id is not null and not private.blocked_either(me, o.id) end

    union all
    -- Discussions d'événement : j'organise, je suis invité ou j'ai répondu Présent / Peut-être ; au moins un message ;
    -- date pas passée de plus de 7 jours (sondage sans date : toujours).
    select ev.id, st.pinned_at, st.archived_at, last.created_at, jsonb_build_object(
      'kind', 'event', 'id', ev.id, 'title', ev.title, 'photo', ev.cover_url, 'emoji', null, 'color', null,
      'user_id', null, 'event_start', ev.starts_at,
      'event_past', coalesce(coalesce(ev.ends_at, ev.starts_at + interval '4 hours') < now(), false),
      'last', jsonb_build_object(
        'id', last.id, 'at', last.created_at, 'from_me', last.user_id = me,
        'author', coalesce(nullif(btrim(a.display_name), ''), '?'),
        'type', private.chat_msg_type(last.deleted_at is not null, last.photo_path, last.audio_path, false),
        'text', case when last.deleted_at is not null then '' else left(last.body, 140) end),
      'unread', coalesce(un.n, 0), 'mention', coalesce(un.mention, false),
      'marked_unread', coalesce(st.marked_unread, false), 'pinned_at', st.pinned_at, 'archived', st.archived_at is not null,
      'notify', case when exists (select 1 from public.event_mutes x where x.event_id = ev.id and x.user_id = me) then 'none' else 'all' end,
      'muted_until', case when st.muted_until > now() then st.muted_until end,
      'request', null, 'seen_by_other', null,
      'members', (select count(*) from public.rsvps r where r.event_id = ev.id and r.status in ('yes', 'maybe')),
      'is_vp', false, 'blocked', false)
    from (select e.id from public.events e where e.created_by = me
          union select o.event_id from public.event_organizers o where o.user_id = me
          union select i.event_id from public.event_invites i where i.user_id = me
          union select r.event_id from public.rsvps r where r.user_id = me and r.status in ('yes', 'maybe')) mine
    join public.events ev on ev.id = mine.id
    left join public.chat_list_state st on st.user_id = me and st.kind = 'event' and st.chat_id = ev.id
    join lateral (select m.* from public.messages m where m.event_id = ev.id and not private.blocked_either(me, m.user_id)
                  order by m.created_at desc limit 1) last on true
    left join public.profiles a on a.id = last.user_id
    left join lateral (select count(*) as n,
                              bool_or(me = any (m.mentions) or m.mention_all or m.announcement
                                      or (m.mention_present and exists (select 1 from public.rsvps r where r.event_id = ev.id
                                                                         and r.user_id = me and r.status in ('yes', 'maybe')))
                                      or exists (select 1 from public.messages r where r.id = m.reply_to and r.user_id = me)) as mention
                       from public.messages m
                       where m.event_id = ev.id and m.user_id <> me and m.deleted_at is null
                         and m.created_at > coalesce(st.read_at, since) and not private.blocked_either(me, m.user_id)) un on true
    where (ev.starts_at is null or coalesce(ev.ends_at, ev.starts_at) > now() - interval '7 days')
      and public.can_see_event(ev.id)
  )
  select coalesce(jsonb_agg(r.c order by r.pinned_at desc nulls last, r.last_at desc nulls last, r.c ->> 'title'), '[]'::jsonb) into out
  from lst r where include_archived or r.archived_at is null;
  return out;
end $$;

create or replace function public.set_chat_state(kind text, chat uuid, pinned boolean default null, archived boolean default null,
                                                 unread boolean default null, muted_until timestamptz default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
#variable_conflict use_variable
declare me uuid := auth.uid(); st public.chat_list_state;
begin
  if me is null then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if kind = 'direct' then
    if not private.in_direct(chat, me) then raise exception 'forbidden: conversation inaccessible' using errcode = '42501'; end if;
  elsif kind = 'group' then
    if not private.reads_group(chat) then raise exception 'forbidden: conversation inaccessible' using errcode = '42501'; end if;
  elsif kind = 'event' then
    if not public.can_see_event(chat) then raise exception 'forbidden: conversation inaccessible' using errcode = '42501'; end if;
  else
    raise exception 'invalid: Sorte de discussion inconnue' using errcode = '22023';
  end if;
  if pinned and (select count(*) from public.chat_list_state s where s.user_id = me and s.pinned_at is not null
                   and not (s.kind = kind and s.chat_id = chat)) >= 5 then
    raise exception 'pin_limit: Tu peux épingler 5 discussions au plus.' using errcode = '22023';
  end if;
  insert into public.chat_list_state (user_id, kind, chat_id) values (me, kind, chat)
  on conflict on constraint chat_list_state_pkey do nothing;
  update public.chat_list_state s set
    pinned_at = case when archived then null when pinned is null then s.pinned_at when pinned then coalesce(s.pinned_at, now()) end,
    archived_at = case when archived is not null then (case when archived then coalesce(s.archived_at, now()) end)
                       when pinned then null else s.archived_at end,
    marked_unread = coalesce(unread, s.marked_unread),
    muted_until = case when muted_until is null then s.muted_until when muted_until > now() then muted_until end
  where s.user_id = me and s.kind = kind and s.chat_id = chat
  returning * into st;
  return jsonb_build_object('kind', st.kind, 'id', st.chat_id, 'pinned_at', st.pinned_at, 'archived', st.archived_at is not null,
    'marked_unread', st.marked_unread, 'muted_until', case when st.muted_until > now() then st.muted_until end);
end $$;

-- Lire une conversation remet « non lu » à zéro (mark_direct_read, mark_group_read, mark_event_chat_read).
create or replace function private.chat_read_clears_unread() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.chat_list_state s set marked_unread = false
   where s.user_id = new.user_id and s.marked_unread
     and ((tg_table_name = 'direct_chat_settings' and s.kind = 'direct' and s.chat_id::text = to_jsonb(new) ->> 'chat_id')
       or (tg_table_name = 'group_chat_settings' and s.kind = 'group' and s.chat_id::text = to_jsonb(new) ->> 'group_id'));
  return null;
end $$;
drop trigger if exists direct_chat_settings_read on public.direct_chat_settings;
create trigger direct_chat_settings_read after insert or update of read_at on public.direct_chat_settings
  for each row when (new.read_at is not null) execute function private.chat_read_clears_unread();
drop trigger if exists group_chat_settings_read on public.group_chat_settings;
create trigger group_chat_settings_read after insert or update of read_at on public.group_chat_settings
  for each row when (new.read_at is not null) execute function private.chat_read_clears_unread();

create or replace function public.mark_event_chat_read(e uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.can_see_event(e) then return; end if;
  insert into public.chat_list_state as s (user_id, kind, chat_id, read_at) values (auth.uid(), 'event', e, now())
  on conflict on constraint chat_list_state_pkey do update set read_at = now(), marked_unread = false;
end $$;

-- Pastille de l'onglet : non lus hors archivées et hors sourdine (« non lu » manuel = 1) + 1 par demande reçue.
create or replace function public.chat_badge() returns integer
language sql stable security definer set search_path = '' as $$
  select coalesce(sum(case
    when c ->> 'request' = 'incoming' then 1
    when c ->> 'request' = 'outgoing' then 0
    when c ->> 'notify' = 'none' or c ->> 'muted_until' is not null then 0
    else greatest((c ->> 'unread')::int, case when (c ->> 'marked_unread')::boolean then 1 else 0 end) end), 0)::int
  from jsonb_array_elements(public.chat_list(false)) c;
$$;

-- ───────────── 4. Personnes ─────────────

-- P = {"id","name","nickname","photo","sub","link","met_count"} ; photo = chemin du stockage (profile-photos).
create or replace function private.chat_person(me uuid, uid uuid, sub text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', p.id, 'name', private.chat_name(p.id), 'nickname', nullif(btrim(p.display_name), ''),
    'photo', p.avatar_url, 'sub', nullif(btrim(coalesce(sub, '')), ''), 'link', private.dm_link(me, p.id),
    'met_count', (select count(*) from private.met_events(me, p.id)))
  from public.profiles p where p.id = uid;
$$;

create or replace function public.chat_people_suggestions() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); vp uuid := private.vip_group_id(); recent jsonb; crossed jsonb; grp jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  -- Conversations récentes (acceptées, avec des messages).
  select coalesce(jsonb_agg(private.chat_person(me, x.u, null) order by x.last_at desc), '[]'::jsonb) into recent from (
    select r.u, r.last_at from (
      select o.u, max(m.created_at) as last_at
      from public.direct_chats d
      cross join lateral (select case when d.user_a = me then d.user_b else d.user_a end as u) o
      join public.direct_messages m on m.chat_id = d.id
      where me in (d.user_a, d.user_b) and d.status = 'active'
      group by o.u) r
    where private.is_account_active(r.u) and not private.blocked_either(me, r.u) and private.dm_link(me, r.u) <> 'none'
    order by r.last_at desc limit 12) x;
  -- Croisés : événements en commun (début dans les 60 derniers jours ou à venir), personnes que je peux y voir.
  select coalesce(jsonb_agg(private.chat_person(me, y.u, y.title) order by y.start_at desc nulls last), '[]'::jsonb) into crossed from (
    select z.u, z.title, z.start_at from (
      select distinct on (p.u) p.u, ev.title, ev.starts_at as start_at
      from public.events ev
      cross join lateral (
        select ev.created_by u
        union select o.user_id from public.event_organizers o where o.event_id = ev.id
        union select r.user_id from public.rsvps r where r.event_id = ev.id and r.status in ('yes', 'maybe')
                and (ev.show_participants or private.chat_manages(ev, me))
        union select i.user_id from public.event_invites i where i.event_id = ev.id and private.chat_manages(ev, me)) p
      where ev.id in (select private.dm_events_of(me)) and ev.status in ('published', 'cancelled')
        and ev.starts_at >= now() - interval '60 days'
        and p.u is not null and p.u <> me
        and exists (select 1 from public.profiles pr where pr.id = p.u and pr.status = 'active' and coalesce(btrim(pr.display_name), '') <> '')
        and not private.blocked_either(me, p.u)
      order by p.u, ev.starts_at desc) z
    where private.dm_link(me, z.u) <> 'none'
    order by z.start_at desc limit 12) y;
  -- Dans mes groupes (hors Vendredi Party).
  select coalesce(jsonb_agg(private.chat_person(me, w.u, w.name) order by w.name, w.dn), '[]'::jsonb) into grp from (
    select v.u, v.name, v.dn from (
      select distinct on (b.user_id) b.user_id u, g.name, pr.display_name dn
      from public.member_group_members a
      join public.member_groups g on g.id = a.group_id and g.id is distinct from vp
      join public.member_group_members b on b.group_id = a.group_id and b.user_id <> me
      join public.profiles pr on pr.id = b.user_id and pr.status = 'active' and coalesce(btrim(pr.display_name), '') <> ''
      where a.user_id = me and not private.blocked_either(me, b.user_id)
      order by b.user_id, g.name) v
    where private.dm_link(me, v.u) <> 'none'
    order by v.name, v.dn limit 12) w;
  return jsonb_build_object('recent', recent, 'crossed', crossed, 'groups', grp);
end $$;

-- Recherche par surnom (et prénom / nom quand la personne les montre), sans accents ; jamais par numéro.
create or replace function public.chat_people_search(q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); qq text := private.fold(btrim(coalesce(q, ''))); see_names boolean; out jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if char_length(qq) < 2 then return '[]'::jsonb; end if;
  see_names := public.has_perm('members.view_identity');
  select coalesce(jsonb_agg(private.chat_person(me, x.id, null) order by x.direct desc, x.prefix desc, x.dn), '[]'::jsonb) into out from (
    select c.id, c.dn, c.prefix, private.dm_link(me, c.id) = 'direct' as direct from (
      select p.id, p.display_name dn,
             starts_with(private.fold(p.display_name), qq) as prefix
      from public.profiles p
      where p.status = 'active' and p.id <> me and coalesce(btrim(p.display_name), '') <> ''
        and not private.blocked_either(me, p.id)
        and (position(qq in private.fold(p.display_name)) > 0
             or ((see_names or private.shows_name(p.id))
                 and position(qq in private.fold(concat_ws(' ', p.first_name, p.last_name))) > 0))
      order by starts_with(private.fold(p.display_name), qq) desc, p.display_name
      limit 200) c
    where private.dm_link(me, c.id) <> 'none'
    order by private.dm_link(me, c.id) = 'direct' desc, c.prefix desc, c.dn
    limit 20) x;
  return out;
end $$;

create or replace function public.member_mini(target uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); vp uuid := private.vip_group_id(); p public.profiles; chat uuid; i_blocked boolean;
  ev_list jsonb; ev_count int; grp_list jsonb; grp_count int; met jsonb; met_count int;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into p from public.profiles where id = target and status = 'active';
  if p.id is null then return null; end if;
  if p.id <> me and exists (select 1 from public.direct_blocks k where k.user_id = p.id and k.blocked_id = me) then
    return jsonb_build_object('id', p.id, 'name', coalesce(nullif(btrim(p.display_name), ''), 'Profil à compléter'),
      'nickname', nullif(btrim(p.display_name), ''), 'photo', p.avatar_url, 'since', null, 'link', 'none',
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = me and k.blocked_id = p.id), 'blocked_me', true,
      'chat', null, 'met_count', 0, 'met', '[]'::jsonb, 'events', '[]'::jsonb, 'groups', '[]'::jsonb,
      'events_count', 0, 'groups_count', 0);
  end if;
  i_blocked := exists (select 1 from public.direct_blocks k where k.user_id = me and k.blocked_id = p.id);
  select d.id into chat from public.direct_chats d where d.user_a = least(me, p.id) and d.user_b = greatest(me, p.id);
  select count(*), coalesce(jsonb_agg(jsonb_build_object('id', x.id, 'title', x.title, 'start', x.starts_at) order by x.starts_at desc)
                              filter (where x.n <= 3), '[]'::jsonb)
    into met_count, met
    from (select m.*, row_number() over (order by m.starts_at desc) n from private.met_events(me, p.id) m) x;
  select count(*), coalesce(jsonb_agg(jsonb_build_object('id', y.id, 'title', y.title, 'start', y.starts_at, 'mine', y.mine, 'theirs', y.theirs)
                                      order by y.starts_at nulls last) filter (where y.n <= 5), '[]'::jsonb)
    into ev_count, ev_list
    from (select ev.id, ev.title, ev.starts_at, private.chat_role(ev, me, me) mine, private.chat_role(ev, p.id, me) theirs,
                 row_number() over (order by ev.starts_at nulls last, ev.id) n
          from public.events ev
          where p.id <> me and ev.id in (select private.dm_events_of(me)) and ev.id in (select private.dm_events_of(p.id))
            and ev.status = 'published'
            and (ev.starts_at is null or coalesce(ev.ends_at, ev.starts_at + interval '4 hours') >= now())
            and public.can_see_event(ev.id) and private.chat_role(ev, p.id, me) is not null) y;
  select count(*), coalesce(jsonb_agg(jsonb_build_object('id', z.id, 'name', z.name, 'emoji', z.emoji, 'color', z.color, 'photo', z.photo_path)
                                      order by z.name) filter (where z.n <= 5), '[]'::jsonb)
    into grp_count, grp_list
    from (select g.*, row_number() over (order by g.name) n from public.member_groups g
          where p.id <> me and g.id is distinct from vp
            and private.in_group_now(g.id, me) and private.in_group_now(g.id, p.id)) z;
  return jsonb_build_object('id', p.id, 'name', private.chat_name(p.id), 'nickname', nullif(btrim(p.display_name), ''),
    'photo', p.avatar_url, 'since', p.created_at, 'link', private.dm_link(me, p.id),
    'blocked', i_blocked, 'blocked_me', false, 'chat', chat,
    'met_count', met_count, 'met', met, 'events', ev_list, 'groups', grp_list,
    'events_count', ev_count, 'groups_count', grp_count);
end $$;

-- ───────────── 6. Conversation ─────────────

-- Lu par l'autre (messages directs) : seulement si nos deux confirmations de lecture sont allumées, conversation acceptée,
-- personne de bloqué.
create or replace function public.direct_seen(chat uuid) returns timestamptz
language sql stable security definer set search_path = '' as $$
  select os.read_at
  from public.direct_chats d
  join public.direct_chat_settings os on os.chat_id = d.id and os.user_id = private.direct_other(d.id, auth.uid())
  where d.id = chat and auth.uid() in (d.user_a, d.user_b) and d.status = 'active'
    and not private.blocked_either(d.user_a, d.user_b)
    and coalesce((select p.read_receipts from public.chat_prefs p where p.user_id = d.user_a), true)
    and coalesce((select p.read_receipts from public.chat_prefs p where p.user_id = d.user_b), true);
$$;

-- Modifier : l'auteur, dans les 15 minutes après l'envoi (edit_window) ; une demande reste un texte sans lien ni numéro.
create or replace function public.edit_direct_message(msg uuid, new_body text) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.direct_messages;
begin
  if btrim(coalesce(new_body, '')) = '' or char_length(new_body) > 2000 then raise exception 'Message vide ou trop long'; end if;
  select * into m from public.direct_messages where id = msg;
  if m.id is null or m.user_id is distinct from auth.uid() or m.deleted_at is not null then
    raise exception 'forbidden: tu ne peux modifier que tes messages' using errcode = '42501';
  end if;
  if m.created_at < now() - interval '15 minutes' then
    raise exception 'edit_window: Un message se modifie dans les 15 minutes après son envoi.' using errcode = '42501';
  end if;
  if exists (select 1 from public.direct_chats c where c.id = m.chat_id and c.status = 'request')
     and private.request_text_refused(new_body) then
    raise exception 'request_pending: Une demande de message est un seul texte, sans photo, vocal, lien ni numéro.' using errcode = '42501';
  end if;
  update public.direct_messages set body = btrim(new_body), edited_at = now() where id = msg;
end $$;

create or replace function public.edit_group_message(msg uuid, new_body text) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.group_messages;
begin
  if btrim(coalesce(new_body, '')) = '' or char_length(new_body) > 2000 then raise exception 'Message vide ou trop long'; end if;
  select * into m from public.group_messages where id = msg;
  if m.id is null or m.user_id is distinct from auth.uid() or m.deleted_at is not null then
    raise exception 'forbidden: tu ne peux modifier que tes messages' using errcode = '42501';
  end if;
  if m.created_at < now() - interval '15 minutes' then
    raise exception 'edit_window: Un message se modifie dans les 15 minutes après son envoi.' using errcode = '42501';
  end if;
  update public.group_messages set body = btrim(new_body), edited_at = now() where id = msg;
end $$;

-- Cartes d'événement des messages : seulement les événements que je peux voir, dans l'ordre demandé.
create or replace function public.chat_event_cards(ids uuid[]) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object(
      'id', ev.id, 'title', ev.title, 'start', ev.starts_at, 'place', nullif(btrim(ev.location_name), ''), 'cover', ev.cover_url,
      'going', (select count(*) from public.rsvps r where r.event_id = ev.id and r.status = 'yes'),
      'mine', coalesce((select r.status::text from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()),
                       case when exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = auth.uid())
                            then 'invited' end))
    order by array_position(ids, ev.id)), '[]'::jsonb)
  from public.events ev
  where auth.uid() is not null and ev.id = any (coalesce(ids, '{}')) and cardinality(ids) <= 100 and public.can_see_event(ev.id);
$$;

-- ───────────── Droits ─────────────

revoke all on function private.fold(text), private.chat_name(uuid), private.chat_msg_type(boolean, text, text, boolean),
  private.request_text_refused(text), private.chat_manages(public.events, uuid), private.chat_role(public.events, uuid, uuid),
  private.met_events(uuid, uuid), private.dm_check(uuid, uuid, boolean), private.dm_link(uuid, uuid),
  private.clean_quote(jsonb), private.guard_direct_message_v2(), private.guard_group_message_v2(),
  private.notify_message_request(), private.direct_chat_changed(), private.chat_requests_tick(),
  private.group_private_chat_guard(), private.chat_read_clears_unread(), private.chat_person(uuid, uuid, text)
  from public, anon, authenticated;
-- Appelée par les règles de lecture des membres de groupe, avec les droits de la personne connectée.
revoke all on function private.group_is_private(uuid) from public, anon;
grant execute on function private.group_is_private(uuid) to authenticated;

revoke all on function public.chat_link(uuid), public.open_direct_chat(uuid, text), public.start_direct_chat(uuid, text),
  public.accept_message_request(uuid), public.decline_message_request(uuid), public.chat_prefs_get(),
  public.chat_prefs_set(text, boolean), public.create_chat_group(text, text, text, uuid[]), public.chat_group_with(uuid[]),
  public.chat_list(boolean), public.set_chat_state(text, uuid, boolean, boolean, boolean, timestamptz),
  public.mark_event_chat_read(uuid), public.chat_badge(), public.chat_people_suggestions(), public.chat_people_search(text),
  public.member_mini(uuid), public.direct_seen(uuid), public.edit_direct_message(uuid, text), public.edit_group_message(uuid, text),
  public.chat_event_cards(uuid[]) from public, anon;
grant execute on function public.chat_link(uuid), public.open_direct_chat(uuid, text), public.start_direct_chat(uuid, text),
  public.accept_message_request(uuid), public.decline_message_request(uuid), public.chat_prefs_get(),
  public.chat_prefs_set(text, boolean), public.create_chat_group(text, text, text, uuid[]), public.chat_group_with(uuid[]),
  public.chat_list(boolean), public.set_chat_state(text, uuid, boolean, boolean, boolean, timestamptz),
  public.mark_event_chat_read(uuid), public.chat_badge(), public.chat_people_suggestions(), public.chat_people_search(text),
  public.member_mini(uuid), public.direct_seen(uuid), public.edit_direct_message(uuid, text), public.edit_group_message(uuid, text),
  public.chat_event_cards(uuid[]) to authenticated;

notify pgrst, 'reload schema';

insert into supabase_migrations.schema_migrations (version, name) values ('20261118120000', 'discussions_v2') on conflict do nothing;
commit;
