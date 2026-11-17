-- Groupes (17.11, recette iPhone) : un événement qui RÉUNIT ses invités dans un groupe (events.guest_group, migration
-- 20261117110000) compte parmi les événements du groupe, comme un événement réservé au groupe (event_groups approuvé) :
-- page du groupe (« Prochains événements ») et ligne de la liste (« prochain événement »). can_see_event reste exigé :
-- un membre du groupe non invité à un événement « sur invitation » ne le voit toujours pas. Additive et rejouable.

create or replace function private.group_event_ids(grp uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select eg.event_id from public.event_groups eg where eg.group_id = grp and eg.status = 'approved'
  union
  select e.id from public.events e where e.guest_group = grp;
$$;
revoke all on function private.group_event_ids(uuid) from public, anon, authenticated;

create or replace function public.my_groups_overview() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(x.g order by x.sys desc, x.last_at desc nulls last, x.name), '[]'::jsonb) from (
    select g.system_key is not null as sys, coalesce(last.created_at, g.created_at) as last_at, g.name,
      jsonb_build_object(
        'id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color, 'system', g.system_key is not null,
        'creator', coalesce(g.created_by = auth.uid(), false),
        'manage', private.manages_group(g.id),
        'member', private.in_group_now(g.id, auth.uid()),
        'created_by_name', (select display_name from public.profiles where id = g.created_by),
        'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
        'faces', (select coalesce(jsonb_agg(jsonb_build_object('id', f.id, 'name', f.display_name, 'avatar_url', f.avatar_url)), '[]'::jsonb)
                  from (select p.id, p.display_name, p.avatar_url from public.member_group_members m
                        join public.profiles p on p.id = m.user_id
                        where m.group_id = g.id and p.status = 'active'
                        order by (p.id = auth.uid()), (p.avatar_url is null), m.added_at desc nulls last limit 5) f),
        'last', case when last.id is null then null
                     when last.deleted_at is not null then 'Message supprimé'
                     when last.body <> '' then left(last.body, 80)
                     when last.audio_path is not null then '🎤 Message vocal'
                     else '📷 Photo' end,
        'last_by', case when last.id is null or last.deleted_at is not null then null
                        when last.user_id = auth.uid() then 'Toi'
                        else (select display_name from public.profiles where id = last.user_id) end,
        'last_at', last.created_at,
        'unread', case when private.in_group_now(g.id, auth.uid()) then
                    (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                       and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity')
                       and not exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = m.user_id))
                  else 0 end,
        'next_event', (select jsonb_build_object('id', e.id, 'title', e.title, 'starts_at', e.starts_at, 'date_mode', e.date_mode)
                       from public.events e
                       where e.id in (select private.group_event_ids(g.id)) and e.status = 'published'
                         and (e.date_mode = 'poll' or e.starts_at > now() - interval '6 hours')
                         and public.can_see_event(e.id)
                       order by e.starts_at nulls last limit 1)
      ) as g
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id
                         and not exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = m.user_id)
                       order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or g.created_by = auth.uid())
  ) x;
$$;

create or replace function public.group_events(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', e.id, 'starts_at', e.starts_at, 'date_mode', e.date_mode,
           'upcoming', e.date_mode = 'poll' or e.starts_at is null or e.starts_at > now() - interval '6 hours')
         order by (e.date_mode = 'poll' or e.starts_at is null or e.starts_at > now() - interval '6 hours') desc,
                  case when e.starts_at > now() - interval '6 hours' then e.starts_at end asc nulls last,
                  e.starts_at desc nulls last), '[]'::jsonb)
  from public.events e
  where e.id in (select private.group_event_ids(grp)) and e.status in ('published', 'cancelled')
    and auth.uid() is not null
    and (private.in_group_now(grp, auth.uid()) or private.sees_all_groups())
    and public.can_see_event(e.id);
$$;

revoke all on function public.my_groups_overview(), public.group_events(uuid) from public, anon;
grant execute on function public.my_groups_overview(), public.group_events(uuid) to authenticated;
notify pgrst, 'reload schema';
