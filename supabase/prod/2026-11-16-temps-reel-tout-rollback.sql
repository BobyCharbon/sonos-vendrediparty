-- Retour arrière de temps_reel_tout (20261116140000) : retire les déclencheurs et les fonctions de signal. Aucune donnée.
-- Les pages reviennent au temps réel par tables et à leur relecture régulière.
begin;
do $$
declare t text;
begin
  foreach t in array array['events', 'rsvps', 'rsvp_notes', 'date_options', 'date_votes', 'polls', 'poll_options',
    'poll_votes', 'bring_items', 'bring_claims', 'messages', 'message_reactions', 'event_organizers', 'event_invites',
    'event_groups', 'event_tags', 'event_join_requests', 'event_announcements', 'event_phone_invites'] loop
    if to_regclass('public.' || t) is not null then execute format('drop trigger if exists event_changed on public.%I', t); end if;
  end loop;
  foreach t in array array['profiles', 'member_group_members', 'role_permissions', 'roles'] loop
    if to_regclass('public.' || t) is not null then execute format('drop trigger if exists access_changed on public.%I', t); end if;
  end loop;
end $$;
drop function if exists private.event_changed();
drop function if exists private.access_changed();
drop function if exists private.party_signal(text);
delete from supabase_migrations.schema_migrations where version = '20261116140000';
commit;
