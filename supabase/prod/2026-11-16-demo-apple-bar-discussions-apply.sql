-- PROD, données de démonstration pour la revue Apple (16.11.2026 ; bar et Discussions ouverts en production) : le compte
-- « Apple-test » (49d9777e…) doit pouvoir essayer le bar et les Discussions sans toucher aux vrais événements.
--  * « Soirée démo Vendredi Party » (sur invitation, sans lien public, sans annonce) : Apple-test invité ET co-organisateur
--    (il voit « Gérer le bar », le récapitulatif et « Scanner au bar ») ; bar PAYANT ouvert aux commandes (événement privé),
--    3 articles dont 2 sans alcool, remboursement par Twint à l'organisateur (Boby). Apple-test répond lui-même « Présent »
--    pour commander.
--  * Groupe « Démo Apple » (Boby + Apple-test) avec 3 messages, et un message direct de Boby à Apple-test.
-- Les fonctions du bar sont appelées au nom de Boby (organisateur, CGU acceptées). Données seulement ; rejouable une fois.
begin;
do $$
declare
  boby uuid := '298ff6e0-07b2-4127-bb69-d254dd63a3d5';
  apple uuid := '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
  e uuid; g uuid; c uuid;
begin
  insert into public.events (title, description, starts_at, ends_at, location_name, visibility, public_link,
                             notify_on_publish, status, created_by)
  values ('Soirée démo Vendredi Party',
          'Événement de démonstration pour la revue Apple. Réponds « Présent » pour commander au bar de la soirée ; en co-organisateur, ouvre « Gérer le bar » pour voir les articles, le direct et le récapitulatif.',
          '2026-12-12 19:00:00+01', '2026-12-13 01:00:00+01', 'Chez Boby', 'invited', false, false, 'published', boby)
  returning id into e;
  insert into public.event_invites (event_id, user_id) values (e, apple) on conflict do nothing;
  insert into public.event_organizers (event_id, user_id) values (e, apple) on conflict do nothing;
  insert into public.rsvps (event_id, user_id, status) values (e, boby, 'yes') on conflict do nothing;

  -- Bar, au nom de Boby (comme dans l'app).
  perform set_config('request.jwt.claims', json_build_object('sub', boby, 'role', 'authenticated')::text, true);
  execute 'set local role authenticated';
  perform public.bar_create(e);
  perform public.bar_save_item(e, '{"name": "Thé froid maison", "emoji": "🧊", "price_chf": 2, "category": "softs"}'::jsonb);
  perform public.bar_save_item(e, '{"name": "Limonade", "emoji": "🍋", "price_chf": 2.5, "category": "softs"}'::jsonb);
  perform public.bar_save_item(e, '{"name": "Bière", "emoji": "🍺", "price_chf": 3, "category": "bieres", "detail": "33 cl", "age_min": 18}'::jsonb);
  perform public.bar_save_settings(e, json_build_object('orders_open', true, 'pay_method', 'twint',
                                                        'repay_by', '2026-12-31')::jsonb);
  execute 'reset role';
  perform set_config('request.jwt.claims', '', true);

  -- Discussions.
  insert into public.member_groups (name, created_by) values ('Démo Apple', boby) returning id into g;
  insert into public.member_group_members (group_id, user_id) values (g, boby), (g, apple) on conflict do nothing;
  insert into public.group_messages (group_id, user_id, body, created_at) values
    (g, boby, 'Salut ! Ici on prépare la Soirée démo du 12 décembre 🎉', now() - interval '3 minutes'),
    (g, boby, 'Le bar est ouvert : réponds « Présent » sur l''événement puis commande depuis ton téléphone.', now() - interval '2 minutes'),
    (g, boby, 'Appui long sur un message pour le signaler ; la fiche d''une personne permet de la bloquer.', now() - interval '1 minute');
  insert into public.direct_chats (user_a, user_b, created_by) values (boby, apple, boby)
    on conflict (user_a, user_b) do update set created_by = excluded.created_by returning id into c;
  insert into public.direct_messages (chat_id, user_id, body) values (c, boby, 'Bienvenue sur Vendredi Party ! Ceci est un message privé de démonstration.');
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261116160000', 'demo_apple_bar_discussions')
  on conflict do nothing;
commit;
