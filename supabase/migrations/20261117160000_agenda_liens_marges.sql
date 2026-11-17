-- Agenda : liens de dispo (demandes de l'admin du 17.11.2026, soir).
-- 1. Marges par lien, comme les agendas de rendez-vous : « pas disponible » N minutes avant chaque rendez-vous et
--    N minutes après (agenda_links.buffer_before_min / buffer_after_min, 0 à 240, par 5 min), autour de tout ce qui
--    rend occupé sur ce lien (calendriers choisis, soirées, demandes de rendez-vous).
-- 2. Plages « pris » envoyées sans calendrier (app iPhone d'avant le 17.11 soir : calendriers cochés « compte dans mes
--    dispos ») : elles comptent pour TOUS les liens, sinon un lien qui choisit ses calendriers ne voyait rien (bug vu le
--    17.11 : 28 plages reçues, lien « General » toujours libre).
-- Purement additive et rejouable.

alter table private.agenda_links add column if not exists buffer_before_min int not null default 0;
alter table private.agenda_links add column if not exists buffer_after_min int not null default 0;
alter table private.agenda_links drop constraint if exists agenda_links_buffers;
alter table private.agenda_links add constraint agenda_links_buffers
  check (buffer_before_min between 0 and 240 and buffer_before_min % 5 = 0 and buffer_after_min between 0 and 240 and buffer_after_min % 5 = 0);

-- Ce qui rend occupé pour UN lien : ses calendriers choisis (et les plages envoyées sans calendrier), toujours ses
-- demandes en attente / acceptées, chaque plage élargie de ses marges avant / après.
create or replace function private.agenda_link_busy(l private.agenda_links, f timestamptz, t timestamptz) returns tstzmultirange
language sql stable security definer set search_path = '' as $$
  with w as (select f - interval '5 hours' f0, t + interval '5 hours' t0),
  base as (
    select case when l.calendars is null then private.agenda_busy_of(l.user_id, (select f0 from w), (select t0 from w), 'link') else (
      select coalesce(range_agg(r), '{}'::tstzmultirange)
      from (
        select tstzrange(b.starts_at, b.ends_at) r from private.agenda_busy b, w
          where b.user_id = l.user_id and (b.cal = '' or b.cal = any (l.calendars)) and b.starts_at < w.t0 and b.ends_at > w.f0
        union all
        select p from w, private.agenda_party_spans(l.user_id, w.f0, w.t0) p
          where exists (select 1 from public.agenda_calendars c where c.user_id = l.user_id and c.kind = 'party' and c.id::text = any (l.calendars))
        union all
        select tstzrange(o.starts_at, o.ends_at) from w, private.agenda_occurrences(l.user_id, w.f0, w.t0) o
          join public.agenda_items i on i.id = o.item_id
          where i.busy and coalesce(i.calendar_id,
            (select c.id from public.agenda_calendars c where c.user_id = l.user_id and c.kind = 'personal'))::text = any (l.calendars)
        union all
        select tstzrange(k.starts_at, k.ends_at) from private.agenda_bookings k, w
          where k.owner_id = l.user_id and k.status in ('to_confirm', 'pending', 'accepted') and k.starts_at < w.t0 and k.ends_at > w.f0
      ) x where r is not null and not isempty(r)) end m
  )
  select coalesce(range_agg(tstzrange(
           private.agenda_floor30(lower(r)) - make_interval(mins => coalesce(l.buffer_before_min, 0)),
           private.agenda_ceil30(upper(r)) + make_interval(mins => coalesce(l.buffer_after_min, 0)))), '{}'::tstzmultirange)
         * tstzmultirange(tstzrange(f, t))
  from base, unnest(base.m) r;
$$;
revoke all on function private.agenda_link_busy(private.agenda_links, timestamptz, timestamptz) from public, anon, authenticated;

create or replace function private.agenda_link_json(l private.agenda_links) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', l.id, 'token', l.token, 'path', '/d/' || l.token, 'name', l.name, 'emoji', l.emoji,
    'display_name', l.display_name, 'rules', l.rules, 'horizon_days', l.horizon_days, 'duration_min', l.duration_min,
    'booking_enabled', l.booking_enabled, 'booking_fields', l.booking_fields, 'message_label', l.message_label,
    'calendars', to_jsonb(l.calendars), 'permanent', l.expires_at is null,
    'buffer_before_min', l.buffer_before_min, 'buffer_after_min', l.buffer_after_min,
    'status', case when l.stopped_at is not null then 'stopped' when l.expires_at <= now() then 'expired' else 'active' end,
    'expires_at', l.expires_at, 'stopped_at', l.stopped_at, 'views', l.views, 'last_viewed_at', l.last_viewed_at,
    'pending', (select count(*) from private.agenda_bookings k where k.link_id = l.id and k.status = 'pending'),
    'created_at', l.created_at);
$$;
revoke all on function private.agenda_link_json(private.agenda_links) from public, anon, authenticated;

-- Marge lue dans le lien envoyé par l'écran (null = inchangée) ; refus clair hors des valeurs permises.
create or replace function private.agenda_buffer(v jsonb) returns int
language plpgsql immutable set search_path = '' as $$
declare n int;
begin
  if v is null or jsonb_typeof(v) = 'null' then return null; end if;
  n := (v #>> '{}')::int;
  if n not between 0 and 240 or n % 5 <> 0 then
    raise exception 'forbidden: Marge de 0 à 4 h, par 5 minutes.' using errcode = '22023';
  end if;
  return n;
end $$;
revoke all on function private.agenda_buffer(jsonb) from public, anon, authenticated;

-- Créer (id absent) ou modifier un lien. link = {name, emoji, display_name, rules, horizon_days, duration_min,
-- booking_enabled, booking_fields, message_label, calendars, permanent, buffer_before_min, buffer_after_min}. Compte actif, profil complet, CGU ; 10 au plus.
-- permanent : true = sans fin ; false = 90 jours (dès maintenant si le lien était permanent) ; absent = inchangé
-- (nouveau lien : 90 jours).
create or replace function public.agenda_link_save(link jsonb, id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; fields jsonb; k text; dn text; lbl text; cals text[]; ends timestamptz;
        before int := private.agenda_buffer(link->'buffer_before_min'); after int := private.agenda_buffer(link->'buffer_after_min');
        days int := (select link_days from private.agenda_settings z where z.id = 1);
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.identity_complete(me) then
    raise exception 'profile_incomplete: Complète ton profil (prénom, nom, surnom) pour créer un lien.' using errcode = '42501';
  end if;
  perform private.require_terms(me);
  if agenda_link_save.id is not null then
    select * into l from private.agenda_links x where x.id = agenda_link_save.id and x.user_id = me for update;
    if l.id is null then raise exception 'not_found: Ce lien n''existe plus.' using errcode = 'PT404'; end if;
  elsif (select count(*) from private.agenda_links x where x.user_id = me) >= (select links_max from private.agenda_settings z where z.id = 1) then
    raise exception 'forbidden: Tu as déjà 10 liens. Supprimes-en un pour en créer un autre.' using errcode = '42501';
  end if;
  if not private.agenda_rules_ok(coalesce(link->'rules', l.rules)) then
    raise exception 'forbidden: Choisis au moins un jour et des heures (à la demi-heure).' using errcode = '22023';
  end if;
  fields := coalesce(link->'booking_fields', l.booking_fields,
    '{"first_name":"required","last_name":"optional","email":"required","phone":"off","message":"optional"}'::jsonb);
  if jsonb_typeof(fields) <> 'object' then raise exception 'forbidden: champs illisibles' using errcode = '22023'; end if;
  for k in select * from jsonb_object_keys(fields) loop
    if k not in ('first_name', 'last_name', 'email', 'phone', 'message') or fields->>k not in ('off', 'optional', 'required') then
      raise exception 'forbidden: champ inconnu' using errcode = '22023';
    end if;
  end loop;
  fields := jsonb_build_object('first_name', 'required', 'last_name', coalesce(fields->>'last_name', 'off'),
    'email', coalesce(fields->>'email', 'off'), 'phone', coalesce(fields->>'phone', 'off'), 'message', coalesce(fields->>'message', 'off'));
  dn := coalesce(nullif(btrim(link->>'display_name'), ''), l.display_name,
                 (select nullif(btrim(p.first_name), '') from public.profiles p where p.id = me), 'Moi');
  dn := private.moderate_text(left(dn, 40), 'name');
  lbl := nullif(btrim(coalesce(case when link ? 'message_label' then link->>'message_label' else l.message_label end, '')), '');
  if lbl is not null then lbl := private.moderate_text(left(lbl, 60), 'name'); end if;
  cals := case when link ? 'calendars' then private.agenda_link_cals(link->'calendars') else l.calendars end;
  ends := case when coalesce((link->>'permanent')::boolean, false) then null
               when link ? 'permanent' and (l.id is null or l.expires_at is null) then now() + make_interval(days => days)
               when l.id is null then now() + make_interval(days => days)
               else l.expires_at end;
  if l.id is null then
    insert into private.agenda_links (user_id, name, emoji, display_name, rules, horizon_days, duration_min, booking_enabled,
      booking_fields, message_label, calendars, expires_at, buffer_before_min, buffer_after_min)
    values (me, left(btrim(coalesce(nullif(link->>'name', ''), 'Mes dispos')), 40), nullif(link->>'emoji', ''), dn, link->'rules',
      coalesce((link->>'horizon_days')::int, 28), coalesce((link->>'duration_min')::int, 60),
      coalesce((link->>'booking_enabled')::boolean, false), fields, lbl, cals, ends, coalesce(before, 0), coalesce(after, 0))
    returning * into l;
  else
    update private.agenda_links x set
      name = left(btrim(coalesce(nullif(link->>'name', ''), x.name)), 40),
      emoji = case when link ? 'emoji' then nullif(link->>'emoji', '') else x.emoji end,
      display_name = dn, rules = coalesce(link->'rules', x.rules),
      horizon_days = coalesce((link->>'horizon_days')::int, x.horizon_days),
      duration_min = coalesce((link->>'duration_min')::int, x.duration_min),
      booking_enabled = coalesce((link->>'booking_enabled')::boolean, x.booking_enabled),
      booking_fields = fields, message_label = lbl, calendars = cals, expires_at = ends,
      buffer_before_min = coalesce(before, x.buffer_before_min), buffer_after_min = coalesce(after, x.buffer_after_min), updated_at = now()
    where x.id = l.id returning * into l;
  end if;
  return private.agenda_link_json(l);
end $$;

revoke all on function public.agenda_link_save(jsonb, uuid) from public, anon;
grant execute on function public.agenda_link_save(jsonb, uuid) to authenticated;

-- Aperçu « Voici ce que verra la personne » d'un lien en cours de réglage (rien n'est enregistré).
create or replace function public.agenda_link_preview(link jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare l private.agenda_links;
begin
  if not private.is_account_active(auth.uid()) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.agenda_rules_ok(link->'rules') then raise exception 'forbidden: Choisis au moins un jour et des heures.' using errcode = '22023'; end if;
  l.id := gen_random_uuid(); l.user_id := auth.uid(); l.rules := link->'rules';
  l.horizon_days := least(greatest(coalesce((link->>'horizon_days')::int, 28), 7), 60);
  l.duration_min := coalesce((link->>'duration_min')::int, 60);
  if l.duration_min not between 30 and 240 or l.duration_min % 30 <> 0 then l.duration_min := 60; end if;
  l.booking_enabled := coalesce((link->>'booking_enabled')::boolean, false);
  l.calendars := private.agenda_link_cals(link->'calendars');
  l.buffer_before_min := coalesce(private.agenda_buffer(link->'buffer_before_min'), 0);
  l.buffer_after_min := coalesce(private.agenda_buffer(link->'buffer_after_min'), 0);
  return jsonb_build_object('slots', private.agenda_link_free(l), 'tz', 'Europe/Zurich');
end $$;
revoke all on function public.agenda_link_preview(jsonb) from public, anon;
grant execute on function public.agenda_link_preview(jsonb) to authenticated;
