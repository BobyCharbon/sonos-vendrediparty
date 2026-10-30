-- Fiche profil et confidentialité (avis n°7 et n°8 de l'admin, 29 octobre 2026) :
-- - Nom et prénom : cachés par défaut ; chacun peut les rendre visibles à tous les comptes (private.member_privacy).
-- - Numéro de téléphone : caché par défaut ; chacun choisit, groupe par groupe, de le montrer aux membres de ce groupe
--   (private.group_phone_shares ; le groupe Vendredi Party compris).
-- - Fiche profil (public.member_card) : photo, surnom, rôle, groupes en commun, et nom / numéro selon ces choix.
--   Les droits « Voir nom, prénom et numéro des membres » (members.view_identity) voient tout, comme avant.
-- Tables à part : la ligne profiles (et l'annuaire qui en dépend) ne change pas de forme. Rejouable.

create table if not exists private.member_privacy (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  show_name boolean not null default false,
  updated_at timestamptz not null default now()
);
create table if not exists private.group_phone_shares (
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  primary key (group_id, user_id)
);
revoke all on private.member_privacy, private.group_phone_shares from public, anon, authenticated;

create or replace function private.shows_name(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select show_name from private.member_privacy where user_id = uid), false);
$$;

-- Numéro de « target » visible par « viewer » : un groupe où target a choisi de le montrer et dont viewer est membre.
create or replace function private.phone_shared_with(target uuid, viewer uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from private.group_phone_shares s
    join public.member_group_members gm on gm.group_id = s.group_id and gm.user_id = viewer
    join public.member_group_members tm on tm.group_id = s.group_id and tm.user_id = target
    where s.user_id = target);
$$;
revoke all on function private.shows_name(uuid), private.phone_shared_with(uuid, uuid) from public, anon;
grant execute on function private.shows_name(uuid), private.phone_shared_with(uuid, uuid) to authenticated;

-- Annuaire : nom et prénom aussi quand la personne a choisi de les montrer (sinon inchangé).
create or replace function private.member_directory()
 RETURNS SETOF public.profiles
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select p.id, p.display_name,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') then p.phone else null end,
    p.avatar_url, p.role, p.status, p.created_at,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') or public.has_perm('members.approve')
              or private.shows_name(p.id) then p.first_name else null end,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') or public.has_perm('members.approve')
              or private.shows_name(p.id) then p.last_name else null end
  from public.profiles p
  where auth.uid() is not null and (p.id = auth.uid() or public.manages_members() or (public.is_active() and private.is_member(p.id)));
$function$;

-- Mes choix : nom public, et les groupes où je montre mon numéro.
create or replace function public.my_privacy() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'show_name', private.shows_name(auth.uid()),
    'phone_groups', coalesce((select jsonb_agg(group_id) from private.group_phone_shares where user_id = auth.uid()), '[]'::jsonb));
$$;

create or replace function public.set_name_public(visible boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  insert into private.member_privacy (user_id, show_name) values (auth.uid(), visible)
  on conflict (user_id) do update set show_name = excluded.show_name, updated_at = now();
  return public.my_privacy();
end $$;

create or replace function public.set_group_phone_share(grp uuid, visible boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not exists (select 1 from public.member_group_members where group_id = grp and user_id = auth.uid()) then
    raise exception 'forbidden: tu ne fais pas partie de ce groupe' using errcode = '42501';
  end if;
  if visible then
    insert into private.group_phone_shares (group_id, user_id) values (grp, auth.uid()) on conflict do nothing;
  else
    delete from private.group_phone_shares where group_id = grp and user_id = auth.uid();
  end if;
  return public.my_privacy();
end $$;

-- Fiche profil : ce que la personne connectée a le droit de voir d'un compte actif.
create or replace function public.member_card(target uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  p public.profiles;
  identity boolean;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  select * into p from public.profiles where id = target and status = 'active';
  if p.id is null then return null; end if;
  identity := p.id = me or public.has_perm('members.view_identity');
  return jsonb_build_object(
    'id', p.id,
    'display_name', p.display_name,
    'avatar_url', p.avatar_url,
    'role', p.role,
    'root', private.is_root(p.id),
    'me', p.id = me,
    'first_name', case when identity or private.shows_name(p.id) then nullif(p.first_name, '') end,
    'last_name', case when identity or private.shows_name(p.id) then nullif(p.last_name, '') end,
    'phone', case when identity or private.phone_shared_with(p.id, me) then nullif(p.phone, '') end,
    'groups', coalesce((select jsonb_agg(g.name order by g.system_key nulls last, g.name)
                        from public.member_groups g
                        where exists (select 1 from public.member_group_members a where a.group_id = g.id and a.user_id = p.id)
                          and exists (select 1 from public.member_group_members b where b.group_id = g.id and b.user_id = me)),
                       '[]'::jsonb));
end $$;

revoke all on function public.my_privacy(), public.set_name_public(boolean), public.set_group_phone_share(uuid, boolean),
  public.member_card(uuid) from public, anon;
grant execute on function public.my_privacy(), public.set_name_public(boolean), public.set_group_phone_share(uuid, boolean),
  public.member_card(uuid) to authenticated;
