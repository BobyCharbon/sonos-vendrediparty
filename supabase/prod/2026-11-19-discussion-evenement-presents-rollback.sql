-- PROD, retour arrière de discussion_evenement_presents (20261119120000) : la discussion d'un événement redevient lisible
-- par tous ceux qui voient l'événement (politiques et fonctions remises par ancre inverse). chat_search et les fonctions
-- private.event_chat_member / event_chat_open restent (sans effet). Tout ou rien.
begin;
drop policy if exists "lire messages" on public.messages;
create policy "lire messages" on public.messages for select using (public.can_see_event(event_id));

do $$ declare chk text;
begin
  select pg_get_expr(p.polwithcheck, p.polrelid) into chk from pg_policy p
  where p.polrelid = 'public.messages'::regclass and p.polname = 'écrire message';
  if chk is not null and position(' AND private.event_chat_open(event_id)' in chk) > 0 then
    execute 'drop policy "écrire message" on public.messages';
    execute format('create policy "écrire message" on public.messages for insert with check (%s)',
                   replace(chk, ' AND private.event_chat_open(event_id)', ''));
  end if;
end $$;

do $$
declare def text; i int;
  edits text[][] := array[
    ['private.event_chat_writes(uuid)', 'select public.can_participate(e)', 'select private.event_chat_open(e) and public.can_participate(e)'],
    ['private.event_chat_require(uuid)', 'or not public.can_see_event(e) then', 'or not public.can_see_event(e) or not private.event_chat_open(e) then'],
    ['public.event_chat_state(uuid)', 'jsonb_build_object(''write_mode''', 'jsonb_build_object(''open'', private.event_chat_open(e), ''write_mode'''],
    ['public.chat_list(boolean)', 'and public.can_see_event(ev.id)', 'and public.can_see_event(ev.id) and private.event_chat_member(ev.id, me)'],
    ['public.chat_event_search(text)', 'and public.can_see_event(ev.id)', 'and public.can_see_event(ev.id) and private.event_chat_member(ev.id, me)'],
    ['public.notify_message()', 'where x not in (select user_id from event_mutes where event_id = ev.id)',
     'where x not in (select user_id from event_mutes where event_id = ev.id) and private.event_chat_member(ev.id, x)']];
begin
  for i in 1 .. array_length(edits, 1) loop
    def := pg_get_functiondef(edits[i][1]::regprocedure);
    if position(edits[i][3] in def) > 0 then execute replace(def, edits[i][3], edits[i][2]); end if;
  end loop;
end $$;

delete from supabase_migrations.schema_migrations where version = '20261119120000';
commit;
