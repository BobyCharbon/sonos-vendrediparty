-- PROD, campagne2_restes (20261107120000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Prérequis (à passer avant, dans cet ordre) : 2026-11-07-campagne2-invitations (invite_preview) et
-- 2026-11-07-campagne2-reponses (public_event). Rejouable. Tout ou rien.
begin;
-- Campagne 2 des bots (07.11.2026) : restes de la base. Additive et rejouable (create or replace seulement).
-- 1. Carte d'invitation (invite_preview) : « qui vient déjà » montre le surnom entier (avant : son premier mot).
-- 2. report_content sur un contenu qu'on ne peut pas lire : refus propre en 404 (PT404), plus une erreur 500 (P0002).
-- 3. public_event rend l'affiche (https seulement) : image de l'aperçu des liens d'un événement public.

-- 1. ----------------------------------------------------------------------------------------------------------------
create or replace function public.invite_preview(token uuid, opened boolean default false) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare l private.invite_links; ev public.events; me uuid := auth.uid(); mine public.rsvps; arrived boolean := false;
        state text; who text; organizer boolean := false;
begin
  if token is null then return null; end if;
  select * into l from private.invite_links il where il.token = invite_preview.token and il.kind = 'event';
  if l.token is null then return null; end if;
  select * into ev from public.events where id = l.target and status in ('published', 'cancelled');
  if ev.id is null then return null; end if;
  if me is not null then organizer := public.is_organizer(ev.id); end if;
  -- L'auteur du lien et les organisateurs ne comptent pas comme une ouverture.
  if opened and l.opened_at is null and me is distinct from l.created_by and not organizer and l.revoked_at is null then
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
    'organizer', organizer,
    'version', l.version, 'label', l.label,
    'places_left', case when l.max_uses > 1 then greatest(l.max_uses - l.uses, 0) end,
    'inviter', nullif(btrim(coalesce(who, '')), ''),
    'title', ev.title, 'status', ev.status, 'date_mode', ev.date_mode,
    'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', coalesce(ev.location_name, case when arrived or organizer then ev.location_address end),
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'description', left(ev.description, 400),
    'allow_maybe', ev.allow_maybe,
    'closed', ev.rsvp_deadline is not null and now() > ev.rsvp_deadline,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'going_names', case when ev.show_participants then coalesce((select jsonb_agg(n) from (
        select nullif(btrim(p.display_name), '') n from public.rsvps r join public.profiles p on p.id = r.user_id
        where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted and nullif(btrim(p.display_name), '') is not null
        order by r.updated_at limit 3) x), '[]'::jsonb) else '[]'::jsonb end,
    -- Ce que voit la personne qui a déjà répondu par ce lien, ou un organisateur (changer sa réponse, adresse, itinéraire).
    'mine', case when (arrived or organizer) and mine.event_id is not null then mine.status::text end,
    'event_id', case when arrived or organizer then ev.id end,
    'location_address', case when arrived or organizer then ev.location_address end,
    'location_url', case when arrived or organizer then ev.location_url end,
    'me_named', me is not null and exists (select 1 from public.profiles p where p.id = me and btrim(p.display_name) <> ''));
end $$;

-- 2. ----------------------------------------------------------------------------------------------------------------
create or replace function public.report_content(p_kind text, p_target text, p_reason text, p_comment text default null)
returns uuid language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); snap jsonb; owner uuid; rid uuid; v_comment text := nullif(btrim(left(p_comment, 500)), '');
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if p_reason is null or p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'other') then
    raise exception 'reason: choisis une raison' using errcode = '22023';
  end if;
  if (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 hour') >= 10
     or (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 day') >= 30 then
    raise exception 'rate_limited: tu as fait beaucoup de signalements, réessaie plus tard' using errcode = '54000';
  end if;
  snap := private.report_snapshot(p_kind, p_target, me);
  if snap is null then raise exception 'not_found: ce contenu n''existe plus ou ne t''est pas visible' using errcode = 'PT404'; end if;
  owner := nullif(snap ->> 'owner', '')::uuid;
  if owner = me then raise exception 'self: tu ne peux pas signaler ton propre contenu' using errcode = '22023'; end if;
  select id into rid from public.content_reports
    where reporter_id = me and target_kind = p_kind and target_id = p_target and status = 'open';
  if rid is not null then
    update public.content_reports set reason = p_reason, comment = v_comment where id = rid;
    return rid;
  end if;
  insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason, comment, snapshot)
  values (me, p_kind, p_target, owner, p_reason, v_comment, snap - 'owner')
  returning id into rid;
  return rid;
end $$;

-- 3. ----------------------------------------------------------------------------------------------------------------
create or replace function public.public_event(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'price_chf', ev.price_chf, 'allow_maybe', ev.allow_maybe, 'rsvp_deadline', ev.rsvp_deadline,
    'max_participants', ev.max_participants,
    'cover_url', case when ev.cover_url like 'https://%' then ev.cover_url end,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones,
                                       'note', (select n.note from public.rsvp_notes n where n.event_id = ev.id and n.user_id = r.user_id))
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261107120000', 'campagne2_restes')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
