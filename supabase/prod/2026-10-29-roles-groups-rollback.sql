-- PROD, retour arrière de 20261028200000_roles_and_groups : droits des rôles remis depuis la sauvegarde, droits des
-- groupes retirés, et le groupe Vendredi Party de nouveau tenu par le rôle (Membre VIP et plus).
begin;
truncate public.role_permissions;
insert into public.role_permissions select * from private.role_permissions_backup_20261028;
truncate public.group_permissions;
create or replace function private.sync_vip_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g uuid := private.vip_group_id();
begin
  if g is null then return null; end if;
  if private.rank_of(new.id) >= 1 then
    insert into public.member_group_members (group_id, user_id) values (g, new.id) on conflict do nothing;
  else
    delete from public.member_group_members where group_id = g and user_id = new.id;
  end if;
  return null;
end $$;
delete from private.one_time_changes where name = 'roles_and_groups_2026_10_28';
delete from supabase_migrations.schema_migrations where version = '20261028200000';
commit;
