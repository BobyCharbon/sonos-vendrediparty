-- PROD, retour arrière de lien_sans_limite (20261111100000) : remet le plafond de 50 places et de 60 jours.
-- Les liens sans limite déjà créés passent à 50 places (ils restent valables). Tout ou rien.
begin;
update private.invite_links set max_uses = greatest(50, uses) where max_uses = 10000;
update private.invite_links set max_uses = 50, uses = least(uses, 50) where max_uses > 50;
alter table private.invite_links drop constraint if exists invite_links_places;
alter table private.invite_links add constraint invite_links_places check (((max_uses >= 1) and (max_uses <= 50)) and (uses >= 0));
create or replace function private.event_link_end(ev public.events) returns timestamptz
language sql stable set search_path = '' as $$
  select least(greatest(coalesce(coalesce(ev.ends_at, ev.starts_at) + interval '1 day', now() + interval '14 days'),
                        now() + interval '1 hour'), now() + interval '60 days');
$$;
revoke all on function private.event_link_end(public.events) from public, anon, authenticated;
create or replace function public.create_event_invite(e uuid, places int default 1, until timestamptz default null,
                                                      label text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; tok uuid; ends timestamptz; name text := nullif(btrim(coalesce(label, '')), '');
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  if ev.status <> 'published' then raise exception 'Publie l''événement avant d''inviter'; end if;
  if places is null or places < 1 or places > 50 then raise exception 'Entre 1 et 50 places par lien'; end if;
  if name is not null and char_length(name) > 40 then raise exception 'Prénom trop long (40 caractères au plus)'; end if;
  -- Par défaut : jusqu'au lendemain de l'événement (ou 14 jours sans date), puis suit la date ; jamais plus de 60 jours.
  ends := case when until is null then private.event_link_end(ev)
               else least(greatest(until, now() + interval '1 hour'), now() + interval '60 days') end;
  if (select count(*) from private.invite_links il where il.kind = 'event' and il.target = e
        and il.revoked_at is null and il.expires_at > now() and il.used_by is null and il.uses < il.max_uses) >= 100 then
    raise exception 'Trop de liens en attente : arrête ceux qui ne serviront plus.';
  end if;
  insert into private.invite_links (kind, target, created_by, expires_at, max_uses, label, version, follows_event)
    values ('event', e, auth.uid(), ends, places, name, 2, until is null) returning token into tok;
  return jsonb_build_object('token', tok, 'expires_at', ends, 'max_uses', places, 'label', name);
end $$;
delete from supabase_migrations.schema_migrations where version = '20261111100000';
commit;
