-- Retour arrière de 20261122120000 : lecture du journal d'avant (noms figés), aide retirée.
begin;
create or replace function public.admin_member_audit(member uuid default null, before bigint default null, lim int default 100)
returns setof public.member_audit
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  return query select * from public.member_audit a
    where (member is null or a.target = member or a.actor = member) and (before is null or a.id < before)
    order by a.id desc limit greatest(1, least(lim, 500));
end $$;
revoke all on function public.admin_member_audit(uuid, bigint, int) from public, anon;
grant execute on function public.admin_member_audit(uuid, bigint, int) to authenticated;
drop function if exists private.audit_name(uuid);
delete from supabase_migrations.schema_migrations where version = '20261122120000';
commit;
