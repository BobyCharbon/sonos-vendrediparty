-- Pas de retour arrière possible pour les données (copies supprimées) : on retire seulement l'inscription.
begin;
delete from supabase_migrations.schema_migrations where version = '20261105191000';
commit;
