-- Lien d'invitation « Plusieurs » sans limite (retour de l'admin du 11.11.2026) : trop de réglages pour qui veut juste
-- inviter un ami. Par défaut le lien est sans limite de places (∞, on peut quand même choisir un nombre) et vaut jusqu'à
-- la fin de l'événement : plus de choix « 3 jours » / « 7 jours », plus de plafond de 60 jours qui faisait mourir un lien
-- avant un événement lointain. L'organisateur peut toujours l'arrêter (revoke_invite_link, inchangé).
-- Purement additif et rejouable.

-- Sans limite = 10000 places (valeur repère : toutes les vérifications existantes « uses < max_uses » restent justes).
alter table private.invite_links drop constraint if exists invite_links_places;
alter table private.invite_links add constraint invite_links_places
  check (((max_uses between 1 and 50) or max_uses = 10000) and uses >= 0);

-- Fin d'un lien qui suit l'événement : le lendemain de sa fin. Sondage encore sans date : un an, puis il suit la date
-- dès qu'elle est fixée (déclencheur event_dates_links, 20261110100100). Jamais avant une heure.
create or replace function private.event_link_end(ev public.events) returns timestamptz
language sql stable set search_path = '' as $$
  select greatest(coalesce(coalesce(ev.ends_at, ev.starts_at) + interval '1 day', now() + interval '365 days'),
                  now() + interval '1 hour');
$$;
revoke all on function private.event_link_end(public.events) from public, anon, authenticated;

-- places = 0 : sans limite. until : gardé pour les anciennes versions de l'app (au plus 60 jours, comme avant).
create or replace function public.create_event_invite(e uuid, places int default 1, until timestamptz default null,
                                                      label text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; tok uuid; ends timestamptz; name text := nullif(btrim(coalesce(label, '')), '');
  seats int := case when places = 0 then 10000 else places end;
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  if ev.status <> 'published' then raise exception 'Publie l''événement avant d''inviter'; end if;
  if seats is null or (seats <> 10000 and (seats < 1 or seats > 50)) then
    raise exception 'Entre 1 et 50 places par lien, ou sans limite';
  end if;
  if name is not null and char_length(name) > 40 then raise exception 'Prénom trop long (40 caractères au plus)'; end if;
  ends := case when until is null then private.event_link_end(ev)
               else least(greatest(until, now() + interval '1 hour'), now() + interval '60 days') end;
  if (select count(*) from private.invite_links il where il.kind = 'event' and il.target = e
        and il.revoked_at is null and il.expires_at > now() and il.used_by is null and il.uses < il.max_uses) >= 100 then
    raise exception 'Trop de liens en attente : arrête ceux qui ne serviront plus.';
  end if;
  insert into private.invite_links (kind, target, created_by, expires_at, max_uses, label, version, follows_event)
    values ('event', e, auth.uid(), ends, seats, name, 2, until is null) returning token into tok;
  return jsonb_build_object('token', tok, 'expires_at', ends, 'max_uses', seats, 'label', name);
end $$;

-- Liens déjà créés « Après l'événement » : ils perdent le plafond de 60 jours (jamais raccourcis ; un lien arrêté le reste).
update private.invite_links il set expires_at = private.event_link_end(ev)
  from public.events ev
  where il.kind = 'event' and il.target = ev.id and il.follows_event and il.revoked_at is null
    and private.event_link_end(ev) > il.expires_at;
