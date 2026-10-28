-- PROD, rôles et groupes séparés (20261028200000_roles_and_groups).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod ») pour cette migration.
-- Tout-ou-rien ; rejouable. Retour arrière : 2026-10-29-roles-groups-rollback.sql (droits remis depuis la sauvegarde).
begin;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);

-- Rôles et groupes séparés (retour de l'admin du 28 octobre 2026) : « Une personne peut avoir plusieurs groupes et
-- un seul rôle. » Le rôle member devient « Membre », avec les mêmes droits que Guest ; être VIP, c'est être dans le
-- groupe « Vendredi Party », qui donne les droits des VIP (voir les événements, en créer…). Les droits d'un compte =
-- ceux de son rôle + ceux de ses groupes (table group_permissions).
-- Personne ne perd rien : les VIP actuels sont déjà dans le groupe, qui reçoit les droits qu'avait le rôle.
-- Le groupe ne suit plus le rôle (plus de synchronisation automatique) : les admins le composent, et une demande
-- d'adhésion acceptée y fait entrer. Un compte passé organisateur ou plus y entre encore tout seul (jamais retiré).
-- Tout le monde peut créer ses propres groupes (Réglages › Groupes).
-- Rejouable : la redistribution des droits est notée dans private.one_time_changes et ne repasse jamais.

create table if not exists public.group_permissions (
  group_id uuid not null references public.member_groups (id) on delete cascade,
  perm text not null references public.permissions (key) on delete cascade,
  primary key (group_id, perm)
);
alter table public.group_permissions enable row level security;
drop policy if exists group_permissions_select on public.group_permissions;
create policy group_permissions_select on public.group_permissions for select to authenticated using ((select public.is_active()));
drop policy if exists group_permissions_write on public.group_permissions;
create policy group_permissions_write on public.group_permissions for all to authenticated
  using ((select public.has_perm('roles.manage'))) with check ((select public.has_perm('roles.manage')));
grant select, insert, update, delete on public.group_permissions to authenticated;

-- Droits d'un compte actif : root, son rôle, ou un de ses groupes.
create or replace function private.user_has(uid uuid, perm text) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and (
    (private.is_root(uid) and exists (select 1 from public.profiles where id = uid and status = 'active'))
    or exists (select 1 from public.profiles p join public.role_permissions rp on rp.role = p.role
               where p.id = uid and p.status = 'active' and rp.perm = user_has.perm)
    or exists (select 1 from public.profiles p
               join public.member_group_members gm on gm.user_id = p.id
               join public.group_permissions gp on gp.group_id = gm.group_id
               where p.id = uid and p.status = 'active' and gp.perm = user_has.perm));
$$;

create table if not exists private.one_time_changes (name text primary key, applied_at timestamptz not null default now());

do $$
declare vip uuid := private.vip_group_id();
begin
  if vip is null or exists (select 1 from private.one_time_changes where name = 'roles_and_groups_2026_10_28') then
    return;
  end if;
  create table if not exists private.role_permissions_backup_20261028 as select * from public.role_permissions;
  -- Les droits des VIP passent du rôle member au groupe Vendredi Party…
  insert into public.group_permissions (group_id, perm)
    select vip, perm from public.role_permissions where role = 'member' on conflict do nothing;
  -- … et le rôle « Membre » prend exactement les droits de Guest.
  delete from public.role_permissions where role = 'member';
  insert into public.role_permissions (role, perm) select 'member', perm from public.role_permissions where role = 'guest';
  insert into private.one_time_changes (name) values ('roles_and_groups_2026_10_28');
end $$;

-- Le groupe ne suit plus le rôle : seulement un ajout automatique pour organisateur et plus (jamais de retrait).
create or replace function private.sync_vip_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g uuid := private.vip_group_id();
begin
  if g is not null and new.status = 'active' and private.role_rank(new.role) >= private.role_rank('organizer') then
    insert into public.member_group_members (group_id, user_id) values (g, new.id) on conflict do nothing;
  end if;
  return null;
end $$;

-- Demande d'adhésion acceptée : la personne devient Membre et entre dans le groupe Vendredi Party.
create or replace function public.decide_join_request(member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    -- Le contrôle d'identité complète de guard_profile s'applique ici.
    update public.profiles set role = 'member' where id = member and role = 'guest';
    insert into public.member_group_members (group_id, user_id) values (private.vip_group_id(), member) on conflict do nothing;
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$$;

-- Compte actif (Guest compris) : peut créer ses groupes.
create or replace function public.is_active_account() returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_account_active(auth.uid());
$$;
revoke all on function public.is_active_account() from public, anon;
grant execute on function public.is_active_account() to authenticated;

-- Tout compte actif crée ses groupes ; les admins (gestion des rôles) composent aussi le groupe Vendredi Party.
drop policy if exists "créer un groupe" on public.member_groups;
create policy "créer un groupe" on public.member_groups for insert to authenticated
  with check (created_by = (select auth.uid()) and (select public.is_active_account()));
drop policy if exists "composer son groupe" on public.member_group_members;
create policy "composer son groupe" on public.member_group_members for all to authenticated
  using (exists (select 1 from public.member_groups g where g.id = group_id and (
           (g.system_key is null and (g.created_by = (select auth.uid()) or (select public.is_admin())))
           or (g.system_key = 'vip' and (select public.has_perm('members.roles'))))))
  with check (exists (select 1 from public.member_groups g where g.id = group_id and (
           (g.system_key is null and (g.created_by = (select auth.uid()) or (select public.is_admin())))
           or (g.system_key = 'vip' and (select public.has_perm('members.roles'))))));

-- Chacun voit les groupes qu'il a créés et ceux dont il fait partie (Réglages › Groupes), même sans être VIP.
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

drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using ((select public.is_active()) or created_by = (select auth.uid()) or private.in_group(id, (select auth.uid())));
drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using ((select public.is_active()) or user_id = (select auth.uid()) or private.created_group(group_id, (select auth.uid())));

insert into supabase_migrations.schema_migrations (version, name) values ('20261028200000', 'roles_and_groups')
  on conflict (version) do nothing;
commit;
