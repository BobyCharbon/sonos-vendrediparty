-- PROD, retour arrière de invitations_details (20261110100200) : invite_preview et remove_invitee d'avant, sans la
-- politique des membres d'un groupe. Tout ou rien.
begin;
drop policy if exists "profils des membres de mes groupes" on public.profiles;
drop function if exists private.shares_group(uuid, uuid);
create or replace function public.invite_preview(token uuid, opened boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text; organizer boolean := false;
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
  end if;
  state := private.invite_link_state(l);
  select display_name into who from public.profiles where id = coalesce(l.created_by, ev.created_by);
  return jsonb_build_object(
    'state', case when arrived and state <> 'revoked' then 'mine' else state end,
    'organizer', organizer,
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 then greatest(l.max_uses - l.uses, 0) end,
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
    'mine', case when (arrived or organizer) and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived or organizer then ev.id end,
    'location_address', case when arrived or organizer then ev.location_address end,
    'location_url', case when arrived or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''),
    'me_complete', me is not null and private.identity_complete(me));
end $$;

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
  -- Plus invitée : sa réponse part avec (sauf si elle voit encore l'événement autrement, ex. événement public).
  if not exists (select 1 from public.events where id = e and public_link and visibility = 'all') then
    delete from public.rsvps where event_id = e and user_id = member;
    -- Ses votes du sondage de dates partent aussi : sinon il revenait dans la liste et était inscrit à la date fixée.
    delete from public.date_votes dv using public.date_options o
      where o.id = dv.option_id and o.event_id = e and dv.user_id = member;
  end if;
end $$;

delete from supabase_migrations.schema_migrations where version = '20261110100200';
commit;
