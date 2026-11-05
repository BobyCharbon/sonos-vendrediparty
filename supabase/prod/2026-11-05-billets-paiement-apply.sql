-- PROD, billets_paiement (20261105121000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration. Rejouable.
-- Prérequis en prod : 2026-11-04-billets-remis-apply.sql (20261104233000). Tout ou rien (begin/commit).
-- Effet : « Pas reçu » / « payé » décoché retire le billet remis PAR CE PAIEMENT ; un co-organisateur active ou coupe
-- l'option « Billets QR » même après publication. Les billets déjà remis par un paiement avant cette migration sont
-- considérés comme remis à la main (issued_by_payment = false) : ils ne repartent pas.
begin;
-- Billets QR et paiements (plan « bêta → main » du 04.11) :
-- 1. Un billet REMIS PAR UN PAIEMENT (« Reçu » ou « payé » coché) repart quand ce paiement est annulé (« Pas reçu »,
--    « payé » décoché, quel que soit le chemin) : event_tickets.issued_by_payment le distingue d'un billet remis à la
--    main par l'organisateur, qui, lui, reste. ticket_view l'indique à l'écran de l'organisateur (message clair).
-- 2. Un co-organisateur active ou désactive l'option « Billets QR » même après publication : exception ciblée dans
--    la garde des événements (public.guard_event), quand SEULE l'option change et que la personne la gère
--    (private.can_manage_tickets_option : organisateur, co-organisateur, admin, droit events.manage_all).
-- Purement additif et rejouable. Prérequis : 20261104233000 (event_tickets_issued).

-- --------------------------------------------------------------------------------------------------------------
-- 1. Billet remis par un paiement
-- --------------------------------------------------------------------------------------------------------------
alter table public.event_tickets add column if not exists issued_by_payment boolean not null default false;

-- Place payée : le billet est remis et marqué « par le paiement » (repris de 20261104233000).
create or replace function private.ticket_paid_issues() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.paid and not coalesce(old.paid, false) and new.issued_at is null then
    new.issued_at := now();
    new.issued_by := coalesce(new.paid_by, auth.uid());
    new.issued_by_payment := true;
  end if;
  return new;
end $$;

-- Paiement annulé : le billet remis par ce paiement repart. Un billet remis (ou retiré) à la main n'est plus « par le
-- paiement ». Déclencheur nommé après ticket_paid_issues : il passe après lui (ordre alphabétique des BEFORE).
create or replace function private.ticket_unpaid_revokes() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.paid and not new.paid and old.issued_by_payment and new.issued_at is not distinct from old.issued_at then
    new.issued_at := null;
    new.issued_by := null;
    new.issued_by_payment := false;
  elsif new.issued_at is null then
    new.issued_by_payment := false;
  elsif old.issued_at is null and not (new.paid and not old.paid) then
    new.issued_by_payment := false;  -- remis à la main (issue_event_ticket, remise à tous)
  end if;
  return new;
end $$;
revoke all on function private.ticket_unpaid_revokes() from public, anon, authenticated;
drop trigger if exists ticket_unpaid_revokes on public.event_tickets;
create trigger ticket_unpaid_revokes before update on public.event_tickets for each row
  execute function private.ticket_unpaid_revokes();

-- Ce que voit l'organisateur : + issued_by_payment (repris de 20261104233000).
create or replace function private.ticket_view(e uuid, member uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'user_id', p.id, 'display_name', p.display_name, 'avatar_url', p.avatar_url,
    'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
    'checked_in_at', t.checked_in_at, 'paid', coalesce(t.paid, false),
    'pay_pending', coalesce(not t.paid and t.pay_declared_at is not null, false), 'pay_declared_at', t.pay_declared_at,
    'price_chf', (select price_chf from public.events where id = e),
    'issued', t.issued_at is not null, 'issued_at', t.issued_at,
    'issued_by_payment', coalesce(t.issued_by_payment, false),
    'tickets_enabled', coalesce((select tickets_enabled from public.events where id = e), false))
  from public.profiles p
  left join public.rsvps r on r.event_id = e and r.user_id = p.id
  left join public.event_tickets t on t.event_id = e and t.user_id = p.id
  where p.id = member;
$$;
revoke all on function private.ticket_view(uuid, uuid) from public, anon, authenticated;

-- « Pas reçu » : le participant apprend aussi que son billet est retiré (repris de 20261103140000, texte complété).
create or replace function public.confirm_ticket_payment(e uuid, member uuid, received boolean) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  ev public.events;
  who text;
  revoked boolean;
begin
  perform private.require_cashier(e);
  if not exists (select 1 from public.rsvps where event_id = e and user_id = member) then
    raise exception 'Cette personne n''a pas répondu à l''événement.' using errcode = '22023';
  end if;
  select * into ev from public.events where id = e;
  perform private.ensure_ticket(e, member);
  select t.paid and t.issued_by_payment and t.issued_at is not null into revoked
    from public.event_tickets t where t.event_id = e and t.user_id = member;
  revoked := coalesce(revoked, false) and not received;
  update public.event_tickets
    set paid = received, paid_at = case when received then now() end, paid_by = case when received then auth.uid() end,
        pay_declared_at = case when received then pay_declared_at end
    where event_id = e and user_id = member;
  who := coalesce(private.member_name(auth.uid()), 'L''organisateur');
  perform public.queue_notification(member, 'ticket_pay_confirmed', e, ev.title,
    case when received then who || ' a bien reçu ton paiement : ta place est payée ✓'
         when revoked then who || ' n''a pas reçu ton paiement : ton billet est retiré en attendant. Vérifie-le, puis touche à nouveau « J''ai payé ».'
         else who || ' n''a pas reçu ton paiement : vérifie-le, puis touche à nouveau « J''ai payé ».' end,
    null, jsonb_build_object('received', received));
  return private.ticket_view(e, member);
end $$;
revoke all on function public.confirm_ticket_payment(uuid, uuid, boolean) from public, anon;
grant execute on function public.confirm_ticket_payment(uuid, uuid, boolean) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 2. Option « Billets QR » après publication : exception ciblée dans public.guard_event (complétée en place, une fois)
-- --------------------------------------------------------------------------------------------------------------
do $$
declare
  def text := pg_get_functiondef('public.guard_event()'::regprocedure);
  anchor text := 'if new.status = ''cancelled'' then return new; end if;';
begin
  if position('can_manage_tickets_option' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then
    raise exception 'guard_event : branche « cancelled » introuvable, exception des billets QR non ajoutée';
  end if;
  execute replace(def, anchor, anchor || E'\n    -- Billets QR (04.11) : seule l''option change → organisateurs et co-organisateurs, même publié.'
    || E'\n    if (to_jsonb(new) - ''tickets_enabled'' - ''updated_at'') = (to_jsonb(old) - ''tickets_enabled'' - ''updated_at'')'
    || E'\n       and private.can_manage_tickets_option(new.id) then return new; end if;');
end $$;


insert into supabase_migrations.schema_migrations (version, name) values ('20261105121000', 'billets_paiement')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
