-- PROD, retour arrière de paiement_en_ligne_sans_declaration (20261116190000) : la fonction d'avant, telle qu'en prod.
begin;
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
end $function$

;

delete from supabase_migrations.schema_migrations where version = '20261116190000';
notify pgrst, 'reload schema';
commit;
