-- PROD, retour arrière de sondage_corrections (20261108110000) : remove_invitee, do_fix_event_date et invite_preview d'avant. Tout ou rien.
begin;
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
  end if;
end $$;

create or replace function public.do_fix_event_date(e uuid, opt uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
declare o date_options; ev events; v record;
begin
  perform private.lock_event_places(e);
  select * into o from date_options where id = opt and event_id = e;
  if not found then raise exception 'Créneau introuvable'; end if;
  update events set date_mode = 'fixed', starts_at = o.starts_at, ends_at = o.ends_at where id = e;
  select * into ev from events where id = e;
  for v in select dv.user_id, dv.vote from date_votes dv
           where dv.option_id = opt and dv.vote in ('yes', 'if_needed')
           order by (dv.vote = 'yes') desc, dv.user_id loop
    -- « Si besoin » sans « Peut-être » : aucune réponse (07.11), la personne répondra elle-même.
    continue when v.vote = 'if_needed' and not ev.allow_maybe;
    -- Sans liste d'attente : seuls les « Oui » qui tiennent dans les places sont inscrits.
    continue when v.vote = 'yes' and not ev.waitlist_enabled and ev.max_participants is not null
      and (select coalesce(sum(1 + r.plus_ones), 0) from rsvps r
           where r.event_id = e and r.status = 'yes' and not r.waitlisted) >= ev.max_participants;
    -- Le vote pour la date retenue décide (08.11) : il remplace une ancienne réponse donnée par un lien.
    insert into rsvps (event_id, user_id, status)
    values (e, v.user_id, case v.vote when 'yes' then 'yes'::rsvp_status else 'maybe'::rsvp_status end)
    on conflict (event_id, user_id) do update set status = excluded.status;
  end loop;
  -- « Non » à la date retenue : ne vient pas, même s'il avait dit « je viens » par un lien avant le sondage.
  insert into rsvps (event_id, user_id, status)
  select e, dv.user_id, 'no'::rsvp_status from date_votes dv where dv.option_id = opt and dv.vote = 'no'
  on conflict (event_id, user_id) do update set status = 'no';
  perform apply_waitlist(e);
end $$;


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
    'closed', ev.rsvp_deadline is not null and now() > ev.rsvp_deadline,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select nullif(btrim(p.display_name), '') n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and nullif(btrim(p.display_name), '') is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Ce que voit la personne qui a déjà répondu par ce lien, ou un organisateur (changer sa réponse, adresse, itinéraire).
    'mine', case when (arrived or organizer) and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived or organizer then ev.id end,
    'location_address', case when arrived or organizer then ev.location_address end,
    'location_url', case when arrived or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''));
end $$;

delete from supabase_migrations.schema_migrations where version = '20261108110000';
commit;

notify pgrst, 'reload schema';
