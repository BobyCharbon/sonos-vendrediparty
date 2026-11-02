-- PROD, retour arrière de bring_quantities (20261102120000) : enlève les quantités partagées, remet la garde d'avant.
begin;
drop trigger if exists bring_claims_guard on public.bring_claims;
drop function if exists public.guard_bring_claim();
drop table if exists public.bring_claims;
drop function if exists private.bring_item_event(uuid);
alter table public.bring_items drop constraint if exists bring_items_quantity_check;
alter table public.bring_items drop column if exists quantity;
create or replace function public.guard_bring_item() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is not null and not (public.is_admin() or public.is_organizer(old.event_id)) then
    new.event_id := old.event_id;
    new.label := old.label;
    new.sort := old.sort;
    new.added_by := old.added_by;
  end if;
  return new;
end $$;
delete from supabase_migrations.schema_migrations where version = '20261102120000';
commit;
