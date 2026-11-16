-- PROD, agenda_votes_sondage (20261115230000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée : deux fonctions de l'agenda abonné (une condition de plus).
begin;
-- Agenda abonné : les votes de dates ne comptent que pendant le SONDAGE (15.11.2026). Depuis caf0e37, fixer la date par
-- le formulaire garde les créneaux et leurs votes (cachés, pour pouvoir repasser en « Date à définir »). Un vote Oui pour
-- une date ne dit pas « je viens » à une autre date : sans cette règle, tous ceux qui avaient voté Oui / Si besoin
-- quelque part voyaient l'événement CONFIRMÉ dans leur agenda (et « déjà ajouté ») sans avoir répondu.
-- Date fixée : seuls l'ajout de la personne et sa réponse Présent / Peut-être comptent (le bouton « Fixer » transforme
-- déjà les votes de la date retenue en réponses). Repassé en sondage, les votes comptent de nouveau.
-- Purement additif et rejouable : mêmes fonctions qu'en 20261111110000, une condition de plus.

create or replace function private.feed_includes(uid uuid, e uuid) returns boolean
language sql stable set search_path = '' as $$
  select not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = uid and r.status = 'no')
     and (exists (select 1 from public.calendar_feed_events c where c.user_id = uid and c.event_id = e)
          or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = uid and r.status in ('yes', 'maybe'))
          or exists (select 1 from public.date_votes v join public.date_options o on o.id = v.option_id
                     join public.events x on x.id = o.event_id and x.date_mode = 'poll'
                     where o.event_id = e and v.user_id = uid and v.vote in ('yes', 'if_needed')));
$$;
revoke all on function private.feed_includes(uuid, uuid) from public, anon, authenticated;

create or replace function public.calendar_feed(t text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare f public.calendar_feeds; out jsonb := '[]'; ev public.events; mine text; voted jsonb; still boolean;
  claims text := current_setting('request.jwt.claims', true); sub text := current_setting('request.jwt.claim.sub', true);
begin
  if t is null or length(t) <> 36 then return null; end if;
  select * into f from public.calendar_feeds where token = t;
  if not found then return null; end if;
  -- Confidentialité : l'agenda ne montre JAMAIS plus que ce que Party montre à la personne (public.can_see_event avec ses
  -- yeux à elle, à chaque lecture) : retirée du groupe ou des invités, compte suspendu, événement privé ou brouillon → dehors.
  perform set_config('request.jwt.claims', json_build_object('sub', f.user_id, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', f.user_id::text, true);
  update public.calendar_feeds set read_at = now() where token = t and (read_at is null or read_at < now() - interval '10 minutes');
  for ev in
    select x.* from public.events x
    where x.id in (select c.event_id from public.calendar_feed_events c where c.user_id = f.user_id
                   union select r.event_id from public.rsvps r where r.user_id = f.user_id and r.status in ('yes', 'maybe')
                   -- Votes : seulement pendant le sondage (date fixée : créneaux et votes cachés, gardés pour un retour).
                   union select o.event_id from public.date_votes v join public.date_options o on o.id = v.option_id
                         join public.events p on p.id = o.event_id and p.date_mode = 'poll'
                         where v.user_id = f.user_id and v.vote in ('yes', 'if_needed'))
      and (x.date_mode <> 'fixed' or x.starts_at is null or coalesce(x.ends_at, x.starts_at) > now() - interval '60 days')
    order by coalesce(x.starts_at, x.updated_at) desc limit 150
  loop
    still := public.can_see_event(ev.id) and ev.status = 'published';
    if not still then continue; end if;  -- plus visible : rien n'en sort (ni titre, ni date, ni lieu)
    mine := null;
    select r.status::text into mine from public.rsvps r where r.event_id = ev.id and r.user_id = f.user_id;
    if mine = 'no' then continue; end if;  -- Pas présent : hors de son agenda
    -- Sondage : dates votées Oui ou Si besoin (maybe = seulement Si besoin) ; sans aucun vote, toutes les dates proposées.
    select coalesce(jsonb_agg(jsonb_build_object('id', o.id, 'starts_at', o.starts_at, 'ends_at', o.ends_at,
             'maybe', exists (select 1 from public.date_votes v where v.option_id = o.id and v.user_id = f.user_id
                              and v.vote = 'if_needed')) order by o.starts_at), '[]')
      into voted
      from public.date_options o
      where o.event_id = ev.id and o.starts_at > now() - interval '1 day'
        and (exists (select 1 from public.date_votes v where v.option_id = o.id and v.user_id = f.user_id and v.vote in ('yes', 'if_needed'))
             or not exists (select 1 from public.date_votes v join public.date_options x on x.id = v.option_id
                            where x.event_id = ev.id and v.user_id = f.user_id));
    out := out || jsonb_build_object(
      'event_id', ev.id, 'title', ev.title, 'description', left(coalesce(ev.description, ''), 2000),
      'location', concat_ws(', ', ev.location_name, ev.location_address),
      'status', ev.status, 'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at,
      'updated_at', ev.updated_at, 'active', true, 'my_rsvp', mine, 'dates', voted);
  end loop;
  perform set_config('request.jwt.claims', coalesce(claims, ''), true);
  perform set_config('request.jwt.claim.sub', coalesce(sub, ''), true);
  return jsonb_build_object('events', out);
end $$;
revoke all on function public.calendar_feed(text) from public;
grant execute on function public.calendar_feed(text) to anon, authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261115230000', 'agenda_votes_sondage') on conflict do nothing;
commit;
notify pgrst, 'reload schema';
