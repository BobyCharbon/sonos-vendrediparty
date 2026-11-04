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

notify pgrst, 'reload schema';
