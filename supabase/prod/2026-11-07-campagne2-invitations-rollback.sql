-- PROD, retour arrière de campagne2_invitations (20261107100000) : remet les fonctions telles qu'après
-- 20261106220000 (annonces aux groupes), retire les deux déclencheurs, les fonctions ajoutées et event_groups.announce.
-- Tout ou rien.
begin;
drop trigger if exists events_keep_cancel_notices on public.events;
drop trigger if exists event_organizers_notify on public.event_organizers;
drop function if exists private.keep_cancel_notices();
drop function if exists private.on_event_organizer_added();
drop function if exists private.event_cancel_audience(uuid);
drop function if exists public.invite_people(uuid, uuid[], uuid[], boolean);

CREATE OR REPLACE FUNCTION private.guard_invite_block()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare inviter uuid := auth.uid();
begin
  if tg_table_name = 'group_invitations' then inviter := coalesce(inviter, new.invited_by); end if;
  if new.user_id is not null and private.blocked_either(inviter, new.user_id) then
    raise exception 'blocked: tu ne peux pas inviter cette personne' using errcode = '42501';
  end if;
  return new;
end $function$;

CREATE OR REPLACE FUNCTION private.send_announcement(a uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare r public.event_announcements; ev public.events; u uuid;
begin
  select * into r from public.event_announcements where id = a;
  select * into ev from public.events where id = r.event_id;
  if r.id is null or ev.id is null or r.status not in ('accepted', 'auto', 'direct') or r.sent_at is not null then return; end if;
  update public.event_announcements set sent_at = now() where id = a;
  if ev.status <> 'published' or coalesce(ev.ends_at, ev.starts_at, 'infinity') <= now() or ev.public_link then return; end if;
  if r.group_id = private.vip_group_id() and ev.visibility = 'all' then
    perform private.broadcast_new_event(ev);
    return;
  end if;
  for u in select m.user_id from public.member_group_members m where m.group_id = r.group_id loop
    if private.should_invite(ev, u) then perform private.queue_private_invite(ev, u); end if;
  end loop;
end $function$;

CREATE OR REPLACE FUNCTION private.open_announcements(e uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare ev public.events; g uuid; a uuid; direct boolean; who text;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or ev.status <> 'published' or ev.public_link
     or coalesce(ev.ends_at, ev.starts_at, 'infinity') <= now() then return; end if;
  who := private.person_label(ev.created_by);

  for g in select eg.group_id from public.event_groups eg where eg.event_id = e and eg.status = 'pending' loop
    perform private.tell_validators(g, ev.created_by, 'group_event_request', 'Événement à valider pour ton groupe',
      who || ' propose « ' || ev.title || ' » au groupe ' || private.group_label(g) || '.', 'group_event_request:' || e || ':' || g, e);
  end loop;

  if not ev.announce_group then return; end if;
  for g in select eg.group_id from public.event_groups eg where eg.event_id = e and eg.status = 'approved'
           union select private.vip_group_id() where ev.visibility = 'all' loop
    continue when g is null or exists (select 1 from public.event_announcements x where x.event_id = e and x.group_id = g);
    direct := private.may_approve_announcement(g, ev.created_by)
           or coalesce((select mg.announce_mode from public.member_groups mg where mg.id = g), 'request') = 'free';
    a := null;
    insert into public.event_announcements (event_id, group_id, requested_by, status, answered_at)
      values (e, g, ev.created_by, case when direct then 'direct' else 'pending' end, case when direct then now() end)
      on conflict (event_id, group_id) do nothing
      returning id into a;
    continue when a is null;
    if direct then
      perform private.send_announcement(a);
    else
      perform private.tell_validators(g, ev.created_by, 'announce_request', 'Annonce à valider',
        who || ' veut prévenir le groupe ' || private.group_label(g) || ' de « ' || ev.title
        || ' ». Sans réponse sous 48 h, l’annonce part d’office.', 'announce_request:' || a, e);
    end if;
  end loop;
end $function$;

CREATE OR REPLACE FUNCTION private.on_event_announce()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  -- « Prévenir le groupe » coupé ou événement devenu public : les demandes encore en attente tombent.
  if tg_op = 'UPDATE' and (not new.announce_group or new.public_link) then
    delete from public.event_announcements where event_id = new.id and status = 'pending';
  end if;
  perform private.open_announcements(new.id);
  return null;
end $function$;

CREATE OR REPLACE FUNCTION public.answer_group_event(e uuid, g uuid, accept boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare r public.event_groups; ev public.events; a uuid;
begin
  select * into r from public.event_groups where event_id = e and group_id = g for update;
  if r.event_id is null then raise exception 'Cette demande n’existe plus'; end if;
  if not private.may_approve_announcement(g, auth.uid()) then
    raise exception 'forbidden: réservé au créateur et aux admins du groupe' using errcode = '42501';
  end if;
  if r.status <> 'pending' then
    return jsonb_build_object('status', r.status, 'already', true, 'answered_by', private.person_label(r.answered_by));
  end if;
  select * into ev from public.events where id = e;
  -- Une seule décision (06.11, Q3) : accepter l'événement envoie aussi l'annonce demandée (« Prévenir le groupe »),
  -- acceptée par ce valideur ; refuser l'événement : rien n'est envoyé.
  if accept and ev.announce_group and ev.status = 'published' and not ev.public_link then
    insert into public.event_announcements (event_id, group_id, requested_by, status, answered_by, answered_at)
      values (e, g, ev.created_by, 'accepted', auth.uid(), now())
      on conflict (event_id, group_id) do nothing
      returning id into a;
  end if;
  update public.event_groups set status = case when accept then 'approved' else 'refused' end,
    answered_by = auth.uid(), answered_at = now() where event_id = e and group_id = g;
  if a is not null then perform private.send_announcement(a); end if;
  perform private.tell_requester(coalesce(r.requested_by, ev.created_by), case when accept then 'group_event_accepted' else 'group_event_refused' end, e,
    case when accept then 'Événement accepté par le groupe' else 'Événement refusé par le groupe' end,
    case when accept then '« ' || ev.title || ' » est maintenant visible par le groupe ' || private.group_label(g)
                          || case when a is not null then ', qui est prévenu.' else '.' end
         else '« ' || ev.title || ' » ne sera pas visible par le groupe ' || private.group_label(g) || '.' end);
  return jsonb_build_object('status', case when accept then 'approved' else 'refused' end, 'already', false);
end $function$;

CREATE OR REPLACE FUNCTION public.accept_invite(token uuid, answer text, first_name text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); arrived boolean; name text := btrim(coalesce(first_name, ''));
        current_name text; who text; u uuid;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if answer is null or answer not in ('yes', 'maybe', 'no') then raise exception 'Réponse inconnue'; end if;
  select * into l from private.invite_links il where il.token = accept_invite.token and il.kind = 'event' for update;
  if l.token is null then raise exception 'Ce lien d''invitation n''existe pas'; end if;
  select * into ev from public.events where id = l.target;
  if ev.id is null then raise exception 'Cet événement n''existe plus'; end if;
  if ev.status = 'cancelled' then raise exception 'Cet événement est annulé'; end if;
  if ev.status <> 'published' then raise exception 'Cet événement n''est plus ouvert'; end if;
  if l.revoked_at is not null then
    raise exception 'Ce lien a été arrêté par la personne qui t''a invité. Demande-lui un nouveau lien.';
  end if;

  -- Compte neuf : le prénom seul suffit (jamais nom, surnom ni photo ici).
  select display_name into current_name from public.profiles where id = me;
  if btrim(coalesce(current_name, '')) = '' then
    if name = '' then raise exception 'first_name_required: écris ton prénom'; end if;
    if char_length(name) > 40 then raise exception 'Prénom trop long (40 caractères au plus)'; end if;
    update public.profiles set display_name = name where id = me;
    insert into private.light_invitees (user_id, event_id) values (me, ev.id) on conflict (user_id) do nothing;
  end if;

  arrived := l.used_by = me or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
  if arrived then
    -- Déjà venu par ce lien : changer sa réponse, sauf si l'organisateur l'a retiré de la liste.
    if not public.can_see_event(ev.id) then
      raise exception 'removed: l''organisateur t''a retiré de la liste des invités';
    end if;
  else
    if l.used_by is not null or l.uses >= l.max_uses then
      raise exception '%', case when l.max_uses = 1
        then 'Ce lien a déjà servi : il était pour une seule personne. Demande ton propre lien.'
        else 'Toutes les places de ce lien sont prises. Demande un autre lien à la personne qui t''a invité.' end;
    end if;
    if l.expires_at <= now() then
      raise exception 'Ce lien n''est plus valable (date limite passée). Demande un nouveau lien.';
    end if;
    insert into private.invite_link_arrivals (token, user_id) values (l.token, me) on conflict do nothing;
    update private.invite_links il set uses = il.uses + 1,
        used_by = case when il.max_uses = 1 then me else il.used_by end,
        used_at = case when il.max_uses = 1 then now() else il.used_at end,
        opened_at = coalesce(il.opened_at, now())
      where il.token = l.token;
    -- Invité de CET événement seulement (jamais ajouté à un groupe) ; un membre qui le voit déjà n'a pas de ligne.
    if not public.can_see_event(ev.id) or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me) then
      insert into public.event_invites (event_id, user_id, via_group, via_link, invited_by, link_token)
        values (ev.id, me, false, true, l.created_by, l.token)
      on conflict (event_id, user_id) do update set via_link = true,
        invited_by = coalesce(public.event_invites.invited_by, excluded.invited_by),
        link_token = coalesce(public.event_invites.link_token, excluded.link_token);
    end if;
    select display_name into who from public.profiles where id = me;
    for u in select x from (select ev.created_by x union select user_id from public.event_organizers where event_id = ev.id) o loop
      perform public.queue_notification(u, 'link_join', ev.id, ev.title,
        coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a répondu par ton lien d''invitation',
        'link_join:' || ev.id || ':' || me);
    end loop;
  end if;

  insert into public.rsvps (event_id, user_id, status) values (ev.id, me, answer::public.rsvp_status)
  on conflict (event_id, user_id) do update set status = excluded.status;

  return jsonb_build_object('event_id', ev.id, 'status', answer, 'title', ev.title,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day, 'date_mode', ev.date_mode,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'description', ev.description,
    'waitlisted', (select r.waitlisted from public.rsvps r where r.event_id = ev.id and r.user_id = me));
end $function$;

CREATE OR REPLACE FUNCTION public.invite_preview(token uuid, opened boolean DEFAULT false)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text;
begin
  if token is null then return null; end if;
  select * into l from private.invite_links il where il.token = invite_preview.token and il.kind = 'event';
  if l.token is null then return null; end if;
  select * into ev from public.events where id = l.target and status in ('published', 'cancelled');
  if ev.id is null then return null; end if;
  if opened and l.opened_at is null and me is distinct from l.created_by and l.revoked_at is null then
    update private.invite_links il set opened_at = now() where il.token = l.token;
  end if;
  if me is not null then
    arrived := l.used_by = me or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
    select * into mine from public.rsvps r where r.event_id = ev.id and r.user_id = me;
  end if;
  state := private.invite_link_state(l);
  select display_name into who from public.profiles where id = coalesce(l.created_by, ev.created_by);
  return jsonb_build_object(
    'state', case when arrived and state <> 'revoked' then 'mine' else state end,
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 then greatest(l.max_uses - l.uses, 0) end,
    'inviter', nullif(btrim(coalesce(who, '')), ''),
    'title', ev.title, 'status', ev.status, 'date_mode', ev.date_mode,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', coalesce(ev.location_name, case when arrived then ev.location_address end),
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'description', left(ev.description, 400),
    'allow_maybe', ev.allow_maybe,
    'closed', ev.rsvp_deadline is not null and now() > ev.rsvp_deadline,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select private.first_word(p.display_name) n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and private.first_word(p.display_name) is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Ce que voit la personne qui a déjà répondu par ce lien (changer sa réponse, adresse, itinéraire).
    'mine', case when arrived and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived then ev.id end,
    'location_address', case when arrived then ev.location_address end,
    'location_url', case when arrived then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''));
end $function$;

CREATE OR REPLACE FUNCTION public.guard_event()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare s group_settings; privileged boolean;
begin
  select * into s from group_settings;
  new.updated_at := now();
  if auth.uid() is null then return new; end if;  -- cron, service role

  privileged := has_perm('events.publish_direct');

  if tg_op = 'INSERT' then
    new.created_by := auth.uid();
    new.approved_by := null; new.approved_at := null; new.rejection_reason := null;
    if new.status <> 'draft' then
      if privileged or not s.require_approval then
        new.status := 'published'; new.approved_by := auth.uid(); new.approved_at := now();
      else
        new.status := 'pending';
      end if;
    end if;
    return new;
  end if;

  new.created_by := old.created_by;
  if has_perm('events.manage_all') then
    if new.status = 'published' and old.status <> 'published' then
      new.approved_by := auth.uid(); new.approved_at := now(); new.rejection_reason := null;
    end if;
    return new;
  end if;

  new.approved_by := old.approved_by; new.approved_at := old.approved_at;
  new.rejection_reason := old.rejection_reason;
  -- Annulé (05.11) : il le reste ; seul events.manage_all (plus haut) le rouvre.
  if old.status = 'cancelled' then new.status := 'cancelled'; return new; end if;
  if old.status = 'published' then
    if new.status = 'cancelled' then return new; end if;
    -- Annonce au groupe (06.11) : seul « Prévenir le groupe » change → organisateurs et co-organisateurs.
    if (to_jsonb(new) - 'announce_group' - 'updated_at') = (to_jsonb(old) - 'announce_group' - 'updated_at')
       and public.is_organizer(new.id) then return new; end if;
    -- Billets QR (04.11) : seule l'option change → organisateurs et co-organisateurs, même publié.
    if (to_jsonb(new) - 'tickets_enabled' - 'updated_at') = (to_jsonb(old) - 'tickets_enabled' - 'updated_at')
       and private.can_manage_tickets_option(new.id) then return new; end if;
    if not has_perm('events.edit_own_published') then
      raise exception 'Seul un admin peut modifier un événement publié';
    end if;
    new.status := 'published';
  elsif new.status = 'draft' then
    null;
  elsif privileged or not s.require_approval then
    new.status := 'published'; new.approved_by := auth.uid(); new.approved_at := now();
  else
    new.status := 'pending'; new.rejection_reason := null;
  end if;
  return new;
end $function$;

CREATE OR REPLACE FUNCTION public.notify_event_change()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare u uuid;
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
    -- Invités un à un (et membres d'un groupe déjà annoncé) : private.should_invite décide.
    for u in select i.user_id from event_invites i where i.event_id = new.id
             union select p.id from event_phone_invites pi join profiles p on p.phone = pi.phone where pi.event_id = new.id loop
      if private.should_invite(new, u) then perform private.queue_private_invite(new, u); end if;
    end loop;
    -- Annonce au groupe (Vendredi Party compris) : private.open_announcements (déclencheur events_announce).
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
end $function$;

CREATE OR REPLACE FUNCTION private.may_receive_push(uid uuid, kind text)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select private.is_member(uid)
    or (kind in ('pet_daily', 'pet_alert', 'pet_gift', 'pet_streak', 'pet_bar') and private.is_account_active(uid))
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message', 'moderation_notice', 'report_new',
                 'private_invite', 'announce_request', 'announce_accepted', 'announce_refused', 'group_event_request', 'group_event_accepted', 'group_event_refused', 'event_changed', 'date_fixed', 'reminder', 'waitlist')
        and private.is_account_active(uid));
$function$;

CREATE OR REPLACE FUNCTION private.web_push_allowed(notification notifications)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare prefs public.notification_prefs; ev public.events;
begin
  if not exists(select 1 from public.profiles where id=notification.user_id and private.may_receive_push(id, notification.kind)) then return false; end if;
  if notification.kind in ('web_push_test', 'push_test') then return true; end if;
  select * into prefs from public.notification_prefs where user_id=notification.user_id;
  if notification.kind='admin_announcement' then
    return exists(select 1 from public.admin_announcements where id::text=notification.data->>'announcement_id')
      and coalesce(prefs.announcements, true);
  end if;
  if prefs.user_id is null or not prefs.push_enabled then return false; end if;
  if notification.event_id is not null then
    select * into ev from public.events where id=notification.event_id;
    if ev.id is null or exists(select 1 from public.event_mutes where event_id=ev.id and user_id=notification.user_id) then return false; end if;
    if not (exists(select 1 from public.profiles where id=notification.user_id and private.user_has(id, 'events.manage_all'))
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
    when 'rsvp_set' then prefs.rsvp_set
    when 'private_invite' then prefs.invites
    when 'approved' then prefs.proposal_result
    when 'rejected' then prefs.proposal_result
    when 'link_join' then prefs.link_join
    when 'group_message' then prefs.group_messages
    when 'group_invite' then prefs.group_invites
    when 'group_join' then prefs.group_joins
    when 'report_new' then coalesce(prefs.moderation_reports, true)
    when 'moderation_notice' then coalesce(prefs.moderation_notices, true)
    when 'pet_daily' then coalesce(prefs.pet_daily, true)
    when 'pet_alert' then coalesce(prefs.pet_alerts, true)
    when 'pet_gift' then coalesce(prefs.pet_gifts, true)
    when 'pet_streak' then coalesce(prefs.pet_streaks, true)
    when 'pet_bar' then coalesce(prefs.pet_bar, true)
    when 'referral_join' then coalesce(prefs.referral_joins, true)
    when 'ticket_pay_declared' then coalesce(prefs.ticket_pay_declared, true)
    when 'ticket_pay_confirmed' then coalesce(prefs.ticket_pay_confirmed, true)
    when 'ticket_issued' then coalesce(prefs.ticket_issued, true)
    when 'direct_message' then coalesce(prefs.direct_messages, true)
    when 'announce_request' then coalesce(prefs.announce_requests, true)
    when 'announce_accepted' then coalesce(prefs.announce_results, true)
    when 'announce_refused' then coalesce(prefs.announce_results, true)
    when 'group_event_request' then coalesce(prefs.group_event_requests, true)
    when 'group_event_accepted' then coalesce(prefs.announce_results, true)
    when 'group_event_refused' then coalesce(prefs.announce_results, true)
    else true end;
end $function$;

CREATE OR REPLACE FUNCTION public.invite_people(e uuid, people uuid[] DEFAULT '{}'::uuid[], groups uuid[] DEFAULT '{}'::uuid[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare ev public.events; u uuid; g uuid; added int := 0; grp int := 0; n int;
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  if coalesce(array_length(people, 1), 0) > 100 or coalesce(array_length(groups, 1), 0) > 20 then
    raise exception 'Trop de personnes d''un coup';
  end if;
  select * into ev from public.events where id = e;
  foreach u in array coalesce(people, '{}') loop
    if u = ev.created_by or not private.is_account_active(u) then continue; end if;
    -- Déjà invité (groupe, lien, un par un) ou membre de Vendredi Party pour un événement du groupe : rien à ajouter.
    if ev.visibility = 'all' and not ev.public_link and private.is_member(u) then continue; end if;
    insert into public.event_invites (event_id, user_id, via_group, invited_by) values (e, u, false, auth.uid())
    on conflict (event_id, user_id) do nothing;
    get diagnostics n = row_count;
    if n > 0 then
      added := added + 1;
      -- Toujours prévenu quand on l'ajoute d'ici (même si « prévenir à la publication » était coupé).
      if ev.status = 'published' and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() then
        perform private.queue_private_invite(ev, u);
      end if;
    end if;
  end loop;
  foreach g in array coalesce(groups, '{}') loop
    if not exists (select 1 from public.member_groups mg where mg.id = g and mg.system_key is null
                   and (public.is_admin() or mg.created_by = auth.uid()
                        or exists (select 1 from public.member_group_members m where m.group_id = g and m.user_id = auth.uid()))) then
      raise exception 'forbidden: tu ne peux inviter que tes groupes' using errcode = '42501';
    end if;
    insert into public.event_groups (event_id, group_id) values (e, g) on conflict do nothing;
    get diagnostics n = row_count;
    grp := grp + n;
  end loop;
  return jsonb_build_object('people', added, 'groups', grp);
end $function$;

alter table public.event_groups drop column if exists announce;
delete from supabase_migrations.schema_migrations where version = '20261107100000';
commit;

notify pgrst, 'reload schema';
