-- Retour arrière de 20261123110000_reglages_groupe_admin : fonctions et règles remises telles qu'avant (lues sur la
-- base de TEST le 23.11, après les migrations du 22.11), fonctions nouvelles retirées. Les colonnes who_* et join_approval,
-- et la table private.group_join_requests restent (migration additive, sans effet une fois les fonctions retirées).
begin;
drop trigger if exists member_groups_rights_guard on public.member_groups;
drop policy if exists "écrire dans ses groupes" on public.group_messages;
create policy "écrire dans ses groupes" on public.group_messages for insert to authenticated
  with check ((user_id = (select auth.uid())) and private.in_group_now(group_id, (select auth.uid()))
              and private.is_account_active((select auth.uid())));
drop policy if exists "retirer du groupe" on public.member_group_members;
create policy "retirer du groupe" on public.member_group_members for delete to authenticated
  using (exists (select 1 from public.member_groups g where g.id = member_group_members.group_id and g.system_key is null
                 and (g.created_by = (select auth.uid()) or (select public.is_admin()))));

CREATE OR REPLACE FUNCTION private.manages_group(grp uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                 and (g.created_by = auth.uid() or public.is_admin()));
$function$;

CREATE OR REPLACE FUNCTION private.may_set_group_rules(grp uuid, uid uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select uid is not null and exists (select 1 from public.member_groups g where g.id = grp
    and (g.created_by = uid or private.is_root(uid) or private.rank_of(uid) >= private.role_rank('coadmin')));
$function$;

CREATE OR REPLACE FUNCTION private.guard_event_group()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if not private.may_use_group(new.group_id) then
    raise exception 'forbidden: tu ne peux inviter que les groupes dont tu fais partie' using errcode = '42501';
  end if;
  return new;
end $function$;

CREATE OR REPLACE FUNCTION private.guard_group_message()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare staff boolean;
begin
  if auth.uid() is not null then new.user_id := auth.uid(); end if;
  staff := private.group_staff(new.group_id, new.user_id);
  new.body := btrim(new.body);
  new.announcement := staff and new.body ~* '(^|[^[:alnum:]_])@annonce($|[^[:alnum:]_])';
  new.pinned := new.announcement;
  new.deleted_at := null;
  new.deleted_by_admin := false;
  new.edited_at := null;
  new.created_at := now();
  new.mention_all := (coalesce(new.mention_all, false)
                      and (staff or coalesce((select g.everyone_tag from public.member_groups g where g.id = new.group_id), 'all') = 'all'))
                     or new.announcement;
  new.mentions := coalesce((select array_agg(distinct m) from unnest(new.mentions) m
                            where private.in_group_now(new.group_id, m) and m <> new.user_id), '{}');
  if new.reply_to is not null and not exists (select 1 from public.group_messages r where r.id = new.reply_to and r.group_id = new.group_id) then
    new.reply_to := null;
  end if;
  if new.photo_path is not null and split_part(new.photo_path, '/', 1) <> new.group_id::text then
    raise exception 'Photo invalide';
  end if;
  if new.audio_path is not null and split_part(new.audio_path, '/', 1) <> new.group_id::text then
    raise exception 'Message vocal invalide';
  end if;
  return new;
end $function$;

CREATE OR REPLACE FUNCTION public.pin_group_message(msg uuid, pin boolean)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare m public.group_messages;
begin
  select * into m from public.group_messages where id = msg and deleted_at is null;
  if m.id is null or not (private.group_admin(m.group_id, auth.uid())
                          or (not pin and m.announcement and private.group_staff(m.group_id, auth.uid()))) then
    raise exception 'forbidden: réservé aux admins du groupe' using errcode = '42501';
  end if;
  update public.group_messages set pinned = pin, announcement = announcement and pin where id = msg;
end $function$;

CREATE OR REPLACE FUNCTION private.group_photo_can_write(obj text)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select auth.uid() is not null and private.manages_group(private.group_photo_group(obj));
$function$;

CREATE OR REPLACE FUNCTION public.join_group_by_link(token uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare grp uuid; author uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not private.identity_complete(auth.uid()) then
    raise exception 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) avant de rejoindre';
  end if;
  select id, coalesce(invite_token_by, created_by) into grp, author from public.member_groups
    where token is not null and invite_token = token and system_key is null;
  if grp is null then
    select id into grp from public.member_groups where id = private.claim_invite_link(token, 'group') and system_key is null;
  end if;
  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  if private.join_group(grp, auth.uid()) and author is not null then
    perform private.note_invite_join(auth.uid(), author, 'group', grp);
  end if;
  return grp;
end $function$;

CREATE OR REPLACE FUNCTION public.answer_group_invitation(inv uuid, accept boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare i private.group_invitations;
begin
  select * into i from private.group_invitations where id = inv and status = 'pending'
    and (user_id = auth.uid() or phone = (select private.digits(phone) from public.profiles where id = auth.uid()));
  if i.id is null then raise exception 'Cette invitation n''est plus valable'; end if;
  if accept then
    if not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
    perform private.join_group(i.group_id, auth.uid());
  else
    update private.group_invitations set status = 'declined' where id = inv;
  end if;
  return public.my_group_invitations();
end $function$;

CREATE OR REPLACE FUNCTION public.group_invite_info(token uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select jsonb_build_object('id', g.id, 'name', g.name,
    'creator', (select display_name from public.profiles where id = g.created_by),
    'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
    'joined', auth.uid() is not null and exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid()))
  from public.member_groups g
  where token is not null and (g.invite_token = token or g.id = private.invite_link_target(token, 'group'))
    and g.system_key is null and private.identity_complete(auth.uid());
$function$;

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
        'manage', private.manages_group(g.id), 'invite', private.may_invite_group(g.id),
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

create or replace function private.may_invite_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.manages_group(grp)
      or exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                   and private.is_account_active(auth.uid())
                   and (private.group_staff(grp, auth.uid())
                        or (g.members_invite and private.in_group_now(grp, auth.uid()))));
$$;

drop function if exists public.set_group_right(uuid, text, text);
drop function if exists public.set_group_role(uuid, uuid, text);
drop function if exists public.update_group_look(uuid, text, text, text);
drop function if exists public.set_group_photo(uuid, text);
drop function if exists public.group_my_rights(uuid);
drop function if exists public.set_group_join_approval(uuid, boolean);
drop function if exists public.decide_group_join(uuid, uuid, boolean);
drop function if exists public.transfer_group(uuid, uuid);
drop function if exists public.group_admin_panel(uuid);
drop function if exists private.request_group_join(uuid, uuid, text);
drop function if exists private.may_remove_member(uuid, uuid);
drop function if exists private.guard_group_rights();
drop function if exists private.group_may(uuid, uuid, text);
drop function if exists private.group_role(uuid, uuid);
delete from supabase_migrations.schema_migrations where version = '20261123110000';
commit;
