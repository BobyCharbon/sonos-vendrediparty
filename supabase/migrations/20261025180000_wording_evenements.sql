-- Vocabulaire : « événement » partout à la place de « sortie » (demande du 25.10.2026).
-- Textes seulement (libellés des droits et messages d'erreur) : aucune structure ni donnée de membre touchée.
-- Rejouable : les update réécrivent les mêmes valeurs ; les fonctions sont recréées à partir de leur définition
-- actuelle, avec le seul texte remplacé.

update public.permissions set hint = 'Faire partie du groupe : événements, sondages, discussions, annonces' where key = 'events.view';
update public.permissions set label = 'Répondre aux événements' where key = 'events.rsvp';
update public.permissions set label = 'Proposer un événement' where key = 'events.create';
update public.permissions set hint = 'Sinon l''événement attend qu''un admin le valide' where key = 'events.publish_direct';
update public.permissions set label = 'Modifier ses événements déjà publiés' where key = 'events.edit_own_published';
update public.permissions set label = 'Modifier ou annuler tous les événements',
  hint = 'Aussi : sondages, objets à apporter et organisateurs de tous les événements' where key = 'events.manage_all';
update public.permissions set label = 'Valider les événements proposés' where key = 'events.approve';
update public.permissions set label = 'Créer des sondages dans ses événements' where key = 'polls.create';

do $$
declare
  fn regprocedure;
  src text;
begin
  for fn in
    select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname in ('approve_event', 'reject_event', 'guard_event')
  loop
    src := pg_get_functiondef(fn);
    src := replace(src, 'Réservé à ceux qui valident les sorties', 'Réservé à ceux qui valident les événements');
    src := replace(src, 'Seul un admin peut modifier une sortie publiée', 'Seul un admin peut modifier un événement publié');
    execute src;
  end loop;
end $$;
