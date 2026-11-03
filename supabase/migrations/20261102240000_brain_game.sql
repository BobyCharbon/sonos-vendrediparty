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
