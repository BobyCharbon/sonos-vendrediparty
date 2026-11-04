-- Compte de démo pour la revue Apple (accord de l'admin du 04.11.2026, point 4) : « Apple-test », Guest, actif.
-- Données seulement (aucune structure) ; numéro de test à code fixe réglé dans Supabase › Auth (sms_test_otp).
begin;
update public.profiles set display_name = 'Apple-test', status = 'active', role = 'guest'
 where id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
insert into supabase_migrations.schema_migrations (version, name) values ('20261105100000', 'compte_demo_apple')
 on conflict do nothing;
commit;
