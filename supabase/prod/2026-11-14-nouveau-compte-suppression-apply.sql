-- PROD, nouveau_compte_suppression (20261114210000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée à l'application : un déclencheur qui, à la suppression d'un compte,
-- efface les notifications « Nouveau compte » qui le nomment (chez les valideurs).
begin;
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

insert into supabase_migrations.schema_migrations (version, name) values ('20261114210000', 'nouveau_compte_suppression') on conflict do nothing;
commit;
