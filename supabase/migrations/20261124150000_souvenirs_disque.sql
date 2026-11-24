-- Souvenirs : les FICHIERS photo quittent Supabase Storage (décision de l'admin du 24.11 : plan Free, 1 Go et 5 Go de
-- sortie par mois, risque de bloquer tout Party). Ils vont sur le disque du serveur Party (DATA_DIR/souvenirs, copie de
-- nuit vers le NAS). La base garde le reste : métadonnées, droits, signalements, blocages, ticket.
-- Additive et rejouable ; à réappliquer après toute réapplication de 20261124090000 (souvenir_take, souvenir_files_gc_now).
--
-- 1. souvenir_take : le ticket du serveur (souvenir_upload_ticket, clé du coffre, 2 min, usage unique) reste la seule
--    garantie qu'une photo vient du serveur ; plus de ligne storage.objects exigée (le fichier s'écrit sur le disque
--    APRÈS l'accord de la base). La règle de dépôt du compartiment reste (ticket exigé), mais plus rien n'y écrit.
-- 2. souvenir_readable(paths) : le serveur vérifie, avec le jeton de la personne, quelles photos elle peut voir
--    (private.souvenir_may_read : cercle, blocages, signalement → organisation, modération) avant de signer un lien.
-- 3. Corbeille : vidée par le serveur (souvenir_trash_take / souvenir_trash_done, clé du serveur) ; la base n'y touche
--    plus (souvenir_files_gc_now n'efface que les anciens fichiers restés dans le compartiment).

-- 1. Prise : ticket seulement.
create or replace function public.souvenir_take(e uuid, id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); ev public.events; n int; f text := e::text || '/' || auth.uid()::text || '/' || id::text || '.jpg';
        p public.souvenir_photos;
begin
  if me is not null then perform pg_advisory_xact_lock(hashtext('souvenir:' || e::text || ':' || me::text)); end if;
  ev := private.souvenir_take_check(e, me);
  select count(*) into n from public.souvenir_photos x where x.event_id = e and x.author_id = me;
  delete from private.souvenir_tickets t where t.path = f and t.user_id = me and t.expires_at > now();
  if not found then
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
revoke all on function public.souvenir_take(uuid, uuid) from public, anon;
grant execute on function public.souvenir_take(uuid, uuid) to authenticated;

-- 2. Lecture : les chemins que MOI je peux voir (200 au plus), pour les liens signés du serveur.
create or replace function public.souvenir_readable(paths text[]) returns text[]
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null then return '{}'; end if;
  return coalesce((select array_agg(x.p) from (select distinct unnest(paths[1:200]) p) x
                   where private.souvenir_may_read(x.p)), '{}');
end $$;
revoke all on function public.souvenir_readable(text[]) from public, anon;
grant execute on function public.souvenir_readable(text[]) to authenticated;

-- 3. Corbeille vidée par le serveur Party (sa clé) : il lit des chemins, efface les fichiers, puis les rend.
create or replace function public.souvenir_trash_take(p_key text, n int default 200) returns text[]
language plpgsql security definer set search_path = '' as $$
begin
  if not private.souvenir_server_ok(p_key) then
    raise exception 'server: réservé au serveur de Party' using errcode = '42501';
  end if;
  return coalesce((select array_agg(t.path order by t.at) from (select path, at from private.souvenir_trash
                   order by at limit greatest(1, least(coalesce(n, 200), 500))) t), '{}');
end $$;
create or replace function public.souvenir_trash_done(p_key text, paths text[]) returns int
language plpgsql security definer set search_path = '' as $$
declare k int;
begin
  if not private.souvenir_server_ok(p_key) then
    raise exception 'server: réservé au serveur de Party' using errcode = '42501';
  end if;
  delete from private.souvenir_trash t where t.path = any (coalesce(paths, '{}'));
  get diagnostics k = row_count;
  return k;
end $$;
revoke all on function public.souvenir_trash_take(text, int), public.souvenir_trash_done(text, text[]) from public;
grant execute on function public.souvenir_trash_take(text, int), public.souvenir_trash_done(text, text[]) to anon, authenticated;

-- La base n'efface plus la corbeille (le serveur en a besoin pour le disque) : seulement les anciens fichiers du
-- compartiment (photos d'avant le 24.11 sur TEST, envois jamais enregistrés) qu'aucune photo ne désigne plus.
create or replace function private.souvenir_files_gc_now() returns int
language plpgsql security definer set search_path = '' as $$
declare names text[];
begin
  if private.storage_api() is null then return 0; end if;
  select coalesce(array_agg(o.name), '{}') into names from (select o.name from storage.objects o
      where o.bucket_id = 'souvenirs' and o.created_at < now() - interval '1 hour'
        and not exists (select 1 from public.souvenir_photos p where p.path = o.name)
      order by o.created_at limit 300) o;
  if cardinality(names) = 0 then return 0; end if;
  return private.storage_remove('souvenirs', names);
end $$;
revoke all on function private.souvenir_files_gc_now() from public, anon, authenticated;
