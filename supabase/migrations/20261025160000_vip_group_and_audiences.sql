-- Groupe « Vendredi Party » = Membres VIP et au-dessus, et qui voit quelle sortie (décisions du 25.10.2026) :
--   Publique (visibility 'all' + public_link) : tous les comptes actifs, Guests compris, et le lien public ;
--   Vendredi Party (visibility 'all' sans lien) : le groupe VIP, plus les personnes ajoutées une à une ;
--   Sur invitation (visibility 'invited') : groupes choisis, plus les personnes ajoutées une à une.
-- Personnes ajoutées : un compte (event_invites, via_group = false) ou un numéro de téléphone
-- (event_phone_invites) — le numéro voit la sortie dès qu'il a un compte, sans révéler s'il en a déjà un.
-- Un compte qui voit une sortie y participe comme un invité (répondre, voter, écrire) : droits events.rsvp
-- et chat.write donnés au rôle Guest, la visibilité restant contrôlée par can_see_event.
-- Purement additive et rejouable.

-- ── Groupe système « Vendredi Party » ──
alter table public.member_groups add column if not exists system_key text unique;
insert into public.member_groups (name, created_by, system_key)
select 'Vendredi Party', null, 'vip' where not exists (select 1 from public.member_groups where system_key = 'vip');

create or replace function private.vip_group_id() returns uuid
language sql stable security definer set search_path = '' as $$
  select id from public.member_groups where system_key = 'vip';
$$;

create or replace function private.is_account_active(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and exists (select 1 from public.profiles where id = uid and status = 'active');
$$;
revoke all on function private.vip_group_id(), private.is_account_active(uuid) from public, anon;
-- Appelée directement par les règles de lecture (catégories, tags) avec les droits du compte connecté.
grant execute on function private.is_account_active(uuid) to authenticated;

-- Le groupe suit le statut : VIP et au-dessus (compte actif) dedans, Guest ou accès retiré dehors.
create or replace function private.sync_vip_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g uuid := private.vip_group_id();
begin
  if g is null then return null; end if;
  if private.rank_of(new.id) >= 1 then
    insert into public.member_group_members (group_id, user_id) values (g, new.id) on conflict do nothing;
  else
    delete from public.member_group_members where group_id = g and user_id = new.id;
  end if;
  return null;
end $$;
drop trigger if exists sync_vip_member on public.profiles;
create trigger sync_vip_member after insert or update of role, status on public.profiles
for each row execute function private.sync_vip_member();
revoke all on function private.sync_vip_member() from public, anon, authenticated;

insert into public.member_group_members (group_id, user_id)
select private.vip_group_id(), p.id from public.profiles p where private.rank_of(p.id) >= 1
on conflict do nothing;

-- Le groupe système ne se renomme pas, ne se supprime pas et ne se compose pas à la main (seulement par le statut).
drop policy if exists "modifier son groupe" on public.member_groups;
create policy "modifier son groupe" on public.member_groups for update to authenticated
  using (system_key is null and (created_by = (select auth.uid()) or (select public.is_admin())));
drop policy if exists "supprimer son groupe" on public.member_groups;
create policy "supprimer son groupe" on public.member_groups for delete to authenticated
  using (system_key is null and (created_by = (select auth.uid()) or (select public.is_admin())));
drop policy if exists "composer son groupe" on public.member_group_members;
create policy "composer son groupe" on public.member_group_members for all to authenticated
  using (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                 and (g.created_by = (select auth.uid()) or (select public.is_admin()))))
  with check (exists (select 1 from public.member_groups g where g.id = group_id and g.system_key is null
                      and (g.created_by = (select auth.uid()) or (select public.is_admin()))));

-- ── Invitations par numéro de téléphone ──
create table if not exists public.event_phone_invites (
  event_id uuid not null references public.events (id) on delete cascade,
  phone text not null check (phone ~ '^[1-9][0-9]{7,14}$'),  -- format d'Auth : indicatif + numéro, sans « + »
  invited_by uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (event_id, phone)
);
create index if not exists event_phone_invites_phone on public.event_phone_invites (phone);
alter table public.event_phone_invites enable row level security;
revoke all on public.event_phone_invites from anon;
grant select, insert, delete on public.event_phone_invites to authenticated;
drop policy if exists "voir les numéros invités" on public.event_phone_invites;
create policy "voir les numéros invités" on public.event_phone_invites for select to authenticated
  using (public.is_admin() or public.is_organizer(event_id));
drop policy if exists "inviter par numéro" on public.event_phone_invites;
create policy "inviter par numéro" on public.event_phone_invites for insert to authenticated
  with check (invited_by = (select auth.uid()) and (public.is_admin() or public.is_organizer(event_id)));
drop policy if exists "retirer un numéro invité" on public.event_phone_invites;
create policy "retirer un numéro invité" on public.event_phone_invites for delete to authenticated
  using (public.is_admin() or public.is_organizer(event_id));

create or replace function private.invited_by_phone(e uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.event_phone_invites pi join public.profiles p on p.phone = pi.phone
                 where pi.event_id = e and p.id = uid);
$$;
revoke all on function private.invited_by_phone(uuid, uuid) from public, anon;

-- ── Qui voit une sortie ──
create or replace function public.can_see_event(e uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select is_admin() or is_organizer(e) or exists (
    select 1 from events ev
    where ev.id = e and ev.status in ('published', 'cancelled') and private.is_account_active(auth.uid())
      and ((ev.visibility = 'all' and (ev.public_link or is_active()))
           or exists (select 1 from event_invites i where i.event_id = e and i.user_id = auth.uid())
           or private.invited_by_phone(e, auth.uid()))
  );
$$;

-- Participer comme un invité : le rôle Guest peut répondre et écrire (là où il voit la sortie).
insert into public.role_permissions (role, perm)
select 'guest', p from unnest(array['events.rsvp', 'chat.write']) as p
where exists (select 1 from public.permissions where key = p)
on conflict do nothing;

-- Catégories et tags : lisibles par tout compte actif (cartes des sorties publiques).
drop policy if exists "lire catégories" on public.categories;
create policy "lire catégories" on public.categories for select to authenticated
  using (public.is_active() or private.is_account_active(auth.uid()));
drop policy if exists "lire tags" on public.tags;
create policy "lire tags" on public.tags for select to authenticated
  using (public.is_active() or private.is_account_active(auth.uid()));

-- Surnom et photo des personnes d'une sortie que l'on voit (le numéro, le prénom et le nom restent illisibles :
-- droits de colonnes). Les membres voient déjà tous les profils.
drop policy if exists "profils des participants" on public.profiles;
create policy "profils des participants" on public.profiles for select to authenticated using (
  not public.is_active() and (
    exists (select 1 from public.rsvps r where r.user_id = profiles.id and public.can_see_event(r.event_id))
    or exists (select 1 from public.events ev where ev.created_by = profiles.id and public.can_see_event(ev.id))
    or exists (select 1 from public.event_organizers o where o.user_id = profiles.id and public.can_see_event(o.event_id))
    or exists (select 1 from public.messages m where m.user_id = profiles.id and public.can_see_event(m.event_id))));

-- ── Notifications ──
-- Invitation : à tout compte actif (Guests compris), jamais au créateur.
create or replace function private.queue_private_invite(ev public.events, u uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare via text;
begin
  if u = ev.created_by or not private.is_account_active(u) then return; end if;
  select string_agg(g.name, ', ' order by g.name) into via
    from public.event_groups eg
    join public.member_groups g on g.id = eg.group_id
    join public.member_group_members gm on gm.group_id = g.id and gm.user_id = u
    where eg.event_id = ev.id;
  perform public.queue_notification(u, 'private_invite', ev.id, '🔒 Invitation à un événement privé',
    'On t’invite à « ' || ev.title || ' »' || coalesce(' avec le groupe ' || via, '') || '.',
    'private_invite:' || ev.id);
end $$;

-- Sortie déjà publiée : un invité ajouté reçoit son invitation (les membres d'une sortie Vendredi Party ont
-- déjà eu « Nouvel événement »).
create or replace function private.should_invite(ev public.events, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select ev.status = 'published' and ev.notify_on_publish and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now()
     and (ev.visibility = 'invited' or (ev.visibility = 'all' and not private.is_member(u)));
$$;
create or replace function private.on_event_invite() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  select * into ev from public.events where id = new.event_id;
  if private.should_invite(ev, new.user_id) then perform private.queue_private_invite(ev, new.user_id); end if;
  return null;
end $$;
create or replace function private.on_event_phone_invite() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events; u uuid;
begin
  select * into ev from public.events where id = new.event_id;
  for u in select p.id from public.profiles p where p.phone = new.phone loop
    if private.should_invite(ev, u) then perform private.queue_private_invite(ev, u); end if;
  end loop;
  return null;
end $$;
drop trigger if exists event_phone_invites_notify on public.event_phone_invites;
create trigger event_phone_invites_notify after insert on public.event_phone_invites
for each row execute function private.on_event_phone_invite();
-- Nouveau compte : les sorties à venir où son numéro était invité lui arrivent tout de suite.
create or replace function private.on_new_account_phone_invites() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  if new.phone is null then return null; end if;
  for ev in select e.* from public.events e join public.event_phone_invites pi on pi.event_id = e.id where pi.phone = new.phone loop
    if private.should_invite(ev, new.id) then perform private.queue_private_invite(ev, new.id); end if;
  end loop;
  return null;
end $$;
drop trigger if exists new_account_phone_invites on public.profiles;
create trigger new_account_phone_invites after insert on public.profiles
for each row execute function private.on_new_account_phone_invites();
revoke all on function private.invited_by_phone(uuid, uuid), private.should_invite(public.events, uuid), private.on_event_phone_invite(),
  private.on_new_account_phone_invites(), private.queue_private_invite(public.events, uuid), private.on_event_invite()
  from public, anon, authenticated;

-- Publication : « Nouvel événement » au groupe (et aux Guests bêta-testeurs pour une sortie publique),
-- invitation aux personnes ajoutées hors groupe.
create or replace function public.notify_event_change() returns trigger
language plpgsql security definer set search_path to 'public' as $function$
declare u uuid; tag_ids uuid[];
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
    if new.notify_on_publish then
      for u in select i.user_id from event_invites i where i.event_id = new.id
               union select p.id from event_phone_invites pi join profiles p on p.phone = pi.phone where pi.event_id = new.id loop
        if private.should_invite(new, u) then perform private.queue_private_invite(new, u); end if;
      end loop;
    end if;
    if new.notify_on_publish and new.visibility = 'all' then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where p.id <> new.created_by and p.status = 'active'
          and (private.is_member(p.id)
               or (new.public_link and exists (select 1 from beta_testers b where b.user_id = p.id)))
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
