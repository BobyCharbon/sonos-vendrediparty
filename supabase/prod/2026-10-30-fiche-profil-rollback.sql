-- PROD, retour arrière de 20261029160000 (fiche profil et confidentialité) : choix de confidentialité effacés,
-- annuaire d'origine. Le code de l'app gère l'absence de ces fonctions (la fiche affiche « indisponible »).
begin;
create or replace function private.member_directory()
 RETURNS SETOF public.profiles
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select p.id, p.display_name,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') then p.phone else null end,
    p.avatar_url, p.role, p.status, p.created_at,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') or public.has_perm('members.approve') then p.first_name else null end,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') or public.has_perm('members.approve') then p.last_name else null end
  from public.profiles p
  where auth.uid() is not null and (p.id = auth.uid() or public.manages_members() or (public.is_active() and private.is_member(p.id)));
$function$;
drop function if exists public.member_card(uuid);
drop function if exists public.set_group_phone_share(uuid, boolean);
drop function if exists public.set_name_public(boolean);
drop function if exists public.my_privacy();
drop function if exists private.phone_shared_with(uuid, uuid);
drop function if exists private.shows_name(uuid);
drop table if exists private.group_phone_shares;
drop table if exists private.member_privacy;
delete from supabase_migrations.schema_migrations where version = '20261029160000';
commit;
