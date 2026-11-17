-- « Réunir les invités dans un groupe » (décision de l'admin du 17.11.2026, remplace « jamais d'ajout d'office » du 10.11 ;
-- avis de conformité du 17.11 : case DÉCOCHÉE par défaut, RGPD Planet49, Apple 5.1.2).
-- - Option par événement (events.guest_group, éteinte par défaut, jamais allumée par l'IA) : un seul groupe, que
--   l'organisateur gère (créateur / admin du groupe) ET dont il fait partie ; jamais Membres Vendredi Party ; « Nouveau
--   groupe » crée groupe et réglage d'un coup (nom filtré, CGU : déclencheurs de member_groups).
-- - L'invité coche lui-même « Rejoindre aussi le groupe » ; l'écran envoie join_group true/false AVEC sa réponse
--   (accept_invite_group, ou set_guest_group_choice sur la fiche) : coché, il entre quelle que soit la réponse (Je viens,
--   Peut-être, Pas présent) ; sans le paramètre ou à false, jamais. La base ne décide jamais seule.
-- - Jamais : blocage avec l'organisateur ou le créateur du groupe, profil incomplet, personne partie du groupe après la
--   création de l'événement (private.group_departures : groupe, personne, date ; seule la personne revient d'elle-même).
-- - Entrée : notification PERSONNELLE « group_added » (interrupteur notification_prefs.group_added) ; aucune aux membres
--   (le créateur garde « X a rejoint ton groupe », existant) ; jamais d'annonce (private.send_announcement seul).
-- - « Garder cette bande ? » (keep_band) : le lendemain, l'organisateur INVITE (invitation à accepter) les présents ou
--   tous les invités, une seule fois par événement, jamais ceux qui ont décoché ni ceux partis du groupe.
-- - invite_to_group refuse désormais aussi une personne en blocage avec le créateur du groupe.
-- Purement additive et rejouable.

alter table public.events add column if not exists guest_group uuid references public.member_groups (id) on delete set null;
comment on column public.events.guest_group is
  'Groupe proposé aux invités (case « Rejoindre aussi le groupe », décochée par défaut) ; null = option éteinte (17.11).';

alter table public.notification_prefs add column if not exists group_added boolean not null default true;

-- Départs : la personne qui a quitté elle-même un groupe n'y est jamais remise sans son propre geste.
create table if not exists private.group_departures (
  group_id uuid not null references public.member_groups (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  left_at timestamptz not null default now(),
  primary key (group_id, user_id)
);
alter table private.group_departures enable row level security;
revoke all on private.group_departures from public, anon, authenticated;

-- Choix de l'invité, gardé avec sa réponse (true / false explicites, envoyés par l'écran) ; joined_at / seen_at : bandeau.
create table if not exists private.guest_group_choices (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  join_group boolean not null,
  chosen_at timestamptz not null default now(),
  group_id uuid references public.member_groups (id) on delete cascade,
  joined_at timestamptz,
  seen_at timestamptz,
  primary key (event_id, user_id)
);
alter table private.guest_group_choices enable row level security;
revoke all on private.guest_group_choices from public, anon, authenticated;

-- « Garder cette bande ? » : une seule fois par événement (fait ou « Non merci »).
create table if not exists private.band_offers (
  event_id uuid primary key references public.events (id) on delete cascade,
  group_id uuid references public.member_groups (id) on delete set null,
  invited int not null default 0,
  done_at timestamptz not null default now()
);
alter table private.band_offers enable row level security;
revoke all on private.band_offers from public, anon, authenticated;

-- Un groupe que la personne gère ET dont elle fait partie (même logique que guard_event_group), jamais un groupe système.
create or replace function private.manages_guest_group(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.member_groups g where g.id = grp and g.system_key is null)
    and private.group_admin(grp, uid) and private.in_group_now(grp, uid);
$$;
revoke all on function private.manages_guest_group(uuid, uuid) from public, anon, authenticated;

create or replace function private.guard_event_guest_group() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.guest_group is not null and auth.uid() is not null
     and (tg_op = 'INSERT' or new.guest_group is distinct from old.guest_group)
     and not private.manages_guest_group(new.guest_group, auth.uid()) then
    raise exception 'forbidden: choisis un groupe que tu gères et dont tu fais partie' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_event_guest_group() from public, anon, authenticated;
drop trigger if exists events_guest_group_guard on public.events;
create trigger events_guest_group_guard before insert or update of guest_group on public.events
  for each row execute function private.guard_event_guest_group();

-- Le groupe tel que l'invité le voit (nom, émoji s'il existe, nombre de membres, prénom de l'organisateur).
create or replace function private.guest_group_card(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', g.id, 'name', g.name, 'emoji', to_jsonb(g)->>'emoji',
    'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
    'owner', (select coalesce(nullif(btrim(p.first_name), ''), nullif(btrim(p.display_name), '')) from public.profiles p
              where p.id = ev.created_by))
  from public.events ev join public.member_groups g on g.id = ev.guest_group and g.system_key is null
  where ev.id = e;
$$;
revoke all on function private.guest_group_card(uuid) from public, anon, authenticated;

create or replace function private.guest_group_eligible(e uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.events ev join public.member_groups g on g.id = ev.guest_group and g.system_key is null
    where ev.id = e and ev.date_mode = 'fixed'
      and private.identity_complete(uid)
      and not private.blocked_either(uid, ev.created_by) and not private.blocked_either(uid, g.created_by)
      -- Partie du groupe après la création de cet événement : pas proposé ici (un nouvel événement le propose).
      and not exists (select 1 from private.group_departures d where d.group_id = g.id and d.user_id = uid
                      and d.left_at >= ev.created_at));
$$;
revoke all on function private.guest_group_eligible(uuid, uuid) from public, anon, authenticated;

-- La case à montrer à cette personne (null : rien à proposer). Sans compte : la case s'affiche, la base tranche ensuite.
create or replace function private.guest_group_offer(e uuid, uid uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select case when uid is null and exists (select 1 from public.events ev where ev.id = e and ev.date_mode = 'fixed')
                then private.guest_group_card(e)
              when uid is not null and private.guest_group_eligible(e, uid)
                   and not private.in_group_now((select guest_group from public.events where id = e), uid)
                then private.guest_group_card(e) end;
$$;
revoke all on function private.guest_group_offer(uuid, uuid) from public, anon, authenticated;

-- L'entrée dans le groupe (après le choix explicite de la personne). Rend joined / already / refused / off.
create or replace function private.guest_group_join(e uuid, uid uuid) returns text
language plpgsql security definer set search_path = '' as $$
declare ev public.events; g public.member_groups;
begin
  select * into ev from public.events where id = e;
  select * into g from public.member_groups where id = ev.guest_group and system_key is null;
  if g.id is null then return 'off'; end if;
  if private.in_group_now(g.id, uid) then
    update private.guest_group_choices set group_id = g.id where event_id = e and user_id = uid;
    return 'already';
  end if;
  if not private.guest_group_eligible(e, uid) then return 'refused'; end if;
  perform private.join_group(g.id, uid);  -- prévient le créateur seulement (« X a rejoint ton groupe »)
  update private.guest_group_choices set group_id = g.id, joined_at = now(), seen_at = null
    where event_id = e and user_id = uid;
  -- Notification personnelle, même si c'est son propre geste (queue_notification l'ignorerait).
  insert into public.notifications (user_id, kind, event_id, title, body, data, dedupe_key)
  values (uid, 'group_added', null, 'Tu es dans le groupe « ' || g.name || ' »',
    'Ajouté avec ta réponse à « ' || ev.title || ' ». Touche pour voir le groupe ou le quitter.',
    jsonb_build_object('kind', 'group_added', 'group_id', g.id, 'event', e),
    'group_added:' || g.id || ':' || uid || ':' || e)
  on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing;
  return 'joined';
end $$;
revoke all on function private.guest_group_join(uuid, uuid) from public, anon, authenticated;

-- Le choix de la personne (true / false), gardé avec sa réponse. Coché et réponse donnée : elle entre ; en attente de
-- l'accord de l'organisateur : elle entrera à l'accord (déclencheur sur rsvps). Sans réponse : refusé.
create or replace function public.set_guest_group_choice(e uuid, join_group boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); st text;
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if join_group is null then raise exception 'Choix manquant'; end if;
  if exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = me) then
    insert into private.guest_group_choices (event_id, user_id, join_group) values (e, me, join_group)
    on conflict (event_id, user_id) do update set join_group = excluded.join_group, chosen_at = now();
    st := case when join_group then private.guest_group_join(e, me) else 'declined' end;
  elsif exists (select 1 from public.event_join_requests q where q.event_id = e and q.user_id = me and q.status = 'pending') then
    insert into private.guest_group_choices (event_id, user_id, join_group) values (e, me, join_group)
    on conflict (event_id, user_id) do update set join_group = excluded.join_group, chosen_at = now();
    st := case when join_group then 'pending' else 'declined' end;
  else
    raise exception 'Réponds d''abord à l''invitation.';
  end if;
  return jsonb_build_object('status', st, 'group', private.guest_group_card(e));
end $$;
revoke all on function public.set_guest_group_choice(uuid, boolean) from public, anon;
grant execute on function public.set_guest_group_choice(uuid, boolean) to authenticated;

-- Réponse par un lien d'invitation + choix du groupe, dans la même transaction (accept_invite inchangée).
create or replace function public.accept_invite_group(token uuid, answer text, join_group boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r jsonb; e uuid;
begin
  r := public.accept_invite(token, answer);
  select il.target into e from private.invite_links il where il.token = accept_invite_group.token and il.kind = 'event';
  if coalesce((r->>'organizer')::boolean, false) or join_group is null
     or not exists (select 1 from public.events ev where ev.id = e and ev.guest_group is not null and ev.date_mode = 'fixed') then
    return r;
  end if;
  return r || jsonb_build_object('guest_group', public.set_guest_group_choice(e, join_group));
end $$;
revoke all on function public.accept_invite_group(uuid, text, boolean) from public, anon;
grant execute on function public.accept_invite_group(uuid, text, boolean) to authenticated;

-- Accord de l'organisateur (decide_join_request) : la réponse arrive ; si la personne avait coché, elle entre.
create or replace function private.guest_group_on_rsvp() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from private.guest_group_choices c where c.event_id = new.event_id and c.user_id = new.user_id
             and c.join_group and c.joined_at is null) then
    perform private.guest_group_join(new.event_id, new.user_id);
  end if;
  return null;
end $$;
revoke all on function private.guest_group_on_rsvp() from public, anon, authenticated;
drop trigger if exists rsvps_guest_group on public.rsvps;
create trigger rsvps_guest_group after insert on public.rsvps for each row execute function private.guest_group_on_rsvp();

-- Départ : seulement quand la personne s'en va elle-même (pas une cascade : groupe ou compte supprimé). Revenir efface la
-- date. Les fiches qui proposent ce groupe se relisent (carte Invités de l'organisateur, en direct).
create or replace function private.note_group_departure() returns trigger
language plpgsql security definer set search_path = '' as $$
declare e uuid;
begin
  if tg_op = 'DELETE' then
    -- Groupe ou compte supprimé : la cascade retire les membres d'un groupe (ou d'un profil) qui n'existe déjà plus.
    if auth.uid() = old.user_id and exists (select 1 from public.member_groups g where g.id = old.group_id)
       and exists (select 1 from public.profiles p where p.id = old.user_id) then
      insert into private.group_departures (group_id, user_id) values (old.group_id, old.user_id)
      on conflict (group_id, user_id) do update set left_at = now();
    end if;
  else
    delete from private.group_departures where group_id = new.group_id and user_id = new.user_id;
  end if;
  for e in select ev.id from public.events ev where ev.guest_group = coalesce(new.group_id, old.group_id)
           and ev.status = 'published' order by ev.created_at desc limit 20 loop
    perform private.party_signal('event:' || e);
  end loop;
  return null;
end $$;
revoke all on function private.note_group_departure() from public, anon, authenticated;
drop trigger if exists member_group_members_departure on public.member_group_members;
create trigger member_group_members_departure after insert or delete on public.member_group_members
  for each row execute function private.note_group_departure();

-- Choisir le groupe (ou « Nouveau groupe », ou éteindre : grp et new_name vides). Organisateurs de l'événement.
create or replace function public.set_event_guest_group(e uuid, grp uuid default null, new_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not private.manages_event(e) then raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501'; end if;
  if nullif(btrim(coalesce(new_name, '')), '') is not null then
    if not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
    -- Nom filtré et CGU exigées (member_groups_moderation) ; le créateur entre d'office (member_groups_creator_joins).
    insert into public.member_groups (name, created_by) values (left(btrim(new_name), 60), auth.uid()) returning id into grp;
  end if;
  update public.events set guest_group = grp where id = e;
  return public.event_guest_group(e);
end $$;

-- Ce que la fiche montre : le groupe, la case ou le bouton « Rejoindre le groupe » de la personne ; pour l'organisation,
-- les groupes qu'elle peut choisir et « Garder cette bande ? ».
create or replace function public.event_guest_group(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events; manage boolean; c private.guest_group_choices; band jsonb;
begin
  select * into ev from public.events where id = e;
  manage := private.manages_event(e);
  if ev.id is null or me is null or not (manage or public.can_see_event(e)) then
    raise exception 'forbidden: événement introuvable' using errcode = '42501';
  end if;
  select * into c from private.guest_group_choices where event_id = e and user_id = me;
  if manage and private.event_is_over(ev) and now() < coalesce(ev.ends_at, ev.starts_at) + interval '7 days'
     and not exists (select 1 from private.band_offers b where b.event_id = e) then
    band := jsonb_build_object(
      'present', (select count(*) from private.band_people(e, 'present') x),
      'all', (select count(*) from private.band_people(e, 'all') x),
      'names', coalesce((select jsonb_agg(n) from (select coalesce(nullif(btrim(p.display_name), ''), '?') n
        from private.band_people(e, 'present') x join public.profiles p on p.id = x.user_id order by p.display_name limit 6) s),
        '[]'::jsonb));
  end if;
  return jsonb_build_object(
    'group', private.guest_group_card(e),
    'in_group', ev.guest_group is not null and private.in_group_now(ev.guest_group, me),
    'offer', private.guest_group_offer(e, me) is not null,
    'answered', exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = me),
    'choice', c.join_group,
    'manage', manage,
    'groups', case when manage then coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'name', g.name,
        'emoji', to_jsonb(g)->>'emoji', 'members', (select count(*) from public.member_group_members m where m.group_id = g.id))
        order by g.name) from public.member_groups g where private.manages_guest_group(g.id, me)), '[]'::jsonb) end,
    'band', band);
end $$;

-- Personnes de « Garder cette bande ? » : présents (Je viens confirmé, ou passés à l'entrée) ou tous les invités.
-- Jamais : l'organisateur qui le fait, ceux qui ont décoché la case à cet événement, ceux partis du groupe de l'événement.
create or replace function private.band_people(e uuid, who text) returns table (user_id uuid)
language sql stable security definer set search_path = '' as $$
  select distinct x.u from (
    select r.user_id u from public.rsvps r where r.event_id = e and (who = 'all' or (r.status = 'yes' and not r.waitlisted))
    union select t.user_id from public.event_tickets t where t.event_id = e and t.checked_in_at is not null
    union select i.user_id from public.event_invites i where i.event_id = e and who = 'all'
  ) x
  join public.profiles p on p.id = x.u and p.status = 'active'
  where x.u is distinct from auth.uid()
    and not exists (select 1 from private.guest_group_choices c where c.event_id = e and c.user_id = x.u and not c.join_group)
    and not exists (select 1 from private.group_departures d join public.events ev on ev.id = e
                    where d.group_id = ev.guest_group and d.user_id = x.u);
$$;
revoke all on function private.band_people(uuid, text) from public, anon, authenticated;

-- « Garder cette bande ? » : une INVITATION au groupe (acceptée ou non par chacun), une seule fois. who = 'none' : « Non merci ».
create or replace function public.keep_band(e uuid, who text, grp uuid default null, new_name text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare ev public.events; g public.member_groups; u uuid; n int := 0; me text;
begin
  if not private.manages_event(e) then raise exception 'forbidden: réservé aux organisateurs' using errcode = '42501'; end if;
  select * into ev from public.events where id = e for update;
  if exists (select 1 from private.band_offers b where b.event_id = e) then raise exception 'C''est déjà fait pour cet événement.'; end if;
  if who not in ('present', 'all', 'none') then raise exception 'Choix inconnu'; end if;
  if who = 'none' then
    insert into private.band_offers (event_id) values (e);
    return jsonb_build_object('invited', 0);
  end if;
  if not private.event_is_over(ev) or now() >= coalesce(ev.ends_at, ev.starts_at) + interval '7 days' then
    raise exception 'Proposé de la fin de l''événement à 7 jours après.';
  end if;
  if nullif(btrim(coalesce(new_name, '')), '') is not null then
    insert into public.member_groups (name, created_by) values (left(btrim(new_name), 60), auth.uid()) returning id into grp;
  elsif grp is null or not private.manages_guest_group(grp, auth.uid()) then
    raise exception 'forbidden: choisis un groupe que tu gères et dont tu fais partie' using errcode = '42501';
  end if;
  select * into g from public.member_groups where id = grp;
  select display_name into me from public.profiles where id = auth.uid();
  for u in select b.user_id from private.band_people(e, who) b loop
    -- Comme invite_to_group : jamais une personne en blocage, ni partie de CE groupe ; une invitation à accepter.
    continue when private.in_group_now(grp, u) or private.blocked_either(u, auth.uid()) or private.blocked_either(u, g.created_by)
      or exists (select 1 from private.group_departures d where d.group_id = grp and d.user_id = u);
    insert into private.group_invitations (group_id, user_id, invited_by) values (grp, u, auth.uid()) on conflict do nothing;
    if found then
      n := n + 1;
      perform public.queue_notification(u, 'group_invite', null, g.name,
        coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' » (après « ' || ev.title || ' »)',
        'group_invite:' || grp || ':' || u);
    end if;
  end loop;
  insert into private.band_offers (event_id, group_id, invited) values (e, grp, n);
  return jsonb_build_object('invited', n, 'group_id', grp);
end $$;
revoke all on function public.keep_band(uuid, text, uuid, text) from public, anon;
grant execute on function public.keep_band(uuid, text, uuid, text) to authenticated;
revoke all on function public.event_guest_group(uuid) from public, anon;
grant execute on function public.event_guest_group(uuid) to authenticated;
revoke all on function public.set_event_guest_group(uuid, uuid, text) from public, anon;
grant execute on function public.set_event_guest_group(uuid, uuid, text) to authenticated;

-- Bandeau « Tu es dans le groupe X · ajouté avec ta réponse à « … » · Quitter » : rendu une fois (première ouverture).
create or replace function public.take_group_join_note(grp uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare c private.guest_group_choices; out jsonb;
begin
  select * into c from private.guest_group_choices where user_id = auth.uid() and group_id = grp and joined_at is not null
    and seen_at is null order by joined_at desc limit 1;
  if c.event_id is null or not private.in_group_now(grp, auth.uid()) then return null; end if;
  update private.guest_group_choices set seen_at = now() where event_id = c.event_id and user_id = c.user_id;
  select jsonb_build_object('event_id', ev.id, 'event_title', ev.title,
      'group_name', coalesce((to_jsonb(g)->>'emoji') || ' ', '') || g.name,
      'owner', (select coalesce(nullif(btrim(p.first_name), ''), nullif(btrim(p.display_name), '')) from public.profiles p where p.id = ev.created_by),
      'creator', g.created_by = auth.uid())
    into out from public.events ev join public.member_groups g on g.id = grp where ev.id = c.event_id;
  return out;
end $$;
revoke all on function public.take_group_join_note(uuid) from public, anon;
grant execute on function public.take_group_join_note(uuid) to authenticated;

-- Trou trouvé (17.11) : invite_to_group ne regardait que le blocage avec l'auteur de l'invitation (group_invitations_block) :
-- un admin du site invitait dans le groupe quelqu'un en blocage avec son CRÉATEUR. Refusé désormais, même phrase que la garde
-- (on ne dit pas qui a bloqué), avant toute invitation ou notification.
create or replace function public.invite_to_group(grp uuid, member uuid default null, phone text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  select * into g from public.member_groups where id = grp;
  if target is null and number is not null then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  if target is not null and exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if target is not null then
    if private.blocked_either(target, auth.uid()) or private.blocked_either(target, g.created_by) then
      raise exception 'blocked: Tu ne peux pas inviter cette personne.' using errcode = '42501';
    end if;
    insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
    select display_name into me from public.profiles where id = auth.uid();
    perform public.queue_notification(target, 'group_invite', null, g.name,
      coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
      'group_invite:' || grp || ':' || target);
    return jsonb_build_object('invited', 'member');
  end if;
  insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
  return jsonb_build_object('invited', 'phone');
end $$;

-- Notification « Tu es dans le groupe X » : son interrupteur partout, reçue par un compte Guest, bloquée comme les autres.
-- Carte Invités : 'in_group' par personne et le groupe ; carte d'invitation : la case à proposer.
do $$ declare def text;
begin
  -- Événement publié : seul le groupe des invités change → organisateurs et co-organisateurs (comme « Prévenir le groupe »).
  def := pg_get_functiondef('public.guard_event()'::regprocedure);
  if position('''guest_group''' in def) = 0 then
    if position('    -- Billets QR (04.11)' in def) = 0 then raise exception 'guard_event : ancre Billets QR introuvable'; end if;
    execute replace(def, '    -- Billets QR (04.11)', $a$    if (to_jsonb(new) - 'guest_group' - 'updated_at') = (to_jsonb(old) - 'guest_group' - 'updated_at')
       and public.is_organizer(new.id) then return new; end if;
    -- Billets QR (04.11)$a$);
  end if;
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''group_added''' in def) = 0 then
    if position($a$    when 'group_join' then prefs.group_joins$a$ in def) = 0 then raise exception 'web_push_allowed : ancre group_join introuvable'; end if;
    execute replace(def, $a$    when 'group_join' then prefs.group_joins$a$, $a$    when 'group_join' then prefs.group_joins
    when 'group_added' then coalesce(prefs.group_added, true)$a$);
  end if;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''group_added''' in def) = 0 then
    if position('''group_join'',' in def) = 0 then raise exception 'may_receive_push : ancre group_join introuvable'; end if;
    execute replace(def, '''group_join'',', '''group_join'', ''group_added'',');
  end if;
  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position('''group_added''' in def) = 0 then
    if position('''group_join'')' in def) = 0 then raise exception 'drop_blocked_notification : ancre group_join introuvable'; end if;
    execute replace(def, '''group_join'')', '''group_join'', ''group_added'')');
  end if;
  def := pg_get_functiondef('private.event_guest_list_full(uuid)'::regprocedure);
  if position('''in_group''' in def) = 0 then
    if position($a$'removable', i.user_id is not null and not i.via_group) x$a$ in def) = 0
       or position($a$'poll', ev.date_mode = 'poll',$a$ in def) = 0 then
      raise exception 'event_guest_list_full : ancres introuvables';
    end if;
    def := replace(def, $a$'removable', i.user_id is not null and not i.via_group) x$a$,
      $a$'removable', i.user_id is not null and not i.via_group,
        'in_group', ev.guest_group is not null and private.in_group_now(ev.guest_group, p.id)) x$a$);
    execute replace(def, $a$'poll', ev.date_mode = 'poll',$a$, $a$'poll', ev.date_mode = 'poll',
    'guest_group', private.guest_group_card(e),$a$);
  end if;
  def := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  if position('''guest_group''' in def) = 0 then
    if position($a$'me_named', me is not null$a$ in def) = 0 then raise exception 'invite_preview : ancre me_named introuvable'; end if;
    -- Pas de case pour qui a déjà sa place dans le groupe, ni pour l'organisateur sur son propre lien.
    execute replace(def, $a$'me_named', me is not null$a$, $a$'guest_group', case when not organizer then private.guest_group_offer(ev.id, me) end,
    'me_named', me is not null$a$);
  end if;
end $$;
