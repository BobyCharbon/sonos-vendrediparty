-- Zicou : la barre « petit cadeau » (avis de l'admin du 5.11.2026 : « une barre qui se remplit et il peut récupérer des
-- pièces ou des choses comme ça, toutes les 2-3 heures »).
--
-- Le calcul (remplissage en 2 h 30, pause la nuit 23 h – 8 h, 4 récupérations par jour, tirage HMAC aux chances
-- affichées) est fait par le serveur Party (app/pet_bar.py) et rangé dans pets.owner -> 'bar'. Ici seulement :
-- 1. pets.bar_full_at : l'heure où la barre sera pleine, recopiée de owner -> 'bar' ->> 'full_at' par un déclencheur
--    (pet_save inchangée) ;
-- 2. la notification « pet_bar » (« Ta barre Zicou est pleine 🎁 ») : private.pet_bar_notify, toutes les 10 minutes ;
--    une par barre au plus, 2 par jour au plus, jamais entre 23 h et 8 h, jamais pendant une soirée où la personne est
--    inscrite présente, ni pendant une pause des notifications, ni si elle est déjà passée depuis que la barre est pleine ;
-- 3. son interrupteur notification_prefs.pet_bar (activé par défaut), respecté par tous les canaux : branches AJOUTÉES
--    à la version en place de private.web_push_allowed et private.may_receive_push (jamais recopiées).
-- Purement additive et rejouable. Prérequis : Compagnon (20261104130000 / 150000 / 170000), pause des notifications
-- (20261103120000 : private.push_paused), pg_cron.

-- 1. Colonnes ---------------------------------------------------------------------------------------------------------
alter table public.pets add column if not exists bar_full_at timestamptz;
alter table public.pets add column if not exists bar_notified_for timestamptz;   -- barre déjà annoncée (une fois)
alter table public.pets add column if not exists bar_sent_on date;
alter table public.pets add column if not exists bar_sent_n integer not null default 0;
alter table public.notification_prefs add column if not exists pet_bar boolean not null default true;
create index if not exists pets_bar_full_at on public.pets (bar_full_at) where bar_full_at is not null;

-- Recopie de l'heure « pleine » écrite par le serveur Party (illisible : rien, jamais d'erreur à l'enregistrement).
create or replace function private.pet_bar_copy() returns trigger
language plpgsql set search_path = '' as $$
declare
  v text := new.owner -> 'bar' ->> 'full_at';
begin
  new.bar_full_at := case when v ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)$' then v::timestamptz end;
  return new;
exception when others then
  new.bar_full_at := null;
  return new;
end;
$$;
revoke all on function private.pet_bar_copy() from public, anon, authenticated;
drop trigger if exists pets_bar_copy on public.pets;
create trigger pets_bar_copy before insert or update of owner on public.pets
  for each row execute function private.pet_bar_copy();
update public.pets set owner = owner where bar_full_at is null and owner ? 'bar';   -- déjà là : recopiées une fois

-- 2. Notification « barre pleine » -------------------------------------------------------------------------------------
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
              and (p.last_seen_at is null or p.last_seen_at < p.bar_full_at)     -- pas encore passé depuis
              and coalesce(np.pet_bar, true)
              and private.is_account_active(p.user_id)
              and not private.push_paused(p.user_id, 'pet_bar')
              and not private.pet_at_soiree(p.user_id, at_time) loop
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

do $$
begin
  perform cron.unschedule('pet-bar-notify') where exists (select 1 from cron.job where jobname = 'pet-bar-notify');
  perform cron.schedule('pet-bar-notify', '*/10 * * * *', 'select private.pet_bar_notify();');
end $$;

-- 3. Interrupteur respecté par tous les canaux : branches AJOUTÉES à la définition en place, une seule fois.
do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''pet_streak'' then coalesce(prefs.pet_streaks, true)';
begin
  if position('''pet_bar''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'web_push_allowed : branche pet_streak introuvable, pet_bar non ajouté';
  end if;
  execute replace(def, anchor, anchor || E'\n    when ''pet_bar'' then coalesce(prefs.pet_bar, true)');
end $$;

do $$
declare
  def text := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  anchor text := '''pet_gift'', ''pet_streak''';
begin
  if position('''pet_bar''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'may_receive_push : branche pet_streak introuvable, pet_bar non ajouté';
  end if;
  execute replace(def, anchor, anchor || ', ''pet_bar''');
end $$;
