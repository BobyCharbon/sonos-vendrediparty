-- Retour arrière : les CGU ne sont plus exigées (l'événement de test supprimé n'est pas recréé).
begin;
update private.moderation_settings set terms_enforced = false where id = 1;
delete from supabase_migrations.schema_migrations where version = '20261106080000';
commit;
