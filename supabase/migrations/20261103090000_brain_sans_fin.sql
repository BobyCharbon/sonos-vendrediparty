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
