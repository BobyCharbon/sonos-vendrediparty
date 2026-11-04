-- PROD, retour arrière de compagnon (20261104130000) : le Compagnon disparaît (personnages, cadeaux et journal EFFACÉS,
-- l'app affiche « ne répond pas »), plus de rappel ni d'alerte. Les notifications pet_* déjà envoyées restent dans
-- l'historique. Les branches pet_daily / pet_alert ajoutées à private.web_push_allowed et private.may_receive_push
-- sont retirées de la définition en place (les autres types restent intacts). Tout ou rien.
begin;

do $$
begin
  perform cron.unschedule('pet-notify') where exists (select 1 from cron.job where jobname = 'pet-notify');
end $$;

drop function if exists private.pet_notify(timestamptz);
drop function if exists public.pet_gift(uuid, text);
drop function if exists public.pet_friend(uuid);
drop function if exists public.pet_friends();
drop function if exists private.pet_card(uuid, uuid);
drop function if exists public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb);
drop function if exists public.pet_load();
drop function if exists private.pet_guard();
drop function if exists private.pet_friends_of(uuid);
drop table if exists public.pet_journal;
drop table if exists public.pet_gifts;
drop table if exists public.pets;

do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
begin
  def := replace(def, E'\n    when ''pet_daily'' then coalesce(prefs.pet_daily, true)', '');
  def := replace(def, E'\n    when ''pet_alert'' then coalesce(prefs.pet_alerts, true)', '');
  execute def;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  def := replace(def, E'\n    or (kind in (''pet_daily'', ''pet_alert'') and private.is_account_active(uid))', '');
  execute def;
end $$;

alter table public.notification_prefs drop column if exists pet_daily;
alter table public.notification_prefs drop column if exists pet_alerts;

delete from supabase_migrations.schema_migrations where version = '20261104130000';
commit;

notify pgrst, 'reload schema';
