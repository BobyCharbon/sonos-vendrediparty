-- Bêta-testeurs des Événements en prod : une case par personne, cochée par qui gère les rôles.
-- Table à part (et non une colonne de profiles) : get_member_directory renvoie les colonnes de profiles une à une.
-- Les admins sont bêta-testeurs d'office. Les visiteurs n'ont aucun accès aux nouvelles tables.

create table public.beta_testers (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  added_by uuid references public.profiles (id) on delete set null,
  created_at timestamptz not null default now()
);
alter table public.beta_testers enable row level security;
revoke all on public.beta_testers from anon, authenticated;
grant select on public.beta_testers to authenticated;
create policy "voir les bêta-testeurs" on public.beta_testers for select to authenticated
  using (user_id = (select auth.uid()) or (select public.manages_members()));
create or replace function public.is_beta_tester() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.beta_testers where user_id = auth.uid()) or public.is_admin();
$$;
revoke all on function public.is_beta_tester() from public, anon;
grant execute on function public.is_beta_tester() to authenticated;
create or replace function public.set_beta_tester(member uuid, enabled boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.roles') then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  if enabled then
    insert into public.beta_testers (user_id, added_by) values (member, auth.uid()) on conflict (user_id) do nothing;
  else
    delete from public.beta_testers where user_id = member;
  end if;
end $$;
revoke all on function public.set_beta_tester(uuid, boolean) from public, anon;
grant execute on function public.set_beta_tester(uuid, boolean) to authenticated;
-- Les tables de la visibilité (20261021120000) n'ont rien à offrir aux visiteurs : RLS les bloquait déjà.
revoke all on public.member_groups, public.member_group_members, public.event_groups from anon;
