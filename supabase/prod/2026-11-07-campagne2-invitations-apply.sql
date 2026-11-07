-- PROD, campagne2_invitations (20261107100000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration,
-- et APRÈS 2026-11-06-campagne-bots, 2026-11-06-ia-personnes-citees et 2026-11-06-annonces-groupe (fonctions et table
-- event_announcements qu'elle remplace / utilise). Retour arrière : 2026-11-07-campagne2-invitations-rollback.sql. Tout ou rien.
begin;
-- Campagne 2 des bots (07.11.2026) : corrections de la base « invitations, groupes, cycle de vie ».
-- Purement additive et rejouable. Tests : tests/supabase_live/test_campagne2_invitations_live.py.
--
-- 1. Blocage (rapports 01, 02, 03, 05, 06, 07) : une personne en blocage avec l'organisateur (dans un sens ou dans l'autre)
--    faisait échouer TOUTE l'invitation d'un groupe (sync_event_group_invites → guard_invite_block) et laissait un brouillon.
--    Désormais la copie « via le groupe » saute en silence les membres en blocage avec le créateur de l'événement ou avec la
--    personne qui agit (création, Inviter, validation par l'admin du groupe, ajout d'un membre au groupe) ; l'annonce au
--    groupe ne les prévient pas ; invite_people saute aussi une personne en blocage (sans dire qui) ; une invitation
--    directe une à une garde le refus, en français propre. Un lien « pour plusieurs » ne fait pas entrer une personne en
--    blocage avec l'organisateur ou l'auteur du lien.
-- 2. « Prévenir le groupe » depuis la feuille Inviter : par groupe (event_groups.announce), plus pour tout l'événement ;
--    invite_people(e, people, groups, announce) ; les groupes déjà présents sans annonce ne sont pas prévenus.
-- 3. Couper / rallumer « Prévenir le groupe » : une seule demande « Annonce à valider » par événement + groupe
--    (clé de dédoublonnage par événement et groupe, plus par demande) ; seule une vraie coupure retire la demande.
-- 4. « Rouvrir l'événement » (annulé → publié) : « Événement rétabli » à ceux qui avaient reçu « Événement annulé »
--    (interrupteur event_changed), jamais « Proposition validée ».
-- 5. L'organisateur / co-organisateur qui ouvre ou utilise son propre lien ne le consomme pas (ni ouverture, ni place).
-- 6. Co-organisateur sans droit de modifier (events.edit_own_published) : ne peut plus annuler (le créateur, si) ;
--    co-organisateur ajouté → « Co-organisateur » (interrupteur « invites ») ; invités sans réponse prévenus d'une
--    annulation (pas d'une modification) ; « Événement annulé » reste dans l'Activité quand l'événement est supprimé
--    (texte autonome, plus de lien vers l'événement).

-- ---------------------------------------------------------------------------------------------------------------------
-- 1. Blocage
-- ---------------------------------------------------------------------------------------------------------------------
create or replace function private.guard_invite_block() returns trigger
language plpgsql security definer set search_path = '' as $$
declare inviter uuid := auth.uid(); creator uuid;
begin
  if tg_table_name = 'group_invitations' then inviter := coalesce(inviter, new.invited_by); end if;
  if new.user_id is null then return new; end if;
  -- (new.via_group n'existe que dans event_invites : lu seulement pour cette table, group_invitations aussi passe ici.)
  if tg_table_name = 'event_invites' then
    if coalesce((to_jsonb(new)->>'via_group')::boolean, false) then
      -- Copie d'un groupe : la personne en blocage est sautée, sans faire échouer le reste ni dire qui.
      select ev.created_by into creator from public.events ev where ev.id = (to_jsonb(new)->>'event_id')::uuid;
      if private.blocked_either(creator, new.user_id) or private.blocked_either(inviter, new.user_id) then return null; end if;
      return new;
    end if;
  end if;
  if private.blocked_either(inviter, new.user_id) then
    raise exception 'blocked: Tu ne peux pas inviter cette personne.' using errcode = '42501';
  end if;
  return new;
end $$;

create or replace function private.send_announcement(a uuid) returns void
language plpgsql security definer set search_path = '' as $$
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
    continue when private.blocked_either(ev.created_by, u);
    if private.should_invite(ev, u) then perform private.queue_private_invite(ev, u); end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- 2. « Prévenir le groupe » par groupe (feuille Inviter)
-- ---------------------------------------------------------------------------------------------------------------------
alter table public.event_groups add column if not exists announce boolean not null default false;
comment on column public.event_groups.announce is
  '« Prévenir le groupe » demandé pour CE groupe (feuille Inviter) ; events.announce_group vaut pour tous les groupes.';

drop function if exists public.invite_people(uuid, uuid[], uuid[]);
create or replace function public.invite_people(e uuid, people uuid[] default '{}', groups uuid[] default '{}',
                                                announce boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
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
    -- En blocage avec l'organisateur ou avec qui invite : sautée, sans le dire (le reste de l'invitation passe).
    if private.blocked_either(auth.uid(), u) or private.blocked_either(ev.created_by, u) then continue; end if;
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
    insert into public.event_groups (event_id, group_id, announce) values (e, g, coalesce(announce, false)) on conflict do nothing;
    get diagnostics n = row_count;
    grp := grp + n;
    if n = 0 and announce then
      update public.event_groups x set announce = true where x.event_id = e and x.group_id = g and not x.announce;
    end if;
  end loop;
  if announce and coalesce(array_length(groups, 1), 0) > 0 then perform private.open_announcements(e); end if;
  return jsonb_build_object('people', added, 'groups', grp);
end $$;
grant execute on function public.invite_people(uuid, uuid[], uuid[], boolean) to authenticated;

create or replace function private.open_announcements(e uuid) returns void
language plpgsql security definer set search_path = '' as $$
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

  -- « Prévenir le groupe » : pour tous les groupes (events.announce_group) ou pour ce groupe seulement (event_groups.announce).
  for g in select eg.group_id from public.event_groups eg
           where eg.event_id = e and eg.status = 'approved' and (ev.announce_group or eg.announce)
           union select private.vip_group_id() where ev.visibility = 'all' and ev.announce_group loop
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
      -- Une seule demande par événement + groupe : couper puis rallumer ne redemande pas (dédoublonnage).
      perform private.tell_validators(g, ev.created_by, 'announce_request', 'Annonce à valider',
        who || ' veut prévenir le groupe ' || private.group_label(g) || ' de « ' || ev.title
        || ' ». Sans réponse sous 48 h, l’annonce part d’office.', 'announce_request:' || e || ':' || g, e);
    end if;
  end loop;
end $$;

create or replace function private.on_event_announce() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Événement devenu public : toutes les demandes en attente tombent. « Prévenir le groupe » coupé (vraie coupure) :
  -- tombent celles qui ne venaient que de lui (pas celles demandées pour un groupe dans la feuille Inviter).
  if tg_op = 'UPDATE' and new.public_link and not old.public_link then
    delete from public.event_announcements where event_id = new.id and status = 'pending';
  elsif tg_op = 'UPDATE' and old.announce_group and not new.announce_group then
    delete from public.event_announcements x where x.event_id = new.id and x.status = 'pending'
      and not exists (select 1 from public.event_groups eg where eg.event_id = x.event_id and eg.group_id = x.group_id and eg.announce);
  end if;
  perform private.open_announcements(new.id);
  return null;
end $$;

create or replace function public.answer_group_event(e uuid, g uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
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
  -- Une seule décision (06.11, Q3) : accepter l'événement envoie aussi l'annonce demandée (« Prévenir le groupe », pour
  -- tous les groupes ou pour ce groupe), acceptée par ce valideur ; refuser l'événement : rien n'est envoyé.
  if accept and (ev.announce_group or r.announce) and ev.status = 'published' and not ev.public_link then
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
end $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- 1 et 5. Liens d'invitation : personne en blocage refusée ; l'organisateur ne consomme pas son propre lien
-- ---------------------------------------------------------------------------------------------------------------------
create or replace function public.accept_invite(token uuid, answer text, first_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
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

  -- L'organisateur (ou un co-organisateur) qui essaie son propre lien : sa réponse compte, le lien reste intact.
  if public.is_organizer(ev.id) then
    insert into public.rsvps (event_id, user_id, status) values (ev.id, me, answer::public.rsvp_status)
    on conflict (event_id, user_id) do update set status = excluded.status;
    return jsonb_build_object('event_id', ev.id, 'status', answer, 'title', ev.title, 'organizer', true,
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

  insert into public.rsvps (event_id, user_id, status) values (ev.id, me, answer::public.rsvp_status)
  on conflict (event_id, user_id) do update set status = excluded.status;

  return jsonb_build_object('event_id', ev.id, 'status', answer, 'title', ev.title,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day, 'date_mode', ev.date_mode,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'description', ev.description,
    'waitlisted', (select r.waitlisted from public.rsvps r where r.event_id = ev.id and r.user_id = me));
end $$;

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
    'closed', ev.rsvp_deadline is not null and now() > ev.rsvp_deadline,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select private.first_word(p.display_name) n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and private.first_word(p.display_name) is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Ce que voit la personne qui a déjà répondu par ce lien, ou un organisateur (changer sa réponse, adresse, itinéraire).
    'mine', case when (arrived or organizer) and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived or organizer then ev.id end,
    'location_address', case when arrived or organizer then ev.location_address end,
    'location_url', case when arrived or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''));
end $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- 6. Annuler = même droit que modifier pour un co-organisateur (le créateur annule toujours le sien)
-- ---------------------------------------------------------------------------------------------------------------------
create or replace function public.guard_event() returns trigger
language plpgsql security definer set search_path = 'public' as $$
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
    if new.status = 'cancelled' then
      -- 07.11 : annuler demande le même droit que modifier (co-organisateur « Membre » : non) ; le créateur, toujours.
      if old.created_by = auth.uid() or has_perm('events.edit_own_published') then return new; end if;
      raise exception 'forbidden: Seuls les organisateurs qui peuvent modifier l’événement peuvent l’annuler.' using errcode = '42501';
    end if;
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
end $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- 4 et 6. Notifications du cycle de vie
-- ---------------------------------------------------------------------------------------------------------------------
-- Qui apprend une annulation : les participants (event_audience) + les invités qui n'ont pas répondu et qui savaient
-- qu'ils étaient invités (invités un à un, par un lien, ou prévenus par l'annonce du groupe).
create or replace function private.event_cancel_audience(e uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select a from public.event_audience(e) a
  union
  select i.user_id from public.event_invites i
  where i.event_id = e
    and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id)
    and not exists (select 1 from public.event_mutes m where m.event_id = e and m.user_id = i.user_id)
    and (not i.via_group or i.via_link
         or exists (select 1 from public.notifications n where n.user_id = i.user_id and n.event_id = e and n.kind = 'private_invite'));
$$;
revoke all on function private.event_cancel_audience(uuid) from public, anon, authenticated;

create or replace function public.notify_event_change() returns trigger
language plpgsql security definer set search_path = 'public' as $$
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

  -- Rouvert par un admin (annulé → publié) : « Événement rétabli » à ceux qui avaient appris l'annulation,
  -- jamais « Proposition validée ».
  if tg_op = 'UPDATE' and old.status = 'cancelled' and new.status = 'published' then
    for u in select distinct n.user_id from notifications n join notification_prefs np on np.user_id = n.user_id
             where n.event_id = new.id and n.kind = 'event_changed' and n.title = 'Événement annulé' and np.event_changed
               and n.user_id not in (select m.user_id from event_mutes m where m.event_id = new.id) loop
      perform queue_notification(u, 'event_changed', new.id, 'Événement rétabli',
        '« ' || new.title || ' » n’est plus annulé : il a bien lieu.');
    end loop;
    return null;
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
      for u in select a from private.event_cancel_audience(new.id) a join notification_prefs np on np.user_id = a where np.event_changed loop
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

-- « Événement annulé » reste dans l'Activité quand l'événement est supprimé : texte autonome, plus de lien.
create or replace function private.keep_cancel_notices() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.notifications n set event_id = null, data = (n.data - 'event_id') || jsonb_build_object('event_deleted', true)
    where n.event_id = old.id and n.kind = 'event_changed' and n.title = 'Événement annulé';
  return old;
end $$;
drop trigger if exists events_keep_cancel_notices on public.events;
create trigger events_keep_cancel_notices before delete on public.events
  for each row execute function private.keep_cancel_notices();

-- Co-organisateur ajouté : prévenu (interrupteur « Invitation à un événement », notification_prefs.invites).
create or replace function private.on_event_organizer_added() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  select * into ev from public.events where id = new.event_id;
  if ev.id is null or new.user_id = ev.created_by or not private.is_account_active(new.user_id)
     or not exists (select 1 from public.notification_prefs np where np.user_id = new.user_id and np.invites is not false) then
    return null;
  end if;
  perform public.queue_notification(new.user_id, 'coorganizer_added', ev.id, 'Co-organisateur',
    coalesce(nullif(btrim(private.person_label(auth.uid())), ''), 'On') || ' t’a ajouté comme co-organisateur de « ' || ev.title || ' ».',
    'coorganizer_added:' || ev.id);
  return null;
end $$;
drop trigger if exists event_organizers_notify on public.event_organizers;
create trigger event_organizers_notify after insert on public.event_organizers
  for each row execute function private.on_event_organizer_added();

create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('pet_daily', 'pet_alert', 'pet_gift', 'pet_streak', 'pet_bar') and private.is_account_active(uid))
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message', 'moderation_notice', 'report_new',
                 'private_invite', 'announce_request', 'announce_accepted', 'announce_refused', 'group_event_request', 'group_event_accepted', 'group_event_refused', 'event_changed', 'date_fixed', 'reminder', 'waitlist',
                 'coorganizer_added')
        and private.is_account_active(uid));
$$;

create or replace function private.web_push_allowed(notification public.notifications) returns boolean
language plpgsql stable security definer set search_path = '' as $$
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
    when 'coorganizer_added' then coalesce(prefs.invites, true)
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
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261107100000', 'campagne2_invitations')
 on conflict do nothing;
commit;

notify pgrst, 'reload schema';
