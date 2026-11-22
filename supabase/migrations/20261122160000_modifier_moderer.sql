-- Suite des groupes libres (décisions de l'admin du 22.11.2026) :
-- 1. Le CRÉATEUR d'un événement publié le modifie même sans events.edit_own_published (Guest, Basic, Membre…) :
--    - public, Membres Vendredi Party ou « Sur invitation » sans groupe : la modification le remet « en attente » d'une
--      nouvelle validation du site (events.approve), comme une nouvelle proposition. Avec events.publish_direct ou
--      events.edit_own_published : comportement inchangé (reste publié) ;
--    - réservé à ses groupes (private.group_only_event) : le groupe décide. Qui gère le groupe
--      (private.may_approve_announcement) : libre. Simple membre d'un groupe « Événements à valider »
--      (events_need_approval) : le lien event_groups de ce groupe repasse « pending », validé par qui gère le groupe
--      (answer_group_event), comme à la création. Ceci vaut pour tout organisateur de l'événement (pas seulement le
--      créateur) qui ne gère pas le groupe.
--    created_by et approved_by ne changent jamais ; groupe → public repasse déjà en attente (20261122150000).
--    Rien de changé (le formulaire réenregistre la ligne) : ni nouvelle validation ni groupe en attente.
-- 2. Nouveaux droits (Rôles et droits) : events.edit_others « Modifier les événements des autres » et
--    events.remove_others « Retirer / annuler les événements des autres », donnés à Admin et Co-admin seulement (qui ont
--    déjà events.manage_all). Un rôle qui les reçoit (ex. Organisateur, par l'admin) : edit_others → organise
--    l'événement publié / en attente d'un autre (is_organizer, jamais ses brouillons), sans jamais en changer le statut ;
--    remove_others → l'annule (status cancelled, rien d'autre). Sans eux : non (la base refuse).
-- 3. Rôle « Modérateur » (moderator), entre Organisateur et Co-admin : droits de l'Organisateur + modération des
--    signalements (moderation.reports, chat.moderate) + validation des événements (events.approve) + nouveaux comptes
--    (members.approve). Jamais members.ban, members.roles, events.manage_all, edit_others, remove_others. Sous le seuil
--    Co-admin (role_rank('coadmin')) : ni admin du site, ni « tous les groupes », ni admin d'office des groupes.
--    Personne n'est mis Modérateur ici.
-- Purement additive et rejouable.

-- 1. Droits --------------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('events.edit_others', 'Événements', 'Modifier les événements des autres',
   'Modifier un événement publié ou en attente dont on n''est pas l''organisateur, sans changer son statut', 16),
  ('events.remove_others', 'Événements', 'Retirer / annuler les événements des autres',
   'Annuler l''événement d''un autre (ses invités sont prévenus)', 16)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'events_others_2026_11_22') then return; end if;
  insert into public.role_permissions (role, perm) values
    ('admin', 'events.edit_others'), ('admin', 'events.remove_others'),
    ('coadmin', 'events.edit_others'), ('coadmin', 'events.remove_others')
  on conflict do nothing;
  insert into private.one_time_changes (name) values ('events_others_2026_11_22');
end $$;

-- 2. Rôle Modérateur -----------------------------------------------------------------------------------------------
do $$
declare at int;
begin
  if exists (select 1 from public.roles where key = 'moderator') then return; end if;
  at := (select rank from public.roles where key = 'coadmin');
  update public.roles set rank = rank + 1 where rank >= at;  -- contrainte d'unicité différée : décalage en un geste
  insert into public.roles (key, label, color, rank, builtin) values ('moderator', 'Modérateur', '#5856D6', at, true);
  insert into public.role_permissions (role, perm)
    select 'moderator', rp.perm from public.role_permissions rp
    where rp.role = 'organizer'
      and rp.perm not in ('members.ban', 'members.roles', 'events.manage_all', 'events.edit_others', 'events.remove_others')
  on conflict do nothing;
  insert into public.role_permissions (role, perm) values
    ('moderator', 'moderation.reports'), ('moderator', 'chat.moderate'),
    ('moderator', 'events.approve'), ('moderator', 'members.approve')
  on conflict do nothing;
end $$;

-- 3. Organiser l'événement d'un autre (events.edit_others) : fiche, formulaire, sondages, invités… jamais un brouillon.
create or replace function public.is_organizer(e uuid) returns boolean
language sql stable security definer set search_path = 'public' as $$
  select (is_active() or (has_perm('events.create') and private.is_account_active(auth.uid()))) and (
    exists (select 1 from events where id = e and created_by = auth.uid())
    or exists (select 1 from event_organizers where event_id = e and user_id = auth.uid())
  ) or (has_perm('events.edit_others') and private.is_account_active(auth.uid())
        and exists (select 1 from events where id = e and status <> 'draft'));
$$;

-- L'organisation de l'événement au sens propre (créateur, co-organisateurs), sans les droits de l'équipe.
create or replace function private.own_event(e uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and (exists (select 1 from public.events where id = e and created_by = uid)
                               or exists (select 1 from public.event_organizers where event_id = e and user_id = uid));
$$;
revoke all on function private.own_event(uuid, uuid) from public, anon, authenticated;

drop policy if exists "modifier événement" on public.events;
create policy "modifier événement" on public.events for update
  using (is_admin() or is_organizer(id) or (select has_perm('events.remove_others')));

-- 4. Groupe « Événements à valider » : la modification d'un simple membre repasse par le groupe -------------------
create or replace function private.guard_event_group_status() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;  -- service, fonctions internes
  -- Remise en attente après une modification (private.regroup_after_edit, dans guard_event) : décidée par la base.
  if tg_op = 'UPDATE' and coalesce(current_setting('party.group_recheck', true), '') = '1' then return new; end if;
  if tg_op = 'INSERT' then
    new.requested_by := auth.uid();
    new.answered_by := null; new.answered_at := null; new.created_at := now();
    new.status := case when coalesce((select mg.events_need_approval from public.member_groups mg where mg.id = new.group_id), false)
                            and not private.may_approve_announcement(new.group_id, auth.uid())
                       then 'pending' else 'approved' end;
    return new;
  end if;
  if not private.may_approve_announcement(new.group_id, auth.uid()) then
    new.status := old.status; new.answered_by := old.answered_by; new.answered_at := old.answered_at;
  end if;
  new.requested_by := old.requested_by; new.created_at := old.created_at;
  return new;
end $$;

create or replace function private.regroup_after_edit(e uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform set_config('party.group_recheck', '1', true);
  update public.event_groups eg set status = 'pending', answered_by = null, answered_at = null,
         requested_by = auth.uid(), created_at = now()
   where eg.event_id = e and eg.status = 'approved'
     and exists (select 1 from public.member_groups mg where mg.id = eg.group_id and mg.system_key is null and mg.events_need_approval)
     and not private.may_approve_announcement(eg.group_id, auth.uid());
  perform set_config('party.group_recheck', '', true);
end $$;
revoke all on function private.regroup_after_edit(uuid) from public, anon, authenticated;

-- Publication par un groupe ajouté : seulement par l'organisation de l'événement (jamais par edit_others).
create or replace function private.on_event_groups_free_publish() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_organizer(new.event_id) or not private.own_event(new.event_id, auth.uid()) then
    return null;
  end if;
  update public.events e set status = 'published'
    where e.id = new.event_id and e.status = 'pending' and private.group_only_event(e);
  -- Plus rien à valider : la « Nouvelle proposition » envoyée aux valideurs à l'insertion part de leur Activité.
  if found then delete from public.notifications where event_id = new.event_id and kind = 'proposal'; end if;
  return null;
end $$;

-- 5. Garde des événements ------------------------------------------------------------------------------------------
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
        new.status := 'pending';  -- ses groupes arrivent ensuite : zzz_event_groups_free_publish
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
  -- Refus de la validation du site (reject_event) par un Organisateur (events.approve sans events.manage_all, 22.11) :
  -- la raison est gardée ; sans cette ligne, la suite republierait l'événement (Organisateur = publish_direct).
  if old.status = 'pending' and new.status = 'rejected' and has_perm('events.approve') then
    new.approved_by := old.approved_by; new.approved_at := old.approved_at;
    return new;
  end if;

  new.approved_by := old.approved_by; new.approved_at := old.approved_at;
  new.rejection_reason := old.rejection_reason;
  -- Discussion (17.11) : seuls « Qui peut écrire » et la description de la discussion changent → l'organisation.
  if (to_jsonb(new) - 'chat_write' - 'chat_description' - 'updated_at') = (to_jsonb(old) - 'chat_write' - 'chat_description' - 'updated_at')
     and private.event_chat_staff(new.id) then return new; end if;

  -- L'événement d'un AUTRE (22.11) : validation du site, events.remove_others (annuler), events.edit_others (modifier
  -- sans changer le statut). Rien d'autre.
  if not private.own_event(new.id, auth.uid()) then
    if old.status in ('pending', 'rejected', 'draft') and new.status = 'published' and has_perm('events.approve')
       and (to_jsonb(new) - 'status' - 'updated_at') = (to_jsonb(old) - 'status' - 'updated_at') then
      new.approved_by := auth.uid(); new.approved_at := now(); new.rejection_reason := null;  -- approve_event
      return new;
    end if;
    if new.status = 'cancelled' and old.status <> 'cancelled' and has_perm('events.remove_others') then
      if not has_perm('events.edit_others')
         and (to_jsonb(new) - 'status' - 'updated_at') <> (to_jsonb(old) - 'status' - 'updated_at') then
        raise exception 'forbidden: Retirer l’événement d’un autre ne change que son statut.' using errcode = '42501';
      end if;
      return new;
    end if;
    if not has_perm('events.edit_others') or old.status = 'draft' then
      raise exception 'forbidden: Seuls ses organisateurs (et l’équipe de Vendredi Party) peuvent modifier cet événement.' using errcode = '42501';
    end if;
    if new.status is distinct from old.status then
      raise exception 'forbidden: Modifier l’événement d’un autre ne change pas son statut.' using errcode = '42501';
    end if;
    return new;
  end if;

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
    if (to_jsonb(new) - 'guest_group' - 'updated_at') = (to_jsonb(old) - 'guest_group' - 'updated_at')
       and public.is_organizer(new.id) then return new; end if;
    -- Billets QR (04.11) : seule l'option change → organisateurs et co-organisateurs, même publié.
    if (to_jsonb(new) - 'tickets_enabled' - 'updated_at') = (to_jsonb(old) - 'tickets_enabled' - 'updated_at')
       and private.can_manage_tickets_option(new.id) then return new; end if;
    -- Rien de changé (le formulaire réenregistre la ligne) : il reste publié, sans nouvelle validation.
    if (to_jsonb(new) - 'status' - 'updated_at') = (to_jsonb(old) - 'status' - 'updated_at') then
      new.status := 'published'; return new;
    end if;
    -- 22.11 : le créateur modifie toujours son événement ; un co-organisateur, avec events.edit_own_published.
    if not has_perm('events.edit_own_published') and old.created_by is distinct from auth.uid() then
      raise exception 'Seul un admin peut modifier un événement publié';
    end if;
    if not privileged and s.require_approval
       and old.visibility = 'invited' and not coalesce(old.public_link, false)
       and (new.visibility = 'all' or coalesce(new.public_link, false)) then
      -- Groupes libres (22.11) : sur invitation / groupe → public ou Membres Vendredi Party = validation du site.
      new.status := 'pending'; new.rejection_reason := null;
    elsif private.group_only_event(new) then
      -- Réservé à ses groupes : le groupe décide (simple membre d'un groupe « Événements à valider » : en attente).
      new.status := 'published';
      perform private.regroup_after_edit(new.id);
    elsif not privileged and not has_perm('events.edit_own_published') and s.require_approval then
      -- Créateur sans droit de modifier un publié : nouvelle validation du site, comme une nouvelle proposition.
      new.status := 'pending'; new.rejection_reason := null;
    else
      new.status := 'published';
    end if;
  elsif new.status = 'draft' then
    null;
  elsif privileged or not s.require_approval or private.group_only_event(new) then
    new.status := 'published'; new.approved_by := auth.uid(); new.approved_at := now();
  else
    new.status := 'pending'; new.rejection_reason := null;
  end if;
  return new;
end $$;
