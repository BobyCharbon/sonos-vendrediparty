-- « Nouveau compte » et suppression du compte (recette des nouveaux comptes, 14.11.2026) : la notification « 👋 Nouveau
-- compte » reçue par les valideurs porte le surnom, le prénom et le nom de la personne. Quand cette personne supprime son
-- compte, tout part avec lui (règle de conformité) : ces notifications aussi, chez chaque valideur. Avant : elles restaient.
-- Purement additive et rejouable.

create or replace function private.forget_member_signup() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  delete from public.notifications where kind = 'member_signup' and data->>'member' = old.id::text;
  return old;
end $$;
revoke all on function private.forget_member_signup() from public, anon, authenticated;

drop trigger if exists profiles_forget_member_signup on public.profiles;
create trigger profiles_forget_member_signup after delete on public.profiles
  for each row execute function private.forget_member_signup();
