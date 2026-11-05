-- PROD, retour arrière de evenement_annule_reste_annule (20261105131500) : la garde public.guard_event perd les deux
-- lignes ajoutées (un événement annulé modifié par un organisateur sans events.manage_all repasse alors par le calcul
-- du statut d'une proposition, comme avant). Tout ou rien.
begin;
do $$
declare
  def text := pg_get_functiondef('public.guard_event()'::regprocedure);
  added text := '-- Annulé (05.11) : il le reste ; seul events.manage_all (plus haut) le rouvre.'
    || E'\n  if old.status = ''cancelled'' then new.status := ''cancelled''; return new; end if;'
    || E'\n  ';
begin
  if position(added in def) > 0 then execute replace(def, added, ''); end if;
end $$;
delete from supabase_migrations.schema_migrations where version = '20261105131500';
commit;

notify pgrst, 'reload schema';
