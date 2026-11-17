-- Agenda : plusieurs durées de rendez-vous par lien (demande de l'admin du 17.11.2026). Le propriétaire coche les durées
-- proposées (15 min à 4 h, par 15 min, 6 au plus) ; c'est la personne qui réserve qui choisit la sienne sur la page
-- publique, et la base vérifie que la durée fait partie de la liste et que le créneau est libre pour cette durée.
-- agenda_links.durations (null = la seule durée duration_min, liens d'avant) ; duration_min = la première (par défaut).
-- Délai minimum avant un rendez-vous (même demande) : choisi par lien (agenda_links.min_notice_min : 0 = sur le moment,
-- 30 min, 1 h, 2 h, 8 h, 24 h, 48 h, 7 jours…) ; 12 h par défaut, comme avant. Sous 24 h, les créneaux du jour même
-- deviennent possibles (avant : dès demain seulement).
-- Purement additive et rejouable ; les fonctions existantes sont ÉTENDUES par ancre.

alter table private.agenda_links add column if not exists min_notice_min int not null default 720;
alter table private.agenda_links drop constraint if exists agenda_links_min_notice_check;
alter table private.agenda_links add constraint agenda_links_min_notice_check
  check (min_notice_min between 0 and 20160 and min_notice_min % 15 = 0);

alter table private.agenda_links add column if not exists durations int[];
-- 15 min et 45 min deviennent possibles (avant : 30 à 240 par 30).
alter table private.agenda_links drop constraint if exists agenda_links_duration_min_check;
alter table private.agenda_links add constraint agenda_links_duration_min_check
  check (duration_min between 15 and 240 and duration_min % 15 = 0);
alter table private.agenda_links drop constraint if exists agenda_links_durations_check;
alter table private.agenda_links add constraint agenda_links_durations_check
  check (durations is null or (cardinality(durations) between 1 and 6 and 15 <= all (durations) and 240 >= all (durations)));

-- Durées proposées par le lien (au moins une).
create or replace function private.agenda_link_durations(l private.agenda_links) returns int[]
language sql stable set search_path = '' as $$
  select case when l.durations is null or cardinality(l.durations) = 0 then array[l.duration_min] else l.durations end;
$$;
revoke all on function private.agenda_link_durations(private.agenda_links) from public, anon, authenticated;

-- Créneaux libres pour UNE durée (mins) ; agenda_link_free(l) = celle par défaut (duration_min).
create or replace function private.agenda_link_free_for(l private.agenda_links, mins int) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare f timestamptz; t timestamptz; busy tstzmultirange; dur interval := make_interval(mins => mins); out jsonb;
begin
  f := (((now() at time zone 'Europe/Zurich')::date)::timestamp) at time zone 'Europe/Zurich';
  t := f + interval '62 days';
  busy := private.agenda_link_busy(l, f, t);
  if not l.booking_enabled then
    select coalesce(jsonb_agg(jsonb_build_array(s, e) order by s), '[]') into out from (
      select private.agenda_ceil30(lower(r)) s, private.agenda_floor30(upper(r)) e
      from unnest(coalesce((select range_agg(w) from private.agenda_link_windows(l) w), '{}'::tstzmultirange) - busy) r) z
    where e - s >= interval '30 minutes';
  else
    select coalesce(jsonb_agg(jsonb_build_array(s, s + dur) order by s), '[]') into out from (
      select distinct g.s from (
        select (dd + (x->>'from')::time) at time zone 'Europe/Zurich' w0, (dd + (x->>'to')::time) at time zone 'Europe/Zurich' w1
        from generate_series(((now() at time zone 'Europe/Zurich')::date)::timestamp,  -- dès aujourd'hui : le délai filtre
                             ((now() at time zone 'Europe/Zurich')::date + least(l.horizon_days, 60))::timestamp, interval '1 day') dd
        cross join jsonb_array_elements(l.rules) x
        where extract(isodow from dd)::int in (select (jsonb_array_elements_text(x->'days'))::int)) w
      cross join lateral generate_series(w.w0, w.w1 - dur, dur) g(s)
      where g.s >= now() + make_interval(mins => l.min_notice_min)
        and not (tstzmultirange(tstzrange(g.s, g.s + dur)) && busy)) z;
  end if;
  return out;
end $$;
revoke all on function private.agenda_link_free_for(private.agenda_links, int) from public, anon, authenticated;

create or replace function private.agenda_link_free(l private.agenda_links) returns jsonb
language sql stable security definer set search_path = '' as $$
  select private.agenda_link_free_for(l, l.duration_min);
$$;
revoke all on function private.agenda_link_free(private.agenda_links) from public, anon, authenticated;

-- Choisir les durées d'un lien (après agenda_link_save, comme le nom du lien) : triées, sans doublon, la plus courte
-- devient la durée par défaut.
create or replace function public.agenda_link_set_durations(id uuid, durations int[]) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; ds int[];
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select coalesce(array_agg(distinct d order by d), '{}') into ds from unnest(coalesce(agenda_link_set_durations.durations, '{}')) d;
  if cardinality(ds) = 0 or cardinality(ds) > 6 or exists (select 1 from unnest(ds) d where d not between 15 and 240 or d % 15 <> 0) then
    raise exception 'invalid: Choisis de 1 à 6 durées, de 15 min à 4 h.' using errcode = '22023';
  end if;
  update private.agenda_links x set durations = ds, duration_min = ds[1], updated_at = now()
  where x.id = agenda_link_set_durations.id and x.user_id = me returning * into l;
  if l.id is null then raise exception 'not_found: Ce lien n''existe plus.' using errcode = 'PT404'; end if;
  return private.agenda_link_json(l);
end $$;
revoke all on function public.agenda_link_set_durations(uuid, int[]) from public, anon;
grant execute on function public.agenda_link_set_durations(uuid, int[]) to authenticated;

-- Délai minimum avant un rendez-vous (minutes, par 15 ; 0 = sur le moment ; 14 jours au plus).
create or replace function public.agenda_link_set_notice(id uuid, minutes int) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if minutes is null or minutes not between 0 and 20160 or minutes % 15 <> 0 then
    raise exception 'invalid: Délai : de « sur le moment » à 14 jours.' using errcode = '22023';
  end if;
  update private.agenda_links x set min_notice_min = minutes, updated_at = now()
  where x.id = agenda_link_set_notice.id and x.user_id = me returning * into l;
  if l.id is null then raise exception 'not_found: Ce lien n''existe plus.' using errcode = 'PT404'; end if;
  return private.agenda_link_json(l);
end $$;
revoke all on function public.agenda_link_set_notice(uuid, int) from public, anon;
grant execute on function public.agenda_link_set_notice(uuid, int) to authenticated;

do $$ declare def text;
begin
  -- Le lien (écrans du propriétaire) : ses durées.
  def := pg_get_functiondef('private.agenda_link_json(private.agenda_links)'::regprocedure);
  if position('''durations''' in def) = 0 then
    if position($a$'duration_min', l.duration_min,$a$ in def) = 0 then raise exception 'agenda_link_json : ancre duration_min introuvable'; end if;
    execute replace(def, $a$'duration_min', l.duration_min,$a$,
      $a$'duration_min', l.duration_min, 'durations', to_jsonb(private.agenda_link_durations(l)),$a$);
  end if;
  def := pg_get_functiondef('private.agenda_link_json(private.agenda_links)'::regprocedure);
  if position('min_notice_min' in def) = 0 then
    if position($a$'durations', to_jsonb(private.agenda_link_durations(l)),$a$ in def) = 0 then raise exception 'agenda_link_json : ancre durations introuvable'; end if;
    execute replace(def, $a$'durations', to_jsonb(private.agenda_link_durations(l)),$a$,
      $a$'durations', to_jsonb(private.agenda_link_durations(l)), 'min_notice_min', l.min_notice_min,$a$);
  end if;

  -- La page publique : les durées et, s'il y en a plusieurs, les créneaux de chacune (clé = minutes).
  def := pg_get_functiondef('public.agenda_public_page(text,boolean)'::regprocedure);
  if position('''slots_by''' in def) = 0 then
    if position($a$'slots', private.agenda_link_free(l),$a$ in def) = 0 then raise exception 'agenda_public_page : ancre slots introuvable'; end if;
    execute replace(def, $a$'slots', private.agenda_link_free(l),$a$, $a$'slots', private.agenda_link_free(l),
    'durations', to_jsonb(private.agenda_link_durations(l)),
    'slots_by', case when l.booking_enabled and cardinality(private.agenda_link_durations(l)) > 1 then
      (select jsonb_object_agg(d::text, private.agenda_link_free_for(l, d)) from unnest(private.agenda_link_durations(l)) d) end,$a$);
  end if;

  -- La page publique commence aujourd'hui quand le délai le permet (demandes de rendez-vous, délai < 24 h).
  def := pg_get_functiondef('public.agenda_public_page(text,boolean)'::regprocedure);
  if position('min_notice_min' in def) = 0 then
    if position($a$'from', ((now() at time zone 'Europe/Zurich')::date + 1),$a$ in def) = 0 then raise exception 'agenda_public_page : ancre from introuvable'; end if;
    execute replace(def, $a$'from', ((now() at time zone 'Europe/Zurich')::date + 1),$a$,
      $a$'from', ((now() at time zone 'Europe/Zurich')::date + case when l.booking_enabled and l.min_notice_min < 1440 then 0 else 1 end),
    'min_notice_min', l.min_notice_min,$a$);
  end if;

  -- La demande : la durée choisie par la personne (absente = celle par défaut), seulement une des durées du lien.
  if to_regprocedure('public.agenda_booking_request(text,timestamptz,jsonb,text,integer)') is null then
    def := pg_get_functiondef('public.agenda_booking_request(text,timestamptz,jsonb,text)'::regprocedure);
    if position('ip text DEFAULT NULL::text)' in def) = 0
       or position('  e := s + make_interval(mins => l.duration_min);' in def) = 0
       or position('  slots := private.agenda_link_free(l);' in def) = 0 then
      raise exception 'agenda_booking_request : ancres introuvables';
    end if;
    def := replace(def, 'ip text DEFAULT NULL::text)', 'ip text DEFAULT NULL::text, duration integer DEFAULT NULL::integer)');
    def := replace(def, '  e := s + make_interval(mins => l.duration_min);', $a$  if agenda_booking_request.duration is not null
     and not (agenda_booking_request.duration = any (private.agenda_link_durations(l))) then
    raise exception 'invalid: Cette durée n''est pas proposée par ce lien.' using errcode = '22023';
  end if;
  e := s + make_interval(mins => coalesce(agenda_booking_request.duration, l.duration_min));$a$);
    def := replace(def, '  slots := private.agenda_link_free(l);',
      '  slots := private.agenda_link_free_for(l, coalesce(agenda_booking_request.duration, l.duration_min));');
    execute def;
    drop function public.agenda_booking_request(text, timestamptz, jsonb, text);
  end if;
end $$;
revoke all on function public.agenda_booking_request(text, timestamptz, jsonb, text, integer) from public;
grant execute on function public.agenda_booking_request(text, timestamptz, jsonb, text, integer) to anon, authenticated;

notify pgrst, 'reload schema';
