-- Journal des membres et suppression du compte (recette réelle du 27.11, Apple 5.1.1(v) et (i)).
-- 1. Un compte supprimé ne laisse plus rien de personnel dans public.member_audit : son identifiant (actor / target)
--    est vidé, son surnom remplacé par « Compte supprimé », phone_end et device retirés. La trace « compte supprimé »
--    reste (account.deleted, { by: self | admin }). Fait APRÈS la suppression (déclencheur AFTER, passé les cascades qui
--    écrivent encore dans le journal, ex. group.remove), et rattrapé pour les comptes déjà supprimés.
-- 2. Les notifications d'autres comptes qui pointent vers la personne (data.member : « nouveau compte », « J'ai payé »)
--    partent avec elle. Les autres notifications déjà reçues restent chez leur destinataire jusqu'à 90 jours (politique).
-- 3. Journal gardé 12 mois (politique : « Journal des connexions et des actions d'administration : 12 mois ») :
--    pg_cron « member-audit-tick » efface chaque nuit les lignes plus anciennes.
-- Rejouable. Prod : supabase/prod/2026-11-27-audit-compte-supprime-apply.sql (+ rollback).

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

-- Lignes écrites PENDANT la suppression par les cascades (group.remove…), après le déclencheur AFTER : un compte qui
-- n'existe plus dans auth.users est écrit d'emblée « Compte supprimé », sans identifiant.
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

-- La trace de suppression n'écrit plus ni surnom ni fin de numéro.
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

-- Rattrapage : comptes déjà supprimés (identifiant absent d'auth.users) et fins de numéro déjà écrites.
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
