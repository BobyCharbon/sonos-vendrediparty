-- Retour arrière de 20261122133000 : plus de suivi de l'origine des inscriptions (les origines notées sont effacées),
-- private.note_invite_join revient à sa version du 04.11 (« Invité par » seulement).
begin;
create or replace function private.note_invite_join(member uuid, inviter uuid, kind text, tgt uuid) returns void
language sql security definer set search_path = '' as $$
  insert into private.invite_joins (user_id, invited_by, via, target)
  select member, nullif(inviter, member), kind, tgt where member is not null
  on conflict do nothing;
$$;
revoke all on function private.note_invite_join(uuid, uuid, text, uuid) from public, anon, authenticated;
drop trigger if exists signup_from_link_arrival on private.invite_link_arrivals;
drop function if exists private.signup_from_link_arrival();
drop function if exists public.note_signup(text, uuid);
drop function if exists public.admin_signup_sources(uuid);
drop function if exists public.admin_signup_stats();
drop function if exists private.signup_line(public.profiles);
drop function if exists private.note_signup_source(uuid, text, uuid, uuid, uuid, text);
drop function if exists private.signup_rank(text);
drop table if exists private.signup_sources;
delete from public.role_permissions where perm = 'members.signup_source';
delete from public.permissions where key = 'members.signup_source';
delete from private.one_time_changes where name = 'members_signup_source_2026_11_22';
delete from supabase_migrations.schema_migrations where version = '20261122133000';
notify pgrst, 'reload schema';
commit;
