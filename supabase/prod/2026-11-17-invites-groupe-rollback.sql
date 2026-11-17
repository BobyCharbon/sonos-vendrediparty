-- PROD, retour arrière de invites_groupe (20261117110000) : les fonctions retrouvent leur texte d'avant, l'option, les
-- choix des invités, les départs et « Garder cette bande ? » disparaissent. Les personnes déjà entrées dans un groupe y
-- restent (ce sont des membres ordinaires) ; les notifications « group_added » déjà envoyées restent dans l'Activité.
begin;
do $$ declare def text;
begin
  def := pg_get_functiondef('public.guard_event()'::regprocedure);
  execute replace(def, $a$    if (to_jsonb(new) - 'guest_group' - 'updated_at') = (to_jsonb(old) - 'guest_group' - 'updated_at')
       and public.is_organizer(new.id) then return new; end if;
$a$, '');
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  execute replace(def, $a$
    when 'group_added' then coalesce(prefs.group_added, true)$a$, '');
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  execute replace(def, '''group_join'', ''group_added'',', '''group_join'',');
  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  execute replace(def, '''group_join'', ''group_added'')', '''group_join'')');
  def := pg_get_functiondef('private.event_guest_list_full(uuid)'::regprocedure);
  def := replace(def, $a$,
        'in_group', ev.guest_group is not null and private.in_group_now(ev.guest_group, p.id)) x$a$, ') x');
  execute replace(def, $a$
    'guest_group', private.guest_group_card(e),$a$, '');
  def := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  execute replace(def, $a$'guest_group', case when not organizer then private.guest_group_offer(ev.id, me) end,
    $a$, '');
end $$;

-- invite_to_group d'avant (sans le contrôle du blocage).
create or replace function public.invite_to_group(grp uuid, member uuid default null, phone text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  select * into g from public.member_groups where id = grp;
  if target is null and number is not null then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  if target is not null and exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if target is not null then
    insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
    select display_name into me from public.profiles where id = auth.uid();
    perform public.queue_notification(target, 'group_invite', null, g.name,
      coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
      'group_invite:' || grp || ':' || target);
    return jsonb_build_object('invited', 'member');
  end if;
  insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
  return jsonb_build_object('invited', 'phone');
end $$;

drop trigger if exists events_guest_group_guard on public.events;
drop trigger if exists rsvps_guest_group on public.rsvps;
drop trigger if exists member_group_members_departure on public.member_group_members;
drop function if exists public.take_group_join_note(uuid);
drop function if exists public.keep_band(uuid, text, uuid, text);
drop function if exists private.band_people(uuid, text);
drop function if exists public.event_guest_group(uuid);
drop function if exists public.set_event_guest_group(uuid, uuid, text);
drop function if exists private.note_group_departure();
drop function if exists private.guest_group_on_rsvp();
drop function if exists public.accept_invite_group(uuid, text, boolean);
drop function if exists public.set_guest_group_choice(uuid, boolean);
drop function if exists private.guest_group_join(uuid, uuid);
drop function if exists private.guest_group_offer(uuid, uuid);
drop function if exists private.guest_group_eligible(uuid, uuid);
drop function if exists private.guest_group_card(uuid);
drop function if exists private.guard_event_guest_group();
drop function if exists private.manages_guest_group(uuid, uuid);
drop table if exists private.band_offers;
drop table if exists private.guest_group_choices;
drop table if exists private.group_departures;
alter table public.notification_prefs drop column if exists group_added;
alter table public.events drop column if exists guest_group;
delete from supabase_migrations.schema_migrations where version = '20261117110000';
commit;
