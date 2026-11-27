-- Retour arrière de 2026-11-27-audit-compte-supprime-apply.sql : remet private.audit et private.audit_account_deleted
-- d'origine (20261025120000), retire le déclencheur AFTER, la purge pg_cron et les fonctions ajoutées.
-- Ne remet AUCUN nom, numéro ni appareil effacé (lignes anonymisées : définitif, voulu).
begin;
create or replace function private.audit(action text, target uuid, details jsonb default null) returns void
language sql security definer set search_path = '' as $$
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values (action, auth.uid(), private.member_name(auth.uid()), target, private.member_name(target), details);
$$;
create or replace function private.audit_account_deleted() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.member_audit (action, actor, actor_name, target, target_name, details)
  values ('account.deleted', auth.uid(), private.member_name(auth.uid()), old.id, private.member_name(old.id),
          jsonb_build_object('by', case when auth.uid() = old.id then 'self' else 'admin' end,
                             'phone_end', right(coalesce(old.phone, ''), 2)));
  return old;
end $$;
drop trigger if exists zz_audit_account_forget on auth.users;
drop function if exists private.audit_account_forget();
drop function if exists private.audit_forget(uuid);
select cron.unschedule('member-audit-tick') where exists (select 1 from cron.job where jobname = 'member-audit-tick');
drop function if exists private.member_audit_tick();
delete from supabase_migrations.schema_migrations where version = '20261127170000';
commit;
