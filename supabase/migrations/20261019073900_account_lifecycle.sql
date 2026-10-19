-- Le répertoire masque les numéros ; la restriction de colonne est déployée
-- séparément après que tous les clients ont migré vers ce RPC.
create or replace function private.member_directory() returns setof public.profiles
language sql stable security definer set search_path = '' as $$
  select p.id, p.display_name,
    case when p.id = auth.uid() or public.is_admin() then p.phone else null end,
    p.avatar_url, p.role, p.status, p.created_at
  from public.profiles p
  where auth.uid() is not null and (p.id = auth.uid() or public.is_admin() or (public.is_active() and p.status = 'active'));
$$;
revoke all on function private.member_directory() from public, anon;
grant execute on function private.member_directory() to authenticated;

create or replace function public.get_member_directory() returns setof public.profiles
language sql stable security invoker set search_path = '' as $$
  select * from private.member_directory();
$$;
revoke all on function public.get_member_directory() from public, anon;
grant execute on function public.get_member_directory() to authenticated;

-- Suppression volontaire du compte courant. Aucun identifiant cible n'est accepté.
create or replace function private.delete_current_account() returns void
language plpgsql security definer set search_path = '' as $$
declare
  member_id uuid := auth.uid();
  current_session text := auth.jwt() ->> 'session_id';
begin
  if member_id is null or current_session is null or not exists (
    select 1 from auth.sessions s where s.user_id = member_id and s.id::text = current_session
  ) then
    raise exception 'Une connexion valide est nécessaire' using errcode = '42501';
  end if;

  -- Sérialiser avec les changements de rôles pour ne jamais retirer le dernier admin.
  lock table public.profiles in share row exclusive mode;
  if exists (select 1 from public.profiles where id = member_id and role = 'admin' and status = 'active')
     and not exists (select 1 from public.profiles where id <> member_id and role = 'admin' and status = 'active') then
    raise exception 'last_admin: désigne un autre administrateur avant de supprimer ton compte';
  end if;

  update public.messages set mentions = array_remove(mentions, member_id) where member_id = any(mentions);
  -- Les FK suppriment profil, sessions, événements créés, messages, réponses,
  -- votes, préférences et jetons push. Toute erreur annule l'opération entière.
  delete from auth.users where id = member_id;
end;
$$;
revoke all on function private.delete_current_account() from public, anon;
grant execute on function private.delete_current_account() to authenticated;

create or replace function public.delete_my_account() returns void
language sql security invoker set search_path = '' as $$
  select private.delete_current_account();
$$;
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
