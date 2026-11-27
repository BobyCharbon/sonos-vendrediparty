-- Recette du 27.11 (version Apple), additive et rejouable :
-- 1. Co-organisateurs : le formulaire ne propose plus tous les comptes de l'équipe à un Guest tout neuf, seulement les
--    personnes avec qui il a un lien (mêmes règles que les autres listes : groupes en commun hors Membres Vendredi Party,
--    événements en commun), jamais un blocage, jamais un compte inactif ou au profil vide. Le filtre « rôle qui peut
--    modifier » reste à l'écran. Un admin du site (events.manage_all) garde la liste complète (écran).
-- 2. Lien d'un groupe ouvert par un inconnu (sans compte) : nom, emoji, couleur du groupe et qui invite, rien d'autre
--    (ni membres, ni nombre, ni photo). Lien inconnu, arrêté, expiré ou groupe système : rien (null).

create or replace function public.co_organizer_suggestions() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); vp uuid := private.vip_group_id();
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Connexion requise' using errcode = '42501';
  end if;
  return (
    with mine as (select private.dm_events_of(me) as id),
    linked as (
      select b.user_id as u
      from public.member_group_members a
      join public.member_group_members b on b.group_id = a.group_id
      where a.user_id = me and a.group_id is distinct from vp
      -- Participants : seulement si la liste est visible (ou si j'organise), comme chat_people_suggestions.
      union select r.user_id from public.rsvps r join public.events ev on ev.id = r.event_id
        where r.event_id in (select id from mine) and r.status in ('yes', 'maybe')
          and (ev.show_participants or private.chat_manages(ev, me))
      union select o.user_id from public.event_organizers o where o.event_id in (select id from mine)
      union select e.created_by from public.events e where e.id in (select id from mine) and e.status in ('published', 'cancelled')
    )
    select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'display_name', p.display_name, 'role', p.role)
                              order by p.display_name), '[]'::jsonb)
    from public.profiles p
    where p.id in (select u from linked where u is not null) and p.id <> me and p.status = 'active'
      and coalesce(btrim(p.display_name), '') <> ''
      and not private.blocked_either(me, p.id)
  );
end $$;
revoke all on function public.co_organizer_suggestions() from public, anon;
grant execute on function public.co_organizer_suggestions() to authenticated;

-- $1 partout : dans une fonction SQL, un nom de colonne (invite_links.token) l'emporte sur le paramètre du même nom.
create or replace function public.group_invite_preview(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('name', g.name, 'emoji', g.emoji, 'color', g.color,
    'inviter', (select nullif(btrim(p.display_name), '') from public.profiles p
                where p.status = 'active' and p.id = coalesce(
                  (select l.created_by from private.invite_links l where l.token = $1 and l.kind = 'group' and l.target = g.id),
                  g.created_by)))
  from public.member_groups g
  where $1 is not null and (g.invite_token = $1 or g.id = private.invite_link_target($1, 'group'))
    and g.system_key is null
  limit 1;
$$;
revoke all on function public.group_invite_preview(uuid) from public;
grant execute on function public.group_invite_preview(uuid) to anon, authenticated;
