-- Visibilité d'un événement (Party web et app iOS) :
--   « Tous les membres + lien public » : visibility 'all' + public_link (consultable par lien, réponse après connexion SMS) ;
--   « Tous les membres »               : visibility 'all' ;
--   « Groupes » / « Personnalisé »     : visibility 'invited'.
-- event_invites reste la seule liste d'invités lue par les règles d'accès existantes : les groupes y sont
-- recopiés (via_group) et suivis quand leurs membres changent. Les invités d'un événement privé reçoivent
-- une notification « private_invite » au lieu de « new_event ».

alter table public.events add column if not exists public_link boolean not null default false;
alter table public.event_invites add column if not exists via_group boolean not null default false;
-- ── Groupes de membres, créés par tout créateur d'événement et partagés entre eux ──
create table public.member_groups (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(btrim(name)) between 1 and 60),
  created_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now()
);
create table public.member_group_members (
  group_id uuid not null references public.member_groups (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  primary key (group_id, user_id)
);
create index member_group_members_user on public.member_group_members (user_id);
create table public.event_groups (
  event_id uuid not null references public.events (id) on delete cascade,
  group_id uuid not null references public.member_groups (id) on delete cascade,
  primary key (event_id, group_id)
);
create index event_groups_group on public.event_groups (group_id);
alter table public.member_groups enable row level security;
alter table public.member_group_members enable row level security;
alter table public.event_groups enable row level security;
grant select, insert, update, delete on public.member_groups, public.member_group_members, public.event_groups to authenticated;
create policy "voir les groupes" on public.member_groups for select to authenticated using ((select public.is_active()));
create policy "créer un groupe" on public.member_groups for insert to authenticated
  with check (created_by = (select auth.uid()) and (select public.has_perm('events.create')));
create policy "modifier son groupe" on public.member_groups for update to authenticated
  using (created_by = (select auth.uid()) or (select public.is_admin()));
create policy "supprimer son groupe" on public.member_groups for delete to authenticated
  using (created_by = (select auth.uid()) or (select public.is_admin()));
create policy "voir les membres des groupes" on public.member_group_members for select to authenticated using ((select public.is_active()));
create policy "composer son groupe" on public.member_group_members for all to authenticated
  using (exists (select 1 from public.member_groups g where g.id = group_id and (g.created_by = (select auth.uid()) or (select public.is_admin()))))
  with check (exists (select 1 from public.member_groups g where g.id = group_id and (g.created_by = (select auth.uid()) or (select public.is_admin()))));
create policy "voir les groupes invités" on public.event_groups for select to authenticated
  using (public.can_see_event(event_id) or public.is_organizer(event_id));
create policy "inviter des groupes" on public.event_groups for all to authenticated
  using (public.is_admin() or public.is_organizer(event_id)) with check (public.is_admin() or public.is_organizer(event_id));
-- ── Recopie des groupes dans event_invites ──
-- Quelqu'un qui quitte le groupe garde l'accès s'il a déjà répondu.
create or replace function private.sync_event_group_invites(e uuid) returns void
language sql security definer set search_path = '' as $$
  delete from public.event_invites i where i.event_id = e and i.via_group
    and not exists (select 1 from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
                    where eg.event_id = e and gm.user_id = i.user_id)
    and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id);
  insert into public.event_invites (event_id, user_id, via_group)
    select distinct eg.event_id, gm.user_id, true
    from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
    where eg.event_id = e and exists (select 1 from public.events where id = e)
  on conflict (event_id, user_id) do nothing;
$$;
create or replace function private.on_event_groups_change() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.sync_event_group_invites(coalesce(new.event_id, old.event_id));
  return null;
end $$;
create trigger event_groups_sync after insert or delete on public.event_groups
  for each row execute function private.on_event_groups_change();
-- Un membre ajouté à un groupe est invité aux événements à venir de ce groupe (et retiré s'il en sort).
create or replace function private.on_group_members_change() returns trigger
language plpgsql security definer set search_path = '' as $$
declare e uuid;
begin
  for e in select eg.event_id from public.event_groups eg join public.events ev on ev.id = eg.event_id
           where eg.group_id = coalesce(new.group_id, old.group_id)
             and ev.status in ('draft', 'pending', 'published')
             and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() loop
    perform private.sync_event_group_invites(e);
  end loop;
  return null;
end $$;
create trigger member_group_members_sync after insert or delete on public.member_group_members
  for each row execute function private.on_group_members_change();
-- ── Notification « Invitation à un événement privé » ──
create or replace function private.queue_private_invite(ev public.events, u uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare via text;
begin
  if u = ev.created_by or not private.is_member(u) then return; end if;
  select string_agg(g.name, ', ' order by g.name) into via
    from public.event_groups eg
    join public.member_groups g on g.id = eg.group_id
    join public.member_group_members gm on gm.group_id = g.id and gm.user_id = u
    where eg.event_id = ev.id;
  perform public.queue_notification(u, 'private_invite', ev.id, '🔒 Invitation à un événement privé',
    'On t’invite à « ' || ev.title || ' »' || coalesce(' avec le groupe ' || via, '') || '.',
    'private_invite:' || ev.id);
end $$;
-- Invité ajouté à un événement privé déjà publié (à la publication, notify_event_change s'en charge).
create or replace function private.on_event_invite() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  select * into ev from public.events where id = new.event_id;
  if ev.status = 'published' and ev.visibility = 'invited' and ev.notify_on_publish
     and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() then
    perform private.queue_private_invite(ev, new.user_id);
  end if;
  return null;
end $$;
create trigger event_invites_notify after insert on public.event_invites
  for each row execute function private.on_event_invite();
revoke all on function private.sync_event_group_invites(uuid), private.on_event_groups_change(), private.on_group_members_change(),
  private.queue_private_invite(public.events, uuid), private.on_event_invite() from public, anon, authenticated;
-- Publication : le groupe reçoit « Nouvel événement », les invités d'un événement privé leur invitation.
CREATE OR REPLACE FUNCTION public.notify_event_change()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare u uuid; tag_ids uuid[];
begin
  -- Nouvelle proposition -> admins
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

  -- Publication -> créateur + groupe selon préférences et abonnements
  if new.status = 'published' and (tg_op = 'INSERT' or old.status <> 'published') then
    if new.created_by <> coalesce(new.approved_by, new.created_by) then
      perform queue_notification(new.created_by, 'approved', new.id, 'Proposition validée',
        '« ' || new.title || ' » est publié.');
    end if;
    if new.notify_on_publish and new.visibility = 'invited' then
      for u in select i.user_id from event_invites i where i.event_id = new.id loop
        perform private.queue_private_invite(new, u);
      end loop;
    elsif new.notify_on_publish then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where private.is_member(p.id) and p.id <> new.created_by
          and (np.new_event = 'all' or (np.new_event = 'subscribed' and (
                exists (select 1 from tag_subscriptions ts where ts.user_id = p.id and ts.tag_id = any (tag_ids))
             or exists (select 1 from category_subscriptions cs where cs.user_id = p.id and cs.category_id = new.category_id))))
      loop
        perform queue_notification(u, 'new_event', new.id,
          case when new.date_mode = 'poll' then 'Nouveau sondage de dates' else 'Nouvel événement' end,
          new.title, 'new_event:' || new.id);
      end loop;
    end if;
  end if;

  if tg_op = 'UPDATE' and old.status = 'published' then
    if new.status = 'cancelled' then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id=a where np.event_changed loop
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
end $function$;
-- ── Lien public : consultation sans compte, réponse avec un compte Party (même invité) ──
create or replace function public.can_answer_public(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.events where id = e and public_link and visibility = 'all' and status = 'published')
     and exists (select 1 from public.profiles where id = auth.uid() and status = 'active');
$$;
revoke all on function public.can_answer_public(uuid) from public, anon;
grant execute on function public.can_answer_public(uuid) to authenticated;
drop policy "répondre" on public.rsvps;
create policy "répondre" on public.rsvps for insert with check (user_id = auth.uid() and (public.can_participate(event_id) or public.can_answer_public(event_id)));
drop policy "changer sa réponse" on public.rsvps;
create policy "changer sa réponse" on public.rsvps for update using (user_id = auth.uid() and (public.can_participate(event_id) or public.can_answer_public(event_id)));
-- Ce que montre le lien public : pas de noms, pas d'infos de paiement, juste le nombre de participants.
create or replace function public.public_event(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'price_chf', ev.price_chf, 'allow_maybe', ev.allow_maybe, 'rsvp_deadline', ev.rsvp_deadline,
    'max_participants', ev.max_participants,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones, 'note', r.note)
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$$;
revoke all on function public.public_event(uuid) from public;
grant usage on schema public to anon;
grant execute on function public.public_event(uuid) to anon, authenticated;
