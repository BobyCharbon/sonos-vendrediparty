-- Sondages de la fiche (demande de l'admin, 19.11.2026) : on ne vote qu'après avoir répondu Présent ou Peut-être ;
-- l'organisation de l'événement (et les admins / co-admins) vote toujours, comme pour la discussion
-- (private.event_chat_member). Sondage de dates (date_mode = 'poll') : pas de « Présent » possible, rien ne change.
-- Retirer son vote reste possible. Insertions du serveur (sans auth.uid()) inchangées. Purement additif et rejouable.
create or replace function private.poll_vote_presence() returns trigger
language plpgsql security definer set search_path = '' as $$
declare e uuid; mode text;
begin
  if auth.uid() is null then return new; end if;
  select p.event_id into e from public.polls p where p.id = new.poll_id;
  if e is null then return new; end if;
  select ev.date_mode into mode from public.events ev where ev.id = e;
  if mode = 'fixed' and not private.event_chat_member(e, auth.uid()) then
    raise exception 'present_required: Réponds Présent ou Peut-être pour voter.' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.poll_vote_presence() from public, anon, authenticated;

drop trigger if exists poll_votes_presence on public.poll_votes;
create trigger poll_votes_presence before insert on public.poll_votes
  for each row execute function private.poll_vote_presence();
