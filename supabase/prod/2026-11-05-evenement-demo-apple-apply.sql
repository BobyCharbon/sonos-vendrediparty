-- Événement de démonstration pour la revue Apple (accord de l'admin du 05.11.2026) : visible SEULEMENT par le compte
-- Apple-test (invitation), sans annonce ni lien public. Données seulement.
begin;
with e as (
  insert into public.events (title, description, starts_at, ends_at, location_name, visibility, public_link,
                             notify_on_publish, status, created_by)
  values ('Soirée démo Vendredi Party',
          'Événement de démonstration pour la revue Apple : réponds Présent, Peut-être ou Absent, regarde qui vient et ajoute-le à ton calendrier.',
          '2026-11-28 19:00:00+01', '2026-11-29 01:00:00+01', 'Chez Boby', 'invited', false, false, 'published',
          '298ff6e0-07b2-4127-bb69-d254dd63a3d5')
  returning id)
insert into public.event_invites (event_id, user_id) select id, '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd' from e;
insert into supabase_migrations.schema_migrations (version, name) values ('20261105190000', 'evenement_demo_apple')
 on conflict do nothing;
commit;
