-- Retour arrière de 2026-11-26-pot-cgu-signaler-apply.sql : chaque ajout est retiré par la même ancre (définitions
-- remises comme avant). Les signalements de dépenses ('tc_expense') sont effacés avant de resserrer la contrainte ;
-- une dépense déjà masquée par la modération le reste.
begin;
delete from public.content_reports where target_kind = 'tc_expense';
do $$ declare def text; f text;
begin
  foreach f in array array['public.tc_create(text,text,text,text)', 'public.tc_update_group(uuid,text,text,text,boolean)',
                           'public.tc_join(uuid,text,uuid)', 'public.tc_add_member(uuid,text)',
                           'public.tc_rename_member(uuid,text)', 'public.tc_save_expense(uuid,jsonb)',
                           'public.tc_set_payment(text,text,jsonb,text)'] loop
    def := pg_get_functiondef(f::regprocedure);
    if position(E'\nbegin\n  perform private.require_terms(auth.uid());\n' in def) > 0 then
      execute replace(def, E'\nbegin\n  perform private.require_terms(auth.uid());\n', E'\nbegin\n');
    end if;
  end loop;

  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position(', ''tc_expense''::text' in def) > 0 then
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, ', ''tc_expense''::text', '');
  end if;

  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('''tc_expense''' in def) > 0 then
    execute replace(def, $a$  elsif p_kind = 'tc_expense' then
    return private.tc_expense_report_snapshot(uid, viewer);
$a$, '');
  end if;

  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position('''tc_expense''' in def) > 0 then
    execute replace(def, $a$  elsif r.target_kind = 'tc_expense' then
    update public.tc_expenses set title = 'Dépense masquée par la modération', note = null, receipt_path = null where id = uid;
$a$, '');
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''tc_expense''' in def) > 0 then
    execute replace(def, $a$when new.target_kind = 'tc_expense' then 'une dépense du Pot commun'
                        $a$, '');
  end if;

  foreach f in array array['public.join_group_by_link(uuid)', 'public.join_event_by_link(uuid)', 'public.claim_app_invite(uuid)'] loop
    if to_regprocedure(f) is null then continue; end if;
    def := pg_get_functiondef(f::regprocedure);
    if position('prénom et surnom)' in def) > 0 then
      execute replace(def, 'prénom et surnom)', 'prénom, surnom et photo)');
    end if;
  end loop;
end $$;
drop function if exists private.tc_expense_report_snapshot(uuid, uuid);
delete from supabase_migrations.schema_migrations where version = '20261126130000';
commit;
