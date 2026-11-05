-- Liste d'attente juste (bugs trouvés au test du parcours participant, 05.11.2026).
-- 1) Le rang dans la liste d'attente (apply_waitlist trie par rsvps.updated_at) changeait dès qu'on touchait à sa
--    réponse : écrire un petit mot à l'organisateur, ou changer ses accompagnants, renvoyait en fin de file une
--    personne en attente (la place libérée allait à quelqu'un arrivé après). Désormais updated_at = moment où l'on a
--    donné CETTE réponse : il ne bouge qu'à la création ou quand le statut change.
-- 2) Un présent confirmé qui ajoutait un accompagnant alors que l'événement était complet passait lui-même en liste
--    d'attente (il perdait sa place, en silence). Décision de l'admin (05.11) : la personne GARDE sa place, seul
--    l'accompagnant de plus passe en liste d'attente ; il monte tout seul quand une place se libère, à son rang dans la
--    file (moment où il a été ajouté), avec la même notification « Une place s'est libérée » (interrupteur respecté).
--    De même, une personne qui monte avec plus d'accompagnants que de places monte seule : les autres attendent.
--      rsvps.plus_ones                  = accompagnants CONFIRMÉS (comptés partout : places, billets, pot, Wallet) ;
--      rsvps.plus_ones_waitlisted       = accompagnants en liste d'attente (comptés nulle part comme présents) ;
--      rsvps.plus_ones_waitlisted_since = leur rang dans la file.
--    L'app envoie le total voulu (plus_ones = total, plus_ones_waitlisted = 0) ; la garde le répartit.
-- 3) Une réponse Peut-être / Absent gardait « waitlisted » à vrai (insertion, ou passage par Présent en attente) :
--    l'app l'affichait « liste d'attente » et la cachait de « Qui vient ? ». Seul un Présent est désormais en attente.
-- Purement additive et rejouable (add column if not exists, create or replace, drop trigger if exists).

alter table public.rsvps add column if not exists plus_ones_waitlisted int not null default 0;
alter table public.rsvps add column if not exists plus_ones_waitlisted_since timestamptz;
-- L'app y écrit 0 avec le total dans plus_ones ; la garde recalcule toujours les deux (aucun moyen de sauter la file).
grant update (plus_ones_waitlisted) on public.rsvps to authenticated;

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

-- Places et liste d'attente, recalculées à chaque réponse :
-- 1) les présents confirmés gardent leur place, dans l'ordre (si les places ont été réduites : leurs accompagnants
--    passent d'abord en attente, puis la personne si même elle n'a plus de place) ;
-- 2) la file (personnes en attente ET accompagnants en attente, à leur rang) monte tant qu'il reste des places.
create or replace function public.apply_waitlist(e uuid) returns void
language plpgsql security definer set search_path = 'public' as $$
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
end $$;

create or replace function public.after_rsvp() returns trigger
language plpgsql security definer set search_path = 'public' as $$
begin
  if current_setting('party.applying_waitlist', true) = 'on' then return null; end if; -- déjà en cours
  perform apply_waitlist(coalesce(new.event_id, old.event_id));
  return null;
end $$;
drop trigger if exists rsvps_after on public.rsvps;
create trigger rsvps_after after insert or update of status, plus_ones, plus_ones_waitlisted or delete on public.rsvps
for each row execute function public.after_rsvp();

-- Réponses Peut-être / Absent restées « en attente » (affichées « liste d'attente », cachées de « Qui vient ? »).
update public.rsvps set waitlisted = false where waitlisted and status <> 'yes';
