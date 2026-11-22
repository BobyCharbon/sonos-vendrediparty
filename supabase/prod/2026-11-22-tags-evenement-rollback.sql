-- Retour arrière de 20261122131000 : garde et notifications d'avant (ancres inversées), fonctions retirées.
begin;
do $$
declare f text; def text; anchor text; repl text;
  edits text[][] := array[
    ['private.guard_message_change()',
     '    new.mentions := coalesce((select array_agg(m) from unnest(new.mentions) m'
       || ' where m in (select private.event_chat_taggable_by(new.event_id, new.user_id))), ''{}'');' || chr(10), ''],
    ['public.notify_message()', 'and (private.event_chat_member(ev.id, x) or x = any (new.mentions))',
     'and private.event_chat_member(ev.id, x)'],
    ['public.notify_message()', '''can_reply'', private.event_chat_member(ev.id, u) and coalesce(ev.chat_write',
     '''can_reply'', coalesce(ev.chat_write']];
  i int;
begin
  for i in 1 .. array_length(edits, 1) loop
    f := edits[i][1]; anchor := edits[i][2]; repl := edits[i][3];
    def := pg_get_functiondef(f::regprocedure);
    if position(anchor in def) > 0 then execute replace(def, anchor, repl); end if;
  end loop;
end $$;
drop function if exists public.event_chat_taggable(uuid);
drop function if exists private.event_chat_taggable_by(uuid, uuid);
delete from supabase_migrations.schema_migrations where version = '20261122131000';
commit;
