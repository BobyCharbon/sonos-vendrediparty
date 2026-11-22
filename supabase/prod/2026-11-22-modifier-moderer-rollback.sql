-- PROD, retour arrière de modifier_moderer (20261122160000) : guard_event, is_organizer, guard_event_group_status et
-- on_event_groups_free_publish retrouvent leur texte de 20261122150000 (groupes libres) ; la politique « modifier
-- événement » redevient (is_admin() or is_organizer(id)) ; les droits events.edit_others / events.remove_others
-- disparaissent ; le rôle Modérateur aussi (ses comptes repassent Organisateur, rangs recompactés). Les événements
-- remis en attente entre-temps le restent. private.own_event et private.regroup_after_edit restent (sans effet).
-- Tout ou rien.
begin;
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
end $function$;

CREATE OR REPLACE FUNCTION public.is_organizer(e uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select (is_active() or (has_perm('events.create') and private.is_account_active(auth.uid()))) and (
    exists (select 1 from events where id = e and created_by = auth.uid())
    or exists (select 1 from event_organizers where event_id = e and user_id = auth.uid())
  );
$function$;

CREATE OR REPLACE FUNCTION private.on_event_groups_free_publish()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if auth.uid() is null or not public.is_organizer(new.event_id) then return null; end if;
  update public.events e set status = 'published'
    where e.id = new.event_id and e.status = 'pending' and private.group_only_event(e);
  -- Plus rien à valider : la « Nouvelle proposition » envoyée aux valideurs à l'insertion part de leur Activité.
  if found then delete from public.notifications where event_id = new.event_id and kind = 'proposal'; end if;
  return null;
end $function$;

CREATE OR REPLACE FUNCTION private.guard_event_group_status()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if auth.uid() is null then return new; end if;  -- service, fonctions internes
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
end $function$;

drop policy if exists "modifier événement" on public.events;
create policy "modifier événement" on public.events for update using (is_admin() or is_organizer(id));

delete from public.role_permissions where perm in ('events.edit_others', 'events.remove_others');
delete from public.permissions where key in ('events.edit_others', 'events.remove_others');
delete from private.one_time_changes where name = 'events_others_2026_11_22';

update public.profiles set role = 'organizer' where role = 'moderator';
delete from public.role_permissions where role = 'moderator';
delete from public.roles where key = 'moderator';
update public.roles r set rank = o.pos
  from (select key, (row_number() over (order by rank) - 1)::int pos from public.roles) o
  where o.key = r.key and r.rank <> o.pos;

notify pgrst, 'reload schema';

delete from supabase_migrations.schema_migrations where version = '20261122160000';
commit;
