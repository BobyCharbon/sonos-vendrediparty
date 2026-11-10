-- Inscription complète pour toute personne invitée (avis 39f148377a8f du 10.11, sondage du paintball) :
-- - accept_invite exige un profil complet (prénom, nom, surnom ; photo facultative), fait par le parcours normal
--   (connexion SMS puis « Faisons connaissance ») : plus aucun compte « invité léger » créé au prénom seul ;
-- - toute arrivée par lien d'un compte hors du groupe laisse une ligne event_invites (via_link), même sur un
--   événement public : l'organisateur voit d'où vient la personne, et la purge ne peut plus la prendre ;
-- - la purge des invités légers compte aussi les VOTES de date (cause du bug : sur un sondage public, ni event_invites
--   ni rsvp → compte effacé avec ses votes, le soir même ou 7 jours après) ; la promesse de la politique de
--   confidentialité reste tenue (effacé 7 jours après le dernier événement) ; jamais un compte au profil complet,
--   sanctionné ou signalé (preuves de modération gardées) ;
-- - sondage : la carte d'invitation et la page publique comptent les VOTANTS (« voters »), comme la fiche.
-- Purement additif et rejouable (create or replace, même signature, mêmes droits).

-- 1. Accepter une invitation : profil complet d'abord -------------------------------------------------------------
create or replace function public.accept_invite(token uuid, answer text, first_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); arrived boolean; who text; u uuid;
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
  -- Sondage de dates : répondre = voter les dates, comme dans l'app ; jamais de « je viens » avant la date fixée.
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

  -- coalesce : l.used_by vaut NULL tant que le lien n'a pas servi ; « not NULL » sauterait l'arrivée plus bas.
  arrived := coalesce(l.used_by = me, false) or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
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
  end if;

  -- Profil complet obligatoire (10.11) : le prénom seul ne suffit plus ; l'écran envoie vers « Faisons connaissance ».
  -- Vérifié après les contrôles du lien (plein, expiré…) : on ne fait pas remplir un profil pour un lien déjà refusé.
  if not private.identity_complete(me) then
    raise exception 'profile_required: complète ton profil (prénom, nom et surnom) pour répondre' using errcode = '42501';
  end if;

  if not arrived then
    insert into private.invite_link_arrivals (token, user_id) values (l.token, me) on conflict do nothing;
    update private.invite_links il set uses = il.uses + 1,
        used_by = case when il.max_uses = 1 then me else il.used_by end,
        used_at = case when il.max_uses = 1 then now() else il.used_at end,
        opened_at = coalesce(il.opened_at, now())
      where il.token = l.token;
    -- Invité de CET événement seulement (jamais ajouté à un groupe). Un membre du groupe qui le voit déjà n'a pas de
    -- ligne ; une personne hors du groupe en a TOUJOURS une, même sur un événement public (10.11 : sinon l'organisateur
    -- ne savait pas d'où elle venait, et la purge la prenait avec ses votes).
    if not public.can_see_event(ev.id) or not private.is_member(me)
       or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me) then
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

-- 2. Purge des comptes invités minimaux : 7 jours après leur dernier événement, votes compris ------------------------
create or replace function private.light_invitees_to_purge() returns setof uuid
language sql stable security definer set search_path = '' as $$
  select li.user_id from private.light_invitees li join public.profiles p on p.id = li.user_id
  where li.created_at < now() - interval '7 days'
    and btrim(p.first_name) = '' and btrim(p.last_name) = '' and coalesce(btrim(p.avatar_url), '') = ''
    and p.role = 'guest' and p.status = 'active' and not private.is_root(p.id)
    and not private.identity_complete(p.id)
    and not exists (select 1 from public.push_tokens t where t.user_id = p.id)
    and not exists (select 1 from public.member_group_members m where m.user_id = p.id)
    and not exists (select 1 from public.event_invites i where i.user_id = p.id and not i.via_link)
    and not exists (select 1 from public.events ev where ev.created_by = p.id)
    -- Preuves de modération (Apple 1.2) : un compte sanctionné ou signalé n'est jamais effacé par la purge.
    and not exists (select 1 from public.moderation_sanctions s where s.user_id = p.id)
    and not exists (select 1 from public.content_reports c where c.target_user = p.id)
    and not exists (select 1 from public.event_invites i join public.events ev on ev.id = i.event_id
                    where i.user_id = p.id and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() - interval '7 days')
    and not exists (select 1 from public.rsvps r join public.events ev on ev.id = r.event_id
                    where r.user_id = p.id and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() - interval '7 days')
    -- 10.11 : un vote de date compte comme une réponse (sondage sans date fixée : jamais effacé tant qu'il dure).
    and not exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                    join public.events ev on ev.id = o.event_id
                    where dv.user_id = p.id and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() - interval '7 days');
$$;

-- 3. Carte d'un lien : en sondage, on compte les votants (comme la fiche), et on dit si le profil est complet ------
create or replace function public.invite_preview(token uuid, opened boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text; organizer boolean := false;
begin
  if token is null then return null; end if;
  select * into l from private.invite_links il where il.token = invite_preview.token and il.kind = 'event';
  if l.token is null then return null; end if;
  select * into ev from public.events where id = l.target and status in ('published', 'cancelled');
  if ev.id is null then return null; end if;
  if me is not null then organizer := public.is_organizer(ev.id); end if;
  -- L'auteur du lien et les organisateurs ne comptent pas comme une ouverture.
  if opened and l.opened_at is null and me is distinct from l.created_by and not organizer and l.revoked_at is null then
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
    'organizer', organizer,
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 then greatest(l.max_uses - l.uses, 0) end,
    'inviter', nullif(btrim(coalesce(who, '')), ''),
    'title', ev.title, 'status', ev.status, 'date_mode', ev.date_mode,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', coalesce(ev.location_name, case when arrived or organizer then ev.location_address end),
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'description', left(ev.description, 400),
    'allow_maybe', ev.allow_maybe,
    'closed', (ev.rsvp_deadline is not null and now() > ev.rsvp_deadline)
              or (ev.date_mode = 'poll' and ev.poll_deadline is not null and now() > ev.poll_deadline),
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select nullif(btrim(p.display_name), '') n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and nullif(btrim(p.display_name), '') is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Sondage (10.11) : les personnes qui ont voté au moins une date, comme le sondage de la fiche.
    'voters', (select count(distinct dv.user_id) from public.date_votes dv join public.date_options o on o.id = dv.option_id
               where o.event_id = ev.id),
    'voter_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select nullif(btrim(p.display_name), '') n from public.profiles p
        where exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                      where o.event_id = ev.id and dv.user_id = p.id)
          and nullif(btrim(p.display_name), '') is not null
        order by p.display_name limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    'mine', case when (arrived or organizer) and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived or organizer then ev.id end,
    'location_address', case when arrived or organizer then ev.location_address end,
    'location_url', case when arrived or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''),
    'me_complete', me is not null and private.identity_complete(me));
end $$;

-- 4. Page publique d'un événement : nombre de votants d'un sondage ------------------------------------------------
create or replace function public.public_event(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'price_chf', ev.price_chf, 'allow_maybe', ev.allow_maybe, 'rsvp_deadline', ev.rsvp_deadline,
    'max_participants', ev.max_participants,
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'voters', (select count(distinct dv.user_id) from public.date_votes dv join public.date_options o on o.id = dv.option_id
               where o.event_id = ev.id),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones,
                                       'note', (select n.note from public.rsvp_notes n where n.event_id = ev.id and n.user_id = r.user_id))
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$$;
