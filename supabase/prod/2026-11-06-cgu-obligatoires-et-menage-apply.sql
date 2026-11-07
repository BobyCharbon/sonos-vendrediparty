-- Accord de l'admin (06.11.2026) : « Exiger les conditions d'utilisation » (Apple 1.2) et suppression de l'événement
-- de test « [TEST] Karting » visible de tous. Données seulement.
begin;
update private.moderation_settings set terms_enforced = true where id = 1;
delete from public.events where id = '6fc98225-0130-48d3-b8ff-9dea4977266c' and title = '[TEST] Karting';
insert into supabase_migrations.schema_migrations (version, name) values ('20261106080000', 'cgu_obligatoires_et_menage')
 on conflict do nothing;
commit;
