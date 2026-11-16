-- Retour arrière de conformite_app_store (20261116150000) : CGU 2026-11-04, blocage sans signalement, sans garde tabac ni
-- bar privé. Les acceptations des CGU 2026-11-16 restent (sans effet).
begin;
update private.moderation_settings set terms_version = '2026-11-04';
alter table private.moderation_settings alter column terms_version set default '2026-11-04';
create or replace function public.set_direct_block(target uuid, blocked boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if target is null or target = auth.uid() then raise exception 'Choisis une autre personne' using errcode = '22023'; end if;
  if blocked then
    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
  else
    delete from public.direct_blocks where user_id = auth.uid() and blocked_id = target;
  end if;
end $$;
do $$ begin
  if to_regclass('public.event_bar_items') is not null then drop trigger if exists bar_item_allowed on public.event_bar_items; end if;
  if to_regclass('public.event_bars') is not null then drop trigger if exists bar_private_only on public.event_bars; end if;
end $$;
drop trigger if exists event_public_bar_guard on public.events;
drop function if exists private.bar_item_allowed();
drop function if exists private.bar_private_only();
drop function if exists private.event_public_bar_guard();
drop function if exists private.event_is_public(uuid);
delete from supabase_migrations.schema_migrations where version = '20261116150000';
commit;
notify pgrst, 'reload schema';
