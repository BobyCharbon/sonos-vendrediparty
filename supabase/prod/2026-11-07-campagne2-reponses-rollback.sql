-- PROD, retour arrière de campagne2_reponses (20261107110000) : fonctions d'avant (liste d'attente, réponses, dates,
-- page publique, signalements), petits mots remis dans rsvps.note, déclencheurs / fonctions / tâche ajoutés retirés,
-- signalements des nouveaux types (petit mot, sondage, objet) supprimés. Tout ou rien.
-- Ne rend PAS le texte des messages du forum supprimés (effacé volontairement). La clé « storage_secret_key » du
-- coffre, si elle a été ajoutée, se retire à part : delete from vault.secrets where name = 'storage_secret_key';
begin;
-- 1. Les petits mots reviennent dans rsvps.note (gardes coupées : seule cette colonne change).
drop trigger if exists rsvps_note_private on public.rsvps;
drop trigger if exists rsvps_note_forget on public.rsvps;
do $$
begin
  if to_regclass('public.rsvp_notes') is not null then
    alter table public.rsvps disable trigger rsvps_guard;
    alter table public.rsvps disable trigger rsvps_set_by;
    update public.rsvps r set note = n.note from public.rsvp_notes n where n.event_id = r.event_id and n.user_id = r.user_id;
    alter table public.rsvps enable trigger rsvps_guard;
    alter table public.rsvps enable trigger rsvps_set_by;
  end if;
end $$;

-- 2. Fonctions d'avant.
CREATE OR REPLACE FUNCTION public.apply_waitlist(e uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare ev events; taken int := 0; fit int; r record; prev text; body text; wants boolean;
begin
  prev := coalesce(current_setting('party.applying_waitlist', true), '');
  perform set_config('party.applying_waitlist', 'on', true);
  select * into ev from events where id = e;
  if ev.max_participants is null then
    update rsvps set waitlisted = false, plus_ones = plus_ones + plus_ones_waitlisted,
                     plus_ones_waitlisted = 0, plus_ones_waitlisted_since = null
      where event_id = e and (waitlisted or plus_ones_waitlisted > 0);
    perform set_config('party.applying_waitlist', prev, true);
    return;
  end if;

  for r in select * from rsvps where event_id = e and status = 'yes' and not waitlisted order by updated_at, user_id loop
    if taken + 1 > ev.max_participants then
      update rsvps set waitlisted = true, plus_ones = r.plus_ones + r.plus_ones_waitlisted,
                       plus_ones_waitlisted = 0, plus_ones_waitlisted_since = null
        where event_id = e and user_id = r.user_id;
    else
      fit := least(r.plus_ones, ev.max_participants - taken - 1);
      taken := taken + 1 + fit;
      if fit < r.plus_ones then
        update rsvps set plus_ones = fit, plus_ones_waitlisted = r.plus_ones_waitlisted + r.plus_ones - fit,
                         plus_ones_waitlisted_since = coalesce(r.plus_ones_waitlisted_since, now())
          where event_id = e and user_id = r.user_id;
      end if;
    end if;
  end loop;

  for r in
    select q.* from (
      select x.user_id, true as person, x.updated_at as since, x.plus_ones as n
        from rsvps x where x.event_id = e and x.status = 'yes' and x.waitlisted
      union all
      select x.user_id, false, x.plus_ones_waitlisted_since, x.plus_ones_waitlisted
        from rsvps x where x.event_id = e and x.status = 'yes' and not x.waitlisted and x.plus_ones_waitlisted > 0
    ) q order by q.since nulls last, q.person desc, q.user_id
  loop
    exit when taken >= ev.max_participants;
    if r.person then
      fit := least(r.n, ev.max_participants - taken - 1);
      taken := taken + 1 + fit;
      update rsvps set waitlisted = false, plus_ones = fit, plus_ones_waitlisted = r.n - fit,
                       plus_ones_waitlisted_since = case when r.n > fit then r.since end
        where event_id = e and user_id = r.user_id;
      body := 'Tu es inscrit à « ' || ev.title || ' ».'
        || case when r.n > fit then ' ' || case when r.n - fit > 1 then 'Tes accompagnants restent' else 'Ton accompagnant reste' end
                || ' en liste d''attente.' else '' end;
    else
      fit := least(r.n, ev.max_participants - taken);
      taken := taken + fit;
      update rsvps set plus_ones = plus_ones + fit, plus_ones_waitlisted = plus_ones_waitlisted - fit,
                       plus_ones_waitlisted_since = case when plus_ones_waitlisted - fit > 0 then plus_ones_waitlisted_since end
        where event_id = e and user_id = r.user_id;
      body := case when fit > 1 then 'Tes ' || fit || ' accompagnants sont inscrits' else 'Ton accompagnant est inscrit' end
        || ' à « ' || ev.title || ' ».';
    end if;
    -- since = now() : réponse ou accompagnant donné dans cette transaction, pas une vraie attente.
    select p.waitlist into wants from notification_prefs p where p.user_id = r.user_id;
    if r.since < now() and coalesce(wants, false) then
      perform queue_notification(r.user_id, 'waitlist', e, 'Une place s''est libérée', body);
    end if;
  end loop;
  perform set_config('party.applying_waitlist', prev, true);
end $function$
;

CREATE OR REPLACE FUNCTION public.do_fix_event_date(e uuid, opt uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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
end $function$
;

CREATE OR REPLACE FUNCTION public.fix_event_date(e uuid, opt uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
begin
  if not (is_admin() or is_organizer(e)) then raise exception 'Réservé à l''organisateur'; end if;
  perform do_fix_event_date(e, opt);
end $function$
;

CREATE OR REPLACE FUNCTION public.guard_rsvp()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare ev events; total int;
begin
  if current_setting('party.applying_waitlist', true) = 'on' then
    return new; -- apply_waitlist range la file (places, accompagnants qui montent)
  end if;
  if tg_op = 'UPDATE' and new.status = old.status and new.plus_ones = old.plus_ones
     and new.plus_ones_waitlisted = old.plus_ones_waitlisted and new.note is not distinct from old.note then
    return new; -- seul `waitlisted` change
  end if;
  select * into ev from events where id = new.event_id;
  if new.status = 'maybe' and not ev.allow_maybe then raise exception 'Réponse « Peut-être » désactivée'; end if;
  -- Accompagnants voulus = confirmés + en attente.
  total := greatest(0, coalesce(new.plus_ones, 0) + coalesce(new.plus_ones_waitlisted, 0));
  if not ev.allow_plus_ones or (auth.uid() is not null and not has_perm('events.plus_ones')) then total := 0;
  else total := least(total, ev.max_plus_ones); end if;
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline and auth.uid() is not null
     and not is_admin() and not is_organizer(new.event_id) then
    raise exception 'La date limite de réponse est passée';
  end if;
  -- Rang (05.11) : seulement à la réponse donnée (création ou changement de statut), pas pour un mot ou un accompagnant.
  if tg_op = 'INSERT' or new.status <> old.status then new.updated_at := now(); end if;
  if new.status <> 'yes' then
    -- Attente (05.11) : seul un Présent est en liste d'attente ; Peut-être / Absent ne le sont jamais.
    -- Peut-être / Absent ne vient pas accompagné : les accompagnants (confirmés ou en attente) sont retirés pour de bon,
    -- un retour à Présent ne les fait jamais revenir (la carte de la liste n'envoie pas la colonne d'attente).
    new.waitlisted := false;
    new.plus_ones := 0; new.plus_ones_waitlisted := 0; new.plus_ones_waitlisted_since := null;
  elsif tg_op = 'INSERT' or old.status <> 'yes' or old.waitlisted then
    -- Nouveau Présent (apply_waitlist décide) ou réponse encore en attente : ses accompagnants attendent avec elle.
    if tg_op = 'INSERT' or old.status <> 'yes' then new.waitlisted := true; end if;
    new.plus_ones := total; new.plus_ones_waitlisted := 0; new.plus_ones_waitlisted_since := null;
  elsif total > old.plus_ones then
    -- Présent confirmé qui ajoute (05.11) : il garde sa place, les accompagnants de plus prennent la file
    -- (apply_waitlist les fait monter tout de suite s'il reste de la place).
    new.plus_ones := old.plus_ones;
    new.plus_ones_waitlisted := total - old.plus_ones;
    new.plus_ones_waitlisted_since := case when old.plus_ones_waitlisted > 0 then old.plus_ones_waitlisted_since else now() end;
  else
    -- Retirer : d'abord les accompagnants en attente, puis les confirmés (une place se libère).
    new.plus_ones := total; new.plus_ones_waitlisted := 0; new.plus_ones_waitlisted_since := null;
  end if;
  return new;
end $function$
;

CREATE OR REPLACE FUNCTION private.moderation_hide(r content_reports)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
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
  elsif r.target_kind = 'profile' then
    update public.profiles set display_name = 'Surnom masqué' where id = uid;
  elsif r.target_kind = 'profile_photo' then
    -- Le fichier se retire par l'API Storage (politique « modérateurs retirent une photo signalée ») : l'appli le fait.
    return jsonb_build_object('remove_photo', r.snapshot ->> 'photo_path');
  end if;
  return '{}'::jsonb;
end $function$
;

CREATE OR REPLACE FUNCTION private.notify_new_report()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare u uuid;
begin
  for u in select p.id from public.profiles p where p.status = 'active' and private.user_has(p.id, 'moderation.reports') loop
    perform public.queue_notification(u, 'report_new', null, 'Nouveau signalement',
      (case new.reason when 'harassment' then 'Harcèlement' when 'shocking' then 'Contenu choquant' when 'spam' then 'Spam'
                       when 'scam' then 'Arnaque ou vente' else 'Autre raison' end)
      || ' · ' || (case when new.target_kind in ('group_message', 'direct_message', 'event_message') then 'un message'
                        when new.target_kind = 'profile' then 'un profil' when new.target_kind = 'profile_photo' then 'une photo de profil'
                        when new.target_kind = 'event' then 'un événement'
                        else 'Zicou' end),
      'report:' || new.id, jsonb_build_object('report_id', new.id));
  end loop;
  return null;
end $function$
;

CREATE OR REPLACE FUNCTION public.public_event(e uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'price_chf', ev.price_chf, 'allow_maybe', ev.allow_maybe, 'rsvp_deadline', ev.rsvp_deadline,
    'max_participants', ev.max_participants,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones, 'note', r.note)
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$function$
;

CREATE OR REPLACE FUNCTION private.report_snapshot(p_kind text, p_id text, viewer uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare gm public.group_messages; dm public.direct_messages; em public.messages; p public.profiles; ev public.events; uid uuid;
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
  elsif p_kind in ('profile', 'profile_photo') then
    select * into p from public.profiles where id = uid and status = 'active';
    if p.id is null then return null; end if;
    return jsonb_build_object('owner', p.id, 'text', p.display_name,
      'photo_path', case when p_kind = 'profile_photo' then p.avatar_url end, 'place', 'Profil');
  end if;
  return null;
end $function$
;


-- 3. Signalements des nouveaux types, puis contrainte d'avant.
delete from public.content_reports where target_kind in ('rsvp_note', 'poll', 'poll_option', 'bring_item');
alter table public.content_reports drop constraint if exists content_reports_target_kind_check;
alter table public.content_reports add constraint content_reports_target_kind_check
  check (target_kind in ('group_message', 'direct_message', 'event_message', 'profile', 'profile_photo', 'event',
                         'pet_name', 'pet_item', 'pet_offer', 'pet_showcase', 'pet_word'));

-- 4. Déclencheurs, fonctions, table et tâche ajoutés.
drop trigger if exists date_options_guard on public.date_options;
drop trigger if exists messages_guard on public.messages;
drop trigger if exists polls_moderation on public.polls;
drop trigger if exists poll_options_moderation on public.poll_options;
drop trigger if exists bring_items_moderation on public.bring_items;
drop trigger if exists tc_event_deleted on public.events;
drop trigger if exists tc_forget_receipts on auth.users;
do $$
begin
  if exists (select 1 from cron.job where jobname = 'tc-receipts-purge') then
    perform cron.unschedule('tc-receipts-purge');
  end if;
end $$;
drop table if exists public.rsvp_notes;
drop function if exists private.lock_event_places(uuid);
drop function if exists private.event_is_over(public.events);
drop function if exists private.guard_date_option();
drop function if exists private.item_text_verdict(text, text);
drop function if exists private.rsvp_note_private();
drop function if exists private.rsvp_note_forget();
drop function if exists private.guard_message_change();
drop function if exists private.moderate_event_item();
drop function if exists private.tc_event_deleted();
drop function if exists private.tc_forget_receipts_of_account();
drop function if exists private.tc_forget_receipts(uuid);
drop function if exists private.tc_purge_receipts();
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;
revoke all on function private.notify_new_report() from public, anon, authenticated;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;

delete from supabase_migrations.schema_migrations where version = '20261107110000';
commit;

notify pgrst, 'reload schema';
