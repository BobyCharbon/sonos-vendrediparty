-- Prod : 20261123090000 recherche_numero (formats de numéro suisses : +41 (0)79, +41 079, 79 …).
begin;
create or replace function private.search_phone(q text) returns text
language sql immutable set search_path = '' as $$
  select case
    when t !~ '^(\+|00)?[0-9][0-9 .()/-]{6,}$' then null
    when intl is not null then nullif(case when intl ~ '^410' and length(intl) = 12 then '41' || substr(intl, 4) else intl end, '')
    when d ~ '^0[1-9]' and length(d) = 10 then '41' || substr(d, 2)
    when d ~ '^[1-9]' and length(d) = 9 then '41' || d
    else d end
  from (select t, d, case when d ~ '^00' then substr(d, 3) when t ~ '^\+' then d end as intl
        from (select btrim(coalesce(q, '')) t, regexp_replace(coalesce(q, ''), '\D', '', 'g') d) x) y;
$$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261123090000', 'recherche_numero') on conflict do nothing;
commit;
