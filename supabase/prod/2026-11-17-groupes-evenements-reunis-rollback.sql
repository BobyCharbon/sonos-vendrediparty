-- PROD, retour arrière de groupes_evenements_reunis (20261117120000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;


delete from supabase_migrations.schema_migrations where version = '20261117120000';
commit;
