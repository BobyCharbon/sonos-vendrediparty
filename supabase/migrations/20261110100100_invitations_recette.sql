-- Invitations : corrections de la recette réelle du 10.11.2026 (agents « lien d'invitation » et « groupes »).
-- Purement additif et rejouable.
--
-- 1. Un lien créé avec « Après l'événement » (valeur par défaut, `until` vide) SUIT la date de l'événement : sur un
--    sondage, il valait 14 jours et ne bougeait plus quand la date était fixée (lien expiré le 24.11 pour un événement
--    du 04.12). Une durée choisie (3 jours, 7 jours) reste celle choisie. Jamais plus de 60 jours, un lien arrêté le reste.
-- 2. Supprimer un événement supprime ses liens (ils restaient dans private.invite_links, sans clé étrangère).
-- 3. Un membre retiré d'un groupe garde l'accès à un sondage où il a VOTÉ (comme une personne qui a répondu) :
--    ses votes restaient comptés alors qu'il ne voyait plus l'événement (même cause que la purge du paintball).
-- 4. Un membre peut quitter lui-même un groupe (jamais le groupe Membres Vendredi Party) :
--    la suppression de sa propre ligne était ignorée en silence.

-- 1. Liens qui suivent la date ---------------------------------------------------------------------------------------
alter table private.invite_links add column if not exists follows_event boolean not null default false;

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

create or replace function private.on_event_dates_links() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'DELETE' then
    delete from private.invite_links where kind = 'event' and target = old.id;
    return null;
  end if;
  if new.starts_at is distinct from old.starts_at or new.ends_at is distinct from old.ends_at then
    update private.invite_links set expires_at = private.event_link_end(new)
      where kind = 'event' and target = new.id and follows_event and revoked_at is null;
  end if;
  return null;
end $$;
revoke all on function private.on_event_dates_links() from public, anon, authenticated;
drop trigger if exists event_dates_links on public.events;
create trigger event_dates_links after update of starts_at, ends_at or delete on public.events
  for each row execute function private.on_event_dates_links();

-- Liens déjà créés « Après l'événement » sur un sondage encore sans date (valeur par défaut d'avant) : ils suivront la date.
update private.invite_links il set follows_event = true
  from public.events ev
  where il.kind = 'event' and il.target = ev.id and ev.starts_at is null and not il.follows_event
    and il.revoked_at is null and il.expires_at > now()
    and abs(extract(epoch from (il.expires_at - il.created_at)) - 14 * 86400) < 120;

-- 2bis. Liens orphelins laissés par des événements déjà supprimés.
delete from private.invite_links il
  where il.kind = 'event' and not exists (select 1 from public.events ev where ev.id = il.target);

-- 3. Retiré du groupe : garde le sondage où il a voté ------------------------------------------------------------
create or replace function private.sync_event_group_invites(e uuid) returns void
language sql security definer set search_path = '' as $$
  delete from public.event_invites i where i.event_id = e and i.via_group
    and not exists (select 1 from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
                    where eg.event_id = e and eg.status = 'approved' and gm.user_id = i.user_id)
    and not exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = i.user_id)
    and not exists (select 1 from public.date_votes v join public.date_options o on o.id = v.option_id
                    where o.event_id = e and v.user_id = i.user_id);
  insert into public.event_invites (event_id, user_id, via_group)
    select distinct eg.event_id, gm.user_id, true
    from public.event_groups eg join public.member_group_members gm on gm.group_id = eg.group_id
    where eg.event_id = e and eg.status = 'approved' and exists (select 1 from public.events where id = e)
  on conflict (event_id, user_id) do nothing;
$$;

-- 4. Quitter un groupe soi-même --------------------------------------------------------------------------------------
drop policy if exists "quitter le groupe" on public.member_group_members;
create policy "quitter le groupe" on public.member_group_members for delete to authenticated
  using (user_id = (select auth.uid()) and exists (
    select 1 from public.member_groups g
    where g.id = member_group_members.group_id and g.system_key is null and g.created_by is distinct from (select auth.uid())));
