-- PROD, retour arrière de moderation (20261104200000) : plus de filtre, de signalements, de sanctions ni de CGU ; le
-- blocage revient aux seuls messages directs (la table public.direct_blocks et ses lignes restent). Les signalements,
-- sanctions et acceptations des CGU sont SUPPRIMÉS. Une suspension en cours n'est pas levée : réintégrer le compte à la
-- main (Administration › Membres) avant si besoin. Fonctions complétées en place : la partie ajoutée est retirée. Tout ou rien.
begin;

select cron.unschedule('moderation-lift') where exists (select 1 from cron.job where jobname = 'moderation-lift');

-- Déclencheurs
drop trigger if exists group_messages_moderation on public.group_messages;
drop trigger if exists group_messages_unmention on public.group_messages;
drop trigger if exists direct_messages_moderation on public.direct_messages;
drop trigger if exists messages_moderation on public.messages;
drop trigger if exists messages_unmention on public.messages;
drop trigger if exists profiles_moderation on public.profiles;
drop trigger if exists member_groups_moderation on public.member_groups;
drop trigger if exists group_invitations_block on private.group_invitations;
drop trigger if exists event_invites_block on public.event_invites;
drop trigger if exists notifications_blocked on public.notifications;
drop trigger if exists content_reports_notify on public.content_reports;

drop policy if exists "modérateurs retirent une photo signalée" on storage.objects;

-- Fonctions complétées en place : on retire ce qui a été ajouté.
do $$
declare def text;
begin
  def := pg_get_functiondef('public.member_card(uuid)'::regprocedure);
  if position('direct_blocks' in def) > 0 then
    def := regexp_replace(def, E'\\n  if p.id <> me and exists \\(select 1 from public.direct_blocks.*?\\n  end if;', '', 's');
    def := replace(def, E'\n    ''blocked'', exists (select 1 from public.direct_blocks k where k.user_id = me and k.blocked_id = p.id),', '');
    execute def;
  end if;
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  def := replace(def, E'\n    when ''report_new'' then coalesce(prefs.moderation_reports, true)', '');
  def := replace(def, E'\n    when ''moderation_notice'' then coalesce(prefs.moderation_notices, true)', '');
  execute def;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  execute replace(def, '''direct_message'', ''moderation_notice'', ''report_new'')', '''direct_message'')');
end $$;

drop function if exists public.moderation_queue(text, integer);
drop function if exists public.moderation_act(uuid, text, text, integer);
drop function if exists public.moderation_lift(uuid);
drop function if exists private.moderation_hide(public.content_reports);
drop function if exists private.lift_expired_suspensions();
drop function if exists private.require_moderator();
drop function if exists public.report_content(text, text, text, text);
drop function if exists public.my_reports();
drop function if exists private.notify_new_report();
drop function if exists private.report_snapshot(text, text, uuid);
drop function if exists private.report_snapshot_pet(text, text, uuid);
drop function if exists private.moderation_hide_pet(text, text);
drop function if exists private.moderate_message();
drop function if exists private.unmention_blocked();
drop function if exists private.moderate_profile_name();
drop function if exists private.moderate_group_name();
drop function if exists private.drop_blocked_notification();
drop function if exists private.guard_invite_block();
drop function if exists public.my_blocks();
drop function if exists public.set_block(uuid, boolean);
drop function if exists public.blocked_with(uuid);
drop function if exists private.blocked_either(uuid, uuid);
drop function if exists public.set_moderation_settings(text, boolean);
drop function if exists public.accept_terms(text);
drop function if exists public.my_terms();
drop function if exists public.moderation_public_info();
drop function if exists private.require_terms(uuid);
drop function if exists private.terms_accepted(uuid);
drop function if exists public.moderation_check(text, text);
drop function if exists private.moderate_text(text, text);
drop function if exists private.moderation_verdict(text, text);
drop function if exists private.mod_mask_insults(text);
drop function if exists private.mod_hit(text, text);
drop function if exists private.mod_regex(text, boolean);
drop function if exists private.mod_merged(text);
drop function if exists private.mod_clean(text);
drop function if exists private.mod_normalize(text);

drop table if exists public.moderation_sanctions;
drop table if exists public.content_reports;
drop table if exists public.terms_acceptances;
drop table if exists private.moderation_settings;
drop table if exists private.moderation_patterns;

alter table public.notification_prefs drop column if exists moderation_reports;
alter table public.notification_prefs drop column if exists moderation_notices;

delete from public.role_permissions where perm = 'moderation.reports';
delete from public.permissions where key = 'moderation.reports';
delete from private.one_time_changes where name = 'moderation_reports_2026_11_04';
comment on table public.direct_blocks is null;

delete from supabase_migrations.schema_migrations where version = '20261104200000';
commit;

notify pgrst, 'reload schema';
