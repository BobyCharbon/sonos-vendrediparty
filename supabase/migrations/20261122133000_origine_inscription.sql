-- Origine des inscriptions (avis 01da90202166, 22.11.2026 ; choix de l'admin : « Sources + qui l'a invité »).
-- À partir de maintenant, chaque NOUVEAU compte (profil créé il y a moins de 24 h) garde d'où il vient :
--   · event_link  : lien d'invitation d'un événement (quel événement, la personne dont c'est le lien) ;
--   · group_link  : lien d'un groupe (quel groupe, qui a créé / généré le lien) ;
--   · app_invite  : lien personnel « X t'invite sur Party » (qui) ;
--   · event_share : lien public « Partager » d'un événement (quel événement) ;
--   · direct      : inscription directe (aucun lien) ;
-- et la plateforme (ios : app iPhone ; web : site), dite à la connexion (`note_signup`, page de connexion web et
-- /api/account/verify de l'app iPhone). Les liens sont notés par la base elle-même (private.note_invite_join et
-- l'arrivée par un lien d'événement à plusieurs places) : un lien l'emporte sur « Partager », qui l'emporte sur
-- « direct » (compte de moins de 24 h) ; un lien noté n'est jamais remplacé. Comptes d'avant : aucune ligne = « Inconnu ».
-- Lecture : droit members.signup_source (« Voir l'origine des inscriptions », Admin ; Root l'a toujours), réglable dans
-- Rôles et droits. Tout part avec le compte (on delete cascade). Purement additif et rejouable.

create table if not exists private.signup_sources (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  source text not null check (source in ('event_link', 'group_link', 'app_invite', 'event_share', 'direct')),
  event_id uuid references public.events(id) on delete set null,
  group_id uuid references public.member_groups(id) on delete set null,
  inviter uuid references public.profiles(id) on delete set null,
  platform text check (platform in ('ios', 'web')),
  at timestamptz not null default now()
);
create index if not exists signup_sources_at on private.signup_sources (at desc);
revoke all on private.signup_sources from public, anon, authenticated;

create or replace function private.signup_rank(src text) returns int
language sql immutable set search_path = '' as $$
  select case src when 'direct' then 0 when 'event_share' then 1 else 2 end;
$$;
revoke all on function private.signup_rank(text) from public, anon, authenticated;

-- Note (ou précise) l'origine d'un compte de moins de 24 h. Un lien n'est jamais remplacé ; la plateforme, une fois dite, reste.
create or replace function private.note_signup_source(member uuid, src text, ev uuid, grp uuid, inv uuid, plat text)
returns void language plpgsql security definer set search_path = '' as $$
declare born timestamptz;
begin
  if member is null or src is null then return; end if;
  select p.created_at into born from public.profiles p where p.id = member;
  if born is null or born < now() - interval '24 hours' then return; end if;
  if plat is not null and plat not in ('ios', 'web') then plat := null; end if;
  insert into private.signup_sources (user_id, source, event_id, group_id, inviter, platform)
    values (member, src, ev, grp, nullif(inv, member), plat)
  on conflict (user_id) do nothing;
  if found then return; end if;
  update private.signup_sources s set
      source = src, event_id = ev, group_id = grp, inviter = nullif(inv, member), at = now()
    where s.user_id = member and private.signup_rank(src) > private.signup_rank(s.source);
  update private.signup_sources s set platform = plat
    where s.user_id = member and s.platform is null and plat is not null;
end $$;
revoke all on function private.note_signup_source(uuid, text, uuid, uuid, uuid, text) from public, anon, authenticated;

-- Arrivées par lien (lien personnel Party, lien unique d'événement ou de groupe, lien réutilisable de groupe) : déjà
-- notées ici pour « Invité par » ; l'origine de l'inscription suit.
create or replace function private.note_invite_join(member uuid, inviter uuid, kind text, tgt uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if member is null then return; end if;
  insert into private.invite_joins (user_id, invited_by, via, target)
    values (member, nullif(inviter, member), kind, tgt)
  on conflict do nothing;
  perform private.note_signup_source(member,
    case kind when 'app' then 'app_invite' when 'group' then 'group_link' else 'event_link' end,
    case when kind = 'event' then tgt end, case when kind = 'group' then tgt end, inviter, null);
end $$;
revoke all on function private.note_invite_join(uuid, uuid, text, uuid) from public, anon, authenticated;

-- Lien d'événement (ou de groupe) à plusieurs places : chaque arrivée est une ligne de private.invite_link_arrivals.
create or replace function private.signup_from_link_arrival() returns trigger
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links;
begin
  select * into l from private.invite_links il where il.token = new.token;
  if l.token is not null and l.kind in ('event', 'group') then
    perform private.note_signup_source(new.user_id, case l.kind when 'event' then 'event_link' else 'group_link' end,
      case when l.kind = 'event' then l.target end, case when l.kind = 'group' then l.target end, l.created_by, null);
  end if;
  return null;
end $$;
drop trigger if exists signup_from_link_arrival on private.invite_link_arrivals;
create trigger signup_from_link_arrival after insert on private.invite_link_arrivals
  for each row execute function private.signup_from_link_arrival();

-- À la connexion (page de connexion web, connexion native de l'app iPhone) : la plateforme, et le lien « Partager »
-- d'où l'on vient (événement public seulement). Sans effet pour un compte de plus de 24 h.
create or replace function public.note_signup(platform text, shared_event uuid default null) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if shared_event is not null and exists (select 1 from public.events ev where ev.id = shared_event and ev.public_link
       and ev.visibility = 'all' and ev.status in ('published', 'cancelled')) then
    perform private.note_signup_source(me, 'event_share', shared_event, null, null, note_signup.platform);
  else
    perform private.note_signup_source(me, 'direct', null, null, null, note_signup.platform);
  end if;
end $$;
revoke all on function public.note_signup(text, uuid) from public, anon;
grant execute on function public.note_signup(text, uuid) to authenticated;

-- Droit « Voir l'origine des inscriptions » : Admin par défaut (Root l'a toujours), réglable dans Rôles et droits.
insert into public.permissions (key, grp, label, hint, sort) values
  ('members.signup_source', 'Membres', 'Voir l''origine des inscriptions',
   'Fiche d''un membre : « Inscrit via … » (lien d''événement, de groupe, « Partager », directe ; app ou site) et compte par source', 37)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint;
do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'members_signup_source_2026_11_22') then return; end if;
  insert into public.role_permissions (role, perm) values ('admin', 'members.signup_source') on conflict do nothing;
  insert into private.one_time_changes (name) values ('members_signup_source_2026_11_22');
end $$;

-- Phrase de la fiche : « Inscrit via le lien d'invitation de « Soirée » (lien de Ludo) · app iPhone · 22.11.2026 ».
create or replace function private.signup_line(p public.profiles) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((
    select case s.source
        when 'event_link' then 'Inscrit via le lien d''invitation de « ' || coalesce(e.title, 'événement supprimé') || ' »'
        when 'group_link' then 'Inscrit via le lien du groupe « ' || coalesce(g.name, 'groupe supprimé') || ' »'
        when 'app_invite' then 'Inscrit via le lien personnel Party'
        when 'event_share' then 'Inscrit via le lien « Partager » de « ' || coalesce(e.title, 'événement supprimé') || ' »'
        else 'Inscrit directement' end
      || case when s.source in ('event_link', 'group_link', 'app_invite')
              then ' (lien de ' || coalesce(private.member_name(s.inviter), 'compte supprimé') || ')' else '' end
      || case s.platform when 'ios' then ' · app iPhone' when 'web' then ' · site' else '' end
      || ' · ' || to_char(s.at at time zone 'Europe/Zurich', 'DD.MM.YYYY')
    from private.signup_sources s
    left join public.events e on e.id = s.event_id
    left join public.member_groups g on g.id = s.group_id
    where s.user_id = p.id), 'Origine inconnue (inscrit avant le suivi des inscriptions)');
$$;
revoke all on function private.signup_line(public.profiles) from public, anon, authenticated;

-- Origine d'un membre (target) ou de tous (target null) : [{id, source, line}] ; refusé sans le droit.
create or replace function public.admin_signup_sources(target uuid default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if not public.has_perm('members.signup_source') then
    raise exception 'forbidden: il faut le droit « Voir l''origine des inscriptions »' using errcode = '42501';
  end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', p.id,
      'source', coalesce((select s.source from private.signup_sources s where s.user_id = p.id), 'unknown'),
      'line', private.signup_line(p)))
    from public.profiles p where target is null or p.id = target), '[]'::jsonb);
end $$;
revoke all on function public.admin_signup_sources(uuid) from public, anon;
grant execute on function public.admin_signup_sources(uuid) to authenticated;

-- Métrique : comptes par source et par plateforme, 30 derniers jours (date du profil) et total.
create or replace function public.admin_signup_stats() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if not public.has_perm('members.signup_source') then
    raise exception 'forbidden: il faut le droit « Voir l''origine des inscriptions »' using errcode = '42501';
  end if;
  return (with x as (
      select coalesce(s.source, 'unknown') as source, coalesce(s.platform, 'unknown') as platform,
             p.created_at >= now() - interval '30 days' as recent
      from public.profiles p left join private.signup_sources s on s.user_id = p.id)
    select jsonb_build_object(
      'sources', (select jsonb_agg(jsonb_build_object('source', k.key, 'label', k.label,
          'last30', (select count(*) from x where x.source = k.key and x.recent),
          'total', (select count(*) from x where x.source = k.key)) order by k.ord)
        from (values (1, 'event_link', 'Lien d''invitation d''un événement'), (2, 'group_link', 'Lien d''un groupe'),
                     (3, 'app_invite', 'Lien personnel Party'), (4, 'event_share', 'Lien « Partager » d''un événement'),
                     (5, 'direct', 'Inscription directe'), (6, 'unknown', 'Inconnu (avant le suivi)')) k(ord, key, label)),
      'platforms', (select jsonb_agg(jsonb_build_object('platform', k.key, 'label', k.label,
          'last30', (select count(*) from x where x.platform = k.key and x.recent),
          'total', (select count(*) from x where x.platform = k.key)) order by k.ord)
        from (values (1, 'ios', 'App iPhone'), (2, 'web', 'Site'), (3, 'unknown', 'Inconnue')) k(ord, key, label))));
end $$;
revoke all on function public.admin_signup_stats() from public, anon;
grant execute on function public.admin_signup_stats() to authenticated;

notify pgrst, 'reload schema';
