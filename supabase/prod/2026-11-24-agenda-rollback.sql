-- Retour arrière de l'Agenda (2026-11-24-agenda-apply.sql : 20261117140000, 150000, 160000, 170000, 200000, 210000).
-- Retire le job pg_cron, le déclencheur sur member_group_members, toutes les tables et fonctions agenda_* (rendez-vous,
-- calendriers, liens, demandes : leurs données sont PERDUES), retire l'ajout de l'Agenda dans les fonctions partagées
-- (en sens inverse, par le texte exact ajouté : les changements faits depuis sont gardés) et les deux types de
-- signalement (les signalements de ces types sont supprimés, leur cible n'existe plus). Garde la colonne
-- notification_prefs.booking_requests (antérieure, 20261119150000) et les notifications déjà envoyées.
-- À lancer seulement si les Pronos (20261117180000) ne sont PAS en prod : ils étendent la contrainte par 'agenda_link'.
begin;
select cron.unschedule(jobid) from cron.job where jobname = 'agenda-tick';
drop trigger if exists member_group_members_agenda_share on public.member_group_members;

do $$ declare def text;
begin
  -- web_push_allowed et may_receive_push : retire seulement les lignes / mots ajoutés (d'autres ont pu s'insérer à côté).
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''booking_request''' in def) > 0 then
    def := replace(def, $a$
    when 'booking_request' then coalesce(prefs.booking_requests, true)$a$, '');
    def := replace(def, $a$
    when 'booking_cancelled' then coalesce(prefs.booking_requests, true)$a$, '');
    if position('booking_' in def) > 0 then
      raise exception 'private.web_push_allowed : texte de l''Agenda introuvable tel quel, retour arrière à faire à la main';
    end if;
    execute def;
  end if;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''booking_request''' in def) > 0 then
    def := replace(def, ' ''booking_request'', ''booking_cancelled'',', '');
    if position('booking_' in def) > 0 then
      raise exception 'private.may_receive_push : texte de l''Agenda introuvable tel quel, retour arrière à faire à la main';
    end if;
    execute def;
  end if;
  -- Les trois suivantes : retire le bloc ajouté seul (texte exact), sans toucher l'ancre ni ce qui a été ajouté depuis.
  def := pg_get_functiondef('private.report_snapshot(text, text, uuid)'::regprocedure);
  if position('''booking_request''' in def) > 0 then
    def := replace(def, $a$  elsif p_kind = 'booking_request' then
    return (select jsonb_build_object('owner', null, 'text', concat_ws(E'\n', concat_ws(' ', k.first_name, k.last_name), k.message),
        'at', k.created_at, 'place', 'Demande de rendez-vous · lien « ' || l.name || ' »', 'link_id', l.id)
      from private.agenda_bookings k join private.agenda_links l on l.id = k.link_id
      where k.id = uid and k.owner_id = viewer and k.wiped_at is null);
$a$, '');
    if position('''booking_request''' in def) > 0 then
      raise exception 'private.report_snapshot : texte de l''Agenda introuvable tel quel, retour arrière à faire à la main';
    end if;
    execute def;
  end if;
  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''booking_request''' in def) > 0 then
    def := replace(def, $a$                        when new.target_kind = 'booking_request' then 'une demande de rendez-vous'
                        when new.target_kind = 'agenda_link' then 'un lien de disponibilités'
$a$, '');
    if position('''booking_request''' in def) > 0 then
      raise exception 'private.notify_new_report : texte de l''Agenda introuvable tel quel, retour arrière à faire à la main';
    end if;
    execute def;
  end if;
  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position('''booking_request''' in def) > 0 then
    def := replace(def, $a$  elsif r.target_kind = 'booking_request' then
    delete from private.agenda_bookings where id = uid;
  elsif r.target_kind = 'agenda_link' then
    update private.agenda_links set stopped_at = coalesce(stopped_at, now()), booking_enabled = false, display_name = 'Nom masqué'
      where id = uid;
$a$, '');
    if position('''booking_request''' in def) > 0 then
      raise exception 'private.moderation_hide : texte de l''Agenda introuvable tel quel, retour arrière à faire à la main';
    end if;
    execute def;
  end if;
end $$;

delete from public.content_reports where target_kind in ('booking_request', 'agenda_link');
do $$ declare def text;
begin
  select pg_get_constraintdef(oid) into def from pg_constraint
   where conrelid = 'public.content_reports'::regclass and conname = 'content_reports_target_kind_check';
  if position(', ''booking_request''::text, ''agenda_link''::text' in def) > 0 then
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, ', ''booking_request''::text, ''agenda_link''::text', '');
  end if;
end $$;

drop table if exists public.agenda_items, public.agenda_calendars, public.agenda_prefs,
  private.agenda_bookings, private.agenda_ip_hits, private.agenda_sender_blocks, private.agenda_links, private.agenda_busy,
  private.agenda_group_shares, private.agenda_sharing, private.agenda_handles, private.agenda_settings cascade;
do $$ declare f regprocedure;
begin
  for f in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname in ('public', 'private') and p.proname like 'agenda\_%' loop
    execute 'drop function if exists ' || f || ' cascade';
  end loop;
end $$;

delete from supabase_migrations.schema_migrations where version = '20261124090000';
delete from supabase_migrations.schema_migrations where version = '20261117210000';
delete from supabase_migrations.schema_migrations where version = '20261117200000';
delete from supabase_migrations.schema_migrations where version = '20261117170000';
delete from supabase_migrations.schema_migrations where version = '20261117160000';
delete from supabase_migrations.schema_migrations where version = '20261117150000';
delete from supabase_migrations.schema_migrations where version = '20261117140000';
notify pgrst, 'reload schema';
commit;
