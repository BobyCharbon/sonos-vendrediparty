-- Retour arrière : les votes redeviennent ouverts à tous ceux qui voient l'événement.
begin;
drop trigger if exists poll_votes_presence on public.poll_votes;
drop function if exists private.poll_vote_presence();
delete from supabase_migrations.schema_migrations where version = '20261119170000';
commit;
