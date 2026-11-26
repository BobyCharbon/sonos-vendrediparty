-- Retour arrière de 2026-11-26-pot-filtre-paiement-purge-apply.sql (20261126160000) : définitions d'avant, identiques en
-- TEST et en PROD le 26.11 (lues en lecture seule), et déclencheur du profil de paiement retiré.
begin;
drop trigger if exists tc_payment_moderation on public.tc_payment;

create or replace function private.moderate_tc_text() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if tg_table_name in ('tc_groups', 'tc_members') then
    if tg_op = 'INSERT' or new.name is distinct from old.name then
      new.name := private.item_text_verdict(new.name, 'Nom');
    end if;
  elsif tg_table_name = 'tc_expenses' then
    if tg_op = 'INSERT' or new.title is distinct from old.title then
      new.title := private.item_text_verdict(new.title, 'Dépense');
    end if;
    if coalesce(new.note, '') <> '' and (tg_op = 'INSERT' or new.note is distinct from old.note) then
      new.note := private.item_text_verdict(new.note, 'Note');
    end if;
  end if;
  return new;
end $$;
revoke all on function private.moderate_tc_text() from public, anon, authenticated;

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

create or replace function private.expire_chat_photos() returns integer
language sql security definer set search_path = '' as $$
  with gone as (update public.group_messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1),
       gone_direct as (update public.direct_messages
                set body = case when btrim(body) <> '' then body when audio_path is not null then '🎤 Message vocal expiré'
                                else '📷 Photo expirée' end,
                    photo_path = null, audio_path = null
                where (photo_path is not null or audio_path is not null) and created_at < now() - interval '90 days' returning 1)
  select ((select count(*) from gone) + (select count(*) from gone_direct))::int;
$$;

delete from supabase_migrations.schema_migrations where version = '20261126160000';
commit;
