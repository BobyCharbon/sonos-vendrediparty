-- Lot 21 (28.11, contrôle Apple final, 1.2), additive et rejouable :
-- (a) public.my_group_invitations ne montre jamais une invitation si je suis en blocage (un sens ou l'autre) avec qui
--     m'invite ou avec le créateur du groupe (private.blocked_either) ;
-- (b) private.group_report_snapshot (« Signaler » le nom d'un groupe, 20261126140000) est permis aussi à qui a une
--     invitation EN ATTENTE pour ce groupe (l'écran des invitations reçues a « 🚩 Signaler »).
-- Par ancre (une fois chacune), sur l'état APRÈS les fichiers prod 1 à 18 : my_group_invitations = 20261117100000
-- (aucun fichier prod 1 à 18 ne la redéfinit ; prod et TEST identiques, md5 e5dae488…) ; group_report_snapshot = fichier 6
-- (pot-paiement-geste), qu'aucun autre ne touche. Ancre manquante = refus, rien n'est modifié ; marqueur présent = laissé tel quel.
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
