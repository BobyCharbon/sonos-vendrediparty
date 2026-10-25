-- PROD, 25.10.2026 — accord explicite de l'admin (« Ok prod »).
-- À coller tel quel dans Supabase → projet VendrediParty → SQL Editor → Run.
-- Tout-ou-rien : si une ligne échoue, rien n'est appliqué. Rejouable sans risque.
begin;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);

-- ════ 20261025120000_member_admin_and_audit ════
-- Section « Membres » pour Root et les admins : liste complète des inscrits, suppression d'un compte,
-- journal des membres (inscriptions, connexions, rôles, bêta, groupes, accès retirés, suppressions,
-- consultations de la liste). BROUILLON : à valider sur la base de TEST (vrai schéma) avant la prod.
--
-- Qui : Root et Admin, c.-à-d. public.my_rank() >= 4 (invité 0 … admin 4, root 99).
-- Le journal est en ajout seul : aucune politique, aucun droit d'écriture pour les clients ; seules les
-- fonctions ci-dessous (security definer) y écrivent. Les lignes ne référencent pas profiles (pas de clé
-- étrangère) pour survivre à la suppression du compte concerné.
-- Purement additive et rejouable.

create table if not exists public.member_audit (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  action text not null check (length(action) between 1 and 40),
  actor uuid,
  actor_name text,
  target uuid,
  target_name text,
  details jsonb
);
create index if not exists member_audit_target on public.member_audit (target, id desc);
create index if not exists member_audit_actor on public.member_audit (actor, action, at desc);
alter table public.member_audit enable row level security;
revoke all on public.member_audit from public, anon, authenticated;

create or replace function private.is_member_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and coalesce(public.my_rank(), -1) >= 4;
$$;
revoke all on function private.is_member_admin() from public, anon;

-- Rang d'un rôle : private.role_rank(public.member_role) existe déjà (migration member_roles_permissions).
drop function if exists private.role_rank(text);

create or replace function private.member_name(member uuid) returns text
language sql stable security definer set search_path = '' as $$
  select nullif(btrim(coalesce(p.display_name, '')), '') from public.profiles p where p.id = member;
$$;
revoke all on function private.member_name(uuid) from public, anon;

create or replace function private.audit(action text, target uuid, details jsonb default null) returns void
language sql security definer set search_path = '' as $$
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values (action, auth.uid(), private.member_name(auth.uid()), target, private.member_name(target), details);
$$;
revoke all on function private.audit(text, uuid, jsonb) from public, anon, authenticated;

-- ── Traces automatiques ──
create or replace function private.audit_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    perform private.audit('account.created', new.id, jsonb_build_object('role', new.role));
  else
    if new.role is distinct from old.role then
      perform private.audit('member.role', new.id, jsonb_build_object('from', old.role, 'to', new.role));
    end if;
    if new.status is distinct from old.status then
      perform private.audit('member.status', new.id, jsonb_build_object('from', old.status, 'to', new.status));
    end if;
  end if;
  return null;
end $$;
drop trigger if exists audit_profile on public.profiles;
create trigger audit_profile after insert or update of role, status on public.profiles
for each row execute function private.audit_profile();

create or replace function private.audit_beta() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.audit('member.beta', coalesce(new.user_id, old.user_id), jsonb_build_object('enabled', tg_op = 'INSERT'));
  return null;
end $$;
drop trigger if exists audit_beta on public.beta_testers;
create trigger audit_beta after insert or delete on public.beta_testers
for each row execute function private.audit_beta();

create or replace function private.audit_group_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g uuid := coalesce(new.group_id, old.group_id);
begin
  perform private.audit(case when tg_op = 'INSERT' then 'group.add' else 'group.remove' end, coalesce(new.user_id, old.user_id),
    jsonb_build_object('group', (select name from public.member_groups where id = g)));
  return null;
end $$;
drop trigger if exists audit_group_member on public.member_group_members;
create trigger audit_group_member after insert or delete on public.member_group_members
for each row execute function private.audit_group_member();

-- Connexion SMS réussie = nouvelle session Supabase Auth. À VÉRIFIER sur la base de test : droit de poser
-- un déclencheur sur auth.sessions (sinon : seulement auth.users.last_sign_in_at dans admin_member_list).
create or replace function private.audit_login() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values ('account.login', new.user_id, private.member_name(new.user_id), new.user_id, private.member_name(new.user_id),
          jsonb_build_object('device', left(coalesce(new.user_agent, ''), 120)));
  return null;
end $$;
drop trigger if exists audit_login on auth.sessions;
create trigger audit_login after insert on auth.sessions
for each row execute function private.audit_login();

-- Toute suppression de compte (par la personne ou par un admin) : nom relu avant que le profil disparaisse.
create or replace function private.audit_account_deleted() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values ('account.deleted', auth.uid(), private.member_name(auth.uid()), old.id, private.member_name(old.id),
          jsonb_build_object('by', case when auth.uid() = old.id then 'self' else 'admin' end,
                             'phone_end', right(coalesce(old.phone, ''), 2)));
  return old;
end $$;
drop trigger if exists audit_account_deleted on auth.users;
create trigger audit_account_deleted before delete on auth.users
for each row execute function private.audit_account_deleted();

-- ── Liste complète des inscrits (Root, Admin) : sections « Membres » et « Utilisateurs » ──
-- Chaque ouverture est journalisée (une fois par 10 min). Première connexion : voir ci-dessous ;
-- nombre de connexions et dernier appareil : comptés depuis l'installation de ce journal.
drop function if exists public.admin_member_list();
create function public.admin_member_list()
returns table (id uuid, display_name text, first_name text, last_name text, phone text, avatar_url text,
               role text, status text, created_at timestamptz, first_sign_in_at timestamptz, last_sign_in_at timestamptz,
               beta boolean, sign_in_count int, last_device text, groups text[], rsvp_count int, message_count int)
language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  if not exists (select 1 from public.member_audit a where a.action = 'members.viewed' and a.actor = auth.uid()
                 and a.at > now() - interval '10 minutes') then
    perform private.audit('members.viewed', null, null);
  end if;
  return query
    select p.id, p.display_name, p.first_name, p.last_name, p.phone, p.avatar_url, p.role::text, p.status::text,
           p.created_at,
           -- Première connexion : Auth réécrit phone_confirmed_at à chaque connexion, on ne s'en sert donc pas.
           -- Connexion notée par le journal le jour même de la création du compte, sinon (compte plus ancien
           -- que le journal) la création du compte = sa toute première demande de code.
           coalesce((select min(a.at) from public.member_audit a where a.action = 'account.login' and a.target = p.id
                     and a.at < u.created_at + interval '1 day'), u.created_at),
           u.last_sign_in_at,
           exists (select 1 from public.beta_testers b where b.user_id = p.id),
           (select count(*)::int from public.member_audit a where a.action = 'account.login' and a.target = p.id),
           (select a.details ->> 'device' from public.member_audit a where a.action = 'account.login' and a.target = p.id order by a.id desc limit 1),
           coalesce((select array_agg(g.name order by g.name) from public.member_group_members gm
                     join public.member_groups g on g.id = gm.group_id where gm.user_id = p.id), '{}'),
           (select count(*)::int from public.rsvps r where r.user_id = p.id and r.status::text = 'yes'),
           (select count(*)::int from public.messages m where m.user_id = p.id and m.deleted_at is null)
    from public.profiles p left join auth.users u on u.id = p.id
    order by p.created_at desc;
end $$;
revoke all on function public.admin_member_list() from public, anon;
grant execute on function public.admin_member_list() to authenticated;

-- ── Journal (Root, Admin) : tout, ou celui d'un membre ; « before » pour la page suivante ──
create or replace function public.admin_member_audit(member uuid default null, before bigint default null, lim int default 100)
returns setof public.member_audit
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  return query select * from public.member_audit a
    where (member is null or a.target = member or a.actor = member) and (before is null or a.id < before)
    order by a.id desc limit greatest(1, least(lim, 500));
end $$;
revoke all on function public.admin_member_audit(uuid, bigint, int) from public, anon;
grant execute on function public.admin_member_audit(uuid, bigint, int) to authenticated;

-- ── Suppression complète d'un compte par Root ou un Admin ──
-- Seulement un compte d'un rôle inférieur au sien (Root n'est supprimable par personne, un admin ne
-- supprime pas un autre admin) ; jamais soi-même (« Supprimer mon compte » existe pour ça). Le surnom
-- tapé doit correspondre. Même nettoyage que delete_current_account : les clés étrangères font le reste.
create or replace function public.admin_delete_member(member uuid, confirm_name text) returns void
language plpgsql security definer set search_path = '' as $$
declare target public.profiles;
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  if member = auth.uid() then raise exception 'self: utilise « Supprimer mon compte »' using errcode = '42501'; end if;
  lock table public.profiles in share row exclusive mode;
  select * into target from public.profiles where id = member;
  if not found then raise exception 'not_found: compte introuvable' using errcode = 'P0002'; end if;
  if private.is_root(target.id) or private.role_rank(target.role) >= public.my_rank() then
    raise exception 'forbidden: ce compte a un rôle égal ou supérieur au tien' using errcode = '42501';
  end if;
  if lower(btrim(coalesce(confirm_name, ''))) <> lower(btrim(coalesce(target.display_name, ''))) then
    raise exception 'confirm: le surnom tapé ne correspond pas' using errcode = '22023';
  end if;
  update public.messages set mentions = array_remove(mentions, member) where member = any(mentions);
  delete from auth.users where id = member;  -- journalisé par audit_account_deleted
end $$;
revoke all on function public.admin_delete_member(uuid, text) from public, anon;
grant execute on function public.admin_delete_member(uuid, text) to authenticated;

insert into supabase_migrations.schema_migrations (version, name, statements) values ('20261025120000', 'member_admin_and_audit', array[$mig$-- Section « Membres » pour Root et les admins : liste complète des inscrits, suppression d'un compte,
-- journal des membres (inscriptions, connexions, rôles, bêta, groupes, accès retirés, suppressions,
-- consultations de la liste). BROUILLON : à valider sur la base de TEST (vrai schéma) avant la prod.
--
-- Qui : Root et Admin, c.-à-d. public.my_rank() >= 4 (invité 0 … admin 4, root 99).
-- Le journal est en ajout seul : aucune politique, aucun droit d'écriture pour les clients ; seules les
-- fonctions ci-dessous (security definer) y écrivent. Les lignes ne référencent pas profiles (pas de clé
-- étrangère) pour survivre à la suppression du compte concerné.
-- Purement additive et rejouable.

create table if not exists public.member_audit (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  action text not null check (length(action) between 1 and 40),
  actor uuid,
  actor_name text,
  target uuid,
  target_name text,
  details jsonb
);
create index if not exists member_audit_target on public.member_audit (target, id desc);
create index if not exists member_audit_actor on public.member_audit (actor, action, at desc);
alter table public.member_audit enable row level security;
revoke all on public.member_audit from public, anon, authenticated;

create or replace function private.is_member_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and coalesce(public.my_rank(), -1) >= 4;
$$;
revoke all on function private.is_member_admin() from public, anon;

-- Rang d'un rôle : private.role_rank(public.member_role) existe déjà (migration member_roles_permissions).
drop function if exists private.role_rank(text);

create or replace function private.member_name(member uuid) returns text
language sql stable security definer set search_path = '' as $$
  select nullif(btrim(coalesce(p.display_name, '')), '') from public.profiles p where p.id = member;
$$;
revoke all on function private.member_name(uuid) from public, anon;

create or replace function private.audit(action text, target uuid, details jsonb default null) returns void
language sql security definer set search_path = '' as $$
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values (action, auth.uid(), private.member_name(auth.uid()), target, private.member_name(target), details);
$$;
revoke all on function private.audit(text, uuid, jsonb) from public, anon, authenticated;

-- ── Traces automatiques ──
create or replace function private.audit_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    perform private.audit('account.created', new.id, jsonb_build_object('role', new.role));
  else
    if new.role is distinct from old.role then
      perform private.audit('member.role', new.id, jsonb_build_object('from', old.role, 'to', new.role));
    end if;
    if new.status is distinct from old.status then
      perform private.audit('member.status', new.id, jsonb_build_object('from', old.status, 'to', new.status));
    end if;
  end if;
  return null;
end $$;
drop trigger if exists audit_profile on public.profiles;
create trigger audit_profile after insert or update of role, status on public.profiles
for each row execute function private.audit_profile();

create or replace function private.audit_beta() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.audit('member.beta', coalesce(new.user_id, old.user_id), jsonb_build_object('enabled', tg_op = 'INSERT'));
  return null;
end $$;
drop trigger if exists audit_beta on public.beta_testers;
create trigger audit_beta after insert or delete on public.beta_testers
for each row execute function private.audit_beta();

create or replace function private.audit_group_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g uuid := coalesce(new.group_id, old.group_id);
begin
  perform private.audit(case when tg_op = 'INSERT' then 'group.add' else 'group.remove' end, coalesce(new.user_id, old.user_id),
    jsonb_build_object('group', (select name from public.member_groups where id = g)));
  return null;
end $$;
drop trigger if exists audit_group_member on public.member_group_members;
create trigger audit_group_member after insert or delete on public.member_group_members
for each row execute function private.audit_group_member();

-- Connexion SMS réussie = nouvelle session Supabase Auth. À VÉRIFIER sur la base de test : droit de poser
-- un déclencheur sur auth.sessions (sinon : seulement auth.users.last_sign_in_at dans admin_member_list).
create or replace function private.audit_login() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values ('account.login', new.user_id, private.member_name(new.user_id), new.user_id, private.member_name(new.user_id),
          jsonb_build_object('device', left(coalesce(new.user_agent, ''), 120)));
  return null;
end $$;
drop trigger if exists audit_login on auth.sessions;
create trigger audit_login after insert on auth.sessions
for each row execute function private.audit_login();

-- Toute suppression de compte (par la personne ou par un admin) : nom relu avant que le profil disparaisse.
create or replace function private.audit_account_deleted() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values ('account.deleted', auth.uid(), private.member_name(auth.uid()), old.id, private.member_name(old.id),
          jsonb_build_object('by', case when auth.uid() = old.id then 'self' else 'admin' end,
                             'phone_end', right(coalesce(old.phone, ''), 2)));
  return old;
end $$;
drop trigger if exists audit_account_deleted on auth.users;
create trigger audit_account_deleted before delete on auth.users
for each row execute function private.audit_account_deleted();

-- ── Liste complète des inscrits (Root, Admin) : sections « Membres » et « Utilisateurs » ──
-- Chaque ouverture est journalisée (une fois par 10 min). Première connexion : voir ci-dessous ;
-- nombre de connexions et dernier appareil : comptés depuis l'installation de ce journal.
drop function if exists public.admin_member_list();
create function public.admin_member_list()
returns table (id uuid, display_name text, first_name text, last_name text, phone text, avatar_url text,
               role text, status text, created_at timestamptz, first_sign_in_at timestamptz, last_sign_in_at timestamptz,
               beta boolean, sign_in_count int, last_device text, groups text[], rsvp_count int, message_count int)
language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  if not exists (select 1 from public.member_audit a where a.action = 'members.viewed' and a.actor = auth.uid()
                 and a.at > now() - interval '10 minutes') then
    perform private.audit('members.viewed', null, null);
  end if;
  return query
    select p.id, p.display_name, p.first_name, p.last_name, p.phone, p.avatar_url, p.role::text, p.status::text,
           p.created_at,
           -- Première connexion : Auth réécrit phone_confirmed_at à chaque connexion, on ne s'en sert donc pas.
           -- Connexion notée par le journal le jour même de la création du compte, sinon (compte plus ancien
           -- que le journal) la création du compte = sa toute première demande de code.
           coalesce((select min(a.at) from public.member_audit a where a.action = 'account.login' and a.target = p.id
                     and a.at < u.created_at + interval '1 day'), u.created_at),
           u.last_sign_in_at,
           exists (select 1 from public.beta_testers b where b.user_id = p.id),
           (select count(*)::int from public.member_audit a where a.action = 'account.login' and a.target = p.id),
           (select a.details ->> 'device' from public.member_audit a where a.action = 'account.login' and a.target = p.id order by a.id desc limit 1),
           coalesce((select array_agg(g.name order by g.name) from public.member_group_members gm
                     join public.member_groups g on g.id = gm.group_id where gm.user_id = p.id), '{}'),
           (select count(*)::int from public.rsvps r where r.user_id = p.id and r.status::text = 'yes'),
           (select count(*)::int from public.messages m where m.user_id = p.id and m.deleted_at is null)
    from public.profiles p left join auth.users u on u.id = p.id
    order by p.created_at desc;
end $$;
revoke all on function public.admin_member_list() from public, anon;
grant execute on function public.admin_member_list() to authenticated;

-- ── Journal (Root, Admin) : tout, ou celui d'un membre ; « before » pour la page suivante ──
create or replace function public.admin_member_audit(member uuid default null, before bigint default null, lim int default 100)
returns setof public.member_audit
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  return query select * from public.member_audit a
    where (member is null or a.target = member or a.actor = member) and (before is null or a.id < before)
    order by a.id desc limit greatest(1, least(lim, 500));
end $$;
revoke all on function public.admin_member_audit(uuid, bigint, int) from public, anon;
grant execute on function public.admin_member_audit(uuid, bigint, int) to authenticated;

-- ── Suppression complète d'un compte par Root ou un Admin ──
-- Seulement un compte d'un rôle inférieur au sien (Root n'est supprimable par personne, un admin ne
-- supprime pas un autre admin) ; jamais soi-même (« Supprimer mon compte » existe pour ça). Le surnom
-- tapé doit correspondre. Même nettoyage que delete_current_account : les clés étrangères font le reste.
create or replace function public.admin_delete_member(member uuid, confirm_name text) returns void
language plpgsql security definer set search_path = '' as $$
declare target public.profiles;
begin
  if not private.is_member_admin() then raise exception 'Accès admin requis' using errcode = '42501'; end if;
  if member = auth.uid() then raise exception 'self: utilise « Supprimer mon compte »' using errcode = '42501'; end if;
  lock table public.profiles in share row exclusive mode;
  select * into target from public.profiles where id = member;
  if not found then raise exception 'not_found: compte introuvable' using errcode = 'P0002'; end if;
  if private.is_root(target.id) or private.role_rank(target.role) >= public.my_rank() then
    raise exception 'forbidden: ce compte a un rôle égal ou supérieur au tien' using errcode = '42501';
  end if;
  if lower(btrim(coalesce(confirm_name, ''))) <> lower(btrim(coalesce(target.display_name, ''))) then
    raise exception 'confirm: le surnom tapé ne correspond pas' using errcode = '22023';
  end if;
  update public.messages set mentions = array_remove(mentions, member) where member = any(mentions);
  delete from auth.users where id = member;  -- journalisé par audit_account_deleted
end $$;
revoke all on function public.admin_delete_member(uuid, text) from public, anon;
grant execute on function public.admin_delete_member(uuid, text) to authenticated;
$mig$]) on conflict (version) do nothing;

-- ════ 20261025160000_vip_group_and_audiences ════
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

insert into supabase_migrations.schema_migrations (version, name, statements) values ('20261025160000', 'vip_group_and_audiences', array[$mig$-- Groupe « Vendredi Party » = Membres VIP et au-dessus, et qui voit quelle sortie (décisions du 25.10.2026) :
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
$mig$]) on conflict (version) do nothing;
commit;
select version, name from supabase_migrations.schema_migrations where version >= '20261025' order by version;
