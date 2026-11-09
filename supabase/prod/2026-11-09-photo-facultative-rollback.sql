-- PROD, retour arrière de photo_profil_facultative (20261109020000) : request_join, guard_profile et identity_complete d'avant (photo obligatoire). Tout ou rien.
begin;
create or replace function public.request_join(note text) returns void
language plpgsql security definer set search_path = '' as $$
declare me public.profiles;
begin
  select * into me from public.profiles where id = auth.uid();
  if me.id is null or me.status <> 'active' then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if not private.below_vip(me.role) then raise exception 'Tu fais déjà partie du groupe'; end if;
  if btrim(me.first_name) = '' or btrim(me.last_name) = '' or btrim(me.display_name) = '' or coalesce(me.avatar_url, '') = '' then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  insert into public.join_requests (user_id, message) values (me.id, nullif(btrim(note), ''))
  on conflict (user_id) do update set message = excluded.message, status = 'pending', created_at = now(), decided_by = null, decided_at = null
    where public.join_requests.status <> 'pending' or public.join_requests.message is distinct from excluded.message;
end;
$$;

create or replace function public.guard_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); my_rank int := private.rank_of(auth.uid());
begin
  if private.is_root(old.id) then
    new.role := 'admin';
    new.status := 'active';
  elsif me is not null and not private.is_root(me) then
    if new.role is distinct from old.role then
      if not ((private.user_has(me, 'members.roles') and private.role_rank(old.role) < my_rank and private.role_rank(new.role) < my_rank)
              or (private.below_vip(old.role) and new.role = 'member' and private.user_has(me, 'members.approve'))) then
        raise exception 'forbidden: tu ne peux pas attribuer ce rôle' using errcode = '42501';
      end if;
    end if;
    if new.status is distinct from old.status then
      if not (private.user_has(me, 'members.ban') and private.role_rank(old.role) < my_rank) then
        raise exception 'forbidden: tu ne peux pas changer l''accès de ce compte' using errcode = '42501';
      end if;
    end if;
  end if;

  new.first_name := btrim(new.first_name);
  new.last_name := btrim(new.last_name);
  new.display_name := btrim(new.display_name);
  if char_length(new.display_name) > 40 then
    raise exception 'nickname_too_long: le surnom est limité à 40 caractères' using errcode = '23514';
  end if;

  -- Toute identité renseignée reste complète, et on ne devient Membre VIP (ou plus) qu'avec une identité complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (not private.below_vip(new.role) and new.role is distinct from old.role))
     and (new.first_name = '' or new.last_name = '' or new.display_name = ''
       or not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
         and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text)) then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  return new;
end;
$$;
revoke all on function public.guard_profile() from public, anon, authenticated;

create or replace function private.identity_complete(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles p where p.id = uid
    and coalesce(btrim(p.first_name), '') <> '' and coalesce(btrim(p.last_name), '') <> ''
    and coalesce(btrim(p.display_name), '') <> '' and coalesce(btrim(p.avatar_url), '') <> '');
$$;
delete from supabase_migrations.schema_migrations where version = '20261109020000';
commit;
notify pgrst, 'reload schema';
