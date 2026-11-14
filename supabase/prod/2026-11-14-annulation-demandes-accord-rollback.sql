-- PROD, retour arrière de annulation_demandes_accord (20261114220000) : les personnes en attente d'accord ne sont plus
-- prévenues d'une annulation (les notifications déjà envoyées restent).
begin;
drop trigger if exists events_tell_waiting_of_cancel on public.events;
drop function if exists private.tell_waiting_of_cancel();
delete from supabase_migrations.schema_migrations where version = '20261114220000';
commit;
