-- PROD, groupes_photo (20261117130000) : migration supabase/migrations/20261117130000_groupes_photo.sql telle quelle (mise en prod du 19.11).
-- Additive et rejouable. Tout ou rien.
begin;
-- Photo de groupe (demande de l'admin du 17.11.2026) : le créateur du groupe (ou un Admin du site) peut lui donner une
-- photo, qui remplace l'emoji dans la tuile et sert de couverture à la page du groupe. Membres Vendredi Party : jamais de
-- photo, son image est le logo officiel de l'app (affiché par les applis), personne ne la change.
--
-- · Fichier : compartiment privé « group-photos », dossier = identifiant du groupe, JPEG/PNG/WebP, 5 Mo au plus.
--   Écrire : qui gère le groupe (private.manages_group). Lire : ses membres, son créateur, qui le gère, les modérateurs.
-- · member_groups.photo_path : garde private.group_photo_guard (chemin du dossier du groupe, fichier présent, CGU,
--   jamais sur le groupe du système) ; photo_by = qui l'a posée (pour la modération).
-- · « Signaler la photo » : content_reports « group_photo » (copie du chemin) ; « Masquer » la retire du groupe et
--   renvoie remove_group_photo (le fichier part par l'API Storage, comme une photo de profil).
-- · my_groups_overview (photo) et my_chats (photo_path) la donnent aux écrans.
-- Purement additif et rejouable.

alter table public.member_groups add column if not exists photo_path text;
alter table public.member_groups add column if not exists photo_by uuid references public.profiles(id) on delete set null;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('group-photos', 'group-photos', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Politiques d'abord : elles dépendent des fonctions ci-dessous (paramètre « obj » : « name » se confondait avec la
-- colonne name de member_groups).
drop policy if exists "photo de groupe : envoyer" on storage.objects;
drop policy if exists "photo de groupe : voir" on storage.objects;
drop policy if exists "photo de groupe : retirer" on storage.objects;
drop function if exists private.group_photo_can_write(text);
drop function if exists private.group_photo_can_read(text);
drop function if exists private.group_photo_group(text);

-- Le groupe d'un fichier (premier dossier du chemin), null si ce n'est pas un identifiant.
create or replace function private.group_photo_group(obj text) returns uuid
language plpgsql immutable set search_path = '' as $$
begin
  return (storage.foldername(obj))[1]::uuid;
exception when others then
  return null;
end $$;

create or replace function private.group_photo_can_write(obj text) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and private.manages_group(private.group_photo_group(obj));
$$;

create or replace function private.group_photo_can_read(obj text) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and exists (
    select 1 from public.member_groups g where g.id = private.group_photo_group(obj)
      and (private.in_group(g.id, auth.uid()) or g.created_by = auth.uid() or private.manages_group(g.id)
           or public.has_perm('moderation.reports')));
$$;
revoke all on function private.group_photo_group(text), private.group_photo_can_write(text), private.group_photo_can_read(text)
  from public, anon;
grant execute on function private.group_photo_group(text), private.group_photo_can_write(text), private.group_photo_can_read(text)
  to authenticated;

drop policy if exists "photo de groupe : envoyer" on storage.objects;
create policy "photo de groupe : envoyer" on storage.objects for insert to authenticated
  with check (bucket_id = 'group-photos' and private.group_photo_can_write(name));
drop policy if exists "photo de groupe : voir" on storage.objects;
create policy "photo de groupe : voir" on storage.objects for select to authenticated
  using (bucket_id = 'group-photos' and private.group_photo_can_read(name));
drop policy if exists "photo de groupe : retirer" on storage.objects;
create policy "photo de groupe : retirer" on storage.objects for delete to authenticated
  using (bucket_id = 'group-photos' and (private.group_photo_can_write(name)
         or ((select public.has_perm('moderation.reports'))
             and exists (select 1 from public.content_reports r where r.target_kind = 'group_photo' and r.snapshot ->> 'photo_path' = name))));

create or replace function private.group_photo_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.system_key is not null then
    new.photo_path := null;
    new.photo_by := null;
    return new;
  end if;
  if tg_op = 'UPDATE' and new.photo_path is not distinct from old.photo_path then
    new.photo_by := old.photo_by;
    return new;
  end if;
  if new.photo_path is null then
    new.photo_by := null;
    return new;
  end if;
  if new.photo_path !~ ('^' || new.id::text || '/[A-Za-z0-9_-]{1,80}\.(jpg|jpeg|png|webp)$')
     or not exists (select 1 from storage.objects o where o.bucket_id = 'group-photos' and o.name = new.photo_path) then
    raise exception 'photo: cette photo n''a pas été envoyée pour ce groupe' using errcode = '22023';
  end if;
  perform private.require_terms(auth.uid());
  new.photo_by := auth.uid();
  return new;
end $$;
revoke all on function private.group_photo_guard() from public, anon, authenticated;

drop trigger if exists member_groups_photo_guard on public.member_groups;
create trigger member_groups_photo_guard before insert or update of photo_path, photo_by, system_key on public.member_groups
  for each row execute function private.group_photo_guard();

-- Photo changée : chaque membre relit ses écrans (même signal que nom / emoji / couleur).
create or replace function private.group_photo_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
declare uid uuid;
begin
  for uid in select user_id from public.member_group_members where group_id = new.id loop
    perform private.party_signal('user:' || uid);
  end loop;
  return null;
exception when others then
  return null;  -- un signal perdu ne fait jamais échouer la modification
end $$;
revoke all on function private.group_photo_changed() from public, anon, authenticated;

drop trigger if exists member_groups_photo_changed on public.member_groups;
create trigger member_groups_photo_changed after update of photo_path on public.member_groups
  for each row when (new.photo_path is distinct from old.photo_path) execute function private.group_photo_changed();

alter table public.content_reports drop constraint if exists content_reports_target_kind_check;
alter table public.content_reports add constraint content_reports_target_kind_check
  check (target_kind in ('group_message', 'direct_message', 'event_message', 'profile', 'profile_photo', 'event',
                         'rsvp_note', 'poll', 'poll_option', 'bring_item', 'group_photo',
                         'pet_name', 'pet_item', 'pet_offer', 'pet_showcase', 'pet_word'));

create or replace function public.my_groups_overview() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(x.g order by x.sys desc, x.last_at desc nulls last, x.name), '[]'::jsonb) from (
    select g.system_key is not null as sys, coalesce(last.created_at, g.created_at) as last_at, g.name,
      jsonb_build_object(
        'id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color, 'photo', g.photo_path, 'system', g.system_key is not null,
        'creator', coalesce(g.created_by = auth.uid(), false),
        'manage', private.manages_group(g.id),
        'member', private.in_group_now(g.id, auth.uid()),
        'created_by_name', (select display_name from public.profiles where id = g.created_by),
        'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
        'faces', (select coalesce(jsonb_agg(jsonb_build_object('id', f.id, 'name', f.display_name, 'avatar_url', f.avatar_url)), '[]'::jsonb)
                  from (select p.id, p.display_name, p.avatar_url from public.member_group_members m
                        join public.profiles p on p.id = m.user_id
                        where m.group_id = g.id and p.status = 'active'
                        order by (p.id = auth.uid()), (p.avatar_url is null), m.added_at desc nulls last limit 5) f),
        'last', case when last.id is null then null
                     when last.deleted_at is not null then 'Message supprimé'
                     when last.body <> '' then left(last.body, 80)
                     when last.audio_path is not null then '🎤 Message vocal'
                     else '📷 Photo' end,
        'last_by', case when last.id is null or last.deleted_at is not null then null
                        when last.user_id = auth.uid() then 'Toi'
                        else (select display_name from public.profiles where id = last.user_id) end,
        'last_at', last.created_at,
        'unread', case when private.in_group_now(g.id, auth.uid()) then
                    (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                       and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity')
                       and not exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = m.user_id))
                  else 0 end,
        'next_event', (select jsonb_build_object('id', e.id, 'title', e.title, 'starts_at', e.starts_at, 'date_mode', e.date_mode)
                       from public.events e
                       where e.id in (select private.group_event_ids(g.id)) and e.status = 'published'
                         and (e.date_mode = 'poll' or e.starts_at > now() - interval '6 hours')
                         and public.can_see_event(e.id)
                       order by e.starts_at nulls last limit 1)
      ) as g
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id
                         and not exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = m.user_id)
                       order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or g.created_by = auth.uid())
  ) x;
$$;

create or replace function public.my_chats() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(c order by (c->>'last_at') desc nulls last, c->>'name'), '[]'::jsonb) from (
    select jsonb_build_object(
      'id', g.id, 'name', g.name, 'kind', 'group', 'system', g.system_key is not null,
      'emoji', g.emoji, 'color', g.color, 'photo_path', g.photo_path,
      'member', private.in_group_now(g.id, auth.uid()),
      'admin', private.group_admin(g.id, auth.uid()),
      'creator', g.created_by = auth.uid(),
      'members', (select count(*) from public.member_group_members m where m.group_id = g.id),
      'notify', coalesce(s.notify, 'mentions'),
      'last_at', last.created_at,
      'last', case when last.id is null then null
                   when last.deleted_at is not null then case when last.deleted_by_admin then 'Message supprimé par un admin' else 'Message supprimé' end
                   else coalesce((select display_name from public.profiles where id = last.user_id), '?') || ' : '
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.group_messages m where m.group_id = g.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.member_groups g
    left join public.group_chat_settings s on s.group_id = g.id and s.user_id = auth.uid()
    left join lateral (select * from public.group_messages m where m.group_id = g.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and (private.in_group_now(g.id, auth.uid()) or private.is_root(auth.uid()))
    union all
    select jsonb_build_object(
      'id', d.id, 'name', coalesce(nullif(btrim(o.display_name), ''), 'Profil à compléter'), 'kind', 'direct', 'system', false,
      'user_id', o.id, 'avatar_url', o.avatar_url,
      'member', true, 'admin', false, 'creator', false, 'members', 2,
      'blocked', exists (select 1 from public.direct_blocks k where k.user_id = auth.uid() and k.blocked_id = o.id),
      'notify', coalesce(s.notify, 'all'),
      'last_at', last.created_at,
      'last', case when last.deleted_at is not null then 'Message supprimé'
                   else case when last.user_id = auth.uid() then 'Toi : ' else '' end
                        || case when last.body <> '' then left(last.body, 80) when last.audio_path is not null then '🎤 Message vocal'
                                else '📷 Photo' end end,
      'unread', (select count(*) from public.direct_messages m where m.chat_id = d.id and m.user_id <> auth.uid()
                 and m.deleted_at is null and m.created_at > coalesce(s.read_at, '-infinity'))) as c
    from public.direct_chats d
    join public.profiles o on o.id = case when d.user_a = auth.uid() then d.user_b else d.user_a end
    left join public.direct_chat_settings s on s.chat_id = d.id and s.user_id = auth.uid()
    join lateral (select * from public.direct_messages m where m.chat_id = d.id order by m.created_at desc limit 1) last on true
    where auth.uid() is not null and auth.uid() in (d.user_a, d.user_b)
  ) x;
$$;

create or replace function private.report_snapshot(p_kind text, p_id text, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare gm public.group_messages; dm public.direct_messages; em public.messages; p public.profiles; ev public.events; uid uuid;
        rn public.rsvp_notes; mg public.member_groups; po public.polls; op public.poll_options; bi public.bring_items;
begin
  if p_kind like 'pet\_%' then return private.report_snapshot_pet(p_kind, p_id, viewer); end if;
  begin uid := p_id::uuid; exception when others then return null; end;
  if p_kind = 'group_message' then
    select * into gm from public.group_messages where id = uid;
    if gm.id is null or not private.reads_group(gm.group_id) then return null; end if;
    return jsonb_build_object('owner', gm.user_id, 'text', gm.body, 'photo_path', gm.photo_path, 'audio_path', gm.audio_path,
      'at', gm.created_at, 'place', (select name from public.member_groups where id = gm.group_id), 'group_id', gm.group_id);
  elsif p_kind = 'direct_message' then
    select * into dm from public.direct_messages where id = uid;
    if dm.id is null or not private.in_direct(dm.chat_id, viewer) then return null; end if;
    return jsonb_build_object('owner', dm.user_id, 'text', dm.body, 'photo_path', dm.photo_path, 'audio_path', dm.audio_path,
      'at', dm.created_at, 'place', 'Message direct', 'chat_id', dm.chat_id);
  elsif p_kind = 'event_message' then
    select * into em from public.messages where id = uid;
    if em.id is null or not public.can_see_event(em.event_id) then return null; end if;
    return jsonb_build_object('owner', em.user_id, 'text', em.body, 'at', em.created_at, 'event_id', em.event_id,
      'place', (select title from public.events where id = em.event_id));
  elsif p_kind = 'event' then
    select * into ev from public.events where id = uid;
    if ev.id is null then return null; end if;
    if not (public.can_see_event(ev.id)
            or (ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled'))) then
      return null;
    end if;
    return jsonb_build_object('owner', ev.created_by,
      'text', ev.title || case when btrim(coalesce(ev.description, '')) <> '' then E'\n\n' || ev.description else '' end,
      'cover_url', ev.cover_url, 'at', ev.created_at, 'event_id', ev.id, 'place', 'Événement');
  elsif p_kind = 'rsvp_note' then
    -- Lu par la personne et l'organisation seulement : seuls eux peuvent le signaler.
    select * into rn from public.rsvp_notes where id = uid;
    if rn.id is null or not (rn.user_id = viewer or public.is_admin() or public.is_organizer(rn.event_id)) then return null; end if;
    return jsonb_build_object('owner', rn.user_id, 'text', rn.note, 'at', rn.updated_at, 'event_id', rn.event_id,
      'place', 'Petit mot · ' || (select title from public.events where id = rn.event_id));
  elsif p_kind = 'poll' then
    select * into po from public.polls where id = uid;
    if po.id is null or not ((po.event_id is null and public.is_active()) or public.can_see_event(po.event_id)
                             or public.is_organizer(po.event_id)) then return null; end if;
    return jsonb_build_object('owner', po.created_by, 'text', po.question, 'at', po.created_at, 'event_id', po.event_id,
      'place', 'Sondage' || coalesce(' · ' || (select title from public.events where id = po.event_id), ''));
  elsif p_kind = 'poll_option' then
    select * into op from public.poll_options where id = uid;
    select * into po from public.polls where id = op.poll_id;
    if op.id is null or not ((po.event_id is null and public.is_active()) or public.can_see_event(po.event_id)
                             or public.is_organizer(po.event_id)) then return null; end if;
    return jsonb_build_object('owner', coalesce(op.created_by, po.created_by), 'text', op.label, 'event_id', po.event_id,
      'place', 'Sondage · ' || po.question);
  elsif p_kind = 'bring_item' then
    select * into bi from public.bring_items where id = uid;
    if bi.id is null or not (public.can_see_event(bi.event_id) or public.is_organizer(bi.event_id)) then return null; end if;
    return jsonb_build_object('owner', bi.added_by, 'text', bi.label, 'event_id', bi.event_id,
      'place', 'Qui amène quoi · ' || (select title from public.events where id = bi.event_id));
  elsif p_kind = 'group_photo' then
    -- Vue par les membres du groupe (et qui le gère) seulement : seuls eux peuvent la signaler.
    select * into mg from public.member_groups where id = uid;
    if mg.id is null or mg.photo_path is null
       or not (private.in_group(mg.id, viewer) or mg.created_by = viewer or private.manages_group(mg.id)) then return null; end if;
    return jsonb_build_object('owner', coalesce(mg.photo_by, mg.created_by), 'text', mg.name, 'photo_path', mg.photo_path,
      'group_id', mg.id, 'place', 'Photo du groupe');
  elsif p_kind in ('profile', 'profile_photo') then
    select * into p from public.profiles where id = uid and status = 'active';
    if p.id is null then return null; end if;
    return jsonb_build_object('owner', p.id, 'text', p.display_name,
      'photo_path', case when p_kind = 'profile_photo' then p.avatar_url end, 'place', 'Profil');
  end if;
  return null;
end $$;

create or replace function private.notify_new_report() returns trigger
language plpgsql security definer set search_path = '' as $$
declare u uuid;
begin
  for u in select p.id from public.profiles p where p.status = 'active' and private.user_has(p.id, 'moderation.reports') loop
    perform public.queue_notification(u, 'report_new', null, 'Nouveau signalement',
      (case new.reason when 'harassment' then 'Harcèlement' when 'shocking' then 'Contenu choquant' when 'spam' then 'Spam'
                       when 'scam' then 'Arnaque ou vente' else 'Autre raison' end)
      || ' · ' || (case when new.target_kind in ('group_message', 'direct_message', 'event_message') then 'un message'
                        when new.target_kind = 'profile' then 'un profil' when new.target_kind = 'profile_photo' then 'une photo de profil'
                        when new.target_kind = 'group_photo' then 'une photo de groupe'
                        when new.target_kind = 'event' then 'un événement'
                        when new.target_kind = 'rsvp_note' then 'un petit mot'
                        when new.target_kind in ('poll', 'poll_option') then 'un sondage'
                        when new.target_kind = 'bring_item' then 'un objet à amener'
                        else 'Zicou' end),
      'report:' || new.id, jsonb_build_object('report_id', new.id));
  end loop;
  return null;
end $$;

create or replace function private.moderation_hide(r public.content_reports) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare uid uuid;
begin
  if r.target_kind like 'pet\_%' then
    perform private.moderation_hide_pet(r.target_kind, r.target_id);
    return '{}'::jsonb;
  end if;
  uid := r.target_id::uuid;
  if r.target_kind = 'group_message' then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false,
      pinned = false, announcement = false, deleted_at = coalesce(deleted_at, now()), deleted_by_admin = true where id = uid;
    delete from public.group_message_reactions where message_id = uid;
  elsif r.target_kind = 'direct_message' then
    update public.direct_messages set body = '', photo_path = null, audio_path = null, pinned = false,
      deleted_at = coalesce(deleted_at, now()) where id = uid;
    delete from public.direct_message_reactions where message_id = uid;
  elsif r.target_kind = 'event_message' then
    update public.messages set body = '•', mentions = '{}', pinned = false, deleted_at = coalesce(deleted_at, now()) where id = uid;
  elsif r.target_kind = 'event' then
    if not private.user_has(auth.uid(), 'events.manage_all') then
      raise exception 'forbidden: masquer un événement demande aussi le droit « Modifier ou annuler tous les événements »'
        using errcode = '42501';
    end if;
    update public.events set title = 'Événement masqué par la modération', description = '', cover_url = null,
      public_link = false where id = uid;
  elsif r.target_kind = 'rsvp_note' then
    delete from public.rsvp_notes where id = uid;
  elsif r.target_kind = 'poll' then
    update public.polls set question = 'Question masquée par la modération' where id = uid;
  elsif r.target_kind = 'poll_option' then
    delete from public.poll_options where id = uid;
  elsif r.target_kind = 'bring_item' then
    delete from public.bring_items where id = uid;
  elsif r.target_kind = 'profile' then
    update public.profiles set display_name = 'Surnom masqué' where id = uid;
  elsif r.target_kind = 'group_photo' then
    -- La photo quitte le groupe (s'il l'a encore) ; le fichier se retire par l'API Storage, comme une photo de profil.
    update public.member_groups set photo_path = null, photo_by = null
      where id = uid and photo_path = r.snapshot ->> 'photo_path';
    return jsonb_build_object('remove_group_photo', r.snapshot ->> 'photo_path');
  elsif r.target_kind = 'profile_photo' then
    -- Le fichier se retire par l'API Storage (politique « modérateurs retirent une photo signalée ») : l'appli le fait.
    return jsonb_build_object('remove_photo', r.snapshot ->> 'photo_path');
  end if;
  return '{}'::jsonb;
end $$;
revoke all on function private.report_snapshot(text, text, uuid), private.notify_new_report(),
  private.moderation_hide(public.content_reports) from public, anon, authenticated;
revoke all on function public.my_groups_overview(), public.my_chats() from public, anon;
grant execute on function public.my_groups_overview(), public.my_chats() to authenticated;

notify pgrst, 'reload schema';

insert into supabase_migrations.schema_migrations (version, name) values ('20261117130000', 'groupes_photo') on conflict do nothing;
commit;
