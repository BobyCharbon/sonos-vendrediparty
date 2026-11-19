-- PROD, reglages_notifications_colonnes (20261119150000) : répare l'envoi des notifications (iPhone et web) en prod.
-- Additive et rejouable. Tout ou rien.
begin;
alter table public.notification_prefs add column if not exists pet_daily boolean not null default true;
alter table public.notification_prefs add column if not exists pet_alerts boolean not null default true;
alter table public.notification_prefs add column if not exists pet_gifts boolean not null default true;
alter table public.notification_prefs add column if not exists pet_streaks boolean not null default true;
alter table public.notification_prefs add column if not exists pet_bar boolean not null default true;
alter table public.notification_prefs add column if not exists group_added boolean not null default true;
alter table public.notification_prefs add column if not exists booking_requests boolean not null default true;
alter table public.notification_prefs add column if not exists pronos boolean not null default true;
alter table public.notification_prefs add column if not exists message_requests boolean not null default true;

insert into supabase_migrations.schema_migrations (version, name) values ('20261119150000', 'reglages_notifications_colonnes') on conflict do nothing;
commit;
