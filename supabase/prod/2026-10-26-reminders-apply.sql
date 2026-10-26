-- PROD, rappels choisis par chaque personne (20261026090000_reminders_personal).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod ») pour cette migration.
-- À coller tel quel dans Supabase → projet VendrediParty → SQL Editor → Run.
-- Tout-ou-rien : si une ligne échoue, rien n'est appliqué. Rejouable sans risque.
-- Retour arrière exact : 2026-10-26-reminders-rollback.sql (lit la sauvegarde faite ici).
begin;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);

-- Sauvegarde des rappels AVANT changement (une seule fois : un second passage ne l'écrase pas).
create table if not exists private.reminders_backup_20261026_events as select id, reminders from public.events;
create table if not exists private.reminders_backup_20261026_prefs as select user_id, reminders from public.notification_prefs;
revoke all on private.reminders_backup_20261026_events, private.reminders_backup_20261026_prefs from public, anon, authenticated;

-- ════ 20261026090000_reminders_personal ════
-- Rappels d'événement : c'est à chaque personne de choisir (Réglages → Notifications), plus à l'organisateur.
-- Un rappel part quand il est à la fois dans l'événement ET dans les préférences de la personne : l'événement
-- propose désormais tous les rappels, la préférence de la personne décide seule.
-- Purement additif et rejouable : rien n'est retiré, aucune ligne déjà à jour n'est touchée.

alter table public.events alter column reminders set default array['7d', '1d', '2h', '0h']::text[];
update public.events
  set reminders = array['7d', '1d', '2h', '0h']::text[]
  where not (reminders @> array['7d', '1d', '2h', '0h']::text[]);

-- Préférences : H-2 et « au début » par défaut, et ajoutés à tous les comptes existants (leurs autres choix restent).
alter table public.notification_prefs alter column reminders set default array['2h', '0h']::text[];
update public.notification_prefs
  set reminders = array(select distinct r from unnest(reminders || array['2h', '0h']::text[]) as r order by r)
  where not (reminders @> array['2h', '0h']::text[]);

insert into supabase_migrations.schema_migrations (version, name, statements) values ('20261026090000', 'reminders_personal', array[$mig$-- Rappels d'événement : c'est à chaque personne de choisir (Réglages → Notifications), plus à l'organisateur.
-- Un rappel part quand il est à la fois dans l'événement ET dans les préférences de la personne : l'événement
-- propose désormais tous les rappels, la préférence de la personne décide seule.
-- Purement additif et rejouable : rien n'est retiré, aucune ligne déjà à jour n'est touchée.

alter table public.events alter column reminders set default array['7d', '1d', '2h', '0h']::text[];
update public.events
  set reminders = array['7d', '1d', '2h', '0h']::text[]
  where not (reminders @> array['7d', '1d', '2h', '0h']::text[]);

-- Préférences : H-2 et « au début » par défaut, et ajoutés à tous les comptes existants (leurs autres choix restent).
alter table public.notification_prefs alter column reminders set default array['2h', '0h']::text[];
update public.notification_prefs
  set reminders = array(select distinct r from unnest(reminders || array['2h', '0h']::text[]) as r order by r)
  where not (reminders @> array['2h', '0h']::text[]);
$mig$]) on conflict (version) do nothing;
commit;

-- Contrôle : rappels des comptes et des événements après application.
select 'prefs' as quoi, reminders::text, count(*) from public.notification_prefs group by 2
union all select 'events', reminders::text, count(*) from public.events group by 2 order by 1, 2;
