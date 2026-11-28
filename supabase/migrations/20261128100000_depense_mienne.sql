-- Lot 20 (28.11, recette de nuit tour 2), additive et rejouable : private.tc_group_json dit pour chaque dépense si elle
-- est À MOI ('mine' = created_by = moi). L'app iPhone cache alors « Signaler la dépense / le ticket » (la base refuse
-- « self » : le propriétaire d'une dépense est created_by, pas le payeur). Rien d'autre ne change.
-- Ancre (une seule fois, dans la partie « expenses ») : identique en prod et sur TEST, et non touchée par les fichiers
-- prod 6 (show_payment) et 13 (blocage-pot-commun). Ancre manquante = rien n'est modifié ; marqueur présent = laissé tel quel.
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
