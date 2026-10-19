-- Vendredi Party — schéma initial
-- Rôles : member < coadmin < admin. Un nouveau membre arrive en "pending"
-- et doit être accepté par un admin (sauf le tout premier, qui devient admin).


-- ---------------------------------------------------------------------------
-- Types
-- ---------------------------------------------------------------------------
create type member_role as enum ('member', 'coadmin', 'admin');
create type member_status as enum ('pending', 'active', 'banned');
create type event_status as enum ('draft', 'pending', 'published', 'rejected', 'cancelled');
create type date_mode as enum ('fixed', 'poll');
create type rsvp_status as enum ('yes', 'maybe', 'no');
create type date_vote as enum ('yes', 'if_needed', 'no');
create type event_visibility as enum ('all', 'invited');
create type chat_notify_mode as enum ('all', 'mentions', 'none');
create type new_event_scope as enum ('all', 'subscribed', 'none');

-- ---------------------------------------------------------------------------
-- Membres et réglages du groupe
-- ---------------------------------------------------------------------------
create table profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null default '',
  phone text,
  avatar_url text,
  role member_role not null default 'member',
  status member_status not null default 'pending',
  created_at timestamptz not null default now()
);

create table group_settings (
  id boolean primary key default true check (id),
  name text not null default 'Vendredi Party',
  timezone text not null default 'Europe/Zurich',
  require_approval boolean not null default true,
  coadmins_skip_approval boolean not null default true,
  organizers_can_edit_published boolean not null default false,
  members_can_create_tags boolean not null default false
);
insert into group_settings default values;

-- Catégorie : UNE par événement (Sport, Soirée, Repas…), gérée par l'admin.
create table categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  color text not null default '#D4F24A',
  icon text,
  sort int not null default 0,
  archived boolean not null default false
);

-- Tags : PLUSIEURS par événement (soirée, bar, cinéma…), on peut s'y abonner.
create table tags (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  color text not null default '#B9A7FF',
  created_by uuid references profiles (id) on delete set null,
  archived boolean not null default false,
  created_at timestamptz not null default now()
);
create unique index tags_name_ci on tags (lower(name));

create table tag_subscriptions (
  user_id uuid not null references profiles (id) on delete cascade,
  tag_id uuid not null references tags (id) on delete cascade,
  primary key (user_id, tag_id)
);

create table category_subscriptions (
  user_id uuid not null references profiles (id) on delete cascade,
  category_id uuid not null references categories (id) on delete cascade,
  primary key (user_id, category_id)
);

insert into categories (name, color, sort) values
  ('Soirée', '#FF7A59', 1),
  ('Sport', '#D4F24A', 2),
  ('Repas', '#F2C14A', 3),
  ('Culture', '#7AD3C8', 4),
  ('Voyage', '#7AA7FF', 5);

insert into tags (name) values
  ('soirée'), ('bar'), ('cinéma'), ('karting'), ('montagne'), ('jeux');

-- ---------------------------------------------------------------------------
-- Événements
-- ---------------------------------------------------------------------------
create table events (
  id uuid primary key default gen_random_uuid(),
  title text not null check (length(title) between 1 and 120),
  description text not null default '',
  cover_url text,
  category_id uuid references categories (id) on delete set null,
  created_by uuid not null references profiles (id) on delete cascade,
  status event_status not null default 'pending',
  rejection_reason text,
  approved_by uuid references profiles (id) on delete set null,
  approved_at timestamptz,

  -- Date
  date_mode date_mode not null default 'fixed',
  starts_at timestamptz,
  ends_at timestamptz,
  all_day boolean not null default false,
  poll_deadline timestamptz,
  members_can_propose_dates boolean not null default true,
  auto_fix_date boolean not null default false,

  -- Lieu & prix
  location_name text,
  location_address text,
  location_url text,
  price_chf numeric(10, 2),
  payment_info text,

  -- Participants
  max_participants int check (max_participants is null or max_participants > 0),
  waitlist_enabled boolean not null default true,
  allow_plus_ones boolean not null default false,
  max_plus_ones int not null default 1 check (max_plus_ones between 0 and 10),
  allow_maybe boolean not null default true,
  rsvp_deadline timestamptz,
  visibility event_visibility not null default 'all',
  show_participants boolean not null default true,

  -- Discussion & notifications
  forum_enabled boolean not null default true,
  notify_on_publish boolean not null default true,
  reminders text[] not null default '{1d,2h}',

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint fixed_needs_start check (date_mode <> 'fixed' or status in ('draft') or starts_at is not null),
  constraint ends_after_start check (ends_at is null or starts_at is null or ends_at >= starts_at),
  constraint reminders_valid check (reminders <@ array['7d', '1d', '2h', '0h']::text[])
);
create index events_status_start on events (status, starts_at);

create table event_tags (
  event_id uuid not null references events (id) on delete cascade,
  tag_id uuid not null references tags (id) on delete cascade,
  primary key (event_id, tag_id)
);

create table event_organizers (
  event_id uuid not null references events (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  primary key (event_id, user_id)
);

create table event_invites (
  event_id uuid not null references events (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  primary key (event_id, user_id)
);

create table event_mutes (
  event_id uuid not null references events (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  primary key (event_id, user_id)
);

create table rsvps (
  event_id uuid not null references events (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  status rsvp_status not null,
  plus_ones int not null default 0 check (plus_ones between 0 and 10),
  note text,
  waitlisted boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (event_id, user_id)
);

-- Sondage de dates (mode "poll")
create table date_options (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events (id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz,
  proposed_by uuid references profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  unique (event_id, starts_at)
);

create table date_votes (
  option_id uuid not null references date_options (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  vote date_vote not null,
  primary key (option_id, user_id)
);

-- Mini-sondages (dans un événement, ou pour tout le groupe si event_id null)
create table polls (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references events (id) on delete cascade,
  question text not null check (length(question) between 1 and 200),
  multiple_choice boolean not null default false,
  anonymous boolean not null default false,
  members_can_add_options boolean not null default false,
  results_after_vote boolean not null default false,
  closes_at timestamptz,
  created_by uuid references profiles (id) on delete set null,
  sort int not null default 0,
  created_at timestamptz not null default now()
);

create table poll_options (
  id uuid primary key default gen_random_uuid(),
  poll_id uuid not null references polls (id) on delete cascade,
  label text not null check (length(label) between 1 and 120),
  created_by uuid references profiles (id) on delete set null,
  sort int not null default 0
);

create table poll_votes (
  poll_id uuid not null references polls (id) on delete cascade,
  option_id uuid not null references poll_options (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (option_id, user_id)
);

-- "Qui amène quoi"
create table bring_items (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events (id) on delete cascade,
  label text not null,
  claimed_by uuid references profiles (id) on delete set null,
  sort int not null default 0
);

-- Forum de l'événement
create table messages (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references events (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  body text not null check (length(body) between 1 and 4000),
  reply_to uuid references messages (id) on delete set null,
  mentions uuid[] not null default '{}',
  pinned boolean not null default false,
  created_at timestamptz not null default now(),
  edited_at timestamptz,
  deleted_at timestamptz
);
create index messages_event_created on messages (event_id, created_at);

create table message_reactions (
  message_id uuid not null references messages (id) on delete cascade,
  user_id uuid not null references profiles (id) on delete cascade,
  emoji text not null check (length(emoji) <= 16),
  primary key (message_id, user_id, emoji)
);

-- ---------------------------------------------------------------------------
-- Notifications
-- ---------------------------------------------------------------------------
create table notification_prefs (
  user_id uuid primary key references profiles (id) on delete cascade,
  push_enabled boolean not null default true,
  quiet_start time default '23:00',
  quiet_end time default '08:00',
  new_event new_event_scope not null default 'all',
  event_changed boolean not null default true,
  poll_new boolean not null default true,
  poll_nudge boolean not null default false,
  date_fixed boolean not null default true,
  waitlist boolean not null default true,
  proposals boolean not null default true,
  rsvp_mine boolean not null default true,
  chat chat_notify_mode not null default 'mentions',
  reminders text[] not null default '{1d,2h}',
  constraint reminders_valid check (reminders <@ array['7d', '1d', '2h', '0h']::text[])
);

create table push_tokens (
  token text primary key,
  user_id uuid not null references profiles (id) on delete cascade,
  platform text,
  updated_at timestamptz not null default now()
);

-- File d'envoi + historique (affiché dans l'app). Remplie par des triggers,
-- vidée par la fonction Edge `send-push`.
create table notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles (id) on delete cascade,
  kind text not null,
  event_id uuid references events (id) on delete cascade,
  title text not null,
  body text not null,
  data jsonb not null default '{}',
  dedupe_key text,
  created_at timestamptz not null default now(),
  read_at timestamptz,
  sent_at timestamptz,
  skipped boolean not null default false
);
create index notifications_unsent on notifications (created_at) where sent_at is null and not skipped;
create index notifications_user on notifications (user_id, created_at desc);
create unique index notifications_dedupe on notifications (user_id, dedupe_key) where dedupe_key is not null;

-- ---------------------------------------------------------------------------
-- Fonctions d'aide (security definer pour éviter la récursion RLS)
-- ---------------------------------------------------------------------------
create function is_active() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and status = 'active');
$$;

create function is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and status = 'active' and role in ('admin', 'coadmin'));
$$;

create function is_organizer(e uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from events where id = e and created_by = auth.uid())
      or exists (select 1 from event_organizers where event_id = e and user_id = auth.uid());
$$;

create function can_see_event(e uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select is_admin() or is_organizer(e) or exists (
    select 1 from events ev
    where ev.id = e and is_active()
      and ev.status in ('published', 'cancelled')
      and (ev.visibility = 'all'
           or exists (select 1 from event_invites i where i.event_id = e and i.user_id = auth.uid()))
  );
$$;

-- Peut interagir (répondre, voter, écrire) : visible et publié.
create function can_participate(e uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select can_see_event(e) and exists (select 1 from events where id = e and status = 'published');
$$;

-- Destinataires "concernés" par un événement : participants (oui/peut-être),
-- votants du sondage de dates, organisateurs. Hors événements coupés.
create function event_audience(e uuid) returns setof uuid
language sql stable security definer set search_path = public as $$
  select distinct u from (
    select user_id u from rsvps where event_id = e and status in ('yes', 'maybe')
    union select dv.user_id from date_votes dv join date_options o on o.id = dv.option_id where o.event_id = e
    union select created_by from events where id = e
    union select user_id from event_organizers where event_id = e
  ) x
  where u not in (select user_id from event_mutes where event_id = e);
$$;

-- ---------------------------------------------------------------------------
-- Profils : création auto à l'inscription, premier inscrit = admin
-- ---------------------------------------------------------------------------
create function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
declare first boolean;
begin
  select not exists (select 1 from profiles) into first;
  insert into profiles (id, phone, role, status)
  values (new.id, new.phone,
          case when first then 'admin'::member_role else 'member' end,
          case when first then 'active'::member_status else 'pending' end);
  insert into notification_prefs (user_id) values (new.id);
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
for each row execute function handle_new_user();

-- Un membre ne peut pas changer son propre rôle ou statut.
create function guard_profile() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is not null and not is_admin() then
    new.role := old.role;
    new.status := old.status;
  end if;
  -- Seul un vrai admin peut nommer ou retirer un admin.
  if auth.uid() is not null and (new.role = 'admin' or old.role = 'admin') and new.role is distinct from old.role
     and not exists (select 1 from profiles where id = auth.uid() and role = 'admin') then
    new.role := old.role;
  end if;
  return new;
end $$;
create trigger profiles_guard before update on profiles for each row execute function guard_profile();

-- ---------------------------------------------------------------------------
-- Événements : workflow de validation
-- ---------------------------------------------------------------------------
create function guard_event() returns trigger
language plpgsql security definer set search_path = public as $$
declare s group_settings; me profiles; privileged boolean;
begin
  select * into s from group_settings;
  select * into me from profiles where id = auth.uid();
  new.updated_at := now();

  -- Appels serveur (cron, service role) : pas de garde.
  if auth.uid() is null then return new; end if;

  privileged := coalesce(me.role = 'admin' or (me.role = 'coadmin' and s.coadmins_skip_approval), false);

  if tg_op = 'INSERT' then
    new.created_by := auth.uid();
    new.approved_by := null; new.approved_at := null; new.rejection_reason := null;
    if new.status <> 'draft' then
      if privileged or not s.require_approval then
        new.status := 'published'; new.approved_by := auth.uid(); new.approved_at := now();
      else
        new.status := 'pending';
      end if;
    end if;
    return new;
  end if;

  -- UPDATE
  new.created_by := old.created_by;
  if is_admin() then
    if new.status = 'published' and old.status <> 'published' then
      new.approved_by := auth.uid(); new.approved_at := now(); new.rejection_reason := null;
    end if;
    return new;
  end if;

  -- Organisateur non-admin
  new.approved_by := old.approved_by; new.approved_at := old.approved_at;
  new.rejection_reason := old.rejection_reason;
  if old.status = 'published' then
    if new.status = 'cancelled' then return new; end if;
    if not s.organizers_can_edit_published then
      raise exception 'Seul l''admin peut modifier un événement publié';
    end if;
    new.status := 'published';
  elsif new.status = 'draft' then
    null; -- reste en brouillon
  elsif privileged or not s.require_approval then
    new.status := 'published'; new.approved_by := auth.uid(); new.approved_at := now();
  else
    -- Brouillon, en attente ou refusé : (re)part en validation
    new.status := 'pending'; new.rejection_reason := null;
  end if;
  return new;
end $$;
create trigger events_guard before insert or update on events for each row execute function guard_event();

create function approve_event(e uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not is_admin() then raise exception 'Réservé aux admins'; end if;
  update events set status = 'published', approved_by = auth.uid(), approved_at = now(), rejection_reason = null
  where id = e and status in ('pending', 'rejected', 'draft');
end $$;

create function reject_event(e uuid, reason text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not is_admin() then raise exception 'Réservé aux admins'; end if;
  update events set status = 'rejected', rejection_reason = reason where id = e and status = 'pending';
end $$;

-- Clôt le sondage de dates : fixe la date, convertit Oui -> Présent, Si besoin -> Peut-être.
create function do_fix_event_date(e uuid, opt uuid) returns void
language plpgsql security definer set search_path = public as $$
declare o date_options;
begin
  select * into o from date_options where id = opt and event_id = e;
  if not found then raise exception 'Créneau introuvable'; end if;
  update events set date_mode = 'fixed', starts_at = o.starts_at, ends_at = o.ends_at where id = e;
  insert into rsvps (event_id, user_id, status)
  select e, user_id, case vote when 'yes' then 'yes'::rsvp_status else 'maybe' end
  from date_votes where option_id = opt and vote in ('yes', 'if_needed')
  on conflict (event_id, user_id) do nothing;
  perform apply_waitlist(e);
end $$;
revoke execute on function do_fix_event_date(uuid, uuid) from public, anon, authenticated;

create function fix_event_date(e uuid, opt uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not (is_admin() or is_organizer(e)) then raise exception 'Réservé à l''organisateur'; end if;
  perform do_fix_event_date(e, opt);
end $$;

-- ---------------------------------------------------------------------------
-- Réponses : limite de places + liste d'attente
-- ---------------------------------------------------------------------------
create function apply_waitlist(e uuid) returns void
language plpgsql security definer set search_path = public as $$
declare ev events; taken int; r record;
begin
  select * into ev from events where id = e;
  if ev.max_participants is null then
    update rsvps set waitlisted = false where event_id = e and waitlisted;
    return;
  end if;
  taken := 0;
  for r in select * from rsvps where event_id = e and status = 'yes' order by waitlisted, updated_at loop
    if taken + 1 + r.plus_ones <= ev.max_participants then
      taken := taken + 1 + r.plus_ones;
      if r.waitlisted then
        update rsvps set waitlisted = false where event_id = e and user_id = r.user_id;
        -- updated_at = now() : réponse donnée dans cette transaction, pas une vraie attente
        if r.updated_at < now() and (select waitlist from notification_prefs where user_id = r.user_id) then
          perform queue_notification(r.user_id, 'waitlist', e, 'Une place s''est libérée',
            'Tu es inscrit à « ' || ev.title || ' ».');
        end if;
      end if;
    elsif not r.waitlisted then
      update rsvps set waitlisted = true where event_id = e and user_id = r.user_id;
    end if;
  end loop;
end $$;

create function guard_rsvp() returns trigger
language plpgsql security definer set search_path = public as $$
declare ev events;
begin
  if tg_op = 'UPDATE' and new.status = old.status and new.plus_ones = old.plus_ones
     and new.note is not distinct from old.note then
    return new; -- seul `waitlisted` change (apply_waitlist)
  end if;
  select * into ev from events where id = new.event_id;
  if new.status = 'maybe' and not ev.allow_maybe then raise exception 'Réponse « Peut-être » désactivée'; end if;
  if not ev.allow_plus_ones then new.plus_ones := 0;
  else new.plus_ones := least(new.plus_ones, ev.max_plus_ones); end if;
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline and auth.uid() is not null and not is_admin() then
    raise exception 'La date limite de réponse est passée';
  end if;
  new.updated_at := now();
  -- Un nouveau "oui" passe en fin de file : seul apply_waitlist décide.
  if tg_op = 'INSERT' or old.status <> 'yes' then new.waitlisted := true; end if;
  return new;
end $$;
create trigger rsvps_guard before insert or update on rsvps for each row execute function guard_rsvp();

create function after_rsvp() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  perform apply_waitlist(coalesce(new.event_id, old.event_id));
  return null;
end $$;
create trigger rsvps_after after insert or update of status, plus_ones or delete on rsvps
for each row execute function after_rsvp();

-- ---------------------------------------------------------------------------
-- Notifications : file d'attente
-- ---------------------------------------------------------------------------
create function queue_notification(u uuid, k text, e uuid, t text, b text, dedupe text default null, d jsonb default '{}')
returns void language plpgsql security definer set search_path = public as $$
begin
  if u = auth.uid() then return; end if; -- pas de notif pour sa propre action
  insert into notifications (user_id, kind, event_id, title, body, data, dedupe_key)
  values (u, k, e, t, b, d || jsonb_build_object('event_id', e, 'kind', k), dedupe)
  on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing;
end $$;

-- Publication / modification / annulation d'un événement
create function notify_event_change() returns trigger
language plpgsql security definer set search_path = public as $$
declare u uuid; tag_ids uuid[];
begin
  -- Nouvelle proposition -> admins
  if new.status = 'pending' and (tg_op = 'INSERT' or old.status <> 'pending') then
    for u in select p.id from profiles p join notification_prefs np on np.user_id = p.id
             where p.status = 'active' and p.role in ('admin', 'coadmin') and np.proposals loop
      perform queue_notification(u, 'proposal', new.id, 'Nouvelle proposition',
        '« ' || new.title || ' » attend ta validation.');
    end loop;
  end if;

  if tg_op = 'UPDATE' and new.status = 'rejected' and old.status <> 'rejected' then
    perform queue_notification(new.created_by, 'rejected', new.id, 'Proposition refusée',
      coalesce(new.rejection_reason, '« ' || new.title || ' » n''a pas été retenu.'));
  end if;

  -- Publication -> créateur + groupe selon préférences et abonnements
  if new.status = 'published' and (tg_op = 'INSERT' or old.status <> 'published') then
    if new.created_by <> coalesce(new.approved_by, new.created_by) then
      perform queue_notification(new.created_by, 'approved', new.id, 'Proposition validée',
        '« ' || new.title || ' » est publié.');
    end if;
    if new.notify_on_publish then
      select coalesce(array_agg(tag_id), '{}') into tag_ids from event_tags where event_id = new.id;
      for u in
        select p.id from profiles p join notification_prefs np on np.user_id = p.id
        where p.status = 'active' and p.id <> new.created_by
          and (new.visibility = 'all' or exists (select 1 from event_invites i where i.event_id = new.id and i.user_id = p.id))
          and (np.new_event = 'all' or (np.new_event = 'subscribed' and (
                exists (select 1 from tag_subscriptions ts where ts.user_id = p.id and ts.tag_id = any (tag_ids))
             or exists (select 1 from category_subscriptions cs where cs.user_id = p.id and cs.category_id = new.category_id))))
      loop
        perform queue_notification(u, 'new_event', new.id,
          case when new.date_mode = 'poll' then 'Nouveau sondage de dates' else 'Nouvel événement' end,
          new.title, 'new_event:' || new.id);
      end loop;
    end if;
  end if;

  if tg_op = 'UPDATE' and old.status = 'published' then
    if new.status = 'cancelled' then
      for u in select event_audience(new.id) loop
        perform queue_notification(u, 'event_changed', new.id, 'Événement annulé', '« ' || new.title || ' » est annulé.');
      end loop;
    elsif old.date_mode = 'poll' and new.date_mode = 'fixed' then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.date_fixed loop
        perform queue_notification(u, 'date_fixed', new.id, 'Date fixée',
          new.title || ' : ' || to_char(new.starts_at at time zone 'Europe/Zurich', 'DD.MM à HH24:MI'));
      end loop;
    elsif new.starts_at is distinct from old.starts_at or new.location_name is distinct from old.location_name
       or new.location_address is distinct from old.location_address then
      for u in select a from event_audience(new.id) a join notification_prefs np on np.user_id = a where np.event_changed loop
        perform queue_notification(u, 'event_changed', new.id, 'Événement modifié',
          '« ' || new.title || ' » : la date ou le lieu a changé.');
      end loop;
    end if;
  end if;
  return null;
end $$;
create trigger events_notify after insert or update on events for each row execute function notify_event_change();

-- Réponse -> organisateurs
create function notify_rsvp() returns trigger
language plpgsql security definer set search_path = public as $$
declare ev events; who text; u uuid;
begin
  if tg_op = 'UPDATE' and new.status = old.status then return null; end if;
  -- Réponses créées automatiquement (clôture d'un sondage) : pas de notif
  if auth.uid() is distinct from new.user_id then return null; end if;
  select * into ev from events where id = new.event_id;
  select display_name into who from profiles where id = new.user_id;
  for u in select x from (select ev.created_by x union select user_id from event_organizers where event_id = ev.id) o
           join notification_prefs np on np.user_id = o.x where np.rsvp_mine loop
    perform queue_notification(u, 'rsvp', ev.id, ev.title,
      who || case new.status when 'yes' then ' vient' when 'maybe' then ' viendra peut-être' else ' ne vient pas' end);
  end loop;
  return null;
end $$;
create trigger rsvps_notify after insert or update of status on rsvps for each row execute function notify_rsvp();

-- Nouveau sondage dans un événement publié
create function notify_poll() returns trigger
language plpgsql security definer set search_path = public as $$
declare ev events; u uuid;
begin
  if new.event_id is null then return null; end if;
  select * into ev from events where id = new.event_id;
  if ev.status <> 'published' then return null; end if;
  for u in select a from event_audience(ev.id) a join notification_prefs np on np.user_id = a where np.poll_new loop
    perform queue_notification(u, 'poll_new', ev.id, ev.title, 'Nouveau sondage : ' || new.question);
  end loop;
  return null;
end $$;
create trigger polls_notify after insert on polls for each row execute function notify_poll();

-- Message du forum
create function notify_message() returns trigger
language plpgsql security definer set search_path = public as $$
declare ev events; who text; reply_author uuid; u uuid; np notification_prefs;
begin
  select * into ev from events where id = new.event_id;
  select display_name into who from profiles where id = new.user_id;
  select user_id into reply_author from messages where id = new.reply_to;
  for u in select distinct x from (
      select a x from event_audience(ev.id) a
      union select user_id from messages where event_id = ev.id
      union select unnest(new.mentions)
    ) s
    where x not in (select user_id from event_mutes where event_id = ev.id) loop
    select * into np from notification_prefs where user_id = u;
    if np.chat = 'all' or (np.chat = 'mentions' and (u = any (new.mentions) or u = reply_author)) then
      perform queue_notification(u, 'message', ev.id, ev.title, who || ' : ' || left(new.body, 140));
    end if;
  end loop;
  return null;
end $$;
create trigger messages_notify after insert on messages for each row execute function notify_message();

-- Tâches planifiées : rappels, relance des non-votants, clôture auto des sondages.
-- Appelée toutes les 5 minutes par pg_cron (voir plus bas).
create function run_scheduled_jobs() returns void
language plpgsql security definer set search_path = public as $$
declare ev events; r record; best uuid;
begin
  -- Rappels avant l'événement
  for r in
    select e.id, e.title, e.starts_at, off, a.uid
    from events e
    cross join lateral unnest(e.reminders) off
    cross join lateral (select user_id uid from rsvps where event_id = e.id and status in ('yes', 'maybe') and not waitlisted) a
    join notification_prefs np on np.user_id = a.uid
    cross join lateral (select case off when '7d' then interval '7 days' when '1d' then interval '1 day'
                                        when '2h' then interval '2 hours' else interval '0' end iv) w
    where e.status = 'published' and e.starts_at > now() - interval '30 minutes'
      and off = any (np.reminders)
      and a.uid not in (select user_id from event_mutes where event_id = e.id)
      and now() between e.starts_at - w.iv and e.starts_at - w.iv + interval '30 minutes'
  loop
    perform queue_notification(r.uid, 'reminder', r.id,
      case r.off when '7d' then 'Dans une semaine' when '1d' then 'C''est demain' when '2h' then 'Dans 2 heures' else 'C''est maintenant' end,
      r.title || ' · ' || to_char(r.starts_at at time zone 'Europe/Zurich', 'DD.MM HH24:MI'),
      'reminder:' || r.id || ':' || r.off);
  end loop;

  -- Relance 24 h avant la fin d'un sondage de dates
  for r in
    select e.id, e.title, p.id uid from events e cross join profiles p
    join notification_prefs np on np.user_id = p.id
    where e.status = 'published' and e.date_mode = 'poll' and e.poll_deadline between now() and now() + interval '24 hours'
      and p.status = 'active' and np.poll_nudge
      and (e.visibility = 'all' or exists (select 1 from event_invites i where i.event_id = e.id and i.user_id = p.id))
      and not exists (select 1 from date_votes v join date_options o on o.id = v.option_id where o.event_id = e.id and v.user_id = p.id)
  loop
    perform queue_notification(r.uid, 'poll_nudge', r.id, 'Plus que 24 h pour voter', r.title, 'poll_nudge:' || r.id);
  end loop;

  -- Clôture automatique : la date avec le plus de Oui (Si besoin = départage)
  for ev in select * from events where status = 'published' and date_mode = 'poll' and auto_fix_date and poll_deadline <= now() loop
    select o.id into best from date_options o left join date_votes v on v.option_id = o.id
    where o.event_id = ev.id group by o.id, o.starts_at
    order by count(*) filter (where v.vote = 'yes') desc, count(*) filter (where v.vote = 'if_needed') desc, o.starts_at
    limit 1;
    if best is not null then perform do_fix_event_date(ev.id, best); end if;
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table profiles enable row level security;
alter table group_settings enable row level security;
alter table categories enable row level security;
alter table tags enable row level security;
alter table tag_subscriptions enable row level security;
alter table category_subscriptions enable row level security;
alter table events enable row level security;
alter table event_tags enable row level security;
alter table event_organizers enable row level security;
alter table event_invites enable row level security;
alter table event_mutes enable row level security;
alter table rsvps enable row level security;
alter table date_options enable row level security;
alter table date_votes enable row level security;
alter table polls enable row level security;
alter table poll_options enable row level security;
alter table poll_votes enable row level security;
alter table bring_items enable row level security;
alter table messages enable row level security;
alter table message_reactions enable row level security;
alter table notification_prefs enable row level security;
alter table push_tokens enable row level security;
alter table notifications enable row level security;

-- Profils
create policy "profils visibles par les membres" on profiles for select using (id = auth.uid() or is_active());
create policy "modifier son profil" on profiles for update using (id = auth.uid() or is_admin());

-- Réglages du groupe
create policy "lire réglages" on group_settings for select using (true);
create policy "admin réglages" on group_settings for update using (is_admin());

-- Catégories & tags
create policy "lire catégories" on categories for select using (is_active());
create policy "admin catégories" on categories for all using (is_admin()) with check (is_admin());
create policy "lire tags" on tags for select using (is_active());
create policy "admin tags" on tags for all using (is_admin()) with check (is_admin());
create policy "membres créent tags" on tags for insert
  with check (is_active() and (select members_can_create_tags from group_settings) and created_by = auth.uid());

create policy "mes abonnements tags" on tag_subscriptions for all
  using (user_id = auth.uid()) with check (user_id = auth.uid() and is_active());
create policy "mes abonnements catégories" on category_subscriptions for all
  using (user_id = auth.uid()) with check (user_id = auth.uid() and is_active());

-- Événements
create policy "voir événements" on events for select
  using (can_see_event(id) or created_by = auth.uid());
create policy "proposer événement" on events for insert with check (is_active());
create policy "modifier événement" on events for update using (is_admin() or is_organizer(id));
create policy "supprimer événement" on events for delete
  using (is_admin() or (created_by = auth.uid() and status in ('draft', 'pending', 'rejected')));

create policy "voir tags événement" on event_tags for select using (can_see_event(event_id) or is_organizer(event_id));
create policy "gérer tags événement" on event_tags for all
  using (is_admin() or is_organizer(event_id)) with check (is_admin() or is_organizer(event_id));

create policy "voir organisateurs" on event_organizers for select using (can_see_event(event_id) or is_organizer(event_id));
create policy "gérer organisateurs" on event_organizers for all
  using (is_admin() or is_organizer(event_id)) with check (is_admin() or is_organizer(event_id));

create policy "voir invités" on event_invites for select using (is_admin() or is_organizer(event_id) or user_id = auth.uid());
create policy "gérer invités" on event_invites for all
  using (is_admin() or is_organizer(event_id)) with check (is_admin() or is_organizer(event_id));

create policy "mes sourdines" on event_mutes for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Réponses
create policy "voir réponses" on rsvps for select using (
  user_id = auth.uid() or is_admin() or is_organizer(event_id)
  or (can_see_event(event_id) and (select show_participants from events where id = event_id)));
create policy "répondre" on rsvps for insert with check (user_id = auth.uid() and can_participate(event_id));
create policy "changer sa réponse" on rsvps for update using (user_id = auth.uid() and can_participate(event_id));
create policy "retirer sa réponse" on rsvps for delete using (user_id = auth.uid() or is_admin());

-- Sondage de dates
create policy "voir créneaux" on date_options for select using (can_see_event(event_id) or is_organizer(event_id));
create policy "organisateur gère créneaux" on date_options for all
  using (is_admin() or is_organizer(event_id)) with check (is_admin() or is_organizer(event_id));
create policy "membre propose créneau" on date_options for insert with check (
  proposed_by = auth.uid() and can_participate(event_id)
  and (select members_can_propose_dates and date_mode = 'poll' from events where id = event_id));

create policy "voir votes dates" on date_votes for select using (
  exists (select 1 from date_options o where o.id = option_id and can_see_event(o.event_id)));
create policy "voter date" on date_votes for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid() and exists (
    select 1 from date_options o join events e on e.id = o.event_id
    where o.id = option_id and can_participate(o.event_id) and e.date_mode = 'poll'
      and (e.poll_deadline is null or e.poll_deadline > now())));

-- Mini-sondages
create policy "voir sondages" on polls for select using (
  (event_id is null and is_active()) or can_see_event(event_id) or is_organizer(event_id));
create policy "créer sondage" on polls for insert with check (
  created_by = auth.uid() and (is_admin() or is_organizer(event_id)));
create policy "gérer sondage" on polls for update using (is_admin() or created_by = auth.uid() or is_organizer(event_id));
create policy "supprimer sondage" on polls for delete using (is_admin() or created_by = auth.uid() or is_organizer(event_id));

create policy "voir options" on poll_options for select using (
  exists (select 1 from polls p where p.id = poll_id and ((p.event_id is null and is_active()) or can_see_event(p.event_id) or is_organizer(p.event_id))));
create policy "ajouter option" on poll_options for insert with check (exists (
  select 1 from polls p where p.id = poll_id and (
    is_admin() or p.created_by = auth.uid() or is_organizer(p.event_id)
    or (p.members_can_add_options and poll_options.created_by = auth.uid()
        and (p.event_id is null or can_participate(p.event_id))))));
create policy "gérer options" on poll_options for update using (exists (
  select 1 from polls p where p.id = poll_id and (is_admin() or p.created_by = auth.uid() or is_organizer(p.event_id))));
create policy "supprimer options" on poll_options for delete using (exists (
  select 1 from polls p where p.id = poll_id and (is_admin() or p.created_by = auth.uid() or is_organizer(p.event_id))));

-- Votes : on voit les votes des autres seulement si le sondage n'est pas anonyme
-- (les totaux anonymes passent par la vue poll_results).
create policy "voir votes" on poll_votes for select using (
  user_id = auth.uid() or exists (
    select 1 from polls p where p.id = poll_id and not p.anonymous
      and ((p.event_id is null and is_active()) or can_see_event(p.event_id))));
create policy "voter" on poll_votes for insert with check (
  user_id = auth.uid() and exists (
    select 1 from polls p join poll_options o on o.poll_id = p.id
    where p.id = poll_votes.poll_id and o.id = poll_votes.option_id
      and (p.closes_at is null or p.closes_at > now())
      and ((p.event_id is null and is_active()) or can_participate(p.event_id))));
create policy "retirer vote" on poll_votes for delete using (user_id = auth.uid());

-- Choix unique : un seul vote par sondage
create function guard_poll_vote() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if not (select multiple_choice from polls where id = new.poll_id) then
    delete from poll_votes where poll_id = new.poll_id and user_id = new.user_id and option_id <> new.option_id;
  end if;
  return new;
end $$;
create trigger poll_votes_guard before insert on poll_votes for each row execute function guard_poll_vote();

create view poll_results with (security_invoker = false) as
  select o.poll_id, o.id as option_id, count(v.user_id)::int as votes
  from poll_options o left join poll_votes v on v.option_id = o.id
  where exists (select 1 from polls p where p.id = o.poll_id
                and ((p.event_id is null and is_active()) or can_see_event(p.event_id))
                and (not p.results_after_vote or is_admin() or p.created_by = auth.uid()
                     or exists (select 1 from poll_votes mv where mv.poll_id = p.id and mv.user_id = auth.uid())))
  group by o.poll_id, o.id;

-- Qui amène quoi
create policy "voir objets" on bring_items for select using (can_see_event(event_id) or is_organizer(event_id));
create policy "organisateur gère objets" on bring_items for all
  using (is_admin() or is_organizer(event_id)) with check (is_admin() or is_organizer(event_id));
create policy "prendre un objet" on bring_items for update using (
  can_participate(event_id) and (claimed_by is null or claimed_by = auth.uid()))
  with check (claimed_by is null or claimed_by = auth.uid());

-- Forum
create policy "lire messages" on messages for select using (can_see_event(event_id));
create policy "écrire message" on messages for insert with check (
  user_id = auth.uid() and can_participate(event_id) and (select forum_enabled from events where id = event_id));
create policy "modifier message" on messages for update using (user_id = auth.uid() or is_admin() or is_organizer(event_id));
create policy "supprimer message" on messages for delete using (user_id = auth.uid() or is_admin());

create policy "voir réactions" on message_reactions for select using (
  exists (select 1 from messages m where m.id = message_id and can_see_event(m.event_id)));
create policy "réagir" on message_reactions for insert with check (
  user_id = auth.uid() and exists (select 1 from messages m where m.id = message_id and can_participate(m.event_id)));
create policy "retirer réaction" on message_reactions for delete using (user_id = auth.uid());

-- Notifications
create policy "mes préférences" on notification_prefs for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "mes appareils" on push_tokens for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "mes notifications" on notifications for select using (user_id = auth.uid());
create policy "marquer lu" on notifications for update using (user_id = auth.uid());

-- Temps réel pour le forum, les réponses et les votes
alter publication supabase_realtime add table messages, message_reactions, rsvps, date_votes, poll_votes;
