-- PROD, retour arrière de custom_roles (20261103140000) : revient à l'énumération public.member_role et aux rangs codés
-- en dur. Les comptes d'un rôle personnalisé repassent au rôle de base juste en dessous (droits de ce rôle perdus) ;
-- l'ordre et les noms des 7 rôles de base reviennent à ceux d'origine ; les droits « Scanner les billets »,
-- « Confirmer les paiements » et « Supprimer un rôle » disparaissent (billets : de nouveau réservés aux organisateurs
-- et aux admins, fonctions remises à l'état de 20261103130000). Tout ou rien.
begin;

-- 1. Comptes des rôles personnalisés → rôle de base juste en dessous (sans les gardes : opération d'administration).
alter table public.profiles disable trigger profiles_guard;
update public.profiles p set role = (
  select b.key from public.roles b where b.builtin and b.rank < r.rank order by b.rank desc limit 1)
from public.roles r where r.key = p.role and not r.builtin;
alter table public.profiles enable trigger profiles_guard;

-- 2. Fonctions de gestion des rôles.
drop function if exists public.roles_overview();
drop function if exists public.create_role(text, text, text, text);
drop function if exists public.update_role(text, text, text, text);
drop function if exists public.delete_role(text, text);
drop function if exists public.reorder_roles(text[]);
drop function if exists private.require_roles_manager();
drop function if exists private.require_role_below(text, int);
drop function if exists private.clean_role_fields(text, text, text);
drop function if exists private.compact_role_ranks();
drop function if exists private.resync_vip_members();

-- 3. Colonnes : texte → énumération.
drop trigger if exists audit_profile on public.profiles;
drop trigger if exists profiles_last_admin on public.profiles;
drop trigger if exists sync_vip_member on public.profiles;
alter table public.profiles drop constraint if exists profiles_role_fkey;
alter table public.role_permissions drop constraint if exists role_permissions_role_fkey;
delete from public.role_permissions where role not in ('guest', 'guestplus', 'basic', 'member', 'organizer', 'coadmin', 'admin');
alter table public.profiles alter column role drop default;
alter table public.profiles alter column role type public.member_role using role::public.member_role;
alter table public.profiles alter column role set default 'member'::public.member_role;
alter table public.role_permissions alter column role type public.member_role using role::public.member_role;
create trigger audit_profile after insert or update of role, status on public.profiles
  for each row execute function private.audit_profile();
create trigger profiles_last_admin before update of role, status on public.profiles
  for each row execute function private.protect_last_admin();
create trigger sync_vip_member after insert or update of role, status on public.profiles
  for each row execute function private.sync_vip_member();

-- 4. Rangs codés en dur (état de 20261029120100_guest_plus_and_feedback_right).
create or replace function private.role_rank(r public.member_role) returns integer
language sql immutable set search_path = '' as $$
  select case r when 'guest' then 0 when 'guestplus' then 0 when 'basic' then 0 when 'member' then 1
                when 'organizer' then 2 when 'coadmin' then 3 when 'admin' then 4 end;
$$;
revoke all on function private.role_rank(public.member_role) from public, anon, authenticated;

CREATE OR REPLACE FUNCTION private.rank_of(uid uuid)
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select case when private.is_root(uid) then 99 else coalesce((select private.role_rank(role) from public.profiles where id = uid and status = 'active'), -1) end;
$function$;

CREATE OR REPLACE FUNCTION private.is_member_admin()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select auth.uid() is not null and coalesce(public.my_rank(), -1) >= 4;
$function$;

CREATE OR REPLACE FUNCTION private.sync_vip_member()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare g uuid := private.vip_group_id();
begin
  if g is null then return null; end if;
  if private.rank_of(new.id) >= 1 then
    insert into public.member_group_members (group_id, user_id) values (g, new.id) on conflict do nothing;
  else
    delete from public.member_group_members where group_id = g and user_id = new.id;
  end if;
  return null;
end $function$;

CREATE OR REPLACE FUNCTION private.group_admin(grp uuid, uid uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select uid is not null and (
    private.is_root(uid)
    or exists (select 1 from public.member_groups g where g.id = grp and g.created_by = uid)
    or (private.in_group_now(grp, uid) and (
          exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid)
          or private.rank_of(uid) >= 3)));  -- admins et co-admins du site : admins d'office de leurs groupes
$function$;

CREATE OR REPLACE FUNCTION public.set_group_admin(grp uuid, member uuid, admin boolean)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if not exists (select 1 from public.member_groups g where g.id = grp
                 and (g.created_by = auth.uid() or private.is_root(auth.uid()) or private.rank_of(auth.uid()) >= 3)) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  if not private.in_group_now(grp, member) then raise exception 'Cette personne n''est pas dans le groupe'; end if;
  if admin then
    insert into public.group_admins (group_id, user_id) values (grp, member) on conflict do nothing;
  else
    delete from public.group_admins where group_id = grp and user_id = member;
  end if;
end $function$;

CREATE OR REPLACE FUNCTION public.request_join(note text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me public.profiles;
begin
  select * into me from public.profiles where id = auth.uid();
  if me.id is null or me.status <> 'active' then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if me.role not in ('guest', 'guestplus', 'basic') then raise exception 'Tu fais déjà partie du groupe'; end if;
  if btrim(me.first_name) = '' or btrim(me.last_name) = '' or btrim(me.display_name) = '' or coalesce(me.avatar_url, '') = '' then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  insert into public.join_requests (user_id, message) values (me.id, nullif(btrim(note), ''))
  on conflict (user_id) do update set message = excluded.message, status = 'pending', created_at = now(), decided_by = null, decided_at = null
    where public.join_requests.status <> 'pending' or public.join_requests.message is distinct from excluded.message;
end;
$function$;

CREATE OR REPLACE FUNCTION public.decide_join_request(member uuid, accept boolean)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    -- Le contrôle d'identité complète de guard_profile s'applique ici.
    update public.profiles set role = 'member' where id = member and role in ('guest', 'guestplus', 'basic');
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$function$;

CREATE OR REPLACE FUNCTION public.guard_profile()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid(); my_rank int := private.rank_of(auth.uid());
begin
  if private.is_root(old.id) then
    new.role := 'admin';
    new.status := 'active';
  elsif me is not null and not private.is_root(me) then
    if new.role is distinct from old.role then
      if not ((private.user_has(me, 'members.roles') and private.role_rank(old.role) < my_rank and private.role_rank(new.role) < my_rank)
              or (old.role in ('guest', 'guestplus', 'basic') and new.role = 'member' and private.user_has(me, 'members.approve'))) then
        raise exception 'forbidden: tu ne peux pas attribuer ce rôle' using errcode = '42501';
      end if;
    end if;
    if new.status is distinct from old.status then
      if not (private.user_has(me, 'members.ban') and private.role_rank(old.role) < my_rank) then
        raise exception 'forbidden: tu ne peux pas changer l''accès de ce compte' using errcode = '42501';
      end if;
    end if;
  end if;

  new.first_name := btrim(new.first_name);
  new.last_name := btrim(new.last_name);
  new.display_name := btrim(new.display_name);
  if char_length(new.display_name) > 40 then
    raise exception 'nickname_too_long: le surnom est limité à 40 caractères' using errcode = '23514';
  end if;

  -- Toute identité renseignée reste complète, et on ne devient membre (ou plus) qu'avec une identité complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (private.role_rank(new.role) > 0 and new.role is distinct from old.role))
     and (new.first_name = '' or new.last_name = '' or new.display_name = ''
       or not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
         and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text)) then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  return new;
end;
$function$;

CREATE OR REPLACE FUNCTION public.member_card(target uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  me uuid := auth.uid();
  p public.profiles;
  identity boolean;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  select * into p from public.profiles where id = target and status = 'active';
  if p.id is null then return null; end if;
  identity := p.id = me or public.has_perm('members.view_identity');
  return jsonb_build_object(
    'id', p.id,
    'display_name', p.display_name,
    'avatar_url', p.avatar_url,
    'role', p.role,
    'root', private.is_root(p.id),
    'me', p.id = me,
    'first_name', case when identity or private.shows_name(p.id) then nullif(p.first_name, '') end,
    'last_name', case when identity or private.shows_name(p.id) then nullif(p.last_name, '') end,
    'phone', case when identity or private.phone_shared_with(p.id, me) then nullif(p.phone, '') end,
    'groups', coalesce((select jsonb_agg(g.name order by g.system_key nulls last, g.name)
                        from public.member_groups g
                        where exists (select 1 from public.member_group_members a where a.group_id = g.id and a.user_id = p.id)
                          and exists (select 1 from public.member_group_members b where b.group_id = g.id and b.user_id = me)),
                       '[]'::jsonb));
end $function$;

drop function if exists public.set_role_permission(text, text, boolean);
CREATE OR REPLACE FUNCTION public.set_role_permission(target member_role, perm text, granted boolean)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid();
begin
  if not (private.is_root(me) or private.user_has(me, 'roles.manage')) then
    raise exception 'forbidden: tu ne peux pas modifier les droits des rôles' using errcode = '42501';
  end if;
  if private.role_rank(target) >= private.rank_of(me) then
    raise exception 'forbidden: seulement les rôles en dessous du tien' using errcode = '42501';
  end if;
  if not exists (select 1 from public.permissions where key = set_role_permission.perm) then
    raise exception 'Droit inconnu';
  end if;
  if granted and not private.user_has(me, perm) then
    raise exception 'forbidden: tu ne peux pas donner un droit que tu n''as pas' using errcode = '42501';
  end if;
  if granted then
    insert into public.role_permissions (role, perm) values (target, perm) on conflict do nothing;
  else
    delete from public.role_permissions where role = target and role_permissions.perm = set_role_permission.perm;
  end if;
end;
$function$;
revoke all on function public.set_role_permission(public.member_role, text, boolean) from public, anon;
grant execute on function public.set_role_permission(public.member_role, text, boolean) to authenticated;

drop function if exists private.below_vip(text);
drop function if exists private.role_rank(text);
drop table if exists public.roles;

-- 5. Billets (état de 20261103130000_event_attendance_tickets) : fonctions d'origine, droits retirés.
create or replace function public.set_ticket_paid(e uuid, member uuid, is_paid boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.require_scanner(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set paid = is_paid, paid_at = case when is_paid then now() end, paid_by = case when is_paid then auth.uid() end,
        pay_declared_at = case when is_paid then pay_declared_at end
    where event_id = e and user_id = member;
  return private.ticket_view(e, member);
end $$;

create or replace function public.event_checkins(e uuid) returns setof jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.require_scanner(e);
  return query
    select private.ticket_view(e, r.user_id)
    from public.rsvps r
    join public.profiles p on p.id = r.user_id
    left join public.event_tickets t on t.event_id = e and t.user_id = r.user_id
    where r.event_id = e and r.status = 'yes'
    order by r.waitlisted, t.checked_in_at desc nulls last, lower(p.display_name);
end $$;

create or replace function public.event_pay_info(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  ev public.events;
  pay public.tc_payment;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'Événement introuvable' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  if coalesce(ev.price_chf, 0) <= 0 then return null; end if;
  if not (private.can_scan(e) or exists (select 1 from public.rsvps where event_id = e and user_id = auth.uid() and status = 'yes')) then
    return null;
  end if;
  select * into pay from public.tc_payment where user_id = ev.created_by;
  return jsonb_build_object(
    'organizer_id', ev.created_by,
    'organizer_name', (select display_name from public.profiles where id = ev.created_by),
    'amount', ev.price_chf, 'payment_info', ev.payment_info,
    'iban', pay.iban, 'holder', pay.holder, 'links', coalesce(pay.links, '{}'::jsonb), 'note', pay.note,
    'reference', left('Party · ' || ev.title, 140));
end $$;

create or replace function public.confirm_ticket_payment(e uuid, member uuid, received boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  ev public.events;
  who text;
begin
  perform private.require_scanner(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  select * into ev from public.events where id = e;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set paid = received, paid_at = case when received then now() end, paid_by = case when received then auth.uid() end,
        pay_declared_at = case when received then pay_declared_at end
    where event_id = e and user_id = member;
  who := coalesce(private.member_name(auth.uid()), 'L''organisateur');
  perform public.queue_notification(member, 'ticket_pay_confirmed', e, ev.title,
    case when received then who || ' a bien reçu ton paiement : ta place est payée ✓'
         else who || ' n''a pas reçu ton paiement : vérifie-le, puis touche à nouveau « J''ai payé ».' end,
    null, jsonb_build_object('received', received));
  return private.ticket_view(e, member);
end $$;
drop function if exists private.require_cashier(uuid);
drop function if exists private.require_entry_staff(uuid);
drop function if exists private.can_take_payments(uuid);
CREATE OR REPLACE FUNCTION private.can_scan(e uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select public.is_admin() or public.is_organizer(e);
$function$;
delete from public.permissions where key in ('tickets.scan', 'tickets.pay', 'roles.delete');
delete from private.one_time_changes where name in ('tickets_scan_2026_11_03', 'tickets_pay_2026_11_03', 'roles_delete_2026_11_03');
update public.permissions set label = 'Modifier les droits des rôles', hint = 'Seulement pour les rôles en dessous du sien' where key = 'roles.manage';

-- 6. Le Vendredi Party suit les anciens rangs.
insert into public.member_group_members (group_id, user_id)
  select private.vip_group_id(), p.id from public.profiles p where private.vip_group_id() is not null and private.rank_of(p.id) >= 1
on conflict do nothing;
delete from public.member_group_members m where m.group_id = private.vip_group_id() and private.rank_of(m.user_id) < 1;

notify pgrst, 'reload schema';
delete from supabase_migrations.schema_migrations where version = '20261103140000';
commit;
