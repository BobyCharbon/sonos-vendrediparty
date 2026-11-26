-- PROD, Pot commun : CGU et Signaler une dépense ; profil sans photo exigée (20261126130000, contrôle Apple du 26.11.2026).
-- Préparé le 26.11, PAS appliqué. Appliqué deux fois et testé sur la base de TEST le 26.11
-- (tests/supabase_live/test_pot_commun_cgu_signaler_live.py). Tout est étendu PAR ANCRE sur les définitions en place :
-- ancres vérifiées en prod (lecture seule, 26.11) dans report_snapshot, moderation_hide, notify_new_report, les 7 tc_*
-- et la contrainte content_reports_target_kind_check ('pet_word'). Compatible avec les fichiers Agenda / Pronos /
-- Souvenirs appliqués plus tard (ils étendent la contrainte par leurs propres ancres). Rejouable, tout ou rien.
-- Retour arrière : 2026-11-26-pot-cgu-signaler-rollback.sql.
begin;
create or replace function private.tc_expense_report_snapshot(uid uuid, viewer uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('owner', e.created_by, 'text', concat_ws(E'\n', e.title, e.note), 'photo_path', e.receipt_path,
           'bucket', 'tc-receipts', 'group_id', e.group_id, 'at', e.created_at, 'place', 'Pot commun · ' || g.name)
  from public.tc_expenses e join public.tc_groups g on g.id = e.group_id
  where e.id = uid and private.tc_member_of(e.group_id, viewer) is not null;
$$;
revoke all on function private.tc_expense_report_snapshot(uuid, uuid) from public, anon, authenticated;

do $$ declare def text; f text;
begin
  -- 1. CGU au début de chaque fonction qui publie (première ligne après « begin »).
  foreach f in array array['public.tc_create(text,text,text,text)', 'public.tc_update_group(uuid,text,text,text,boolean)',
                           'public.tc_join(uuid,text,uuid)', 'public.tc_add_member(uuid,text)',
                           'public.tc_rename_member(uuid,text)', 'public.tc_save_expense(uuid,jsonb)',
                           'public.tc_set_payment(text,text,jsonb,text)'] loop
    def := pg_get_functiondef(f::regprocedure);
    if position('require_terms' in def) = 0 then
      if position(E'\nbegin\n' in def) = 0 then raise exception '% : ancre begin introuvable', f; end if;
      execute regexp_replace(def, E'\nbegin\n', E'\nbegin\n  perform private.require_terms(auth.uid());\n');
    end if;
  end loop;

  -- 2. Signalement d'une dépense du pot.
  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position('''tc_expense''' in def) = 0 then
    if position('''pet_word''::text' in def) = 0 then raise exception 'content_reports : ancre pet_word introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, '''pet_word''::text', '''pet_word''::text, ''tc_expense''::text');
  end if;

  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('''tc_expense''' in def) = 0 then
    if position($a$  elsif p_kind in ('profile', 'profile_photo') then$a$ in def) = 0 then raise exception 'report_snapshot : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif p_kind in ('profile', 'profile_photo') then$a$, $a$  elsif p_kind = 'tc_expense' then
    return private.tc_expense_report_snapshot(uid, viewer);
  elsif p_kind in ('profile', 'profile_photo') then$a$);
  end if;

  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position('''tc_expense''' in def) = 0 then
    if position($a$  elsif r.target_kind = 'profile' then$a$ in def) = 0 then raise exception 'moderation_hide : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif r.target_kind = 'profile' then$a$, $a$  elsif r.target_kind = 'tc_expense' then
    update public.tc_expenses set title = 'Dépense masquée par la modération', note = null, receipt_path = null where id = uid;
  elsif r.target_kind = 'profile' then$a$);
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''tc_expense''' in def) = 0 then
    if position($a$else 'Zicou' end)$a$ in def) = 0 then raise exception 'notify_new_report : ancre Zicou introuvable'; end if;
    execute replace(def, $a$else 'Zicou' end)$a$, $a$when new.target_kind = 'tc_expense' then 'une dépense du Pot commun'
                        else 'Zicou' end)$a$);
  end if;

  -- 3. Photo facultative : le message ne la demande plus.
  foreach f in array array['public.join_group_by_link(uuid)', 'public.join_event_by_link(uuid)'] loop
    if to_regprocedure(f) is null then continue; end if;
    def := pg_get_functiondef(f::regprocedure);
    if position('prénom, surnom et photo)' in def) > 0 then
      execute replace(def, 'prénom, surnom et photo)', 'prénom et surnom)');
    end if;
  end loop;
  for f in select p.oid::regprocedure::text from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.proname = 'claim_app_invite' loop
    def := pg_get_functiondef(f::regprocedure);
    if position('prénom, surnom et photo)' in def) > 0 then
      execute replace(def, 'prénom, surnom et photo)', 'prénom et surnom)');
    end if;
  end loop;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261126130000', 'pot_commun_cgu_signaler') on conflict do nothing;
commit;
