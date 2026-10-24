-- Rôles et droits réglables (Party web et app iOS).
-- Hiérarchie : root (un seul compte, fixé ici) > admin > co-admin > organisateur > membre > invité.
-- Chaque rôle sauf root a une liste de droits cochables ; personne ne donne un droit qu'il n'a pas,
-- ni ne touche à un rôle égal ou supérieur au sien. « Actif » veut désormais dire « compte utilisable »
-- (un invité est actif pour les jeux) ; être membre du groupe = avoir le droit « Voir les événements ».

-- ── Catalogue des droits ──
create table public.permissions (
  key text primary key,
  grp text not null,
  label text not null,
  hint text,
  sort int not null
);
alter table public.permissions enable row level security;
create policy "lire le catalogue des droits" on public.permissions for select to authenticated using (true);
insert into public.permissions (key, grp, label, hint, sort) values
  ('events.view',               'Événements', 'Voir les événements', 'Faire partie du groupe : sorties, sondages, discussions, annonces', 10),
  ('events.rsvp',               'Événements', 'Répondre aux sorties', 'Présent, peut-être, absent ; voter pour une date', 11),
  ('events.plus_ones',          'Événements', 'Amener des accompagnants', null, 12),
  ('events.create',             'Événements', 'Proposer une sortie', null, 13),
  ('events.publish_direct',     'Événements', 'Publier sans validation', 'Sinon la sortie attend qu''un admin la valide', 14),
  ('events.edit_own_published', 'Événements', 'Modifier ses sorties déjà publiées', null, 15),
  ('events.manage_all',         'Événements', 'Modifier ou annuler toutes les sorties', 'Aussi : sondages, objets à apporter et organisateurs de toutes les sorties', 16),
  ('events.approve',            'Événements', 'Valider les sorties proposées', null, 17),
  ('events.see_participants',   'Événements', 'Voir les participants même si la liste est masquée', null, 18),
  ('polls.create',              'Événements', 'Créer des sondages dans ses sorties', null, 19),
  ('chat.write',                'Événements', 'Écrire dans les discussions', null, 20),
  ('chat.moderate',             'Événements', 'Supprimer les messages des autres', null, 21),
  ('taxonomy.manage',           'Événements', 'Créer des catégories et des tags', null, 22),
  ('announcements.publish',     'Événements', 'Publier une annonce au groupe', null, 23),
  ('group.settings',            'Événements', 'Modifier les règles du groupe', null, 24),
  ('members.approve',           'Membres', 'Accepter ou refuser les demandes d''adhésion', null, 30),
  ('members.view_identity',     'Membres', 'Voir nom, prénom et numéro des membres', null, 31),
  ('members.roles',             'Membres', 'Changer le rôle des membres', 'Seulement pour les rôles en dessous du sien', 32),
  ('members.ban',               'Membres', 'Bannir ou réintégrer un compte', 'Seulement pour les rôles en dessous du sien', 33),
  ('roles.manage',              'Membres', 'Modifier les droits des rôles', 'Seulement pour les rôles en dessous du sien', 34),
  ('games.create',              'Jeux', 'Créer une partie', null, 40),
  ('games.lead_all',            'Jeux', 'Animer n''importe quelle partie', 'Exclure, bannir, passer la main', 41),
  ('games.close_all',           'Jeux', 'Voir et fermer toutes les parties', null, 42),
  ('music.add',                 'Musique', 'Ajouter des titres à la file', null, 50),
  ('music.manage_queue',        'Musique', 'Passer, retirer ou réordonner la file', null, 51),
  ('music.control',             'Musique', 'Lecture, volume, enceintes et playlists', null, 52),
  ('music.moderate',            'Musique', 'Bannir ou renommer un auditeur', null, 53),
  ('party.admin',               'Admin de Party', 'Ouvrir la page admin', null, 60),
  ('party.feedback',            'Admin de Party', 'Lire et traiter les retours (« Ton avis »)', null, 61),
  ('party.notify',              'Admin de Party', 'Envoyer une notification à tout le monde', null, 62),
  ('party.settings',            'Admin de Party', 'Réglages du site (code, Spotify, mode)', null, 63);
create table public.role_permissions (
  role public.member_role not null,
  perm text not null references public.permissions(key) on delete cascade,
  primary key (role, perm)
);
alter table public.role_permissions enable row level security;
create policy "lire les droits des rôles" on public.role_permissions for select to authenticated using (true);
-- Valeurs de départ (toutes modifiables ensuite).
insert into public.role_permissions (role, perm)
select r.role::public.member_role, p from (values
  ('admin',     array['events.view','events.rsvp','events.plus_ones','events.create','events.publish_direct','events.edit_own_published','events.manage_all','events.approve','events.see_participants','polls.create','chat.write','chat.moderate','taxonomy.manage','announcements.publish','group.settings','members.approve','members.view_identity','members.roles','members.ban','games.create','games.lead_all','games.close_all','music.add','music.manage_queue','music.control','music.moderate','party.admin','party.feedback','party.notify','party.settings']),
  ('coadmin',   array['events.view','events.rsvp','events.plus_ones','events.create','events.publish_direct','events.edit_own_published','events.manage_all','events.approve','events.see_participants','polls.create','chat.write','chat.moderate','taxonomy.manage','members.approve','members.view_identity','members.ban','games.create','games.lead_all','games.close_all','music.add','music.manage_queue','music.control','music.moderate','party.admin','party.feedback']),
  ('organizer', array['events.view','events.rsvp','events.plus_ones','events.create','events.publish_direct','events.edit_own_published','polls.create','chat.write','taxonomy.manage','games.create','music.add']),
  ('member',    array['events.view','events.rsvp','events.plus_ones','events.create','polls.create','chat.write','games.create','music.add']),
  ('guest',     array['games.create','music.add'])
) as r(role, perms), unnest(r.perms) as p;
-- ── Qui a quel droit ──
create or replace function private.is_root(uid uuid) returns boolean
language sql immutable set search_path = '' as $$
  select uid = '298ff6e0-07b2-4127-bb69-d254dd63a3d5'::uuid;  -- +41 76 557 69 00, le seul root
$$;
create or replace function private.role_rank(r public.member_role) returns int
language sql immutable set search_path = '' as $$
  select case r when 'guest' then 0 when 'member' then 1 when 'organizer' then 2 when 'coadmin' then 3 when 'admin' then 4 end;
$$;
create or replace function private.rank_of(uid uuid) returns int
language sql stable security definer set search_path = '' as $$
  select case when private.is_root(uid) then 99 else coalesce((select private.role_rank(role) from public.profiles where id = uid and status = 'active'), -1) end;
$$;
create or replace function private.user_has(uid uuid, perm text) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and (
    (private.is_root(uid) and exists (select 1 from public.profiles where id = uid and status = 'active'))
    or exists (select 1 from public.profiles p join public.role_permissions rp on rp.role = p.role
               where p.id = uid and p.status = 'active' and rp.perm = user_has.perm));
$$;
create or replace function private.is_member(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.user_has(uid, 'events.view');
$$;
create or replace function public.has_perm(perm text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.user_has(auth.uid(), perm);
$$;
-- Droits du compte connecté (pour les écrans et pour le serveur Party).
create or replace function public.my_permissions() returns text[]
language sql stable security definer set search_path = '' as $$
  select coalesce(array_agg(key order by sort), '{}') from public.permissions where private.user_has(auth.uid(), key);
$$;
create or replace function public.my_rank() returns int
language sql stable security definer set search_path = '' as $$
  select private.rank_of(auth.uid());
$$;
-- Cocher ou décocher un droit pour un rôle.
create or replace function public.set_role_permission(target public.member_role, perm text, granted boolean) returns void
language plpgsql security definer set search_path = '' as $$
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
$$;
revoke all on function public.set_role_permission(public.member_role, text, boolean) from public, anon;
grant execute on function public.set_role_permission(public.member_role, text, boolean) to authenticated;
-- ── Demandes d'adhésion (invité → membre), avec un message facultatif ──
create table public.join_requests (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  message text check (char_length(message) <= 500),
  status text not null default 'pending' check (status in ('pending', 'accepted', 'refused')),
  created_at timestamptz not null default now(),
  decided_by uuid references public.profiles(id) on delete set null,
  decided_at timestamptz
);
alter table public.join_requests enable row level security;
create policy "voir sa demande ou les demandes à traiter" on public.join_requests for select to authenticated
  using (user_id = (select auth.uid()) or (select public.has_perm('members.approve')));
create or replace function public.request_join(note text) returns void
language plpgsql security definer set search_path = '' as $$
declare me public.profiles;
begin
  select * into me from public.profiles where id = auth.uid();
  if me.id is null or me.status <> 'active' then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if me.role <> 'guest' then raise exception 'Tu fais déjà partie du groupe'; end if;
  if btrim(me.first_name) = '' or btrim(me.last_name) = '' or btrim(me.display_name) = '' or coalesce(me.avatar_url, '') = '' then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  insert into public.join_requests (user_id, message) values (me.id, nullif(btrim(note), ''))
  on conflict (user_id) do update set message = excluded.message, status = 'pending', created_at = now(), decided_by = null, decided_at = null
    where public.join_requests.status <> 'pending' or public.join_requests.message is distinct from excluded.message;
end;
$$;
create or replace function public.cancel_join_request() returns void
language sql security definer set search_path = '' as $$
  delete from public.join_requests where user_id = auth.uid() and status = 'pending';
$$;
create or replace function public.decide_join_request(member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    -- Le contrôle d'identité complète de guard_profile s'applique ici.
    update public.profiles set role = 'member' where id = member and role = 'guest';
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$$;
revoke all on function public.request_join(text), public.cancel_join_request(), public.decide_join_request(uuid, boolean) from public, anon;
grant execute on function public.request_join(text), public.cancel_join_request(), public.decide_join_request(uuid, boolean) to authenticated;
-- ── Les anciennes fonctions de rôle deviennent des droits ──
create or replace function public.is_active() returns boolean
language sql stable security definer set search_path = '' as $$
  select public.has_perm('events.view');  -- membre du groupe
$$;
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select public.has_perm('events.manage_all');
$$;
create or replace function public.can_participate(e uuid) returns boolean
language sql stable security definer set search_path = 'public' as $$
  select can_see_event(e) and has_perm('events.rsvp') and exists (select 1 from events where id = e and status = 'published');
$$;
create or replace function public.manages_members() returns boolean
language sql stable security definer set search_path = '' as $$
  select public.has_perm('members.approve') or public.has_perm('members.view_identity') or public.has_perm('members.roles') or public.has_perm('members.ban');
$$;
create or replace function private.member_directory() returns setof public.profiles
language sql stable security definer set search_path = '' as $$
  select p.id, p.display_name,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') then p.phone else null end,
    p.avatar_url, p.role, p.status, p.created_at,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') or public.has_perm('members.approve') then p.first_name else null end,
    case when p.id = auth.uid() or public.has_perm('members.view_identity') or public.has_perm('members.approve') then p.last_name else null end
  from public.profiles p
  where auth.uid() is not null and (p.id = auth.uid() or public.manages_members() or (public.is_active() and private.is_member(p.id)));
$$;
create or replace function public.approve_event(e uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
begin
  if not has_perm('events.approve') then raise exception 'Réservé à ceux qui valident les sorties'; end if;
  update events set status = 'published', approved_by = auth.uid(), approved_at = now(), rejection_reason = null
  where id = e and status in ('pending', 'rejected', 'draft');
end $$;
create or replace function public.reject_event(e uuid, reason text) returns void
language plpgsql security definer set search_path = 'public' as $$
begin
  if not has_perm('events.approve') then raise exception 'Réservé à ceux qui valident les sorties'; end if;
  update events set status = 'rejected', rejection_reason = reason where id = e and status = 'pending';
end $$;
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = 'public' as $$
begin
  -- Nouveau compte : invité (jeux, musique, profil) ; il demande ensuite à rejoindre le groupe.
  insert into profiles (id, phone, role, status) values (new.id, new.phone, 'guest', 'active');
  insert into notification_prefs (user_id) values (new.id);
  return new;
end $$;
-- Rôle et statut : selon les droits et le rang ; identité complète pour devenir membre ; le root est intouchable.
create or replace function public.guard_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); my_rank int := private.rank_of(auth.uid());
begin
  if private.is_root(old.id) then
    new.role := 'admin';
    new.status := 'active';
  elsif me is not null and not private.is_root(me) then
    if new.role is distinct from old.role then
      if not ((private.user_has(me, 'members.roles') and private.role_rank(old.role) < my_rank and private.role_rank(new.role) < my_rank)
              or (old.role = 'guest' and new.role = 'member' and private.user_has(me, 'members.approve'))) then
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
$$;
revoke all on function public.guard_profile() from public, anon, authenticated;
-- Sorties : publier sans validation et modifier une sortie publiée deviennent des droits.
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
  if old.status = 'published' then
    if new.status = 'cancelled' then return new; end if;
    if not has_perm('events.edit_own_published') then
      raise exception 'Seul un admin peut modifier une sortie publiée';
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
create or replace function public.guard_rsvp() returns trigger
language plpgsql security definer set search_path = 'public' as $$
declare ev events;
begin
  if tg_op = 'UPDATE' and new.status = old.status and new.plus_ones = old.plus_ones
     and new.note is not distinct from old.note then
    return new; -- seul `waitlisted` change (apply_waitlist)
  end if;
  select * into ev from events where id = new.event_id;
  if new.status = 'maybe' and not ev.allow_maybe then raise exception 'Réponse « Peut-être » désactivée'; end if;
  if not ev.allow_plus_ones or (auth.uid() is not null and not has_perm('events.plus_ones')) then new.plus_ones := 0;
  else new.plus_ones := least(new.plus_ones, ev.max_plus_ones); end if;
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline and auth.uid() is not null and not is_admin() then
    raise exception 'La date limite de réponse est passée';
  end if;
  new.updated_at := now();
  if tg_op = 'INSERT' or old.status <> 'yes' then new.waitlisted := true; end if;
  return new;
end $$;
-- ── Règles d'accès qui changent de sens ──
drop policy "admin catégories" on public.categories;
create policy "gérer les catégories" on public.categories for all to authenticated
  using ((select public.has_perm('taxonomy.manage'))) with check ((select public.has_perm('taxonomy.manage')));
drop policy "admin tags" on public.tags;
create policy "gérer les tags" on public.tags for all to authenticated
  using ((select public.has_perm('taxonomy.manage'))) with check ((select public.has_perm('taxonomy.manage')));
drop policy "membres créent tags" on public.tags;
drop policy "admin réglages" on public.group_settings;
create policy "modifier les règles du groupe" on public.group_settings for update to authenticated using ((select public.has_perm('group.settings')));
drop policy "proposer événement" on public.events;
create policy "proposer événement" on public.events for insert to authenticated with check ((select public.has_perm('events.create')));
drop policy "supprimer message" on public.messages;
create policy "supprimer message" on public.messages for delete to authenticated
  using (user_id = (select auth.uid()) or (select public.has_perm('chat.moderate')));
drop policy "écrire message" on public.messages;
create policy "écrire message" on public.messages for insert to authenticated
  with check (user_id = (select auth.uid()) and can_participate(event_id) and (select public.has_perm('chat.write'))
    and (select events.forum_enabled from public.events where events.id = messages.event_id));
drop policy "créer sondage" on public.polls;
create policy "créer sondage" on public.polls for insert to authenticated
  with check (created_by = (select auth.uid()) and (is_admin() or (is_organizer(event_id) and (select public.has_perm('polls.create')))));
drop policy "voir réponses" on public.rsvps;
create policy "voir réponses" on public.rsvps for select to authenticated
  using (user_id = (select auth.uid()) or is_admin() or is_organizer(event_id)
    or (can_see_event(event_id) and ((select events.show_participants from public.events where events.id = rsvps.event_id) or (select public.has_perm('events.see_participants')))));
drop policy "modifier son profil" on public.profiles;
create policy "modifier son profil" on public.profiles for update to authenticated
  using (id = (select auth.uid()) or (select public.has_perm('members.roles')) or (select public.has_perm('members.ban')) or (select public.has_perm('members.approve')));
drop policy "photos du groupe autorisé" on storage.objects;
create policy "photos du groupe autorisé" on storage.objects for select to authenticated
using (bucket_id = 'profile-photos' and (
  (storage.foldername(name))[1] = (select auth.uid())::text
  or (select public.manages_members())
  or ((select public.is_active()) and exists (select 1 from public.profiles p where p.status = 'active' and p.avatar_url = name))
));
-- Les règles d'accès n'appellent que des fonctions publiques (le schéma private reste fermé aux membres).
revoke all on function public.has_perm(text), public.my_permissions(), public.my_rank(), public.manages_members() from public, anon;
grant execute on function public.has_perm(text), public.my_permissions(), public.my_rank(), public.manages_members() to authenticated;
revoke all on function private.is_root(uuid), private.role_rank(public.member_role), private.rank_of(uuid), private.user_has(uuid, text), private.is_member(uuid) from public, anon, authenticated;
-- ── Notifications : seuls les membres du groupe (droit « Voir les événements ») reçoivent celles du groupe ──
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
    if new.notify_on_publish then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where private.is_member(p.id) and p.id <> new.created_by
          and (new.visibility = 'all' or exists (select 1 from event_invites i where i.event_id = new.id and i.user_id = p.id))
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
CREATE OR REPLACE FUNCTION public.notify_message()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare ev events; who text; reply_author uuid; u uuid; np notification_prefs;
begin
  select * into ev from events where id = new.event_id;
  select display_name into who from profiles where id = new.user_id;
  select user_id into reply_author from messages where id = new.reply_to;
  for u in select distinct x from (
      select a x from event_audience(ev.id) a
      union select user_id from messages where event_id = ev.id
      union select unnest(new.mentions)
    ) s
    where x not in (select user_id from event_mutes where event_id = ev.id)
      and exists(select 1 from profiles p where p.id=x and private.is_member(p.id) and (
        private.user_has(p.id, 'events.manage_all') or ev.created_by=x
        or exists(select 1 from event_organizers where event_id=ev.id and user_id=x)
        or (ev.status in ('published','cancelled') and (ev.visibility='all'
          or exists(select 1 from event_invites where event_id=ev.id and user_id=x))))) loop
    select * into np from notification_prefs where user_id = u;
    if np.chat = 'all' or (np.chat = 'mentions' and (u = any (new.mentions) or u = reply_author)) then
      perform queue_notification(u, 'message', ev.id, ev.title, who || ' : ' || left(new.body, 140), null, jsonb_build_object('mentioned', u=any(new.mentions) or u=reply_author));
    end if;
  end loop;
  return null;
end $function$;
CREATE OR REPLACE FUNCTION public.run_scheduled_jobs()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare ev events; r record; best uuid;
begin
  -- Rappels avant l'événement
  for r in
    select e.id, e.title, e.starts_at, off, a.uid
    from events e
    cross join lateral unnest(e.reminders) off
    cross join lateral (select user_id uid from rsvps where event_id = e.id and status in ('yes', 'maybe') and not waitlisted) a
    join notification_prefs np on np.user_id = a.uid
    cross join lateral (select case off when '7d' then interval '7 days' when '1d' then interval '1 day'
                                        when '2h' then interval '2 hours' else interval '0' end iv) w
    where e.status = 'published' and e.starts_at > now() - interval '30 minutes'
      and off = any (np.reminders)
      and a.uid not in (select user_id from event_mutes where event_id = e.id)
      and now() between e.starts_at - w.iv and e.starts_at - w.iv + interval '30 minutes'
  loop
    perform queue_notification(r.uid, 'reminder', r.id,
      case r.off when '7d' then 'Dans une semaine' when '1d' then 'C''est demain' when '2h' then 'Dans 2 heures' else 'C''est maintenant' end,
      r.title || ' · ' || to_char(r.starts_at at time zone 'Europe/Zurich', 'DD.MM HH24:MI'),
      'reminder:' || r.id || ':' || r.off);
  end loop;

  -- Relance 24 h avant la fin d'un sondage de dates
  for r in
    select e.id, e.title, p.id uid from events e cross join profiles p
    join notification_prefs np on np.user_id = p.id
    where e.status = 'published' and e.date_mode = 'poll' and e.poll_deadline between now() and now() + interval '24 hours'
      and private.is_member(p.id) and np.poll_nudge
      and (e.visibility = 'all' or exists (select 1 from event_invites i where i.event_id = e.id and i.user_id = p.id))
      and not exists (select 1 from date_votes v join date_options o on o.id = v.option_id where o.event_id = e.id and v.user_id = p.id)
  loop
    perform queue_notification(r.uid, 'poll_nudge', r.id, 'Plus que 24 h pour voter', r.title, 'poll_nudge:' || r.id);
  end loop;

  -- Clôture automatique : la date avec le plus de Oui (Si besoin = départage)
  for ev in select * from events where status = 'published' and date_mode = 'poll' and auto_fix_date and poll_deadline <= now() loop
    select o.id into best from date_options o left join date_votes v on v.option_id = o.id
    where o.event_id = ev.id group by o.id, o.starts_at
    order by count(*) filter (where v.vote = 'yes') desc, count(*) filter (where v.vote = 'if_needed') desc, o.starts_at
    limit 1;
    if best is not null then perform do_fix_event_date(ev.id, best); end if;
  end loop;
end $function$;
CREATE OR REPLACE FUNCTION public.claim_push_deliveries(batch_size integer DEFAULT 100)
 RETURNS TABLE(delivery_id uuid, notification_id uuid, user_id uuid, token text, attempts integer, title text, body text, data jsonb)
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
  with chosen as (
    select d.id from public.notification_deliveries d join public.notifications n on n.id=d.notification_id
    join public.notification_prefs p on p.user_id=n.user_id
    where d.status='queued' and d.next_attempt_at<=now() and (d.lease_until is null or d.lease_until<now())
      and not n.skipped and p.push_enabled and not private.push_is_quiet(p.quiet_start,p.quiet_end)
      and exists(select 1 from public.profiles p where p.id=n.user_id and private.is_member(p.id))
      and exists(select 1 from public.push_tokens t where t.token=d.token and t.user_id=n.user_id and t.session_id is not null)
    order by d.next_attempt_at,d.id limit greatest(1,least(coalesce(batch_size,100),100)) for update of d skip locked
  ), claimed as (
    update public.notification_deliveries d set lease_until=now()+interval '2 minutes', attempts=d.attempts+1
      from chosen c where d.id=c.id returning d.*
  )
  select d.id,d.notification_id,n.user_id,d.token,d.attempts,n.title,n.body,n.data
    from claimed d join public.notifications n on n.id=d.notification_id;
$function$;
CREATE OR REPLACE FUNCTION public.prepare_push_deliveries()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  update public.notifications n set skipped=true where n.sent_at is null and not n.skipped
    and (not exists(select 1 from public.profiles p where p.id=n.user_id and private.is_member(p.id))
      or not exists(select 1 from public.notification_prefs p where p.user_id=n.user_id and p.push_enabled)
      or not exists(select 1 from public.push_tokens t where t.user_id=n.user_id and t.session_id is not null));
  update public.notification_deliveries d set status='failed', error='DeviceUnavailable', lease_until=null
    from public.notifications n where n.id=d.notification_id and d.status='queued'
      and (n.skipped or not exists(select 1 from public.push_tokens t where t.user_id=n.user_id and t.token=d.token and t.session_id is not null));
  insert into public.notification_deliveries(notification_id,token)
    select n.id,t.token from public.notifications n join public.push_tokens t on t.user_id=n.user_id
    where n.sent_at is null and not n.skipped and t.session_id is not null
    on conflict(notification_id,token) do nothing;
end;
$function$;
CREATE OR REPLACE FUNCTION private.web_push_allowed(notification notifications)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare prefs public.notification_prefs; ev public.events;
begin
  if not exists(select 1 from public.profiles where id=notification.user_id and private.is_member(id)) then return false; end if;
  if notification.kind='admin_announcement' then
    return exists(select 1 from public.admin_announcements where id::text=notification.data->>'announcement_id');
  end if;
  if notification.kind='web_push_test' then return true; end if;
  select * into prefs from public.notification_prefs where user_id=notification.user_id;
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
    else true end;
end $function$;
CREATE OR REPLACE FUNCTION private.publish_admin_announcement(announcement_title text, announcement_body text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare result uuid; headline text:=btrim(announcement_title); content text:=btrim(announcement_body);
begin
  if auth.uid() is null or not public.has_perm('announcements.publish') then raise exception 'Accès admin requis' using errcode='42501'; end if;
  if headline is null or length(headline) not between 1 and 120 or content is null or length(content) not between 1 and 4000 then
    raise exception 'Renseigne un titre (120 caractères maximum) et un message (4000 maximum)';
  end if;
  perform pg_advisory_xact_lock(hashtext('admin-announcements'));
  -- Une reprise après une réponse réseau perdue ne publie pas deux fois la même annonce.
  select id into result from public.admin_announcements where created_by=auth.uid()
    and title=headline and body=content and created_at>now()-interval '5 minutes' order by created_at desc limit 1;
  if result is not null then return result; end if;
  if (select count(*) from public.admin_announcements where created_at>now()-interval '1 minute')>=5 then
    raise exception 'Attends une minute avant de publier une autre annonce';
  end if;
  insert into public.admin_announcements(title,body,created_by) values(headline,content,auth.uid()) returning id into result;
  insert into public.notifications(user_id,kind,title,body,dedupe_key,data)
    select id,'admin_announcement',headline,content,'announcement:'||result,
      jsonb_build_object('kind','admin_announcement','announcement_id',result)
    from public.profiles where private.is_member(id);
  return result;
end $function$;
-- ── Comptes existants ──
-- Les demandes en attente deviennent des invités (ils jouent tout de suite) avec leur demande d'adhésion ouverte.
-- Le contrôle d'identité est suspendu le temps de cette conversion : il s'appliquera à leur acceptation.
alter table public.profiles disable trigger profiles_guard;
insert into public.join_requests (user_id, created_at) select id, created_at from public.profiles where status = 'pending' on conflict do nothing;
update public.profiles set role = 'guest', status = 'active' where status = 'pending';
update public.profiles set role = 'admin', status = 'active' where private.is_root(id);
alter table public.profiles enable trigger profiles_guard;
