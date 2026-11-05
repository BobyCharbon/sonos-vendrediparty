-- PROD, retour arrière de groups_visible_to_members (20261104093000) : on revient aux règles de lecture d'avant
-- (migration 20261028200100 : tout compte actif lit tous les groupes et leur composition ; « composer son groupe » FOR ALL
-- de 20261025160000). event_group_names est gardée (le site publié l'appelle ; sans risque : noms des groupes d'un
-- événement visible). Tout ou rien.
begin;

drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using ((select public.is_active()) or created_by = (select auth.uid()) or private.in_group(id, (select auth.uid())));
drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using ((select public.is_active()) or user_id = (select auth.uid()) or private.created_group(group_id, (select auth.uid())));

drop policy if exists "ajouter au groupe" on public.member_group_members;
drop policy if exists "modifier un membre du groupe" on public.member_group_members;
drop policy if exists "retirer du groupe" on public.member_group_members;
drop policy if exists "composer son groupe" on public.member_group_members;
create policy "composer son groupe" on public.member_group_members for all to authenticated
  using (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                 and (g.created_by = (select auth.uid()) or (select public.is_admin()))))
  with check (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                      and (g.created_by = (select auth.uid()) or (select public.is_admin()))));

drop function if exists private.sees_all_groups();

delete from supabase_migrations.schema_migrations where version = '20261104093000';
commit;

notify pgrst, 'reload schema';
