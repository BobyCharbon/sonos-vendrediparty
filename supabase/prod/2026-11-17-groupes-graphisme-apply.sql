-- PROD, groupes_graphisme (20261117100000) : migration supabase/migrations/20261117100000_groupes_graphisme.sql telle quelle (mise en prod du 19.11).
-- Additive et rejouable. Tout ou rien.
begin;
-- Groupes : nouveau graphisme (17.11.2026, maquette A « Néon & couvertures » + bulles de B).
-- • member_groups.emoji (liste fermée) et color (une des 6 couleurs de Party) : la couverture d'un groupe = dégradé de sa
--   couleur + son emoji (pas de photo de couverture : contenu à modérer). « Membres Vendredi Party » : 🎉 lavande, fixe.
-- • my_groups_overview() : mes groupes façon WhatsApp (membres, quelques visages, dernier message, non lus, prochain
--   événement que JE peux voir) ; group_events(grp) : les événements du groupe que la personne a le droit de voir ;
--   group_invite_suggestions(grp) : seulement les personnes déjà croisées à des événements (jamais tout le site).
-- • my_chats() : + emoji et couleur des groupes (lignes de Discussions, app iPhone).
-- Purement additive et rejouable.

alter table public.member_groups add column if not exists emoji text not null default '👯';
-- Groupes existants : une couleur au hasard (la liste n'est pas toute rose) ; un nouveau groupe la choisit à la création.
alter table public.member_groups add column if not exists color text not null
  default (array['pink', 'coral', 'mint', 'sky', 'lavender', 'lemon'])[1 + floor(random() * 6)::int];

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'member_groups_emoji_check') then
    alter table public.member_groups add constraint member_groups_emoji_check check (emoji = any (array[
      '👯', '🎉', '🪩', '⚽', '🏡', '🎲', '🥾', '🎸', '🍕', '🍻', '🍷', '🎂', '🌴', '🎮', '🎤', '🏀']));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'member_groups_color_check') then
    alter table public.member_groups add constraint member_groups_color_check
      check (color = any (array['pink', 'coral', 'mint', 'sky', 'lavender', 'lemon']));
  end if;
end $$;

-- Membres Vendredi Party : emoji et couleur fixes, quoi qu'on envoie (la politique « modifier son groupe » exclut déjà
-- le groupe du système ; ceci couvre aussi les fonctions de la base).
create or replace function private.group_look_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.system_key is not null then
    new.emoji := '🎉';
    new.color := 'lavender';
  end if;
  return new;
end $$;

drop trigger if exists member_groups_look_guard on public.member_groups;
create trigger member_groups_look_guard before insert or update of emoji, color, system_key on public.member_groups
  for each row execute function private.group_look_guard();

update public.member_groups set emoji = '🎉', color = 'lavender'
  where system_key is not null and (emoji, color) is distinct from ('🎉', 'lavender');

-- Nom, emoji ou couleur changés : chaque membre relit ses écrans (signal sans contenu « user:<id> », comme access_changed).
create or replace function private.group_look_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
declare uid uuid;
begin
  if (old.name, old.emoji, old.color) is not distinct from (new.name, new.emoji, new.color) then return null; end if;
  for uid in select user_id from public.member_group_members where group_id = new.id loop
    perform private.party_signal('user:' || uid);
  end loop;
  return null;
exception when others then
  return null;  -- un signal perdu ne fait jamais échouer la modification
end $$;

drop trigger if exists member_groups_look_changed on public.member_groups;
create trigger member_groups_look_changed after update of name, emoji, color on public.member_groups
  for each row execute function private.group_look_changed();

-- --------------------------------------------------------------------------------------------------------------
-- Mes groupes (créés par moi ou dont je fais partie), le plus récent en haut, Vendredi Party d'abord.
-- Dernier message : jamais celui d'une personne que j'ai bloquée (ni compté en non lu).
create or replace function public.my_groups_overview() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(x.g order by x.sys desc, x.last_at desc nulls last, x.name), '[]'::jsonb) from (
    select g.system_key is not null as sys, coalesce(last.created_at, g.created_at) as last_at, g.name,
      jsonb_build_object(
        'id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color, 'system', g.system_key is not null,
        'creator', coalesce(g.created_by = auth.uid(), false),
        'manage', private.manages_group(g.id),
        'member', private.in_group_now(g.id, auth.uid()),
        'created_by_name', (select display_name from public.profiles where id = g.created_by),
        'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
        'faces', (select coalesce(jsonb_agg(jsonb_build_object('id', f.id, 'name', f.display_name, 'avatar_url', f.avatar_url)), '[]'::jsonb)
                  from (select p.id, p.display_name, p.avatar_url from public.member_group_members m
                        join public.profiles p on p.id = m.user_id
                        where m.group_id = g.id and p.status = 'active'
                        order by (p.id = auth.uid()), (p.avatar_url is null), m.added_at desc nulls last limit 5) f),
        'last', case when last.id is null then null
                     when last.deleted_at is not null then 'Message supprimé'
                     when last.body <> '' then left(last.body, 80)
                     when last.audio_path is not null then '🎤 Message vocal'
                     else '📷 Photo' end,
        'last_by', case when last.id is null or last.deleted_at is not null then null
                        when last.user_id = auth.uid() then 'Toi'
                        else (select display_name from public.profiles where id = last.user_id) end,
        'last_at', last.created_at,
        'unread', case when private.in_group_now(g.id, auth.uid()) then
                    (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                       and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity')
                       and not exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = m.user_id))
                  else 0 end,
        'next_event', (select jsonb_build_object('id', e.id, 'title', e.title, 'starts_at', e.starts_at, 'date_mode', e.date_mode)
                       from public.event_groups eg join public.events e on e.id = eg.event_id
                       where eg.group_id = g.id and eg.status = 'approved' and e.status = 'published'
                         and (e.date_mode = 'poll' or e.starts_at > now() - interval '6 hours')
                         and public.can_see_event(e.id)
                       order by e.starts_at nulls last limit 1)
      ) as g
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id
                         and not exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = m.user_id)
                       order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or g.created_by = auth.uid())
  ) x;
$$;

-- Événements du groupe que la personne a le droit de voir (membre du groupe, ou Admin du site) : à venir et sondages
-- d'abord, puis les passés. La fiche se lit ensuite comme toute autre (règles d'accès des événements).
create or replace function public.group_events(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', e.id, 'starts_at', e.starts_at, 'date_mode', e.date_mode,
           'upcoming', e.date_mode = 'poll' or e.starts_at is null or e.starts_at > now() - interval '6 hours')
         order by (e.date_mode = 'poll' or e.starts_at is null or e.starts_at > now() - interval '6 hours') desc,
                  case when e.starts_at > now() - interval '6 hours' then e.starts_at end asc nulls last,
                  e.starts_at desc nulls last), '[]'::jsonb)
  from public.event_groups eg join public.events e on e.id = eg.event_id
  where eg.group_id = grp and eg.status = 'approved' and e.status in ('published', 'cancelled')
    and auth.uid() is not null
    and (private.in_group_now(grp, auth.uid()) or private.sees_all_groups())
    and public.can_see_event(e.id);
$$;

-- « Déjà sur Party » à l'étape Inviter : seulement les personnes croisées à un événement (présentes ou peut-être,
-- organisatrices), jamais tout le site ; ni bloquées, ni déjà membres. Réservé à qui gère le groupe (comme invite_to_group).
create or replace function private.met_events(uid uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select event_id from public.rsvps where user_id = uid and status in ('yes', 'maybe')
  union select event_id from public.event_organizers where user_id = uid
  union select id from public.events where created_by = uid and status = 'published';
$$;

create or replace function public.group_invite_suggestions(grp uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  return (
    with mine as (select id from private.met_events(me) m(id)),
    pairs as (
      select r.event_id, r.user_id from public.rsvps r where r.event_id in (select id from mine) and r.status in ('yes', 'maybe')
      union select o.event_id, o.user_id from public.event_organizers o where o.event_id in (select id from mine)
      union select e.id, e.created_by from public.events e where e.id in (select id from mine) and e.created_by is not null
    )
    select coalesce(jsonb_agg(jsonb_build_object('id', x.id, 'display_name', x.display_name, 'avatar_url', x.avatar_url,
             'together', x.together, 'last_title', x.last_title, 'invited', x.invited) order by x.together desc, x.last_at desc nulls last), '[]'::jsonb)
    from (
      select p.id, p.display_name, p.avatar_url, count(distinct e.id) as together, max(e.starts_at) as last_at,
        (array_agg(e.title order by e.starts_at desc nulls last))[1] as last_title,
        exists (select 1 from private.group_invitations i where i.group_id = grp and i.user_id = p.id and i.status = 'pending') as invited
      from pairs
      join public.events e on e.id = pairs.event_id and e.status = 'published'
      join public.profiles p on p.id = pairs.user_id and p.id <> me and p.status = 'active'
      where not exists (select 1 from public.member_group_members m where m.group_id = grp and m.user_id = p.id)
        and not private.dm_blocked(me, p.id)
      group by p.id, p.display_name, p.avatar_url
      order by count(distinct e.id) desc, max(e.starts_at) desc nulls last
      limit 40
    ) x
  );
end $$;

-- Invitations reçues : avec l'emoji et la couleur du groupe (tuile de la liste).
create or replace function public.my_group_invitations() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', i.id, 'group_id', g.id, 'group', g.name, 'emoji', g.emoji, 'color', g.color,
           'invited_by', (select display_name from public.profiles where id = i.invited_by), 'at', i.created_at)
           order by i.created_at desc), '[]'::jsonb)
  from private.group_invitations i join public.member_groups g on g.id = i.group_id
  where i.status = 'pending' and auth.uid() is not null
    and (i.user_id = auth.uid() or i.phone = (select private.digits(phone) from public.profiles where id = auth.uid()))
    and not exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid());
$$;

-- Discussions (app iPhone, page Discussions) : emoji et couleur de chaque groupe. Le reste est inchangé.
create or replace function public.my_chats() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(c order by (c->>'last_at') desc nulls last, c->>'name'), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', g.id, 'name', g.name, 'kind', 'group', 'system', g.system_key is not null,
      'emoji', g.emoji, 'color', g.color,
      'member', private.in_group_now(g.id, auth.uid()),
      'admin', private.group_admin(g.id, auth.uid()),
      'creator', g.created_by = auth.uid(),
      'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
      'notify', coalesce(s.notify, 'mentions'),
      'last_at', last.created_at,
      'last', case when last.id is null then null
                   when last.deleted_at is not null then case when last.deleted_by_admin then 'Message supprimé par un admin' else 'Message supprimé' end
                   else coalesce((select display_name from public.profiles where id = last.user_id), '?') || ' : '
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or private.is_root(auth.uid()))
    union all
    select jsonb_build_object(
      'id', d.id, 'name', coalesce(nullif(btrim(o.display_name), ''), 'Profil à compléter'), 'kind', 'direct', 'system', false,
      'user_id', o.id, 'avatar_url', o.avatar_url,
      'member', true, 'admin', false, 'creator', false, 'members', 2,
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = o.id),
      'notify', coalesce(s.notify, 'all'),
      'last_at', last.created_at,
      'last', case when last.deleted_at is not null then 'Message supprimé'
                   else case when last.user_id = auth.uid() then 'Toi : ' else '' end
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.direct_messages m where m.chat_id = d.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.direct_chats d
    join public.profiles o on o.id = case when d.user_a = auth.uid() then d.user_b else d.user_a end
    left join public.direct_chat_settings s on s.chat_id = d.id and s.user_id = auth.uid()
    join lateral (select * from public.direct_messages m where m.chat_id = d.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)
  ) x;
$$;

revoke all on function private.group_look_guard(), private.group_look_changed(), private.met_events(uuid) from public, anon, authenticated;
revoke all on function public.my_groups_overview(), public.group_events(uuid), public.group_invite_suggestions(uuid) from public, anon;
grant execute on function public.my_groups_overview(), public.group_events(uuid), public.group_invite_suggestions(uuid) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261117100000', 'groupes_graphisme') on conflict do nothing;
commit;
