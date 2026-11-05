-- PROD, retour arrière de billets_paiement (20261105121000) : un paiement annulé ne retire plus le billet, l'option
-- « Billets QR » d'un événement publié redevient réservée à qui peut le modifier. Fonctions reprises telles qu'avant
-- (20261104233000, 20261103140000) ; la colonne issued_by_payment est supprimée. Tout ou rien.
begin;
drop trigger if exists ticket_unpaid_revokes on public.event_tickets;
drop function if exists private.ticket_unpaid_revokes();

create or replace function private.ticket_paid_issues() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.paid and not coalesce(old.paid, false) and new.issued_at is null then
    new.issued_at := now();
    new.issued_by := coalesce(new.paid_by, auth.uid());
  end if;
  return new;
end $$;

create or replace function private.ticket_view(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'user_id', p.id, 'display_name', p.display_name, 'avatar_url', p.avatar_url,
    'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
    'checked_in_at', t.checked_in_at, 'paid', coalesce(t.paid, false),
    'pay_pending', coalesce(not t.paid and t.pay_declared_at is not null, false), 'pay_declared_at', t.pay_declared_at,
    'price_chf', (select price_chf from public.events where id = e),
    'issued', t.issued_at is not null, 'issued_at', t.issued_at,
    'tickets_enabled', coalesce((select tickets_enabled from public.events where id = e), false))
  from public.profiles p
  left join public.rsvps r on r.event_id = e and r.user_id = p.id
  left join public.event_tickets t on t.event_id = e and t.user_id = p.id
  where p.id = member;
$$;
revoke all on function private.ticket_view(uuid, uuid) from public, anon, authenticated;

create or replace function public.confirm_ticket_payment(e uuid, member uuid, received boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  ev public.events;
  who text;
begin
  perform private.require_cashier(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  select * into ev from public.events where id = e;
  perform private.ensure_ticket(e, member);
  update public.event_tickets
    set paid = received, paid_at = case when received then now() end, paid_by = case when received then auth.uid() end,
        pay_declared_at = case when received then pay_declared_at end
    where event_id = e and user_id = member;
  who := coalesce(private.member_name(auth.uid()), 'L''organisateur');
  perform public.queue_notification(member, 'ticket_pay_confirmed', e, ev.title,
    case when received then who || ' a bien reçu ton paiement : ta place est payée ✓'
         else who || ' n''a pas reçu ton paiement : vérifie-le, puis touche à nouveau « J''ai payé ».' end,
    null, jsonb_build_object('received', received));
  return private.ticket_view(e, member);
end $$;
revoke all on function public.confirm_ticket_payment(uuid, uuid, boolean) from public, anon;
grant execute on function public.confirm_ticket_payment(uuid, uuid, boolean) to authenticated;

-- Garde des événements : l'exception des billets QR est retirée (fonction réécrite sans les 3 lignes ajoutées).
do $$
declare
  def text := pg_get_functiondef('public.guard_event()'::regprocedure);
  added text := E'\n    -- Billets QR (04.11) : seule l''option change → organisateurs et co-organisateurs, même publié.'
    || E'\n    if (to_jsonb(new) - ''tickets_enabled'' - ''updated_at'') = (to_jsonb(old) - ''tickets_enabled'' - ''updated_at'')'
    || E'\n       and private.can_manage_tickets_option(new.id) then return new; end if;';
begin
  if position(added in def) > 0 then execute replace(def, added, ''); end if;
end $$;

alter table public.event_tickets drop column if exists issued_by_payment;
delete from supabase_migrations.schema_migrations where version = '20261105121000';
commit;

notify pgrst, 'reload schema';
