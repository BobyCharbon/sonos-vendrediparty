-- PROD, pot commun dit sur la page d'invitation (20261126120000, contrôle Apple du 26.11.2026).
-- Appliqué et testé sur la base de TEST le 26.11 (rejoué deux fois). Rejouable, tout ou rien.
-- Retour arrière : 2026-11-26-invitation-pot-commun-rollback.sql.
begin;
-- invite_preview renvoie aussi `pot_enabled` : « Je viens ! » dit, comme la fiche, qu'en répondant Présent on entre dans
-- le pot commun de l'événement. La fonction existante est ÉTENDUE (une clé de plus), rien d'autre ne change.
do $$
declare def text;
begin
  def := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  if position('''pot_enabled''' in def) = 0 then
    if position($a$'allow_maybe', ev.allow_maybe,$a$ in def) = 0 then
      raise exception 'invite_preview : ancre allow_maybe introuvable';
    end if;
    execute replace(def, $a$'allow_maybe', ev.allow_maybe,$a$, $a$'allow_maybe', ev.allow_maybe,
    'pot_enabled', coalesce(ev.pot_enabled, false),$a$);
  end if;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261126120000', 'invitation_pot_commun') on conflict do nothing;
commit;
