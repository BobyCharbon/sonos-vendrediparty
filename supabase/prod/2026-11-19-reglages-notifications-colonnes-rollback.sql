-- PROD, retour arrière de reglages_notifications_colonnes (20261119150000) : les colonnes restent (une fonction de la base
-- les lit ; les retirer remettrait la panne des notifications) ; seul l'enregistrement de la migration part.
begin;
delete from supabase_migrations.schema_migrations where version = '20261119150000';
commit;
