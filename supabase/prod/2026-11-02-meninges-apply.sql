-- PROD, Méninges (20261102210000 + analyse 20261102220000 + percentile par jeu 20261102240000 + sans fin 20261103090000 + garde-fous 20261103100000 + performance 20261103101000 + niveaux 20261103150000). À appliquer SEULEMENT après « Ok prod ». Rejouable.
-- Entraînement cérébral solo : catalogue brain_games, parties brain_sessions, fonctions brain_record / brain_my_stats / brain_compare.
begin;
-- Méninges (entraînement cérébral solo) : une ligne par partie jouée par un compte Party.
-- Lecture : chacun ses propres parties (RLS). Écriture : uniquement par public.brain_record (security definer), qui
-- vérifie le compte actif, le jeu, la durée et borne le score. Statistiques : brain_my_stats, brain_compare.
-- Catalogue (public.brain_games) : MÊMES valeurs que CATALOG dans app/brain.py (tests/test_brain.py le vérifie).
-- Migration additive et rejouable.

create table if not exists public.brain_games (
  id text primary key check (id ~ '^[a-z_]{2,20}$'),
  domain text not null check (domain in ('vitesse', 'memoire', 'attention', 'flexibilite', 'logique', 'calcul')),
  median integer not null check (median > 0),
  spread integer not null check (spread > 0),
  max_score integer not null check (max_score > 0),
  max_seconds integer not null check (max_seconds > 0)
);

insert into public.brain_games (id, domain, median, spread, max_score, max_seconds) values
  ('pareil', 'vitesse', 9000, 4050, 70000, 75),
  ('motif', 'vitesse', 8500, 3825, 70000, 75),
  ('autoroute', 'attention', 9000, 4050, 92500, 90),
  ('grille', 'memoire', 6000, 2700, 250000, 1800),
  ('deux_avant', 'memoire', 8000, 3600, 70000, 75),
  ('tresor', 'memoire', 5000, 2250, 250000, 1800),
  ('nuee', 'attention', 8500, 3825, 70000, 75),
  ('aiguillage', 'attention', 9000, 4050, 182500, 150),
  ('intrus', 'attention', 8000, 3600, 70000, 75),
  ('encre', 'flexibilite', 9000, 4050, 70000, 75),
  ('bascule', 'flexibilite', 8500, 3825, 70000, 75),
  ('courant', 'flexibilite', 8000, 3600, 70000, 75),
  ('balance', 'calcul', 8500, 3825, 70000, 75),
  ('gouttes', 'calcul', 6000, 2700, 250000, 1800),
  ('syllabes', 'logique', 9000, 4050, 92500, 90)
on conflict (id) do update set domain = excluded.domain, median = excluded.median, spread = excluded.spread,
  max_score = excluded.max_score, max_seconds = excluded.max_seconds;

alter table public.brain_games enable row level security;
drop policy if exists "méninges : catalogue" on public.brain_games;
create policy "méninges : catalogue" on public.brain_games for select to authenticated using (true);
revoke insert, update, delete on public.brain_games from anon, authenticated;

create table if not exists public.brain_sessions (
  id bigint generated always as identity primary key,
  user_id uuid not null references public.profiles(id) on delete cascade,
  game text not null references public.brain_games(id),
  domain text not null,
  score integer not null check (score >= 0),
  idx integer not null check (idx between 0 and 2000),
  accuracy real check (accuracy between 0 and 1),
  avg_rt_ms integer check (avg_rt_ms between 0 and 20000),
  level smallint not null default 1 check (level between 1 and 99),
  duration_ms integer not null check (duration_ms between 0 and 3600000),
  played_at timestamptz not null default now()
);
create index if not exists brain_sessions_user_domain on public.brain_sessions(user_id, domain, played_at desc);
create index if not exists brain_sessions_user_game on public.brain_sessions(user_id, game, played_at desc);

alter table public.brain_sessions enable row level security;
drop policy if exists "méninges : ses parties" on public.brain_sessions;
create policy "méninges : ses parties" on public.brain_sessions for select to authenticated using (user_id = auth.uid());
revoke insert, update, delete on public.brain_sessions from anon, authenticated;

-- Score brut → indice 0–2000 (courbe en S, 1000 = score typique). Même formule que app/brain.py:raw_index.
create or replace function private.brain_index(p_game text, p_score integer) returns integer
language sql stable security definer set search_path = '' as $$
  select floor(2000.0 / (1 + exp(-((least(greatest(p_score, 0), g.max_score) - g.median)::double precision / g.spread))) + 0.5)::integer
  from public.brain_games g where g.id = p_game;
$$;

-- Indices d'un compte : jeu = moyenne des 5 meilleurs indices des 30 jours avant sa dernière partie de ce jeu ;
-- domaine = moyenne de ses jeux ; Température = moyenne des 5 domaines joués (Calcul à part).
create or replace function private.brain_profile(uid uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  with s as (
    select game, domain, idx, played_at, max(played_at) over (partition by game) as last
    from public.brain_sessions where user_id = uid
  ), w as (
    select game, domain, idx, row_number() over (partition by game order by idx desc) as r
    from s where played_at > last - interval '30 days'
  ), g as (
    select game, domain, avg(idx)::double precision as gi from w where r <= 5 group by game, domain
  ), d as (
    select domain, avg(gi) as di from g group by domain
  )
  select jsonb_build_object(
    'temperature', coalesce((select floor(avg(di) + 0.5)::integer from d where domain <> 'calcul'), 0),
    'domains', coalesce((select jsonb_object_agg(domain, floor(di + 0.5)::integer) from d), '{}'::jsonb),
    'games', coalesce((select jsonb_object_agg(game, floor(gi + 0.5)::integer) from g), '{}'::jsonb));
$$;

-- Température de chaque compte actif qui a joué.
create or replace function private.brain_players() returns table (user_id uuid, temperature integer)
language sql stable security definer set search_path = '' as $$
  select p.id, (private.brain_profile(p.id) ->> 'temperature')::integer
  from public.profiles p
  where p.status = 'active' and exists (select 1 from public.brain_sessions b where b.user_id = p.id);
$$;

-- Percentile (0–100) d'une Température parmi les joueurs ; null si pas joué ou seul joueur.
create or replace function private.brain_percentile(mine integer) returns integer
language sql stable security definer set search_path = '' as $$
  select case when mine is not null and count(*) >= 2
    then floor(100.0 * count(*) filter (where temperature < mine) / (count(*) - 1) + 0.5)::integer end
  from private.brain_players();
$$;

create or replace function public.brain_record(p_game text, p_score integer, p_accuracy real, p_avg_rt_ms integer,
                                               p_level integer, p_duration_ms integer) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  g public.brain_games;
  s integer;
  prev integer;
  n integer;
  new_idx integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select * into g from public.brain_games where id = p_game;
  if not found then
    raise exception 'invalid: Jeu inconnu.';
  end if;
  if p_duration_ms is null or p_duration_ms < 1000 or p_duration_ms > g.max_seconds * 1000 then
    raise exception 'invalid: Durée de partie invalide.';
  end if;
  if p_accuracy is not null and (p_accuracy < 0 or p_accuracy > 1) then
    raise exception 'invalid: Précision invalide.';
  end if;
  if (select count(*) from public.brain_sessions where user_id = me and played_at > now() - interval '1 day') >= 300 then
    raise exception 'limit: Assez de parties pour aujourd''hui. Reviens demain !';
  end if;
  s := least(greatest(coalesce(p_score, 0), 0), g.max_score);
  select max(score), count(*) into prev, n from public.brain_sessions where user_id = me and game = g.id;
  new_idx := private.brain_index(g.id, s);
  insert into public.brain_sessions (user_id, game, domain, score, idx, accuracy, avg_rt_ms, level, duration_ms)
  values (me, g.id, g.domain, s, new_idx, p_accuracy, least(greatest(coalesce(p_avg_rt_ms, 0), 0), 20000),
          least(greatest(coalesce(p_level, 1), 1), 99), p_duration_ms);
  return jsonb_build_object('index', new_idx, 'best', greatest(coalesce(prev, 0), s), 'previous_best', prev,
                            'record', prev is null or s > prev, 'plays', n + 1);
end;
$$;

-- Mes parties (400 derniers jours, 2000 au plus) et mon percentile parmi les joueurs Party actifs.
create or replace function public.brain_my_stats() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  mine integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select temperature into mine from private.brain_players() where user_id = me;
  return jsonb_build_object(
    'sessions', coalesce((select jsonb_agg(jsonb_build_object('game', game, 'score', score, 'accuracy', accuracy,
        'avg_rt_ms', avg_rt_ms, 'level', level, 'duration_ms', duration_ms, 'played_at', played_at) order by played_at)
      from (select * from public.brain_sessions where user_id = me and played_at > now() - interval '400 days'
            order by played_at desc limit 2000) x), '[]'::jsonb),
    'percentile', private.brain_percentile(mine),
    'players', (select count(*) from private.brain_players()));
end;
$$;

-- Classement entre amis (comptes actifs qui ont joué) et, si p_target est donné, le profil de ce membre à comparer.
create or replace function public.brain_compare(p_target uuid default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  board jsonb;
  mine integer;
  target jsonb;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object('id', x.user_id, 'name', coalesce(p.display_name, '?'),
           'temperature', x.temperature, 'me', x.user_id = me) order by x.temperature desc, p.display_name), '[]'::jsonb)
    into board
    from private.brain_players() x join public.profiles p on p.id = x.user_id;
  select (e ->> 'temperature')::integer into mine from jsonb_array_elements(board) e where (e ->> 'me')::boolean;
  if p_target is not null and private.is_account_active(p_target) then
    select private.brain_profile(p_target) || jsonb_build_object('id', p.id, 'name', coalesce(p.display_name, '?'))
      into target from public.profiles p where p.id = p_target;
  end if;
  return jsonb_build_object(
    'board', coalesce((select jsonb_agg(e order by n) from jsonb_array_elements(board) with ordinality t(e, n) where n <= 50), '[]'::jsonb),
    'rank', case when mine is not null then
      (select count(*) + 1 from jsonb_array_elements(board) e where (e ->> 'temperature')::integer > mine) end,
    'players', jsonb_array_length(board),
    'percentile', private.brain_percentile(mine),
    'target', target);
end;
$$;

revoke all on function private.brain_index(text, integer), private.brain_profile(uuid), private.brain_players(),
  private.brain_percentile(integer) from public, anon, authenticated;
revoke all on function public.brain_record(text, integer, real, integer, integer, integer), public.brain_my_stats(),
  public.brain_compare(uuid) from public, anon;
grant execute on function public.brain_record(text, integer, real, integer, integer, integer), public.brain_my_stats(),
  public.brain_compare(uuid) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261102210000', 'brain')
  on conflict (version) do nothing;

-- ── Méninges, analyse (20261102220000) : moyenne des autres joueurs par domaine dans brain_my_stats ──
-- Méninges, analyse : brain_my_stats renvoie en plus la moyenne des AUTRES joueurs Party par domaine (« party »),
-- pour comparer chaque domaine du joueur à celle des autres (app/brain_analysis.py, avec au moins 3 joueurs).
-- Un domaine ne compte pour un joueur qu'à partir de 3 parties dans ce domaine (pas de moyenne faussée par un essai).
-- Seuls des indices agrégés sortent de la base : jamais les parties ni le nom des autres joueurs.
-- Migration additive et rejouable (create or replace).

create or replace function private.brain_party_domains(p_except uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  with players as (
    select p.id, private.brain_profile(p.id) -> 'domains' as domains
    from public.profiles p
    where p.status = 'active' and p.id is distinct from p_except
      and exists (select 1 from public.brain_sessions b where b.user_id = p.id)
  ), enough as (
    select user_id, domain from public.brain_sessions group by user_id, domain having count(*) >= 3
  ), per_domain as (
    select e.key as domain, floor(avg(e.value::integer) + 0.5)::integer as avg_idx, count(*)::integer as players
    from players x cross join lateral jsonb_each_text(x.domains) e
    join enough n on n.user_id = x.id and n.domain = e.key
    group by e.key
  )
  select jsonb_build_object('domains', coalesce(
    (select jsonb_object_agg(domain, jsonb_build_object('avg', avg_idx, 'players', players)) from per_domain),
    '{}'::jsonb));
$$;

-- Mes parties (400 derniers jours, 2000 au plus), mon percentile parmi les joueurs Party actifs et la moyenne des autres
-- joueurs par domaine (même contenu qu'avant, plus 'party').
create or replace function public.brain_my_stats() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  mine integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select temperature into mine from private.brain_players() where user_id = me;
  return jsonb_build_object(
    'sessions', coalesce((select jsonb_agg(jsonb_build_object('game', game, 'score', score, 'accuracy', accuracy,
        'avg_rt_ms', avg_rt_ms, 'level', level, 'duration_ms', duration_ms, 'played_at', played_at) order by played_at)
      from (select * from public.brain_sessions where user_id = me and played_at > now() - interval '400 days'
            order by played_at desc limit 2000) x), '[]'::jsonb),
    'percentile', private.brain_percentile(mine),
    'players', (select count(*) from private.brain_players()),
    'party', private.brain_party_domains(me));
end;
$$;

revoke all on function private.brain_party_domains(uuid) from public, anon, authenticated;
revoke all on function public.brain_my_stats() from public, anon;
grant execute on function public.brain_my_stats() to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261102220000', 'brain_analyse')
  on conflict (version) do nothing;

-- ── Méninges, percentile par jeu (20261102240000) ──
-- Méninges : percentile d'un jeu (fiche du jeu, écran de fin). Mon indice du jeu comparé à celui des autres comptes
-- actifs qui ont joué à ce jeu (même calcul d'indice que private.brain_profile). Null si je n'y ai pas joué ou si je
-- suis seul. Migration additive et rejouable ; app/brain.py:BrainStore.game s'en passe si elle manque.

create or replace function public.brain_game_percentile(p_game text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  mine integer;
  players integer;
  below integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  if not exists (select 1 from public.brain_games where id = p_game) then
    raise exception 'invalid: Jeu inconnu.';
  end if;
  with x as (
    select p.id as user_id, (private.brain_profile(p.id) -> 'games' ->> p_game)::integer as idx
    from public.profiles p
    where p.status = 'active' and exists (select 1 from public.brain_sessions b where b.user_id = p.id and b.game = p_game)
  )
  select (select idx from x where user_id = me), count(*), count(*) filter (where idx < (select idx from x where user_id = me))
    into mine, players, below
    from x;
  return jsonb_build_object(
    'percentile', case when mine is not null and players >= 2 then floor(100.0 * below / (players - 1) + 0.5)::integer end,
    'players', players);
end;
$$;

revoke all on function public.brain_game_percentile(text) from public, anon;
grant execute on function public.brain_game_percentile(text) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261102240000', 'brain_game')
  on conflict (version) do nothing;

-- ── Méninges sans fin (20261103090000) : catalogue revu, indice score + niveau, durée bornée à 30 min ──
-- Méninges SANS FIN (03.11.2026) : plus de chrono, 3 vies, paliers de 5 niveaux. Les parties durent bien plus
-- longtemps et les scores sont bien plus grands :
--  - catalogue public.brain_games revu (MÊMES valeurs que CATALOG dans app/brain.py, tests/test_brain.py le vérifie) :
--    score typique relevé, spread = largeur de la courbe en millièmes de ln(score), plafond de score très large
--    (borné, jamais refusé), durée comptée jusqu'à 30 min ;
--  - indice 0–2000 qui tient compte du score ET du niveau atteint (private.brain_index à 3 arguments, même formule
--    que app/brain.py:raw_index) ; l'indice des parties déjà jouées est recalculé ;
--  - brain_record : une partie plus longue que 30 min est bornée à 30 min au lieu d'être refusée.
-- Migration additive et rejouable.

insert into public.brain_games (id, domain, median, spread, max_score, max_seconds) values
  ('pareil', 'vitesse', 22500, 800, 2702500, 1800),
  ('motif', 'vitesse', 21000, 800, 2702500, 1800),
  ('autoroute', 'attention', 22500, 800, 2702500, 1800),
  ('grille', 'memoire', 15000, 800, 2702500, 1800),
  ('deux_avant', 'memoire', 20000, 800, 2702500, 1800),
  ('tresor', 'memoire', 12500, 800, 2702500, 1800),
  ('nuee', 'attention', 21000, 800, 2702500, 1800),
  ('aiguillage', 'attention', 22500, 800, 2702500, 1800),
  ('intrus', 'attention', 20000, 800, 2702500, 1800),
  ('encre', 'flexibilite', 22500, 800, 2702500, 1800),
  ('bascule', 'flexibilite', 21000, 800, 2702500, 1800),
  ('courant', 'flexibilite', 20000, 800, 2702500, 1800),
  ('balance', 'calcul', 21000, 800, 2702500, 1800),
  ('gouttes', 'calcul', 15000, 800, 2702500, 1800),
  ('syllabes', 'logique', 22500, 800, 2702500, 1800)
on conflict (id) do update set domain = excluded.domain, median = excluded.median, spread = excluded.spread,
  max_score = excluded.max_score, max_seconds = excluded.max_seconds;

-- Score + niveau → indice 0–2000. Note z = 0,65 × ln((score + 500) / (typique + 500)) / (spread / 1000)
--                                         + 0,35 × (niveau − 10) / 8 ; indice = 2000 / (1 + e^−z), arrondi.
create or replace function private.brain_index(p_game text, p_score integer, p_level integer) returns integer
language sql stable security definer set search_path = '' as $$
  select floor(2000.0::double precision / (1 + exp(-(
      0.65::double precision * (ln((least(greatest(coalesce(p_score, 0), 0), g.max_score) + 500)::double precision
                                    / (g.median + 500)::double precision) / (g.spread::double precision / 1000))
    + 0.35::double precision * ((least(greatest(coalesce(p_level, 1), 1), 99) - 10)::double precision / 8)))) + 0.5)::integer
  from public.brain_games g where g.id = p_game;
$$;

-- Ancienne signature (score seul) : même courbe, au niveau typique (10).
create or replace function private.brain_index(p_game text, p_score integer) returns integer
language sql stable security definer set search_path = '' as $$
  select private.brain_index(p_game, p_score, 10);
$$;

create or replace function public.brain_record(p_game text, p_score integer, p_accuracy real, p_avg_rt_ms integer,
                                               p_level integer, p_duration_ms integer) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  g public.brain_games;
  s integer;
  lvl integer;
  prev integer;
  n integer;
  new_idx integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select * into g from public.brain_games where id = p_game;
  if not found then
    raise exception 'invalid: Jeu inconnu.';
  end if;
  if p_duration_ms is null or p_duration_ms < 1000 then
    raise exception 'invalid: Durée de partie invalide.';
  end if;
  if p_accuracy is not null and (p_accuracy < 0 or p_accuracy > 1) then
    raise exception 'invalid: Précision invalide.';
  end if;
  if (select count(*) from public.brain_sessions where user_id = me and played_at > now() - interval '1 day') >= 300 then
    raise exception 'limit: Assez de parties pour aujourd''hui. Reviens demain !';
  end if;
  s := least(greatest(coalesce(p_score, 0), 0), g.max_score);
  lvl := least(greatest(coalesce(p_level, 1), 1), 99);
  select max(score), count(*) into prev, n from public.brain_sessions where user_id = me and game = g.id;
  new_idx := private.brain_index(g.id, s, lvl);
  insert into public.brain_sessions (user_id, game, domain, score, idx, accuracy, avg_rt_ms, level, duration_ms)
  values (me, g.id, g.domain, s, new_idx, p_accuracy, least(greatest(coalesce(p_avg_rt_ms, 0), 0), 20000),
          lvl, least(p_duration_ms, g.max_seconds * 1000));
  return jsonb_build_object('index', new_idx, 'best', greatest(coalesce(prev, 0), s), 'previous_best', prev,
                            'record', prev is null or s > prev, 'plays', n + 1);
end;
$$;

-- Parties déjà jouées : indice recalculé avec la nouvelle courbe (Température et percentile cohérents avec le serveur).
update public.brain_sessions b set idx = private.brain_index(b.game, b.score, b.level)
  where b.idx is distinct from private.brain_index(b.game, b.score, b.level);

revoke all on function private.brain_index(text, integer, integer), private.brain_index(text, integer)
  from public, anon, authenticated;
revoke all on function public.brain_record(text, integer, real, integer, integer, integer) from public, anon;
grant execute on function public.brain_record(text, integer, real, integer, integer, integer) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103090000', 'brain_sans_fin')
  on conflict (version) do nothing;

-- ── Méninges, garde-fous (20261103100000) : score et niveau bornés par la durée, 60 parties / 10 min, verrou par compte ──
-- Méninges, garde-fous (QA du 03.11.2026) : brain_record borne un résultat IMPOSSIBLE au lieu de l'accepter tel quel.
--  - score borné par la durée de la partie : 3 000 points par seconde au plus (deux fois le rythme d'un robot parfait,
--    3 bonnes réponses/s à ×10 = 1 500 pts/s) + 2 500 de bonus final (×10). 2,7 millions de points en 45 s → 137 500 ;
--  - niveau borné par la durée : au plus 1 niveau par seconde de jeu au-delà du premier niveau du palier de départ
--    le plus haut possible (palier du niveau max déjà enregistré pour ce jeu) ; niveau 99 en 1 s → niveau 2 ;
--  - au plus 60 parties en 10 minutes (envoi groupé des 30 parties jouées hors connexion compris), en plus des 300
--    par jour : « 1 000 parties en une minute » → 60 enregistrées, les autres refusées ;
--  - un verrou par compte (pg_advisory_xact_lock) : des envois simultanés ne dépassent plus ces limites.
-- Même borne de score que app/brain.py:validate (SCORE_PER_SECOND_CAP, SCORE_BONUS_CAP ; tests/test_brain_qa.py).
-- Rien de possible n'est refusé : un robot parfait qui joue 30 min garde le plafond (2 702 500).
-- Index (compte, date) : les deux comptages ci-dessus et brain_my_stats (2 000 dernières parties) ne parcourent plus
-- toutes les parties du compte jeu par jeu.
-- Migration additive et rejouable (create or replace, create index if not exists).

create index if not exists brain_sessions_user_played on public.brain_sessions(user_id, played_at desc);

create or replace function public.brain_record(p_game text, p_score integer, p_accuracy real, p_avg_rt_ms integer,
                                               p_level integer, p_duration_ms integer) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  g public.brain_games;
  s integer;
  lvl integer;
  dur integer;
  prev integer;
  prev_level integer;
  n integer;
  new_idx integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select * into g from public.brain_games where id = p_game;
  if not found then
    raise exception 'invalid: Jeu inconnu.';
  end if;
  if p_duration_ms is null or p_duration_ms < 1000 then
    raise exception 'invalid: Durée de partie invalide.';
  end if;
  if p_accuracy is not null and (p_accuracy < 0 or p_accuracy > 1) then   -- NaN > 1 en SQL : refusé aussi
    raise exception 'invalid: Précision invalide.';
  end if;
  -- Un envoi à la fois par compte : les limites ci-dessous restent exactes avec des envois simultanés.
  perform pg_advisory_xact_lock(hashtextextended('brain_record:' || me::text, 0));
  if (select count(*) from public.brain_sessions where user_id = me and played_at > now() - interval '1 day') >= 300 then
    raise exception 'limit: Assez de parties pour aujourd''hui. Reviens demain !';
  end if;
  if (select count(*) from public.brain_sessions where user_id = me and played_at > now() - interval '10 minutes') >= 60 then
    raise exception 'limit: Beaucoup de parties d''un coup : fais une pause de quelques minutes.';
  end if;
  dur := least(p_duration_ms, g.max_seconds * 1000);
  select max(score), max(level), count(*) into prev, prev_level, n
    from public.brain_sessions where user_id = me and game = g.id;
  -- Score : plafond du jeu, et 3 000 points par seconde de jeu + 2 500 de bonus final.
  s := least(greatest(coalesce(p_score, 0), 0), g.max_score, dur * 3 + 2500);
  -- Niveau : premier niveau du palier le plus haut déjà atteint (départ possible) + 1 niveau par seconde de jeu.
  lvl := least(greatest(coalesce(p_level, 1), 1), 99,
               ((greatest(coalesce(prev_level, 1), 1) - 1) / 5) * 5 + 1 + dur / 1000);
  new_idx := private.brain_index(g.id, s, lvl);
  insert into public.brain_sessions (user_id, game, domain, score, idx, accuracy, avg_rt_ms, level, duration_ms)
  values (me, g.id, g.domain, s, new_idx, p_accuracy, least(greatest(coalesce(p_avg_rt_ms, 0), 0), 20000), lvl, dur);
  return jsonb_build_object('index', new_idx, 'best', greatest(coalesce(prev, 0), s), 'previous_best', prev,
                            'record', prev is null or s > prev, 'plays', n + 1, 'score', s, 'level', lvl);
end;
$$;

revoke all on function public.brain_record(text, integer, real, integer, integer, integer) from public, anon;
grant execute on function public.brain_record(text, integer, real, integer, integer, integer) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103100000', 'brain_anti_triche')
  on conflict (version) do nothing;

-- ── Méninges, performance (20261103101000) : classement, percentile et moyenne Party calculés pour tous en une requête ──
-- Méninges, performance (QA du 03.11.2026) : le classement, le percentile et la moyenne Party recalculaient le profil
-- de CHAQUE joueur un par un (private.brain_profile appelé par joueur, 3 à 4 fois par appel de brain_my_stats).
-- Avec 200 joueurs × 1 500 parties, brain_my_stats prenait ~4 s (limite d'une requête : 8 s). Ici, le même calcul est
-- fait pour tous les joueurs en une seule requête (fenêtres par joueur et par jeu). Résultats IDENTIQUES à
-- private.brain_profile : indice d'un jeu = moyenne des 5 meilleurs idx des 30 jours avant sa dernière partie ;
-- domaine = moyenne de ses jeux ; Température = moyenne des domaines hors Calcul, arrondie (floor(x + 0.5)).
-- brain_my_stats et brain_compare ne lisent plus la liste des joueurs qu'UNE fois (percentile calculé sur cette liste).
-- Mêmes signatures et mêmes résultats (vérifié sur TEST, ancien ↔ nouveau, dans une transaction annulée).
-- Migration additive et rejouable (create or replace).

-- Indice brut (non arrondi) de chaque domaine joué, pour chaque compte actif qui a joué.
create or replace function private.brain_domain_scores() returns table (user_id uuid, domain text, di double precision)
language sql stable security definer set search_path = '' as $$
  with s as (
    select b.user_id, b.game, b.domain, b.idx, b.played_at,
           max(b.played_at) over (partition by b.user_id, b.game) as last
    from public.brain_sessions b join public.profiles p on p.id = b.user_id
    where p.status = 'active'
  ), w as (
    select s.user_id, s.game, s.domain, s.idx,
           row_number() over (partition by s.user_id, s.game order by s.idx desc) as r
    from s where s.played_at > s.last - interval '30 days'
  ), g as (
    select w.user_id, w.game, w.domain, avg(w.idx)::double precision as gi from w where w.r <= 5
    group by w.user_id, w.game, w.domain
  )
  select g.user_id, g.domain, avg(g.gi) from g group by g.user_id, g.domain;
$$;

-- Température de chaque compte actif qui a joué (même résultat que private.brain_profile(id) ->> 'temperature').
create or replace function private.brain_players() returns table (user_id uuid, temperature integer)
language sql stable security definer set search_path = '' as $$
  select d.user_id, coalesce(floor(avg(d.di) filter (where d.domain <> 'calcul') + 0.5)::integer, 0)
  from private.brain_domain_scores() d group by d.user_id;
$$;

-- Moyenne des AUTRES joueurs par domaine (domaine compté à partir de 3 parties), comme avant.
create or replace function private.brain_party_domains(p_except uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  with enough as (
    select b.user_id, b.domain from public.brain_sessions b group by b.user_id, b.domain having count(*) >= 3
  ), per_domain as (
    select d.domain, floor(avg(floor(d.di + 0.5)::integer) + 0.5)::integer as avg_idx, count(*)::integer as players
    from private.brain_domain_scores() d
    join enough n on n.user_id = d.user_id and n.domain = d.domain
    where d.user_id is distinct from p_except
    group by d.domain
  )
  select jsonb_build_object('domains', coalesce(
    (select jsonb_object_agg(domain, jsonb_build_object('avg', avg_idx, 'players', players)) from per_domain),
    '{}'::jsonb));
$$;

-- Percentile d'un jeu : indice du jeu de chaque compte actif qui y a joué, en une requête.
create or replace function public.brain_game_percentile(p_game text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  mine integer;
  players integer;
  below integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  if not exists (select 1 from public.brain_games where id = p_game) then
    raise exception 'invalid: Jeu inconnu.';
  end if;
  with s as (
    select b.user_id, b.idx, b.played_at, max(b.played_at) over (partition by b.user_id) as last
    from public.brain_sessions b join public.profiles p on p.id = b.user_id
    where b.game = p_game and p.status = 'active'
  ), w as (
    select s.user_id, s.idx, row_number() over (partition by s.user_id order by s.idx desc) as r
    from s where s.played_at > s.last - interval '30 days'
  ), x as (
    select w.user_id, floor(avg(w.idx)::double precision + 0.5)::integer as idx from w where w.r <= 5 group by w.user_id
  )
  select (select idx from x where user_id = me), count(*), count(*) filter (where idx < (select idx from x where user_id = me))
    into mine, players, below
    from x;
  return jsonb_build_object(
    'percentile', case when mine is not null and players >= 2 then floor(100.0 * below / (players - 1) + 0.5)::integer end,
    'players', players);
end;
$$;

-- Mes parties (400 derniers jours, 2000 au plus), mon percentile, le nombre de joueurs et la moyenne des autres par
-- domaine : même contenu qu'avant, la liste des joueurs n'est lue qu'une fois.
create or replace function public.brain_my_stats() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  temps integer[];
  mine integer;
  n_players integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select coalesce(array_agg(x.temperature), '{}'), max(x.temperature) filter (where x.user_id = me)
    into temps, mine from private.brain_players() x;
  n_players := cardinality(temps);
  return jsonb_build_object(
    'sessions', coalesce((select jsonb_agg(jsonb_build_object('game', game, 'score', score, 'accuracy', accuracy,
        'avg_rt_ms', avg_rt_ms, 'level', level, 'duration_ms', duration_ms, 'played_at', played_at) order by played_at)
      from (select * from public.brain_sessions where user_id = me and played_at > now() - interval '400 days'
            order by played_at desc limit 2000) x), '[]'::jsonb),
    'percentile', case when mine is not null and n_players >= 2
      then floor(100.0 * (select count(*) from unnest(temps) t where t < mine) / (n_players - 1) + 0.5)::integer end,
    'players', n_players,
    'party', private.brain_party_domains(me));
end;
$$;

-- Classement entre amis et profil d'un membre à comparer : même contenu qu'avant, percentile calculé sur le classement.
create or replace function public.brain_compare(p_target uuid default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  board jsonb;
  mine integer;
  n_players integer;
  target jsonb;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object('id', x.user_id, 'name', coalesce(p.display_name, '?'),
           'temperature', x.temperature, 'me', x.user_id = me) order by x.temperature desc, p.display_name), '[]'::jsonb)
    into board
    from private.brain_players() x join public.profiles p on p.id = x.user_id;
  select (e ->> 'temperature')::integer into mine from jsonb_array_elements(board) e where (e ->> 'me')::boolean;
  n_players := jsonb_array_length(board);
  if p_target is not null and private.is_account_active(p_target) then
    select private.brain_profile(p_target) || jsonb_build_object('id', p.id, 'name', coalesce(p.display_name, '?'))
      into target from public.profiles p where p.id = p_target;
  end if;
  return jsonb_build_object(
    'board', coalesce((select jsonb_agg(e order by n) from jsonb_array_elements(board) with ordinality t(e, n) where n <= 50), '[]'::jsonb),
    'rank', case when mine is not null then
      (select count(*) + 1 from jsonb_array_elements(board) e where (e ->> 'temperature')::integer > mine) end,
    'players', n_players,
    'percentile', case when mine is not null and n_players >= 2 then floor(100.0 *
      (select count(*) from jsonb_array_elements(board) e where (e ->> 'temperature')::integer < mine) / (n_players - 1) + 0.5)::integer end,
    'target', target);
end;
$$;

revoke all on function private.brain_domain_scores(), private.brain_players(), private.brain_party_domains(uuid)
  from public, anon, authenticated;
revoke all on function public.brain_game_percentile(text), public.brain_my_stats(), public.brain_compare(uuid) from public, anon;
grant execute on function public.brain_game_percentile(text), public.brain_my_stats(), public.brain_compare(uuid) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103101000', 'brain_perf')
  on conflict (version) do nothing;

-- ── Méninges, niveaux jusqu'à 999 (20261103150000) ──
-- Méninges, niveaux jusqu'à 999 (03.11.2026) : les jeux sans fin montent à 250+, le plafond de 99 coupait le niveau
-- (colonne brain_sessions.level, brain_record) et la courbe du niveau dans l'indice. Même plafond que app/brain.py
-- (MAX_LEVEL) et le moteur (core.js) ; tests/test_brain_niveaux.py le vérifie. Les parties déjà enregistrées (niveau
-- ≤ 99) gardent leur indice : le nouveau plafond ne change rien en dessous de 99.
-- Migration additive et rejouable (drop constraint if exists puis add, create or replace).

alter table public.brain_sessions drop constraint if exists brain_sessions_level_check;
alter table public.brain_sessions add constraint brain_sessions_level_check check (level between 1 and 999);

-- Score + niveau → indice 0–2000 (même formule que app/brain.py:raw_index), niveau borné à 999.
create or replace function private.brain_index(p_game text, p_score integer, p_level integer) returns integer
language sql stable security definer set search_path = '' as $$
  select floor(2000.0::double precision / (1 + exp(-(
      0.65::double precision * (ln((least(greatest(coalesce(p_score, 0), 0), g.max_score) + 500)::double precision
                                    / (g.median + 500)::double precision) / (g.spread::double precision / 1000))
    + 0.35::double precision * ((least(greatest(coalesce(p_level, 1), 1), 999) - 10)::double precision / 8)))) + 0.5)::integer
  from public.brain_games g where g.id = p_game;
$$;

-- Résultat d'une partie : mêmes garde-fous que 20261103100000_brain_anti_triche, niveau borné à 999.
create or replace function public.brain_record(p_game text, p_score integer, p_accuracy real, p_avg_rt_ms integer,
                                               p_level integer, p_duration_ms integer) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  g public.brain_games;
  s integer;
  lvl integer;
  dur integer;
  prev integer;
  prev_level integer;
  n integer;
  new_idx integer;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'forbidden: Ton compte n''a pas accès à Méninges.';
  end if;
  select * into g from public.brain_games where id = p_game;
  if not found then
    raise exception 'invalid: Jeu inconnu.';
  end if;
  if p_duration_ms is null or p_duration_ms < 1000 then
    raise exception 'invalid: Durée de partie invalide.';
  end if;
  if p_accuracy is not null and (p_accuracy < 0 or p_accuracy > 1) then   -- NaN > 1 en SQL : refusé aussi
    raise exception 'invalid: Précision invalide.';
  end if;
  -- Un envoi à la fois par compte : les limites ci-dessous restent exactes avec des envois simultanés.
  perform pg_advisory_xact_lock(hashtextextended('brain_record:' || me::text, 0));
  if (select count(*) from public.brain_sessions where user_id = me and played_at > now() - interval '1 day') >= 300 then
    raise exception 'limit: Assez de parties pour aujourd''hui. Reviens demain !';
  end if;
  if (select count(*) from public.brain_sessions where user_id = me and played_at > now() - interval '10 minutes') >= 60 then
    raise exception 'limit: Beaucoup de parties d''un coup : fais une pause de quelques minutes.';
  end if;
  dur := least(p_duration_ms, g.max_seconds * 1000);
  select max(score), max(level), count(*) into prev, prev_level, n
    from public.brain_sessions where user_id = me and game = g.id;
  -- Score : plafond du jeu, et 3 000 points par seconde de jeu + 2 500 de bonus final.
  s := least(greatest(coalesce(p_score, 0), 0), g.max_score, dur * 3 + 2500);
  -- Niveau : premier niveau du palier le plus haut déjà atteint (départ possible) + 1 niveau par seconde de jeu.
  lvl := least(greatest(coalesce(p_level, 1), 1), 999,
               ((greatest(coalesce(prev_level, 1), 1) - 1) / 5) * 5 + 1 + dur / 1000);
  new_idx := private.brain_index(g.id, s, lvl);
  insert into public.brain_sessions (user_id, game, domain, score, idx, accuracy, avg_rt_ms, level, duration_ms)
  values (me, g.id, g.domain, s, new_idx, p_accuracy, least(greatest(coalesce(p_avg_rt_ms, 0), 0), 20000), lvl, dur);
  return jsonb_build_object('index', new_idx, 'best', greatest(coalesce(prev, 0), s), 'previous_best', prev,
                            'record', prev is null or s > prev, 'plays', n + 1, 'score', s, 'level', lvl);
end;
$$;

revoke all on function public.brain_record(text, integer, real, integer, integer, integer) from public, anon;
grant execute on function public.brain_record(text, integer, real, integer, integer, integer) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103150000', 'brain_niveaux')
  on conflict (version) do nothing;
commit;
