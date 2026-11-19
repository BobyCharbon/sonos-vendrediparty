-- PROD, test_notification_apns (20261119150200) : notification de test (push_test) aux seuls comptes qui ont un iPhone
-- inscrit, après l'ajout des secrets APNs (19.11, demandé par l'admin). Sur une base vide : ne fait rien.
begin;
select public.queue_notification(t.user_id, 'push_test', null, 'Vendredi Party', 'Les notifications de Vendredi Party fonctionnent.')
from (select distinct user_id from public.push_tokens where token like 'apns:%' and session_id is not null) t;
insert into supabase_migrations.schema_migrations (version, name) values ('20261119150200', 'test_notification_apns') on conflict do nothing;
commit;
