-- Web Push est indépendant des abonnements musique et des anciens jetons Expo.
create table private.web_push_config (
  id boolean primary key default true check(id),
  public_key text not null,
  private_key text not null,
  created_at timestamptz not null default now()
);
alter table private.web_push_config enable row level security;
revoke all on private.web_push_config from public, anon, authenticated;

create table private.web_push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  session_id uuid not null references auth.sessions(id) on delete cascade,
  endpoint text not null unique,
  subscription jsonb not null,
  origin text not null check(origin in ('https://party.bobycharbon.ch','https://partytest.bobycharbon.ch')),
  registered_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table private.web_push_subscriptions enable row level security;
revoke all on private.web_push_subscriptions from public, anon, authenticated;
create index web_push_subscriptions_member on private.web_push_subscriptions(user_id,session_id);

create table private.web_push_deliveries (
  id uuid primary key default gen_random_uuid(),
  notification_id uuid not null references public.notifications(id) on delete cascade,
  subscription_id uuid not null references private.web_push_subscriptions(id) on delete cascade,
  status text not null default 'queued' check(status in ('queued','sent','failed','cancelled')),
  attempts integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  lease_until timestamptz,
  accepted_at timestamptz,
  error text,
  unique(notification_id,subscription_id)
);
alter table private.web_push_deliveries enable row level security;
revoke all on private.web_push_deliveries from public, anon, authenticated;
create index web_push_delivery_queue on private.web_push_deliveries(next_attempt_at) where status='queued';

-- Les destinataires peuvent lire une annonce, jamais la masquer ni la supprimer.
create table public.admin_announcements (
  id uuid primary key default gen_random_uuid(),
  title text not null check(length(btrim(title)) between 1 and 120),
  body text not null check(length(btrim(body)) between 1 and 4000),
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
alter table public.admin_announcements enable row level security;
revoke all on public.admin_announcements from public, anon, authenticated;
grant select on public.admin_announcements to authenticated;
create policy "annonces pour les membres actifs" on public.admin_announcements for select
  to authenticated using ((select public.is_active()));
create index admin_announcements_recent on public.admin_announcements(created_at desc,id desc);

create function private.web_push_config_keys(initial_public text default null,initial_private text default null) returns jsonb
language plpgsql security definer set search_path='' as $$
begin
  if initial_public is not null then
    if initial_public !~ '^[A-Za-z0-9_-]{87}$' or initial_private is null or initial_private !~ '^[A-Za-z0-9_-]{43}$' then
      raise exception 'Invalid VAPID configuration';
    end if;
    insert into private.web_push_config(id,public_key,private_key) values(true,initial_public,initial_private)
      on conflict(id) do nothing;
  end if;
  return (select jsonb_build_object('publicKey',public_key,'privateKey',private_key) from private.web_push_config where id);
end $$;
revoke all on function private.web_push_config_keys(text,text) from public,anon,authenticated;
grant usage on schema private to service_role;
grant execute on function private.web_push_config_keys(text,text) to service_role;
create function public.web_push_config_keys(initial_public text default null,initial_private text default null) returns jsonb
language sql security invoker set search_path='' as $$ select private.web_push_config_keys(initial_public,initial_private); $$;
revoke all on function public.web_push_config_keys(text,text) from public,anon,authenticated;
grant execute on function public.web_push_config_keys(text,text) to service_role;

create function private.web_push_public_key() returns text
language plpgsql stable security definer set search_path='' as $$
begin
  if auth.uid() is null or not public.is_active() then raise exception 'Connexion requise' using errcode='42501'; end if;
  return (select public_key from private.web_push_config where id);
end $$;
revoke all on function private.web_push_public_key() from public,anon;
grant execute on function private.web_push_public_key() to authenticated;
create function public.get_web_push_public_key() returns text language sql security invoker set search_path='' as $$ select private.web_push_public_key(); $$;
revoke all on function public.get_web_push_public_key() from public,anon;
grant execute on function public.get_web_push_public_key() to authenticated;

create function private.register_web_push(device_subscription jsonb,device_origin text) returns void
language plpgsql security definer set search_path='' as $$
declare member_id uuid:=auth.uid(); active_session uuid; destination text:=device_subscription->>'endpoint';
begin
  if member_id is null or not public.is_active() then raise exception 'Connexion requise' using errcode='42501'; end if;
  select id into active_session from auth.sessions where user_id=member_id and id::text=auth.jwt()->>'session_id';
  if active_session is null then raise exception 'Session expirée' using errcode='42501'; end if;
  if device_origin is null or device_origin not in ('https://party.bobycharbon.ch','https://partytest.bobycharbon.ch')
    or destination is null or length(destination)>2048 or destination ~ '[#[:space:]]'
    or destination !~* '^https://(fcm\.googleapis\.com|([a-z0-9-]+\.)*push\.services\.mozilla\.com|([a-z0-9-]+\.)*push\.apple\.com|([a-z0-9-]+\.)*notify\.windows\.com)/.+'
    or coalesce(jsonb_typeof(device_subscription#>'{keys,p256dh}'),'')<>'string'
    or coalesce(device_subscription#>>'{keys,p256dh}','') !~ '^[A-Za-z0-9_-]{87}=?$'
    or coalesce(jsonb_typeof(device_subscription#>'{keys,auth}'),'')<>'string'
    or coalesce(device_subscription#>>'{keys,auth}','') !~ '^[A-Za-z0-9_-]{22}(==)?$' then
    raise exception 'Abonnement de notifications non valide' using errcode='22023';
  end if;
  perform pg_advisory_xact_lock(hashtext('webpush:'||member_id));
  if not exists(select 1 from private.web_push_subscriptions where endpoint=destination)
    and (select count(*) from private.web_push_subscriptions where user_id=member_id)>=10 then
    raise exception 'Dix appareils sont déjà associés à ce compte';
  end if;
  insert into private.web_push_subscriptions(user_id,session_id,endpoint,subscription,origin)
    values(member_id,active_session,destination,jsonb_build_object('endpoint',destination,'keys',device_subscription->'keys'),device_origin)
    on conflict(endpoint) do update set user_id=excluded.user_id,session_id=excluded.session_id,
      subscription=excluded.subscription,origin=excluded.origin,updated_at=now(),
      registered_at=case when web_push_subscriptions.session_id=excluded.session_id then web_push_subscriptions.registered_at else now() end;
end $$;
revoke all on function private.register_web_push(jsonb,text) from public,anon;
grant execute on function private.register_web_push(jsonb,text) to authenticated;
create function public.register_web_push(device_subscription jsonb,device_origin text) returns void
language sql security invoker set search_path='' as $$ select private.register_web_push(device_subscription,device_origin); $$;
revoke all on function public.register_web_push(jsonb,text) from public,anon;
grant execute on function public.register_web_push(jsonb,text) to authenticated;

create function private.web_push_device_status(device_endpoint text) returns boolean
language sql stable security definer set search_path='' as $$
  select public.is_active() and exists(select 1 from private.web_push_subscriptions s join auth.sessions a on a.id=s.session_id
    where s.endpoint=device_endpoint and s.user_id=auth.uid() and a.id::text=auth.jwt()->>'session_id');
$$;
revoke all on function private.web_push_device_status(text) from public,anon;
grant execute on function private.web_push_device_status(text) to authenticated;
create function public.web_push_device_status(device_endpoint text) returns boolean language sql security invoker set search_path='' as $$ select private.web_push_device_status(device_endpoint); $$;
revoke all on function public.web_push_device_status(text) from public,anon;
grant execute on function public.web_push_device_status(text) to authenticated;

create function private.unregister_web_push(device_endpoint text) returns void language sql security definer set search_path='' as $$
  delete from private.web_push_subscriptions where endpoint=device_endpoint and user_id=auth.uid();
$$;
revoke all on function private.unregister_web_push(text) from public,anon;
grant execute on function private.unregister_web_push(text) to authenticated;
create function public.unregister_web_push(device_endpoint text) returns void language sql security invoker set search_path='' as $$ select private.unregister_web_push(device_endpoint); $$;
revoke all on function public.unregister_web_push(text) from public,anon;
grant execute on function public.unregister_web_push(text) to authenticated;

create function private.publish_admin_announcement(announcement_title text,announcement_body text) returns uuid
language plpgsql security definer set search_path='' as $$
declare result uuid; headline text:=btrim(announcement_title); content text:=btrim(announcement_body);
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Accès admin requis' using errcode='42501'; end if;
  if headline is null or length(headline) not between 1 and 120 or content is null or length(content) not between 1 and 4000 then
    raise exception 'Renseigne un titre (120 caractères maximum) et un message (4000 maximum)';
  end if;
  perform pg_advisory_xact_lock(hashtext('admin-announcements'));
  if (select count(*) from public.admin_announcements where created_at>now()-interval '1 minute')>=5 then
    raise exception 'Attends une minute avant de publier une autre annonce';
  end if;
  insert into public.admin_announcements(title,body,created_by) values(headline,content,auth.uid()) returning id into result;
  insert into public.notifications(user_id,kind,title,body,dedupe_key,data)
    select id,'admin_announcement',headline,content,'announcement:'||result,
      jsonb_build_object('kind','admin_announcement','announcement_id',result)
    from public.profiles where status='active';
  return result;
end $$;
revoke all on function private.publish_admin_announcement(text,text) from public,anon;
grant execute on function private.publish_admin_announcement(text,text) to authenticated;
create function public.publish_admin_announcement(announcement_title text,announcement_body text) returns uuid
language sql security invoker set search_path='' as $$ select private.publish_admin_announcement(announcement_title,announcement_body); $$;
revoke all on function public.publish_admin_announcement(text,text) from public,anon;
grant execute on function public.publish_admin_announcement(text,text) to authenticated;

-- Réévaluer les choix et la visibilité au moment de l'envoi, pas seulement à la création.
create function private.web_push_allowed(notification public.notifications) returns boolean
language plpgsql stable security definer set search_path='' as $$
declare prefs public.notification_prefs; ev public.events;
begin
  if not exists(select 1 from public.profiles where id=notification.user_id and status='active') then return false; end if;
  if notification.kind='admin_announcement' then
    return exists(select 1 from public.admin_announcements where id::text=notification.data->>'announcement_id');
  end if;
  if notification.kind='web_push_test' then return true; end if;
  select * into prefs from public.notification_prefs where user_id=notification.user_id;
  if prefs.user_id is null or not prefs.push_enabled then return false; end if;
  if notification.event_id is not null then
    select * into ev from public.events where id=notification.event_id;
    if ev.id is null or exists(select 1 from public.event_mutes where event_id=ev.id and user_id=notification.user_id) then return false; end if;
    if not (exists(select 1 from public.profiles where id=notification.user_id and role in ('admin','coadmin'))
      or ev.created_by=notification.user_id
      or exists(select 1 from public.event_organizers where event_id=ev.id and user_id=notification.user_id)
      or (ev.status in ('published','cancelled') and (ev.visibility='all'
        or exists(select 1 from public.event_invites where event_id=ev.id and user_id=notification.user_id)))) then return false; end if;
  end if;
  return case notification.kind
    when 'new_event' then prefs.new_event='all' or (prefs.new_event='subscribed' and (
      exists(select 1 from public.category_subscriptions where user_id=notification.user_id and category_id=ev.category_id)
      or exists(select 1 from public.tag_subscriptions t join public.event_tags e on e.tag_id=t.tag_id where e.event_id=ev.id and t.user_id=notification.user_id)))
    when 'event_changed' then prefs.event_changed
    when 'poll_new' then prefs.poll_new
    when 'date_fixed' then prefs.date_fixed
    when 'poll_nudge' then prefs.poll_nudge
    when 'waitlist' then prefs.waitlist
    when 'proposal' then prefs.proposals
    when 'rsvp' then prefs.rsvp_mine
    when 'message' then prefs.chat='all' or (prefs.chat='mentions' and coalesce((notification.data->>'mentioned')::boolean,false))
    when 'reminder' then split_part(notification.dedupe_key,':',3)=any(prefs.reminders)
    else true end;
end $$;
revoke all on function private.web_push_allowed(public.notifications) from public,anon,authenticated;

create function private.prepare_web_push_deliveries() returns void
language plpgsql security definer set search_path='' as $$
begin
  -- Un nouvel appareil ne rejoue pas l'historique. Les annonces restent lisibles dans leur table durable.
  insert into private.web_push_deliveries(notification_id,subscription_id)
    select n.id,s.id from public.notifications n join private.web_push_subscriptions s on s.user_id=n.user_id
    join auth.sessions a on a.id=s.session_id
    where n.created_at>=s.registered_at and n.created_at>now()-interval '7 days' and n.read_at is null
      and private.web_push_allowed(n)
      and (n.kind<>'web_push_test' or n.data->>'subscription_id'=s.id::text)
    on conflict(notification_id,subscription_id) do nothing;
  update private.web_push_deliveries d set status='cancelled',error='PreferencesOrAccessChanged',lease_until=null
    from public.notifications n,private.web_push_subscriptions s
    where n.id=d.notification_id and s.id=d.subscription_id and d.status='queued'
      and (n.user_id<>s.user_id or n.created_at<s.registered_at or n.read_at is not null
        or n.created_at<now()-interval '7 days' or not private.web_push_allowed(n)
        or not exists(select 1 from auth.sessions where id=s.session_id));
end $$;
revoke all on function private.prepare_web_push_deliveries() from public,anon,authenticated;
grant execute on function private.prepare_web_push_deliveries() to service_role;
create function public.prepare_web_push_deliveries() returns void language sql security invoker set search_path='' as $$ select private.prepare_web_push_deliveries(); $$;
revoke all on function public.prepare_web_push_deliveries() from public,anon,authenticated;
grant execute on function public.prepare_web_push_deliveries() to service_role;

create function private.claim_web_push_deliveries(batch_size integer default 20) returns jsonb
language sql security definer set search_path='' as $$
  with chosen as (
    select d.id from private.web_push_deliveries d join public.notifications n on n.id=d.notification_id
    join private.web_push_subscriptions s on s.id=d.subscription_id
    join auth.sessions a on a.id=s.session_id
    left join public.notification_prefs p on p.user_id=n.user_id
    where d.status='queued' and d.next_attempt_at<=now() and (d.lease_until is null or d.lease_until<now())
      and n.user_id=s.user_id and n.read_at is null and n.created_at>=s.registered_at and private.web_push_allowed(n)
      and (n.kind='web_push_test' or not private.push_is_quiet(p.quiet_start,p.quiet_end))
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,20),50)) for update of d skip locked
  ), claimed as (
    update private.web_push_deliveries d set lease_until=now()+interval '2 minutes',attempts=attempts+1
      from chosen c where c.id=d.id returning d.*
  ) select coalesce(jsonb_agg(jsonb_build_object('id',d.id,'attempts',d.attempts,'subscription',s.subscription,
    'origin',s.origin,'title',n.title,'body',n.body,'event_id',n.event_id,'kind',n.kind,'notification_id',n.id)), '[]'::jsonb)
    from claimed d join public.notifications n on n.id=d.notification_id join private.web_push_subscriptions s on s.id=d.subscription_id;
$$;
revoke all on function private.claim_web_push_deliveries(integer) from public,anon,authenticated;
grant execute on function private.claim_web_push_deliveries(integer) to service_role;
create function public.claim_web_push_deliveries(batch_size integer default 20) returns jsonb language sql security invoker set search_path='' as $$ select private.claim_web_push_deliveries(batch_size); $$;
revoke all on function public.claim_web_push_deliveries(integer) from public,anon,authenticated;
grant execute on function public.claim_web_push_deliveries(integer) to service_role;

create function private.finish_web_push_delivery(delivery_id uuid,result_code integer) returns void
language plpgsql security definer set search_path='' as $$
declare item private.web_push_deliveries;
begin
  select * into item from private.web_push_deliveries where id=delivery_id and status='queued' for update;
  if not found then return; end if;
  if result_code in (404,410) then
    delete from private.web_push_subscriptions where id=item.subscription_id;
  else
    update private.web_push_deliveries set
      status=case when result_code between 200 and 299 then 'sent'
        when attempts>=8 or (result_code between 400 and 499 and result_code not in (408,429)) then 'failed' else 'queued' end,
      accepted_at=case when result_code between 200 and 299 then now() else null end,
      error=case when result_code between 200 and 299 then null else 'PushHTTP'||coalesce(result_code,0) end,
      next_attempt_at=now()+make_interval(secs=>least(3600,30*power(2,least(attempts-1,7)))::integer),lease_until=null
    where id=item.id;
  end if;
end $$;
revoke all on function private.finish_web_push_delivery(uuid,integer) from public,anon,authenticated;
grant execute on function private.finish_web_push_delivery(uuid,integer) to service_role;
create function public.finish_web_push_delivery(delivery_id uuid,result_code integer) returns void language sql security invoker set search_path='' as $$ select private.finish_web_push_delivery(delivery_id,result_code); $$;
revoke all on function public.finish_web_push_delivery(uuid,integer) from public,anon,authenticated;
grant execute on function public.finish_web_push_delivery(uuid,integer) to service_role;

create function private.test_web_push(device_endpoint text) returns void
language plpgsql security definer set search_path='' as $$
declare device uuid;
begin
  if not private.web_push_device_status(device_endpoint) then raise exception 'Active d’abord les notifications sur cet appareil' using errcode='42501'; end if;
  perform pg_advisory_xact_lock(hashtext('test-webpush:'||auth.uid()));
  if exists(select 1 from public.notifications where user_id=auth.uid() and kind='web_push_test' and created_at>now()-interval '1 minute') then raise exception 'Attends une minute entre deux essais'; end if;
  select id into device from private.web_push_subscriptions where endpoint=device_endpoint and user_id=auth.uid();
  insert into public.notifications(user_id,kind,title,body,data)
    values(auth.uid(),'web_push_test','Party · Notifications','Les notifications d’événements sont activées sur cet appareil.',jsonb_build_object('subscription_id',device));
end $$;
revoke all on function private.test_web_push(text) from public,anon;
grant execute on function private.test_web_push(text) to authenticated;
create function public.test_web_push(device_endpoint text) returns void language sql security invoker set search_path='' as $$ select private.test_web_push(device_endpoint); $$;
revoke all on function public.test_web_push(text) from public,anon;
grant execute on function public.test_web_push(text) to authenticated;

create function private.dispatch_web_push_job() returns bigint language sql security definer set search_path='' as $$
  select net.http_post(url:=(select decrypted_secret from vault.decrypted_secrets where name='project_url' limit 1)||'/functions/v1/send-web-push',
    headers:=jsonb_build_object('Content-Type','application/json','x-job-secret',(select decrypted_secret from vault.decrypted_secrets where name='push_job_secret' limit 1)),
    body:='{}'::jsonb,timeout_milliseconds:=60000);
$$;
revoke all on function private.dispatch_web_push_job() from public,anon,authenticated;
-- Activer le cron seulement après le déploiement de send-web-push.

-- Même choix dans le fil Activité et dans le push. Les mentions respectent la visibilité.
create or replace function public.notify_event_change() returns trigger
language plpgsql security definer set search_path = public as $$
declare u uuid; tag_ids uuid[];
begin
  -- Nouvelle proposition -> admins
  if new.status = 'pending' and (tg_op = 'INSERT' or old.status <> 'pending') then
    for u in select p.id from profiles p join notification_prefs np on np.user_id = p.id
             where p.status = 'active' and p.role in ('admin', 'coadmin') and np.proposals loop
      perform queue_notification(u, 'proposal', new.id, 'Nouvelle proposition',
        '« ' || new.title || ' » attend ta validation.');
    end loop;
  end if;

  if tg_op = 'UPDATE' and new.status = 'rejected' and old.status <> 'rejected' then
    perform queue_notification(new.created_by, 'rejected', new.id, 'Proposition refusée',
      coalesce(new.rejection_reason, '« ' || new.title || ' » n''a pas été retenu.'));
  end if;

  -- Publication -> créateur + groupe selon préférences et abonnements
  if new.status = 'published' and (tg_op = 'INSERT' or old.status <> 'published') then
    if new.created_by <> coalesce(new.approved_by, new.created_by) then
      perform queue_notification(new.created_by, 'approved', new.id, 'Proposition validée',
        '« ' || new.title || ' » est publié.');
    end if;
    if new.notify_on_publish then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where p.status = 'active' and p.id <> new.created_by
          and (new.visibility = 'all' or exists (select 1 from event_invites i where i.event_id = new.id and i.user_id = p.id))
          and (np.new_event = 'all' or (np.new_event = 'subscribed' and (
                exists (select 1 from tag_subscriptions ts where ts.user_id = p.id and ts.tag_id = any (tag_ids))
             or exists (select 1 from category_subscriptions cs where cs.user_id = p.id and cs.category_id = new.category_id))))
      loop
        perform queue_notification(u, 'new_event', new.id,
          case when new.date_mode = 'poll' then 'Nouveau sondage de dates' else 'Nouvel événement' end,
          new.title, 'new_event:' || new.id);
      end loop;
    end if;
  end if;

  if tg_op = 'UPDATE' and old.status = 'published' then
    if new.status = 'cancelled' then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id=a where np.event_changed loop
        perform queue_notification(u, 'event_changed', new.id, 'Événement annulé', '« ' || new.title || ' » est annulé.');
      end loop;
    elsif old.date_mode = 'poll' and new.date_mode = 'fixed' then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.date_fixed loop
        perform queue_notification(u, 'date_fixed', new.id, 'Date fixée',
          new.title || ' : ' || to_char(new.starts_at at time zone 'Europe/Zurich', 'DD.MM à HH24:MI'));
      end loop;
    elsif new.starts_at is distinct from old.starts_at or new.location_name is distinct from old.location_name
       or new.location_address is distinct from old.location_address
       or new.ends_at is distinct from old.ends_at or new.location_url is distinct from old.location_url
       or new.title is distinct from old.title or new.description is distinct from old.description
       or new.price_chf is distinct from old.price_chf then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.event_changed loop
        perform queue_notification(u, 'event_changed', new.id, 'Événement modifié',
          '« ' || new.title || ' » : les informations ont changé.');
      end loop;
    end if;
  end if;
  return null;
end $$;

create or replace function public.notify_message() returns trigger
language plpgsql security definer set search_path = public as $$
declare ev events; who text; reply_author uuid; u uuid; np notification_prefs;
begin
  select * into ev from events where id = new.event_id;
  select display_name into who from profiles where id = new.user_id;
  select user_id into reply_author from messages where id = new.reply_to;
  for u in select distinct x from (
      select a x from event_audience(ev.id) a
      union select user_id from messages where event_id = ev.id
      union select unnest(new.mentions)
    ) s
    where x not in (select user_id from event_mutes where event_id = ev.id)
      and exists(select 1 from profiles p where p.id=x and p.status='active' and (
        p.role in ('admin','coadmin') or ev.created_by=x
        or exists(select 1 from event_organizers where event_id=ev.id and user_id=x)
        or (ev.status in ('published','cancelled') and (ev.visibility='all'
          or exists(select 1 from event_invites where event_id=ev.id and user_id=x))))) loop
    select * into np from notification_prefs where user_id = u;
    if np.chat = 'all' or (np.chat = 'mentions' and (u = any (new.mentions) or u = reply_author)) then
      perform queue_notification(u, 'message', ev.id, ev.title, who || ' : ' || left(new.body, 140), null, jsonb_build_object('mentioned', u=any(new.mentions) or u=reply_author));
    end if;
  end loop;
  return null;
end $$;
