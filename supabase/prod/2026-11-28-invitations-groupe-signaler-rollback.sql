-- Retour arrière de 2026-11-28-invitations-groupe-signaler-apply.sql (20261128110000) : retire, par le même texte ajouté,
-- le filtre de blocage de public.my_group_invitations et l'invitation en attente de private.group_report_snapshot.
-- Rejouable (rien si déjà retiré). À passer AVANT le retour arrière du fichier 6 (qui supprime group_report_snapshot).
begin;
do $patch$
declare
  def text;
  added1 constant text := $a$    and not private.blocked_either(auth.uid(), i.invited_by) and not private.blocked_either(auth.uid(), g.created_by) /* blocage (20261128110000) */
$a$;
  added2 constant text := $a$
         or exists (select 1 from private.group_invitations i where i.group_id = mg.id and i.status = 'pending'
                    and (i.user_id = viewer or i.phone = (select private.digits(p.phone) from public.profiles p where p.id = viewer))) /* invitation en attente (20261128110000) */$a$;
begin
  def := pg_get_functiondef('public.my_group_invitations()'::regprocedure);
  if position(added1 in def) > 0 then execute replace(def, added1, ''); end if;
  if to_regprocedure('private.group_report_snapshot(uuid,uuid)') is not null then
    def := pg_get_functiondef('private.group_report_snapshot(uuid,uuid)'::regprocedure);
    if position(added2 in def) > 0 then execute replace(def, added2, ''); end if;
  end if;
end $patch$;
delete from supabase_migrations.schema_migrations where version = '20261128110000';
commit;
