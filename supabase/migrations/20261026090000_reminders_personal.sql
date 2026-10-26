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
