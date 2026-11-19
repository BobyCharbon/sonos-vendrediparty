-- PROD, paiement_en_ligne_declare (20261119180000) : migration supabase/migrations/20261119180000_paiement_en_ligne_declare.sql telle quelle (19.11).
-- Rejouable (repères). Tout ou rien.
begin;
-- Paiement en ligne (demande de l'admin, 19.11.2026, revient sur l'avis du 16.11) : la personne note « J'ai payé » après
-- avoir payé sur le site ; l'organisateur n'a RIEN à accepter (pas de « Reçu ✓ ») : il voit qui a payé et quand.
-- « On me paie » : inchangé (Reçu ✓). Sur place : inchangé (rien à noter). La déclaration en ligne ne passe jamais la place
-- en « payé » (paid) : pas de billet QR remis sur la seule parole de la personne (l'entrée peut toujours cocher « payé »).
-- Modifie declare_ticket_payment par repères (texte en place relu, jamais réécrit en entier). Rejouable.
do $$
declare src text := pg_get_functiondef('public.declare_ticket_payment(uuid, boolean)'::regprocedure);
  refuse text := E'  if declared and ev.payment_mode = ''online'' then\n    raise exception ''Cet événement se paie en ligne, sur le site indiqué : rien à noter dans Party.'' using errcode = ''22023'';\n  end if;\n';
  old_text text := E'who || '' dit avoir payé sa place ('' || trim_scale(ev.price_chf)::text || '' CHF) : confirme quand tu l''''as vérifié.''';
  new_text text := E'case when ev.payment_mode = ''online'' then who || '' a payé sa place en ligne ('' || trim_scale(ev.price_chf)::text || '' CHF).'' else who || '' dit avoir payé sa place ('' || trim_scale(ev.price_chf)::text || '' CHF) : confirme quand tu l''''as vérifié.'' end';
begin
  if position('a payé sa place en ligne' in src) > 0 then return; end if;  -- déjà fait
  if position(refuse in src) = 0 or position(old_text in src) = 0 then
    raise exception 'declare_ticket_payment : repères introuvables, rien changé';
  end if;
  execute replace(replace(src, refuse, ''), old_text, new_text);
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261119180000', 'paiement_en_ligne_declare') on conflict do nothing;
commit;
