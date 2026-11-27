-- Retour arrière de 2026-11-27-blocage-notifications-pot-apply.sql (20261127150000) : chaque ajout est retiré par la même
-- ancre (drop_blocked_notification, report_snapshot, moderation_hide, notify_new_report, notify_content_hidden remises
-- comme avant), types 'tc_group' / 'tc_member' retirés de la contrainte, fonctions de copie supprimées. À passer AVANT les
-- retours arrière de 2026-11-26-pot-cgu-signaler, 2026-11-26-pot-paiement-geste et 2026-11-27-suppression-blocage.
-- Refuse (rien n'est modifié) s'il existe déjà des signalements de ces deux types : à traiter d'abord par la modération.
-- Rejouable (rien si déjà retiré).
begin;
do $patch$
declare
  f record;
  def text;
  pair text[];
  defs text[] := '{}';
  con text;
begin
  if exists (select 1 from public.content_reports where target_kind in ('tc_group', 'tc_member')) then
    raise exception 'signalements tc_group / tc_member présents : rien n''est modifié';
  end if;
  for f in select * from (values
    ('private.drop_blocked_notification()', array[
      array[E'  -- Événement d''une personne en blocage avec le destinataire (20261127150000)\n'
            || E'  if new.event_id is not null\n'
            || E'     and new.kind in (''new_event'', ''event_changed'', ''poll_new'', ''poll_nudge'', ''reminder'', ''date_fixed'',\n'
            || E'                      ''private_invite'', ''rsvp_set'', ''coorganizer_added'', ''bar_changed'')\n'
            || E'     and exists (select 1 from public.events ev where ev.id = new.event_id and ev.created_by is not null\n'
            || E'                 and ev.created_by <> new.user_id and private.blocked_either(ev.created_by, new.user_id)) then\n'
            || E'    return null;\n'
            || E'  end if;\n'
            || E'  return new;\nend',
            E'  return new;\nend']]),
    ('private.report_snapshot(text,text,uuid)', array[
      array[$a$  elsif p_kind = 'tc_group' then
    return private.tc_group_report_snapshot(uid, viewer);
  elsif p_kind = 'tc_member' then
    return private.tc_member_report_snapshot(uid, viewer);
  elsif p_kind in ('profile', 'profile_photo') then$a$,
            $a$  elsif p_kind in ('profile', 'profile_photo') then$a$]]),
    ('private.moderation_hide(public.content_reports)', array[
      array[$a$  elsif r.target_kind = 'tc_group' then
    update public.tc_groups set name = 'Pot renommé par la modération' where id = uid;
  elsif r.target_kind = 'tc_member' then
    update public.tc_members set name = 'Prénom masqué' where id = uid;
  elsif r.target_kind = 'profile' then$a$,
            $a$  elsif r.target_kind = 'profile' then$a$]]),
    ('private.notify_new_report()', array[
      array[$a$when new.target_kind = 'tc_group' then 'le nom d''un Pot commun'
                        when new.target_kind = 'tc_member' then 'un prénom du Pot commun'
                        else 'Zicou' end)$a$,
            $a$else 'Zicou' end)$a$]]),
    ('private.notify_content_hidden(public.content_reports)', array[
      array[$a$when r.target_kind = 'tc_group' then 'Le nom de ton Pot commun a été remplacé'
               when r.target_kind = 'tc_member' then 'Ton prénom dans un Pot commun a été masqué'
               else 'Un contenu que tu as publié a été retiré' end$a$,
            $a$else 'Un contenu que tu as publié a été retiré' end$a$]])
  ) v(fn, pairs)
  loop
    def := pg_get_functiondef(f.fn::regprocedure);
    foreach pair slice 1 in array f.pairs loop
      continue when position(pair[1] in def) = 0;  -- déjà retiré
      def := replace(def, pair[1], pair[2]);
    end loop;
    defs := defs || def;
  end loop;
  for i in 1 .. coalesce(array_length(defs, 1), 0) loop
    execute defs[i];
  end loop;
  con := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position(', ''tc_group''::text, ''tc_member''::text' in con) > 0 then
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(con, ', ''tc_group''::text, ''tc_member''::text', '');
  end if;
end $patch$;
drop function if exists private.tc_group_report_snapshot(uuid, uuid);
drop function if exists private.tc_member_report_snapshot(uuid, uuid);
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;

delete from supabase_migrations.schema_migrations where version = '20261127150000';
commit;
