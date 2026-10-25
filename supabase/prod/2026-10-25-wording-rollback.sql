-- Retour arrière de 20261025180000_wording_evenements (valeurs relevées en prod le 25.10.2026 avant application).
update public.permissions set hint = 'Faire partie du groupe : sorties, sondages, discussions, annonces' where key = 'events.view';
update public.permissions set label = 'Répondre aux sorties' where key = 'events.rsvp';
update public.permissions set label = 'Proposer une sortie' where key = 'events.create';
update public.permissions set hint = 'Sinon la sortie attend qu''un admin la valide' where key = 'events.publish_direct';
update public.permissions set label = 'Modifier ses sorties déjà publiées' where key = 'events.edit_own_published';
update public.permissions set label = 'Modifier ou annuler toutes les sorties',
  hint = 'Aussi : sondages, objets à apporter et organisateurs de toutes les sorties' where key = 'events.manage_all';
update public.permissions set label = 'Valider les sorties proposées' where key = 'events.approve';
update public.permissions set label = 'Créer des sondages dans ses sorties' where key = 'polls.create';

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
    src := replace(src, 'Réservé à ceux qui valident les événements', 'Réservé à ceux qui valident les sorties');
    src := replace(src, 'Seul un admin peut modifier un événement publié', 'Seul un admin peut modifier une sortie publiée');
    execute src;
  end loop;
end $$;
