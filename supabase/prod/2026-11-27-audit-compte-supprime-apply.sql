-- PROD, journal des membres après la suppression d'un compte + purge à 12 mois (20261127170000, recette du 27.11, Apple 5.1.1(v)).
-- Testé sur TEST le 27.11 (tests/supabase_live/test_audit_compte_supprime_live.py, test_suppression_compte_cascade_live.py,
-- test_member_admin_live.py). Ancres : private.audit et private.audit_account_deleted identiques sur prod et TEST le 27.11
-- (md5 b8fefeed… / 572e8ded… ; après : a0997d96… / 522cf508…). Rejouable. IRRÉVERSIBLE pour les lignes anonymisées
-- (rattrapage des comptes déjà supprimés) : le retour arrière ne remet aucun nom ni numéro.
-- Retour arrière : 2026-11-27-audit-compte-supprime-rollback.sql.
begin;
do $check$
begin
  if md5(pg_get_functiondef('private.audit(text,uuid,jsonb)'::regprocedure)) not in
       ('b8fefeed8169d49d44f8f3499c0bb0e8', 'a0997d96cc6609e5d989f7cbe799cb62')
     or md5(pg_get_functiondef('private.audit_account_deleted()'::regprocedure)) not in
       ('572e8ded1f35f784558670d9e1a25637', '522cf508638cbab1305edd9311e38799') then
    raise exception 'audit / audit_account_deleted : définition inattendue en prod, rien n''est modifié';
  end if;
end $check$;

create or replace function private.audit_forget(member uuid) returns void
language sql security definer set search_path = '' as $$
  update public.member_audit a set
    actor = case when a.actor = member then null else a.actor end,
    actor_name = case when a.actor = member then 'Compte supprimé' else a.actor_name end,
    target = case when a.target = member then null else a.target end,
    target_name = case when a.target = member then 'Compte supprimé' else a.target_name end,
    details = case when a.details is null then null else a.details - 'phone_end' - 'device' end
  where a.actor = member or a.target = member;
$$;
revoke all on function private.audit_forget(uuid) from public, anon, authenticated;

create or replace function private.audit(action text, target uuid, details jsonb default null) returns void
language sql security definer set search_path = '' as $$
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  select action,
    case when gone_a then null else auth.uid() end,
    case when gone_a then 'Compte supprimé' else private.member_name(auth.uid()) end,
    case when gone_t then null else target end,
    case when gone_t then 'Compte supprimé' else private.member_name(target) end,
    details
  from (select auth.uid() is not null and not exists (select 1 from auth.users u where u.id = auth.uid()) gone_a,
               target is not null and not exists (select 1 from auth.users u where u.id = target) gone_t) g;
$$;
revoke all on function private.audit(text, uuid, jsonb) from public, anon, authenticated;

create or replace function private.audit_account_deleted() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values ('account.deleted', auth.uid(), private.member_name(auth.uid()), old.id, null,
          jsonb_build_object('by', case when auth.uid() = old.id then 'self' else 'admin' end));
  return old;
end $$;

create or replace function private.audit_account_forget() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform private.audit_forget(old.id);
  delete from public.notifications n where n.data ->> 'member' = old.id::text;
  return null;
end $$;
revoke all on function private.audit_account_forget() from public, anon, authenticated;
drop trigger if exists zz_audit_account_forget on auth.users;
create trigger zz_audit_account_forget after delete on auth.users
for each row execute function private.audit_account_forget();

do $catch$
declare m uuid;
begin
  for m in select x from (select a.actor x from public.member_audit a union select a.target from public.member_audit a) s
           where x is not null and not exists (select 1 from auth.users u where u.id = s.x) loop
    perform private.audit_forget(m);
  end loop;
  update public.member_audit set details = details - 'phone_end' where details ? 'phone_end';
end $catch$;

create or replace function private.member_audit_tick() returns void
language sql security definer set search_path = '' as $$
  delete from public.member_audit where at < now() - interval '12 months';
$$;
revoke all on function private.member_audit_tick() from public, anon, authenticated;
select cron.unschedule('member-audit-tick') where exists (select 1 from cron.job where jobname = 'member-audit-tick');
select cron.schedule('member-audit-tick', '41 4 * * *', 'select private.member_audit_tick();');
insert into supabase_migrations.schema_migrations (version, name) values ('20261127170000', 'audit_compte_supprime') on conflict do nothing;
commit;
