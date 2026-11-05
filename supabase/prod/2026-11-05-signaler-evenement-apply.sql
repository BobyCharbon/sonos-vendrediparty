-- PROD, signaler_evenement (20261105180000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- PRÉREQUIS : 2026-11-04-moderation (content_reports, moderation_verdict…) déjà appliquée en prod (elle-même après
-- messages-directs). Ajoute le type « event » aux signalements et le filtre sur le titre / la description des événements.
-- Rejouable. Tout ou rien.
begin;
-- Signaler un événement + filtre de contenu sur son titre et sa description (contrôle App Store du 05.11.2026, O2,
-- Apple 1.2). Le titre, la description et la photo d'un événement sont du contenu de membre, visible de tous les
-- comptes (et sans compte par le lien public) : on peut désormais le signaler (type « event ») et la base filtre
-- le titre et la description à la création et à chaque modification (même règle qu'un message : insulte d'un mot
-- masquée, propos haineux ou sexuels refusés ; liens et numéros permis, une description en contient souvent).
-- Prérequis : 20261104200000_moderation (content_reports, moderation_verdict, report_snapshot…).
-- Purement additive et rejouable : contrainte remplacée par une version plus large, fonctions en create or replace,
-- déclencheur en drop if exists / create.

-- 1. Le type « event » dans les signalements
alter table public.content_reports drop constraint if exists content_reports_target_kind_check;
alter table public.content_reports add constraint content_reports_target_kind_check
  check (target_kind in ('group_message', 'direct_message', 'event_message', 'profile', 'profile_photo', 'event',
                         'pet_name', 'pet_item', 'pet_offer', 'pet_showcase', 'pet_word'));

-- 2. Ce que voit le modérateur (copie au moment du signalement). Un événement est signalable par qui le voit :
--    invité, membre (public.can_see_event) ou toute personne connectée qui a son lien public.
create or replace function private.report_snapshot(p_kind text, p_id text, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
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
end $$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;

-- 3. Notification des modérateurs : « un événement »
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
                        when new.target_kind = 'event' then 'un événement'
                        else 'Zicou' end),
      'report:' || new.id, jsonb_build_object('report_id', new.id));
  end loop;
  return null;
end $$;
revoke all on function private.notify_new_report() from public, anon, authenticated;

-- 4. « Masquer le contenu » d'un événement : titre remplacé, description et photo retirées, lien public coupé.
--    L'événement reste (réponses, billets) ; l'annuler ou le supprimer reste une décision à part. Comme toute
--    modification de l'événement d'un autre, il faut aussi « Modifier ou annuler tous les événements ».
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
  elsif r.target_kind = 'profile' then
    update public.profiles set display_name = 'Surnom masqué' where id = uid;
  elsif r.target_kind = 'profile_photo' then
    -- Le fichier se retire par l'API Storage (politique « modérateurs retirent une photo signalée ») : l'appli le fait.
    return jsonb_build_object('remove_photo', r.snapshot ->> 'photo_path');
  end if;
  return '{}'::jsonb;
end $$;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;

-- 5. Filtre sur le titre et la description (web, app iOS, assistant IA : tous écrivent par PostgREST avec la session
--    de la personne). CGU exigées avant le premier événement (sans effet tant que « Exiger les CGU » est éteint).
--    Le système (cron, service) n'y passe pas. Nommé events_moderation : lancé après events_guard (ordre alphabétique
--    des déclencheurs BEFORE), donc created_by est déjà fixé.
create or replace function private.event_text_verdict(p_text text, p_part text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare v jsonb := private.moderation_verdict(p_text, 'message'); reason text;
begin
  if (v ->> 'ok')::boolean then return v ->> 'text'; end if;
  reason := case v ->> 'category' when 'haine' then 'des propos haineux' when 'sexuel' then 'un contenu sexuel'
                                  when 'insulte' then 'une insulte' else 'un mot interdit' end;
  raise exception 'content_refused: Événement non enregistré : % contient %. Les règles de Party l''interdisent.', p_part, reason
    using errcode = '23514';
end $$;
revoke all on function private.event_text_verdict(text, text) from public, anon, authenticated;

create or replace function private.moderate_event_text() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if tg_op = 'INSERT' then
    perform private.require_terms(new.created_by);
  end if;
  if tg_op = 'INSERT' or new.title is distinct from old.title then
    new.title := private.event_text_verdict(new.title, 'le titre');
  end if;
  if btrim(coalesce(new.description, '')) <> '' and (tg_op = 'INSERT' or new.description is distinct from old.description) then
    new.description := private.event_text_verdict(new.description, 'la description');
  end if;
  return new;
end $$;
revoke all on function private.moderate_event_text() from public, anon, authenticated;
drop trigger if exists events_moderation on public.events;
create trigger events_moderation before insert or update of title, description on public.events
  for each row execute function private.moderate_event_text();

insert into supabase_migrations.schema_migrations (version, name) values ('20261105180000', 'signaler_evenement')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
