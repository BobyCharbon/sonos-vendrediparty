-- Compagnon : personnage à entretenir, façon Tamagotchi (avis de l'admin 243907b1981a, 4 novembre 2026).
-- « Quelque chose qui s'entretient avec le temps, un jeu où les gens peuvent venir l'alimenter souvent » ; chacun son
-- personnage ; il peut mourir (puis on recommence avec un œuf).
--
-- Le calcul de vie est fait par le serveur Party (app/pet.py, un seul endroit) : la base GARDE l'état et sait, grâce aux
-- projections envoyées à chaque enregistrement (hungry_at, dies_at), quand prévenir le propriétaire. Aucun minuteur.
--
-- 1. public.pets : un personnage par compte. life = le personnage (montrable aux amis), owner = ce qui reste au compte
--    (série, tenues, souvenirs, compteurs du jour : jamais montré aux autres). Table fermée (RLS sans politique) : tout
--    passe par les fonctions ci-dessous, chacun n'écrit QUE le sien.
-- 2. public.pet_gifts : câlin ou goûter offert par un ami (groupe en commun), un par ami et par jour (jour de Zurich).
-- 3. public.pet_journal : journal des soins et des grands moments (éclosion, évolution, envol), 300 lignes par compte.
-- 4. Notifications, chacune avec SON interrupteur (notification_prefs.pet_daily / pet_alerts), respecté par tous les
--    canaux (private.web_push_allowed), pause 🌙 (son coupé) et heures calmes comprises (envoi retenu) :
--    · pet_daily : rappel doux une fois par jour au plus, entre 17 h et 20 h (Zurich), s'il a un petit creux et
--      qu'on n'est pas passé s'en occuper aujourd'hui ;
--    · pet_alert : deux alertes avant un envol (48 h et 12 h avant), jamais culpabilisantes.
--    Reçues par tous les comptes actifs, Guest compris (private.may_receive_push).
-- Purement additif et rejouable.

-- 1. Tables ------------------------------------------------------------------------------------------------------------
create table if not exists public.pets (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  life jsonb not null,
  owner jsonb not null,
  version integer not null default 1,
  gen integer not null default 1 check (gen >= 1),
  name text not null default '' check (char_length(name) <= 40),
  stage text not null default 'egg' check (stage in ('egg', 'baby', 'teen', 'adult', 'dead')),
  hungry_at timestamptz,
  dies_at timestamptz,
  last_care_at timestamptz,
  daily_sent_on date,
  alerts_sent text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists pets_hungry on public.pets (hungry_at) where stage <> 'dead';
create index if not exists pets_dies on public.pets (dies_at) where stage <> 'dead';
alter table public.pets enable row level security;
revoke all on public.pets from anon, authenticated;

create table if not exists public.pet_gifts (
  id uuid primary key default gen_random_uuid(),
  from_user uuid not null references public.profiles(id) on delete cascade,
  to_user uuid not null references public.profiles(id) on delete cascade,
  kind text not null check (kind in ('hug', 'snack')),
  day date not null default (now() at time zone 'Europe/Zurich')::date,
  created_at timestamptz not null default now(),
  applied_at timestamptz,
  constraint pet_gifts_not_self check (from_user <> to_user),
  constraint pet_gifts_one_a_day unique (from_user, to_user, day)
);
create index if not exists pet_gifts_pending on public.pet_gifts (to_user) where applied_at is null;
alter table public.pet_gifts enable row level security;
revoke all on public.pet_gifts from anon, authenticated;

create table if not exists public.pet_journal (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  at timestamptz not null default now(),
  kind text not null check (kind ~ '^[a-z_]{2,20}$'),
  detail jsonb not null default '{}'
);
create index if not exists pet_journal_user on public.pet_journal (user_id, at desc);
alter table public.pet_journal enable row level security;
revoke all on public.pet_journal from anon, authenticated;

alter table public.notification_prefs add column if not exists pet_daily boolean not null default true;
alter table public.notification_prefs add column if not exists pet_alerts boolean not null default true;

-- 2. Amis : au moins un groupe en commun -------------------------------------------------------------------------------
create or replace function private.pet_friends_of(me uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select distinct o.user_id
    from public.member_group_members m
    join public.member_group_members o on o.group_id = m.group_id and o.user_id <> me
    join public.profiles p on p.id = o.user_id and p.status = 'active'
   where m.user_id = me;
$$;
revoke all on function private.pet_friends_of(uuid) from public, anon, authenticated;

create or replace function private.pet_guard() returns uuid
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Connecte-toi pour retrouver ton Zicou.';
  end if;
  return me;
end;
$$;
revoke all on function private.pet_guard() from public, anon, authenticated;

-- 3. Mon personnage ------------------------------------------------------------------------------------------------------
-- Tout ce dont le serveur a besoin pour le faire vivre : l'état, les cadeaux pas encore ouverts, les parties de
-- Méninges et les soirées récentes (récompenses ; le serveur ne compte que les nouvelles).
create or replace function public.pet_load() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := private.pet_guard();
begin
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
revoke all on function public.pet_load() from public, anon;
grant execute on function public.pet_load() to authenticated;

-- Enregistre mon personnage (version attendue : 0 pour le premier œuf). Garde-fous : taille, génération qui ne
-- recule jamais, stade et nom valides ; conflit si un autre appareil a enregistré entre-temps (le serveur relit).
create or replace function public.pet_save(p_life jsonb, p_owner jsonb, p_version integer, p_hungry_at timestamptz,
                                           p_dies_at timestamptz, p_cared boolean default false,
                                           p_gifts uuid[] default '{}', p_journal jsonb default '[]')
returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_guard();
  cur public.pets;
  v_gen integer;
  v_stage text := p_life ->> 'stage';
  v_name text := coalesce(p_life ->> 'name', '');
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
  select * into cur from public.pets where user_id = me for update;
  if cur.user_id is null then
    if coalesce(p_version, 0) <> 0 then
      raise exception 'conflict: Ton Zicou a changé sur un autre appareil.';
    end if;
    insert into public.pets (user_id, life, owner, version, gen, name, stage, hungry_at, dies_at, last_care_at)
    values (me, p_life, p_owner, 1, v_gen, v_name, v_stage, p_hungry_at, p_dies_at, case when p_cared then now() end)
    on conflict (user_id) do nothing;
    if not found then
      raise exception 'conflict: Ton Zicou a changé sur un autre appareil.';
    end if;
  else
    if cur.version is distinct from p_version then
      raise exception 'conflict: Ton Zicou a changé sur un autre appareil.';
    end if;
    if v_gen < cur.gen then
      raise exception 'invalid: État illisible.';
    end if;
    update public.pets set
      life = p_life, owner = p_owner, version = cur.version + 1, gen = v_gen, name = v_name, stage = v_stage,
      hungry_at = p_hungry_at, dies_at = p_dies_at,
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
revoke all on function public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb) from public, anon;
grant execute on function public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb) to authenticated;

-- 4. Amis -----------------------------------------------------------------------------------------------------------------
-- Ce qu'un ami voit : son surnom, sa photo et le personnage (life) — jamais owner (souvenirs, compteurs), ni le journal.
create or replace function private.pet_card(me uuid, friend uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', pr.id, 'name', pr.display_name, 'avatar_url', pr.avatar_url, 'life', p.life,
           'gifted', exists (select 1 from public.pet_gifts g where g.from_user = me and g.to_user = friend
                               and g.day = (now() at time zone 'Europe/Zurich')::date))
    from public.pets p join public.profiles pr on pr.id = p.user_id
   where p.user_id = friend;
$$;
revoke all on function private.pet_card(uuid, uuid) from public, anon, authenticated;

create or replace function public.pet_friends() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := private.pet_guard();
begin
  return coalesce((select jsonb_agg(c order by c ->> 'name')
                     from (select private.pet_card(me, f) as c
                             from private.pet_friends_of(me) f
                            where exists (select 1 from public.pets p where p.user_id = f)
                            limit 200) x), '[]'::jsonb);
end;
$$;
revoke all on function public.pet_friends() from public, anon;
grant execute on function public.pet_friends() to authenticated;

create or replace function public.pet_friend(p_friend uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := private.pet_guard();
begin
  if p_friend is null or not exists (select 1 from private.pet_friends_of(me) f where f = p_friend)
     or not exists (select 1 from public.pets where user_id = p_friend) then
    raise exception 'forbidden: Tu ne peux rendre visite qu''aux membres de tes groupes.';
  end if;
  return private.pet_card(me, p_friend);
end;
$$;
revoke all on function public.pet_friend(uuid) from public, anon;
grant execute on function public.pet_friend(uuid) to authenticated;

-- Câlin ou goûter pour le compagnon d'un ami : un par ami et par jour ; ouvert par l'ami à sa prochaine visite.
create or replace function public.pet_gift(p_friend uuid, p_kind text) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := private.pet_guard();
begin
  if p_kind is null or p_kind not in ('hug', 'snack') then
    raise exception 'invalid: Cadeau inconnu.';
  end if;
  if p_friend is null or not exists (select 1 from private.pet_friends_of(me) f where f = p_friend) then
    raise exception 'forbidden: Tu ne peux rendre visite qu''aux membres de tes groupes.';
  end if;
  if not exists (select 1 from public.pets where user_id = p_friend and stage in ('baby', 'teen', 'adult')) then
    raise exception 'invalid: Son Zicou ne peut pas recevoir de cadeau pour l''instant.';
  end if;
  insert into public.pet_gifts (from_user, to_user, kind) values (me, p_friend, p_kind)
  on conflict on constraint pet_gifts_one_a_day do nothing;
  if not found then
    raise exception 'limit: Tu lui as déjà fait un cadeau aujourd''hui. Reviens demain 💜';
  end if;
  insert into public.pet_journal (user_id, kind, detail) values (me, 'gift_given', jsonb_build_object('kind', p_kind));
  return jsonb_build_object('ok', true);
end;
$$;
revoke all on function public.pet_gift(uuid, text) from public, anon;
grant execute on function public.pet_gift(uuid, text) to authenticated;

-- 5. Notifications ---------------------------------------------------------------------------------------------------------
create or replace function private.pet_notify(at_time timestamptz default now()) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare
  local_now timestamp := at_time at time zone 'Europe/Zurich';
  today date := local_now::date;
  day_start timestamptz := (today::timestamp) at time zone 'Europe/Zurich';
  sent integer := 0;
  r record;
  hours_left integer;
  tag text;
begin
  -- Rappel doux du jour (17 h – 20 h) : un petit creux, et personne n'est passé s'en occuper aujourd'hui.
  if extract(hour from local_now) between 17 and 19 then
    for r in select p.user_id, p.name from public.pets p
              where p.stage in ('baby', 'teen', 'adult') and p.hungry_at <= at_time
                and p.daily_sent_on is distinct from today
                and (p.last_care_at is null or p.last_care_at < day_start)
                and private.is_account_active(p.user_id) loop
      insert into public.notifications (user_id, kind, title, body, data, dedupe_key)
      values (r.user_id, 'pet_daily', r.name || ' a un petit creux 🍕', 'Passe lui faire un coucou quand tu as un moment.',
              jsonb_build_object('kind', 'pet_daily', 'url', '/?tab=games&pet=1'), 'pet_daily:' || today)
      on conflict do nothing;
      update public.pets set daily_sent_on = today where user_id = r.user_id;
      sent := sent + 1;
    end loop;
  end if;
  -- Alertes avant un envol : 48 h puis 12 h avant (une seule fois chacune, refaites s'il a remangé entre-temps).
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
            jsonb_build_object('kind', 'pet_alert', 'url', '/?tab=games&pet=1'));
    -- L'alerte des 12 h vaut aussi pour celle des 48 h (jamais deux alertes d'affilée).
    update public.pets set alerts_sent = array[r.gen || ':48'] || case when hours_left < 12 then array[tag] else '{}' end
     where user_id = r.user_id;
    sent := sent + 1;
  end loop;
  return sent;
end;
$$;
revoke all on function private.pet_notify(timestamptz) from public, anon, authenticated;

do $$
begin
  perform cron.unschedule('pet-notify') where exists (select 1 from cron.job where jobname = 'pet-notify');
  perform cron.schedule('pet-notify', '7 * * * *', 'select private.pet_notify();');
end $$;

-- Interrupteurs respectés par tous les canaux : on AJOUTE les deux branches à la définition en place de
-- private.web_push_allowed (réécrite par plusieurs migrations du même jour), une seule fois.
do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''group_join'' then prefs.group_joins';
begin
  if position('''pet_daily''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'web_push_allowed : branche group_join introuvable, pet_daily / pet_alert non ajoutés';
  end if;
  execute replace(def, anchor, anchor || E'\n    when ''pet_daily'' then coalesce(prefs.pet_daily, true)'
                                       || E'\n    when ''pet_alert'' then coalesce(prefs.pet_alerts, true)');
end $$;

-- Reçues par tous les comptes actifs (Guest compris), comme les messages directs : branche ajoutée à la définition en place.
do $$
declare
  def text := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  anchor text := 'select private.is_member(uid)';
begin
  if position('''pet_daily''' in def) > 0 then
    return;
  end if;
  if position(anchor in def) = 0 then
    raise exception 'may_receive_push : début inattendu, pet_daily / pet_alert non ajoutés';
  end if;
  execute replace(def, anchor, anchor || E'\n    or (kind in (''pet_daily'', ''pet_alert'') and private.is_account_active(uid))');
end $$;

notify pgrst, 'reload schema';
