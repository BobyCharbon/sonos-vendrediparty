-- Souvenirs (24.11) : un Présent en liste d'attente (`rsvps.waitlisted`, événement complet) n'est PAS venu : il ne fait
-- pas partie du cercle (prise de photo, story, notification du dévoilement, bulles). Peut-être et organisation : inchangés.
-- Purement additive et rejouable (remplace seulement private.souvenir_circle de 20261124090000).
create or replace function private.souvenir_circle(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select u is not null and private.is_account_active(u) and (
    exists (select 1 from public.events ev where ev.id = e and ev.created_by = u)
    or exists (select 1 from public.event_organizers o where o.event_id = e and o.user_id = u)
    or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = u and r.status in ('yes', 'maybe')
               and not r.waitlisted));
$$;
revoke all on function private.souvenir_circle(uuid, uuid) from public, anon, authenticated;
