-- PROD, retour arrière de la collection (20261104210000 : catalogue, exemplaires et certificats, cadeaux d'événement
-- EFFACÉS), puis des garde-fous (20261104170000), de la boucle du jour (20261104150000) PUIS du compagnon (20261104130000) : le Compagnon disparaît (personnages, cadeaux et journal EFFACÉS,
-- l'app affiche « ne répond pas »), plus de rappel ni d'alerte. Les notifications pet_* déjà envoyées restent dans
-- l'historique. Les branches pet_daily / pet_alert ajoutées à private.web_push_allowed et private.may_receive_push
-- sont retirées de la définition en place (les autres types restent intacts). Tout ou rien.
begin;

-- ══ Nouvelle économie (20261105120000) : caisse commune EFFACÉE ; les cadeaux et le catalogue partent plus bas avec le
-- Compagnon et la collection ══
drop function if exists public.pet_pot_give(text, integer, text, text);
drop function if exists public.pet_pot_get(text);
drop function if exists private.pet_pot_state(uuid);
drop function if exists public.pet_pot_public();
drop table if exists public.pet_pot_gifts;
drop table if exists public.pet_pot_goals;
delete from private.one_time_changes where name = 'zicou_economie_2026_11_05';
delete from supabase_migrations.schema_migrations where version = '20261105120000';

-- ══ Pièces Zicou d'un événement (20261105090000) : réglages et journal EFFACÉS ; pet_load et pet_event_draw_due
-- sont supprimés plus bas avec la collection et le Compagnon ══
drop function if exists public.pet_event_coins_claim(uuid[], text);
drop function if exists public.pet_event_coins_set(uuid, integer);
drop function if exists public.pet_event_coins_get(uuid);
drop function if exists private.pet_event_coins_due(uuid);
drop function if exists private.pet_event_coins_grant(uuid);
drop function if exists private.pet_event_coins_open_until(uuid);
drop table if exists public.pet_event_coin_grants;
drop table if exists public.pet_event_coins;
delete from public.role_permissions where perm = 'zicou.event_coins';
delete from public.permissions where key = 'zicou.event_coins';
delete from private.one_time_changes where name = 'zicou_event_coins_2026_11_05';
delete from supabase_migrations.schema_migrations where version = '20261105090000';

-- ══ Zicou sur la fiche profil (20261104240000) ══
drop function if exists public.pet_profile(uuid, text);
delete from supabase_migrations.schema_migrations where version = '20261104240000';

-- ══ Réactions de Zicou (20261104230000, neutre) : seule sa version était notée ══
delete from supabase_migrations.schema_migrations where version = '20261104230000';

-- ══ D'abord la collection (20261104210000) ══
do $$
begin
  perform cron.unschedule('pet-event-draw') where exists (select 1 from cron.job where jobname = 'pet-event-draw');
end $$;
drop trigger if exists pets_moderate on public.pets;
drop function if exists private.moderate_pet();
drop function if exists public.pet_awards_claim(uuid[], text);
drop function if exists public.pet_drop_bounds_set(boolean, jsonb, integer, integer);
drop function if exists private.pet_event_draw_due(uuid);
drop function if exists private.pet_event_draw(uuid);
drop function if exists public.pet_event_drop_publish(uuid);
drop function if exists public.pet_event_drop_delete(uuid);
drop function if exists public.pet_event_drop_save(uuid, jsonb);
drop function if exists private.pet_drop_editable(uuid);
drop function if exists private.pet_drop_check(uuid, jsonb, text);
drop function if exists public.pet_event_drop_get(uuid);
drop function if exists private.pet_drop_view(public.pet_event_drops, boolean);
drop function if exists private.pet_drop_roll(text, uuid, uuid, integer);
drop function if exists private.pet_drop_draw_at(uuid);
drop function if exists private.pet_drop_eligible(uuid);
drop function if exists private.pet_drop_role(uuid);
drop function if exists public.pet_verify(text);
drop function if exists public.pet_cert_set(uuid, text, text, text, text);
drop function if exists public.pet_mint(text, text, text, text);
drop function if exists private.pet_mint_for(uuid, text, text, text, uuid);
drop function if exists private.pet_item_json(public.pet_items);
drop function if exists private.pet_item_payload(public.pet_items);
drop table if exists public.pet_event_awards;
drop table if exists public.pet_event_drops;
drop table if exists private.pet_drop_bounds;
drop table if exists public.pet_item_owners;
drop table if exists public.pet_items;
drop function if exists private.pet_items_guard();
drop table if exists public.pet_catalog;
-- Points d'accroche de la modération : de nouveau vides (comme 20261104200000, qui reste en prod).
create or replace function private.report_snapshot_pet(p_kind text, p_id text, viewer uuid) returns jsonb
language sql stable security definer set search_path = '' as $$ select null::jsonb; $$;
create or replace function private.moderation_hide_pet(p_kind text, p_id text) returns void
language plpgsql security definer set search_path = '' as $$ begin return; end $$;
revoke all on function private.report_snapshot_pet(text, text, uuid), private.moderation_hide_pet(text, text)
  from public, anon, authenticated;
-- pet_load, pet_friends_of, pet_state_problem : supprimés plus bas avec le Compagnon (sections suivantes).
delete from supabase_migrations.schema_migrations where version = '20261104210000';

-- ══ Puis les garde-fous (20261104170000) : fonctions à clé du serveur, enrôlement, colonnes d'appartenance ══
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
