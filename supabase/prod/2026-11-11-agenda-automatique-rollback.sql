-- PROD, retour arrière d'agenda_automatique (20261111110000) : l'agenda ne montre plus que les événements ajoutés à la
-- main (fonctions de 20261111090000). Aucune donnée touchée. Tout ou rien.
begin;
create or replace function public.calendar_feed_token(e uuid, add boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare f public.calendar_feeds;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  insert into public.calendar_feeds (user_id) values (auth.uid())
  on conflict (user_id) do update set user_id = excluded.user_id
  returning * into f;
  if add then
    insert into public.calendar_feed_events (user_id, event_id) values (auth.uid(), e) on conflict do nothing;
  end if;
  return jsonb_build_object('token', f.token,
    'subscribed', coalesce(f.read_at > now() - interval '10 days', false),
    'added', exists (select 1 from public.calendar_feed_events c where c.user_id = auth.uid() and c.event_id = e));
end $$;
revoke all on function public.calendar_feed_token(uuid, boolean) from public, anon;
grant execute on function public.calendar_feed_token(uuid, boolean) to authenticated;

-- Ce que l'agenda abonné affiche (appelé par le serveur de Party avec le jeton, sans compte).
create or replace function public.calendar_feed(t text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare f public.calendar_feeds; out jsonb := '[]'; ev public.events; mine text; voted jsonb; still boolean;
  claims text := current_setting('request.jwt.claims', true); sub text := current_setting('request.jwt.claim.sub', true);
begin
  if t is null or length(t) <> 36 then return null; end if;
  select * into f from public.calendar_feeds where token = t;
  if not found then return null; end if;
  -- Confidentialité : l'agenda ne montre JAMAIS plus que ce que Party montre à la personne. On regarde chaque événement
  -- avec ses yeux à elle, À CHAQUE lecture (même règle que l'app : public.can_see_event) : retirée du groupe ou de la
  -- liste des invités, compte suspendu, événement repassé en privé ou en brouillon → il quitte son agenda.
  perform set_config('request.jwt.claims', json_build_object('sub', f.user_id, 'role', 'authenticated')::text, true);
  perform set_config('request.jwt.claim.sub', f.user_id::text, true);
  update public.calendar_feeds set read_at = now() where token = t and (read_at is null or read_at < now() - interval '10 minutes');
  for ev in
    select x.* from public.calendar_feed_events c join public.events x on x.id = c.event_id
    where c.user_id = f.user_id
      and (x.date_mode <> 'fixed' or x.starts_at is null or coalesce(x.ends_at, x.starts_at) > now() - interval '60 days')
    order by c.added_at desc limit 150
  loop
    still := public.can_see_event(ev.id) and ev.status = 'published';
    if not still then continue; end if;  -- plus visible : rien n'en sort (ni titre, ni date, ni lieu)
    mine := null;
    select r.status::text into mine from public.rsvps r where r.event_id = ev.id and r.user_id = f.user_id;
    -- Sondage : dates votées Oui ou Si besoin ; sans aucun vote, toutes les dates proposées.
    select coalesce(jsonb_agg(jsonb_build_object('id', o.id, 'starts_at', o.starts_at, 'ends_at', o.ends_at) order by o.starts_at), '[]')
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
drop function if exists private.feed_includes(uuid, uuid);
delete from supabase_migrations.schema_migrations where version = '20261111110000';
commit;
