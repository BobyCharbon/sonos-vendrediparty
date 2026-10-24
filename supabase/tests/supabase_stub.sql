-- Schéma Supabase minimal pour tester les migrations hors ligne (PGlite). Seules les parties utilisées
-- par les migrations testées ; à remplacer par le vrai schéma de base une fois exporté de la prod.
create role anon nologin;
create role authenticated nologin;
create schema auth;
create schema private;
grant usage on schema auth, private, public to authenticated;

create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
grant execute on function auth.uid() to authenticated;

create table auth.users (id uuid primary key, phone text, created_at timestamptz not null default now(), phone_confirmed_at timestamptz, last_sign_in_at timestamptz);
create table auth.sessions (id uuid primary key default gen_random_uuid(), user_id uuid references auth.users on delete cascade, user_agent text);

create type public.member_role as enum ('guest', 'member', 'organizer', 'coadmin', 'admin');
create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text not null default '', first_name text, last_name text, phone text, avatar_url text,
  role public.member_role not null default 'guest', status text not null default 'active', created_at timestamptz not null default now()
);
create table public.beta_testers (user_id uuid primary key references public.profiles on delete cascade, added_by uuid);
create table public.member_groups (id uuid primary key default gen_random_uuid(), name text not null);
create table public.member_group_members (group_id uuid references public.member_groups on delete cascade,
  user_id uuid references public.profiles on delete cascade, primary key (group_id, user_id));
create table public.events (id uuid primary key default gen_random_uuid());
create table public.rsvps (event_id uuid references public.events on delete cascade, user_id uuid references public.profiles on delete cascade,
  status text not null, primary key (event_id, user_id));
create table public.messages (id serial primary key, user_id uuid references public.profiles on delete cascade,
  mentions uuid[] not null default '{}', deleted_at timestamptz);

-- Comme en prod (migration member_roles_permissions) : un seul root, identifiant fixe ; sinon le rang du rôle.
create function private.is_root(uid uuid) returns boolean language sql immutable as $$
  select uid = '00000000-0000-0000-0000-000000000099'::uuid
$$;
create function private.role_rank(r public.member_role) returns int language sql immutable as $$
  select array_position(enum_range(null::public.member_role), r) - 1
$$;
create function public.my_rank() returns int language sql stable security definer set search_path = '' as $$
  select case when private.is_root(auth.uid()) then 99
    else coalesce((select private.role_rank(role) from public.profiles where id = auth.uid() and status = 'active'), -1) end
$$;
grant execute on function public.my_rank() to authenticated;
