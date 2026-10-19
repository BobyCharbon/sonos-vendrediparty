create extension if not exists pg_net;

-- Un appareil est lié à la session qui l'a enregistré. Une déconnexion ou une
-- suppression de compte retire donc aussi son droit de recevoir des notifications.
alter table public.push_tokens add column if not exists session_id uuid references auth.sessions(id) on delete cascade;
revoke all on public.push_tokens from anon, authenticated;
grant all on public.push_tokens to service_role;

create or replace function private.register_push_token(device_token text, device_platform text) returns void
language plpgsql security definer set search_path = '' as $$
declare member_id uuid := auth.uid(); active_session uuid;
begin
  if not public.is_active() or device_platform is null or device_platform not in ('ios', 'android')
    or device_token is null or device_token !~ '^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$' then
    raise exception 'Appareil non valide' using errcode = '42501';
  end if;
  select s.id into active_session from auth.sessions s
    where s.user_id = member_id and s.id::text = (auth.jwt() ->> 'session_id');
  if active_session is null then raise exception 'Session expirée' using errcode = '42501'; end if;
  insert into public.push_tokens(token, user_id, platform, session_id, updated_at)
  values(device_token, member_id, device_platform, active_session, now())
  on conflict(token) do update set user_id=excluded.user_id, platform=excluded.platform,
    session_id=excluded.session_id, updated_at=excluded.updated_at;
end;
$$;
revoke all on function private.register_push_token(text,text) from public, anon;
grant execute on function private.register_push_token(text,text) to authenticated;
create or replace function public.register_device_push_token(device_token text, device_platform text) returns void
language sql security invoker set search_path = '' as $$ select private.register_push_token(device_token, device_platform); $$;
revoke all on function public.register_device_push_token(text,text) from public, anon;
grant execute on function public.register_device_push_token(text,text) to authenticated;

create or replace function private.unregister_push_token(device_token text) returns void
language sql security definer set search_path = '' as $$
  delete from public.push_tokens where token=device_token and user_id=auth.uid();
$$;
revoke all on function private.unregister_push_token(text) from public, anon;
grant execute on function private.unregister_push_token(text) to authenticated;
create or replace function public.unregister_device_push_token(device_token text) returns void
language sql security invoker set search_path = '' as $$ select private.unregister_push_token(device_token); $$;
revoke all on function public.unregister_device_push_token(text) from public, anon;
grant execute on function public.unregister_device_push_token(text) to authenticated;

create or replace function private.queue_test_push() returns void
language plpgsql security definer set search_path = '' as $$
declare member_id uuid := auth.uid();
begin
  if not public.is_active() or not exists(select 1 from public.push_tokens where user_id=member_id and session_id is not null) then
    raise exception 'Autorise d’abord les notifications sur ton appareil' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtext(member_id::text));
  if exists(select 1 from public.notifications where user_id=member_id and kind='push_test' and created_at>now()-interval '1 minute') then
    raise exception 'Attends une minute entre deux tests';
  end if;
  perform public.queue_notification(member_id, 'push_test', null, 'Vendredi Party', 'Les notifications de Vendredi Party fonctionnent.');
end;
$$;
revoke all on function private.queue_test_push() from public, anon;
grant execute on function private.queue_test_push() to authenticated;
create or replace function public.test_push_notification() returns void
language sql security invoker set search_path = '' as $$ select private.queue_test_push(); $$;
revoke all on function public.test_push_notification() from public, anon;
grant execute on function public.test_push_notification() to authenticated;

-- Une livraison par notification ET appareil : un échec sur un appareil ne
-- provoque pas un nouvel envoi sur ceux qui ont déjà reçu leur notification.
create table public.notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  notification_id uuid not null references public.notifications(id) on delete cascade,
  token text not null,
  status text not null default 'queued' check(status in ('queued','ticketed','delivered','failed')),
  attempts integer not null default 0,
  ticket_id text,
  error text,
  next_attempt_at timestamptz not null default now(),
  lease_until timestamptz,
  requested_at timestamptz,
  receipt_checked_at timestamptz,
  unique(notification_id, token)
);
alter table public.notification_deliveries enable row level security;
revoke all on public.notification_deliveries from public, anon, authenticated;
grant all on public.notification_deliveries to service_role;
create index notification_deliveries_queue on public.notification_deliveries(next_attempt_at) where status='queued';
create index notification_deliveries_receipts on public.notification_deliveries(requested_at) where status='ticketed';

create or replace function private.push_is_quiet(start_at time, end_at time) returns boolean
language sql stable set search_path = '' as $$
  select case when start_at is null or end_at is null or start_at=end_at then false
    when start_at<end_at then clock_time>=start_at and clock_time<end_at
    else clock_time>=start_at or clock_time<end_at end
  from (select (now() at time zone coalesce((select timezone from public.group_settings limit 1),'Europe/Zurich'))::time as clock_time) t;
$$;
revoke all on function private.push_is_quiet(time,time) from public, anon, authenticated;

create or replace function public.prepare_push_deliveries() returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.notifications n set skipped=true where n.sent_at is null and not n.skipped
    and (not exists(select 1 from public.profiles p where p.id=n.user_id and p.status='active')
      or not exists(select 1 from public.notification_prefs p where p.user_id=n.user_id and p.push_enabled)
      or not exists(select 1 from public.push_tokens t where t.user_id=n.user_id and t.session_id is not null));
  update public.notification_deliveries d set status='failed', error='DeviceUnavailable', lease_until=null
    from public.notifications n where n.id=d.notification_id and d.status='queued'
      and (n.skipped or not exists(select 1 from public.push_tokens t where t.user_id=n.user_id and t.token=d.token and t.session_id is not null));
  insert into public.notification_deliveries(notification_id,token)
    select n.id,t.token from public.notifications n join public.push_tokens t on t.user_id=n.user_id
    where n.sent_at is null and not n.skipped and t.session_id is not null
    on conflict(notification_id,token) do nothing;
end;
$$;
revoke all on function public.prepare_push_deliveries() from public, anon, authenticated;
grant execute on function public.prepare_push_deliveries() to service_role;

create or replace function public.claim_push_deliveries(batch_size integer default 100)
returns table(delivery_id uuid, notification_id uuid, user_id uuid, token text, attempts integer, title text, body text, data jsonb)
language sql security definer set search_path = '' as $$
  with chosen as (
    select d.id from public.notification_deliveries d join public.notifications n on n.id=d.notification_id
    join public.notification_prefs p on p.user_id=n.user_id
    where d.status='queued' and d.next_attempt_at<=now() and (d.lease_until is null or d.lease_until<now())
      and not n.skipped and p.push_enabled and not private.push_is_quiet(p.quiet_start,p.quiet_end)
      and exists(select 1 from public.profiles p where p.id=n.user_id and p.status='active')
      and exists(select 1 from public.push_tokens t where t.token=d.token and t.user_id=n.user_id and t.session_id is not null)
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,100),100)) for update of d skip locked
  ), claimed as (
    update public.notification_deliveries d set lease_until=now()+interval '2 minutes', attempts=d.attempts+1
      from chosen c where d.id=c.id returning d.*
  )
  select d.id,d.notification_id,n.user_id,d.token,d.attempts,n.title,n.body,n.data
    from claimed d join public.notifications n on n.id=d.notification_id;
$$;
revoke all on function public.claim_push_deliveries(integer) from public, anon, authenticated;
grant execute on function public.claim_push_deliveries(integer) to service_role;

create or replace function public.finalize_push_notifications() returns void
language sql security definer set search_path = '' as $$
  update public.notifications n set sent_at=now() where n.sent_at is null and not n.skipped
    and exists(select 1 from public.notification_deliveries d where d.notification_id=n.id)
    and not exists(select 1 from public.notification_deliveries d where d.notification_id=n.id and d.status in ('queued','ticketed'));
$$;
revoke all on function public.finalize_push_notifications() from public, anon, authenticated;
grant execute on function public.finalize_push_notifications() to service_role;

-- Secret généré en base, jamais présent dans le code ni envoyé aux clients.
do $$ begin
  if not exists(select 1 from vault.secrets where name='push_job_secret') then
    perform vault.create_secret(encode(extensions.gen_random_bytes(32),'hex'),'push_job_secret');
  end if;
  if not exists(select 1 from vault.secrets where name='project_url') then
    perform vault.create_secret('https://gsuetixzobooggeaubvb.supabase.co','project_url');
  end if;
end $$;

create or replace function public.authorize_push_job(candidate text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(length(candidate)=64 and extensions.digest(candidate,'sha256')=
    extensions.digest((select decrypted_secret from vault.decrypted_secrets where name='push_job_secret' limit 1),'sha256'),false);
$$;
revoke all on function public.authorize_push_job(text) from public, anon, authenticated;
grant execute on function public.authorize_push_job(text) to service_role;

create or replace function private.dispatch_push_job() returns bigint
language sql security definer set search_path = '' as $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='project_url' limit 1)||'/functions/v1/send-push',
    headers := jsonb_build_object('Content-Type','application/json','x-job-secret',
      (select decrypted_secret from vault.decrypted_secrets where name='push_job_secret' limit 1)),
    body := '{}'::jsonb, timeout_milliseconds := 60000
  );
$$;
revoke all on function private.dispatch_push_job() from public, anon, authenticated;
-- Planifier seulement après le déploiement de la fonction Edge send-push :
-- select cron.schedule('send-push','* * * * *','select private.dispatch_push_job();');
