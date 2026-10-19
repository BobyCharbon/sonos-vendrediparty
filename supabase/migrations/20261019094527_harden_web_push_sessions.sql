-- Respecter les sessions expirées et éviter les annonces en double après une erreur réseau.

create or replace function private.register_web_push(device_subscription jsonb,device_origin text) returns void
language plpgsql security definer set search_path='' as $$
declare member_id uuid:=auth.uid(); active_session uuid; destination text:=device_subscription->>'endpoint';
begin
  if member_id is null or not public.is_active() then raise exception 'Connexion requise' using errcode='42501'; end if;
  select id into active_session from auth.sessions where user_id=member_id and id::text=auth.jwt()->>'session_id' and (not_after is null or not_after>now());
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

create or replace function private.web_push_device_status(device_endpoint text) returns boolean
language sql stable security definer set search_path='' as $$
  select public.is_active() and exists(select 1 from private.web_push_subscriptions s join auth.sessions a on a.id=s.session_id
    where s.endpoint=device_endpoint and s.user_id=auth.uid() and a.id::text=auth.jwt()->>'session_id' and (a.not_after is null or a.not_after>now()));
$$;

create or replace function private.prepare_web_push_deliveries() returns void
language plpgsql security definer set search_path='' as $$
begin
  -- Un nouvel appareil ne rejoue pas l'historique. Les annonces restent lisibles dans leur table durable.
  insert into private.web_push_deliveries(notification_id,subscription_id)
    select n.id,s.id from public.notifications n join private.web_push_subscriptions s on s.user_id=n.user_id
    join auth.sessions a on a.id=s.session_id and (a.not_after is null or a.not_after>now())
    where n.created_at>=s.registered_at and n.created_at>now()-interval '7 days' and n.read_at is null
      and private.web_push_allowed(n)
      and (n.kind<>'web_push_test' or n.data->>'subscription_id'=s.id::text)
    on conflict(notification_id,subscription_id) do nothing;
  update private.web_push_deliveries d set status='cancelled',error='PreferencesOrAccessChanged',lease_until=null
    from public.notifications n,private.web_push_subscriptions s
    where n.id=d.notification_id and s.id=d.subscription_id and d.status='queued'
      and (n.user_id<>s.user_id or n.created_at<s.registered_at or n.read_at is not null
        or n.created_at<now()-interval '7 days' or not private.web_push_allowed(n)
        or not exists(select 1 from auth.sessions where id=s.session_id and (not_after is null or not_after>now())));
end $$;

create or replace function private.claim_web_push_deliveries(batch_size integer default 20) returns jsonb
language sql security definer set search_path='' as $$
  with chosen as (
    select d.id from private.web_push_deliveries d join public.notifications n on n.id=d.notification_id
    join private.web_push_subscriptions s on s.id=d.subscription_id
    join auth.sessions a on a.id=s.session_id and (a.not_after is null or a.not_after>now())
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

create or replace function private.publish_admin_announcement(announcement_title text,announcement_body text) returns uuid
language plpgsql security definer set search_path='' as $$
declare result uuid; headline text:=btrim(announcement_title); content text:=btrim(announcement_body);
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Accès admin requis' using errcode='42501'; end if;
  if headline is null or length(headline) not between 1 and 120 or content is null or length(content) not between 1 and 4000 then
    raise exception 'Renseigne un titre (120 caractères maximum) et un message (4000 maximum)';
  end if;
  perform pg_advisory_xact_lock(hashtext('admin-announcements'));
  -- Une reprise après une réponse réseau perdue ne publie pas deux fois la même annonce.
  select id into result from public.admin_announcements where created_by=auth.uid()
    and title=headline and body=content and created_at>now()-interval '5 minutes' order by created_at desc limit 1;
  if result is not null then return result; end if;
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

select cron.schedule('send-web-push','* * * * *','select private.dispatch_web_push_job();');
