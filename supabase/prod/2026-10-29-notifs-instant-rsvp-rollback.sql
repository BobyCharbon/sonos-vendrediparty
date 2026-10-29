-- PROD, retour arrière de 20261029140000 : envoi à nouveau par la seule tâche de chaque minute, et une notification
-- par réponse (version d'origine de notify_rsvp). Les réponses encore retenues sont envoyées avant la suppression.
begin;
update private.rsvp_digest set first_at = now() - interval '6 minutes';
select private.flush_rsvp_digests();
select cron.unschedule('rsvp-digest');
drop trigger if exists notifications_kick_push on public.notifications;
drop function if exists private.kick_push();
drop function if exists private.flush_rsvp_digests();
drop function if exists private.rsvp_phrase(text, public.rsvp_status);
drop table if exists private.rsvp_digest;
drop table if exists private.push_kick;
create or replace function public.notify_rsvp() returns trigger
language plpgsql security definer set search_path to 'public' as $function$
declare ev events; who text; u uuid;
begin
  if tg_op = 'UPDATE' and new.status = old.status then return null; end if;
  -- Réponses créées automatiquement (clôture d'un sondage) : pas de notif
  if auth.uid() is distinct from new.user_id then return null; end if;
  select * into ev from events where id = new.event_id;
  select display_name into who from profiles where id = new.user_id;
  for u in select x from (select ev.created_by x union select user_id from event_organizers where event_id = ev.id) o
           join notification_prefs np on np.user_id = o.x where np.rsvp_mine loop
    perform queue_notification(u, 'rsvp', ev.id, ev.title,
      who || case new.status when 'yes' then ' vient' when 'maybe' then ' viendra peut-être' else ' ne vient pas' end);
  end loop;
  return null;
end $function$;
delete from supabase_migrations.schema_migrations where version = '20261029140000';
commit;
