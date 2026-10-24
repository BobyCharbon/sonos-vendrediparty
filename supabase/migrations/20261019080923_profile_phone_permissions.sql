-- À appliquer après déploiement des clients utilisant get_member_directory().
revoke select on public.profiles from authenticated;
grant select (id, display_name, avatar_url, role, status, created_at) on public.profiles to authenticated;
