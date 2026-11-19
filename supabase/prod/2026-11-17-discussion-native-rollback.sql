-- Retour arrière de la discussion d'événement native (20261117190000) : les six fonctions étendues retrouvent leur texte
-- d'avant (remplacement inverse des mêmes ancres, sans toucher au reste : une migration passée depuis est gardée),
-- garde, fonctions event_chat_*, colonnes chat_write / chat_description et table event_chat_prefs retirées. Perdu : les
-- réglages de notification par discussion, les « lu jusqu'ici », « Qui peut écrire » et les descriptions de discussion.
begin;
do $$ declare def text; nw text; ol text;
begin
  def := pg_get_functiondef('public.guard_event()'::regprocedure);
  nw := $a$  -- Discussion (17.11) : seuls « Qui peut écrire » et la description de la discussion changent → l'organisation.
  if (to_jsonb(new) - 'chat_write' - 'chat_description' - 'updated_at') = (to_jsonb(old) - 'chat_write' - 'chat_description' - 'updated_at')
     and private.event_chat_staff(new.id) then return new; end if;
  -- Annulé (05.11)$a$;
  if position(nw in def) > 0 then execute replace(def, nw, '  -- Annulé (05.11)'); end if;

  def := pg_get_functiondef('private.event_chat_writes(uuid)'::regprocedure);
  ol := 'and coalesce((select ev.forum_enabled from public.events ev where ev.id = e), false);';
  nw := $a$and coalesce((select ev.forum_enabled from public.events ev where ev.id = e), false)
         and (coalesce((select ev.chat_write from public.events ev where ev.id = e), 'all') = 'all' or private.event_chat_staff(e));$a$;
  if position(nw in def) > 0 then execute replace(def, nw, ol); end if;

  def := pg_get_functiondef('private.guard_message_change()'::regprocedure);
  nw := $a$
    if not staff and coalesce((select ev.chat_write from public.events ev where ev.id = new.event_id), 'all') = 'staff' then
      raise exception 'forbidden: Seule l''organisation peut écrire dans cette discussion.' using errcode = '42501';
    end if;$a$;
  if position(nw in def) > 0 then execute replace(def, nw, ''); end if;

  def := pg_get_functiondef('public.notify_message()'::regprocedure);
  if position('event_chat_wants' in def) > 0 then
    def := replace(def, $a$    if private.event_chat_wants(ev.id, u, cited) then$a$,
      $a$    if np.chat = 'all' or (np.chat = 'mentions' and cited) then$a$);
    execute replace(def, $a$jsonb_build_object('mentioned', cited, 'message_id', new.id, 'chat', true,
          'thread', 'event-chat:' || ev.id::text,
          'can_reply', coalesce(ev.chat_write, 'all') = 'all' or private.event_chat_staff_of(ev.id, u))$a$,
      $a$jsonb_build_object('mentioned', cited, 'message_id', new.id, 'chat', true)$a$);
  end if;

  def := pg_get_functiondef('public.event_chat_state(uuid)'::regprocedure);
  nw := $a$m.user_id = auth.uid()))
    || (private.event_chat_me(e) - 'custom' - 'last_read_at')
    || jsonb_build_object('write_mode', coalesce(ev.chat_write, 'all'), 'description', ev.chat_description,
                          'can_write', private.event_chat_writes(e));$a$;
  if position(nw in def) > 0 then execute replace(def, nw, $a$m.user_id = auth.uid()));$a$); end if;

  def := pg_get_functiondef('private.report_snapshot(text, text, uuid)'::regprocedure);
  nw := $a$
        || case when btrim(coalesce(ev.chat_description, '')) <> '' then E'\n\nDescription de la discussion : ' || ev.chat_description else '' end,$a$;
  if position(nw in def) > 0 then execute replace(def, nw, ','); end if;

  -- Plus aucune trace des réglages dans les fonctions gardées.
  if position('chat_write' in replace(pg_get_functiondef('public.guard_event()'::regprocedure), '''chat_write''', '')) > 0
     or position('ev.chat_write' in pg_get_functiondef('private.event_chat_writes(uuid)'::regprocedure)) > 0
     or position('ev.chat_write' in pg_get_functiondef('private.guard_message_change()'::regprocedure)) > 0
     or position('event_chat_wants' in pg_get_functiondef('public.notify_message()'::regprocedure)) > 0
     or position('write_mode' in pg_get_functiondef('public.event_chat_state(uuid)'::regprocedure)) > 0
     or position('chat_description' in pg_get_functiondef('private.report_snapshot(text, text, uuid)'::regprocedure)) > 0 then
    raise exception 'Retour arrière incomplet : une fonction garde encore les réglages de la discussion.';
  end if;
end $$;

drop trigger if exists events_chat_guard on public.events;
drop function if exists private.guard_event_chat();
drop function if exists public.event_chat_prefs_get(uuid);
drop function if exists public.event_chat_set_level(uuid, text);
drop function if exists public.event_chat_mute(uuid, timestamptz);
drop function if exists public.event_chat_mark_read(uuid);
drop function if exists public.event_chat_set_settings(uuid, text, text);
drop function if exists public.event_chat_media(uuid, timestamptz, integer);
drop function if exists public.event_chat_search(uuid, text);
drop function if exists private.event_chat_require(uuid);
drop function if exists private.event_chat_wants(uuid, uuid, boolean);
drop function if exists private.event_chat_me(uuid);
drop function if exists private.event_chat_unread(uuid, uuid);
drop function if exists private.event_chat_staff_of(uuid, uuid);
drop function if exists private.event_chat_level(uuid, uuid);
drop function if exists private.chat_default_level(uuid);
alter table public.events drop constraint if exists events_chat_description_check;
alter table public.events drop constraint if exists events_chat_write_check;
alter table public.events drop column if exists chat_description;
alter table public.events drop column if exists chat_write;
drop table if exists public.event_chat_prefs;
delete from supabase_migrations.schema_migrations where version = '20261117190000';
commit;
notify pgrst, 'reload schema';
