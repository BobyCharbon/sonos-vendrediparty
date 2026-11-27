-- Retour arrière de 2026-11-27-coorganisateurs-apercu-groupe-apply.sql : retire les deux fonctions ajoutées.
-- L'écran se replie seul (fonction absente) : aucune suggestion de co-organisateur hors admins, invitation de groupe générique.
begin;
drop function if exists public.co_organizer_suggestions();
drop function if exists public.group_invite_preview(uuid);
delete from supabase_migrations.schema_migrations where version = '20261127100000';
commit;
