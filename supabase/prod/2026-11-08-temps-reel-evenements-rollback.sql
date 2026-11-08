-- PROD, retour arrière de temps_reel_evenements (20261108100000) : les 7 tables quittent le temps réel. Tout ou rien.
begin;
do $$
declare t text;
begin
  foreach t in array array['events', 'event_invites', 'event_groups', 'member_group_members', 'event_organizers',
                           'bring_items', 'date_options'] loop
    if exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime drop table public.%I', t);
    end if;
  end loop;
end $$;
delete from supabase_migrations.schema_migrations where version = '20261108100000';
commit;
