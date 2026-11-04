-- PROD, retour arrière des garde-fous (20261104170000), de la boucle du jour (20261104150000) PUIS du compagnon (20261104130000) : le Compagnon disparaît (personnages, cadeaux et journal EFFACÉS,
-- l'app affiche « ne répond pas »), plus de rappel ni d'alerte. Les notifications pet_* déjà envoyées restent dans
-- l'historique. Les branches pet_daily / pet_alert ajoutées à private.web_push_allowed et private.may_receive_push
-- sont retirées de la définition en place (les autres types restent intacts). Tout ou rien.
begin;

-- ══ D'abord les garde-fous (20261104170000) : fonctions à clé du serveur, enrôlement, colonnes d'appartenance ══
drop function if exists public.pet_gift(uuid, text, text);
drop function if exists public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb, text);
drop function if exists public.pet_load(text, text);
drop function if exists private.pet_state_problem(jsonb, jsonb, public.pets);
drop function if exists public.pet_server_enroll(text);
drop function if exists private.pet_server_guard(text);
drop function if exists private.pet_server_ok(text);
drop table if exists private.pet_server_keys;
delete from vault.secrets where name = 'pet_server_key';
alter table public.member_group_members drop column if exists added_at;
alter table public.member_group_members drop column if exists added_by;
delete from supabase_migrations.schema_migrations where version = '20261104170000';

-- ══ Puis la boucle du jour (20261104150000) : mesure, rappel intelligent, interrupteurs pet_gifts / pet_streaks ══
drop function if exists public.pet_admin_stats();
drop view if exists private.pet_engagement;
drop function if exists private.pet_at_soiree(uuid, timestamptz);
drop function if exists public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb);
drop function if exists public.pet_load(text);
drop table if exists public.pet_opens;
do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
begin
  def := replace(def, E'\n    when ''pet_gift'' then coalesce(prefs.pet_gifts, true)', '');
  def := replace(def, E'\n    when ''pet_streak'' then coalesce(prefs.pet_streaks, true)', '');
  execute def;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  def := replace(def, 'kind in (''pet_daily'', ''pet_alert'', ''pet_gift'', ''pet_streak'')', 'kind in (''pet_daily'', ''pet_alert'')');
  execute def;
end $$;
alter table public.notification_prefs drop column if exists pet_gifts;
alter table public.notification_prefs drop column if exists pet_streaks;
delete from supabase_migrations.schema_migrations where version = '20261104150000';

-- ══ Puis le Compagnon lui-même (20261104130000) ══

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
