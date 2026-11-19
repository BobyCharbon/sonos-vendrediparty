-- Fusion du 19.11.2026 : discussion d'événement native (20261117190000, en prod depuis le 17.11) × Discussions v2
-- (20261118120000). La même discussion d'événement avait deux états par personne, qui s'ignoraient :
--   - event_chat_prefs (écran de la discussion : cloche, sourdine, dernier message lu → non-lus, notifications) ;
--   - chat_list_state (liste des Discussions : sourdine depuis la liste, lu, « non lu », pastille de l'onglet).
-- Lue dans l'écran natif, une discussion restait non lue dans la liste ; mise en sourdine depuis la liste, elle
-- prévenait encore. Désormais :
--  1. « lu » (last_read_at ↔ read_at, le plus récent gagne) et sourdine (muted_until) se recopient d'un état à l'autre
--     (déclencheurs ; sans boucle : rien n'est réécrit quand la valeur est déjà la même) ; rattrapage des lignes d'avant ;
--  2. chat_list : le niveau d'une discussion d'événement est celui de sa cloche (private.event_chat_level, Mentions
--     seulement par défaut) ; « Rien » si l'ancienne coupure de la fiche (event_mutes) est posée.
-- Purement additive et rejouable.

-- 1. -----------------------------------------------------------------------------------------------------------------
create or replace function private.event_chat_prefs_to_list() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  read_changed boolean := new.last_read_at is not null
    and (tg_op = 'INSERT' or new.last_read_at is distinct from old.last_read_at);
  mute_changed boolean := case when tg_op = 'INSERT' then new.muted_until is not null
                               else new.muted_until is distinct from old.muted_until end;
begin
  if not (read_changed or mute_changed) then return null; end if;
  insert into public.chat_list_state (user_id, kind, chat_id) values (new.user_id, 'event', new.event_id)
    on conflict on constraint chat_list_state_pkey do nothing;
  update public.chat_list_state s set
      read_at = case when read_changed then greatest(s.read_at, new.last_read_at) else s.read_at end,
      marked_unread = case when read_changed then false else s.marked_unread end,
      muted_until = case when mute_changed then new.muted_until else s.muted_until end
    where s.user_id = new.user_id and s.kind = 'event' and s.chat_id = new.event_id
      and ((read_changed and (s.read_at is distinct from greatest(s.read_at, new.last_read_at) or s.marked_unread))
        or (mute_changed and s.muted_until is distinct from new.muted_until));
  return null;
end $$;
revoke all on function private.event_chat_prefs_to_list() from public, anon, authenticated;

create or replace function private.chat_list_state_to_event_prefs() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  read_changed boolean := new.read_at is not null
    and (tg_op = 'INSERT' or new.read_at is distinct from old.read_at);
  mute_changed boolean := case when tg_op = 'INSERT' then new.muted_until is not null
                               else new.muted_until is distinct from old.muted_until end;
begin
  if new.kind <> 'event' or not (read_changed or mute_changed) then return null; end if;
  if not exists (select 1 from public.events e where e.id = new.chat_id) then return null; end if;
  insert into public.event_chat_prefs (event_id, user_id) values (new.chat_id, new.user_id)
    on conflict (event_id, user_id) do nothing;
  update public.event_chat_prefs p set
      last_read_at = case when read_changed then greatest(p.last_read_at, new.read_at) else p.last_read_at end,
      muted_until = case when mute_changed then new.muted_until else p.muted_until end,
      updated_at = now()
    where p.event_id = new.chat_id and p.user_id = new.user_id
      and ((read_changed and p.last_read_at is distinct from greatest(p.last_read_at, new.read_at))
        or (mute_changed and p.muted_until is distinct from new.muted_until));
  return null;
end $$;
revoke all on function private.chat_list_state_to_event_prefs() from public, anon, authenticated;

drop trigger if exists event_chat_prefs_to_list on public.event_chat_prefs;
create trigger event_chat_prefs_to_list after insert or update of last_read_at, muted_until on public.event_chat_prefs
  for each row execute function private.event_chat_prefs_to_list();
drop trigger if exists chat_list_state_to_event_prefs on public.chat_list_state;
create trigger chat_list_state_to_event_prefs after insert or update of read_at, muted_until on public.chat_list_state
  for each row when (new.kind = 'event') execute function private.chat_list_state_to_event_prefs();

-- Rattrapage : le « lu » le plus récent et la sourdine en cours valent des deux côtés (rejouable : rien ne change ensuite).
insert into public.chat_list_state (user_id, kind, chat_id)
  select p.user_id, 'event', p.event_id from public.event_chat_prefs p
  where p.last_read_at is not null or p.muted_until > now()
  on conflict on constraint chat_list_state_pkey do nothing;
update public.chat_list_state s set read_at = p.last_read_at, marked_unread = false
  from public.event_chat_prefs p
  where s.kind = 'event' and s.chat_id = p.event_id and s.user_id = p.user_id and p.last_read_at > coalesce(s.read_at, '-infinity');
update public.chat_list_state s set muted_until = p.muted_until
  from public.event_chat_prefs p
  where s.kind = 'event' and s.chat_id = p.event_id and s.user_id = p.user_id
    and p.muted_until > now() and s.muted_until is distinct from p.muted_until;
insert into public.event_chat_prefs (event_id, user_id)
  select s.chat_id, s.user_id from public.chat_list_state s join public.events e on e.id = s.chat_id
  where s.kind = 'event' and (s.read_at is not null or s.muted_until > now())
  on conflict (event_id, user_id) do nothing;
update public.event_chat_prefs p set last_read_at = s.read_at, updated_at = now()
  from public.chat_list_state s
  where s.kind = 'event' and s.chat_id = p.event_id and s.user_id = p.user_id and s.read_at > coalesce(p.last_read_at, '-infinity');
update public.event_chat_prefs p set muted_until = s.muted_until, updated_at = now()
  from public.chat_list_state s
  where s.kind = 'event' and s.chat_id = p.event_id and s.user_id = p.user_id
    and s.muted_until > now() and (p.muted_until is null or p.muted_until <= now());

-- 2. -----------------------------------------------------------------------------------------------------------------
do $$ declare def text;
begin
  def := pg_get_functiondef('public.chat_list(boolean)'::regprocedure);
  if position('event_chat_level' in def) = 0 then
    if position($a$x.user_id = me) then 'none' else 'all' end,$a$ in def) = 0 then
      raise exception 'chat_list : ancre notify de la discussion d''événement introuvable';
    end if;
    execute replace(def, $a$x.user_id = me) then 'none' else 'all' end,$a$,
      $a$x.user_id = me) then 'none' else private.event_chat_level(ev.id, me) end,$a$);
  end if;
end $$;
