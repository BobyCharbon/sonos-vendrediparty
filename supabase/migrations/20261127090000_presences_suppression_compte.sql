-- Présences sans compte : la suppression du compte de l'organisateur qui a noté quelqu'un était refusée (recette iPhone
-- du 27.11) : la cascade `added_by -> null` passait par la garde, qui exigeait un événement publié et remettait added_by.
-- Correctif : une mise à jour qui ne change que `added_by` vers null (cascade de la base, jamais l'écran) passe telle quelle.
-- Additive et rejouable : la garde est étendue par ancre (insertion en tête de la branche UPDATE).
do $patch$
declare def text;
  anchor text := $a$  if tg_op = 'UPDATE' then
    new.id := old.id;$a$;
  added text := $a$  if tg_op = 'UPDATE' and new.added_by is null and old.added_by is not null
     and new.name is not distinct from old.name and new.status is not distinct from old.status
     and new.event_id is not distinct from old.event_id then
    return new; -- compte supprimé : la base efface seulement qui a noté la personne
  end if;
$a$;
begin
  def := pg_get_functiondef('private.guard_manual_guest()'::regprocedure);
  if position('compte supprimé : la base efface' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then raise exception 'guard_manual_guest : ancre introuvable, rien n''est modifié'; end if;
  execute replace(def, anchor, added || anchor);
end $patch$;
