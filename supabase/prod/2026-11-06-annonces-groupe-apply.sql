-- PROD, annonces_groupe (20261106220000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- « Prévenir le groupe » avec validation (48 h), réglages du groupe, droit groups.announce_approve, 3 interrupteurs.
-- Prérequis : 20261106200000_campagne_bots_corrections, 20261106090000 et 20261103121000 (group_staff). Rejouable. Tout ou rien.
begin;
-- Annonces d'événement aux groupes (décision de l'admin du 06.11.2026, spécification « annonces-groupe ») :
-- 1. Un événement PUBLIC ne prévient jamais personne (déjà garanti : events_public_silent, 20261106200000).
-- 2. Un événement réservé à un GROUPE (groupe choisi, ou « Membres Vendredi Party ») ne prévient le groupe que si
--    l'organisateur l'a demandé (events.announce_group, « Prévenir le groupe », éteint par défaut) :
--    - organisateur créateur / admin / organisateur du groupe (private.group_staff), ou titulaire du droit
--      groups.announce_approve, ou groupe réglé « notifications libres » : envoi direct ;
--    - sinon : demande « Annonce à valider » (public.event_announcements), envoyée aux valideurs du groupe ; la première
--      réponse gagne (verrou de ligne) ; acceptée → le groupe est prévenu ; refusée → rien n'est envoyé, l'événement
--      reste publié et visible ; sans réponse en 48 h → acceptée et envoyée d'office (tâche pg_cron).
-- 3. Réglages du groupe, décidés par son créateur : events_need_approval (un événement proposé au groupe par un simple
--    membre attend la validation d'un valideur du groupe avant d'être visible par le groupe : event_groups.status) et
--    announce_mode ('request' : demande ci-dessus ; 'free' : les membres préviennent librement).
-- 4. Invitation une à une : inchangée (notify_on_publish, invite_people).
-- 5. Notifications « Annonce à valider », « Ton annonce a été acceptée / refusée », « Événement à valider pour ton
--    groupe », « Événement accepté / refusé par le groupe » : chacune suit son interrupteur (notification_prefs) à
--    l'insertion ET à l'envoi (private.web_push_allowed, utilisé par send-push et send-web-push).
-- 6. Garanti par la base : la notification d'un membre arrivé par le groupe (private.should_invite) et l'annonce
--    « Nouvel événement » aux Membres VIP ne partent QUE par une annonce envoyée. L'assistant IA (app/ai_events.py)
--    écrit avec le jeton de la personne : mêmes règles.
-- Purement additive et rejouable : add column if not exists, create or replace, drop … if exists.

-- 1. Structure ----------------------------------------------------------------------------------------------------
alter table public.events add column if not exists announce_group boolean not null default false;

alter table public.member_groups add column if not exists events_need_approval boolean not null default false;
alter table public.member_groups add column if not exists announce_mode text not null default 'request';
alter table public.member_groups drop constraint if exists member_groups_announce_mode_check;
alter table public.member_groups add constraint member_groups_announce_mode_check check (announce_mode in ('request', 'free'));

alter table public.event_groups add column if not exists status text not null default 'approved';
alter table public.event_groups drop constraint if exists event_groups_status_check;
alter table public.event_groups add constraint event_groups_status_check check (status in ('pending', 'approved', 'refused'));
alter table public.event_groups add column if not exists requested_by uuid references public.profiles(id) on delete set null;
alter table public.event_groups add column if not exists answered_by uuid references public.profiles(id) on delete set null;
alter table public.event_groups add column if not exists answered_at timestamptz;
alter table public.event_groups add column if not exists created_at timestamptz not null default now();

alter table public.notification_prefs add column if not exists announce_requests boolean not null default true;
alter table public.notification_prefs add column if not exists announce_results boolean not null default true;
alter table public.notification_prefs add column if not exists group_event_requests boolean not null default true;

create table if not exists public.event_announcements (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  group_id uuid not null references public.member_groups(id) on delete cascade,
  requested_by uuid references public.profiles(id) on delete set null,
  -- pending : en attente ; accepted / refused : réponse d'un valideur ; auto : 48 h sans réponse ; direct : sans validation
  status text not null default 'pending' check (status in ('pending', 'accepted', 'refused', 'auto', 'direct')),
  requested_at timestamptz not null default now(),
  answered_by uuid references public.profiles(id) on delete set null,
  answered_at timestamptz,
  sent_at timestamptz,
  unique (event_id, group_id)
);
create index if not exists event_announcements_pending on public.event_announcements (requested_at) where status = 'pending';
alter table public.event_announcements enable row level security;

-- 2. Droit dédié ----------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('groups.announce_approve', 'Événements', 'Valider les annonces des groupes',
   'Accepter ou refuser qu''un événement soit annoncé à un groupe, ou proposé à un groupe qui demande une validation (en plus du créateur et des admins du groupe)', 19)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'announce_approve_2026_11_06') then return; end if;
  insert into public.role_permissions (role, perm) values ('admin', 'groups.announce_approve'), ('coadmin', 'groups.announce_approve')
  on conflict do nothing;
  insert into private.one_time_changes (name) values ('announce_approve_2026_11_06');
end $$;

-- 3. Qui valide -----------------------------------------------------------------------------------------------------
create or replace function private.may_approve_announcement(g uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and private.is_account_active(uid)
     and (private.group_staff(g, uid) or private.user_has(uid, 'groups.announce_approve'));
$$;
revoke all on function private.may_approve_announcement(uuid, uuid) from public, anon;
grant execute on function private.may_approve_announcement(uuid, uuid) to authenticated;  -- appelée par une politique

-- Valideurs PRÉVENUS : le créateur, les admins et les organisateurs du groupe (sauf le demandeur). Les titulaires du
-- droit groups.announce_approve peuvent toujours répondre, mais ne sont prévenus que si le groupe n'a personne d'autre.
create or replace function private.announcement_validators(g uuid, requester uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  with staff as (
    select distinct c.uid from (
      select m.user_id uid from public.member_group_members m where m.group_id = g
      union select mg.created_by from public.member_groups mg where mg.id = g and mg.created_by is not null
    ) c
    where c.uid is distinct from requester and private.is_account_active(c.uid) and private.group_staff(g, c.uid)
  )
  select uid from staff
  union
  select p.id from public.profiles p
  where not exists (select 1 from staff) and p.id is distinct from requester and p.status = 'active'
    and private.user_has(p.id, 'groups.announce_approve');
$$;
revoke all on function private.announcement_validators(uuid, uuid) from public, anon, authenticated;

drop policy if exists "voir les annonces de groupe" on public.event_announcements;
create policy "voir les annonces de groupe" on public.event_announcements for select to authenticated
  using (requested_by = (select auth.uid()) or public.is_organizer(event_id)
         or private.may_approve_announcement(group_id, (select auth.uid())));
grant select on public.event_announcements to authenticated;

-- 4. Qui est prévenu ------------------------------------------------------------------------------------------------
-- Invité un à un (compte ou numéro) : comme avant, selon « prévenir à la publication ».
create or replace function private.invited_in_person(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.event_invites i where i.event_id = e and i.user_id = u and not i.via_group)
      or exists (select 1 from public.event_phone_invites pi join public.profiles p on p.phone = pi.phone
                 where pi.event_id = e and p.id = u);
$$;
revoke all on function private.invited_in_person(uuid, uuid) from public, anon, authenticated;

-- Membre d'un groupe dont l'annonce est partie (acceptée, d'office ou directe).
create or replace function private.group_announced_to(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.event_announcements a
                 join public.member_group_members m on m.group_id = a.group_id and m.user_id = u
                 where a.event_id = e and a.status in ('accepted', 'auto', 'direct'));
$$;
revoke all on function private.group_announced_to(uuid, uuid) from public, anon, authenticated;

create or replace function private.should_invite(ev public.events, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select ev.status = 'published' and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now()
     and (ev.visibility = 'invited' or (ev.visibility = 'all' and not private.is_member(u)))
     and ((ev.notify_on_publish and private.invited_in_person(ev.id, u)) or private.group_announced_to(ev.id, u));
$$;

-- « Nouvel événement » aux Membres VIP (et abonnés) : sorti de notify_event_change, envoyé par l'annonce du groupe
-- Vendredi Party seulement.
create or replace function private.broadcast_new_event(ev public.events) returns void
language plpgsql security definer set search_path = '' as $$
declare u uuid; tag_ids uuid[];
begin
  select coalesce(array_agg(tag_id), '{}') into tag_ids from public.event_tags where event_id = ev.id;
  for u in
    select p.id from public.profiles p join public.notification_prefs np on np.user_id = p.id
    where p.id <> ev.created_by and p.status = 'active' and private.is_member(p.id)
      and (np.new_event = 'all' or (np.new_event = 'subscribed' and (
            exists (select 1 from public.tag_subscriptions ts where ts.user_id = p.id and ts.tag_id = any (tag_ids))
         or exists (select 1 from public.category_subscriptions cs where cs.user_id = p.id and cs.category_id = ev.category_id))))
  loop
    perform public.queue_notification(u, 'new_event', ev.id,
      case when ev.date_mode = 'poll' then 'Nouveau sondage de dates' else 'Nouvel événement' end,
      ev.title, 'new_event:' || ev.id);
  end loop;
end $$;
revoke all on function private.broadcast_new_event(public.events) from public, anon, authenticated;

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
end $$;

-- 5. Envoi d'une annonce ------------------------------------------------------------------------------------------
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
    if private.should_invite(ev, u) then perform private.queue_private_invite(ev, u); end if;
  end loop;
end $$;
revoke all on function private.send_announcement(uuid) from public, anon, authenticated;

create or replace function private.group_label(g uuid) returns text
language sql stable security definer set search_path = '' as $$
  select case when mg.system_key = 'vip' then 'Vendredi Party' else mg.name end from public.member_groups mg where mg.id = g;
$$;
revoke all on function private.group_label(uuid) from public, anon, authenticated;

create or replace function private.person_label(u uuid) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select nullif(btrim(display_name), '') from public.profiles where id = u), 'Quelqu’un');
$$;
revoke all on function private.person_label(uuid) from public, anon, authenticated;

-- Organisateur informé de la réponse (interrupteur « Réponses à mes demandes au groupe »).
create or replace function private.tell_requester(u uuid, k text, e uuid, t text, b text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if u is null or not exists (select 1 from public.notification_prefs np where np.user_id = u and np.announce_results) then return; end if;
  perform public.queue_notification(u, k, e, t, b, null, jsonb_build_object('url', '/?tab=events&event=' || e));
end $$;
revoke all on function private.tell_requester(uuid, text, uuid, text, text) from public, anon, authenticated;

-- Valideurs prévenus d'une demande (interrupteur « Annonces à valider » ou « Événements à valider pour mes groupes »).
-- Pas d'event_id : un valideur ne voit pas forcément l'événement ; le toucher ouvre Activité, carte « À valider ».
create or replace function private.tell_validators(g uuid, requester uuid, k text, t text, b text, dedupe text, e uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare u uuid;
begin
  for u in select v from private.announcement_validators(g, requester) v
           join public.notification_prefs np on np.user_id = v
           where (k = 'announce_request' and np.announce_requests) or (k = 'group_event_request' and np.group_event_requests) loop
    perform public.queue_notification(u, k, null, t, b, dedupe || ':' || u,
      jsonb_build_object('url', '/?tab=events&activity=1', 'target_event', e, 'group_id', g));
  end loop;
end $$;
revoke all on function private.tell_validators(uuid, uuid, text, text, text, text, uuid) from public, anon, authenticated;

-- Ouvre les annonces d'un événement publié qui doit prévenir son groupe (une par groupe validé, une fois) ; prévient
-- aussi les valideurs des groupes où l'événement attend d'être accepté.
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

  if not ev.announce_group then return; end if;
  for g in select eg.group_id from public.event_groups eg where eg.event_id = e and eg.status = 'approved'
           union select private.vip_group_id() where ev.visibility = 'all' loop
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
      perform private.tell_validators(g, ev.created_by, 'announce_request', 'Annonce à valider',
        who || ' veut prévenir le groupe ' || private.group_label(g) || ' de « ' || ev.title
        || ' ». Sans réponse sous 48 h, l’annonce part d’office.', 'announce_request:' || a, e);
    end if;
  end loop;
end $$;
revoke all on function private.open_announcements(uuid) from public, anon, authenticated;

-- 6. Déclencheurs -------------------------------------------------------------------------------------------------
create or replace function private.on_event_announce() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- « Prévenir le groupe » coupé ou événement devenu public : les demandes encore en attente tombent.
  if tg_op = 'UPDATE' and (not new.announce_group or new.public_link) then
    delete from public.event_announcements where event_id = new.id and status = 'pending';
  end if;
  perform private.open_announcements(new.id);
  return null;
end $$;
revoke all on function private.on_event_announce() from public, anon, authenticated;
drop trigger if exists events_announce on public.events;
create trigger events_announce after insert or update of status, announce_group, visibility, public_link on public.events
  for each row execute function private.on_event_announce();

-- Groupe proposé par un simple membre à un groupe « avec validation » : en attente ; seul un valideur change le statut.
create or replace function private.guard_event_group_status() returns trigger
language plpgsql security definer set search_path = '' as $$
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
end $$;
revoke all on function private.guard_event_group_status() from public, anon, authenticated;
drop trigger if exists guard_event_group_status on public.event_groups;
create trigger guard_event_group_status before insert or update on public.event_groups
  for each row execute function private.guard_event_group_status();

-- Les membres d'un groupe n'entrent dans les invités (et ne voient l'événement) qu'une fois le groupe validé.
create or replace function private.sync_event_group_invites(e uuid) returns void
language sql security definer set search_path = '' as $$
  delete from public.event_invites i where i.event_id = e and i.via_group
    and not exists (select 1 from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
                    where eg.event_id = e and eg.status = 'approved' and gm.user_id = i.user_id)
    and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id);
  insert into public.event_invites (event_id, user_id, via_group)
    select distinct eg.event_id, gm.user_id, true
    from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
    where eg.event_id = e and eg.status = 'approved' and exists (select 1 from public.events where id = e)
  on conflict (event_id, user_id) do nothing;
$$;
drop trigger if exists event_groups_sync on public.event_groups;
create trigger event_groups_sync after insert or delete or update of status on public.event_groups
  for each row execute function private.on_event_groups_change();

-- Nommé « zz_ » : après event_groups_sync (les invités du groupe sont déjà là).
create or replace function private.on_event_group_announce() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    delete from public.event_announcements where event_id = old.event_id and group_id = old.group_id and status = 'pending';
    return null;
  end if;
  perform private.open_announcements(new.event_id);
  return null;
end $$;
revoke all on function private.on_event_group_announce() from public, anon, authenticated;
drop trigger if exists zz_event_groups_announce on public.event_groups;
create trigger zz_event_groups_announce after insert or delete or update of status on public.event_groups
  for each row execute function private.on_event_group_announce();

-- 7. Réponses -----------------------------------------------------------------------------------------------------
-- Première réponse gagnante : la ligne est verrouillée (for update) ; une réponse arrivée après dit qui a répondu.
create or replace function public.answer_announcement(a uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.event_announcements; ev public.events;
begin
  select * into r from public.event_announcements where id = a for update;
  if r.id is null then raise exception 'Cette demande n’existe plus'; end if;
  if not private.may_approve_announcement(r.group_id, auth.uid()) then
    raise exception 'forbidden: réservé au créateur et aux admins du groupe' using errcode = '42501';
  end if;
  if r.status <> 'pending' then
    return jsonb_build_object('status', r.status, 'already', true, 'answered_by', private.person_label(r.answered_by));
  end if;
  update public.event_announcements set status = case when accept then 'accepted' else 'refused' end,
    answered_by = auth.uid(), answered_at = now() where id = a;
  select * into ev from public.events where id = r.event_id;
  if accept then
    perform private.send_announcement(a);
    perform private.tell_requester(r.requested_by, 'announce_accepted', ev.id, 'Ton annonce a été acceptée',
      '« ' || ev.title || ' » : le groupe ' || private.group_label(r.group_id) || ' est prévenu.');
  else
    perform private.tell_requester(r.requested_by, 'announce_refused', ev.id, 'Ton annonce a été refusée',
      '« ' || ev.title || ' » reste visible par le groupe ' || private.group_label(r.group_id) || ', sans notification.');
  end if;
  return jsonb_build_object('status', case when accept then 'accepted' else 'refused' end, 'already', false);
end $$;
revoke all on function public.answer_announcement(uuid, boolean) from public, anon;
grant execute on function public.answer_announcement(uuid, boolean) to authenticated;

create or replace function public.answer_group_event(e uuid, g uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r public.event_groups; ev public.events;
begin
  select * into r from public.event_groups where event_id = e and group_id = g for update;
  if r.event_id is null then raise exception 'Cette demande n’existe plus'; end if;
  if not private.may_approve_announcement(g, auth.uid()) then
    raise exception 'forbidden: réservé au créateur et aux admins du groupe' using errcode = '42501';
  end if;
  if r.status <> 'pending' then
    return jsonb_build_object('status', r.status, 'already', true, 'answered_by', private.person_label(r.answered_by));
  end if;
  update public.event_groups set status = case when accept then 'approved' else 'refused' end,
    answered_by = auth.uid(), answered_at = now() where event_id = e and group_id = g;
  select * into ev from public.events where id = e;
  perform private.tell_requester(coalesce(r.requested_by, ev.created_by), case when accept then 'group_event_accepted' else 'group_event_refused' end, e,
    case when accept then 'Événement accepté par le groupe' else 'Événement refusé par le groupe' end,
    case when accept then '« ' || ev.title || ' » est maintenant visible par le groupe ' || private.group_label(g) || '.'
         else '« ' || ev.title || ' » ne sera pas visible par le groupe ' || private.group_label(g) || '.' end);
  return jsonb_build_object('status', case when accept then 'approved' else 'refused' end, 'already', false);
end $$;
revoke all on function public.answer_group_event(uuid, uuid, boolean) from public, anon;
grant execute on function public.answer_group_event(uuid, uuid, boolean) to authenticated;

-- 48 h sans réponse : acceptée et envoyée d'office (pg_cron, toutes les 10 minutes).
create or replace function private.auto_accept_announcements() returns int
language plpgsql security definer set search_path = '' as $$
declare r public.event_announcements; ev public.events; n int := 0;
begin
  for r in select * from public.event_announcements
           where status = 'pending' and requested_at <= now() - interval '48 hours'
           order by requested_at for update skip locked loop
    update public.event_announcements set status = 'auto', answered_at = now() where id = r.id;
    perform private.send_announcement(r.id);
    select * into ev from public.events where id = r.event_id;
    if ev.status = 'published' then
      perform private.tell_requester(r.requested_by, 'announce_accepted', ev.id, 'Ton annonce est partie',
        'Sans réponse en 48 h, « ' || ev.title || ' » a été annoncé au groupe ' || private.group_label(r.group_id) || '.');
    end if;
    n := n + 1;
  end loop;
  return n;
end $$;
revoke all on function private.auto_accept_announcements() from public, anon, authenticated;

do $$
begin
  perform cron.unschedule('group-announcements-auto') where exists (select 1 from cron.job where jobname = 'group-announcements-auto');
  perform cron.schedule('group-announcements-auto', '*/10 * * * *', 'select private.auto_accept_announcements();');
end $$;

-- 8. Écran « À valider » et réglages du groupe -------------------------------------------------------------------
create or replace function public.my_group_requests() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(x order by x->>'requested_at'), '[]') from (
    select jsonb_build_object('kind', 'announce', 'id', a.id, 'event_id', ev.id, 'group_id', a.group_id,
      'group', private.group_label(a.group_id), 'title', ev.title, 'starts_at', ev.starts_at, 'all_day', ev.all_day,
      'date_mode', ev.date_mode, 'location_name', ev.location_name, 'cover_url', ev.cover_url,
      'description', left(coalesce(ev.description, ''), 280), 'organizer', private.person_label(a.requested_by),
      'requested_at', a.requested_at, 'auto_at', a.requested_at + interval '48 hours',
      'members', (select count(*) from public.member_group_members m where m.group_id = a.group_id),
      'message_title', case when a.group_id = private.vip_group_id() and ev.visibility = 'all' then 'Nouvel événement'
                            else '🔒 Invitation à un événement privé' end,
      'message_body', case when a.group_id = private.vip_group_id() and ev.visibility = 'all' then ev.title
                           else 'On t’invite à « ' || ev.title || ' » avec le groupe ' || private.group_label(a.group_id) || '.' end) x
    from public.event_announcements a join public.events ev on ev.id = a.event_id
    where a.status = 'pending' and ev.status = 'published' and private.may_approve_announcement(a.group_id, auth.uid())
    union all
    select jsonb_build_object('kind', 'event', 'id', eg.event_id || ':' || eg.group_id, 'event_id', ev.id, 'group_id', eg.group_id,
      'group', private.group_label(eg.group_id), 'title', ev.title, 'starts_at', ev.starts_at, 'all_day', ev.all_day,
      'date_mode', ev.date_mode, 'location_name', ev.location_name, 'cover_url', ev.cover_url,
      'description', left(coalesce(ev.description, ''), 280), 'organizer', private.person_label(coalesce(eg.requested_by, ev.created_by)),
      'requested_at', eg.created_at, 'announce', ev.announce_group,
      'members', (select count(*) from public.member_group_members m where m.group_id = eg.group_id))
    from public.event_groups eg join public.events ev on ev.id = eg.event_id
    where eg.status = 'pending' and ev.status = 'published' and private.may_approve_announcement(eg.group_id, auth.uid())
  ) t;
$$;
revoke all on function public.my_group_requests() from public, anon;
grant execute on function public.my_group_requests() to authenticated;

-- Statut des annonces d'un événement, pour son organisateur (fiche) : par groupe.
create or replace function public.event_announcement_status(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select case when not private.manages_event(e) then '[]'::jsonb else coalesce((
    select jsonb_agg(jsonb_build_object('group', private.group_label(x.group_id), 'status', x.status,
      'answered_by', case when x.answered_by is null then null else private.person_label(x.answered_by) end,
      'auto_at', x.auto_at) order by private.group_label(x.group_id))
    from (
      select a.group_id, a.status, a.answered_by, a.requested_at + interval '48 hours' auto_at
      from public.event_announcements a where a.event_id = e
      union all
      select eg.group_id, 'group_' || eg.status, eg.answered_by, null
      from public.event_groups eg where eg.event_id = e and eg.status <> 'approved'
    ) x), '[]'::jsonb) end;
$$;
revoke all on function public.event_announcement_status(uuid) from public, anon;
grant execute on function public.event_announcement_status(uuid) to authenticated;

-- Réglages du groupe : son créateur (ou un Co-admin et plus du site, comme set_group_admin ; Vendredi Party : eux seuls).
create or replace function private.may_set_group_rules(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and exists (select 1 from public.member_groups g where g.id = grp
    and (g.created_by = uid or private.is_root(uid) or private.rank_of(uid) >= private.role_rank('coadmin')));
$$;
revoke all on function private.may_set_group_rules(uuid, uuid) from public, anon, authenticated;

create or replace function public.set_group_event_rules(grp uuid, need_approval boolean, mode text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if mode is null or mode not in ('request', 'free') then raise exception 'Réglage inconnu'; end if;
  if not private.may_set_group_rules(grp, auth.uid()) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  update public.member_groups set events_need_approval = coalesce(need_approval, false), announce_mode = mode where id = grp;
end $$;
revoke all on function public.set_group_event_rules(uuid, boolean, text) from public, anon;
grant execute on function public.set_group_event_rules(uuid, boolean, text) to authenticated;

-- Seul le créateur change ces réglages (un admin du site par la politique « modifier son groupe » ne les touche pas).
create or replace function private.guard_group_event_rules() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null and (new.events_need_approval is distinct from old.events_need_approval or new.announce_mode is distinct from old.announce_mode)
     and not private.may_set_group_rules(old.id, auth.uid()) then
    new.events_need_approval := old.events_need_approval; new.announce_mode := old.announce_mode;
  end if;
  return new;
end $$;
revoke all on function private.guard_group_event_rules() from public, anon, authenticated;
drop trigger if exists member_groups_event_rules on public.member_groups;
create trigger member_groups_event_rules before update on public.member_groups
  for each row execute function private.guard_group_event_rules();

-- 9. Envoi : interrupteurs respectés par tous les canaux -------------------------------------------------------
do $$
declare
  def text := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  anchor text := '''private_invite'', ''event_changed''';
begin
  if position('announce_request' in def) = 0 and position(anchor in def) > 0 then
    execute replace(def, anchor, '''private_invite'', ''announce_request'', ''announce_accepted'', ''announce_refused'', '
      || '''group_event_request'', ''group_event_accepted'', ''group_event_refused'', ''event_changed''');
  end if;
end $$;

do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''direct_message'' then coalesce(prefs.direct_messages, true)';
begin
  if position('announce_request' in def) = 0 and position(anchor in def) > 0 then
    execute replace(def, anchor, anchor || '
    when ''announce_request'' then coalesce(prefs.announce_requests, true)
    when ''announce_accepted'' then coalesce(prefs.announce_results, true)
    when ''announce_refused'' then coalesce(prefs.announce_results, true)
    when ''group_event_request'' then coalesce(prefs.group_event_requests, true)
    when ''group_event_accepted'' then coalesce(prefs.announce_results, true)
    when ''group_event_refused'' then coalesce(prefs.announce_results, true)');
  end if;
end $$;

-- 10. Existant : les événements à venir qui ont déjà prévenu leur groupe gardent leur annonce (un nouveau membre du
-- groupe est invité comme avant) ; rien n'est envoyé ici.
do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'announcements_backfill_2026_11_06') then return; end if;
  insert into public.event_announcements (event_id, group_id, requested_by, status, requested_at, answered_at, sent_at)
    select ev.id, g.gid, ev.created_by, 'direct', coalesce(ev.approved_at, ev.created_at), coalesce(ev.approved_at, ev.created_at), coalesce(ev.approved_at, ev.created_at)
    from public.events ev
    cross join lateral (select eg.group_id gid from public.event_groups eg where eg.event_id = ev.id
                        union select private.vip_group_id() where ev.visibility = 'all') g
    where ev.status = 'published' and ev.notify_on_publish and not ev.public_link and g.gid is not null
      and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now()
  on conflict (event_id, group_id) do nothing;
  insert into private.one_time_changes (name) values ('announcements_backfill_2026_11_06');
end $$;


-- 11. « Prévenir le groupe » allumé après la publication (feuille « Inviter », fiche) par un organisateur, même sans le
-- droit de modifier un événement publié : seul ce réglage change (comme l'option des billets).
do $$
declare
  def text := pg_get_functiondef('public.guard_event()'::regprocedure);
  anchor text := '    -- Billets QR (04.11)';
begin
  if position('announce_group' in def) = 0 and position(anchor in def) > 0 then
    execute replace(def, anchor, '    -- Annonce au groupe (06.11) : seul « Prévenir le groupe » change → organisateurs et co-organisateurs.
    if (to_jsonb(new) - ''announce_group'' - ''updated_at'') = (to_jsonb(old) - ''announce_group'' - ''updated_at'')
       and public.is_organizer(new.id) then return new; end if;
' || anchor);
  end if;
end $$;

-- Pour l'écran : la demande partira-t-elle directement (valideur, groupe « libre ») ou sera-t-elle à valider ?
create or replace function public.my_announce_modes(groups uuid[]) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_object_agg(g, case when private.may_approve_announcement(g, auth.uid())
      or coalesce((select mg.announce_mode from public.member_groups mg where mg.id = g), 'request') = 'free'
    then 'direct' else 'request' end), '{}')
  from unnest(coalesce(groups, '{}')) g;
$$;
revoke all on function public.my_announce_modes(uuid[]) from public, anon;
grant execute on function public.my_announce_modes(uuid[]) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261106220000', 'annonces_groupe')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
