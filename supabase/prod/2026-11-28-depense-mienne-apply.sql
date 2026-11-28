-- PROD, lot 20 (28.11, recette de nuit tour 2) — migration 20261128100000 : private.tc_group_json ajoute à chaque dépense
-- 'mine' (created_by = moi) ; l'app iPhone (nouveau build) cache « Signaler la dépense / le ticket » sur sa propre dépense
-- (la base refuse « self »). Une seule ancre, dans la partie « expenses » : vérifiée le 28.11 en lecture seule contre la
-- prod (présente une seule fois) ; ni le fichier 6 (pot-paiement-geste), ni le 13 (blocage-pot-commun), ni le 14 ne la touchent.
-- ORDRE : APRÈS le fichier 13 (et donc 4 à 7) ; ancre manquante = refus, rien n'est modifié. Rejouable.
-- Testé sur TEST le 28.11 : tests/supabase_live/test_depense_mienne_live.py ; retour arrière essayé puis réapplication.
-- Retour arrière : 2026-11-28-depense-mienne-rollback.sql (n'importe quel ordre par rapport aux autres retours arrière).
begin;
do $patch$
declare
  def text := pg_get_functiondef('private.tc_group_json(uuid)'::regprocedure);
  anchor constant text := $a$'split_mode', e.split_mode, 'created_at', e.created_at,$a$;
begin
  if position('(20261128100000)' in def) > 0 then return; end if;
  if position(anchor in def) = 0 or position(anchor in substr(def, position(anchor in def) + 1)) > 0 then
    raise exception 'private.tc_group_json : ancre introuvable ou en double, rien n''est modifié';
  end if;
  execute replace(def, anchor,
    $a$'split_mode', e.split_mode, 'created_at', e.created_at, 'mine', e.created_by = auth.uid() /* dépense à moi (20261128100000) */,$a$);
end $patch$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261128100000', 'depense_mienne') on conflict do nothing;
commit;
