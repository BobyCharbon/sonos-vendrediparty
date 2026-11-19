-- Discussion d'un événement réservée à ceux qui viennent (décision de l'admin du 19.11) : seuls ceux qui ont répondu
-- Présent ou Peut-être, et l'organisation (créateur, co-organisateurs, admins), la voient dans Discussions, la lisent,
-- y écrivent et en reçoivent les notifications. Pas répondu ou Absent : rien (« ça ne pollue pas son espace ») ; dès
-- Présent / Peut-être, il la retrouve. @toutlemonde et les annonces ne touchent donc plus les invités sans réponse.
-- Fonctions partagées ÉTENDUES par ancre (pg_get_functiondef + replace), jamais réécrites. Additive et rejouable.
-- Aussi : chat_search (recherche « Messages » des Discussions, appelée par le web et l'iPhone mais jamais créée).

create or replace function private.event_chat_member(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select u is not null and (private.event_chat_staff_of(e, u)
    or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = u and r.status in ('yes', 'maybe')));
$$;
revoke all on function private.event_chat_member(uuid, uuid) from public, anon, authenticated;

create or replace function private.event_chat_open(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.event_chat_member(e, auth.uid());
$$;
revoke all on function private.event_chat_open(uuid) from public, anon;
grant execute on function private.event_chat_open(uuid) to authenticated;

-- Lire et écrire les messages (RLS).
drop policy if exists "lire messages" on public.messages;
create policy "lire messages" on public.messages for select
  using (public.can_see_event(event_id) and private.event_chat_open(event_id));

do $$ declare chk text;
begin
  select pg_get_expr(p.polwithcheck, p.polrelid) into chk from pg_policy p
  where p.polrelid = 'public.messages'::regclass and p.polname = 'écrire message';
  if chk is null then raise exception 'politique « écrire message » introuvable'; end if;
  if position('event_chat_open' in chk) = 0 then
    execute 'drop policy "écrire message" on public.messages';
    execute format('create policy "écrire message" on public.messages for insert with check ((%s) and private.event_chat_open(event_id))', chk);
  end if;
end $$;

-- Fonctions étendues par ancre.
do $$
declare f text; def text; anchor text; repl text;
  edits text[][] := array[
    -- Écrire : aussi Présent / Peut-être (ou organisation).
    ['private.event_chat_writes(uuid)', 'select public.can_participate(e)', 'select private.event_chat_open(e) and public.can_participate(e)'],
    -- Médias, recherche, réglages de la discussion : même accès.
    ['private.event_chat_require(uuid)', 'or not public.can_see_event(e) then', 'or not public.can_see_event(e) or not private.event_chat_open(e) then'],
    -- L'écran sait pourquoi la discussion est fermée.
    ['public.event_chat_state(uuid)', 'jsonb_build_object(''write_mode''', 'jsonb_build_object(''open'', private.event_chat_open(e), ''write_mode'''],
    -- Liste des Discussions et recherche « Événements ».
    ['public.chat_list(boolean)', 'and public.can_see_event(ev.id)', 'and public.can_see_event(ev.id) and private.event_chat_member(ev.id, me)'],
    ['public.chat_event_search(text)', 'and public.can_see_event(ev.id)', 'and public.can_see_event(ev.id) and private.event_chat_member(ev.id, me)'],
    -- Notifications : seulement ceux qui ont accès.
    ['public.notify_message()', 'where x not in (select user_id from event_mutes where event_id = ev.id)',
     'where x not in (select user_id from event_mutes where event_id = ev.id) and private.event_chat_member(ev.id, x)']];
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

-- Recherche « Messages » des Discussions (contrat §8) : mes conversations seulement (messages directs, groupes dont je
-- fais partie, discussions d'événement où j'ai accès), sans messages supprimés ni bloqués ; 30 au plus, récents d'abord.
create or replace function public.chat_search(q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); qq text := private.fold(btrim(coalesce(q, ''))); out jsonb;
begin
  if me is null or char_length(qq) < 2 then return '[]'::jsonb; end if;
  select coalesce(jsonb_agg(h.j order by h.at desc), '[]'::jsonb) into out from (
    select x.at, jsonb_build_object('kind', x.kind, 'id', x.id, 'title', x.title, 'message_id', x.mid,
                                    'excerpt', left(x.body, 160), 'at', x.at) as j
    from (
      select 'direct'::text kind, d.id, coalesce(nullif(btrim(o.display_name), ''), '?') title, m.id mid, m.body, m.created_at at
      from public.direct_chats d
      join public.direct_messages m on m.chat_id = d.id
      join public.profiles o on o.id = case when d.user_a = me then d.user_b else d.user_a end
      where (d.user_a = me or d.user_b = me) and m.deleted_at is null and not private.blocked_either(me, m.user_id)
        and position(qq in private.fold(coalesce(m.body, ''))) > 0
      union all
      select 'group', g.id, g.name, m.id, m.body, m.created_at
      from public.group_messages m join public.member_groups g on g.id = m.group_id
      where private.in_group_now(g.id, me) and m.deleted_at is null and not private.blocked_either(me, m.user_id)
        and position(qq in private.fold(coalesce(m.body, ''))) > 0
      union all
      select 'event', ev.id, ev.title, m.id, m.body, m.created_at
      from public.messages m join public.events ev on ev.id = m.event_id
      where m.deleted_at is null and not private.blocked_either(me, m.user_id)
        and position(qq in private.fold(coalesce(m.body, ''))) > 0
        and private.event_chat_member(ev.id, me) and public.can_see_event(ev.id)
    ) x
    order by x.at desc
    limit 30) h;
  return out;
end $$;
revoke all on function public.chat_search(text) from public, anon;
grant execute on function public.chat_search(text) to authenticated;
