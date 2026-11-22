-- « Chacun est libre de faire ce qu'il veut avec son groupe » (décision de l'admin du 22.11.2026).
-- 1. Un événement réservé UNIQUEMENT à des groupes ordinaires (visibility 'invited', sans lien public, au moins un groupe
--    non système en attente ou accepté) ne passe JAMAIS par la validation du site (group_settings.require_approval) :
--    publié directement. Dans le groupe, la règle du groupe décide seule (member_groups.events_need_approval →
--    event_groups.status 'pending', validé par qui gère le groupe : guard_event_group_status, inchangé).
--    Public, Membres Vendredi Party (visibility 'all') et « Sur invitation » sans groupe : inchangés.
--    Le statut se décide à l'INSERT de l'événement, avant ses groupes : le formulaire et l'étape 2 passent par un brouillon
--    puis un UPDATE du statut (guard_event voit alors les groupes) ; une insertion directe en « pending » est publiée par
--    le déclencheur zzz_event_groups_free_publish dès qu'un groupe ordinaire est ajouté par son organisateur.
--    Pas de faille : un événement publié qui s'ÉLARGIT (sur invitation / groupe → public ou Membres Vendredi Party) par
--    quelqu'un sans events.publish_direct repasse « pending » (validation du site). Modifier un événement publié demande
--    toujours events.edit_own_published (droit réglable dans Rôles et droits, inchangé).
--    Celui qui a events.create organise ce qu'il a créé (is_organizer) : un Guest n'avait pas events.view et ne pouvait
--    ni ajouter ses groupes ni publier son brouillon.
-- 2. Validation du site : le rôle Organisateur reçoit events.approve (comme Admin et Co-admin) ; ceux qui ont ce droit
--    voient les propositions en attente (can_see_event), pour les accepter ou les refuser.
-- 3. Les admins du site (private.sees_all_groups) voient TOUS les groupes, groupes privés de Discussions compris (nom,
--    emoji, couleur, créateur, membres), JAMAIS leur contenu : group_messages (private.reads_group), photos et vocaux
--    (chat-photos), discussion : inchangés, toujours fermés pour un groupe privé dont on n'est pas membre.
-- Purement additive et rejouable.

-- 1. Événement de groupe ------------------------------------------------------------------------------------------
create or replace function private.group_only_event(ev public.events) returns boolean
language sql stable security definer set search_path = '' as $$
  select ev.visibility = 'invited' and not coalesce(ev.public_link, false)
     and exists (select 1 from public.event_groups eg join public.member_groups mg on mg.id = eg.group_id
                 where eg.event_id = ev.id and mg.system_key is null and eg.status in ('pending', 'approved'));
$$;
revoke all on function private.group_only_event(public.events) from public, anon, authenticated;

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
    if not has_perm('events.edit_own_published') then
      raise exception 'Seul un admin peut modifier un événement publié';
    end if;
    -- Groupes libres (22.11) : sur invitation / groupe → public ou Membres Vendredi Party = validation du site.
    if not privileged and s.require_approval
       and old.visibility = 'invited' and not coalesce(old.public_link, false)
       and (new.visibility = 'all' or coalesce(new.public_link, false)) then
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

-- Un Guest (ou Basic) a events.create mais pas events.view (is_active) : il créait un événement sans pouvoir l'organiser
-- (ni ses groupes, ni « Publier » : le brouillon restait brouillon). Celui qui peut créer organise ce qu'il a créé.
create or replace function public.is_organizer(e uuid) returns boolean
language sql stable security definer set search_path = 'public' as $$
  select (is_active() or (has_perm('events.create') and private.is_account_active(auth.uid()))) and (
    exists (select 1 from events where id = e and created_by = auth.uid())
    or exists (select 1 from event_organizers where event_id = e and user_id = auth.uid())
  );
$$;

-- Événement inséré directement « en attente » (API, anciennes apps), puis son groupe ordinaire ajouté par son
-- organisateur : guard_event le publie. Nommé « zzz_ » : après event_groups_sync et zz_event_groups_announce.
create or replace function private.on_event_groups_free_publish() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_organizer(new.event_id) then return null; end if;
  update public.events e set status = 'published'
    where e.id = new.event_id and e.status = 'pending' and private.group_only_event(e);
  -- Plus rien à valider : la « Nouvelle proposition » envoyée aux valideurs à l'insertion part de leur Activité.
  if found then delete from public.notifications where event_id = new.event_id and kind = 'proposal'; end if;
  return null;
end $$;
revoke all on function private.on_event_groups_free_publish() from public, anon, authenticated;
drop trigger if exists zzz_event_groups_free_publish on public.event_groups;
create trigger zzz_event_groups_free_publish after insert on public.event_groups
  for each row execute function private.on_event_groups_free_publish();

-- 2. Validation du site par les Organisateurs ----------------------------------------------------------------------
do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'organizer_events_approve_2026_11_22') then return; end if;
  insert into public.role_permissions (role, perm) values ('organizer', 'events.approve') on conflict do nothing;
  insert into private.one_time_changes (name) values ('organizer_events_approve_2026_11_22');
end $$;

-- Qui valide voit la proposition en attente (fiche, sondages, dates…), sans events.manage_all.
create or replace function public.can_see_event(e uuid) returns boolean
language sql stable security definer set search_path = 'public' as $$
  select is_admin() or is_organizer(e) or exists (
    select 1 from events ev
    where ev.id = e and ev.status in ('published', 'cancelled') and private.is_account_active(auth.uid())
      and ((ev.visibility = 'all' and (ev.public_link or is_active()))
           or exists (select 1 from event_invites i where i.event_id = e and i.user_id = auth.uid())
           or private.invited_by_phone(e, auth.uid()))
  ) or (has_perm('events.approve') and exists (select 1 from events ev where ev.id = e and ev.status = 'pending'));
$$;

-- 3. Les admins voient tous les groupes et leurs membres (jamais leur contenu) --------------------------------------
drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using ((created_by = (select auth.uid())) or private.in_group(id, (select auth.uid()))
         or (select private.sees_all_groups()));
drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using ((user_id = (select auth.uid())) or private.in_group(group_id, (select auth.uid()))
         or private.created_group(group_id, (select auth.uid()))
         or (select private.sees_all_groups()));
