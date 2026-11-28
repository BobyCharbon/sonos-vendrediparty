-- Retour arrière de 2026-11-28-depense-mienne-apply.sql (20261128100000) : retire 'mine' des dépenses de
-- private.tc_group_json par la même ancre (l'app revient à la règle du payeur). Rejouable (rien si déjà retiré).
begin;
do $patch$
declare
  def text := pg_get_functiondef('private.tc_group_json(uuid)'::regprocedure);
  added constant text := $a$ 'mine', e.created_by = auth.uid() /* dépense à moi (20261128100000) */,$a$;
begin
  if position(added in def) = 0 then return; end if;
  execute replace(def, added, '');
end $patch$;
delete from supabase_migrations.schema_migrations where version = '20261128100000';
commit;
