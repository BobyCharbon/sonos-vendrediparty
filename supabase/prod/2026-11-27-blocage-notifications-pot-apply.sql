-- PROD, lot 14 (27.11, contrôle Apple, Apple 1.2) — migration 20261127150000 : aucune notification d'un événement créé
-- par une personne en blocage avec le destinataire (pg_cron compris, d'après events.created_by), et « Signaler » le nom
-- d'un Pot commun ('tc_group') et le prénom d'un membre ('tc_member').
-- ORDRE : APRÈS 2026-11-26-pot-cgu-signaler et 2026-11-26-pot-paiement-geste (fichiers 5 et 6) et
-- 2026-11-27-suppression-blocage (fichier 10) ; ses ancres sont indépendantes des leurs (vérifiées en lecture seule contre
-- la prod le 27.11), mais l'état testé sur TEST est celui d'après. Retour arrière :
-- 2026-11-27-blocage-notifications-pot-rollback.sql, à passer AVANT ceux de 5, 6 et 10.
-- Testé sur TEST le 27.11 : tests/supabase_live/test_blocage_notifications_pot_live.py ; retour arrière essayé puis
-- réapplication. Rejouable (rien si déjà fait).
begin;
-- Lot 14 (27.11, contrôle Apple, 1.2 « blocage commun » et « Signaler »), additive et rejouable.
-- Passe APRÈS 20261126130000, 20261126140000 et 20261127110000 (prod : la checklist le dit) ; les ancres sont communes
-- à la prod (sans Agenda, Pronos ni Souvenirs) et à TEST, vérifiées en lecture seule le 27.11.
-- 1. private.drop_blocked_notification : jette aussi les notifications qui viennent du CRÉATEUR d'un événement ou
--    annoncent son événement (new_event, event_changed — paiement ouvert compris —, poll_new, poll_nudge, reminder,
--    date_fixed, private_invite — relances comprises —, rsvp_set, coorganizer_added, bar_changed) quand il est en blocage
--    avec le destinataire. Fondé sur events.created_by et le destinataire, jamais sur auth.uid() (vide quand pg_cron
--    envoie). Tout ce qui sert à qui participe encore reste : messages du chat écrits par d'autres, bar_served,
--    ticket_pay_*, ticket_issued, souvenirs_revealed, waitlist, rsvp / link_join à un co-organisateur, modération.
-- 2. Signaler, dans un Pot commun, le NOM du pot (type 'tc_group', cible = id du pot) et le PRÉNOM d'un membre
--    (type 'tc_member', cible = id de la ligne tc_members) : visibles par les seuls membres du pot ; « Masquer » remplace
--    par « Pot renommé par la modération » / « Prénom masqué » (les comptes ne bougent pas). Un prénom n'a pas d'auteur
--    sûr (tout membre renomme tout membre, tc_rename_member) : aucun propriétaire (ni sanction ni avis à la mauvaise
--    personne), et on peut signaler son propre prénom écrit par un autre. Le nom du pot : son créateur.
-- Toutes les ancres sont vérifiées AVANT la moindre modification ; une définition qui porte déjà le marqueur
-- « (20261127150000) » ou le type est laissée telle quelle.

create or replace function private.tc_group_report_snapshot(uid uuid, viewer uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('owner', g.created_by, 'text', g.name, 'tc_group', g.id, 'place', 'Nom du Pot commun')
  from public.tc_groups g
  where g.id = uid and private.tc_member_of(g.id, viewer) is not null;
$$;
revoke all on function private.tc_group_report_snapshot(uuid, uuid) from public, anon, authenticated;

create or replace function private.tc_member_report_snapshot(uid uuid, viewer uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('owner', null, 'text', m.name, 'tc_group', g.id, 'place', 'Prénom · Pot commun · ' || g.name)
  from public.tc_members m join public.tc_groups g on g.id = m.group_id
  where m.id = uid and private.tc_member_of(g.id, viewer) is not null;
$$;
revoke all on function private.tc_member_report_snapshot(uuid, uuid) from public, anon, authenticated;

do $patch$
declare
  f record;
  def text;
  pair text[];
  defs text[] := '{}';
  con text;
begin
  for f in select * from (values
    ('private.drop_blocked_notification()', '(20261127150000)', array[
      array[E'  return new;\nend',
            E'  -- Événement d''une personne en blocage avec le destinataire (20261127150000)\n'
            || E'  if new.event_id is not null\n'
            || E'     and new.kind in (''new_event'', ''event_changed'', ''poll_new'', ''poll_nudge'', ''reminder'', ''date_fixed'',\n'
            || E'                      ''private_invite'', ''rsvp_set'', ''coorganizer_added'', ''bar_changed'')\n'
            || E'     and exists (select 1 from public.events ev where ev.id = new.event_id and ev.created_by is not null\n'
            || E'                 and ev.created_by <> new.user_id and private.blocked_either(ev.created_by, new.user_id)) then\n'
            || E'    return null;\n'
            || E'  end if;\n'
            || E'  return new;\nend']]),
    ('private.report_snapshot(text,text,uuid)', 'tc_group_report_snapshot', array[
      array[$a$  elsif p_kind in ('profile', 'profile_photo') then$a$,
            $a$  elsif p_kind = 'tc_group' then
    return private.tc_group_report_snapshot(uid, viewer);
  elsif p_kind = 'tc_member' then
    return private.tc_member_report_snapshot(uid, viewer);
  elsif p_kind in ('profile', 'profile_photo') then$a$]]),
    ('private.moderation_hide(public.content_reports)', $m$r.target_kind = 'tc_group'$m$, array[
      array[$a$  elsif r.target_kind = 'profile' then$a$,
            $a$  elsif r.target_kind = 'tc_group' then
    update public.tc_groups set name = 'Pot renommé par la modération' where id = uid;
  elsif r.target_kind = 'tc_member' then
    update public.tc_members set name = 'Prénom masqué' where id = uid;
  elsif r.target_kind = 'profile' then$a$]]),
    ('private.notify_new_report()', $m$new.target_kind = 'tc_group'$m$, array[
      array[$a$else 'Zicou' end)$a$,
            $a$when new.target_kind = 'tc_group' then 'le nom d''un Pot commun'
                        when new.target_kind = 'tc_member' then 'un prénom du Pot commun'
                        else 'Zicou' end)$a$]]),
    ('private.notify_content_hidden(public.content_reports)', $m$r.target_kind = 'tc_group'$m$, array[
      array[$a$else 'Un contenu que tu as publié a été retiré' end$a$,
            $a$when r.target_kind = 'tc_group' then 'Le nom de ton Pot commun a été remplacé'
               when r.target_kind = 'tc_member' then 'Ton prénom dans un Pot commun a été masqué'
               else 'Un contenu que tu as publié a été retiré' end$a$]])
  ) v(fn, marker, pairs)
  loop
    if to_regprocedure(f.fn) is null then
      raise exception '% introuvable, rien n''est modifié', f.fn;
    end if;
    def := pg_get_functiondef(f.fn::regprocedure);
    continue when position(f.marker in def) > 0;
    foreach pair slice 1 in array f.pairs loop
      if position(pair[1] in def) = 0 then
        raise exception '% : ancre introuvable, rien n''est modifié', f.fn;
      end if;
      def := replace(def, pair[1], pair[2]);
    end loop;
    defs := defs || def;
  end loop;

  con := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if con is null then raise exception 'content_reports_target_kind_check introuvable, rien n''est modifié'; end if;
  if position('''tc_group''' in con) = 0 and position('''pet_word''::text' in con) = 0 then
    raise exception 'content_reports : ancre pet_word introuvable, rien n''est modifié';
  end if;

  for i in 1 .. coalesce(array_length(defs, 1), 0) loop
    execute defs[i];
  end loop;
  -- Contrainte : on garde TOUS les types en place (prod comme TEST) et on ajoute les deux nouveaux.
  if position('''tc_group''' in con) = 0 then
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(con, '''pet_word''::text', '''pet_word''::text, ''tc_group''::text, ''tc_member''::text');
  end if;
end $patch$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261127150000', 'blocage_notifications_pot') on conflict do nothing;
commit;
