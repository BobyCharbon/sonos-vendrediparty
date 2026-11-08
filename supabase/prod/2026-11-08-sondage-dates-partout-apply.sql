-- PROD, sondage_dates_partout (20261108090000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Sondage de dates, une seule logique : l'invité venu par un lien vote les dates (aucun « je viens » avant la date
-- fixée), la carte « Invités » compte les votants, la date fixée inscrit chacun selon son vote pour cette date.
-- Prérequis (déjà en prod) : 20261105200000_invitations_v2, 20261107100000_campagne2_invitations,
-- 20261107110000_campagne2_reponses. Rejouable. Tout ou rien. Aucune donnée modifiée.
begin;
-- Sondage de dates, une seule logique partout (retours de l'admin du 08.11) :
-- - invité venu par un lien : il vote les dates comme un membre de l'app (accept_invite « poll » : aucune réponse
--   « je viens » avant que la date soit fixée) ;
-- - liste des invités : « voted » (a voté au moins une date) et « poll », pour compter comme le sondage ;
-- - date fixée : le vote pour la date retenue décide (Oui → vient, Si besoin → peut-être, Non → ne vient pas).
-- Purement additif et rejouable (create or replace).

create or replace function public.accept_invite(token uuid, answer text, first_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); arrived boolean; name text := btrim(coalesce(first_name, ''));
        current_name text; who text; u uuid;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if answer is null or answer not in ('yes', 'maybe', 'no', 'poll') then raise exception 'Réponse inconnue'; end if;
  select * into l from private.invite_links il where il.token = accept_invite.token and il.kind = 'event' for update;
  if l.token is null then raise exception 'Ce lien d''invitation n''existe pas'; end if;
  select * into ev from public.events where id = l.target;
  if ev.id is null then raise exception 'Cet événement n''existe plus'; end if;
  if ev.status = 'cancelled' then raise exception 'Cet événement est annulé'; end if;
  if ev.status <> 'published' then raise exception 'Cet événement n''est plus ouvert'; end if;
  -- Sondage de dates (08.11) : répondre = voter les dates, comme dans l'app ; jamais de « je viens » avant la date fixée.
  -- Date fixée : « poll » (ancienne page restée ouverte) n'est pas une réponse.
  if ev.date_mode = 'poll' then answer := 'poll';
  elsif answer = 'poll' then raise exception 'La date est fixée : réponds « Je viens », « Peut-être » ou « Je ne peux pas ».';
  end if;
  if l.revoked_at is not null then
    raise exception 'Ce lien a été arrêté par la personne qui t''a invité. Demande-lui un nouveau lien.';
  end if;

  -- L'organisateur (ou un co-organisateur) qui essaie son propre lien : sa réponse compte, le lien reste intact.
  if public.is_organizer(ev.id) then
    if answer <> 'poll' then
      insert into public.rsvps (event_id, user_id, status) values (ev.id, me, answer::public.rsvp_status)
      on conflict (event_id, user_id) do update set status = excluded.status;
    end if;
    return jsonb_build_object('event_id', ev.id, 'status', nullif(answer, 'poll'), 'title', ev.title, 'organizer', true,
      'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day, 'date_mode', ev.date_mode,
      'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
      'description', ev.description,
      'waitlisted', (select r.waitlisted from public.rsvps r where r.event_id = ev.id and r.user_id = me));
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
    -- En blocage avec l'organisateur ou avec l'auteur du lien : n'entre pas (sans dire qui a bloqué).
    if private.blocked_either(ev.created_by, me) or private.blocked_either(l.created_by, me) then
      raise exception 'Tu ne peux pas répondre à cette invitation.' using errcode = '42501';
    end if;
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

  if answer <> 'poll' then
    insert into public.rsvps (event_id, user_id, status) values (ev.id, me, answer::public.rsvp_status)
    on conflict (event_id, user_id) do update set status = excluded.status;
  end if;

  return jsonb_build_object('event_id', ev.id, 'status', nullif(answer, 'poll'), 'title', ev.title,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day, 'date_mode', ev.date_mode,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'description', ev.description,
    'waitlisted', (select r.waitlisted from public.rsvps r where r.event_id = ev.id and r.user_id = me));
end $$;

create or replace function public.event_guest_list(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events; vip boolean; vip_name text;
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  vip := ev.visibility = 'all' and not ev.public_link;
  select name into vip_name from public.member_groups where system_key = 'vip' limit 1;
  return jsonb_build_object(
    'vip', vip, 'public', ev.public_link, 'vip_name', vip_name, 'poll', ev.date_mode = 'poll',
    'groups', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'name', g.name,
        'members', (select count(*) from public.member_group_members m where m.group_id = g.id)) order by g.name)
      from public.event_groups eg join public.member_groups g on g.id = eg.group_id where eg.event_id = e), '[]'::jsonb),
    'people', coalesce((select jsonb_agg(x order by x->>'name') from (
      select jsonb_build_object(
        'id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url,
        'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
        'answered_at', r.updated_at,
        -- Sondage de dates : a voté pour au moins une date (la réponse d'un sondage, 08.11).
        'voted', exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                         where o.event_id = e and dv.user_id = p.id),
        'source', case when i.user_id is null then (case when vip and private.is_member(p.id) then 'vip' else 'public' end)
                       when i.via_group then 'group' when i.via_link then 'link' else 'person' end,
        'group', case when i.user_id is null and vip and private.is_member(p.id) then vip_name
                      when i.via_group then (select string_agg(g.name, ', ' order by g.name) from public.event_groups eg
                        join public.member_groups g on g.id = eg.group_id
                        join public.member_group_members gm on gm.group_id = g.id and gm.user_id = p.id where eg.event_id = e) end,
        'invited_by', case when i.via_group then null else (select display_name from public.profiles where id = i.invited_by) end,
        'invited_by_id', case when i.via_group then null else i.invited_by end,
        'link_label', (select il.label from private.invite_links il where il.token = i.link_token), 'link_token', i.link_token,
        'invited_at', i.created_at,
        'has_app', private.has_app(p.id),
        'light', exists (select 1 from private.light_invitees li where li.user_id = p.id),
        'nudged_today', private.nudged_today(e, p.id, null) is not null,
        'removable', i.user_id is not null and not i.via_group) x
      from public.profiles p
      left join public.event_invites i on i.event_id = e and i.user_id = p.id
      left join public.rsvps r on r.event_id = e and r.user_id = p.id
      where p.status = 'active' and p.id <> ev.created_by
        and (i.user_id is not null or r.user_id is not null or (vip and private.is_member(p.id))
             or exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                        where o.event_id = e and dv.user_id = p.id))) s), '[]'::jsonb),
    'links', coalesce((select jsonb_agg(x order by x->>'created_at' desc) from (
      select jsonb_build_object(
        'token', l.token, 'label', l.label, 'max_uses', l.max_uses, 'uses', l.uses, 'created_at', l.created_at,
        'expires_at', l.expires_at, 'opened_at', l.opened_at, 'state', private.invite_link_state(l), 'version', l.version,
        'created_by', (select display_name from public.profiles where id = l.created_by), 'created_by_id', l.created_by,
        'nudged_today', private.nudged_today(e, null, l.token) is not null,
        'arrivals', coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id)) order by a.at)
          from private.invite_link_arrivals a join public.profiles p on p.id = a.user_id where a.token = l.token),
          case when l.used_by is not null then (select jsonb_build_array(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id)))
            from public.profiles p where p.id = l.used_by) else '[]'::jsonb end)) x
      from private.invite_links l
      where l.kind = 'event' and l.target = e and (l.revoked_at is null or l.uses > 0 or l.used_by is not null)
      order by l.created_at desc limit 60) s), '[]'::jsonb));
end $$;

create or replace function public.do_fix_event_date(e uuid, opt uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
declare o date_options; ev events; v record;
begin
  perform private.lock_event_places(e);
  select * into o from date_options where id = opt and event_id = e;
  if not found then raise exception 'Créneau introuvable'; end if;
  update events set date_mode = 'fixed', starts_at = o.starts_at, ends_at = o.ends_at where id = e;
  select * into ev from events where id = e;
  for v in select dv.user_id, dv.vote from date_votes dv
           where dv.option_id = opt and dv.vote in ('yes', 'if_needed')
           order by (dv.vote = 'yes') desc, dv.user_id loop
    -- « Si besoin » sans « Peut-être » : aucune réponse (07.11), la personne répondra elle-même.
    continue when v.vote = 'if_needed' and not ev.allow_maybe;
    -- Sans liste d'attente : seuls les « Oui » qui tiennent dans les places sont inscrits.
    continue when v.vote = 'yes' and not ev.waitlist_enabled and ev.max_participants is not null
      and (select coalesce(sum(1 + r.plus_ones), 0) from rsvps r
           where r.event_id = e and r.status = 'yes' and not r.waitlisted) >= ev.max_participants;
    -- Le vote pour la date retenue décide (08.11) : il remplace une ancienne réponse donnée par un lien.
    insert into rsvps (event_id, user_id, status)
    values (e, v.user_id, case v.vote when 'yes' then 'yes'::rsvp_status else 'maybe'::rsvp_status end)
    on conflict (event_id, user_id) do update set status = excluded.status;
  end loop;
  -- « Non » à la date retenue : ne vient pas, même s'il avait dit « je viens » par un lien avant le sondage.
  insert into rsvps (event_id, user_id, status)
  select e, dv.user_id, 'no'::rsvp_status from date_votes dv where dv.option_id = opt and dv.vote = 'no'
  on conflict (event_id, user_id) do update set status = 'no';
  perform apply_waitlist(e);
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261108090000', 'sondage_dates_partout')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
