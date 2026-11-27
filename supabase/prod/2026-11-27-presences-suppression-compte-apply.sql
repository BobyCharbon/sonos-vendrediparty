-- PROD, présences sans compte : suppression du compte de l'organisateur de nouveau possible (20261127090000, recette iPhone du 27.11).
-- Testé sur TEST le 27.11 (cascade added_by -> null acceptée, vraie modification toujours refusée). Rejouable. Retour arrière : 2026-11-27-presences-suppression-compte-rollback.sql.
begin;
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
insert into supabase_migrations.schema_migrations (version, name) values ('20261127090000', 'presences_suppression_compte') on conflict do nothing;
commit;
