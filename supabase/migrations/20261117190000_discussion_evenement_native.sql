-- Discussion d'un événement NATIVE façon WhatsApp (demande de l'admin du 17.11.2026) : réglages de la discussion,
-- notifications par discussion (de base : mentions seulement), non-lus, médias, recherche. Purement additive et rejouable ;
-- ne dépend que de 20261116180000 (discussion v1). Les fonctions partagées s'ÉTENDENT (ancre + replace), jamais réécrites.
--  1. event_chat_prefs : par personne et par événement, niveau (all / mentions / none), sourdine (muted_until, 'infinity' =
--     toujours), dernier message lu. Sans ligne (ou niveau jamais choisi : custom = false), le niveau est celui de
--     notification_prefs.chat de la personne ('mentions' par défaut). RLS : sa ligne seulement.
--  2. events.chat_write ('all' | 'staff' : « Qui peut écrire ») et events.chat_description (≤ 500, filtrée, CGU) : changés
--     seulement par l'organisation de l'événement (private.event_chat_staff), garde events_chat_guard ; guard_event laisse
--     l'organisation (co-organisateurs compris) changer ces deux réglages, même publié.
--  3. guard_message_change : en « Organisation seulement », un message d'un autre est refusé ; event_chat_writes (droit
--     d'écrire, photos et vocaux compris) suit le même réglage.
--  4. notify_message : niveau de la discussion d'abord (none ou sourdine → rien ; mentions → cité, réponse, @toutlemonde,
--     @present, annonce ; all → tout), event_mutes toujours respecté ; data gagne thread 'event-chat:<id>' et can_reply
--     (false en « Organisation seulement » pour qui n'est pas de l'organisation).
--  5. Fonctions : event_chat_prefs_get, event_chat_set_level, event_chat_mute, event_chat_mark_read,
--     event_chat_set_settings, event_chat_media, event_chat_search ; event_chat_state gagne unread, level, muted_until,
--     write_mode, description, can_write.
--  6. Signalement d'un événement (Apple 1.2) : le texte signalé contient aussi la description de la discussion.
-- Temps réel : changer un réglage de la discussion met à jour events → signal `event:<id>` (déclencheur event_changed),
-- redit explicitement par event_chat_set_settings. Les préférences personnelles ne signalent rien aux autres.

-- 1. -----------------------------------------------------------------------------------------------------------------
create table if not exists public.event_chat_prefs (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  level text not null default 'mentions' check (level in ('all', 'mentions', 'none')),
  muted_until timestamptz,
  last_read_at timestamptz,
  updated_at timestamptz default now(),
  primary key (event_id, user_id)
);
-- Niveau choisi pour CETTE discussion (sinon : le réglage global de la personne, même s'il change ensuite).
alter table public.event_chat_prefs add column if not exists custom boolean not null default false;
create index if not exists event_chat_prefs_user on public.event_chat_prefs (user_id);
alter table public.event_chat_prefs enable row level security;
revoke all on public.event_chat_prefs from anon;
grant select, insert, update, delete on public.event_chat_prefs to authenticated;
drop policy if exists "lire ses réglages de discussion" on public.event_chat_prefs;
create policy "lire ses réglages de discussion" on public.event_chat_prefs for select to authenticated
  using (user_id = (select auth.uid()));
drop policy if exists "créer ses réglages de discussion" on public.event_chat_prefs;
create policy "créer ses réglages de discussion" on public.event_chat_prefs for insert to authenticated
  with check (user_id = (select auth.uid()) and public.can_see_event(event_id));
drop policy if exists "modifier ses réglages de discussion" on public.event_chat_prefs;
create policy "modifier ses réglages de discussion" on public.event_chat_prefs for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists "effacer ses réglages de discussion" on public.event_chat_prefs;
create policy "effacer ses réglages de discussion" on public.event_chat_prefs for delete to authenticated
  using (user_id = (select auth.uid()));

-- Niveau global de la personne (notification_prefs.chat), 'mentions' par défaut.
create or replace function private.chat_default_level(u uuid) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select np.chat::text from public.notification_prefs np where np.user_id = u), 'mentions');
$$;
revoke all on function private.chat_default_level(uuid) from public, anon, authenticated;

-- Niveau effectif d'une personne dans une discussion.
create or replace function private.event_chat_level(e uuid, u uuid) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select p.level from public.event_chat_prefs p where p.event_id = e and p.user_id = u and p.custom),
                  private.chat_default_level(u));
$$;
revoke all on function private.event_chat_level(uuid, uuid) from public, anon, authenticated;

-- Organisation de l'événement pour une personne donnée (event_chat_staff lit auth.uid()).
create or replace function private.event_chat_staff_of(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.user_has(u, 'events.manage_all')
      or exists (select 1 from public.events ev where ev.id = e and ev.created_by = u)
      or exists (select 1 from public.event_organizers o where o.event_id = e and o.user_id = u);
$$;
revoke all on function private.event_chat_staff_of(uuid, uuid) from public, anon, authenticated;

-- Non-lus : messages des autres après le dernier lu, sans les supprimés ni ceux des personnes bloquées.
create or replace function private.event_chat_unread(e uuid, u uuid) returns integer
language sql stable security definer set search_path = '' as $$
  select count(*)::int from public.messages m
  where m.event_id = e and m.user_id <> u and m.deleted_at is null
    and m.created_at > coalesce((select p.last_read_at from public.event_chat_prefs p where p.event_id = e and p.user_id = u), '-infinity')
    and not private.blocked_either(u, m.user_id);
$$;
revoke all on function private.event_chat_unread(uuid, uuid) from public, anon, authenticated;

-- Ce que la personne connectée voit de ses réglages ; sourdine passée = null.
create or replace function private.event_chat_me(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'level', private.event_chat_level(e, auth.uid()),
    'custom', coalesce(p.custom, false),
    'muted_until', case when p.muted_until > now() then p.muted_until end,
    'last_read_at', p.last_read_at,
    'unread', private.event_chat_unread(e, auth.uid()))
  from (select 1) x left join public.event_chat_prefs p on p.event_id = e and p.user_id = auth.uid();
$$;
revoke all on function private.event_chat_me(uuid) from public, anon, authenticated;

-- Veut-elle être prévenue de ce message ? Niveau de la discussion, sinon global ; sourdine → non.
create or replace function private.event_chat_wants(e uuid, u uuid, cited boolean) returns boolean
language sql stable security definer set search_path = '' as $$
  select case
    when exists (select 1 from public.event_chat_prefs p where p.event_id = e and p.user_id = u and p.muted_until > now()) then false
    else case private.event_chat_level(e, u) when 'all' then true when 'mentions' then coalesce(cited, false) else false end
  end;
$$;
revoke all on function private.event_chat_wants(uuid, uuid, boolean) from public, anon, authenticated;

-- 2. -----------------------------------------------------------------------------------------------------------------
alter table public.events add column if not exists chat_write text not null default 'all';
alter table public.events add column if not exists chat_description text;
alter table public.events drop constraint if exists events_chat_write_check;
alter table public.events add constraint events_chat_write_check check (chat_write in ('all', 'staff'));
alter table public.events drop constraint if exists events_chat_description_check;
alter table public.events add constraint events_chat_description_check check (char_length(chat_description) <= 500);

create or replace function private.guard_event_chat() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and new.chat_write is not distinct from old.chat_write
     and new.chat_description is not distinct from old.chat_description then
    return new;
  end if;
  new.chat_description := nullif(btrim(coalesce(new.chat_description, '')), '');
  if auth.uid() is null then return new; end if;  -- cron, service role
  if tg_op = 'UPDATE' and not private.event_chat_staff(new.id) then
    raise exception 'forbidden: Seule l''organisation de l''événement règle sa discussion.' using errcode = '42501';
  end if;
  if new.chat_description is not null and (tg_op = 'INSERT' or new.chat_description is distinct from old.chat_description) then
    if char_length(new.chat_description) > 500 then
      raise exception 'invalid: La description de la discussion fait 500 caractères au plus.' using errcode = '22023';
    end if;
    perform private.require_terms(auth.uid());
    new.chat_description := private.moderate_text(new.chat_description, 'message');
  end if;
  return new;
end $$;
revoke all on function private.guard_event_chat() from public, anon, authenticated;
drop trigger if exists events_chat_guard on public.events;
create trigger events_chat_guard before insert or update of chat_write, chat_description on public.events
  for each row execute function private.guard_event_chat();

do $$ declare def text;
begin
  -- guard_event : seuls les réglages de la discussion changent → l'organisation, quel que soit le statut.
  def := pg_get_functiondef('public.guard_event()'::regprocedure);
  if position('''chat_write''' in def) = 0 then
    if position('  -- Annulé (05.11)' in def) = 0 then raise exception 'guard_event : ancre Annulé introuvable'; end if;
    execute replace(def, '  -- Annulé (05.11)', $a$  -- Discussion (17.11) : seuls « Qui peut écrire » et la description de la discussion changent → l'organisation.
  if (to_jsonb(new) - 'chat_write' - 'chat_description' - 'updated_at') = (to_jsonb(old) - 'chat_write' - 'chat_description' - 'updated_at')
     and private.event_chat_staff(new.id) then return new; end if;
  -- Annulé (05.11)$a$);
  end if;

  -- 3. event_chat_writes : « Organisation seulement » → seule l'organisation écrit (photos et vocaux compris).
  def := pg_get_functiondef('private.event_chat_writes(uuid)'::regprocedure);
  if position('ev.chat_write' in def) = 0 then
    if position('and coalesce((select ev.forum_enabled from public.events ev where ev.id = e), false);' in def) = 0 then
      raise exception 'event_chat_writes : ancre forum_enabled introuvable';
    end if;
    execute replace(def, 'and coalesce((select ev.forum_enabled from public.events ev where ev.id = e), false);',
      $a$and coalesce((select ev.forum_enabled from public.events ev where ev.id = e), false)
         and (coalesce((select ev.chat_write from public.events ev where ev.id = e), 'all') = 'all' or private.event_chat_staff(e));$a$);
  end if;

  -- guard_message_change : refus à l'INSERT en « Organisation seulement ».
  def := pg_get_functiondef('private.guard_message_change()'::regprocedure);
  if position('ev.chat_write' in def) = 0 then
    if position($a$  if tg_op = 'INSERT' then
    if new.photo_path is not null$a$ in def) = 0 then raise exception 'guard_message_change : ancre INSERT introuvable'; end if;
    execute replace(def, $a$  if tg_op = 'INSERT' then
    if new.photo_path is not null$a$, $a$  if tg_op = 'INSERT' then
    if not staff and coalesce((select ev.chat_write from public.events ev where ev.id = new.event_id), 'all') = 'staff' then
      raise exception 'forbidden: Seule l''organisation peut écrire dans cette discussion.' using errcode = '42501';
    end if;
    if new.photo_path is not null$a$);
  end if;

  -- 4. notify_message : niveau de la discussion, sourdine ; thread et can_reply dans data.
  def := pg_get_functiondef('public.notify_message()'::regprocedure);
  if position('event_chat_wants' in def) = 0 then
    if position($a$    if np.chat = 'all' or (np.chat = 'mentions' and cited) then$a$ in def) = 0
       or position($a$jsonb_build_object('mentioned', cited, 'message_id', new.id, 'chat', true)$a$ in def) = 0 then
      raise exception 'notify_message : ancres introuvables';
    end if;
    def := replace(def, $a$    if np.chat = 'all' or (np.chat = 'mentions' and cited) then$a$,
      $a$    if private.event_chat_wants(ev.id, u, cited) then$a$);
    execute replace(def, $a$jsonb_build_object('mentioned', cited, 'message_id', new.id, 'chat', true)$a$,
      $a$jsonb_build_object('mentioned', cited, 'message_id', new.id, 'chat', true,
          'thread', 'event-chat:' || ev.id::text,
          'can_reply', coalesce(ev.chat_write, 'all') = 'all' or private.event_chat_staff_of(ev.id, u))$a$);
  end if;

  -- 5. event_chat_state : réglages et non-lus de la personne, réglages de la discussion.
  def := pg_get_functiondef('public.event_chat_state(uuid)'::regprocedure);
  if position('write_mode' in def) = 0 then
    if position($a$m.user_id = auth.uid()));$a$ in def) = 0 then raise exception 'event_chat_state : ancre muted introuvable'; end if;
    execute replace(def, $a$m.user_id = auth.uid()));$a$, $a$m.user_id = auth.uid()))
    || (private.event_chat_me(e) - 'custom' - 'last_read_at')
    || jsonb_build_object('write_mode', coalesce(ev.chat_write, 'all'), 'description', ev.chat_description,
                          'can_write', private.event_chat_writes(e));$a$);
  end if;

  -- 6. Signalement d'un événement : la description de la discussion fait partie du texte signalé.
  def := pg_get_functiondef('private.report_snapshot(text, text, uuid)'::regprocedure);
  if position('chat_description' in def) = 0 then
    if position($a$      'text', ev.title || case when btrim(coalesce(ev.description, '')) <> '' then E'\n\n' || ev.description else '' end,$a$ in def) = 0 then
      raise exception 'report_snapshot : ancre event introuvable';
    end if;
    execute replace(def, $a$      'text', ev.title || case when btrim(coalesce(ev.description, '')) <> '' then E'\n\n' || ev.description else '' end,$a$,
      $a$      'text', ev.title || case when btrim(coalesce(ev.description, '')) <> '' then E'\n\n' || ev.description else '' end
        || case when btrim(coalesce(ev.chat_description, '')) <> '' then E'\n\nDescription de la discussion : ' || ev.chat_description else '' end,$a$);
  end if;
end $$;

-- 5. -----------------------------------------------------------------------------------------------------------------
create or replace function private.event_chat_require(e uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or e is null or not public.can_see_event(e) then
    raise exception 'forbidden: Cette discussion n''est pas accessible.' using errcode = '42501';
  end if;
end $$;
revoke all on function private.event_chat_require(uuid) from public, anon, authenticated;

create or replace function public.event_chat_prefs_get(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.event_chat_require(e);
  return private.event_chat_me(e);
end $$;

create or replace function public.event_chat_set_level(e uuid, level text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare lv text := lower(btrim(coalesce(event_chat_set_level.level, '')));
begin
  perform private.event_chat_require(e);
  if lv not in ('all', 'mentions', 'none') then
    raise exception 'invalid: Niveau de notification inconnu (all, mentions ou none).' using errcode = '22023';
  end if;
  insert into public.event_chat_prefs as p (event_id, user_id, level, custom, updated_at)
    values (e, auth.uid(), lv, true, now())
    on conflict (event_id, user_id) do update set level = lv, custom = true, updated_at = now();
  return private.event_chat_me(e);
end $$;

create or replace function public.event_chat_mute(e uuid, until timestamptz) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare t timestamptz := case when until > now() then until end;  -- null ou passé = réactiver ; 'infinity' = toujours
begin
  perform private.event_chat_require(e);
  insert into public.event_chat_prefs as p (event_id, user_id, level, muted_until, updated_at)
    values (e, auth.uid(), private.chat_default_level(auth.uid()), t, now())
    on conflict (event_id, user_id) do update set muted_until = t, updated_at = now();
  return private.event_chat_me(e);
end $$;

create or replace function public.event_chat_mark_read(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  perform private.event_chat_require(e);
  insert into public.event_chat_prefs as p (event_id, user_id, level, last_read_at, updated_at)
    values (e, auth.uid(), private.chat_default_level(auth.uid()), now(), now())
    on conflict (event_id, user_id) do update set last_read_at = now(), updated_at = now();
  -- Les notifications de cette discussion sont lues aussi.
  update public.notifications n set read_at = now()
    where n.user_id = auth.uid() and n.event_id = e and n.kind = 'message' and n.read_at is null;
  return jsonb_build_object('unread', 0);
end $$;

create or replace function public.event_chat_set_settings(e uuid, write text default null, description text default null)
returns jsonb
language plpgsql security definer set search_path = '' as $$
declare w text := lower(btrim(event_chat_set_settings.write)); d text := event_chat_set_settings.description;
        ev public.events;
begin
  perform private.event_chat_require(e);
  if not private.event_chat_staff(e) then
    raise exception 'forbidden: Seule l''organisation de l''événement règle sa discussion.' using errcode = '42501';
  end if;
  if w is not null and w not in ('all', 'staff') then
    raise exception 'invalid: « Qui peut écrire » : all ou staff.' using errcode = '22023';
  end if;
  update public.events set chat_write = coalesce(w, chat_write),
                           chat_description = case when d is null then chat_description else d end
    where id = e returning * into ev;
  perform private.party_signal('event:' || e::text);
  return jsonb_build_object('write_mode', ev.chat_write, 'description', ev.chat_description);
end $$;

create or replace function public.event_chat_media(e uuid, before timestamptz default null, lim int default 60) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare n int := least(greatest(coalesce(lim, 60), 1), 200);
begin
  perform private.event_chat_require(e);
  return coalesce((
    select jsonb_agg(x.j order by x.at desc, x.k) from (
      select it.at, it.k, jsonb_build_object('message_id', it.message_id, 'kind', it.kind, 'path', it.path, 'url', it.url,
               'seconds', it.seconds, 'at', it.at, 'author', it.author, 'author_name', pr.display_name, 'text', it.body) j
      from (
        select m.id message_id, 'photo' kind, m.photo_path path, null::text url, null::numeric seconds, m.created_at at,
               m.user_id author, m.body, 0 k
          from public.messages m where m.event_id = e and m.photo_path is not null
        union all
        select m.id, 'audio', m.audio_path, null, m.audio_seconds, m.created_at, m.user_id, m.body, 1
          from public.messages m where m.event_id = e and m.audio_path is not null
        union all
        select m.id, 'link', null, regexp_replace(l[1], '[.,;:!?)\]]+$', ''), null, m.created_at, m.user_id, m.body, 2
          from public.messages m cross join lateral regexp_matches(m.body, '(https?://[^[:space:]<>"]+)', 'g') l
          where m.event_id = e and m.body ~* 'https?://'
      ) it
      join public.messages m on m.id = it.message_id
      left join public.profiles pr on pr.id = it.author
      where m.deleted_at is null and (event_chat_media.before is null or it.at < event_chat_media.before)
        and not private.blocked_either(auth.uid(), it.author)
      order by it.at desc, it.k
      limit n
    ) x), '[]'::jsonb);
end $$;

create or replace function public.event_chat_search(e uuid, q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare s text := btrim(coalesce(q, '')); pat text;
begin
  perform private.event_chat_require(e);
  if char_length(s) < 2 then return '[]'::jsonb; end if;
  s := left(s, 100);
  pat := '%' || replace(replace(replace(s, '\', '\\'), '%', '\%'), '_', '\_') || '%';
  return coalesce((
    select jsonb_agg(jsonb_build_object('message_id', r.id, 'at', r.created_at, 'author', r.user_id,
             'author_name', r.display_name, 'snippet', r.snippet) order by r.created_at desc)
    from (
      select m.id, m.created_at, m.user_id, pr.display_name,
             case when greatest(strpos(lower(m.body), lower(s)) - 40, 1) > 1 then '…' else '' end
             || substr(m.body, greatest(strpos(lower(m.body), lower(s)) - 40, 1), 120)
             || case when greatest(strpos(lower(m.body), lower(s)) - 40, 1) + 120 <= char_length(m.body) then '…' else '' end snippet
      from public.messages m left join public.profiles pr on pr.id = m.user_id
      where m.event_id = e and m.deleted_at is null and m.body ilike pat escape '\'
        and not private.blocked_either(auth.uid(), m.user_id)
      order by m.created_at desc
      limit 50
    ) r), '[]'::jsonb);
end $$;

do $$ declare f text;
begin
  foreach f in array array['public.event_chat_prefs_get(uuid)', 'public.event_chat_set_level(uuid, text)',
    'public.event_chat_mute(uuid, timestamptz)', 'public.event_chat_mark_read(uuid)',
    'public.event_chat_set_settings(uuid, text, text)', 'public.event_chat_media(uuid, timestamptz, integer)',
    'public.event_chat_search(uuid, text)'] loop
    execute format('revoke all on function %s from public, anon', f);
    execute format('grant execute on function %s to authenticated', f);
  end loop;
end $$;

notify pgrst, 'reload schema';
