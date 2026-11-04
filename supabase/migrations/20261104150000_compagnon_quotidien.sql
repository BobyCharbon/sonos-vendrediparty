-- Compagnon, lot 1 « donner l'envie de venir tous les jours » (avis de l'admin, 4 novembre 2026, plan du game designer
-- validé : lot 1 maintenant ; la mort après 72 h ventre vide est gardée).
--
-- La boucle du jour (coffre, série protégée, missions, rituels, pièces) est calculée par le serveur Party
-- (app/pet_loop.py, app/pet_streak.py) et rangée dans pets.owner : rien de nouveau à garder ici, sauf :
-- 1. MESURE : public.pet_opens, une ligne par compte et par jour (Zurich) : nombre d'ouvertures, première et dernière,
--    d'où elles viennent (tab, notification, widget, link) ; remplie par pet_load(p_src). Vue en lecture seule
--    private.pet_engagement (cohortes J1/J7/J30, jours actifs sur 7, ouvertures par jour, interrupteurs coupés) et
--    public.pet_admin_stats() pour la tuile « Compagnon » de l'admin (réservée aux admins).
-- 2. RAPPEL DU JOUR « intelligent » : pets.nudge (préparé par le serveur à chaque enregistrement : heure apprise =
--    heure habituelle de passage − 15 min, repli 17–20 h ; texte écrit par lui). private.pet_notify envoie AU PLUS UNE
--    notification par jour (hors alertes vitales), jamais entre 23 h et 8 h, jamais pendant une soirée où la personne
--    est inscrite présente, et seulement si elle n'est pas encore passée aujourd'hui :
--      · pet_gift   : « Léa m'a fait un câlin 🤗 » (cadeau d'un ami pas encore vu) — interrupteur pet_gifts ;
--      · pet_streak : « Aujourd'hui, ça fera 7 jours qu'on se voit 🔥 » (palier de série) — interrupteur pet_streaks ;
--      · pet_daily  : le rappel du jour (coffre qui brille, petit creux, mission…) — interrupteur pet_daily.
--    Les alertes vitales (pet_alert, 48 h et 12 h avant un envol) ne changent pas. Le toucher porte src=notif (mesure).
-- 3. Chaque type a SON interrupteur, respecté par tous les canaux : branches AJOUTÉES à la version en place de
--    private.web_push_allowed et private.may_receive_push (jamais recopiées).
-- Rejouable. pet_load() et pet_save(8 arguments) sont remplacées par leur version à un argument de plus (le Compagnon
-- n'est pas encore en prod : la migration 20261104130000 part en prod avec celle-ci, même fichier).

-- 1. Colonnes et tables --------------------------------------------------------------------------------------------------
alter table public.pets add column if not exists nudge jsonb;
alter table public.pets add column if not exists last_seen_at timestamptz;
alter table public.pets add column if not exists gifts_noted_at timestamptz;
alter table public.notification_prefs add column if not exists pet_gifts boolean not null default true;
alter table public.notification_prefs add column if not exists pet_streaks boolean not null default true;

create table if not exists public.pet_opens (
  user_id uuid not null references public.profiles(id) on delete cascade,
  day date not null,
  n integer not null default 1 check (n >= 1),
  first_at timestamptz not null default now(),
  last_at timestamptz not null default now(),
  src jsonb not null default '{}',
  primary key (user_id, day)
);
create index if not exists pet_opens_day on public.pet_opens (day);
alter table public.pet_opens enable row level security;
revoke all on public.pet_opens from anon, authenticated;

-- 2. Chargement : compte l'ouverture (p_src), note le passage ---------------------------------------------------------
drop function if exists public.pet_load();
create or replace function public.pet_load(p_src text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_guard();
  today date := (now() at time zone 'Europe/Zurich')::date;
begin
  if p_src in ('tab', 'notification', 'widget', 'link') then
    insert into public.pet_opens as o (user_id, day, src) values (me, today, jsonb_build_object(p_src, 1))
    on conflict (user_id, day) do update
      set n = o.n + 1, last_at = now(),
          src = o.src || jsonb_build_object(p_src, coalesce((o.src ->> p_src)::integer, 0) + 1);
  end if;
  update public.pets set last_seen_at = now() where user_id = me;
  return jsonb_build_object(
    'pet', (select jsonb_build_object('life', p.life, 'owner', p.owner, 'version', p.version)
              from public.pets p where p.user_id = me),
    'gifts', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'kind', g.kind, 'created_at', g.created_at,
                                                            'from_name', coalesce(pr.display_name, 'Un ami')) order by g.created_at)
                         from public.pet_gifts g left join public.profiles pr on pr.id = g.from_user
                        where g.to_user = me and g.applied_at is null), '[]'::jsonb),
    'brain', coalesce((select jsonb_agg(b.played_at order by b.played_at)
                         from (select played_at from public.brain_sessions
                                where user_id = me and played_at > now() - interval '48 hours'
                                order by played_at desc limit 20) b), '[]'::jsonb),
    'events', coalesce((select jsonb_agg(jsonb_build_object('id', e.id, 'starts_at', e.starts_at))
                          from public.rsvps r join public.events e on e.id = r.event_id
                         where r.user_id = me and r.status = 'yes' and not r.waitlisted and e.status = 'published'
                           and e.starts_at between now() - interval '7 days' and now()), '[]'::jsonb));
end;
$$;
revoke all on function public.pet_load(text) from public, anon;
grant execute on function public.pet_load(text) to authenticated;

-- 3. Enregistrement : + le rappel de demain (p_nudge) ------------------------------------------------------------------
drop function if exists public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb);
create or replace function public.pet_save(p_life jsonb, p_owner jsonb, p_version integer, p_hungry_at timestamptz,
                                           p_dies_at timestamptz, p_cared boolean default false,
                                           p_gifts uuid[] default '{}', p_journal jsonb default '[]',
                                           p_nudge jsonb default null)
returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_guard();
  cur public.pets;
  v_gen integer;
  v_stage text := p_life ->> 'stage';
  v_name text := coalesce(p_life ->> 'name', '');
  v_nudge jsonb;
  entry jsonb;
begin
  if jsonb_typeof(p_life) is distinct from 'object' or jsonb_typeof(p_owner) is distinct from 'object'
     or pg_column_size(p_life) > 8000 or pg_column_size(p_owner) > 32000 then
    raise exception 'invalid: État illisible.';
  end if;
  begin
    v_gen := (p_life ->> 'gen')::integer;
  exception when others then
    raise exception 'invalid: État illisible.';
  end;
  if v_gen is null or v_gen < 1 or v_stage is null or v_stage not in ('egg', 'baby', 'teen', 'adult', 'dead')
     or char_length(v_name) not between 1 and 40 then
    raise exception 'invalid: État illisible.';
  end if;
  if jsonb_typeof(coalesce(p_journal, '[]')) <> 'array' or jsonb_array_length(coalesce(p_journal, '[]')) > 12 then
    raise exception 'invalid: Journal illisible.';
  end if;
  -- Rappel de demain : un objet court, une minute du jour entre 8 h et 22 h 45, un type connu ; sinon ignoré.
  v_nudge := case when jsonb_typeof(p_nudge) = 'object' and pg_column_size(p_nudge) < 2000
                       and coalesce(p_nudge ->> 'kind', '') in ('pet_daily', 'pet_streak')
                       and coalesce(p_nudge ->> 'minute', '') ~ '^\d{1,4}$'
                       and coalesce(p_nudge ->> 'day', '') ~ '^\d{4}-\d{2}-\d{2}$'
                  then p_nudge end;
  if v_nudge is not null and (v_nudge ->> 'minute')::integer not between 480 and 1365 then
    v_nudge := null;
  end if;
  select * into cur from public.pets where user_id = me for update;
  if cur.user_id is null then
    if coalesce(p_version, 0) <> 0 then
      raise exception 'conflict: Ton compagnon a changé sur un autre appareil.';
    end if;
    insert into public.pets (user_id, life, owner, version, gen, name, stage, hungry_at, dies_at, last_care_at, nudge,
                             last_seen_at)
    values (me, p_life, p_owner, 1, v_gen, v_name, v_stage, p_hungry_at, p_dies_at, case when p_cared then now() end,
            v_nudge, now())
    on conflict (user_id) do nothing;
    if not found then
      raise exception 'conflict: Ton compagnon a changé sur un autre appareil.';
    end if;
  else
    if cur.version is distinct from p_version then
      raise exception 'conflict: Ton compagnon a changé sur un autre appareil.';
    end if;
    if v_gen < cur.gen then
      raise exception 'invalid: État illisible.';
    end if;
    update public.pets set
      life = p_life, owner = p_owner, version = cur.version + 1, gen = v_gen, name = v_name, stage = v_stage,
      hungry_at = p_hungry_at, dies_at = p_dies_at, nudge = v_nudge, last_seen_at = now(),
      last_care_at = case when p_cared then now() else cur.last_care_at end,
      -- Alertes à refaire si l'envol prévu a reculé (il a mangé) ou si c'est un nouveau personnage.
      alerts_sent = case when v_gen <> cur.gen or p_dies_at is null
                           or p_dies_at > coalesce(cur.dies_at, '-infinity'::timestamptz) + interval '1 hour'
                         then '{}' else cur.alerts_sent end,
      updated_at = now()
    where user_id = me;
  end if;
  update public.pet_gifts set applied_at = now()
   where to_user = me and applied_at is null and id = any(coalesce(p_gifts, '{}'));
  for entry in select * from jsonb_array_elements(coalesce(p_journal, '[]')) loop
    if (entry ->> 'kind') ~ '^[a-z_]{2,20}$' and pg_column_size(entry) < 1000 then
      insert into public.pet_journal (user_id, kind, detail) values (me, entry ->> 'kind', coalesce(entry -> 'detail', '{}'));
    end if;
  end loop;
  delete from public.pet_journal where user_id = me and id not in (
    select id from public.pet_journal where user_id = me order by at desc, id desc limit 300);
  return jsonb_build_object('version', coalesce(cur.version, 0) + 1);
end;
$$;
revoke all on function public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb) from public, anon;
grant execute on function public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb) to authenticated;

-- 4. Notifications -------------------------------------------------------------------------------------------------------
-- En soirée : inscrit présent à un événement en cours (de 30 min avant le début à la fin, 6 h si pas de fin).
create or replace function private.pet_at_soiree(uid uuid, at_time timestamptz) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.rsvps r join public.events e on e.id = r.event_id
                  where r.user_id = uid and r.status = 'yes' and not r.waitlisted and e.status = 'published'
                    and at_time between e.starts_at - interval '30 minutes'
                                    and coalesce(e.ends_at, e.starts_at + interval '6 hours'));
$$;
revoke all on function private.pet_at_soiree(uuid, timestamptz) from public, anon, authenticated;

create or replace function private.pet_notify(at_time timestamptz default now()) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare
  local_now timestamp := at_time at time zone 'Europe/Zurich';
  today date := local_now::date;
  day_start timestamptz := (today::timestamp) at time zone 'Europe/Zurich';
  now_min integer := extract(hour from local_now)::integer * 60 + extract(minute from local_now)::integer;
  url text := '/?tab=games&pet=1&src=notif';
  -- Rappels sans texte préparé pour aujourd'hui (pas revenu depuis plusieurs jours) : écrits par lui, variés.
  generic text[] := array['J''ai trouvé un truc ce matin… je te le garde 🎁',
                          'Le coffre du jour brille sous mon lit. On l''ouvre ensemble ? 🎁',
                          'Psst… quelque chose brille dans mon coin 👀🎁',
                          'Toc toc ! Le coffre du jour t''attend jusqu''à minuit 🎁',
                          'J''ai creusé dans le jardin et… surprise ! Viens voir 🎁'];
  sent integer := 0;
  r record;
  g record;
  v_kind text;
  v_title text;
  v_body text;
  v_minute integer;
  hours_left integer;
  tag text;
begin
  -- Au plus une par jour (cadeau d'un ami, palier, rappel), entre 8 h et 23 h, hors soirée, si pas encore passé.
  if now_min >= 8 * 60 and now_min < 23 * 60 then
    for r in select p.user_id, p.name, p.nudge, p.gifts_noted_at,
                    coalesce(np.pet_daily, true) as daily_on, coalesce(np.pet_gifts, true) as gifts_on,
                    coalesce(np.pet_streaks, true) as streaks_on
               from public.pets p left join public.notification_prefs np on np.user_id = p.user_id
              where p.stage in ('baby', 'teen', 'adult')
                and p.daily_sent_on is distinct from today
                and (p.last_seen_at is null or p.last_seen_at < day_start)
                and private.is_account_active(p.user_id)
                and not private.pet_at_soiree(p.user_id, at_time) loop
      v_kind := null;
      if r.gifts_on then
        select count(*) as n, (array_agg(coalesce(pr.display_name, 'Un ami') order by g2.created_at desc))[1] as who,
               (array_agg(g2.kind order by g2.created_at desc))[1] as kind
          into g
          from public.pet_gifts g2 left join public.profiles pr on pr.id = g2.from_user
         where g2.to_user = r.user_id and g2.applied_at is null
           and g2.created_at > coalesce(r.gifts_noted_at, '-infinity'::timestamptz);
        if g.n > 0 then
          v_kind := 'pet_gift';
          v_title := r.name;
          v_body := case when g.n > 1 then g.who || ' et ' || (g.n - 1) || case when g.n > 2 then ' autres amis' else ' autre ami' end
                                           || ' m''ont gâté 💜 Viens voir !'
                         when g.kind = 'hug' then g.who || ' m''a fait un câlin 🤗 Viens voir comme je suis content !'
                         else g.who || ' m''a apporté un goûter 🍪 On le partage ?' end;
        end if;
      end if;
      if v_kind is null then
        v_minute := coalesce(case when (r.nudge ->> 'minute') ~ '^\d{1,4}$' then (r.nudge ->> 'minute')::integer end,
                             17 * 60 + abs(hashtext(r.user_id::text)) % 180);
        if now_min >= v_minute then
          if r.nudge ->> 'day' = today::text and r.nudge ->> 'kind' = 'pet_streak' and r.streaks_on then
            v_kind := 'pet_streak';
            v_title := coalesce(nullif(r.nudge ->> 'title', ''), r.name);
            v_body := r.nudge ->> 'body';
          elsif r.daily_on then
            v_kind := 'pet_daily';
            if r.nudge ->> 'day' = today::text then
              v_title := coalesce(nullif(r.nudge ->> 'alt_title', ''), r.name);
              v_body := r.nudge ->> 'alt_body';
            else
              v_title := r.name;
              v_body := generic[1 + (today - date '2026-01-01') % array_length(generic, 1)];
            end if;
          end if;
        end if;
      end if;
      continue when v_kind is null or coalesce(v_body, '') = '';
      insert into public.notifications (user_id, kind, title, body, data, dedupe_key)
      values (r.user_id, v_kind, left(v_title, 100), left(v_body, 180), jsonb_build_object('kind', v_kind, 'url', url),
              'pet_nudge:' || today)
      on conflict do nothing;
      update public.pets set daily_sent_on = today,
                             gifts_noted_at = case when v_kind = 'pet_gift' then at_time else gifts_noted_at end
       where user_id = r.user_id;
      sent := sent + 1;
    end loop;
  end if;
  -- Alertes vitales avant un envol : 48 h puis 12 h avant (une seule fois chacune, refaites s'il a remangé entre-temps).
  for r in select p.user_id, p.name, p.gen, p.dies_at, p.alerts_sent from public.pets p
            where p.stage in ('baby', 'teen', 'adult') and p.dies_at is not null
              and p.dies_at > at_time and p.dies_at <= at_time + interval '48 hours'
              and private.is_account_active(p.user_id) loop
    hours_left := floor(extract(epoch from (r.dies_at - at_time)) / 3600);
    tag := r.gen || ':' || case when hours_left < 12 then '12' else '48' end;
    continue when tag = any(r.alerts_sent);
    insert into public.notifications (user_id, kind, title, body, data)
    values (r.user_id, 'pet_alert',
            case when hours_left < 12 then r.name || ' a besoin de toi' else r.name || ' a très faim' end,
            case when hours_left < 12 then 'Il s''affaiblit : un repas dans les prochaines heures et tout ira bien 💜'
                 else 'Son ventre est vide depuis un moment. Un petit repas lui ferait tellement plaisir 🍕' end,
            jsonb_build_object('kind', 'pet_alert', 'url', url));
    -- L'alerte des 12 h vaut aussi pour celle des 48 h (jamais deux alertes d'affilée).
    update public.pets set alerts_sent = array[r.gen || ':48'] || case when hours_left < 12 then array[tag] else '{}' end
     where user_id = r.user_id;
    sent := sent + 1;
  end loop;
  return sent;
end;
$$;
revoke all on function private.pet_notify(timestamptz) from public, anon, authenticated;

-- Toutes les 10 minutes : l'heure apprise tombe à 10 minutes près (au lieu d'une fois par heure).
do $$
begin
  perform cron.unschedule('pet-notify') where exists (select 1 from cron.job where jobname = 'pet-notify');
  perform cron.schedule('pet-notify', '*/10 * * * *', 'select private.pet_notify();');
end $$;

-- Interrupteurs respectés par tous les canaux : branches AJOUTÉES à la définition en place, une seule fois.
do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''pet_alert'' then coalesce(prefs.pet_alerts, true)';
begin
  if position('''pet_gift''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'web_push_allowed : branche pet_alert introuvable, pet_gift / pet_streak non ajoutés';
  end if;
  execute replace(def, anchor, anchor || E'\n    when ''pet_gift'' then coalesce(prefs.pet_gifts, true)'
                                     || E'\n    when ''pet_streak'' then coalesce(prefs.pet_streaks, true)');
end $$;

do $$
declare
  def text := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  anchor text := 'kind in (''pet_daily'', ''pet_alert'')';
begin
  if position('''pet_gift''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'may_receive_push : branche pet_daily introuvable, pet_gift / pet_streak non ajoutés';
  end if;
  execute replace(def, anchor, 'kind in (''pet_daily'', ''pet_alert'', ''pet_gift'', ''pet_streak'')');
end $$;

-- 5. Mesure : vue en lecture seule et tuile de l'admin ------------------------------------------------------------------
create or replace view private.pet_engagement with (security_barrier) as
with firsts as (select user_id, min(day) as first_day from public.pet_opens group by user_id),
today as (select (now() at time zone 'Europe/Zurich')::date as d),
cohorts as (
  select k.n,
         count(*) filter (where f.first_day <= t.d - k.n) as eligible,
         count(*) filter (where f.first_day <= t.d - k.n and exists (
           select 1 from public.pet_opens o where o.user_id = f.user_id and o.day = f.first_day + k.n)) as retained
    from firsts f cross join today t cross join (values (1), (7), (30)) as k(n)
   group by k.n),
week as (select o.* from public.pet_opens o, today t where o.day > t.d - 7),
per_user as (select user_id, count(*) as days, sum(n) as opens from week group by user_id),
sources as (select s.key, sum(s.value::integer) as n from week, jsonb_each_text(week.src) s group by s.key)
select
  (select count(*) from public.pets) as pets,
  (select count(*) from public.pets where stage in ('baby', 'teen', 'adult')) as alive,
  (select count(*) from firsts) as players,
  (select count(*) from per_user) as active_7d,
  (select count(*) from public.pet_opens o, today t where o.day = t.d) as active_today,
  (select round(avg(days)::numeric, 2) from per_user) as active_days_per_7,
  (select round(avg(n)::numeric, 2) from week) as opens_per_day,
  (select coalesce(jsonb_object_agg(n, jsonb_build_object('eligible', eligible, 'retained', retained,
            'pct', case when eligible > 0 then round(100.0 * retained / eligible) end)), '{}') from cohorts) as cohorts,
  (select coalesce(jsonb_object_agg(key, n), '{}') from sources) as sources_7d,
  (select jsonb_build_object(
     'pet_daily', count(*) filter (where not np.pet_daily), 'pet_alerts', count(*) filter (where not np.pet_alerts),
     'pet_gifts', count(*) filter (where not np.pet_gifts), 'pet_streaks', count(*) filter (where not np.pet_streaks))
     from public.notification_prefs np join public.pets p on p.user_id = np.user_id) as switches_off;
revoke all on private.pet_engagement from public, anon, authenticated;

create or replace function public.pet_admin_stats() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.is_admin() then
    raise exception 'forbidden: Réservé aux admins.' using errcode = '42501';
  end if;
  return (select to_jsonb(e) from private.pet_engagement e);
end;
$$;
revoke all on function public.pet_admin_stats() from public, anon;
grant execute on function public.pet_admin_stats() to authenticated;

notify pgrst, 'reload schema';
