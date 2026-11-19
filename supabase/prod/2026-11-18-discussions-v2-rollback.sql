-- PROD, retour arrière de discussions_v2 (20261118120000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
CREATE OR REPLACE FUNCTION private.group_admin(grp uuid, uid uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select uid is not null and (
    private.is_root(uid)
    or exists (select 1 from public.member_groups g where g.id = grp and g.created_by = uid)
    or (private.in_group_now(grp, uid) and (
          exists (select 1 from public.group_admins a where a.group_id = grp and a.user_id = uid)
          or private.rank_of(uid) >= private.role_rank('coadmin'))));  -- co-admins du site et au-dessus : admins d'office de leurs groupes
$function$;

CREATE OR REPLACE FUNCTION private.notify_direct_message()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare other uuid; who text; preview text;
begin
  other := private.direct_other(new.chat_id, new.user_id);
  if other is null or exists (select 1 from public.direct_chat_settings s
                              where s.chat_id = new.chat_id and s.user_id = other and s.notify = 'none') then
    return null;
  end if;
  select display_name into who from public.profiles where id = new.user_id;
  preview := case when new.body <> '' then left(new.body, 140) when new.audio_path is not null then '🎤 Message vocal' else '📷 Photo' end;
  insert into public.notifications (user_id, kind, event_id, title, body, data)
  values (other, 'direct_message', null, 'Nouveau message de ' || coalesce(nullif(btrim(who), ''), 'quelqu''un'), preview,
          jsonb_build_object('chat_id', new.chat_id, 'group_id', new.chat_id, 'direct', true, 'message_id', new.id,
                             'kind', 'direct_message'));
  return null;
end $function$;

CREATE OR REPLACE FUNCTION private.reads_group(grp uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select auth.uid() is not null and (private.in_group_now(grp, auth.uid())
    or (private.is_root(auth.uid()) and exists (select 1 from public.member_groups g where g.id = grp)));
$function$;

CREATE OR REPLACE FUNCTION public.edit_direct_message(msg uuid, new_body text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if btrim(coalesce(new_body, '')) = '' or char_length(new_body) > 2000 then raise exception 'Message vide ou trop long'; end if;
  update public.direct_messages set body = btrim(new_body), edited_at = now()
    where id = msg and user_id = auth.uid() and deleted_at is null;
  if not found then raise exception 'forbidden: tu ne peux modifier que tes messages' using errcode = '42501'; end if;
end $function$;

CREATE OR REPLACE FUNCTION public.edit_group_message(msg uuid, new_body text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
begin
  if btrim(coalesce(new_body, '')) = '' or char_length(new_body) > 2000 then raise exception 'Message vide ou trop long'; end if;
  update public.group_messages set body = btrim(new_body), edited_at = now()
    where id = msg and user_id = auth.uid() and deleted_at is null;
  if not found then raise exception 'forbidden: tu ne peux modifier que tes messages' using errcode = '42501'; end if;
end $function$;

CREATE OR REPLACE FUNCTION public.start_direct_chat(target uuid, contact_hash text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid(); a uuid; b uuid; chat uuid;
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if target is null or target = me then raise exception 'Choisis une autre personne' using errcode = '22023'; end if;
  a := least(me, target); b := greatest(me, target);
  select id into chat from public.direct_chats where user_a = a and user_b = b;
  if chat is not null then return chat; end if;  -- déjà ouverte : toujours accessible (l'historique reste lisible)
  if not private.is_account_active(target) or private.dm_blocked(me, target) or not private.dm_knows(me, target, contact_hash) then
    raise exception 'forbidden: tu ne peux pas écrire à cette personne' using errcode = '42501';
  end if;
  insert into public.direct_chats (user_a, user_b, created_by) values (a, b, me)
  on conflict (user_a, user_b) do nothing returning id into chat;
  if chat is null then select id into chat from public.direct_chats where user_a = a and user_b = b; end if;
  return chat;
end $function$;

drop trigger if exists direct_chat_settings_read on public.direct_chat_settings;

drop trigger if exists direct_chats_changed on public.direct_chats;

drop trigger if exists direct_messages_request on public.direct_messages;

drop trigger if exists direct_messages_request_notify on public.direct_messages;

drop trigger if exists group_chat_settings_read on public.group_chat_settings;

drop trigger if exists group_messages_card on public.group_messages;

drop trigger if exists member_groups_private_chat on public.member_groups;

delete from supabase_migrations.schema_migrations where version = '20261118120000';
commit;
