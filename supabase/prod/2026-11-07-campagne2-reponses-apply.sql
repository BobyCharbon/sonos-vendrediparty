-- PROD, campagne2_reponses (20261107110000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Corrections de la campagne 2 (réponses, liste d'attente, sondages, forum, modération, pot commun) : voir l'en-tête
-- de la migration ci-dessous. Prérequis (déjà en prod) : 20261104200000_moderation, 20261105143000_liste_attente_rang,
-- 20261105180000_signaler_evenement, 20261031150000_pot_commun_events. Rejouable. Tout ou rien.
-- APRÈS l'application (une seule fois, par l'admin, dans le SQL Editor de la PROD, avec la clé secrète du projet
-- « Settings › API Keys › Secret key ») pour que la purge des photos de tickets efface vraiment les fichiers :
--   select vault.create_secret('<clé secrète sb_secret_…>', 'storage_secret_key',
--     'Clé secrète (API Storage) : purge des photos de tickets orphelines');
-- Sans cette clé, la purge ne fait rien (aucune erreur) ; tout le reste marche.
-- Les textes des messages du forum déjà supprimés sont effacés (« • ») : le retour arrière ne peut pas les rendre.
begin;
-- Campagne 2 des bots (07.11.2026), lot « réponses, liste d'attente, sondages, forum, modération » (rapports 04, 05,
-- 06, 08). Tests : tests/supabase_live/test_campagne2_reponses_live.py.
--  1. Liste d'attente DÉSACTIVÉE : complet → « Présent » refusé (« C'est complet. »), personne n'est mis en attente.
--  2. Fixer une date quand « Peut-être » est désactivé : un vote « Si besoin » ne crée AUCUNE réponse (la personne
--     n'a pas dit « je viens » ; c'est le choix le plus sûr : ni place prise à sa place, ni Peut-être interdit) ; sans
--     liste d'attente, seuls les « Oui » qui tiennent dans les places sont inscrits. Date passée : refusée.
--  3. Surréservation : apply_waitlist prend un verrou par événement (pg_advisory_xact_lock) ; deux « Présent »
--     simultanés sur la dernière place ne peuvent plus être confirmés tous les deux.
--  4. Événement terminé (6 h après la fin, ou après le début sans fin : même règle que l'écran, lib/eventTime.ts) :
--     la personne ne change plus sa réponse ; l'organisateur / l'admin note encore les présences (set_rsvp_for).
--  5. Petit mot pour l'organisateur : rangé dans public.rsvp_notes, lu par la personne, l'organisation (créateur,
--     co-organisateurs) et les admins seulement ; filtré (insulte masquée, propos haineux refusés), CGU exigées,
--     signalable (type « rsvp_note »). rsvps.note reste la porte d'écriture (compatibilité) : le déclencheur range
--     le mot et vide la colonne. null = mot inchangé ; '' = mot effacé.
--  6. Forum : seul l'auteur réécrit son message ; un message supprimé perd son texte (« • ») ; épingler est réservé à
--     l'organisation (organisateur, co-organisateurs, admins).
--  7. Sondages (question, options) et « Qui amène quoi » : filtre, CGU, signalables (« poll », « poll_option »,
--     « bring_item »).
--  8. Sondage de dates : proposer une date passée refusé ; vote sur les dates clos → plus de nouvelle date (sauf
--     organisation) ; fixer une date passée refusé (fix_event_date ; la clôture automatique reste inchangée).
-- 10. Pot commun : supprimer un événement supprime son pot s'il est vide, sinon le clôt (archivé, dépenses gardées).
--     Photos de tickets : toute photo qui n'est plus rattachée à une dépense (dépense ou pot supprimé, compte supprimé,
--     photo jamais utilisée) depuis plus d'un jour est effacée par l'API Storage (tâche horaire tc-receipts-purge,
--     clé secrète « storage_secret_key » dans le coffre ; sans elle, rien n'est effacé). Le compte supprimé emporte
--     les photos des dépenses qu'il a créées.
-- Purement additive et rejouable : create table / index if not exists, create or replace, drop … if exists.

-- ------------------------------------------------------------------------------------------------------------------
-- 1 + 3. Liste d'attente : verrou par événement, et « complet » quand la liste d'attente est coupée
-- ------------------------------------------------------------------------------------------------------------------
create or replace function private.lock_event_places(e uuid) returns void
language sql security definer set search_path = '' as $$
  select pg_advisory_xact_lock(hashtextextended('party.event_places:' || e::text, 0));
$$;
revoke all on function private.lock_event_places(uuid) from public, anon, authenticated;

create or replace function public.apply_waitlist(e uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
declare ev events; taken int := 0; fit int; r record; prev text; body text; wants boolean;
begin
  -- Une seule transaction à la fois range les places d'un événement : la suivante attend, puis relit les réponses
  -- validées entre-temps (lecture validée : chaque requête voit les autres transactions terminées).
  perform private.lock_event_places(e);
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

  -- Liste d'attente coupée (07.11) : une réponse ou un accompagnant DONNÉ DANS CETTE TRANSACTION qui ne tient pas
  -- est refusé (rien n'est mis en attente). Ceux qui attendaient déjà (option coupée après coup, places réduites
  -- par l'organisateur) restent dans la file : on ne retire jamais quelqu'un sans le prévenir.
  if not ev.waitlist_enabled then
    if exists (select 1 from rsvps where event_id = e and status = 'yes' and waitlisted and updated_at = now()) then
      raise exception 'C''est complet.' using errcode = 'P0001';
    end if;
    if exists (select 1 from rsvps where event_id = e and status = 'yes' and plus_ones_waitlisted > 0
               and plus_ones_waitlisted_since = now()) then
      raise exception 'C''est complet : il n''y a plus de place pour un accompagnant.' using errcode = 'P0001';
    end if;
  end if;
  perform set_config('party.applying_waitlist', prev, true);
end $$;

-- ------------------------------------------------------------------------------------------------------------------
-- 4. Événement terminé : réponses closes pour la personne (l'organisation note encore les présences)
-- ------------------------------------------------------------------------------------------------------------------
-- Même règle que l'écran (web/events/src/lib/eventTime.ts, eventEnded) : terminé 6 h après la fin, ou après le début
-- s'il n'y a pas de fin ; un sondage de dates n'est jamais terminé.
create or replace function private.event_is_over(ev public.events) returns boolean
language sql stable security definer set search_path = '' as $$
  select ev.date_mode = 'fixed' and coalesce(ev.ends_at, ev.starts_at) is not null
     and now() > coalesce(ev.ends_at, ev.starts_at) + interval '6 hours';
$$;
revoke all on function private.event_is_over(public.events) from public, anon;
grant execute on function private.event_is_over(public.events) to authenticated;

create or replace function public.guard_rsvp() returns trigger
language plpgsql security definer set search_path = 'public' as $$
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
  -- Terminé (07.11) : la personne ne répond plus ; l'organisateur et l'admin notent encore les présences.
  if auth.uid() is not null and private.event_is_over(ev) and not is_admin() and not is_organizer(new.event_id) then
    raise exception 'Cet événement est terminé : les réponses sont closes.' using errcode = 'P0001';
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
end $$;

-- ------------------------------------------------------------------------------------------------------------------
-- 2 + 8. Fixer une date
-- ------------------------------------------------------------------------------------------------------------------
create or replace function public.do_fix_event_date(e uuid, opt uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
declare o date_options; ev events; v record;
begin
  perform private.lock_event_places(e);
  select * into o from date_options where id = opt and event_id = e;
  if not found then raise exception 'Créneau introuvable'; end if;
  update events set date_mode = 'fixed', starts_at = o.starts_at, ends_at = o.ends_at where id = e;
  select * into ev from events where id = e;
  for v in select dv.user_id, dv.vote from date_votes dv
           where dv.option_id = opt and dv.vote in ('yes', 'if_needed')
           order by (dv.vote = 'yes') desc, dv.user_id loop
    -- « Si besoin » sans « Peut-être » : aucune réponse (07.11), la personne répondra elle-même.
    continue when v.vote = 'if_needed' and not ev.allow_maybe;
    -- Sans liste d'attente : seuls les « Oui » qui tiennent dans les places sont inscrits.
    continue when v.vote = 'yes' and not ev.waitlist_enabled and ev.max_participants is not null
      and (select coalesce(sum(1 + r.plus_ones), 0) from rsvps r
           where r.event_id = e and r.status = 'yes' and not r.waitlisted) >= ev.max_participants;
    insert into rsvps (event_id, user_id, status)
    values (e, v.user_id, case v.vote when 'yes' then 'yes'::rsvp_status else 'maybe'::rsvp_status end)
    on conflict (event_id, user_id) do nothing;
  end loop;
  perform apply_waitlist(e);
end $$;

create or replace function public.fix_event_date(e uuid, opt uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
begin
  if not (is_admin() or is_organizer(e)) then raise exception 'Réservé à l''organisateur'; end if;
  if (select starts_at from date_options where id = opt and event_id = e) < now() then
    raise exception 'Cette date est déjà passée : choisis une date à venir.' using errcode = '22023';
  end if;
  perform do_fix_event_date(e, opt);
end $$;

create or replace function private.guard_date_option() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if (tg_op = 'INSERT' or new.starts_at is distinct from old.starts_at) and new.starts_at < now() then
    raise exception 'Cette date est déjà passée : propose une date à venir.' using errcode = '22023';
  end if;
  if tg_op = 'INSERT' and not (public.is_admin() or public.is_organizer(new.event_id))
     and exists (select 1 from public.events where id = new.event_id and poll_deadline is not null and poll_deadline <= now()) then
    raise exception 'Le vote sur les dates est clos.' using errcode = '22023';
  end if;
  return new;
end $$;
revoke all on function private.guard_date_option() from public, anon, authenticated;
drop trigger if exists date_options_guard on public.date_options;
create trigger date_options_guard before insert or update of starts_at on public.date_options
  for each row execute function private.guard_date_option();

-- ------------------------------------------------------------------------------------------------------------------
-- Filtre des petits textes (mot, sondage, objet) : insulte d'un mot masquée, propos haineux / sexuels refusés.
-- ------------------------------------------------------------------------------------------------------------------
create or replace function private.item_text_verdict(p_text text, p_what text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare v jsonb := private.moderation_verdict(p_text, 'message'); reason text;
begin
  if (v ->> 'ok')::boolean then return v ->> 'text'; end if;
  reason := case v ->> 'category' when 'haine' then 'des propos haineux' when 'sexuel' then 'un contenu sexuel'
                                  when 'insulte' then 'une insulte' else 'un mot interdit' end;
  raise exception 'content_refused: % non enregistré : il contient %. Les règles de Party l''interdisent.', p_what, reason
    using errcode = '23514';
end $$;
revoke all on function private.item_text_verdict(text, text) from public, anon, authenticated;

-- ------------------------------------------------------------------------------------------------------------------
-- 5. Petit mot pour l'organisateur
-- ------------------------------------------------------------------------------------------------------------------
create table if not exists public.rsvp_notes (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  note text not null check (char_length(note) between 1 and 500),
  updated_at timestamptz not null default now(),
  unique (event_id, user_id)
);
alter table public.rsvp_notes enable row level security;
drop policy if exists "petit mot : la personne et l'organisation" on public.rsvp_notes;
create policy "petit mot : la personne et l'organisation" on public.rsvp_notes for select to authenticated
  using (user_id = (select auth.uid()) or public.is_admin() or public.is_organizer(event_id));
revoke all on public.rsvp_notes from anon;
revoke insert, update, delete on public.rsvp_notes from authenticated;
grant select on public.rsvp_notes to authenticated;

-- Les mots déjà écrits passent dans la nouvelle table (une seule fois : la colonne est ensuite toujours vide).
insert into public.rsvp_notes (event_id, user_id, note)
select r.event_id, r.user_id, left(btrim(r.note), 500) from public.rsvps r where btrim(coalesce(r.note, '')) <> ''
on conflict (event_id, user_id) do nothing;
do $$
begin
  if exists (select 1 from public.rsvps where note is not null) then
    -- Seule la colonne du mot change : ni rang, ni places, ni « noté par » (déclencheurs de garde coupés le temps
    -- de cette mise à jour ; les autres ne regardent pas cette colonne).
    alter table public.rsvps disable trigger rsvps_guard;
    alter table public.rsvps disable trigger rsvps_set_by;
    update public.rsvps set note = null where note is not null;
    alter table public.rsvps enable trigger rsvps_guard;
    alter table public.rsvps enable trigger rsvps_set_by;
  end if;
end $$;

create or replace function private.rsvp_note_private() returns trigger
language plpgsql security definer set search_path = '' as $$
declare v text;
begin
  if new.note is null then return new; end if; -- null = mot inchangé
  v := btrim(new.note);
  new.note := null;
  if v = '' then
    delete from public.rsvp_notes where event_id = new.event_id and user_id = new.user_id;
    return new;
  end if;
  perform private.require_terms(new.user_id);
  v := private.item_text_verdict(left(v, 500), 'Mot');
  insert into public.rsvp_notes (event_id, user_id, note) values (new.event_id, new.user_id, v)
  on conflict (event_id, user_id) do update set note = excluded.note, updated_at = now();
  return new;
end $$;
revoke all on function private.rsvp_note_private() from public, anon, authenticated;
-- Après rsvps_guard (ordre alphabétique) : délai de réponse et fin d'événement d'abord.
drop trigger if exists rsvps_note_private on public.rsvps;
create trigger rsvps_note_private before insert or update on public.rsvps
  for each row execute function private.rsvp_note_private();

create or replace function private.rsvp_note_forget() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  delete from public.rsvp_notes where event_id = old.event_id and user_id = old.user_id;
  return null;
end $$;
revoke all on function private.rsvp_note_forget() from public, anon, authenticated;
drop trigger if exists rsvps_note_forget on public.rsvps;
create trigger rsvps_note_forget after delete on public.rsvps
  for each row execute function private.rsvp_note_forget();

-- Page publique (lien) : la personne retrouve son mot.
create or replace function public.public_event(e uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', ev.id, 'title', ev.title, 'description', ev.description, 'status', ev.status,
    'date_mode', ev.date_mode, 'starts_at', ev.starts_at, 'ends_at', ev.ends_at, 'all_day', ev.all_day,
    'location_name', ev.location_name, 'location_address', ev.location_address, 'location_url', ev.location_url,
    'price_chf', ev.price_chf, 'allow_maybe', ev.allow_maybe, 'rsvp_deadline', ev.rsvp_deadline,
    'max_participants', ev.max_participants,
    'going', (select coalesce(sum(1 + r.plus_ones), 0) from public.rsvps r where r.event_id = ev.id and r.status = 'yes' and not r.waitlisted),
    'mine', (select jsonb_build_object('status', r.status, 'waitlisted', r.waitlisted, 'plus_ones', r.plus_ones,
                                       'note', (select n.note from public.rsvp_notes n where n.event_id = ev.id and n.user_id = r.user_id))
             from public.rsvps r where r.event_id = ev.id and r.user_id = auth.uid()))
  from public.events ev
  where ev.id = e and ev.public_link and ev.visibility = 'all' and ev.status in ('published', 'cancelled');
$$;

do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'rsvp_notes') then
    alter publication supabase_realtime add table public.rsvp_notes;
  end if;
end $$;

-- ------------------------------------------------------------------------------------------------------------------
-- 6. Forum de l'événement
-- ------------------------------------------------------------------------------------------------------------------
create or replace function private.guard_message_change() returns trigger
language plpgsql security definer set search_path = '' as $$
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
end $$;
revoke all on function private.guard_message_change() from public, anon, authenticated;
-- messages_guard passe avant messages_moderation (ordre alphabétique des déclencheurs BEFORE).
drop trigger if exists messages_guard on public.messages;
create trigger messages_guard before insert or update on public.messages
  for each row execute function private.guard_message_change();

-- Les messages déjà supprimés perdent leur texte.
update public.messages set body = '•', mentions = '{}', pinned = false where deleted_at is not null and body <> '•';

-- ------------------------------------------------------------------------------------------------------------------
-- 7. Sondages et « Qui amène quoi » : CGU + filtre
-- ------------------------------------------------------------------------------------------------------------------
create or replace function private.moderate_event_item() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if tg_table_name = 'polls' then
    if tg_op = 'INSERT' then perform private.require_terms(coalesce(new.created_by, auth.uid())); end if;
    if tg_op = 'INSERT' or new.question is distinct from old.question then
      new.question := private.item_text_verdict(new.question, 'Sondage');
    end if;
  elsif tg_table_name = 'poll_options' then
    if tg_op = 'INSERT' then perform private.require_terms(coalesce(new.created_by, auth.uid())); end if;
    if tg_op = 'INSERT' or new.label is distinct from old.label then
      new.label := private.item_text_verdict(new.label, 'Choix');
    end if;
  elsif tg_table_name = 'bring_items' then
    if tg_op = 'INSERT' then perform private.require_terms(coalesce(new.added_by, auth.uid())); end if;
    if tg_op = 'INSERT' or new.label is distinct from old.label then
      new.label := private.item_text_verdict(new.label, 'Objet');
    end if;
  end if;
  return new;
end $$;
revoke all on function private.moderate_event_item() from public, anon, authenticated;
drop trigger if exists polls_moderation on public.polls;
create trigger polls_moderation before insert or update of question on public.polls
  for each row execute function private.moderate_event_item();
drop trigger if exists poll_options_moderation on public.poll_options;
create trigger poll_options_moderation before insert or update of label on public.poll_options
  for each row execute function private.moderate_event_item();
-- bring_items_guard (remet le libellé d'un participant) passe avant bring_items_moderation.
drop trigger if exists bring_items_moderation on public.bring_items;
create trigger bring_items_moderation before insert or update of label on public.bring_items
  for each row execute function private.moderate_event_item();

-- ------------------------------------------------------------------------------------------------------------------
-- 5 + 7. Signaler : petit mot, sondage, choix de sondage, objet à amener
-- ------------------------------------------------------------------------------------------------------------------
alter table public.content_reports drop constraint if exists content_reports_target_kind_check;
alter table public.content_reports add constraint content_reports_target_kind_check
  check (target_kind in ('group_message', 'direct_message', 'event_message', 'profile', 'profile_photo', 'event',
                         'rsvp_note', 'poll', 'poll_option', 'bring_item',
                         'pet_name', 'pet_item', 'pet_offer', 'pet_showcase', 'pet_word'));

create or replace function private.report_snapshot(p_kind text, p_id text, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare gm public.group_messages; dm public.direct_messages; em public.messages; p public.profiles; ev public.events; uid uuid;
        rn public.rsvp_notes; po public.polls; op public.poll_options; bi public.bring_items;
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
  elsif p_kind in ('profile', 'profile_photo') then
    select * into p from public.profiles where id = uid and status = 'active';
    if p.id is null then return null; end if;
    return jsonb_build_object('owner', p.id, 'text', p.display_name,
      'photo_path', case when p_kind = 'profile_photo' then p.avatar_url end, 'place', 'Profil');
  end if;
  return null;
end $$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;

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
                        when new.target_kind = 'rsvp_note' then 'un petit mot'
                        when new.target_kind in ('poll', 'poll_option') then 'un sondage'
                        when new.target_kind = 'bring_item' then 'un objet à amener'
                        else 'Zicou' end),
      'report:' || new.id, jsonb_build_object('report_id', new.id));
  end loop;
  return null;
end $$;
revoke all on function private.notify_new_report() from public, anon, authenticated;

-- « Masquer le contenu » : le mot, le choix ou l'objet est retiré ; la question d'un sondage est remplacée.
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
  elsif r.target_kind = 'profile_photo' then
    -- Le fichier se retire par l'API Storage (politique « modérateurs retirent une photo signalée ») : l'appli le fait.
    return jsonb_build_object('remove_photo', r.snapshot ->> 'photo_path');
  end if;
  return '{}'::jsonb;
end $$;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;

-- ------------------------------------------------------------------------------------------------------------------
-- 10. Pot commun : événement supprimé, photos de tickets
-- ------------------------------------------------------------------------------------------------------------------
create or replace function private.tc_event_deleted() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Pot vide : supprimé avec l'événement. Pot avec des dépenses : clos (archivé), les comptes entre amis restent.
  delete from public.tc_groups g where g.event_id = old.id
    and not exists (select 1 from public.tc_expenses x where x.group_id = g.id);
  update public.tc_groups set archived = true where event_id = old.id and not archived;
  return old;
end $$;
revoke all on function private.tc_event_deleted() from public, anon, authenticated;
drop trigger if exists tc_event_deleted on public.events;
create trigger tc_event_deleted before delete on public.events
  for each row execute function private.tc_event_deleted();

-- Compte supprimé : les photos des dépenses qu'il a créées partent (le fichier est effacé par la purge ci-dessous).
create or replace function private.tc_forget_receipts(who uuid) returns integer
language sql security definer set search_path = '' as $$
  with gone as (update public.tc_expenses set receipt_path = null
                where created_by = who and receipt_path is not null returning 1)
  select count(*)::int from gone;
$$;
revoke all on function private.tc_forget_receipts(uuid) from public, anon, authenticated;

create or replace function private.tc_forget_receipts_of_account() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.tc_forget_receipts(old.id);
  return old;
end $$;
revoke all on function private.tc_forget_receipts_of_account() from public, anon, authenticated;
drop trigger if exists tc_forget_receipts on auth.users;
create trigger tc_forget_receipts before delete on auth.users
  for each row execute function private.tc_forget_receipts_of_account();

-- Purge : chaque photo du bucket tc-receipts qui n'est plus rattachée à une dépense depuis plus d'un jour est effacée
-- par l'API Storage (un effacement SQL laisserait le fichier). Clé secrète du projet dans le coffre
-- (« storage_secret_key », à ajouter une fois par l'admin) ; sans elle, rien n'est effacé.
create or replace function private.tc_purge_receipts() returns integer
language plpgsql security definer set search_path = '' as $$
declare key text; base text; n int := 0; obj record;
begin
  select decrypted_secret into key from vault.decrypted_secrets where name = 'storage_secret_key' limit 1;
  select decrypted_secret into base from vault.decrypted_secrets where name = 'project_url' limit 1;
  if key is null or base is null then return 0; end if;
  for obj in
    select o.name from storage.objects o
    where o.bucket_id = 'tc-receipts' and o.created_at < now() - interval '1 day'
      and not exists (select 1 from public.tc_expenses x where x.receipt_path = o.name)
    order by o.created_at limit 200
  loop
    perform net.http_delete(url := base || '/storage/v1/object/tc-receipts/' || obj.name,
                            headers := jsonb_build_object('apikey', key));
    n := n + 1;
  end loop;
  return n;
end $$;
revoke all on function private.tc_purge_receipts() from public, anon, authenticated;

do $$
begin
  perform cron.schedule('tc-receipts-purge', '23 * * * *', 'select private.tc_purge_receipts();');
end $$;


insert into supabase_migrations.schema_migrations (version, name) values ('20261107110000', 'campagne2_reponses')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
