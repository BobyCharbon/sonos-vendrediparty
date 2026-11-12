-- Accord de l'organisateur (décision de l'admin, 12.11.2026, suite de l'avis 83ebee37aa0f) : sur un événement « sur
-- invitation », de groupe ou réservé aux Membres Vendredi Party (tout ce qui n'a pas de lien public), une personne qui
-- arrive par le lien d'un INVITÉ ne voit l'événement qu'une fois acceptée par l'organisateur (ou un co-organisateur).
-- Seuls l'organisateur et les co-organisateurs ajoutent quelqu'un directement (liste, groupe, ou leurs propres liens).
-- Événement public : rien ne change (le lien public circule déjà librement). Purement additif et rejouable.

-- 1. Les demandes --------------------------------------------------------------------------------------------------
create table if not exists public.event_join_requests (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  token uuid,
  invited_by uuid references public.profiles (id) on delete set null,
  answer text not null default 'yes' check (answer in ('yes', 'maybe', 'no', 'poll')),
  status text not null default 'pending' check (status in ('pending', 'accepted', 'refused')),
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  decided_by uuid references public.profiles (id) on delete set null,
  primary key (event_id, user_id)
);
alter table public.event_join_requests enable row level security;
revoke all on public.event_join_requests from anon, authenticated;
create index if not exists event_join_requests_pending on public.event_join_requests (event_id) where status = 'pending';

-- 2. Un lien demande l'accord : événement sans lien public, et lien créé par quelqu'un qui n'organise pas.
create or replace function private.needs_approval(ev public.events, creator uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select not coalesce(ev.public_link, false)
     and creator is distinct from ev.created_by
     and not exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = creator)
     and not (creator is not null and private.user_has(creator, 'events.manage_all'));
$$;
revoke all on function private.needs_approval(public.events, uuid) from public, anon, authenticated;

-- Réponse « en attente » : ce que la carte d'invitation montrait déjà, jamais l'adresse ni la fiche.
create or replace function private.join_request_answer(ev public.events, answer text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('pending', true, 'event_id', null, 'status', nullif(answer, 'poll'), 'title', ev.title,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day, 'date_mode', ev.date_mode,
    'location_name', ev.location_name, 'location_address', null, 'location_url', null,
    'description', left(ev.description, 400), 'waitlisted', null,
    'host', (select nullif(btrim(p.display_name), '') from public.profiles p where p.id = ev.created_by));
$$;
revoke all on function private.join_request_answer(public.events, text) from public, anon, authenticated;

-- « pending » / « refused » tant que la personne ne voit pas l'événement ; null sinon.
create or replace function private.join_request_state(e uuid, u uuid) returns text
language sql stable security definer set search_path = '' as $$
  select q.status from public.event_join_requests q
  where q.event_id = e and q.user_id = u and q.status in ('pending', 'refused')
    and not exists (select 1 from public.event_invites i where i.event_id = e and i.user_id = u);
$$;
revoke all on function private.join_request_state(uuid, uuid) from public, anon, authenticated;

-- 3. Répondre par un lien (corps de 20261110090000 + la demande d'accord) ------------------------------------------
create or replace function public.accept_invite(token uuid, answer text, first_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
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
end $$;

-- 4. Carte d'invitation (corps de 20261110100200) : « l'organisateur accepte chaque personne », « en attente », « refusé ».
create or replace function public.invite_preview(token uuid, opened boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text; organizer boolean := false; already boolean := false; removed boolean := false;
        req public.event_join_requests; sees boolean := false; waiting boolean := false; refused boolean := false;
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
    sees := public.can_see_event(ev.id);
    select * into req from public.event_join_requests q where q.event_id = ev.id and q.user_id = me;
    -- Le lien de l'organisateur ou d'un co-organisateur vaut accord : ni « en attente » ni « refusé » dessus.
    waiting := not sees and not organizer and coalesce(req.status = 'pending', false) and private.needs_approval(ev, l.created_by);
    refused := not sees and not organizer and coalesce(req.status = 'refused', false) and private.needs_approval(ev, l.created_by);
    arrived := coalesce(l.used_by = me, false)
      or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
    select * into mine from public.rsvps r where r.event_id = ev.id and r.user_id = me;
    -- Retiré de la liste par l'organisateur (venu par ce lien, ne voit plus l'événement) : on le dit d'emblée.
    removed := arrived and not organizer and not sees and not waiting and not refused;
    -- Déjà invité autrement (liste, groupe, autre lien) ou déjà répondu : la carte mène à l'événement.
    already := not arrived and not organizer and (mine.event_id is not null
      or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me));
  end if;
  state := private.invite_link_state(l);
  select display_name into who from public.profiles where id = coalesce(l.created_by, ev.created_by);
  return jsonb_build_object(
    'state', case when waiting then 'waiting' when refused then 'refused' when removed then 'removed'
                  when arrived and state <> 'revoked' then 'mine' else state end,
    'already', already,
    'organizer', organizer,
    -- L'organisateur accepte chaque personne arrivée par ce lien (lien d'un invité, événement sans lien public).
    'approval', not organizer and not sees and private.needs_approval(ev, l.created_by),
    'host', (select nullif(btrim(p.display_name), '') from public.profiles p where p.id = ev.created_by),
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 and state in ('pending', 'opened') then greatest(l.max_uses - l.uses, 0) end,
    'multi', l.max_uses > 1,
    'inviter', nullif(btrim(coalesce(who, '')), ''),
    'title', ev.title, 'status', ev.status, 'date_mode', ev.date_mode,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', coalesce(ev.location_name, case when (arrived and sees) or organizer then ev.location_address end),
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
    'mine', case when (arrived or organizer or already) and not removed and not waiting and not refused
                      and mine.event_id is not null then mine.status::text end,
    'event_id', case when (arrived and sees) or organizer or already then ev.id end,
    'location_address', case when (arrived and sees) or organizer then ev.location_address end,
    'location_url', case when (arrived and sees) or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''),
    'me_complete', me is not null and private.identity_complete(me));
end $$;

-- 5. Liste des invités (corps de 20261111120000) : les demandes à accepter, et l'état de chaque arrivée d'un lien.
create or replace function private.event_guest_list_full(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events; vip boolean; vip_name text;
begin
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
    -- 12.11 : personnes arrivées par le lien d'un invité, qui attendent l'accord de l'organisateur.
    'requests', coalesce((select jsonb_agg(jsonb_build_object(
        'id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url, 'answer', q.answer, 'created_at', q.created_at,
        'invited_by', (select display_name from public.profiles where id = q.invited_by), 'invited_by_id', q.invited_by,
        'link_label', (select il.label from private.invite_links il where il.token = q.token)) order by q.created_at)
      from public.event_join_requests q join public.profiles p on p.id = q.user_id
      where q.event_id = e and q.status = 'pending' and p.status = 'active'
        and not exists (select 1 from public.event_invites i where i.event_id = e and i.user_id = q.user_id)), '[]'::jsonb),
    'links', coalesce((select jsonb_agg(x order by x->>'created_at' desc) from (
      select jsonb_build_object(
        'token', l.token, 'label', l.label, 'max_uses', l.max_uses, 'uses', l.uses, 'created_at', l.created_at,
        'expires_at', l.expires_at, 'opened_at', l.opened_at, 'state', private.invite_link_state(l), 'version', l.version,
        'created_by', (select display_name from public.profiles where id = l.created_by), 'created_by_id', l.created_by,
        'nudged_today', private.nudged_today(e, null, l.token) is not null,
        'arrivals', coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id),
            'request', private.join_request_state(e, p.id)) order by a.at)
          from private.invite_link_arrivals a join public.profiles p on p.id = a.user_id where a.token = l.token),
          case when l.used_by is not null then (select jsonb_build_array(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id),
            'request', private.join_request_state(e, p.id)))
            from public.profiles p where p.id = l.used_by) else '[]'::jsonb end)) x
      from private.invite_links l
      where l.kind = 'event' and l.target = e and (l.revoked_at is null or l.uses > 0 or l.used_by is not null)
      order by l.created_at desc limit 60) s), '[]'::jsonb));
end $$;
revoke all on function private.event_guest_list_full(uuid) from public, anon, authenticated;

create or replace function public.event_guest_list(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare whole jsonb; me uuid := auth.uid(); poll boolean; people jsonb; links jsonb; waiting jsonb;
begin
  if private.manages_event(e) then return private.event_guest_list_full(e); end if;
  if me is null or not public.can_see_event(e)
     or not exists (select 1 from public.events x where x.id = e and x.status = 'published') then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  whole := private.event_guest_list_full(e);
  poll := coalesce((whole->>'poll')::boolean, false);
  people := whole->'people';
  links := whole->'links';
  -- Mêmes comptes que la carte de l'organisateur (lib/invites.ts guestCounts) : un lien « une personne » encore sans
  -- réponse compte comme une personne (ouvert → pas répondu, sinon lien pas ouvert).
  select coalesce(jsonb_agg(l), '[]') into waiting from jsonb_array_elements(links) l
    where (l->>'max_uses')::int = 1 and l->>'state' in ('pending', 'opened') and jsonb_array_length(l->'arrivals') = 0;
  return jsonb_build_object(
    'guest', true, 'poll', poll, 'vip', whole->'vip', 'public', whole->'public', 'vip_name', whole->'vip_name',
    'groups', whole->'groups', 'people', '[]'::jsonb, 'requests', '[]'::jsonb,
    'counts', jsonb_build_object(
      'yes', (select count(*) from jsonb_array_elements(people) p
              where case when poll then (p->>'voted')::boolean else p->>'status' = 'yes' end),
      'maybe', case when poll then 0 else (select count(*) from jsonb_array_elements(people) p where p->>'status' = 'maybe') end,
      'no', case when poll then 0 else (select count(*) from jsonb_array_elements(people) p where p->>'status' = 'no') end,
      'none', (select count(*) from jsonb_array_elements(people) p
               where case when poll then not (p->>'voted')::boolean else p->>'status' is null end)
              + (select count(*) from jsonb_array_elements(waiting) l where l->>'state' = 'opened'),
      'unopened', (select count(*) from jsonb_array_elements(waiting) l where l->>'state' = 'pending'),
      'total', jsonb_array_length(people) + jsonb_array_length(waiting)),
    -- Ses liens à lui : nombre de réponses (et demandes en attente d'accord), jamais les noms de ceux qui sont venus.
    'links', coalesce((select jsonb_agg(l || jsonb_build_object('nudged_today', false, 'arrivals',
        coalesce((select jsonb_agg(jsonb_build_object('id', null, 'name', null, 'status', a->'status', 'request', a->'request'))
                  from jsonb_array_elements(l->'arrivals') a), '[]'::jsonb)))
      from jsonb_array_elements(links) l where l->>'created_by_id' = me::text), '[]'::jsonb));
end $$;
revoke all on function public.event_guest_list(uuid) from public, anon;
grant execute on function public.event_guest_list(uuid) to authenticated;

-- 6. L'organisateur accepte ou refuse ------------------------------------------------------------------------------
create or replace function public.decide_join_request(e uuid, person uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare req public.event_join_requests; ev public.events; host text;
begin
  if not private.manages_event(e) then raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501'; end if;
  select * into req from public.event_join_requests q where q.event_id = e and q.user_id = person for update;
  if req.event_id is null or req.status <> 'pending' then raise exception 'Cette demande a déjà été traitée.'; end if;
  select * into ev from public.events where id = e;
  update public.event_join_requests q set status = case when accept then 'accepted' else 'refused' end,
      decided_at = now(), decided_by = auth.uid()
    where q.event_id = e and q.user_id = person;
  select nullif(btrim(display_name), '') into host from public.profiles where id = auth.uid();
  if accept then
    -- Le message d'accord d'abord : la notification d'invitation de la base (même clé) ne part pas en double.
    perform public.queue_notification(person, 'private_invite', e, '✅ C’est bon pour « ' || ev.title || ' »',
      coalesce(host, 'L’organisateur') || ' a accepté ta venue.', 'private_invite:' || e);
    insert into public.event_invites (event_id, user_id, via_group, via_link, invited_by, link_token)
      values (e, person, false, true, req.invited_by, req.token)
    on conflict (event_id, user_id) do update set via_link = true,
      invited_by = coalesce(public.event_invites.invited_by, excluded.invited_by),
      link_token = coalesce(public.event_invites.link_token, excluded.link_token);
    if req.answer <> 'poll' and ev.date_mode <> 'poll' then
      insert into public.rsvps (event_id, user_id, status) values (e, person, req.answer::public.rsvp_status)
      on conflict (event_id, user_id) do nothing;
    end if;
  else
    perform public.queue_notification(person, 'private_invite', e, ev.title,
      'L’organisateur n’a pas pu accepter ta venue cette fois.', 'join_refused:' || e);
  end if;
  return public.event_guest_list(e);
end $$;
revoke all on function public.decide_join_request(uuid, uuid, boolean) from public, anon;
grant execute on function public.decide_join_request(uuid, uuid, boolean) to authenticated;

-- 7. « À valider » (onglet Activité) : les demandes de tous MES événements (organisateur ou co-organisateur), pour les
-- voir tout de suite sans ouvrir chaque fiche.
create or replace function public.my_join_requests() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object(
      'event_id', ev.id, 'title', ev.title, 'starts_at', ev.starts_at, 'date_mode', ev.date_mode,
      'id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url, 'answer', q.answer, 'created_at', q.created_at,
      'invited_by', (select display_name from public.profiles where id = q.invited_by), 'invited_by_id', q.invited_by,
      'link_label', (select il.label from private.invite_links il where il.token = q.token)) order by q.created_at), '[]'::jsonb)
  from public.event_join_requests q
  join public.events ev on ev.id = q.event_id
  join public.profiles p on p.id = q.user_id
  where q.status = 'pending' and p.status = 'active' and ev.status = 'published'
    and (ev.created_by = auth.uid() or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = auth.uid()))
    and not exists (select 1 from public.event_invites i where i.event_id = q.event_id and i.user_id = q.user_id);
$$;
revoke all on function public.my_join_requests() from public, anon;
grant execute on function public.my_join_requests() to authenticated;

-- 8. Notification « join_request » (12.11) : importante (bulle rouge de la cloche) pour être vue tout de suite ; même
-- interrupteur que « Quelqu'un rejoint ou demande à venir par un lien » (notification_prefs.link_join), tous canaux.
do $$ declare def text; anchor text := $a$    when 'link_join' then prefs.link_join$a$;
begin
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''join_request''' in def) = 0 then
    if position(anchor in def) = 0 then raise exception 'web_push_allowed : ancre link_join introuvable'; end if;
    def := replace(def, anchor, anchor || $a$
    when 'join_request' then coalesce(prefs.link_join, true)$a$);
    execute def;
  end if;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''join_request''' in def) = 0 then
    if position('''link_join'',' in def) = 0 then raise exception 'may_receive_push : ancre link_join introuvable'; end if;
    def := replace(def, '''link_join'',', '''link_join'', ''join_request'',');
    execute def;
  end if;
end $$;
