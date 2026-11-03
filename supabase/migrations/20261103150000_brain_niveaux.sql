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
