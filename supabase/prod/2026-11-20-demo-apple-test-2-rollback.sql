-- Retour arrière de 2026-11-20-demo-apple-test-2-apply.sql : retire la demande de message et rend le profil vide.
begin;
delete from public.direct_chats where requested_by = '6cb2b529-cd4b-4121-9f30-c29d70facfc5'
  and '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' in (user_a, user_b) and status = 'request';
delete from public.notifications where user_id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' and kind = 'message_request';
delete from public.terms_acceptances where user_id = '6cb2b529-cd4b-4121-9f30-c29d70facfc5';
update public.profiles set first_name = '', last_name = '', display_name = '' where id = '6cb2b529-cd4b-4121-9f30-c29d70facfc5';
delete from supabase_migrations.schema_migrations where version = '20261120060000';
commit;
