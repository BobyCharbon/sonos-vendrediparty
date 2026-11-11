-- PROD, retour arrière de agenda_abonnement (20261111090000) : retire les agendas abonnés (les agendas déjà abonnés
-- reçoivent ensuite une erreur et gardent ce qu'ils avaient). Tout ou rien.
begin;
drop function if exists public.calendar_feed(text);
drop function if exists public.calendar_feed_token(uuid);
drop function if exists public.calendar_feed_token(uuid, boolean);
drop table if exists public.calendar_feed_events;
drop table if exists public.calendar_feeds;
delete from supabase_migrations.schema_migrations where version = '20261111090000';
commit;
