-- Réglages du groupe pour son admin (demande de l'admin du site du 23.11.2026 : « un panel où il peut changer les droits
-- de son groupe »). Décisions du 22.11 inchangées : chacun est libre dans son groupe, le créateur en est l'admin ; un
-- événement de groupe ne passe jamais par la validation du site ; un événement PUBLIC passe toujours par l'équipe.
-- Membres Vendredi Party (system_key) n'a JAMAIS ces réglages. Les admins du site gardent l'accès à tout groupe (aider).
--
-- 1. Rôles dans le groupe : Admin du groupe (le créateur, created_by), Co-admins (table group_admins, existante),
--    Organisateurs (group_organizers, existante), Membres. Co-admin = comme l'admin (réglages, rôles, membres, lien,
--    accord des nouveaux) SAUF supprimer le groupe et le transmettre. private.manages_group et may_set_group_rules
--    comptent maintenant les co-admins du groupe. set_group_role(grp, membre, 'member' | 'organizer' | 'coadmin').
-- 2. « Qui peut… » : une colonne par droit (who_*), 'admins' (admin + co-admins) | 'staff' (+ organisateurs) |
--    'members' (tout membre). Par défaut = le comportement d'avant :
--      who_invite   ← members_invite (true → members, false → staff), gardés en accord par la base (anciennes apps) ;
--      who_events   'members' (+ events_need_approval inchangé : « à valider par un admin », les organisateurs publient) ;
--      who_announce ← everyone_tag (all → members, staff → staff) : @tout ; @annonce reste aux organisateurs et admins ;
--      who_write    'members' ; who_pin 'admins' ; who_edit 'admins' (nom, emoji, couleur, photo) ; who_remove 'admins'.
--    La BASE fait respecter chaque droit : invitations (may_invite_group), événement du groupe (guard_event_group),
--    @tout / @annonce (guard_group_message), écrire (politique d'insertion de group_messages), épingler
--    (pin_group_message), nom / emoji / photo (update_group_look, set_group_photo, compartiment group-photos),
--    retirer (politique de suppression de member_group_members → private.may_remove_member).
--    set_group_right(grp, droit, niveau) : qui règle le groupe (may_set_group_rules), jamais Membres Vendredi Party.
-- 3. Entrée : « Accepter chaque nouveau membre » (join_approval, éteint par défaut). Allumé : qui ouvre le lien du
--    groupe (ou un lien unique / une invitation d'un simple membre) attend l'accord de l'admin ou d'un co-admin
--    (private.group_join_requests, decide_group_join). Une invitation de l'admin ou d'un co-admin fait entrer direct.
-- 4. transfer_group(grp, membre) : le créateur (ou un admin du site) transmet le groupe ; l'ancien créateur reste co-admin.
-- 5. group_admin_panel(grp) : tout l'écran des réglages en une lecture ; group_my_rights(grp) : mes droits (pages, chat).
-- Purement additive et rejouable.

-- 1. Colonnes --------------------------------------------------------------------------------------------------------------
alter table public.member_groups add column if not exists who_invite text;
alter table public.member_groups add column if not exists who_events text not null default 'members';
alter table public.member_groups add column if not exists who_announce text;
alter table public.member_groups add column if not exists who_write text not null default 'members';
alter table public.member_groups add column if not exists who_pin text not null default 'admins';
alter table public.member_groups add column if not exists who_edit text not null default 'admins';
alter table public.member_groups add column if not exists who_remove text not null default 'admins';
alter table public.member_groups add column if not exists join_approval boolean not null default false;
-- Reprise de l'existant (rejouable : seulement les lignes encore vides).
update public.member_groups set who_invite = case when members_invite is false then 'staff' else 'members' end where who_invite is null;
update public.member_groups set who_announce = case when everyone_tag = 'staff' then 'staff' else 'members' end where who_announce is null;
alter table public.member_groups alter column who_invite set default 'members';
alter table public.member_groups alter column who_invite set not null;
alter table public.member_groups alter column who_announce set default 'members';
alter table public.member_groups alter column who_announce set not null;
do $$
declare c text;
begin
  foreach c in array array['who_invite', 'who_events', 'who_announce', 'who_write', 'who_pin', 'who_edit', 'who_remove'] loop
    if not exists (select 1 from pg_constraint where conname = 'member_groups_' || c || '_check') then
      execute format('alter table public.member_groups add constraint %I check (%I in (''admins'', ''staff'', ''members''))',
                     'member_groups_' || c || '_check', c);
    end if;
  end loop;
end $$;

create table if not exists private.group_join_requests (
  group_id uuid not null references public.member_groups (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  via text not null default 'link',
  created_at timestamptz not null default now(),
  primary key (group_id, user_id)
);
revoke all on private.group_join_requests from public, anon, authenticated;

-- 2. Qui gère : créateur, admin du site, co-admins du groupe -----------------------------------------------------------------
create or replace function private.manages_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                 and (g.created_by = auth.uid() or public.is_admin()
                      or (private.in_group_now(grp, auth.uid())
                          and exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = auth.uid()))));
$$;

create or replace function private.may_set_group_rules(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and exists (select 1 from public.member_groups g where g.id = grp
    and (g.created_by = uid or private.is_root(uid) or private.rank_of(uid) >= private.role_rank('coadmin')
         or (g.system_key is null and private.in_group_now(grp, uid)
             and exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid))));
$$;

-- Rôle d'une personne dans le groupe : 'creator' | 'coadmin' | 'organizer' | 'member' | null (pas dedans).
create or replace function private.group_role(grp uuid, uid uuid) returns text
language sql stable security definer set search_path = '' as $$
  select case
    when uid is null then null
    when exists (select 1 from public.member_groups g where g.id = grp and g.created_by = uid) then 'creator'
    when not private.in_group_now(grp, uid) then null
    when exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid) then 'coadmin'
    when exists (select 1 from public.group_organizers o where o.group_id = grp and o.user_id = uid) then 'organizer'
    else 'member' end;
$$;
revoke all on function private.group_role(uuid, uuid) from public, anon, authenticated;

-- Le droit « r » de la personne uid dans le groupe, d'après son niveau (who_*). Admins : admin du groupe (créateur,
-- co-admins, co-admins du site membres, root hors groupe privé) ou, pour soi-même, qui gère le groupe (admin du site).
create or replace function private.group_may(grp uuid, uid uuid, r text) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and coalesce((
    select case lvl
      when 'members' then private.in_group_now(grp, uid) or adm
      when 'staff' then adm or (private.in_group_now(grp, uid)
                                and exists (select 1 from public.group_organizers o where o.group_id = grp and o.user_id = uid))
      else adm end
    from (select case r when 'invite' then g.who_invite when 'events' then g.who_events when 'announce' then g.who_announce
                        when 'write' then g.who_write when 'pin' then g.who_pin when 'edit' then g.who_edit
                        when 'remove' then g.who_remove end as lvl,
                 private.group_admin(grp, uid) or (uid = auth.uid() and private.manages_group(grp)) as adm
          from public.member_groups g where g.id = grp) x), false);
$$;
revoke all on function private.group_may(uuid, uuid, text) from public, anon;
grant execute on function private.group_may(uuid, uuid, text) to authenticated;  -- politique d'insertion de group_messages

-- Inviter (et partager le lien du groupe) : who_invite (avant : members_invite).
create or replace function private.may_invite_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.manages_group(grp)
      or exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                   and private.is_account_active(auth.uid()) and private.group_may(grp, auth.uid(), 'invite'));
$$;

-- Garde des colonnes who_* / join_approval (écriture directe dans la table) + accord avec les anciennes colonnes
-- members_invite / everyone_tag (anciennes apps). Nommé « rights » : après les autres gardes de member_groups.
create or replace function private.guard_group_rights() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.system_key is not null then  -- Membres Vendredi Party : jamais ces réglages (anciennes colonnes inchangées)
    new.who_invite := 'members'; new.who_events := 'members'; new.who_announce := 'members'; new.who_write := 'members';
    new.who_pin := 'admins'; new.who_edit := 'admins'; new.who_remove := 'admins'; new.join_approval := false;
    return new;
  end if;
  if tg_op = 'UPDATE' then
    if auth.uid() is not null
       and not private.may_set_group_rules(old.id, auth.uid())
       and (row(new.who_invite, new.who_events, new.who_announce, new.who_write, new.who_pin, new.who_edit, new.who_remove, new.join_approval)
            is distinct from row(old.who_invite, old.who_events, old.who_announce, old.who_write, old.who_pin, old.who_edit, old.who_remove, old.join_approval)) then
      new.who_invite := old.who_invite; new.who_events := old.who_events; new.who_announce := old.who_announce;
      new.who_write := old.who_write; new.who_pin := old.who_pin; new.who_edit := old.who_edit; new.who_remove := old.who_remove;
      new.join_approval := old.join_approval;
    end if;
    -- Ancienne colonne changée (set_group_members_invite, set_group_everyone_tag) → le droit suit ; sinon l'inverse.
    if new.members_invite is distinct from old.members_invite and new.who_invite is not distinct from old.who_invite then
      new.who_invite := case when new.members_invite then 'members' when old.who_invite = 'admins' then 'admins' else 'staff' end;
    end if;
    if new.everyone_tag is distinct from old.everyone_tag and new.who_announce is not distinct from old.who_announce then
      new.who_announce := case when new.everyone_tag = 'all' then 'members' when old.who_announce = 'admins' then 'admins' else 'staff' end;
    end if;
  end if;
  new.members_invite := new.who_invite = 'members';
  new.everyone_tag := case when new.who_announce = 'members' then 'all' else 'staff' end;
  return new;
end $$;
revoke all on function private.guard_group_rights() from public, anon, authenticated;
drop trigger if exists member_groups_rights_guard on public.member_groups;
create trigger member_groups_rights_guard before insert or update on public.member_groups
  for each row execute function private.guard_group_rights();

create or replace function public.set_group_right(grp uuid, k text, level text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if k is null or k not in ('invite', 'events', 'announce', 'write', 'pin', 'edit', 'remove') then raise exception 'Droit inconnu'; end if;
  if level is null or level not in ('admins', 'staff', 'members') then raise exception 'Choix inconnu'; end if;
  if exists (select 1 from public.member_groups where id = grp and system_key is not null) then
    raise exception 'forbidden: pas de réglage pour Membres Vendredi Party' using errcode = '42501';
  end if;
  if not private.may_set_group_rules(grp, auth.uid()) then
    raise exception 'forbidden: réservé à l''admin et aux co-admins du groupe' using errcode = '42501';
  end if;
  execute format('update public.member_groups set %I = $1 where id = $2', 'who_' || k) using level, grp;
end $$;
revoke all on function public.set_group_right(uuid, text, text) from public, anon;
grant execute on function public.set_group_right(uuid, text, text) to authenticated;

-- Rôle d'un membre : Membre / Organisateur / Co-admin. Qui gère le groupe ; jamais le créateur (il reste admin).
create or replace function public.set_group_role(grp uuid, member uuid, role text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if role is null or role not in ('member', 'organizer', 'coadmin') then raise exception 'Rôle inconnu'; end if;
  if exists (select 1 from public.member_groups where id = grp and system_key is not null) then
    raise exception 'forbidden: pas de rôles dans Membres Vendredi Party' using errcode = '42501';
  end if;
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé à l''admin et aux co-admins du groupe' using errcode = '42501';
  end if;
  if exists (select 1 from public.member_groups where id = grp and created_by = member) then
    raise exception 'forbidden: le créateur reste toujours admin du groupe' using errcode = '42501';
  end if;
  if not private.in_group_now(grp, member) then raise exception 'Cette personne n''est pas dans le groupe'; end if;
  delete from public.group_admins where group_id = grp and user_id = member and role <> 'coadmin';
  delete from public.group_organizers where group_id = grp and user_id = member and role <> 'organizer';
  if role = 'coadmin' then
    insert into public.group_admins (group_id, user_id) values (grp, member) on conflict do nothing;
  elsif role = 'organizer' then
    insert into public.group_organizers (group_id, user_id) values (grp, member) on conflict do nothing;
  end if;
end $$;
revoke all on function public.set_group_role(uuid, uuid, text) from public, anon;
grant execute on function public.set_group_role(uuid, uuid, text) to authenticated;

-- 3. Faire respecter chaque droit -----------------------------------------------------------------------------------------
-- Événement pour le groupe : who_events (en plus d'en faire partie). « À valider » : events_need_approval, inchangé.
create or replace function private.guard_event_group() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if not private.may_use_group(new.group_id) then
    raise exception 'forbidden: tu ne peux inviter que les groupes dont tu fais partie' using errcode = '42501';
  end if;
  if auth.uid() is not null and not public.is_admin()
     and exists (select 1 from public.member_groups g where g.id = new.group_id and g.system_key is null)
     and not private.group_may(new.group_id, auth.uid(), 'events') then
    raise exception 'forbidden: dans ce groupe, seuls % créent un événement pour le groupe',
      case (select who_events from public.member_groups where id = new.group_id)
        when 'admins' then 'l''admin et les co-admins' else 'les organisateurs et les admins' end
      using errcode = '42501';
  end if;
  return new;
end $$;

-- @tout (mention_all) : who_announce ; @annonce : organisateurs et admins, et seulement si who_announce le permet.
create or replace function private.guard_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare staff boolean; may_all boolean;
begin
  if auth.uid() is not null then new.user_id := auth.uid(); end if;
  staff := private.group_staff(new.group_id, new.user_id);
  may_all := private.group_may(new.group_id, new.user_id, 'announce');
  new.body := btrim(new.body);
  new.announcement := staff and may_all and new.body ~* '(^|[^[:alnum:]_])@annonce($|[^[:alnum:]_])';
  new.pinned := new.announcement;
  new.deleted_at := null;
  new.deleted_by_admin := false;
  new.edited_at := null;
  new.created_at := now();
  new.mention_all := (coalesce(new.mention_all, false) and may_all) or new.announcement;
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
end $$;

-- Écrire dans la discussion : who_write.
drop policy if exists "écrire dans ses groupes" on public.group_messages;
create policy "écrire dans ses groupes" on public.group_messages for insert to authenticated
  with check ((user_id = (select auth.uid())) and private.in_group_now(group_id, (select auth.uid()))
              and private.is_account_active((select auth.uid()))
              and private.group_may(group_id, (select auth.uid()), 'write'));

-- Épingler : who_pin (un organisateur retire toujours une annonce).
create or replace function public.pin_group_message(msg uuid, pin boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.group_messages;
begin
  select * into m from public.group_messages where id = msg and deleted_at is null;
  if m.id is null or not (private.group_admin(m.group_id, auth.uid()) or private.group_may(m.group_id, auth.uid(), 'pin')
                          or (not pin and m.announcement and private.group_staff(m.group_id, auth.uid()))) then
    raise exception 'forbidden: dans ce groupe, tu ne peux pas épingler de message' using errcode = '42501';
  end if;
  update public.group_messages set pinned = pin, announcement = announcement and pin where id = msg;
end $$;

-- Nom, emoji, couleur, photo : who_edit (les écrans passent par ces fonctions ; l'écriture directe reste au créateur et
-- aux admins du site, politique « modifier son groupe » inchangée). Filtre du nom et CGU : déclencheurs existants.
create or replace function public.update_group_look(grp uuid, group_name text, group_emoji text, group_color text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from public.member_groups where id = grp and system_key is not null) then
    raise exception 'forbidden: Membres Vendredi Party ne se renomme pas' using errcode = '42501';
  end if;
  if not private.group_may(grp, auth.uid(), 'edit') or not private.is_account_active(auth.uid()) then
    raise exception 'forbidden: dans ce groupe, tu ne peux pas changer le nom, l''emoji ni la photo' using errcode = '42501';
  end if;
  if nullif(btrim(coalesce(group_name, '')), '') is null then raise exception 'Donne un nom au groupe'; end if;
  update public.member_groups set name = left(btrim(group_name), 60), emoji = coalesce(group_emoji, emoji),
         color = coalesce(group_color, color) where id = grp;
end $$;
revoke all on function public.update_group_look(uuid, text, text, text) from public, anon;
grant execute on function public.update_group_look(uuid, text, text, text) to authenticated;

create or replace function public.set_group_photo(grp uuid, path text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from public.member_groups where id = grp and system_key is not null) then
    raise exception 'forbidden: Membres Vendredi Party n''a pas de photo' using errcode = '42501';
  end if;
  if not private.group_may(grp, auth.uid(), 'edit') or not private.is_account_active(auth.uid()) then
    raise exception 'forbidden: dans ce groupe, tu ne peux pas changer le nom, l''emoji ni la photo' using errcode = '42501';
  end if;
  update public.member_groups set photo_path = nullif(path, '') where id = grp;
end $$;
revoke all on function public.set_group_photo(uuid, text) from public, anon;
grant execute on function public.set_group_photo(uuid, text) to authenticated;

create or replace function private.group_photo_can_write(obj text) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (private.manages_group(private.group_photo_group(obj))
                                      or private.group_may(private.group_photo_group(obj), auth.uid(), 'edit'));
$$;

-- Retirer un membre : qui gère le groupe (jamais le créateur), ou who_remove pour un simple membre.
create or replace function private.may_remove_member(grp uuid, target uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and target <> auth.uid() and exists (
    select 1 from public.member_groups g where g.id = grp and g.system_key is null and g.created_by is distinct from target
      and (private.manages_group(grp)
           or (private.group_may(grp, auth.uid(), 'remove') and private.group_role(grp, target) = 'member')));
$$;
revoke all on function private.may_remove_member(uuid, uuid) from public, anon;
grant execute on function private.may_remove_member(uuid, uuid) to authenticated;
drop policy if exists "retirer du groupe" on public.member_group_members;
create policy "retirer du groupe" on public.member_group_members for delete to authenticated
  using (private.may_remove_member(group_id, user_id));

-- Mes droits dans le groupe (pages, discussion) : la base décide, les écrans suivent.
create or replace function public.group_my_rights(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select case when g.id is null then null else jsonb_build_object(
    'role', private.group_role(grp, auth.uid()),
    'manage', private.manages_group(grp),
    'rules', g.system_key is null and private.may_set_group_rules(grp, auth.uid()),
    'owner', g.system_key is null and (g.created_by = auth.uid() or public.is_admin()),
    'invite', private.may_invite_group(grp),
    'events', private.group_may(grp, auth.uid(), 'events'),
    'announce', private.group_may(grp, auth.uid(), 'announce'),
    'write', private.group_may(grp, auth.uid(), 'write'),
    'pin', private.group_admin(grp, auth.uid()) or private.group_may(grp, auth.uid(), 'pin'),
    'edit', g.system_key is null and private.group_may(grp, auth.uid(), 'edit'),
    'remove', g.system_key is null and (private.manages_group(grp) or private.group_may(grp, auth.uid(), 'remove'))) end
  from (select 1) one left join public.member_groups g on g.id = grp
  where auth.uid() is not null;
$$;
revoke all on function public.group_my_rights(uuid) from public, anon;
grant execute on function public.group_my_rights(uuid) to authenticated;

-- 4. Entrée dans le groupe ------------------------------------------------------------------------------------------------
create or replace function public.set_group_join_approval(grp uuid, approval boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from public.member_groups where id = grp and system_key is not null) then
    raise exception 'forbidden: pas de réglage pour Membres Vendredi Party' using errcode = '42501';
  end if;
  if not private.may_set_group_rules(grp, auth.uid()) then
    raise exception 'forbidden: réservé à l''admin et aux co-admins du groupe' using errcode = '42501';
  end if;
  update public.member_groups set join_approval = coalesce(approval, false) where id = grp;
end $$;
revoke all on function public.set_group_join_approval(uuid, boolean) from public, anon;
grant execute on function public.set_group_join_approval(uuid, boolean) to authenticated;

-- Demande d'entrée : l'admin et les co-admins sont prévenus (même notification que « X a rejoint ton groupe »).
create or replace function private.request_group_join(grp uuid, member uuid, how text) returns void
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text; a uuid;
begin
  select * into g from public.member_groups where id = grp;
  insert into private.group_join_requests (group_id, user_id, via) values (grp, member, how) on conflict do nothing;
  if not found then return; end if;
  select display_name into who from public.profiles where id = member;
  for a in select g.created_by union select ad.user_id from public.group_admins ad where ad.group_id = grp
           and private.in_group_now(grp, ad.user_id) loop
    if a is not null and a <> member then
      perform public.queue_notification(a, 'group_join', null, g.name,
        coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' demande à rejoindre ton groupe', 'group_join_request:' || grp || ':' || member);
    end if;
  end loop;
end $$;
revoke all on function private.request_group_join(uuid, uuid, text) from public, anon, authenticated;

create or replace function public.join_group_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid; author uuid; single boolean := false; needs boolean;
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
    if grp is not null then
      single := true;
      select created_by into author from private.invite_links where invite_links.token = join_group_by_link.token;
    end if;
  end if;
  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  if private.in_group_now(grp, auth.uid()) then return grp; end if;
  -- « Accepter chaque nouveau membre » : le lien du groupe attend l'accord ; un lien unique de l'admin ou d'un co-admin
  -- vaut accord.
  needs := coalesce((select join_approval from public.member_groups where id = grp), false)
           and not (single and author is not null and private.group_admin(grp, author));
  if needs then
    perform private.request_group_join(grp, auth.uid(), 'link');
    return grp;
  end if;
  if private.join_group(grp, auth.uid()) and author is not null then
    perform private.note_invite_join(auth.uid(), author, 'group', grp);
  end if;
  return grp;
end $$;

create or replace function public.answer_group_invitation(inv uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i private.group_invitations;
begin
  select * into i from private.group_invitations where id = inv and status = 'pending'
    and (user_id = auth.uid() or phone = (select private.digits(phone) from public.profiles where id = auth.uid()));
  if i.id is null then raise exception 'Cette invitation n''est plus valable'; end if;
  if accept then
    if not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
    -- Invitation d'un simple membre dans un groupe qui accepte chaque nouveau membre : demande à l'admin.
    if coalesce((select join_approval from public.member_groups where id = i.group_id), false)
       and not private.group_admin(i.group_id, i.invited_by) then
      update private.group_invitations set status = 'accepted' where id = inv;
      perform private.request_group_join(i.group_id, auth.uid(), 'invitation');
    else
      perform private.join_group(i.group_id, auth.uid());
    end if;
  else
    update private.group_invitations set status = 'declined' where id = inv;
  end if;
  return public.my_group_invitations();
end $$;

create or replace function public.decide_group_join(grp uuid, member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé à l''admin et aux co-admins du groupe' using errcode = '42501';
  end if;
  delete from private.group_join_requests where group_id = grp and user_id = member;
  if not found then raise exception 'Cette demande n''existe plus'; end if;
  if accept and private.is_account_active(member) then
    select * into g from public.member_groups where id = grp;
    if private.join_group(grp, member) then
      perform public.queue_notification(member, 'group_added', null, g.name,
        'Ta demande est acceptée : tu es dans le groupe « ' || g.name || ' »', 'group_join_ok:' || grp || ':' || member);
    end if;
  end if;
end $$;
revoke all on function public.decide_group_join(uuid, uuid, boolean) from public, anon;
grant execute on function public.decide_group_join(uuid, uuid, boolean) to authenticated;

create or replace function public.group_invite_info(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', g.id, 'name', g.name,
    'creator', (select display_name from public.profiles where id = g.created_by),
    'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
    'joined', auth.uid() is not null and exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid()),
    'approval', g.join_approval,
    'requested', auth.uid() is not null and exists (select 1 from private.group_join_requests r where r.group_id = g.id and r.user_id = auth.uid()))
  from public.member_groups g
  where token is not null and (g.invite_token = token or g.id = private.invite_link_target(token, 'group'))
    and g.system_key is null and private.identity_complete(auth.uid());
$$;

-- 5. Transmettre le groupe ------------------------------------------------------------------------------------------------
create or replace function public.transfer_group(grp uuid, member uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text;
begin
  select * into g from public.member_groups where id = grp for update;
  if g.id is null or g.system_key is not null then
    raise exception 'forbidden: ce groupe ne se transmet pas' using errcode = '42501';
  end if;
  if not (g.created_by = auth.uid() or public.is_admin()) then
    raise exception 'forbidden: seul l''admin du groupe le transmet' using errcode = '42501';
  end if;
  if member is null or member = g.created_by or not private.in_group_now(grp, member) then
    raise exception 'Choisis un membre du groupe';
  end if;
  if not private.is_account_active(member) or not private.identity_complete(member) then
    raise exception 'Cette personne ne peut pas recevoir le groupe pour l''instant';
  end if;
  update public.member_groups set created_by = member where id = grp;
  delete from public.group_admins where group_id = grp and user_id = member;
  delete from public.group_organizers where group_id = grp and user_id = member;
  if g.created_by is not null and private.in_group_now(grp, g.created_by) then
    insert into public.group_admins (group_id, user_id) values (grp, g.created_by) on conflict do nothing;  -- reste co-admin
  end if;
  select display_name into who from public.profiles where id = auth.uid();
  perform public.queue_notification(member, 'group_added', null, g.name,
    coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' te transmet le groupe « ' || g.name || ' » : tu en es l''admin',
    'group_owner:' || grp || ':' || member);
end $$;
revoke all on function public.transfer_group(uuid, uuid) from public, anon;
grant execute on function public.transfer_group(uuid, uuid) to authenticated;

-- 6. L'écran des réglages en une lecture -----------------------------------------------------------------------------------
create or replace function public.group_admin_panel(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'group', jsonb_build_object('id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color,
               'photo', case when g.system_key is null then g.photo_path end, 'system', g.system_key is not null,
               'created_by', g.created_by, 'created_at', g.created_at),
    'me', public.group_my_rights(grp),
    'rights', jsonb_build_object('invite', g.who_invite, 'events', g.who_events, 'announce', g.who_announce,
               'write', g.who_write, 'pin', g.who_pin, 'edit', g.who_edit, 'remove', g.who_remove),
    'events_need_approval', g.events_need_approval, 'announce_mode', g.announce_mode, 'join_approval', g.join_approval,
    'link_active', g.invite_token is not null,
    'members', (select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'photo', p.avatar_url,
                    'role', private.group_role(grp, p.id), 'since', m.added_at)
                  order by case private.group_role(grp, p.id) when 'creator' then 0 when 'coadmin' then 1 when 'organizer' then 2 else 3 end,
                           p.display_name), '[]'::jsonb)
                from public.member_group_members m join public.profiles p on p.id = m.user_id where m.group_id = grp),
    'requests', case when private.manages_group(grp) then
                  (select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'photo', p.avatar_url,
                          'at', r.created_at, 'via', r.via) order by r.created_at), '[]'::jsonb)
                   from private.group_join_requests r join public.profiles p on p.id = r.user_id where r.group_id = grp)
                else '[]'::jsonb end)
  from public.member_groups g
  where g.id = grp and auth.uid() is not null
    and (private.in_group_now(grp, auth.uid()) or private.manages_group(grp) or private.sees_all_groups());
$$;
revoke all on function public.group_admin_panel(uuid) from public, anon;
grant execute on function public.group_admin_panel(uuid) to authenticated;

-- Liste « droits » de mes groupes : + 'events' (bouton « Créer un événement pour le groupe » de sa page, web et iPhone).
do $$
declare def text := pg_get_functiondef('public.my_groups_overview()'::regprocedure);
begin
  if position('''events'', private.group_may' in def) = 0 then
    execute replace(def, '''invite'', private.may_invite_group(g.id),',
                         '''invite'', private.may_invite_group(g.id), ''events'', private.group_may(g.id, auth.uid(), ''events''),');
  end if;
end $$;
