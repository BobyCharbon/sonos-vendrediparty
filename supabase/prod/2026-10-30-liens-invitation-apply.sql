-- PROD, invite_links (20261029170000). À appliquer SEULEMENT après « Ok prod ». Rejouable.
begin;
-- Liens et invitations (avis n°9 de l'admin, 29 octobre 2026) :
-- 1) Événement réservé à un groupe, avec un lien d'invitation partageable : qui l'ouvre crée son compte (ou se connecte)
--    et devient invité de CET événement seulement (event_invites.via_link, affiché en orange) ; les organisateurs
--    sont prévenus (« X a rejoint ton événement par le lien »). Le lien se renouvelle (l'ancien ne marche plus).
-- 2) Groupes : lien d'invitation (on clique, on crée son compte, on rejoint le groupe) et invitation par surnom ou
--    numéro, acceptée ou refusée dans les Réglages. Le groupe Vendredi Party (système) n'a ni lien ni invitation :
--    on y entre par le rôle Membre VIP.
-- Rejouable.

alter table public.events add column if not exists invite_token uuid unique;
alter table public.event_invites add column if not exists via_link boolean not null default false;
alter table public.member_groups add column if not exists invite_token uuid unique;

-- 1) Événements -----------------------------------------------------------------------------------------------------

create or replace function private.manages_event(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_organizer(e) or public.has_perm('events.manage_all');
$$;

-- Lien d'invitation d'un événement (organisateurs) ; renew : nouveau lien, l'ancien ne marche plus.
create or replace function public.event_invite_link(e uuid, renew boolean default false) returns uuid
language plpgsql security definer set search_path = '' as $$
declare token uuid;
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  update public.events set invite_token = gen_random_uuid() where id = e and (invite_token is null or renew)
    returning invite_token into token;
  return coalesce(token, (select invite_token from public.events where id = e));
end $$;

-- Ce que montre le lien, même sans compte : l'essentiel de l'événement et qui l'organise.
create or replace function public.invite_event(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address,
    'organizer', (select display_name from public.profiles where id = ev.created_by),
    'joined', auth.uid() is not null and (public.can_see_event(ev.id)
              or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = auth.uid())))
  from public.events ev
  where token is not null and ev.invite_token = token and ev.status in ('published', 'cancelled');
$$;

-- Rejoindre par le lien : invité de cet événement seulement ; les organisateurs sont prévenus (une fois).
create or replace function public.join_event_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare ev public.events; who text; u uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  select * into ev from public.events where token is not null and invite_token = token and status = 'published';
  if ev.id is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  insert into public.event_invites (event_id, user_id, via_group, via_link) values (ev.id, auth.uid(), false, true)
  on conflict (event_id, user_id) do nothing;
  if found then
    select display_name into who from public.profiles where id = auth.uid();
    for u in select x from (select ev.created_by x union select user_id from public.event_organizers where event_id = ev.id) o loop
      perform public.queue_notification(u, 'link_join', ev.id, ev.title,
        coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a rejoint ton événement par le lien',
        'link_join:' || ev.id || ':' || auth.uid());
    end loop;
  end if;
  return ev.id;
end $$;

-- 2) Groupes --------------------------------------------------------------------------------------------------------

create table if not exists private.group_invitations (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete cascade,
  phone text,
  invited_by uuid references public.profiles(id) on delete set null,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'declined')),
  created_at timestamptz not null default now(),
  check (user_id is not null or phone is not null)
);
create unique index if not exists group_invitations_pending_user on private.group_invitations (group_id, user_id)
  where status = 'pending' and user_id is not null;
create unique index if not exists group_invitations_pending_phone on private.group_invitations (group_id, phone)
  where status = 'pending' and phone is not null;
revoke all on private.group_invitations from public, anon, authenticated;

create or replace function private.manages_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                 and (g.created_by = auth.uid() or public.is_admin()));
$$;

create or replace function private.digits(t text) returns text
language sql immutable set search_path = '' as $$
  select nullif(regexp_replace(coalesce(t, ''), '\D', '', 'g'), '');
$$;

create or replace function private.join_group(grp uuid, member uuid) returns boolean
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text;
begin
  select * into g from public.member_groups where id = grp;
  insert into public.member_group_members (group_id, user_id) values (grp, member) on conflict do nothing;
  if not found then return false; end if;
  update private.group_invitations set status = 'accepted' where group_id = grp and status = 'pending'
    and (user_id = member or phone = (select private.digits(phone) from public.profiles where id = member));
  select display_name into who from public.profiles where id = member;
  if g.created_by is not null and g.created_by <> member then
    perform public.queue_notification(g.created_by, 'group_join', null, g.name,
      coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a rejoint ton groupe', 'group_join:' || grp || ':' || member);
  end if;
  return true;
end $$;

create or replace function public.group_invite_link(grp uuid, renew boolean default false) returns uuid
language plpgsql security definer set search_path = '' as $$
declare token uuid;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  update public.member_groups set invite_token = gen_random_uuid() where id = grp and (invite_token is null or renew)
    returning invite_token into token;
  return coalesce(token, (select invite_token from public.member_groups where id = grp));
end $$;

create or replace function public.group_invite_info(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', g.id, 'name', g.name,
    'creator', (select display_name from public.profiles where id = g.created_by),
    'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
    'joined', auth.uid() is not null and exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid()))
  from public.member_groups g
  where token is not null and g.invite_token = token and g.system_key is null;
$$;

create or replace function public.join_group_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  select id into grp from public.member_groups where token is not null and invite_token = token and system_key is null;
  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  perform private.join_group(grp, auth.uid());
  return grp;
end $$;

-- Inviter par surnom (compte) ou par numéro (compte ou pas encore inscrit : l'invitation l'attend).
create or replace function public.invite_to_group(grp uuid, member uuid default null, phone text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  select * into g from public.member_groups where id = grp;
  if target is null and number is not null then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  if target is not null and exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if target is not null then
    insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
    select display_name into me from public.profiles where id = auth.uid();
    perform public.queue_notification(target, 'group_invite', null, g.name,
      coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
      'group_invite:' || grp || ':' || target);
    return jsonb_build_object('invited', 'member');
  end if;
  insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
  return jsonb_build_object('invited', 'phone');
end $$;

-- Mes invitations en attente (par mon compte ou par mon numéro).
create or replace function public.my_group_invitations() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', i.id, 'group_id', g.id, 'group', g.name,
           'invited_by', (select display_name from public.profiles where id = i.invited_by), 'at', i.created_at)
           order by i.created_at desc), '[]'::jsonb)
  from private.group_invitations i join public.member_groups g on g.id = i.group_id
  where i.status = 'pending' and auth.uid() is not null
    and (i.user_id = auth.uid() or i.phone = (select private.digits(phone) from public.profiles where id = auth.uid()))
    and not exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid());
$$;

create or replace function public.answer_group_invitation(inv uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
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
end $$;

revoke all on function public.event_invite_link(uuid, boolean), public.join_event_by_link(uuid),
  public.group_invite_link(uuid, boolean), public.join_group_by_link(uuid), public.invite_to_group(uuid, uuid, text),
  public.my_group_invitations(), public.answer_group_invitation(uuid, boolean) from public, anon;
grant execute on function public.event_invite_link(uuid, boolean), public.join_event_by_link(uuid),
  public.group_invite_link(uuid, boolean), public.join_group_by_link(uuid), public.invite_to_group(uuid, uuid, text),
  public.my_group_invitations(), public.answer_group_invitation(uuid, boolean) to authenticated;
-- Ce que montre un lien avant connexion : lisible sans compte.
grant execute on function public.invite_event(uuid), public.group_invite_info(uuid) to anon, authenticated;
revoke all on function private.manages_event(uuid), private.manages_group(uuid), private.digits(text),
  private.join_group(uuid, uuid) from public, anon;
grant execute on function private.manages_event(uuid), private.manages_group(uuid), private.digits(text) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261029170000', 'invite_links')
  on conflict (version) do nothing;
commit;
