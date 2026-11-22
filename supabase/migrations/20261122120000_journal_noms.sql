-- Journal des membres (demande de l'admin du 22.11) : « compte supprimé a créé son compte » alors que le compte existe.
-- Le nom est figé à l'écriture ; à la création et à la 1re connexion, le profil n'a pas encore de surnom (rempli juste
-- après, « Faisons connaissance »). À la lecture, un nom vide prend le surnom actuel, sinon le dernier nom connu dans le
-- journal (compte supprimé depuis). Rien n'est réécrit dans la table.
create or replace function private.audit_name(member uuid) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce(private.member_name(member),
    (select x.name from (
       select b.id, b.target_name as name from public.member_audit b where b.target = member and b.target_name is not null
       union all
       select b.id, b.actor_name from public.member_audit b where b.actor = member and b.actor_name is not null
     ) x order by x.id desc limit 1));
$$;
revoke all on function private.audit_name(uuid) from public, anon, authenticated;

create or replace function public.admin_member_audit(member uuid default null, before bigint default null, lim int default 100)
returns setof public.member_audit
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  return query select a.id, a.at, a.action,
      a.actor, coalesce(a.actor_name, case when a.actor is not null then private.audit_name(a.actor) end),
      a.target, coalesce(a.target_name, case when a.target is not null then private.audit_name(a.target) end),
      a.details
    from public.member_audit a
    where (member is null or a.target = member or a.actor = member) and (before is null or a.id < before)
    order by a.id desc limit greatest(1, least(lim, 500));
end $$;
revoke all on function public.admin_member_audit(uuid, bigint, int) from public, anon;
grant execute on function public.admin_member_audit(uuid, bigint, int) to authenticated;
