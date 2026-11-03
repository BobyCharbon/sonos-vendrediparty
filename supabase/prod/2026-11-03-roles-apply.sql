-- PROD, custom_roles (20261103140000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration. Rejouable.
-- À appliquer APRÈS 2026-11-03-billets-presents-apply.sql (20261103130000) : reprend ses fonctions de scan et de paiement.
-- Change le type de profiles.role et role_permissions.role (énumération → texte, mêmes valeurs) : tout ou rien (begin/commit).
begin;
-- Rôles personnalisés et droit « Scanner les billets » (demande de l'admin du 3 novembre 2026) :
-- « il faudrait créer un droit [pour scanner les billets]. D'ailleurs, il faudrait que je puisse rajouter des rôles aussi
--   directement depuis l'app facilement et gérer les accès. J'aimerais aussi pouvoir réorganiser les rôles si besoin. »
--
-- 1. Droits tickets.scan (scanner, noter les arrivées) et tickets.pay (« payé », « Reçu ») sur TOUS les événements
--    (l'organisateur, les co-organisateurs et les admins le font déjà pour les leurs) : voir la partie 5.
-- 2. Les rôles quittent l'énumération figée public.member_role pour une table public.roles (clé, nom, couleur, icône,
--    rang). Le rang = la place dans la liste (0 = le plus bas) : réordonner les rôles change la hiérarchie.
--    · profiles.role et role_permissions.role passent en texte (mêmes valeurs), reliés à public.roles ;
--    · les 7 rôles existants gardent leur clé (guest, guestplus, basic, member, organizer, coadmin, admin) et leur ordre ;
--      ils ne se suppriment pas (ils servent au code : nouveaux comptes Guest, Membre VIP = Vendredi Party, Admin) ;
--      Admin reste toujours en haut, Guest toujours en bas ;
--    · les seuils codés en dur (rang ≥ 1, ≥ 3, ≥ 4, > 0) deviennent « au moins Membre VIP / Co-admin / Admin », lus
--      dans la table : ils suivent les rôles quand on les réordonne ;
--    · gestion par fonctions seulement (droit roles.manage) : créer, renommer / couleur / icône, réordonner,
--      supprimer (en réaffectant ses membres ; il faut en plus le droit roles.delete) ; toujours seulement les rôles en dessous du sien ; un rôle ne reçoit que
--      des droits qu'on a soi-même ; personne ne touche à son propre rôle (donc ne se retire jamais roles.manage).
--    Le type public.member_role reste (inutilisé) pour le retour arrière.
-- Rejouable : chaque étape vérifie l'état avant d'agir.

-- --------------------------------------------------------------------------------------------------------------
-- 1. Table des rôles
-- --------------------------------------------------------------------------------------------------------------
create table if not exists public.roles (
  key text primary key check (key ~ '^[a-z][a-z0-9_]{1,30}$'),
  label text not null check (char_length(btrim(label)) between 1 and 30),
  color text check (color ~ '^#[0-9A-Fa-f]{6}$'),
  icon text check (char_length(icon) between 1 and 8),
  rank int not null check (rank between 0 and 98),
  builtin boolean not null default false,
  created_at timestamptz not null default now()
);
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'roles_rank_unique') then
    -- Différée : réordonner échange des rangs dans une seule requête.
    alter table public.roles add constraint roles_rank_unique unique (rank) deferrable initially deferred;
  end if;
end $$;
create unique index if not exists roles_label_unique on public.roles (lower(btrim(label)));
alter table public.roles enable row level security;
drop policy if exists "lire les rôles" on public.roles;
create policy "lire les rôles" on public.roles for select to authenticated using (true);
revoke insert, update, delete, truncate on public.roles from public, anon, authenticated;
grant select on public.roles to authenticated;

insert into public.roles (key, label, color, rank, builtin) values
  ('guest',     'Guest',        '#8E8E93', 0, true),
  ('guestplus', 'Guest+',       '#A2845E', 1, true),
  ('basic',     'Membre',       '#5AC8FA', 2, true),
  ('member',    'Membre VIP',   '#34C759', 3, true),
  ('organizer', 'Organisateur', '#FF9500', 4, true),
  ('coadmin',   'Co-admin',     '#AF52DE', 5, true),
  ('admin',     'Admin',        '#FF3B30', 6, true)
on conflict (key) do nothing;

-- --------------------------------------------------------------------------------------------------------------
-- 2. profiles.role et role_permissions.role : énumération → texte relié à public.roles
-- --------------------------------------------------------------------------------------------------------------
-- Les déclencheurs « update of role » empêchent de changer le type de la colonne : retirés puis remis à l'identique.
drop trigger if exists audit_profile on public.profiles;
drop trigger if exists profiles_last_admin on public.profiles;
drop trigger if exists sync_vip_member on public.profiles;
do $$
begin
  if (select data_type from information_schema.columns
      where table_schema = 'public' and table_name = 'profiles' and column_name = 'role') = 'USER-DEFINED' then
    alter table public.profiles alter column role drop default;
    alter table public.profiles alter column role type text using role::text;
    alter table public.profiles alter column role set default 'member';  -- même défaut qu'avant (les comptes créés par handle_new_user sont Guest)
  end if;
  if (select data_type from information_schema.columns
      where table_schema = 'public' and table_name = 'role_permissions' and column_name = 'role') = 'USER-DEFINED' then
    alter table public.role_permissions alter column role type text using role::text;
  end if;
  if not exists (select 1 from pg_constraint where conname = 'profiles_role_fkey') then
    alter table public.profiles add constraint profiles_role_fkey foreign key (role) references public.roles (key) on update cascade;
  end if;
  if not exists (select 1 from pg_constraint where conname = 'role_permissions_role_fkey') then
    alter table public.role_permissions add constraint role_permissions_role_fkey
      foreign key (role) references public.roles (key) on update cascade on delete cascade;
  end if;
end $$;
create trigger audit_profile after insert or update of role, status on public.profiles
  for each row execute function private.audit_profile();
create trigger profiles_last_admin before update of role, status on public.profiles
  for each row execute function private.protect_last_admin();
create trigger sync_vip_member after insert or update of role, status on public.profiles
  for each row execute function private.sync_vip_member();

-- --------------------------------------------------------------------------------------------------------------
-- 3. Rangs lus dans la table, seuils par rôle
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.role_rank(r text) returns integer
language sql stable security definer set search_path = '' as $$
  select rank from public.roles where key = r;
$$;
drop function if exists private.role_rank(public.member_role);
revoke all on function private.role_rank(text) from public, anon, authenticated;

create or replace function private.rank_of(uid uuid) returns integer
language sql stable security definer set search_path = '' as $$
  select case when private.is_root(uid) then 99 else coalesce((select private.role_rank(role) from public.profiles where id = uid and status = 'active'), -1) end;
$$;

-- Admin (et Root) : liste complète, journal, suppression de comptes.
create or replace function private.is_member_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and coalesce(public.my_rank(), -1) >= private.role_rank('admin');
$$;

-- Membre VIP et au-dessus : dans le groupe Vendredi Party.
create or replace function private.sync_vip_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g uuid := private.vip_group_id();
begin
  if g is null then return null; end if;
  if private.rank_of(new.id) >= private.role_rank('member') then
    insert into public.member_group_members (group_id, user_id) values (g, new.id) on conflict do nothing;
  else
    delete from public.member_group_members where group_id = g and user_id = new.id;
  end if;
  return null;
end $$;

-- Après un changement d'ordre ou une suppression de rôle : le groupe Vendredi Party suit la nouvelle hiérarchie.
create or replace function private.resync_vip_members() returns void
language plpgsql security definer set search_path = '' as $$
declare g uuid := private.vip_group_id(); vip int := private.role_rank('member');
begin
  if g is null then return; end if;
  insert into public.member_group_members (group_id, user_id)
    select g, p.id from public.profiles p where private.rank_of(p.id) >= vip
  on conflict do nothing;
  delete from public.member_group_members m where m.group_id = g and private.rank_of(m.user_id) < vip;
end $$;
revoke all on function private.resync_vip_members() from public, anon, authenticated;

create or replace function private.group_admin(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and (
    private.is_root(uid)
    or exists (select 1 from public.member_groups g where g.id = grp and g.created_by = uid)
    or (private.in_group_now(grp, uid) and (
          exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid)
          or private.rank_of(uid) >= private.role_rank('coadmin'))));  -- co-admins du site et au-dessus : admins d'office de leurs groupes
$$;

create or replace function public.set_group_admin(grp uuid, member uuid, admin boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select 1 from public.member_groups g where g.id = grp
                 and (g.created_by = auth.uid() or private.is_root(auth.uid()) or private.rank_of(auth.uid()) >= private.role_rank('coadmin'))) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  if not private.in_group_now(grp, member) then raise exception 'Cette personne n''est pas dans le groupe'; end if;
  if admin then
    insert into public.group_admins (group_id, user_id) values (grp, member) on conflict do nothing;
  else
    delete from public.group_admins where group_id = grp and user_id = member;
  end if;
end $$;

-- Rôles sous Membre VIP (Guest, Guest+, Membre et les rôles personnalisés placés dessous) : peuvent demander à
-- rejoindre Vendredi Party ; acceptés, ils passent Membre VIP.
create or replace function private.below_vip(r text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(private.role_rank(r) < private.role_rank('member'), false);
$$;
revoke all on function private.below_vip(text) from public, anon, authenticated;

create or replace function public.request_join(note text) returns void
language plpgsql security definer set search_path = '' as $$
declare me public.profiles;
begin
  select * into me from public.profiles where id = auth.uid();
  if me.id is null or me.status <> 'active' then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if not private.below_vip(me.role) then raise exception 'Tu fais déjà partie du groupe'; end if;
  if btrim(me.first_name) = '' or btrim(me.last_name) = '' or btrim(me.display_name) = '' or coalesce(me.avatar_url, '') = '' then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  insert into public.join_requests (user_id, message) values (me.id, nullif(btrim(note), ''))
  on conflict (user_id) do update set message = excluded.message, status = 'pending', created_at = now(), decided_by = null, decided_at = null
    where public.join_requests.status <> 'pending' or public.join_requests.message is distinct from excluded.message;
end;
$$;

create or replace function public.decide_join_request(member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    -- Le contrôle d'identité complète de guard_profile s'applique ici.
    update public.profiles set role = 'member' where id = member and private.below_vip(role);
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$$;

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
              or (private.below_vip(old.role) and new.role = 'member' and private.user_has(me, 'members.approve'))) then
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

  -- Toute identité renseignée reste complète, et on ne devient Membre VIP (ou plus) qu'avec une identité complète.
  if (new.first_name <> '' or new.last_name <> '' or old.first_name <> '' or old.last_name <> ''
      or (not private.below_vip(new.role) and new.role is distinct from old.role))
     and (new.first_name = '' or new.last_name = '' or new.display_name = ''
       or not exists (select 1 from storage.objects o where o.bucket_id = 'profile-photos'
         and o.name = new.avatar_url and (storage.foldername(o.name))[1] = new.id::text)) then
    raise exception 'profile_incomplete: nom, prénom, surnom et photo obligatoires avant validation' using errcode = '23514';
  end if;
  return new;
end;
$$;
revoke all on function public.guard_profile() from public, anon, authenticated;

-- Fiche d'un membre : le nom et la couleur du rôle en plus de sa clé (rôles personnalisés).
create or replace function public.member_card(target uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
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
    'role_label', (select r.label from public.roles r where r.key = p.role),
    'role_color', (select r.color from public.roles r where r.key = p.role),
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
end $$;

-- --------------------------------------------------------------------------------------------------------------
-- 4. Gestion des rôles (droit roles.manage, toujours en dessous de son propre rang)
-- --------------------------------------------------------------------------------------------------------------
create or replace function private.require_roles_manager() returns integer
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null or not (private.is_root(me) or private.user_has(me, 'roles.manage')) then
    raise exception 'forbidden: tu ne peux pas gérer les rôles' using errcode = '42501';
  end if;
  return private.rank_of(me);
end $$;

create or replace function private.require_role_below(role_key text, my_rank int) returns public.roles
language plpgsql stable security definer set search_path = '' as $$
declare r public.roles;
begin
  select * into r from public.roles where key = role_key;
  if r.key is null then raise exception 'role_unknown: ce rôle n''existe plus' using errcode = 'P0002'; end if;
  if r.rank >= my_rank then raise exception 'forbidden: seulement les rôles en dessous du tien' using errcode = '42501'; end if;
  return r;
end $$;

create or replace function private.clean_role_fields(role_label text, role_color text, role_icon text,
                                                      out label text, out color text, out icon text)
language plpgsql immutable set search_path = '' as $$
begin
  label := regexp_replace(btrim(coalesce(role_label, '')), '\s+', ' ', 'g');
  if char_length(label) not between 1 and 30 then
    raise exception 'role_label: donne un nom de 1 à 30 caractères' using errcode = '22023';
  end if;
  color := nullif(btrim(coalesce(role_color, '')), '');
  if color is not null and color !~ '^#[0-9A-Fa-f]{6}$' then
    raise exception 'role_color: couleur invalide' using errcode = '22023';
  end if;
  color := upper(color);
  icon := nullif(btrim(coalesce(role_icon, '')), '');
  if icon is not null and char_length(icon) > 8 then
    raise exception 'role_icon: une icône (emoji) seulement' using errcode = '22023';
  end if;
end $$;

-- Renumérote 0, 1, 2… dans l'ordre actuel (après une suppression).
create or replace function private.compact_role_ranks() returns void
language sql security definer set search_path = '' as $$
  update public.roles r set rank = o.pos
  from (select key, (row_number() over (order by rank) - 1)::int pos from public.roles) o
  where o.key = r.key and r.rank <> o.pos;
$$;

revoke all on function private.require_roles_manager(), private.require_role_below(text, int),
  private.clean_role_fields(text, text, text), private.compact_role_ranks() from public, anon, authenticated;

-- Liste pour les écrans de gestion : chaque rôle, son nombre de comptes, et si je peux le modifier.
create or replace function public.roles_overview()
returns table (key text, label text, color text, icon text, rank int, builtin boolean, members int, editable boolean)
language plpgsql stable security definer set search_path = '' as $$
declare my_rank int;
begin
  if auth.uid() is null or not (private.is_root(auth.uid()) or private.user_has(auth.uid(), 'roles.manage')
                                or private.user_has(auth.uid(), 'members.roles')) then
    raise exception 'forbidden: tu ne peux pas gérer les rôles' using errcode = '42501';
  end if;
  my_rank := private.rank_of(auth.uid());
  return query
    select r.key, r.label, r.color, r.icon, r.rank, r.builtin,
           (select count(*)::int from public.profiles p where p.role = r.key),
           r.rank < my_rank
    from public.roles r order by r.rank;
end $$;

-- Nouveau rôle, placé juste au-dessus de Guest (le moins de pouvoir) ; droits copiés d'un rôle si demandé,
-- seulement ceux qu'on a soi-même.
create or replace function public.create_role(role_label text, role_color text default null, role_icon text default null,
                                              copy_from text default null) returns text
language plpgsql security definer set search_path = '' as $$
declare
  my_rank int := private.require_roles_manager();
  f record;
  new_key text;
  bottom int := coalesce(private.role_rank('guest'), 0);
begin
  if bottom + 1 >= my_rank then
    raise exception 'forbidden: seulement les rôles en dessous du tien' using errcode = '42501';
  end if;
  if (select count(*) from public.roles) >= 40 then
    raise exception 'role_limit: 40 rôles au maximum' using errcode = '22023';
  end if;
  f := private.clean_role_fields(role_label, role_color, role_icon);
  if exists (select 1 from public.roles where lower(btrim(label)) = lower(f.label)) then
    raise exception 'role_duplicate: ce nom de rôle existe déjà' using errcode = '23505';
  end if;
  if copy_from is not null then perform private.require_role_below(copy_from, 99); end if;
  perform pg_advisory_xact_lock(hashtext('party-roles'));
  new_key := 'r_' || substr(replace(pg_catalog.gen_random_uuid()::text, '-', ''), 1, 10);
  update public.roles set rank = rank + 1 where rank > bottom;
  insert into public.roles (key, label, color, icon, rank) values (new_key, f.label, f.color, f.icon, bottom + 1);
  if copy_from is not null then
    insert into public.role_permissions (role, perm)
      select new_key, rp.perm from public.role_permissions rp
      where rp.role = copy_from and (private.is_root(auth.uid()) or private.user_has(auth.uid(), rp.perm))
    on conflict do nothing;
  end if;
  perform private.audit('role.created', null, jsonb_build_object('key', new_key, 'label', f.label, 'copy_from', copy_from));
  return new_key;
end $$;

-- Nom, couleur, icône (la clé ne change jamais : les comptes et les droits suivent).
create or replace function public.update_role(role_key text, role_label text, role_color text default null,
                                              role_icon text default null) returns void
language plpgsql security definer set search_path = '' as $$
declare
  my_rank int := private.require_roles_manager();
  r public.roles := private.require_role_below(role_key, my_rank);
  f record := private.clean_role_fields(role_label, role_color, role_icon);
begin
  if exists (select 1 from public.roles where lower(btrim(label)) = lower(f.label) and key <> role_key) then
    raise exception 'role_duplicate: ce nom de rôle existe déjà' using errcode = '23505';
  end if;
  update public.roles set label = f.label, color = f.color, icon = f.icon where key = role_key;
  if r.label is distinct from f.label then
    perform private.audit('role.updated', null, jsonb_build_object('key', role_key, 'from', r.label, 'to', f.label));
  end if;
end $$;

-- Supprimer un rôle personnalisé : vide, ou en passant ses comptes à un autre rôle (en dessous du sien aussi ;
-- les règles habituelles d'attribution s'appliquent à chaque compte : droit members.roles, identité complète).
create or replace function public.delete_role(role_key text, move_to text default null) returns void
language plpgsql security definer set search_path = '' as $$
declare
  my_rank int := private.require_roles_manager();
  r public.roles := private.require_role_below(role_key, my_rank);
  moved int;
begin
  if not (private.is_root(auth.uid()) or private.user_has(auth.uid(), 'roles.delete')) then
    raise exception 'forbidden: il faut aussi le droit « Supprimer un rôle »' using errcode = '42501';
  end if;
  if r.builtin then raise exception 'role_builtin: ce rôle de base ne se supprime pas (renomme-le si besoin)' using errcode = '42501'; end if;
  perform pg_advisory_xact_lock(hashtext('party-roles'));
  if exists (select 1 from public.profiles where role = role_key) then
    if move_to is null then
      raise exception 'role_not_empty: choisis le rôle qui reprend ses comptes' using errcode = '23503';
    end if;
    if move_to = role_key then raise exception 'role_not_empty: choisis un autre rôle' using errcode = '22023'; end if;
    perform private.require_role_below(move_to, my_rank);
    update public.profiles set role = move_to where role = role_key;
    get diagnostics moved = row_count;
  end if;
  delete from public.roles where key = role_key;  -- ses droits partent avec (role_permissions, on delete cascade)
  perform private.compact_role_ranks();
  perform private.resync_vip_members();
  perform private.audit('role.deleted', null, jsonb_build_object('key', role_key, 'label', r.label, 'move_to', move_to,
                                                                 'moved', coalesce(moved, 0)));
end $$;

-- Nouvel ordre complet, du plus bas au plus haut. Guest reste en bas, Admin en haut ; les rôles égaux ou supérieurs
-- au sien (le sien compris) gardent leur place : on ne range que ce qui est en dessous de soi.
create or replace function public.reorder_roles(role_keys text[]) returns void
language plpgsql security definer set search_path = '' as $$
declare
  my_rank int := private.require_roles_manager();
  n int := (select count(*) from public.roles);
  r public.roles;
begin
  if role_keys is null or cardinality(role_keys) <> n
     or (select count(distinct k) from unnest(role_keys) k) <> n
     or exists (select 1 from unnest(role_keys) k where not exists (select 1 from public.roles where key = k)) then
    raise exception 'role_order: la liste des rôles a changé, recharge l''écran' using errcode = '22023';
  end if;
  if role_keys[1] <> 'guest' or role_keys[n] <> 'admin' then
    raise exception 'role_order: Guest reste en bas et Admin en haut' using errcode = '22023';
  end if;
  perform pg_advisory_xact_lock(hashtext('party-roles'));
  for r in select * from public.roles where rank >= my_rank loop
    if role_keys[r.rank + 1] is distinct from r.key then
      raise exception 'forbidden: seulement les rôles en dessous du tien' using errcode = '42501';
    end if;
  end loop;
  update public.roles set rank = o.pos - 1
  from unnest(role_keys) with ordinality as o(k, pos)
  where public.roles.key = o.k and public.roles.rank <> o.pos - 1;
  perform private.resync_vip_members();
  perform private.audit('roles.reordered', null, jsonb_build_object('order', to_jsonb(role_keys)));
end $$;

-- Cocher ou décocher un droit pour un rôle (mêmes règles qu'avant, rôle en texte).
drop function if exists public.set_role_permission(public.member_role, text, boolean);
create or replace function public.set_role_permission(target text, perm text, granted boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not (private.is_root(me) or private.user_has(me, 'roles.manage')) then
    raise exception 'forbidden: tu ne peux pas modifier les droits des rôles' using errcode = '42501';
  end if;
  if not exists (select 1 from public.roles where key = target) then
    raise exception 'role_unknown: ce rôle n''existe plus' using errcode = 'P0002';
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

revoke all on function public.roles_overview(), public.create_role(text, text, text, text), public.update_role(text, text, text, text),
  public.delete_role(text, text), public.reorder_roles(text[]), public.set_role_permission(text, text, boolean) from public, anon;
grant execute on function public.roles_overview(), public.create_role(text, text, text, text), public.update_role(text, text, text, text),
  public.delete_role(text, text), public.reorder_roles(text[]), public.set_role_permission(text, text, boolean) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 5. Billets : deux droits distincts (réponse de l'admin : « c'est deux droits différents »)
--    · « Scanner les billets » (tickets.scan) : scanner, noter l'arrivée, nouveau QR pour quelqu'un ;
--    · « Confirmer les paiements » (tickets.pay) : cocher « payé », confirmer « Reçu » / « Pas reçu ».
--    Sur tous les événements. Organisateur, co-organisateurs et admins gardent les deux pour leurs événements.
--    Les fonctions de 20261103130000_event_attendance_tickets sont reprises À L'IDENTIQUE, seule la vérification change.
-- --------------------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('tickets.scan', 'Événements', 'Scanner les billets',
   'À l''entrée de tous les événements : scanner les billets et noter les arrivées (les organisateurs le font déjà pour les leurs)', 25),
  ('tickets.pay', 'Événements', 'Confirmer les paiements',
   'Sur tous les événements payants : cocher « payé », confirmer « Reçu » ou « Pas reçu » (les organisateurs le font déjà pour les leurs)', 26)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if not exists (select 1 from private.one_time_changes where name = 'tickets_scan_2026_11_03') then
    -- Admin et Co-admin le font déjà (events.manage_all) : le droit leur est donné pour qu'ils puissent le transmettre.
    insert into public.role_permissions (role, perm) values ('admin', 'tickets.scan'), ('coadmin', 'tickets.scan') on conflict do nothing;
    insert into private.one_time_changes (name) values ('tickets_scan_2026_11_03');
  end if;
  if not exists (select 1 from private.one_time_changes where name = 'tickets_pay_2026_11_03') then
    insert into public.role_permissions (role, perm) values ('admin', 'tickets.pay'), ('coadmin', 'tickets.pay') on conflict do nothing;
    insert into private.one_time_changes (name) values ('tickets_pay_2026_11_03');
  end if;
end $$;

-- Repris de 20261103130000_event_attendance_tickets, avec le droit en plus.
create or replace function private.can_scan(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_admin() or public.is_organizer(e) or public.has_perm('tickets.scan');
$$;

create or replace function private.can_take_payments(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_admin() or public.is_organizer(e) or public.has_perm('tickets.pay');
$$;

create or replace function private.require_cashier(e uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.can_take_payments(e) then
    raise exception 'Seuls les organisateurs de l''événement confirment les paiements.' using errcode = '42501';
  end if;
end $$;

-- Liste de l'entrée : pour qui scanne ou qui encaisse.
create or replace function private.require_entry_staff(e uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not (private.can_scan(e) or private.can_take_payments(e)) then
    raise exception 'Seuls les organisateurs de l''événement valident les billets.' using errcode = '42501';
  end if;
end $$;
revoke all on function private.can_scan(uuid), private.can_take_payments(uuid), private.require_cashier(uuid),
  private.require_entry_staff(uuid) from public, anon, authenticated;

create or replace function public.set_ticket_paid(e uuid, member uuid, is_paid boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.require_cashier(e);
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
  perform private.require_entry_staff(e);
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
  if not (private.can_scan(e) or private.can_take_payments(e) or exists (select 1 from public.rsvps where event_id = e and user_id = auth.uid() and status = 'yes')) then
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
  perform private.require_cashier(e);
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

-- --------------------------------------------------------------------------------------------------------------
-- 6. Droit « Supprimer un rôle » (réponse de l'admin) : supprimer un rôle exige roles.manage ET roles.delete.
--    Donné au départ seulement aux rôles qui ont déjà roles.manage (en prod : aucun, seul Root gère les rôles).
-- --------------------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('roles.manage', 'Membres', 'Gérer les rôles et leurs droits',
   'Créer, renommer, réordonner les rôles en dessous du sien et choisir leurs droits', 34),
  ('roles.delete', 'Membres', 'Supprimer un rôle',
   'Avec « Gérer les rôles » : supprimer un rôle créé dans l''app (ses comptes passent à un autre rôle)', 35)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'roles_delete_2026_11_03') then
    return;
  end if;
  insert into public.role_permissions (role, perm)
    select role, 'roles.delete' from public.role_permissions where perm = 'roles.manage'
  on conflict do nothing;
  insert into private.one_time_changes (name) values ('roles_delete_2026_11_03');
end $$;

notify pgrst, 'reload schema';

insert into supabase_migrations.schema_migrations (version, name) values ('20261103140000', 'custom_roles')
  on conflict (version) do nothing;
commit;
