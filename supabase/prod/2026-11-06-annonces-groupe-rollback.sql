-- PROD, retour arrière d'annonces_groupe (20261106220000) : retour au comportement d'avant (un événement de groupe prévient
-- son groupe selon notify_on_publish, « Nouvel événement » aux Membres VIP à la publication, aucun groupe en attente).
-- Les demandes d'annonce, les réglages des groupes et les 3 interrupteurs sont effacés. Tout ou rien.
begin;
do $$ begin
  perform cron.unschedule('group-announcements-auto') where exists (select 1 from cron.job where jobname = 'group-announcements-auto');
end $$;
drop trigger if exists events_announce on public.events;
drop trigger if exists zz_event_groups_announce on public.event_groups;
drop trigger if exists guard_event_group_status on public.event_groups;
drop trigger if exists member_groups_event_rules on public.member_groups;
drop trigger if exists event_groups_sync on public.event_groups;
create trigger event_groups_sync after insert or delete on public.event_groups
  for each row execute function private.on_event_groups_change();

create or replace function private.should_invite(ev public.events, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select ev.status = 'published' and ev.notify_on_publish and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now()
     and (ev.visibility = 'invited' or (ev.visibility = 'all' and not private.is_member(u)));
$$;

create or replace function private.sync_event_group_invites(e uuid) returns void
language sql security definer set search_path = '' as $$
  delete from public.event_invites i where i.event_id = e and i.via_group
    and not exists (select 1 from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
                    where eg.event_id = e and gm.user_id = i.user_id)
    and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id);
  insert into public.event_invites (event_id, user_id, via_group)
    select distinct eg.event_id, gm.user_id, true
    from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
    where eg.event_id = e and exists (select 1 from public.events where id = e)
  on conflict (event_id, user_id) do nothing;
$$;

create or replace function public.notify_event_change()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $fn$
declare u uuid; tag_ids uuid[];
begin
  if new.status = 'pending' and (tg_op = 'INSERT' or old.status <> 'pending') then
    for u in select p.id from profiles p join notification_prefs np on np.user_id = p.id
             where private.user_has(p.id, 'events.approve') and np.proposals loop
      perform queue_notification(u, 'proposal', new.id, 'Nouvelle proposition',
        '« ' || new.title || ' » attend ta validation.');
    end loop;
  end if;

  if tg_op = 'UPDATE' and new.status = 'rejected' and old.status <> 'rejected' then
    perform queue_notification(new.created_by, 'rejected', new.id, 'Proposition refusée',
      coalesce(new.rejection_reason, '« ' || new.title || ' » n''a pas été retenu.'));
  end if;

  if new.status = 'published' and (tg_op = 'INSERT' or old.status <> 'published') then
    if new.created_by <> coalesce(new.approved_by, new.created_by) then
      perform queue_notification(new.created_by, 'approved', new.id, 'Proposition validée',
        '« ' || new.title || ' » est publié.');
    end if;
    if new.notify_on_publish then
      for u in select i.user_id from event_invites i where i.event_id = new.id
               union select p.id from event_phone_invites pi join profiles p on p.phone = pi.phone where pi.event_id = new.id loop
        if private.should_invite(new, u) then perform private.queue_private_invite(new, u); end if;
      end loop;
    end if;
    if new.notify_on_publish and new.visibility = 'all' then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where p.id <> new.created_by and p.status = 'active'
          and (private.is_member(p.id)
               or (new.public_link and exists (select 1 from beta_testers b where b.user_id = p.id)))
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
end $fn$

;

do $$
declare def text := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
begin
  execute replace(def, '''private_invite'', ''announce_request'', ''announce_accepted'', ''announce_refused'', '
    || '''group_event_request'', ''group_event_accepted'', ''group_event_refused'', ''event_changed''', '''private_invite'', ''event_changed''');
end $$;
do $$
declare def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
begin
  execute replace(def, 'when ''direct_message'' then coalesce(prefs.direct_messages, true)
    when ''announce_request'' then coalesce(prefs.announce_requests, true)
    when ''announce_accepted'' then coalesce(prefs.announce_results, true)
    when ''announce_refused'' then coalesce(prefs.announce_results, true)
    when ''group_event_request'' then coalesce(prefs.group_event_requests, true)
    when ''group_event_accepted'' then coalesce(prefs.announce_results, true)
    when ''group_event_refused'' then coalesce(prefs.announce_results, true)', 'when ''direct_message'' then coalesce(prefs.direct_messages, true)');
end $$;

do $$
declare def text := pg_get_functiondef('public.guard_event()'::regprocedure);
begin
  execute replace(def, '    -- Annonce au groupe (06.11) : seul « Prévenir le groupe » change → organisateurs et co-organisateurs.
    if (to_jsonb(new) - ''announce_group'' - ''updated_at'') = (to_jsonb(old) - ''announce_group'' - ''updated_at'')
       and public.is_organizer(new.id) then return new; end if;
', '');
end $$;
drop function if exists public.my_announce_modes(uuid[]);
drop function if exists public.answer_announcement(uuid, boolean);
drop function if exists public.answer_group_event(uuid, uuid, boolean);
drop function if exists public.my_group_requests();
drop function if exists public.event_announcement_status(uuid);
drop function if exists public.set_group_event_rules(uuid, boolean, text);
drop function if exists private.auto_accept_announcements();
drop function if exists private.on_event_announce();
drop function if exists private.on_event_group_announce();
drop function if exists private.guard_event_group_status();
drop function if exists private.guard_group_event_rules();
drop function if exists private.may_set_group_rules(uuid, uuid);
drop function if exists private.open_announcements(uuid);
drop function if exists private.tell_validators(uuid, uuid, text, text, text, text, uuid);
drop function if exists private.tell_requester(uuid, text, uuid, text, text);
drop function if exists private.send_announcement(uuid);
drop function if exists private.broadcast_new_event(public.events);
drop function if exists private.group_announced_to(uuid, uuid);
drop function if exists private.invited_in_person(uuid, uuid);
drop function if exists private.group_label(uuid);
drop function if exists private.person_label(uuid);
drop table if exists public.event_announcements;
drop function if exists private.announcement_validators(uuid, uuid);
drop function if exists private.may_approve_announcement(uuid, uuid);

-- Groupes en attente ou refusés : retirés (avant, un groupe ajouté était toujours actif).
delete from public.event_groups where status <> 'approved';
alter table public.event_groups drop constraint if exists event_groups_status_check;
alter table public.event_groups drop column if exists status, drop column if exists requested_by,
  drop column if exists answered_by, drop column if exists answered_at, drop column if exists created_at;
alter table public.member_groups drop constraint if exists member_groups_announce_mode_check;
alter table public.member_groups drop column if exists events_need_approval, drop column if exists announce_mode;
alter table public.events drop column if exists announce_group;
alter table public.notification_prefs drop column if exists announce_requests, drop column if exists announce_results,
  drop column if exists group_event_requests;
delete from public.role_permissions where perm = 'groups.announce_approve';
delete from public.permissions where key = 'groups.announce_approve';
delete from private.one_time_changes where name in ('announce_approve_2026_11_06', 'announcements_backfill_2026_11_06');
delete from supabase_migrations.schema_migrations where version = '20261106220000';
commit;

notify pgrst, 'reload schema';
