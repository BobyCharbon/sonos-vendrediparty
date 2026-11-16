-- Retour arrière de paiement_mode (20261115120000) : fonctions d'avant, contraintes et colonnes retirées
-- (les modes et liens choisis entre-temps sont perdus ; le prix et la précision restent).
begin;
create or replace function public.event_pay_info(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  ev public.events;
  pay public.tc_payment;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'Événement introuvable' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  if coalesce(ev.price_chf, 0) <= 0 then return null; end if;
  if not (private.can_scan(e) or private.can_take_payments(e) or exists (select 1 from public.rsvps where event_id = e and user_id = auth.uid() and status = 'yes')) then
    return null;
  end if;
  select * into pay from public.tc_payment where user_id = ev.created_by;
  return jsonb_build_object(
    'organizer_id', ev.created_by,
    'organizer_name', (select display_name from public.profiles where id = ev.created_by),
    'amount', ev.price_chf, 'payment_info', ev.payment_info,
    'iban', pay.iban, 'holder', pay.holder, 'links', coalesce(pay.links, '{}'::jsonb), 'note', pay.note,
    'reference', left('Party · ' || ev.title, 140));
end $$;

create or replace function public.declare_ticket_payment(e uuid, declared boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  ev public.events;
  t public.event_tickets;
  who text;
  manager uuid;
begin
  if me is null then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if not exists (select 1 from public.rsvps where event_id = e and user_id = me and status = 'yes' and not waitlisted) then
    raise exception 'Seuls les présents paient leur place.' using errcode = '22023';
  end if;
  select * into ev from public.events where id = e;
  if coalesce(ev.price_chf, 0) <= 0 then raise exception 'Cet événement est gratuit.' using errcode = '22023'; end if;
  t := private.ensure_ticket(e, me);
  if t.paid then return public.my_event_ticket(e); end if;
  update public.event_tickets set pay_declared_at = case when declared then coalesce(pay_declared_at, now()) end
    where event_id = e and user_id = me;
  if declared and t.pay_declared_at is null then
    who := coalesce(private.member_name(me), 'Quelqu''un');
    for manager in select private.event_managers(e) loop
      perform public.queue_notification(manager, 'ticket_pay_declared', e, ev.title,
        who || ' dit avoir payé sa place (' || trim_scale(ev.price_chf)::text || ' CHF) : confirme quand tu l''as reçu.',
        null, jsonb_build_object('member', me));
    end loop;
  end if;
  return public.my_event_ticket(e);
end $$;

alter table public.events drop constraint if exists events_payment_online_url_check;
alter table public.events drop constraint if exists events_payment_url_check;
alter table public.events drop constraint if exists events_payment_mode_check;
alter table public.events drop column if exists payment_url;
alter table public.events drop column if exists payment_mode;
delete from supabase_migrations.schema_migrations where version = '20261115120000';
commit;
notify pgrst, 'reload schema';
