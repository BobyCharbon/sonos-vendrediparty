-- PROD, retour arrière de 20261028170000_event_templates : retire la table des modèles (et les modèles créés).
begin;
drop table if exists public.event_templates;
drop function if exists private.guard_event_template();
drop function if exists private.guard_event_template() cascade;
delete from supabase_migrations.schema_migrations where version = '20261028170000';
commit;
