-- PROD, retour arrière de reponse_profil_complet (20261110100000) : retire les deux gardes. Tout ou rien.
begin;
drop trigger if exists rsvps_identity on public.rsvps;
drop trigger if exists date_votes_identity on public.date_votes;
drop function if exists private.guard_answer_identity();
delete from supabase_migrations.schema_migrations where version = '20261110100000';
commit;
