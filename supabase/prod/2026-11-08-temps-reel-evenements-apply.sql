-- PROD, temps_reel_evenements (20261108100000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Ajoute 7 tables au temps réel (liste des événements et fiche à jour sans recharger). Aucune donnée modifiée. Rejouable.
begin;
-- Événements en temps réel (retour de l'admin du 08.11) : ajouté à un groupe ou invité → l'événement apparaît tout de
-- suite dans la liste ; dans un événement, ce que font les autres (qui amène quoi, dates proposées, modifications,
-- co-organisateurs) s'affiche sans recharger. Les règles d'accès (RLS) s'appliquent aussi au temps réel : chacun ne
-- reçoit que ce qu'il a le droit de voir. Purement additif et rejouable.
do $$
declare t text;
begin
  foreach t in array array['events', 'event_invites', 'event_groups', 'member_group_members', 'event_organizers',
                           'bring_items', 'date_options'] loop
    if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261108100000', 'temps_reel_evenements')
  on conflict (version) do nothing;
commit;
