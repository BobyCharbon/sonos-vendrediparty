-- Prod : ouverture de l'Agenda (préparé le 24.11.2026, PAS appliqué). Les 6 migrations de l'Agenda absentes de la prod, dans
-- l'ordre, en une seule transaction : 20261117140000_agenda, 20261117150000_agenda_liens_calendriers,
-- 20261117160000_agenda_liens_marges, 20261117170000_agenda_adresses, 20261117200000_agenda_durees,
-- 20261117210000_agenda_pas_present, puis 20261124090000_agenda_apercu_delai (aperçu d'un lien avec le délai). Contenu identique aux fichiers de supabase/migrations/, sauf deux retouches marquées
-- [prod 24.11] pour la rejouabilité (contrainte des signalements étendue au lieu d'être réécrite ; ancienne
-- agenda_booking_request retirée après la version avec durée).
-- Dépendances vérifiées en prod (lecture seule, 24.11 00 h) : aucun objet agenda_* ; pg_cron 1.6.4, pgcrypto ; colonne
-- notification_prefs.booking_requests déjà là (20261119150000) ; ancres de web_push_allowed, may_receive_push,
-- report_snapshot, notify_new_report, moderation_hide présentes ; contrainte content_reports = liste d'origine (16 types).
-- Indépendant de 20261123090000 / 20261123110000 (ordre libre). À appliquer AVANT toute migration Pronos (20261117180000
-- étend la contrainte par l'ancre 'agenda_link').
-- Sans effet visible tant que AGENDA_ENABLED est éteint sur le serveur (routes /agenda, /d/ et relais en 404) ; seul
-- le job pg_cron « agenda-tick » (toutes les 10 min, tables vides) tourne.
begin;
-- ═════════════════════════ 20261117140000_agenda.sql ═════════════════════════
-- Agenda de Party (décisions de l'admin du 17.11.2026 ; conformité Exigence Apple, 3 volets).
-- - Rendez-vous créés dans Party (public.agenda_items, propriétaire seul), calendriers (Party, « Juste pour moi »,
--   agendas ajoutés avec un lien .ics à adresse secrète), réglages d'affichage (public.agenda_prefs).
-- - Partage des dispos groupe par groupe : tout décoché au départ, accord daté, jamais Membres Vendredi Party d'office,
--   bloqués exclus, quitter le groupe = arrêt ; seules des plages « pris » arrondies à 30 min, 60 jours au plus, arrivent
--   (private.agenda_busy, purgées ; aucun titre). « Qui est libre ? » : agenda_group_free.
-- - Liens publics de dispo (private.agenda_links) : jeton de 144 bits, 10 au plus, 90 jours, arrêter / rallumer à la
--   même adresse, compteur de vues ; rien le jour même (dès demain, ≥ 12 h), 60 jours au plus.
-- - Demandes de rendez-vous (private.agenda_bookings) : créneau réservé en attente 48 h, 5 en attente par lien, 1 par
--   e-mail / téléphone, 3 / h par IP hachée (gardée 24 h), 20 / jour par lien, filtre de modération, effacement
--   (refus, annulation, sans réponse : aussitôt ; accepté : 30 jours après le rendez-vous), Signaler (content_reports :
--   'booking_request', 'agenda_link'), Bloquer l'expéditeur (empreintes), notification booking_request sans coordonnée
--   (interrupteur notification_prefs.booking_requests, allumé), pastille agenda_badge + signal user:<id>.
-- - Tout part avec le compte (on delete cascade sur profiles). Purement additive et rejouable.

-- ───────────────────────── Outils ─────────────────────────
create or replace function private.agenda_floor30(t timestamptz) returns timestamptz
language sql immutable set search_path = '' as $$ select to_timestamp(floor(extract(epoch from t) / 1800) * 1800) $$;
create or replace function private.agenda_ceil30(t timestamptz) returns timestamptz
language sql immutable set search_path = '' as $$ select to_timestamp(ceil(extract(epoch from t) / 1800) * 1800) $$;
revoke all on function private.agenda_floor30(timestamptz), private.agenda_ceil30(timestamptz) from public, anon, authenticated;

-- Réglages communs (une ligne) : les plafonds et délais du 17.11, modifiables par l'admin sans nouvelle migration.
create table if not exists private.agenda_settings (
  id int primary key default 1 check (id = 1),
  pepper bytea not null default extensions.gen_random_bytes(32),   -- empreintes (IP, e-mail, téléphone) : jamais lisible
  pending_hours int not null default 48,
  max_pending_per_link int not null default 5,
  per_ip_per_hour int not null default 3,
  per_link_per_day int not null default 20,
  links_max int not null default 10,
  link_days int not null default 90,
  double_opt_in boolean not null default false,  -- e-mails futurs : la demande attend le clic « Confirmer » (to_confirm)
  confirm_minutes int not null default 30
);
insert into private.agenda_settings (id) values (1) on conflict (id) do nothing;
alter table private.agenda_settings enable row level security;
revoke all on private.agenda_settings from public, anon, authenticated;

create or replace function private.agenda_fp(kind text, val text) returns text
language sql stable security definer set search_path = '' as $$
  select case when nullif(btrim(coalesce(val, '')), '') is null then null
    else encode(extensions.hmac(convert_to(kind || ':' || val, 'UTF8'), (select pepper from private.agenda_settings z where z.id = 1), 'sha256'), 'hex') end;
$$;
revoke all on function private.agenda_fp(text, text) from public, anon, authenticated;

create or replace function private.agenda_token(bytes int) returns text
language sql volatile set search_path = '' as $$
  select translate(encode(extensions.gen_random_bytes(bytes), 'base64'), '+/=', '-_');
$$;
revoke all on function private.agenda_token(int) from public, anon, authenticated;

-- ───────────────────────── Calendriers, réglages, rendez-vous ─────────────────────────
create table if not exists public.agenda_calendars (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  kind text not null check (kind in ('party', 'personal', 'ics')),
  name text not null check (char_length(btrim(name)) between 1 and 60),
  color text not null default 'sky' check (color in ('pink', 'coral', 'mint', 'sky', 'lavender', 'lemon', 'violet', 'gray')),
  visible boolean not null default true,
  counts_busy boolean not null default false,   -- agenda ajouté avec un lien : compte dans mes dispos (web)
  ics_url text check (ics_url is null or (ics_url ~ '^(https|webcal)://[^[:space:]]+$' and char_length(ics_url) <= 1000)),
  fetched_at timestamptz,
  fetch_error text check (fetch_error is null or char_length(fetch_error) <= 200),
  created_at timestamptz not null default now(),
  constraint agenda_calendars_ics check ((kind = 'ics') = (ics_url is not null))
);
create unique index if not exists agenda_calendars_one_builtin on public.agenda_calendars (user_id, kind) where kind in ('party', 'personal');
alter table public.agenda_calendars enable row level security;
drop policy if exists "agenda calendriers à soi" on public.agenda_calendars;
create policy "agenda calendriers à soi" on public.agenda_calendars for select using (user_id = (select auth.uid()));
drop policy if exists "agenda calendriers ajout" on public.agenda_calendars;
create policy "agenda calendriers ajout" on public.agenda_calendars for insert with check (user_id = (select auth.uid()) and kind = 'ics');
drop policy if exists "agenda calendriers modif" on public.agenda_calendars;
create policy "agenda calendriers modif" on public.agenda_calendars for update using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));
drop policy if exists "agenda calendriers retrait" on public.agenda_calendars;
create policy "agenda calendriers retrait" on public.agenda_calendars for delete using (user_id = (select auth.uid()) and kind = 'ics');
grant select, insert, update, delete on public.agenda_calendars to authenticated;

-- Garde : le genre ne change pas, 10 agendas ajoutés avec un lien au plus, l'état de lecture n'est écrit que par le serveur.
create or replace function private.agenda_calendar_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' then
    if new.kind <> old.kind or new.user_id <> old.user_id then raise exception 'forbidden: calendrier non modifiable' using errcode = '42501'; end if;
    if (new.ics_url is distinct from old.ics_url) then new.fetched_at := null; new.fetch_error := null; end if;
  elsif new.kind = 'ics' and (select count(*) from public.agenda_calendars c where c.user_id = new.user_id and c.kind = 'ics') >= 10 then
    raise exception 'forbidden: 10 agendas ajoutés avec un lien au plus.' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.agenda_calendar_guard() from public, anon, authenticated;
drop trigger if exists agenda_calendars_guard on public.agenda_calendars;
create trigger agenda_calendars_guard before insert or update on public.agenda_calendars
  for each row execute function private.agenda_calendar_guard();

create table if not exists public.agenda_prefs (
  user_id uuid primary key default auth.uid() references public.profiles (id) on delete cascade,
  prefs jsonb not null default '{}'::jsonb check (jsonb_typeof(prefs) = 'object' and pg_column_size(prefs) <= 8000),
  updated_at timestamptz not null default now()
);
alter table public.agenda_prefs enable row level security;
drop policy if exists "agenda réglages à soi" on public.agenda_prefs;
create policy "agenda réglages à soi" on public.agenda_prefs for all using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));
grant select, insert, update, delete on public.agenda_prefs to authenticated;

create table if not exists public.agenda_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  calendar_id uuid references public.agenda_calendars (id) on delete set null,
  title text not null check (char_length(btrim(title)) between 1 and 120),
  place text check (place is null or char_length(place) <= 200),
  notes text check (notes is null or char_length(notes) <= 2000),
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  all_day boolean not null default false,
  repeat text not null default 'none' check (repeat in ('none', 'daily', 'weekly', 'biweekly', 'monthly', 'yearly')),
  repeat_until date,
  skip_dates date[] not null default '{}' check (cardinality(skip_dates) <= 200),
  alert_minutes int check (alert_minutes is null or alert_minutes between 0 and 10080),
  busy boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint agenda_items_span check (ends_at > starts_at and ends_at <= starts_at + interval '31 days')
);
create index if not exists agenda_items_user_time on public.agenda_items (user_id, starts_at);
alter table public.agenda_items enable row level security;
drop policy if exists "agenda rendez-vous à soi" on public.agenda_items;
create policy "agenda rendez-vous à soi" on public.agenda_items for all using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));
grant select, insert, update, delete on public.agenda_items to authenticated;

create or replace function private.agenda_item_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.calendar_id is not null and not exists (select 1 from public.agenda_calendars c where c.id = new.calendar_id
       and c.user_id = new.user_id and c.kind = 'personal') then
    raise exception 'forbidden: choisis un de tes calendriers' using errcode = '42501';
  end if;
  new.updated_at := now();
  return new;
end $$;
revoke all on function private.agenda_item_guard() from public, anon, authenticated;
drop trigger if exists agenda_items_guard on public.agenda_items;
create trigger agenda_items_guard before insert or update on public.agenda_items
  for each row execute function private.agenda_item_guard();

-- Les deux calendriers de base (Party et « Juste pour moi »), créés au premier usage.
create or replace function private.agenda_builtin(uid uuid, k text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare cid uuid;
begin
  select id into cid from public.agenda_calendars where user_id = uid and kind = k;
  if cid is null then
    insert into public.agenda_calendars (user_id, kind, name, color)
    values (uid, k, case k when 'party' then 'Mes soirées Party' else 'Juste pour moi' end, case k when 'party' then 'pink' else 'lavender' end)
    on conflict do nothing returning id into cid;
    if cid is null then select id into cid from public.agenda_calendars where user_id = uid and kind = k; end if;
  end if;
  return cid;
end $$;
revoke all on function private.agenda_builtin(uuid, text) from public, anon, authenticated;

-- Calendriers de la personne (les deux de base créés au besoin), adresse secrète des liens .ics comprise (à elle seule).
create or replace function public.agenda_calendars_list() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  perform private.agenda_builtin(me, 'party');
  perform private.agenda_builtin(me, 'personal');
  return (select coalesce(jsonb_agg(to_jsonb(c) - 'user_id' order by case c.kind when 'party' then 0 when 'personal' then 1 else 2 end, c.created_at), '[]')
          from public.agenda_calendars c where c.user_id = me);
end $$;
revoke all on function public.agenda_calendars_list() from public, anon;
grant execute on function public.agenda_calendars_list() to authenticated;

-- Lecture d'un agenda .ics par le serveur (avec la session de la personne) : il note l'heure ou l'erreur.
create or replace function public.agenda_calendar_fetched(cal uuid, error text default null) returns void
language sql security definer set search_path = '' as $$
  update public.agenda_calendars set fetched_at = now(), fetch_error = left(nullif(btrim(coalesce(error, '')), ''), 200)
  where id = cal and user_id = auth.uid() and kind = 'ics';
$$;
revoke all on function public.agenda_calendar_fetched(uuid, text) from public, anon;
grant execute on function public.agenda_calendar_fetched(uuid, text) to authenticated;

-- Dates d'un rendez-vous (répétitions comprises, heure de Suisse) qui touchent [f, t).
create or replace function private.agenda_occurrences(uid uuid, f timestamptz, t timestamptz)
returns table (item_id uuid, starts_at timestamptz, ends_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select i.id, o.s, o.s + (i.ends_at - i.starts_at)
  from public.agenda_items i
  cross join lateral (
    select case i.repeat when 'daily' then interval '1 day' when 'weekly' then interval '7 days'
      when 'biweekly' then interval '14 days' when 'monthly' then interval '1 month' when 'yearly' then interval '1 year'
      else interval '0' end as step,
      case i.repeat when 'none' then 0
        when 'daily' then floor(extract(epoch from f - i.starts_at) / 86400)::int - 1
        when 'weekly' then floor(extract(epoch from f - i.starts_at) / 604800)::int - 1
        when 'biweekly' then floor(extract(epoch from f - i.starts_at) / 1209600)::int - 1
        when 'monthly' then (extract(year from age(f, i.starts_at)) * 12 + extract(month from age(f, i.starts_at)))::int - 1
        else extract(year from age(f, i.starts_at))::int - 1 end as k0
  ) st
  cross join lateral generate_series(greatest(0, st.k0), case when i.repeat = 'none' then 0 else greatest(0, st.k0) + 400 end) k
  cross join lateral (select (((i.starts_at at time zone 'Europe/Zurich') + k * st.step) at time zone 'Europe/Zurich') as s) o
  where i.user_id = uid and i.starts_at < t
    and o.s < t and o.s + (i.ends_at - i.starts_at) > f
    and (i.repeat_until is null or (o.s at time zone 'Europe/Zurich')::date <= i.repeat_until)
    and not ((o.s at time zone 'Europe/Zurich')::date = any (i.skip_dates));
$$;
revoke all on function private.agenda_occurrences(uuid, timestamptz, timestamptz) from public, anon, authenticated;

-- Soirées Party d'une personne (date fixée, publiées) : elle organise, ou a répondu Présent / Peut-être.
create or replace function private.agenda_party_spans(uid uuid, f timestamptz, t timestamptz) returns setof tstzrange
language sql stable security definer set search_path = '' as $$
  select case when ev.all_day then tstzrange(
           ((ev.starts_at at time zone 'Europe/Zurich')::date)::timestamp at time zone 'Europe/Zurich',
           (((coalesce(ev.ends_at, ev.starts_at) at time zone 'Europe/Zurich')::date + 1)::timestamp) at time zone 'Europe/Zurich')
         else tstzrange(ev.starts_at, coalesce(ev.ends_at, ev.starts_at + interval '4 hours')) end
  from public.events ev
  where ev.date_mode = 'fixed' and ev.status = 'published' and ev.starts_at is not null
    and ev.starts_at < t and coalesce(ev.ends_at, ev.starts_at + interval '1 day') > f - interval '1 day'
    and (ev.created_by = uid
         or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = uid)
         or exists (select 1 from public.rsvps r where r.event_id = ev.id and r.user_id = uid and r.status in ('yes', 'maybe')));
$$;
revoke all on function private.agenda_party_spans(uuid, timestamptz, timestamptz) from public, anon, authenticated;

-- ───────────────────────── Partage des dispos ─────────────────────────
create table if not exists private.agenda_sharing (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  share_party boolean not null default false,    -- « Mes soirées Party (Présent et Peut-être) »
  share_manual boolean not null default false,   -- « Ce que je note Pris ici » (rendez-vous de Party)
  updated_at timestamptz not null default now(),
  busy_updated_at timestamptz
);
alter table private.agenda_sharing enable row level security;
revoke all on private.agenda_sharing from public, anon, authenticated;

create table if not exists private.agenda_group_shares (
  user_id uuid not null references public.profiles (id) on delete cascade,
  group_id uuid not null references public.member_groups (id) on delete cascade,
  consented_at timestamptz not null default now(),   -- accord daté, groupe par groupe
  primary key (user_id, group_id)
);
alter table private.agenda_group_shares enable row level security;
revoke all on private.agenda_group_shares from public, anon, authenticated;

-- Plages « pris » envoyées par l'appareil (calendriers de l'iPhone) ou le web (agendas ajoutés avec un lien) : début et
-- fin à la demi-heure, 60 jours au plus, jamais de titre.
create table if not exists private.agenda_busy (
  user_id uuid not null references public.profiles (id) on delete cascade,
  source text not null check (source in ('device', 'web')),
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  primary key (user_id, source, starts_at),
  check (ends_at > starts_at and extract(epoch from starts_at)::bigint % 1800 = 0 and extract(epoch from ends_at)::bigint % 1800 = 0)
);
alter table private.agenda_busy enable row level security;
revoke all on private.agenda_busy from public, anon, authenticated;

-- Quitter un groupe (ou en être retiré) arrête le partage avec lui.
create or replace function private.agenda_share_on_leave() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  delete from private.agenda_group_shares where user_id = old.user_id and group_id = old.group_id;
  return null;
end $$;
revoke all on function private.agenda_share_on_leave() from public, anon, authenticated;
drop trigger if exists member_group_members_agenda_share on public.member_group_members;
create trigger member_group_members_agenda_share after delete on public.member_group_members
  for each row execute function private.agenda_share_on_leave();

-- ───────────────────────── Liens publics et demandes ─────────────────────────
create table if not exists private.agenda_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  token text not null unique default private.agenda_token(18),   -- 144 bits
  name text not null check (char_length(btrim(name)) between 1 and 40),             -- pour le propriétaire
  emoji text check (emoji is null or char_length(emoji) <= 16),
  display_name text not null check (char_length(btrim(display_name)) between 1 and 40),  -- filtré comme un nom
  rules jsonb not null,
  horizon_days int not null default 28 check (horizon_days between 7 and 60),
  duration_min int not null default 60 check (duration_min between 30 and 240 and duration_min % 30 = 0),
  booking_enabled boolean not null default false,
  booking_fields jsonb not null default '{"first_name":"required","last_name":"optional","email":"required","phone":"off","message":"optional"}',
  message_label text check (message_label is null or char_length(message_label) <= 60),
  expires_at timestamptz not null default now() + interval '90 days',
  stopped_at timestamptz,
  views int not null default 0,
  last_viewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists agenda_links_user on private.agenda_links (user_id);
alter table private.agenda_links enable row level security;
revoke all on private.agenda_links from public, anon, authenticated;

create table if not exists private.agenda_bookings (
  id uuid primary key default gen_random_uuid(),
  link_id uuid not null references private.agenda_links (id) on delete cascade,
  owner_id uuid not null references public.profiles (id) on delete cascade,
  secret text not null unique default private.agenda_token(24),  -- 192 bits : lien de suivi de l'inconnu
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  status text not null default 'pending' check (status in ('to_confirm', 'pending', 'accepted', 'refused', 'expired', 'cancelled')),
  first_name text, last_name text, email text, phone text, message text,
  email_fp text, phone_fp text, ip_hash text,
  item_id uuid references public.agenda_items (id) on delete set null,
  created_at timestamptz not null default now(),
  expires_at timestamptz,          -- en attente : sans réponse à cette heure, le créneau se libère
  confirm_by timestamptz,          -- to_confirm (e-mails futurs, double opt-in)
  decided_at timestamptz,
  wiped_at timestamptz,            -- données de l'inconnu effacées (reste : statut et créneau, sans donnée personnelle)
  mail_state text not null default 'none' check (mail_state in ('none', 'to_send', 'sent', 'failed'))  -- point d'accroche des e-mails
);
create index if not exists agenda_bookings_owner on private.agenda_bookings (owner_id, status);
create index if not exists agenda_bookings_link on private.agenda_bookings (link_id, status);
alter table private.agenda_bookings enable row level security;
revoke all on private.agenda_bookings from public, anon, authenticated;

create table if not exists private.agenda_ip_hits (
  ip_hash text not null,
  link_id uuid references private.agenda_links (id) on delete cascade,
  kind text not null check (kind in ('booking', 'report')),
  at timestamptz not null default now()
);
create index if not exists agenda_ip_hits_ip on private.agenda_ip_hits (ip_hash, at);
create index if not exists agenda_ip_hits_link on private.agenda_ip_hits (link_id, at);
alter table private.agenda_ip_hits enable row level security;
revoke all on private.agenda_ip_hits from public, anon, authenticated;

-- « Bloquer l'expéditeur » : empreintes de l'e-mail et du téléphone (tant que le blocage existe) + IP hachée (24 h).
create table if not exists private.agenda_sender_blocks (
  owner_id uuid not null references public.profiles (id) on delete cascade,
  fp text not null,
  kind text not null check (kind in ('email', 'phone', 'ip')),
  created_at timestamptz not null default now(),
  expires_at timestamptz,
  primary key (owner_id, fp)
);
alter table private.agenda_sender_blocks enable row level security;
revoke all on private.agenda_sender_blocks from public, anon, authenticated;

-- ───────────────────────── Plages occupées et créneaux libres ─────────────────────────
-- mode 'group' : ce que la personne a choisi de partager ; mode 'link' : tout ce qui la rend prise (pour ses liens).
create or replace function private.agenda_busy_of(uid uuid, f timestamptz, t timestamptz, mode text) returns tstzmultirange
language sql stable security definer set search_path = '' as $$
  select coalesce(range_agg(tstzrange(private.agenda_floor30(lower(r)), private.agenda_ceil30(upper(r)))), '{}'::tstzmultirange)
         * tstzmultirange(tstzrange(f, t))
  from (
    select tstzrange(b.starts_at, b.ends_at) r from private.agenda_busy b where b.user_id = uid and b.starts_at < t and b.ends_at > f
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

create or replace function private.agenda_rules_ok(r jsonb) returns boolean
language plpgsql immutable set search_path = '' as $$
declare x jsonb; d jsonb;
begin
  if jsonb_typeof(r) <> 'array' or jsonb_array_length(r) not between 1 and 7 then return false; end if;
  for x in select * from jsonb_array_elements(r) loop
    if jsonb_typeof(x) <> 'object' or jsonb_typeof(x->'days') <> 'array' or jsonb_array_length(x->'days') not between 1 and 7
       or coalesce(x->>'from', '') !~ '^([01][0-9]|2[0-3]):(00|30)$' or coalesce(x->>'to', '') !~ '^(([01][0-9]|2[0-3]):(00|30)|24:00)$'
       or (x->>'to')::time <= (x->>'from')::time and x->>'to' <> '24:00' then
      return false;
    end if;
    for d in select * from jsonb_array_elements(x->'days') loop
      if jsonb_typeof(d) <> 'number' or d::text !~ '^[1-7]$' then return false; end if;
    end loop;
  end loop;
  return true;
end $$;
revoke all on function private.agenda_rules_ok(jsonb) from public, anon, authenticated;

-- Fenêtres d'un lien (jours × plages, heure de Suisse), de demain (≥ 12 h) à l'horizon (60 jours au plus).
create or replace function private.agenda_link_windows(l private.agenda_links) returns setof tstzrange
language sql stable security definer set search_path = '' as $$
  select tstzrange(greatest((dd + (x->>'from')::time) at time zone 'Europe/Zurich',
                            now() + interval '12 hours',
                            (((now() at time zone 'Europe/Zurich')::date + 1)::timestamp) at time zone 'Europe/Zurich'),
                   (dd + (x->>'to')::time) at time zone 'Europe/Zurich')
  from generate_series(((now() at time zone 'Europe/Zurich')::date + 1)::timestamp,
                       ((now() at time zone 'Europe/Zurich')::date + least(l.horizon_days, 60))::timestamp, interval '1 day') dd
  cross join jsonb_array_elements(l.rules) x
  where extract(isodow from dd)::int in (select (jsonb_array_elements_text(x->'days'))::int)
    and (dd + (x->>'to')::time) at time zone 'Europe/Zurich' > now() + interval '12 hours';
$$;
revoke all on function private.agenda_link_windows(private.agenda_links) from public, anon, authenticated;

-- Ce que voit l'inconnu : sans demandes, les plages libres (≥ 30 min) ; avec demandes, des créneaux à la suite de la
-- durée du lien, alignés sur le début de chaque plage du lien, entièrement libres. Rien sur un « pris ».
create or replace function private.agenda_link_free(l private.agenda_links) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare f timestamptz; t timestamptz; busy tstzmultirange; dur interval := make_interval(mins => l.duration_min); out jsonb;
begin
  f := (((now() at time zone 'Europe/Zurich')::date)::timestamp) at time zone 'Europe/Zurich';
  t := f + interval '62 days';
  busy := private.agenda_busy_of(l.user_id, f, t, 'link');
  if not l.booking_enabled then
    select coalesce(jsonb_agg(jsonb_build_array(s, e) order by s), '[]') into out from (
      select private.agenda_ceil30(lower(r)) s, private.agenda_floor30(upper(r)) e
      from unnest(coalesce((select range_agg(w) from private.agenda_link_windows(l) w), '{}'::tstzmultirange) - busy) r) z
    where e - s >= interval '30 minutes';
  else
    -- Créneaux : départ = début de la plage du lien (avant le délai de 12 h) + k × durée ; entièrement dans la plage et libres.
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
  select l.id is not null and l.stopped_at is null and l.expires_at > now() and private.is_account_active(l.user_id);
$$;
revoke all on function private.agenda_link_active(private.agenda_links) from public, anon, authenticated;

-- ───────────────────────── Partage : fonctions de la personne ─────────────────────────
create or replace function public.agenda_sharing() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); s private.agenda_sharing;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into s from private.agenda_sharing where user_id = me;
  return jsonb_build_object(
    'share_party', coalesce(s.share_party, false), 'share_manual', coalesce(s.share_manual, false),
    'busy_updated_at', s.busy_updated_at,
    'busy_count', (select count(*) from private.agenda_busy b where b.user_id = me),
    'links_active', (select count(*) from private.agenda_links l where l.user_id = me and private.agenda_link_active(l)),
    'groups', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color,
        'system', g.system_key is not null,
        'members', (select count(*) from public.member_group_members m2 where m2.group_id = g.id),
        'shared', sh.group_id is not null, 'consented_at', sh.consented_at)
        order by sh.group_id is null, g.system_key is not null, g.name)
      from public.member_groups g join public.member_group_members m on m.group_id = g.id and m.user_id = me
      left join private.agenda_group_shares sh on sh.group_id = g.id and sh.user_id = me), '[]'));
end $$;
revoke all on function public.agenda_sharing() from public, anon;
grant execute on function public.agenda_sharing() to authenticated;

-- « Partager mes dispos » : la liste COMPLÈTE des groupes cochés (les autres sont retirés) et les deux sources de Party.
-- Groupes : seulement ceux dont on fait partie ; un groupe déjà partagé garde la date de son accord.
create or replace function public.agenda_set_sharing(groups uuid[], share_party boolean default false, share_manual boolean default false)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); g uuid;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  foreach g in array coalesce(groups, '{}') loop
    if not private.in_group_now(g, me) then raise exception 'forbidden: Tu ne fais pas partie de ce groupe.' using errcode = '42501'; end if;
  end loop;
  if cardinality(coalesce(groups, '{}')) = 0 then return public.agenda_stop_sharing(); end if;
  delete from private.agenda_group_shares where user_id = me and not (group_id = any (groups));
  insert into private.agenda_group_shares (user_id, group_id) select me, x from unnest(groups) x on conflict do nothing;
  insert into private.agenda_sharing (user_id, share_party, share_manual) values (me, coalesce(share_party, false), coalesce(share_manual, false))
  on conflict (user_id) do update set share_party = excluded.share_party, share_manual = excluded.share_manual, updated_at = now();
  return public.agenda_sharing();
end $$;

-- « Arrêter de partager » : plus aucun groupe, tout ce qui a été envoyé est effacé (sauf si un lien public actif s'en sert).
create or replace function public.agenda_stop_sharing() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  delete from private.agenda_group_shares where user_id = me;
  update private.agenda_sharing set share_party = false, share_manual = false, updated_at = now() where user_id = me;
  if not exists (select 1 from private.agenda_links l where l.user_id = me and private.agenda_link_active(l)) then
    delete from private.agenda_busy where user_id = me;
    update private.agenda_sharing set busy_updated_at = null where user_id = me;
  end if;
  return public.agenda_sharing();
end $$;
revoke all on function public.agenda_set_sharing(uuid[], boolean, boolean), public.agenda_stop_sharing() from public, anon;
grant execute on function public.agenda_set_sharing(uuid[], boolean, boolean), public.agenda_stop_sharing() to authenticated;

-- Envoi des plages « pris » de l'appareil (source 'device') ou du web ('web') : remplace tout l'envoi précédent de cette
-- source. blocks = [{"s": "<ISO>", "e": "<ISO>"}…] ; arrondies vers l'extérieur à 30 min, coupées à [maintenant, +60 j],
-- fusionnées, 1000 au plus. Permis seulement avec un partage actif (un groupe) ou un lien public actif.
create or replace function public.agenda_set_busy(source text, blocks jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); f timestamptz := private.agenda_floor30(now()); t timestamptz := private.agenda_floor30(now()) + interval '60 days';
        merged tstzmultirange; n int;
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
  select coalesce(range_agg(tstzrange(private.agenda_floor30((b->>'s')::timestamptz), private.agenda_ceil30((b->>'e')::timestamptz))), '{}')
         * tstzmultirange(tstzrange(f, t))
    into merged
  from jsonb_array_elements(coalesce(blocks, '[]')) b
  where (b->>'s')::timestamptz < (b->>'e')::timestamptz;
  delete from private.agenda_busy where user_id = me and agenda_busy.source = agenda_set_busy.source;
  insert into private.agenda_busy (user_id, source, starts_at, ends_at)
  select me, agenda_set_busy.source, lower(r), upper(r) from unnest(merged) r order by lower(r) limit 1000;
  get diagnostics n = row_count;
  insert into private.agenda_sharing (user_id, busy_updated_at) values (me, now())
  on conflict (user_id) do update set busy_updated_at = now();
  return jsonb_build_object('saved', n, 'updated_at', now());
end $$;
revoke all on function public.agenda_set_busy(text, jsonb) from public, anon;
grant execute on function public.agenda_set_busy(text, jsonb) to authenticated;

-- « Qui est libre ? » d'un groupe dont on fait partie. Chaque membre (sauf blocage dans un sens ou l'autre) :
-- shares = true → ses plages « pris » (sans aucun motif) ; false → rien de plus (« Les autres membres », sans texte).
create or replace function public.agenda_group_free(grp uuid, from_ts timestamptz default null, days int default 60) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); g public.member_groups; f timestamptz; t timestamptz;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into g from public.member_groups where id = grp;
  if g.id is null or not private.in_group_now(grp, me) then
    raise exception 'forbidden: Tu ne fais pas partie de ce groupe.' using errcode = '42501';
  end if;
  f := greatest(coalesce(from_ts, now()), private.agenda_floor30(now()));
  t := least(f + make_interval(0, 0, 0, greatest(1, least(coalesce(days, 60), 60))), private.agenda_floor30(now()) + interval '60 days');
  return jsonb_build_object(
    'group', jsonb_build_object('id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color, 'system', g.system_key is not null),
    'from', f, 'to', t,
    'i_share', exists (select 1 from private.agenda_group_shares s where s.user_id = me and s.group_id = grp),
    'members', coalesce((select jsonb_agg(x order by (x->>'me')::boolean desc, (x->>'shares')::boolean desc, x->>'name') from (
      select case when sh.user_id is not null then
          jsonb_build_object('id', p.id, 'name', coalesce(nullif(btrim(p.display_name), ''), nullif(btrim(p.first_name), ''), '?'),
            'avatar_url', p.avatar_url, 'me', p.id = me, 'shares', true,
            'updated_at', (select s.busy_updated_at from private.agenda_sharing s where s.user_id = p.id),
            'busy', (select coalesce(jsonb_agg(jsonb_build_array(lower(r), upper(r)) order by lower(r)), '[]')
                     from unnest(private.agenda_busy_of(p.id, f, t, 'group')) r))
        else jsonb_build_object('id', p.id, 'name', coalesce(nullif(btrim(p.display_name), ''), nullif(btrim(p.first_name), ''), '?'),
            'avatar_url', p.avatar_url, 'me', p.id = me, 'shares', false) end x
      from public.member_group_members m
      join public.profiles p on p.id = m.user_id and p.status = 'active'
      left join private.agenda_group_shares sh on sh.user_id = p.id and sh.group_id = grp
      where m.group_id = grp and (p.id = me or not private.blocked_either(me, p.id))) y), '[]'));
end $$;
revoke all on function public.agenda_group_free(uuid, timestamptz, int) from public, anon;
grant execute on function public.agenda_group_free(uuid, timestamptz, int) to authenticated;

-- ───────────────────────── Mon agenda (une période) ─────────────────────────
-- Rendez-vous (répétitions dépliées), soirées Party et sondages à voter entre from_ts et to_ts (62 jours au plus).
create or replace function public.agenda_window(from_ts timestamptz, to_ts timestamptz) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if to_ts <= from_ts or to_ts > from_ts + interval '62 days' then raise exception 'forbidden: période de 62 jours au plus' using errcode = '22023'; end if;
  return jsonb_build_object(
    'items', coalesce((select jsonb_agg(jsonb_build_object('id', i.id, 'calendar_id', i.calendar_id, 'title', i.title,
        'place', i.place, 'notes', i.notes, 'starts_at', o.starts_at, 'ends_at', o.ends_at, 'all_day', i.all_day,
        'repeat', i.repeat, 'repeat_until', i.repeat_until, 'alert_minutes', i.alert_minutes, 'busy', i.busy,
        'series_start', i.starts_at,
        'booking', (select jsonb_build_object('id', k.id, 'status', k.status, 'link_name', l.name)
                    from private.agenda_bookings k join private.agenda_links l on l.id = k.link_id where k.item_id = i.id limit 1))
        order by o.starts_at)
      from private.agenda_occurrences(me, from_ts, to_ts) o join public.agenda_items i on i.id = o.item_id), '[]'),
    'party', coalesce((select jsonb_agg(jsonb_build_object('event_id', ev.id, 'title', ev.title, 'starts_at', ev.starts_at,
        'ends_at', ev.ends_at, 'all_day', ev.all_day, 'location_name', ev.location_name, 'status', ev.status,
        'icon', (select c.icon from public.categories c where c.id = ev.category_id),
        'organizer', ev.created_by = me or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = me),
        'answer', (select r.status from public.rsvps r where r.event_id = ev.id and r.user_id = me))
        order by ev.starts_at)
      from public.events ev
      where ev.date_mode = 'fixed' and ev.status in ('published', 'cancelled') and ev.starts_at is not null
        and ev.starts_at < to_ts and coalesce(ev.ends_at, ev.starts_at + interval '4 hours') > from_ts
        and (ev.created_by = me or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = me)
             or exists (select 1 from public.rsvps r where r.event_id = ev.id and r.user_id = me)
             or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me))), '[]'),
    'polls', coalesce((select jsonb_agg(jsonb_build_object('event_id', ev.id, 'title', ev.title,
        'options', (select jsonb_agg(jsonb_build_object('id', d.id, 'starts_at', d.starts_at, 'ends_at', d.ends_at,
                      'my_vote', (select v.vote from public.date_votes v where v.option_id = d.id and v.user_id = me)) order by d.starts_at)
                    from public.date_options d where d.event_id = ev.id and d.starts_at < to_ts
                      and coalesce(d.ends_at, d.starts_at + interval '4 hours') > from_ts)))
      from public.events ev
      where ev.date_mode = 'poll' and ev.status = 'published'
        and exists (select 1 from public.date_options d where d.event_id = ev.id and d.starts_at < to_ts
                    and coalesce(d.ends_at, d.starts_at + interval '4 hours') > from_ts)
        and (ev.created_by = me or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = me)
             or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me)
             or exists (select 1 from public.date_votes v join public.date_options d on d.id = v.option_id
                        where d.event_id = ev.id and v.user_id = me))), '[]'));
end $$;
revoke all on function public.agenda_window(timestamptz, timestamptz) from public, anon;
grant execute on function public.agenda_window(timestamptz, timestamptz) to authenticated;

-- ───────────────────────── Liens publics : propriétaire ─────────────────────────
create or replace function private.agenda_link_json(l private.agenda_links) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', l.id, 'token', l.token, 'path', '/d/' || l.token, 'name', l.name, 'emoji', l.emoji,
    'display_name', l.display_name, 'rules', l.rules, 'horizon_days', l.horizon_days, 'duration_min', l.duration_min,
    'booking_enabled', l.booking_enabled, 'booking_fields', l.booking_fields, 'message_label', l.message_label,
    'status', case when l.stopped_at is not null then 'stopped' when l.expires_at <= now() then 'expired' else 'active' end,
    'expires_at', l.expires_at, 'stopped_at', l.stopped_at, 'views', l.views, 'last_viewed_at', l.last_viewed_at,
    'pending', (select count(*) from private.agenda_bookings k where k.link_id = l.id and k.status = 'pending'),
    'created_at', l.created_at);
$$;
revoke all on function private.agenda_link_json(private.agenda_links) from public, anon, authenticated;

create or replace function public.agenda_links() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); mx int := (select links_max from private.agenda_settings z where z.id = 1);
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return jsonb_build_object(
    'links', coalesce((select jsonb_agg(private.agenda_link_json(l) order by l.stopped_at is not null, l.created_at)
                       from private.agenda_links l where l.user_id = me), '[]'),
    'max', mx,
    'missing', case when not private.identity_complete(me) then 'profile'
                    when (select terms_enforced from private.moderation_settings where id = 1) and not private.terms_accepted(me) then 'terms' end,
    'notify', coalesce((select p.booking_requests from public.notification_prefs p where p.user_id = me), true),
    'pending', (select count(*) from private.agenda_bookings k where k.owner_id = me and k.status = 'pending'));
end $$;

-- Créer (id absent) ou modifier un lien. link = {name, emoji, display_name, rules, horizon_days, duration_min,
-- booking_enabled, booking_fields, message_label}. Réservé à un compte actif, profil complet, CGU acceptées ; 10 au plus.
create or replace function public.agenda_link_save(link jsonb, id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; fields jsonb; k text; dn text; lbl text;
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
  -- Le prénom est toujours demandé : l'agenda garde « Rendez-vous · Prénom N. ».
  fields := jsonb_build_object('first_name', 'required', 'last_name', coalesce(fields->>'last_name', 'off'),
    'email', coalesce(fields->>'email', 'off'), 'phone', coalesce(fields->>'phone', 'off'), 'message', coalesce(fields->>'message', 'off'));
  dn := coalesce(nullif(btrim(link->>'display_name'), ''), l.display_name,
                 (select nullif(btrim(p.first_name), '') from public.profiles p where p.id = me), 'Moi');
  dn := private.moderate_text(left(dn, 40), 'name');
  lbl := nullif(btrim(coalesce(case when link ? 'message_label' then link->>'message_label' else l.message_label end, '')), '');
  if lbl is not null then lbl := private.moderate_text(left(lbl, 60), 'name'); end if;
  if l.id is null then
    insert into private.agenda_links (user_id, name, emoji, display_name, rules, horizon_days, duration_min, booking_enabled,
      booking_fields, message_label, expires_at)
    values (me, left(btrim(coalesce(nullif(link->>'name', ''), 'Mes dispos')), 40), nullif(link->>'emoji', ''), dn, link->'rules',
      coalesce((link->>'horizon_days')::int, 28), coalesce((link->>'duration_min')::int, 60),
      coalesce((link->>'booking_enabled')::boolean, false), fields, lbl,
      now() + make_interval(days => (select link_days from private.agenda_settings z where z.id = 1)))
    returning * into l;
  else
    update private.agenda_links x set
      name = left(btrim(coalesce(nullif(link->>'name', ''), x.name)), 40),
      emoji = case when link ? 'emoji' then nullif(link->>'emoji', '') else x.emoji end,
      display_name = dn, rules = coalesce(link->'rules', x.rules),
      horizon_days = coalesce((link->>'horizon_days')::int, x.horizon_days),
      duration_min = coalesce((link->>'duration_min')::int, x.duration_min),
      booking_enabled = coalesce((link->>'booking_enabled')::boolean, x.booking_enabled),
      booking_fields = fields, message_label = lbl, updated_at = now()
    where x.id = l.id returning * into l;
  end if;
  return private.agenda_link_json(l);
end $$;

-- Arrêter / rallumer (même adresse ; expiré : repart pour 90 jours) / prolonger (90 jours dès maintenant) / supprimer.
create or replace function public.agenda_link_set(id uuid, action text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; days int := (select link_days from private.agenda_settings z where z.id = 1);
begin
  select * into l from private.agenda_links x where x.id = agenda_link_set.id and x.user_id = me for update;
  if l.id is null then raise exception 'not_found: Ce lien n''existe plus.' using errcode = 'PT404'; end if;
  if action = 'stop' then
    update private.agenda_links x set stopped_at = coalesce(x.stopped_at, now()), updated_at = now() where x.id = l.id returning * into l;
  elsif action = 'restart' then
    update private.agenda_links x set stopped_at = null, updated_at = now(),
      expires_at = case when x.expires_at <= now() then now() + make_interval(0, 0, 0, days) else x.expires_at end
    where x.id = l.id returning * into l;
  elsif action = 'extend' then
    update private.agenda_links x set expires_at = now() + make_interval(0, 0, 0, days), updated_at = now() where x.id = l.id returning * into l;
  elsif action = 'bookings_off' then
    update private.agenda_links x set booking_enabled = false, updated_at = now() where x.id = l.id returning * into l;
  elsif action = 'bookings_on' then
    update private.agenda_links x set booking_enabled = true, updated_at = now() where x.id = l.id returning * into l;
  elsif action = 'delete' then
    -- Les rendez-vous déjà acceptés restent dans l'agenda (« Rendez-vous · Prénom N. ») ; les demandes partent avec le lien.
    delete from private.agenda_links x where x.id = l.id;
    return jsonb_build_object('deleted', true);
  else
    raise exception 'forbidden: action inconnue' using errcode = '22023';
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
  return jsonb_build_object('slots', private.agenda_link_free(l), 'tz', 'Europe/Zurich');
end $$;
revoke all on function public.agenda_links(), public.agenda_link_save(jsonb, uuid), public.agenda_link_set(uuid, text),
  public.agenda_link_preview(jsonb) from public, anon;
grant execute on function public.agenda_links(), public.agenda_link_save(jsonb, uuid), public.agenda_link_set(uuid, text),
  public.agenda_link_preview(jsonb) to authenticated;

-- ───────────────────────── Page publique (sans compte) ─────────────────────────
-- null : lien inconnu, arrêté, expiré ou compte inactif (la page montre le même écran neutre dans tous les cas).
create or replace function public.agenda_public_page(t text, count_view boolean default true) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.agenda_links; st private.agenda_settings;
begin
  if coalesce(t, '') !~ '^[A-Za-z0-9_-]{20,64}$' then return null; end if;
  select * into l from private.agenda_links where token = t;
  if not private.agenda_link_active(l) then return null; end if;
  select * into st from private.agenda_settings where id = 1;
  if count_view then
    update private.agenda_links set views = views + 1, last_viewed_at = now() where id = l.id;
  end if;
  return jsonb_build_object(
    'name', l.display_name, 'link_name', l.name, 'tz', 'Europe/Zurich', 'rules', l.rules,
    'duration_min', l.duration_min, 'horizon_days', l.horizon_days,
    'from', ((now() at time zone 'Europe/Zurich')::date + 1), 'to', ((now() at time zone 'Europe/Zurich')::date + least(l.horizon_days, 60)),
    'slots', private.agenda_link_free(l),
    'booking', case when l.booking_enabled then jsonb_build_object('fields', l.booking_fields, 'message_label', l.message_label,
        'pending_hours', st.pending_hours,
        'full', (select count(*) from private.agenda_bookings k where k.link_id = l.id and k.status in ('pending', 'to_confirm')) >= st.max_pending_per_link)
      end,
    'contact_email', (select m.contact_email from private.moderation_settings m where m.id = 1));
end $$;
revoke all on function public.agenda_public_page(text, boolean) from public;
grant execute on function public.agenda_public_page(text, boolean) to anon, authenticated;

-- Motif d'un refus du filtre, au vouvoiement (DSA art. 17 : on dit pourquoi).
create or replace function private.agenda_refusal(label text, v jsonb) returns text
language sql immutable set search_path = '' as $$
  select 'content_refused: ' || label || ' refusé : il contient ' ||
    case v->>'category' when 'haine' then 'des propos haineux' when 'sexuel' then 'un contenu sexuel' when 'insulte' then 'une insulte'
      when 'lien' then 'un lien, et les liens ne sont pas acceptés ici' when 'numero' then 'un numéro de téléphone'
      else 'un mot interdit' end || '. Retirez-le puis envoyez de nouveau. Rien n''a été transmis.';
$$;
revoke all on function private.agenda_refusal(text, jsonb) from public, anon, authenticated;

create or replace function private.agenda_short_date(s timestamptz) returns text
language sql immutable set search_path = '' as $$
  select (array['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'])[extract(isodow from s at time zone 'Europe/Zurich')::int]
    || ' ' || to_char(s at time zone 'Europe/Zurich', 'DD.MM') || ', '
    || extract(hour from s at time zone 'Europe/Zurich')::int || ' h'
    || case when extract(minute from s at time zone 'Europe/Zurich') = 0 then '' else ' ' || to_char(s at time zone 'Europe/Zurich', 'MI') end;
$$;
revoke all on function private.agenda_short_date(timestamptz) from public, anon, authenticated;

-- Notification au propriétaire : ni coordonnée ni texte libre (elle passe par Apple / Google / Mozilla).
create or replace function private.agenda_notify(k private.agenda_bookings, kind text) returns void
language plpgsql security definer set search_path = '' as $$
declare lname text := (select name from private.agenda_links where id = k.link_id);
begin
  insert into public.notifications (user_id, kind, event_id, title, body, data, dedupe_key)
  values (k.owner_id, kind, null,
    case kind when 'booking_request' then 'Nouvelle demande de rendez-vous' else 'Rendez-vous annulé' end,
    coalesce(lname, 'Lien de dispo') || ' · ' || private.agenda_short_date(k.starts_at),
    -- url : le toucher d'une notification web ouvre la demande (send-web-push lit data.url).
    jsonb_build_object('kind', kind, 'booking_id', k.id, 'link_id', k.link_id, 'url', '/?tab=events&booking=' || k.id),
    kind || ':' || k.id)
  on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing;
end $$;
revoke all on function private.agenda_notify(private.agenda_bookings, text) from public, anon, authenticated;

-- Demande d'un inconnu (appelée par le serveur, qui passe l'IP de la personne ; jamais gardée en clair).
-- answers = {first_name, last_name, email, phone, message}. Erreurs « code: phrase » : not_found, closed, full, slot_taken,
-- rate_limited, duplicate, invalid, content_refused.
create or replace function public.agenda_booking_request(t text, starts_at timestamptz, answers jsonb, ip text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.agenda_links; st private.agenda_settings; fields jsonb; k private.agenda_bookings;
        s timestamptz := agenda_booking_request.starts_at; e timestamptz; v jsonb; ih text; efp text; pfp text;
        fn text; ln text; em text; ph text; msg text; slots jsonb;
begin
  if coalesce(t, '') !~ '^[A-Za-z0-9_-]{20,64}$' then raise exception 'not_found: Ce lien n''est plus actif.' using errcode = 'PT404'; end if;
  select * into l from private.agenda_links where token = t for update;   -- une demande à la fois par lien
  if not private.agenda_link_active(l) then raise exception 'not_found: Ce lien n''est plus actif.' using errcode = 'PT404'; end if;
  if not l.booking_enabled then raise exception 'closed: Ce lien ne prend pas de demandes.' using errcode = '42501'; end if;
  select * into st from private.agenda_settings where id = 1;
  fields := l.booking_fields;
  answers := coalesce(answers, '{}'::jsonb);
  ih := private.agenda_fp('ip', nullif(btrim(coalesce(ip,
          split_part(coalesce(nullif(current_setting('request.headers', true), '')::json->>'x-forwarded-for', ''), ',', 1))), ''));

  -- Champs : seulement ceux que le lien demande ; obligatoire = rempli.
  fn := nullif(btrim(left(answers->>'first_name', 60)), '');
  ln := case when fields->>'last_name' <> 'off' then nullif(btrim(left(answers->>'last_name', 60)), '') end;
  em := case when fields->>'email' <> 'off' then nullif(lower(btrim(left(answers->>'email', 300))), '') end;
  ph := case when fields->>'phone' <> 'off' then nullif(btrim(left(answers->>'phone', 40)), '') end;
  msg := case when fields->>'message' <> 'off' then nullif(btrim(left(answers->>'message', 600)), '') end;
  if fn is null or char_length(fn) > 40 then raise exception 'invalid: Prénom : obligatoire, 40 caractères au plus.' using errcode = '22023'; end if;
  if fields->>'last_name' = 'required' and ln is null or char_length(coalesce(ln, '')) > 40 then
    raise exception 'invalid: Nom : obligatoire pour ce rendez-vous, 40 caractères au plus.' using errcode = '22023';
  end if;
  if fields->>'email' = 'required' and em is null then raise exception 'invalid: Adresse e-mail : obligatoire pour ce rendez-vous.' using errcode = '22023'; end if;
  if em is not null and (char_length(em) > 254 or em !~ '^[^@[:space:]]{1,64}@[^@[:space:]]+\.[^@[:space:].]{2,}$') then
    raise exception 'invalid: Adresse e-mail : ce format n''est pas valable.' using errcode = '22023';
  end if;
  if fields->>'phone' = 'required' and ph is null then raise exception 'invalid: Téléphone : obligatoire pour ce rendez-vous.' using errcode = '22023'; end if;
  if ph is not null and (ph !~ '^\+?[0-9 ().-]{8,25}$' or char_length(regexp_replace(ph, '[^0-9]', '', 'g')) not between 8 and 15) then
    raise exception 'invalid: Téléphone : ce format n''est pas valable.' using errcode = '22023';
  end if;
  if fields->>'message' = 'required' and msg is null then raise exception 'invalid: Message : obligatoire pour ce rendez-vous.' using errcode = '22023'; end if;
  if char_length(coalesce(msg, '')) > 500 then raise exception 'invalid: Message : 500 caractères au plus.' using errcode = '22023'; end if;
  v := private.moderation_verdict(fn, 'name');
  if not (v->>'ok')::boolean then raise exception '%', private.agenda_refusal('Prénom', v) using errcode = '23514'; end if;
  if ln is not null then
    v := private.moderation_verdict(ln, 'name');
    if not (v->>'ok')::boolean then raise exception '%', private.agenda_refusal('Nom', v) using errcode = '23514'; end if;
  end if;
  if msg is not null then
    v := private.moderation_verdict(msg, 'name');   -- le filtre des noms repère aussi les liens (« www… », « x.ch »)
    if v->>'category' = 'lien' then raise exception '%', private.agenda_refusal('Message', v) using errcode = '23514'; end if;
    v := private.moderation_verdict(msg, 'message');
    if not (v->>'ok')::boolean then raise exception '%', private.agenda_refusal('Message', v) using errcode = '23514'; end if;
    msg := v->>'text';
  end if;
  efp := private.agenda_fp('email', em);
  pfp := private.agenda_fp('phone', regexp_replace(coalesce(ph, ''), '[^0-9]', '', 'g'));

  -- Anti-abus : IP (3 / h), lien (20 / jour), 5 en attente par lien, expéditeur bloqué, 1 en attente par e-mail / téléphone.
  if ih is not null and (select count(*) from private.agenda_ip_hits h where h.ip_hash = ih and h.kind = 'booking'
                         and h.at > now() - interval '1 hour') >= st.per_ip_per_hour then
    raise exception 'rate_limited: Trop de demandes depuis cette connexion. Réessayez dans une heure.' using errcode = '54000';
  end if;
  if (select count(*) from private.agenda_ip_hits h where h.link_id = l.id and h.kind = 'booking' and h.at > now() - interval '1 day')
     >= st.per_link_per_day
     or (select count(*) from private.agenda_bookings b where b.link_id = l.id and b.status in ('pending', 'to_confirm')) >= st.max_pending_per_link
     or exists (select 1 from private.agenda_sender_blocks x where x.owner_id = l.user_id and x.fp in (efp, pfp, ih)
                and (x.expires_at is null or x.expires_at > now())) then
    raise exception 'full: Ce lien ne prend plus de demandes pour le moment.' using errcode = '54000';
  end if;
  if exists (select 1 from private.agenda_bookings b where b.link_id = l.id and b.status in ('pending', 'to_confirm')
             and (b.email_fp = efp or b.phone_fp = pfp)) then
    raise exception 'duplicate: Une demande est déjà en attente avec cette adresse e-mail ou ce numéro.' using errcode = '23505';
  end if;

  -- Créneau : exactement un de ceux que la page propose (libres, dès demain, ≥ 12 h, dans l'horizon).
  e := s + make_interval(mins => l.duration_min);
  slots := private.agenda_link_free(l);
  if not exists (select 1 from jsonb_array_elements(slots) x where (x->>0)::timestamptz = s and (x->>1)::timestamptz = e) then
    raise exception 'slot_taken: Ce créneau n''est plus libre. Choisissez-en un autre.' using errcode = '23505';
  end if;

  insert into private.agenda_bookings (link_id, owner_id, starts_at, ends_at, status, first_name, last_name, email, phone, message,
    email_fp, phone_fp, ip_hash, expires_at, confirm_by)
  values (l.id, l.user_id, s, e, case when st.double_opt_in and em is not null then 'to_confirm' else 'pending' end,
    fn, ln, em, ph, msg, efp, pfp, ih, least(now() + make_interval(hours => st.pending_hours), s),
    case when st.double_opt_in and em is not null then now() + make_interval(mins => st.confirm_minutes) end)
  returning * into k;
  if ih is not null then insert into private.agenda_ip_hits (ip_hash, link_id, kind) values (ih, l.id, 'booking'); end if;
  if k.status = 'pending' then perform private.agenda_notify(k, 'booking_request'); end if;
  return jsonb_build_object('secret', k.secret, 'status', k.status, 'starts_at', k.starts_at, 'ends_at', k.ends_at,
    'expires_at', k.expires_at, 'name', l.display_name);
end $$;
revoke all on function public.agenda_booking_request(text, timestamptz, jsonb, text) from public;
grant execute on function public.agenda_booking_request(text, timestamptz, jsonb, text) to anon, authenticated;

-- Efface les données de l'inconnu (reste : statut, créneau et lien de suivi, aucune donnée personnelle).
create or replace function private.agenda_wipe(bid uuid, new_status text) returns void
language sql security definer set search_path = '' as $$
  update private.agenda_bookings set status = coalesce(new_status, status), first_name = null, last_name = null, email = null,
    phone = null, message = null, email_fp = null, phone_fp = null, ip_hash = null, wiped_at = now(),
    decided_at = case when new_status is not null then coalesce(decided_at, now()) else decided_at end
  where id = bid;
$$;
revoke all on function private.agenda_wipe(uuid, text) from public, anon, authenticated;

-- Page de suivi de l'inconnu (lien secret) : null = « Cette demande n'existe plus ».
create or replace function public.agenda_booking_status(secret text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('status', k.status, 'starts_at', k.starts_at, 'ends_at', k.ends_at, 'expires_at', k.expires_at,
    'created_at', k.created_at, 'decided_at', k.decided_at, 'name', l.display_name, 'link_name', l.name,
    'link_path', case when private.agenda_link_active(l) then '/d/' || l.token end,
    'can_cancel', k.status in ('to_confirm', 'pending', 'accepted') and k.starts_at > now(),
    'answers', case when k.wiped_at is null then jsonb_strip_nulls(jsonb_build_object('first_name', k.first_name,
      'last_name', k.last_name, 'email', k.email, 'phone', k.phone, 'message', k.message)) end,
    'message_label', l.message_label,
    'contact_email', (select m.contact_email from private.moderation_settings m where m.id = 1))
  from private.agenda_bookings k join private.agenda_links l on l.id = k.link_id
  where coalesce(agenda_booking_status.secret, '') ~ '^[A-Za-z0-9_-]{24,64}$' and k.secret = agenda_booking_status.secret;
$$;

-- « Annuler ma demande » : tout est effacé, le créneau se libère ; accepté : retiré de l'agenda du membre (prévenu).
create or replace function public.agenda_booking_cancel(secret text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings;
begin
  select * into k from private.agenda_bookings b where b.secret = agenda_booking_cancel.secret for update;
  if k.id is null then raise exception 'not_found: Cette demande n''existe plus.' using errcode = 'PT404'; end if;
  if k.status not in ('to_confirm', 'pending', 'accepted') or k.starts_at <= now() then
    raise exception 'closed: Cette demande ne peut plus être annulée.' using errcode = '42501';
  end if;
  if k.status = 'accepted' then
    if k.item_id is not null then delete from public.agenda_items where id = k.item_id; end if;
    perform private.agenda_notify(k, 'booking_cancelled');
  end if;
  perform private.agenda_wipe(k.id, 'cancelled');
  return public.agenda_booking_status(agenda_booking_cancel.secret);
end $$;

-- « Effacer mes données » : la demande disparaît ; un rendez-vous accepté reste dans l'agenda du membre sous « Rendez-vous ».
create or replace function public.agenda_booking_erase(secret text) returns void
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings;
begin
  select * into k from private.agenda_bookings b where b.secret = agenda_booking_erase.secret for update;
  if k.id is null then return; end if;
  if k.item_id is not null then update public.agenda_items set title = 'Rendez-vous', notes = null where id = k.item_id; end if;
  delete from private.agenda_bookings where id = k.id;
end $$;
revoke all on function public.agenda_booking_status(text), public.agenda_booking_cancel(text), public.agenda_booking_erase(text) from public;
grant execute on function public.agenda_booking_status(text), public.agenda_booking_cancel(text), public.agenda_booking_erase(text)
  to anon, authenticated;

-- E-mails futurs (double opt-in, éteint en v1) : la demande n'arrive au membre qu'après ce clic.
create or replace function public.agenda_booking_confirm(secret text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings;
begin
  update private.agenda_bookings b set status = 'pending', confirm_by = null
  where b.secret = agenda_booking_confirm.secret and b.status = 'to_confirm' and b.confirm_by > now() returning * into k;
  if k.id is not null then perform private.agenda_notify(k, 'booking_request'); end if;
  return public.agenda_booking_status(agenda_booking_confirm.secret);
end $$;
revoke all on function public.agenda_booking_confirm(text) from public;
grant execute on function public.agenda_booking_confirm(text) to anon, authenticated;

-- « Signaler cette page » (sans compte) : vers les modérateurs, 3 / h par IP hachée.
create or replace function public.agenda_public_report(t text, reason text, comment text default null, ip text default null) returns void
language plpgsql security definer set search_path = '' as $$
declare l private.agenda_links; ih text;
begin
  select * into l from private.agenda_links where token = t;
  if l.id is null then return; end if;   -- rien à apprendre sur un jeton inconnu
  if reason is null or reason not in ('harassment', 'shocking', 'spam', 'scam', 'other') then
    raise exception 'reason: choisissez une raison' using errcode = '22023';
  end if;
  ih := private.agenda_fp('ip', nullif(btrim(coalesce(ip, '')), ''));
  if ih is not null and (select count(*) from private.agenda_ip_hits h where h.ip_hash = ih and h.kind = 'report'
                         and h.at > now() - interval '1 hour') >= 3 then
    raise exception 'rate_limited: Trop de signalements depuis cette connexion. Réessayez plus tard.' using errcode = '54000';
  end if;
  if ih is not null then insert into private.agenda_ip_hits (ip_hash, link_id, kind) values (ih, l.id, 'report'); end if;
  insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason, comment, snapshot)
  values (null, 'agenda_link', l.id::text, l.user_id, reason, nullif(btrim(left(comment, 500)), ''),
    jsonb_build_object('text', l.display_name || ' · ' || l.name, 'place', 'Lien de disponibilités (page publique)', 'at', now()));
end $$;
revoke all on function public.agenda_public_report(text, text, text, text) from public;
grant execute on function public.agenda_public_report(text, text, text, text) to anon, authenticated;

-- ───────────────────────── Demandes : propriétaire ─────────────────────────
create or replace function private.agenda_booking_json(k private.agenda_bookings) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', k.id, 'link_id', k.link_id, 'link_name', l.name, 'link_emoji', l.emoji,
    'starts_at', k.starts_at, 'ends_at', k.ends_at, 'status', k.status, 'created_at', k.created_at,
    'expires_at', k.expires_at, 'decided_at', k.decided_at, 'item_id', k.item_id,
    'first_name', k.first_name, 'last_name', k.last_name, 'email', k.email, 'phone', k.phone, 'message', k.message,
    'message_label', coalesce(l.message_label, 'Message'), 'verified', false)
  from private.agenda_links l where l.id = k.link_id;
$$;
revoke all on function private.agenda_booking_json(private.agenda_bookings) from public, anon, authenticated;

-- Mes demandes (d'un lien ou de tous) : en attente d'abord, puis les décidées encore gardées.
create or replace function public.agenda_booking_requests(link uuid default null) returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(private.agenda_booking_json(k) order by k.status <> 'pending', k.starts_at), '[]')
  from private.agenda_bookings k
  where k.owner_id = auth.uid() and (link is null or k.link_id = link) and k.status <> 'to_confirm'
    and (k.status in ('pending', 'accepted') or k.decided_at > now() - interval '7 days');
$$;

-- Pastille « 1 » : demandes en attente (marche sans notification ; temps réel : signal user:<id>).
create or replace function public.agenda_badge() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('pending', (select count(*) from private.agenda_bookings k where k.owner_id = auth.uid() and k.status = 'pending'));
$$;

create or replace function private.agenda_my_booking(bid uuid) returns private.agenda_bookings
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings;
begin
  select * into k from private.agenda_bookings where id = bid and owner_id = auth.uid() for update;
  if k.id is null then raise exception 'not_found: Cette demande n''existe plus.' using errcode = 'PT404'; end if;
  return k;
end $$;
revoke all on function private.agenda_my_booking(uuid) from public, anon, authenticated;

-- Accepter (le rendez-vous entre dans « Juste pour moi » : « Rendez-vous · Prénom N. ») ou refuser (tout est effacé).
create or replace function public.agenda_booking_decide(id uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings := private.agenda_my_booking(agenda_booking_decide.id); item uuid;
begin
  if k.status <> 'pending' then raise exception 'closed: Cette demande a déjà une réponse.' using errcode = '42501'; end if;
  if accept then
    if k.starts_at <= now() then raise exception 'closed: Ce créneau est passé.' using errcode = '42501'; end if;
    insert into public.agenda_items (user_id, calendar_id, title, starts_at, ends_at)
    values (k.owner_id, private.agenda_builtin(k.owner_id, 'personal'),
      'Rendez-vous · ' || k.first_name || coalesce(' ' || left(k.last_name, 1) || '.', ''), k.starts_at, k.ends_at)
    returning agenda_items.id into item;
    update private.agenda_bookings set status = 'accepted', decided_at = now(), item_id = item,
      mail_state = case when email is not null then 'none' else mail_state end   -- v1 : aucun e-mail (voir mail_state)
    where agenda_bookings.id = k.id returning * into k;
  else
    perform private.agenda_wipe(k.id, 'refused');
    select * into k from private.agenda_bookings where agenda_bookings.id = agenda_booking_decide.id;
  end if;
  return private.agenda_booking_json(k);
end $$;

-- Rendez-vous accepté que le membre annule ensuite : retiré de son agenda, l'inconnu le voit sur son lien de suivi.
create or replace function public.agenda_booking_owner_cancel(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings := private.agenda_my_booking(agenda_booking_owner_cancel.id);
begin
  if k.status not in ('accepted', 'pending') then raise exception 'closed: Rien à annuler.' using errcode = '42501'; end if;
  if k.item_id is not null then delete from public.agenda_items where agenda_items.id = k.item_id; end if;
  perform private.agenda_wipe(k.id, case when k.status = 'pending' then 'refused' else 'cancelled' end);
  select * into k from private.agenda_bookings where agenda_bookings.id = agenda_booking_owner_cancel.id;
  return private.agenda_booking_json(k);
end $$;

-- Signaler (copie du contenu aux modérateurs, puis refus et effacement) et Bloquer l'expéditeur (empreintes, puis refus).
create or replace function public.agenda_booking_report(id uuid, reason text, comment text default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings := private.agenda_my_booking(agenda_booking_report.id); rid uuid;
begin
  rid := public.report_content('booking_request', k.id::text, reason, comment);
  if k.status = 'pending' then perform private.agenda_wipe(k.id, 'refused'); end if;
  return rid;
end $$;

create or replace function public.agenda_booking_block(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare k private.agenda_bookings := private.agenda_my_booking(agenda_booking_block.id);
begin
  insert into private.agenda_sender_blocks (owner_id, fp, kind, expires_at)
  select k.owner_id, x.fp, x.kind, case when x.kind = 'ip' then now() + interval '24 hours' end
  from (values (k.email_fp, 'email'), (k.phone_fp, 'phone'), (k.ip_hash, 'ip')) x(fp, kind) where x.fp is not null
  on conflict (owner_id, fp) do update set expires_at = excluded.expires_at, created_at = now();
  if k.status = 'pending' then perform private.agenda_wipe(k.id, 'refused'); end if;
  return jsonb_build_object('blocked', (select count(*) from private.agenda_sender_blocks b where b.owner_id = k.owner_id
    and (b.expires_at is null or b.expires_at > now())));
end $$;

-- Débloquer tous les expéditeurs bloqués (on ne garde aucune liste lisible : seulement des empreintes).
create or replace function public.agenda_unblock_senders() returns jsonb
language sql security definer set search_path = '' as $$
  with d as (delete from private.agenda_sender_blocks where owner_id = auth.uid() returning 1)
  select jsonb_build_object('removed', (select count(*) from d));
$$;
revoke all on function public.agenda_booking_requests(uuid), public.agenda_badge(), public.agenda_booking_decide(uuid, boolean),
  public.agenda_booking_owner_cancel(uuid), public.agenda_booking_report(uuid, text, text), public.agenda_booking_block(uuid),
  public.agenda_unblock_senders() from public, anon;
grant execute on function public.agenda_booking_requests(uuid), public.agenda_badge(), public.agenda_booking_decide(uuid, boolean),
  public.agenda_booking_owner_cancel(uuid), public.agenda_booking_report(uuid, text, text), public.agenda_booking_block(uuid),
  public.agenda_unblock_senders() to authenticated;

-- Pastille en temps réel : chaque changement d'une demande prévient son propriétaire (canal user:<id>, sans contenu).
create or replace function private.agenda_booking_signal() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.party_signal('user:' || coalesce(new.owner_id, old.owner_id));
  return null;
end $$;
revoke all on function private.agenda_booking_signal() from public, anon, authenticated;
drop trigger if exists agenda_bookings_signal on private.agenda_bookings;
create trigger agenda_bookings_signal after insert or update or delete on private.agenda_bookings
  for each row execute function private.agenda_booking_signal();

-- ───────────────────────── Effacements planifiés ─────────────────────────
create or replace function private.agenda_tick() returns void
language plpgsql security definer set search_path = '' as $$
declare r record;
begin
  -- Sans réponse (48 h) : tout est effacé, le créneau se libère. Non confirmée (e-mails futurs) : supprimée.
  for r in select id from private.agenda_bookings where status = 'pending' and expires_at <= now() loop
    perform private.agenda_wipe(r.id, 'expired');
  end loop;
  delete from private.agenda_bookings where status = 'to_confirm' and confirm_by <= now();
  -- IP hachée : 24 h au plus.
  update private.agenda_bookings set ip_hash = null where ip_hash is not null and created_at < now() - interval '24 hours';
  delete from private.agenda_ip_hits where at < now() - interval '24 hours';
  delete from private.agenda_sender_blocks where expires_at is not null and expires_at <= now();
  -- 30 jours après le rendez-vous : la demande disparaît ; l'agenda du membre garde « Rendez-vous · Prénom N. ».
  delete from private.agenda_bookings where ends_at < now() - interval '30 days';
  -- Plages « pris » passées.
  delete from private.agenda_busy where ends_at <= now();
end $$;
revoke all on function private.agenda_tick() from public, anon, authenticated;
select cron.unschedule(jobid) from cron.job where jobname = 'agenda-tick';
select cron.schedule('agenda-tick', '*/10 * * * *', 'select private.agenda_tick();');

-- ───────────────────────── Notification, signalements, modération ─────────────────────────
alter table public.notification_prefs add column if not exists booking_requests boolean not null default true;

-- [prod 24.11] Contrainte ÉTENDUE (et non réécrite) : seulement si 'agenda_link' manque, en gardant les types déjà
-- présents (rejouer ce fichier après les Pronos ne retire plus 'prono' / 'prono_answer').
do $$ declare def text;
begin
  select pg_get_constraintdef(oid) into def from pg_constraint
   where conrelid = 'public.content_reports'::regclass and conname = 'content_reports_target_kind_check';
  if def is null or position('''agenda_link''' in def) = 0 then
    if def is null or position('''pet_word''::text' in def) = 0 then raise exception 'content_reports : ancre pet_word introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, '''pet_word''::text', '''pet_word''::text, ''booking_request''::text, ''agenda_link''::text');
  end if;
end $$;

do $$ declare def text;
begin
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''booking_request''' in def) = 0 then
    if position($a$    when 'group_added' then coalesce(prefs.group_added, true)$a$ in def) = 0 then
      raise exception 'web_push_allowed : ancre group_added introuvable';
    end if;
    execute replace(def, $a$    when 'group_added' then coalesce(prefs.group_added, true)$a$, $a$    when 'group_added' then coalesce(prefs.group_added, true)
    when 'booking_request' then coalesce(prefs.booking_requests, true)
    when 'booking_cancelled' then coalesce(prefs.booking_requests, true)$a$);
  end if;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''booking_request''' in def) = 0 then
    if position('''group_added'',' in def) = 0 then raise exception 'may_receive_push : ancre group_added introuvable'; end if;
    execute replace(def, '''group_added'',', '''group_added'', ''booking_request'', ''booking_cancelled'',');
  end if;
  -- Signaler une demande : seul son destinataire la voit ; la copie part sans propriétaire (personne sans compte).
  def := pg_get_functiondef('private.report_snapshot(text, text, uuid)'::regprocedure);
  if position('''booking_request''' in def) = 0 then
    if position($a$  elsif p_kind in ('profile', 'profile_photo') then$a$ in def) = 0 then raise exception 'report_snapshot : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif p_kind in ('profile', 'profile_photo') then$a$, $a$  elsif p_kind = 'booking_request' then
    return (select jsonb_build_object('owner', null, 'text', concat_ws(E'\n', concat_ws(' ', k.first_name, k.last_name), k.message),
        'at', k.created_at, 'place', 'Demande de rendez-vous · lien « ' || l.name || ' »', 'link_id', l.id)
      from private.agenda_bookings k join private.agenda_links l on l.id = k.link_id
      where k.id = uid and k.owner_id = viewer and k.wiped_at is null);
  elsif p_kind in ('profile', 'profile_photo') then$a$);
  end if;
  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''booking_request''' in def) = 0 then
    if position($a$                        else 'Zicou' end),$a$ in def) = 0 then raise exception 'notify_new_report : ancre Zicou introuvable'; end if;
    execute replace(def, $a$                        else 'Zicou' end),$a$, $a$                        when new.target_kind = 'booking_request' then 'une demande de rendez-vous'
                        when new.target_kind = 'agenda_link' then 'un lien de disponibilités'
                        else 'Zicou' end),$a$);
  end if;
  -- Masquer : la demande est effacée ; le lien est arrêté, ses demandes coupées et son nom masqué.
  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position('''booking_request''' in def) = 0 then
    if position($a$  elsif r.target_kind = 'profile_photo' then$a$ in def) = 0 then raise exception 'moderation_hide : ancre profile_photo introuvable'; end if;
    execute replace(def, $a$  elsif r.target_kind = 'profile_photo' then$a$, $a$  elsif r.target_kind = 'booking_request' then
    delete from private.agenda_bookings where id = uid;
  elsif r.target_kind = 'agenda_link' then
    update private.agenda_links set stopped_at = coalesce(stopped_at, now()), booking_enabled = false, display_name = 'Nom masqué'
      where id = uid;
  elsif r.target_kind = 'profile_photo' then$a$);
  end if;
end $$;

-- ───────────────────────── Rendez-vous, calendriers et réglages par fonctions (web et iPhone) ─────────────────────────
-- Les tables restent lisibles et modifiables par leur propriétaire (RLS) ; ces fonctions évitent à chaque écran de refaire
-- les règles (calendrier par défaut, suppression d'une seule date d'une série, rendez-vous accepté par un lien).
create or replace function public.agenda_item_save(item jsonb, id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); r public.agenda_items;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if agenda_item_save.id is null then
    insert into public.agenda_items (user_id, calendar_id, title, place, notes, starts_at, ends_at, all_day, repeat, repeat_until,
      alert_minutes, busy)
    values (me, coalesce((item->>'calendar_id')::uuid, private.agenda_builtin(me, 'personal')), btrim(item->>'title'),
      nullif(btrim(item->>'place'), ''), nullif(btrim(item->>'notes'), ''), (item->>'starts_at')::timestamptz,
      (item->>'ends_at')::timestamptz, coalesce((item->>'all_day')::boolean, false), coalesce(item->>'repeat', 'none'),
      (item->>'repeat_until')::date, (item->>'alert_minutes')::int, coalesce((item->>'busy')::boolean, true))
    returning * into r;
  else
    update public.agenda_items i set
      calendar_id = case when item ? 'calendar_id' then coalesce((item->>'calendar_id')::uuid, i.calendar_id) else i.calendar_id end,
      title = coalesce(btrim(item->>'title'), i.title),
      place = case when item ? 'place' then nullif(btrim(item->>'place'), '') else i.place end,
      notes = case when item ? 'notes' then nullif(btrim(item->>'notes'), '') else i.notes end,
      starts_at = coalesce((item->>'starts_at')::timestamptz, i.starts_at),
      ends_at = coalesce((item->>'ends_at')::timestamptz, i.ends_at),
      all_day = coalesce((item->>'all_day')::boolean, i.all_day),
      repeat = coalesce(item->>'repeat', i.repeat),
      repeat_until = case when item ? 'repeat_until' then (item->>'repeat_until')::date else i.repeat_until end,
      alert_minutes = case when item ? 'alert_minutes' then (item->>'alert_minutes')::int else i.alert_minutes end,
      busy = coalesce((item->>'busy')::boolean, i.busy)
    where i.id = agenda_item_save.id and i.user_id = me returning * into r;
    if r.id is null then raise exception 'not_found: Ce rendez-vous n''existe plus.' using errcode = 'PT404'; end if;
  end if;
  return to_jsonb(r) - 'user_id';
end $$;

-- Supprimer : 'all' (tout), 'one' (seulement la date `occurrence`, heure de Suisse), 'following' (celle-ci et les suivantes).
-- Un rendez-vous accepté par un lien et supprimé ici : la demande passe « annulée » (l'inconnu le voit sur son lien).
create or replace function public.agenda_item_delete(id uuid, scope text default 'all', occurrence date default null) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); r public.agenda_items; k private.agenda_bookings;
begin
  select * into r from public.agenda_items i where i.id = agenda_item_delete.id and i.user_id = me for update;
  if r.id is null then return; end if;
  if scope = 'one' and r.repeat <> 'none' and occurrence is not null then
    update public.agenda_items i set skip_dates = array_append(i.skip_dates, occurrence) where i.id = r.id;
  elsif scope = 'following' and r.repeat <> 'none' and occurrence is not null
        and occurrence > (r.starts_at at time zone 'Europe/Zurich')::date then
    update public.agenda_items i set repeat_until = occurrence - 1 where i.id = r.id;
  else
    select * into k from private.agenda_bookings b where b.item_id = r.id and b.status = 'accepted';
    if k.id is not null then perform private.agenda_wipe(k.id, 'cancelled'); end if;
    delete from public.agenda_items i where i.id = r.id;
  end if;
end $$;

-- Calendrier : un agenda ajouté avec un lien (cal = {name, color, ics_url, visible, counts_busy}) ou le réglage d'un
-- calendrier existant (nom, couleur, afficher, compte dans mes dispos ; l'adresse d'un agenda .ics).
create or replace function public.agenda_calendar_save(cal jsonb, id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); r public.agenda_calendars; u text := nullif(btrim(cal->>'ics_url'), '');
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if u is not null and (u !~ '^(https|webcal)://[^[:space:]]+$' or char_length(u) > 1000) then
    raise exception 'forbidden: Ce lien ne donne pas d''agenda. Vérifie qu''il commence par https:// ou webcal://' using errcode = '22023';
  end if;
  if agenda_calendar_save.id is null then
    if u is null then raise exception 'forbidden: Colle le lien de l''agenda.' using errcode = '22023'; end if;
    insert into public.agenda_calendars (user_id, kind, name, color, ics_url, visible, counts_busy)
    values (me, 'ics', left(coalesce(nullif(btrim(cal->>'name'), ''), 'Agenda ajouté'), 60), coalesce(cal->>'color', 'sky'), u,
      coalesce((cal->>'visible')::boolean, true), coalesce((cal->>'counts_busy')::boolean, false))
    returning * into r;
  else
    update public.agenda_calendars c set
      name = left(coalesce(nullif(btrim(cal->>'name'), ''), c.name), 60), color = coalesce(cal->>'color', c.color),
      visible = coalesce((cal->>'visible')::boolean, c.visible), counts_busy = coalesce((cal->>'counts_busy')::boolean, c.counts_busy),
      ics_url = case when c.kind = 'ics' then coalesce(u, c.ics_url) else null end
    where c.id = agenda_calendar_save.id and c.user_id = me returning * into r;
    if r.id is null then raise exception 'not_found: Ce calendrier n''existe plus.' using errcode = 'PT404'; end if;
  end if;
  return to_jsonb(r) - 'user_id';
end $$;

create or replace function public.agenda_calendar_delete(id uuid) returns void
language sql security definer set search_path = '' as $$
  delete from public.agenda_calendars c where c.id = agenda_calendar_delete.id and c.user_id = auth.uid() and c.kind = 'ics';
$$;

-- Réglages d'affichage (premier jour, vue, numéros de semaine, durée par défaut…) : objet libre de l'écran, 8 ko au plus.
create or replace function public.agenda_prefs_save(prefs jsonb) returns jsonb
language sql security definer set search_path = '' as $$
  insert into public.agenda_prefs (user_id, prefs) values (auth.uid(), coalesce(prefs, '{}'))
  on conflict (user_id) do update set prefs = public.agenda_prefs.prefs || excluded.prefs, updated_at = now()
  returning prefs;
$$;
create or replace function public.agenda_prefs_get() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce((select prefs from public.agenda_prefs where user_id = auth.uid()), '{}'::jsonb);
$$;
revoke all on function public.agenda_item_save(jsonb, uuid), public.agenda_item_delete(uuid, text, date),
  public.agenda_calendar_save(jsonb, uuid), public.agenda_calendar_delete(uuid), public.agenda_prefs_save(jsonb),
  public.agenda_prefs_get() from public, anon;
grant execute on function public.agenda_item_save(jsonb, uuid), public.agenda_item_delete(uuid, text, date),
  public.agenda_calendar_save(jsonb, uuid), public.agenda_calendar_delete(uuid), public.agenda_prefs_save(jsonb),
  public.agenda_prefs_get() to authenticated;

-- ═════════════════════════ 20261117150000_agenda_liens_calendriers.sql ═════════════════════════
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

-- ═════════════════════════ 20261117160000_agenda_liens_marges.sql ═════════════════════════
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

-- ═════════════════════════ 20261117170000_agenda_adresses.sql ═════════════════════════
-- Agenda : adresse lisible des liens de dispo (demande de l'admin du 17.11.2026) : <site>/agenda/<nom>/<lien>, par
-- exemple /agenda/ludovic/semaine, au lieu de seulement /d/<jeton>. Le nom (private.agenda_handles) est choisi une fois
-- par personne, unique sur le site, filtré comme un surnom, mots réservés refusés ; le nom du lien
-- (agenda_links.slug) est unique pour la personne. L'adresse en lettres (/d/<jeton>) marche toujours. Lien arrêté,
-- expiré, nom ou lien changé : l'adresse lisible ne montre plus rien (même page neutre que pour un lien inconnu).
-- Purement additive et rejouable.

create table if not exists private.agenda_handles (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  handle text not null unique check (handle ~ '^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$' and handle !~ '--'),
  updated_at timestamptz not null default now()
);
alter table private.agenda_handles enable row level security;
revoke all on private.agenda_handles from public, anon, authenticated;

alter table private.agenda_links add column if not exists slug text;
alter table private.agenda_links drop constraint if exists agenda_links_slug;
alter table private.agenda_links add constraint agenda_links_slug
  check (slug is null or (slug ~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$' and slug !~ '--'));
create unique index if not exists agenda_links_user_slug on private.agenda_links (user_id, slug) where slug is not null;

-- Mots qu'aucun nom ne peut prendre (rôles, marque, pages du site).
create or replace function private.agenda_handle_reserved(h text) returns boolean
language sql immutable set search_path = '' as $$
  select h = any (array['admin', 'root', 'api', 'app', 'apple', 'google', 'agenda', 'aide', 'help', 'support', 'contact',
    'moderation', 'moderateur', 'party', 'vendredi', 'vendrediparty', 'vendredi-party', 'bobycharbon', 'events', 'static',
    'compte', 'account', 'login', 'connexion', 'securite', 'security', 'officiel', 'official', 'test', 'demo', 'null'])
    or h like 'vendredi-party%' or h like 'vendrediparty%' or h like 'admin%';
$$;
revoke all on function private.agenda_handle_reserved(text) from public, anon, authenticated;

create or replace function private.agenda_link_json(l private.agenda_links) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', l.id, 'token', l.token, 'path', '/d/' || l.token, 'name', l.name, 'emoji', l.emoji,
    'display_name', l.display_name, 'rules', l.rules, 'horizon_days', l.horizon_days, 'duration_min', l.duration_min,
    'booking_enabled', l.booking_enabled, 'booking_fields', l.booking_fields, 'message_label', l.message_label,
    'calendars', to_jsonb(l.calendars), 'permanent', l.expires_at is null,
    'buffer_before_min', l.buffer_before_min, 'buffer_after_min', l.buffer_after_min,
    'slug', l.slug,
    'nice_path', (select '/agenda/' || h.handle || '/' || l.slug from private.agenda_handles h where h.user_id = l.user_id and l.slug is not null),
    'status', case when l.stopped_at is not null then 'stopped' when l.expires_at <= now() then 'expired' else 'active' end,
    'expires_at', l.expires_at, 'stopped_at', l.stopped_at, 'views', l.views, 'last_viewed_at', l.last_viewed_at,
    'pending', (select count(*) from private.agenda_bookings k where k.link_id = l.id and k.status = 'pending'),
    'created_at', l.created_at);
$$;
revoke all on function private.agenda_link_json(private.agenda_links) from public, anon, authenticated;

-- Mon nom d'adresse (null : pas encore choisi).
create or replace function public.agenda_handle() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return jsonb_build_object('handle', (select h.handle from private.agenda_handles h where h.user_id = me));
end $$;
revoke all on function public.agenda_handle() from public, anon;
grant execute on function public.agenda_handle() to authenticated;

-- Choisir / changer mon nom d'adresse (vide : retiré, les adresses lisibles s'arrêtent ; /d/<jeton> reste).
create or replace function public.agenda_handle_set(handle text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); h text := lower(btrim(coalesce(agenda_handle_set.handle, '')));
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if h = '' then
    delete from private.agenda_handles x where x.user_id = me;
    return jsonb_build_object('handle', null);
  end if;
  if not private.identity_complete(me) then
    raise exception 'profile_incomplete: Complète ton profil (prénom, nom, surnom) pour choisir ton adresse.' using errcode = '42501';
  end if;
  perform private.require_terms(me);
  if h !~ '^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$' or h ~ '--' then
    raise exception 'invalid: De 3 à 30 lettres, chiffres ou tirets, sans accent ni espace.' using errcode = '22023';
  end if;
  if private.agenda_handle_reserved(h) then
    raise exception 'duplicate: « % » est réservé. Choisis-en un autre.', h using errcode = '23505';
  end if;
  perform private.moderate_text(replace(h, '-', ' '), 'name');
  if exists (select 1 from private.agenda_handles x where x.handle = h and x.user_id <> me) then
    raise exception 'duplicate: « % » est déjà pris. Essaie avec ton nom ou un chiffre.', h using errcode = '23505';
  end if;
  insert into private.agenda_handles (user_id, handle) values (me, h)
  on conflict (user_id) do update set handle = excluded.handle, updated_at = now();
  return jsonb_build_object('handle', h);
end $$;
revoke all on function public.agenda_handle_set(text) from public, anon;
grant execute on function public.agenda_handle_set(text) to authenticated;

-- Mes liens : le nom d'adresse en plus.
create or replace function public.agenda_links() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); mx int := (select links_max from private.agenda_settings z where z.id = 1);
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return jsonb_build_object(
    'links', coalesce((select jsonb_agg(private.agenda_link_json(l) order by l.stopped_at is not null, l.created_at)
                       from private.agenda_links l where l.user_id = me), '[]'),
    'max', mx,
    'handle', (select h.handle from private.agenda_handles h where h.user_id = me),
    'missing', case when not private.identity_complete(me) then 'profile'
                    when (select terms_enforced from private.moderation_settings where id = 1) and not private.terms_accepted(me) then 'terms' end,
    'notify', coalesce((select p.booking_requests from public.notification_prefs p where p.user_id = me), true),
    'pending', (select count(*) from private.agenda_bookings k where k.owner_id = me and k.status = 'pending'));
end $$;
revoke all on function public.agenda_links() from public, anon;
grant execute on function public.agenda_links() to authenticated;

-- Nom du lien choisi par le propriétaire (link.slug : vide = sans adresse lisible), unique pour lui.
create or replace function private.agenda_link_slug_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.slug is not distinct from old.slug then return new; end if;
  if new.slug is not null then
    if new.slug !~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$' or new.slug ~ '--' then
      raise exception 'invalid: Nom du lien : lettres, chiffres ou tirets, sans accent ni espace.' using errcode = '22023';
    end if;
    perform private.moderate_text(replace(new.slug, '-', ' '), 'name');
    if exists (select 1 from private.agenda_links x where x.user_id = new.user_id and x.slug = new.slug and x.id <> new.id) then
      raise exception 'duplicate: Tu as déjà un lien « % ». Choisis un autre nom.', new.slug using errcode = '23505';
    end if;
  end if;
  return new;
end $$;
revoke all on function private.agenda_link_slug_guard() from public, anon, authenticated;
drop trigger if exists agenda_links_slug_guard on private.agenda_links;
create trigger agenda_links_slug_guard before insert or update of slug on private.agenda_links
  for each row execute function private.agenda_link_slug_guard();

-- Le nom du lien s'enregistre avec le reste (agenda_link_save garde sa signature) : appelée juste après par l'écran.
create or replace function public.agenda_link_set_slug(id uuid, slug text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; s text := nullif(lower(btrim(coalesce(agenda_link_set_slug.slug, ''))), '');
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if s is not null and not exists (select 1 from private.agenda_handles h where h.user_id = me) then
    raise exception 'forbidden: Choisis d''abord ton nom d''adresse.' using errcode = '42501';
  end if;
  update private.agenda_links x set slug = s, updated_at = now()
  where x.id = agenda_link_set_slug.id and x.user_id = me returning * into l;
  if l.id is null then raise exception 'not_found: Ce lien n''existe plus.' using errcode = 'PT404'; end if;
  return private.agenda_link_json(l);
end $$;
revoke all on function public.agenda_link_set_slug(uuid, text) from public, anon;
grant execute on function public.agenda_link_set_slug(uuid, text) to authenticated;

-- Page publique : l'adresse lisible donne le jeton du lien, seulement s'il est actif (sinon null : page neutre).
create or replace function public.agenda_resolve(handle text, slug text) returns text
language sql stable security definer set search_path = '' as $$
  select l.token from private.agenda_handles h
    join private.agenda_links l on l.user_id = h.user_id and l.slug = lower(agenda_resolve.slug)
  where h.handle = lower(agenda_resolve.handle) and private.agenda_link_active(l);
$$;
revoke all on function public.agenda_resolve(text, text) from public;
grant execute on function public.agenda_resolve(text, text) to anon, authenticated;

-- ═════════════════════════ 20261117200000_agenda_durees.sql ═════════════════════════
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

-- [prod 24.11] Rejouable : 20261117140000 recrée la demande à 4 arguments ; une fois la version avec durée en place,
-- l'ancienne est retirée (sinon deux fonctions agenda_booking_request ambiguës).
do $$ begin
  if to_regprocedure('public.agenda_booking_request(text,timestamptz,jsonb,text,integer)') is not null then
    drop function if exists public.agenda_booking_request(text, timestamptz, jsonb, text);
  end if;
end $$;

-- ═════════════════════════ 20261117210000_agenda_pas_present.sql ═════════════════════════
-- Agenda : une soirée Party à laquelle on a répondu « Pas présent » ne rend plus occupé, même si on l'organise
-- (analyse du 17.11 : la « Fondue » de l'admin, répondue « Pas présent », bloquait toute sa soirée sur son lien de dispo).
-- Purement additive et rejouable : private.agenda_party_spans est ÉTENDUE par ancre.

do $$ declare def text;
begin
  def := pg_get_functiondef('private.agenda_party_spans(uuid,timestamptz,timestamptz)'::regprocedure);
  if position('n.status = ''no''' in def) = 0 then
    if position('and (ev.created_by = uid' in def) = 0 then raise exception 'agenda_party_spans : ancre created_by introuvable'; end if;
    execute replace(def, 'and (ev.created_by = uid',
      'and not exists (select 1 from public.rsvps n where n.event_id = ev.id and n.user_id = uid and n.status = ''no'')
    and (ev.created_by = uid');
  end if;
end $$;
revoke all on function private.agenda_party_spans(uuid, timestamptz, timestamptz) from public, anon, authenticated;

-- ═════════════════════════ 20261124090000_agenda_apercu_delai.sql ═════════════════════════
-- Agenda : l'aperçu d'un lien (« Voici ce que verra la personne ») tient compte du délai minimum (recette iPhone du 24.11).
-- Avec les demandes de rendez-vous allumées, l'aperçu ne recevait pas min_notice_min (null) : aucun créneau, « Aucun moment
-- libre dans ces heures » juste au-dessus de « Dès le … ». Délai lu dans le brouillon (par 15 min, 14 jours au plus),
-- 12 h sinon, comme un nouveau lien. Purement additive et rejouable.
create or replace function public.agenda_link_preview(link jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare l private.agenda_links; n int;
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
  n := case when jsonb_typeof(link->'min_notice_min') = 'number' then (link->>'min_notice_min')::numeric::int end;
  l.min_notice_min := case when n between 0 and 20160 and n % 15 = 0 then n else 720 end;
  return jsonb_build_object('slots', private.agenda_link_free(l), 'tz', 'Europe/Zurich');
end $$;
revoke all on function public.agenda_link_preview(jsonb) from public, anon;
grant execute on function public.agenda_link_preview(jsonb) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261117140000', 'agenda') on conflict do nothing;
insert into supabase_migrations.schema_migrations (version, name) values ('20261117150000', 'agenda_liens_calendriers') on conflict do nothing;
insert into supabase_migrations.schema_migrations (version, name) values ('20261117160000', 'agenda_liens_marges') on conflict do nothing;
insert into supabase_migrations.schema_migrations (version, name) values ('20261117170000', 'agenda_adresses') on conflict do nothing;
insert into supabase_migrations.schema_migrations (version, name) values ('20261117200000', 'agenda_durees') on conflict do nothing;
insert into supabase_migrations.schema_migrations (version, name) values ('20261117210000', 'agenda_pas_present') on conflict do nothing;
insert into supabase_migrations.schema_migrations (version, name) values ('20261124090000', 'agenda_apercu_delai') on conflict do nothing;
notify pgrst, 'reload schema';
commit;
