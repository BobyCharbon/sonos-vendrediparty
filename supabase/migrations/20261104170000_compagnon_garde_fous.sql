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

notify pgrst, 'reload schema';
