-- PROD, présences gérées par l'organisateur (20261026120000_rsvp_set_by_organizer).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod ») pour cette migration.
-- À coller tel quel dans Supabase → projet VendrediParty → SQL Editor → Run.
-- Tout-ou-rien : si une ligne échoue, rien n'est appliqué. Rejouable sans risque.
-- Retour arrière : 2026-10-26-presences-rollback.sql.
begin;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);

-- Présences gérées par l'organisateur : l'organisateur d'un événement (ou un admin) peut noter quelqu'un
-- Présent, Peut-être ou Absent, ou retirer sa réponse (ex. une personne qui ne vient finalement pas).
-- La réponse garde la trace de qui l'a posée (rsvps.set_by) ; elle redevient celle de la personne dès
-- qu'elle répond elle-même. La personne est prévenue et l'action est inscrite au journal des membres.
-- Purement additive et rejouable.

alter table public.rsvps add column if not exists set_by uuid references public.profiles (id) on delete set null;

-- Une réponse donnée par la personne elle-même efface la trace de l'organisateur
-- (et personne ne peut s'attribuer une réponse « posée par l'organisateur »).
create or replace function private.rsvp_set_by() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or auth.uid() = new.user_id then new.set_by := null; end if;
  return new;
end $$;
revoke all on function private.rsvp_set_by() from public, anon, authenticated;
drop trigger if exists rsvps_set_by on public.rsvps;
create trigger rsvps_set_by before insert or update on public.rsvps for each row execute function private.rsvp_set_by();

-- Date limite de réponse : l'organisateur peut encore corriger les présences le jour J (comme un admin).
create or replace function public.guard_rsvp() returns trigger
language plpgsql security definer set search_path = 'public' as $$
declare ev events;
begin
  if tg_op = 'UPDATE' and new.status = old.status and new.plus_ones = old.plus_ones
     and new.note is not distinct from old.note then
    return new; -- seul `waitlisted` change (apply_waitlist)
  end if;
  select * into ev from events where id = new.event_id;
  if new.status = 'maybe' and not ev.allow_maybe then raise exception 'Réponse « Peut-être » désactivée'; end if;
  if not ev.allow_plus_ones or (auth.uid() is not null and not has_perm('events.plus_ones')) then new.plus_ones := 0;
  else new.plus_ones := least(new.plus_ones, ev.max_plus_ones); end if;
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline and auth.uid() is not null
     and not is_admin() and not is_organizer(new.event_id) then
    raise exception 'La date limite de réponse est passée';
  end if;
  new.updated_at := now();
  if tg_op = 'INSERT' or old.status <> 'yes' then new.waitlisted := true; end if;
  return new;
end $$;

-- La personne voit-elle déjà l'événement sans nouvelle invitation ? (règle de can_see_event, pour un autre compte)
create or replace function private.sees_event_uninvited(ev public.events, member uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select (ev.visibility = 'all' and (ev.public_link or private.user_has(member, 'events.view')))
      or exists (select 1 from public.event_invites i where i.event_id = ev.id and i.user_id = member)
      or private.invited_by_phone(ev.id, member)
      or ev.created_by = member
      or exists (select 1 from public.event_organizers o where o.event_id = ev.id and o.user_id = member);
$$;
revoke all on function private.sees_event_uninvited(public.events, uuid) from public, anon, authenticated;

-- answer = null : retire la réponse.
create or replace function public.set_rsvp_for(event uuid, member uuid, answer public.rsvp_status) returns void
language plpgsql security definer set search_path = '' as $$
declare ev public.events; prev public.rsvps; who text;
begin
  if auth.uid() is null or not (public.is_admin() or public.is_organizer(event)) then
    raise exception 'Réservé à l''organisateur' using errcode = '42501';
  end if;
  select * into ev from public.events where id = event;
  if ev.id is null or ev.status <> 'published' then raise exception 'Cet événement n''est pas publié'; end if;
  if not private.is_account_active(member) then raise exception 'Ce compte n''existe pas ou n''est plus actif'; end if;
  select * into prev from public.rsvps where event_id = event and user_id = member;
  if prev.status is not distinct from answer then return; end if;

  if answer is null then
    delete from public.rsvps where event_id = event and user_id = member;
  else
    -- Noter quelqu'un qui ne voit pas l'événement (événement sur invitation) l'y invite.
    if answer <> 'no' and not private.sees_event_uninvited(ev, member) then
      insert into public.event_invites (event_id, user_id) values (event, member) on conflict do nothing;
    end if;
    insert into public.rsvps (event_id, user_id, status, plus_ones, set_by)
    values (event, member, answer, 0, auth.uid())
    on conflict (event_id, user_id) do update
      set status = excluded.status,
          plus_ones = case when excluded.status = 'yes' then public.rsvps.plus_ones else 0 end,
          set_by = excluded.set_by;
  end if;

  perform private.audit('event.rsvp_set', member, jsonb_build_object(
    'event', event, 'title', ev.title, 'from', prev.status, 'to', answer));
  who := coalesce(private.member_name(auth.uid()), 'L''organisateur');
  perform public.queue_notification(member, 'rsvp_set', event, ev.title,
    who || case answer when 'yes' then ' t''a noté présent' when 'maybe' then ' t''a noté peut-être'
                       when 'no' then ' t''a noté absent' else ' a retiré ta réponse' end);
end $$;
revoke all on function public.set_rsvp_for(uuid, uuid, public.rsvp_status) from public, anon;
grant execute on function public.set_rsvp_for(uuid, uuid, public.rsvp_status) to authenticated;

insert into supabase_migrations.schema_migrations (version, name, statements) values ('20261026120000', 'rsvp_set_by_organizer', array[]::text[]) on conflict do nothing;
commit;

-- Contrôle : la fonction et la colonne existent.
select (select count(*) from pg_proc where proname = 'set_rsvp_for') as fonction,
       (select count(*) from information_schema.columns where table_name = 'rsvps' and column_name = 'set_by') as colonne;
