-- PROD, compagnon (20261104130000) + sa boucle du jour, lot 1 « revenir tous les jours » (20261104150000) + ses
-- garde-fous (20261104170000, playtest « Marc » : seul le serveur Party écrit, cadeaux limités, amis « installés »),
-- dans cet ordre. À appliquer SEULEMENT après un « Ok prod » donné pour CES migrations.
-- + la COLLECTION (20261104210000, lot A : catalogue, exemplaires numérotés et certificats, cadeaux d'événement,
--   modération du nom et de la vitrine). PRÉREQUIS pour cette partie : 2026-11-04-moderation-apply.sql DÉJÀ appliqué
--   (blocage commun, filtre, signalements) ; sinon tout le fichier s'arrête (garde ci-dessous) et rien n'est appliqué.
--   Serveur Party à déployer avec : app/pet_catalog.json, pet_collection.py, pet_coll_store.py, pet_cert.py,
--   pet_events.py ; module Événements reconstruit (écran « Cadeaux de l'événement »).
-- + les RÉACTIONS de Zicou (20261104230000, devenue neutre : seule sa version est notée). Serveur Party à déployer avec
--   app/pet_reactions.py et app/static/pet/reactions.js.
-- + le ZICOU SUR LA FICHE PROFIL (20261104240000 : public.pet_profile). Serveur Party à déployer avec app/pet_profile.py,
--   app/static/pet/profile-zicou.js et .css ; module Événements reconstruit (fiche d'un membre).
-- + les PIÈCES ZICOU D'UN ÉVÉNEMENT (20261105090000 : droit zicou.event_coins donné à Admin et Co-admin, montant 5–100
--   versé une fois à chaque présent, journal pet_event_coin_grants ; pet_load sans « events » ni « answers »). Serveur
--   Party à déployer avec app/pet.py et app/pet_store.py ; module Événements reconstruit (page des cadeaux Zicou).
-- + la NOUVELLE ÉCONOMIE (20261105120000 : catalogue recopié, Mythiques des coffres à 8 exemplaires, cadeaux d'événement
--   réservés aux admins et co-admins, festins offerts « feast_pizza » / « feast_fondue », caisse commune du groupe).
--   Serveur Party à déployer avec app/pet_chest.py, pet_feast.py, pet_xp.py, pet_pot.py, tv_star.py, pet_catalog.json
--   (version 2) et app/static/pet/economy.js / economy.css ; app Apple TV avec la vedette (ZicouStarView).
-- Serveur Party : poser PET_SECRET = la clé du coffre, lue en prod (lecture seule) par
--   select decrypted_secret from vault.decrypted_secrets where name = 'pet_server_key';
-- Sans PET_SECRET, le serveur crée sa propre clé (DATA_DIR/pet_secret, 0600) et l'enrôle au premier besoin (une seule
-- clé acceptée : vérifier ensuite « select enrolled_at from private.pet_server_keys »).
-- Rejouable. Prérequis déjà en prod : Méninges (brain_sessions), groupes (member_group_members), pause des notifications
-- (20261103120000 : branche group_join de private.web_push_allowed), pg_cron. Indépendante des messages directs
-- (20261104100000) : les branches pet_daily / pet_alert sont AJOUTÉES aux fonctions en place, quelle que soit leur
-- version. Le serveur Party (app/pet.py, routes /api/pet/*) doit être déployé en même temps ou après.
-- Edge Functions à redéployer pour le toucher d'une notification (onglet Jeux, tous les types pet_*, src=notif pour la
-- mesure) : send-push (apns.ts) et send-web-push.
-- Tout ou rien (begin/commit).
begin;
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


insert into supabase_migrations.schema_migrations (version, name) values ('20261104130000', 'compagnon') on conflict do nothing;

-- ══ 20261104150000_compagnon_quotidien ══
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
      raise exception 'conflict: Ton Zicou a changé sur un autre appareil.';
    end if;
    insert into public.pets (user_id, life, owner, version, gen, name, stage, hungry_at, dies_at, last_care_at, nudge,
                             last_seen_at)
    values (me, p_life, p_owner, 1, v_gen, v_name, v_stage, p_hungry_at, p_dies_at, case when p_cared then now() end,
            v_nudge, now())
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

insert into supabase_migrations.schema_migrations (version, name) values ('20261104150000', 'compagnon_quotidien') on conflict do nothing;

-- ══ 20261104170000_compagnon_garde_fous ══
-- Compagnon, garde-fous (playtest « Marc », joueur compétitif, 4 novembre 2026). Purement additif et rejouable.
--
-- 1. CRITIQUE — seul le serveur Party écrit l'état. Avant : pet_save était appelable par tout compte connecté avec un
--    état forgé (999 999 pièces, série de 365 jours, toutes les tenues). Le serveur relaie avec le jeton du membre
--    (auth.uid() reste la seule identité) ET doit présenter la clé du serveur Party (p_key) : un secret aléatoire gardé
--    dans le coffre de la base (vault, « pet_server_key », créé ici s'il manque) et dans la variable d'environnement
--    PET_SECRET du serveur. Jamais envoyé au navigateur ni écrit dans le dépôt. Sans la clé : refus.
--    Choix : pas de clé « service_role » sur le serveur (elle ouvrirait TOUTE la base) ; cette clé-ci n'ouvre que
--    pet_load / pet_save / pet_gift, et seulement pour le compte dont le jeton est présenté.
--    Sans PET_SECRET, le serveur ne casse pas : il crée UNE fois sa propre clé (fichier 0600 dans DATA_DIR) et
--    l'enregistre ici par pet_server_enroll, accepté une seule fois (premier arrivé, empreinte sha256 gardée dans
--    private.pet_server_keys). Recommandé quand même : PET_SECRET = la clé du coffre (aucune fenêtre « premier
--    arrivé »). L'admin voit la date d'enrôlement et peut le remettre à zéro (delete from private.pet_server_keys).
--    En plus (si la clé fuyait un jour), pet_save refuse un état incohérent : jauges hors 0–100, pièces négatives ou
--    qui montent de plus de 1 500 d'un coup, série ou record plus longs que l'âge du personnage en base (en jours),
--    plus d'adultes « étoile » que de générations.
-- 2. Cadeaux (comptes secondaires) : pour offrir, avoir un compagnon vivant et un compte de 3 jours au moins ; un
--    compagnon reçoit au plus 3 cadeaux par jour (tous amis confondus).
-- 3. « Ami » du Compagnon : un groupe en commun où chacun est entré lui-même (lien, création) ou depuis 3 jours au
--    moins. Avant : le créateur d'un groupe pouvait y ajouter n'importe qui et devenir aussitôt son « ami » (visite,
--    cadeaux). member_group_members garde désormais qui a ajouté (added_by) et quand (added_at) ; les lignes déjà
--    là avant cette migration comptent comme acceptées.
-- La boucle du jour (pièces, coffres, série) reste calculée par le serveur (app/pet_loop.py, app/pet_store.py).

-- 1. Clé du serveur Party -------------------------------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from vault.secrets where name = 'pet_server_key') then
    perform vault.create_secret(encode(extensions.gen_random_bytes(32), 'hex'), 'pet_server_key',
                                'Compagnon : clé du serveur Party (PET_SECRET), seule à pouvoir écrire les personnages');
  end if;
end $$;

create table if not exists private.pet_server_keys (
  id integer primary key default 1 check (id = 1),     -- une seule clé enrôlée
  key_hash bytea not null,
  enrolled_at timestamptz not null default now(),
  enrolled_by uuid
);
revoke all on private.pet_server_keys from public, anon, authenticated;

create or replace function private.pet_server_ok(p_key text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(char_length(p_key) >= 32
                  and (extensions.digest(p_key, 'sha256') = extensions.digest(
                         (select decrypted_secret from vault.decrypted_secrets where name = 'pet_server_key' limit 1),
                         'sha256')
                       or exists (select 1 from private.pet_server_keys k
                                   where k.key_hash = extensions.digest(p_key, 'sha256'))), false);
$$;
revoke all on function private.pet_server_ok(text) from public, anon, authenticated;

-- Enrôlement de la clé propre au serveur (sans PET_SECRET) : accepté une seule fois. true si p_key est (désormais) la
-- clé enrôlée ou celle du coffre, false sinon (une autre clé a été enrôlée avant : l'admin tranche).
create or replace function public.pet_server_enroll(p_key text) returns boolean
language plpgsql volatile security definer set search_path = '' as $$
begin
  if p_key is null or char_length(p_key) < 32 or char_length(p_key) > 200 then
    return false;
  end if;
  insert into private.pet_server_keys (id, key_hash, enrolled_by)
  values (1, extensions.digest(p_key, 'sha256'), auth.uid())
  on conflict (id) do nothing;
  return private.pet_server_ok(p_key);
end;
$$;
revoke all on function public.pet_server_enroll(text) from public, anon;
grant execute on function public.pet_server_enroll(text) to authenticated;

-- Le compte (jeton) ET la clé du serveur : sinon refus (« server: » → le serveur Party répond « ne répond pas »).
create or replace function private.pet_server_guard(p_key text) returns uuid
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.pet_server_ok(p_key) then
    raise exception 'server: Zicou ne répond pas. Réessaie dans un instant.';
  end if;
  return private.pet_guard();
end;
$$;
revoke all on function private.pet_server_guard(text) from public, anon, authenticated;

-- 3. Amis : appartenance « installée » ------------------------------------------------------------------------------------
alter table public.member_group_members add column if not exists added_at timestamptz;
alter table public.member_group_members add column if not exists added_by uuid;
alter table public.member_group_members alter column added_at set default now();
alter table public.member_group_members alter column added_by set default auth.uid();

create or replace function private.pet_friends_of(me uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select distinct o.user_id
    from public.member_group_members m
    join public.member_group_members o on o.group_id = m.group_id and o.user_id <> me
    join public.profiles p on p.id = o.user_id and p.status = 'active'
   where m.user_id = me
     and (m.added_by is null or m.added_by = m.user_id or m.added_at <= now() - interval '3 days')
     and (o.added_by is null or o.added_by = o.user_id or o.added_at <= now() - interval '3 days');
$$;
revoke all on function private.pet_friends_of(uuid) from public, anon, authenticated;

-- Chargement : comme avant, avec la clé du serveur ------------------------------------------------------------------------
drop function if exists public.pet_load(text);
create or replace function public.pet_load(p_src text default null, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
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
revoke all on function public.pet_load(text, text) from public, anon;
grant execute on function public.pet_load(text, text) to authenticated;

-- Cohérence d'un état (défense en profondeur, en plus de la clé) : NULL si tout va bien, sinon ce qui cloche.
create or replace function private.pet_state_problem(p_life jsonb, p_owner jsonb, cur public.pets) returns text
language plpgsql stable security definer set search_path = '' as $$
declare
  k text;
  v numeric;
  coins numeric;
  before_coins numeric := 0;
  age_days integer := 1;
begin
  foreach k in array array['food', 'joy', 'energy', 'care'] loop
    v := (p_life -> 'g' ->> k)::numeric;
    if v is null or v < 0 or v > 100 then
      return 'jauge ' || k;
    end if;
  end loop;
  coins := coalesce((p_owner -> 'loop' ->> 'coins')::numeric, 0);
  if cur.user_id is not null then
    before_coins := coalesce((cur.owner -> 'loop' ->> 'coins')::numeric, 0);
    age_days := ((now() at time zone 'Europe/Zurich')::date - (cur.created_at at time zone 'Europe/Zurich')::date) + 1;
  end if;
  if coins < 0 or coins > before_coins + 1500 then
    return 'pièces';
  end if;
  if coalesce((p_owner -> 'streak' ->> 'count')::numeric, 0) > age_days
     or coalesce((p_owner -> 'streak' ->> 'best')::numeric, 0) > age_days then
    return 'série';
  end if;
  if coalesce((p_owner -> 'stats' ->> 'stars')::numeric, 0) > (p_life ->> 'gen')::numeric then
    return 'étoiles';
  end if;
  return null;
exception when others then
  return 'illisible';
end;
$$;
revoke all on function private.pet_state_problem(jsonb, jsonb, public.pets) from public, anon, authenticated;

-- Enregistrement : comme avant, avec la clé du serveur et le contrôle de cohérence ----------------------------------------
drop function if exists public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb);
create or replace function public.pet_save(p_life jsonb, p_owner jsonb, p_version integer, p_hungry_at timestamptz,
                                           p_dies_at timestamptz, p_cared boolean default false,
                                           p_gifts uuid[] default '{}', p_journal jsonb default '[]',
                                           p_nudge jsonb default null, p_key text default null)
returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
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
  v_nudge := case when jsonb_typeof(p_nudge) = 'object' and pg_column_size(p_nudge) < 2000
                       and coalesce(p_nudge ->> 'kind', '') in ('pet_daily', 'pet_streak')
                       and coalesce(p_nudge ->> 'minute', '') ~ '^\d{1,4}$'
                       and coalesce(p_nudge ->> 'day', '') ~ '^\d{4}-\d{2}-\d{2}$'
                  then p_nudge end;
  if v_nudge is not null and (v_nudge ->> 'minute')::integer not between 480 and 1365 then
    v_nudge := null;
  end if;
  select * into cur from public.pets where user_id = me for update;
  if private.pet_state_problem(p_life, p_owner, cur) is not null then
    raise exception 'invalid: État incohérent.';
  end if;
  if cur.user_id is null then
    if coalesce(p_version, 0) <> 0 then
      raise exception 'conflict: Ton Zicou a changé sur un autre appareil.';
    end if;
    insert into public.pets (user_id, life, owner, version, gen, name, stage, hungry_at, dies_at, last_care_at, nudge,
                             last_seen_at)
    values (me, p_life, p_owner, 1, v_gen, v_name, v_stage, p_hungry_at, p_dies_at, case when p_cared then now() end,
            v_nudge, now())
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
      hungry_at = p_hungry_at, dies_at = p_dies_at, nudge = v_nudge, last_seen_at = now(),
      last_care_at = case when p_cared then now() else cur.last_care_at end,
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
revoke all on function public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb, text) from public, anon;
grant execute on function public.pet_save(jsonb, jsonb, integer, timestamptz, timestamptz, boolean, uuid[], jsonb, jsonb, text) to authenticated;

-- 2. Cadeaux : clé du serveur, donneur vivant et installé, 3 cadeaux reçus par jour au plus -------------------------------
drop function if exists public.pet_gift(uuid, text);
create or replace function public.pet_gift(p_friend uuid, p_kind text, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  today date := (now() at time zone 'Europe/Zurich')::date;
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
  if not exists (select 1 from public.pets where user_id = me and stage in ('baby', 'teen', 'adult')) then
    raise exception 'invalid: Les cadeaux s''offrent de Zicou à Zicou : il faut que le tien soit là 🥚';
  end if;
  if exists (select 1 from public.profiles where id = me and created_at > now() - interval '3 days') then
    raise exception 'invalid: Les cadeaux s''offrent après tes 3 premiers jours sur Party 💜';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('pet_gift_to:' || p_friend::text, 0));
  if exists (select 1 from public.pet_gifts where from_user = me and to_user = p_friend and day = today) then
    raise exception 'limit: Tu lui as déjà fait un cadeau aujourd''hui. Reviens demain 💜';
  end if;
  if (select count(*) from public.pet_gifts where to_user = p_friend and day = today) >= 3 then
    raise exception 'limit: Son Zicou a déjà reçu plein de cadeaux aujourd''hui. Reviens demain 💜';
  end if;
  insert into public.pet_gifts (from_user, to_user, kind, day) values (me, p_friend, p_kind, today)
  on conflict on constraint pet_gifts_one_a_day do nothing;
  if not found then
    raise exception 'limit: Tu lui as déjà fait un cadeau aujourd''hui. Reviens demain 💜';
  end if;
  insert into public.pet_journal (user_id, kind, detail) values (me, 'gift_given', jsonb_build_object('kind', p_kind));
  return jsonb_build_object('ok', true);
end;
$$;
revoke all on function public.pet_gift(uuid, text, text) from public, anon;
grant execute on function public.pet_gift(uuid, text, text) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261104170000', 'compagnon_garde_fous') on conflict do nothing;

-- ══ Collection (20261104210000) ══
do $$
begin
  if to_regprocedure('private.blocked_either(uuid, uuid)') is null or to_regprocedure('private.moderate_text(text, text)') is null then
    raise exception 'Appliquer d''abord 2026-11-04-moderation-apply.sql (20261104200000) : la collection s''y branche.';
  end if;
end $$;
-- Compagnon, lot A « Collection » (décisions de l'admin du 4 novembre 2026 ; sans encore les échanges ni les rangs).
-- Purement additif et rejouable. Prérequis : 20261104130000 / 150000 / 170000 (Compagnon) et 20261104200000 (modération).
--
-- 1. CATALOGUE : public.pet_catalog = copie de app/pet_catalog.json (le fichier unique ; tests/test_pet_catalog.py
--    vérifie l'égalité). 66 objets, 10 emplacements, 6 séries, 5 raretés. Le tirage d'un Mythique n'est JAMAIS
--    augmenté ni réédité : une fois posé, il ne change plus (coalesce ci-dessous).
-- 2. EXEMPLAIRES NUMÉROTÉS : public.pet_items (Légendaires et Mythiques) : numéro unique par objet (contrainte), plafond
--    du tirage pour un Mythique (« n° 3/25 »), frappe en UNE transaction (verrou par objet), idempotente (ref : un même
--    coffre ne frappe jamais deux fois). Certificat signé par le serveur Party (Ed25519, app/pet_cert.py) : payload
--    recalculé ici, signature et code court (ZC-…) gardés. Provenance : public.pet_item_owners (jamais effacée).
--    Compte supprimé : l'exemplaire reste (numéro gardé, sans propriétaire), il ne revient jamais dans le jeu.
-- 3. CADEAUX D'ÉVÉNEMENT : l'admin (ou l'organisateur, dans les bornes fixées par l'admin) choisit EN AMONT les objets
--    et leur chance ; publication avant le début → chances et exemplaires FIGÉS ; graine tirée par la base, son
--    empreinte sha256 publiée, la graine révélée après le tirage (chacun peut refaire son propre jet). Tirage par la
--    base à la FIN de l'événement (cron toutes les 10 min, ou au premier chargement d'un présent) ; participants =
--    TOUS les PRÉSENTS (billet scanné / arrivée notée, ou noté « Présent » par l'organisateur), JAMAIS selon un
--    paiement (la colonne « payé » n'est jamais lue). Aucun lot réel : des accessoires du jeu seulement.
-- 4. MODÉRATION branchée (20261104200000) : nom du Zicou et titre de la vitrine passent par le filtre (déclencheur,
--    en plus du serveur), Signaler (report_snapshot_pet) et masquer (moderation_hide_pet), blocage commun (un joueur
--    bloqué n'est plus un « ami » du Compagnon : ni visite, ni cadeau, ni vitrine).
-- 5. Garde-fous de pet_save complétés : poussière et collection ne bondissent pas (défense en profondeur).

-- 1. Catalogue ----------------------------------------------------------------------------------------------------------
create table if not exists public.pet_catalog (
  id text primary key check (id ~ '^[a-z0-9-]{1,30}$'),
  slot text not null check (slot in ('head', 'eyes', 'neck', 'hand', 'back', 'feet', 'facets', 'effect', 'decor', 'pet')),
  series text not null check (series ~ '^[a-z]{2,20}$'),
  rarity text not null check (rarity in ('common', 'rare', 'epic', 'legendary', 'mythic')),
  edition integer check (edition is null or edition between 1 and 1000),
  source text not null check (source in ('chest', 'event')),
  label text not null check (char_length(label) between 1 and 80),
  check ((rarity = 'mythic') = (edition is not null))
);
alter table public.pet_catalog enable row level security;
revoke all on public.pet_catalog from anon, authenticated;

insert into public.pet_catalog (id, slot, series, rarity, edition, source, label) values
-- CATALOGUE (généré par app/pet_catalog.py sql_values)
('lunettes', 'eyes', 'disco', 'common', null, 'chest', 'Lunettes de soleil'),
('bandeau-eponge', 'head', 'disco', 'common', null, 'chest', 'Bandeau éponge'),
('baskets-compensees', 'feet', 'disco', 'common', null, 'chest', 'Baskets compensées'),
('facettes-miroir', 'facets', 'disco', 'common', null, 'chest', 'Facettes miroir'),
('boa', 'neck', 'disco', 'rare', null, 'chest', 'Collier lumineux'),
('micro-chrome', 'hand', 'disco', 'rare', null, 'chest', 'Micro chromé'),
('decor-piste', 'decor', 'disco', 'rare', null, 'chest', 'Piste de danse lumineuse'),
('casque', 'head', 'disco', 'epic', null, 'chest', 'Casque de DJ doré'),
('paillettes', 'neck', 'disco', 'epic', null, 'chest', 'Veste à paillettes'),
('facettes-or', 'facets', 'disco', 'legendary', null, 'chest', '« Saturday Night Zicou » : facettes d''or'),
('m-disco', 'head', 'disco', 'mythic', 25, 'chest', 'Couronne Aurore'),
('bonnet', 'head', 'montagne', 'common', null, 'chest', 'Bonnet à pompon'),
('echarpe', 'neck', 'montagne', 'common', null, 'chest', 'Écharpe douillette'),
('chaussettes-laine', 'feet', 'montagne', 'common', null, 'chest', 'Chaussettes en laine'),
('bouquet-edelweiss', 'hand', 'montagne', 'common', null, 'chest', 'Bouquet d''edelweiss'),
('cloche-vache', 'neck', 'montagne', 'rare', null, 'chest', 'Cloche de vache'),
('sac-rando', 'back', 'montagne', 'rare', null, 'chest', 'Sac à dos de rando'),
('lunettes-glacier', 'eyes', 'montagne', 'rare', null, 'chest', 'Lunettes de glacier'),
('cor-alpes', 'hand', 'montagne', 'epic', null, 'chest', 'Cor des Alpes'),
('decor-chalet', 'decor', 'montagne', 'epic', null, 'chest', 'Chalet sous la neige'),
('marmotte', 'pet', 'montagne', 'legendary', null, 'chest', 'Marmotte des Alpes'),
('m-montagne', 'facets', 'montagne', 'mythic', 25, 'chest', 'Facettes Glacier éternel'),
('casquette', 'head', 'escalade', 'common', null, 'chest', 'Casquette'),
('sac-magnesie', 'back', 'escalade', 'common', null, 'chest', 'Sac à magnésie'),
('chaussons-escalade', 'feet', 'escalade', 'common', null, 'chest', 'Chaussons d''escalade'),
('mousqueton', 'hand', 'escalade', 'common', null, 'chest', 'Mousqueton'),
('baudrier', 'neck', 'escalade', 'rare', null, 'chest', 'Baudrier'),
('casque-grimpe', 'head', 'escalade', 'rare', null, 'chest', 'Casque de grimpe'),
('corde', 'back', 'escalade', 'rare', null, 'chest', 'Corde lovée'),
('nuage-magnesie', 'effect', 'escalade', 'epic', null, 'chest', 'Nuage de magnésie'),
('decor-mur', 'decor', 'escalade', 'epic', null, 'chest', 'Mur d''escalade'),
('piolet-or', 'hand', 'escalade', 'legendary', null, 'chest', 'Piolet d''or'),
('m-escalade', 'effect', 'escalade', 'mythic', 25, 'chest', 'Aura du sommet'),
('chapeau-sorciere', 'head', 'halloween', 'common', null, 'chest', 'Chapeau de sorcière'),
('loup-bal', 'eyes', 'halloween', 'common', null, 'chest', 'Loup de bal masqué'),
('bottes-citrouille', 'feet', 'halloween', 'common', null, 'chest', 'Bottes citrouille'),
('lanterne-citrouille', 'hand', 'halloween', 'common', null, 'chest', 'Lanterne citrouille'),
('cape', 'back', 'halloween', 'rare', null, 'chest', 'Cape de héros'),
('aureole', 'head', 'halloween', 'rare', null, 'chest', 'Auréole'),
('chauve-souris', 'pet', 'halloween', 'rare', null, 'chest', 'Chauve-souris'),
('brume', 'effect', 'halloween', 'epic', null, 'chest', 'Brume ensorcelée'),
('decor-manoir', 'decor', 'halloween', 'epic', null, 'chest', 'Manoir hanté'),
('facettes-squelette', 'facets', 'halloween', 'legendary', null, 'chest', '« Zicou Squelette » : facettes phosphorescentes'),
('m-halloween', 'effect', 'halloween', 'mythic', 25, 'chest', 'Pleine lune'),
('chapeau', 'head', 'nouvelan', 'common', null, 'chest', 'Chapeau de fête'),
('lunettes-2027', 'eyes', 'nouvelan', 'common', null, 'chest', 'Lunettes « 2027 »'),
('langue-belle-mere', 'hand', 'nouvelan', 'common', null, 'chest', 'Langue de belle-mère'),
('noeud-or', 'neck', 'nouvelan', 'common', null, 'chest', 'Nœud doré'),
('confettis', 'effect', 'nouvelan', 'rare', null, 'chest', 'Pluie de confettis'),
('escarpins-paillettes', 'feet', 'nouvelan', 'rare', null, 'chest', 'Souliers à paillettes'),
('decor-minuit', 'decor', 'nouvelan', 'rare', null, 'chest', 'Minuit sur la ville'),
('comete', 'effect', 'nouvelan', 'epic', null, 'chest', 'Comète'),
('horloge-minuit', 'hand', 'nouvelan', 'epic', null, 'chest', 'Horloge de minuit'),
('feu-artifice', 'effect', 'nouvelan', 'legendary', null, 'chest', 'Feu d''artifice'),
('m-nouvelan', 'pet', 'nouvelan', 'mythic', 25, 'chest', 'Phénix de minuit'),
('noeud', 'neck', 'soirees', 'common', null, 'event', 'Nœud papillon'),
('bracelet-entree', 'hand', 'soirees', 'common', null, 'event', 'Bracelet d''entrée'),
('baskets-led', 'feet', 'soirees', 'common', null, 'event', 'Baskets LED'),
('lunettes-coeur', 'eyes', 'soirees', 'common', null, 'event', 'Lunettes cœur'),
('ailes', 'back', 'soirees', 'rare', null, 'event', 'Ailes de fée'),
('baton-lumineux', 'hand', 'soirees', 'rare', null, 'event', 'Bâton lumineux'),
('decor-salon', 'decor', 'soirees', 'rare', null, 'event', 'Le salon de Party'),
('couronne', 'head', 'soirees', 'epic', null, 'event', 'Couronne'),
('lumi', 'pet', 'soirees', 'epic', null, 'event', 'Lumi la luciole'),
('projecteurs', 'effect', 'soirees', 'legendary', null, 'event', '« Hôte de la soirée » : projecteurs'),
('m-soirees', 'head', 'soirees', 'mythic', 10, 'event', 'Boule de Party')
on conflict (id) do update set slot = excluded.slot, series = excluded.series, rarity = excluded.rarity,
  source = excluded.source, label = excluded.label,
  edition = coalesce(public.pet_catalog.edition, excluded.edition);   -- jamais réédité ni agrandi

-- 2. Exemplaires numérotés -------------------------------------------------------------------------------------------------
create table if not exists public.pet_items (
  id uuid primary key default gen_random_uuid(),
  item text not null references public.pet_catalog(id),
  serial integer not null check (serial >= 1),
  owner_id uuid references public.profiles(id) on delete set null,
  minted_for uuid references public.profiles(id) on delete set null,
  minted_at timestamptz not null default date_trunc('second', now()),
  source text not null check (source in ('chest', 'bonus_chest', 'atelier', 'event')),
  ref text not null check (char_length(ref) between 3 and 120),
  event_id uuid references public.events(id) on delete set null,
  payload text,
  sig text check (sig is null or sig ~ '^[A-Za-z0-9+/=]{40,120}$'),
  code text check (code is null or code ~ '^ZC-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$'),
  unique (item, serial)
);
create unique index if not exists pet_items_code on public.pet_items (code) where code is not null;
create unique index if not exists pet_items_ref on public.pet_items (minted_for, ref) where minted_for is not null;
create index if not exists pet_items_owner on public.pet_items (owner_id);
alter table public.pet_items enable row level security;
revoke all on public.pet_items from anon, authenticated;

create table if not exists public.pet_item_owners (
  id bigserial primary key,
  item_id uuid not null references public.pet_items(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete set null,
  since timestamptz not null default now(),
  how text not null check (how in ('minted', 'traded', 'gift', 'admin'))
);
create index if not exists pet_item_owners_item on public.pet_item_owners (item_id, since);
alter table public.pet_item_owners enable row level security;
revoke all on public.pet_item_owners from anon, authenticated;

-- Plafond du tirage d'un Mythique, vérifié à chaque insertion (en plus du verrou de la frappe).
create or replace function private.pet_items_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
declare c public.pet_catalog;
begin
  select * into c from public.pet_catalog where id = new.item;
  if c.rarity not in ('legendary', 'mythic') then
    raise exception 'invalid: seuls les Légendaires et les Mythiques sont numérotés';
  end if;
  if c.edition is not null and new.serial > c.edition then
    raise exception 'sold_out: Tous les exemplaires sont déjà partis.';
  end if;
  return new;
end $$;
revoke all on function private.pet_items_guard() from public, anon, authenticated;
drop trigger if exists pet_items_guard on public.pet_items;
create trigger pet_items_guard before insert on public.pet_items for each row execute function private.pet_items_guard();

-- Texte signé (même format que app/pet_cert.payload) : ZC1|id|objet|numéro|tirage|date de frappe (UTC)|origine.
create or replace function private.pet_item_payload(i public.pet_items) returns text
language sql stable security definer set search_path = '' as $$
  select 'ZC1|' || i.id || '|' || i.item || '|' || i.serial || '|'
         || coalesce((select edition from public.pet_catalog where id = i.item), 0) || '|'
         || to_char(i.minted_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') || '|' || i.source;
$$;

create or replace function private.pet_item_json(i public.pet_items) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', i.id, 'item', i.item, 'serial', i.serial,
    'edition', (select edition from public.pet_catalog where id = i.item),
    'minted_at', to_char(i.minted_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'source', i.source,
    'event_id', i.event_id, 'code', i.code, 'sig', i.sig, 'payload', i.payload);
$$;
revoke all on function private.pet_item_payload(public.pet_items), private.pet_item_json(public.pet_items)
  from public, anon, authenticated;

-- Frappe (interne) : verrou par objet, numéro suivant, plafond, provenance. Idempotente par (compte, ref).
create or replace function private.pet_mint_for(who uuid, p_item text, p_source text, p_ref text, p_event uuid)
returns jsonb language plpgsql volatile security definer set search_path = '' as $$
declare inst public.pet_items; n integer;
begin
  select * into inst from public.pet_items where minted_for = who and ref = p_ref;
  if found then return private.pet_item_json(inst); end if;
  perform pg_advisory_xact_lock(hashtextextended('pet_mint:' || p_item, 0));
  select coalesce(max(serial), 0) + 1 into n from public.pet_items where item = p_item;
  insert into public.pet_items (item, serial, owner_id, minted_for, source, ref, event_id)
  values (p_item, n, who, who, p_source, p_ref, p_event) returning * into inst;
  insert into public.pet_item_owners (item_id, user_id, how) values (inst.id, who, 'minted');
  return private.pet_item_json(inst);
end $$;
revoke all on function private.pet_mint_for(uuid, text, text, text, uuid) from public, anon, authenticated;

-- Frappe demandée par le serveur Party (coffre, coffre bonus, atelier) : clé du serveur + jeton du membre.
create or replace function public.pet_mint(p_item text, p_source text, p_ref text, p_key text default null)
returns jsonb language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := private.pet_server_guard(p_key); c public.pet_catalog;
begin
  select * into c from public.pet_catalog where id = p_item;
  if c.id is null or c.rarity not in ('legendary', 'mythic') then
    raise exception 'invalid: Objet inconnu.';
  end if;
  if p_source not in ('chest', 'bonus_chest', 'atelier') or coalesce(p_ref, '') !~ '^[a-z_]{3,20}:[0-9a-z:-]{1,80}$' then
    raise exception 'invalid: Frappe refusée.';
  end if;
  if c.source = 'event' then
    raise exception 'invalid: Cet objet ne se gagne qu''aux événements Party.';
  end if;
  if c.rarity = 'mythic' and p_source = 'atelier' then
    raise exception 'invalid: Un Mythique ne se fabrique pas.';
  end if;
  return private.pet_mint_for(me, p_item, p_source, p_ref, null);
end $$;
revoke all on function public.pet_mint(text, text, text, text) from public, anon;
grant execute on function public.pet_mint(text, text, text, text) to authenticated;

-- Certificat : le serveur Party signe (Ed25519) le payload calculé ici ; une seule fois par exemplaire.
create or replace function public.pet_cert_set(p_id uuid, p_sig text, p_code text, p_payload text, p_key text default null)
returns jsonb language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := private.pet_server_guard(p_key); inst public.pet_items;
begin
  select * into inst from public.pet_items where id = p_id and (owner_id = me or minted_for = me) for update;
  if inst.id is null then raise exception 'invalid: Exemplaire inconnu.'; end if;
  if inst.sig is not null then return private.pet_item_json(inst); end if;
  if p_payload is distinct from private.pet_item_payload(inst) then
    raise exception 'invalid: Certificat illisible.';
  end if;
  update public.pet_items set sig = p_sig, code = p_code, payload = p_payload where id = p_id returning * into inst;
  return private.pet_item_json(inst);
end $$;
revoke all on function public.pet_cert_set(uuid, text, text, text, text) from public, anon;
grant execute on function public.pet_cert_set(uuid, text, text, text, text) to authenticated;

-- Vérifier un objet (page d'authenticité, même sans compte) : certificat + provenance ANONYME (dates et façon).
create or replace function public.pet_verify(p_code text) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('item', i.item, 'label', c.label, 'rarity', c.rarity, 'slot', c.slot, 'series', c.series,
    'serial', i.serial, 'edition', c.edition,
    'minted_at', to_char(i.minted_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), 'source', i.source,
    'event', (select e.title from public.events e where e.id = i.event_id and e.visibility = 'all'),
    'payload', i.payload, 'sig', i.sig, 'code', i.code, 'retired', i.owner_id is null,
    'minted_so_far', (select count(*) from public.pet_items x where x.item = i.item),
    'owners', coalesce((select jsonb_agg(jsonb_build_object('since', o.since, 'how', o.how) order by o.since)
                          from public.pet_item_owners o where o.item_id = i.id), '[]'::jsonb))
  from public.pet_items i join public.pet_catalog c on c.id = i.item
  where i.code = upper(btrim(p_code)) and i.sig is not null;
$$;
revoke all on function public.pet_verify(text) from public;
grant execute on function public.pet_verify(text) to anon, authenticated;

-- 3. Cadeaux d'événement -----------------------------------------------------------------------------------------------
create table if not exists private.pet_drop_bounds (
  id integer primary key default 1 check (id = 1),
  organizers boolean not null default true,              -- les organisateurs peuvent-ils préparer des cadeaux ?
  max_pct jsonb not null default '{"common": 100, "rare": 50, "epic": 20, "legendary": 10, "mythic": 0}',
  max_prizes integer not null default 5 check (max_prizes between 1 and 10),
  max_copies integer not null default 10 check (max_copies between 1 and 200),
  updated_at timestamptz not null default now(),
  updated_by uuid
);
insert into private.pet_drop_bounds (id) values (1) on conflict (id) do nothing;
revoke all on private.pet_drop_bounds from public, anon, authenticated;

create table if not exists public.pet_event_drops (
  event_id uuid primary key references public.events(id) on delete cascade,
  prizes jsonb not null default '[]' check (jsonb_typeof(prizes) = 'array'),
  status text not null default 'draft' check (status in ('draft', 'published', 'drawn')),
  seed text,
  seed_hash text,
  published_at timestamptz,
  published_by uuid references public.profiles(id) on delete set null,
  drawn_at timestamptz,
  eligible_count integer,
  updated_by uuid references public.profiles(id) on delete set null,
  updated_at timestamptz not null default now()
);
alter table public.pet_event_drops enable row level security;
revoke all on public.pet_event_drops from anon, authenticated;

create table if not exists public.pet_event_awards (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  prize integer not null check (prize between 0 and 9),
  item text not null references public.pet_catalog(id),
  roll numeric not null,
  instance_id uuid references public.pet_items(id) on delete set null,
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  unique (event_id, user_id, prize)
);
create index if not exists pet_event_awards_user on public.pet_event_awards (user_id) where claimed_at is null;
alter table public.pet_event_awards enable row level security;
revoke all on public.pet_event_awards from anon, authenticated;

-- Qui prépare : un admin, ou un organisateur de l'événement (si l'admin le permet, dans ses bornes).
create or replace function private.pet_drop_role(e uuid) returns text
language sql stable security definer set search_path = '' as $$
  select case when public.is_admin() then 'admin'
              when public.is_organizer(e) and (select organizers from private.pet_drop_bounds where id = 1) then 'organizer'
         end;
$$;

-- Les présents : billet scanné ou arrivée notée à la main, OU noté « Présent » par l'organisateur / un admin.
-- Jamais un paiement (event_tickets.paid n'est pas lu). Comptes actifs seulement.
create or replace function private.pet_drop_eligible(e uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select x.user_id from (
    select t.user_id from public.event_tickets t where t.event_id = e and t.checked_in_at is not null
    union
    select r.user_id from public.rsvps r
     where r.event_id = e and r.status = 'yes' and not r.waitlisted and r.set_by is not null and r.set_by <> r.user_id
  ) x join public.profiles p on p.id = x.user_id and p.status = 'active';
$$;

create or replace function private.pet_drop_draw_at(e uuid) returns timestamptz
language sql stable security definer set search_path = '' as $$
  select coalesce(ends_at, starts_at + interval '6 hours') from public.events where id = e;
$$;

-- Jet d'un présent pour un lot (0 ≤ jet < 100) : HMAC-SHA256(graine, « événement|compte|lot »), 52 premiers bits.
-- Même calcul en Python (app/pet_events.py roll) : chacun peut refaire le sien une fois la graine révélée.
create or replace function private.pet_drop_roll(seed text, e uuid, who uuid, prize integer) returns numeric
language sql immutable security definer set search_path = '' as $$
  select round((('x' || lpad(substr(encode(extensions.hmac(e::text || '|' || who::text || '|' || prize::text, seed, 'sha256'),
               'hex'), 1, 13), 16, '0'))::bit(64)::bigint)::numeric / 4503599627370496 * 100, 6);
$$;

create or replace function private.pet_drop_view(d public.pet_event_drops, editor boolean) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('status', d.status, 'seed_hash', d.seed_hash,
    'seed', case when d.status = 'drawn' then d.seed end, 'published_at', d.published_at, 'drawn_at', d.drawn_at,
    'eligible_count', d.eligible_count, 'draw_at', private.pet_drop_draw_at(d.event_id),
    'prizes', coalesce((select jsonb_agg(jsonb_build_object('item', case when c.rarity = 'mythic' and not editor then null else c.id end,
                 'label', case when c.rarity = 'mythic' and not editor then 'Objet mystère (Mythique numéroté)' else c.label end,
                 'rarity', c.rarity, 'pct', (p ->> 'pct')::numeric, 'copies', (p ->> 'copies')::integer,
                 'given', (select count(*) from public.pet_event_awards a where a.event_id = d.event_id and a.prize = (o - 1)))
               order by o)
             from jsonb_array_elements(d.prizes) with ordinality as x(p, o)
             join public.pet_catalog c on c.id = p ->> 'item'), '[]'::jsonb));
$$;
revoke all on function private.pet_drop_role(uuid), private.pet_drop_eligible(uuid), private.pet_drop_draw_at(uuid),
  private.pet_drop_roll(text, uuid, uuid, integer), private.pet_drop_view(public.pet_event_drops, boolean)
  from public, anon, authenticated;

-- Fiche « Cadeaux de l'événement » : règlement et chances (tous ceux qui voient l'événement), édition (admin /
-- organisateur dans ses bornes), mes gains.
create or replace function public.pet_event_drop_get(p_event uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare role text := private.pet_drop_role(p_event); d public.pet_event_drops; b private.pet_drop_bounds; ev public.events;
begin
  if auth.uid() is null or not public.can_see_event(p_event) then
    raise exception 'forbidden: Événement introuvable.' using errcode = '42501';
  end if;
  select * into ev from public.events where id = p_event;
  select * into d from public.pet_event_drops where event_id = p_event;
  select * into b from private.pet_drop_bounds where id = 1;
  return jsonb_build_object(
    'event', jsonb_build_object('id', ev.id, 'title', ev.title, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at,
                                'status', ev.status, 'started', coalesce(ev.starts_at <= now(), false)),
    'role', role,
    'drop', case when d.event_id is null then null
                 when d.status = 'draft' and role is null then null
                 else private.pet_drop_view(d, role is not null) end,
    'eligible_now', case when role is not null then (select count(*) from private.pet_drop_eligible(p_event)) end,
    'bounds', case when role is not null then jsonb_build_object('organizers', b.organizers, 'max_pct', b.max_pct,
                    'max_prizes', b.max_prizes, 'max_copies', b.max_copies) end,
    'catalog', case when role is not null then coalesce((select jsonb_agg(jsonb_build_object('id', c.id, 'label', c.label,
                    'rarity', c.rarity, 'series', c.series, 'slot', c.slot, 'edition', c.edition,
                    'left', case when c.edition is not null then c.edition - (select count(*) from public.pet_items i where i.item = c.id) end)
                    order by array_position(array['common', 'rare', 'epic', 'legendary', 'mythic'], c.rarity), c.series, c.label)
                  from public.pet_catalog c
                  where role = 'admin' or coalesce((b.max_pct ->> c.rarity)::numeric, 0) > 0), '[]'::jsonb) end,
    'mine', coalesce((select jsonb_agg(jsonb_build_object('item', a.item, 'label', c.label, 'rarity', c.rarity,
                       'roll', a.roll, 'prize', a.prize) order by a.prize)
                      from public.pet_event_awards a join public.pet_catalog c on c.id = a.item
                     where a.event_id = p_event and a.user_id = auth.uid()), '[]'::jsonb));
end $$;

create or replace function private.pet_drop_check(p_event uuid, p_prizes jsonb, role text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare b private.pet_drop_bounds; p jsonb; c public.pet_catalog; pct numeric; copies integer; out jsonb := '[]';
  seen text[] := '{}'; most integer;
begin
  select * into b from private.pet_drop_bounds where id = 1;
  most := case when role = 'admin' then 10 else b.max_prizes end;
  if jsonb_typeof(p_prizes) is distinct from 'array' or jsonb_array_length(p_prizes) = 0 then
    raise exception 'invalid: Choisis au moins un objet à gagner.';
  end if;
  if jsonb_array_length(p_prizes) > most then
    raise exception 'invalid: Trop d''objets : % au plus.', most;
  end if;
  for p in select * from jsonb_array_elements(p_prizes) loop
    select * into c from public.pet_catalog where id = p ->> 'item';
    if c.id is null then raise exception 'invalid: Objet inconnu.'; end if;
    if c.id = any(seen) then raise exception 'invalid: « % » est déjà dans la liste.', c.label; end if;
    seen := seen || c.id;
    begin
      pct := round((p ->> 'pct')::numeric, 1);
      copies := nullif(p ->> 'copies', '')::integer;
    exception when others then
      raise exception 'invalid: Chance ou nombre d''exemplaires illisible.';
    end;
    if pct is null or pct < 0.1 or pct > 100 then raise exception 'invalid: Une chance va de 0,1 %% à 100 %%.'; end if;
    if copies is not null and (copies < 1 or copies > 200) then raise exception 'invalid: De 1 à 200 exemplaires.'; end if;
    if role <> 'admin' then
      if pct > coalesce((b.max_pct ->> c.rarity)::numeric, 0) then
        raise exception 'invalid: « % » : % %% au plus pour un organisateur (borne de l''admin).', c.label,
          coalesce((b.max_pct ->> c.rarity)::numeric, 0);
      end if;
      if c.rarity in ('legendary', 'mythic') and (copies is null or copies > b.max_copies) then
        raise exception 'invalid: « % » : % exemplaires au plus pour un organisateur.', c.label, b.max_copies;
      end if;
    end if;
    if c.rarity = 'mythic' then
      if copies is null then raise exception 'invalid: Un Mythique demande un nombre d''exemplaires.'; end if;
      if copies > c.edition - (select count(*) from public.pet_items i where i.item = c.id) then
        raise exception 'invalid: « % » : il ne reste que % exemplaire(s).', c.label,
          c.edition - (select count(*) from public.pet_items i where i.item = c.id);
      end if;
    end if;
    out := out || jsonb_build_array(jsonb_build_object('item', c.id, 'pct', pct, 'copies', copies));
  end loop;
  return out;
end $$;
revoke all on function private.pet_drop_check(uuid, jsonb, text) from public, anon, authenticated;

create or replace function private.pet_drop_editable(p_event uuid) returns text
language plpgsql stable security definer set search_path = '' as $$
declare role text := private.pet_drop_role(p_event); ev public.events;
begin
  if auth.uid() is null or role is null then
    raise exception 'forbidden: Réservé à l''admin et aux organisateurs de l''événement.' using errcode = '42501';
  end if;
  select * into ev from public.events where id = p_event;
  if ev.starts_at is null or ev.starts_at <= now() then
    raise exception 'invalid: Les cadeaux se préparent avant le début de l''événement (date fixe).';
  end if;
  if exists (select 1 from public.pet_event_drops where event_id = p_event and status <> 'draft') then
    raise exception 'frozen: Les chances sont publiées : elles ne changent plus.';
  end if;
  return role;
end $$;
revoke all on function private.pet_drop_editable(uuid) from public, anon, authenticated;

create or replace function public.pet_event_drop_save(p_event uuid, p_prizes jsonb) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare role text := private.pet_drop_editable(p_event); clean jsonb;
begin
  perform pg_advisory_xact_lock(hashtextextended('pet_drop:' || p_event::text, 0));
  clean := private.pet_drop_check(p_event, p_prizes, role);
  insert into public.pet_event_drops (event_id, prizes, updated_by) values (p_event, clean, auth.uid())
  on conflict (event_id) do update set prizes = excluded.prizes, updated_by = excluded.updated_by, updated_at = now()
    where public.pet_event_drops.status = 'draft';
  perform private.audit('pet.drop_save', null, jsonb_build_object('event', p_event, 'prizes', clean));
  return public.pet_event_drop_get(p_event);
end $$;

create or replace function public.pet_event_drop_delete(p_event uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  perform private.pet_drop_editable(p_event);
  delete from public.pet_event_drops where event_id = p_event and status = 'draft';
  return public.pet_event_drop_get(p_event);
end $$;

-- Publier : chances et exemplaires FIGÉS ; graine tirée maintenant, seule son empreinte est montrée avant le tirage.
create or replace function public.pet_event_drop_publish(p_event uuid) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare role text := private.pet_drop_editable(p_event); d public.pet_event_drops; s text;
begin
  perform pg_advisory_xact_lock(hashtextextended('pet_drop:' || p_event::text, 0));
  select * into d from public.pet_event_drops where event_id = p_event for update;
  if d.event_id is null then raise exception 'invalid: Prépare d''abord les objets à gagner.'; end if;
  if not exists (select 1 from public.events where id = p_event and status = 'published') then
    raise exception 'invalid: L''événement doit être publié.';
  end if;
  perform private.pet_drop_check(p_event, d.prizes, role);   -- toujours dans les bornes (et exemplaires restants)
  s := encode(extensions.gen_random_bytes(32), 'hex');
  update public.pet_event_drops set status = 'published', seed = s,
    seed_hash = encode(extensions.digest(s, 'sha256'), 'hex'), published_at = now(), published_by = auth.uid()
  where event_id = p_event;
  perform private.audit('pet.drop_publish', null, jsonb_build_object('event', p_event, 'prizes', d.prizes));
  return public.pet_event_drop_get(p_event);
end $$;

-- Tirage (interne) : tous les présents, dans un ordre tiré de la graine ; un jet par lot ; exemplaires limités.
create or replace function private.pet_event_draw(p_event uuid) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare d public.pet_event_drops; who uuid; p jsonb; i integer; roll numeric; c public.pet_catalog; given integer[];
  inst jsonb; n integer := 0; total integer := 0;
begin
  perform pg_advisory_xact_lock(hashtextextended('pet_drop:' || p_event::text, 0));
  select * into d from public.pet_event_drops where event_id = p_event for update;
  if d.status is distinct from 'published' or private.pet_drop_draw_at(p_event) > now()
     or not exists (select 1 from public.events where id = p_event and status = 'published') then
    return 0;
  end if;
  given := array_fill(0, array[jsonb_array_length(d.prizes)]);
  for who in select u from private.pet_drop_eligible(p_event) u
              order by encode(extensions.hmac(u::text, d.seed, 'sha256'), 'hex') loop
    total := total + 1;
    for i in 0 .. jsonb_array_length(d.prizes) - 1 loop
      p := d.prizes -> i;
      select * into c from public.pet_catalog where id = p ->> 'item';
      roll := private.pet_drop_roll(d.seed, p_event, who, i);
      continue when roll >= (p ->> 'pct')::numeric;
      continue when (p ->> 'copies') is not null and given[i + 1] >= (p ->> 'copies')::integer;
      continue when c.edition is not null and (select count(*) from public.pet_items x where x.item = c.id) >= c.edition;
      inst := null;
      if c.rarity in ('legendary', 'mythic') then
        inst := private.pet_mint_for(who, c.id, 'event', 'event:' || p_event || ':' || i, p_event);
      end if;
      insert into public.pet_event_awards (event_id, user_id, prize, item, roll, instance_id)
      values (p_event, who, i, c.id, roll, (inst ->> 'id')::uuid) on conflict do nothing;
      given[i + 1] := given[i + 1] + 1;
      n := n + 1;
    end loop;
  end loop;
  update public.pet_event_drops set status = 'drawn', drawn_at = now(), eligible_count = total where event_id = p_event;
  return n;
end $$;
revoke all on function private.pet_event_draw(uuid) from public, anon, authenticated;

create or replace function private.pet_event_draw_due(only_for uuid default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare e uuid; n integer := 0;
begin
  for e in select d.event_id from public.pet_event_drops d
            where d.status = 'published' and private.pet_drop_draw_at(d.event_id) <= now()
              and (only_for is null or only_for in (select private.pet_drop_eligible(d.event_id))) loop
    n := n + private.pet_event_draw(e);
  end loop;
  return n;
end $$;
revoke all on function private.pet_event_draw_due(uuid) from public, anon, authenticated;

do $$
begin
  perform cron.unschedule('pet-event-draw') where exists (select 1 from cron.job where jobname = 'pet-event-draw');
  perform cron.schedule('pet-event-draw', '*/10 * * * *', 'select private.pet_event_draw_due();');
end $$;

-- Bornes des organisateurs (admin).
create or replace function public.pet_drop_bounds_set(p_organizers boolean, p_max_pct jsonb, p_max_prizes integer,
                                                      p_max_copies integer) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare k text;
begin
  if not public.is_admin() then raise exception 'forbidden: Réservé aux admins.' using errcode = '42501'; end if;
  if jsonb_typeof(p_max_pct) is distinct from 'object' then raise exception 'invalid: Bornes illisibles.'; end if;
  foreach k in array array['common', 'rare', 'epic', 'legendary', 'mythic'] loop
    if (p_max_pct ->> k) is null or (p_max_pct ->> k)::numeric not between 0 and 100 then
      raise exception 'invalid: Une borne va de 0 à 100 %%.';
    end if;
  end loop;
  update private.pet_drop_bounds set organizers = coalesce(p_organizers, organizers),
    max_pct = jsonb_build_object('common', (p_max_pct ->> 'common')::numeric, 'rare', (p_max_pct ->> 'rare')::numeric,
      'epic', (p_max_pct ->> 'epic')::numeric, 'legendary', (p_max_pct ->> 'legendary')::numeric,
      'mythic', (p_max_pct ->> 'mythic')::numeric),
    max_prizes = coalesce(p_max_prizes, max_prizes), max_copies = coalesce(p_max_copies, max_copies),
    updated_at = now(), updated_by = auth.uid()
  where id = 1;
  perform private.audit('pet.drop_bounds', null, p_max_pct);
  return (select to_jsonb(b) - 'id' - 'updated_by' from private.pet_drop_bounds b where id = 1);
end $$;

revoke all on function public.pet_event_drop_get(uuid), public.pet_event_drop_save(uuid, jsonb),
  public.pet_event_drop_delete(uuid), public.pet_event_drop_publish(uuid),
  public.pet_drop_bounds_set(boolean, jsonb, integer, integer) from public, anon;
grant execute on function public.pet_event_drop_get(uuid), public.pet_event_drop_save(uuid, jsonb),
  public.pet_event_drop_delete(uuid), public.pet_event_drop_publish(uuid),
  public.pet_drop_bounds_set(boolean, jsonb, integer, integer) to authenticated;

-- Cadeaux rangés par le serveur dans la collection (après l'enregistrement du personnage).
create or replace function public.pet_awards_claim(p_ids uuid[], p_key text default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := private.pet_server_guard(p_key); n integer;
begin
  update public.pet_event_awards set claimed_at = now()
   where user_id = me and claimed_at is null and id = any(coalesce(p_ids, '{}'));
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.pet_awards_claim(uuid[], text) from public, anon;
grant execute on function public.pet_awards_claim(uuid[], text) to authenticated;

-- Chargement : comme 20261104170000, plus mes exemplaires, les Mythiques encore disponibles et mes cadeaux
-- d'événement pas encore rangés (le tirage d'un événement fini où je suis présent est fait ici si besoin).
create or replace function public.pet_load(p_src text default null, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  today date := (now() at time zone 'Europe/Zurich')::date;
begin
  if p_src in ('tab', 'notification', 'widget', 'link') then
    insert into public.pet_opens as o (user_id, day, src) values (me, today, jsonb_build_object(p_src, 1))
    on conflict (user_id, day) do update
      set n = o.n + 1, last_at = now(),
          src = o.src || jsonb_build_object(p_src, coalesce((o.src ->> p_src)::integer, 0) + 1);
    perform private.pet_event_draw_due(me);
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
                           and e.starts_at between now() - interval '7 days' and now()), '[]'::jsonb),
    'items', coalesce((select jsonb_agg(private.pet_item_json(i) order by i.minted_at)
                         from public.pet_items i where i.owner_id = me), '[]'::jsonb),
    'mythic_left', coalesce((select jsonb_object_agg(c.id, c.edition - (select count(*) from public.pet_items i where i.item = c.id))
                               from public.pet_catalog c where c.rarity = 'mythic'), '{}'::jsonb),
    'awards', coalesce((select jsonb_agg(jsonb_build_object('id', a.id, 'event_id', a.event_id, 'event', e.title,
                                'item', a.item, 'prize', a.prize, 'roll', a.roll, 'instance', a.instance_id) order by a.created_at)
                          from public.pet_event_awards a join public.events e on e.id = a.event_id
                         where a.user_id = me and a.claimed_at is null), '[]'::jsonb));
end;
$$;
revoke all on function public.pet_load(text, text) from public, anon;
grant execute on function public.pet_load(text, text) to authenticated;

-- 4. Modération ---------------------------------------------------------------------------------------------------------
-- Ami du Compagnon : comme 20261104170000, sans les personnes bloquées (dans un sens ou l'autre).
create or replace function private.pet_friends_of(me uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select distinct o.user_id
    from public.member_group_members m
    join public.member_group_members o on o.group_id = m.group_id and o.user_id <> me
    join public.profiles p on p.id = o.user_id and p.status = 'active'
   where m.user_id = me
     and (m.added_by is null or m.added_by = m.user_id or m.added_at <= now() - interval '3 days')
     and (o.added_by is null or o.added_by = o.user_id or o.added_at <= now() - interval '3 days')
     and not private.blocked_either(me, o.user_id);
$$;
revoke all on function private.pet_friends_of(uuid) from public, anon, authenticated;

-- Nom du Zicou et titre de la vitrine : même filtre que les surnoms (refus), CGU si l'admin les exige.
create or replace function private.moderate_pet() returns trigger
language plpgsql security definer set search_path = '' as $$
declare title text := new.life -> 'showcase' ->> 'title'; old_title text; old_name text := 'Zicou';
begin
  if tg_op = 'UPDATE' then
    old_title := old.life -> 'showcase' ->> 'title';
    old_name := old.name;
  end if;
  if new.name is distinct from old_name then
    perform private.require_terms(new.user_id);
    perform private.moderate_text(new.name, 'name');
  end if;
  if coalesce(title, '') <> '' and title is distinct from old_title then
    perform private.require_terms(new.user_id);
    perform private.moderate_text(title, 'showcase');
  end if;
  return new;
end $$;
revoke all on function private.moderate_pet() from public, anon, authenticated;
drop trigger if exists pets_moderate on public.pets;
create trigger pets_moderate before insert or update of name, life on public.pets
  for each row execute function private.moderate_pet();

-- Signaler : nom du Zicou ou vitrine d'un ami (id = son compte). Copie du contenu au moment du signalement.
create or replace function private.report_snapshot_pet(p_kind text, p_id text, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare uid uuid; l jsonb;
begin
  if p_kind not in ('pet_name', 'pet_showcase') then return null; end if;
  begin uid := p_id::uuid; exception when others then return null; end;
  if uid is distinct from viewer and not exists (select 1 from private.pet_friends_of(viewer) f where f = uid) then
    return null;
  end if;
  select life into l from public.pets where user_id = uid;
  if l is null then return null; end if;
  if p_kind = 'pet_name' then
    return jsonb_build_object('owner', uid, 'text', l ->> 'name', 'place', 'Zicou · nom', 'at', now());
  end if;
  if coalesce(l -> 'showcase' ->> 'title', '') = '' then return null; end if;
  return jsonb_build_object('owner', uid, 'text', l -> 'showcase' ->> 'title', 'place', 'Zicou · vitrine', 'at', now());
end $$;

-- Masquer (modérateur) : le nom redevient « Zicou », la vitrine perd son titre. Version +1 (le serveur relit).
create or replace function private.moderation_hide_pet(p_kind text, p_id text) returns void
language plpgsql security definer set search_path = '' as $$
declare uid uuid;
begin
  begin uid := p_id::uuid; exception when others then return; end;
  if p_kind = 'pet_name' then
    update public.pets set life = jsonb_set(life, '{name}', '"Zicou"'), name = 'Zicou', version = version + 1,
      updated_at = now() where user_id = uid;
  elsif p_kind = 'pet_showcase' then
    update public.pets set life = jsonb_set(life, '{showcase,title}', '""'), version = version + 1, updated_at = now()
     where user_id = uid and life ? 'showcase';
  end if;
end $$;
revoke all on function private.report_snapshot_pet(text, text, uuid), private.moderation_hide_pet(text, text)
  from public, anon, authenticated;

-- 5. Garde-fous de pet_save : comme 20261104170000, plus la poussière et la collection.
create or replace function private.pet_state_problem(p_life jsonb, p_owner jsonb, cur public.pets) returns text
language plpgsql stable security definer set search_path = '' as $$
declare
  k text;
  v numeric;
  coins numeric;
  before_coins numeric := 0;
  dust numeric;
  before_dust numeric := 0;
  items integer;
  before_items integer := 0;
  age_days integer := 1;
begin
  foreach k in array array['food', 'joy', 'energy', 'care'] loop
    v := (p_life -> 'g' ->> k)::numeric;
    if v is null or v < 0 or v > 100 then
      return 'jauge ' || k;
    end if;
  end loop;
  coins := coalesce((p_owner -> 'loop' ->> 'coins')::numeric, 0);
  dust := coalesce((p_owner -> 'coll' ->> 'dust')::numeric, 0);
  items := (select count(*) from jsonb_object_keys(coalesce(p_owner -> 'coll' -> 'inv', '{}'::jsonb)));
  if cur.user_id is not null then
    before_coins := coalesce((cur.owner -> 'loop' ->> 'coins')::numeric, 0);
    before_dust := coalesce((cur.owner -> 'coll' ->> 'dust')::numeric, 0);
    before_items := (select count(*) from jsonb_object_keys(coalesce(cur.owner -> 'coll' -> 'inv', '{}'::jsonb)));
    age_days := ((now() at time zone 'Europe/Zurich')::date - (cur.created_at at time zone 'Europe/Zurich')::date) + 1;
  end if;
  if coins < 0 or coins > before_coins + 1500 then
    return 'pièces';
  end if;
  if dust < 0 or dust > before_dust + 2500 then
    return 'poussière';
  end if;
  if items > before_items + 20 then   -- conversion des tenues d'avant, un coffre, un achat, des cadeaux d'événement
    return 'collection';
  end if;
  if coalesce((p_owner -> 'streak' ->> 'count')::numeric, 0) > age_days
     or coalesce((p_owner -> 'streak' ->> 'best')::numeric, 0) > age_days then
    return 'série';
  end if;
  if coalesce((p_owner -> 'stats' ->> 'stars')::numeric, 0) > (p_life ->> 'gen')::numeric then
    return 'étoiles';
  end if;
  return null;
exception when others then
  return 'illisible';
end;
$$;
revoke all on function private.pet_state_problem(jsonb, jsonb, public.pets) from public, anon, authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261104210000', 'compagnon_collection') on conflict do nothing;

-- ══ Réactions de Zicou (20261104230000) : migration devenue NEUTRE (décision de l'admin du 4.11.2026 : répondre à un
-- événement ne rapporte plus rien) ; seule sa version est notée, pour garder le même historique. ══
insert into supabase_migrations.schema_migrations (version, name) values ('20261104230000', 'compagnon_reactions') on conflict do nothing;

-- ══ Zicou sur la fiche profil (20261104240000) : public.pet_profile, lue par le serveur Party seulement ══
-- Zicou sur la fiche profil (avis de l'admin, 4 novembre 2026) : « depuis n'importe où, si on clique sur le profil d'une
-- personne, on doit voir son Zicou » ; sans Zicou, un œuf terne qui donne envie d'en avoir un.
-- Purement additif et rejouable. Prérequis : 20261104210000 (Compagnon, collection : pet_friends_of sans les bloqués)
-- et 20261104200000 (blocage commun : private.blocked_either).
--
-- public.pet_profile(p_member, p_key) : lue SEULEMENT par le serveur Party (clé du serveur, comme pet_load), qui n'en
-- renvoie que l'apparence publique (app/pet_profile.py : stade, humeur, tenue, shiny, génération, âge ; jamais jauges,
-- pièces ni inventaire). Visible par tout membre actif qui peut ouvrir la fiche (public.member_card), sauf blocage dans
-- un sens ou l'autre : null (le serveur répond 404, sans dire pourquoi). Jamais owner ; le titre de vitrine (texte
-- d'un joueur) est retiré. « friend » : visite possible (même règle que pet_friend) ; « mine » : le lecteur a un Zicou.

create or replace function public.pet_profile(p_member uuid, p_key text default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  l jsonb;
begin
  if p_member is null or private.blocked_either(me, p_member)
     or not exists (select 1 from public.profiles where id = p_member and status = 'active') then
    return null;
  end if;
  select p.life into l from public.pets p where p.user_id = p_member and p.stage <> 'dead';
  if l ? 'showcase' and jsonb_typeof(l -> 'showcase') = 'object' then
    l := jsonb_set(l, '{showcase,title}', '""');
  end if;
  return jsonb_build_object(
    'life', l,
    'me', p_member = me,
    'friend', p_member <> me and l is not null
              and exists (select 1 from private.pet_friends_of(me) f where f = p_member),
    'mine', exists (select 1 from public.pets p where p.user_id = me and p.stage <> 'dead'));
end;
$$;
revoke all on function public.pet_profile(uuid, text) from public, anon;
grant execute on function public.pet_profile(uuid, text) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261104240000', 'zicou_fiche') on conflict do nothing;
-- ══ Pièces Zicou d'un événement (20261105090000) : droit zicou.event_coins, réglage, versement aux présents, ══
-- ══ pet_load sans « events » ni « answers », plus « coins » ══
-- Zicou, pièces d'un événement (décision de l'admin du 4 novembre 2026). Purement additif et rejouable.
-- Prérequis : 20261104210000 (collection : cadeaux d'événement, présents) et 20261103140000 (rôles et droits).
--
-- Être présent à une soirée ou à un événement ne rapporte PLUS rien automatiquement, répondre à un événement non plus
-- (la migration 20261104230000 est devenue neutre ; app/pet.py n'a plus les sources « soiree » ni « rsvp »).
-- À la place, un droit « zicou.event_coins » (« Donner des pièces Zicou pour un événement »), donné au départ aux rôles
-- Admin et Co-admin : sur la page « Cadeaux Zicou » de l'événement, on active « Pièces pour les présents » avec un
-- montant borné (5 à 100). La base les verse UNE fois à chaque PRÉSENT (même définition que les cadeaux d'événement :
-- private.pet_drop_eligible, jamais selon un paiement) à la fin de l'événement (private.pet_drop_draw_at), avec un
-- journal (public.pet_event_coin_grants, une ligne par personne, unique). Le serveur Party les range dans le Zicou à
-- la prochaine ouverture (pet_load « coins »), puis les marque (pet_event_coins_claim) : jamais versées deux fois.
-- Sans le droit : rien n'est visible (pet_event_coins_get ne renvoie que ses propres pièces reçues).
--
-- 1. Droit ; 2. réglage et journal ; 3. réglage (lire, fixer) ; 4. versement ; 5. pet_load (sans « events » ni
-- « answers », plus « coins ») et marque.

-- 1. Droit ----------------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('zicou.event_coins', 'Zicou', 'Donner des pièces Zicou pour un événement',
   'Sur la page des cadeaux Zicou d''un événement : des pièces (5 à 100) pour chaque présent, versées une fois à la fin', 80)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'zicou_event_coins_2026_11_05') then
    return;
  end if;
  insert into public.role_permissions (role, perm)
    select r.key, 'zicou.event_coins' from public.roles r where r.key in ('admin', 'coadmin')
  on conflict do nothing;
  insert into private.one_time_changes (name) values ('zicou_event_coins_2026_11_05');
end $$;

-- 2. Réglage et journal ---------------------------------------------------------------------------------------------
create table if not exists public.pet_event_coins (
  event_id uuid primary key references public.events(id) on delete cascade,
  coins integer not null check (coins between 5 and 100),
  set_by uuid references public.profiles(id) on delete set null,
  set_at timestamptz not null default now()
);
alter table public.pet_event_coins enable row level security;
revoke all on public.pet_event_coins from anon, authenticated;

create table if not exists public.pet_event_coin_grants (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  coins integer not null check (coins between 5 and 100),
  created_at timestamptz not null default now(),
  claimed_at timestamptz,
  unique (event_id, user_id)
);
create index if not exists pet_event_coin_grants_user on public.pet_event_coin_grants (user_id) where claimed_at is null;
alter table public.pet_event_coin_grants enable row level security;
revoke all on public.pet_event_coin_grants from anon, authenticated;

-- Après la fin de l'événement, les présents notés plus tard reçoivent encore leurs pièces pendant 7 jours.
create or replace function private.pet_event_coins_open_until(e uuid) returns timestamptz
language sql stable security definer set search_path = '' as $$
  select private.pet_drop_draw_at(e) + interval '7 days';
$$;
revoke all on function private.pet_event_coins_open_until(uuid) from public, anon, authenticated;

-- 3. Réglage ---------------------------------------------------------------------------------------------------------
create or replace function public.pet_event_coins_get(p_event uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare allowed boolean := public.has_perm('zicou.event_coins'); c public.pet_event_coins;
begin
  if auth.uid() is null or not public.can_see_event(p_event) then
    raise exception 'forbidden: Événement introuvable.' using errcode = '42501';
  end if;
  select * into c from public.pet_event_coins where event_id = p_event;
  return jsonb_build_object(
    'allowed', allowed,
    'mine', (select g.coins from public.pet_event_coin_grants g where g.event_id = p_event and g.user_id = auth.uid()),
    'setting', case when allowed then jsonb_build_object(
        'coins', c.coins, 'set_at', c.set_at, 'min', 5, 'max', 100,
        'pay_at', private.pet_drop_draw_at(p_event),
        'open_until', private.pet_event_coins_open_until(p_event),
        'late', now() > private.pet_event_coins_open_until(p_event),
        'given', (select count(*) from public.pet_event_coin_grants g where g.event_id = p_event),
        'eligible_now', (select count(*) from private.pet_drop_eligible(p_event))) end);
end $$;

-- 4. Versement (interne) : chaque présent pas encore servi, une fois ; journal = pet_event_coin_grants.
create or replace function private.pet_event_coins_grant(p_event uuid) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare c public.pet_event_coins; n integer;
begin
  perform pg_advisory_xact_lock(hashtextextended('pet_coins:' || p_event::text, 0));
  select * into c from public.pet_event_coins where event_id = p_event;
  if c.event_id is null or private.pet_drop_draw_at(p_event) > now()
     or now() > private.pet_event_coins_open_until(p_event)
     or not exists (select 1 from public.events where id = p_event and status = 'published') then
    return 0;
  end if;
  insert into public.pet_event_coin_grants (event_id, user_id, coins)
    select p_event, u, c.coins from private.pet_drop_eligible(p_event) u
  on conflict (event_id, user_id) do nothing;
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function private.pet_event_coins_grant(uuid) from public, anon, authenticated;

-- Fixer le montant (p_coins entre 5 et 100) ou l'enlever (null). Refusé dès qu'une pièce a été versée (plus rien ne
-- change : chacun reçoit le même montant) et après la fenêtre de 7 jours. Versé tout de suite si l'événement est fini.
create or replace function public.pet_event_coins_set(p_event uuid, p_coins integer) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
begin
  if auth.uid() is null or not public.has_perm('zicou.event_coins') then
    raise exception 'forbidden: Réservé aux personnes qui ont le droit « Donner des pièces Zicou pour un événement ».'
      using errcode = '42501';
  end if;
  if not exists (select 1 from public.events where id = p_event) or not public.can_see_event(p_event) then
    raise exception 'forbidden: Événement introuvable.' using errcode = '42501';
  end if;
  if p_coins is not null and (p_coins < 5 or p_coins > 100) then
    raise exception 'invalid: De 5 à 100 pièces par présent.';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('pet_coins:' || p_event::text, 0));
  if exists (select 1 from public.pet_event_coin_grants where event_id = p_event) then
    raise exception 'frozen: Les pièces sont déjà versées : le montant ne change plus.';
  end if;
  if now() > private.pet_event_coins_open_until(p_event) then
    raise exception 'invalid: Trop tard : l''événement est fini depuis plus de 7 jours.';
  end if;
  if p_coins is null then
    delete from public.pet_event_coins where event_id = p_event;
  else
    insert into public.pet_event_coins (event_id, coins, set_by) values (p_event, p_coins, auth.uid())
    on conflict (event_id) do update set coins = excluded.coins, set_by = excluded.set_by, set_at = now();
  end if;
  perform private.audit('pet.event_coins', null, jsonb_build_object('event', p_event, 'coins', p_coins));
  perform private.pet_event_coins_grant(p_event);
  return public.pet_event_coins_get(p_event);
end $$;

revoke all on function public.pet_event_coins_get(uuid), public.pet_event_coins_set(uuid, integer) from public, anon;
grant execute on function public.pet_event_coins_get(uuid), public.pet_event_coins_set(uuid, integer) to authenticated;

-- Événements à servir (cron toutes les 10 min, et à l'ouverture de Zicou pour ses propres événements).
create or replace function private.pet_event_coins_due(only_for uuid default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare e uuid; n integer := 0;
begin
  for e in select c.event_id from public.pet_event_coins c
            where private.pet_drop_draw_at(c.event_id) <= now() and now() <= private.pet_event_coins_open_until(c.event_id)
              and (only_for is null or only_for in (select private.pet_drop_eligible(c.event_id)))
              and (only_for is null or not exists (select 1 from public.pet_event_coin_grants g
                                                    where g.event_id = c.event_id and g.user_id = only_for)) loop
    n := n + private.pet_event_coins_grant(e);
  end loop;
  return n;
end $$;
revoke all on function private.pet_event_coins_due(uuid) from public, anon, authenticated;

-- Comme 20261104210000, plus le versement des pièces d'événement (même cron « pet-event-draw », même pet_load).
create or replace function private.pet_event_draw_due(only_for uuid default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare e uuid; n integer := 0;
begin
  for e in select d.event_id from public.pet_event_drops d
            where d.status = 'published' and private.pet_drop_draw_at(d.event_id) <= now()
              and (only_for is null or only_for in (select private.pet_drop_eligible(d.event_id))) loop
    n := n + private.pet_event_draw(e);
  end loop;
  return n + private.pet_event_coins_due(only_for);
end $$;
revoke all on function private.pet_event_draw_due(uuid) from public, anon, authenticated;

-- 5. Pièces rangées par le serveur dans le Zicou (après l'enregistrement du personnage).
create or replace function public.pet_event_coins_claim(p_ids uuid[], p_key text default null) returns integer
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := private.pet_server_guard(p_key); n integer;
begin
  update public.pet_event_coin_grants set claimed_at = now()
   where user_id = me and claimed_at is null and id = any(coalesce(p_ids, '{}'));
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.pet_event_coins_claim(uuid[], text) from public, anon;
grant execute on function public.pet_event_coins_claim(uuid[], text) to authenticated;

-- Chargement : comme 20261104210000, sans « events » (présence) ni « answers » (réponses) qui ne rapportent plus rien,
-- plus « coins » : mes pièces d'événement pas encore rangées.
create or replace function public.pet_load(p_src text default null, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  today date := (now() at time zone 'Europe/Zurich')::date;
begin
  if p_src in ('tab', 'notification', 'widget', 'link') then
    insert into public.pet_opens as o (user_id, day, src) values (me, today, jsonb_build_object(p_src, 1))
    on conflict (user_id, day) do update
      set n = o.n + 1, last_at = now(),
          src = o.src || jsonb_build_object(p_src, coalesce((o.src ->> p_src)::integer, 0) + 1);
    perform private.pet_event_draw_due(me);
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
    'items', coalesce((select jsonb_agg(private.pet_item_json(i) order by i.minted_at)
                         from public.pet_items i where i.owner_id = me), '[]'::jsonb),
    'mythic_left', coalesce((select jsonb_object_agg(c.id, c.edition - (select count(*) from public.pet_items i where i.item = c.id))
                               from public.pet_catalog c where c.rarity = 'mythic'), '{}'::jsonb),
    'awards', coalesce((select jsonb_agg(jsonb_build_object('id', a.id, 'event_id', a.event_id, 'event', e.title,
                                'item', a.item, 'prize', a.prize, 'roll', a.roll, 'instance', a.instance_id) order by a.created_at)
                          from public.pet_event_awards a join public.events e on e.id = a.event_id
                         where a.user_id = me and a.claimed_at is null), '[]'::jsonb),
    'coins', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'event_id', g.event_id, 'event', e.title,
                                'coins', g.coins) order by g.created_at)
                         from public.pet_event_coin_grants g join public.events e on e.id = g.event_id
                        where g.user_id = me and g.claimed_at is null), '[]'::jsonb));
end;
$$;
revoke all on function public.pet_load(text, text) from public, anon;
grant execute on function public.pet_load(text, text) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261105090000', 'zicou_event_coins') on conflict do nothing;

-- ══ 20261105120000_zicou_economie ══
-- Zicou, nouvelle économie EN BÊTA (décision de l'admin du 4 novembre 2026 ; chiffres : scratchpad economie/rapport.md,
-- usages : economie/usages-pieces.md). Purement additif et rejouable. Prérequis : 20261104210000 (collection),
-- 20261104170000 (garde-fous, cadeaux), 20261105090000 (pièces d'un événement).
-- Zicou reste ÉTEINT hors site de test (compagnon_enabled) ; jamais appliquée en production avant que l'admin dise
-- « le projet Compagnon est complet » (fichier prod : supabase/prod/2026-11-04-personnage-apply.sql, partie 20261105120000).
--
-- 1. Catalogue recopié (app/pet_catalog.json, version 2) : les Mythiques des coffres passent de 25 à 8 exemplaires —
--    SEULEMENT si aucun exemplaire n'a déjà un numéro plus grand (jamais un objet existant cassé ; aucun n'était frappé).
-- 2. Cadeaux d'événement réservés aux admins et co-admins (organizers = false), bornes d'un organisateur abaissées
--    (si l'admin les rouvre un jour) : Commun 25 %, Rare 8 %, Épique 3 %, Légendaire 1 %, lots de la série Soirées
--    Party seulement. Une seule fois (l'admin peut ensuite changer les bornes avec pet_drop_bounds_set).
-- 3. Festins offerts : pet_gifts accepte « feast_pizza » et « feast_fondue » (payés en pièces par celui qui offre,
--    côté serveur Party ; l'ami reçoit un EFFET, jamais des pièces). Mêmes limites : un cadeau par ami et par jour,
--    3 reçus par jour au plus.
-- 4. Caisse commune du groupe : objectifs (5 000 pièces chacun), versements des membres (10 à 250, 500 par jour au
--    plus, référence unique : jamais compté deux fois), SANS classement (on montre le total, le nombre de donateurs et
--    les prénoms des amis qui ont donné, jamais les montants des autres). Le versement passe par la clé du serveur
--    Party (il débite les pièces). Compte supprimé : son nom part (user_id → null), le total reste.

-- 1. Catalogue ----------------------------------------------------------------------------------------------------------
insert into public.pet_catalog (id, slot, series, rarity, edition, source, label) values
-- CATALOGUE (généré par app/pet_catalog.py sql_values)
('lunettes', 'eyes', 'disco', 'common', null, 'chest', 'Lunettes de soleil'),
('bandeau-eponge', 'head', 'disco', 'common', null, 'chest', 'Bandeau éponge'),
('baskets-compensees', 'feet', 'disco', 'common', null, 'chest', 'Baskets compensées'),
('facettes-miroir', 'facets', 'disco', 'common', null, 'chest', 'Facettes miroir'),
('boa', 'neck', 'disco', 'rare', null, 'chest', 'Collier lumineux'),
('micro-chrome', 'hand', 'disco', 'rare', null, 'chest', 'Micro chromé'),
('decor-piste', 'decor', 'disco', 'rare', null, 'chest', 'Piste de danse lumineuse'),
('casque', 'head', 'disco', 'epic', null, 'chest', 'Casque de DJ doré'),
('paillettes', 'neck', 'disco', 'epic', null, 'chest', 'Veste à paillettes'),
('facettes-or', 'facets', 'disco', 'legendary', null, 'chest', '« Saturday Night Zicou » : facettes d''or'),
('m-disco', 'head', 'disco', 'mythic', 8, 'chest', 'Couronne Aurore'),
('bonnet', 'head', 'montagne', 'common', null, 'chest', 'Bonnet à pompon'),
('echarpe', 'neck', 'montagne', 'common', null, 'chest', 'Écharpe douillette'),
('chaussettes-laine', 'feet', 'montagne', 'common', null, 'chest', 'Chaussettes en laine'),
('bouquet-edelweiss', 'hand', 'montagne', 'common', null, 'chest', 'Bouquet d''edelweiss'),
('cloche-vache', 'neck', 'montagne', 'rare', null, 'chest', 'Cloche de vache'),
('sac-rando', 'back', 'montagne', 'rare', null, 'chest', 'Sac à dos de rando'),
('lunettes-glacier', 'eyes', 'montagne', 'rare', null, 'chest', 'Lunettes de glacier'),
('cor-alpes', 'hand', 'montagne', 'epic', null, 'chest', 'Cor des Alpes'),
('decor-chalet', 'decor', 'montagne', 'epic', null, 'chest', 'Chalet sous la neige'),
('marmotte', 'pet', 'montagne', 'legendary', null, 'chest', 'Marmotte des Alpes'),
('m-montagne', 'facets', 'montagne', 'mythic', 8, 'chest', 'Facettes Glacier éternel'),
('casquette', 'head', 'escalade', 'common', null, 'chest', 'Casquette'),
('sac-magnesie', 'back', 'escalade', 'common', null, 'chest', 'Sac à magnésie'),
('chaussons-escalade', 'feet', 'escalade', 'common', null, 'chest', 'Chaussons d''escalade'),
('mousqueton', 'hand', 'escalade', 'common', null, 'chest', 'Mousqueton'),
('baudrier', 'neck', 'escalade', 'rare', null, 'chest', 'Baudrier'),
('casque-grimpe', 'head', 'escalade', 'rare', null, 'chest', 'Casque de grimpe'),
('corde', 'back', 'escalade', 'rare', null, 'chest', 'Corde lovée'),
('nuage-magnesie', 'effect', 'escalade', 'epic', null, 'chest', 'Nuage de magnésie'),
('decor-mur', 'decor', 'escalade', 'epic', null, 'chest', 'Mur d''escalade'),
('piolet-or', 'hand', 'escalade', 'legendary', null, 'chest', 'Piolet d''or'),
('m-escalade', 'effect', 'escalade', 'mythic', 8, 'chest', 'Aura du sommet'),
('chapeau-sorciere', 'head', 'halloween', 'common', null, 'chest', 'Chapeau de sorcière'),
('loup-bal', 'eyes', 'halloween', 'common', null, 'chest', 'Loup de bal masqué'),
('bottes-citrouille', 'feet', 'halloween', 'common', null, 'chest', 'Bottes citrouille'),
('lanterne-citrouille', 'hand', 'halloween', 'common', null, 'chest', 'Lanterne citrouille'),
('cape', 'back', 'halloween', 'rare', null, 'chest', 'Cape de héros'),
('aureole', 'head', 'halloween', 'rare', null, 'chest', 'Auréole'),
('chauve-souris', 'pet', 'halloween', 'rare', null, 'chest', 'Chauve-souris'),
('brume', 'effect', 'halloween', 'epic', null, 'chest', 'Brume ensorcelée'),
('decor-manoir', 'decor', 'halloween', 'epic', null, 'chest', 'Manoir hanté'),
('facettes-squelette', 'facets', 'halloween', 'legendary', null, 'chest', '« Zicou Squelette » : facettes phosphorescentes'),
('m-halloween', 'effect', 'halloween', 'mythic', 8, 'chest', 'Pleine lune'),
('chapeau', 'head', 'nouvelan', 'common', null, 'chest', 'Chapeau de fête'),
('lunettes-2027', 'eyes', 'nouvelan', 'common', null, 'chest', 'Lunettes « 2027 »'),
('langue-belle-mere', 'hand', 'nouvelan', 'common', null, 'chest', 'Langue de belle-mère'),
('noeud-or', 'neck', 'nouvelan', 'common', null, 'chest', 'Nœud doré'),
('confettis', 'effect', 'nouvelan', 'rare', null, 'chest', 'Pluie de confettis'),
('escarpins-paillettes', 'feet', 'nouvelan', 'rare', null, 'chest', 'Souliers à paillettes'),
('decor-minuit', 'decor', 'nouvelan', 'rare', null, 'chest', 'Minuit sur la ville'),
('comete', 'effect', 'nouvelan', 'epic', null, 'chest', 'Comète'),
('horloge-minuit', 'hand', 'nouvelan', 'epic', null, 'chest', 'Horloge de minuit'),
('feu-artifice', 'effect', 'nouvelan', 'legendary', null, 'chest', 'Feu d''artifice'),
('m-nouvelan', 'pet', 'nouvelan', 'mythic', 8, 'chest', 'Phénix de minuit'),
('noeud', 'neck', 'soirees', 'common', null, 'event', 'Nœud papillon'),
('bracelet-entree', 'hand', 'soirees', 'common', null, 'event', 'Bracelet d''entrée'),
('baskets-led', 'feet', 'soirees', 'common', null, 'event', 'Baskets LED'),
('lunettes-coeur', 'eyes', 'soirees', 'common', null, 'event', 'Lunettes cœur'),
('ailes', 'back', 'soirees', 'rare', null, 'event', 'Ailes de fée'),
('baton-lumineux', 'hand', 'soirees', 'rare', null, 'event', 'Bâton lumineux'),
('decor-salon', 'decor', 'soirees', 'rare', null, 'event', 'Le salon de Party'),
('couronne', 'head', 'soirees', 'epic', null, 'event', 'Couronne'),
('lumi', 'pet', 'soirees', 'epic', null, 'event', 'Lumi la luciole'),
('projecteurs', 'effect', 'soirees', 'legendary', null, 'event', '« Hôte de la soirée » : projecteurs'),
('m-soirees', 'head', 'soirees', 'mythic', 10, 'event', 'Boule de Party')
on conflict (id) do update set slot = excluded.slot, series = excluded.series, rarity = excluded.rarity,
  source = excluded.source, label = excluded.label,
  -- moins d'exemplaires (25 → 8) seulement si aucun numéro déjà frappé ne dépasse le nouveau tirage ; jamais agrandi
  edition = case
    when excluded.edition is not null and excluded.edition < public.pet_catalog.edition
         and not exists (select 1 from public.pet_items i where i.item = public.pet_catalog.id and i.serial > excluded.edition)
      then excluded.edition
    else coalesce(public.pet_catalog.edition, excluded.edition) end;

-- 2. Cadeaux d'événement : admins et co-admins seulement --------------------------------------------------------------
do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'zicou_economie_2026_11_05') then
    return;
  end if;
  update private.pet_drop_bounds
     set organizers = false,
         max_pct = '{"common": 25, "rare": 8, "epic": 3, "legendary": 1, "mythic": 0}'::jsonb,
         updated_at = now()
   where id = 1;
  insert into private.one_time_changes (name) values ('zicou_economie_2026_11_05');
end $$;

-- Un organisateur (si l'admin rouvre ce droit) ne met en jeu que des objets de la série Soirées Party.
create or replace function private.pet_drop_check(p_event uuid, p_prizes jsonb, role text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare b private.pet_drop_bounds; p jsonb; c public.pet_catalog; pct numeric; copies integer; out jsonb := '[]';
  seen text[] := '{}'; most integer;
begin
  select * into b from private.pet_drop_bounds where id = 1;
  most := case when role = 'admin' then 10 else b.max_prizes end;
  if jsonb_typeof(p_prizes) is distinct from 'array' or jsonb_array_length(p_prizes) = 0 then
    raise exception 'invalid: Choisis au moins un objet à gagner.';
  end if;
  if jsonb_array_length(p_prizes) > most then
    raise exception 'invalid: Trop d''objets : % au plus.', most;
  end if;
  for p in select * from jsonb_array_elements(p_prizes) loop
    select * into c from public.pet_catalog where id = p ->> 'item';
    if c.id is null then raise exception 'invalid: Objet inconnu.'; end if;
    if c.id = any(seen) then raise exception 'invalid: « % » est déjà dans la liste.', c.label; end if;
    seen := seen || c.id;
    begin
      pct := round((p ->> 'pct')::numeric, 1);
      copies := nullif(p ->> 'copies', '')::integer;
    exception when others then
      raise exception 'invalid: Chance ou nombre d''exemplaires illisible.';
    end;
    if pct is null or pct < 0.1 or pct > 100 then raise exception 'invalid: Une chance va de 0,1 %% à 100 %%.'; end if;
    if copies is not null and (copies < 1 or copies > 200) then raise exception 'invalid: De 1 à 200 exemplaires.'; end if;
    if role <> 'admin' then
      if c.series <> 'soirees' then
        raise exception 'invalid: « % » : un organisateur ne met en jeu que des objets de la série Soirées Party.', c.label;
      end if;
      if pct > coalesce((b.max_pct ->> c.rarity)::numeric, 0) then
        raise exception 'invalid: « % » : % %% au plus pour un organisateur (borne de l''admin).', c.label,
          coalesce((b.max_pct ->> c.rarity)::numeric, 0);
      end if;
      if c.rarity in ('legendary', 'mythic') and (copies is null or copies > b.max_copies) then
        raise exception 'invalid: « % » : % exemplaires au plus pour un organisateur.', c.label, b.max_copies;
      end if;
    end if;
    if c.rarity = 'mythic' then
      if copies is null then raise exception 'invalid: Un Mythique demande un nombre d''exemplaires.'; end if;
      if copies > c.edition - (select count(*) from public.pet_items i where i.item = c.id) then
        raise exception 'invalid: « % » : il ne reste que % exemplaire(s).', c.label,
          c.edition - (select count(*) from public.pet_items i where i.item = c.id);
      end if;
    end if;
    out := out || jsonb_build_array(jsonb_build_object('item', c.id, 'pct', pct, 'copies', copies));
  end loop;
  return out;
end $$;
revoke all on function private.pet_drop_check(uuid, jsonb, text) from public, anon, authenticated;

-- 3. Festins offerts ----------------------------------------------------------------------------------------------------
alter table public.pet_gifts drop constraint if exists pet_gifts_kind_check;
alter table public.pet_gifts add constraint pet_gifts_kind_check
  check (kind in ('hug', 'snack', 'feast_pizza', 'feast_fondue'));

create or replace function public.pet_gift(p_friend uuid, p_kind text, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  today date := (now() at time zone 'Europe/Zurich')::date;
begin
  if p_kind is null or p_kind not in ('hug', 'snack', 'feast_pizza', 'feast_fondue') then
    raise exception 'invalid: Cadeau inconnu.';
  end if;
  if p_friend is null or not exists (select 1 from private.pet_friends_of(me) f where f = p_friend) then
    raise exception 'forbidden: Tu ne peux rendre visite qu''aux membres de tes groupes.';
  end if;
  if not exists (select 1 from public.pets where user_id = p_friend and stage in ('baby', 'teen', 'adult')) then
    raise exception 'invalid: Son Zicou ne peut pas recevoir de cadeau pour l''instant.';
  end if;
  if not exists (select 1 from public.pets where user_id = me and stage in ('baby', 'teen', 'adult')) then
    raise exception 'invalid: Les cadeaux s''offrent de Zicou à Zicou : il faut que le tien soit là 🥚';
  end if;
  if exists (select 1 from public.profiles where id = me and created_at > now() - interval '3 days') then
    raise exception 'invalid: Les cadeaux s''offrent après tes 3 premiers jours sur Party 💜';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('pet_gift_to:' || p_friend::text, 0));
  if exists (select 1 from public.pet_gifts where from_user = me and to_user = p_friend and day = today) then
    raise exception 'limit: Tu lui as déjà fait un cadeau aujourd''hui. Reviens demain 💜';
  end if;
  if (select count(*) from public.pet_gifts where to_user = p_friend and day = today) >= 3 then
    raise exception 'limit: Son Zicou a déjà reçu plein de cadeaux aujourd''hui. Reviens demain 💜';
  end if;
  insert into public.pet_gifts (from_user, to_user, kind, day) values (me, p_friend, p_kind, today)
  on conflict on constraint pet_gifts_one_a_day do nothing;
  if not found then
    raise exception 'limit: Tu lui as déjà fait un cadeau aujourd''hui. Reviens demain 💜';
  end if;
  insert into public.pet_journal (user_id, kind, detail) values (me, 'gift_given', jsonb_build_object('kind', p_kind));
  return jsonb_build_object('ok', true);
end;
$$;
revoke all on function public.pet_gift(uuid, text, text) from public, anon;
grant execute on function public.pet_gift(uuid, text, text) to authenticated;

-- 4. Caisse commune du groupe ------------------------------------------------------------------------------------------
create table if not exists public.pet_pot_goals (
  id text primary key check (id ~ '^[a-z0-9-]{1,30}$'),
  label text not null check (char_length(label) between 1 and 80),
  emoji text not null check (char_length(emoji) between 1 and 16),
  target integer not null check (target between 100 and 100000),
  sort integer not null default 0
);
alter table public.pet_pot_goals enable row level security;
revoke all on public.pet_pot_goals from anon, authenticated;
insert into public.pet_pot_goals (id, label, emoji, target, sort) values
  ('boule-disco', 'Boule disco géante au Salon de Party', '🪩', 5000, 1),
  ('neons', 'Néons arc-en-ciel au Salon de Party', '🌈', 5000, 2),
  ('feu-artifice', 'Feu d''artifice à l''Apple TV', '🎆', 5000, 3)
on conflict (id) do update set label = excluded.label, emoji = excluded.emoji, target = excluded.target, sort = excluded.sort;

create table if not exists public.pet_pot_gifts (
  id uuid primary key default gen_random_uuid(),
  ref text not null unique check (ref ~ '^[a-z0-9-]{8,64}$'),
  goal text not null references public.pet_pot_goals(id),
  user_id uuid references public.profiles(id) on delete set null,
  coins integer not null check (coins between 1 and 500),
  day date not null default (now() at time zone 'Europe/Zurich')::date,
  created_at timestamptz not null default now()
);
create index if not exists pet_pot_gifts_goal on public.pet_pot_gifts (goal);
create index if not exists pet_pot_gifts_user_day on public.pet_pot_gifts (user_id, day);
alter table public.pet_pot_gifts enable row level security;
revoke all on public.pet_pot_gifts from anon, authenticated;

-- Totaux (sans nom) : pour l'Apple TV et le serveur Party, sans compte.
create or replace function public.pet_pot_public() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', g.id, 'label', g.label, 'emoji', g.emoji, 'target', g.target,
           'total', coalesce((select sum(x.coins) from public.pet_pot_gifts x where x.goal = g.id), 0)) order by g.sort, g.id),
         '[]'::jsonb)
    from public.pet_pot_goals g;
$$;
revoke all on function public.pet_pot_public() from public;
grant execute on function public.pet_pot_public() to anon, authenticated;

-- Pour le membre (via le serveur Party) : totaux, nombre de donateurs, prénoms des AMIS qui ont donné (ordre
-- alphabétique, sans montant), ce qu'il a lui-même versé (total et aujourd'hui). Jamais de classement.
create or replace function private.pet_pot_state(me uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'goals', public.pet_pot_public(),
    'donors', (select count(distinct x.user_id) from public.pet_pot_gifts x where x.user_id is not null),
    'friends', coalesce((select jsonb_agg(n order by n) from (
        select distinct coalesce(p.display_name, '') n from public.pet_pot_gifts x
          join public.profiles p on p.id = x.user_id
         where x.user_id in (select f from private.pet_friends_of(me) f) and coalesce(p.display_name, '') <> '') d), '[]'::jsonb),
    'mine', coalesce((select sum(x.coins) from public.pet_pot_gifts x where x.user_id = me), 0),
    'mine_today', coalesce((select sum(x.coins) from public.pet_pot_gifts x
                             where x.user_id = me and x.day = (now() at time zone 'Europe/Zurich')::date), 0));
$$;
revoke all on function private.pet_pot_state(uuid) from public, anon, authenticated;

create or replace function public.pet_pot_get(p_key text default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := private.pet_server_guard(p_key);
begin
  return private.pet_pot_state(me);
end;
$$;
revoke all on function public.pet_pot_get(text) from public, anon;
grant execute on function public.pet_pot_get(text) to authenticated;

-- Versement : pièces DÉJÀ débitées par le serveur Party (seul à détenir la clé). Référence unique : un même versement
-- rejoué ne compte qu'une fois. 10 à 250 par versement, 500 par jour et par personne, objectif pas encore atteint.
create or replace function public.pet_pot_give(p_goal text, p_coins integer, p_ref text, p_key text default null) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  today date := (now() at time zone 'Europe/Zurich')::date;
  g public.pet_pot_goals;
  total integer;
begin
  if exists (select 1 from public.pet_pot_gifts where ref = p_ref and user_id = me) then
    return private.pet_pot_state(me);   -- déjà compté (rejeu)
  end if;
  if p_coins is null or p_coins < 10 or p_coins > 250 then
    raise exception 'invalid: De 10 à 250 pièces par versement.';
  end if;
  if not exists (select 1 from public.pets where user_id = me) then
    raise exception 'invalid: Il faut un Zicou pour participer à la caisse commune 🥚';
  end if;
  select * into g from public.pet_pot_goals where id = p_goal;
  if g.id is null then raise exception 'invalid: Objectif inconnu.'; end if;
  perform pg_advisory_xact_lock(hashtextextended('pet_pot:' || g.id, 0));
  total := coalesce((select sum(coins) from public.pet_pot_gifts where goal = g.id), 0);
  if total >= g.target then
    raise exception 'invalid: Cet objectif est déjà atteint 🎉';
  end if;
  if coalesce((select sum(coins) from public.pet_pot_gifts where user_id = me and day = today), 0) + p_coins > 500 then
    raise exception 'limit: 500 pièces par jour au plus dans la caisse commune. Merci pour ta générosité 💜';
  end if;
  insert into public.pet_pot_gifts (ref, goal, user_id, coins, day) values (p_ref, g.id, me, p_coins, today)
  on conflict (ref) do nothing;
  insert into public.pet_journal (user_id, kind, detail) values (me, 'pot_give', jsonb_build_object('goal', g.id, 'coins', p_coins));
  return private.pet_pot_state(me);
end;
$$;
revoke all on function public.pet_pot_give(text, integer, text, text) from public, anon;
grant execute on function public.pet_pot_give(text, integer, text, text) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261105120000', 'zicou_economie') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
