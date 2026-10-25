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
