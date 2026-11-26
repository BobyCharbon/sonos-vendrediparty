-- Retour arrière de 2026-11-26-invitation-pot-commun-apply.sql : invite_preview sans la clé `pot_enabled` (définition
-- d'avant, identique en TEST et en PROD le 26.11). L'écran sait faire sans (clé absente : rien n'est dit).
begin;
do $$
declare def text;
begin
  def := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  if position('''pot_enabled''' in def) > 0 then
    execute replace(def, $a$
    'pot_enabled', coalesce(ev.pot_enabled, false),$a$, '');
  end if;
end $$;
delete from supabase_migrations.schema_migrations where version = '20261126120000';
commit;
