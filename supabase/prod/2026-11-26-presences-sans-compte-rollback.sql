-- Retour arrière de 2026-11-26-presences-sans-compte-apply.sql : les fonctions reprennent leur définition de prod
-- d'avant (lue le 26.11), puis la table des présences sans compte est supprimée (ses lignes avec).
begin;
CREATE OR REPLACE FUNCTION public.apply_waitlist(e uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare ev events; taken int := 0; fit int; r record; prev text; body text; wants boolean;
begin
  -- Une seule transaction à la fois range les places d'un événement : la suivante attend, puis relit les réponses
  -- validées entre-temps (lecture validée : chaque requête voit les autres transactions terminées).
  perform private.lock_event_places(e);
  prev := coalesce(current_setting('party.applying_waitlist', true), '');
  perform set_config('party.applying_waitlist', 'on', true);
  select * into ev from events where id = e;
  if ev.max_participants is null then
    update rsvps set waitlisted = false, plus_ones = plus_ones + plus_ones_waitlisted,
                     plus_ones_waitlisted = 0, plus_ones_waitlisted_since = null
      where event_id = e and (waitlisted or plus_ones_waitlisted > 0);
    perform set_config('party.applying_waitlist', prev, true);
    return;
  end if;

  for r in select * from rsvps where event_id = e and status = 'yes' and not waitlisted order by updated_at, user_id loop
    if taken + 1 > ev.max_participants then
      update rsvps set waitlisted = true, plus_ones = r.plus_ones + r.plus_ones_waitlisted,
                       plus_ones_waitlisted = 0, plus_ones_waitlisted_since = null
        where event_id = e and user_id = r.user_id;
    else
      fit := least(r.plus_ones, ev.max_participants - taken - 1);
      taken := taken + 1 + fit;
      if fit < r.plus_ones then
        update rsvps set plus_ones = fit, plus_ones_waitlisted = r.plus_ones_waitlisted + r.plus_ones - fit,
                         plus_ones_waitlisted_since = coalesce(r.plus_ones_waitlisted_since, now())
          where event_id = e and user_id = r.user_id;
      end if;
    end if;
  end loop;

  for r in
    select q.* from (
      select x.user_id, true as person, x.updated_at as since, x.plus_ones as n
        from rsvps x where x.event_id = e and x.status = 'yes' and x.waitlisted
      union all
      select x.user_id, false, x.plus_ones_waitlisted_since, x.plus_ones_waitlisted
        from rsvps x where x.event_id = e and x.status = 'yes' and not x.waitlisted and x.plus_ones_waitlisted > 0
    ) q order by q.since nulls last, q.person desc, q.user_id
  loop
    exit when taken >= ev.max_participants;
    if r.person then
      fit := least(r.n, ev.max_participants - taken - 1);
      taken := taken + 1 + fit;
      update rsvps set waitlisted = false, plus_ones = fit, plus_ones_waitlisted = r.n - fit,
                       plus_ones_waitlisted_since = case when r.n > fit then r.since end
        where event_id = e and user_id = r.user_id;
      body := 'Tu es inscrit à « ' || ev.title || ' ».'
        || case when r.n > fit then ' ' || case when r.n - fit > 1 then 'Tes accompagnants restent' else 'Ton accompagnant reste' end
                || ' en liste d''attente.' else '' end;
    else
      fit := least(r.n, ev.max_participants - taken);
      taken := taken + fit;
      update rsvps set plus_ones = plus_ones + fit, plus_ones_waitlisted = plus_ones_waitlisted - fit,
                       plus_ones_waitlisted_since = case when plus_ones_waitlisted - fit > 0 then plus_ones_waitlisted_since end
        where event_id = e and user_id = r.user_id;
      body := case when fit > 1 then 'Tes ' || fit || ' accompagnants sont inscrits' else 'Ton accompagnant est inscrit' end
        || ' à « ' || ev.title || ' ».';
    end if;
    -- since = now() : réponse ou accompagnant donné dans cette transaction, pas une vraie attente.
    select p.waitlist into wants from notification_prefs p where p.user_id = r.user_id;
    if r.since < now() and coalesce(wants, false) then
      perform queue_notification(r.user_id, 'waitlist', e, 'Une place s''est libérée', body);
    end if;
  end loop;

  -- Liste d'attente coupée (07.11) : une réponse ou un accompagnant DONNÉ DANS CETTE TRANSACTION qui ne tient pas
  -- est refusé (rien n'est mis en attente). Ceux qui attendaient déjà (option coupée après coup, places réduites
  -- par l'organisateur) restent dans la file : on ne retire jamais quelqu'un sans le prévenir.
  if not ev.waitlist_enabled then
    if exists (select 1 from rsvps where event_id = e and status = 'yes' and waitlisted and updated_at = now()) then
      raise exception 'C''est complet.' using errcode = 'P0001';
    end if;
    if exists (select 1 from rsvps where event_id = e and status = 'yes' and plus_ones_waitlisted > 0
               and plus_ones_waitlisted_since = now()) then
      raise exception 'C''est complet : il n''y a plus de place pour un accompagnant.' using errcode = 'P0001';
    end if;
  end if;
  perform set_config('party.applying_waitlist', prev, true);
end $function$
;
CREATE OR REPLACE FUNCTION public.chat_event_cards(ids uuid[])
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select coalesce(jsonb_agg(jsonb_build_object(
      'id', ev.id, 'title', ev.title, 'start', ev.starts_at, 'place', nullif(btrim(ev.location_name), ''), 'cover', ev.cover_url,
      'going', (select count(*) from public.rsvps r where r.event_id = ev.id and r.status = 'yes'),
      'mine', coalesce((select r.status::text from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()),
                       case when exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = auth.uid())
                            then 'invited' end))
    order by array_position(ids, ev.id)), '[]'::jsonb)
  from public.events ev
  where auth.uid() is not null and ev.id = any (coalesce(ids, '{}')) and cardinality(ids) <= 100 and public.can_see_event(ev.id);
$function$
;
CREATE OR REPLACE FUNCTION public.event_attendance(ids uuid[])
 RETURNS TABLE(event_id uuid, going integer, maybe integer, waitlist integer, faces jsonb)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select e.id,
    coalesce((select sum(1 + r.plus_ones)::int from public.rsvps r
              where r.event_id = e.id and r.status = 'yes' and not r.waitlisted), 0),
    (select count(*)::int from public.rsvps r where r.event_id = e.id and r.status = 'maybe'),
    (select count(*)::int from public.rsvps r where r.event_id = e.id and r.status = 'yes' and r.waitlisted),
    case when private.sees_participants(e.id) then coalesce((
      select jsonb_agg(jsonb_build_object('id', f.id, 'name', f.display_name, 'avatar_url', f.avatar_url) order by f.at)
      from (select p.id, p.display_name, p.avatar_url, r.updated_at as at
            from public.rsvps r join public.profiles p on p.id = r.user_id
            where r.event_id = e.id and r.status = 'yes' and not r.waitlisted and p.status = 'active'
            order by r.updated_at limit 3) f), '[]'::jsonb)
    else '[]'::jsonb end
  from public.events e
  where e.id = any(ids[1:200]) and public.can_see_event(e.id);
$function$
;
CREATE OR REPLACE FUNCTION private.event_changed()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
declare
  r jsonb;
  e uuid;
begin
  if tg_op = 'DELETE' then r := to_jsonb(old); else r := to_jsonb(new); end if;
  begin
    e := case tg_table_name
      when 'events' then (r->>'id')::uuid
      when 'poll_options' then (select p.event_id from polls p where p.id = (r->>'poll_id')::uuid)
      when 'poll_votes' then (select p.event_id from polls p where p.id = (r->>'poll_id')::uuid)
      when 'date_votes' then (select o.event_id from date_options o where o.id = (r->>'option_id')::uuid)
      when 'bring_claims' then (select b.event_id from bring_items b where b.id = (r->>'item_id')::uuid)
      when 'message_reactions' then (select m.event_id from messages m where m.id = (r->>'message_id')::uuid)
      else (r->>'event_id')::uuid
    end;
    if e is not null then perform private.party_signal('event:' || e::text); end if;
    -- Ce qui change la liste des événements (apparaît, disparaît, change de titre ou de date, réponses).
    if tg_table_name in ('events', 'event_groups', 'event_invites', 'rsvps') then perform private.party_signal('events'); end if;
  exception when others then
    null;
  end;
  return null;
end $function$
;
CREATE OR REPLACE FUNCTION public.event_guest_list(e uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
    'groups', whole->'groups', 'people', '[]'::jsonb, 'requests', '[]'::jsonb,
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
    -- Ses liens à lui : nombre de réponses (et demandes en attente d'accord), jamais les noms de ceux qui sont venus.
    'links', coalesce((select jsonb_agg(l || jsonb_build_object('nudged_today', false, 'arrivals',
        coalesce((select jsonb_agg(jsonb_build_object('id', null, 'name', null, 'status', a->'status', 'request', a->'request'))
                  from jsonb_array_elements(l->'arrivals') a), '[]'::jsonb)))
      from jsonb_array_elements(links) l where l->>'created_by_id' = me::text), '[]'::jsonb));
end $function$
;
CREATE OR REPLACE FUNCTION public.public_event(e uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'price_chf', ev.price_chf, 'allow_maybe', ev.allow_maybe, 'rsvp_deadline', ev.rsvp_deadline,
    'max_participants', ev.max_participants,
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'voters', (select count(distinct dv.user_id) from public.date_votes dv join public.date_options o on o.id = dv.option_id
               where o.event_id = ev.id),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones,
                                       'note', (select n.note from public.rsvp_notes n where n.event_id = ev.id and n.user_id = r.user_id))
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$function$
;

do $patch$
declare def text := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
begin
  if position(' + private.manual_guests(ev.id, ''yes''),' in def) > 0 then
    execute replace(def, ' + private.manual_guests(ev.id, ''yes''),', ',');
  end if;
end $patch$;

drop table if exists public.event_manual_guests;
drop function if exists private.guard_manual_guest();
drop function if exists private.manual_guest_freed();
drop function if exists private.manual_guests(uuid, public.rsvp_status);
delete from supabase_migrations.schema_migrations where version = '20261126150000';
commit;
