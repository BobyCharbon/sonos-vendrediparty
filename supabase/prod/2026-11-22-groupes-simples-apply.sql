-- Prod : 20261122134000_groupes_simples (avis f0e9bf158133, 22.11) : recherche « numéro exact ou nom » pour ajouter
-- quelqu'un à un groupe (jamais de liste, jamais le numéro, 30 / heure), « Tous les membres peuvent inviter ».
begin;
-- Groupes plus simples (avis f0e9bf158133, choix de l'admin du 22.11.2026).
-- 1. Réglage du groupe « Tous les membres peuvent inviter » (member_groups.members_invite, ALLUMÉ par défaut) : allumé,
--    tout membre invite (invite_to_group) et partage le lien du groupe (group_invite_link) ; éteint, seuls ceux qui gèrent
--    le groupe (créateur, admins et organisateurs du groupe, Admin du site). Changé par le créateur (ou un Co-admin et
--    plus) seulement : set_group_members_invite + garde guard_group_members_invite. Jamais Membres Vendredi Party.
--    « Événements à valider » existe déjà (events_need_approval, 20261106220000) : inchangé, éteint par défaut.
-- 2. Recherche « Numéro exact ou nom » (group_people_search) au lieu d'une liste de personnes : numéro complet → la
--    personne si elle a un compte ; nom, prénom ou surnom (3 lettres au moins) → 5 personnes au plus. Rend : id, surnom,
--    photo, initiale du nom, déjà invité. JAMAIS le numéro. Exclus : moi, blocages (avec moi ou le créateur du groupe),
--    profils incomplets, comptes non actifs (suspendus, bannis), déjà membres, personnes qui refusent toute demande
--    (chat_prefs.message_requests = 'none' : lien « none » de dm_check). 30 recherches par heure et par personne.
-- 3. invite_to_group : invite aussi une personne trouvée ainsi (lien « direct » OU « request », comme une demande de
--    message ; un numéro compte comme un contact) ; blocage, membres, 30 invitations par jour : inchangés. Toujours une
--    INVITATION (la personne accepte), jamais un ajout direct.
-- Purement additive et rejouable.

-- 1. Réglage ---------------------------------------------------------------------------------------------------------------
alter table public.member_groups add column if not exists members_invite boolean not null default true;

create or replace function private.may_invite_group(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.manages_group(grp)
      or exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null
                   and private.is_account_active(auth.uid())
                   and (private.group_staff(grp, auth.uid())
                        or (g.members_invite and private.in_group_now(grp, auth.uid()))));
$$;
revoke all on function private.may_invite_group(uuid) from public, anon, authenticated;

create or replace function public.set_group_members_invite(grp uuid, allowed boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from public.member_groups where id = grp and system_key is not null) then
    raise exception 'forbidden: pas de réglage pour Membres Vendredi Party' using errcode = '42501';
  end if;
  if not private.may_set_group_rules(grp, auth.uid()) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  update public.member_groups set members_invite = coalesce(allowed, true) where id = grp;
end $$;
revoke all on function public.set_group_members_invite(uuid, boolean) from public, anon;
grant execute on function public.set_group_members_invite(uuid, boolean) to authenticated;

create or replace function private.guard_group_members_invite() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null and new.members_invite is distinct from old.members_invite
     and (old.system_key is not null or not private.may_set_group_rules(old.id, auth.uid())) then
    new.members_invite := old.members_invite;
  end if;
  return new;
end $$;
revoke all on function private.guard_group_members_invite() from public, anon, authenticated;
drop trigger if exists member_groups_members_invite on public.member_groups;
create trigger member_groups_members_invite before update on public.member_groups
  for each row execute function private.guard_group_members_invite();

-- Lien réutilisable du groupe : qui peut inviter (avant : le créateur seul).
create or replace function public.group_invite_link(grp uuid, renew boolean default false) returns uuid
language plpgsql security definer set search_path = '' as $$
declare token uuid;
begin
  if not private.may_invite_group(grp) then
    raise exception 'forbidden: seuls ceux qui gèrent le groupe invitent' using errcode = '42501';
  end if;
  -- Renouveler (l'ancien lien ne marche plus) : qui gère le groupe seulement.
  update public.member_groups set invite_token = gen_random_uuid()
    where id = grp and (invite_token is null or (renew and private.manages_group(grp)))
    returning invite_token into token;
  return coalesce(token, (select invite_token from public.member_groups where id = grp));
end $$;
revoke all on function public.group_invite_link(uuid, boolean) from public, anon;
grant execute on function public.group_invite_link(uuid, boolean) to authenticated;

-- Liste « droits » de mes groupes : + 'invite' (bouton « Inviter » de la page du groupe, web et iPhone).
do $$
declare def text := pg_get_functiondef('public.my_groups_overview()'::regprocedure);
begin
  if position('''invite'', private.may_invite_group' in def) = 0 then
    execute replace(def, '''manage'', private.manages_group(g.id),',
                         '''manage'', private.manages_group(g.id), ''invite'', private.may_invite_group(g.id),');
  end if;
end $$;

-- Anciennes versions de l'app (liste « Déjà sur Party ») : mêmes droits que l'invitation.
do $$
declare def text := pg_get_functiondef('public.group_invite_suggestions(uuid)'::regprocedure);
begin
  if position('may_invite_group' in def) = 0 then
    execute replace(def, 'if not private.manages_group(grp) then', 'if not private.may_invite_group(grp) then');
  end if;
end $$;

-- 2. Recherche ---------------------------------------------------------------------------------------------------------------
create table if not exists private.group_search_log (
  user_id uuid not null references auth.users (id) on delete cascade,
  q text not null,
  at timestamptz not null default now()
);
create index if not exists group_search_log_user_at on private.group_search_log (user_id, at);
revoke all on private.group_search_log from public, anon, authenticated;

-- « +41 79 123 45 67 », « 0041 79… », « 079 123 45 67 » → 41791234567 (comme la connexion SMS) ; null si ce n'est pas un numéro.
create or replace function private.search_phone(q text) returns text
language sql immutable set search_path = '' as $$
  select case
    when btrim(coalesce(q, '')) !~ '^(\+|00)?[0-9][0-9 .()/-]{6,}$' then null
    when d ~ '^00' then nullif(substr(d, 3), '')
    when d ~ '^0[1-9]' and length(d) = 10 then '41' || substr(d, 2)
    else d end
  from (select regexp_replace(coalesce(q, ''), '\D', '', 'g') d) x;
$$;

create or replace function public.group_people_search(grp uuid, q text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  me uuid := auth.uid(); g public.member_groups; number text := private.search_phone(q);
  qq text := private.fold(btrim(regexp_replace(coalesce(q, ''), '^\s*@', '')));
  key text; out jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.may_invite_group(grp) then
    raise exception 'forbidden: seuls ceux qui gèrent le groupe invitent' using errcode = '42501';
  end if;
  if number is not null and length(number) < 8 then return '[]'::jsonb; end if;
  if number is null and char_length(qq) < 3 then return '[]'::jsonb; end if;
  -- Anti-annuaire : 30 recherches différentes par heure (la même recherche répétée ne compte qu'une fois).
  key := coalesce('tel:' || number, qq);
  delete from private.group_search_log l where l.user_id = me and l.at < now() - interval '1 day';
  if not exists (select 1 from private.group_search_log l where l.user_id = me and l.q = key and l.at > now() - interval '1 hour') then
    if (select count(*) from private.group_search_log l where l.user_id = me and l.at > now() - interval '1 hour') >= 30 then
      raise exception 'limit: tu as fait beaucoup de recherches, réessaie dans une heure' using errcode = '54000';
    end if;
    insert into private.group_search_log (user_id, q) values (me, key);
  end if;
  select * into g from public.member_groups where id = grp;
  with cand as (
    select p.id, p.display_name, p.avatar_url, p.last_name,
           starts_with(private.fold(p.display_name), qq) as prefix
    from public.profiles p
    where p.status = 'active' and p.id <> me
      and private.identity_complete(p.id)
      and case when number is not null then private.digits(p.phone) = number
               else position(qq in private.fold(p.display_name)) > 0
                 or starts_with(private.fold(p.first_name), qq) or starts_with(private.fold(p.last_name), qq)
                 or position(qq in private.fold(concat_ws(' ', p.first_name, p.last_name))) > 0 end
      and not exists (select 1 from public.member_group_members m where m.group_id = grp and m.user_id = p.id)
      and not private.blocked_either(me, p.id)
      and (g.created_by is null or not private.blocked_either(p.id, g.created_by))
    order by prefix desc, p.display_name
    limit 50
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', x.id, 'display_name', x.display_name, 'avatar_url', x.avatar_url,
           'initial', nullif(upper(left(btrim(coalesce(x.last_name, '')), 1)), ''),
           'invited', exists (select 1 from private.group_invitations i where i.group_id = grp and i.user_id = x.id and i.status = 'pending'))
         order by x.prefix desc, x.display_name), '[]'::jsonb) into out
  from (select * from cand
        where private.dm_check_core(me, cand.id, number is not null, false) ->> 'link' <> 'none'
        order by cand.prefix desc, cand.display_name limit 5) x;
  return out;
end $$;
revoke all on function public.group_people_search(uuid, text) from public, anon;
grant execute on function public.group_people_search(uuid, text) to authenticated;

-- 3. invite_to_group : qui peut inviter, et une personne trouvée par la recherche ---------------------------------------
create or replace function public.invite_to_group(grp uuid, member uuid default null, phone text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text; by_phone boolean; link jsonb;
begin
  if not private.may_invite_group(grp) then
    raise exception 'forbidden: seuls ceux qui gèrent le groupe invitent' using errcode = '42501';
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  delete from private.group_invite_log where user_id = auth.uid() and at < now() - interval '2 days';
  if (select count(*) from private.group_invite_log where user_id = auth.uid() and at > now() - interval '1 day') >= 30 then
    raise exception 'limit: tu as envoyé beaucoup d''invitations aujourd''hui, réessaie demain' using errcode = '54000';
  end if;
  insert into private.group_invite_log (user_id) values (auth.uid());
  select * into g from public.member_groups where id = grp;
  by_phone := target is null;
  if by_phone then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
    if target is null then
      insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
      return jsonb_build_object('invited', 'phone');
    end if;
    -- Un compte a ce numéro : invité s'il accepte les demandes (le numéro vaut contact) ; sinon rien, et la même réponse.
    if not exists (select 1 from public.member_group_members where group_id = grp and user_id = target)
       and not private.blocked_either(target, auth.uid()) and not private.blocked_either(target, g.created_by)
       and coalesce(private.dm_check(auth.uid(), target, true) ->> 'link', 'none') <> 'none' then
      insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
      select display_name into me from public.profiles where id = auth.uid();
      perform public.queue_notification(target, 'group_invite', null, g.name,
        coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
        'group_invite:' || grp || ':' || target);
    end if;
    return jsonb_build_object('invited', 'phone');
  end if;
  if exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if private.blocked_either(target, auth.uid()) or private.blocked_either(target, g.created_by) then
    raise exception 'blocked: Tu ne peux pas inviter cette personne.' using errcode = '42501';
  end if;
  link := private.dm_check(auth.uid(), target, false);
  if link ->> 'reason' = 'terms_required' then
    raise exception 'terms_required: accepte les conditions d''utilisation de Party pour inviter.' using errcode = '42501';
  end if;
  if coalesce(link ->> 'link', 'none') = 'none' then
    raise exception 'link_required: cette personne ne reçoit pas d''invitation de ta part.' using errcode = '42501';
  end if;
  insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
  select display_name into me from public.profiles where id = auth.uid();
  perform public.queue_notification(target, 'group_invite', null, g.name,
    coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
    'group_invite:' || grp || ':' || target);
  return jsonb_build_object('invited', 'member');
end $$;
revoke all on function public.invite_to_group(uuid, uuid, text) from public, anon;
grant execute on function public.invite_to_group(uuid, uuid, text) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261122134000', 'groupes_simples') on conflict do nothing;
commit;
