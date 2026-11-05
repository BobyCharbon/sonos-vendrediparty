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

notify pgrst, 'reload schema';
