-- Invitations : détails de la recette réelle du 10.11.2026, suite (avis de l'admin : « reprends les défauts »).
-- Purement additif et rejouable.
-- 1. La carte d'un lien dit d'emblée « tu as été retiré » (state 'removed', plus de boutons de réponse) ; une personne
--    déjà invitée autrement qui ouvre un lien plein ou fermé reçoit l'événement (already + event_id) ; un lien fermé
--    n'annonce plus « reste N places » (places_left seulement pour un lien encore ouvert ; multi dit s'il était pour plusieurs).
-- 2. Retirer un invité venu par un lien pour plusieurs rend sa place au lien.
-- 3. Les membres d'un même groupe voient le surnom et la photo les uns des autres (un Guest voyait « ? »). Le numéro
--    reste illisible (colonne fermée), comme pour les participants d'un événement.

-- 1. Carte du lien ------------------------------------------------------------------------------------------------------
create or replace function public.invite_preview(token uuid, opened boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text; organizer boolean := false; already boolean := false; removed boolean := false;
begin
  if token is null then return null; end if;
  select * into l from private.invite_links il where il.token = invite_preview.token and il.kind = 'event';
  if l.token is null then return null; end if;
  select * into ev from public.events where id = l.target and status in ('published', 'cancelled');
  if ev.id is null then return null; end if;
  if me is not null then organizer := public.is_organizer(ev.id); end if;
  -- L'auteur du lien et les organisateurs ne comptent pas comme une ouverture.
  if opened and l.opened_at is null and me is distinct from l.created_by and not organizer and l.revoked_at is null then
    update private.invite_links il set opened_at = now() where il.token = l.token;
  end if;
  if me is not null then
    arrived := l.used_by = me or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
    select * into mine from public.rsvps r where r.event_id = ev.id and r.user_id = me;
    -- Retiré de la liste par l'organisateur (venu par ce lien, ne voit plus l'événement) : on le dit d'emblée.
    removed := arrived and not organizer and not public.can_see_event(ev.id);
    -- Déjà invité autrement (liste, groupe, autre lien) ou déjà répondu : la carte mène à l'événement.
    already := not arrived and not organizer and (mine.event_id is not null
      or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me));
  end if;
  state := private.invite_link_state(l);
  select display_name into who from public.profiles where id = coalesce(l.created_by, ev.created_by);
  return jsonb_build_object(
    'state', case when removed then 'removed' when arrived and state <> 'revoked' then 'mine' else state end,
    'already', already,
    'organizer', organizer,
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 and state in ('pending', 'opened') then greatest(l.max_uses - l.uses, 0) end,
    'multi', l.max_uses > 1,
    'inviter', nullif(btrim(coalesce(who, '')), ''),
    'title', ev.title, 'status', ev.status, 'date_mode', ev.date_mode,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', coalesce(ev.location_name, case when arrived or organizer then ev.location_address end),
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'description', left(ev.description, 400),
    'allow_maybe', ev.allow_maybe,
    'closed', (ev.rsvp_deadline is not null and now() > ev.rsvp_deadline)
              or (ev.date_mode = 'poll' and ev.poll_deadline is not null and now() > ev.poll_deadline),
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select nullif(btrim(p.display_name), '') n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and nullif(btrim(p.display_name), '') is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Sondage (10.11) : les personnes qui ont voté au moins une date, comme le sondage de la fiche.
    'voters', (select count(distinct dv.user_id) from public.date_votes dv join public.date_options o on o.id = dv.option_id
               where o.event_id = ev.id),
    'voter_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select nullif(btrim(p.display_name), '') n from public.profiles p
        where exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                      where o.event_id = ev.id and dv.user_id = p.id)
          and nullif(btrim(p.display_name), '') is not null
        order by p.display_name limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    'mine', case when (arrived or organizer or already) and not removed and mine.event_id is not null then mine.status::text end,
    'event_id', case when (arrived and not removed) or organizer or already then ev.id end,
    'location_address', case when arrived or organizer then ev.location_address end,
    'location_url', case when arrived or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''),
    'me_complete', me is not null and private.identity_complete(me));
end $$;

-- 2. Retirer un invité ----------------------------------------------------------------------------------------------
create or replace function public.remove_invitee(e uuid, member uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  if not exists (select 1 from public.event_invites where event_id = e and user_id = member and not via_group) then
    raise exception 'Cette personne vient avec un groupe : retire le groupe dans « Modifier ».';
  end if;
  delete from public.event_invites where event_id = e and user_id = member and not via_group;
  -- Venu par un lien pour plusieurs : sa place est rendue au lien (il ne peut pas revenir par ce lien : « retiré »).
  update private.invite_links il set uses = greatest(il.uses - 1, 0)
    where il.kind = 'event' and il.target = e and il.max_uses > 1
      and exists (select 1 from private.invite_link_arrivals a where a.token = il.token and a.user_id = member);
  -- Plus invitée : sa réponse part avec (sauf si elle voit encore l'événement autrement, ex. événement public).
  if not exists (select 1 from public.events where id = e and public_link and visibility = 'all') then
    delete from public.rsvps where event_id = e and user_id = member;
    -- Ses votes du sondage de dates partent aussi : sinon il revenait dans la liste et était inscrit à la date fixée.
    delete from public.date_votes dv using public.date_options o
      where o.id = dv.option_id and o.event_id = e and dv.user_id = member;
  end if;
end $$;

-- 3. Profils des membres de mes groupes ---------------------------------------------------------------------------
create or replace function private.shares_group(a uuid, b uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_group_members x join public.member_group_members y on y.group_id = x.group_id
                 join public.member_groups g on g.id = x.group_id
                 where x.user_id = a and y.user_id = b and g.system_key is null);
$$;
revoke all on function private.shares_group(uuid, uuid) from public, anon;
grant execute on function private.shares_group(uuid, uuid) to authenticated;

drop policy if exists "profils des membres de mes groupes" on public.profiles;
create policy "profils des membres de mes groupes" on public.profiles for select to authenticated
  using (private.shares_group((select auth.uid()), id));
