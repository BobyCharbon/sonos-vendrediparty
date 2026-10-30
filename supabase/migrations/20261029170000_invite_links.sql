-- Liens et invitations (avis n°9 de l'admin, 29 octobre 2026) :
-- 1) Événement réservé à un groupe, avec un lien d'invitation partageable : qui l'ouvre crée son compte (ou se connecte)
--    et devient invité de CET événement seulement (event_invites.via_link, affiché en orange) ; les organisateurs
--    sont prévenus (« X a rejoint ton événement par le lien »). Le lien se renouvelle (l'ancien ne marche plus).
-- 2) Groupes : lien d'invitation (on clique, on crée son compte, on rejoint le groupe) et invitation par surnom ou
--    numéro, acceptée ou refusée dans les Réglages. Le groupe Vendredi Party (système) n'a ni lien ni invitation :
--    on y entre par le rôle Membre VIP.
-- 3) Liens uniques (précision du 30.10) : un événement privé ne se partage que par des liens uniques (une personne, une
--    fois, 7 jours) ; un groupe privé, au choix, par lien unique (par défaut) ou réutilisable (member_groups.invite_token).
--    Les organisateurs voient les liens créés (en attente / utilisé par… / expiré / annulé) et peuvent les annuler.
-- Rejouable.

alter table public.events add column if not exists invite_token uuid unique;
alter table public.event_invites add column if not exists via_link boolean not null default false;
alter table public.member_groups add column if not exists invite_token uuid unique;

-- 1) Événements -----------------------------------------------------------------------------------------------------

create or replace function private.manages_event(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select public.is_organizer(e) or public.has_perm('events.manage_all');
$$;

-- Liens uniques : une personne, une fois, 7 jours. Lus seulement par les fonctions ci-dessous.
create table if not exists private.invite_links (
  token uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('event', 'group')),
  target uuid not null,
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '7 days',
  used_by uuid references public.profiles(id) on delete set null,
  used_at timestamptz,
  revoked_at timestamptz
);
create index if not exists invite_links_by_target on private.invite_links (kind, target, created_at desc);
revoke all on private.invite_links from public, anon, authenticated;

-- Cible d'un lien unique encore valable pour moi (ou déjà utilisé par moi : je retrouve mon invitation).
create or replace function private.invite_link_target(tok uuid, k text) returns uuid
language sql stable security definer set search_path = '' as $$
  select target from private.invite_links where token = tok and kind = k and revoked_at is null
    and (used_by = auth.uid() or (used_by is null and expires_at > now()));
$$;

-- Prend un lien unique pour moi (dans la transaction qui me fait rejoindre) ; sinon dit pourquoi il ne marche pas.
create or replace function private.claim_invite_link(tok uuid, k text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare t uuid; l private.invite_links;
begin
  update private.invite_links set used_by = auth.uid(), used_at = now()
    where token = tok and kind = k and revoked_at is null and used_by is null and expires_at > now()
    returning target into t;
  if t is not null then return t; end if;
  select * into l from private.invite_links where token = tok and kind = k;
  if l.token is null then return null; end if;
  if l.used_by = auth.uid() then return l.target; end if;
  if l.revoked_at is not null then raise exception 'Ce lien a été annulé. Demande un nouveau lien à la personne qui t''a invité.'; end if;
  if l.used_by is not null then raise exception 'Ce lien a déjà été utilisé : il ne marche qu''une fois. Demande ton propre lien.'; end if;
  raise exception 'Ce lien a expiré (7 jours). Demande un nouveau lien à la personne qui t''a invité.';
end $$;

-- Nouveau lien unique (organisateurs de l'événement, créateur du groupe privé).
create or replace function public.create_invite_link(k text, target uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare tok uuid;
begin
  if k = 'event' and not private.manages_event(target) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  elsif k = 'group' and not (private.manages_group(target)
        and exists (select 1 from public.member_groups where id = target and system_key is null)) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  elsif k not in ('event', 'group') then
    raise exception 'Type de lien inconnu';
  end if;
  if (select count(*) from private.invite_links il where il.kind = k and il.target = create_invite_link.target
        and il.used_by is null and il.revoked_at is null and il.expires_at > now()) >= 100 then
    raise exception 'Trop de liens en attente : annule ceux qui ne serviront plus.';
  end if;
  insert into private.invite_links (kind, target, created_by) values (k, target, auth.uid()) returning token into tok;
  return tok;
end $$;

-- Liens uniques créés (les 50 derniers) et leur état, pour l'organisateur.
create or replace function public.my_invite_links(k text, target uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if not ((k = 'event' and private.manages_event(target)) or (k = 'group' and private.manages_group(target))) then
    raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501';
  end if;
  return coalesce((select jsonb_agg(x order by x->>'created_at' desc) from (
    select jsonb_build_object('token', l.token, 'created_at', l.created_at, 'expires_at', l.expires_at,
      'used_at', l.used_at, 'used_by', p.display_name,
      'status', case when l.used_by is not null then 'used' when l.revoked_at is not null then 'revoked'
                     when l.expires_at <= now() then 'expired' else 'pending' end) x
    from private.invite_links l left join public.profiles p on p.id = l.used_by
    where l.kind = k and l.target = my_invite_links.target
    order by l.created_at desc limit 50) s), '[]'::jsonb);
end $$;

-- Annuler un lien unique pas encore utilisé (envoyé à la mauvaise personne…).
create or replace function public.revoke_invite_link(tok uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links;
begin
  select * into l from private.invite_links where token = tok;
  if l.token is null or not ((l.kind = 'event' and private.manages_event(l.target))
                             or (l.kind = 'group' and private.manages_group(l.target))) then
    raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501';
  end if;
  update private.invite_links set revoked_at = now() where token = tok and used_by is null and revoked_at is null;
end $$;

-- Compatibilité : l'ancien appel crée désormais un lien unique (un événement privé n'a plus de lien réutilisable).
create or replace function public.event_invite_link(e uuid, renew boolean default false) returns uuid
language sql security definer set search_path = '' as $$
  select public.create_invite_link('event', e);
$$;

-- Profil complet (nom, prénom, surnom, photo) : exigé avant de voir ou de rejoindre une invitation par lien
-- (avis n°9 : on s'inscrit avec son numéro, on complète son profil, puis on accède à l'événement ou au groupe).
create or replace function private.identity_complete(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.profiles p where p.id = uid
    and coalesce(btrim(p.first_name), '') <> '' and coalesce(btrim(p.last_name), '') <> ''
    and coalesce(btrim(p.display_name), '') <> '' and coalesce(btrim(p.avatar_url), '') <> '');
$$;

-- Ce que montre le lien : rien sans compte au profil complet (le lien seul ne révèle pas l'événement).
create or replace function public.invite_event(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address,
    'organizer', (select display_name from public.profiles where id = ev.created_by),
    'joined', auth.uid() is not null and (public.can_see_event(ev.id)
              or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = auth.uid())))
  from public.events ev
  where token is not null and ev.id = private.invite_link_target(token, 'event') and ev.status in ('published', 'cancelled')
    and private.identity_complete(auth.uid());
$$;

-- Rejoindre par le lien : invité de cet événement seulement ; les organisateurs sont prévenus (une fois).
create or replace function public.join_event_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare ev public.events; who text; u uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not private.identity_complete(auth.uid()) then
    raise exception 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) avant de rejoindre';
  end if;
  select * into ev from public.events where id = private.claim_invite_link(token, 'event') and status = 'published';
  if ev.id is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  insert into public.event_invites (event_id, user_id, via_group, via_link) values (ev.id, auth.uid(), false, true)
  on conflict (event_id, user_id) do nothing;
  if found then
    select display_name into who from public.profiles where id = auth.uid();
    for u in select x from (select ev.created_by x union select user_id from public.event_organizers where event_id = ev.id) o loop
      perform public.queue_notification(u, 'link_join', ev.id, ev.title,
        coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a rejoint ton événement par le lien',
        'link_join:' || ev.id || ':' || auth.uid());
    end loop;
  end if;
  return ev.id;
end $$;

-- 2) Groupes --------------------------------------------------------------------------------------------------------

create table if not exists private.group_invitations (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete cascade,
  phone text,
  invited_by uuid references public.profiles(id) on delete set null,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'declined')),
  created_at timestamptz not null default now(),
  check (user_id is not null or phone is not null)
);
create unique index if not exists group_invitations_pending_user on private.group_invitations (group_id, user_id)
  where status = 'pending' and user_id is not null;
create unique index if not exists group_invitations_pending_phone on private.group_invitations (group_id, phone)
  where status = 'pending' and phone is not null;
revoke all on private.group_invitations from public, anon, authenticated;

create or replace function private.manages_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                 and (g.created_by = auth.uid() or public.is_admin()));
$$;

create or replace function private.digits(t text) returns text
language sql immutable set search_path = '' as $$
  select nullif(regexp_replace(coalesce(t, ''), '\D', '', 'g'), '');
$$;

create or replace function private.join_group(grp uuid, member uuid) returns boolean
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text;
begin
  select * into g from public.member_groups where id = grp;
  insert into public.member_group_members (group_id, user_id) values (grp, member) on conflict do nothing;
  if not found then return false; end if;
  update private.group_invitations set status = 'accepted' where group_id = grp and status = 'pending'
    and (user_id = member or phone = (select private.digits(phone) from public.profiles where id = member));
  select display_name into who from public.profiles where id = member;
  if g.created_by is not null and g.created_by <> member then
    perform public.queue_notification(g.created_by, 'group_join', null, g.name,
      coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a rejoint ton groupe', 'group_join:' || grp || ':' || member);
  end if;
  return true;
end $$;

create or replace function public.group_invite_link(grp uuid, renew boolean default false) returns uuid
language plpgsql security definer set search_path = '' as $$
declare token uuid;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  update public.member_groups set invite_token = gen_random_uuid() where id = grp and (invite_token is null or renew)
    returning invite_token into token;
  return coalesce(token, (select invite_token from public.member_groups where id = grp));
end $$;

create or replace function public.group_invite_info(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', g.id, 'name', g.name,
    'creator', (select display_name from public.profiles where id = g.created_by),
    'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
    'joined', auth.uid() is not null and exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid()))
  from public.member_groups g
  where token is not null and (g.invite_token = token or g.id = private.invite_link_target(token, 'group'))
    and g.system_key is null and private.identity_complete(auth.uid());
$$;

create or replace function public.join_group_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not private.identity_complete(auth.uid()) then
    raise exception 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) avant de rejoindre';
  end if;
  select id into grp from public.member_groups where token is not null and invite_token = token and system_key is null;
  if grp is null then
    select id into grp from public.member_groups where id = private.claim_invite_link(token, 'group') and system_key is null;
  end if;
  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  perform private.join_group(grp, auth.uid());
  return grp;
end $$;

-- Inviter par surnom (compte) ou par numéro (compte ou pas encore inscrit : l'invitation l'attend).
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

-- Mes invitations en attente (par mon compte ou par mon numéro).
create or replace function public.my_group_invitations() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', i.id, 'group_id', g.id, 'group', g.name,
           'invited_by', (select display_name from public.profiles where id = i.invited_by), 'at', i.created_at)
           order by i.created_at desc), '[]'::jsonb)
  from private.group_invitations i join public.member_groups g on g.id = i.group_id
  where i.status = 'pending' and auth.uid() is not null
    and (i.user_id = auth.uid() or i.phone = (select private.digits(phone) from public.profiles where id = auth.uid()))
    and not exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid());
$$;

create or replace function public.answer_group_invitation(inv uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare i private.group_invitations;
begin
  select * into i from private.group_invitations where id = inv and status = 'pending'
    and (user_id = auth.uid() or phone = (select private.digits(phone) from public.profiles where id = auth.uid()));
  if i.id is null then raise exception 'Cette invitation n''est plus valable'; end if;
  if accept then
    if not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
    perform private.join_group(i.group_id, auth.uid());
  else
    update private.group_invitations set status = 'declined' where id = inv;
  end if;
  return public.my_group_invitations();
end $$;

revoke all on function public.event_invite_link(uuid, boolean), public.join_event_by_link(uuid),
  public.group_invite_link(uuid, boolean), public.join_group_by_link(uuid), public.invite_to_group(uuid, uuid, text),
  public.my_group_invitations(), public.answer_group_invitation(uuid, boolean) from public, anon;
grant execute on function public.event_invite_link(uuid, boolean), public.join_event_by_link(uuid),
  public.group_invite_link(uuid, boolean), public.join_group_by_link(uuid), public.invite_to_group(uuid, uuid, text),
  public.my_group_invitations(), public.answer_group_invitation(uuid, boolean) to authenticated;
-- Aperçu d'un lien : réservé aux comptes connectés au profil complet (plus rien pour les visiteurs).
revoke all on function public.invite_event(uuid), public.group_invite_info(uuid) from public, anon;
grant execute on function public.invite_event(uuid), public.group_invite_info(uuid) to authenticated;
revoke all on function private.identity_complete(uuid) from public, anon;
grant execute on function private.identity_complete(uuid) to authenticated;
revoke all on function public.create_invite_link(text, uuid), public.my_invite_links(text, uuid), public.revoke_invite_link(uuid),
  private.invite_link_target(uuid, text), private.claim_invite_link(uuid, text) from public, anon;
grant execute on function public.create_invite_link(text, uuid), public.my_invite_links(text, uuid), public.revoke_invite_link(uuid),
  private.invite_link_target(uuid, text), private.claim_invite_link(uuid, text) to authenticated;
revoke all on function private.manages_event(uuid), private.manages_group(uuid), private.digits(text),
  private.join_group(uuid, uuid) from public, anon;
grant execute on function private.manages_event(uuid), private.manages_group(uuid), private.digits(text) to authenticated;
