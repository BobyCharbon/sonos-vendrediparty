-- Discussions : « Nouveau message » montre les gens même quand MES CGU sont à accepter (retour de l'admin du 19.11).
-- Bug : sans les CGU de la version en cours (nouvelle version = tout le monde), dm_check rendait 'none' (terms_required)
-- pour chaque personne : la recherche et les suggestions étaient vides (« Il trouve personne ») et la feuille des CGU,
-- prévue au moment d'écrire (open_direct_chat → terms_required), ne venait jamais.
-- Correction : les LISTES (chat_people_search, chat_people_suggestions) lisent le lien sans le contrôle des CGU de la
-- personne qui cherche ; écrire (open_direct_chat, chat_link, dm_link) le garde tel quel → feuille des CGU puis nouvel essai.
-- Purement additive et rejouable (create or replace). Aucune règle d'écriture ne change.

create or replace function private.dm_check_core(me uuid, target uuid, contact boolean, check_terms boolean) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare vp uuid := private.vip_group_id();
begin
  if me is null or target is null or me = target then return jsonb_build_object('link', 'none', 'reason', null); end if;
  if not private.is_account_active(me) or not private.is_account_active(target) then
    return jsonb_build_object('link', 'none', 'reason', 'inactive');
  end if;
  if private.blocked_either(me, target) then return jsonb_build_object('link', 'none', 'reason', 'blocked'); end if;
  if not private.identity_complete(me) then return jsonb_build_object('link', 'none', 'reason', 'profile_required'); end if;
  if check_terms and coalesce((select s.terms_enforced from private.moderation_settings s where s.id = 1), false) and not private.terms_accepted(me) then
    return jsonb_build_object('link', 'none', 'reason', 'terms_required');
  end if;
  if exists (select 1 from public.direct_chats c where c.user_a = least(me, target) and c.user_b = greatest(me, target)
             and c.status = 'active')
     or exists (select 1 from public.member_group_members a join public.member_group_members b on b.group_id = a.group_id
                where a.user_id = me and b.user_id = target and a.group_id is distinct from vp)
     or exists (select 1 from public.events ev
                where ev.visibility = 'invited' and ev.status in ('published', 'cancelled')
                  and not exists (select 1 from public.event_groups eg where eg.event_id = ev.id and eg.group_id = vp)
                  and ev.id in (select private.dm_events_of(me)) and ev.id in (select private.dm_events_of(target)))
     or exists (select 1 from public.rsvps r join public.events ev on ev.id = r.event_id
                where (r.user_id = target and (ev.created_by = me
                         or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = me)))
                   or (r.user_id = me and (ev.created_by = target
                         or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = target)))) then
    return jsonb_build_object('link', 'direct', 'reason', null);
  end if;
  if coalesce((select p.message_requests from public.chat_prefs p where p.user_id = target), 'all') = 'none'
     or not private.identity_complete(target) then
    return jsonb_build_object('link', 'none', 'reason', 'closed');
  end if;
  if coalesce(contact, false)
     or (vp is not null and private.in_group_now(vp, me) and private.in_group_now(vp, target))
     or exists (select 1 from public.events ev
                where (ev.visibility = 'all' or exists (select 1 from public.event_groups eg where eg.event_id = ev.id and eg.group_id = vp))
                  and ev.status in ('published', 'cancelled')
                  and ev.id in (select private.dm_events_of(me)) and ev.id in (select private.dm_events_of(target)))
     or (private.is_member(me) and private.is_member(target)) then
    return jsonb_build_object('link', 'request', 'reason', null);
  end if;
  return jsonb_build_object('link', 'none', 'reason', null);
end $$;

create or replace function private.dm_check(me uuid, target uuid, contact boolean default false) returns jsonb
language sql stable security definer set search_path = '' as $$
  select private.dm_check_core(me, target, contact, true);
$$;

-- Lien montré dans les listes : le même, sans le contrôle des CGU de « me » (demandées au moment d'écrire).
create or replace function private.dm_link_listed(me uuid, target uuid) returns text
language sql stable security definer set search_path = '' as $$
  select private.dm_check_core(me, target, false, false) ->> 'link';
$$;

create or replace function public.chat_people_suggestions() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); vp uuid := private.vip_group_id(); recent jsonb; crossed jsonb; grp jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  -- Conversations récentes (acceptées, avec des messages).
  with cand as materialized (
    select r.u, r.last_at, private.dm_link_listed(me, r.u) as link from (
      select o.u, max(m.created_at) as last_at
      from public.direct_chats d
      cross join lateral (select case when d.user_a = me then d.user_b else d.user_a end as u) o
      join public.direct_messages m on m.chat_id = d.id
      where me in (d.user_a, d.user_b) and d.status = 'active'
      group by o.u) r
    where private.is_account_active(r.u) and not private.blocked_either(me, r.u))
  select coalesce(jsonb_agg(private.chat_person_linked(me, x.u, null, x.link) order by x.last_at desc), '[]'::jsonb) into recent
  from (select * from cand where cand.link <> 'none' order by cand.last_at desc limit 12) x;
  -- Croisés : événements en commun (début dans les 60 derniers jours ou à venir), personnes que je peux y voir.
  with cand as materialized (
    select z.u, z.title, z.start_at, private.dm_link_listed(me, z.u) as link from (
      select distinct on (p.u) p.u, ev.title, ev.starts_at as start_at
      from public.events ev
      cross join lateral (
        select ev.created_by u
        union select o.user_id from public.event_organizers o where o.event_id = ev.id
        union select r.user_id from public.rsvps r where r.event_id = ev.id and r.status in ('yes', 'maybe')
                and (ev.show_participants or private.chat_manages(ev, me))
        union select i.user_id from public.event_invites i where i.event_id = ev.id and private.chat_manages(ev, me)) p
      where ev.id in (select private.dm_events_of(me)) and ev.status in ('published', 'cancelled')
        and ev.starts_at >= now() - interval '60 days'
        and p.u is not null and p.u <> me
        and exists (select 1 from public.profiles pr where pr.id = p.u and pr.status = 'active' and coalesce(btrim(pr.display_name), '') <> '')
        and not private.blocked_either(me, p.u)
      order by p.u, ev.starts_at desc) z)
  select coalesce(jsonb_agg(private.chat_person_linked(me, y.u, y.title, y.link) order by y.start_at desc nulls last), '[]'::jsonb) into crossed
  from (select * from cand where cand.link <> 'none' order by cand.start_at desc limit 12) y;
  -- Dans mes groupes (hors Vendredi Party).
  with cand as materialized (
    select v.u, v.name, v.dn, private.dm_link_listed(me, v.u) as link from (
      select distinct on (b.user_id) b.user_id u, g.name, pr.display_name dn
      from public.member_group_members a
      join public.member_groups g on g.id = a.group_id and g.id is distinct from vp
      join public.member_group_members b on b.group_id = a.group_id and b.user_id <> me
      join public.profiles pr on pr.id = b.user_id and pr.status = 'active' and coalesce(btrim(pr.display_name), '') <> ''
      where a.user_id = me and not private.blocked_either(me, b.user_id)
      order by b.user_id, g.name) v)
  select coalesce(jsonb_agg(private.chat_person_linked(me, w.u, w.name, w.link) order by w.name, w.dn), '[]'::jsonb) into grp
  from (select * from cand where cand.link <> 'none' order by cand.name, cand.dn limit 12) w;
  return jsonb_build_object('recent', recent, 'crossed', crossed, 'groups', grp);
end $$;

create or replace function public.chat_people_search(q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); qq text := private.fold(btrim(coalesce(q, ''))); see_names boolean; out jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if char_length(qq) < 2 then return '[]'::jsonb; end if;
  see_names := public.has_perm('members.view_identity');
  with cand as materialized (
    select c.id, c.dn, c.prefix, private.dm_link_listed(me, c.id) as link from (
      select p.id, p.display_name dn,
             starts_with(private.fold(p.display_name), qq) as prefix
      from public.profiles p
      where p.status = 'active' and p.id <> me and coalesce(btrim(p.display_name), '') <> ''
        and not private.blocked_either(me, p.id)
        and (position(qq in private.fold(p.display_name)) > 0
             or ((see_names or private.shows_name(p.id))
                 and position(qq in private.fold(concat_ws(' ', p.first_name, p.last_name))) > 0))
      order by starts_with(private.fold(p.display_name), qq) desc, p.display_name
      limit 200) c)
  select coalesce(jsonb_agg(private.chat_person_linked(me, x.id, null, x.link) order by x.link = 'direct' desc, x.prefix desc, x.dn),
                  '[]'::jsonb) into out
  from (select * from cand where cand.link <> 'none' order by cand.link = 'direct' desc, cand.prefix desc, cand.dn limit 20) x;
  return out;
end $$;

revoke all on function private.dm_check_core(uuid, uuid, boolean, boolean) from public, anon, authenticated;
revoke all on function private.dm_link_listed(uuid, uuid) from public, anon, authenticated;
