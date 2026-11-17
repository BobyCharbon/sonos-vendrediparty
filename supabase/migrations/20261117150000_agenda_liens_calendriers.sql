-- Agenda : liens de dispo (demande de l'admin du 17.11.2026).
-- 1. Chaque lien choisit les calendriers qui rendent occupé (agenda_links.calendars, clés : id d'un calendrier de Party
--    — soirées Party, « Juste pour moi », agenda .ics — ou « ios:<id> » pour un calendrier de l'iPhone). null = tout
--    ce qui est envoyé (liens d'avant). Les demandes de rendez-vous en attente / acceptées comptent toujours.
--    Les plages « pris » arrivent donc par calendrier (agenda_busy.cal, jamais un nom ni un titre) ; « Qui est libre ? »
--    ne lit que celles des calendriers qui comptent pour les groupes (agenda_busy.for_groups).
-- 2. Un lien peut être permanent (expires_at null) : il ne s'arrête que quand on l'arrête.
-- Purement additive et rejouable.

alter table private.agenda_links add column if not exists calendars text[];
alter table private.agenda_links alter column expires_at drop not null;

alter table private.agenda_busy add column if not exists cal text not null default '';
alter table private.agenda_busy add column if not exists for_groups boolean not null default true;
alter table private.agenda_busy drop constraint if exists agenda_busy_pkey;
alter table private.agenda_busy add constraint agenda_busy_pkey primary key (user_id, source, cal, for_groups, starts_at);
alter table private.agenda_busy drop constraint if exists agenda_busy_cal;
alter table private.agenda_busy add constraint agenda_busy_cal check (cal ~ '^(|ios:[A-Za-z0-9:_.-]{1,120}|[0-9a-f-]{36})$');

-- Clé de calendrier valable (ce que la page et l'app envoient).
create or replace function private.agenda_cal_key_ok(k text) returns boolean
language sql immutable set search_path = '' as $$
  select coalesce(k, '') ~ '^(ios:[A-Za-z0-9:_.-]{1,120}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$';
$$;
revoke all on function private.agenda_cal_key_ok(text) from public, anon, authenticated;

-- mode 'group' : ce que la personne a choisi de partager (calendriers qui comptent pour les groupes) ;
-- mode 'link' : tout ce qui la rend prise (liens d'avant, sans liste de calendriers).
create or replace function private.agenda_busy_of(uid uuid, f timestamptz, t timestamptz, mode text) returns tstzmultirange
language sql stable security definer set search_path = '' as $$
  select coalesce(range_agg(tstzrange(private.agenda_floor30(lower(r)), private.agenda_ceil30(upper(r)))), '{}'::tstzmultirange)
         * tstzmultirange(tstzrange(f, t))
  from (
    select tstzrange(b.starts_at, b.ends_at) r from private.agenda_busy b
      where b.user_id = uid and b.starts_at < t and b.ends_at > f and (mode = 'link' or b.for_groups)
    union all
    select p from private.agenda_party_spans(uid, f, t) p
      where mode = 'link' or exists (select 1 from private.agenda_sharing s where s.user_id = uid and s.share_party)
    union all
    select tstzrange(o.starts_at, o.ends_at) from private.agenda_occurrences(uid, f, t) o
      join public.agenda_items i on i.id = o.item_id
      where i.busy and (mode = 'link' or exists (select 1 from private.agenda_sharing s where s.user_id = uid and s.share_manual))
    union all
    select tstzrange(k.starts_at, k.ends_at) from private.agenda_bookings k
      where mode = 'link' and k.owner_id = uid and k.status in ('to_confirm', 'pending', 'accepted') and k.starts_at < t and k.ends_at > f
  ) x where r is not null and not isempty(r);
$$;
revoke all on function private.agenda_busy_of(uuid, timestamptz, timestamptz, text) from public, anon, authenticated;

-- Ce qui rend occupé pour UN lien : ses calendriers choisis, et toujours ses demandes en attente / acceptées.
create or replace function private.agenda_link_busy(l private.agenda_links, f timestamptz, t timestamptz) returns tstzmultirange
language sql stable security definer set search_path = '' as $$
  select case when l.calendars is null then private.agenda_busy_of(l.user_id, f, t, 'link') else (
    select coalesce(range_agg(tstzrange(private.agenda_floor30(lower(r)), private.agenda_ceil30(upper(r)))), '{}'::tstzmultirange)
           * tstzmultirange(tstzrange(f, t))
    from (
      select tstzrange(b.starts_at, b.ends_at) r from private.agenda_busy b
        where b.user_id = l.user_id and b.cal = any (l.calendars) and b.starts_at < t and b.ends_at > f
      union all
      select p from private.agenda_party_spans(l.user_id, f, t) p
        where exists (select 1 from public.agenda_calendars c where c.user_id = l.user_id and c.kind = 'party' and c.id::text = any (l.calendars))
      union all
      select tstzrange(o.starts_at, o.ends_at) from private.agenda_occurrences(l.user_id, f, t) o
        join public.agenda_items i on i.id = o.item_id
        where i.busy and coalesce(i.calendar_id,
          (select c.id from public.agenda_calendars c where c.user_id = l.user_id and c.kind = 'personal'))::text = any (l.calendars)
      union all
      select tstzrange(k.starts_at, k.ends_at) from private.agenda_bookings k
        where k.owner_id = l.user_id and k.status in ('to_confirm', 'pending', 'accepted') and k.starts_at < t and k.ends_at > f
    ) x where r is not null and not isempty(r)) end;
$$;
revoke all on function private.agenda_link_busy(private.agenda_links, timestamptz, timestamptz) from public, anon, authenticated;

-- Ce que voit l'inconnu : sans demandes, les plages libres (≥ 30 min) ; avec demandes, des créneaux à la suite de la
-- durée du lien, alignés sur le début de chaque plage du lien, entièrement libres. Rien sur un « pris ».
create or replace function private.agenda_link_free(l private.agenda_links) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare f timestamptz; t timestamptz; busy tstzmultirange; dur interval := make_interval(mins => l.duration_min); out jsonb;
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
        from generate_series(((now() at time zone 'Europe/Zurich')::date + 1)::timestamp,
                             ((now() at time zone 'Europe/Zurich')::date + least(l.horizon_days, 60))::timestamp, interval '1 day') dd
        cross join jsonb_array_elements(l.rules) x
        where extract(isodow from dd)::int in (select (jsonb_array_elements_text(x->'days'))::int)) w
      cross join lateral generate_series(w.w0, w.w1 - dur, dur) g(s)
      where g.s >= now() + interval '12 hours'
        and not (tstzmultirange(tstzrange(g.s, g.s + dur)) && busy)) z;
  end if;
  return out;
end $$;
revoke all on function private.agenda_link_free(private.agenda_links) from public, anon, authenticated;

create or replace function private.agenda_link_active(l private.agenda_links) returns boolean
language sql stable security definer set search_path = '' as $$
  select l.id is not null and l.stopped_at is null and (l.expires_at is null or l.expires_at > now())
     and private.is_account_active(l.user_id);
$$;
revoke all on function private.agenda_link_active(private.agenda_links) from public, anon, authenticated;

create or replace function private.agenda_link_json(l private.agenda_links) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', l.id, 'token', l.token, 'path', '/d/' || l.token, 'name', l.name, 'emoji', l.emoji,
    'display_name', l.display_name, 'rules', l.rules, 'horizon_days', l.horizon_days, 'duration_min', l.duration_min,
    'booking_enabled', l.booking_enabled, 'booking_fields', l.booking_fields, 'message_label', l.message_label,
    'calendars', to_jsonb(l.calendars), 'permanent', l.expires_at is null,
    'status', case when l.stopped_at is not null then 'stopped' when l.expires_at <= now() then 'expired' else 'active' end,
    'expires_at', l.expires_at, 'stopped_at', l.stopped_at, 'views', l.views, 'last_viewed_at', l.last_viewed_at,
    'pending', (select count(*) from private.agenda_bookings k where k.link_id = l.id and k.status = 'pending'),
    'created_at', l.created_at);
$$;
revoke all on function private.agenda_link_json(private.agenda_links) from public, anon, authenticated;

-- Liste de calendriers d'un lien (jsonb) : null = tout ; sinon 60 clés au plus, chacune valable.
create or replace function private.agenda_link_cals(v jsonb) returns text[]
language plpgsql immutable set search_path = '' as $$
declare out text[];
begin
  if v is null or jsonb_typeof(v) = 'null' then return null; end if;
  if jsonb_typeof(v) <> 'array' or jsonb_array_length(v) > 60 then
    raise exception 'forbidden: calendriers illisibles' using errcode = '22023';
  end if;
  select coalesce(array_agg(distinct x), '{}') into out from jsonb_array_elements_text(v) x;
  if exists (select 1 from unnest(out) k where not private.agenda_cal_key_ok(k)) then
    raise exception 'forbidden: calendrier inconnu' using errcode = '22023';
  end if;
  return out;
end $$;
revoke all on function private.agenda_link_cals(jsonb) from public, anon, authenticated;

-- Créer (id absent) ou modifier un lien. link = {name, emoji, display_name, rules, horizon_days, duration_min,
-- booking_enabled, booking_fields, message_label, calendars, permanent}. Compte actif, profil complet, CGU ; 10 au plus.
-- permanent : true = sans fin ; false = 90 jours (dès maintenant si le lien était permanent) ; absent = inchangé
-- (nouveau lien : 90 jours).
create or replace function public.agenda_link_save(link jsonb, id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; fields jsonb; k text; dn text; lbl text; cals text[]; ends timestamptz;
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
      booking_fields, message_label, calendars, expires_at)
    values (me, left(btrim(coalesce(nullif(link->>'name', ''), 'Mes dispos')), 40), nullif(link->>'emoji', ''), dn, link->'rules',
      coalesce((link->>'horizon_days')::int, 28), coalesce((link->>'duration_min')::int, 60),
      coalesce((link->>'booking_enabled')::boolean, false), fields, lbl, cals, ends)
    returning * into l;
  else
    update private.agenda_links x set
      name = left(btrim(coalesce(nullif(link->>'name', ''), x.name)), 40),
      emoji = case when link ? 'emoji' then nullif(link->>'emoji', '') else x.emoji end,
      display_name = dn, rules = coalesce(link->'rules', x.rules),
      horizon_days = coalesce((link->>'horizon_days')::int, x.horizon_days),
      duration_min = coalesce((link->>'duration_min')::int, x.duration_min),
      booking_enabled = coalesce((link->>'booking_enabled')::boolean, x.booking_enabled),
      booking_fields = fields, message_label = lbl, calendars = cals, expires_at = ends, updated_at = now()
    where x.id = l.id returning * into l;
  end if;
  return private.agenda_link_json(l);
end $$;

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
  return jsonb_build_object('slots', private.agenda_link_free(l), 'tz', 'Europe/Zurich');
end $$;
revoke all on function public.agenda_link_save(jsonb, uuid), public.agenda_link_preview(jsonb) from public, anon;
grant execute on function public.agenda_link_save(jsonb, uuid), public.agenda_link_preview(jsonb) to authenticated;

-- Plages « pris » d'une source (l'iPhone ou le web) : blocks = [{s, e, c, g}] ; c = clé du calendrier (« ios:<id> » ou
-- id d'un agenda .ics), g = compte aussi pour les groupes. Arrondies à 30 min, 60 jours au plus, fusionnées par
-- calendrier, 3000 au plus. Permis seulement avec un partage actif (un groupe) ou un lien public actif.
create or replace function public.agenda_set_busy(source text, blocks jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); f timestamptz := private.agenda_floor30(now()); t timestamptz := private.agenda_floor30(now()) + interval '60 days';
        n int;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if source not in ('device', 'web') then raise exception 'forbidden: source inconnue' using errcode = '22023'; end if;
  if not exists (select 1 from private.agenda_group_shares s where s.user_id = me)
     and not exists (select 1 from private.agenda_links l where l.user_id = me and private.agenda_link_active(l)) then
    raise exception 'forbidden: Active d''abord le partage de tes dispos.' using errcode = '42501';
  end if;
  if jsonb_typeof(coalesce(blocks, '[]')) <> 'array' or jsonb_array_length(coalesce(blocks, '[]')) > 5000 then
    raise exception 'forbidden: plages illisibles' using errcode = '22023';
  end if;
  if exists (select 1 from jsonb_array_elements(coalesce(blocks, '[]')) b
             where coalesce(b->>'c', '') <> '' and not private.agenda_cal_key_ok(b->>'c')) then
    raise exception 'forbidden: calendrier inconnu' using errcode = '22023';
  end if;
  delete from private.agenda_busy where user_id = me and agenda_busy.source = agenda_set_busy.source;
  insert into private.agenda_busy (user_id, source, cal, for_groups, starts_at, ends_at)
  select me, agenda_set_busy.source, m.c, m.g, lower(r), upper(r)
  from (
    select coalesce(b->>'c', '') c, coalesce((b->>'g')::boolean, true) g,
           range_agg(tstzrange(private.agenda_floor30((b->>'s')::timestamptz), private.agenda_ceil30((b->>'e')::timestamptz)))
             * tstzmultirange(tstzrange(f, t)) mr
    from jsonb_array_elements(coalesce(blocks, '[]')) b
    where (b->>'s')::timestamptz < (b->>'e')::timestamptz
    group by 1, 2
  ) m cross join lateral unnest(m.mr) r
  where not isempty(r)
  order by lower(r) limit 3000;
  get diagnostics n = row_count;
  insert into private.agenda_sharing (user_id, busy_updated_at) values (me, now())
  on conflict (user_id) do update set busy_updated_at = now();
  return jsonb_build_object('saved', n, 'updated_at', now());
end $$;
revoke all on function public.agenda_set_busy(text, jsonb) from public, anon;
grant execute on function public.agenda_set_busy(text, jsonb) to authenticated;
