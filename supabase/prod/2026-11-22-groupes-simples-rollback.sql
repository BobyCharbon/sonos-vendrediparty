-- Retour arrière de 20261122134000 : fonctions remises telles qu'en prod avant la migration (lues le 22.11),
-- recherche et réglage retirés (la colonne members_invite reste, sans effet : migration additive).
begin;
CREATE OR REPLACE FUNCTION public.invite_to_group(grp uuid, member uuid DEFAULT NULL::uuid, phone text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text; by_phone boolean;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  delete from private.group_invite_log where user_id = auth.uid() and at < now() - interval '2 days';
  if (select count(*) from private.group_invite_log where user_id = auth.uid() and at > now() - interval '1 day') >= 30 then
    raise exception 'limit: tu as envoyé beaucoup d''invitations aujourd''hui, réessaie demain' using errcode = '54000';
  end if;
  insert into private.group_invite_log (user_id) values (auth.uid());
  select * into g from public.member_groups where id = grp;
  by_phone := target is null;
  if by_phone then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
    if target is null then
      insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
      return jsonb_build_object('invited', 'phone');
    end if;
    -- Un compte a ce numéro : invité seulement s'il passerait par son identifiant ; sinon rien, et la même réponse
    -- (on ne révèle jamais qu'un numéro est inscrit, ni un blocage).
    if not exists (select 1 from public.member_group_members where group_id = grp and user_id = target)
       and not private.blocked_either(target, auth.uid()) and not private.blocked_either(target, g.created_by)
       and private.invite_link(auth.uid(), target) = 'direct' then
      insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
      select display_name into me from public.profiles where id = auth.uid();
      perform public.queue_notification(target, 'group_invite', null, g.name,
        coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
        'group_invite:' || grp || ':' || target);
    end if;
    return jsonb_build_object('invited', 'phone');
  end if;
  if exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if private.blocked_either(target, auth.uid()) or private.blocked_either(target, g.created_by) then
    raise exception 'blocked: Tu ne peux pas inviter cette personne.' using errcode = '42501';
  end if;
  if private.invite_link(auth.uid(), target) is distinct from 'direct' then
    raise exception 'link_required: tu ne peux inviter que les personnes que tu connais déjà (groupe, soirée privée ou conversation) : écris-lui d''abord.'
      using errcode = '42501';
  end if;
  insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
  select display_name into me from public.profiles where id = auth.uid();
  perform public.queue_notification(target, 'group_invite', null, g.name,
    coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
    'group_invite:' || grp || ':' || target);
  return jsonb_build_object('invited', 'member');
end $function$;
CREATE OR REPLACE FUNCTION public.group_invite_link(grp uuid, renew boolean DEFAULT false)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare token uuid;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  update public.member_groups set invite_token = gen_random_uuid() where id = grp and (invite_token is null or renew)
    returning invite_token into token;
  return coalesce(token, (select invite_token from public.member_groups where id = grp));
end $function$;
CREATE OR REPLACE FUNCTION public.my_groups_overview()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select coalesce(jsonb_agg(x.g order by x.sys desc, x.last_at desc nulls last, x.name), '[]'::jsonb) from (
    select g.system_key is not null as sys, coalesce(last.created_at, g.created_at) as last_at, g.name,
      jsonb_build_object(
        'id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color, 'photo', g.photo_path, 'system', g.system_key is not null,
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
$function$;
CREATE OR REPLACE FUNCTION public.group_invite_suggestions(grp uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid();
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  return (
    with mine as (select id from private.met_events(me) m(id)),
    pairs as (
      select r.event_id, r.user_id from public.rsvps r where r.event_id in (select id from mine) and r.status in ('yes', 'maybe')
      union select o.event_id, o.user_id from public.event_organizers o where o.event_id in (select id from mine)
      union select e.id, e.created_by from public.events e where e.id in (select id from mine) and e.created_by is not null
    )
    select coalesce(jsonb_agg(jsonb_build_object('id', x.id, 'display_name', x.display_name, 'avatar_url', x.avatar_url,
             'together', x.together, 'last_title', x.last_title, 'invited', x.invited) order by x.together desc, x.last_at desc nulls last), '[]'::jsonb)
    from (
      select p.id, p.display_name, p.avatar_url, count(distinct e.id) as together, max(e.starts_at) as last_at,
        (array_agg(e.title order by e.starts_at desc nulls last))[1] as last_title,
        exists (select 1 from private.group_invitations i where i.group_id = grp and i.user_id = p.id and i.status = 'pending') as invited
      from pairs
      join public.events e on e.id = pairs.event_id and e.status = 'published'
      join public.profiles p on p.id = pairs.user_id and p.id <> me and p.status = 'active'
      where not exists (select 1 from public.member_group_members m where m.group_id = grp and m.user_id = p.id)
        and not private.dm_blocked(me, p.id)
      group by p.id, p.display_name, p.avatar_url
      order by count(distinct e.id) desc, max(e.starts_at) desc nulls last
      limit 40
    ) x
  );
end $function$;
drop trigger if exists member_groups_members_invite on public.member_groups;
drop function if exists private.guard_group_members_invite();
drop function if exists public.set_group_members_invite(uuid, boolean);
drop function if exists public.group_people_search(uuid, text);
drop function if exists private.search_phone(text);
drop function if exists private.may_invite_group(uuid);
drop table if exists private.group_search_log;
delete from supabase_migrations.schema_migrations where version = '20261122134000';
commit;
