-- Un événement annulé reste annulé quand un organisateur le modifie (bug trouvé au test du parcours organisateur,
-- 05.11.2026). public.guard_event recalculait le statut d'un événement non publié comme celui d'une proposition :
-- un co-organisateur (ou un organisateur sans le droit « tous les événements ») qui corrigeait un événement ANNULÉ le
-- faisait repasser « en attente de validation » (ou « publié » avec le droit de publier sans validation), en silence.
-- Désormais, pour eux, un événement annulé garde son statut ; le rouvrir reste réservé au droit events.manage_all.
-- Fonction complétée en place, une seule fois (même méthode que 20261105121000_billets_paiement) : purement additif
-- et rejouable.
do $$
declare
  def text := pg_get_functiondef('public.guard_event()'::regprocedure);
  anchor text := 'if old.status = ''published'' then';
begin
  if position('Annulé (05.11)' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then
    raise exception 'guard_event : branche « published » introuvable, garde des événements annulés non ajoutée';
  end if;
  execute replace(def, anchor, '-- Annulé (05.11) : il le reste ; seul events.manage_all (plus haut) le rouvre.'
    || E'\n  if old.status = ''cancelled'' then new.status := ''cancelled''; return new; end if;'
    || E'\n  ' || anchor);
end $$;

notify pgrst, 'reload schema';
