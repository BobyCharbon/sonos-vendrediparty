-- Retour arrière de 2026-11-27-presences-suppression-compte-apply.sql : retire le passage ajouté en tête de la garde.
begin;
do $patch$
declare def text;
  added text := $a$  if tg_op = 'UPDATE' and new.added_by is null and old.added_by is not null
     and new.name is not distinct from old.name and new.status is not distinct from old.status
     and new.event_id is not distinct from old.event_id then
    return new; -- compte supprimé : la base efface seulement qui a noté la personne
  end if;
$a$;
begin
  def := pg_get_functiondef('private.guard_manual_guest()'::regprocedure);
  if position(added in def) > 0 then execute replace(def, added, ''); end if;
end $patch$;
delete from supabase_migrations.schema_migrations where version = '20261127090000';
commit;
