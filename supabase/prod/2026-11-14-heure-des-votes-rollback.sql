-- PROD, retour arrière de heure_des_votes (20261114100000) : plus d'heure sur les votes de dates.
begin;
drop trigger if exists date_votes_time on public.date_votes;
drop function if exists private.date_vote_time();
alter table public.date_votes drop column if exists voted_at;
delete from supabase_migrations.schema_migrations where version = '20261114100000';
commit;
