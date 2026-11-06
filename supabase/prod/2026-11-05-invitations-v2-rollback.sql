-- PROD, retour arrière de invitations_v2 (20261105200000) : fonctions, tables et colonnes ajoutées retirées ;
-- private.may_receive_push redevient celle de la prod au 05.11.2026 (avant cette migration). Les liens « pour plusieurs »,
-- les relances et la liste des comptes invités minimaux sont PERDUS (les comptes eux-mêmes restent). Tout ou rien.
begin;
do $$ begin perform cron.unschedule('purge-light-invitees'); exception when others then null; end $$;
drop function if exists private.purge_light_invitees();
drop function if exists private.light_invitees_to_purge();
drop function if exists public.nudge_invite_link(uuid);
drop function if exists public.nudge_invitees(uuid, uuid[]);
drop function if exists public.remove_invitee(uuid, uuid);
drop function if exists public.invite_people(uuid, uuid[], uuid[]);
drop function if exists public.event_guest_list(uuid);
drop function if exists public.accept_invite(uuid, text, text);
drop function if exists public.invite_preview(uuid, boolean);
drop function if exists public.create_event_invite(uuid, int, timestamptz, text);
drop function if exists private.first_word(text);
drop function if exists private.has_app(uuid);
drop function if exists private.invite_link_state(private.invite_links);
drop function if exists private.nudged_today(uuid, uuid, uuid);
drop table if exists private.light_invitees;
drop table if exists private.invite_nudges;
alter table public.event_invites drop column if exists created_at;
alter table public.event_invites drop column if exists link_token;
alter table public.event_invites drop column if exists invited_by;
drop table if exists private.invite_link_arrivals;
alter table private.invite_links drop constraint if exists invite_links_label_len;
alter table private.invite_links drop constraint if exists invite_links_places;
alter table private.invite_links drop column if exists version;
alter table private.invite_links drop column if exists opened_at;
alter table private.invite_links drop column if exists label;
alter table private.invite_links drop column if exists uses;
alter table private.invite_links drop column if exists max_uses;
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join', 'referral_join', 'direct_message', 'moderation_notice', 'report_new')
        and private.is_account_active(uid));
$$;
delete from supabase_migrations.schema_migrations where version = '20261105200000';
commit;

notify pgrst, 'reload schema';
