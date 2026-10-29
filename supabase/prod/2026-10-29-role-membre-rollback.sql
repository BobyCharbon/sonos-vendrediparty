-- PROD, retour arrière du rôle « Membre » (20261028200100) : les Membres repassent Guest, leurs droits sont retirés,
-- et les fonctions retrouvent leur version d'avant. La valeur basic reste dans le type (sans effet, Postgres ne
-- permet pas de la retirer simplement). Les règles de groupes (créer, voir les siens) restent : sans risque.
begin;
update public.profiles set role = 'guest' where role = 'basic';
delete from public.role_permissions where role = 'basic';
create or replace function private.role_rank(r public.member_role) returns integer
language sql immutable set search_path = '' as $$
  select case r when 'guest' then 0 when 'member' then 1 when 'organizer' then 2 when 'coadmin' then 3 when 'admin' then 4 end;
$$;
create or replace function public.decide_join_request(member uuid, accept boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_perm('members.approve') then raise exception 'forbidden: réservé à ceux qui valident les demandes' using errcode = '42501'; end if;
  if not exists (select 1 from public.join_requests where user_id = member and status = 'pending') then raise exception 'Cette demande a déjà été traitée'; end if;
  if accept then
    update public.profiles set role = 'member' where id = member and role = 'guest';
  end if;
  update public.join_requests set status = case when accept then 'accepted' else 'refused' end, decided_by = auth.uid(), decided_at = now()
  where user_id = member;
end;
$$;
delete from supabase_migrations.schema_migrations where version in ('20261028200000', '20261028200100');
commit;
