-- Discussions (avis de l'admin, 3 novembre 2026, et ses réponses du même jour) :
-- • rôle de groupe « Organisateur » (en plus de membre et admin), nommé par les admins du groupe ;
-- • @tout : chaque groupe choisit qui peut l'écrire (tous les membres, par défaut, ou admins et organisateurs) ;
-- • @annonce (admins et organisateurs) : message épinglé d'office, marqué annonce (bandeau en surbrillance en haut) et
--   notifié à tout le groupe comme @tout ; d'un simple membre, c'est un message normal (l'app le prévient avant l'envoi) ;
--   retirée par les admins et les organisateurs du groupe ;
-- • Réglages › Notifications : « Annonces et @tout des groupes » se coupe (notification_prefs.group_broadcasts),
--   en plus du réglage de chaque groupe (tout / citations / rien) et de la pause des Discussions.
-- • un groupe créé (Réglages › Groupes ou Discussions) compte son créateur parmi ses membres d'office, comme
--   « Créateur · Admin » (il en était déjà l'admin : private.group_admin) ; les groupes existants ne changent pas.
-- Purement additif et rejouable : l'ancien code (qui ignore ces colonnes) continue de marcher.

alter table public.group_messages add column if not exists announcement boolean not null default false;
-- Qui peut écrire @tout dans ce groupe : 'all' (tous les membres) ou 'staff' (admins et organisateurs).
alter table public.member_groups add column if not exists everyone_tag text not null default 'all';
alter table public.member_groups drop constraint if exists member_groups_everyone_tag_check;
alter table public.member_groups add constraint member_groups_everyone_tag_check check (everyone_tag in ('all', 'staff'));
alter table public.notification_prefs add column if not exists group_broadcasts boolean not null default true;

create table if not exists public.group_organizers (
  group_id uuid not null references public.member_groups(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  primary key (group_id, user_id)
);
alter table public.group_organizers enable row level security;
drop policy if exists "voir les organisateurs du groupe" on public.group_organizers;
create policy "voir les organisateurs du groupe" on public.group_organizers for select to authenticated
  using (private.reads_group(group_id));
grant select on public.group_organizers to authenticated;

-- Admins et organisateurs du groupe (organisateur : seulement tant qu'il fait partie du groupe).
create or replace function private.group_staff(grp uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.group_admin(grp, uid)
    or (private.in_group_now(grp, uid) and exists (select 1 from public.group_organizers o where o.group_id = grp and o.user_id = uid));
$$;
revoke all on function private.group_staff(uuid, uuid) from public, anon;
grant execute on function private.group_staff(uuid, uuid) to authenticated;

-- Un message à l'arrivée : auteur = la personne connectée ; citations limitées aux membres du groupe ; rien de supprimé
-- d'office ; @tout selon le choix du groupe ; « @annonce » (mot entier, sans casse) d'un admin ou d'un organisateur :
-- épinglé, annonce, et cité à tout le groupe.
create or replace function private.guard_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare staff boolean;
begin
  if auth.uid() is not null then new.user_id := auth.uid(); end if;
  staff := private.group_staff(new.group_id, new.user_id);
  new.body := btrim(new.body);
  new.announcement := staff and new.body ~* '(^|[^[:alnum:]_])@annonce($|[^[:alnum:]_])';
  new.pinned := new.announcement;
  new.deleted_at := null;
  new.deleted_by_admin := false;
  new.edited_at := null;
  new.created_at := now();
  new.mention_all := (coalesce(new.mention_all, false)
                      and (staff or coalesce((select g.everyone_tag from public.member_groups g where g.id = new.group_id), 'all') = 'all'))
                     or new.announcement;
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
drop trigger if exists group_messages_guard on public.group_messages;
create trigger group_messages_guard before insert on public.group_messages
  for each row execute function private.guard_group_message();

-- Notifications : citations (@surnom, réponse) ; @tout et annonces à tout le groupe, sauf pour qui a coupé
-- « Annonces et @tout des groupes » dans Réglages ; « tous les messages » ou « rien » au choix par groupe.
-- (La pause des Discussions s'applique ensuite à l'envoi, comme pour tout message de groupe.)
create or replace function private.notify_group_message() returns trigger
language plpgsql security definer set search_path = '' as $$
declare g public.member_groups; who text; replied uuid; u uuid; level text; cited boolean; preview text; broadcasts boolean;
begin
  select * into g from public.member_groups where id = new.group_id;
  select display_name into who from public.profiles where id = new.user_id;
  select user_id into replied from public.group_messages where id = new.reply_to;
  preview := case when new.announcement then '📣 ' else '' end
          || case when new.body <> '' then left(new.body, 140) when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end;
  for u in select user_id from public.member_group_members where group_id = new.group_id and user_id <> new.user_id loop
    select notify into level from public.group_chat_settings where group_id = new.group_id and user_id = u;
    broadcasts := coalesce((select p.group_broadcasts from public.notification_prefs p where p.user_id = u), true);
    cited := (new.mention_all and broadcasts) or u = any(new.mentions) or u = replied;
    if coalesce(level, 'mentions') = 'all' or (coalesce(level, 'mentions') = 'mentions' and cited) then
      insert into public.notifications (user_id, kind, event_id, title, body, data)
      values (u, 'group_message', null, g.name, coalesce(nullif(btrim(who), ''), 'Quelqu''un') || ' : ' || preview,
              jsonb_build_object('group_id', g.id, 'message_id', new.id, 'mentioned', cited, 'kind', 'group_message',
                                 'announcement', new.announcement));
    end if;
  end loop;
  return null;
end $$;
drop trigger if exists group_messages_notify on public.group_messages;
create trigger group_messages_notify after insert on public.group_messages
  for each row execute function private.notify_group_message();

-- Épingler (admins du groupe) ; désépingler : admins, et pour une annonce aussi les organisateurs.
create or replace function public.pin_group_message(msg uuid, pin boolean) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.group_messages;
begin
  select * into m from public.group_messages where id = msg and deleted_at is null;
  if m.id is null or not (private.group_admin(m.group_id, auth.uid())
                          or (not pin and m.announcement and private.group_staff(m.group_id, auth.uid()))) then
    raise exception 'forbidden: réservé aux admins du groupe' using errcode = '42501';
  end if;
  update public.group_messages set pinned = pin, announcement = announcement and pin where id = msg;
end $$;

-- Supprimer : l'auteur ou un admin du groupe ; une annonce supprimée quitte aussi le bandeau.
create or replace function public.delete_group_message(msg uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare m public.group_messages;
begin
  select * into m from public.group_messages where id = msg and deleted_at is null;
  if m.id is null then raise exception 'Message introuvable'; end if;
  if m.user_id = auth.uid() then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false, pinned = false,
      announcement = false, deleted_at = now(), deleted_by_admin = false where id = msg;
  elsif private.group_admin(m.group_id, auth.uid()) then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false, pinned = false,
      announcement = false, deleted_at = now(), deleted_by_admin = true where id = msg;
  else
    raise exception 'forbidden: seuls l''auteur et les admins du groupe suppriment un message' using errcode = '42501';
  end if;
  delete from public.group_message_reactions where message_id = msg;
end $$;

-- Les admins du groupe nomment ou retirent ses organisateurs (membres du groupe).
create or replace function public.set_group_organizer(grp uuid, member uuid, organizer boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not private.group_admin(grp, auth.uid()) then
    raise exception 'forbidden: réservé aux admins du groupe' using errcode = '42501';
  end if;
  if organizer and not private.in_group_now(grp, member) then raise exception 'Cette personne n''est pas dans le groupe'; end if;
  if organizer then
    insert into public.group_organizers (group_id, user_id) values (grp, member) on conflict do nothing;
  else
    delete from public.group_organizers where group_id = grp and user_id = member;
  end if;
end $$;

-- Les admins du groupe choisissent qui peut écrire @tout : 'all' (tous les membres) ou 'staff' (admins et organisateurs).
create or replace function public.set_group_everyone_tag(grp uuid, who text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if who is null or who not in ('all', 'staff') then raise exception 'Choix inconnu'; end if;
  if not private.group_admin(grp, auth.uid()) then
    raise exception 'forbidden: réservé aux admins du groupe' using errcode = '42501';
  end if;
  update public.member_groups set everyone_tag = who where id = grp;
end $$;

-- everyone_tag ne change que par un admin du groupe (la règle « modifier son groupe » ne suffit pas).
create or replace function private.guard_group_everyone_tag() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.everyone_tag is distinct from old.everyone_tag and auth.uid() is not null
     and not private.group_admin(new.id, auth.uid()) then
    new.everyone_tag := old.everyone_tag;
  end if;
  return new;
end $$;
drop trigger if exists member_groups_everyone_tag_guard on public.member_groups;
create trigger member_groups_everyone_tag_guard before update on public.member_groups
  for each row execute function private.guard_group_everyone_tag();

-- Le créateur d'un groupe en fait partie d'office (pas les groupes du système, comme Vendredi Party).
create or replace function private.group_creator_joins() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.created_by is not null and new.system_key is null then
    insert into public.member_group_members (group_id, user_id) values (new.id, new.created_by) on conflict do nothing;
  end if;
  return null;
end $$;
drop trigger if exists member_groups_creator_joins on public.member_groups;
create trigger member_groups_creator_joins after insert on public.member_groups
  for each row execute function private.group_creator_joins();

revoke all on function public.delete_group_message(uuid), public.pin_group_message(uuid, boolean),
  public.set_group_organizer(uuid, uuid, boolean), public.set_group_everyone_tag(uuid, text) from public, anon;
grant execute on function public.delete_group_message(uuid), public.pin_group_message(uuid, boolean),
  public.set_group_organizer(uuid, uuid, boolean), public.set_group_everyone_tag(uuid, text) to authenticated;
