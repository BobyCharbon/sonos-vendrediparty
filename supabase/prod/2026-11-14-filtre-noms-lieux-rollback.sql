-- PROD, retour arrière de filtre_noms_lieux (20261114123000) : prénom, nom, nom de lien et nom de lieu ne sont plus filtrés.
begin;
drop trigger if exists profiles_identity_moderation on public.profiles;
drop trigger if exists invite_links_label_moderation on private.invite_links;
drop trigger if exists events_place_moderation on public.events;
drop function if exists private.moderate_profile_identity();
drop function if exists private.moderate_invite_label();
drop function if exists private.moderate_event_place();
delete from supabase_migrations.schema_migrations where version = '20261114123000';
commit;
