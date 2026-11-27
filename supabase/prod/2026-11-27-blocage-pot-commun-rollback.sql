-- Retour arrière de 2026-11-27-blocage-pot-commun-apply.sql (20261127140000) : chaque ajout est retiré par la même
-- ancre (tc_group_json, tc_join_info, tc_save_expense, tc_event_sync, flush_rsvp_digests remises comme avant), règle de
-- lecture de tc_payment remise comme dans 20261126140000. Rejouable (rien si déjà retiré). À passer AVANT
-- 2026-11-26-pot-paiement-geste-rollback.sql. Les « Présent » non ajoutés pendant le blocage ne sont pas rajoutés ici
-- (le prochain tc_event_sync de l'événement le fera).
begin;
do $patch$
declare
  f record;
  def text;
  i int;
begin
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
    continue when to_regprocedure(f.fn) is null;
    def := pg_get_functiondef(f.fn::regprocedure);
    continue when position('(20261127140000)' in def) = 0;
    for i in reverse array_length(f.pairs, 1) .. 1 loop
      def := replace(def, f.pairs[i][2], f.pairs[i][1]);
    end loop;
    execute def;
  end loop;
end $patch$;

drop policy if exists "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment;
create policy "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment for select to authenticated
  using (user_id = (select auth.uid()) or exists (
    select 1 from public.tc_members mine join public.tc_members theirs on theirs.group_id = mine.group_id
    where mine.user_id = (select auth.uid()) and mine.left_at is null
      and theirs.user_id = tc_payment.user_id and theirs.left_at is null and theirs.show_payment));

delete from supabase_migrations.schema_migrations where version = '20261127140000';
commit;
