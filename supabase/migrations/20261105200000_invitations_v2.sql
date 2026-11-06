-- Invitations, version 2 (décision de l'admin du 05.11.2026, en BÊTA : écrans visibles seulement sur le site de test,
-- drapeau serveur invites_v2_enabled). Mélange des maquettes A et C :
-- - organisateur : carte « Invités » sur la fiche (qui vient, qui n'a pas répondu, qui a invité qui, liens envoyés),
--   « + » qui ouvre la feuille « Inviter » (lien pour une personne ou pour plusieurs, avec places et date limite ;
--   gens de Party, même hors du groupe, ou un groupe) ; relances (notification si la personne a l'app, sinon la feuille
--   de partage) : une au plus par jour et par personne ; retrait d'un invité ;
-- - invité sans app : carte d'invitation lisible SANS compte (invite_preview), « Je viens » → prénom + numéro → code
--   SMS → réponse enregistrée d'un coup (accept_invite). Compte invité minimal : le prénom seul (dans display_name ;
--   nom, photo… ne sont demandés qu'en ouvrant l'app). Personne n'entre dans un groupe par un lien d'événement.
-- - données : les comptes invités minimaux sans app sont effacés 7 jours après leur dernier événement
--   (private.purge_light_invitees, chaque nuit) — politique de confidentialité mise à jour.
-- Purement additive et rejouable : colonnes « if not exists », tables « if not exists », fonctions « create or replace »,
-- contraintes ajoutées une fois. Les liens et écrans existants (version 1) continuent de marcher tels quels.

-- 1. Liens : places, prénom noté, ouverture, version -----------------------------------------------------------------
alter table private.invite_links add column if not exists max_uses int not null default 1;
alter table private.invite_links add column if not exists uses int not null default 0;
alter table private.invite_links add column if not exists label text;
alter table private.invite_links add column if not exists opened_at timestamptz;
alter table private.invite_links add column if not exists version int not null default 1;
do $$ begin
  alter table private.invite_links add constraint invite_links_places check (max_uses between 1 and 50 and uses >= 0);
exception when duplicate_object then null; end $$;
do $$ begin
  alter table private.invite_links add constraint invite_links_label_len check (label is null or char_length(label) <= 40);
exception when duplicate_object then null; end $$;

-- Qui est arrivé par quel lien (un lien « pour plusieurs » sert à plusieurs personnes).
create table if not exists private.invite_link_arrivals (
  token uuid not null references private.invite_links(token) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  at timestamptz not null default now(),
  primary key (token, user_id)
);
create index if not exists invite_link_arrivals_user on private.invite_link_arrivals (user_id);
revoke all on private.invite_link_arrivals from public, anon, authenticated;

-- 2. Invités : qui a invité, par quel lien, depuis quand ------------------------------------------------------------
alter table public.event_invites add column if not exists invited_by uuid default auth.uid() references public.profiles(id) on delete set null;
alter table public.event_invites add column if not exists link_token uuid references private.invite_links(token) on delete set null;
alter table public.event_invites add column if not exists created_at timestamptz default now();

-- 3. Relances : une au plus par jour et par personne (ou par lien) --------------------------------------------------
create table if not exists private.invite_nudges (
  id bigint generated always as identity primary key,
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid references public.profiles(id) on delete cascade,
  token uuid references private.invite_links(token) on delete cascade,
  by uuid references public.profiles(id) on delete set null,
  channel text not null check (channel in ('push', 'share')),
  at timestamptz not null default now(),
  check (user_id is not null or token is not null)
);
create index if not exists invite_nudges_user on private.invite_nudges (event_id, user_id, at desc);
create index if not exists invite_nudges_token on private.invite_nudges (token, at desc);
revoke all on private.invite_nudges from public, anon, authenticated;

-- 4. Comptes invités minimaux (prénom + numéro, arrivés par un lien d'événement) -------------------------------------
create table if not exists private.light_invitees (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  event_id uuid references public.events(id) on delete set null,
  created_at timestamptz not null default now()
);
revoke all on private.light_invitees from public, anon, authenticated;

-- Aujourd'hui (heure de Suisse) : une relance par jour calendaire.
create or replace function private.nudged_today(e uuid, u uuid, tok uuid) returns timestamptz
language sql stable security definer set search_path = '' as $$
  select max(n.at) from private.invite_nudges n
  where n.event_id = e and ((u is not null and n.user_id = u) or (tok is not null and n.token = tok))
    and (n.at at time zone 'Europe/Zurich')::date = (now() at time zone 'Europe/Zurich')::date;
$$;

-- État d'un lien, en mots simples pour l'écran : revoked, full (unique utilisé ou places prises), expired, opened, pending.
create or replace function private.invite_link_state(l private.invite_links) returns text
language sql stable security definer set search_path = '' as $$
  select case when l.revoked_at is not null then 'revoked'
              when l.used_by is not null or l.uses >= l.max_uses then 'full'
              when l.expires_at <= now() then 'expired'
              when l.opened_at is not null then 'opened'
              else 'pending' end;
$$;

-- A l'app (au moins un appareil abonné aux notifications) : la relance part en notification, sinon par le partage.
create or replace function private.has_app(u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.push_tokens t where t.user_id = u and t.session_id is not null);
$$;

-- Premier mot du surnom : « qui vient déjà » montré sans compte, prénoms seulement.
create or replace function private.first_word(t text) returns text
language sql immutable set search_path = '' as $$
  select nullif(split_part(btrim(coalesce(t, '')), ' ', 1), '');
$$;

-- 5. Créer un lien (organisateurs), quel que soit le public de l'événement -----------------------------------------
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

-- 6. Carte d'invitation, lisible sans compte (aperçu WhatsApp compris) ---------------------------------------------
-- Seulement le nécessaire : titre, date, nom du lieu (l'adresse exacte après la réponse), affiche, qui invite,
-- combien viennent et 3 prénoms au plus (rien si l'organisateur cache la liste). opened = true : la page s'ouvre
-- (l'organisateur voit « A ouvert ») ; l'aperçu du serveur passe false.
create or replace function public.invite_preview(token uuid, opened boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text;
begin
  if token is null then return null; end if;
  select * into l from private.invite_links il where il.token = invite_preview.token and il.kind = 'event';
  if l.token is null then return null; end if;
  select * into ev from public.events where id = l.target and status in ('published', 'cancelled');
  if ev.id is null then return null; end if;
  if opened and l.opened_at is null and me is distinct from l.created_by and l.revoked_at is null then
    update private.invite_links il set opened_at = now() where il.token = l.token;
  end if;
  if me is not null then
    arrived := l.used_by = me or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
    select * into mine from public.rsvps r where r.event_id = ev.id and r.user_id = me;
  end if;
  state := private.invite_link_state(l);
  select display_name into who from public.profiles where id = coalesce(l.created_by, ev.created_by);
  return jsonb_build_object(
    'state', case when arrived and state <> 'revoked' then 'mine' else state end,
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 then greatest(l.max_uses - l.uses, 0) end,
    'inviter', private.first_word(who),
    'title', ev.title, 'status', ev.status, 'date_mode', ev.date_mode,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', coalesce(ev.location_name, case when arrived then ev.location_address end),
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'description', left(ev.description, 400),
    'allow_maybe', ev.allow_maybe,
    'closed', ev.rsvp_deadline is not null and now() > ev.rsvp_deadline,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select private.first_word(p.display_name) n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and private.first_word(p.display_name) is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Ce que voit la personne qui a déjà répondu par ce lien (changer sa réponse, adresse, itinéraire).
    'mine', case when arrived and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived then ev.id end,
    'location_address', case when arrived then ev.location_address end,
    'location_url', case when arrived then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''));
end $$;

-- 7. Répondre par le lien, en une fois : prénom (compte neuf), arrivée sur l'événement, réponse ---------------------
create or replace function public.accept_invite(token uuid, answer text, first_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); arrived boolean; name text := btrim(coalesce(first_name, ''));
        current_name text; who text; u uuid;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if answer is null or answer not in ('yes', 'maybe', 'no') then raise exception 'Réponse inconnue'; end if;
  select * into l from private.invite_links il where il.token = accept_invite.token and il.kind = 'event' for update;
  if l.token is null then raise exception 'Ce lien d''invitation n''existe pas'; end if;
  select * into ev from public.events where id = l.target;
  if ev.id is null then raise exception 'Cet événement n''existe plus'; end if;
  if ev.status = 'cancelled' then raise exception 'Cet événement est annulé'; end if;
  if ev.status <> 'published' then raise exception 'Cet événement n''est plus ouvert'; end if;
  if l.revoked_at is not null then
    raise exception 'Ce lien a été arrêté par la personne qui t''a invité. Demande-lui un nouveau lien.';
  end if;

  -- Compte neuf : le prénom seul suffit (jamais nom, surnom ni photo ici).
  select display_name into current_name from public.profiles where id = me;
  if btrim(coalesce(current_name, '')) = '' then
    if name = '' then raise exception 'first_name_required: écris ton prénom'; end if;
    if char_length(name) > 40 then raise exception 'Prénom trop long (40 caractères au plus)'; end if;
    update public.profiles set display_name = name where id = me;
    insert into private.light_invitees (user_id, event_id) values (me, ev.id) on conflict (user_id) do nothing;
  end if;

  arrived := l.used_by = me or exists (select 1 from private.invite_link_arrivals a where a.token = l.token and a.user_id = me);
  if arrived then
    -- Déjà venu par ce lien : changer sa réponse, sauf si l'organisateur l'a retiré de la liste.
    if not public.can_see_event(ev.id) then
      raise exception 'removed: l''organisateur t''a retiré de la liste des invités';
    end if;
  else
    if l.used_by is not null or l.uses >= l.max_uses then
      raise exception '%', case when l.max_uses = 1
        then 'Ce lien a déjà servi : il était pour une seule personne. Demande ton propre lien.'
        else 'Toutes les places de ce lien sont prises. Demande un autre lien à la personne qui t''a invité.' end;
    end if;
    if l.expires_at <= now() then
      raise exception 'Ce lien n''est plus valable (date limite passée). Demande un nouveau lien.';
    end if;
    insert into private.invite_link_arrivals (token, user_id) values (l.token, me) on conflict do nothing;
    update private.invite_links il set uses = il.uses + 1,
        used_by = case when il.max_uses = 1 then me else il.used_by end,
        used_at = case when il.max_uses = 1 then now() else il.used_at end,
        opened_at = coalesce(il.opened_at, now())
      where il.token = l.token;
    -- Invité de CET événement seulement (jamais ajouté à un groupe) ; un membre qui le voit déjà n'a pas de ligne.
    if not public.can_see_event(ev.id) or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = me) then
      insert into public.event_invites (event_id, user_id, via_group, via_link, invited_by, link_token)
        values (ev.id, me, false, true, l.created_by, l.token)
      on conflict (event_id, user_id) do update set via_link = true,
        invited_by = coalesce(public.event_invites.invited_by, excluded.invited_by),
        link_token = coalesce(public.event_invites.link_token, excluded.link_token);
    end if;
    select display_name into who from public.profiles where id = me;
    for u in select x from (select ev.created_by x union select user_id from public.event_organizers where event_id = ev.id) o loop
      perform public.queue_notification(u, 'link_join', ev.id, ev.title,
        coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' a répondu par ton lien d''invitation',
        'link_join:' || ev.id || ':' || me);
    end loop;
  end if;

  insert into public.rsvps (event_id, user_id, status) values (ev.id, me, answer::public.rsvp_status)
  on conflict (event_id, user_id) do update set status = excluded.status;

  return jsonb_build_object('event_id', ev.id, 'status', answer, 'title', ev.title,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day, 'date_mode', ev.date_mode,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'description', ev.description,
    'waitlisted', (select r.waitlisted from public.rsvps r where r.event_id = ev.id and r.user_id = me));
end $$;

-- 8. Carte « Invités » de l'organisateur : tout le monde, d'où il vient, sa réponse, les liens envoyés --------------
create or replace function public.event_guest_list(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events; vip boolean; vip_name text;
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  select * into ev from public.events where id = e;
  vip := ev.visibility = 'all' and not ev.public_link;
  select name into vip_name from public.member_groups where system_key = 'vip' limit 1;
  return jsonb_build_object(
    'vip', vip, 'public', ev.public_link, 'vip_name', vip_name,
    'groups', coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'name', g.name,
        'members', (select count(*) from public.member_group_members m where m.group_id = g.id)) order by g.name)
      from public.event_groups eg join public.member_groups g on g.id = eg.group_id where eg.event_id = e), '[]'::jsonb),
    'people', coalesce((select jsonb_agg(x order by x->>'name') from (
      select jsonb_build_object(
        'id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url,
        'status', r.status, 'waitlisted', coalesce(r.waitlisted, false), 'plus_ones', coalesce(r.plus_ones, 0),
        'answered_at', r.updated_at,
        'source', case when i.user_id is null then (case when vip and private.is_member(p.id) then 'vip' else 'public' end)
                       when i.via_group then 'group' when i.via_link then 'link' else 'person' end,
        'group', case when i.user_id is null and vip and private.is_member(p.id) then vip_name
                      when i.via_group then (select string_agg(g.name, ', ' order by g.name) from public.event_groups eg
                        join public.member_groups g on g.id = eg.group_id
                        join public.member_group_members gm on gm.group_id = g.id and gm.user_id = p.id where eg.event_id = e) end,
        'invited_by', case when i.via_group then null else (select display_name from public.profiles where id = i.invited_by) end,
        'invited_by_id', case when i.via_group then null else i.invited_by end,
        'link_label', (select il.label from private.invite_links il where il.token = i.link_token), 'link_token', i.link_token,
        'invited_at', i.created_at,
        'has_app', private.has_app(p.id),
        'light', exists (select 1 from private.light_invitees li where li.user_id = p.id),
        'nudged_today', private.nudged_today(e, p.id, null) is not null,
        'removable', i.user_id is not null and not i.via_group) x
      from public.profiles p
      left join public.event_invites i on i.event_id = e and i.user_id = p.id
      left join public.rsvps r on r.event_id = e and r.user_id = p.id
      where p.status = 'active' and p.id <> ev.created_by
        and (i.user_id is not null or r.user_id is not null or (vip and private.is_member(p.id)))) s), '[]'::jsonb),
    'links', coalesce((select jsonb_agg(x order by x->>'created_at' desc) from (
      select jsonb_build_object(
        'token', l.token, 'label', l.label, 'max_uses', l.max_uses, 'uses', l.uses, 'created_at', l.created_at,
        'expires_at', l.expires_at, 'opened_at', l.opened_at, 'state', private.invite_link_state(l), 'version', l.version,
        'created_by', (select display_name from public.profiles where id = l.created_by), 'created_by_id', l.created_by,
        'nudged_today', private.nudged_today(e, null, l.token) is not null,
        'arrivals', coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id)) order by a.at)
          from private.invite_link_arrivals a join public.profiles p on p.id = a.user_id where a.token = l.token),
          case when l.used_by is not null then (select jsonb_build_array(jsonb_build_object('id', p.id, 'name', p.display_name,
            'status', (select r.status from public.rsvps r where r.event_id = e and r.user_id = p.id)))
            from public.profiles p where p.id = l.used_by) else '[]'::jsonb end)) x
      from private.invite_links l
      where l.kind = 'event' and l.target = e and (l.revoked_at is null or l.uses > 0 or l.used_by is not null)
      order by l.created_at desc limit 60) s), '[]'::jsonb));
end $$;

-- 9. Ajouter des gens de Party (même hors du groupe) ou un groupe : ils voient l'événement, sans entrer dans le groupe
create or replace function public.invite_people(e uuid, people uuid[] default '{}', groups uuid[] default '{}') returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; u uuid; g uuid; added int := 0; grp int := 0; n int;
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  if coalesce(array_length(people, 1), 0) > 100 or coalesce(array_length(groups, 1), 0) > 20 then
    raise exception 'Trop de personnes d''un coup';
  end if;
  select * into ev from public.events where id = e;
  foreach u in array coalesce(people, '{}') loop
    if u = ev.created_by or not private.is_account_active(u) then continue; end if;
    -- Déjà invité (groupe, lien, un par un) ou membre de Vendredi Party pour un événement du groupe : rien à ajouter.
    if ev.visibility = 'all' and not ev.public_link and private.is_member(u) then continue; end if;
    insert into public.event_invites (event_id, user_id, via_group, invited_by) values (e, u, false, auth.uid())
    on conflict (event_id, user_id) do nothing;
    get diagnostics n = row_count;
    if n > 0 then
      added := added + 1;
      -- Toujours prévenu quand on l'ajoute d'ici (même si « prévenir à la publication » était coupé).
      if ev.status = 'published' and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() then
        perform private.queue_private_invite(ev, u);
      end if;
    end if;
  end loop;
  foreach g in array coalesce(groups, '{}') loop
    if not exists (select 1 from public.member_groups mg where mg.id = g and mg.system_key is null
                   and (public.is_admin() or mg.created_by = auth.uid()
                        or exists (select 1 from public.member_group_members m where m.group_id = g and m.user_id = auth.uid()))) then
      raise exception 'forbidden: tu ne peux inviter que tes groupes' using errcode = '42501';
    end if;
    insert into public.event_groups (event_id, group_id) values (e, g) on conflict do nothing;
    get diagnostics n = row_count;
    grp := grp + n;
  end loop;
  return jsonb_build_object('people', added, 'groups', grp);
end $$;

-- 10. Retirer un invité ajouté un par un ou venu par un lien (jamais un membre du groupe invité)
create or replace function public.remove_invitee(e uuid, member uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  if not exists (select 1 from public.event_invites where event_id = e and user_id = member and not via_group) then
    raise exception 'Cette personne vient avec un groupe : retire le groupe dans « Modifier ».';
  end if;
  delete from public.event_invites where event_id = e and user_id = member and not via_group;
  -- Plus invitée : sa réponse part avec (sauf si elle voit encore l'événement autrement, ex. événement public).
  if not exists (select 1 from public.events where id = e and public_link and visibility = 'all') then
    delete from public.rsvps where event_id = e and user_id = member;
  end if;
end $$;

-- 11. Relancer : notification Party si la personne a l'app (son interrupteur « Invitations »), sinon la feuille de
--     partage (renvoyé à l'écran). Une relance au plus par jour et par personne, seulement à qui n'a pas répondu.
create or replace function public.nudge_invitees(e uuid, people uuid[]) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; u uuid; host text; notified int := 0; skipped int := 0; share uuid[] := '{}';
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  if coalesce(array_length(people, 1), 0) > 300 then raise exception 'Trop de personnes d''un coup'; end if;
  select * into ev from public.events where id = e;
  if ev.status <> 'published' then raise exception 'Cet événement n''est pas ouvert aux réponses'; end if;
  select display_name into host from public.profiles where id = auth.uid();
  foreach u in array coalesce(people, '{}') loop
    if u = auth.uid() or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = u) then continue; end if;
    -- Seulement les invités (groupe, Vendredi Party, un par un, lien).
    if not (exists (select 1 from public.event_invites i where i.event_id = e and i.user_id = u)
            or (ev.visibility = 'all' and not ev.public_link and private.is_member(u))) then continue; end if;
    if private.nudged_today(e, u, null) is not null then skipped := skipped + 1; continue; end if;
    if private.has_app(u) then
      perform public.queue_notification(u, 'private_invite', e, '📬 ' || ev.title,
        coalesce(private.first_word(host), 'L''organisateur') || ' attend ta réponse : tu viens ?',
        'invite_nudge:' || e || ':' || u || ':' || to_char(now() at time zone 'Europe/Zurich', 'YYYY-MM-DD'));
      insert into private.invite_nudges (event_id, user_id, by, channel) values (e, u, auth.uid(), 'push');
      notified := notified + 1;
    else
      insert into private.invite_nudges (event_id, user_id, by, channel) values (e, u, auth.uid(), 'share');
      share := share || u;
    end if;
  end loop;
  return jsonb_build_object('notified', notified, 'skipped', skipped, 'share', to_jsonb(share));
end $$;

-- Relancer par un lien (la personne n'a pas encore de compte) : noté, une fois par jour ; l'écran ouvre le partage.
create or replace function public.nudge_invite_link(tok uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links;
begin
  select * into l from private.invite_links where token = tok and kind = 'event';
  if l.token is null or not private.manages_event(l.target) then
    raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501';
  end if;
  if private.nudged_today(l.target, null, tok) is not null then raise exception 'Déjà relancé aujourd''hui'; end if;
  insert into private.invite_nudges (event_id, token, by, channel) values (l.target, tok, auth.uid(), 'share');
end $$;

-- 12. Notifications des invités hors du groupe (Guests) : leur invitation, sa relance et les nouvelles de la soirée
--     (annulation, date fixée, rappels, place libérée) leur parviennent aussi ; chaque type garde son interrupteur.
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('pet_daily', 'pet_alert', 'pet_gift', 'pet_streak', 'pet_bar') and private.is_account_active(uid))
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message', 'moderation_notice', 'report_new',
                 'private_invite', 'event_changed', 'date_fixed', 'reminder', 'waitlist')
        and private.is_account_active(uid));
$$;

-- 13. Effacer les comptes invités minimaux restés sans app, 7 jours après leur dernier événement ------------------
create or replace function private.light_invitees_to_purge() returns setof uuid
language sql stable security definer set search_path = '' as $$
  select li.user_id from private.light_invitees li join public.profiles p on p.id = li.user_id
  where li.created_at < now() - interval '7 days'
    and btrim(p.first_name) = '' and btrim(p.last_name) = '' and coalesce(btrim(p.avatar_url), '') = ''
    and p.role = 'guest' and not private.is_root(p.id)
    and not exists (select 1 from public.push_tokens t where t.user_id = p.id)
    and not exists (select 1 from public.member_group_members m where m.user_id = p.id)
    and not exists (select 1 from public.event_invites i where i.user_id = p.id and not i.via_link)
    and not exists (select 1 from public.events ev where ev.created_by = p.id)
    and not exists (select 1 from public.event_invites i join public.events ev on ev.id = i.event_id
                    where i.user_id = p.id and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() - interval '7 days')
    and not exists (select 1 from public.rsvps r join public.events ev on ev.id = r.event_id
                    where r.user_id = p.id and coalesce(ev.ends_at, ev.starts_at, 'infinity') > now() - interval '7 days');
$$;

create or replace function private.purge_light_invitees() returns int
language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  with gone as (delete from auth.users where id in (select private.light_invitees_to_purge()) returning id)
  select count(*) into n from gone;
  return n;
end $$;

do $$ begin
  perform cron.schedule('purge-light-invitees', '37 4 * * *', 'select private.purge_light_invitees();');
exception when undefined_function or invalid_schema_name then null; end $$;

-- Droits --------------------------------------------------------------------------------------------------------
revoke all on function private.nudged_today(uuid, uuid, uuid), private.invite_link_state(private.invite_links),
  private.has_app(uuid), private.first_word(text), private.light_invitees_to_purge(), private.purge_light_invitees()
  from public, anon, authenticated;
revoke all on function public.create_event_invite(uuid, int, timestamptz, text), public.accept_invite(uuid, text, text),
  public.event_guest_list(uuid), public.invite_people(uuid, uuid[], uuid[]), public.remove_invitee(uuid, uuid),
  public.nudge_invitees(uuid, uuid[]), public.nudge_invite_link(uuid) from public, anon;
grant execute on function public.create_event_invite(uuid, int, timestamptz, text), public.accept_invite(uuid, text, text),
  public.event_guest_list(uuid), public.invite_people(uuid, uuid[], uuid[]), public.remove_invitee(uuid, uuid),
  public.nudge_invitees(uuid, uuid[]), public.nudge_invite_link(uuid) to authenticated;
-- La carte d'invitation se lit sans compte (seulement le nécessaire, voir plus haut).
revoke all on function public.invite_preview(uuid, boolean) from public;
grant execute on function public.invite_preview(uuid, boolean) to anon, authenticated;
