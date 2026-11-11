-- Menu de partage commun (avis 83ebee37aa0f de l'admin, 11.11.2026) : chaque invité a le même menu « Invités » que
-- l'organisateur, mais n'y voit que les CHIFFRES (viennent, peut-être, absents, pas répondu, lien pas ouvert), jamais un
-- nom ; il peut créer ses propres liens (nommés, « Plusieurs » compris), les recopier et les arrêter. L'organisateur garde
-- tout, comme avant. Purement additif et rejouable.

-- 1. La liste complète (corps inchangé de 20261108090000), réservée aux fonctions de la base.
create or replace function private.event_guest_list_full(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events; vip boolean; vip_name text;
begin
  select * into ev from public.events where id = e;
  vip := ev.visibility = 'all' and not ev.public_link;
  select name into vip_name from public.member_groups where system_key = 'vip' limit 1;
  return jsonb_build_object(
    'vip', vip, 'public', ev.public_link, 'vip_name', vip_name, 'poll', ev.date_mode = 'poll',
    'groups', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'name', g.name,
        'members', (select count(*) from public.member_group_members m where m.group_id = g.id)) order by g.name)
      from public.event_groups eg join public.member_groups g on g.id = eg.group_id where eg.event_id = e), '[]'::jsonb),
    'people', coalesce((select jsonb_agg(x order by x->>'name') from (
      select jsonb_build_object(
        'id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url,
        'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
        'answered_at', r.updated_at,
        -- Sondage de dates : a voté pour au moins une date (la réponse d'un sondage, 08.11).
        'voted', exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                         where o.event_id = e and dv.user_id = p.id),
        'source', case when i.user_id is null then (case when vip and private.is_member(p.id) then 'vip' else 'public' end)
                       when i.via_group then 'group' when i.via_link then 'link' else 'person' end,
        'group', case when i.user_id is null and vip and private.is_member(p.id) then vip_name
                      when i.via_group then (select string_agg(g.name, ', ' order by g.name) from public.event_groups eg
                        join public.member_groups g on g.id = eg.group_id
                        join public.member_group_members gm on gm.group_id = g.id and gm.user_id = p.id where eg.event_id = e) end,
        'invited_by', case when i.via_group then null else (select display_name from public.profiles where id = i.invited_by) end,
        'invited_by_id', case when i.via_group then null else i.invited_by end,
        'link_label', (select il.label from private.invite_links il where il.token = i.link_token), 'link_token', i.link_token,
        'invited_at', i.created_at,
        'has_app', private.has_app(p.id),
        'light', exists (select 1 from private.light_invitees li where li.user_id = p.id),
        'nudged_today', private.nudged_today(e, p.id, null) is not null,
        'removable', i.user_id is not null and not i.via_group) x
      from public.profiles p
      left join public.event_invites i on i.event_id = e and i.user_id = p.id
      left join public.rsvps r on r.event_id = e and r.user_id = p.id
      where p.status = 'active' and p.id <> ev.created_by
        and (i.user_id is not null or r.user_id is not null or (vip and private.is_member(p.id))
             or exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                        where o.event_id = e and dv.user_id = p.id))) s), '[]'::jsonb),
    'links', coalesce((select jsonb_agg(x order by x->>'created_at' desc) from (
      select jsonb_build_object(
        'token', l.token, 'label', l.label, 'max_uses', l.max_uses, 'uses', l.uses, 'created_at', l.created_at,
        'expires_at', l.expires_at, 'opened_at', l.opened_at, 'state', private.invite_link_state(l), 'version', l.version,
        'created_by', (select display_name from public.profiles where id = l.created_by), 'created_by_id', l.created_by,
        'nudged_today', private.nudged_today(e, null, l.token) is not null,
        'arrivals', coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id)) order by a.at)
          from private.invite_link_arrivals a join public.profiles p on p.id = a.user_id where a.token = l.token),
          case when l.used_by is not null then (select jsonb_build_array(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id)))
            from public.profiles p where p.id = l.used_by) else '[]'::jsonb end)) x
      from private.invite_links l
      where l.kind = 'event' and l.target = e and (l.revoked_at is null or l.uses > 0 or l.used_by is not null)
      order by l.created_at desc limit 60) s), '[]'::jsonb));
end $$;
revoke all on function private.event_guest_list_full(uuid) from public, anon, authenticated;

-- 2. Organisateur : la liste complète. Invité (toute personne qui voit l'événement publié) : chiffres + SES liens, sans nom.
create or replace function public.event_guest_list(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare whole jsonb; me uuid := auth.uid(); poll boolean; people jsonb; links jsonb; waiting jsonb;
begin
  if private.manages_event(e) then return private.event_guest_list_full(e); end if;
  if me is null or not public.can_see_event(e)
     or not exists (select 1 from public.events x where x.id = e and x.status = 'published') then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  whole := private.event_guest_list_full(e);
  poll := coalesce((whole->>'poll')::boolean, false);
  people := whole->'people';
  links := whole->'links';
  -- Mêmes comptes que la carte de l'organisateur (lib/invites.ts guestCounts) : un lien « une personne » encore sans
  -- réponse compte comme une personne (ouvert → pas répondu, sinon lien pas ouvert).
  select coalesce(jsonb_agg(l), '[]') into waiting from jsonb_array_elements(links) l
    where (l->>'max_uses')::int = 1 and l->>'state' in ('pending', 'opened') and jsonb_array_length(l->'arrivals') = 0;
  return jsonb_build_object(
    'guest', true, 'poll', poll, 'vip', whole->'vip', 'public', whole->'public', 'vip_name', whole->'vip_name',
    'groups', whole->'groups', 'people', '[]'::jsonb,
    'counts', jsonb_build_object(
      'yes', (select count(*) from jsonb_array_elements(people) p
              where case when poll then (p->>'voted')::boolean else p->>'status' = 'yes' end),
      'maybe', case when poll then 0 else (select count(*) from jsonb_array_elements(people) p where p->>'status' = 'maybe') end,
      'no', case when poll then 0 else (select count(*) from jsonb_array_elements(people) p where p->>'status' = 'no') end,
      'none', (select count(*) from jsonb_array_elements(people) p
               where case when poll then not (p->>'voted')::boolean else p->>'status' is null end)
              + (select count(*) from jsonb_array_elements(waiting) l where l->>'state' = 'opened'),
      'unopened', (select count(*) from jsonb_array_elements(waiting) l where l->>'state' = 'pending'),
      'total', jsonb_array_length(people) + jsonb_array_length(waiting)),
    -- Ses liens à lui : nombre de réponses, jamais les noms de ceux qui sont venus.
    'links', coalesce((select jsonb_agg(l || jsonb_build_object('nudged_today', false, 'arrivals',
        coalesce((select jsonb_agg(jsonb_build_object('id', null, 'name', null, 'status', a->'status'))
                  from jsonb_array_elements(l->'arrivals') a), '[]'::jsonb)))
      from jsonb_array_elements(links) l where l->>'created_by_id' = me::text), '[]'::jsonb));
end $$;
revoke all on function public.event_guest_list(uuid) from public, anon;
grant execute on function public.event_guest_list(uuid) to authenticated;

-- 3. Créer un lien : l'organisateur comme avant ; un invité (voit l'événement publié, profil complet) crée ses propres
-- liens, 20 en attente au plus. Le reste est inchangé (20261111100000).
create or replace function public.create_event_invite(e uuid, places int default 1, until timestamptz default null,
                                                      label text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; tok uuid; ends timestamptz; name text := nullif(btrim(coalesce(label, '')), '');
  seats int := case when places = 0 then 10000 else places end; organizer boolean := private.manages_event(e);
begin
  if not organizer and (auth.uid() is null or not public.can_see_event(e)) then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  if not organizer and not private.identity_complete(auth.uid()) then
    raise exception 'profile_required: complète ton profil pour inviter' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  if ev.status <> 'published' then raise exception 'Publie l''événement avant d''inviter'; end if;
  if seats is null or (seats <> 10000 and (seats < 1 or seats > 50)) then
    raise exception 'Entre 1 et 50 places par lien, ou sans limite';
  end if;
  if name is not null and char_length(name) > 40 then raise exception 'Nom du lien trop long (40 caractères au plus)'; end if;
  ends := case when until is null then private.event_link_end(ev)
               else least(greatest(until, now() + interval '1 hour'), now() + interval '60 days') end;
  if (select count(*) from private.invite_links il where il.kind = 'event' and il.target = e
        and il.revoked_at is null and il.expires_at > now() and il.used_by is null and il.uses < il.max_uses) >= 100 then
    raise exception 'Trop de liens en attente : arrête ceux qui ne serviront plus.';
  end if;
  if not organizer and (select count(*) from private.invite_links il where il.kind = 'event' and il.target = e
        and il.created_by = auth.uid() and il.revoked_at is null and il.expires_at > now() and il.used_by is null
        and il.uses < il.max_uses) >= 20 then
    raise exception 'Tu as déjà 20 liens en attente : arrête ceux qui ne serviront plus.';
  end if;
  insert into private.invite_links (kind, target, created_by, expires_at, max_uses, label, version, follows_event)
    values ('event', e, auth.uid(), ends, seats, name, 2, until is null) returning token into tok;
  return jsonb_build_object('token', tok, 'expires_at', ends, 'max_uses', seats, 'label', name);
end $$;

-- 4. Arrêter un lien : l'organisateur, ou la personne qui l'a créé.
create or replace function public.revoke_invite_link(tok uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links;
begin
  select * into l from private.invite_links where token = tok;
  if l.token is null or not ((l.kind = 'event' and (private.manages_event(l.target) or l.created_by = auth.uid()))
                             or (l.kind = 'group' and private.manages_group(l.target))) then
    raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501';
  end if;
  update private.invite_links set revoked_at = now() where token = tok and used_by is null and revoked_at is null;
end $$;
