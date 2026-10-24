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

create table auth.users (id uuid primary key, phone text, last_sign_in_at timestamptz);
create table auth.sessions (id uuid primary key default gen_random_uuid(), user_id uuid references auth.users on delete cascade, user_agent text);

create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text not null default '', first_name text, last_name text, phone text, avatar_url text,
  role text not null default 'guest', status text not null default 'active', created_at timestamptz not null default now()
);
create table public.beta_testers (user_id uuid primary key references public.profiles on delete cascade, added_by uuid);
create table public.member_groups (id uuid primary key default gen_random_uuid(), name text not null);
create table public.member_group_members (group_id uuid references public.member_groups on delete cascade,
  user_id uuid references public.profiles on delete cascade, primary key (group_id, user_id));
create table public.messages (id serial primary key, author uuid references public.profiles on delete cascade, mentions uuid[] not null default '{}');

-- Root : identifiant fixe (comme ROOT_ID côté app) ; sinon le rang du rôle.
create function public.my_rank() returns int language sql stable security definer set search_path = '' as $$
  select case when auth.uid() = '00000000-0000-0000-0000-000000000099' then 99
    else (select coalesce(array_position(array['guest','member','organizer','coadmin','admin'], role) - 1, -1)
          from public.profiles where id = auth.uid()) end
$$;
grant execute on function public.my_rank() to authenticated;
