-- PROD, retour arrière de 20261029170000 (liens et invitations) : les liens ne marchent plus, les invitations de
-- groupe en attente sont effacées. Les colonnes invite_token / via_link restent (sans effet) : aucune donnée perdue
-- pour les personnes déjà arrivées (elles gardent leur accès à l'événement ou au groupe).
begin;
drop function if exists public.answer_group_invitation(uuid, boolean);
drop function if exists public.my_group_invitations();
drop function if exists public.invite_to_group(uuid, uuid, text);
drop function if exists public.join_group_by_link(uuid);
drop function if exists public.group_invite_info(uuid);
drop function if exists public.group_invite_link(uuid, boolean);
drop function if exists public.join_event_by_link(uuid);
drop function if exists public.invite_event(uuid);
drop function if exists public.event_invite_link(uuid, boolean);
drop function if exists private.join_group(uuid, uuid);
drop function if exists private.manages_group(uuid);
drop function if exists private.manages_event(uuid);
drop table if exists private.group_invitations;
drop function if exists private.digits(text);
drop function if exists private.identity_complete(uuid);
drop function if exists public.revoke_invite_link(uuid);
drop function if exists public.my_invite_links(text, uuid);
drop function if exists public.create_invite_link(text, uuid);
drop function if exists private.claim_invite_link(uuid, text);
drop function if exists private.invite_link_target(uuid, text);
drop table if exists private.invite_links;
delete from supabase_migrations.schema_migrations where version = '20261029170000';
commit;
