-- Tâches planifiées. Prérequis (une fois, dans le SQL editor de Supabase) :
--   select vault.create_secret('https://<project-ref>.supabase.co', 'project_url');
--   select vault.create_secret('<service_role_key>', 'service_role_key');

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Rappels, relances et clôture automatique des sondages de dates
select cron.schedule('scheduled-jobs', '*/5 * * * *', $$ select public.run_scheduled_jobs(); $$);

-- Envoi des notifications push en attente (respecte le mode silencieux)
select cron.schedule('send-push', '* * * * *', $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/send-push',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'service_role_key')
    ),
    body := '{}'::jsonb
  );
$$);

-- Purge de l'historique après 90 jours
select cron.schedule('purge-notifications', '0 4 * * *', $$
  delete from public.notifications where created_at < now() - interval '90 days';
$$);
