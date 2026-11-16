-- PROD, retour arrière de la suite du bar (devise, récapitulatif, notification « verre servi ») : plus de récapitulatif ni de
-- choix de devise, montants toujours en CHF. La colonne `currency` reste (valeur CHF par défaut, sans effet). Pour retirer
-- tout le bar : ensuite 2026-11-10-bar-soiree-rollback.sql. Tout ou rien.
begin;
drop function if exists public.bar_recap(uuid);
drop function if exists public.bar_set_currency(uuid, text);
create or replace function private.bar_chf(n numeric, e uuid) returns text
language sql stable set search_path = '' as $$
  select case when n = trunc(n) then trunc(n)::text else to_char(n, 'FM999990.00') end || ' CHF';
$$;
update public.event_bars set currency = 'CHF' where currency <> 'CHF';
delete from supabase_migrations.schema_migrations where version = '20261116090000';
delete from supabase_migrations.schema_migrations where version = '20261116100000';
delete from supabase_migrations.schema_migrations where version = '20261116120000';
commit;
notify pgrst, 'reload schema';
