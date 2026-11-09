-- Compte de démo de la revue Apple « Apple-test » (accord de l'admin du 09.11.2026 : « Oui complète et remplis
-- complètement son profil ») : Guest+ (« Ton avis », ses événements attendent une validation), prénom « Apple »,
-- nom « Review », photo neutre « AR » (déjà déposée dans profile-photos/<id>/apple-review.jpg). Données seulement.
begin;
update public.profiles
   set first_name = 'Apple', last_name = 'Review', display_name = 'Apple-test',
       avatar_url = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd/apple-review.jpg', role = 'guestplus', status = 'active'
 where id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
insert into supabase_migrations.schema_migrations (version, name) values ('20261109010000', 'apple_test_profil')
  on conflict (version) do nothing;
commit;
