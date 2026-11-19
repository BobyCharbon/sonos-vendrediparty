-- PROD, retour arrière de groupes_graphisme (20261117100000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
CREATE OR REPLACE FUNCTION public.my_chats()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select coalesce(jsonb_agg(c order by (c->>'last_at') desc nulls last, c->>'name'), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', g.id, 'name', g.name, 'kind', 'group', 'system', g.system_key is not null,
      'member', private.in_group_now(g.id, auth.uid()),
      'admin', private.group_admin(g.id, auth.uid()),
      'creator', g.created_by = auth.uid(),
      'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
      'notify', coalesce(s.notify, 'mentions'),
      'last_at', last.created_at,
      'last', case when last.id is null then null
                   when last.deleted_at is not null then case when last.deleted_by_admin then 'Message supprimé par un admin' else 'Message supprimé' end
                   else coalesce((select display_name from public.profiles where id = last.user_id), '?') || ' : '
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or private.is_root(auth.uid()))
    union all
    select jsonb_build_object(
      'id', d.id, 'name', coalesce(nullif(btrim(o.display_name), ''), 'Profil à compléter'), 'kind', 'direct', 'system', false,
      'user_id', o.id, 'avatar_url', o.avatar_url,
      'member', true, 'admin', false, 'creator', false, 'members', 2,
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = o.id),
      'notify', coalesce(s.notify, 'all'),
      'last_at', last.created_at,
      'last', case when last.deleted_at is not null then 'Message supprimé'
                   else case when last.user_id = auth.uid() then 'Toi : ' else '' end
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.direct_messages m where m.chat_id = d.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.direct_chats d
    join public.profiles o on o.id = case when d.user_a = auth.uid() then d.user_b else d.user_a end
    left join public.direct_chat_settings s on s.chat_id = d.id and s.user_id = auth.uid()
    join lateral (select * from public.direct_messages m where m.chat_id = d.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)
  ) x;
$function$;

CREATE OR REPLACE FUNCTION public.my_group_invitations()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select coalesce(jsonb_agg(jsonb_build_object('id', i.id, 'group_id', g.id, 'group', g.name,
           'invited_by', (select display_name from public.profiles where id = i.invited_by), 'at', i.created_at)
           order by i.created_at desc), '[]'::jsonb)
  from private.group_invitations i join public.member_groups g on g.id = i.group_id
  where i.status = 'pending' and auth.uid() is not null
    and (i.user_id = auth.uid() or i.phone = (select private.digits(phone) from public.profiles where id = auth.uid()))
    and not exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid());
$function$;

drop trigger if exists member_groups_look_changed on public.member_groups;

drop trigger if exists member_groups_look_guard on public.member_groups;

delete from supabase_migrations.schema_migrations where version = '20261117100000';
commit;
