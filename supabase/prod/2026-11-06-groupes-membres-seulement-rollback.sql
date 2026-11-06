-- PROD, retour arrière de groupes_membres_seulement (20261106090000) : un organisateur peut de nouveau ajouter
-- n'importe quel groupe et réserver un événement à Vendredi Party sans en faire partie. Tout ou rien.
begin;
drop trigger if exists guard_event_vip_visibility on public.events;
drop trigger if exists guard_event_group on public.event_groups;
drop function if exists private.guard_event_vip_visibility();
drop function if exists private.guard_event_group();
drop function if exists private.may_use_group(uuid);
delete from supabase_migrations.schema_migrations where version = '20261106090000';
commit;

notify pgrst, 'reload schema';
