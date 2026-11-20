-- Retour arrière de 20261120090000 : « ne vient pas » notifie de nouveau l'organisateur.
begin;
do $$
declare src text := pg_get_functiondef('private.flush_rsvp_digests()'::regprocedure);
begin
  execute replace(src, ' and d.status in (''yes'', ''maybe'');', ';');
end $$;
do $$
declare src text := pg_get_functiondef('public.accept_invite(uuid, text, text)'::regprocedure);
begin
  execute replace(src, ') o where answer <> ''no'' loop', ') o loop');
end $$;
delete from supabase_migrations.schema_migrations where version = '20261120090000';
commit;
