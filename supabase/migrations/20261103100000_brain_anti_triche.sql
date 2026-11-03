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
