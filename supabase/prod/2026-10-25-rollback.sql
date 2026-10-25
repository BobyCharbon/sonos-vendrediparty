-- Retour arrière PROD (25.10.2026) : état d'avant les migrations 20261025120000 et 20261025160000.
begin;
CREATE OR REPLACE FUNCTION public.can_see_event(e uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select is_admin() or is_organizer(e) or exists (
    select 1 from events ev
    where ev.id = e and is_active()
      and ev.status in ('published', 'cancelled')
      and (ev.visibility = 'all'
           or exists (select 1 from event_invites i where i.event_id = e and i.user_id = auth.uid()))
  );
$function$
;
CREATE OR REPLACE FUNCTION private.queue_private_invite(ev events, u uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare via text;
begin
  if u = ev.created_by or not private.is_member(u) then return; end if;
  select string_agg(g.name, ', ' order by g.name) into via
    from public.event_groups eg
    join public.member_groups g on g.id = eg.group_id
    join public.member_group_members gm on gm.group_id = g.id and gm.user_id = u
    where eg.event_id = ev.id;
  perform public.queue_notification(u, 'private_invite', ev.id, '🔒 Invitation à un événement privé',
    'On t’invite à « ' || ev.title || ' »' || coalesce(' avec le groupe ' || via, '') || '.',
    'private_invite:' || ev.id);
end $function$
;
CREATE OR REPLACE FUNCTION private.on_event_invite()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare ev public.events;
begin
  select * into ev from public.events where id = new.event_id;
  if ev.status = 'published' and ev.visibility = 'invited' and ev.notify_on_publish
     and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() then
    perform private.queue_private_invite(ev, new.user_id);
  end if;
  return null;
end $function$
;
CREATE OR REPLACE FUNCTION public.notify_event_change()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare u uuid; tag_ids uuid[];
begin
  -- Nouvelle proposition -> admins
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

  -- Publication -> créateur + groupe selon préférences et abonnements
  if new.status = 'published' and (tg_op = 'INSERT' or old.status <> 'published') then
    if new.created_by <> coalesce(new.approved_by, new.created_by) then
      perform queue_notification(new.created_by, 'approved', new.id, 'Proposition validée',
        '« ' || new.title || ' » est publié.');
    end if;
    if new.notify_on_publish and new.visibility = 'invited' then
      for u in select i.user_id from event_invites i where i.event_id = new.id loop
        perform private.queue_private_invite(new, u);
      end loop;
    elsif new.notify_on_publish then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where private.is_member(p.id) and p.id <> new.created_by
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
end $function$
;
drop policy if exists "lire catégories" on public.categories; create policy "lire catégories" on public.categories as PERMISSIVE for SELECT to public using (is_active());
drop policy if exists "lire tags" on public.tags; create policy "lire tags" on public.tags as PERMISSIVE for SELECT to public using (is_active());
drop policy if exists "modifier son groupe" on public.member_groups; create policy "modifier son groupe" on public.member_groups as PERMISSIVE for UPDATE to authenticated using (((created_by = ( SELECT auth.uid() AS uid)) OR ( SELECT is_admin() AS is_admin)));
drop policy if exists "supprimer son groupe" on public.member_groups; create policy "supprimer son groupe" on public.member_groups as PERMISSIVE for DELETE to authenticated using (((created_by = ( SELECT auth.uid() AS uid)) OR ( SELECT is_admin() AS is_admin)));
drop policy if exists "composer son groupe" on public.member_group_members; create policy "composer son groupe" on public.member_group_members as PERMISSIVE for ALL to authenticated using ((EXISTS ( SELECT 1
   FROM member_groups g
  WHERE ((g.id = member_group_members.group_id) AND ((g.created_by = ( SELECT auth.uid() AS uid)) OR ( SELECT is_admin() AS is_admin)))))) with check ((EXISTS ( SELECT 1
   FROM member_groups g
  WHERE ((g.id = member_group_members.group_id) AND ((g.created_by = ( SELECT auth.uid() AS uid)) OR ( SELECT is_admin() AS is_admin))))));
-- Droits du rôle Guest avant : guest:games.create,music.add
delete from public.role_permissions where role = 'guest' and perm in ('events.rsvp','chat.write');
commit;
