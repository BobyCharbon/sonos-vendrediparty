-- PROD, guest_plus_and_feedback_right (20261029120100). À appliquer SEULEMENT après « Ok prod », après le fichier 1. Rejouable.
begin;
-- Rôle « Guest+ » et droit « Écrire un avis » (demande de l'admin du 29 octobre 2026) :
-- Guest+ a les mêmes droits que Guest, plus « Écrire un avis ». Un Guest (et un non connecté) n'écrit plus d'avis :
-- le droit est donné à Guest+ et au-dessus, puis réglable dans Administration › Rôles et droits.
-- Rejouable : la distribution initiale du droit est notée dans private.one_time_changes et ne repasse jamais
-- (un réglage fait ensuite par un admin n'est pas écrasé).

-- Rang : Guest+ au niveau de Guest (pas de droits de gestion, hors Vendredi Party).
create or replace function private.role_rank(r public.member_role) returns integer
language sql immutable set search_path = '' as $$
  select case r when 'guest' then 0 when 'guestplus' then 0 when 'basic' then 0 when 'member' then 1
                when 'organizer' then 2 when 'coadmin' then 3 when 'admin' then 4 end;
$$;

insert into public.permissions (key, grp, label, hint, sort) values
  ('feedback.write', 'Ton avis', 'Écrire un avis', 'Envoyer une idée ou signaler un bug dans « Ton avis »', 45)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'guest_plus_feedback_2026_10_29') then
    return;
  end if;
  -- Guest+ = droits de Guest, copiés une fois.
  insert into public.role_permissions (role, perm)
    select 'guestplus', perm from public.role_permissions where role = 'guest'
  on conflict do nothing;
  -- Écrire un avis : Guest+ et au-dessus ; jamais Guest.
  insert into public.role_permissions (role, perm)
    select r, 'feedback.write' from unnest(array['guestplus', 'basic', 'member', 'organizer', 'coadmin', 'admin']::public.member_role[]) r
  on conflict do nothing;
  delete from public.role_permissions where role = 'guest' and perm = 'feedback.write';
  insert into private.one_time_changes (name) values ('guest_plus_feedback_2026_10_29');
end $$;

-- Un Guest+ peut demander à rejoindre Vendredi Party comme un Guest ou un Membre ; accepté, il passe Membre VIP.
create or replace function public.request_join(note text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me public.profiles;
begin
  select * into me from public.profiles where id = auth.uid();
  if me.id is null or me.status <> 'active' then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if me.role not in ('guest', 'guestplus', 'basic') then raise exception 'Tu fais déjà partie du groupe'; end if;
  if btrim(me.first_name) = '' or btrim(me.last_name) = '' or btrim(me.display_name) = '' or coalesce(me.avatar_url, '') = '' then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  insert into public.join_requests (user_id, message) values (me.id, nullif(btrim(note), ''))
  on conflict (user_id) do update set message = excluded.message, status = 'pending', created_at = now(), decided_by = null, decided_at = null
    where public.join_requests.status <> 'pending' or public.join_requests.message is distinct from excluded.message;
end;
$function$;

create or replace function public.guard_profile()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid(); my_rank int := private.rank_of(auth.uid());
begin
  if private.is_root(old.id) then
    new.role := 'admin';
    new.status := 'active';
  elsif me is not null and not private.is_root(me) then
    if new.role is distinct from old.role then
      if not ((private.user_has(me, 'members.roles') and private.role_rank(old.role) < my_rank and private.role_rank(new.role) < my_rank)
              or (old.role in ('guest', 'guestplus', 'basic') and new.role = 'member' and private.user_has(me, 'members.approve'))) then
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

  -- Toute identité renseignée reste complète, et on ne devient membre (ou plus) qu'avec une identité complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (private.role_rank(new.role) > 0 and new.role is distinct from old.role))
     and (new.first_name = '' or new.last_name = '' or new.display_name = ''
       or not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
         and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text)) then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  return new;
end;
$function$;

create or replace function public.decide_join_request(member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    -- Le contrôle d'identité complète de guard_profile s'applique ici.
    update public.profiles set role = 'member' where id = member and role in ('guest', 'guestplus', 'basic');
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261029120100', 'guest_plus_and_feedback_right')
  on conflict (version) do nothing;
commit;
