-- PROD, données de démonstration pour la revue Apple (20.11.2026) : second compte de démo « Apple-test 2 »
-- (+41 79 000 00 01, 6cb2b529…), annoncé par les notes de revue (section DISCUSSIONS) et le guide joint.
--  * profil complet (prénom, nom, surnom), CGU de la version en vigueur acceptées (au nom du compte, comme dans l'app) ;
--  * aucun groupe ni événement en commun avec « Apple-test » ;
--  * une demande de message en attente d'Apple-test 2 vers Apple-test (Discussions › Demandes (1)), écrite au nom
--    d'Apple-test 2 : les gardes de la base (un seul texte, ni lien ni numéro) et la notification jouent comme dans l'app.
-- Le code fixe du numéro est réglé à part (Supabase › Auth › Test OTP), jamais dans le dépôt. Rejouable une fois.
begin;
do $$
declare
  apple uuid := '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
  apple2 uuid := '6cb2b529-cd4b-4121-9f30-c29d70facfc5';
  c uuid;
  v text := (select terms_version from private.moderation_settings where id = 1);
begin
  update public.profiles set first_name = 'Apple', last_name = 'Review 2', display_name = 'Apple-test 2' where id = apple2;
  insert into public.direct_chats (user_a, user_b, created_by, status, requested_by, requested_at)
  values (least(apple, apple2), greatest(apple, apple2), apple2, 'request', apple2, now())
  on conflict (user_a, user_b) do nothing returning id into c;
  if c is null then raise exception 'Une conversation existe déjà entre les deux comptes de démo'; end if;

  perform set_config('request.jwt.claims', json_build_object('sub', apple2, 'role', 'authenticated')::text, true);
  execute 'set local role authenticated';
  perform public.accept_terms(v);
  insert into public.direct_messages (chat_id, user_id, body)
  values (c, apple2, 'Salut, on s''est croisés à la soirée démo ?');
  execute 'reset role';
  perform set_config('request.jwt.claims', '', true);
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261120060000', 'demo_apple_test_2')
  on conflict do nothing;
commit;
