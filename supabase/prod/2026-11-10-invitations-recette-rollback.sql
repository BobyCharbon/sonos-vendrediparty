-- PROD, retour arrière de invitations_recette (20261110100100) : create_event_invite et sync_event_group_invites d'avant,
-- sans le déclencheur des dates ni la politique « quitter le groupe ». La colonne follows_event reste (inutilisée). Tout ou rien.
begin;
drop trigger if exists event_dates_links on public.events;
drop function if exists private.on_event_dates_links();
drop policy if exists "quitter le groupe" on public.member_group_members;
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
  -- Par défaut : jusqu'au lendemain de l'événement (ou 14 jours sans date) ; jamais plus de 60 jours.
  ends := coalesce(until, coalesce(ev.ends_at, ev.starts_at) + interval '1 day', now() + interval '14 days');
  ends := least(greatest(ends, now() + interval '1 hour'), now() + interval '60 days');
  if (select count(*) from private.invite_links il where il.kind = 'event' and il.target = e
        and il.revoked_at is null and il.expires_at > now() and il.used_by is null and il.uses < il.max_uses) >= 100 then
    raise exception 'Trop de liens en attente : arrête ceux qui ne serviront plus.';
  end if;
  insert into private.invite_links (kind, target, created_by, expires_at, max_uses, label, version)
    values ('event', e, auth.uid(), ends, places, name, 2) returning token into tok;
  return jsonb_build_object('token', tok, 'expires_at', ends, 'max_uses', places, 'label', name);
end $$;
create or replace function private.sync_event_group_invites(e uuid) returns void
language sql security definer set search_path = '' as $$
  delete from public.event_invites i where i.event_id = e and i.via_group
    and not exists (select 1 from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
                    where eg.event_id = e and eg.status = 'approved' and gm.user_id = i.user_id)
    and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id);
  insert into public.event_invites (event_id, user_id, via_group)
    select distinct eg.event_id, gm.user_id, true
    from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
    where eg.event_id = e and eg.status = 'approved' and exists (select 1 from public.events where id = e)
  on conflict (event_id, user_id) do nothing;
$$;
drop function if exists private.event_link_end(public.events);
delete from supabase_migrations.schema_migrations where version = '20261110100100';
commit;
