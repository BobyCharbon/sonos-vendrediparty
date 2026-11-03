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
