-- Retour arrière de la discussion d'un événement façon WhatsApp (20261116180000) : garde et notification des messages
-- d'avant (définitions lues en prod le 16.11.2026), fonctions et règles de stockage retirées. Les photos, vocaux et
-- annonces déjà écrits perdent ces colonnes ; un message sans texte (photo ou vocal seul) est supprimé (l'ancienne
-- contrainte exige un texte).
begin;
CREATE OR REPLACE FUNCTION private.guard_message_change()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare staff boolean;
begin
  if auth.uid() is null then return new; end if;
  staff := public.is_admin() or public.is_organizer(coalesce(old.event_id, new.event_id));
  if tg_op = 'INSERT' then
    if new.pinned and not staff then new.pinned := false; end if;
    return new;
  end if;
  new.event_id := old.event_id; new.user_id := old.user_id; new.created_at := old.created_at;
  if old.deleted_at is not null then
    -- Supprimé : le reste, sans texte.
    new.deleted_at := old.deleted_at; new.body := old.body; new.mentions := old.mentions; new.reply_to := old.reply_to;
    new.edited_at := old.edited_at; new.pinned := false;
    return new;
  end if;
  if new.deleted_at is not null then
    -- Supprimer efface le texte pour de bon (plus lisible par l'API).
    new.body := '•'; new.mentions := '{}'; new.pinned := false;
    return new;
  end if;
  if auth.uid() is distinct from old.user_id
     and (new.body is distinct from old.body or new.mentions is distinct from old.mentions
          or new.reply_to is distinct from old.reply_to or new.edited_at is distinct from old.edited_at) then
    raise exception 'Seul l''auteur peut modifier son message.' using errcode = '42501';
  end if;
  if new.pinned is distinct from old.pinned and not staff then
    raise exception 'Épingler un message est réservé à l''organisation de l''événement.' using errcode = '42501';
  end if;
  return new;
end $function$;
CREATE OR REPLACE FUNCTION public.notify_message()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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
    where x not in (select user_id from event_mutes where event_id = ev.id)
      and exists(select 1 from profiles p where p.id=x and private.is_member(p.id) and (
        private.user_has(p.id, 'events.manage_all') or ev.created_by=x
        or exists(select 1 from event_organizers where event_id=ev.id and user_id=x)
        or (ev.status in ('published','cancelled') and (ev.visibility='all'
          or exists(select 1 from event_invites where event_id=ev.id and user_id=x))))) loop
    select * into np from notification_prefs where user_id = u;
    if np.chat = 'all' or (np.chat = 'mentions' and (u = any (new.mentions) or u = reply_author)) then
      perform queue_notification(u, 'message', ev.id, ev.title, who || ' : ' || left(new.body, 140), null, jsonb_build_object('mentioned', u=any(new.mentions) or u=reply_author));
    end if;
  end loop;
  return null;
end $function$;
drop function if exists public.event_chat_state(uuid);
drop function if exists public.event_chat_people(uuid);
drop policy if exists "envoyer une photo dans un événement" on storage.objects;
drop policy if exists "voir les photos d'un événement" on storage.objects;
drop function if exists private.event_chat_writes(uuid);
drop function if exists private.event_chat_staff(uuid);
drop index if exists public.messages_pinned;
alter table public.messages drop constraint if exists messages_content;
delete from public.messages where length(body) < 1;
alter table public.messages drop constraint if exists messages_body_check;
alter table public.messages add constraint messages_body_check check (length(body) >= 1 and length(body) <= 4000);
alter table public.messages drop column if exists announcement;
alter table public.messages drop column if exists mention_present;
alter table public.messages drop column if exists mention_all;
alter table public.messages drop column if exists audio_seconds;
alter table public.messages drop column if exists audio_path;
alter table public.messages drop column if exists photo_path;
delete from supabase_migrations.schema_migrations where version = '20261116180000';
commit;
notify pgrst, 'reload schema';
