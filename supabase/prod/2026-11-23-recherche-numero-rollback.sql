-- Retour arrière de 20261123090000 : private.search_phone d'avant (20261122134000).
begin;
create or replace function private.search_phone(q text) returns text
language sql immutable set search_path = '' as $$
  select case
    when btrim(coalesce(q, '')) !~ '^(\+|00)?[0-9][0-9 .()/-]{6,}$' then null
    when d ~ '^00' then nullif(substr(d, 3), '')
    when d ~ '^0[1-9]' and length(d) = 10 then '41' || substr(d, 2)
    else d end
  from (select regexp_replace(coalesce(q, ''), '\D', '', 'g') d) x;
$$;
delete from supabase_migrations.schema_migrations where version = '20261123090000';
commit;
