-- L'identité civile reste privée ; display_name est le surnom public.
alter table public.profiles
  add column first_name text not null default '' check (char_length(first_name) <= 100),
  add column last_name text not null default '' check (char_length(last_name) <= 100);
grant update (first_name, last_name) on public.profiles to authenticated;

-- Aucun droit SELECT direct sur l'identité : le répertoire contrôle sa visibilité.
create or replace function private.member_directory() returns setof public.profiles
language sql stable security definer set search_path = '' as $$
  select p.id, p.display_name,
    case when p.id = auth.uid() or public.is_admin() then p.phone else null end,
    p.avatar_url, p.role, p.status, p.created_at,
    case when p.id = auth.uid() or public.is_admin() then p.first_name else null end,
    case when p.id = auth.uid() or public.is_admin() then p.last_name else null end
  from public.profiles p
  where auth.uid() is not null and (p.id = auth.uid() or public.is_admin() or (public.is_active() and p.status = 'active'));
$$;
revoke all on function private.member_directory() from public, anon;
grant execute on function private.member_directory() to authenticated;

create or replace function public.guard_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null and not public.is_admin() then
    new.role := old.role;
    new.status := old.status;
  end if;
  if auth.uid() is not null and (new.role = 'admin' or old.role = 'admin') and new.role is distinct from old.role
     and not exists (select 1 from public.profiles where id = auth.uid() and role = 'admin') then
    new.role := old.role;
  end if;

  new.first_name := btrim(new.first_name);
  new.last_name := btrim(new.last_name);
  new.display_name := btrim(new.display_name);
  if char_length(new.display_name) > 40 then
    raise exception 'nickname_too_long: le surnom est limité à 40 caractères' using errcode = '23514';
  end if;

  -- Les anciens clients restent compatibles ; toute nouvelle identité est complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (new.status = 'active' and old.status <> 'active'))
     and (new.first_name = '' or new.last_name = '' or new.display_name = ''
       or not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
         and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text)) then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  return new;
end;
$$;
revoke all on function public.guard_profile() from public, anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('profile-photos', 'profile-photos', false, 5242880, array['image/jpeg', 'image/png', 'image/webp']);

create policy "envoyer sa photo" on storage.objects for insert to authenticated
with check (bucket_id = 'profile-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy "photos du groupe autorisé" on storage.objects for select to authenticated
using (bucket_id = 'profile-photos' and (
  (storage.foldername(name))[1] = (select auth.uid())::text
  or (select public.is_admin())
  or ((select public.is_active()) and exists (
    select 1 from public.profiles p where p.status = 'active' and p.avatar_url = name
  ))
));

create policy "retirer sa photo" on storage.objects for delete to authenticated
using (bucket_id = 'profile-photos' and (storage.foldername(name))[1] = (select auth.uid())::text);
