-- Surnom limité à 12 caractères (avis bda77087d7dc de l'admin, 14.11.2026) : il tient partout (jeux, listes, Apple TV).
-- Seul un surnom nouveau ou modifié est contrôlé ; les surnoms plus longs déjà enregistrés restent (2 en prod le 14.11).
-- Même règle que l'app (web IdentityForm, iOS ProfileRules). Purement additive et rejouable (create or replace).

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
  new.avatar_url := nullif(btrim(coalesce(new.avatar_url, '')), '');
  -- Surnom : 12 caractères au plus (avis bda77087d7dc, 14.11.2026). Un surnom plus long d'avant reste tant qu'on n'y
  -- touche pas : sinon la personne ne pourrait plus enregistrer sa photo ou son nom.
  if new.display_name is distinct from btrim(old.display_name) and char_length(new.display_name) > 12 then
    raise exception 'nickname_too_long: le surnom est limité à 12 caractères' using errcode = '23514';
  end if;

  -- Toute identité renseignée reste complète, et on ne devient Membre VIP (ou plus) qu'avec une identité complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (not private.below_vip(new.role) and new.role is distinct from old.role))
     and (new.first_name = '' or new.last_name = '' or new.display_name = '') then
    raise exception 'profile_incomplete: nom, prénom et surnom obligatoires avant validation' using errcode = '23514';
  end if;
  -- Photo facultative ; donnée, elle doit être un fichier du dossier du membre.
  if new.avatar_url is distinct from old.avatar_url and new.avatar_url is not null
     and not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
       and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text) then
    raise exception 'profile_photo_invalid: photo de profil introuvable' using errcode = '23514';
  end if;
  return new;
end;
$$;
revoke all on function public.guard_profile() from public, anon, authenticated;
