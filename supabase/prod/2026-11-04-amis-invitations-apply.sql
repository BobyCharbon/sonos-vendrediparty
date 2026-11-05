-- PROD, friends_and_app_invites (20261104090000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Prérequis : rôles personnalisés (20261103140000, table public.roles) et liens d'invitation (20261029170000,
-- private.invite_links, private.identity_complete), déjà en prod. Indépendante des noms des contacts (20261103170000) :
-- contacts_friends ne lit que des identifiants de comptes. Tout ou rien (begin/commit).
begin;
-- Mes amis dans Party et invitations dans l'app (avis de l'admin du 3 novembre 2026, 84fab3987f68) :
-- « Créer un endroit dans les réglages -> mes amis dans Party. Ça montre toutes les personnes que nous avons dans nos
--   contacts qui sont aussi inscrites dans Party. + avec la possibilité d'inviter des gens dans l'app Party. »
--
-- 1. contacts_friends(ids) : l'app iPhone a déjà reconnu ses contacts (contacts_match, empreintes seulement) ; elle
--    demande ici, pour ces comptes-là, ce qu'il faut pour la liste « Mes amis » : surnom, photo, date d'arrivée sur
--    Party et groupes en commun. JAMAIS de numéro, de nom ou de rôle. Comptes actifs seulement, 2 000 ids au plus.
-- 2. Lien personnel d'invitation dans Party (un par compte, réutilisable) : private.app_invites. Renouveler le lien
--    remplace l'ancien (qui ne marche plus) ; 5 renouvellements par jour au plus (anti-abus).
--    · app_invite_preview(token) : lisible AVANT connexion (« Ludo t'invite sur Party ») : surnom et photo de
--      l'inviteur, rien d'autre ;
--    · claim_app_invite(token) : le nouveau compte (créé il y a moins de 24 h, profil complet) note qui l'a invité,
--      une seule fois, jamais soi-même ; l'inviteur est prévenu (notification referral_join, « X a rejoint Party
--      grâce à toi ») et voit le NOMBRE de personnes arrivées grâce à lui (my_app_invite.joined), pas leur liste.
--      Le lien ne donne AUCUN droit : le nouveau compte reste Guest (rôle donné à l'inscription).
-- 3. Droit members.invite (« Inviter dans Party ») donné à TOUS les rôles, Guest compris (décision de l'admin :
--    « tout le monde » peut inviter) ; retirable rôle par rôle dans Administration › Rôles et droits.
-- 4. Notifications (règle : chaque type a son interrupteur, respecté par tous les canaux) :
--    · referral_join (serveur) : notification_prefs.referral_joins, appliqué par private.web_push_allowed ;
--      reçu aussi par les comptes Guest (private.may_receive_push) ;
--    · « Ton contact Léa est sur Party » : notification LOCALE de l'iPhone (les contacts ne quittent pas l'appareil),
--      interrupteur notification_prefs.contact_joins, lu par l'app.
-- 5. « Invité par » (précision de l'admin du 4 novembre : « que ce soit marqué avec qui il a rejoint le groupe, grâce
--    à qui […] visible dans le profil de la personne, juste pour les admins. Donc aussi un droit en plus ») :
--    · private.invite_joins : chaque arrivée par un lien — lien personnel Party, lien unique de groupe ou d'événement
--      (private.invite_links.created_by), lien réutilisable de groupe (qui l'a généré : member_groups.invite_token_by,
--      sinon le créateur du groupe) — avec l'inviteur, la cible et la date ;
--    · droit members.view_referrals (« Voir qui a invité qui »), donné au seul rôle Admin (Root l'a toujours) ;
--    · member_invited_by(target) : la section « Invité par » de la fiche, vide sans ce droit. La personne invitée et
--      les autres membres n'y ont pas accès (claim_app_invite ne renvoie plus le nom de l'inviteur, pas de liste
--      « arrivés grâce à moi » : seulement leur nombre pour l'inviteur, et sa notification referral_join).
-- Purement additif et rejouable.

-- 4. Interrupteurs (activés par défaut) ------------------------------------------------------------------------------
alter table public.notification_prefs add column if not exists referral_joins boolean not null default true;
alter table public.notification_prefs add column if not exists contact_joins boolean not null default true;

-- 3. Droit « Inviter dans Party » -------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('members.invite', 'Membres', 'Inviter dans Party', 'Partager son lien personnel pour faire venir ses amis (ils arrivent en Guest)', 29)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'members_invite_2026_11_04') then
    return;
  end if;
  insert into public.role_permissions (role, perm) select r.key, 'members.invite' from public.roles r on conflict do nothing;
  insert into private.one_time_changes (name) values ('members_invite_2026_11_04');
end $$;

-- 1. Mes amis dans Party ---------------------------------------------------------------------------------------------
create or replace function public.contacts_friends(ids uuid[]) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if coalesce(cardinality(ids), 0) > 2000 then
    raise exception 'Trop de contacts d''un coup' using errcode = '22023';
  end if;
  return coalesce((select jsonb_agg(jsonb_build_object(
      'id', p.id,
      'display_name', p.display_name,
      'avatar_url', p.avatar_url,
      'joined_at', p.created_at,
      'common_groups', coalesce((select jsonb_agg(g.name order by g.system_key nulls last, g.name)
                                 from public.member_groups g
                                 where exists (select 1 from public.member_group_members a where a.group_id = g.id and a.user_id = p.id)
                                   and exists (select 1 from public.member_group_members b where b.group_id = g.id and b.user_id = me)),
                                '[]'::jsonb)) order by p.id)
    from public.profiles p
    where p.id = any(ids) and p.id <> me and p.status = 'active'), '[]'::jsonb);
end $$;

-- 5. « Invité par » : historique des arrivées par lien, lisible avec le droit members.view_referrals -----------------
create table if not exists private.invite_joins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  invited_by uuid references public.profiles(id) on delete set null,
  via text not null check (via in ('app', 'group', 'event')),
  target uuid,
  at timestamptz not null default now()
);
create unique index if not exists invite_joins_once
  on private.invite_joins (user_id, via, coalesce(target, '00000000-0000-0000-0000-000000000000'::uuid));
create index if not exists invite_joins_by_user on private.invite_joins (user_id, at desc);
revoke all on private.invite_joins from public, anon, authenticated;

-- Une arrivée par lien (une fois par personne et par cible ; jamais « invité par soi-même »).
create or replace function private.note_invite_join(member uuid, inviter uuid, kind text, tgt uuid) returns void
language sql security definer set search_path = '' as $$
  insert into private.invite_joins (user_id, invited_by, via, target)
  select member, nullif(inviter, member), kind, tgt where member is not null
  on conflict do nothing;
$$;
revoke all on function private.note_invite_join(uuid, uuid, text, uuid) from public, anon, authenticated;

-- Liens uniques (événement, groupe) : consommés par private.claim_invite_link → l'inviteur est celui qui a créé le lien.
create or replace function private.invite_link_used() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.used_by is not null and old.used_by is null then
    perform private.note_invite_join(new.used_by, new.created_by, new.kind, new.target);
  end if;
  return new;
end $$;
drop trigger if exists invite_link_used on private.invite_links;
create trigger invite_link_used after update of used_by on private.invite_links
  for each row execute function private.invite_link_used();

-- Lien réutilisable d'un groupe : on retient qui l'a généré (créateur du groupe ou admin).
alter table public.member_groups add column if not exists invite_token_by uuid references public.profiles(id) on delete set null;
create or replace function private.group_token_author() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.invite_token is distinct from old.invite_token then
    new.invite_token_by := auth.uid();
  end if;
  return new;
end $$;
drop trigger if exists group_token_author on public.member_groups;
create trigger group_token_author before update of invite_token on public.member_groups
  for each row execute function private.group_token_author();

-- Rejoindre un groupe par lien (reprise de 20261029170000, plus l'arrivée notée pour le lien réutilisable ; le lien
-- unique est noté par le déclencheur invite_link_used).
create or replace function public.join_group_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid; author uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not private.identity_complete(auth.uid()) then
    raise exception 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) avant de rejoindre';
  end if;
  select id, coalesce(invite_token_by, created_by) into grp, author from public.member_groups
    where token is not null and invite_token = token and system_key is null;
  if grp is null then
    select id into grp from public.member_groups where id = private.claim_invite_link(token, 'group') and system_key is null;
  end if;
  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  if private.join_group(grp, auth.uid()) and author is not null then
    perform private.note_invite_join(auth.uid(), author, 'group', grp);
  end if;
  return grp;
end $$;

insert into public.permissions (key, grp, label, hint, sort) values
  ('members.view_referrals', 'Membres', 'Voir qui a invité qui', 'Section « Invité par » dans la fiche d''un membre (lien Party, groupe, événement)', 36)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint;
do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'members_view_referrals_2026_11_04') then
    return;
  end if;
  insert into public.role_permissions (role, perm) values ('admin', 'members.view_referrals') on conflict do nothing;
  insert into private.one_time_changes (name) values ('members_view_referrals_2026_11_04');
end $$;

-- Fiche d'un membre › « Invité par » : vide (null) sans le droit. Les plus récentes d'abord.
create or replace function public.member_invited_by(target uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.has_perm('members.view_referrals') then
    return null;
  end if;
  return coalesce((select jsonb_agg(jsonb_build_object(
      'invited_by', j.invited_by,
      'inviter', (select display_name from public.profiles where id = j.invited_by),
      'via', j.via,
      'target', j.target,
      'target_name', case j.via when 'group' then (select name from public.member_groups where id = j.target)
                                when 'event' then (select title from public.events where id = j.target) end,
      'at', j.at) order by j.at desc)
    from private.invite_joins j where j.user_id = member_invited_by.target), '[]'::jsonb);
end $$;
revoke all on function public.member_invited_by(uuid) from public, anon;
grant execute on function public.member_invited_by(uuid) to authenticated;

-- 2. Lien personnel d'invitation --------------------------------------------------------------------------------------
create table if not exists private.app_invites (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  token uuid not null unique default gen_random_uuid(),
  created_at timestamptz not null default now(),
  renewed_on date,
  renewals integer not null default 0 check (renewals >= 0)
);
revoke all on private.app_invites from public, anon, authenticated;

create table if not exists private.app_referrals (
  invitee uuid primary key references public.profiles(id) on delete cascade,
  inviter uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists app_referrals_by_inviter on private.app_referrals (inviter, created_at desc);
revoke all on private.app_referrals from public, anon, authenticated;

-- Mon lien (créé à la première demande) ; renew = un nouveau lien, l'ancien ne marche plus (5 fois par jour au plus).
create or replace function public.my_app_invite(renew boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); inv private.app_invites; today date := (now() at time zone 'Europe/Zurich')::date;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not public.has_perm('members.invite') then
    raise exception 'forbidden: ton rôle ne permet pas d''inviter dans Party' using errcode = '42501';
  end if;
  insert into private.app_invites (user_id) values (me) on conflict (user_id) do nothing;
  if renew then
    select * into inv from private.app_invites where user_id = me for update;
    if inv.renewed_on = today and inv.renewals >= 5 then
      raise exception 'rate_limited: Tu as déjà changé de lien 5 fois aujourd''hui. Réessaie demain.' using errcode = '54000';
    end if;
    update private.app_invites set token = gen_random_uuid(), created_at = now(),
      renewals = case when renewed_on = today then renewals + 1 else 1 end, renewed_on = today
      where user_id = me;
  end if;
  select * into inv from private.app_invites where user_id = me;
  return jsonb_build_object('token', inv.token, 'created_at', inv.created_at,
    'joined', (select count(*) from private.app_referrals r join public.profiles p on p.id = r.invitee
               where r.inviter = me and p.status = 'active'));
end $$;

-- Ce que montre le lien avant connexion : le surnom et la photo de l'inviteur, s'il peut encore inviter. Rien sinon.
create or replace function public.app_invite_preview(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('inviter', p.display_name, 'avatar_url', p.avatar_url)
  from private.app_invites i join public.profiles p on p.id = i.user_id
  where app_invite_preview.token is not null and i.token = app_invite_preview.token and p.status = 'active'
    and private.user_has(p.id, 'members.invite');
$$;

-- Le nouveau compte note qui l'a invité : une fois, compte de moins de 24 h, profil complet, jamais soi-même.
-- Aucun droit n'est donné : le compte reste dans son rôle (Guest à l'inscription).
create or replace function public.claim_app_invite(token uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); inviter uuid; already uuid; who text; joined timestamptz;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not private.identity_complete(me) then
    raise exception 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) d''abord';
  end if;
  select i.user_id into inviter from private.app_invites i join public.profiles p on p.id = i.user_id
    where claim_app_invite.token is not null and i.token = claim_app_invite.token and p.status = 'active'
      and private.user_has(p.id, 'members.invite');
  if inviter is null then
    raise exception 'invalid: Ce lien d''invitation n''est plus valable.';
  end if;
  if inviter = me then
    raise exception 'self: C''est ton propre lien d''invitation.';
  end if;
  select r.inviter into already from private.app_referrals r where r.invitee = me;
  if found then
    if already is not distinct from inviter then
      return jsonb_build_object('new', false);
    end if;
    raise exception 'already: Ton arrivée sur Party est déjà notée.';
  end if;
  select created_at, display_name into joined, who from public.profiles where id = me;
  if joined < now() - interval '24 hours' then
    raise exception 'too_old: Tu étais déjà sur Party : ce lien sert aux nouveaux venus.';
  end if;
  insert into private.app_referrals (invitee, inviter) values (me, inviter) on conflict (invitee) do nothing;
  perform private.note_invite_join(me, inviter, 'app', null);
  perform public.queue_notification(inviter, 'referral_join', null, 'Party',
    coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a rejoint Party grâce à toi',
    'referral_join:' || me, jsonb_build_object('user_id', me));
  return jsonb_build_object('new', true);
end $$;

revoke all on function public.contacts_friends(uuid[]), public.my_app_invite(boolean), public.claim_app_invite(uuid),
  public.app_invite_preview(uuid) from public, anon;
grant execute on function public.contacts_friends(uuid[]), public.my_app_invite(boolean), public.claim_app_invite(uuid),
  public.app_invite_preview(uuid) to authenticated;
grant execute on function public.app_invite_preview(uuid) to anon;

-- 4. referral_join : reçu aussi par les Guests, et coupé par son interrupteur sur tous les canaux ----------------------
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join') and private.is_account_active(uid));
$$;
revoke all on function private.may_receive_push(uuid, text) from public, anon;

-- private.web_push_allowed est réécrite par plusieurs migrations du même jour : on AJOUTE la branche referral_join à la
-- définition en place (au lieu d'en recopier une version qui effacerait les autres types), une seule fois.
do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''group_join'' then prefs.group_joins';
begin
  if position('''referral_join''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'web_push_allowed : branche group_join introuvable, referral_join non ajouté';
  end if;
  execute replace(def, anchor, anchor || E'\n    when ''referral_join'' then coalesce(prefs.referral_joins, true)');
end $$;


insert into supabase_migrations.schema_migrations (version, name) values ('20261104090000', 'friends_and_app_invites') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
