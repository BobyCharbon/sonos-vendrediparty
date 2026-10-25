select 'col' k, table_schema||'.'||table_name||'.'||column_name||' '||data_type||' '||coalesce(column_default,'')||' '||is_nullable v
  from information_schema.columns where table_schema in ('public','private')
union all select 'fn', n.nspname||'.'||p.proname||'('||pg_get_function_identity_arguments(p.oid)||') '||md5(pg_get_functiondef(p.oid))
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private') and p.prokind='f'
union all select 'pol', schemaname||'.'||tablename||' '||policyname||' '||cmd||' '||roles::text||' '||md5(coalesce(qual,'')||'|'||coalesce(with_check,''))
  from pg_policies where schemaname in ('public','private','storage')
union all select 'trg', n.nspname||'.'||c.relname||' '||t.tgname||' '||md5(pg_get_triggerdef(t.oid))
  from pg_trigger t join pg_class c on c.oid=t.tgrelid join pg_namespace n on n.oid=c.relnamespace
  where not t.tgisinternal and n.nspname in ('public','private','auth','storage')
union all select 'con', n.nspname||'.'||c.relname||' '||co.conname||' '||md5(pg_get_constraintdef(co.oid))
  from pg_constraint co join pg_class c on c.oid=co.conrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','private')
union all select 'idx', schemaname||'.'||indexname||' '||md5(indexdef) from pg_indexes where schemaname in ('public','private')
union all select 'grant', table_schema||'.'||table_name||' '||grantee||' '||privilege_type
  from information_schema.role_table_grants where table_schema in ('public','private') and grantee in ('anon','authenticated','service_role')
union all select 'colgrant', table_schema||'.'||table_name||'.'||column_name||' '||grantee||' '||privilege_type
  from information_schema.column_privileges where table_schema='public' and grantee in ('anon','authenticated')
union all select 'fngrant', n.nspname||'.'||p.proname||' '||coalesce(array_to_string(p.proacl,','),'default')
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','private')
union all select 'enum', t.typname||' '||string_agg(e.enumlabel, ',' order by e.enumsortorder)
  from pg_type t join pg_enum e on e.enumtypid=t.oid group by t.typname
union all select 'cron', jobname||' '||schedule||' '||md5(command) from cron.job
union all select 'bucket', id||' public='||public||' '||coalesce(file_size_limit::text,'')||' '||coalesce(array_to_string(allowed_mime_types,','),'') from storage.buckets
union all select 'ext', extname from pg_extension
union all select 'rls', n.nspname||'.'||c.relname||' '||c.relrowsecurity||' '||c.relforcerowsecurity
  from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','private') and c.relkind='r'
union all select 'view', schemaname||'.'||viewname||' '||md5(definition) from pg_views where schemaname in ('public','private')
order by 1,2;
