-- Sécurité (campagne du 14.11.2026) : la règle « modifier son profil » ouvre la ligne ENTIÈRE d'un autre compte à ceux qui
-- ont members.roles, members.ban ou members.approve (le rôle Organisateur compris). guard_profile ne contrôlait que le rôle
-- et l'accès : un organisateur pouvait renommer n'importe qui (Root et admins compris : surnom, prénom, nom) ou lui retirer
-- sa photo. Désormais seule la personne change son identité ; l'admin ne change que le rôle et l'accès (écran Membres).
-- La modération (« Surnom masqué ») passe par les fonctions de la base (current_user = postgres) : inchangée.
-- Purement additive et rejouable.

create or replace function private.guard_profile_identity() returns trigger
language plpgsql set search_path = '' as $$  -- invoker exprès : current_user dit si la demande vient directement de l'app
begin
  if current_user = 'authenticated' and old.id is distinct from auth.uid()
     and (new.display_name, new.first_name, new.last_name, new.avatar_url)
         is distinct from (old.display_name, old.first_name, old.last_name, old.avatar_url) then
    raise exception 'forbidden: seule la personne change son nom, son surnom ou sa photo' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_profile_identity() from public, anon, authenticated;

-- « profiles_auth… » passe avant profiles_guard (ordre alphabétique des déclencheurs BEFORE) : il voit la demande brute.
drop trigger if exists profiles_auth_identity on public.profiles;
create trigger profiles_auth_identity before update of display_name, first_name, last_name, avatar_url on public.profiles
  for each row execute function private.guard_profile_identity();
