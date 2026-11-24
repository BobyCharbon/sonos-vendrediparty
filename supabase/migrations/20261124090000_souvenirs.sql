-- Souvenirs (avis 74d36b93e7bd, 24.11.2026, corrections de l'admin du même jour) : le socle en base.
--
-- Option par événement (events.souvenirs_enabled, éteinte par défaut, jamais allumée par l'IA : hors de son schéma).
-- - Qui prend : Présent, Peut-être et l'organisation (créateur, co-organisateurs), profil complet, CGU acceptées.
-- - Quand : du début à la fin + 2 h (sans heure de fin : début + 12 h), et avant le dévoilement. 3 photos par personne,
--   jamais revues ; annulables 5 s (8 s en base, pour le réseau).
-- - Dévoilement : fin + 24 h (souvenirs_reveal_at null), avancé par l'organisation (souvenir_reveal_now), jamais avant la
--   fin. Notification souvenirs_revealed au cercle (interrupteur notification_prefs.souvenirs).
-- - Story : 24 h après le dévoilement, TOUTES les photos au cercle (Présent, Peut-être, organisation), blocage dans les
--   deux sens. Pendant la story, « ⭐ Garder dans mes souvenirs » (souvenir_keeps : une référence, jamais une copie), si
--   souvenirs_keep (vrai par défaut). Mes propres photos sont d'office dans mes souvenirs.
-- - Après la story : souvenirs_keep vrai → « Mes souvenirs » (mes photos + gardées) 13 mois ; faux → tout est effacé.
-- - Relecture : l'organisation (créateur, co-organisateurs, events.manage_all) voit TOUJOURS les photos avant le
--   dévoilement et peut en retirer (souvenir_review / souvenir_remove), sans réglage.
-- - Signaler (report_content, type « souvenir », motif my_image « Je suis sur la photo… » en plus des habituels) :
--   masquée aussitôt pour tous, gardées comprises ; modération de Party ET organisation prévenues (souvenir_reported).
--   L'organisation la retire (souvenir_remove) ou la remet (souvenir_restore) ; la modération a le dernier mot
--   (« Masquer » l'efface, « Classer » la remet).
-- - Réglages figés dès la 1re photo (souvenirs_locked). Fichiers : compartiment privé « souvenirs »
--   (<événement>/<auteur>/<id>.jpg), envoyés par le serveur (EXIF / GPS retirés, 1600 px), lus par liens signés ;
--   toute ligne effacée (auteur, organisation, modération, compte, événement, story sans « garder », 13 mois) met
--   son fichier à la corbeille, vidée par la base (souvenir_files_gc, API Storage avec la clé du coffre).
-- Purement additive et rejouable.

-- ───────────── Événement : options ─────────────
alter table public.events add column if not exists souvenirs_enabled boolean not null default false;
alter table public.events add column if not exists souvenirs_keep boolean not null default true;
alter table public.events add column if not exists souvenirs_reveal_at timestamptz;
alter table public.events add column if not exists souvenirs_locked boolean not null default false;
comment on column public.events.souvenirs_enabled is 'Souvenirs : appareil photo de la soirée (option de l''organisation, 24.11).';
comment on column public.events.souvenirs_keep is 'Souvenirs : garder les photos après la story de 24 h (vrai par défaut).';
comment on column public.events.souvenirs_reveal_at is 'Souvenirs : dévoilement avancé par l''organisation (null = fin + 24 h).';
comment on column public.events.souvenirs_locked is 'Souvenirs : réglages figés dès la 1re photo.';

alter table public.notification_prefs add column if not exists souvenirs boolean not null default true;

-- ───────────── Tables (aucun accès direct : tout passe par les fonctions souvenir_*) ─────────────
create table if not exists public.souvenir_photos (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events (id) on delete cascade,
  author_id uuid not null references public.profiles (id) on delete cascade,
  path text not null unique check (path ~ '^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$'),
  taken_at timestamptz not null default now(),
  hidden_at timestamptz,      -- signalée : masquée pour tous en attendant l'organisation ou la modération
  restored_at timestamptz,    -- remise par l'organisation
  restored_by uuid references public.profiles (id) on delete set null
);
comment on table public.souvenir_photos is 'Souvenirs : photos prises pendant un événement (3 par personne), fichiers dans le compartiment souvenirs.';
create index if not exists souvenir_photos_event on public.souvenir_photos (event_id, taken_at);
create index if not exists souvenir_photos_author on public.souvenir_photos (author_id, event_id);
alter table public.souvenir_photos enable row level security;
revoke all on public.souvenir_photos from anon, authenticated;

create table if not exists public.souvenir_keeps (
  photo_id uuid not null references public.souvenir_photos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  kept_at timestamptz not null default now(),
  primary key (photo_id, user_id)
);
comment on table public.souvenir_keeps is 'Souvenirs : photo d''un autre gardée pendant la story (référence, jamais une copie).';
create index if not exists souvenir_keeps_user on public.souvenir_keeps (user_id);
alter table public.souvenir_keeps enable row level security;
revoke all on public.souvenir_keeps from anon, authenticated;

create table if not exists public.souvenir_seen (
  event_id uuid not null references public.events (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  seen_at timestamptz not null default now(),
  primary key (event_id, user_id)
);
comment on table public.souvenir_seen is 'Souvenirs : story vue (anneau de la bulle).';
alter table public.souvenir_seen enable row level security;
revoke all on public.souvenir_seen from anon, authenticated;

create table if not exists private.souvenir_runs (
  event_id uuid primary key references public.events (id) on delete cascade,
  revealed_at timestamptz,
  purged_at timestamptz
);
create table if not exists private.souvenir_trash (
  path text primary key,
  at timestamptz not null default now()
);
create table if not exists private.souvenir_gc_runs (
  id integer primary key default 1 check (id = 1),
  last_at timestamptz not null,
  removed int
);
revoke all on private.souvenir_runs, private.souvenir_trash, private.souvenir_gc_runs from public, anon, authenticated;

-- Toute ligne effacée (cascade du compte ou de l'événement comprise) : son fichier part à la corbeille.
create or replace function private.souvenir_trash_file() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into private.souvenir_trash (path) values (old.path) on conflict do nothing;
  return null;
end $$;
revoke all on function private.souvenir_trash_file() from public, anon, authenticated;
drop trigger if exists souvenir_trash_file on public.souvenir_photos;
create trigger souvenir_trash_file after delete on public.souvenir_photos
  for each row execute function private.souvenir_trash_file();

-- Temps réel : chaque photo (prise, annulée, retirée, signalée) relit la fiche (compteur) par le signal event:<id>.
drop trigger if exists event_changed on public.souvenir_photos;
create trigger event_changed after insert or update or delete on public.souvenir_photos
  for each row execute function private.event_changed();

-- ───────────── Règles ─────────────
-- Le cercle : organisation (créateur, co-organisateurs), Présent, Peut-être ; compte actif.
create or replace function private.souvenir_circle(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select u is not null and private.is_account_active(u) and (
    exists (select 1 from public.events ev where ev.id = e and ev.created_by = u)
    or exists (select 1 from public.event_organizers o where o.event_id = e and o.user_id = u)
    or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = u and r.status in ('yes', 'maybe')));
$$;
revoke all on function private.souvenir_circle(uuid, uuid) from public, anon, authenticated;

-- L'organisation : créateur, co-organisateurs, droit events.manage_all.
create or replace function private.souvenir_staff(e uuid, u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select u is not null and private.is_account_active(u) and (
    exists (select 1 from public.events ev where ev.id = e and ev.created_by = u)
    or exists (select 1 from public.event_organizers o where o.event_id = e and o.user_id = u)
    or private.user_has(u, 'events.manage_all'));
$$;
revoke all on function private.souvenir_staff(uuid, uuid) from public, anon;
grant execute on function private.souvenir_staff(uuid, uuid) to authenticated;  -- garde des colonnes (déclencheur)

create or replace function private.souvenir_end(ev public.events) returns timestamptz
language sql immutable set search_path = '' as $$
  select coalesce(ev.ends_at, ev.starts_at + interval '12 hours');
$$;
create or replace function private.souvenir_reveal_at(ev public.events) returns timestamptz
language sql immutable set search_path = '' as $$
  select coalesce(ev.souvenirs_reveal_at, private.souvenir_end(ev) + interval '24 hours');
$$;
-- off | soon (avant le début) | open (prise de vue) | waiting (fermé, avant le dévoilement) | story (24 h) | after
create or replace function private.souvenir_phase(ev public.events) returns text
language plpgsql stable set search_path = '' as $$
declare rv timestamptz := private.souvenir_reveal_at(ev);
begin
  if not coalesce(ev.souvenirs_enabled, false) then return 'off'; end if;
  if ev.starts_at is null or now() < ev.starts_at then return 'soon'; end if;
  if now() >= rv + interval '24 hours' then return 'after'; end if;
  if now() >= rv then return 'story'; end if;
  if now() < private.souvenir_end(ev) + interval '2 hours' then return 'open'; end if;
  return 'waiting';
end $$;
revoke all on function private.souvenir_end(public.events), private.souvenir_reveal_at(public.events),
  private.souvenir_phase(public.events) from public, anon, authenticated;

-- Une photo que u peut voir maintenant (jamais masquée ni d'une personne en blocage, dans un sens ou dans l'autre).
create or replace function private.souvenir_visible(p public.souvenir_photos, u uuid) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare ev public.events; ph text;
begin
  if p.id is null or u is null or p.hidden_at is not null or private.blocked_either(u, p.author_id) then return false; end if;
  select * into ev from public.events where id = p.event_id;
  ph := private.souvenir_phase(ev);
  if ph in ('soon', 'open', 'waiting') then
    return private.souvenir_staff(ev.id, u);                                    -- relecture de l'organisation
  elsif ph = 'story' then
    return private.souvenir_circle(ev.id, u) or private.souvenir_staff(ev.id, u) or p.author_id = u;
  elsif ph = 'after' then
    return ev.souvenirs_keep and (p.author_id = u
      or exists (select 1 from public.souvenir_keeps k where k.photo_id = p.id and k.user_id = u));
  end if;
  return false;  -- option éteinte : plus rien n'est montré
end $$;
revoke all on function private.souvenir_visible(public.souvenir_photos, uuid) from public, anon, authenticated;

-- Garde des colonnes de l'événement (sans security definer : current_user dit qui écrit). Une personne (rôle
-- authenticated) : seule l'organisation change l'option ; dévoilement et verrou passent par les fonctions ; figé dès
-- la 1re photo. Les fonctions souvenir_* (propriétaire postgres) et la base elle-même passent.
create or replace function private.souvenirs_guard() returns trigger
language plpgsql set search_path = '' as $$
begin
  if current_user not in ('authenticated', 'anon') then return new; end if;
  if tg_op = 'INSERT' then
    new.souvenirs_locked := false;
    new.souvenirs_reveal_at := null;
    return new;
  end if;
  if new.souvenirs_locked is distinct from old.souvenirs_locked or new.souvenirs_reveal_at is distinct from old.souvenirs_reveal_at then
    raise exception 'forbidden: le dévoilement des souvenirs passe par « Dévoiler maintenant »' using errcode = '42501';
  end if;
  if new.souvenirs_enabled is distinct from old.souvenirs_enabled or new.souvenirs_keep is distinct from old.souvenirs_keep then
    if not private.souvenir_staff(new.id, auth.uid()) then
      raise exception 'forbidden: seule l''organisation règle les Souvenirs' using errcode = '42501';
    end if;
    if old.souvenirs_locked then
      raise exception 'locked: les réglages des Souvenirs sont figés depuis la première photo' using errcode = '42501';
    end if;
  end if;
  return new;
end $$;
revoke all on function private.souvenirs_guard() from public, anon, authenticated;
drop trigger if exists souvenirs_guard on public.events;
create trigger souvenirs_guard before insert or update on public.events
  for each row execute function private.souvenirs_guard();

-- ───────────── Compartiment privé ─────────────
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('souvenirs', 'souvenirs', false, 4 * 1024 * 1024, array['image/jpeg'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Déposer : dans son dossier <événement>/<moi>/, quand je peux encore prendre une photo.
create or replace function private.souvenir_may_upload(name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); e uuid; ev public.events;
begin
  if me is null or name !~ '^[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$' or split_part(name, '/', 2) <> me::text then
    return false;
  end if;
  e := split_part(name, '/', 1)::uuid;
  select * into ev from public.events where id = e;
  return ev.id is not null and ev.status = 'published' and private.souvenir_phase(ev) = 'open'
    and private.souvenir_circle(e, me)
    and (select count(*) from public.souvenir_photos p where p.event_id = e and p.author_id = me) < 3;
end $$;
-- Lire (liens signés) : une photo visible pour moi, ou signalée et lue par la modération.
create or replace function private.souvenir_may_read(name text) returns boolean
language plpgsql stable security definer set search_path = '' as $$
declare p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos where path = name;
  if p.id is null then return false; end if;
  return private.souvenir_visible(p, auth.uid())
    or (public.has_perm('moderation.reports') and exists (select 1 from public.content_reports r
          where r.target_kind = 'souvenir' and r.target_id = p.id::text));
end $$;
-- Effacer : seulement un fichier à moi qu'aucune photo ne désigne (envoi refusé ensuite par souvenir_take).
create or replace function private.souvenir_may_drop(name text) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and split_part(name, '/', 2) = auth.uid()::text
    and not exists (select 1 from public.souvenir_photos p where p.path = name);
$$;
revoke all on function private.souvenir_may_upload(text), private.souvenir_may_read(text), private.souvenir_may_drop(text)
  from public, anon;
grant execute on function private.souvenir_may_upload(text), private.souvenir_may_read(text), private.souvenir_may_drop(text)
  to authenticated;

drop policy if exists "souvenirs : déposer" on storage.objects;
create policy "souvenirs : déposer" on storage.objects for insert to authenticated
  with check (bucket_id = 'souvenirs' and private.souvenir_may_upload(name));
drop policy if exists "souvenirs : voir" on storage.objects;
create policy "souvenirs : voir" on storage.objects for select to authenticated
  using (bucket_id = 'souvenirs' and private.souvenir_may_read(name));
drop policy if exists "souvenirs : retirer son envoi refusé" on storage.objects;
create policy "souvenirs : retirer son envoi refusé" on storage.objects for delete to authenticated
  using (bucket_id = 'souvenirs' and private.souvenir_may_drop(name));

-- ───────────── Lecture ─────────────
create or replace function private.souvenir_json(p public.souvenir_photos, me uuid, origin text default null) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', p.id, 'event_id', p.event_id, 'path', p.path, 'taken_at', p.taken_at,
    'mine', p.author_id = me,
    'author', (select jsonb_build_object('id', a.id, 'name', a.display_name, 'avatar_url', a.avatar_url)
               from public.profiles a where a.id = p.author_id))
    || case when origin is null then '{}'::jsonb else jsonb_build_object('origin', origin) end;
$$;
revoke all on function private.souvenir_json(public.souvenir_photos, uuid, text) from public, anon, authenticated;

-- État de la fiche : le NOMBRE de photos seulement (jamais qui ni quoi), phase, dates, ce que je peux faire.
create or replace function public.souvenir_counter(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events; member boolean; staff boolean; mine int; seen boolean;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not public.can_see_event(e) then
    raise exception 'not_found: événement introuvable' using errcode = 'PT404';
  end if;
  if not ev.souvenirs_enabled then return jsonb_build_object('enabled', false); end if;
  member := private.souvenir_circle(e, me);
  staff := private.souvenir_staff(e, me);
  select count(*) into mine from public.souvenir_photos p where p.event_id = e and p.author_id = me;
  seen := exists (select 1 from public.souvenir_seen s where s.event_id = e and s.user_id = me);
  return jsonb_build_object('enabled', true, 'keep', ev.souvenirs_keep, 'locked', ev.souvenirs_locked,
    'phase', private.souvenir_phase(ev),
    'count', (select count(*) from public.souvenir_photos p where p.event_id = e and p.hidden_at is null
              and not private.blocked_either(me, p.author_id)),
    'take_from', ev.starts_at, 'take_until', least(private.souvenir_end(ev) + interval '2 hours', private.souvenir_reveal_at(ev)),
    'reveal_at', private.souvenir_reveal_at(ev), 'story_until', private.souvenir_reveal_at(ev) + interval '24 hours',
    'can_reveal_now', staff and private.souvenir_phase(ev) in ('open', 'waiting') and now() >= private.souvenir_end(ev),
    'member', member, 'staff', staff, 'max', 3, 'taken', mine, 'left', case when member then greatest(0, 3 - mine) else 0 end,
    'can_take', member and ev.status = 'published' and private.souvenir_phase(ev) = 'open' and mine < 3,
    'seen', seen);
end $$;

-- Story (24 h) : toutes les photos, de la première à la dernière ; « kept » / « can_keep » pour ⭐.
create or replace function public.souvenir_story(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not (private.souvenir_circle(e, me) or private.souvenir_staff(e, me)) then
    raise exception 'forbidden: la story est réservée aux participants (Présent ou Peut-être) et à l''organisation' using errcode = '42501';
  end if;
  if private.souvenir_phase(ev) <> 'story' then
    raise exception 'closed: la story n''est pas visible maintenant' using errcode = '22023';
  end if;
  return jsonb_build_object('event_id', e, 'title', ev.title, 'keep', ev.souvenirs_keep,
    'until', private.souvenir_reveal_at(ev) + interval '24 hours',
    'photos', coalesce((select jsonb_agg(private.souvenir_json(p, me) || jsonb_build_object(
        'kept', exists (select 1 from public.souvenir_keeps k where k.photo_id = p.id and k.user_id = me),
        'can_keep', ev.souvenirs_keep and p.author_id <> me) order by p.taken_at, p.id)
      from public.souvenir_photos p where p.event_id = e and private.souvenir_visible(p, me)), '[]'::jsonb));
end $$;

-- Mes souvenirs : mes photos (« taken ») et celles que j'ai gardées (« kept »), ordre chronologique, après le dévoilement.
create or replace function public.souvenir_mine(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events; ph text;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or me is null or not public.can_see_event(e) then
    raise exception 'not_found: événement introuvable' using errcode = 'PT404';
  end if;
  ph := private.souvenir_phase(ev);
  if ph not in ('story', 'after') or not ev.souvenirs_keep then
    return jsonb_build_object('keep', ev.souvenirs_keep, 'phase', ph, 'photos', '[]'::jsonb);
  end if;
  return jsonb_build_object('keep', true, 'phase', ph, 'photos', coalesce((select jsonb_agg(x.j order by x.at, x.id) from (
      select private.souvenir_json(p, me, case when p.author_id = me then 'taken' else 'kept' end) j, p.taken_at at, p.id
      from public.souvenir_photos p where p.event_id = e and private.souvenir_visible(p, me)
        and (p.author_id = me or exists (select 1 from public.souvenir_keeps k where k.photo_id = p.id and k.user_id = me))) x),
    '[]'::jsonb));
end $$;

-- Relecture de l'organisation (toujours permise, sans réglage) : avant le dévoilement, toutes les photos visibles.
create or replace function public.souvenir_review(e uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not private.souvenir_staff(e, me) then
    raise exception 'forbidden: la relecture est réservée à l''organisation' using errcode = '42501';
  end if;
  return jsonb_build_object('phase', private.souvenir_phase(ev),
    'photos', coalesce((select jsonb_agg(private.souvenir_json(p, me) order by p.taken_at, p.id)
      from public.souvenir_photos p where p.event_id = e and p.hidden_at is null and not private.blocked_either(me, p.author_id)), '[]'::jsonb),
    -- Signalées, masquées en attendant : l'organisation les retire ou les remet ; motifs des signalements ouverts
    -- (jamais qui a signalé).
    'reported', coalesce((select jsonb_agg(private.souvenir_json(p, me) || jsonb_build_object('hidden_at', p.hidden_at,
        'reasons', (select coalesce(jsonb_agg(distinct r.reason), '[]'::jsonb) from public.content_reports r
                    where r.target_kind = 'souvenir' and r.target_id = p.id::text and r.status = 'open')) order by p.taken_at)
      from public.souvenir_photos p where p.event_id = e and p.hidden_at is not null), '[]'::jsonb));
end $$;

-- Bulles de story (Discussions) : mes stories en cours, avec au moins une photo, vues ou non.
create or replace function public.souvenir_stories() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('event_id', ev.id, 'title', ev.title,
      'until', private.souvenir_reveal_at(ev) + interval '24 hours', 'count', x.n,
      'seen', exists (select 1 from public.souvenir_seen s where s.event_id = ev.id and s.user_id = auth.uid()))
    order by private.souvenir_reveal_at(ev) desc), '[]'::jsonb)
  from public.events ev
  cross join lateral (select count(*) n from public.souvenir_photos p
                      where p.event_id = ev.id and private.souvenir_visible(p, auth.uid())) x
  where ev.souvenirs_enabled and private.souvenir_phase(ev) = 'story' and x.n > 0
    and (private.souvenir_circle(ev.id, auth.uid()) or private.souvenir_staff(ev.id, auth.uid()));
$$;

create or replace function public.souvenir_mark_seen(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not (private.souvenir_circle(e, me) or private.souvenir_staff(e, me)) then
    raise exception 'forbidden: story réservée aux participants' using errcode = '42501';
  end if;
  insert into public.souvenir_seen (event_id, user_id) values (e, me)
  on conflict (event_id, user_id) do update set seen_at = now();
  return jsonb_build_object('seen', true);
end $$;

-- ───────────── Prise de vue ─────────────
-- Le serveur a déposé <e>/<moi>/<id>.jpg (EXIF / GPS retirés) ; la photo est enregistrée ici. 3 au plus par personne.
create or replace function public.souvenir_take(e uuid, id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events; n int; f text := e::text || '/' || auth.uid()::text || '/' || id::text || '.jpg';
        p public.souvenir_photos;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: connecte-toi' using errcode = '42501'; end if;
  if not private.identity_complete(me) then
    raise exception 'profile_required: Complète ton profil (prénom, nom, surnom) pour prendre des photos.' using errcode = '42501';
  end if;
  perform private.require_terms(me);
  select * into ev from public.events x where x.id = e;
  if ev.id is null or not ev.souvenirs_enabled or ev.status <> 'published' then
    raise exception 'not_found: les Souvenirs ne sont pas actifs sur cet événement' using errcode = 'PT404';
  end if;
  if not private.souvenir_circle(e, me) then
    raise exception 'forbidden: les photos sont réservées aux participants (Présent ou Peut-être) et à l''organisation' using errcode = '42501';
  end if;
  if private.souvenir_phase(ev) <> 'open' then
    raise exception 'closed: l''appareil photo est ouvert du début de l''événement à 2 h après sa fin' using errcode = '22023';
  end if;
  perform pg_advisory_xact_lock(hashtext('souvenir:' || e::text || ':' || me::text));
  select count(*) into n from public.souvenir_photos x where x.event_id = e and x.author_id = me;
  if n >= 3 then raise exception 'full: tu as déjà pris tes 3 photos' using errcode = '22023'; end if;
  if not exists (select 1 from storage.objects o where o.bucket_id = 'souvenirs' and o.name = f
                 and (o.owner = me or o.owner_id = me::text)) then
    raise exception 'invalid: photo introuvable, réessaie' using errcode = '22023';
  end if;
  insert into public.souvenir_photos (id, event_id, author_id, path) values (id, e, me, f)
  on conflict do nothing returning * into p;
  if p.id is null then raise exception 'duplicate: photo déjà enregistrée' using errcode = '22023'; end if;
  if not ev.souvenirs_locked then
    perform set_config('party.souvenirs', 'on', true);
    update public.events x set souvenirs_locked = true where x.id = e;
    perform set_config('party.souvenirs', '', true);
  end if;
  return jsonb_build_object('id', p.id, 'path', p.path, 'taken', n + 1, 'left', 2 - n,
    'cancel_until', p.taken_at + interval '5 seconds');
end $$;

-- Annuler dans les 5 s (8 s en base pour le réseau), sans la revoir.
create or replace function public.souvenir_cancel(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_cancel.id;
  if p.id is null or p.author_id is distinct from me then raise exception 'not_found: photo introuvable' using errcode = 'PT404'; end if;
  if now() > p.taken_at + interval '8 seconds' then
    raise exception 'closed: trop tard pour annuler cette photo' using errcode = '22023';
  end if;
  delete from public.souvenir_photos x where x.id = p.id;
  return jsonb_build_object('cancelled', true,
    'left', 3 - (select count(*) from public.souvenir_photos x where x.event_id = p.event_id and x.author_id = me));
end $$;

-- L'auteur retire sa photo, n'importe quand : elle part aussi des souvenirs de ceux qui l'avaient gardée.
create or replace function public.souvenir_delete(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_delete.id;
  if p.id is null or p.author_id is distinct from me then raise exception 'not_found: photo introuvable' using errcode = 'PT404'; end if;
  delete from public.souvenir_photos x where x.id = p.id;
  return jsonb_build_object('deleted', true);
end $$;

-- L'organisation retire une photo (relecture, signalement), n'importe quand.
create or replace function public.souvenir_remove(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_remove.id;
  if p.id is null or not private.souvenir_staff(p.event_id, me) then
    raise exception 'not_found: photo introuvable' using errcode = 'PT404';
  end if;
  delete from public.souvenir_photos x where x.id = p.id;
  return jsonb_build_object('removed', true);
end $$;

-- L'organisation remet une photo signalée (la modération de Party garde le dernier mot : « Masquer » l'efface).
create or replace function public.souvenir_restore(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_restore.id;
  if p.id is null or not private.souvenir_staff(p.event_id, me) then
    raise exception 'not_found: photo introuvable' using errcode = 'PT404';
  end if;
  if p.hidden_at is null then return jsonb_build_object('restored', false); end if;
  update public.souvenir_photos x set hidden_at = null, restored_at = now(), restored_by = me where x.id = p.id;
  return jsonb_build_object('restored', true);
end $$;

-- ⭐ Garder la photo d'un autre dans mes souvenirs (pendant la story, si l'organisation le permet).
create or replace function public.souvenir_keep(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p public.souvenir_photos; ev public.events;
begin
  select * into p from public.souvenir_photos x where x.id = souvenir_keep.id;
  select * into ev from public.events where events.id = p.event_id;
  if p.id is null or not private.souvenir_visible(p, me) then
    raise exception 'not_found: photo introuvable' using errcode = 'PT404';
  end if;
  if not ev.souvenirs_keep then
    raise exception 'forbidden: l''organisation n''autorise pas à garder les photos de cette soirée' using errcode = '42501';
  end if;
  if private.souvenir_phase(ev) <> 'story' or not private.souvenir_circle(ev.id, me) then
    raise exception 'closed: on garde une photo pendant la story seulement' using errcode = '22023';
  end if;
  if p.author_id = me then return jsonb_build_object('kept', true); end if;  -- les miennes y sont d'office
  insert into public.souvenir_keeps (photo_id, user_id) values (p.id, me) on conflict do nothing;
  return jsonb_build_object('kept', true);
end $$;

create or replace function public.souvenir_unkeep(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  delete from public.souvenir_keeps k where k.photo_id = souvenir_unkeep.id and k.user_id = auth.uid();
  return jsonb_build_object('kept', false);
end $$;

-- ───────────── Réglages et dévoilement ─────────────
-- body : enabled, keep (facultatifs). Organisation seulement ; figés dès la 1re photo.
create or replace function public.souvenir_settings(e uuid, body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events; en boolean; kp boolean;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not private.souvenir_staff(e, me) then
    raise exception 'forbidden: seule l''organisation règle les Souvenirs' using errcode = '42501';
  end if;
  en := coalesce((body ->> 'enabled')::boolean, ev.souvenirs_enabled);
  kp := coalesce((body ->> 'keep')::boolean, ev.souvenirs_keep);
  if (en, kp) is distinct from (ev.souvenirs_enabled, ev.souvenirs_keep) then
    if ev.souvenirs_locked then
      raise exception 'locked: les réglages des Souvenirs sont figés depuis la première photo' using errcode = '42501';
    end if;
    perform set_config('party.souvenirs', 'on', true);
    update public.events set souvenirs_enabled = en, souvenirs_keep = kp where id = e;
    perform set_config('party.souvenirs', '', true);
  end if;
  return public.souvenir_counter(e);
end $$;

-- Dévoilement : une fois, notification au cercle (interrupteur souvenirs), seulement s'il y a des photos.
create or replace function private.souvenir_reveal_run(e uuid) returns int
language plpgsql security definer set search_path = '' as $$
declare ev public.events; u uuid; n int := 0;
begin
  select * into ev from public.events where id = e;
  insert into private.souvenir_runs (event_id) values (e) on conflict do nothing;
  update private.souvenir_runs set revealed_at = now() where event_id = e and revealed_at is null;
  if not found then return 0; end if;
  if not exists (select 1 from public.souvenir_photos p where p.event_id = e and p.hidden_at is null) then return 0; end if;
  for u in select x.u from (
      select ev.created_by u union select o.user_id from public.event_organizers o where o.event_id = e
      union select r.user_id from public.rsvps r where r.event_id = e and r.status in ('yes', 'maybe')) x
    left join public.notification_prefs np on np.user_id = x.u
    where x.u is not null and coalesce(np.souvenirs, true) and private.souvenir_circle(e, x.u) loop
    perform public.queue_notification(u, 'souvenirs_revealed', e, '📸 Les souvenirs sont dévoilés',
      'Les photos de « ' || ev.title || ' » sont à voir pendant 24 h.',
      'souvenirs_revealed:' || e || ':' || u, jsonb_build_object('url', '/?tab=events&event=' || e || '&souvenirs=1'));
    n := n + 1;
  end loop;
  return n;
end $$;
revoke all on function private.souvenir_reveal_run(uuid) from public, anon, authenticated;

create or replace function public.souvenir_reveal_now(e uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events;
begin
  select * into ev from public.events where id = e;
  if ev.id is null or not ev.souvenirs_enabled or not private.souvenir_staff(e, me) then
    raise exception 'forbidden: le dévoilement est réservé à l''organisation' using errcode = '42501';
  end if;
  if ev.starts_at is null or now() < private.souvenir_end(ev) then
    raise exception 'too_early: on ne dévoile jamais avant la fin de l''événement' using errcode = '22023';
  end if;
  if private.souvenir_phase(ev) in ('open', 'waiting') then
    perform set_config('party.souvenirs', 'on', true);
    update public.events set souvenirs_reveal_at = now() where id = e;
    perform set_config('party.souvenirs', '', true);
    perform private.souvenir_reveal_run(e);
  end if;
  return public.souvenir_counter(e);
end $$;

-- ───────────── Fichiers et tâche planifiée ─────────────
-- Corbeille + fichiers déposés jamais enregistrés (plus d'une heure) : effacés par l'API Storage (clé du coffre).
create or replace function private.souvenir_files_gc_now() returns int
language plpgsql security definer set search_path = '' as $$
declare names text[]; n int;
begin
  if private.storage_api() is null then return 0; end if;
  select coalesce(array_agg(path), '{}') into names from (select path from private.souvenir_trash order by at limit 300) t;
  names := names || coalesce((select array_agg(o.name) from (select o.name from storage.objects o
      where o.bucket_id = 'souvenirs' and o.created_at < now() - interval '1 hour'
        and not exists (select 1 from public.souvenir_photos p where p.path = o.name)
        and not exists (select 1 from private.souvenir_trash t where t.path = o.name)
      order by o.created_at limit 300) o), '{}');
  n := private.storage_remove('souvenirs', names);
  delete from private.souvenir_trash where path = any (names);
  return n;
end $$;
revoke all on function private.souvenir_files_gc_now() from public, anon, authenticated;

-- Appelée par le serveur Party (clé publique, sans compte) ; au plus une fois toutes les 10 minutes.
create or replace function public.souvenir_files_gc() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare last timestamptz; n int;
begin
  select last_at into last from private.souvenir_gc_runs where id = 1 for update;
  if last > now() - interval '10 minutes' then return jsonb_build_object('skipped', true); end if;
  if private.storage_api() is null then return jsonb_build_object('skipped', true, 'reason', 'no_storage_key'); end if;
  n := private.souvenir_files_gc_now();
  insert into private.souvenir_gc_runs (id, last_at, removed) values (1, now(), n)
  on conflict (id) do update set last_at = excluded.last_at, removed = excluded.removed;
  return jsonb_build_object('removed', n);
end $$;
revoke all on function public.souvenir_files_gc() from public;
grant execute on function public.souvenir_files_gc() to anon, authenticated;

create or replace function private.souvenir_tick() returns void
language plpgsql security definer set search_path = '' as $$
declare ev public.events;
begin
  -- 1. Dévoilement (fin + 24 h, ou avancé) et notification, une fois.
  for ev in select x.* from public.events x
      where x.souvenirs_enabled and x.starts_at is not null and private.souvenir_reveal_at(x) <= now()
        and not exists (select 1 from private.souvenir_runs r where r.event_id = x.id and r.revealed_at is not null) loop
    perform private.souvenir_reveal_run(ev.id);
  end loop;
  -- 2. Fin de la story sans « garder » : rien ne reste (fichiers à la corbeille par le déclencheur).
  for ev in select x.* from public.events x
      where x.starts_at is not null and not x.souvenirs_keep and private.souvenir_reveal_at(x) + interval '24 hours' <= now()
        and exists (select 1 from public.souvenir_photos p where p.event_id = x.id) loop
    delete from public.souvenir_photos p where p.event_id = ev.id;
    insert into private.souvenir_runs (event_id, purged_at) values (ev.id, now())
    on conflict (event_id) do update set purged_at = now();
  end loop;
  -- 3. Conservation : 13 mois.
  delete from public.souvenir_photos p where p.taken_at < now() - interval '13 months';
  delete from public.souvenir_seen s where s.seen_at < now() - interval '13 months';
  -- 4. Fichiers.
  perform private.souvenir_files_gc_now();
end $$;
revoke all on function private.souvenir_tick() from public, anon, authenticated;
select cron.unschedule('souvenirs-tick') where exists (select 1 from cron.job where jobname = 'souvenirs-tick');
select cron.schedule('souvenirs-tick', '*/5 * * * *', 'select private.souvenir_tick();');

-- ───────────── Droits des fonctions ─────────────
revoke all on function public.souvenir_counter(uuid), public.souvenir_story(uuid), public.souvenir_mine(uuid),
  public.souvenir_review(uuid), public.souvenir_stories(), public.souvenir_mark_seen(uuid), public.souvenir_take(uuid, uuid),
  public.souvenir_cancel(uuid), public.souvenir_delete(uuid), public.souvenir_remove(uuid), public.souvenir_restore(uuid),
  public.souvenir_keep(uuid), public.souvenir_unkeep(uuid), public.souvenir_settings(uuid, jsonb),
  public.souvenir_reveal_now(uuid) from public, anon;
grant execute on function public.souvenir_counter(uuid), public.souvenir_story(uuid), public.souvenir_mine(uuid),
  public.souvenir_review(uuid), public.souvenir_stories(), public.souvenir_mark_seen(uuid), public.souvenir_take(uuid, uuid),
  public.souvenir_cancel(uuid), public.souvenir_delete(uuid), public.souvenir_remove(uuid), public.souvenir_restore(uuid),
  public.souvenir_keep(uuid), public.souvenir_unkeep(uuid), public.souvenir_settings(uuid, jsonb),
  public.souvenir_reveal_now(uuid) to authenticated;

-- ───────────── Signaler ─────────────
-- Copie gardée par le signalement : visible seulement par qui voit la photo.
create or replace function private.souvenir_report_snapshot(uid uuid, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare p public.souvenir_photos;
begin
  select * into p from public.souvenir_photos where id = uid;
  if p.id is null or not private.souvenir_visible(p, viewer) then return null; end if;
  return jsonb_build_object('owner', p.author_id, 'photo_path', p.path, 'bucket', 'souvenirs', 'event_id', p.event_id,
    'at', p.taken_at, 'place', 'Souvenirs · ' || (select title from public.events where id = p.event_id));
end $$;
revoke all on function private.souvenir_report_snapshot(uuid, uuid) from public, anon, authenticated;

-- Signalée : masquée aussitôt pour tous (gardées comprises) ; l'organisation est prévenue. Classée par la modération :
-- remise (si plus aucun signalement ouvert).
create or replace function private.souvenir_reported() returns trigger
language plpgsql security definer set search_path = '' as $$
declare p public.souvenir_photos; u uuid;
begin
  if new.target_kind <> 'souvenir' then return null; end if;
  begin
    select * into p from public.souvenir_photos where id = new.target_id::uuid;
  exception when others then return null;
  end;
  if p.id is null then return null; end if;
  if tg_op = 'INSERT' then
    update public.souvenir_photos set hidden_at = coalesce(hidden_at, now()) where id = p.id;
    for u in select ev.created_by from public.events ev where ev.id = p.event_id
             union select o.user_id from public.event_organizers o where o.event_id = p.event_id loop
      perform public.queue_notification(u, 'souvenir_reported', p.event_id, '🚩 Une photo Souvenirs a été signalée',
        'Elle est masquée en attendant : retire-la ou remets-la (fiche › Souvenirs).',
        'souvenir_reported:' || p.id || ':' || u, jsonb_build_object('photo_id', p.id,
          'url', '/?tab=events&event=' || p.event_id || '&souvenirs=review'));
    end loop;
  elsif new.status = 'dismissed' and old.status = 'open'
        and not exists (select 1 from public.content_reports r where r.target_kind = 'souvenir' and r.target_id = new.target_id
                        and r.status = 'open') then
    update public.souvenir_photos set hidden_at = null where id = p.id;
  end if;
  return null;
end $$;
revoke all on function private.souvenir_reported() from public, anon, authenticated;
drop trigger if exists souvenir_reported on public.content_reports;
create trigger souvenir_reported after insert or update of status on public.content_reports
  for each row execute function private.souvenir_reported();

-- Fonctions partagées : extension par ancre (raise si l'ancre manque ; rien si déjà fait).
do $$ declare def text;
begin
  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position('''souvenir''' in def) = 0 then
    if position('''prono_answer''::text' in def) = 0 then raise exception 'content_reports : ancre prono_answer introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, '''prono_answer''::text', '''prono_answer''::text, ''souvenir''::text');
  end if;

  -- Motif « my_image » : « Je suis sur la photo et je ne veux pas qu'elle soit montrée ».
  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_reason_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position('''my_image''' in def) = 0 then
    if position('''money''::text' in def) = 0 then raise exception 'content_reports : ancre money introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_reason_check;
    execute 'alter table public.content_reports add constraint content_reports_reason_check '
      || replace(def, '''money''::text', '''money''::text, ''my_image''::text');
  end if;

  def := pg_get_functiondef('public.report_content(text,text,text,text,boolean)'::regprocedure);
  if position('''my_image''' in def) = 0 then
    if position($a$p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'money', 'other')$a$ in def) = 0 then
      raise exception 'report_content : ancre des raisons introuvable';
    end if;
    execute replace(def, $a$p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'money', 'other')$a$,
                         $a$p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'money', 'other', 'my_image')$a$);
  end if;

  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('''souvenir''' in def) = 0 then
    if position($a$  elsif p_kind in ('profile', 'profile_photo') then$a$ in def) = 0 then raise exception 'report_snapshot : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif p_kind in ('profile', 'profile_photo') then$a$, $a$  elsif p_kind = 'souvenir' then
    return private.souvenir_report_snapshot(uid, viewer);
  elsif p_kind in ('profile', 'profile_photo') then$a$);
  end if;

  -- « Masquer » de la modération de Party : la photo est effacée (dernier mot ; le fichier part à la corbeille).
  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position('''souvenir''' in def) = 0 then
    if position($a$  elsif r.target_kind = 'profile' then$a$ in def) = 0 then raise exception 'moderation_hide : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif r.target_kind = 'profile' then$a$, $a$  elsif r.target_kind = 'souvenir' then
    delete from public.souvenir_photos where id = uid;
  elsif r.target_kind = 'profile' then$a$);
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''souvenir''' in def) = 0 then
    if position($a$when 'money' then 'Demande d''argent ou vente de confettis'$a$ in def) = 0
       or position($a$when new.target_kind = 'agenda_link' then 'un lien de disponibilités'$a$ in def) = 0 then
      raise exception 'notify_new_report : ancres introuvables';
    end if;
    def := replace(def, $a$when 'money' then 'Demande d''argent ou vente de confettis'$a$,
      $a$when 'money' then 'Demande d''argent ou vente de confettis' when 'my_image' then 'Droit à l''image'$a$);
    execute replace(def, $a$when new.target_kind = 'agenda_link' then 'un lien de disponibilités'$a$,
      $a$when new.target_kind = 'agenda_link' then 'un lien de disponibilités'
                        when new.target_kind = 'souvenir' then 'une photo Souvenirs'$a$);
  end if;

  def := pg_get_functiondef('private.notify_content_hidden(public.content_reports)'::regprocedure);
  if position('''souvenir''' in def) = 0 then
    if position($a$when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'$a$ in def) = 0
       or position($a$when 'money' then 'argent'$a$ in def) = 0 then
      raise exception 'notify_content_hidden : ancres introuvables';
    end if;
    def := replace(def, $a$when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'$a$,
      $a$when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'
               when r.target_kind = 'souvenir' then 'Ta photo Souvenirs a été retirée'$a$);
    execute replace(def, $a$when 'money' then 'argent'$a$, $a$when 'money' then 'argent' when 'my_image' then 'droit à l''image'$a$);
  end if;

  -- guard_event : les fonctions souvenir_* (drapeau de transaction party.souvenirs) ne changent que les colonnes
  -- souvenirs_* ; elles décident elles-mêmes qui (organisation, prise de vue qui fige les réglages, dévoilement).
  def := pg_get_functiondef('public.guard_event()'::regprocedure);
  if position('party.souvenirs' in def) = 0 then
    if position($a$  if auth.uid() is null then return new; end if;  -- cron, service role$a$ in def) = 0 then
      raise exception 'guard_event : ancre auth.uid introuvable';
    end if;
    execute replace(def, $a$  if auth.uid() is null then return new; end if;  -- cron, service role$a$,
      $a$  if auth.uid() is null then return new; end if;  -- cron, service role
  if tg_op = 'UPDATE' and current_setting('party.souvenirs', true) = 'on'
     and (to_jsonb(new) - 'souvenirs_enabled' - 'souvenirs_keep' - 'souvenirs_locked' - 'souvenirs_reveal_at' - 'updated_at')
       = (to_jsonb(old) - 'souvenirs_enabled' - 'souvenirs_keep' - 'souvenirs_locked' - 'souvenirs_reveal_at' - 'updated_at') then
    return new;  -- fonctions souvenir_* (migration 20261124090000)
  end if;$a$);
  end if;

  -- Notifications : interrupteur souvenirs (souvenirs_revealed, souvenir_reported), comptes actifs, blocage (souvenir_reported).
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''souvenirs_revealed''' in def) = 0 then
    if position($a$    when 'group_added' then coalesce(prefs.group_added, true)$a$ in def) = 0 then raise exception 'web_push_allowed : ancre group_added introuvable'; end if;
    execute replace(def, $a$    when 'group_added' then coalesce(prefs.group_added, true)$a$, $a$    when 'group_added' then coalesce(prefs.group_added, true)
    when 'souvenirs_revealed' then coalesce(prefs.souvenirs, true)
    when 'souvenir_reported' then coalesce(prefs.souvenirs, true)$a$);
  elsif position($a$when 'souvenir_reported' then$a$ in def) = 0 then  -- base où seule la 1re branche est posée
    execute replace(def, $a$    when 'souvenirs_revealed' then coalesce(prefs.souvenirs, true)$a$,
      $a$    when 'souvenirs_revealed' then coalesce(prefs.souvenirs, true)
    when 'souvenir_reported' then coalesce(prefs.souvenirs, true)$a$);
  end if;

  def := pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure);
  if position('''souvenirs_revealed''' in def) = 0 then
    if position('''group_added'',' in def) = 0 then raise exception 'may_receive_push : ancre group_added introuvable'; end if;
    execute replace(def, '''group_added'',', '''group_added'', ''souvenirs_revealed'', ''souvenir_reported'',');
  end if;

  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position('''souvenir_reported''' in def) = 0 then
    if position('''group_added'',' in def) = 0 then raise exception 'drop_blocked_notification : ancre group_added introuvable'; end if;
    execute replace(def, '''group_added'',', '''group_added'', ''souvenir_reported'',');
  end if;
end $$;

notify pgrst, 'reload schema';
