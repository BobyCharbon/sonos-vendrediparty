-- PROD, retour arrière de groupes libres (20261122150000) : guard_event, can_see_event et is_organizer retrouvent leur
-- texte de prod du 22.11 (lu avant la mise en prod) ; le déclencheur zzz_event_groups_free_publish est retiré ; le rôle
-- Organisateur perd events.approve ; les admins ne voient plus les groupes privés de Discussions. Les événements publiés
-- entre-temps le restent. private.group_only_event et private.on_event_groups_free_publish restent (sans effet). Tout ou rien.
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

CREATE OR REPLACE FUNCTION public.can_see_event(e uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select is_admin() or is_organizer(e) or exists (
    select 1 from events ev
    where ev.id = e and ev.status in ('published', 'cancelled') and private.is_account_active(auth.uid())
      and ((ev.visibility = 'all' and (ev.public_link or is_active()))
           or exists (select 1 from event_invites i where i.event_id = e and i.user_id = auth.uid())
           or private.invited_by_phone(e, auth.uid()))
  );
$function$;

CREATE OR REPLACE FUNCTION public.is_organizer(e uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  select is_active() and (
    exists (select 1 from events where id = e and created_by = auth.uid())
    or exists (select 1 from event_organizers where event_id = e and user_id = auth.uid())
  );
$function$;

drop trigger if exists zzz_event_groups_free_publish on public.event_groups;

delete from public.role_permissions where role = 'organizer' and perm = 'events.approve';
delete from private.one_time_changes where name = 'organizer_events_approve_2026_11_22';

drop policy if exists "voir les groupes" on public.member_groups;
create policy "voir les groupes" on public.member_groups for select to authenticated
  using ((created_by = (select auth.uid())) or private.in_group(id, (select auth.uid()))
         or ((select private.sees_all_groups()) and not private_chat));
drop policy if exists "voir les membres des groupes" on public.member_group_members;
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated
  using ((user_id = (select auth.uid())) or private.in_group(group_id, (select auth.uid()))
         or private.created_group(group_id, (select auth.uid()))
         or ((select private.sees_all_groups()) and not private.group_is_private(group_id)));

notify pgrst, 'reload schema';

delete from supabase_migrations.schema_migrations where version = '20261122150000';
commit;
