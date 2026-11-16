-- Paiement « pas encore ouvert » (demande de l'admin du 16.11.2026) : l'organisateur prépare tout (mode, lien, précision)
-- et coche « Paiement ouvert » quand c'est prêt ; avant, les invités voient « Paiement bientôt possible », sans bouton, et
-- la base refuse « J'ai payé » (annuler une déclaration d'avant reste possible). Allumé par défaut : rien ne change pour
-- les événements existants. Purement additif et rejouable.

alter table public.events add column if not exists payment_open boolean not null default true;

CREATE OR REPLACE FUNCTION public.event_pay_info(e uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
  -- Paiement pas encore ouvert : aucun lien pour les invités (l'organisateur voit tout pour préparer).
  if not ev.payment_open and not (private.can_scan(e) or private.can_take_payments(e)) then return null; end if;
  select * into pay from public.tc_payment where user_id = ev.created_by;
  return jsonb_build_object(
    'organizer_id', ev.created_by,
    'organizer_name', (select display_name from public.profiles where id = ev.created_by),
    'amount', ev.price_chf, 'payment_info', ev.payment_info,
    'mode', ev.payment_mode, 'open', ev.payment_open, 'payment_url', ev.payment_url,
    'iban', pay.iban, 'holder', pay.holder, 'links', coalesce(pay.links, '{}'::jsonb), 'note', pay.note,
    'reference', left('Party · ' || ev.title, 140));
end $function$;

CREATE OR REPLACE FUNCTION public.declare_ticket_payment(e uuid, declared boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
  -- Sur place : on ne note plus « J'ai payé », mais on annule toujours une déclaration d'avant le changement de mode.
  if declared and not ev.payment_open then
    raise exception 'Le paiement n''est pas encore ouvert : l''organisateur l''ouvrira bientôt.' using errcode = '22023';
  end if;
  if declared and ev.payment_mode = 'on_site' then
    raise exception 'Cet événement se paie sur place : rien à noter dans Party.' using errcode = '22023';
  end if;
  t := private.ensure_ticket(e, me);
  if t.paid then return public.my_event_ticket(e); end if;
  update public.event_tickets set pay_declared_at = case when declared then coalesce(pay_declared_at, now()) end
    where event_id = e and user_id = me;
  if declared and t.pay_declared_at is null then
    who := coalesce(private.member_name(me), 'Quelqu''un');
    for manager in select private.event_managers(e) loop
      perform public.queue_notification(manager, 'ticket_pay_declared', e, ev.title,
        who || case when ev.payment_mode = 'online' then ' dit avoir payé sa place en ligne (' else ' dit avoir payé sa place (' end
          || trim_scale(ev.price_chf)::text || ' CHF) : confirme quand tu l''as vérifié.',
        null, jsonb_build_object('member', me));
    end loop;
  end if;
  return public.my_event_ticket(e);
end $function$;

revoke all on function public.event_pay_info(uuid), public.declare_ticket_payment(uuid, boolean) from public, anon;
grant execute on function public.event_pay_info(uuid), public.declare_ticket_payment(uuid, boolean) to authenticated;

notify pgrst, 'reload schema';
