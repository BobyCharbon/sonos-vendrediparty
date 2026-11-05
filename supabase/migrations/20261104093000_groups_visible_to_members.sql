-- Groupes visibles par leurs membres seulement (avis 1b4b43021c1e de Lidia, 3 novembre 2026 : « je vois un groupe dans
-- lequel je ne suis pas (DreamTeam) »). Décision de l'admin : seuls les Admins voient TOUS les groupes.
--
-- Avant : « voir les groupes » et « voir les membres des groupes » laissaient tout compte actif (droit events.view)
-- lire tous les groupes et leur composition ; « composer son groupe » (FOR ALL) ouvrait aussi la lecture des membres
-- à tout détenteur de events.manage_all (Co-admins compris).
-- Après : un groupe et sa composition se lisent par
--   · ses membres,
--   · son créateur,
--   · les Admins du site (rang du rôle Admin et au-dessus, Root compris) — PAS les Co-admins : private.is_member_admin(),
--     le critère déjà utilisé pour la liste complète des membres et le journal.
-- Le nom des groupes invités à un événement reste lisible par qui voit cet événement, sans leur composition ni leur
-- lien d'invitation : fonction public.event_group_names (security definer).
-- Toutes les autres lectures (Discussions, cartes de profil, invitations, liens, synchronisation des invités) passent
-- déjà par des fonctions security definer : inchangées.
-- Purement additif et rejouable (create or replace, drop policy if exists).

create or replace function private.sees_all_groups() returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member_admin();
$$;
revoke all on function private.sees_all_groups() from public, anon;
grant execute on function private.sees_all_groups() to authenticated;

drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using (created_by = (select auth.uid())
         or private.in_group(id, (select auth.uid()))
         or (select private.sees_all_groups()));

drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using (user_id = (select auth.uid())
         or private.in_group(group_id, (select auth.uid()))
         or private.created_group(group_id, (select auth.uid()))
         or (select private.sees_all_groups()));

-- « composer son groupe » était FOR ALL : il donnait aussi la lecture. Mêmes conditions, en écriture seulement.
drop policy if exists "composer son groupe" on public.member_group_members;
drop policy if exists "ajouter au groupe" on public.member_group_members;
create policy "ajouter au groupe" on public.member_group_members for insert to authenticated
  with check (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                      and (g.created_by = (select auth.uid()) or (select public.is_admin()))));
drop policy if exists "modifier un membre du groupe" on public.member_group_members;
create policy "modifier un membre du groupe" on public.member_group_members for update to authenticated
  using (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                 and (g.created_by = (select auth.uid()) or (select public.is_admin()))))
  with check (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                      and (g.created_by = (select auth.uid()) or (select public.is_admin()))));
drop policy if exists "retirer du groupe" on public.member_group_members;
create policy "retirer du groupe" on public.member_group_members for delete to authenticated
  using (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                 and (g.created_by = (select auth.uid()) or (select public.is_admin()))));

-- Noms des groupes invités à un événement (fiche de l'événement) : pour qui voit l'événement ou l'organise.
create or replace function public.event_group_names(e uuid) returns text[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(g.name order by g.name), '{}')
  from public.event_groups eg join public.member_groups g on g.id = eg.group_id
  where eg.event_id = e and (public.can_see_event(e) or public.is_organizer(e));
$$;
revoke all on function public.event_group_names(uuid) from public, anon;
grant execute on function public.event_group_names(uuid) to authenticated;
