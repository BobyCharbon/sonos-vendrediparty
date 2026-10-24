-- Base de TEST seulement (Vendrediparty-test, ewromqfsmcqsthftyhzm), après avoir rejoué supabase/migrations.
-- Jamais en prod. Rejouable.

-- 1. Les envois de notifications appellent les fonctions Edge de CETTE base (la migration
--    push_delivery_pipeline enregistre l'adresse de la prod dans le coffre-fort).
select vault.update_secret((select id from vault.secrets where name = 'project_url'), 'https://ewromqfsmcqsthftyhzm.supabase.co');

-- 2. Compte Root de test : même identifiant que le root de la prod (private.is_root), numéro de test
--    à code fixe (Auth → numéros de test). Les champs texte d'Auth doivent être '' et non NULL.
insert into auth.users (instance_id, id, aud, role, phone, phone_confirmed_at, created_at, updated_at, raw_app_meta_data, raw_user_meta_data,
  is_sso_user, is_anonymous, confirmation_token, recovery_token, email_change_token_new, email_change, email_change_token_current,
  phone_change, phone_change_token, reauthentication_token)
select '00000000-0000-0000-0000-000000000000', '298ff6e0-07b2-4127-bb69-d254dd63a3d5', 'authenticated', 'authenticated', '41765576900',
  now(), now(), now(), '{"provider":"phone","providers":["phone"]}', '{}', false, false, '', '', '', '', '', '', '', ''
where not exists (select 1 from auth.users where id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5');
insert into auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
select '298ff6e0-07b2-4127-bb69-d254dd63a3d5', '298ff6e0-07b2-4127-bb69-d254dd63a3d5',
  '{"sub":"298ff6e0-07b2-4127-bb69-d254dd63a3d5","phone":"41765576900","phone_verified":true}', 'phone', now(), now(), now()
where not exists (select 1 from auth.identities where user_id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5');
-- 3. Photo : envoyer d'abord une image dans profile-photos/298ff6e0-…/test.png (la garde de profil vérifie
--    qu'elle existe), puis :
-- update public.profiles set display_name = 'Boby', first_name = 'Ludovic', last_name = 'Test',
--   avatar_url = '298ff6e0-07b2-4127-bb69-d254dd63a3d5/test.png' where id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5';
