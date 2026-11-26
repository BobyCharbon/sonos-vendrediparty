-- Présences à la main (demande de l'admin du 26.11.2026) : « Je dois pouvoir rajouter des gens à la main pour la présence.
-- Des gens qui ont un compte et des gens qui n'en ont pas. Par exemple « Pote Théo du bar », et rapidement le comptabiliser
-- dans les présents, absents, peut-être. »
--   · Membres de Party : inchangé, set_rsvp_for (la personne est prévenue).
--   · Sans compte : public.event_manual_guests (un nom de 1 à 60 caractères + Présent / Peut-être / Absent). Lue et écrite
--     par l'organisation de l'événement seulement (mêmes droits que set_rsvp_for : is_admin() = events.manage_all, ou
--     is_organizer : créateur, co-organisateurs, events.edit_others). Personne n'est prévenu, la personne ne voit rien.
--   · Les invités voient seulement les NOMBRES : event_attendance (pastille, cartes, places), public_event (page publique),
--     invite_preview (invitation), chat_event_cards (carte d'une discussion), event_guest_list (carte Invités, vue invité :
--     chiffres ; vue organisation : objet « manual »). Jamais un nom.
--   · Places : un Présent sans compte prend une place (apply_waitlist part de leur nombre) ; complet → refusé (jamais de
--     membre poussé en liste d'attente). En retirer un libère une place (la liste d'attente avance).
--   · Nom filtré comme un prénom (private.moderate_text 'name') ; Peut-être refusé si allow_maybe est faux ; date fixe et
--     événement publié seulement ; 200 au plus par événement.
--   · Temps réel : déclencheur event_changed. Récurrents : spawn_series ne recopie pas cette table. Pot commun et billets :
--     jamais concernés.
-- Purement additive et rejouable.

create table if not exists public.event_manual_guests (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 60),
  status public.rsvp_status not null default 'yes',
  added_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists event_manual_guests_event_idx on public.event_manual_guests (event_id);

alter table public.event_manual_guests enable row level security;
revoke all on public.event_manual_guests from anon;
grant select, insert, update, delete on public.event_manual_guests to authenticated;

drop policy if exists "manual guests: organisation reads" on public.event_manual_guests;
create policy "manual guests: organisation reads" on public.event_manual_guests for select to authenticated
  using (public.is_admin() or public.is_organizer(event_id));
drop policy if exists "manual guests: organisation adds" on public.event_manual_guests;
create policy "manual guests: organisation adds" on public.event_manual_guests for insert to authenticated
  with check (public.is_admin() or public.is_organizer(event_id));
drop policy if exists "manual guests: organisation changes" on public.event_manual_guests;
create policy "manual guests: organisation changes" on public.event_manual_guests for update to authenticated
  using (public.is_admin() or public.is_organizer(event_id))
  with check (public.is_admin() or public.is_organizer(event_id));
drop policy if exists "manual guests: organisation removes" on public.event_manual_guests;
create policy "manual guests: organisation removes" on public.event_manual_guests for delete to authenticated
  using (public.is_admin() or public.is_organizer(event_id));

-- Nombre de personnes sans compte d'un événement pour une réponse (jamais leurs noms).
create or replace function private.manual_guests(e uuid, s public.rsvp_status) returns int
language sql stable security definer set search_path = '' as $$
  select count(*)::int from public.event_manual_guests m where m.event_id = e and m.status = s;
$$;
revoke all on function private.manual_guests(uuid, public.rsvp_status) from public, anon, authenticated;

-- Garde : nom filtré, champs figés, date fixe + publié, Peut-être selon l'événement, places comptées.
create or replace function private.guard_manual_guest() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ev public.events; heads int;
begin
  if tg_op = 'UPDATE' then
    new.id := old.id; new.event_id := old.event_id; new.added_by := old.added_by; new.created_at := old.created_at;
  else
    new.added_by := auth.uid(); new.created_at := now();
  end if;
  new.updated_at := now();
  new.name := btrim(coalesce(new.name, ''));
  if new.name = '' then raise exception 'Écris un nom.' using errcode = '23514'; end if;
  if char_length(new.name) > 60 then raise exception 'Ce nom est trop long (60 caractères au plus).' using errcode = '23514'; end if;
  if auth.uid() is not null and (tg_op = 'INSERT' or new.name is distinct from old.name) then
    new.name := private.moderate_text(new.name, 'name');
  end if;

  select * into ev from public.events where id = new.event_id;
  if ev.id is null or ev.status <> 'published' then raise exception 'Cet événement n''est pas publié' using errcode = '23514'; end if;
  if ev.date_mode <> 'fixed' then raise exception 'Fixe d''abord la date pour noter des présences.' using errcode = '23514'; end if;
  if new.status = 'maybe' and not ev.allow_maybe then
    raise exception '« Peut-être » n''est pas proposé pour cet événement.' using errcode = '23514';
  end if;
  if tg_op = 'INSERT' and (select count(*) from public.event_manual_guests m where m.event_id = new.event_id) >= 200 then
    raise exception 'Tu as déjà ajouté 200 personnes à la main.' using errcode = '23514';
  end if;

  if new.status = 'yes' and (tg_op = 'INSERT' or old.status <> 'yes') and ev.max_participants is not null then
    perform private.lock_event_places(new.event_id);
    heads := coalesce((select sum(1 + r.plus_ones)::int from public.rsvps r
                       where r.event_id = new.event_id and r.status = 'yes' and not r.waitlisted), 0)
             + private.manual_guests(new.event_id, 'yes');
    if heads >= ev.max_participants then
      raise exception 'C''est complet : ajoute des places à l''événement pour noter quelqu''un de plus.' using errcode = 'P0001';
    end if;
  end if;
  return new;
end $$;
revoke all on function private.guard_manual_guest() from public, anon, authenticated;
drop trigger if exists event_manual_guests_guard on public.event_manual_guests;
create trigger event_manual_guests_guard before insert or update on public.event_manual_guests
  for each row execute function private.guard_manual_guest();

-- Une place libérée (retiré, ou plus Présent) : la liste d'attente avance.
create or replace function private.manual_guest_freed() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.status = 'yes' and (tg_op = 'DELETE' or new.status <> 'yes')
     and exists (select 1 from public.events e where e.id = old.event_id and e.max_participants is not null) then
    perform public.apply_waitlist(old.event_id);
  end if;
  return null;
end $$;
revoke all on function private.manual_guest_freed() from public, anon, authenticated;
drop trigger if exists event_manual_guests_freed on public.event_manual_guests;
create trigger event_manual_guests_freed after update or delete on public.event_manual_guests
  for each row execute function private.manual_guest_freed();

-- Temps réel de la fiche (et de la liste : les nombres changent).
drop trigger if exists event_changed on public.event_manual_guests;
create trigger event_changed after insert or delete or update on public.event_manual_guests
  for each row execute function private.event_changed();

create or replace function private.event_changed()
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
    if tg_table_name in ('events', 'event_groups', 'event_invites', 'rsvps', 'event_manual_guests') then perform private.party_signal('events'); end if;
  exception when others then
    null;
  end;
  return null;
end $function$;

-- Places : les Présents sans compte passent d'abord (ils ne sont jamais en liste d'attente).
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
  -- Présences notées à la main (sans compte, 26.11) : elles occupent leurs places.
  taken := private.manual_guests(e, 'yes');

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
end $function$;

-- Pastille des présents, cartes, places : les sans compte comptent (jamais de visage ni de nom pour eux).
CREATE OR REPLACE FUNCTION public.event_attendance(ids uuid[])
 RETURNS TABLE(event_id uuid, going integer, maybe integer, waitlist integer, faces jsonb)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select e.id,
    coalesce((select sum(1 + r.plus_ones)::int from public.rsvps r
              where r.event_id = e.id and r.status = 'yes' and not r.waitlisted), 0) + private.manual_guests(e.id, 'yes'),
    (select count(*)::int from public.rsvps r where r.event_id = e.id and r.status = 'maybe') + private.manual_guests(e.id, 'maybe'),
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
$function$;

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
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted)
             + private.manual_guests(ev.id, 'yes'),
    'voters', (select count(distinct dv.user_id) from public.date_votes dv join public.date_options o on o.id = dv.option_id
               where o.event_id = ev.id),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones,
                                       'note', (select n.note from public.rsvp_notes n where n.event_id = ev.id and n.user_id = r.user_id))
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$function$;

CREATE OR REPLACE FUNCTION public.chat_event_cards(ids uuid[])
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select coalesce(jsonb_agg(jsonb_build_object(
      'id', ev.id, 'title', ev.title, 'start', ev.starts_at, 'place', nullif(btrim(ev.location_name), ''), 'cover', ev.cover_url,
      'going', (select count(*) from public.rsvps r where r.event_id = ev.id and r.status = 'yes') + private.manual_guests(ev.id, 'yes'),
      'mine', coalesce((select r.status::text from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()),
                       case when exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = auth.uid())
                            then 'invited' end))
    order by array_position(ids, ev.id)), '[]'::jsonb)
  from public.events ev
  where auth.uid() is not null and ev.id = any (coalesce(ids, '{}')) and cardinality(ids) <= 100 and public.can_see_event(ev.id);
$function$;

-- Carte Invités : l'organisation reçoit « manual » (nombres par réponse) ; un invité, les chiffres seulement.
CREATE OR REPLACE FUNCTION public.event_guest_list(e uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare whole jsonb; me uuid := auth.uid(); poll boolean; people jsonb; links jsonb; waiting jsonb;
  m_yes int := private.manual_guests(e, 'yes'); m_maybe int := private.manual_guests(e, 'maybe');
  m_no int := private.manual_guests(e, 'no');
begin
  if private.manages_event(e) then
    return private.event_guest_list_full(e) || jsonb_build_object('manual', jsonb_build_object('yes', m_yes, 'maybe', m_maybe, 'no', m_no));
  end if;
  if me is null or not public.can_see_event(e)
     or not exists (select 1 from public.events x where x.id = e and x.status = 'published') then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  whole := private.event_guest_list_full(e);
  poll := coalesce((whole->>'poll')::boolean, false);
  people := whole->'people';
  links := whole->'links';
  if poll then m_yes := 0; m_maybe := 0; m_no := 0; end if;
  -- Mêmes comptes que la carte de l'organisateur (lib/invites.ts guestCounts) : un lien « une personne » encore sans
  -- réponse compte comme une personne (ouvert → pas répondu, sinon lien pas ouvert).
  select coalesce(jsonb_agg(l), '[]') into waiting from jsonb_array_elements(links) l
    where (l->>'max_uses')::int = 1 and l->>'state' in ('pending', 'opened') and jsonb_array_length(l->'arrivals') = 0;
  return jsonb_build_object(
    'guest', true, 'poll', poll, 'vip', whole->'vip', 'public', whole->'public', 'vip_name', whole->'vip_name',
    'groups', whole->'groups', 'people', '[]'::jsonb, 'requests', '[]'::jsonb,
    'counts', jsonb_build_object(
      'yes', (select count(*) from jsonb_array_elements(people) p
              where case when poll then (p->>'voted')::boolean else p->>'status' = 'yes' end) + m_yes,
      'maybe', case when poll then 0 else (select count(*) from jsonb_array_elements(people) p where p->>'status' = 'maybe') end + m_maybe,
      'no', case when poll then 0 else (select count(*) from jsonb_array_elements(people) p where p->>'status' = 'no') end + m_no,
      'none', (select count(*) from jsonb_array_elements(people) p
               where case when poll then not (p->>'voted')::boolean else p->>'status' is null end)
              + (select count(*) from jsonb_array_elements(waiting) l where l->>'state' = 'opened'),
      'unopened', (select count(*) from jsonb_array_elements(waiting) l where l->>'state' = 'pending'),
      'total', jsonb_array_length(people) + jsonb_array_length(waiting) + m_yes + m_maybe + m_no),
    -- Ses liens à lui : nombre de réponses (et demandes en attente d'accord), jamais les noms de ceux qui sont venus.
    'links', coalesce((select jsonb_agg(l || jsonb_build_object('nudged_today', false, 'arrivals',
        coalesce((select jsonb_agg(jsonb_build_object('id', null, 'name', null, 'status', a->'status', 'request', a->'request'))
                  from jsonb_array_elements(l->'arrivals') a), '[]'::jsonb)))
      from jsonb_array_elements(links) l where l->>'created_by_id' = me::text), '[]'::jsonb));
end $function$;

-- Invitation (invite_preview) : « going » compte aussi les sans compte. La fonction diffère entre les bases (champs
-- ajoutés ailleurs) : on ne remplace QUE l'expression du nombre, dans la définition en place. Rejouable (déjà fait : rien).
do $patch$
declare def text; old_expr text := $x$'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),$x$;
  new_expr text := $x$'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted) + private.manual_guests(ev.id, 'yes'),$x$;
begin
  def := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  if position('private.manual_guests' in def) > 0 then return; end if;
  if position(old_expr in def) = 0 then
    raise exception 'invite_preview : expression « going » introuvable, rien n''est modifié';
  end if;
  execute replace(def, old_expr, new_expr);
end $patch$;
