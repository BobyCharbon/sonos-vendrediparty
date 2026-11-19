-- la panne des notifications (20261119150000) laissait en
-- attente des notifications vieilles de plusieurs jours ; à la reprise, elles seraient toutes parties d'un coup.
-- Plus de 2 heures : marquées traitées pour le push (iPhone : skipped ; web : livraison annulée). Elles restent dans
-- l'Activité de chacun, non lues. Données seulement, rejouable. Tout ou rien.
update public.notifications set skipped = true
where sent_at is null and not skipped and created_at < now() - interval '2 hours';
insert into private.web_push_deliveries (notification_id, subscription_id, status, error)
  select n.id, s.id, 'cancelled', 'StaleAfterOutage'
  from public.notifications n join private.web_push_subscriptions s on s.user_id = n.user_id
  where n.created_at < now() - interval '2 hours' and n.created_at > now() - interval '8 days'
on conflict (notification_id, subscription_id) do nothing;
update private.web_push_deliveries d set status = 'cancelled', error = 'StaleAfterOutage', lease_until = null
  from public.notifications n where n.id = d.notification_id and d.status = 'queued' and n.created_at < now() - interval '2 hours';
