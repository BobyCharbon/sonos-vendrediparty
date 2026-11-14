-- PROD, annulation_demandes_accord (20261114220000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée : une fonction et un déclencheur sur public.events.
begin;
-- Annulation et demandes d'accord (décision de l'admin, 14.11.2026, recette des notifications) : une personne qui attend
-- l'accord de l'organisateur (event_join_requests « pending », venue par le lien d'un invité) apprend aussi que
-- l'événement est annulé : une seule fois, même interrupteur que les autres annulations (notification_prefs.event_changed),
-- pas pendant une mise en sourdine de l'événement. Elle ne voit pas l'événement : la notification vient SANS lien vers
-- lui (event_id vide, comme le refus de 20261114201500), sinon elle n'est jamais envoyée et ouvrirait une fiche
-- introuvable. Les autres destinataires d'une annulation ne changent pas (notify_event_change). Additive et rejouable.
create or replace function private.tell_waiting_of_cancel() returns trigger
language plpgsql security definer set search_path = '' as $$
declare u uuid;
begin
  if not (old.status = 'published' and new.status = 'cancelled') then return null; end if;
  for u in select q.user_id from public.event_join_requests q
           join public.notification_prefs np on np.user_id = q.user_id and np.event_changed
           where q.event_id = new.id and q.status = 'pending'
             and not exists (select 1 from public.event_mutes m where m.event_id = new.id and m.user_id = q.user_id) loop
    perform public.queue_notification(u, 'event_changed', null, 'Événement annulé',
      '« ' || new.title || ' » est annulé.', 'join_cancelled:' || new.id);
  end loop;
  return null;
end $$;
revoke all on function private.tell_waiting_of_cancel() from public, anon, authenticated;

drop trigger if exists events_tell_waiting_of_cancel on public.events;
create trigger events_tell_waiting_of_cancel after update of status on public.events
  for each row execute function private.tell_waiting_of_cancel();

insert into supabase_migrations.schema_migrations (version, name) values ('20261114220000', 'annulation_demandes_accord') on conflict do nothing;
commit;
