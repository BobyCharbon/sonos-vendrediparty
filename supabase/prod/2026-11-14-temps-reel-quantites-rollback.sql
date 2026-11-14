-- PROD, retour arrière de temps_reel_quantites (20261114110000) : bring_claims quitte le temps réel.
begin;
do $$
begin
  if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime'
             and schemaname = 'public' and tablename = 'bring_claims') then
    alter publication supabase_realtime drop table public.bring_claims;
  end if;
end $$;
delete from supabase_migrations.schema_migrations where version = '20261114110000';
commit;
