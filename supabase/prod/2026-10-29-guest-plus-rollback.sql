-- PROD, retour arrière de Guest+ et du droit « Écrire un avis » (20261029120100) : les Guest+ repassent Guest,
-- le droit disparaît (le serveur Party refuse alors les avis à tous les comptes : remettre l'ancien code avant).
-- La valeur guestplus reste dans le type (sans effet, Postgres ne permet pas de la retirer simplement).
begin;
update public.profiles set role = 'guest' where role = 'guestplus';
delete from public.role_permissions where role = 'guestplus' or perm = 'feedback.write';
delete from public.permissions where key = 'feedback.write';
delete from private.one_time_changes where name = 'guest_plus_feedback_2026_10_29';
create or replace function private.role_rank(r public.member_role) returns integer
language sql immutable set search_path = '' as $$
  select case r when 'guest' then 0 when 'basic' then 0 when 'member' then 1 when 'organizer' then 2 when 'coadmin' then 3 when 'admin' then 4 end;  -- rôle Membre gardé
$$;
delete from supabase_migrations.schema_migrations where version in ('20261029120000', '20261029120100');
commit;
