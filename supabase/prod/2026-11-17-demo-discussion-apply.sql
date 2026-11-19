-- PROD, données de démonstration pour la revue Apple (17.11.2026) : la discussion NATIVE de l'événement
-- « Soirée démo Vendredi Party » (Apple-test invité et co-organisateur) reçoit 3 messages de Boby, dont une annonce
-- épinglée et une citation d'Apple-test : l'examinateur voit tout de suite le fil, le bandeau, la mention et la cloche.
-- Données seulement ; rejouable une fois (enregistrée comme 20261117190100).
begin;
do $$
declare
  boby uuid := '298ff6e0-07b2-4127-bb69-d254dd63a3d5';
  apple uuid := '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
  e uuid;
begin
  select id into e from public.events where title = 'Soirée démo Vendredi Party' and created_by = boby
    and starts_at = '2026-12-12 19:00:00+01';
  if e is null then raise exception 'Soirée démo introuvable'; end if;
  update public.events set forum_enabled = true where id = e;
  insert into public.messages (event_id, user_id, body, announcement, pinned, created_at) values
    (e, boby, 'Bienvenue dans la discussion de la soirée ! On se retrouve à 19 h.', true, true, now() - interval '2 hours'),
    (e, boby, 'Pensez à répondre « Présent » pour commander au bar.', false, false, now() - interval '90 minutes');
  insert into public.messages (event_id, user_id, body, mentions, created_at)
    values (e, boby, '@Apple-test tu peux régler les notifications avec la cloche en haut de la discussion.', array[apple], now() - interval '1 hour');
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261117190100', 'demo_discussion_native') on conflict do nothing;
commit;
