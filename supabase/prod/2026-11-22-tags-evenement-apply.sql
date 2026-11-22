-- Prod : 20261122131000_tags_evenement (avis f0e2fd838ab8, 22.11) : tout participant cite des @surnoms.
begin;
-- Citer des @surnoms dans la discussion d'un événement (avis f0e2fd838ab8, décision de l'admin du 22.11.2026).
-- @toutlemonde, @present et les annonces restent à l'organisation (private.event_chat_staff) : inchangé.
-- Tout participant cite un @surnom parmi :
--   - l'organisation (créateur, co-organisateurs) et les Présent / Peut-être ;
--   - événement NON public (sur invitation, groupe, Membres Vendredi Party) : aussi les invités qui n'ont pas encore répondu.
-- Jamais soi-même, jamais une personne en blocage avec l'auteur. La base décide : guard_message_change ne garde que ces
-- personnes dans `mentions` ; notify_message prévient aussi l'invité sans réponse cité (il n'a pas accès à la discussion,
-- règle du 19.11 : sa notification ne propose pas de répondre), selon ses réglages habituels (niveau, sourdine, blocage).
-- Fonctions partagées ÉTENDUES par ancre (pg_get_functiondef + replace), jamais réécrites. Additive et rejouable.

create or replace function private.event_chat_taggable_by(e uuid, author uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select distinct x.u from (
    select ev.created_by u from public.events ev where ev.id = e
    union select o.user_id from public.event_organizers o where o.event_id = e
    union select r.user_id from public.rsvps r where r.event_id = e and r.status in ('yes', 'maybe')
    union select i.user_id from public.event_invites i join public.events ev on ev.id = i.event_id
      where i.event_id = e and ev.visibility <> 'all'
        and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id)
  ) x
  join public.profiles p on p.id = x.u
  where x.u is distinct from author and p.status = 'active' and coalesce(p.display_name, '') <> ''
    and not private.blocked_either(author, x.u);
$$;
revoke all on function private.event_chat_taggable_by(uuid, uuid) from public, anon, authenticated;

-- Suggestions de l'@ : les personnes que JE peux citer (discussion ouverte pour moi seulement).
create or replace function public.event_chat_taggable(e uuid)
returns table (id uuid, display_name text, avatar_url text)
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.can_see_event(e) or not private.event_chat_open(e) then
    raise exception 'Cette discussion n''est pas accessible.' using errcode = '42501';
  end if;
  return query select p.id, p.display_name, p.avatar_url
    from private.event_chat_taggable_by(e, auth.uid()) t(u) join public.profiles p on p.id = t.u;
end $$;
revoke all on function public.event_chat_taggable(uuid) from public, anon;
grant execute on function public.event_chat_taggable(uuid) to authenticated;

do $$
declare f text; def text; anchor text; repl text;
  edits text[][] := array[
    -- Écrire : seules les personnes qu'on peut citer restent dans `mentions`.
    ['private.guard_message_change()',
     '    if new.photo_path is not null and split_part(new.photo_path, ''/'', 1) <> new.event_id::text then',
     '    new.mentions := coalesce((select array_agg(m) from unnest(new.mentions) m'
       || ' where m in (select private.event_chat_taggable_by(new.event_id, new.user_id))), ''{}'');' || chr(10)
       || '    if new.photo_path is not null and split_part(new.photo_path, ''/'', 1) <> new.event_id::text then'],
    -- Notifications : aussi la personne citée (déjà filtrée par la garde).
    ['public.notify_message()', 'and private.event_chat_member(ev.id, x)',
     'and (private.event_chat_member(ev.id, x) or x = any (new.mentions))'],
    -- Répondre depuis la notification : seulement qui a accès à la discussion.
    ['public.notify_message()', '''can_reply'', coalesce(ev.chat_write',
     '''can_reply'', private.event_chat_member(ev.id, u) and coalesce(ev.chat_write']];
  i int;
begin
  for i in 1 .. array_length(edits, 1) loop
    f := edits[i][1]; anchor := edits[i][2]; repl := edits[i][3];
    def := pg_get_functiondef(f::regprocedure);
    if position(repl in def) > 0 then continue; end if;  -- déjà fait (rejoué)
    if position(anchor in def) = 0 then raise exception 'ancre introuvable dans % : %', f, anchor; end if;
    if (length(def) - length(replace(def, anchor, ''))) / length(anchor) <> 1 then
      raise exception 'ancre non unique dans % : %', f, anchor;
    end if;
    execute replace(def, anchor, repl);
  end loop;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261122131000', 'tags_evenement') on conflict do nothing;
commit;
