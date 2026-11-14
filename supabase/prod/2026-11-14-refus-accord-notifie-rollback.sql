-- PROD, retour arrière de refus_accord_notifie (20261114201500) : decide_join_request comme en 20261112090000
-- (le refus reprend son event_id).
begin;
create or replace function public.decide_join_request(e uuid, person uuid, accept boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare req public.event_join_requests; ev public.events; host text;
begin
  if not private.manages_event(e) then raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501'; end if;
  select * into req from public.event_join_requests q where q.event_id = e and q.user_id = person for update;
  if req.event_id is null or req.status <> 'pending' then raise exception 'Cette demande a déjà été traitée.'; end if;
  select * into ev from public.events where id = e;
  update public.event_join_requests q set status = case when accept then 'accepted' else 'refused' end,
      decided_at = now(), decided_by = auth.uid()
    where q.event_id = e and q.user_id = person;
  select nullif(btrim(display_name), '') into host from public.profiles where id = auth.uid();
  if accept then
    -- Le message d'accord d'abord : la notification d'invitation de la base (même clé) ne part pas en double.
    perform public.queue_notification(person, 'private_invite', e, '✅ C’est bon pour « ' || ev.title || ' »',
      coalesce(host, 'L’organisateur') || ' a accepté ta venue.', 'private_invite:' || e);
    insert into public.event_invites (event_id, user_id, via_group, via_link, invited_by, link_token)
      values (e, person, false, true, req.invited_by, req.token)
    on conflict (event_id, user_id) do update set via_link = true,
      invited_by = coalesce(public.event_invites.invited_by, excluded.invited_by),
      link_token = coalesce(public.event_invites.link_token, excluded.link_token);
    if req.answer <> 'poll' and ev.date_mode <> 'poll' then
      insert into public.rsvps (event_id, user_id, status) values (e, person, req.answer::public.rsvp_status)
      on conflict (event_id, user_id) do nothing;
    end if;
  else
    perform public.queue_notification(person, 'private_invite', e, ev.title,
      'L’organisateur n’a pas pu accepter ta venue cette fois.', 'join_refused:' || e);
  end if;
  return public.event_guest_list(e);
end $$;
revoke all on function public.decide_join_request(uuid, uuid, boolean) from public, anon;
grant execute on function public.decide_join_request(uuid, uuid, boolean) to authenticated;
delete from supabase_migrations.schema_migrations where version = '20261114201500';
commit;
