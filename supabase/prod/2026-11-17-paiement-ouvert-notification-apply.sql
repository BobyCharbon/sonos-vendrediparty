-- PROD, paiement_ouvert_notification (20261117135000) : migration supabase/migrations/20261117135000_paiement_ouvert_notification.sql telle quelle (mise en prod du 19.11).
-- Additive et rejouable. Tout ou rien.
begin;
-- « Paiement ouvert » prévient les participants (demande de l'admin du 17.11.2026) : quand l'organisateur allume
-- « Paiement ouvert » (events.payment_open, 20261116130000), chaque participant « Présent » (pas en liste d'attente)
-- qui n'a pas encore payé ni noté « J'ai payé » reçoit « 💳 Le paiement est ouvert ». Texte générique (place, billet,
-- réservation…). Interrupteur : celui des changements d'événement (notification_prefs.event_changed) ; « Ne plus
-- suivre » l'événement (event_mutes) aussi. Jamais l'organisateur qui l'allume ; jamais pour « Sur place » ; une seule
-- fois par personne et par événement (éteindre puis rallumer ne renvoie rien). L'organisateur choisit sur l'événement
-- (events.payment_open_notify, « Prévenir les participants à l'ouverture », allumé par défaut) ; éteint : rien ne part.
-- Purement additif et rejouable.

alter table public.events add column if not exists payment_open_notify boolean not null default true;

create or replace function private.notify_payment_open() returns trigger
language plpgsql security definer set search_path = '' as $$
declare u uuid;
begin
  if not new.payment_open_notify or new.status <> 'published' or coalesce(new.price_chf, 0) <= 0 or coalesce(new.payment_mode, '') = 'on_site' then
    return null;
  end if;
  for u in
    select r.user_id from public.rsvps r
    join public.notification_prefs np on np.user_id = r.user_id and np.event_changed
    where r.event_id = new.id and r.status = 'yes' and not r.waitlisted
      and r.user_id is distinct from auth.uid()
      and not exists (select 1 from public.event_mutes m where m.event_id = new.id and m.user_id = r.user_id)
      and not exists (select 1 from public.event_tickets t where t.event_id = new.id and t.user_id = r.user_id
                        and (t.paid or t.pay_declared_at is not null))
  loop
    perform public.queue_notification(u, 'event_changed', new.id, '💳 Le paiement est ouvert',
      '« ' || new.title || ' » : tu peux maintenant payer ta place.', 'payment_open:' || new.id || ':' || u);
  end loop;
  return null;
end $$;
revoke all on function private.notify_payment_open() from public, anon, authenticated;

drop trigger if exists events_payment_open_notify on public.events;
create trigger events_payment_open_notify after update of payment_open on public.events
  for each row when (new.payment_open and not old.payment_open) execute function private.notify_payment_open();

insert into supabase_migrations.schema_migrations (version, name) values ('20261117135000', 'paiement_ouvert_notification') on conflict do nothing;
commit;
