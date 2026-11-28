-- PROD, lot 21 (28.11, contrôle Apple final, 1.2) — migration 20261128110000 :
-- (a) public.my_group_invitations : plus jamais d'invitation d'une personne en blocage avec moi (qui invite ou créateur
--     du groupe) ; (b) private.group_report_snapshot : « Signaler » le groupe permis à qui a une invitation en attente.
-- Ancres vérifiées le 28.11 en lecture seule : my_group_invitations de la prod = celle de TEST (md5 e5dae488…), non
-- redéfinie par les fichiers 1 à 18 ; group_report_snapshot n'existe qu'APRÈS le fichier 6 (pot-paiement-geste), seul
-- à la créer, et aucun autre fichier ne la touche. ORDRE : APRÈS le fichier 6 (19e, dernier) ; sans lui, refus, rien
-- n'est modifié. Rejouable. Aucun texte de message ni de notification.
-- Testé sur TEST le 28.11 : tests/supabase_live/test_invitations_groupe_signaler_live.py ; retour arrière essayé puis réappliqué.
-- Retour arrière : 2026-11-28-invitations-groupe-signaler-rollback.sql.
begin;
do $patch$
declare
  def text;
  a1 constant text := $a$    and not exists (select 1 from public.member_group_members m where m.group_id = g.id and m.user_id = auth.uid());$a$;
  a2 constant text := $a$ or private.manages_group(mg.id));$a$;
begin
  -- (a) Invitations reçues : jamais celle d'une personne en blocage avec moi (qui invite ou créateur du groupe).
  def := pg_get_functiondef('public.my_group_invitations()'::regprocedure);
  if position('(20261128110000)' in def) = 0 then
    if position(a1 in def) = 0 or position(a1 in substr(def, position(a1 in def) + 1)) > 0 then
      raise exception 'public.my_group_invitations : ancre introuvable ou en double, rien n''est modifié';
    end if;
    execute replace(def, a1, $a$    and not private.blocked_either(auth.uid(), i.invited_by) and not private.blocked_either(auth.uid(), g.created_by) /* blocage (20261128110000) */
$a$ || a1);
  end if;

  -- (b) Signaler un groupe : permis aussi à qui a une invitation en attente pour ce groupe.
  def := pg_get_functiondef('private.group_report_snapshot(uuid,uuid)'::regprocedure);
  if position('(20261128110000)' in def) = 0 then
    if position(a2 in def) = 0 or position(a2 in substr(def, position(a2 in def) + 1)) > 0 then
      raise exception 'private.group_report_snapshot : ancre introuvable ou en double, rien n''est modifié';
    end if;
    execute replace(def, a2, $a$ or private.manages_group(mg.id)
         or exists (select 1 from private.group_invitations i where i.group_id = mg.id and i.status = 'pending'
                    and (i.user_id = viewer or i.phone = (select private.digits(p.phone) from public.profiles p where p.id = viewer))) /* invitation en attente (20261128110000) */);$a$);
  end if;
end $patch$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261128110000', 'invitations_groupe_signaler') on conflict do nothing;
commit;
