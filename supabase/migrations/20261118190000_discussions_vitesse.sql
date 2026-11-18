-- Discussions : vitesse (demande de l'admin du 18.11 : « le plus rapide possible »). Mêmes règles, mêmes réponses,
-- moins de calcul :
--  * private.met_events (« Déjà vu N fois ») part des soirées EN COMMUN (intersection), au lieu de passer chaque
--    événement du site au crible : 2 à 3 fois plus rapide, et ne grandit plus avec le nombre d'événements ;
--  * « Nouveau message » (chat_people_search, chat_people_suggestions) : qui-écrit-à-qui (private.dm_link) calculé UNE
--    fois par personne (il l'était 3 à 4 fois : filtre, tri, puis carte de la personne).
-- Purement additive et rejouable (create or replace). Aucune règle de la base ne change (dm_link reste la seule source).

create or replace function private.met_events(me uuid, other uuid)
returns table (id uuid, title text, starts_at timestamptz)
language sql stable security definer set search_path = '' as $$
  with together as (select private.dm_events_of(me) as id intersect select private.dm_events_of(other))
  select ev.id, ev.title, ev.starts_at from together t join public.events ev on ev.id = t.id
  where ev.status = 'published' and ev.starts_at is not null
    and coalesce(ev.ends_at, ev.starts_at + interval '4 hours') < now()
    and public.can_see_event(ev.id)
    and (private.chat_role(ev, me, me) in ('organizer', 'yes')
         or exists (select 1 from public.event_tickets tk where tk.event_id = ev.id and tk.user_id = me and tk.checked_in_at is not null))
    and (private.chat_role(ev, other, me) in ('organizer', 'yes')
         or (private.chat_manages(ev, me)
             and exists (select 1 from public.event_tickets tk where tk.event_id = ev.id and tk.user_id = other and tk.checked_in_at is not null)))
  order by ev.starts_at desc;
$$;

-- Carte d'une personne quand son lien (dm_link) est déjà connu ; chat_person garde sa forme et le calcule.
create or replace function private.chat_person_linked(me uuid, uid uuid, sub text, link text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', p.id, 'name', private.chat_name(p.id), 'nickname', nullif(btrim(p.display_name), ''),
    'photo', p.avatar_url, 'sub', nullif(btrim(coalesce(sub, '')), ''), 'link', link,
    'met_count', (select count(*) from private.met_events(me, p.id)))
  from public.profiles p where p.id = uid;
$$;

create or replace function private.chat_person(me uuid, uid uuid, sub text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select private.chat_person_linked(me, uid, sub, private.dm_link(me, uid));
$$;

create or replace function public.chat_people_suggestions() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); vp uuid := private.vip_group_id(); recent jsonb; crossed jsonb; grp jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  -- Conversations récentes (acceptées, avec des messages).
  with cand as materialized (
    select r.u, r.last_at, private.dm_link(me, r.u) as link from (
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
    select z.u, z.title, z.start_at, private.dm_link(me, z.u) as link from (
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
    select v.u, v.name, v.dn, private.dm_link(me, v.u) as link from (
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

-- Recherche par surnom (et prénom / nom quand la personne les montre), sans accents ; jamais par numéro.
create or replace function public.chat_people_search(q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); qq text := private.fold(btrim(coalesce(q, ''))); see_names boolean; out jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if char_length(qq) < 2 then return '[]'::jsonb; end if;
  see_names := public.has_perm('members.view_identity');
  with cand as materialized (
    select c.id, c.dn, c.prefix, private.dm_link(me, c.id) as link from (
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

revoke all on function private.chat_person_linked(uuid, uuid, text, text) from public, anon, authenticated;
