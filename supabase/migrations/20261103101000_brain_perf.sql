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
