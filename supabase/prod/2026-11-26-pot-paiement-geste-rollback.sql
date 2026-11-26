-- Retour arrière de 2026-11-26-pot-paiement-geste-apply.sql (20261126140000) : chaque ajout est retiré par la même
-- ancre (définitions remises comme avant), règles d'avant remises, colonne show_payment retirée en dernier. Les
-- signalements de noms de groupe ('group') sont effacés avant de resserrer la contrainte ; un nom déjà remplacé par la
-- modération le reste. Essayé sur la base de TEST le 26.11 (puis migration réappliquée).
begin;
delete from public.content_reports where target_kind = 'group';
do $$ declare def text;
begin
  def := pg_get_functiondef('private.tc_group_json(uuid)'::regprocedure);
  if position('m.show_payment' in def) > 0 then
    def := replace(def, $a$'left', m.left_at is not null, 'show_payment', m.show_payment,$a$, $a$'left', m.left_at is not null,$a$);
    def := replace(def, $a$ and (m.show_payment or m.user_id = auth.uid()) then$a$, $a$ then$a$);
    execute def;
  end if;

  def := pg_get_functiondef('private.tc_event_sync(uuid)'::regprocedure);
  if position('show_payment' in def) > 0 then
    execute replace(def, E'  insert into public.tc_members (group_id, user_id, show_payment, name)\n  select grp, ev.created_by, true, left(',
                         E'  insert into public.tc_members (group_id, user_id, name)\n  select grp, ev.created_by, left(');
  end if;

  def := pg_get_functiondef('public.tc_create(text,text,text,text)'::regprocedure);
  if position('show_payment' in def) > 0 then
    execute replace(def, 'insert into public.tc_members (group_id, user_id, name, show_payment) values (grp, auth.uid(), btrim(my_name), true);',
                         'insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));');
  end if;

  def := pg_get_functiondef('public.tc_join(uuid,text,uuid)'::regprocedure);
  if position('show_payment' in def) > 0 then
    def := replace(def, 'update public.tc_members set show_payment = show_payment or left_at is not null, left_at = null where id = existing;',
                        'update public.tc_members set left_at = null where id = existing;');
    def := replace(def, 'update public.tc_members set user_id = auth.uid(), show_payment = true where id = claim',
                        'update public.tc_members set user_id = auth.uid() where id = claim');
    def := replace(def, 'insert into public.tc_members (group_id, user_id, name, show_payment) values (grp, auth.uid(), btrim(my_name), true);',
                        'insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));');
    execute def;
  end if;

  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position(', ''group''::text' in def) > 0 then
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, ', ''group''::text', '');
  end if;

  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('group_report_snapshot' in def) > 0 then
    execute replace(def, $a$  elsif p_kind = 'group' then
    return private.group_report_snapshot(uid, viewer);
$a$, '');
  end if;

  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position($a$r.target_kind = 'group' then$a$ in def) > 0 then
    execute replace(def, $a$  elsif r.target_kind = 'group' then
    update public.member_groups set name = 'Groupe renommé par la modération' where id = uid and system_key is null;
$a$, '');
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position($a$new.target_kind = 'group' then$a$ in def) > 0 then
    execute replace(def, $a$when new.target_kind = 'group' then 'le nom d''un groupe'
                        else 'Zicou' end)$a$, $a$else 'Zicou' end)$a$);
  end if;

  def := pg_get_functiondef('private.notify_content_hidden(public.content_reports)'::regprocedure);
  if position($a$r.target_kind = 'group' then$a$ in def) > 0 then
    execute replace(def, $a$
               when r.target_kind = 'group' then 'Le nom de ton groupe a été remplacé'$a$, '');
  end if;

  def := pg_get_functiondef('public.report_content(text,text,text,text,boolean)'::regprocedure);
  if position($a$(is_msg or p_kind = 'tc_expense')$a$ in def) > 0 then
    execute replace(def, $a$(is_msg or p_kind = 'tc_expense')$a$, 'is_msg');
  end if;

  def := pg_get_functiondef('private.moderation_copy_evidence(uuid,jsonb)'::regprocedure);
  if position('tc-receipts' in def) > 0 then
    execute replace(def, $a$'bucketId', case when snap ->> 'bucket' = 'tc-receipts' then 'tc-receipts' else 'chat-photos' end$a$,
                         $a$'bucketId', 'chat-photos'$a$);
  end if;
end $$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;
revoke all on function private.moderation_copy_evidence(uuid, jsonb) from public, anon, authenticated;

drop policy if exists "modération : voir un ticket signalé" on storage.objects;
drop function if exists private.tc_receipt_reported(text);
drop function if exists private.group_report_snapshot(uuid, uuid);
drop function if exists public.tc_set_show_payment(uuid, boolean);

drop policy if exists "voir les photos d'un événement" on storage.objects;
create policy "voir les photos d'un événement" on storage.objects for select to authenticated
  using (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and exists (select 1 from public.events ev where ev.id = ((storage.foldername(name))[1])::uuid)
         and public.can_see_event(((storage.foldername(name))[1])::uuid));
revoke execute on function private.event_chat_member(uuid, uuid) from authenticated;

drop policy if exists "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment;
create policy "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment for select to authenticated
  using (user_id = (select auth.uid()) or exists (
    select 1 from public.tc_members mine join public.tc_members theirs on theirs.group_id = mine.group_id
    where mine.user_id = (select auth.uid()) and mine.left_at is null and theirs.user_id = tc_payment.user_id and theirs.left_at is null));
alter table public.tc_members drop column if exists show_payment;
delete from supabase_migrations.schema_migrations where version = '20261126140000';
commit;
