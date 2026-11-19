-- Retour arrière : texte de accept_invite en prod avant la migration (19.11).
begin;
CREATE OR REPLACE FUNCTION public.accept_invite(token uuid, answer text, first_name text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); arrived boolean; who text; inviter text; u uuid;
        req public.event_join_requests; sees boolean;
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

  sees := public.can_see_event(ev.id);
  select * into req from public.event_join_requests q where q.event_id = ev.id and q.user_id = me;
  if not sees and req.status in ('pending', 'refused') and not private.needs_approval(ev, l.created_by) then
    -- Lien de l'organisateur ou d'un co-organisateur : il vaut accord, même après un refus (refus par erreur, 12.11).
    update public.event_join_requests q set status = 'accepted', decided_at = now(), decided_by = l.created_by
      where q.event_id = ev.id and q.user_id = me;
  elsif not sees and req.status = 'pending' then
    -- Demande déjà envoyée (par le lien d'un invité) : on garde la réponse la plus récente, on attend l'organisateur.
    update public.event_join_requests q set answer = accept_invite.answer where q.event_id = ev.id and q.user_id = me;
    return private.join_request_answer(ev, answer);
  elsif not sees and req.status = 'refused' then
    raise exception 'refused: l''organisateur n''a pas accepté ta venue à cet événement' using errcode = '42501';
  end if;

  -- coalesce : l.used_by vaut NULL tant que le lien n'a pas servi ; « not NULL » sauterait l'arrivée plus bas.
  arrived := coalesce(l.used_by = me, false) or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
  if arrived then
    -- Déjà venu par ce lien : changer sa réponse, sauf si l'organisateur l'a retiré de la liste.
    if not sees then
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
    select display_name into who from public.profiles where id = me;

    -- 12.11 : lien d'un invité sur un événement sans lien public → l'organisateur accepte d'abord. La place du lien est
    -- prise (comme une réponse) ; la personne ne voit l'événement qu'une fois acceptée.
    if not sees and private.needs_approval(ev, l.created_by) then
      insert into public.event_join_requests (event_id, user_id, token, invited_by, answer)
        values (ev.id, me, l.token, l.created_by, answer)
      on conflict (event_id, user_id) do update set token = excluded.token, invited_by = excluded.invited_by,
        answer = excluded.answer, status = 'pending', created_at = now(), decided_at = null, decided_by = null;
      select display_name into inviter from public.profiles where id = l.created_by;
      for u in select x from (select ev.created_by x union select user_id from public.event_organizers where event_id = ev.id) o loop
        perform public.queue_notification(u, 'join_request', ev.id, ev.title,
          coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' aimerait venir (invité par '
            || coalesce(nullif(btrim(inviter), ''), 'un invité') || ') : accepte ou refuse dans la liste des invités.',
          'join_request:' || ev.id || ':' || me);
      end loop;
      return private.join_request_answer(ev, answer);
    end if;

    -- Invité de CET événement seulement (jamais ajouté à un groupe). Un membre du groupe qui le voit déjà n'a pas de
    -- ligne ; une personne hors du groupe en a TOUJOURS une, même sur un événement public (10.11 : sinon l'organisateur
    -- ne savait pas d'où elle venait, et la purge la prenait avec ses votes).
    if not sees or not private.is_member(me)
       or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me) then
      insert into public.event_invites (event_id, user_id, via_group, via_link, invited_by, link_token)
        values (ev.id, me, false, true, l.created_by, l.token)
      on conflict (event_id, user_id) do update set via_link = true,
        invited_by = coalesce(public.event_invites.invited_by, excluded.invited_by),
        link_token = coalesce(public.event_invites.link_token, excluded.link_token);
    end if;
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
end $function$;
delete from supabase_migrations.schema_migrations where version = '20261119190000';
commit;
