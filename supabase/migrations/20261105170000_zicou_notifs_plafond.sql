-- Zicou : AU PLUS 2 notifications push par jour et par compte, toutes sortes confondues (avis de l'admin du 5.11.2026,
-- bêta Zicou) : cadeau d'ami (pet_gift), alertes « très faim » / « a besoin de toi » (pet_alert), rappel du jour et
-- palier de série (pet_daily, pet_streak), barre pleine (pet_bar).
--
-- Priorité aux plus utiles : cadeau d'ami > très faim > rappel > barre. Comme les envois s'étalent dans la journée, les
-- moins utiles laissent de la place aux autres :
--   · cadeau d'ami et alertes : tant que moins de 2 sont partis aujourd'hui ;
--   · rappel du jour / palier : pareil, mais si une alerte « très faim » peut encore venir (envol dans moins de 48 h),
--     il ne prend jamais la dernière place (l'alerte dit déjà « viens ») ;
--   · barre pleine : seulement si RIEN n'est encore parti aujourd'hui (elle ne prend jamais la dernière place), donc
--     jamais les jours où le rappel du jour (ou le cadeau d'un ami) est déjà parti ; une barre par jour au plus.
-- Compteur du jour (Zurich) sur pets : push_on / push_n, pris par private.pet_push_take en une seule mise à jour
-- (sûr même si les deux tâches tournent en même temps). private.pet_notify et private.pet_bar_notify : leur version en
-- place (20261104150000 et 20261105160000) plus cette prise de place juste avant l'envoi.
-- Purement additive et rejouable. Prérequis : 20261104150000 (pet_notify, pet_at_soiree), 20261105160000 (barre).

-- 1. Compteur du jour ----------------------------------------------------------------------------------------------------
alter table public.pets add column if not exists push_on date;
alter table public.pets add column if not exists push_n integer not null default 0;

create or replace function private.pet_push_max() returns integer
language sql immutable set search_path = '' as $$ select 2 $$;
revoke all on function private.pet_push_max() from public, anon, authenticated;

-- Prend une place du jour si moins de `below` notifications Zicou sont déjà parties aujourd'hui (Zurich) ; vrai si prise.
create or replace function private.pet_push_take(uid uuid, at_time timestamptz, below integer) returns boolean
language plpgsql volatile security definer set search_path = '' as $$
declare
  today date := (at_time at time zone 'Europe/Zurich')::date;
  taken boolean;
begin
  update public.pets
     set push_n = case when push_on = today then push_n + 1 else 1 end, push_on = today
   where user_id = uid
     and (case when push_on = today then push_n else 0 end) < least(below, private.pet_push_max())
  returning true into taken;
  return coalesce(taken, false);
end;
$$;
revoke all on function private.pet_push_take(uuid, timestamptz, integer) from public, anon, authenticated;

-- 2. Rappel du jour, cadeau d'ami, palier, alertes vitales : version 20261104150000 + la place du jour --------------------
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
    for r in select p.user_id, p.name, p.nudge, p.gifts_noted_at, p.dies_at,
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
      -- Place du jour : le rappel laisse la dernière à une alerte « très faim » encore possible (envol < 48 h).
      continue when not private.pet_push_take(r.user_id, at_time,
        case when v_kind = 'pet_gift' then private.pet_push_max()
             when r.dies_at is not null and r.dies_at <= at_time + interval '48 hours' then private.pet_push_max() - 1
             else private.pet_push_max() end);
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
  -- Plafond du jour atteint : l'alerte attend (elle repart le lendemain si elle est toujours due).
  for r in select p.user_id, p.name, p.gen, p.dies_at, p.alerts_sent from public.pets p
            where p.stage in ('baby', 'teen', 'adult') and p.dies_at is not null
              and p.dies_at > at_time and p.dies_at <= at_time + interval '48 hours'
              and private.is_account_active(p.user_id) loop
    hours_left := floor(extract(epoch from (r.dies_at - at_time)) / 3600);
    tag := r.gen || ':' || case when hours_left < 12 then '12' else '48' end;
    continue when tag = any(r.alerts_sent);
    continue when not private.pet_push_take(r.user_id, at_time, private.pet_push_max());
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

-- 3. Barre pleine : version 20261105160000, seulement si rien d'autre n'est parti aujourd'hui -----------------------------
create or replace function private.pet_bar_notify(at_time timestamptz default now()) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare
  local_now timestamp := at_time at time zone 'Europe/Zurich';
  today date := local_now::date;
  now_min integer := extract(hour from local_now)::integer * 60 + extract(minute from local_now)::integer;
  url text := '/?tab=games&pet=1&src=notif';
  sent integer := 0;
  r record;
begin
  if now_min < 8 * 60 or now_min >= 23 * 60 then
    return 0;   -- jamais la nuit
  end if;
  for r in select p.user_id, p.name, p.bar_full_at
             from public.pets p left join public.notification_prefs np on np.user_id = p.user_id
            where p.stage in ('baby', 'teen', 'adult')
              and p.bar_full_at is not null and p.bar_full_at <= at_time
              and p.bar_full_at > at_time - interval '12 hours'                 -- pleine depuis longtemps : plus rien
              and p.bar_notified_for is distinct from p.bar_full_at              -- une fois par barre
              and (p.bar_sent_on is distinct from today or p.bar_sent_n < 2)     -- 2 par jour au plus
              and p.daily_sent_on is distinct from today                         -- rappel du jour déjà parti : rien
              and (p.last_seen_at is null or p.last_seen_at < p.bar_full_at)     -- pas encore passé depuis
              and coalesce(np.pet_bar, true)
              and private.is_account_active(p.user_id)
              and not private.push_paused(p.user_id, 'pet_bar')
              and not private.pet_at_soiree(p.user_id, at_time) loop
    -- Jamais la dernière place du jour : seulement si aucune notification Zicou n'est encore partie aujourd'hui.
    continue when not private.pet_push_take(r.user_id, at_time, 1);
    insert into public.notifications (user_id, kind, title, body, data, dedupe_key)
    values (r.user_id, 'pet_bar', left(r.name, 100), 'Ta barre Zicou est pleine 🎁 Un petit cadeau t''attend, quand tu veux.',
            jsonb_build_object('kind', 'pet_bar', 'url', url),
            'pet_bar:' || to_char(r.bar_full_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI'))
    on conflict do nothing;
    update public.pets set bar_notified_for = r.bar_full_at,
                           bar_sent_n = case when bar_sent_on = today then bar_sent_n + 1 else 1 end,
                           bar_sent_on = today
     where user_id = r.user_id;
    sent := sent + 1;
  end loop;
  return sent;
end;
$$;
revoke all on function private.pet_bar_notify(timestamptz) from public, anon, authenticated;
