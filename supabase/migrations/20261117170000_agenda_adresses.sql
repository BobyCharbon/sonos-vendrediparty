-- Agenda : adresse lisible des liens de dispo (demande de l'admin du 17.11.2026) : <site>/agenda/<nom>/<lien>, par
-- exemple /agenda/ludovic/semaine, au lieu de seulement /d/<jeton>. Le nom (private.agenda_handles) est choisi une fois
-- par personne, unique sur le site, filtré comme un surnom, mots réservés refusés ; le nom du lien
-- (agenda_links.slug) est unique pour la personne. L'adresse en lettres (/d/<jeton>) marche toujours. Lien arrêté,
-- expiré, nom ou lien changé : l'adresse lisible ne montre plus rien (même page neutre que pour un lien inconnu).
-- Purement additive et rejouable.

create table if not exists private.agenda_handles (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  handle text not null unique check (handle ~ '^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$' and handle !~ '--'),
  updated_at timestamptz not null default now()
);
alter table private.agenda_handles enable row level security;
revoke all on private.agenda_handles from public, anon, authenticated;

alter table private.agenda_links add column if not exists slug text;
alter table private.agenda_links drop constraint if exists agenda_links_slug;
alter table private.agenda_links add constraint agenda_links_slug
  check (slug is null or (slug ~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$' and slug !~ '--'));
create unique index if not exists agenda_links_user_slug on private.agenda_links (user_id, slug) where slug is not null;

-- Mots qu'aucun nom ne peut prendre (rôles, marque, pages du site).
create or replace function private.agenda_handle_reserved(h text) returns boolean
language sql immutable set search_path = '' as $$
  select h = any (array['admin', 'root', 'api', 'app', 'apple', 'google', 'agenda', 'aide', 'help', 'support', 'contact',
    'moderation', 'moderateur', 'party', 'vendredi', 'vendrediparty', 'vendredi-party', 'bobycharbon', 'events', 'static',
    'compte', 'account', 'login', 'connexion', 'securite', 'security', 'officiel', 'official', 'test', 'demo', 'null'])
    or h like 'vendredi-party%' or h like 'vendrediparty%' or h like 'admin%';
$$;
revoke all on function private.agenda_handle_reserved(text) from public, anon, authenticated;

create or replace function private.agenda_link_json(l private.agenda_links) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', l.id, 'token', l.token, 'path', '/d/' || l.token, 'name', l.name, 'emoji', l.emoji,
    'display_name', l.display_name, 'rules', l.rules, 'horizon_days', l.horizon_days, 'duration_min', l.duration_min,
    'booking_enabled', l.booking_enabled, 'booking_fields', l.booking_fields, 'message_label', l.message_label,
    'calendars', to_jsonb(l.calendars), 'permanent', l.expires_at is null,
    'buffer_before_min', l.buffer_before_min, 'buffer_after_min', l.buffer_after_min,
    'slug', l.slug,
    'nice_path', (select '/agenda/' || h.handle || '/' || l.slug from private.agenda_handles h where h.user_id = l.user_id and l.slug is not null),
    'status', case when l.stopped_at is not null then 'stopped' when l.expires_at <= now() then 'expired' else 'active' end,
    'expires_at', l.expires_at, 'stopped_at', l.stopped_at, 'views', l.views, 'last_viewed_at', l.last_viewed_at,
    'pending', (select count(*) from private.agenda_bookings k where k.link_id = l.id and k.status = 'pending'),
    'created_at', l.created_at);
$$;
revoke all on function private.agenda_link_json(private.agenda_links) from public, anon, authenticated;

-- Mon nom d'adresse (null : pas encore choisi).
create or replace function public.agenda_handle() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return jsonb_build_object('handle', (select h.handle from private.agenda_handles h where h.user_id = me));
end $$;
revoke all on function public.agenda_handle() from public, anon;
grant execute on function public.agenda_handle() to authenticated;

-- Choisir / changer mon nom d'adresse (vide : retiré, les adresses lisibles s'arrêtent ; /d/<jeton> reste).
create or replace function public.agenda_handle_set(handle text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); h text := lower(btrim(coalesce(agenda_handle_set.handle, '')));
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if h = '' then
    delete from private.agenda_handles x where x.user_id = me;
    return jsonb_build_object('handle', null);
  end if;
  if not private.identity_complete(me) then
    raise exception 'profile_incomplete: Complète ton profil (prénom, nom, surnom) pour choisir ton adresse.' using errcode = '42501';
  end if;
  perform private.require_terms(me);
  if h !~ '^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$' or h ~ '--' then
    raise exception 'invalid: De 3 à 30 lettres, chiffres ou tirets, sans accent ni espace.' using errcode = '22023';
  end if;
  if private.agenda_handle_reserved(h) then
    raise exception 'duplicate: « % » est réservé. Choisis-en un autre.', h using errcode = '23505';
  end if;
  perform private.moderate_text(replace(h, '-', ' '), 'name');
  if exists (select 1 from private.agenda_handles x where x.handle = h and x.user_id <> me) then
    raise exception 'duplicate: « % » est déjà pris. Essaie avec ton nom ou un chiffre.', h using errcode = '23505';
  end if;
  insert into private.agenda_handles (user_id, handle) values (me, h)
  on conflict (user_id) do update set handle = excluded.handle, updated_at = now();
  return jsonb_build_object('handle', h);
end $$;
revoke all on function public.agenda_handle_set(text) from public, anon;
grant execute on function public.agenda_handle_set(text) to authenticated;

-- Mes liens : le nom d'adresse en plus.
create or replace function public.agenda_links() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); mx int := (select links_max from private.agenda_settings z where z.id = 1);
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return jsonb_build_object(
    'links', coalesce((select jsonb_agg(private.agenda_link_json(l) order by l.stopped_at is not null, l.created_at)
                       from private.agenda_links l where l.user_id = me), '[]'),
    'max', mx,
    'handle', (select h.handle from private.agenda_handles h where h.user_id = me),
    'missing', case when not private.identity_complete(me) then 'profile'
                    when (select terms_enforced from private.moderation_settings where id = 1) and not private.terms_accepted(me) then 'terms' end,
    'notify', coalesce((select p.booking_requests from public.notification_prefs p where p.user_id = me), true),
    'pending', (select count(*) from private.agenda_bookings k where k.owner_id = me and k.status = 'pending'));
end $$;
revoke all on function public.agenda_links() from public, anon;
grant execute on function public.agenda_links() to authenticated;

-- Nom du lien choisi par le propriétaire (link.slug : vide = sans adresse lisible), unique pour lui.
create or replace function private.agenda_link_slug_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.slug is not distinct from old.slug then return new; end if;
  if new.slug is not null then
    if new.slug !~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$' or new.slug ~ '--' then
      raise exception 'invalid: Nom du lien : lettres, chiffres ou tirets, sans accent ni espace.' using errcode = '22023';
    end if;
    perform private.moderate_text(replace(new.slug, '-', ' '), 'name');
    if exists (select 1 from private.agenda_links x where x.user_id = new.user_id and x.slug = new.slug and x.id <> new.id) then
      raise exception 'duplicate: Tu as déjà un lien « % ». Choisis un autre nom.', new.slug using errcode = '23505';
    end if;
  end if;
  return new;
end $$;
revoke all on function private.agenda_link_slug_guard() from public, anon, authenticated;
drop trigger if exists agenda_links_slug_guard on private.agenda_links;
create trigger agenda_links_slug_guard before insert or update of slug on private.agenda_links
  for each row execute function private.agenda_link_slug_guard();

-- Le nom du lien s'enregistre avec le reste (agenda_link_save garde sa signature) : appelée juste après par l'écran.
create or replace function public.agenda_link_set_slug(id uuid, slug text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); l private.agenda_links; s text := nullif(lower(btrim(coalesce(agenda_link_set_slug.slug, ''))), '');
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if s is not null and not exists (select 1 from private.agenda_handles h where h.user_id = me) then
    raise exception 'forbidden: Choisis d''abord ton nom d''adresse.' using errcode = '42501';
  end if;
  update private.agenda_links x set slug = s, updated_at = now()
  where x.id = agenda_link_set_slug.id and x.user_id = me returning * into l;
  if l.id is null then raise exception 'not_found: Ce lien n''existe plus.' using errcode = 'PT404'; end if;
  return private.agenda_link_json(l);
end $$;
revoke all on function public.agenda_link_set_slug(uuid, text) from public, anon;
grant execute on function public.agenda_link_set_slug(uuid, text) to authenticated;

-- Page publique : l'adresse lisible donne le jeton du lien, seulement s'il est actif (sinon null : page neutre).
create or replace function public.agenda_resolve(handle text, slug text) returns text
language sql stable security definer set search_path = '' as $$
  select l.token from private.agenda_handles h
    join private.agenda_links l on l.user_id = h.user_id and l.slug = lower(agenda_resolve.slug)
  where h.handle = lower(agenda_resolve.handle) and private.agenda_link_active(l);
$$;
revoke all on function public.agenda_resolve(text, text) from public;
grant execute on function public.agenda_resolve(text, text) to anon, authenticated;
