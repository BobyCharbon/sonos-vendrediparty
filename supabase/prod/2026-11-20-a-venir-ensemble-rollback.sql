-- Retour arrière de 20261120150000 : « À venir ensemble » liste de nouveau tout événement où la personne a une réponse.
begin;
do $$
declare src text := pg_get_functiondef('public.member_mini(uuid)'::regprocedure);
begin
  execute replace(src, 'private.chat_role(ev, p.id, me) in (''organizer'', ''yes'', ''maybe'')
            and private.chat_role(ev, me, me) in (''organizer'', ''yes'', ''maybe'')) y;', 'private.chat_role(ev, p.id, me) is not null) y;');
end $$;
delete from supabase_migrations.schema_migrations where version = '20261120150000';
commit;
