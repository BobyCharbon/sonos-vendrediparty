-- PROD, retour arrière de ia_personnes_citees (20261106210000) : la colonne events.ai_suggested disparaît (le serveur
-- et l'étape 2 s'en passent : personnes citées seulement dans l'adresse de l'étape 2, comme avant). Tout ou rien.
begin;
alter table public.events drop column if exists ai_suggested;
delete from supabase_migrations.schema_migrations where version = '20261106210000';
commit;

notify pgrst, 'reload schema';
