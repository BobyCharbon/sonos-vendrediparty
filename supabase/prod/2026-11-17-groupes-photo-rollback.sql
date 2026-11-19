-- PROD, retour arrière de groupes_photo (20261117130000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
CREATE OR REPLACE FUNCTION private.moderation_hide(r content_reports)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare uid uuid;
begin
  if r.target_kind like 'pet\_%' then
    perform private.moderation_hide_pet(r.target_kind, r.target_id);
    return '{}'::jsonb;
  end if;
  uid := r.target_id::uuid;
  if r.target_kind = 'group_message' then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false,
      pinned = false, announcement = false, deleted_at = coalesce(deleted_at, now()), deleted_by_admin = true where id = uid;
    delete from public.group_message_reactions where message_id = uid;
  elsif r.target_kind = 'direct_message' then
    update public.direct_messages set body = '', photo_path = null, audio_path = null, pinned = false,
      deleted_at = coalesce(deleted_at, now()) where id = uid;
    delete from public.direct_message_reactions where message_id = uid;
  elsif r.target_kind = 'event_message' then
    update public.messages set body = '•', mentions = '{}', pinned = false, deleted_at = coalesce(deleted_at, now()) where id = uid;
  elsif r.target_kind = 'event' then
    if not private.user_has(auth.uid(), 'events.manage_all') then
      raise exception 'forbidden: masquer un événement demande aussi le droit « Modifier ou annuler tous les événements »'
        using errcode = '42501';
    end if;
    update public.events set title = 'Événement masqué par la modération', description = '', cover_url = null,
      public_link = false where id = uid;
  elsif r.target_kind = 'rsvp_note' then
    delete from public.rsvp_notes where id = uid;
  elsif r.target_kind = 'poll' then
    update public.polls set question = 'Question masquée par la modération' where id = uid;
  elsif r.target_kind = 'poll_option' then
    delete from public.poll_options where id = uid;
  elsif r.target_kind = 'bring_item' then
    delete from public.bring_items where id = uid;
  elsif r.target_kind = 'profile' then
    update public.profiles set display_name = 'Surnom masqué' where id = uid;
  elsif r.target_kind = 'profile_photo' then
    -- Le fichier se retire par l'API Storage (politique « modérateurs retirent une photo signalée ») : l'appli le fait.
    return jsonb_build_object('remove_photo', r.snapshot ->> 'photo_path');
  end if;
  return '{}'::jsonb;
end $function$;

CREATE OR REPLACE FUNCTION private.notify_new_report()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare u uuid;
begin
  for u in select p.id from public.profiles p where p.status = 'active' and private.user_has(p.id, 'moderation.reports') loop
    perform public.queue_notification(u, 'report_new', null, 'Nouveau signalement',
      (case new.reason when 'harassment' then 'Harcèlement' when 'shocking' then 'Contenu choquant' when 'spam' then 'Spam'
                       when 'scam' then 'Arnaque ou vente' else 'Autre raison' end)
      || ' · ' || (case when new.target_kind in ('group_message', 'direct_message', 'event_message') then 'un message'
                        when new.target_kind = 'profile' then 'un profil' when new.target_kind = 'profile_photo' then 'une photo de profil'
                        when new.target_kind = 'event' then 'un événement'
                        when new.target_kind = 'rsvp_note' then 'un petit mot'
                        when new.target_kind in ('poll', 'poll_option') then 'un sondage'
                        when new.target_kind = 'bring_item' then 'un objet à amener'
                        else 'Zicou' end),
      'report:' || new.id, jsonb_build_object('report_id', new.id));
  end loop;
  return null;
end $function$;

CREATE OR REPLACE FUNCTION private.report_snapshot(p_kind text, p_id text, viewer uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare gm public.group_messages; dm public.direct_messages; em public.messages; p public.profiles; ev public.events; uid uuid;
        rn public.rsvp_notes; po public.polls; op public.poll_options; bi public.bring_items;
begin
  if p_kind like 'pet\_%' then return private.report_snapshot_pet(p_kind, p_id, viewer); end if;
  begin uid := p_id::uuid; exception when others then return null; end;
  if p_kind = 'group_message' then
    select * into gm from public.group_messages where id = uid;
    if gm.id is null or not private.reads_group(gm.group_id) then return null; end if;
    return jsonb_build_object('owner', gm.user_id, 'text', gm.body, 'photo_path', gm.photo_path, 'audio_path', gm.audio_path,
      'at', gm.created_at, 'place', (select name from public.member_groups where id = gm.group_id), 'group_id', gm.group_id);
  elsif p_kind = 'direct_message' then
    select * into dm from public.direct_messages where id = uid;
    if dm.id is null or not private.in_direct(dm.chat_id, viewer) then return null; end if;
    return jsonb_build_object('owner', dm.user_id, 'text', dm.body, 'photo_path', dm.photo_path, 'audio_path', dm.audio_path,
      'at', dm.created_at, 'place', 'Message direct', 'chat_id', dm.chat_id);
  elsif p_kind = 'event_message' then
    select * into em from public.messages where id = uid;
    if em.id is null or not public.can_see_event(em.event_id) then return null; end if;
    return jsonb_build_object('owner', em.user_id, 'text', em.body, 'at', em.created_at, 'event_id', em.event_id,
      'place', (select title from public.events where id = em.event_id));
  elsif p_kind = 'event' then
    select * into ev from public.events where id = uid;
    if ev.id is null then return null; end if;
    if not (public.can_see_event(ev.id)
            or (ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled'))) then
      return null;
    end if;
    return jsonb_build_object('owner', ev.created_by,
      'text', ev.title || case when btrim(coalesce(ev.description, '')) <> '' then E'\n\n' || ev.description else '' end
        || case when btrim(coalesce(ev.chat_description, '')) <> '' then E'\n\nDescription de la discussion : ' || ev.chat_description else '' end,
      'cover_url', ev.cover_url, 'at', ev.created_at, 'event_id', ev.id, 'place', 'Événement');
  elsif p_kind = 'rsvp_note' then
    -- Lu par la personne et l'organisation seulement : seuls eux peuvent le signaler.
    select * into rn from public.rsvp_notes where id = uid;
    if rn.id is null or not (rn.user_id = viewer or public.is_admin() or public.is_organizer(rn.event_id)) then return null; end if;
    return jsonb_build_object('owner', rn.user_id, 'text', rn.note, 'at', rn.updated_at, 'event_id', rn.event_id,
      'place', 'Petit mot · ' || (select title from public.events where id = rn.event_id));
  elsif p_kind = 'poll' then
    select * into po from public.polls where id = uid;
    if po.id is null or not ((po.event_id is null and public.is_active()) or public.can_see_event(po.event_id)
                             or public.is_organizer(po.event_id)) then return null; end if;
    return jsonb_build_object('owner', po.created_by, 'text', po.question, 'at', po.created_at, 'event_id', po.event_id,
      'place', 'Sondage' || coalesce(' · ' || (select title from public.events where id = po.event_id), ''));
  elsif p_kind = 'poll_option' then
    select * into op from public.poll_options where id = uid;
    select * into po from public.polls where id = op.poll_id;
    if op.id is null or not ((po.event_id is null and public.is_active()) or public.can_see_event(po.event_id)
                             or public.is_organizer(po.event_id)) then return null; end if;
    return jsonb_build_object('owner', coalesce(op.created_by, po.created_by), 'text', op.label, 'event_id', po.event_id,
      'place', 'Sondage · ' || po.question);
  elsif p_kind = 'bring_item' then
    select * into bi from public.bring_items where id = uid;
    if bi.id is null or not (public.can_see_event(bi.event_id) or public.is_organizer(bi.event_id)) then return null; end if;
    return jsonb_build_object('owner', bi.added_by, 'text', bi.label, 'event_id', bi.event_id,
      'place', 'Qui amène quoi · ' || (select title from public.events where id = bi.event_id));
  elsif p_kind in ('profile', 'profile_photo') then
    select * into p from public.profiles where id = uid and status = 'active';
    if p.id is null then return null; end if;
    return jsonb_build_object('owner', p.id, 'text', p.display_name,
      'photo_path', case when p_kind = 'profile_photo' then p.avatar_url end, 'place', 'Profil');
  end if;
  return null;
end $function$;

CREATE OR REPLACE FUNCTION public.my_chats()
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select coalesce(jsonb_agg(c order by (c->>'last_at') desc nulls last, c->>'name'), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', g.id, 'name', g.name, 'kind', 'group', 'system', g.system_key is not null,
      'member', private.in_group_now(g.id, auth.uid()),
      'admin', private.group_admin(g.id, auth.uid()),
      'creator', g.created_by = auth.uid(),
      'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
      'notify', coalesce(s.notify, 'mentions'),
      'last_at', last.created_at,
      'last', case when last.id is null then null
                   when last.deleted_at is not null then case when last.deleted_by_admin then 'Message supprimé par un admin' else 'Message supprimé' end
                   else coalesce((select display_name from public.profiles where id = last.user_id), '?') || ' : '
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or private.is_root(auth.uid()))
    union all
    select jsonb_build_object(
      'id', d.id, 'name', coalesce(nullif(btrim(o.display_name), ''), 'Profil à compléter'), 'kind', 'direct', 'system', false,
      'user_id', o.id, 'avatar_url', o.avatar_url,
      'member', true, 'admin', false, 'creator', false, 'members', 2,
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = o.id),
      'notify', coalesce(s.notify, 'all'),
      'last_at', last.created_at,
      'last', case when last.deleted_at is not null then 'Message supprimé'
                   else case when last.user_id = auth.uid() then 'Toi : ' else '' end
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.direct_messages m where m.chat_id = d.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.direct_chats d
    join public.profiles o on o.id = case when d.user_a = auth.uid() then d.user_b else d.user_a end
    left join public.direct_chat_settings s on s.chat_id = d.id and s.user_id = auth.uid()
    join lateral (select * from public.direct_messages m where m.chat_id = d.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)
  ) x;
$function$;

drop trigger if exists member_groups_photo_changed on public.member_groups;

drop trigger if exists member_groups_photo_guard on public.member_groups;

delete from supabase_migrations.schema_migrations where version = '20261117130000';
commit;
