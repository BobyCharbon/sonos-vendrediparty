-- Retour arrière des messages de démonstration de la discussion (17.11).
begin;
delete from public.messages where user_id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5'
  and event_id in (select id from public.events where title = 'Soirée démo Vendredi Party' and starts_at = '2026-12-12 19:00:00+01')
  and body in ('Bienvenue dans la discussion de la soirée ! On se retrouve à 19 h.', 'Pensez à répondre « Présent » pour commander au bar.',
               '@Apple-test tu peux régler les notifications avec la cloche en haut de la discussion.');
delete from supabase_migrations.schema_migrations where version = '20261117190100';
commit;
