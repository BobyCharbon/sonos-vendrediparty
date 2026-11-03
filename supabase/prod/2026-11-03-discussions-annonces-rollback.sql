-- PROD, retour arrière de chat_mentions_annonces (20261103121000) : @tout de nouveau réservé aux admins du groupe,
-- plus d'@annonce (les annonces déjà faites restent épinglées comme de simples messages épinglés), plus d'organisateurs
-- de groupe, plus de choix « qui peut écrire @tout », plus de réglage « Annonces et @tout des groupes ».
begin;
drop trigger if exists member_groups_creator_joins on public.member_groups;
drop function if exists private.group_creator_joins();
drop trigger if exists member_groups_everyone_tag_guard on public.member_groups;
drop function if exists private.guard_group_everyone_tag();
drop function if exists public.set_group_everyone_tag(uuid, text);
drop function if exists public.set_group_organizer(uuid, uuid, boolean);

create or replace function private.notify_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text; replied uuid; u uuid; level text; cited boolean; preview text;
begin
  select * into g from public.member_groups where id = new.group_id;
  select display_name into who from public.profiles where id = new.user_id;
  select user_id into replied from public.group_messages where id = new.reply_to;
  preview := case when new.body <> '' then left(new.body, 140) when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end;
  for u in select user_id from public.member_group_members where group_id = new.group_id and user_id <> new.user_id loop
    select notify into level from public.group_chat_settings where group_id = new.group_id and user_id = u;
    cited := new.mention_all or u = any(new.mentions) or u = replied;
    if coalesce(level, 'mentions') = 'all' or (coalesce(level, 'mentions') = 'mentions' and cited) then
      insert into public.notifications (user_id, kind, event_id, title, body, data)
      values (u, 'group_message', null, g.name, coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' : ' || preview,
              jsonb_build_object('group_id', g.id, 'message_id', new.id, 'mentioned', cited, 'kind', 'group_message'));
    end if;
  end loop;
  return null;
end $$;
create or replace function private.guard_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null then new.user_id := auth.uid(); end if;
  new.body := btrim(new.body);
  new.pinned := false;
  new.deleted_at := null;
  new.deleted_by_admin := false;
  new.edited_at := null;
  new.created_at := now();
  if new.mention_all and not private.group_admin(new.group_id, new.user_id) then new.mention_all := false; end if;
  new.mentions := coalesce((select array_agg(distinct m) from unnest(new.mentions) m
                            where private.in_group_now(new.group_id, m) and m <> new.user_id), '{}');
  if new.reply_to is not null and not exists (select 1 from public.group_messages r where r.id = new.reply_to and r.group_id = new.group_id) then
    new.reply_to := null;
  end if;
  if new.photo_path is not null and split_part(new.photo_path, '/', 1) <> new.group_id::text then
    raise exception 'Photo invalide';
  end if;
  if new.audio_path is not null and split_part(new.audio_path, '/', 1) <> new.group_id::text then
    raise exception 'Message vocal invalide';
  end if;
  return new;
end $$;

create or replace function public.pin_group_message(msg uuid, pin boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  select group_id into grp from public.group_messages where id = msg and deleted_at is null;
  if grp is null or not private.group_admin(grp, auth.uid()) then
    raise exception 'forbidden: réservé aux admins du groupe' using errcode = '42501';
  end if;
  update public.group_messages set pinned = pin where id = msg;
end $$;

create or replace function public.delete_group_message(msg uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.group_messages;
begin
  select * into m from public.group_messages where id = msg and deleted_at is null;
  if m.id is null then raise exception 'Message introuvable'; end if;
  if m.user_id = auth.uid() then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false, pinned = false,
      deleted_at = now(), deleted_by_admin = false where id = msg;
  elsif private.group_admin(m.group_id, auth.uid()) then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false, pinned = false,
      deleted_at = now(), deleted_by_admin = true where id = msg;
  else
    raise exception 'forbidden: seuls l''auteur et les admins du groupe suppriment un message' using errcode = '42501';
  end if;
  delete from public.group_message_reactions where message_id = msg;
end $$;

alter table public.group_messages drop column if exists announcement;
drop function if exists private.group_staff(uuid, uuid);
drop table if exists public.group_organizers;
alter table public.member_groups drop constraint if exists member_groups_everyone_tag_check;
alter table public.member_groups drop column if exists everyone_tag;
alter table public.notification_prefs drop column if exists group_broadcasts;
delete from supabase_migrations.schema_migrations where version = '20261103121000';
commit;
