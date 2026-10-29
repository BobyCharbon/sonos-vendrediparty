-- PROD, role_membre_and_groups (20261028200100_role_membre_and_groups).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod »), dans l'ordre : 1-enum puis 2.
-- Rejouable.
begin;
-- Rôles (retour de l'admin du 28 octobre 2026) : Guest · Membre (nouveau, mêmes droits que Guest) · Membre VIP
-- (Vendredi Party, inchangé) · Organisateur · Co-admin · Admin. Un seul rôle par personne ; les groupes sont à part :
-- chacun crée les siens (Réglages › Groupes) et voit ceux dont il fait partie.
-- Un Membre peut demander à rejoindre Vendredi Party comme un Guest ; accepté, il passe Membre VIP.
-- Rejouable.

-- Rang : Membre au niveau de Guest (hors Vendredi Party, pas de droits de gestion).
create or replace function private.role_rank(r public.member_role) returns integer
language sql immutable set search_path = '' as $$
  select case r when 'guest' then 0 when 'basic' then 0 when 'member' then 1 when 'organizer' then 2 when 'coadmin' then 3 when 'admin' then 4 end;
$$;

-- Droits du rôle Membre = ceux de Guest (copiés une fois ; ensuite réglables dans Administration › Rôles).
insert into public.role_permissions (role, perm)
  select 'basic', perm from public.role_permissions where role = 'guest'
  and not exists (select 1 from public.role_permissions where role = 'basic')
on conflict do nothing;

create or replace function public.request_join(note text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me public.profiles;
begin
  select * into me from public.profiles where id = auth.uid();
  if me.id is null or me.status <> 'active' then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if me.role not in ('guest', 'basic') then raise exception 'Tu fais déjà partie du groupe'; end if;
  if btrim(me.first_name) = '' or btrim(me.last_name) = '' or btrim(me.display_name) = '' or coalesce(me.avatar_url, '') = '' then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  insert into public.join_requests (user_id, message) values (me.id, nullif(btrim(note), ''))
  on conflict (user_id) do update set message = excluded.message, status = 'pending', created_at = now(), decided_by = null, decided_at = null
    where public.join_requests.status <> 'pending' or public.join_requests.message is distinct from excluded.message;
end;
$function$;

create or replace function public.guard_profile()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid(); my_rank int := private.rank_of(auth.uid());
begin
  if private.is_root(old.id) then
    new.role := 'admin';
    new.status := 'active';
  elsif me is not null and not private.is_root(me) then
    if new.role is distinct from old.role then
      if not ((private.user_has(me, 'members.roles') and private.role_rank(old.role) < my_rank and private.role_rank(new.role) < my_rank)
              or (old.role in ('guest', 'basic') and new.role = 'member' and private.user_has(me, 'members.approve'))) then
        raise exception 'forbidden: tu ne peux pas attribuer ce rôle' using errcode = '42501';
      end if;
    end if;
    if new.status is distinct from old.status then
      if not (private.user_has(me, 'members.ban') and private.role_rank(old.role) < my_rank) then
        raise exception 'forbidden: tu ne peux pas changer l''accès de ce compte' using errcode = '42501';
      end if;
    end if;
  end if;

  new.first_name := btrim(new.first_name);
  new.last_name := btrim(new.last_name);
  new.display_name := btrim(new.display_name);
  if char_length(new.display_name) > 40 then
    raise exception 'nickname_too_long: le surnom est limité à 40 caractères' using errcode = '23514';
  end if;

  -- Toute identité renseignée reste complète, et on ne devient membre (ou plus) qu'avec une identité complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (private.role_rank(new.role) > 0 and new.role is distinct from old.role))
     and (new.first_name = '' or new.last_name = '' or new.display_name = ''
       or not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
         and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text)) then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  return new;
end;
$function$;

create or replace function public.decide_join_request(member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    -- Le contrôle d'identité complète de guard_profile s'applique ici.
    update public.profiles set role = 'member' where id = member and role in ('guest', 'basic');
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$$;

-- Groupes : tout compte actif crée les siens et voit ceux qu'il a créés ou dont il fait partie.
create or replace function public.is_active_account() returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_account_active(auth.uid());
$$;
revoke all on function public.is_active_account() from public, anon;
grant execute on function public.is_active_account() to authenticated;

-- Fonctions à droits élevés : les deux règles de lecture ne se citent pas l'une l'autre (sinon récursion infinie).
create or replace function private.in_group(gid uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_group_members where group_id = gid and user_id = uid);
$$;
create or replace function private.created_group(gid uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_groups where id = gid and created_by = uid);
$$;
revoke all on function private.in_group(uuid, uuid), private.created_group(uuid, uuid) from public, anon;
grant execute on function private.in_group(uuid, uuid), private.created_group(uuid, uuid) to authenticated;

drop policy if exists "créer un groupe" on public.member_groups;
create policy "créer un groupe" on public.member_groups for insert to authenticated
  with check (created_by = (select auth.uid()) and (select public.is_active_account()));
drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using ((select public.is_active()) or created_by = (select auth.uid()) or private.in_group(id, (select auth.uid())));
drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using ((select public.is_active()) or user_id = (select auth.uid()) or private.created_group(group_id, (select auth.uid())));

insert into supabase_migrations.schema_migrations (version, name) values ('20261028200100', 'role_membre_and_groups')
  on conflict (version) do nothing;
commit;
