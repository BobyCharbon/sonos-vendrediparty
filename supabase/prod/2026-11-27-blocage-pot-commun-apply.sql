-- PROD, lot 11B (27.11, contrôle Apple tour 6, Apple 1.2) — migration 20261127140000 : blocage dans le Pot commun
-- (« Personne bloquée », titre / note / ticket des dépenses de l'autre cachés, pas de moyens de paiement, montants gardés ;
-- aperçu du lien ; dépense de l'autre non modifiable ; pas d'ajout d'office d'un « Présent » en blocage avec le créateur du
-- pot) et résumé des réponses sans la personne en blocage avec l'organisateur.
-- ORDRE : APRÈS 2026-11-26-invitation-pot-commun, 2026-11-26-pot-cgu-signaler, 2026-11-26-pot-paiement-geste et
-- 2026-11-26-pot-filtre-paiement-purge (fichiers 4 à 7 : sans show_payment, ce fichier refuse et rien n'est modifié).
-- Retour arrière : 2026-11-27-blocage-pot-commun-rollback.sql, à passer AVANT celui de 2026-11-26-pot-paiement-geste.
-- Testé sur TEST le 27.11 : tests/supabase_live/test_blocage_pot_commun_live.py ; retour arrière essayé puis réapplication.
-- Rejouable (rien si déjà fait).
begin;
-- Lot 11B (27.11, contrôle Apple tour 6, Apple 1.2 « blocage commun à toute l'app »), additive et rejouable.
-- Passe APRÈS 20261126120000, 20261126130000, 20261126140000 et 20261126160000 (prod : fichiers 4 à 7 de la checklist) :
-- les ancres sont prises sur leur état (show_payment de 140000, require_terms de 130000).
-- 1. Pot commun, quand A et B sont en blocage (private.blocked_either), dans un pot partagé :
--    - private.tc_group_json : le membre de l'autre s'appelle « Personne bloquée », sans moyens de paiement ; les dépenses
--      créées par l'autre ont un titre vide, ni note ni ticket ; montants, payeur et parts restent (les comptes restent justes) ;
--    - public.tc_join_info (aperçu d'un lien de pot) : même nom « Personne bloquée » ;
--    - public.tc_save_expense : on ne modifie pas une dépense créée par l'autre (sinon le titre vidé l'effacerait) ;
--    - private.tc_event_sync : un « Présent » en blocage avec le créateur du pot (ou de l'événement) n'y est pas ajouté d'office ;
--    - lecture directe de tc_payment (RLS) : jamais les moyens de paiement de quelqu'un en blocage avec soi.
-- 2. private.flush_rsvp_digests : la réponse d'une personne en blocage avec l'organisateur n'entre jamais dans son résumé.
-- Toutes les ancres sont vérifiées AVANT la moindre modification : une ancre manquante = rien n'est modifié.
-- Une fonction qui porte déjà le marqueur « (20261127140000) » est laissée telle quelle (rejouable).

do $patch$
declare
  f record;
  def text;
  pair text[];
  defs text[] := '{}';
begin
  if not exists (select 1 from information_schema.columns
                 where table_schema = 'public' and table_name = 'tc_members' and column_name = 'show_payment') then
    raise exception 'tc_members.show_payment introuvable (appliquer d''abord 20261126140000), rien n''est modifié';
  end if;
  for f in select * from (values
    ('private.tc_group_json(uuid)', array[
      array[$a$jsonb_build_object('id', m.id, 'name', m.name, 'linked',$a$,
            $a$jsonb_build_object('id', m.id, 'name', case when private.blocked_either(auth.uid(), m.user_id) then 'Personne bloquée' else m.name end /* blocage (20261127140000) */, 'linked',$a$],
      array[$a$'payment', case when m.user_id is not null and m.left_at is null and (m.show_payment$a$,
            $a$'payment', case when m.user_id is not null and m.left_at is null and not private.blocked_either(auth.uid(), m.user_id) and (m.show_payment$a$],
      array[$a$'title', e.title,$a$,
            $a$'title', case when private.blocked_either(auth.uid(), e.created_by) then '' else e.title end,$a$],
      array[$a$'note', e.note, 'receipt_path', e.receipt_path,$a$,
            $a$'note', case when private.blocked_either(auth.uid(), e.created_by) then null else e.note end, 'receipt_path', case when private.blocked_either(auth.uid(), e.created_by) then null else e.receipt_path end,$a$]]),
    ('public.tc_join_info(uuid)', array[
      array[$a$jsonb_build_object('id', m.id, 'name', m.name, 'linked',$a$,
            $a$jsonb_build_object('id', m.id, 'name', case when private.blocked_either(auth.uid(), m.user_id) then 'Personne bloquée' else m.name end /* blocage (20261127140000) */, 'linked',$a$]]),
    ('public.tc_save_expense(uuid,jsonb)', array[
      array[E'    where id = eid and group_id = grp;\n    if not found then raise exception ''forbidden: dépense introuvable''; end if;',
            E'    where id = eid and group_id = grp and not private.blocked_either(auth.uid(), created_by); -- blocage (20261127140000)\n    if not found then raise exception ''forbidden: dépense introuvable''; end if;']]),
    ('private.tc_event_sync(uuid)', array[
      array[E'  where r.event_id = e and r.status = ''yes'' and not r.waitlisted\n',
            E'  where r.event_id = e and r.status = ''yes'' and not r.waitlisted\n'
            || E'    and not private.blocked_either(r.user_id, ev.created_by) -- blocage (20261127140000)\n'
            || E'    and not private.blocked_either(r.user_id, (select g.created_by from public.tc_groups g where g.id = grp))\n']]),
    ('private.flush_rsvp_digests()', array[
      array[$a$and d.updated_at <= started and d.status in ('yes', 'maybe');$a$,
            $a$and d.updated_at <= started and d.status in ('yes', 'maybe')
          and not private.blocked_either(recipient, d.user_id); -- blocage (20261127140000)$a$]])
  ) v(fn, pairs)
  loop
    if to_regprocedure(f.fn) is null then
      raise exception '% introuvable, rien n''est modifié', f.fn;
    end if;
    def := pg_get_functiondef(f.fn::regprocedure);
    continue when position('(20261127140000)' in def) > 0;
    foreach pair slice 1 in array f.pairs loop
      if position(pair[1] in def) = 0 then
        raise exception '% : ancre introuvable, rien n''est modifié', f.fn;
      end if;
      def := replace(def, pair[1], pair[2]);
    end loop;
    defs := defs || def;
  end loop;
  for i in 1 .. coalesce(array_length(defs, 1), 0) loop
    execute defs[i];
  end loop;
end $patch$;

-- Lecture directe des moyens de paiement : règle de 20261126140000, plus le blocage.
drop policy if exists "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment;
create policy "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment for select to authenticated
  using (user_id = (select auth.uid()) or (not private.blocked_either((select auth.uid()), tc_payment.user_id) and exists (
    select 1 from public.tc_members mine join public.tc_members theirs on theirs.group_id = mine.group_id
    where mine.user_id = (select auth.uid()) and mine.left_at is null
      and theirs.user_id = tc_payment.user_id and theirs.left_at is null and theirs.show_payment)));

insert into supabase_migrations.schema_migrations (version, name) values ('20261127140000', 'blocage_pot_commun') on conflict do nothing;
commit;
