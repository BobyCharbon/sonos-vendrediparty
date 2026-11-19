-- PROD, retour arrière de notifications_anciennes_sans_push (20261119150100) : rien à défaire (notifications déjà
-- passées ou trop anciennes) ; seul l'enregistrement part.
begin;
delete from supabase_migrations.schema_migrations where version = '20261119150100';
commit;
