-- Tout l'événement en temps réel (avis de l'admin du 16.11 : « n'importe quel élément changé dans l'événement »).
--
-- Le temps réel par tables (postgres_changes) laissait des trous :
--   * les SUPPRESSIONS filtrées n'arrivent pas (vote de date ou de sondage retiré, « J'amène » retiré, réaction retirée…) ;
--   * des tables n'y sont pas : sondages et leurs choix, demandes « À accepter », annonces aux groupes, étiquettes,
--     invitations par numéro ; les notes de présence et réactions n'étaient pas écoutées par la fiche.
-- Ici : tout changement d'une table de l'événement envoie UN signal « changed » sur le canal public `event:<id>`
-- (realtime.send, sans contenu : seulement « relis »), une fois par transaction et par événement. La fiche, la discussion
-- et l'étape « Qui est invité » l'écoutent (useLivePing) et se relisent aussitôt.
-- Bar, billets et covoiturage gardent leurs signaux par personne (live_pings, migration 20261116110000) : un verre servi
-- ne fait pas relire la fiche de tous les invités.
-- Liste des événements et droits (même avis : « je donne Membre VIP à quelqu'un, il voit aussitôt tous les événements ») :
--   * canal `events` : un événement créé, modifié, supprimé, ses groupes, invitations ou réponses → les listes se relisent ;
--   * canal `user:<id>` : le rôle, le statut ou les groupes de CETTE personne changent → ses droits et sa liste se relisent ;
--   * canal `access` : les droits d'un rôle changent (Rôles et droits) → tout le monde relit ses droits.
-- Purement additive et rejouable.

-- Un signal « changed » (sans contenu) sur un canal public, une fois par transaction et par canal.
create or replace function private.party_signal(topic text) returns void
language plpgsql security definer set search_path = public, pg_temp as $$
declare sent text;
begin
  if topic is null then return; end if;
  sent := coalesce(current_setting('party.signals', true), '');
  if position('|' || topic || '|' in sent) > 0 then return; end if;
  perform set_config('party.signals', sent || '|' || topic || '|', true);
  perform realtime.send('{}'::jsonb, 'changed', topic, false);
exception when others then
  null;  -- un signal perdu ne doit jamais faire échouer le changement (la relecture régulière reste en secours)
end $$;
revoke all on function private.party_signal(text) from public, anon, authenticated;

create or replace function private.event_changed() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  r jsonb;
  e uuid;
begin
  if tg_op = 'DELETE' then r := to_jsonb(old); else r := to_jsonb(new); end if;
  begin
    e := case tg_table_name
      when 'events' then (r->>'id')::uuid
      when 'poll_options' then (select p.event_id from polls p where p.id = (r->>'poll_id')::uuid)
      when 'poll_votes' then (select p.event_id from polls p where p.id = (r->>'poll_id')::uuid)
      when 'date_votes' then (select o.event_id from date_options o where o.id = (r->>'option_id')::uuid)
      when 'bring_claims' then (select b.event_id from bring_items b where b.id = (r->>'item_id')::uuid)
      when 'message_reactions' then (select m.event_id from messages m where m.id = (r->>'message_id')::uuid)
      else (r->>'event_id')::uuid
    end;
    if e is not null then perform private.party_signal('event:' || e::text); end if;
    -- Ce qui change la liste des événements (apparaît, disparaît, change de titre ou de date, réponses).
    if tg_table_name in ('events', 'event_groups', 'event_invites', 'rsvps') then perform private.party_signal('events'); end if;
  exception when others then
    null;
  end;
  return null;
end $$;
revoke all on function private.event_changed() from public, anon, authenticated;

-- Rôle, statut, groupes d'une personne ; droits des rôles.
create or replace function private.access_changed() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if tg_op = 'DELETE' then r := to_jsonb(old); else r := to_jsonb(new); end if;
  begin
    if tg_table_name = 'profiles' then
      if tg_op = 'UPDATE' and old.role is not distinct from new.role and old.status is not distinct from new.status then
        return null;
      end if;
      perform private.party_signal('user:' || (r->>'id'));
    elsif tg_table_name = 'member_group_members' then
      perform private.party_signal('user:' || (r->>'user_id'));
    else
      perform private.party_signal('access');
    end if;
  exception when others then
    null;
  end;
  return null;
end $$;
revoke all on function private.access_changed() from public, anon, authenticated;

do $$
declare t text;
begin
  foreach t in array array['events', 'rsvps', 'rsvp_notes', 'date_options', 'date_votes', 'polls', 'poll_options',
    'poll_votes', 'bring_items', 'bring_claims', 'messages', 'message_reactions', 'event_organizers', 'event_invites',
    'event_groups', 'event_tags', 'event_join_requests', 'event_announcements', 'event_phone_invites'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists event_changed on public.%I', t);
      execute format('create trigger event_changed after insert or update or delete on public.%I '
        'for each row execute function private.event_changed()', t);
    end if;
  end loop;
end $$;

do $$
declare t text;
begin
  foreach t in array array['profiles', 'member_group_members', 'role_permissions', 'roles'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists access_changed on public.%I', t);
      execute format('create trigger access_changed after insert or update or delete on public.%I '
        'for each row execute function private.access_changed()', t);
    end if;
  end loop;
end $$;
