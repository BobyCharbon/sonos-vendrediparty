-- Recherche des Discussions : « Événements » (demande de l'admin du 19.11). La liste ne montre une discussion
-- d'événement qu'après son premier message ; la recherche trouve aussi MES événements encore sans message (organisés,
-- co-organisés, invité, Présent / Peut-être), pour y lancer la discussion. Même fenêtre que la liste (fini depuis moins
-- de 7 jours, ou à venir), toujours sous can_see_event. Additive et rejouable.

create or replace function public.chat_event_search(q text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); qq text := private.fold(btrim(coalesce(q, ''))); out jsonb;
begin
  if me is null then return '[]'::jsonb; end if;
  if char_length(qq) < 2 then return '[]'::jsonb; end if;
  select coalesce(jsonb_agg(x.c order by x.upcoming desc, x.starts_at nulls last), '[]'::jsonb) into out
  from (
    select ev.starts_at, coalesce(coalesce(ev.ends_at, ev.starts_at + interval '4 hours') >= now(), true) as upcoming,
      jsonb_build_object(
        'kind', 'event', 'id', ev.id, 'title', ev.title, 'photo', ev.cover_url, 'emoji', null, 'color', null,
        'user_id', null, 'event_start', ev.starts_at,
        'event_past', coalesce(coalesce(ev.ends_at, ev.starts_at + interval '4 hours') < now(), false),
        'last', null, 'unread', 0, 'mention', false, 'marked_unread', false, 'pinned_at', null, 'archived', false,
        'notify', 'all', 'muted_until', null, 'request', null, 'seen_by_other', null,
        'members', (select count(*) from public.rsvps r where r.event_id = ev.id and r.status in ('yes', 'maybe')),
        'is_vp', false, 'blocked', false) as c
    from (select e.id from public.events e where e.created_by = me
          union select o.event_id from public.event_organizers o where o.user_id = me
          union select i.event_id from public.event_invites i where i.user_id = me
          union select r.event_id from public.rsvps r where r.user_id = me and r.status in ('yes', 'maybe')) mine
    join public.events ev on ev.id = mine.id
    where position(qq in private.fold(coalesce(ev.title, ''))) > 0
      and (ev.starts_at is null or coalesce(ev.ends_at, ev.starts_at) > now() - interval '7 days')
      and public.can_see_event(ev.id)
    order by 2 desc, ev.starts_at nulls last
    limit 10) x;
  return out;
end $$;

revoke all on function public.chat_event_search(text) from public, anon;
grant execute on function public.chat_event_search(text) to authenticated;
