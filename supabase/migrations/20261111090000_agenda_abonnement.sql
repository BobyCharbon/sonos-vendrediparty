-- Agenda abonné « Vendredi Party » (retours de l'admin du 11.11.2026, suite de l'avis 9ddbdea7fe8f).
-- Chaque personne a UN calendrier « Vendredi Party », auquel son agenda (iPhone, Mac, Google, Outlook) s'abonne une
-- seule fois et qu'il relit tout seul. « Ajouter à mon agenda » (événement normal) ou « Valider mes dates » (sondage)
-- y ajoute l'événement. Ensuite tout suit sans rouvrir Party : date, heure, lieu, titre, description modifiés ; sondage
-- ouvert → ses dates votées (Oui, Si besoin) « À confirmer » ; date fixée → la seule bonne ; rien si elle a dit Non,
-- si l'événement est annulé ou si elle n'y a plus accès.
-- Le jeton (secret, aléatoire) ne donne accès qu'à ces événements-là. Purement additif et rejouable.

create table if not exists public.calendar_feeds (
  token text primary key default encode(extensions.gen_random_bytes(18), 'hex'),
  user_id uuid not null unique references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  read_at timestamptz  -- dernière lecture par un agenda : l'abonnement est en place
);
alter table public.calendar_feeds enable row level security;
revoke all on public.calendar_feeds from public, anon, authenticated;

create table if not exists public.calendar_feed_events (
  user_id uuid not null references public.profiles(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  added_at timestamptz not null default now(),
  primary key (user_id, event_id)
);
alter table public.calendar_feed_events enable row level security;
revoke all on public.calendar_feed_events from public, anon, authenticated;
-- Aucune politique : lues et écrites seulement par les fonctions ci-dessous.

-- Le lien du calendrier de la personne connectée (toujours le même), si son agenda est déjà abonné (lu ces 10
-- derniers jours : rien à ouvrir, l'événement y arrive tout seul) et si cet événement y est déjà. Avec add = true,
-- l'événement y est ajouté (toucher sur « Ajouter à mon agenda » ou « Valider mes dates »).
drop function if exists public.calendar_feed_token(uuid);
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
drop function if exists public.calendar_feed(text);
create or replace function public.calendar_feed(t text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare f public.calendar_feeds; out jsonb := '[]'; ev public.events; mine text; voted jsonb; still boolean;
begin
  if t is null or length(t) <> 36 then return null; end if;
  select * into f from public.calendar_feeds where token = t;
  if not found then return null; end if;
  update public.calendar_feeds set read_at = now() where token = t and (read_at is null or read_at < now() - interval '10 minutes');
  for ev in
    select x.* from public.calendar_feed_events c join public.events x on x.id = c.event_id
    where c.user_id = f.user_id
      and (x.date_mode <> 'fixed' or x.starts_at is null or coalesce(x.ends_at, x.starts_at) > now() - interval '60 days')
    order by c.added_at desc limit 150
  loop
    -- Toujours concerné : organisateur, invité, a répondu ou voté, ou événement ouvert à tous.
    still := ev.created_by = f.user_id
      or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = f.user_id)
      or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = f.user_id)
      or exists (select 1 from public.rsvps r where r.event_id = ev.id and r.user_id = f.user_id)
      or exists (select 1 from public.date_votes v join public.date_options o on o.id = v.option_id
                 where o.event_id = ev.id and v.user_id = f.user_id)
      or (ev.visibility = 'all' and ev.public_link);
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
      'updated_at', ev.updated_at, 'active', still and ev.status = 'published', 'my_rsvp', mine, 'dates', voted);
  end loop;
  return jsonb_build_object('events', out);
end $$;
revoke all on function public.calendar_feed(text) from public;
grant execute on function public.calendar_feed(text) to anon, authenticated;
