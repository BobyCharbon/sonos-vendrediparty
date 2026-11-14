-- Fiche d'un événement en direct pour tout le monde (avis ead4902642da de l'admin, 13.11.2026) : « Qui amène quoi » en
-- quantités (bring_claims) passe aussi par le temps réel, comme les réponses, votes et messages. La règle de lecture
-- existante (« voir qui amène combien ») décide qui reçoit quoi. Purement additive et rejouable.
do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime'
                 and schemaname = 'public' and tablename = 'bring_claims') then
    alter publication supabase_realtime add table public.bring_claims;
  end if;
end $$;
