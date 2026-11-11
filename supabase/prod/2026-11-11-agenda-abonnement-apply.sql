-- PROD, agenda_abonnement (20261111090000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée existante modifiée (nouvelle table vide, deux fonctions).
begin;
-- Sondage de dates → agenda qui se met à jour tout seul (retour de l'admin du 11.11.2026, suite de l'avis 9ddbdea7fe8f).
-- Après « Valider mes dates », la personne venue par un lien (souvent dans le navigateur, sans l'app) s'abonne à un
-- petit calendrier propre à elle et à cet événement. Son agenda le relit tout seul : tant que le sondage est ouvert, il
-- montre les dates qu'elle a votées (Oui, Si besoin) « À confirmer » ; une fois la date fixée, seulement la bonne, sous
-- le vrai titre ; rien si elle a dit Non à cette date, si l'événement est annulé ou si elle n'y a plus accès.
-- Le jeton (secret, aléatoire) ne donne accès qu'à ces dates, ce titre et ce lieu. Purement additif et rejouable.

create table if not exists public.calendar_feeds (
  token text primary key default encode(extensions.gen_random_bytes(18), 'hex'),
  user_id uuid not null references public.profiles(id) on delete cascade,
  event_id uuid not null references public.events(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, event_id)
);
alter table public.calendar_feeds enable row level security;
-- Aucune politique : lu et écrit seulement par les deux fonctions ci-dessous.
revoke all on public.calendar_feeds from public, anon, authenticated;

-- Le lien d'abonnement de la personne connectée pour cet événement (le même à chaque fois).
create or replace function public.calendar_feed_token(e uuid) returns text
language plpgsql security definer set search_path = '' as $$
declare t text;
begin
  if auth.uid() is null or not public.can_see_event(e) then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  insert into public.calendar_feeds (user_id, event_id) values (auth.uid(), e)
  on conflict (user_id, event_id) do update set user_id = excluded.user_id
  returning token into t;
  return t;
end $$;
revoke all on function public.calendar_feed_token(uuid) from public, anon;
grant execute on function public.calendar_feed_token(uuid) to authenticated;

-- Ce que l'agenda abonné affiche (appelé par le serveur de Party avec le jeton, sans compte).
create or replace function public.calendar_feed(t text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare f public.calendar_feeds; ev public.events; mine text; voted jsonb; still boolean;
begin
  if t is null or length(t) <> 36 then return null; end if;
  select * into f from public.calendar_feeds where token = t;
  if not found then return null; end if;
  select * into ev from public.events where id = f.event_id;
  if not found then return null; end if;
  -- Toujours concerné : organisateur, invité, a répondu ou voté, ou événement ouvert à tous.
  still := ev.created_by = f.user_id
    or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = f.user_id)
    or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = f.user_id)
    or exists (select 1 from public.rsvps r where r.event_id = ev.id and r.user_id = f.user_id)
    or exists (select 1 from public.date_votes v join public.date_options o on o.id = v.option_id
               where o.event_id = ev.id and v.user_id = f.user_id)
    or (ev.visibility = 'all' and ev.public_link);
  select r.status::text into mine from public.rsvps r where r.event_id = ev.id and r.user_id = f.user_id;
  -- Dates votées Oui ou Si besoin ; sans aucun vote, toutes les dates proposées.
  select coalesce(jsonb_agg(jsonb_build_object('id', o.id, 'starts_at', o.starts_at, 'ends_at', o.ends_at) order by o.starts_at), '[]')
    into voted
    from public.date_options o
    where o.event_id = ev.id and o.starts_at > now() - interval '1 day'
      and (exists (select 1 from public.date_votes v where v.option_id = o.id and v.user_id = f.user_id and v.vote in ('yes', 'if_needed'))
           or not exists (select 1 from public.date_votes v join public.date_options x on x.id = v.option_id
                          where x.event_id = ev.id and v.user_id = f.user_id));
  return jsonb_build_object(
    'event_id', ev.id, 'title', ev.title, 'location', concat_ws(', ', ev.location_name, ev.location_address),
    'status', ev.status, 'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at,
    'active', still and ev.status = 'published', 'my_rsvp', mine, 'dates', voted);
end $$;
revoke all on function public.calendar_feed(text) from public;
grant execute on function public.calendar_feed(text) to anon, authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261111090000', 'agenda_abonnement') on conflict do nothing;
commit;
