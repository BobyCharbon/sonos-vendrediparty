-- PROD, discussions_moderation (20261118121000) : migration supabase/migrations/20261118121000_discussions_moderation.sql telle quelle (mise en prod du 19.11).
-- Additive et rejouable. Tout ou rien.
begin;
-- Discussions v2 — modération (revue de conformité du 18.11.2026, 🔴 2 et 6, 🟠 7, 8 et 9). Purement additive et
-- rejouable. Passe APRÈS 20261118120000_discussions_v2.sql (private.dm_link).
--
-- 1. Preuve gardée (🔴 2) : signaler un message (groupe, direct, événement) avec une photo ou un vocal en garde une copie
--    dans le compartiment privé « moderation-evidence » (dossier = le signalement), lisible par les seuls modérateurs
--    (droit moderation.reports) ; la copie part avec le signalement (1 an après son traitement, purge existante).
--    La copie est faite par la base (API Storage, clé « storage_secret_key » du coffre, comme tc_purge_receipts) : elle
--    vaut pour le web (qui appelle report_content directement) comme pour l'iPhone. Sans la clé : pas de copie (le
--    signalement part quand même, le modérateur voit le texte).
-- 2. Contexte (🟠 8) : report_content(..., p_context boolean default false) joint les 10 messages précédents de la même
--    conversation (texte, auteur, heure ; photo / vocal en mots) à la copie du signalement.
-- 3. « Masquer » prévient l'auteur (🟠 7, DSA art. 17) : notification content_hidden avec le motif et le recours
--    (adresse de contact de la modération). Interrupteur : celui des messages de la modération (moderation_notices).
-- 4. invite_to_group (🟠 9) : n'invite plus qu'une personne en lien « direct » (private.dm_link, comme les groupes à
--    plusieurs), même réponse qu'un numéro ait un compte ou non (« phone »), 30 invitations par jour et par personne.
-- 5. Fichiers orphelins (🔴 6) : public.chat_files_gc(), appelée par le serveur Party au démarrage puis toutes les 6 h
--    (le serveur n'a aucune clé Storage : la base efface par l'API Storage avec la clé du coffre). Efface dans
--    chat-photos, group-photos et moderation-evidence tout fichier qu'aucune ligne ne désigne plus ET vieux de plus
--    d'une heure (un envoi en cours n'est jamais touché). Au plus une fois toutes les 10 minutes.
--    Suppression d'un compte : les fichiers de ses messages partent aussitôt (déclencheur sur auth.users).

-- 1. Compartiment des preuves ----------------------------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit)
values ('moderation-evidence', 'moderation-evidence', false, 8388608)
on conflict (id) do update set public = false;

drop policy if exists "preuves de modération : voir" on storage.objects;
create policy "preuves de modération : voir" on storage.objects for select to authenticated
  using (bucket_id = 'moderation-evidence' and (select public.has_perm('moderation.reports')));
-- Aucune écriture par l'API publique : seule la base (clé du coffre) y copie et en efface.

-- Accès à l'API Storage avec la clé du coffre (null sans clé : rien n'est fait).
create or replace function private.storage_api() returns jsonb
language sql stable security definer set search_path = '' as $$
  select case when k.key is not null and b.base is not null
              then jsonb_build_object('base', b.base, 'key', k.key) end
  from (select decrypted_secret as key from vault.decrypted_secrets where name = 'storage_secret_key' limit 1) k
  full join (select decrypted_secret as base from vault.decrypted_secrets where name = 'project_url' limit 1) b on true;
$$;
revoke all on function private.storage_api() from public, anon, authenticated;

-- Efface des fichiers par l'API Storage (une requête par fichier, partie après la transaction ; annulée avec elle).
create or replace function private.storage_remove(bucket text, names text[]) returns integer
language plpgsql security definer set search_path = '' as $$
declare api jsonb := private.storage_api(); n int := 0; f text;
begin
  if api is null or names is null then return 0; end if;
  foreach f in array names loop
    continue when f is null or f !~ '^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$';
    perform net.http_delete(url := (api ->> 'base') || '/storage/v1/object/' || bucket || '/' || f,
                            headers := jsonb_build_object('apikey', api ->> 'key'));
    n := n + 1;
  end loop;
  return n;
end $$;
revoke all on function private.storage_remove(text, text[]) from public, anon, authenticated;

-- Copie la photo et le vocal d'un message signalé dans moderation-evidence/<signalement>/ ; rend {photo, audio}.
create or replace function private.moderation_copy_evidence(rid uuid, snap jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare api jsonb := private.storage_api(); out jsonb := '{}'::jsonb; k text; src text; dest text;
begin
  if api is null then return out; end if;
  foreach k in array array['photo', 'audio'] loop
    src := snap ->> (k || '_path');
    continue when src is null or src !~ '^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$';
    dest := rid::text || '/' || k || '-' || split_part(src, '/', 2);
    perform net.http_post(url := (api ->> 'base') || '/storage/v1/object/copy',
      body := jsonb_build_object('bucketId', 'chat-photos', 'sourceKey', src,
                                 'destinationBucket', 'moderation-evidence', 'destinationKey', dest),
      headers := jsonb_build_object('apikey', api ->> 'key', 'Content-Type', 'application/json'));
    out := out || jsonb_build_object(k, dest);
  end loop;
  return out;
end $$;
revoke all on function private.moderation_copy_evidence(uuid, jsonb) from public, anon, authenticated;

-- La copie part avec le signalement (purge d'un an, compte supprimé…).
create or replace function private.moderation_evidence_gone() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.snapshot ? 'evidence' then
    perform private.storage_remove('moderation-evidence',
      array[old.snapshot -> 'evidence' ->> 'photo', old.snapshot -> 'evidence' ->> 'audio']);
  end if;
  return old;
end $$;
revoke all on function private.moderation_evidence_gone() from public, anon, authenticated;
drop trigger if exists moderation_evidence_gone on public.content_reports;
create trigger moderation_evidence_gone after delete on public.content_reports
  for each row execute function private.moderation_evidence_gone();

-- La copie d'un message d'événement garde aussi sa photo et son vocal (ceux des groupes et des directs les gardaient).
do $$ declare def text;
begin
  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('''photo_path'', em.photo_path' in def) = 0 then
    if position($a$return jsonb_build_object('owner', em.user_id, 'text', em.body, 'at', em.created_at,$a$ in def) = 0 then
      raise exception 'report_snapshot : ancre event_message introuvable';
    end if;
    execute replace(def, $a$return jsonb_build_object('owner', em.user_id, 'text', em.body, 'at', em.created_at,$a$,
      $a$return jsonb_build_object('owner', em.user_id, 'text', em.body, 'photo_path', em.photo_path,
      'audio_path', em.audio_path, 'at', em.created_at,$a$);
  end if;
end $$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;

-- 2. Les 10 messages précédents (chronologiques) de la conversation d'un message signalé ---------------------------------
create or replace function private.report_context(p_kind text, msg uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare rows jsonb;
begin
  with m as (
    select x.id, x.user_id, x.body, x.photo_path, x.audio_path, x.deleted_at, x.created_at
    from public.group_messages x, public.group_messages t
    where p_kind = 'group_message' and t.id = msg and x.group_id = t.group_id
      and (x.created_at, x.id) < (t.created_at, t.id)
    union all
    select x.id, x.user_id, x.body, x.photo_path, x.audio_path, x.deleted_at, x.created_at
    from public.direct_messages x, public.direct_messages t
    where p_kind = 'direct_message' and t.id = msg and x.chat_id = t.chat_id
      and (x.created_at, x.id) < (t.created_at, t.id)
    union all
    select x.id, x.user_id, x.body, x.photo_path, x.audio_path, x.deleted_at, x.created_at
    from public.messages x, public.messages t
    where p_kind = 'event_message' and t.id = msg and x.event_id = t.event_id
      and (x.created_at, x.id) < (t.created_at, t.id)
  ), last10 as (select * from m order by created_at desc, id desc limit 10)
  select coalesce(jsonb_agg(jsonb_build_object(
      'author', coalesce(private.member_name(l.user_id), 'Compte supprimé'), 'user_id', l.user_id, 'at', l.created_at,
      'text', case when l.deleted_at is not null then 'Message supprimé'
                   when btrim(coalesce(l.body, '')) not in ('', '•') then left(l.body, 2000)
                   when l.audio_path is not null then '🎤 Message vocal'
                   when l.photo_path is not null then '📷 Photo' else '' end)
    order by l.created_at, l.id), '[]'::jsonb)
  into rows from last10 l;
  return rows;
end $$;
revoke all on function private.report_context(text, uuid) from public, anon, authenticated;

-- report_content : même contrat qu'avant + p_context (case « Joindre les 10 messages précédents », décochée) et la preuve.
-- L'ancienne signature (4 paramètres) disparaît : les appels d'avant (4 paramètres nommés) tombent sur celle-ci.
drop function if exists public.report_content(text, text, text, text);
create or replace function public.report_content(p_kind text, p_target text, p_reason text, p_comment text default null,
                                                 p_context boolean default false) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); snap jsonb; owner uuid; rid uuid; v_comment text := nullif(btrim(left(p_comment, 500)), '');
        is_msg boolean := p_kind in ('group_message', 'direct_message', 'event_message'); ctx jsonb; ev jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if p_reason is null or p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'money', 'other') then
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
  if is_msg and coalesce(p_context, false) then
    ctx := jsonb_build_object('context', private.report_context(p_kind, p_target::uuid));
  end if;
  select id into rid from public.content_reports
    where reporter_id = me and target_kind = p_kind and target_id = p_target and status = 'open';
  if rid is not null then
    update public.content_reports set reason = p_reason, comment = v_comment,
      snapshot = case when ctx is not null and not snapshot ? 'context' then snapshot || ctx else snapshot end
    where id = rid;
    return rid;
  end if;
  insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason, comment, snapshot)
  values (me, p_kind, p_target, owner, p_reason, v_comment, (snap - 'owner') || coalesce(ctx, '{}'::jsonb))
  returning id into rid;
  if is_msg and (snap ->> 'photo_path' is not null or snap ->> 'audio_path' is not null) then
    ev := private.moderation_copy_evidence(rid, snap);
    if ev <> '{}'::jsonb then
      update public.content_reports set snapshot = snapshot || jsonb_build_object('evidence', ev) where id = rid;
    end if;
  end if;
  return rid;
end $$;
revoke all on function public.report_content(text, text, text, text, boolean) from public, anon;
grant execute on function public.report_content(text, text, text, text, boolean) to authenticated;

-- 3. « Masquer » prévient l'auteur ------------------------------------------------------------------------------------------
create or replace function private.notify_content_hidden(r public.content_reports) returns void
language plpgsql security definer set search_path = '' as $$
declare what text; why text; contact text;
begin
  if r.target_user is null then return; end if;
  what := case when r.target_kind in ('group_message', 'direct_message', 'event_message') then 'Ton message a été retiré'
               when r.target_kind = 'profile' then 'Ton surnom a été masqué'
               when r.target_kind = 'profile_photo' then 'Ta photo de profil a été retirée'
               when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'
               when r.target_kind = 'event' then 'Ton événement a été masqué'
               when r.target_kind in ('poll', 'poll_option') then 'Ton sondage a été modifié'
               else 'Un contenu que tu as publié a été retiré' end;
  why := case r.reason when 'harassment' then 'harcèlement' when 'shocking' then 'contenu choquant' when 'spam' then 'spam'
                       when 'scam' then 'arnaque ou vente' when 'money' then 'argent' else 'contenu contraire aux règles' end;
  select nullif(btrim(contact_email), '') into contact from private.moderation_settings where id = 1;
  perform public.queue_notification(r.target_user, 'content_hidden', null, 'Contenu retiré par la modération',
    what || ' : ' || why || ' (conditions d''utilisation de Party). Tu peux contester : '
      || coalesce(contact, 'écris à l''adresse de contact indiquée dans les conditions d''utilisation') || '.',
    'content_hidden:' || r.target_kind || ':' || r.target_id, jsonb_build_object('target_kind', r.target_kind));
end $$;
revoke all on function private.notify_content_hidden(public.content_reports) from public, anon, authenticated;

do $$ declare def text;
begin
  def := pg_get_functiondef('public.moderation_act(uuid,text,text,integer)'::regprocedure);
  if position('notify_content_hidden' in def) = 0 then
    if position('extra := private.moderation_hide(r);' in def) = 0 then raise exception 'moderation_act : ancre hide introuvable'; end if;
    execute replace(def, 'extra := private.moderation_hide(r);',
      'extra := private.moderation_hide(r);
    perform private.notify_content_hidden(r);');
  end if;

  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''content_hidden''' in def) = 0 then
    if position($a$    when 'moderation_notice' then coalesce(prefs.moderation_notices, true)$a$ in def) = 0 then
      raise exception 'web_push_allowed : ancre moderation_notice introuvable';
    end if;
    execute replace(def, $a$    when 'moderation_notice' then coalesce(prefs.moderation_notices, true)$a$,
      $a$    when 'moderation_notice' then coalesce(prefs.moderation_notices, true)
    when 'content_hidden' then coalesce(prefs.moderation_notices, true)$a$);
  end if;

  def := pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure);
  if position('''content_hidden''' in def) = 0 then
    if position('''moderation_notice'', ''report_new''' in def) = 0 then raise exception 'may_receive_push : ancre moderation_notice introuvable'; end if;
    execute replace(def, '''moderation_notice'', ''report_new''', '''moderation_notice'', ''content_hidden'', ''report_new''');
  end if;
end $$;

-- 4. invite_to_group : lien « direct », même réponse avec ou sans compte, 30 par jour --------------------------------------
create table if not exists private.group_invite_log (
  user_id uuid not null references auth.users (id) on delete cascade,
  at timestamptz not null default now()
);
create index if not exists group_invite_log_user_at on private.group_invite_log (user_id, at);
revoke all on private.group_invite_log from public, anon, authenticated;

-- Lien entre deux personnes (§1 du contrat) ; tant que la migration discussions_v2 manque : 'direct' (règle d'avant).
create or replace function private.invite_link(me uuid, target uuid) returns text
language plpgsql stable security definer set search_path = '' as $$
declare link text;
begin
  if to_regprocedure('private.dm_link(uuid,uuid)') is null then return 'direct'; end if;
  execute 'select private.dm_link($1, $2)' into link using me, target;
  return link;
end $$;
revoke all on function private.invite_link(uuid, uuid) from public, anon, authenticated;

create or replace function public.invite_to_group(grp uuid, member uuid default null, phone text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text; by_phone boolean;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  delete from private.group_invite_log where user_id = auth.uid() and at < now() - interval '2 days';
  if (select count(*) from private.group_invite_log where user_id = auth.uid() and at > now() - interval '1 day') >= 30 then
    raise exception 'limit: tu as envoyé beaucoup d''invitations aujourd''hui, réessaie demain' using errcode = '54000';
  end if;
  insert into private.group_invite_log (user_id) values (auth.uid());
  select * into g from public.member_groups where id = grp;
  by_phone := target is null;
  if by_phone then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
    if target is null then
      insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
      return jsonb_build_object('invited', 'phone');
    end if;
    -- Un compte a ce numéro : invité seulement s'il passerait par son identifiant ; sinon rien, et la même réponse
    -- (on ne révèle jamais qu'un numéro est inscrit, ni un blocage).
    if not exists (select 1 from public.member_group_members where group_id = grp and user_id = target)
       and not private.blocked_either(target, auth.uid()) and not private.blocked_either(target, g.created_by)
       and private.invite_link(auth.uid(), target) = 'direct' then
      insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
      select display_name into me from public.profiles where id = auth.uid();
      perform public.queue_notification(target, 'group_invite', null, g.name,
        coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
        'group_invite:' || grp || ':' || target);
    end if;
    return jsonb_build_object('invited', 'phone');
  end if;
  if exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if private.blocked_either(target, auth.uid()) or private.blocked_either(target, g.created_by) then
    raise exception 'blocked: Tu ne peux pas inviter cette personne.' using errcode = '42501';
  end if;
  if private.invite_link(auth.uid(), target) is distinct from 'direct' then
    raise exception 'link_required: tu ne peux inviter que les personnes que tu connais déjà (groupe, soirée privée ou conversation) : écris-lui d''abord.'
      using errcode = '42501';
  end if;
  insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
  select display_name into me from public.profiles where id = auth.uid();
  perform public.queue_notification(target, 'group_invite', null, g.name,
    coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
    'group_invite:' || grp || ':' || target);
  return jsonb_build_object('invited', 'member');
end $$;
revoke all on function public.invite_to_group(uuid, uuid, text) from public, anon;
grant execute on function public.invite_to_group(uuid, uuid, text) to authenticated;

-- 5. Fichiers orphelins -----------------------------------------------------------------------------------------------------
create table if not exists private.chat_files_gc_runs (
  id integer primary key default 1 check (id = 1),
  last_at timestamptz not null,
  removed jsonb
);
revoke all on private.chat_files_gc_runs from public, anon, authenticated;

-- Fichiers qu'aucune ligne ne désigne plus, vieux de plus d'une heure (300 au plus par compartiment et par passage).
create or replace function private.chat_files_orphans(bucket text, lim integer default 300) returns text[]
language sql stable security definer set search_path = '' as $$
  with refs as (
    select photo_path as p from public.group_messages where bucket = 'chat-photos' and photo_path is not null
    union all select audio_path from public.group_messages where bucket = 'chat-photos' and audio_path is not null
    union all select photo_path from public.direct_messages where bucket = 'chat-photos' and photo_path is not null
    union all select audio_path from public.direct_messages where bucket = 'chat-photos' and audio_path is not null
    union all select photo_path from public.messages where bucket = 'chat-photos' and photo_path is not null
    union all select audio_path from public.messages where bucket = 'chat-photos' and audio_path is not null
    union all select photo_path from public.member_groups where bucket = 'group-photos' and photo_path is not null
    -- Signalements d'avant la copie de preuve : le modérateur lit encore le fichier d'origine (on le garde).
    union all select r.snapshot ->> 'photo_path' from public.content_reports r
      where bucket in ('chat-photos', 'group-photos') and not r.snapshot ? 'evidence' and r.snapshot ->> 'photo_path' is not null
    union all select r.snapshot ->> 'audio_path' from public.content_reports r
      where bucket = 'chat-photos' and not r.snapshot ? 'evidence' and r.snapshot ->> 'audio_path' is not null
  )
  select coalesce(array_agg(o.name order by o.created_at), '{}') from (
    select o.name, o.created_at from storage.objects o
    where o.bucket_id = bucket and o.created_at < now() - interval '1 hour'
      and case when bucket = 'moderation-evidence'
               then not exists (select 1 from public.content_reports r where r.id::text = split_part(o.name, '/', 1))
               else not exists (select 1 from refs where refs.p = o.name) end
    order by o.created_at limit greatest(1, least(coalesce(lim, 300), 1000))) o;
$$;
revoke all on function private.chat_files_orphans(text, integer) from public, anon, authenticated;

-- Appelée par le serveur Party (sans compte : clé publique) ; au plus une fois toutes les 10 minutes.
create or replace function public.chat_files_gc() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare last timestamptz; out jsonb := '{}'::jsonb; b text;
begin
  select last_at into last from private.chat_files_gc_runs where id = 1 for update;
  if last > now() - interval '10 minutes' then return jsonb_build_object('skipped', true); end if;
  if private.storage_api() is null then return jsonb_build_object('skipped', true, 'reason', 'no_storage_key'); end if;
  foreach b in array array['chat-photos', 'group-photos', 'moderation-evidence'] loop
    out := out || jsonb_build_object(b, private.storage_remove(b, private.chat_files_orphans(b)));
  end loop;
  insert into private.chat_files_gc_runs (id, last_at, removed) values (1, now(), out)
  on conflict (id) do update set last_at = excluded.last_at, removed = excluded.removed;
  return out;
end $$;
revoke all on function public.chat_files_gc() from public;
grant execute on function public.chat_files_gc() to anon, authenticated;

-- Compte supprimé : les photos et vocaux de ses messages partent aussitôt (la cascade n'efface que les lignes).
create or replace function private.chat_files_of_account() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.storage_remove('chat-photos', array(
    select p from (
      select photo_path as p from public.group_messages where user_id = old.id
      union all select audio_path from public.group_messages where user_id = old.id
      union all select photo_path from public.direct_messages where user_id = old.id
      union all select audio_path from public.direct_messages where user_id = old.id
      union all select photo_path from public.messages where user_id = old.id
      union all select audio_path from public.messages where user_id = old.id) f
    where p is not null limit 5000));
  return old;
end $$;
revoke all on function private.chat_files_of_account() from public, anon, authenticated;
drop trigger if exists chat_files_of_account on auth.users;
create trigger chat_files_of_account before delete on auth.users
  for each row execute function private.chat_files_of_account();

notify pgrst, 'reload schema';

insert into supabase_migrations.schema_migrations (version, name) values ('20261118121000', 'discussions_moderation') on conflict do nothing;
commit;
